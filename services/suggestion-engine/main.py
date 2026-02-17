"""
AI Suggestion Engine Service - Consumes transcripts, matches Ontario ACR Problem Codes,
extracts location via local LLM (Ollama), geocodes addresses, and publishes structured
suggestions with MPDS priority levels to Kafka.
"""

import os
import json
import logging
import sys
import time
import threading
import uuid
from collections import defaultdict
from datetime import datetime

import requests

from shared.kafka_client import create_consumer, create_producer
from shared.types import Transcript, Suggestion
from shared.acr_codes import ACR_PROBLEM_CODES

# Add parent directory to path to access shared module
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
sys.path.insert(0, parent_dir)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Maximum number of suggestions to return per transcript
MAX_SUGGESTIONS = 3

# Priority ordering for tie-breaking (higher severity first)
PRIORITY_RANK = {"Purple": 5, "Red": 4, "Orange": 3, "Yellow": 2, "Green": 1}

# ── Ollama / LLM configuration ──────────────────────────────────────────────
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")

LOCATION_EXTRACTION_PROMPT = """You are an emergency call location extractor. Given a transcript from a 911 emergency call, extract any location information mentioned.

Look for:
- Street addresses (e.g. "234 Columbia St")
- Intersections (e.g. "King and University")
- Landmarks or building names (e.g. "University of Waterloo", "Grand River Hospital")
- Area descriptions (e.g. "near the park on Weber Street")

Respond ONLY with a JSON object in this exact format, no other text:
{"location": "<extracted address or null if none found>", "confidence": <0.0 to 1.0>}

If no location is mentioned, respond with:
{"location": null, "confidence": 0.0}

Transcript:
"""

# In-memory transcript accumulator: session_id -> list of transcript texts
transcript_history: dict[str, list[str]] = defaultdict(list)

# Track which ACR codes have already been suggested per session to avoid duplicates
# Maps session_id -> set of incident_code strings
suggested_codes_by_session: dict[str, set[str]] = defaultdict(set)

# Nominatim geocoding config
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_HEADERS = {"User-Agent": "ERAS-EmergencyDispatch/1.0"}
# Bias geocoding toward Waterloo Region, Ontario
NOMINATIM_VIEWBOX = "-80.7,43.3,-80.3,43.6"


# ── Ollama helpers ───────────────────────────────────────────────────────────

def ensure_model_available() -> bool:
    """Pull the configured model if not already present. Blocks until complete."""
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=10)
        resp.raise_for_status()
        models = [m["name"] for m in resp.json().get("models", [])]
        base_model_name = OLLAMA_MODEL.split(":")[0]
        if any(base_model_name in m for m in models):
            logger.info(f"Model '{OLLAMA_MODEL}' already available")
            return True
    except Exception as e:
        logger.warning(f"Could not check models: {e}")

    logger.info(f"Pulling model '{OLLAMA_MODEL}' — this may take a few minutes on first run...")
    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/pull",
            json={"name": OLLAMA_MODEL},
            stream=True,
            timeout=900,
        )
        resp.raise_for_status()
        for line in resp.iter_lines():
            if line:
                try:
                    data = json.loads(line)
                    status = data.get("status", "")
                    if "error" in data:
                        logger.error(f"  Model pull error: {data['error']}")
                        return False
                    total = data.get("total", 0)
                    completed = data.get("completed", 0)
                    if total and completed:
                        pct = int(completed / total * 100)
                        logger.info(f"  Model pull: {status} ({pct}%)")
                    elif status:
                        logger.info(f"  Model pull: {status}")
                except json.JSONDecodeError:
                    pass
        logger.info(f"Model '{OLLAMA_MODEL}' pulled successfully")
        return True
    except requests.exceptions.Timeout:
        logger.error(f"Model pull timed out — run 'docker exec eras-ollama ollama pull {OLLAMA_MODEL}' manually")
        return False
    except Exception as e:
        logger.error(f"Failed to pull model '{OLLAMA_MODEL}': {e}", exc_info=True)
        return False


