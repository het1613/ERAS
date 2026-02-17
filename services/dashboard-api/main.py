"""
Dashboard API Service - Aggregated API and WebSocket gateway for frontend.
"""

import os
import logging
import sys
import asyncio
import threading
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
from collections import defaultdict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx

from shared.kafka_client import create_consumer
from shared.types import Transcript, Suggestion, VehicleLocation, PRIORITY_WEIGHT_MAP
from shared.db import get_connection

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

# Store event loop reference for use in Kafka consumer thread
event_loop = None


# --- Incident request models ---

class CreateIncidentRequest(BaseModel):
    session_id: Optional[str] = None
    lat: float
    lon: float
    location: Optional[str] = None
    type: Optional[str] = None
    priority: str = "Yellow"
    weight: Optional[int] = None

class UpdateIncidentRequest(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None
    weight: Optional[int] = None
    location: Optional[str] = None
    type: Optional[str] = None


# --- Incident helper functions ---

def _row_to_incident_dict(row) -> dict:
    """Convert a DB row tuple to an incident dict."""
    return {
        "id": row[0],
        "session_id": row[1],
        "lat": float(row[2]),
        "lon": float(row[3]),
        "location": row[4],
        "type": row[5],
        "priority": row[6],
        "weight": row[7],
        "status": row[8],
        "reported_at": row[9].isoformat() if row[9] else None,
        "updated_at": row[10].isoformat() if row[10] else None,
    }

INCIDENT_SELECT = "SELECT id, session_id, lat, lon, location, type, priority, weight, status, reported_at, updated_at FROM incidents"


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "dashboard-api"}


# --- Incident CRUD endpoints ---

@app.get("/incidents")
async def list_incidents(status: Optional[str] = None):
    """List all incidents, optionally filtered by status."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if status:
                cur.execute(f"{INCIDENT_SELECT} WHERE status = %s ORDER BY reported_at DESC", (status,))
            else:
                cur.execute(f"{INCIDENT_SELECT} ORDER BY reported_at DESC")
            rows = cur.fetchall()
            return {"incidents": [_row_to_incident_dict(r) for r in rows]}
    finally:
        conn.close()


@app.get("/incidents/{incident_id}")
async def get_incident(incident_id: str):
    """Get a single incident by ID."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f"{INCIDENT_SELECT} WHERE id = %s", (incident_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Incident not found")
            return _row_to_incident_dict(row)
    finally:
        conn.close()


@app.post("/incidents")
async def create_incident(req: CreateIncidentRequest):
    """Create a new incident, write to DB, broadcast via WebSocket."""
    incident_id = str(uuid.uuid4())
    weight = req.weight if req.weight is not None else PRIORITY_WEIGHT_MAP.get(req.priority, 2)
    now = datetime.now(timezone.utc)

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO incidents (id, session_id, lat, lon, location, type, priority, weight, status, reported_at, updated_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'open', %s, %s)""",
                (incident_id, req.session_id, req.lat, req.lon, req.location, req.type, req.priority, weight, now, now)
            )
        conn.commit()

        # Read back the full row
        with conn.cursor() as cur:
            cur.execute(f"{INCIDENT_SELECT} WHERE id = %s", (incident_id,))
            row = cur.fetchone()
            incident_dict = _row_to_incident_dict(row)
    finally:
        conn.close()

    # Broadcast to WebSocket clients
    await manager.broadcast({
        "type": "incident_created",
        "data": incident_dict
    })

    logger.info(f"Created incident {incident_id}")
    return incident_dict


@app.patch("/incidents/{incident_id}")
async def update_incident(incident_id: str, req: UpdateIncidentRequest):
    """Update an incident's fields, write to DB, broadcast via WebSocket."""
    # Build dynamic SET clause from provided fields
    updates = []
    params = []
    if req.status is not None:
        updates.append("status = %s")
        params.append(req.status)
    if req.priority is not None:
        updates.append("priority = %s")
        params.append(req.priority)
        # Auto-update weight if priority changes and weight not explicitly set
        if req.weight is None:
            updates.append("weight = %s")
            params.append(PRIORITY_WEIGHT_MAP.get(req.priority, 2))
    if req.weight is not None:
        updates.append("weight = %s")
        params.append(req.weight)
    if req.location is not None:
        updates.append("location = %s")
        params.append(req.location)
    if req.type is not None:
        updates.append("type = %s")
        params.append(req.type)

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.append(incident_id)

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE incidents SET {', '.join(updates)} WHERE id = %s",
                params
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Incident not found")
        conn.commit()

        # Read back the updated row
        with conn.cursor() as cur:
            cur.execute(f"{INCIDENT_SELECT} WHERE id = %s", (incident_id,))
            row = cur.fetchone()
            incident_dict = _row_to_incident_dict(row)
    finally:
        conn.close()

    # Broadcast to WebSocket clients
    await manager.broadcast({
        "type": "incident_updated",
        "data": incident_dict
    })

    logger.info(f"Updated incident {incident_id}")
    return incident_dict


