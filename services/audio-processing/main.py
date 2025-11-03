"""
Audio Processing Service - Consumes audio chunks from Kafka, performs STT, and publishes transcripts.
"""

import os
import logging
import sys
from datetime import datetime

from shared.kafka_client import create_consumer, create_producer
from shared.types import AudioChunk, Transcript

# Add parent directory to path to access shared module
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
sys.path.insert(0, parent_dir)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def stt(audio_chunk: AudioChunk) -> str:
    """
    Speech-to-Text function.
    
    Args:
        audio_chunk: AudioChunk object containing audio data
        
    Returns:
        Transcribed text string
    """
    # TODO: Use a real STT service (e.g., Google Cloud Speech-to-Text, AWS Transcribe, or Whisper).
    transcript_text = f"Mock transcript for session {audio_chunk.session_id}. This is a placeholder transcript generated for demonstration purposes."
    
    logger.info(f"Generated mock transcript for session: {audio_chunk.session_id}")
    return transcript_text


def process_audio_chunk(chunk_data: dict, producer) -> None:
    """
    Process a single audio chunk: transcribe and publish transcript.
    
    Args:
        chunk_data: Dictionary containing audio chunk data
        producer: Kafka producer instance
    """
    try:
        # Parse audio chunk
        # Handle datetime conversion from ISO string
        if isinstance(chunk_data.get('timestamp'), str):
            chunk_data['timestamp'] = datetime.fromisoformat(chunk_data['timestamp'])
        
        audio_chunk = AudioChunk(**chunk_data)
        logger.info(f"Processing audio chunk for session: {audio_chunk.session_id}")
        
        # STT transcription
        transcript_text = stt(audio_chunk)
        
        # Create transcript object
        transcript = Transcript(
            session_id=audio_chunk.session_id,
            text=transcript_text,
            timestamp=datetime.now()
        )
        
        # Serialize and publish to Kafka
        transcript_dict = transcript.model_dump()
        transcript_dict['timestamp'] = transcript_dict['timestamp'].isoformat()
        
        producer.send("transcripts", transcript_dict)
        producer.flush()
        
        logger.info(f"Published transcript to Kafka for session: {audio_chunk.session_id}")
        
    except Exception as e:
        logger.error(f"Error processing audio chunk: {e}", exc_info=True)


def main():
    """Main function to run the audio processing service."""
    bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
    
    logger.info(f"Initializing Audio Processing Service...")
    logger.info(f"Connecting to Kafka at: {bootstrap_servers}")
    
    try:
        # Create Kafka consumer for audio-chunks topic
        consumer = create_consumer(
            topics=["audio-chunks"],
            group_id="audio-processing-service",
            bootstrap_servers=bootstrap_servers
        )
        
        # Create Kafka producer for transcripts topic
        producer = create_producer(bootstrap_servers=bootstrap_servers)
        
        logger.info("Audio Processing Service started. Waiting for audio chunks...")
        
        # Continuously consume and process messages
        for message in consumer:
            try:
                # message.value is already deserialized by our custom deserializer
                chunk_data = message.value
                process_audio_chunk(chunk_data, producer)
            except Exception as e:
                logger.error(f"Error processing message: {e}", exc_info=True)
                continue
                
    except KeyboardInterrupt:
        logger.info("Shutting down Audio Processing Service...")
    except Exception as e:
        logger.error(f"Fatal error in Audio Processing Service: {e}", exc_info=True)
        raise
    finally:
        if 'consumer' in locals():
            consumer.close()
        if 'producer' in locals():
            producer.close()
        logger.info("Audio Processing Service stopped.")


if __name__ == "__main__":
    main()