def extract_location(full_transcript: str) -> dict | None:
    """
    Call Ollama to extract location from the accumulated transcript text.
    Returns {"location": str, "confidence": float} or None on failure.
    """
    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": LOCATION_EXTRACTION_PROMPT + full_transcript,
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": 0.1,
                    "num_predict": 100,
                },
            },
            timeout=30,
        )
        resp.raise_for_status()
        raw_response = resp.json().get("response", "").strip()
        logger.info(f"Ollama raw response: {raw_response}")

        parsed = json.loads(raw_response)
        location = parsed.get("location")
        confidence = parsed.get("confidence", 0.0)

        if location and isinstance(location, str) and location.lower() != "null":
            return {"location": location, "confidence": float(confidence)}

        return None

    except requests.exceptions.ConnectionError:
        logger.warning("Ollama not reachable — skipping location extraction")
        return None
    except requests.exceptions.Timeout:
        logger.warning("Ollama request timed out — skipping location extraction")
        return None
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            logger.warning(
                f"Model '{OLLAMA_MODEL}' not found in Ollama — "
                f"run 'docker exec eras-ollama ollama pull {OLLAMA_MODEL}' to download it"
            )
        else:
            logger.warning(f"Ollama HTTP error: {e}")
        return None
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.warning(f"Could not parse Ollama response: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during location extraction: {e}", exc_info=True)
        return None


# ── Geocoding via Nominatim ──────────────────────────────────────────────────

