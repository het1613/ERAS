"""
AI Suggestion Engine Service - Consumes transcripts, matches Ontario ACR Problem Codes,
extracts location via OpenAI GPT, geocodes addresses, and publishes structured
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
from openai import OpenAI

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

# ── OpenAI / GPT configuration ────────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1")

openai_client: OpenAI | None = None

LOCATION_EXTRACTION_SYSTEM_PROMPT = """You are an emergency call location extractor. Given a transcript from a 911 emergency call, extract any location information mentioned.

Look for:
- Street addresses (e.g. "234 Columbia St")
- Intersections (e.g. "King and University")
- Landmarks or building names (e.g. "University of Waterloo", "Grand River Hospital")
- Area descriptions (e.g. "near the park on Weber Street")

Respond ONLY with a JSON object in this exact format, no other text:
{"location": "<extracted address or null if none found>", "confidence": <0.0 to 1.0>}

If no location is mentioned, respond with:
{"location": null, "confidence": 0.0}"""

# In-memory transcript accumulator: session_id -> list of transcript texts
transcript_history: dict[str, list[str]] = defaultdict(list)

# Track which ACR codes have already been suggested per session to avoid duplicates
# Maps session_id -> set of incident_code strings
suggested_codes_by_session: dict[str, set[str]] = defaultdict(set)

# Track all published suggestions per session so location updates can re-publish them
# Maps session_id -> list of Suggestion objects
published_suggestions_by_session: dict[str, list] = defaultdict(list)

# Track the last extracted location per session to avoid redundant updates
last_location_by_session: dict[str, str] = {}

# Nominatim geocoding config
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_HEADERS = {"User-Agent": "ERAS-EmergencyDispatch/1.0"}
# Bias geocoding toward Waterloo Region, Ontario
NOMINATIM_VIEWBOX = "-80.7,43.3,-80.3,43.6"


# ── OpenAI helpers ────────────────────────────────────────────────────────────

def init_openai_client() -> bool:
    """Initialize the OpenAI client. Returns True if successful."""
    global openai_client
    if not OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY not set — location extraction will be unavailable")
        return False
    openai_client = OpenAI(api_key=OPENAI_API_KEY)
    logger.info(f"OpenAI client initialized (model: {OPENAI_MODEL})")
    return True


def extract_location(full_transcript: str) -> dict | None:
    """
    Call OpenAI GPT to extract location from the accumulated transcript text.
    Returns {"location": str, "confidence": float} or None on failure.
    """
    if not openai_client:
        logger.warning("OpenAI client not initialized — skipping location extraction")
        return None

    try:
        response = openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": LOCATION_EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": full_transcript},
            ],
            temperature=0.1,
            max_tokens=100,
            response_format={"type": "json_object"},
        )
        raw_response = response.choices[0].message.content.strip()
        logger.info(f"GPT raw response: {raw_response}")

        parsed = json.loads(raw_response)
        location = parsed.get("location")
        confidence = parsed.get("confidence", 0.0)

        if location and isinstance(location, str) and location.lower() != "null":
            return {"location": location, "confidence": float(confidence)}

        return None

    except Exception as e:
        logger.warning(f"OpenAI location extraction failed: {e}")
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

def _score_code_against_text(text_lower: str, code_entry: dict) -> tuple[float, list[dict]]:
    """
    Score how well a transcript matches a given ACR code entry.

    Multi-word phrases score higher than single-word matches to reward specificity.
    Returns (score, matched_evidence) where matched_evidence is a list of
    {keyword, score} dicts for display in the frontend.
    """
    score = 0.0
    matched_keywords = 0
    total_keywords = len(code_entry["keywords"])
    evidence = []

    for keyword in code_entry["keywords"]:
        if keyword in text_lower:
            matched_keywords += 1
            word_count = len(keyword.split())
            kw_score = word_count * 2.0
            score += kw_score
            evidence.append({"keyword": keyword, "score": round(kw_score, 2)})

    if matched_keywords == 0:
        return 0.0, []

    coverage_bonus = (matched_keywords / total_keywords) * 1.0
    return score + coverage_bonus, evidence


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
        score, evidence = _score_code_against_text(text_lower, entry)
        if score > 0:
            scored.append((score, entry, evidence))

    if not scored:
        return []

    scored.sort(
        key=lambda item: (item[0], PRIORITY_RANK.get(item[1]["default_priority"], 0)),
        reverse=True,
    )

    max_score = scored[0][0]
    suggestions = []
    seen_codes = set()

    for score, entry, evidence in scored:
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
            matched_evidence=evidence,
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
    producer,
) -> None:
    """
    Background thread: extract location via LLM, geocode it, and re-publish
    all pending suggestions for this session with updated location data.
    Skips if the extracted location is the same as the last one.
    """
    try:
        llm_result = extract_location(full_text)
        if not llm_result:
            logger.info(f"No location found in transcript for session {session_id}")
            return

        extracted_location = llm_result["location"]

        # Skip if location hasn't changed since last extraction
        if last_location_by_session.get(session_id) == extracted_location:
            logger.info(f"Location unchanged for session {session_id}, skipping update")
            return
        last_location_by_session[session_id] = extracted_location

        extracted_lat = None
        extracted_lon = None

        coords = geocode_location(extracted_location)
        if coords:
            extracted_lat, extracted_lon = coords

        logger.info(
            f"Extracted location for session {session_id}: "
            f"'{extracted_location}' -> ({extracted_lat}, {extracted_lon})"
        )

        location_confidence = llm_result.get("confidence", None)

        # Update ALL pending suggestions for this session
        suggestions = published_suggestions_by_session.get(session_id, [])
        for suggestion in suggestions:
            suggestion.extracted_location = extracted_location
            suggestion.extracted_lat = extracted_lat
            suggestion.extracted_lon = extracted_lon
            suggestion.location_confidence = location_confidence
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
    Location extraction runs on every transcript regardless of new suggestions,
    so updated addresses are always picked up.
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

        if suggestions:
            for suggestion in suggestions:
                _publish_suggestion(suggestion, producer)
                logger.info(
                    f"Published suggestion '{suggestion.value}' "
                    f"(priority={suggestion.priority}, confidence={suggestion.confidence}) "
                    f"for session: {transcript.session_id}"
                )
            # Track for future location updates
            published_suggestions_by_session[transcript.session_id].extend(suggestions)

        # Always run LLM location extraction in background — updates all
        # existing suggestions for this session if a new location is found
        if published_suggestions_by_session.get(transcript.session_id):
            thread = threading.Thread(
                target=_location_update_worker,
                args=(
                    transcript.session_id,
                    full_text,
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
    logger.info(f"OpenAI model: {OPENAI_MODEL}")

    # Initialize OpenAI client (tolerates missing key)
    init_openai_client()

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
