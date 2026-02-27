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
from shared.acr_codes import get_acr_codes_for_api

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
suggestions_by_id: Dict[str, Suggestion] = {}  # suggestion.id -> Suggestion for O(1) lookup

# Active dispatch routes: vehicle_id -> {incident_id, route: [{lat, lng}, ...]}
active_routes: Dict[str, Dict] = {}

# Vehicle status tracking: vehicle_id -> status string
# Updated on dispatch ("dispatched") and arrival ("available")
vehicle_statuses: Dict[str, str] = {}

# Per-incident dispatch state: incident_id -> { declined_vehicles: [str], suggestion_id: str | None }
incident_dispatch_state: Dict[str, Dict] = {}

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


class AcceptSuggestionRequest(BaseModel):
    incident_code: Optional[str] = None
    incident_code_description: Optional[str] = None
    incident_code_category: Optional[str] = None
    priority: Optional[str] = None
    lat: float
    lon: float
    location: Optional[str] = None


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


class FindBestRequest(BaseModel):
    incident_id: str
    exclude_vehicles: list[str] = []


async def _find_best_and_broadcast(incident_id: str, exclude_vehicles: list[str] = []):
    """Call geospatial-dispatch find-best and broadcast the result via WebSocket.

    Returns the suggestion data dict on success, or None on failure.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{GEOSPATIAL_DISPATCH_URL}/assignments/find-best",
                json={"incident_id": incident_id, "exclude_vehicles": exclude_vehicles},
                timeout=15.0,
            )
            response.raise_for_status()
            data = response.json()

        # Track the active suggestion for this incident
        suggestion_id = data.get("suggestion_id")
        if incident_id not in incident_dispatch_state:
            incident_dispatch_state[incident_id] = {"declined_vehicles": [], "suggestion_id": None}
        incident_dispatch_state[incident_id]["suggestion_id"] = suggestion_id

        # Broadcast dispatch suggestion to all connected Dashboard clients
        await manager.broadcast({
            "type": "dispatch_suggestion",
            "data": data,
        })

        logger.info(f"Broadcast dispatch_suggestion for incident {incident_id}: vehicle {data.get('suggested_vehicle_id')}")
        return data

    except httpx.HTTPStatusError as e:
        detail = e.response.json().get("detail", "Error") if e.response else "Error"
        logger.error(f"find-best failed for incident {incident_id}: {detail}")
        return None
    except Exception as e:
        logger.error(f"Error calling find-best for incident {incident_id}: {e}")
        return None


@app.post("/assignments/find-best")
async def proxy_find_best(request: FindBestRequest):
    """Proxy find-best to geospatial-dispatch."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{GEOSPATIAL_DISPATCH_URL}/assignments/find-best",
                json=request.model_dump(),
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.json().get("detail", "Error"))
    except httpx.RequestError as e:
        logger.error(f"Error proxying find-best: {e}")
        raise HTTPException(status_code=503, detail="Geospatial service unavailable")


@app.post("/assignments/{suggestion_id}/accept")
async def proxy_accept(suggestion_id: str):
    """Proxy accept to geospatial-dispatch."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{GEOSPATIAL_DISPATCH_URL}/assignments/{suggestion_id}/accept",
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.json().get("detail", "Error"))
    except httpx.RequestError as e:
        logger.error(f"Error proxying accept: {e}")
        raise HTTPException(status_code=503, detail="Geospatial service unavailable")


@app.post("/assignments/{suggestion_id}/decline")
async def proxy_decline(suggestion_id: str):
    """Proxy decline to geospatial-dispatch."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{GEOSPATIAL_DISPATCH_URL}/assignments/{suggestion_id}/decline",
                timeout=5.0,
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.json().get("detail", "Error"))
    except httpx.RequestError as e:
        logger.error(f"Error proxying decline: {e}")
        raise HTTPException(status_code=503, detail="Geospatial service unavailable")


class DeclineAndReassignRequest(BaseModel):
    incident_id: str
    declined_vehicle_id: str


@app.post("/assignments/{suggestion_id}/decline-and-reassign")
async def decline_and_reassign(suggestion_id: str, req: DeclineAndReassignRequest):
    """Decline the current suggestion, add the vehicle to the exclude list, and find the next best."""
    # Decline the current suggestion on geospatial-dispatch
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{GEOSPATIAL_DISPATCH_URL}/assignments/{suggestion_id}/decline",
                timeout=5.0,
            )
            response.raise_for_status()
    except Exception as e:
        logger.warning(f"Error declining suggestion {suggestion_id}: {e}")

    # Track declined vehicles for this incident
    if req.incident_id not in incident_dispatch_state:
        incident_dispatch_state[req.incident_id] = {"declined_vehicles": [], "suggestion_id": None}
    state = incident_dispatch_state[req.incident_id]
    if req.declined_vehicle_id not in state["declined_vehicles"]:
        state["declined_vehicles"].append(req.declined_vehicle_id)

    # Find the next best vehicle, excluding all previously declined ones
    dispatch_data = await _find_best_and_broadcast(
        req.incident_id,
        exclude_vehicles=state["declined_vehicles"],
    )

    if not dispatch_data:
        return {"status": "no_vehicles_available", "suggestion_id": suggestion_id}

    return {"status": "reassigned", "dispatch_suggestion": dispatch_data}


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


