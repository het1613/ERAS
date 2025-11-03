"""
Geospatial Dispatch Service - Tracks vehicles and provides assignment recommendations.
"""

import os
import math
import logging
import sys
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from shared.types import Vehicle, AssignmentSuggestion

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


def find_nearest_vehicle(incident_lat: float, incident_lon: float, vehicle_type: Optional[str] = None) -> Optional[Vehicle]:
    """
    Find the nearest available vehicle to an incident location.
    
    Args:
        incident_lat: Incident latitude
        incident_lon: Incident longitude
        vehicle_type: Optional filter for vehicle type
        
    Returns:
        Nearest available Vehicle or None
    """
    available_vehicles = [
        v for v in MOCK_VEHICLES
        if v.status == "available" and (vehicle_type is None or v.vehicle_type == vehicle_type)
    ]
    
    if not available_vehicles:
        return None
    
    # Find vehicle with minimum distance
    nearest = min(
        available_vehicles,
        key=lambda v: calculate_distance(incident_lat, incident_lon, v.lat, v.lon)
    )
    
    return nearest


def generate_route(vehicle: Vehicle, incident_lat: float, incident_lon: float) -> str:
    """
    Generate a route description.
    
    Args:
        vehicle: Vehicle to route from
        incident_lat, incident_lon: Destination coordinates
        
    Returns:
        Route description
    """
    # TODO: Use a routing API (e.g., Google Maps, OSRM).
    distance = calculate_distance(vehicle.lat, vehicle.lon, incident_lat, incident_lon)
    return f"Route from {vehicle.current_location} to incident (approx {distance:.1f} km)"


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
    Get or generate vehicle assignment suggestion for a session.
    
    Args:
        session_id: Session identifier
        lat: Optional incident latitude (for new assignments)
        lon: Optional incident longitude (for new assignments)
        
    Returns:
        Assignment suggestion
    """
    # If assignment already exists, return it
    if session_id in vehicle_assignments:
        assignment = vehicle_assignments[session_id]
        return assignment.model_dump()
    
    # For MVP: Use default location if not provided (Waterloo, ON)
    if lat is None:
        lat = 43.4643
    if lon is None:
        lon = -80.5204
    
    # Find nearest available vehicle
    nearest_vehicle = find_nearest_vehicle(lat, lon)
    
    if not nearest_vehicle:
        raise HTTPException(status_code=503, detail="No available vehicles")
    
    # Generate route
    route = generate_route(nearest_vehicle, lat, lon)
    
    # Create assignment suggestion
    assignment = AssignmentSuggestion(
        session_id=session_id,
        suggested_vehicle_id=nearest_vehicle.id,
        route=route,
        timestamp=datetime.now()
    )
    
    # Store assignment
    vehicle_assignments[session_id] = assignment
    
    logger.info(f"Generated assignment suggestion for session {session_id}: {nearest_vehicle.id}")
    
    return assignment.model_dump()


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

