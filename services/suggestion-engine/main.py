"""
AI Suggestion Engine Service - Consumes transcripts, matches Ontario ACR Problem Codes,
and publishes structured suggestions with MPDS priority levels to Kafka.
"""

import os
import logging
import sys
import uuid
from datetime import datetime

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
            # Multi-word phrases get bonus weight for specificity
            score += word_count * 2.0

    if matched_keywords == 0:
        return 0.0

    # Normalize: fraction of keywords matched adds a small bonus
    coverage_bonus = (matched_keywords / total_keywords) * 1.0
    return score + coverage_bonus


def generate_suggestions(transcript: Transcript) -> list[Suggestion]:
    """
    Generate Ontario ACR Problem Code suggestions based on transcript content.

    Scans the transcript text against all ACR code keyword sets, scores each match,
    and returns the top matches with MPDS priority levels.
    """
    text_lower = transcript.text.lower()

    # Score every ACR code
    scored = []
    for entry in ACR_PROBLEM_CODES:
        score = _score_code_against_text(text_lower, entry)
        if score > 0:
            scored.append((score, entry))

    if not scored:
        return []

    # Sort by score descending, then by priority severity for tie-breaking
    scored.sort(
        key=lambda item: (item[0], PRIORITY_RANK.get(item[1]["default_priority"], 0)),
        reverse=True,
    )

    # Determine max score for confidence calculation
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
        # Only include lower-ranked matches if they're reasonably close
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

    return suggestions


def process_transcript(transcript_data: dict, producer) -> None:
    """
    Process a single transcript: generate suggestions and publish to Kafka.
    """
    try:
        if isinstance(transcript_data.get('timestamp'), str):
            transcript_data['timestamp'] = datetime.fromisoformat(transcript_data['timestamp'])

        transcript = Transcript(**transcript_data)
        logger.info(f"Processing transcript for session: {transcript.session_id}")

        suggestions = generate_suggestions(transcript)

        if not suggestions:
            logger.info(f"No suggestions generated for session: {transcript.session_id}")
            return

        for suggestion in suggestions:
            suggestion_dict = suggestion.model_dump()
            suggestion_dict['timestamp'] = suggestion_dict['timestamp'].isoformat()

            producer.send("suggestions", suggestion_dict)
            producer.flush()

            logger.info(
                f"Published suggestion '{suggestion.value}' "
                f"(priority={suggestion.priority}, confidence={suggestion.confidence}) "
                f"for session: {transcript.session_id}"
            )

    except Exception as e:
        logger.error(f"Error processing transcript: {e}", exc_info=True)


def main():
    """Main function to run the AI suggestion engine service."""
    bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")

    logger.info("Initializing AI Suggestion Engine Service (Ontario ACR)...")
    logger.info(f"Loaded {len(ACR_PROBLEM_CODES)} ACR Problem Codes")
    logger.info(f"Connecting to Kafka at: {bootstrap_servers}")

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