@app.get("/active-routes")
async def get_active_routes():
    """Return all active dispatch routes (survives frontend refresh)."""
    return {"routes": active_routes}


@app.post("/admin/reset")
async def admin_reset():
    """Wipe all DB data and in-memory state, reset vehicles, broadcast to clients."""
    # 1. Clear database tables (incidents has FK to sessions, so delete order matters)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM incidents")
            cur.execute("DELETE FROM suggestions")
            cur.execute("DELETE FROM transcripts")
            cur.execute("DELETE FROM sessions")
        conn.commit()
        logger.info("Cleared all database tables")
    finally:
        conn.close()

    # 2. Clear all in-memory state
    sessions.clear()
    transcripts_by_session.clear()
    suggestions_by_session.clear()
    suggestions_by_id.clear()
    active_routes.clear()
    vehicle_statuses.clear()
    incident_dispatch_state.clear()

    # 3. Reset vehicles on geospatial-dispatch
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{GEOSPATIAL_DISPATCH_URL}/admin/reset", timeout=10.0
            )
            resp.raise_for_status()
            logger.info("Geospatial-dispatch reset successful")
    except Exception as e:
        logger.warning(f"Failed to reset geospatial-dispatch: {e}")

    # 4. Broadcast reset event so all connected frontends clear their state
    await manager.broadcast({"type": "system_reset", "data": {}})

    logger.info("Admin reset complete")
    return {"status": "reset_complete"}


# --- Geocoding endpoint ---

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_HEADERS = {"User-Agent": "ERAS-EmergencyDispatch/1.0"}
NOMINATIM_VIEWBOX = "-80.7,43.3,-80.3,43.6"


class GeocodeRequest(BaseModel):
    address: str


@app.post("/geocode")
async def geocode_address(req: GeocodeRequest):
    """Geocode an address string using Nominatim (OpenStreetMap), biased toward Waterloo Region."""
    if not req.address.strip():
        raise HTTPException(status_code=400, detail="Address is required")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                NOMINATIM_URL,
                params={
                    "q": req.address,
                    "format": "json",
                    "limit": 1,
                    "viewbox": NOMINATIM_VIEWBOX,
                    "bounded": 1,
                    "countrycodes": "ca",
                },
                headers=NOMINATIM_HEADERS,
                timeout=10.0,
            )
            response.raise_for_status()
            results = response.json()

        if results:
            lat = float(results[0]["lat"])
            lon = float(results[0]["lon"])
            logger.info(f"Geocoded '{req.address}' -> ({lat}, {lon})")
            return {"lat": lat, "lon": lon, "found": True}

        logger.info(f"No geocoding results for '{req.address}'")
        return {"lat": None, "lon": None, "found": False}

    except Exception as e:
        logger.warning(f"Geocoding failed for '{req.address}': {e}")
        raise HTTPException(status_code=502, detail="Geocoding service unavailable")


# --- ACR Code & Suggestion Accept/Dismiss endpoints ---

@app.get("/acr-codes")
async def list_acr_codes():
    """Return all Ontario ACR Problem Codes for frontend dropdowns."""
    return {"codes": get_acr_codes_for_api()}


