"""
Dashboard API Service - Aggregated API and WebSocket gateway for frontend.

All sessions, transcripts, suggestions, incidents, and dispatch routes are
persisted in PostgreSQL. Only ephemeral vehicle statuses remain in-memory
(they rebuild from live Kafka location messages on restart).
"""

import os
import json
import logging
import sys
import asyncio
import threading
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx

from shared.kafka_client import create_consumer
from shared.types import Transcript, Suggestion, VehicleLocation, PRIORITY_WEIGHT_MAP
from shared.db import get_connection
from shared.acr_codes import get_acr_codes_for_api

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
sys.path.insert(0, parent_dir)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Dashboard API Service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ephemeral in-memory state (rebuilds from Kafka on restart)
vehicle_statuses: Dict[str, str] = {}


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
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error sending to WebSocket client: {e}")
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn)


manager = ConnectionManager()

GEOSPATIAL_DISPATCH_URL = os.getenv("GEOSPATIAL_DISPATCH_URL", "http://geospatial-dispatch:8002")

event_loop = None


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

INCIDENT_SELECT = """SELECT id, session_id, lat, lon, location, type, priority, weight,
                            status, source, assigned_vehicle_id, reported_at, updated_at
                     FROM incidents"""


def _row_to_incident_dict(row) -> dict:
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
        "source": row[9],
        "assigned_vehicle_id": row[10],
        "reported_at": row[11].isoformat() if row[11] else None,
        "updated_at": row[12].isoformat() if row[12] else None,
    }


def _log_incident_event(conn, incident_id: str, event_type: str,
                         old_status: str = None, new_status: str = None,
                         vehicle_id: str = None, metadata: dict = None):
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO incident_events
               (incident_id, event_type, old_status, new_status, vehicle_id, timestamp, metadata)
               VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, %s)""",
            (incident_id, event_type, old_status, new_status, vehicle_id,
             json.dumps(metadata) if metadata else None),
        )


def _row_to_suggestion_dict(row) -> dict:
    return {
        "id": row[0],
        "session_id": row[1],
        "suggestion_type": row[2],
        "value": row[3],
        "status": row[4],
        "timestamp": row[5].isoformat() if row[5] else None,
        "incident_code": row[6],
        "incident_code_description": row[7],
        "incident_code_category": row[8],
        "priority": row[9],
        "confidence": float(row[10]) if row[10] is not None else None,
        "matched_evidence": row[11],
        "extracted_location": row[12],
        "extracted_lat": float(row[13]) if row[13] is not None else None,
        "extracted_lon": float(row[14]) if row[14] is not None else None,
        "location_confidence": float(row[15]) if row[15] is not None else None,
    }


SUGGESTION_SELECT = """SELECT id, session_id, suggestion_type, value, status, timestamp,
                              incident_code, incident_code_description, incident_code_category,
                              priority, confidence, matched_evidence,
                              extracted_location, extracted_lat, extracted_lon, location_confidence
                       FROM suggestions"""


def _broadcast_incident_update_from_thread(incident_dict: dict):
    """Schedule an incident_updated broadcast from a Kafka consumer thread."""
    global event_loop
    if event_loop and event_loop.is_running():
        asyncio.run_coroutine_threadsafe(
            manager.broadcast({"type": "incident_updated", "data": incident_dict}),
            event_loop,
        )


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class CreateIncidentRequest(BaseModel):
    session_id: Optional[str] = None
    lat: float
    lon: float
    location: Optional[str] = None
    type: Optional[str] = None
    priority: str = "Yellow"
    weight: Optional[int] = None
    source: str = "manual"


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


class FindBestRequest(BaseModel):
    incident_id: str
    exclude_vehicles: list[str] = []


class DeclineAndReassignRequest(BaseModel):
    incident_id: str
    declined_vehicle_id: str


class GeocodeRequest(BaseModel):
    address: str


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "dashboard-api"}


# ---------------------------------------------------------------------------
# Incident CRUD
# ---------------------------------------------------------------------------

@app.get("/incidents")
async def list_incidents(status: Optional[str] = None, source: Optional[str] = None):
    """List incidents, optionally filtered by status and/or source."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            wheres: list[str] = []
            params: list = []
            if status:
                wheres.append("status = %s")
                params.append(status)
            if source:
                wheres.append("source = %s")
                params.append(source)
            where_clause = (" WHERE " + " AND ".join(wheres)) if wheres else ""
            cur.execute(f"{INCIDENT_SELECT}{where_clause} ORDER BY reported_at DESC", params)
            rows = cur.fetchall()
            return {"incidents": [_row_to_incident_dict(r) for r in rows]}
    finally:
        conn.close()