def geocode_location(address: str) -> tuple[float, float] | None:
    """
    Geocode an address string using Nominatim (OpenStreetMap).
    Returns (lat, lon) or None. Rate-limited to respect Nominatim usage policy.
    """
    try:
        time.sleep(1.1)  # Nominatim requires max 1 req/sec
        resp = requests.get(
            NOMINATIM_URL,
            params={
                "q": address,
                "format": "json",
                "limit": 1,
                "viewbox": NOMINATIM_VIEWBOX,
                "bounded": 1,
                "countrycodes": "ca",
            },
            headers=NOMINATIM_HEADERS,
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json()

        if results and len(results) > 0:
            lat = float(results[0]["lat"])
            lon = float(results[0]["lon"])
            logger.info(f"Geocoded '{address}' -> ({lat}, {lon})")
            return (lat, lon)

        logger.info(f"No geocoding results for '{address}'")
        return None

    except Exception as e:
        logger.warning(f"Geocoding failed for '{address}': {e}")
        return None


# ── ACR keyword matching (existing logic) ────────────────────────────────────

def _score_code_against_text(text_lower: str, code_entry: dict) -> float:
    """
    Score how well a transcript matches a given ACR code entry.

    Multi-word phrases score higher than single-word matches to reward specificity.
    Returns a float score where 0.0 means no match.
    """
    score = 0.0
    matched_keywords = 0
    total_keywords = len(code_entry["keywords"])

    for keyword in code_entry["keywords"]:
        if keyword in text_lower:
            matched_keywords += 1
            word_count = len(keyword.split())
            score += word_count * 2.0

    if matched_keywords == 0:
        return 0.0

    coverage_bonus = (matched_keywords / total_keywords) * 1.0
    return score + coverage_bonus


def generate_suggestions(transcript: Transcript) -> list[Suggestion]:
    """
    Generate Ontario ACR Problem Code suggestions based on transcript content.
    Pure keyword matching — fast, no LLM calls.
    Skips ACR codes that have already been suggested for this session.
    """
    text_lower = transcript.text.lower()
    already_suggested = suggested_codes_by_session[transcript.session_id]

    scored = []
    for entry in ACR_PROBLEM_CODES:
        if entry["code"] in already_suggested:
            continue
        score = _score_code_against_text(text_lower, entry)
        if score > 0:
            scored.append((score, entry))

    if not scored:
        return []

    scored.sort(
        key=lambda item: (item[0], PRIORITY_RANK.get(item[1]["default_priority"], 0)),
        reverse=True,
    )

    max_score = scored[0][0]
    suggestions = []
    seen_codes = set()

    for score, entry in scored:
        if len(suggestions) >= MAX_SUGGESTIONS:
            break

        if entry["code"] in seen_codes:
            continue
        seen_codes.add(entry["code"])

        confidence = round(min(score / max(max_score, 1.0), 1.0), 2)
        if len(suggestions) > 0 and confidence < 0.3:
            break

        value = f"Code {entry['code']} - {entry['category']}: {entry['description']}"

        suggestions.append(Suggestion(
            id=str(uuid.uuid4()),
            session_id=transcript.session_id,
            suggestion_type="incident_code",
            value=value,
            timestamp=datetime.now(),
            incident_code=entry["code"],
            incident_code_description=entry["description"],
            incident_code_category=entry["category"],
            priority=entry["default_priority"],
            confidence=confidence,
        ))

    # Record these codes so they won't be suggested again for this session
    for s in suggestions:
        if s.incident_code:
            already_suggested.add(s.incident_code)

    return suggestions


def _publish_suggestion(suggestion: Suggestion, producer) -> None:
    """Serialize and publish a single suggestion to Kafka."""
    suggestion_dict = suggestion.model_dump()
    suggestion_dict['timestamp'] = suggestion_dict['timestamp'].isoformat()
    producer.send("suggestions", suggestion_dict)
    producer.flush()


def _location_update_worker(
    session_id: str,
    full_text: str,
    suggestion_ids: list[str],
    suggestions: list[Suggestion],
    producer,
) -> None:
    """
    Background thread: extract location via LLM, geocode it, and re-publish
    the suggestions with location data so the frontend can update the cards.
    """
    try:
        llm_result = extract_location(full_text)
        if not llm_result:
            logger.info(f"No location found in transcript for session {session_id}")
            return

        extracted_location = llm_result["location"]
        extracted_lat = None
        extracted_lon = None

        coords = geocode_location(extracted_location)
        if coords:
            extracted_lat, extracted_lon = coords

        logger.info(
            f"Extracted location for session {session_id}: "
            f"'{extracted_location}' -> ({extracted_lat}, {extracted_lon})"
        )

        for suggestion in suggestions:
            suggestion.extracted_location = extracted_location
            suggestion.extracted_lat = extracted_lat
            suggestion.extracted_lon = extracted_lon
            _publish_suggestion(suggestion, producer)
            logger.info(
                f"Published location update for suggestion {suggestion.id} "
                f"(location='{extracted_location}') for session: {session_id}"
            )

    except Exception as e:
        logger.error(f"Error in location extraction worker for session {session_id}: {e}", exc_info=True)


def process_transcript(transcript_data: dict, producer) -> None:
    """
    Process a single transcript: publish keyword-matched suggestions immediately,
    then kick off LLM location extraction in a background thread.
    """
    try:
        if isinstance(transcript_data.get('timestamp'), str):
            transcript_data['timestamp'] = datetime.fromisoformat(transcript_data['timestamp'])

        transcript = Transcript(**transcript_data)
        logger.info(f"Processing transcript for session: {transcript.session_id}")

        # Accumulate transcript text for this session
        transcript_history[transcript.session_id].append(transcript.text)
        full_text = " ".join(transcript_history[transcript.session_id])

        # Publish keyword-matched suggestions immediately (no location)
        suggestions = generate_suggestions(transcript)

        if not suggestions:
            logger.info(f"No suggestions generated for session: {transcript.session_id}")
            return

        for suggestion in suggestions:
            _publish_suggestion(suggestion, producer)
            logger.info(
                f"Published suggestion '{suggestion.value}' "
                f"(priority={suggestion.priority}, confidence={suggestion.confidence}) "
                f"for session: {transcript.session_id}"
            )

        # Run LLM location extraction in background thread — will re-publish
        # the same suggestions with location data when ready
        thread = threading.Thread(
            target=_location_update_worker,
            args=(
                transcript.session_id,
                full_text,
                [s.id for s in suggestions],
                suggestions,
                producer,
            ),
            daemon=True,
        )
        thread.start()

    except Exception as e:
        logger.error(f"Error processing transcript: {e}", exc_info=True)


def main():
    """Main function to run the AI suggestion engine service."""
    bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")

    logger.info("Initializing AI Suggestion Engine Service (Ontario ACR)...")
    logger.info(f"Loaded {len(ACR_PROBLEM_CODES)} ACR Problem Codes")
    logger.info(f"Connecting to Kafka at: {bootstrap_servers}")
    logger.info(f"Ollama URL: {OLLAMA_BASE_URL}, Model: {OLLAMA_MODEL}")

    # Pull LLM model on startup (blocking, tolerates failure)
    max_retries = 5
    for attempt in range(1, max_retries + 1):
        if ensure_model_available():
            break
        logger.warning(f"Model pull attempt {attempt}/{max_retries} failed, retrying in 10s...")
        time.sleep(10)
    else:
        logger.warning(
            "Could not pull LLM model after retries — "
            "location extraction will be unavailable until Ollama is ready"
        )

    try:
        consumer = create_consumer(
            topics=["transcripts"],
            group_id="suggestion-engine-service",
            bootstrap_servers=bootstrap_servers
        )

        producer = create_producer(bootstrap_servers=bootstrap_servers)

        logger.info("AI Suggestion Engine Service started. Waiting for transcripts...")

        for message in consumer:
            try:
                transcript_data = message.value
                process_transcript(transcript_data, producer)
            except Exception as e:
                logger.error(f"Error processing message: {e}", exc_info=True)
                continue

    except KeyboardInterrupt:
        logger.info("Shutting down AI Suggestion Engine Service...")
    except Exception as e:
        logger.error(f"Fatal error in AI Suggestion Engine Service: {e}", exc_info=True)
        raise
    finally:
        if 'consumer' in locals():
            consumer.close()
        if 'producer' in locals():
            producer.close()
        logger.info("AI Suggestion Engine Service stopped.")


if __name__ == "__main__":
    main()
