"""
Geospatial Dispatch Service - Tracks vehicles and provides assignment recommendations.
"""

import os
import math
import logging
import sys
import time
import uuid
import threading
from datetime import datetime
from typing import Optional

import numpy as np
import requests as http_requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from shared.types import Vehicle, AssignmentSuggestion, VehicleDispatchEvent
from shared.kafka_client import create_producer, create_consumer
from shared.db import get_connection
from optimization import run_weighted_dispatch_with_hospitals
from vehicle_tracker import VehicleLocationTracker

# Add parent directory to path to access shared module
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
sys.path.insert(0, parent_dir)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Geospatial Dispatch Service", version="0.1.0")

# Enable CORS for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def load_vehicles_from_db():
    """Load vehicles from the DB. Returns list of Vehicle objects."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, lat, lon, status, vehicle_type FROM vehicles ORDER BY id")
            rows = cur.fetchall()
            if not rows:
                logger.warning("No vehicles found in DB!")
                return []
            return [
                Vehicle(
                    id=r[0], lat=float(r[1]), lon=float(r[2]),
                    status=r[3], vehicle_type=r[4],
                )
                for r in rows
            ]
    finally:
        conn.close()


# Vehicles list and tracker — initialized at startup from DB
vehicles: list[Vehicle] = []
vehicle_tracker: VehicleLocationTracker | None = None

def get_hospitals_from_db():
    """Load hospitals from DB. Returns (np.array of coords, list of metadata dicts)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, lat, lon, address FROM hospitals ORDER BY id")
            rows = cur.fetchall()
            if not rows:
                # Fallback to Grand River Hospital if DB is empty
                return (
                    np.array([[43.455280, -80.505836]]),
                    [{"id": 0, "name": "Grand River Hospital", "lat": 43.455280,
                      "lon": -80.505836, "address": "835 King St W, Kitchener, ON N2G 1G3"}],
                )
            coords = np.array([[float(r[2]), float(r[3])] for r in rows])
            metadata = [{"id": r[0], "name": r[1], "lat": float(r[2]),
                         "lon": float(r[3]), "address": r[4]} for r in rows]
            return coords, metadata
    finally:
        conn.close()

# Kafka producer for dispatch events
kafka_producer = None

OSRM_BASE_URL = "https://router.project-osrm.org"


def fetch_route_from_osrm(origin_lat: float, origin_lon: float, dest_lat: float, dest_lon: float):
    """Fetch a driving route from OSRM. Returns (route, duration_seconds) tuple."""
    try:
        # OSRM expects lon,lat order
        url = f"{OSRM_BASE_URL}/route/v1/driving/{origin_lon},{origin_lat};{dest_lon},{dest_lat}?overview=full&geometries=geojson"
        resp = http_requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != "Ok" or not data.get("routes"):
            logger.warning(f"OSRM returned no route: {data.get('code')}")
            return [], None
        route_data = data["routes"][0]
        # GeoJSON coordinates are [lon, lat] — flip to [lat, lon]
        coords = route_data["geometry"]["coordinates"]
        duration = route_data.get("duration")  # seconds
        return [[c[1], c[0]] for c in coords], duration
    except Exception as e:
        logger.error(f"OSRM route fetch failed: {e}")
        return [], None


def lifecycle_consumer_thread():
    """Background thread that consumes vehicle lifecycle events to update vehicle status."""
    try:
        consumer = create_consumer(
            topics=["vehicle-arrivals", "vehicle-transporting", "vehicle-at-hospital", "vehicle-resolved"],
            group_id="geospatial-lifecycle-consumer",
            auto_offset_reset="latest",
        )
        logger.info("Lifecycle consumer started, listening for vehicle lifecycle events...")
        for message in consumer:
            try:
                data = message.value
                vehicle_id = data.get("vehicle_id")
                if not vehicle_id:
                    continue
                vehicle = next((v for v in vehicles if v.id == vehicle_id), None)
                if not vehicle:
                    continue

                topic = message.topic
                if topic == "vehicle-arrivals":
                    vehicle.status = "on_scene"
                    logger.info(f"Vehicle {vehicle_id} arrived at scene (on_scene)")
                elif topic == "vehicle-transporting":
                    vehicle.status = "transporting"
                    logger.info(f"Vehicle {vehicle_id} transporting to hospital")
                elif topic == "vehicle-at-hospital":
                    vehicle.status = "at_hospital"
                    logger.info(f"Vehicle {vehicle_id} at hospital")
                elif topic == "vehicle-resolved":
                    vehicle.status = "available"
                    logger.info(f"Vehicle {vehicle_id} resolved, status reset to available")
            except Exception as e:
                logger.error(f"Error processing lifecycle message: {e}")
    except Exception as e:
        logger.error(f"Fatal error in lifecycle consumer: {e}")