# --- Existing endpoints ---

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

        # Broadcast to WebSocket clients (schedule in event loop)
        transcript_dict = transcript.model_dump()
        transcript_dict['timestamp'] = transcript_dict['timestamp'].isoformat()
        # Use asyncio.run_coroutine_threadsafe to schedule from thread
        global event_loop
        if event_loop and event_loop.is_running():
            asyncio.run_coroutine_threadsafe(
                manager.broadcast({
                    "type": "transcript",
                    "data": transcript_dict
                }),
                event_loop
            )

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

        # Broadcast to WebSocket clients (schedule in event loop)
        suggestion_dict = suggestion.model_dump()
        suggestion_dict['timestamp'] = suggestion_dict['timestamp'].isoformat()
        # Use asyncio.run_coroutine_threadsafe to schedule from thread
        global event_loop
        if event_loop and event_loop.is_running():
            asyncio.run_coroutine_threadsafe(
                manager.broadcast({
                    "type": "suggestion",
                    "data": suggestion_dict
                }),
                event_loop
            )

    except Exception as e:
        logger.error(f"Error processing suggestion message: {e}", exc_info=True)


def process_vehicle_location_message(message_value: dict):
    """Process a vehicle location message from Kafka."""
    try:
        if isinstance(message_value.get('timestamp'), str):
            message_value['timestamp'] = datetime.fromisoformat(message_value['timestamp'])

        location = VehicleLocation(**message_value)

        logger.info(f"Processed vehicle location for: {location.vehicle_id}")

        location_dict = location.model_dump()
        location_dict['timestamp'] = location_dict['timestamp'].isoformat()

        global event_loop
        if event_loop and event_loop.is_running():
            asyncio.run_coroutine_threadsafe(
                manager.broadcast({
                    "type": "vehicle_location",
                    "data": location_dict
                }),
                event_loop
            )

    except Exception as e:
        logger.error(f"Error processing vehicle location message: {e}", exc_info=True)


def process_vehicle_dispatch_message(message_value: dict):
    """Process a vehicle dispatch message from Kafka and broadcast route to frontend."""
    try:
        vehicle_id = message_value.get("vehicle_id")
        incident_id = message_value.get("incident_id")
        route_raw = message_value.get("route", [])

        # Convert [lat, lon] pairs to {lat, lng} objects for Google Maps
        route = [{"lat": point[0], "lng": point[1]} for point in route_raw]

        logger.info(f"Processed vehicle dispatch for: {vehicle_id} ({len(route)} waypoints)")

        global event_loop
        if event_loop and event_loop.is_running():
            asyncio.run_coroutine_threadsafe(
                manager.broadcast({
                    "type": "vehicle_dispatched",
                    "data": {
                        "vehicle_id": vehicle_id,
                        "incident_id": incident_id,
                        "route": route,
                    }
                }),
                event_loop
            )

    except Exception as e:
        logger.error(f"Error processing vehicle dispatch message: {e}", exc_info=True)


def process_vehicle_arrival_message(message_value: dict):
    """Process a vehicle arrival event: mark incident as resolved and broadcast update."""
    try:
        vehicle_id = message_value.get("vehicle_id")
        incident_id = message_value.get("incident_id")

        if not incident_id:
            return

        logger.info(f"Vehicle {vehicle_id} arrived at incident {incident_id}, resolving...")

        # Mark the incident as resolved in DB
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE incidents SET status = 'resolved', updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                    (incident_id,)
                )
            conn.commit()

            # Read back the full row to broadcast
            with conn.cursor() as cur:
                cur.execute(f"{INCIDENT_SELECT} WHERE id = %s", (incident_id,))
                row = cur.fetchone()
                if row:
                    incident_dict = _row_to_incident_dict(row)
                else:
                    return
        finally:
            conn.close()

        # Broadcast incident_updated so frontend clears the route polyline
        global event_loop
        if event_loop and event_loop.is_running():
            asyncio.run_coroutine_threadsafe(
                manager.broadcast({
                    "type": "incident_updated",
                    "data": incident_dict
                }),
                event_loop
            )

        logger.info(f"Incident {incident_id} resolved on arrival of {vehicle_id}")

    except Exception as e:
        logger.error(f"Error processing vehicle arrival message: {e}", exc_info=True)


def kafka_consumer_thread():
    """Run Kafka consumer in a separate thread to avoid blocking the event loop."""
    bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")

    logger.info(f"Starting Kafka consumer. Connecting to: {bootstrap_servers}")

    try:
        consumer = create_consumer(
            topics=["transcripts", "suggestions", "vehicle-locations", "vehicle-dispatches", "vehicle-arrivals"],
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
                elif topic == "vehicle-locations":
                    process_vehicle_location_message(message_value)
                elif topic == "vehicle-dispatches":
                    process_vehicle_dispatch_message(message_value)
                elif topic == "vehicle-arrivals":
                    process_vehicle_arrival_message(message_value)

            except Exception as e:
                logger.error(f"Error processing Kafka message: {e}", exc_info=True)
                continue

    except Exception as e:
        logger.error(f"Fatal error in Kafka consumer: {e}", exc_info=True)
    finally:
        if 'consumer' in locals():
            consumer.close()


@app.on_event("startup")
async def startup_event():
    """Start background tasks on application startup."""
    # Store event loop reference for use in Kafka consumer thread
    global event_loop
    event_loop = asyncio.get_event_loop()

    # Start Kafka consumer in a separate thread to avoid blocking the event loop
    kafka_thread = threading.Thread(target=kafka_consumer_thread, daemon=True)
    kafka_thread.start()
    logger.info("Dashboard API Service started")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown."""
    logger.info("Dashboard API Service shutting down")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
