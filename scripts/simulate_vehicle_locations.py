"""
Simulator that publishes mock GPS updates for ambulances to Kafka.

Usage:
    KAFKA_BOOTSTRAP_SERVERS=localhost:9092 python scripts/simulate_vehicle_locations.py

Run from the project root so the shared module is importable.
"""

import sys
import os
import time
import random
from datetime import datetime

# Add project root to path so shared module is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from shared.kafka_client import create_producer

TOPIC = "vehicle-locations"

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


def main():
    print(f"Creating Kafka producer for topic '{TOPIC}'...")
    producer = create_producer()
    print("Producer ready. Sending vehicle location updates every 2 seconds. Press Ctrl+C to stop.")

    try:
        while True:
            for v in VEHICLES:
                # Random walk
                v["lat"] += random.uniform(-STEP_LAT, STEP_LAT)
                v["lon"] += random.uniform(-STEP_LON, STEP_LON)

                message = {
                    "vehicle_id": v["vehicle_id"],
                    "lat": round(v["lat"], 6),
                    "lon": round(v["lon"], 6),
                    "timestamp": datetime.now().isoformat(),
                }

                producer.send(
                    TOPIC,
                    key=v["vehicle_id"].encode("utf-8"),
                    value=message,
                )

                print(f"  {v['vehicle_id']}: ({message['lat']}, {message['lon']})")

            producer.flush()
            print("---")
            time.sleep(2)
    except KeyboardInterrupt:
        print("\nStopping simulator.")
    finally:
        producer.close()


if __name__ == "__main__":
    main()
