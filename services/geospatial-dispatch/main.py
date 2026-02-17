"""
Geospatial Dispatch Service - Tracks vehicles and provides assignment recommendations.
"""

import os
import math
import logging
import sys
import uuid
from datetime import datetime
from typing import Optional

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from shared.types import Vehicle, AssignmentSuggestion
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

# Mock vehicle data
MOCK_VEHICLES = [
    Vehicle(
        id="ambulance-1",
        lat=43.4723,
        lon=-80.5449,
        status="available",
        vehicle_type="ambulance",
    ),
    Vehicle(
        id="ambulance-2",
        lat=43.4515,
        lon=-80.4925,
        status="available",
        vehicle_type="ambulance",
    ),
    Vehicle(
        id="ambulance-3",
        lat=43.4643,
        lon=-80.5204,
        status="available",
        vehicle_type="ambulance",
    ),
    Vehicle(
        id="ambulance-4",
        lat=43.4583,
        lon=-80.5025,
        status="dispatched",
        vehicle_type="ambulance",
    ),
    Vehicle(
        id="ambulance-5",
        lat=43.4553,
        lon=-80.5165,
        status="available",
        vehicle_type="ambulance",
    ),
]

# Mock hospital data (lat, lng)
MOCK_HOSPITALS = np.array([
    [43.5313, -80.3458],  # Hospital 0
    [43.6537, -80.7036]   # Hospital 1
])

# Vehicle location tracker (updates positions from Kafka)
vehicle_tracker = VehicleLocationTracker(MOCK_VEHICLES)


@app.on_event("startup")
async def startup_event():
    vehicle_tracker.start_consumer()


# In-memory storage for vehicle assignments
vehicle_assignments = {}


class FindBestRequest(BaseModel):
    incident_id: str


def get_open_incidents():
    """Fetch all open/in_progress incidents from DB."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, lat, lon, weight, status FROM incidents WHERE status IN ('open', 'in_progress')"
            )
            rows = cur.fetchall()
            return [{"id": r[0], "lat": float(r[1]), "lon": float(r[2]), "weight": r[3], "status": r[4]} for r in rows]
    finally:
        conn.close()


def get_incident_by_id(incident_id: str):
    """Fetch a single incident from DB."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, lat, lon, weight, status FROM incidents WHERE id = %s",
                (incident_id,)
            )
            row = cur.fetchone()
            if row:
                return {"id": row[0], "lat": float(row[1]), "lon": float(row[2]), "weight": row[3], "status": row[4]}
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
    vehicles = MOCK_VEHICLES
    if status:
        vehicles = [v for v in vehicles if v.status == status]

    return {
        "vehicles": [v.model_dump() for v in vehicles]
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
    vehicle = next((v for v in MOCK_VEHICLES if v.id == vehicle_id), None)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    return vehicle.model_dump()


@app.post("/assignments/find-best")
async def find_best_assignment(request: FindBestRequest):
    """
    Find the best vehicle for an incident (by ID), considering the current global state.
    Reads the target incident and all other open incidents from DB.
    """
    vehicle_tracker.update_vehicle_positions()

    # Look up the target incident from DB
    target_incident = get_incident_by_id(request.incident_id)
    if not target_incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    # Get all open incidents from DB for full optimization context
    all_open_incidents = get_open_incidents()

    # Get all currently available vehicles
    available_vehicles = [v for v in MOCK_VEHICLES if v.status == "available"]
    if not available_vehicles:
        raise HTTPException(status_code=503, detail="No available vehicles to assign")

    # Run the full optimization model on the current state
    dispatch_results = run_weighted_dispatch_with_hospitals(
        available_vehicles, all_open_incidents, MOCK_HOSPITALS, verbose=True
    )

    # Find the assignment for our specific target incident
    assignment_for_target = None
    # Build index mapping: find the index of our target incident in the all_open_incidents list
    target_index = None
    for idx, inc in enumerate(all_open_incidents):
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

    # Mark the incident as in_progress in DB
    update_incident_status(request.incident_id, "in_progress")

    vehicle_id = assignment_for_target["ambulance_id"]

    # Generate a simple route description for the assignment
    route_description = (
        f"Optimized route for {vehicle_id} to incident at "
        f"(lat: {target_incident['lat']:.4f}, lon: {target_incident['lon']:.4f}). "
        f"Total unweighted distance: {assignment_for_target['unweighted_dist']:.2f} km."
    )

    # Generate a unique suggestion ID for this assignment suggestion
    suggestion_id = str(uuid.uuid4())

    # Create and store the assignment suggestion
    assignment_suggestion = AssignmentSuggestion(
        suggestion_id=suggestion_id,
        suggested_vehicle_id=vehicle_id,
        route=route_description,
        timestamp=datetime.now()
    )

    vehicle_assignments[suggestion_id] = {
        "suggestion": assignment_suggestion,
        "incident_id": request.incident_id,
    }

    logger.info(f"Generated globally-optimized assignment for suggestion {suggestion_id}: vehicle {vehicle_id}")

    return assignment_suggestion.model_dump()


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

    Args:
        suggestion_id: Suggestion identifier

    Returns:
        Confirmation message
    """
    if suggestion_id not in vehicle_assignments:
        raise HTTPException(status_code=404, detail="Assignment not found")

    entry = vehicle_assignments[suggestion_id]
    assignment = entry["suggestion"]
    incident_id = entry.get("incident_id")

    vehicle = next((v for v in MOCK_VEHICLES if v.id == assignment.suggested_vehicle_id), None)

    if vehicle:
        vehicle.status = "dispatched"
        logger.info(f"Accepted assignment for suggestion {suggestion_id}: vehicle {vehicle.id} dispatched")

    # Update incident status in DB
    if incident_id:
        update_incident_status(incident_id, "in_progress")

    return {"status": "accepted", "suggestion_id": suggestion_id, "vehicle_id": assignment.suggested_vehicle_id}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
