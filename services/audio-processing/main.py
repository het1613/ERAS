"""
Audio Processing Service - Consumes audio chunks from Kafka, performs STT, and publishes transcripts.

Toggle STT provider via STT_PROVIDER env var:
  - "whisperx" (default) — local WhisperX inference
  - "deepgram"           — Deepgram Nova-3 API (requires DEEPGRAM_API_KEY)
"""

import os
import logging
import sys
import base64
import tempfile
import asyncio
import wave
import io
from datetime import datetime

import numpy as np

from shared.kafka_client import create_consumer, create_producer
from shared.types import AudioChunk, Transcript

# Add parent directory to path to access shared module
# Since Dockerfile copies main.py to /app/main.py and shared to /app/shared,
# and WORKDIR is /app, we don't need complicated path hacking if we run `python main.py`.
# But for local dev compatibility:
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# STT provider toggle: "whisperx" or "deepgram"
STT_PROVIDER = os.getenv("STT_PROVIDER", "whisperx").lower()

# Global model variables (WhisperX)
model = None
model_a = None
metadata = None
diarize_model = None
device = "cpu" # Force CPU for now as requested
compute_type = "int8" # quantize for CPU efficiency

# Global Deepgram client
deepgram_client = None
deepgram_keywords = None

def load_models():
    """Load STT models/clients based on STT_PROVIDER."""
    global model, metadata, device, compute_type, deepgram_client, deepgram_keywords

    if STT_PROVIDER == "deepgram":
        from deepgram import DeepgramClient
        api_key = os.getenv("DEEPGRAM_API_KEY")
        if not api_key:
            raise ValueError("DEEPGRAM_API_KEY env var is required when STT_PROVIDER=deepgram")
        deepgram_client = DeepgramClient(api_key)

        # Load regional keyterms for address recognition
        keyterms_path = os.path.join(os.path.dirname(__file__), "waterloo_keyterms.json")
        if os.path.exists(keyterms_path):
            import json as _json
            with open(keyterms_path) as f:
                terms = _json.load(f)
            deepgram_keywords = terms
            logger.info(f"Loaded {len(deepgram_keywords)} Deepgram keywords from {keyterms_path}")
        else:
            logger.warning(f"Keyterms file not found at {keyterms_path}, proceeding without keywords")

        logger.info("Deepgram client initialized (Nova-3).")
    else:
        import whisperx
        logger.info(f"Loading WhisperX model on {device} with {compute_type}...")
        try:
            model = whisperx.load_model("small.en", device, compute_type=compute_type)
            logger.info("WhisperX model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load WhisperX model: {e}")
            raise

def create_wav_from_pcm(pcm_data: bytes, sample_rate: int = 16000, channels: int = 1, sample_width: int = 2) -> bytes:
    """
    Create a WAV file from raw PCM data by adding proper headers.
    
    Args:
        pcm_data: Raw PCM audio bytes
        sample_rate: Sample rate in Hz (default 16000)
        channels: Number of audio channels (default 1 for mono)
        sample_width: Bytes per sample (default 2 for 16-bit)
        
    Returns:
        WAV file bytes with proper headers
    """
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, 'wb') as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_data)
    return wav_buffer.getvalue()


def is_valid_wav(data: bytes) -> bool:
    """Check if data starts with WAV file header."""
    return len(data) >= 4 and data[:4] == b'RIFF'


# Common Whisper hallucination phrases on silence/noise.
# These are well-documented artifacts that Whisper produces when fed silent or near-silent audio,
# especially when an initial_prompt biases toward certain domains.
HALLUCINATION_PATTERNS = [
    "a 911 emergency call",
    "call 911",
    "911 emergency",
    "thank you for watching",
    "thanks for watching",
    "thank you for listening",
    "thanks for listening",
    "please subscribe",
    "like and subscribe",
    "the end",
    "bye bye",
    "goodbye",
    "subtitles by",
    "transcribed by",
    "translated by",
    "you",
]


def is_hallucination(text: str) -> bool:
    """
    Check if transcribed text is a known Whisper hallucination.
    Returns True if the text matches common hallucination patterns.
    """
    cleaned = text.strip().lower().rstrip('.')
    for pattern in HALLUCINATION_PATTERNS:
        if cleaned == pattern or cleaned == pattern + ".":
            return True
    return False


def audio_has_speech(audio: np.ndarray, threshold: float = 0.005) -> bool:
    """
    Simple energy-based check to determine if audio contains speech.
    Returns False if the audio is essentially silence.
    """
    rms = np.sqrt(np.mean(audio ** 2))
    return rms > threshold


# Global session context to store last transcript for continuity
session_context = {}


async def stt_deepgram(audio_chunk: AudioChunk) -> str:
    """
    Speech-to-Text using Deepgram Nova-2 API.
    Sends pre-recorded audio and returns transcribed text.
    """
    from deepgram import PrerecordedOptions

    if not deepgram_client:
        logger.error("Deepgram client not initialized")
        return ""

    try:
        audio_bytes = base64.b64decode(audio_chunk.chunk_data)

        # Wrap raw PCM in WAV headers so Deepgram knows the format
        if not is_valid_wav(audio_bytes):
            audio_bytes = create_wav_from_pcm(audio_bytes, sample_rate=16000, channels=1, sample_width=2)

        payload = {"buffer": audio_bytes}
        options = PrerecordedOptions(
            model="nova-3",
            language="en",
            smart_format=True,
            numerals=True,
            keyterm=deepgram_keywords or [],
        )

        response = deepgram_client.listen.rest.v("1").transcribe_file(payload, options)
        transcript = (
            response.results.channels[0].alternatives[0].transcript
            if response.results.channels
            else ""
        )

        if not transcript:
            return ""

        if is_hallucination(transcript):
            logger.info(f"Filtered hallucinated transcript: '{transcript}'")
            return ""

        return transcript.strip()

    except Exception as e:
        logger.error(f"Deepgram STT Error: {e}", exc_info=True)
        return ""


