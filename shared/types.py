"""
Data models for ERAS system.
"""

from pydantic import BaseModel
from typing import Optional
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
    session_id: str
    suggestion_type: str  # e.g., "incident_code", "alert", "vehicle"
    value: str  # e.g., "10-70: Fire Alarm"
    timestamp: datetime
    status: str = "pending"  # "pending", "accepted", "declined", "modified"


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


PRIORITY_WEIGHT_MAP = {
    "Purple": 16,
    "Red": 8,
    "Orange": 4,
    "Yellow": 2,
    "Green": 1,
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
    reported_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __init__(self, **data):
        super().__init__(**data)
        if self.weight == 0:
            self.weight = PRIORITY_WEIGHT_MAP.get(self.priority, 2)

