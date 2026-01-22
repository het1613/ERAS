"""
Geospatial Dispatch Service - Tracks vehicles and provides assignment recommendations.
"""

import os
import math
import logging
import sys
from datetime import datetime
from typing import Optional

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from shared.types import Vehicle, AssignmentSuggestion
from optimization import run_weighted_dispatch_with_hospitals

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
    vehicle = next((v for v in MOCK_VEHICLES if v.id == vehicle_id), None)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    
    return vehicle.model_dump()


@app.get("/assignments/{session_id}")
async def get_assignment(session_id: str, lat: Optional[float] = None, lon: Optional[float] = None):
    """
    Get or generate vehicle assignment suggestion for a session using the optimization model.
    """
    # If assignment already exists, return it
    if session_id in vehicle_assignments:
        return vehicle_assignments[session_id].model_dump()

    # Get available vehicles
    available_vehicles = [v for v in MOCK_VEHICLES if v.status == "available"]
    if not available_vehicles:
        raise HTTPException(status_code=503, detail="No available vehicles")

    # Run the weighted dispatch optimization
    dispatch_results = run_weighted_dispatch_with_hospitals(
        available_vehicles, MOCK_INCIDENTS, MOCK_HOSPITALS, verbose=True
    )

    # Extract the first assignment from the first round
    if not dispatch_results["rounds"] or not dispatch_results["rounds"][0]["assignments"]:
        raise HTTPException(status_code=404, detail="Could not find a suitable assignment.")

    first_assignment = dispatch_results["rounds"][0]["assignments"][0]
    
    vehicle_id = first_assignment["ambulance_id"]
    incident_id = first_assignment["incident_id"]
    
    vehicle = next((v for v in available_vehicles if v.id == vehicle_id), None)
    incident = MOCK_INCIDENTS[incident_id]

    # Generate a simple route description for the assignment
    route_description = (
        f"Optimized route for {vehicle.id} to incident {incident_id} "
        f"(lat: {incident['lat']:.4f}, lon: {incident['lon']:.4f}). "
        f"Total unweighted distance: {first_assignment['unweighted_dist']:.2f} km."
    )

    # Create and store the assignment suggestion
    assignment_suggestion = AssignmentSuggestion(
        session_id=session_id,
        suggested_vehicle_id=vehicle_id,
        route=route_description,
        timestamp=datetime.now()
    )
    
    vehicle_assignments[session_id] = assignment_suggestion
    
    logger.info(f"Generated optimized assignment for session {session_id}: vehicle {vehicle_id}")
    
    return assignment_suggestion.model_dump()


@app.post("/assignments/{session_id}/accept")
async def accept_assignment(session_id: str):
    """
    Accept a vehicle assignment (mark vehicle as dispatched).
    
    Args:
        session_id: Session identifier
        
    Returns:
        Confirmation message
    """
    if session_id not in vehicle_assignments:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    assignment = vehicle_assignments[session_id]
    vehicle = next((v for v in MOCK_VEHICLES if v.id == assignment.suggested_vehicle_id), None)
    
    if vehicle:
        vehicle.status = "dispatched"
        logger.info(f"Accepted assignment for session {session_id}: vehicle {vehicle.id} dispatched")
    
    return {"status": "accepted", "session_id": session_id, "vehicle_id": assignment.suggested_vehicle_id}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)