async def stt(audio_chunk: AudioChunk, initial_prompt: str = "") -> str:
    """
    Speech-to-Text function using WhisperX (or underlying FasterWhisper).
    
    Args:
        audio_chunk: AudioChunk object containing audio data
        initial_prompt: Previous text to use as context
        
    Returns:
        Transcribed text string
    """
    global model
    
    if not model:
        logger.error("Model not initialized")
        return "Error: Model not initialized"

    try:
        # Decode base64 audio
        audio_bytes = base64.b64decode(audio_chunk.chunk_data)
        
        # Check if this is already a valid WAV file or raw PCM data
        if is_valid_wav(audio_bytes):
            # Already a WAV file, use as-is
            wav_data = audio_bytes
        else:
            # Raw PCM data - add WAV headers
            # Audio ingestion uses 16kHz, 16-bit, mono (CHUNK_SIZE = 16000 * 2)
            wav_data = create_wav_from_pcm(audio_bytes, sample_rate=16000, channels=1, sample_width=2)
        
        # WhisperX expects a file path or numpy array.
        # Writing to temp file is safest for compatibility.
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_audio:
            temp_audio.write(wav_data)
            temp_audio_path = temp_audio.name
            
        try:
            # Load audio using WhisperX utility
            import whisperx
            audio = whisperx.load_audio(temp_audio_path)
            
            # Check if audio has sufficient length (at least 0.5 second at 16kHz)
            if len(audio) < 8000:
                logger.debug(f"Audio chunk too short for transcription: {len(audio)} samples")
                return ""
            
            # Check if audio actually contains speech (energy-based)
            if not audio_has_speech(audio):
                logger.debug("Audio chunk appears to be silence, skipping transcription")
                return ""
            
            logger.debug(f"Transcribing audio with {len(audio)} samples ({len(audio)/16000:.2f} seconds)")
            
            # Use the underlying faster-whisper model directly to bypass VAD for short chunks.
            # This is more robust for streaming 5s chunks.
            # model is a FasterWhisperPipeline, model.model is the FasterWhisper model
            
            # Run transcription
            # beam_size=5 is standard. best_of=5. temperature defaults.
            segments, info = model.model.transcribe(
                audio, 
                beam_size=5, 
                language="en", 
                initial_prompt=initial_prompt,
                condition_on_previous_text=True
            )
            
            # segments is a generator, must consume it
            segments_list = list(segments)
            
            if not segments_list:
                logger.debug("No speech segments detected in audio")
                return ""
            
            text = " ".join([segment.text.strip() for segment in segments_list if segment.text])
            
            # If no text found (silence), return empty string
            if not text:
                return ""
            
            # Filter out known Whisper hallucinations (common on silence/noise)
            if is_hallucination(text):
                logger.info(f"Filtered hallucinated transcript: '{text}'")
                return ""
                
            return text
            
        finally:
            # Clean up temp file
            if os.path.exists(temp_audio_path):
                os.remove(temp_audio_path)
                
    except Exception as e:
        logger.error(f"STT Error: {e}", exc_info=True)
        # Don't return error string to user, just log it. Return empty to keep going.
        return ""


def process_audio_chunk(chunk_data: dict, producer: object) -> None:
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
        
        # Only process if we have actual data
        if audio_chunk.chunk_data == "mock_audio_data":
             logger.info(f"Skipping mock data for session: {audio_chunk.session_id}")
             return

        logger.info(f"Processing audio chunk for session: {audio_chunk.session_id}")
        
        # STT transcription — route to the configured provider
        if STT_PROVIDER == "deepgram":
            transcript_text = asyncio.run(stt_deepgram(audio_chunk))
        else:
            # Get context (last transcript) for this session.
            # Use empty string as default - avoid domain-specific prompts that cause
            # Whisper to hallucinate phrases like "A 911 emergency call" on silence.
            last_context = session_context.get(audio_chunk.session_id, "")
            transcript_text = asyncio.run(stt(audio_chunk, initial_prompt=last_context))
        
        if not transcript_text:
            logger.info("No speech detected.")
            return

        # Update session context for WhisperX continuity (not used by Deepgram)
        if STT_PROVIDER != "deepgram":
            new_context = (last_context + " " + transcript_text).strip()
            if len(new_context) > 200:
                new_context = new_context[-200:]
            session_context[audio_chunk.session_id] = new_context

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
        
        logger.info(f"Published transcript to Kafka for session: {audio_chunk.session_id}: '{transcript_text}'")
        
    except Exception as e:
        logger.error(f"Error processing audio chunk: {e}", exc_info=True)



def main():
    """Main function to run the audio processing service."""
    bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
    
    logger.info(f"Initializing Audio Processing Service...")
    
    # Load models
    load_models()
    
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

