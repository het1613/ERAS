"""
Simulator that publishes mock GPS updates for ambulances to Kafka.
Dispatched vehicles follow pre-computed OSRM routes; others random-walk.
Vehicles go through a full lifecycle: available -> dispatched -> on_scene -> returning -> available

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

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from shared.kafka_client import create_producer, create_consumer

LOCATION_TOPIC = "vehicle-locations"
DISPATCH_TOPIC = "vehicle-dispatches"
ARRIVAL_TOPIC = "vehicle-arrivals"

# Same starting positions as MOCK_VEHICLES in geospatial-dispatch/main.py
VEHICLES = [
    {"vehicle_id": "ambulance-1", "lat": 43.4723, "lon": -80.5449},
    {"vehicle_id": "ambulance-2", "lat": 43.4515, "lon": -80.4925},
    {"vehicle_id": "ambulance-3", "lat": 43.4643, "lon": -80.5204},
    {"vehicle_id": "ambulance-4", "lat": 43.4583, "lon": -80.5025},
    {"vehicle_id": "ambulance-5", "lat": 43.4553, "lon": -80.5165},
]

# Tiny GPS drift for idle vehicles (~5m, simulates real GPS jitter)
STEP_LAT = 0.00005
STEP_LON = 0.00007

# Speed: ~60 km/h => ~33.3 m/s => ~66.7 m per 2s tick
SPEED_M_PER_TICK = 66.7
TICK_SECONDS = 2

ON_SCENE_DURATION_S = 30
RETURNING_DURATION_S = 30

# Thread-safe storage for active routes: vehicle_id -> {"route": deque, "incident_id": str}
vehicle_routes = {}
route_lock = threading.Lock()

# Per-vehicle lifecycle state. Keys: status, timer, incident_id
# status: "available" | "dispatched" | "on_scene" | "returning"
vehicle_states = {}
state_lock = threading.Lock()


def haversine_m(lat1, lon1, lat2, lon2):
    """Return distance in meters between two lat/lon points."""
    R = 6_371_000
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
                incident_id = data.get("incident_id")
                if not vehicle_id or not route:
                    continue

                with route_lock:
                    vehicle_routes[vehicle_id] = {
                        "route": deque(route),
                        "incident_id": incident_id,
                    }
                with state_lock:
                    vehicle_states[vehicle_id] = {
                        "status": "dispatched",
                        "incident_id": incident_id,
                        "timer": None,
                    }

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
            current_lat, current_lon = next_wp[0], next_wp[1]
            budget -= dist
            route_deque.popleft()
        else:
            fraction = budget / dist
            current_lat, current_lon = interpolate(current_lat, current_lon, next_wp[0], next_wp[1], fraction)
            budget = 0

    vehicle["lat"] = current_lat
    vehicle["lon"] = current_lon

    return len(route_deque) > 0


def get_vehicle_status(vid):
    with state_lock:
        state = vehicle_states.get(vid)
        if state:
            return state["status"]
    return "available"


def main():
    print(f"Creating Kafka producer for topic '{LOCATION_TOPIC}'...")
    producer = create_producer()
    print("Producer ready. Sending vehicle location updates every 2 seconds. Press Ctrl+C to stop.")

    # Initialize all vehicles as available
    for v in VEHICLES:
        vehicle_states[v["vehicle_id"]] = {
            "status": "available",
            "incident_id": None,
            "timer": None,
        }

    dispatch_thread = threading.Thread(target=dispatch_consumer_thread, daemon=True)
    dispatch_thread.start()

    try:
        while True:
            now = time.time()

            for v in VEHICLES:
                vid = v["vehicle_id"]

                with state_lock:
                    state = vehicle_states.get(vid, {"status": "available", "incident_id": None, "timer": None})

                status = state["status"]

                if status == "dispatched":
                    with route_lock:
                        entry = vehicle_routes.get(vid)
                    if entry is not None:
                        still_going = advance_along_route(v, entry["route"])
                        if not still_going:
                            # Arrived at scene -> enter on_scene phase
                            incident_id = entry["incident_id"]
                            with route_lock:
                                del vehicle_routes[vid]
                            with state_lock:
                                vehicle_states[vid] = {
                                    "status": "on_scene",
                                    "incident_id": incident_id,
                                    "timer": now + ON_SCENE_DURATION_S,
                                }
                            print(f"  [{vid}] ARRIVED — entering on_scene for {ON_SCENE_DURATION_S}s")
                        else:
                            mode = "ROUTED"

                elif status == "on_scene":
                    if state["timer"] and now >= state["timer"]:
                        # On-scene time expired -> publish arrival event and enter returning
                        incident_id = state["incident_id"]
                        if incident_id:
                            producer.send(
                                ARRIVAL_TOPIC,
                                key=vid.encode("utf-8"),
                                value={
                                    "vehicle_id": vid,
                                    "incident_id": incident_id,
                                    "timestamp": datetime.now().isoformat(),
                                },
                            )
                        with state_lock:
                            vehicle_states[vid] = {
                                "status": "returning",
                                "incident_id": None,
                                "timer": now + RETURNING_DURATION_S,
                            }
                        print(f"  [{vid}] ON_SCENE complete — returning for {RETURNING_DURATION_S}s")

                elif status == "returning":
                    # Random walk while returning
                    v["lat"] += random.uniform(-STEP_LAT, STEP_LAT)
                    v["lon"] += random.uniform(-STEP_LON, STEP_LON)
                    if state["timer"] and now >= state["timer"]:
                        with state_lock:
                            vehicle_states[vid] = {
                                "status": "available",
                                "incident_id": None,
                                "timer": None,
                            }
                        print(f"  [{vid}] Back AVAILABLE")

                else:
                    # available -> random walk
                    v["lat"] += random.uniform(-STEP_LAT, STEP_LAT)
                    v["lon"] += random.uniform(-STEP_LON, STEP_LON)

                current_status = get_vehicle_status(vid)
                message = {
                    "vehicle_id": vid,
                    "lat": round(v["lat"], 6),
                    "lon": round(v["lon"], 6),
                    "timestamp": datetime.now().isoformat(),
                    "status": current_status,
                }

                producer.send(
                    LOCATION_TOPIC,
                    key=vid.encode("utf-8"),
                    value=message,
                )

                print(f"  [{current_status.upper()}] {vid}: ({message['lat']}, {message['lon']})")

            producer.flush()
            print("---")
            time.sleep(TICK_SECONDS)
    except KeyboardInterrupt:
        print("\nStopping simulator.")
    finally:
        producer.close()


if __name__ == "__main__":
    main()
