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

from shared.types import Vehicle, AssignmentSuggestion, Incident
from optimization import run_weighted_dispatch_with_hospitals, find_best_ambulance_for_incident
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

# Mock incident data
MOCK_INCIDENTS = [
    {"id": 0, "lat": 43.2761, "lon": -80.7318, "weight": 8},
    {"id": 1, "lat": 43.6398, "lon": -80.7308, "weight": 8},
    {"id": 2, "lat": 43.5205, "lon": -80.6522, "weight": 4},
    {"id": 3, "lat": 43.5686, "lon": -80.5089, "weight": 8},
    {"id": 4, "lat": 43.2593, "lon": -80.5692, "weight": 8},
    {"id": 5, "lat": 43.6865, "lon": -80.6607, "weight": 1},
    {"id": 6, "lat": 43.6246, "lon": -80.4523, "weight": 4},
    {"id": 7, "lat": 43.3456, "lon": -80.7593, "weight": 16},
]

# Vehicle location tracker (updates positions from Kafka)
vehicle_tracker = VehicleLocationTracker(MOCK_VEHICLES)


@app.on_event("startup")
async def startup_event():
    vehicle_tracker.start_consumer()


# In-memory storage for all incoming incidents
TRACKED_INCIDENTS = []

# In-memory storage for vehicle assignments
vehicle_assignments = {}


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
async def find_best_assignment(incident: Incident):
    """
    Find the best vehicle for a single incident, considering the current global state.
    """
    vehicle_tracker.update_vehicle_positions()

    # Assign a unique ID to the new incident for tracking
    new_incident_id = str(uuid.uuid4())
    
    # Create a dictionary for the new incident to store it
    new_incident_dict = {
        "id": new_incident_id,
        "lat": incident.lat,
        "lon": incident.lon,
        "weight": incident.weight,
        "status": "unassigned"  # Track assignment status
    }
    
    # Add the new incident to our persistent list
    TRACKED_INCIDENTS.append(new_incident_dict)

    # Get all currently available vehicles
    available_vehicles = [v for v in MOCK_VEHICLES if v.status == "available"]
    if not available_vehicles:
        raise HTTPException(status_code=503, detail="No available vehicles to assign")

    # Get all incidents that are not yet assigned
    unassigned_incidents = [i for i in TRACKED_INCIDENTS if i.get("status") == "unassigned"]
    
    # Run the full optimization model on the current state
    dispatch_results = run_weighted_dispatch_with_hospitals(
        available_vehicles, unassigned_incidents, MOCK_HOSPITALS, verbose=True
    )

    # Find the assignment for our specific new incident
    assignment_for_new_incident = None
    for round_summary in dispatch_results.get("rounds", []):
        for assignment in round_summary.get("assignments", []):
            # The 'incident_id' from the optimizer corresponds to the index in the list
            # of unassigned_incidents that was passed to it.
            assigned_incident_index = assignment["incident_id"]
            if unassigned_incidents[assigned_incident_index]["id"] == new_incident_id:
                assignment_for_new_incident = assignment
                break
        if assignment_for_new_incident:
            break

    if not assignment_for_new_incident:
        raise HTTPException(status_code=404, detail="Could not find a suitable assignment for the new incident.")

    # Mark the incident as "assigned" in our tracked list
    new_incident_dict["status"] = "assigned"

    vehicle_id = assignment_for_new_incident["ambulance_id"]

    # Generate a simple route description for the assignment
    route_description = (
        f"Optimized route for {vehicle_id} to new incident at "
        f"(lat: {incident.lat:.4f}, lon: {incident.lon:.4f}). "
        f"Total unweighted distance: {assignment_for_new_incident['unweighted_dist']:.2f} km."
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
    
    vehicle_assignments[suggestion_id] = assignment_suggestion
    
    logger.info(f"Generated globally-optimized assignment for suggestion {suggestion_id}: vehicle {vehicle_id}")
    
    return assignment_suggestion.model_dump()


@app.get("/assignments/{suggestion_id}")
async def get_assignment(suggestion_id: str):
    """
    Retrieve a previously generated assignment suggestion by its suggestion ID.
    """
    # If assignment already exists, return it
    if suggestion_id in vehicle_assignments:
        return vehicle_assignments[suggestion_id].model_dump()
    
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
    
    assignment = vehicle_assignments[suggestion_id]
    vehicle = next((v for v in MOCK_VEHICLES if v.id == assignment.suggested_vehicle_id), None)
    
    if vehicle:
        vehicle.status = "dispatched"
        logger.info(f"Accepted assignment for suggestion {suggestion_id}: vehicle {vehicle.id} dispatched")
    
    return {"status": "accepted", "suggestion_id": suggestion_id, "vehicle_id": assignment.suggested_vehicle_id}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)

