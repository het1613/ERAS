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


class AssignmentSuggestion(BaseModel):
    """Represents a suggested vehicle assignment for an incident."""
    session_id: str
    suggested_vehicle_id: str
    route: str 
    timestamp: datetime


class Incident(BaseModel):
    """Represents a single incident, used as input for targeted dispatch."""
    lat: float
    lon: float
    weight: int

