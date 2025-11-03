"""AI Suggestion Engine - Generates actionable suggestions."""
import os
import sys
import uuid
import threading
from datetime import datetime

# Add shared module to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from shared.kafka_client import create_consumer, create_producer, consume_messages
from shared.redis_client import create_redis_client, publish_realtime_update
from shared.types import (
    ProcessedTranscript, AISuggestion, SuggestionType, IncidentType, Severity
)

app = FastAPI(title="AI Suggestion Engine", version="1.0.0")

producer = create_producer()
redis_client = create_redis_client()

KAFKA_TOPIC_PROCESSED_DATA = "processed-data"
KAFKA_TOPIC_SUGGESTIONS = "suggestions"


def generate_suggestions(transcript_data: dict) -> list[AISuggestion]:
    """Generate AI suggestions based on processed transcript."""
    suggestions = []
    session_id = transcript_data["session_id"]
    
    # Suggestion 1: Incident Code
    if transcript_data.get("incident_type"):
        suggestions.append(AISuggestion(
            session_id=session_id,
            suggestion_id=str(uuid.uuid4()),
            type=SuggestionType.INCIDENT_CODE,
            content={
                "code": transcript_data["incident_type"],
                "description": f"Suggested incident code: {transcript_data['incident_type']}"
            },
            confidence=0.85,
            timestamp=datetime.utcnow()
        ))
    
    # Suggestion 2: Severity
    if transcript_data.get("severity"):
        suggestions.append(AISuggestion(
            session_id=session_id,
            suggestion_id=str(uuid.uuid4()),
            type=SuggestionType.SEVERITY,
            content={
                "severity": transcript_data["severity"],
                "description": f"Suggested severity: {transcript_data['severity']}"
            },
            confidence=0.80,
            timestamp=datetime.utcnow()
        ))
    
    # Suggestion 3: Alert (if high/critical severity)
    if transcript_data.get("severity") in ["high", "critical"]:
        suggestions.append(AISuggestion(
            session_id=session_id,
            suggestion_id=str(uuid.uuid4()),
            type=SuggestionType.ALERT,
            content={
                "alert_type": "high_priority",
                "message": f"High priority incident detected: {transcript_data.get('incident_type', 'Unknown')}"
            },
            confidence=0.90,
            timestamp=datetime.utcnow()
        ))
    
    return suggestions


def process_transcript(message: dict):
    """Process transcript and generate suggestions."""
    try:
        # Generate suggestions
        suggestions = generate_suggestions(message)
        
        # Store suggestions in database and publish
        import psycopg2
        from psycopg2.extras import RealDictCursor
        import json
        
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            database=os.getenv("POSTGRES_DB", "eras_db"),
            user=os.getenv("POSTGRES_USER", "eras_user"),
            password=os.getenv("POSTGRES_PASSWORD", "eras_password")
        )
        
        try:
            for suggestion in suggestions:
                with conn.cursor() as cur:
                    # Store in database
                    cur.execute("""
                        INSERT INTO suggestions 
                        (suggestion_id, session_id, type, content, confidence, status, timestamp)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        suggestion.suggestion_id,
                        suggestion.session_id,
                        suggestion.type.value,
                        json.dumps(suggestion.content),
                        suggestion.confidence,
                        suggestion.status,
                        suggestion.timestamp
                    ))
                
                # Publish to Kafka
                publish_message(
                    producer,
                    KAFKA_TOPIC_SUGGESTIONS,
                    suggestion.dict(),
                    key=suggestion.session_id
                )
                
                # Publish real-time update
                publish_realtime_update(
                    redis_client,
                    f"suggestion:{suggestion.session_id}",
                    suggestion.dict()
                )
            
            conn.commit()
        finally:
            conn.close()
            
    except Exception as e:
        print(f"Error generating suggestions: {e}")


def start_kafka_consumer():
    """Start Kafka consumer in background thread."""
    consumer = create_consumer(KAFKA_TOPIC_PROCESSED_DATA, "ai-suggestion-group")
    consume_messages(consumer, process_transcript)


@app.on_event("startup")
async def startup():
    """Start Kafka consumer on service startup."""
    thread = threading.Thread(target=start_kafka_consumer, daemon=True)
    thread.start()


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "ai-suggestion-engine"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)

