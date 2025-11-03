"""Shared type definitions for ERAS services."""
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum
from pydantic import BaseModel


class IncidentType(str, Enum):
    """Standard incident codes."""
    ACCIDENT = "10-50"
    FIRE = "10-70"
    MEDICAL = "10-33"
    POLICE = "10-13"
    UNKNOWN = "10-99"


class Severity(str, Enum):
    """Incident severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class VehicleStatus(str, Enum):
    """Emergency vehicle status."""
    AVAILABLE = "available"
    DISPATCHED = "dispatched"
    ON_SCENE = "on_scene"
    RETURNING = "returning"
    OFFLINE = "offline"


class SuggestionType(str, Enum):
    """Types of AI suggestions."""
    INCIDENT_CODE = "incident_code"
    SEVERITY = "severity"
    VEHICLE = "vehicle"
    ROUTE = "route"
    ALERT = "alert"


class AudioChunk(BaseModel):
    """Audio chunk data."""
    session_id: str
    chunk_id: str
    audio_data: bytes
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None


class ProcessedTranscript(BaseModel):
    """Processed transcript with extracted information."""
    session_id: str
    transcript: str
    confidence: float
    language: str = "en"
    entities: Dict[str, Any] = {}
    incident_type: Optional[IncidentType] = None
    location: Optional[Dict[str, float]] = None  # {lat, lng}
    severity: Optional[Severity] = None
    timestamp: datetime


class AISuggestion(BaseModel):
    """AI-generated suggestion."""
    session_id: str
    suggestion_id: str
    type: SuggestionType
    content: Dict[str, Any]
    confidence: float
    timestamp: datetime
    status: str = "pending"  # pending, accepted, declined, modified


class Vehicle(BaseModel):
    """Emergency vehicle representation."""
    vehicle_id: str
    vehicle_type: str  # ambulance, fire_truck, police_car
    status: VehicleStatus
    location: Dict[str, float]  # {lat, lng}
    current_incident_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class DispatchCommand(BaseModel):
    """Dispatch command."""
    command_id: str
    session_id: str
    vehicle_id: str
    incident_id: str
    route: Optional[List[Dict[str, float]]] = None
    timestamp: datetime
    status: str = "pending"


class Session(BaseModel):
    """Emergency call session."""
    session_id: str
    caller_info: Optional[Dict[str, Any]] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    status: str = "active"  # active, resolved, archived
    incident_code: Optional[str] = None
    dispatched_vehicles: List[str] = []