@app.get("/incidents/{incident_id}")
async def get_incident(incident_id: str):
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
    """Create a new incident. Source defaults to 'manual'; use 'call_taker' for manual entries from the call-taker UI (also triggers auto-dispatch)."""
    source = req.source if req.source in ("manual", "call_taker") else "manual"
    incident_id = str(uuid.uuid4())
    weight = req.weight if req.weight is not None else PRIORITY_WEIGHT_MAP.get(req.priority, 2)
    now = datetime.now(timezone.utc)

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if source == "call_taker" and req.session_id:
                cur.execute(
                    "INSERT INTO sessions (id, created_at, status) VALUES (%s, %s, 'active') ON CONFLICT (id) DO NOTHING",
                    (req.session_id, now),
                )
            cur.execute(
                """INSERT INTO incidents
                   (id, session_id, lat, lon, location, type, priority, weight, status, source, reported_at, updated_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'open', %s, %s, %s)""",
                (incident_id, req.session_id, req.lat, req.lon,
                 req.location, req.type, req.priority, weight, source, now, now),
            )
            _log_incident_event(conn, incident_id, "created", None, "open")
        conn.commit()

        with conn.cursor() as cur:
            cur.execute(f"{INCIDENT_SELECT} WHERE id = %s", (incident_id,))
            incident_dict = _row_to_incident_dict(cur.fetchone())
    finally:
        conn.close()

    await manager.broadcast({"type": "incident_created", "data": incident_dict})
    logger.info(f"Created incident {incident_id} (source={source})")

    dispatch_data = None
    if source == "call_taker":
        dispatch_data = await _find_best_and_broadcast(incident_id)

    return {"incident": incident_dict, "dispatch_suggestion": dispatch_data}


@app.patch("/incidents/{incident_id}")
async def update_incident(incident_id: str, req: UpdateIncidentRequest):
    updates: list[str] = []
    params: list = []
    if req.status is not None:
        updates.append("status = %s")
        params.append(req.status)
    if req.priority is not None:
        updates.append("priority = %s")
        params.append(req.priority)
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
        old_status = None
        if req.status is not None:
            with conn.cursor() as cur:
                cur.execute("SELECT status FROM incidents WHERE id = %s", (incident_id,))
                row = cur.fetchone()
                if row:
                    old_status = row[0]

        with conn.cursor() as cur:
            cur.execute(f"UPDATE incidents SET {', '.join(updates)} WHERE id = %s", params)
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Incident not found")

        if req.status is not None and old_status:
            _log_incident_event(conn, incident_id, "status_change", old_status, req.status)

        conn.commit()

        with conn.cursor() as cur:
            cur.execute(f"{INCIDENT_SELECT} WHERE id = %s", (incident_id,))
            incident_dict = _row_to_incident_dict(cur.fetchone())
    finally:
        conn.close()

    await manager.broadcast({"type": "incident_updated", "data": incident_dict})
    logger.info(f"Updated incident {incident_id}")
    return incident_dict


# ---------------------------------------------------------------------------
# Sessions / Transcripts / Suggestions (DB-backed)
# ---------------------------------------------------------------------------

