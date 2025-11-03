"""Audio Ingestion Service - Handles incoming audio streams."""
import os
import sys
import uuid
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import sys

# Add shared module to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from shared.kafka_client import create_producer, publish_message
from shared.redis_client import create_redis_client, set_session_data
from shared.types import AudioChunk

app = FastAPI(title="Audio Ingestion Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

producer = create_producer()
redis_client = create_redis_client()

KAFKA_TOPIC_AUDIO_CHUNKS = "audio-chunks"


@app.post("/api/v1/audio/upload")
async def upload_audio(file: UploadFile = File(...)):
    """Upload audio file for processing."""
    session_id = str(uuid.uuid4())
    
    # Read audio file
    audio_data = await file.read()
    
    # Create audio chunk
    chunk = AudioChunk(
        session_id=session_id,
        chunk_id=str(uuid.uuid4()),
        audio_data=audio_data,
        timestamp=datetime.utcnow(),
        metadata={"filename": file.filename, "content_type": file.content_type}
    )
    
    # Store session in Redis
    set_session_data(
        redis_client,
        session_id,
        {"status": "processing", "start_time": chunk.timestamp.isoformat()}
    )
    
    # Publish to Kafka
    publish_message(
        producer,
        KAFKA_TOPIC_AUDIO_CHUNKS,
        {
            "session_id": chunk.session_id,
            "chunk_id": chunk.chunk_id,
            "audio_data": audio_data.hex(),  # Convert bytes to hex for JSON
            "timestamp": chunk.timestamp.isoformat(),
            "metadata": chunk.metadata
        },
        key=session_id
    )
    
    return {"session_id": session_id, "status": "accepted"}


@app.websocket("/ws/v1/audio/stream")
async def stream_audio(websocket: WebSocket):
    """WebSocket endpoint for real-time audio streaming."""
    await websocket.accept()
    session_id = str(uuid.uuid4())
    
    # Initialize session
    set_session_data(
        redis_client,
        session_id,
        {"status": "streaming", "start_time": datetime.utcnow().isoformat()}
    )
    
    try:
        await websocket.send_json({"session_id": session_id, "status": "connected"})
        
        while True:
            # Receive audio chunk
            data = await websocket.receive_bytes()
            
            # Create chunk
            chunk = AudioChunk(
                session_id=session_id,
                chunk_id=str(uuid.uuid4()),
                audio_data=data,
                timestamp=datetime.utcnow()
            )
            
            # Publish to Kafka
            publish_message(
                producer,
                KAFKA_TOPIC_AUDIO_CHUNKS,
                {
                    "session_id": chunk.session_id,
                    "chunk_id": chunk.chunk_id,
                    "audio_data": data.hex(),
                    "timestamp": chunk.timestamp.isoformat()
                },
                key=session_id
            )
            
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        await websocket.close()


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "audio-ingestion"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)