@app.on_event("startup")
async def startup_event():
    global kafka_producer, vehicles, vehicle_tracker
    kafka_producer = create_producer()

    # Load vehicles from DB with retry (postgres may still be starting)
    for attempt in range(10):
        try:
            vehicles = load_vehicles_from_db()
            logger.info(f"Loaded {len(vehicles)} vehicles from DB")
            break
        except Exception as e:
            logger.warning(f"Failed to load vehicles from DB (attempt {attempt + 1}/10): {e}")
            time.sleep(2)
    else:
        logger.error("Could not load vehicles from DB after 10 attempts")

    vehicle_tracker = VehicleLocationTracker(vehicles)
    vehicle_tracker.start_consumer()
    threading.Thread(target=lifecycle_consumer_thread, daemon=True).start()


# In-memory storage for vehicle assignments
vehicle_assignments = {}


class FindBestRequest(BaseModel):
    incident_id: str
    exclude_vehicles: list[str] = []


ACTIVE_INCIDENT_STATUSES = ('open', 'dispatched', 'en_route', 'on_scene', 'transporting', 'at_hospital')


def get_open_incidents():
    """Fetch all active (non-resolved) incidents from DB."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            placeholders = ','.join(['%s'] * len(ACTIVE_INCIDENT_STATUSES))
            cur.execute(
                f"SELECT id, lat, lon, weight, status, assigned_vehicle_id, type, priority, location FROM incidents WHERE status IN ({placeholders})",
                ACTIVE_INCIDENT_STATUSES,
            )
            rows = cur.fetchall()
            return [{
                "id": r[0], "lat": float(r[1]), "lon": float(r[2]), "weight": r[3],
                "status": r[4], "assigned_vehicle_id": r[5], "type": r[6],
                "priority": r[7], "location": r[8],
            } for r in rows]
    finally:
        conn.close()


def get_incident_by_id(incident_id: str):
    """Fetch a single incident from DB."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, lat, lon, weight, status, type, priority, location FROM incidents WHERE id = %s",
                (incident_id,)
            )
            row = cur.fetchone()
            if row:
                return {
                    "id": row[0], "lat": float(row[1]), "lon": float(row[2]),
                    "weight": row[3], "status": row[4],
                    "type": row[5], "priority": row[6], "location": row[7],
                }
            return None
    finally:
        conn.close()


def update_incident_status(incident_id: str, status: str):
    """Update an incident's status in DB."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE incidents SET status = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                (status, incident_id)
            )
        conn.commit()
    finally:
        conn.close()


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate Euclidean distance between two GPS coordinates.

    Args:
        lat1, lon1: First coordinate
        lat2, lon2: Second coordinate

    Returns:
        Distance in approximate kilometers
    """
    # TODO: Note: Use dedicated routing service.
    # Simplified distance calculation (Euclidean)
    return math.sqrt((lat2 - lat1) ** 2 + (lon2 - lon1) ** 2) * 111  # Rough km conversion




@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "geospatial-dispatch"}


@app.get("/vehicles")
async def get_vehicles(status: Optional[str] = None):
    """
    Get list of vehicles, optionally filtered by status.

    Args:
        status: Optional status filter (e.g., "available", "dispatched")

    Returns:
        List of vehicles
    """
    vehicle_tracker.update_vehicle_positions()
    result = vehicles
    if status:
        result = [v for v in vehicles if v.status == status]

    return {
        "vehicles": [v.model_dump() for v in result]
    }


@app.get("/vehicles/{vehicle_id}")
async def get_vehicle(vehicle_id: str):
    """
    Get a specific vehicle by ID.

    Args:
        vehicle_id: Vehicle identifier

    Returns:
        Vehicle details
    """
    vehicle_tracker.update_vehicle_positions()
    vehicle = next((v for v in vehicles if v.id == vehicle_id), None)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    return vehicle.model_dump()


