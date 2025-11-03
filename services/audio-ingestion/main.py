"""
Audio Ingestion Service - Receives audio input and publishes to Kafka.
"""

import os
import uuid
import logging
import sys
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from shared.kafka_client import create_producer
from shared.types import AudioChunk

# Add parent directory to path to access shared module
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
sys.path.insert(0, parent_dir)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Audio Ingestion Service", version="0.1.0")

# Enable CORS for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Kafka producer
producer = None


@app.on_event("startup")
async def startup_event():
    """Initialize Kafka producer on startup."""
    global producer
    try:
        bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
        producer = create_producer(bootstrap_servers=bootstrap_servers)
        logger.info(f"Kafka producer initialized with bootstrap_servers: {bootstrap_servers}")
    except Exception as e:
        logger.error(f"Failed to initialize Kafka producer: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Close Kafka producer on shutdown."""
    global producer
    if producer:
        producer.close()
        logger.info("Kafka producer closed")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "audio-ingestion"}


@app.post("/ingest")
async def ingest_audio(file: UploadFile = File(...)):
    """
    Accept audio file upload and publish chunks to Kafka.
    """
    if producer is None:
        raise HTTPException(status_code=503, detail="Kafka producer not initialized")
    
    try:
        # Generate session ID for this audio ingestion
        session_id = str(uuid.uuid4())
        logger.info(f"Processing audio file for session: {session_id}")
        
        # Read file content
        file_content = await file.read()
        
        # For MVP: Create a single chunk with mock data
        # In production, this would process and chunk the audio appropriately
        chunk_data = file_content.decode('utf-8', errors='ignore') if isinstance(file_content, bytes) else str(file_content)
        
        chunk = AudioChunk(
            session_id=session_id,
            chunk_data=chunk_data or "mock_audio_data",
            timestamp=datetime.now(),
            sequence_number=0
        )
        
        # Serialize and publish to Kafka
        chunk_dict = chunk.model_dump()
        chunk_dict['timestamp'] = chunk_dict['timestamp'].isoformat() # Convert datetime to ISO format string for JSON serialization
        
        producer.send("audio-chunks", chunk_dict)
        producer.flush()  # Ensure message is sent
        
        logger.info(f"Published audio chunk to Kafka for session: {session_id}")
        
        return {
            "session_id": session_id,
            "status": "ingested",
            "filename": file.filename,
            "size": len(file_content)
        }
        
    except Exception as e:
        logger.error(f"Error ingesting audio: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error ingesting audio: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)

