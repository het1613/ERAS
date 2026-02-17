"""
Simulator that publishes mock GPS updates for ambulances to Kafka.
Dispatched vehicles follow pre-computed OSRM routes; others random-walk.

Usage:
    KAFKA_BOOTSTRAP_SERVERS=localhost:9092 python scripts/simulate_vehicle_locations.py

Run from the project root so the shared module is importable.
"""

import sys
import os
import time
import random
import math
import threading
from collections import deque
from datetime import datetime

# Add project root to path so shared module is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from shared.kafka_client import create_producer, create_consumer

LOCATION_TOPIC = "vehicle-locations"
DISPATCH_TOPIC = "vehicle-dispatches"

# Same starting positions as MOCK_VEHICLES in geospatial-dispatch/main.py
VEHICLES = [
    {"vehicle_id": "ambulance-1", "lat": 43.4723, "lon": -80.5449},
    {"vehicle_id": "ambulance-2", "lat": 43.4515, "lon": -80.4925},
    {"vehicle_id": "ambulance-3", "lat": 43.4643, "lon": -80.5204},
    {"vehicle_id": "ambulance-4", "lat": 43.4583, "lon": -80.5025},
    {"vehicle_id": "ambulance-5", "lat": 43.4553, "lon": -80.5165},
]

# ~200m in degrees (rough approximation at ~43N latitude)
STEP_LAT = 0.0018
STEP_LON = 0.0025

# Speed: ~60 km/h => ~33.3 m/s => ~66.7 m per 2s tick
SPEED_M_PER_TICK = 66.7
TICK_SECONDS = 2

# Thread-safe storage for active routes: vehicle_id -> deque of [lat, lon]
vehicle_routes = {}
route_lock = threading.Lock()


def haversine_m(lat1, lon1, lat2, lon2):
    """Return distance in meters between two lat/lon points."""
    R = 6_371_000  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def interpolate(lat1, lon1, lat2, lon2, fraction):
    """Linearly interpolate between two points by fraction [0, 1]."""
    return (
        lat1 + (lat2 - lat1) * fraction,
        lon1 + (lon2 - lon1) * fraction,
    )


def dispatch_consumer_thread():
    """Background thread that listens for vehicle-dispatches and stores routes."""
    bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    print(f"[DISPATCH] Connecting to Kafka at {bootstrap_servers} for dispatch events...")

    try:
        consumer = create_consumer(
            topics=[DISPATCH_TOPIC],
            group_id="simulator-dispatch-consumer",
            bootstrap_servers=bootstrap_servers,
            auto_offset_reset="latest",
        )
        print("[DISPATCH] Consumer ready. Listening for dispatch events...")

        for message in consumer:
            try:
                data = message.value
                vehicle_id = data.get("vehicle_id")
                route = data.get("route", [])

                if not vehicle_id or not route:
                    continue

                with route_lock:
                    vehicle_routes[vehicle_id] = deque(route)

                print(f"[DISPATCH] Received route for {vehicle_id}: {len(route)} waypoints")

            except Exception as e:
                print(f"[DISPATCH] Error processing message: {e}")
                continue

    except Exception as e:
        print(f"[DISPATCH] Fatal error: {e}")


def advance_along_route(vehicle, route_deque):
    """Advance a vehicle along its route by SPEED_M_PER_TICK meters. Returns True if still en route."""
    budget = SPEED_M_PER_TICK
    current_lat = vehicle["lat"]
    current_lon = vehicle["lon"]

    while budget > 0 and route_deque:
        next_wp = route_deque[0]
        dist = haversine_m(current_lat, current_lon, next_wp[0], next_wp[1])

        if dist <= budget:
            # Consume this waypoint
            current_lat, current_lon = next_wp[0], next_wp[1]
            budget -= dist
            route_deque.popleft()
        else:
            # Interpolate partway toward next waypoint
            fraction = budget / dist
            current_lat, current_lon = interpolate(current_lat, current_lon, next_wp[0], next_wp[1], fraction)
            budget = 0

    vehicle["lat"] = current_lat
    vehicle["lon"] = current_lon

    return len(route_deque) > 0


def main():
    print(f"Creating Kafka producer for topic '{LOCATION_TOPIC}'...")
    producer = create_producer()
    print("Producer ready. Sending vehicle location updates every 2 seconds. Press Ctrl+C to stop.")

    # Start dispatch consumer in background thread
    dispatch_thread = threading.Thread(target=dispatch_consumer_thread, daemon=True)
    dispatch_thread.start()

    try:
        while True:
            for v in VEHICLES:
                vid = v["vehicle_id"]
                mode = "RANDOM"

                with route_lock:
                    route = vehicle_routes.get(vid)

                if route is not None:
                    still_going = advance_along_route(v, route)
                    if not still_going:
                        # Arrived at destination
                        with route_lock:
                            del vehicle_routes[vid]
                        print(f"  [{vid}] ARRIVED at destination!")
                        mode = "ARRIVED"
                    else:
                        mode = "ROUTED"
                else:
                    # Random walk
                    v["lat"] += random.uniform(-STEP_LAT, STEP_LAT)
                    v["lon"] += random.uniform(-STEP_LON, STEP_LON)

                message = {
                    "vehicle_id": vid,
                    "lat": round(v["lat"], 6),
                    "lon": round(v["lon"], 6),
                    "timestamp": datetime.now().isoformat(),
                }

                producer.send(
                    LOCATION_TOPIC,
                    key=vid.encode("utf-8"),
                    value=message,
                )

                print(f"  [{mode}] {vid}: ({message['lat']}, {message['lon']})")

            producer.flush()
            print("---")
            time.sleep(TICK_SECONDS)
    except KeyboardInterrupt:
        print("\nStopping simulator.")
    finally:
        producer.close()


if __name__ == "__main__":
    main()