@app.post("/assignments/find-best")
async def find_best_assignment(request: FindBestRequest):
    """
    Find the best vehicle for an incident (by ID), considering the current global state.
    Considers both available and dispatched vehicles. If the optimizer assigns a dispatched
    vehicle (reroute), the response includes preempted incident info and a reassignment vehicle.
    """
    vehicle_tracker.update_vehicle_positions()

    # Look up the target incident from DB
    target_incident = get_incident_by_id(request.incident_id)
    if not target_incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    # Get all open incidents from DB for full optimization context
    all_open_incidents = get_open_incidents()

    # Eligible vehicles: available + dispatched (NOT on_scene/transporting/at_hospital)
    # "dispatched" in geospatial-dispatch covers both "Dispatched" and "En Route" on the frontend
    exclude_set = set(request.exclude_vehicles)
    eligible_vehicles = [v for v in vehicles if v.status in ("available", "dispatched") and v.id not in exclude_set]
    dispatched_eligible = [v.id for v in eligible_vehicles if v.status == "dispatched"]
    available_eligible = [v.id for v in eligible_vehicles if v.status == "available"]
    logger.info(f"find-best: {len(available_eligible)} available + {len(dispatched_eligible)} dispatched/en-route vehicles eligible. Dispatched: {dispatched_eligible}")
    if not eligible_vehicles:
        raise HTTPException(status_code=503, detail="No available or reroutable vehicles to assign")

    # Build current_assignments map: {vehicle_id: incident_dict} for dispatched vehicles
    current_assignments = {}
    for inc in all_open_incidents:
        if inc["status"] == "dispatched" and inc.get("assigned_vehicle_id"):
            current_assignments[inc["assigned_vehicle_id"]] = inc

    # Optimizable incidents: open + dispatched (assignable states)
    optimizable_incidents = [inc for inc in all_open_incidents if inc["status"] in ("open", "dispatched")]

    # Load hospitals from DB
    hospital_coords, hospital_metadata = get_hospitals_from_db()

    # Run the full optimization model on the current state
    dispatch_results = run_weighted_dispatch_with_hospitals(
        eligible_vehicles, optimizable_incidents, hospital_coords, verbose=True
    )

    # Find the assignment for our specific target incident
    assignment_for_target = None
    target_index = None
    for idx, inc in enumerate(optimizable_incidents):
        if inc["id"] == request.incident_id:
            target_index = idx
            break

    if target_index is not None:
        for round_summary in dispatch_results.get("rounds", []):
            for assignment in round_summary.get("assignments", []):
                if assignment["incident_id"] == target_index:
                    assignment_for_target = assignment
                    break
            if assignment_for_target:
                break

    if not assignment_for_target:
        raise HTTPException(status_code=404, detail="Could not find a suitable assignment for the incident.")

    primary_vehicle_id = assignment_for_target["ambulance_id"]

    # Detect reroute: is the assigned vehicle currently dispatched to another case?
    is_reroute = primary_vehicle_id in current_assignments
    preempted_incident = current_assignments.get(primary_vehicle_id) if is_reroute else None

    # Build reassignment info if this is a reroute
    reassignment_info = None
    if is_reroute and preempted_incident:
        # Find the optimizer's assignment for the preempted incident
        preempted_index = None
        for idx, inc in enumerate(optimizable_incidents):
            if inc["id"] == preempted_incident["id"]:
                preempted_index = idx
                break

        reassignment_assignment = None
        if preempted_index is not None:
            for round_summary in dispatch_results.get("rounds", []):
                for assignment in round_summary.get("assignments", []):
                    if assignment["incident_id"] == preempted_index and assignment["ambulance_id"] != primary_vehicle_id:
                        reassignment_assignment = assignment
                        break
                if reassignment_assignment:
                    break

        if reassignment_assignment:
            reassignment_vehicle_id = reassignment_assignment["ambulance_id"]
            reassignment_vehicle = next((v for v in vehicles if v.id == reassignment_vehicle_id), None)

            # Fetch OSRM route for reassignment vehicle -> preempted incident
            reassign_route = []
            reassign_duration = None
            if reassignment_vehicle:
                reassign_route, reassign_duration = fetch_route_from_osrm(
                    reassignment_vehicle.lat, reassignment_vehicle.lon,
                    preempted_incident["lat"], preempted_incident["lon"]
                )

            # Hospital for preempted incident
            reassign_hospital_idx = reassignment_assignment.get("hospital_id", 0)
            reassign_hospital = hospital_metadata[reassign_hospital_idx] if reassign_hospital_idx < len(hospital_metadata) else hospital_metadata[0]

            reassignment_info = {
                "vehicle_id": reassignment_vehicle_id,
                "incident_id": preempted_incident["id"],
                "route_preview": reassign_route,
                "duration_seconds": int(reassign_duration) if reassign_duration else None,
                "hospital": reassign_hospital,
            }

    # Generate route description
    route_description = (
        f"Optimized route for {primary_vehicle_id} to incident at "
        f"(lat: {target_incident['lat']:.4f}, lon: {target_incident['lon']:.4f}). "
        f"Total unweighted distance: {assignment_for_target['unweighted_dist']:.2f} km."
    )

    # Fetch route preview from OSRM for primary vehicle -> target incident
    vehicle = next((v for v in vehicles if v.id == primary_vehicle_id), None)
    route_preview = []
    route_duration = None
    if vehicle:
        route_preview, route_duration = fetch_route_from_osrm(
            vehicle.lat, vehicle.lon, target_incident["lat"], target_incident["lon"]
        )

    # Map optimizer hospital_id (index) to metadata
    hospital_idx = assignment_for_target.get("hospital_id", 0)
    hospital = hospital_metadata[hospital_idx] if hospital_idx < len(hospital_metadata) else hospital_metadata[0]

    # Generate a unique suggestion ID
    suggestion_id = str(uuid.uuid4())

    # Create the assignment suggestion with reroute fields
    assignment_suggestion = AssignmentSuggestion(
        suggestion_id=suggestion_id,
        suggested_vehicle_id=primary_vehicle_id,
        route=route_description,
        timestamp=datetime.now(),
        hospital_id=hospital["id"],
        hospital_name=hospital["name"],
        hospital_lat=hospital["lat"],
        hospital_lon=hospital["lon"],
        hospital_address=hospital.get("address"),
        is_reroute=is_reroute,
        preempted_incident_id=preempted_incident["id"] if preempted_incident else None,
        preempted_incident_priority=preempted_incident.get("priority") if preempted_incident else None,
        preempted_incident_type=preempted_incident.get("type") if preempted_incident else None,
        preempted_incident_location=preempted_incident.get("location") if preempted_incident else None,
    )

    vehicle_assignments[suggestion_id] = {
        "suggestion": assignment_suggestion,
        "incident_id": request.incident_id,
        "route_preview": route_preview,
        "hospital": hospital,
        "is_reroute": is_reroute,
        "reassignment": reassignment_info,
        "preempted_incident": preempted_incident,
    }

    logger.info(f"Generated {'reroute' if is_reroute else 'normal'} assignment for suggestion {suggestion_id}: vehicle {primary_vehicle_id}, hospital {hospital['name']}")

    result = assignment_suggestion.model_dump()
    result["route_preview"] = route_preview
    result["incident"] = {
        "id": target_incident["id"],
        "type": target_incident.get("type"),
        "priority": target_incident.get("priority"),
        "location": target_incident.get("location"),
        "lat": target_incident["lat"],
        "lon": target_incident["lon"],
    }
    result["hospital"] = hospital
    result["duration_seconds"] = int(route_duration) if route_duration else None
    if reassignment_info:
        result["reassignment"] = reassignment_info
    return result


