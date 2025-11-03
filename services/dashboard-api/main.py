"""
Dashboard API Service - Aggregated API and WebSocket gateway for frontend.
"""

import os
import logging
import sys
import asyncio
from datetime import datetime
from typing import Dict, List
from collections import defaultdict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx

from shared.kafka_client import create_consumer
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

app = FastAPI(title="Dashboard API Service", version="0.1.0")

# Enable CORS for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for sessions, transcripts, and suggestions
# TODO: Store in PostgreSQL
sessions: Dict[str, Dict] = {}
transcripts_by_session: Dict[str, List[Transcript]] = defaultdict(list)
suggestions_by_session: Dict[str, List[Suggestion]] = defaultdict(list)

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"WebSocket client disconnected. Total connections: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Broadcast message to all connected WebSocket clients."""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error sending to WebSocket client: {e}")
                disconnected.append(connection)
        
        # Remove disconnected clients
        for conn in disconnected:
            self.disconnect(conn)

manager = ConnectionManager()

# Service URLs (from docker-compose network)
GEOSPATIAL_DISPATCH_URL = os.getenv("GEOSPATIAL_DISPATCH_URL", "http://geospatial-dispatch:8002")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "dashboard-api"}


@app.get("/sessions")
async def get_sessions():
    """
    Get all active sessions.
    
    Returns:
        List of session summaries
    """
    session_list = []
    for session_id, session_data in sessions.items():
        session_list.append({
            "session_id": session_id,
            "created_at": session_data.get("created_at"),
            "transcript_count": len(transcripts_by_session.get(session_id, [])),
            "suggestion_count": len(suggestions_by_session.get(session_id, [])),
        })
    return {"sessions": session_list}


@app.get("/sessions/{session_id}/transcript")
async def get_session_transcript(session_id: str):
    """
    Get transcript for a specific session.
    
    Args:
        session_id: Session identifier
        
    Returns:
        List of transcripts for the session
    """
    transcripts = transcripts_by_session.get(session_id, [])
    return {
        "session_id": session_id,
        "transcripts": [
            {**t.model_dump(), "timestamp": t.timestamp.isoformat()}
            for t in transcripts
        ]
    }


@app.get("/sessions/{session_id}/suggestions")
async def get_session_suggestions(session_id: str):
    """
    Get suggestions for a specific session.
    
    Args:
        session_id: Session identifier
        
    Returns:
        List of suggestions for the session
    """
    suggestions = suggestions_by_session.get(session_id, [])
    return {
        "session_id": session_id,
        "suggestions": [
            {**s.model_dump(), "timestamp": s.timestamp.isoformat()}
            for s in suggestions
        ]
    }


@app.get("/sessions/{session_id}/assignment")
async def get_session_assignment(session_id: str):
    """
    Get vehicle assignment for a specific session.
    Fetches from Geospatial Dispatch Service.
    
    Args:
        session_id: Session identifier
        
    Returns:
        Assignment suggestion
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GEOSPATIAL_DISPATCH_URL}/assignments/{session_id}",
                timeout=5.0
            )
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail="Assignment not found")
            response.raise_for_status()
            return response.json()
    except httpx.RequestError as e:
        logger.error(f"Error fetching assignment from geospatial service: {e}")
        raise HTTPException(status_code=503, detail="Geospatial service unavailable")


@app.get("/vehicles")
async def get_vehicles():
    """
    Get list of vehicles.
    Fetches from Geospatial Dispatch Service.
    
    Returns:
        List of vehicles
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GEOSPATIAL_DISPATCH_URL}/vehicles",
                timeout=5.0
            )
            response.raise_for_status()
            return response.json()
    except httpx.RequestError as e:
        logger.error(f"Error fetching vehicles from geospatial service: {e}")
        raise HTTPException(status_code=503, detail="Geospatial service unavailable")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time updates.
    
    Clients connect to receive transcripts and suggestions as they arrive.
    """
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive and handle client messages if needed
            data = await websocket.receive_text()
            # For now, we don't process incoming messages
            # TODO: handle subscription filters, etc.
    except WebSocketDisconnect:
        manager.disconnect(websocket)


def process_transcript_message(message_value: dict):
    """Process a transcript message from Kafka."""
    try:
        # Parse transcript
        if isinstance(message_value.get('timestamp'), str):
            message_value['timestamp'] = datetime.fromisoformat(message_value['timestamp'])
        
        transcript = Transcript(**message_value)
        
        # Store transcript
        session_id = transcript.session_id
        transcripts_by_session[session_id].append(transcript)
        
        # Create session if it doesn't exist
        if session_id not in sessions:
            sessions[session_id] = {
                "created_at": transcript.timestamp.isoformat(),
            }
        
        logger.info(f"Processed transcript for session: {session_id}")
        
        # Broadcast to WebSocket clients
        transcript_dict = transcript.model_dump()
        transcript_dict['timestamp'] = transcript_dict['timestamp'].isoformat()
        asyncio.create_task(manager.broadcast({
            "type": "transcript",
            "data": transcript_dict
        }))
        
    except Exception as e:
        logger.error(f"Error processing transcript message: {e}", exc_info=True)


def process_suggestion_message(message_value: dict):
    """Process a suggestion message from Kafka."""
    try:
        # Parse suggestion
        if isinstance(message_value.get('timestamp'), str):
            message_value['timestamp'] = datetime.fromisoformat(message_value['timestamp'])
        
        suggestion = Suggestion(**message_value)
        
        # Store suggestion
        session_id = suggestion.session_id
        suggestions_by_session[session_id].append(suggestion)
        
        logger.info(f"Processed suggestion for session: {session_id}")
        
        # Broadcast to WebSocket clients
        suggestion_dict = suggestion.model_dump()
        suggestion_dict['timestamp'] = suggestion_dict['timestamp'].isoformat()
        asyncio.create_task(manager.broadcast({
            "type": "suggestion",
            "data": suggestion_dict
        }))
        
    except Exception as e:
        logger.error(f"Error processing suggestion message: {e}", exc_info=True)


async def kafka_consumer_task():
    """Background task to consume from Kafka and process messages."""
    bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
    
    logger.info(f"Starting Kafka consumer. Connecting to: {bootstrap_servers}")
    
    try:
        consumer = create_consumer(
            topics=["transcripts", "suggestions"],
            group_id="dashboard-api-service",
            bootstrap_servers=bootstrap_servers
        )
        
        logger.info("Kafka consumer started. Waiting for messages...")
        
        for message in consumer:
            try:
                topic = message.topic
                message_value = message.value
                
                if topic == "transcripts":
                    process_transcript_message(message_value)
                elif topic == "suggestions":
                    process_suggestion_message(message_value)
                    
            except Exception as e:
                logger.error(f"Error processing Kafka message: {e}", exc_info=True)
                continue
                
    except Exception as e:
        logger.error(f"Fatal error in Kafka consumer: {e}", exc_info=True)


@app.on_event("startup")
async def startup_event():
    """Start background tasks on application startup."""
    asyncio.create_task(kafka_consumer_task())
    logger.info("Dashboard API Service started")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown."""
    logger.info("Dashboard API Service shutting down")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

