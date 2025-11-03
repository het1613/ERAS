"""
AI Suggestion Engine Service - Consumes transcripts, generates suggestions, and publishes to Kafka.
"""

import os
import logging
import sys
from datetime import datetime

from shared.kafka_client import create_consumer, create_producer
from shared.types import Transcript, Suggestion

# Add parent directory to path to access shared module
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
sys.path.insert(0, parent_dir)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def generate_suggestions(transcript: Transcript) -> list[Suggestion]:
    """
    Generate AI suggestions based on transcript content.
    
    Args:
        transcript: Transcript object containing transcribed text
        
    Returns:
        List of Suggestion objects
    """
    suggestions = []
    text_lower = transcript.text.lower()
    
    # Keyword-based suggestion rules
    # TODO: Use ML models or more sophisticated NLP.
    if "fire" in text_lower or "burning" in text_lower or "smoke" in text_lower:
        suggestions.append(Suggestion(
            session_id=transcript.session_id,
            suggestion_type="incident_code",
            value="10-70: Fire Alarm",
            timestamp=datetime.now()
        ))
    
    if "accident" in text_lower or "crash" in text_lower or "collision" in text_lower:
        suggestions.append(Suggestion(
            session_id=transcript.session_id,
            suggestion_type="incident_code",
            value="10-50: Accident",
            timestamp=datetime.now()
        ))
    
    if "medical" in text_lower or "ambulance" in text_lower or "heart" in text_lower or "chest pain" in text_lower:
        suggestions.append(Suggestion(
            session_id=transcript.session_id,
            suggestion_type="incident_code",
            value="10-33: Medical Emergency",
            timestamp=datetime.now()
        ))
    
    if "police" in text_lower or "theft" in text_lower or "robbery" in text_lower or "suspect" in text_lower:
        suggestions.append(Suggestion(
            session_id=transcript.session_id,
            suggestion_type="incident_code",
            value="10-13: Police Assistance",
            timestamp=datetime.now()
        ))
    
    if "urgent" in text_lower or "emergency" in text_lower or "immediate" in text_lower:
        suggestions.append(Suggestion(
            session_id=transcript.session_id,
            suggestion_type="alert",
            value="High Priority - Immediate Response Required",
            timestamp=datetime.now()
        ))
    
    return suggestions


def process_transcript(transcript_data: dict, producer) -> None:
    """
    Process a single transcript: generate suggestions and publish.
    
    Args:
        transcript_data: Dictionary containing transcript data
        producer: Kafka producer instance
    """
    try:
        # Parse transcript
        # Handle datetime conversion from ISO string
        if isinstance(transcript_data.get('timestamp'), str):
            transcript_data['timestamp'] = datetime.fromisoformat(transcript_data['timestamp'])
        
        transcript = Transcript(**transcript_data)
        logger.info(f"Processing transcript for session: {transcript.session_id}")
        
        # Generate suggestions
        suggestions = generate_suggestions(transcript)
        
        if not suggestions:
            logger.info(f"No suggestions generated for session: {transcript.session_id}")
            return
        
        # Publish each suggestion
        for suggestion in suggestions:
            suggestion_dict = suggestion.model_dump()
            suggestion_dict['timestamp'] = suggestion_dict['timestamp'].isoformat()
            
            producer.send("suggestions", suggestion_dict)
            producer.flush()
            
            logger.info(
                f"Published suggestion '{suggestion.value}' "
                f"for session: {transcript.session_id}"
            )
        
    except Exception as e:
        logger.error(f"Error processing transcript: {e}", exc_info=True)


def main():
    """Main function to run the AI suggestion engine service."""
    bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
    
    logger.info(f"Initializing AI Suggestion Engine Service...")
    logger.info(f"Connecting to Kafka at: {bootstrap_servers}")
    
    try:
        # Create Kafka consumer for transcripts topic
        consumer = create_consumer(
            topics=["transcripts"],
            group_id="suggestion-engine-service",
            bootstrap_servers=bootstrap_servers
        )
        
        # Create Kafka producer for suggestions topic
        producer = create_producer(bootstrap_servers=bootstrap_servers)
        
        logger.info("AI Suggestion Engine Service started. Waiting for transcripts...")
        
        # Continuously consume and process messages
        for message in consumer:
            try:
                # message.value is already deserialized by our custom deserializer
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