@app.get("/assignments/{suggestion_id}")
async def get_assignment(suggestion_id: str):
    """
    Retrieve a previously generated assignment suggestion by its suggestion ID.
    """
    # If assignment already exists, return it
    if suggestion_id in vehicle_assignments:
        return vehicle_assignments[suggestion_id]["suggestion"].model_dump()

    # If the suggestion_id is not found, raise an error
    raise HTTPException(status_code=404, detail="Assignment not found")


@app.post("/assignments/{suggestion_id}/accept")
async def accept_assignment(suggestion_id: str):
    """
    Accept a vehicle assignment (mark vehicle as dispatched).
    For reroutes: publishes two dispatch events (primary + reassignment) and
    validates that the rerouted vehicle hasn't progressed past dispatched.
    """
    if suggestion_id not in vehicle_assignments:
        raise HTTPException(status_code=404, detail="Assignment not found")

    entry = vehicle_assignments[suggestion_id]
    assignment = entry["suggestion"]
    incident_id = entry.get("incident_id")
    is_reroute = entry.get("is_reroute", False)
    reassignment_info = entry.get("reassignment")

    vehicle = next((v for v in vehicles if v.id == assignment.suggested_vehicle_id), None)

    # Race condition check: if reroute, verify vehicle hasn't progressed past dispatched
    if is_reroute and vehicle and vehicle.status not in ("available", "dispatched"):
        del vehicle_assignments[suggestion_id]
        raise HTTPException(
            status_code=409,
            detail=f"Vehicle {vehicle.id} has progressed to '{vehicle.status}' and can no longer be rerouted"
        )

    if vehicle:
        vehicle.status = "dispatched"
        logger.info(f"Accepted {'reroute' if is_reroute else 'normal'} assignment for suggestion {suggestion_id}: vehicle {vehicle.id} dispatched")

    # Publish primary dispatch event: primary_vehicle -> target_incident
    if vehicle and incident_id:
        incident = get_incident_by_id(incident_id)
        if incident:
            route = entry.get("route_preview")
            if not route:
                route, _ = fetch_route_from_osrm(vehicle.lat, vehicle.lon, incident["lat"], incident["lon"])
            hospital = entry.get("hospital", {})
            dispatch_event = VehicleDispatchEvent(
                vehicle_id=vehicle.id,
                incident_id=incident_id,
                incident_lat=incident["lat"],
                incident_lon=incident["lon"],
                route=route,
                timestamp=datetime.now(),
                hospital_lat=hospital.get("lat"),
                hospital_lon=hospital.get("lon"),
                hospital_name=hospital.get("name"),
            )
            if kafka_producer and route:
                kafka_producer.send(
                    "vehicle-dispatches",
                    key=vehicle.id.encode("utf-8"),
                    value=dispatch_event.model_dump(mode="json"),
                )
                kafka_producer.flush()
                logger.info(f"Published dispatch event for {vehicle.id} with {len(route)} waypoints")

    # If reroute, publish second dispatch event: reassignment_vehicle -> preempted_incident
    if is_reroute and reassignment_info:
        reassign_vehicle_id = reassignment_info["vehicle_id"]
        reassign_incident_id = reassignment_info["incident_id"]
        reassign_vehicle = next((v for v in vehicles if v.id == reassign_vehicle_id), None)

        if reassign_vehicle:
            reassign_vehicle.status = "dispatched"

        preempted_incident = get_incident_by_id(reassign_incident_id)
        if preempted_incident and reassign_vehicle:
            reassign_route = reassignment_info.get("route_preview", [])
            if not reassign_route:
                reassign_route, _ = fetch_route_from_osrm(
                    reassign_vehicle.lat, reassign_vehicle.lon,
                    preempted_incident["lat"], preempted_incident["lon"]
                )
            reassign_hospital = reassignment_info.get("hospital", {})
            reassign_dispatch_event = VehicleDispatchEvent(
                vehicle_id=reassign_vehicle.id,
                incident_id=reassign_incident_id,
                incident_lat=preempted_incident["lat"],
                incident_lon=preempted_incident["lon"],
                route=reassign_route,
                timestamp=datetime.now(),
                hospital_lat=reassign_hospital.get("lat"),
                hospital_lon=reassign_hospital.get("lon"),
                hospital_name=reassign_hospital.get("name"),
            )
            if kafka_producer and reassign_route:
                kafka_producer.send(
                    "vehicle-dispatches",
                    key=reassign_vehicle.id.encode("utf-8"),
                    value=reassign_dispatch_event.model_dump(mode="json"),
                )
                kafka_producer.flush()
                logger.info(f"Published reassignment dispatch event for {reassign_vehicle.id} -> incident {reassign_incident_id}")

    return {"status": "accepted", "suggestion_id": suggestion_id, "vehicle_id": assignment.suggested_vehicle_id}


@app.post("/admin/reset")
async def admin_reset():
    """Reset all in-memory state: vehicles back to available, clear assignments."""
    for vehicle in vehicles:
        vehicle.status = "available"
    vehicle_assignments.clear()
    vehicle_tracker.reset_positions(vehicles)
    logger.info("Admin reset: all vehicles available, assignments cleared")
    return {"status": "reset_complete"}


@app.post("/assignments/{suggestion_id}/decline")
async def decline_assignment(suggestion_id: str):
    """Decline a vehicle assignment suggestion, removing it from memory."""
    if suggestion_id not in vehicle_assignments:
        raise HTTPException(status_code=404, detail="Assignment not found")

    del vehicle_assignments[suggestion_id]
    logger.info(f"Declined assignment suggestion {suggestion_id}")
    return {"status": "declined", "suggestion_id": suggestion_id}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
