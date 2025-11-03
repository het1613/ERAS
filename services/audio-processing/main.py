"""Audio Processing Service - STT and ML extraction."""
import os
import sys
import json
import threading
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import re
import psycopg2
from psycopg2.extras import RealDictCursor

# Add shared module to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from shared.kafka_client import create_consumer, create_producer, consume_messages
from shared.redis_client import create_redis_client, get_session_data, publish_realtime_update
from shared.types import ProcessedTranscript, IncidentType, Severity

app = FastAPI(title="Audio Processing Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

producer = create_producer()
redis_client = create_redis_client()

# Database connection
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_DB = os.getenv("POSTGRES_DB", "eras_db")
POSTGRES_USER = os.getenv("POSTGRES_USER", "eras_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "eras_password")

KAFKA_TOPIC_AUDIO_CHUNKS = "audio-chunks"
KAFKA_TOPIC_PROCESSED_DATA = "processed-data"


def get_db_connection():
    """Get PostgreSQL connection."""
    return psycopg2.connect(
        host=POSTGRES_HOST,
        database=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD
    )


def mock_stt(audio_data_hex: str) -> str:
    """Mock STT - in production, integrate with actual STT service (e.g., Google, Azure)."""
    # For MVP, return mock transcript based on patterns
    # In production, this would call actual STT API
    return "Emergency, I need help. There's been an accident at Main Street and 5th Avenue."


def extract_entities(transcript: str) -> dict:
    """Extract entities from transcript using NLP patterns."""
    entities = {
        "locations": [],
        "numbers": [],
        "keywords": []
    }
    
    # Extract potential locations (simple pattern matching)
    location_patterns = [
        r'\b\d+\w+\s+Street\b',
        r'\b\d+\w+\s+Avenue\b',
        r'\bMain\s+Street\b',
        r'\b\d+\w+\s+and\s+\d+\w+\b'
    ]
    
    for pattern in location_patterns:
        matches = re.findall(pattern, transcript, re.IGNORECASE)
        entities["locations"].extend(matches)
    
    # Extract keywords
    keywords = ["accident", "fire", "medical", "emergency", "help", "ambulance", "police"]
    for keyword in keywords:
        if keyword.lower() in transcript.lower():
            entities["keywords"].append(keyword)
    
    return entities


def detect_incident_type(transcript: str, entities: dict) -> IncidentType:
    """Detect incident type from transcript."""
    transcript_lower = transcript.lower()
    
    if any(word in transcript_lower for word in ["accident", "crash", "collision"]):
        return IncidentType.ACCIDENT
    elif any(word in transcript_lower for word in ["fire", "smoke", "burning"]):
        return IncidentType.FIRE
    elif any(word in transcript_lower for word in ["medical", "heart", "unconscious", "ambulance"]):
        return IncidentType.MEDICAL
    elif any(word in transcript_lower for word in ["police", "crime", "robbery", "assault"]):
        return IncidentType.POLICE
    
    return IncidentType.UNKNOWN


def detect_severity(transcript: str) -> Severity:
    """Detect severity from transcript."""
    transcript_lower = transcript.lower()
    
    if any(word in transcript_lower for word in ["critical", "urgent", "dying", "unconscious"]):
        return Severity.CRITICAL
    elif any(word in transcript_lower for word in ["serious", "bad", "wounded"]):
        return Severity.HIGH
    elif any(word in transcript_lower for word in ["minor", "small", "slight"]):
        return Severity.LOW
    
    return Severity.MEDIUM


def extract_location(transcript: str, entities: dict) -> dict:
    """Extract location coordinates (mock - in production, use geocoding API)."""
    # For MVP, return mock coordinates
    # In production, use geocoding service (Google Maps, OpenStreetMap, etc.)
    if entities["locations"]:
        return {"lat": 43.4723, "lng": -80.5449}  # Mock coordinates
    return None


def process_audio_chunk(message: dict):
    """Process audio chunk: STT -> Extract entities -> Create processed transcript."""
    try:
        session_id = message["session_id"]
        audio_data_hex = message["audio_data"]
        
        # Convert hex back to bytes (for actual STT processing)
        # audio_data = bytes.fromhex(audio_data_hex)
        
        # Mock STT
        transcript = mock_stt(audio_data_hex)
        
        # Extract entities
        entities = extract_entities(transcript)
        
        # Detect incident type
        incident_type = detect_incident_type(transcript, entities)
        
        # Detect severity
        severity = detect_severity(transcript)
        
        # Extract location
        location = extract_location(transcript, entities)
        
        # Create processed transcript
        processed = ProcessedTranscript(
            session_id=session_id,
            transcript=transcript,
            confidence=0.85,  # Mock confidence
            language="en",
            entities=entities,
            incident_type=incident_type,
            location=location,
            severity=severity,
            timestamp=datetime.utcnow()
        )
        
        # Store in database
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # Ensure session exists
                cur.execute("""
                    INSERT INTO sessions (session_id, start_time, status)
                    VALUES (%s, %s, 'active')
                    ON CONFLICT (session_id) DO NOTHING
                """, (session_id, processed.timestamp))
                
                # Insert transcript
                cur.execute("""
                    INSERT INTO transcripts 
                    (session_id, transcript, confidence, language, entities, 
                     incident_type, location, severity, timestamp)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    session_id,
                    processed.transcript,
                    processed.confidence,
                    processed.language,
                    json.dumps(processed.entities),
                    processed.incident_type.value if processed.incident_type else None,
                    json.dumps(processed.location) if processed.location else None,
                    processed.severity.value if processed.severity else None,
                    processed.timestamp
                ))
                
                conn.commit()
        finally:
            conn.close()
        
        # Publish to processed-data topic
        publish_message(
            producer,
            KAFKA_TOPIC_PROCESSED_DATA,
            processed.dict(),
            key=session_id
        )
        
        # Publish real-time update
        publish_realtime_update(
            redis_client,
            f"transcript:{session_id}",
            processed.dict()
        )
        
    except Exception as e:
        print(f"Error processing audio chunk: {e}")


def start_kafka_consumer():
    """Start Kafka consumer in background thread."""
    consumer = create_consumer(KAFKA_TOPIC_AUDIO_CHUNKS, "audio-processing-group")
    consume_messages(consumer, process_audio_chunk)


@app.on_event("startup")
async def startup():
    """Start Kafka consumer on service startup."""
    thread = threading.Thread(target=start_kafka_consumer, daemon=True)
    thread.start()


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "audio-processing"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)