@app.get("/sessions")
async def get_sessions():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT s.id, s.created_at, s.status,
                       (SELECT COUNT(*) FROM transcripts t WHERE t.session_id = s.id),
                       (SELECT COUNT(*) FROM suggestions sg WHERE sg.session_id = s.id)
                FROM sessions s ORDER BY s.created_at DESC
            """)
            return {"sessions": [
                {
                    "session_id": r[0],
                    "created_at": r[1].isoformat() if r[1] else None,
                    "status": r[2],
                    "transcript_count": r[3],
                    "suggestion_count": r[4],
                }
                for r in cur.fetchall()
            ]}
    finally:
        conn.close()


@app.get("/sessions/{session_id}/transcript")
async def get_session_transcript(session_id: str):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT text, timestamp FROM transcripts WHERE session_id = %s ORDER BY timestamp ASC",
                (session_id,),
            )
            return {
                "session_id": session_id,
                "transcripts": [
                    {"session_id": session_id, "text": r[0],
                     "timestamp": r[1].isoformat() if r[1] else None}
                    for r in cur.fetchall()
                ],
            }
    finally:
        conn.close()


@app.get("/sessions/{session_id}/suggestions")
async def get_session_suggestions(session_id: str):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f"{SUGGESTION_SELECT} WHERE session_id = %s ORDER BY timestamp ASC",
                        (session_id,))
            return {
                "session_id": session_id,
                "suggestions": [_row_to_suggestion_dict(r) for r in cur.fetchall()],
            }
    finally:
        conn.close()


@app.get("/sessions/{session_id}/assignment")
async def get_session_assignment(session_id: str):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GEOSPATIAL_DISPATCH_URL}/assignments/{session_id}", timeout=5.0,
            )
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail="Assignment not found")
            response.raise_for_status()
            return response.json()
    except httpx.RequestError as e:
        logger.error(f"Error fetching assignment from geospatial service: {e}")
        raise HTTPException(status_code=503, detail="Geospatial service unavailable")


# ---------------------------------------------------------------------------
# Dispatch proxies
# ---------------------------------------------------------------------------

async def _find_best_and_broadcast(incident_id: str, exclude_vehicles: list[str] | None = None):
    """Call geospatial-dispatch find-best and broadcast the result via WebSocket."""
    if exclude_vehicles is None:
        exclude_vehicles = []
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{GEOSPATIAL_DISPATCH_URL}/assignments/find-best",
                json={"incident_id": incident_id, "exclude_vehicles": exclude_vehicles},
                timeout=15.0,
            )
            response.raise_for_status()
            data = response.json()

        suggestion_id = data.get("suggestion_id")
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """UPDATE incidents SET dispatch_metadata =
                       jsonb_set(COALESCE(dispatch_metadata, '{}'), '{suggestion_id}', %s::jsonb)
                       WHERE id = %s""",
                    (json.dumps(suggestion_id), incident_id),
                )
            conn.commit()
        finally:
            conn.close()

        await manager.broadcast({"type": "dispatch_suggestion", "data": data})
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
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{GEOSPATIAL_DISPATCH_URL}/assignments/find-best",
                json=request.model_dump(), timeout=15.0,
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code,
                            detail=e.response.json().get("detail", "Error"))
    except httpx.RequestError as e:
        logger.error(f"Error proxying find-best: {e}")
        raise HTTPException(status_code=503, detail="Geospatial service unavailable")


@app.post("/assignments/{suggestion_id}/accept")
async def proxy_accept(suggestion_id: str):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{GEOSPATIAL_DISPATCH_URL}/assignments/{suggestion_id}/accept",
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code,
                            detail=e.response.json().get("detail", "Error"))
    except httpx.RequestError as e:
        logger.error(f"Error proxying accept: {e}")
        raise HTTPException(status_code=503, detail="Geospatial service unavailable")


@app.post("/assignments/{suggestion_id}/decline")
async def proxy_decline(suggestion_id: str):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{GEOSPATIAL_DISPATCH_URL}/assignments/{suggestion_id}/decline",
                timeout=5.0,
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code,
                            detail=e.response.json().get("detail", "Error"))
    except httpx.RequestError as e:
        logger.error(f"Error proxying decline: {e}")
        raise HTTPException(status_code=503, detail="Geospatial service unavailable")


@app.post("/assignments/{suggestion_id}/decline-and-reassign")
async def decline_and_reassign(suggestion_id: str, req: DeclineAndReassignRequest):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{GEOSPATIAL_DISPATCH_URL}/assignments/{suggestion_id}/decline",
                timeout=5.0,
            )
            response.raise_for_status()
    except Exception as e:
        logger.warning(f"Error declining suggestion {suggestion_id}: {e}")

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT dispatch_metadata FROM incidents WHERE id = %s", (req.incident_id,))
            row = cur.fetchone()
            metadata = row[0] if row and row[0] else {}
            declined = metadata.get("declined_vehicles", [])
            if req.declined_vehicle_id not in declined:
                declined.append(req.declined_vehicle_id)
            metadata["declined_vehicles"] = declined
            cur.execute("UPDATE incidents SET dispatch_metadata = %s WHERE id = %s",
                        (json.dumps(metadata), req.incident_id))
        conn.commit()
    finally:
        conn.close()

    dispatch_data = await _find_best_and_broadcast(req.incident_id, exclude_vehicles=declined)
    if not dispatch_data:
        return {"status": "no_vehicles_available", "suggestion_id": suggestion_id}
    return {"status": "reassigned", "dispatch_suggestion": dispatch_data}


# ---------------------------------------------------------------------------
# Vehicles & Active Routes (DB-backed dispatches)
# ---------------------------------------------------------------------------

@app.get("/vehicles")
async def get_vehicles():
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{GEOSPATIAL_DISPATCH_URL}/vehicles", timeout=5.0)
            response.raise_for_status()
            return response.json()
    except httpx.RequestError as e:
        logger.error(f"Error fetching vehicles from geospatial service: {e}")
        raise HTTPException(status_code=503, detail="Geospatial service unavailable")


@app.get("/active-routes")
async def get_active_routes():
    """Return all active dispatch routes from DB (persists across restarts)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT vehicle_id, incident_id, route FROM dispatches WHERE status = 'active'")
            routes = {}
            for r in cur.fetchall():
                routes[r[0]] = {"incident_id": r[1], "route": r[2]}
            return {"routes": routes}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------