@app.post("/suggestions/{suggestion_id}/accept")
async def accept_suggestion(suggestion_id: str, req: AcceptSuggestionRequest):
    """
    Accept a suggestion: apply optional overrides, create an incident, update status,
    and automatically trigger dispatch optimization (server-side auto-dispatch).
    """
    suggestion = suggestions_by_id.get(suggestion_id)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    # Determine final values (user overrides take precedence)
    final_priority = req.priority or suggestion.priority or "Yellow"
    code_desc = req.incident_code_description or suggestion.incident_code_description or ""
    code_cat = req.incident_code_category or suggestion.incident_code_category or ""
    code_num = req.incident_code or suggestion.incident_code or ""
    incident_type = f"Code {code_num} - {code_cat}: {code_desc}" if code_num else suggestion.value

    weight = PRIORITY_WEIGHT_MAP.get(final_priority, 2)
    incident_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Ensure session exists in DB (sessions are in-memory but incidents FK references sessions table)
            if suggestion.session_id:
                cur.execute(
                    "INSERT INTO sessions (id, created_at, status) VALUES (%s, %s, 'active') ON CONFLICT (id) DO NOTHING",
                    (suggestion.session_id, now)
                )
            cur.execute(
                """INSERT INTO incidents (id, session_id, lat, lon, location, type, priority, weight, status, reported_at, updated_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'open', %s, %s)""",
                (incident_id, suggestion.session_id, req.lat, req.lon, req.location, incident_type, final_priority, weight, now, now)
            )
        conn.commit()

        with conn.cursor() as cur:
            cur.execute(f"{INCIDENT_SELECT} WHERE id = %s", (incident_id,))
            row = cur.fetchone()
            incident_dict = _row_to_incident_dict(row)
    finally:
        conn.close()

    # Update suggestion status
    suggestion.status = "accepted"

    # Broadcast the new incident
    await manager.broadcast({
        "type": "incident_created",
        "data": incident_dict
    })

    # Broadcast suggestion status change
    suggestion_dict = suggestion.model_dump()
    suggestion_dict['timestamp'] = suggestion_dict['timestamp'].isoformat()
    await manager.broadcast({
        "type": "suggestion_updated",
        "data": suggestion_dict
    })

    logger.info(f"Accepted suggestion {suggestion_id}, created incident {incident_id}")

    # Server-side auto-dispatch: find the best ambulance and push suggestion to dispatcher
    dispatch_data = await _find_best_and_broadcast(incident_id)

    return {
        "incident": incident_dict,
        "suggestion_status": "accepted",
        "dispatch_suggestion": dispatch_data,
    }


@app.post("/suggestions/{suggestion_id}/dismiss")
async def dismiss_suggestion(suggestion_id: str):
    """Dismiss a suggestion and broadcast the status change."""
    suggestion = suggestions_by_id.get(suggestion_id)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    suggestion.status = "dismissed"

    suggestion_dict = suggestion.model_dump()
    suggestion_dict['timestamp'] = suggestion_dict['timestamp'].isoformat()
    await manager.broadcast({
        "type": "suggestion_updated",
        "data": suggestion_dict
    })

    logger.info(f"Dismissed suggestion {suggestion_id}")
    return {"status": "dismissed"}


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
        session_id = suggestion.session_id

        # Check if this is an update to an existing suggestion (same ID)
        is_update = suggestion.id and suggestion.id in suggestions_by_id

        if is_update:
            # Update existing suggestion in-place in the session list
            old = suggestions_by_id[suggestion.id]
            session_list = suggestions_by_session.get(session_id, [])
            for i, s in enumerate(session_list):
                if s.id == suggestion.id:
                    session_list[i] = suggestion
                    break
            suggestions_by_id[suggestion.id] = suggestion
            logger.info(f"Updated suggestion for session: {session_id} (id={suggestion.id})")
        else:
            # New suggestion
            suggestions_by_session[session_id].append(suggestion)
            if suggestion.id:
                suggestions_by_id[suggestion.id] = suggestion
            logger.info(f"Processed suggestion for session: {session_id} (id={suggestion.id})")

        # Broadcast to WebSocket clients
        suggestion_dict = suggestion.model_dump()
        suggestion_dict['timestamp'] = suggestion_dict['timestamp'].isoformat()
        broadcast_type = "suggestion_updated" if is_update else "suggestion"

        global event_loop
        if event_loop and event_loop.is_running():
            asyncio.run_coroutine_threadsafe(
                manager.broadcast({
                    "type": broadcast_type,
                    "data": suggestion_dict
                }),
                event_loop
            )

    except Exception as e:
        logger.error(f"Error processing suggestion message: {e}", exc_info=True)


def process_vehicle_location_message(message_value: dict):
    """Process a vehicle location message from Kafka."""
    try:
        # Extract simulator-provided status before building VehicleLocation (which doesn't have a status field)
        status_from_sim = message_value.pop("status", None)

        if isinstance(message_value.get('timestamp'), str):
            message_value['timestamp'] = datetime.fromisoformat(message_value['timestamp'])

        location = VehicleLocation(**message_value)

        # Use simulator status as source of truth when available; fall back to internal tracking
        if status_from_sim:
            vehicle_statuses[location.vehicle_id] = status_from_sim
        status = vehicle_statuses.get(location.vehicle_id, "available")

        location_dict = location.model_dump()
        location_dict['timestamp'] = location_dict['timestamp'].isoformat()
        location_dict['status'] = status

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

        # Persist active route so it survives frontend refreshes
        if vehicle_id and route:
            active_routes[vehicle_id] = {"incident_id": incident_id, "route": route}

        # Track vehicle status
        if vehicle_id:
            vehicle_statuses[vehicle_id] = "dispatched"

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

        # Clear the active route; status is managed by simulator via location messages
        if vehicle_id:
            active_routes.pop(vehicle_id, None)
            vehicle_statuses[vehicle_id] = "returning"

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
