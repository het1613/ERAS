"""
Data models for ERAS system.
"""

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class AudioChunk(BaseModel):
    """Represents a chunk of audio data."""
    session_id: str
    chunk_data: str  # Base64 encoded or path to audio file for MVP (mocked)
    timestamp: datetime
    sequence_number: int


class Transcript(BaseModel):
    """Represents a transcribed text from audio."""
    session_id: str
    text: str
    timestamp: datetime


class Suggestion(BaseModel):
    """Represents an AI-generated suggestion for a dispatch action."""
    id: str = ""  # Unique identifier for frontend reference
    session_id: str
    suggestion_type: str  # e.g., "incident_code", "alert", "vehicle"
    value: str  # Human-readable summary, e.g., "Code 51 - Cardiac: Ischemic"
    timestamp: datetime
    status: str = "pending"  # "pending", "accepted", "dismissed"
    # Structured Ontario ACR Problem Code fields
    incident_code: Optional[str] = None  # ACR code, e.g., "51"
    incident_code_description: Optional[str] = None  # e.g., "Ischemic"
    incident_code_category: Optional[str] = None  # e.g., "Cardiac"
    priority: Optional[str] = None  # MPDS priority: Purple/Red/Orange/Yellow/Green
    confidence: Optional[float] = None  # 0.0 - 1.0 match confidence
    matched_evidence: Optional[List[dict]] = None  # [{keyword, score}] matched keywords
    # LLM-extracted location fields
    extracted_location: Optional[str] = None  # Street address / description from LLM
    extracted_lat: Optional[float] = None  # Geocoded latitude (via Nominatim)
    extracted_lon: Optional[float] = None  # Geocoded longitude (via Nominatim)
    location_confidence: Optional[float] = None  # 0.0 - 1.0 LLM location confidence


class Vehicle(BaseModel):
    """Represents an emergency vehicle."""
    id: str
    lat: float
    lon: float
    status: str  # "available", "dispatched", "offline"
    vehicle_type: str  # "ambulance", "fire_truck", "police"


class VehicleLocation(BaseModel):
    """Represents a real-time vehicle location update from Kafka."""
    vehicle_id: str
    lat: float
    lon: float
    timestamp: datetime


class AssignmentSuggestion(BaseModel):
    """Represents a suggested vehicle assignment for an incident."""
    suggestion_id: str
    suggested_vehicle_id: str
    route: str 
    timestamp: datetime


class VehicleDispatchEvent(BaseModel):
    """Represents a dispatch event sent via Kafka when an assignment is accepted."""
    vehicle_id: str
    incident_id: str
    incident_lat: float
    incident_lon: float
    route: List[List[float]]  # List of [lat, lon] pairs
    timestamp: datetime


class VehicleArrivalEvent(BaseModel):
    """Published by the simulator when a dispatched vehicle arrives at its incident."""
    vehicle_id: str
    incident_id: str
    timestamp: datetime


class VehicleTransportingEvent(BaseModel):
    """Published when an ambulance leaves the scene heading to hospital."""
    vehicle_id: str
    incident_id: str
    route: List[List[float]]
    timestamp: datetime


class VehicleAtHospitalEvent(BaseModel):
    """Published when an ambulance arrives at the hospital."""
    vehicle_id: str
    incident_id: str
    timestamp: datetime


INCIDENT_STATUSES = [
    "open", "dispatched", "en_route", "on_scene",
    "transporting", "at_hospital", "resolved",
]

PRIORITY_WEIGHT_MAP = {
    "Purple": 16,
    "Red": 8,
    "Orange": 4,
    "Yellow": 2,
    "Green": 1,
}

GRAND_RIVER_HOSPITAL = {
    "lat": 43.455280,
    "lon": -80.505836,
    "name": "Grand River Hospital",
    "address": "835 King St W, Kitchener, ON N2G 1G3",
}


class Incident(BaseModel):
    """Represents a single incident, used as input for targeted dispatch."""
    id: Optional[str] = None
    session_id: Optional[str] = None
    lat: float
    lon: float
    location: Optional[str] = None
    type: Optional[str] = None
    priority: str = "Yellow"
    weight: int = 0
    status: str = "open"
    source: str = "manual"
    assigned_vehicle_id: Optional[str] = None
    reported_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __init__(self, **data):
        super().__init__(**data)
        if self.weight == 0:
            self.weight = PRIORITY_WEIGHT_MAP.get(self.priority, 2)