@app.post("/admin/reset")
async def admin_reset():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM incident_events")
            cur.execute("DELETE FROM dispatches")
            cur.execute("DELETE FROM incidents")
            cur.execute("DELETE FROM suggestions")
            cur.execute("DELETE FROM transcripts")
            cur.execute("DELETE FROM sessions")
        conn.commit()
        logger.info("Cleared all database tables")
    finally:
        conn.close()

    vehicle_statuses.clear()

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{GEOSPATIAL_DISPATCH_URL}/admin/reset", timeout=10.0)
            resp.raise_for_status()
            logger.info("Geospatial-dispatch reset successful")
    except Exception as e:
        logger.warning(f"Failed to reset geospatial-dispatch: {e}")

    await manager.broadcast({"type": "system_reset", "data": {}})
    logger.info("Admin reset complete")
    return {"status": "reset_complete"}


# ---------------------------------------------------------------------------
# Geocoding
# ---------------------------------------------------------------------------

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_HEADERS = {"User-Agent": "ERAS-EmergencyDispatch/1.0"}
NOMINATIM_VIEWBOX = "-80.7,43.3,-80.3,43.6"


@app.post("/geocode")
async def geocode_address(req: GeocodeRequest):
    if not req.address.strip():
        raise HTTPException(status_code=400, detail="Address is required")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                NOMINATIM_URL,
                params={"q": req.address, "format": "json", "limit": 1,
                        "viewbox": NOMINATIM_VIEWBOX, "bounded": 1, "countrycodes": "ca"},
                headers=NOMINATIM_HEADERS, timeout=10.0,
            )
            response.raise_for_status()
            results = response.json()
        if results:
            lat, lon = float(results[0]["lat"]), float(results[0]["lon"])
            logger.info(f"Geocoded '{req.address}' -> ({lat}, {lon})")
            return {"lat": lat, "lon": lon, "found": True}
        logger.info(f"No geocoding results for '{req.address}'")
        return {"lat": None, "lon": None, "found": False}
    except Exception as e:
        logger.warning(f"Geocoding failed for '{req.address}': {e}")
        raise HTTPException(status_code=502, detail="Geocoding service unavailable")


# ---------------------------------------------------------------------------
# ACR Codes
# ---------------------------------------------------------------------------

@app.get("/acr-codes")
async def list_acr_codes():
    return {"codes": get_acr_codes_for_api()}


# ---------------------------------------------------------------------------
# Suggestion Accept / Dismiss (DB-backed)
# ---------------------------------------------------------------------------

def _get_suggestion_from_db(suggestion_id: str) -> Optional[dict]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f"{SUGGESTION_SELECT} WHERE id = %s", (suggestion_id,))
            row = cur.fetchone()
            return _row_to_suggestion_dict(row) if row else None
    finally:
        conn.close()


