"""Geospatial and Dispatch Service - Vehicle tracking and routing."""
import os
import sys
import uuid
import threading
import math
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
from psycopg2.extras import RealDictCursor

# Add shared module to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from shared.kafka_client import create_consumer, create_producer, consume_messages
from shared.redis_client import create_redis_client, publish_realtime_update
from shared.types import (
    ProcessedTranscript, AISuggestion, Vehicle, DispatchCommand, VehicleStatus
)

app = FastAPI(title="Geospatial Dispatch Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

producer = create_producer()
redis_client = create_redis_client()

# Database connection
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_DB = os.getenv("POSTGRES_DB", "eras_db")
POSTGRES_USER = os.getenv("POSTGRES_USER", "eras_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "eras_password")


def get_db_connection():
    """Get PostgreSQL connection."""
    return psycopg2.connect(
        host=POSTGRES_HOST,
        database=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD
    )


def calculate_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate distance between two coordinates (Haversine formula)."""
    R = 6371  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat/2)**2 + 
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * 
         math.sin(dlng/2)**2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c


def find_nearest_vehicle(incident_location: dict, vehicle_type: Optional[str] = None) -> Optional[dict]:
    """Find nearest available vehicle to incident location."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            query = """
                SELECT * FROM vehicles 
                WHERE status = 'available'
            """
            if vehicle_type:
                query += f" AND vehicle_type = '{vehicle_type}'"
            
            cur.execute(query)
            vehicles = cur.fetchall()
            
            if not vehicles:
                return None
            
            # Find nearest vehicle
            nearest = None
            min_distance = float('inf')
            
            for vehicle in vehicles:
                vehicle_loc = vehicle['location']
                distance = calculate_distance(
                    incident_location['lat'],
                    incident_location['lng'],
                    vehicle_loc['lat'],
                    vehicle_loc['lng']
                )
                
                if distance < min_distance:
                    min_distance = distance
                    nearest = vehicle
            
            return dict(nearest) if nearest else None
            
    finally:
        conn.close()


def generate_route(start: dict, end: dict) -> List[dict]:
    """Generate route between two points (mock - in production, use routing API)."""
    # For MVP, return simple route
    # In production, use OSRM, Google Maps, or similar
    return [start, end]


def process_transcript_for_dispatch(message: dict):
    """Process transcript and suggest vehicle/route."""
    try:
        session_id = message["session_id"]
        location = message.get("location")
        incident_type = message.get("incident_type")
        
        if not location:
            return
        
        # Map incident type to vehicle type
        vehicle_type_map = {
            "10-50": "ambulance",  # Accident
            "10-70": "fire_truck",  # Fire
            "10-33": "ambulance",   # Medical
            "10-13": "police_car",  # Police
        }
        
        vehicle_type = vehicle_type_map.get(incident_type)
        
        # Find nearest vehicle
        vehicle = find_nearest_vehicle(location, vehicle_type)
        
        if vehicle:
            # Generate route
            route = generate_route(
                vehicle['location'],
                location
            )
            
            # Create dispatch suggestion
            from shared.types import SuggestionType, AISuggestion
            
            suggestion = AISuggestion(
                session_id=session_id,
                suggestion_id=str(uuid.uuid4()),
                type=SuggestionType.VEHICLE,
                content={
                    "vehicle_id": vehicle['vehicle_id'],
                    "vehicle_type": vehicle['vehicle_type'],
                    "distance_km": calculate_distance(
                        vehicle['location']['lat'],
                        vehicle['location']['lng'],
                        location['lat'],
                        location['lng']
                    ),
                    "estimated_time_minutes": 10  # Mock
                },
                confidence=0.85,
                timestamp=datetime.utcnow()
            )
            
            # Publish route suggestion
            route_suggestion = AISuggestion(
                session_id=session_id,
                suggestion_id=str(uuid.uuid4()),
                type=SuggestionType.ROUTE,
                content={
                    "route": route,
                    "distance_km": calculate_distance(
                        route[0]['lat'],
                        route[0]['lng'],
                        route[-1]['lat'],
                        route[-1]['lng']
                    )
                },
                confidence=0.80,
                timestamp=datetime.utcnow()
            )
            
            # Publish suggestions
            from shared.kafka_client import publish_message
            from shared.types import SuggestionType as ST
            
            publish_message(
                producer,
                "suggestions",
                suggestion.dict(),
                key=session_id
            )
            
            publish_message(
                producer,
                "suggestions",
                route_suggestion.dict(),
                key=session_id
            )
            
            # Real-time updates
            publish_realtime_update(
                redis_client,
                f"suggestion:{session_id}",
                suggestion.dict()
            )
            
    except Exception as e:
        print(f"Error processing dispatch: {e}")


def start_kafka_consumer():
    """Start Kafka consumer in background thread."""
    consumer = create_consumer("processed-data", "geospatial-dispatch-group")
    consume_messages(consumer, process_transcript_for_dispatch)


@app.on_event("startup")
async def startup():
    """Start Kafka consumer on service startup."""
    thread = threading.Thread(target=start_kafka_consumer, daemon=True)
    thread.start()


@app.post("/api/v1/vehicles/{vehicle_id}/location")
async def update_vehicle_location(vehicle_id: str, location: dict):
    """Update vehicle location."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO vehicles (vehicle_id, vehicle_type, status, location, updated_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (vehicle_id) 
                DO UPDATE SET location = %s, updated_at = %s
            """, (
                vehicle_id,
                location.get("vehicle_type", "ambulance"),
                "available",
                f'{{"lat": {location["lat"]}, "lng": {location["lng"]}}}',
                datetime.utcnow(),
                f'{{"lat": {location["lat"]}, "lng": {location["lng"]}}}',
                datetime.utcnow()
            ))
            conn.commit()
        
        return {"status": "updated", "vehicle_id": vehicle_id}
    finally:
        conn.close()


@app.get("/api/v1/vehicles")
async def get_vehicles(status: Optional[str] = None):
    """Get all vehicles, optionally filtered by status."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if status:
                cur.execute("SELECT * FROM vehicles WHERE status = %s", (status,))
            else:
                cur.execute("SELECT * FROM vehicles")
            
            vehicles = cur.fetchall()
            return [dict(v) for v in vehicles]
    finally:
        conn.close()


@app.post("/api/v1/dispatch")
async def dispatch_vehicle(command: dict):
    """Execute dispatch command."""
    conn = get_db_connection()
    try:
        command_id = str(uuid.uuid4())
        
        with conn.cursor() as cur:
            # Insert dispatch command
            cur.execute("""
                INSERT INTO dispatch_commands 
                (command_id, session_id, vehicle_id, incident_id, route, status, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                command_id,
                command["session_id"],
                command["vehicle_id"],
                command.get("incident_id", command["session_id"]),
                command.get("route"),
                "dispatched",
                datetime.utcnow()
            ))
            
            # Update vehicle status
            cur.execute("""
                UPDATE vehicles 
                SET status = 'dispatched', current_incident_id = %s
                WHERE vehicle_id = %s
            """, (command.get("incident_id", command["session_id"]), command["vehicle_id"]))
            
            conn.commit()
        
        # Publish real-time update
        publish_realtime_update(
            redis_client,
            f"dispatch:{command['session_id']}",
            {"command_id": command_id, "status": "dispatched"}
        )
        
        return {"command_id": command_id, "status": "dispatched"}
    finally:
        conn.close()


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "geospatial-dispatch"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)