@app.post("/suggestions/{suggestion_id}/accept")
async def accept_suggestion(suggestion_id: str, req: AcceptSuggestionRequest):
    """Accept a suggestion: create an incident (source=call_taker), update status, auto-dispatch."""
    suggestion = _get_suggestion_from_db(suggestion_id)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    final_priority = req.priority or suggestion.get("priority") or "Yellow"
    code_desc = req.incident_code_description or suggestion.get("incident_code_description") or ""
    code_cat = req.incident_code_category or suggestion.get("incident_code_category") or ""
    code_num = req.incident_code or suggestion.get("incident_code") or ""
    incident_type = f"Code {code_num} - {code_cat}: {code_desc}" if code_num else suggestion["value"]

    weight = PRIORITY_WEIGHT_MAP.get(final_priority, 2)
    incident_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    session_id = suggestion["session_id"]

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if session_id:
                cur.execute(
                    "INSERT INTO sessions (id, created_at, status) VALUES (%s, %s, 'active') ON CONFLICT (id) DO NOTHING",
                    (session_id, now),
                )
            cur.execute(
                """INSERT INTO incidents
                   (id, session_id, lat, lon, location, type, priority, weight, status, source, reported_at, updated_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'open', 'call_taker', %s, %s)""",
                (incident_id, session_id, req.lat, req.lon, req.location,
                 incident_type, final_priority, weight, now, now),
            )
            _log_incident_event(conn, incident_id, "created", None, "open")
            cur.execute("UPDATE suggestions SET status = 'accepted' WHERE id = %s", (suggestion_id,))
        conn.commit()

        with conn.cursor() as cur:
            cur.execute(f"{INCIDENT_SELECT} WHERE id = %s", (incident_id,))
            incident_dict = _row_to_incident_dict(cur.fetchone())
    finally:
        conn.close()

    await manager.broadcast({"type": "incident_created", "data": incident_dict})

    suggestion["status"] = "accepted"
    await manager.broadcast({"type": "suggestion_updated", "data": suggestion})

    logger.info(f"Accepted suggestion {suggestion_id}, created incident {incident_id}")

    dispatch_data = await _find_best_and_broadcast(incident_id)
    return {
        "incident": incident_dict,
        "suggestion_status": "accepted",
        "dispatch_suggestion": dispatch_data,
    }


@app.post("/suggestions/{suggestion_id}/dismiss")
async def dismiss_suggestion(suggestion_id: str):
    suggestion = _get_suggestion_from_db(suggestion_id)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE suggestions SET status = 'dismissed' WHERE id = %s", (suggestion_id,))
        conn.commit()
    finally:
        conn.close()

    suggestion["status"] = "dismissed"
    await manager.broadcast({"type": "suggestion_updated", "data": suggestion})
    logger.info(f"Dismissed suggestion {suggestion_id}")
    return {"status": "dismissed"}


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ---------------------------------------------------------------------------
# Kafka message processors (all persist to DB)
# ---------------------------------------------------------------------------

def process_transcript_message(message_value: dict):
    try:
        if isinstance(message_value.get('timestamp'), str):
            message_value['timestamp'] = datetime.fromisoformat(message_value['timestamp'])

        transcript = Transcript(**message_value)
        session_id = transcript.session_id

        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO sessions (id, created_at, status) VALUES (%s, %s, 'active') ON CONFLICT (id) DO NOTHING",
                    (session_id, transcript.timestamp),
                )
                cur.execute(
                    "INSERT INTO transcripts (session_id, text, timestamp) VALUES (%s, %s, %s)",
                    (session_id, transcript.text, transcript.timestamp),
                )
            conn.commit()
        finally:
            conn.close()

        logger.info(f"Persisted transcript for session: {session_id}")

        transcript_dict = transcript.model_dump()
        transcript_dict['timestamp'] = transcript_dict['timestamp'].isoformat()
        global event_loop
        if event_loop and event_loop.is_running():
            asyncio.run_coroutine_threadsafe(
                manager.broadcast({"type": "transcript", "data": transcript_dict}),
                event_loop,
            )
    except Exception as e:
        logger.error(f"Error processing transcript message: {e}", exc_info=True)


def process_suggestion_message(message_value: dict):
    try:
        if isinstance(message_value.get('timestamp'), str):
            message_value['timestamp'] = datetime.fromisoformat(message_value['timestamp'])

        suggestion = Suggestion(**message_value)
        session_id = suggestion.session_id

        matched_evidence_json = (json.dumps(suggestion.matched_evidence)
                                 if suggestion.matched_evidence else None)

        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO sessions (id, created_at, status) VALUES (%s, CURRENT_TIMESTAMP, 'active') ON CONFLICT (id) DO NOTHING",
                    (session_id,),
                )

                is_update = False
                if suggestion.id:
                    cur.execute("SELECT id FROM suggestions WHERE id = %s", (suggestion.id,))
                    is_update = cur.fetchone() is not None

                if is_update:
                    cur.execute(
                        """UPDATE suggestions SET suggestion_type=%s, value=%s, status=%s, timestamp=%s,
                           incident_code=%s, incident_code_description=%s, incident_code_category=%s,
                           priority=%s, confidence=%s, matched_evidence=%s,
                           extracted_location=%s, extracted_lat=%s, extracted_lon=%s, location_confidence=%s
                           WHERE id=%s""",
                        (suggestion.suggestion_type, suggestion.value, suggestion.status,
                         suggestion.timestamp, suggestion.incident_code,
                         suggestion.incident_code_description, suggestion.incident_code_category,
                         suggestion.priority, suggestion.confidence, matched_evidence_json,
                         suggestion.extracted_location, suggestion.extracted_lat,
                         suggestion.extracted_lon, suggestion.location_confidence,
                         suggestion.id),
                    )
                    logger.info(f"Updated suggestion in DB: session={session_id} id={suggestion.id}")
                else:
                    cur.execute(
                        """INSERT INTO suggestions
                           (id, session_id, suggestion_type, value, status, timestamp,
                            incident_code, incident_code_description, incident_code_category,
                            priority, confidence, matched_evidence,
                            extracted_location, extracted_lat, extracted_lon, location_confidence)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (suggestion.id, session_id, suggestion.suggestion_type, suggestion.value,
                         suggestion.status, suggestion.timestamp, suggestion.incident_code,
                         suggestion.incident_code_description, suggestion.incident_code_category,
                         suggestion.priority, suggestion.confidence, matched_evidence_json,
                         suggestion.extracted_location, suggestion.extracted_lat,
                         suggestion.extracted_lon, suggestion.location_confidence),
                    )
                    logger.info(f"Inserted suggestion in DB: session={session_id} id={suggestion.id}")
            conn.commit()
        finally:
            conn.close()

        suggestion_dict = suggestion.model_dump()
        suggestion_dict['timestamp'] = suggestion_dict['timestamp'].isoformat()
        broadcast_type = "suggestion_updated" if is_update else "suggestion"

        global event_loop
        if event_loop and event_loop.is_running():
            asyncio.run_coroutine_threadsafe(
                manager.broadcast({"type": broadcast_type, "data": suggestion_dict}),
                event_loop,
            )
    except Exception as e:
        logger.error(f"Error processing suggestion message: {e}", exc_info=True)


def process_vehicle_location_message(message_value: dict):
    try:
        status_from_sim = message_value.pop("status", None)
        if isinstance(message_value.get('timestamp'), str):
            message_value['timestamp'] = datetime.fromisoformat(message_value['timestamp'])

        location = VehicleLocation(**message_value)
        if status_from_sim:
            vehicle_statuses[location.vehicle_id] = status_from_sim
        status = vehicle_statuses.get(location.vehicle_id, "available")

        location_dict = location.model_dump()
        location_dict['timestamp'] = location_dict['timestamp'].isoformat()
        location_dict['status'] = status

        global event_loop
        if event_loop and event_loop.is_running():
            asyncio.run_coroutine_threadsafe(
                manager.broadcast({"type": "vehicle_location", "data": location_dict}),
                event_loop,
            )
    except Exception as e:
        logger.error(f"Error processing vehicle location message: {e}", exc_info=True)


def process_vehicle_dispatch_message(message_value: dict):
    """Persist dispatch route, transition incident to dispatched."""
    try:
        vehicle_id = message_value.get("vehicle_id")
        incident_id = message_value.get("incident_id")
        route_raw = message_value.get("route", [])
        route = [{"lat": point[0], "lng": point[1]} for point in route_raw]

        if vehicle_id:
            vehicle_statuses[vehicle_id] = "dispatched"

        if vehicle_id and incident_id:
            conn = get_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE dispatches SET status='completed', completed_at=CURRENT_TIMESTAMP "
                        "WHERE vehicle_id=%s AND status='active'", (vehicle_id,))
                    if route:
                        cur.execute(
                            "INSERT INTO dispatches (incident_id, vehicle_id, route, status) VALUES (%s,%s,%s,'active')",
                            (incident_id, vehicle_id, json.dumps(route)))
                    cur.execute("SELECT status FROM incidents WHERE id=%s", (incident_id,))
                    row = cur.fetchone()
                    if row:
                        old_status = row[0]
                        cur.execute(
                            "UPDATE incidents SET status='dispatched', assigned_vehicle_id=%s, updated_at=CURRENT_TIMESTAMP WHERE id=%s",
                            (vehicle_id, incident_id))
                        _log_incident_event(conn, incident_id, "status_change", old_status, "dispatched", vehicle_id)
                conn.commit()

                with conn.cursor() as cur:
                    cur.execute(f"{INCIDENT_SELECT} WHERE id=%s", (incident_id,))
                    irow = cur.fetchone()
                    if irow:
                        _broadcast_incident_update_from_thread(_row_to_incident_dict(irow))
            finally:
                conn.close()

        logger.info(f"Processed vehicle dispatch for: {vehicle_id} ({len(route)} waypoints)")

        global event_loop
        if event_loop and event_loop.is_running():
            asyncio.run_coroutine_threadsafe(
                manager.broadcast({
                    "type": "vehicle_dispatched",
                    "data": {"vehicle_id": vehicle_id, "incident_id": incident_id, "route": route},
                }),
                event_loop,
            )
    except Exception as e:
        logger.error(f"Error processing vehicle dispatch message: {e}", exc_info=True)


def process_vehicle_arrival_message(message_value: dict):
    """Vehicle arrived at scene -> transition incident to on_scene."""
    try:
        vehicle_id = message_value.get("vehicle_id")
        incident_id = message_value.get("incident_id")
        if not incident_id:
            return

        if vehicle_id:
            vehicle_statuses[vehicle_id] = "on_scene"

        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT status FROM incidents WHERE id=%s", (incident_id,))
                row = cur.fetchone()
                if not row:
                    return
                old_status = row[0]
                cur.execute("UPDATE incidents SET status='on_scene', updated_at=CURRENT_TIMESTAMP WHERE id=%s",
                            (incident_id,))
                _log_incident_event(conn, incident_id, "status_change", old_status, "on_scene", vehicle_id)
                cur.execute(
                    "UPDATE dispatches SET status='completed', completed_at=CURRENT_TIMESTAMP "
                    "WHERE vehicle_id=%s AND status='active'", (vehicle_id,))
            conn.commit()

            with conn.cursor() as cur:
                cur.execute(f"{INCIDENT_SELECT} WHERE id=%s", (incident_id,))
                irow = cur.fetchone()
                if irow:
                    _broadcast_incident_update_from_thread(_row_to_incident_dict(irow))
        finally:
            conn.close()

        logger.info(f"Incident {incident_id} on_scene after arrival of {vehicle_id}")
    except Exception as e:
        logger.error(f"Error processing vehicle arrival message: {e}", exc_info=True)


def process_vehicle_transporting_message(message_value: dict):
    """Ambulance leaving scene heading to hospital -> transporting."""
    try:
        vehicle_id = message_value.get("vehicle_id")
        incident_id = message_value.get("incident_id")
        route_raw = message_value.get("route", [])
        if not incident_id:
            return

        if vehicle_id:
            vehicle_statuses[vehicle_id] = "transporting"

        route = [{"lat": point[0], "lng": point[1]} for point in route_raw]

        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT status FROM incidents WHERE id=%s", (incident_id,))
                row = cur.fetchone()
                if not row:
                    return
                old_status = row[0]
                cur.execute("UPDATE incidents SET status='transporting', updated_at=CURRENT_TIMESTAMP WHERE id=%s",
                            (incident_id,))
                _log_incident_event(conn, incident_id, "status_change", old_status, "transporting", vehicle_id)
                if vehicle_id and route:
                    cur.execute(
                        "UPDATE dispatches SET status='completed', completed_at=CURRENT_TIMESTAMP "
                        "WHERE vehicle_id=%s AND status='active'", (vehicle_id,))
                    cur.execute(
                        "INSERT INTO dispatches (incident_id, vehicle_id, route, status) VALUES (%s,%s,%s,'active')",
                        (incident_id, vehicle_id, json.dumps(route)))
            conn.commit()

            with conn.cursor() as cur:
                cur.execute(f"{INCIDENT_SELECT} WHERE id=%s", (incident_id,))
                irow = cur.fetchone()
                if irow:
                    _broadcast_incident_update_from_thread(_row_to_incident_dict(irow))
        finally:
            conn.close()

        global event_loop
        if event_loop and event_loop.is_running():
            asyncio.run_coroutine_threadsafe(
                manager.broadcast({
                    "type": "vehicle_dispatched",
                    "data": {"vehicle_id": vehicle_id, "incident_id": incident_id, "route": route},
                }),
                event_loop,
            )
        logger.info(f"Incident {incident_id} transporting with {vehicle_id}")
    except Exception as e:
        logger.error(f"Error processing vehicle transporting message: {e}", exc_info=True)


def process_vehicle_at_hospital_message(message_value: dict):
    """Ambulance arrived at hospital -> at_hospital."""
    try:
        vehicle_id = message_value.get("vehicle_id")
        incident_id = message_value.get("incident_id")
        if not incident_id:
            return

        if vehicle_id:
            vehicle_statuses[vehicle_id] = "at_hospital"

        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT status FROM incidents WHERE id=%s", (incident_id,))
                row = cur.fetchone()
                if not row:
                    return
                old_status = row[0]
                cur.execute("UPDATE incidents SET status='at_hospital', updated_at=CURRENT_TIMESTAMP WHERE id=%s",
                            (incident_id,))
                _log_incident_event(conn, incident_id, "status_change", old_status, "at_hospital", vehicle_id)
                cur.execute(
                    "UPDATE dispatches SET status='completed', completed_at=CURRENT_TIMESTAMP "
                    "WHERE vehicle_id=%s AND status='active'", (vehicle_id,))
            conn.commit()

            with conn.cursor() as cur:
                cur.execute(f"{INCIDENT_SELECT} WHERE id=%s", (incident_id,))
                irow = cur.fetchone()
                if irow:
                    _broadcast_incident_update_from_thread(_row_to_incident_dict(irow))
        finally:
            conn.close()
        logger.info(f"Incident {incident_id} at_hospital with {vehicle_id}")
    except Exception as e:
        logger.error(f"Error processing vehicle at-hospital message: {e}", exc_info=True)


def process_vehicle_resolved_message(message_value: dict):
    """Vehicle done at hospital -> resolve incident."""
    try:
        vehicle_id = message_value.get("vehicle_id")
        incident_id = message_value.get("incident_id")
        if not incident_id:
            return

        if vehicle_id:
            vehicle_statuses[vehicle_id] = "returning"

        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT status FROM incidents WHERE id=%s", (incident_id,))
                row = cur.fetchone()
                if not row:
                    return
                old_status = row[0]
                cur.execute("UPDATE incidents SET status='resolved', updated_at=CURRENT_TIMESTAMP WHERE id=%s",
                            (incident_id,))
                _log_incident_event(conn, incident_id, "status_change", old_status, "resolved", vehicle_id)
                cur.execute(
                    "UPDATE dispatches SET status='completed', completed_at=CURRENT_TIMESTAMP "
                    "WHERE vehicle_id=%s AND status='active'", (vehicle_id,))
            conn.commit()

            with conn.cursor() as cur:
                cur.execute(f"{INCIDENT_SELECT} WHERE id=%s", (incident_id,))
                irow = cur.fetchone()
                if irow:
                    _broadcast_incident_update_from_thread(_row_to_incident_dict(irow))
        finally:
            conn.close()
        logger.info(f"Incident {incident_id} resolved after {vehicle_id} completed at hospital")
    except Exception as e:
        logger.error(f"Error processing vehicle resolved message: {e}", exc_info=True)


# ---------------------------------------------------------------------------
# Kafka consumer thread
# ---------------------------------------------------------------------------

def kafka_consumer_thread():
    bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
    logger.info(f"Starting Kafka consumer. Connecting to: {bootstrap_servers}")

    try:
        consumer = create_consumer(
            topics=[
                "transcripts", "suggestions",
                "vehicle-locations", "vehicle-dispatches", "vehicle-arrivals",
                "vehicle-transporting", "vehicle-at-hospital", "vehicle-resolved",
            ],
            group_id="dashboard-api-service",
            bootstrap_servers=bootstrap_servers,
        )
        logger.info("Kafka consumer started. Waiting for messages...")

        for message in consumer:
            try:
                topic = message.topic
                mv = message.value

                if topic == "transcripts":
                    process_transcript_message(mv)
                elif topic == "suggestions":
                    process_suggestion_message(mv)
                elif topic == "vehicle-locations":
                    process_vehicle_location_message(mv)
                elif topic == "vehicle-dispatches":
                    process_vehicle_dispatch_message(mv)
                elif topic == "vehicle-arrivals":
                    process_vehicle_arrival_message(mv)
                elif topic == "vehicle-transporting":
                    process_vehicle_transporting_message(mv)
                elif topic == "vehicle-at-hospital":
                    process_vehicle_at_hospital_message(mv)
                elif topic == "vehicle-resolved":
                    process_vehicle_resolved_message(mv)
            except Exception as e:
                logger.error(f"Error processing Kafka message: {e}", exc_info=True)
                continue
    except Exception as e:
        logger.error(f"Fatal error in Kafka consumer: {e}", exc_info=True)
    finally:
        if 'consumer' in locals():
            consumer.close()


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup_event():
    global event_loop
    event_loop = asyncio.get_event_loop()
    kafka_thread = threading.Thread(target=kafka_consumer_thread, daemon=True)
    kafka_thread.start()
    logger.info("Dashboard API Service started")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Dashboard API Service shutting down")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
