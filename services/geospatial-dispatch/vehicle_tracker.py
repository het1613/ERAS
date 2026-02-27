"""
Vehicle Location Tracker - Consumes real-time vehicle positions from Kafka.
"""

import os
import logging
import threading
from typing import Dict, List, Tuple

from shared.kafka_client import create_consumer
from shared.types import Vehicle

logger = logging.getLogger(__name__)

VEHICLE_LOCATIONS_TOPIC = "vehicle-locations"


class VehicleLocationTracker:
    """
    Maintains a thread-safe dict of latest vehicle positions by consuming
    from the 'vehicle-locations' Kafka topic in a background thread.
    Updates Vehicle objects in-place before optimization runs.
    """

    def __init__(self, vehicles: List[Vehicle]):
        self._vehicles = vehicles
        self._lock = threading.Lock()
        # Seed positions from initial vehicle data
        self._positions: Dict[str, Tuple[float, float]] = {
            v.id: (v.lat, v.lon) for v in vehicles
        }
        self._consumer_thread: threading.Thread | None = None

    def start_consumer(self) -> None:
        """Start the background Kafka consumer thread."""
        self._consumer_thread = threading.Thread(
            target=self._consume_loop,
            daemon=True,
            name="vehicle-location-consumer",
        )
        self._consumer_thread.start()
        logger.info("Vehicle location consumer thread started")

    def _consume_loop(self) -> None:
        """Continuously consume vehicle location messages from Kafka."""
        try:
            consumer = create_consumer(
                topics=[VEHICLE_LOCATIONS_TOPIC],
                group_id=os.getenv("KAFKA_CONSUMER_GROUP_ID", "geospatial-dispatch-service"),
                auto_offset_reset="latest",
            )
            logger.info(f"Subscribed to '{VEHICLE_LOCATIONS_TOPIC}' topic")
        except Exception:
            logger.exception("Failed to create Kafka consumer for vehicle locations. Positions will remain static.")
            return

        for message in consumer:
            try:
                data = message.value
                vehicle_id = data.get("vehicle_id")
                lat = data.get("lat")
                lon = data.get("lon")

                if vehicle_id is None or lat is None or lon is None:
                    logger.warning(f"Skipping malformed vehicle location message: {data}")
                    continue

                with self._lock:
                    self._positions[vehicle_id] = (float(lat), float(lon))

                logger.debug(f"Updated position for {vehicle_id}: ({lat}, {lon})")
            except Exception:
                logger.exception("Error processing vehicle location message")

    def update_vehicle_positions(self) -> None:
        """
        Snapshot current positions and patch Vehicle objects in-place.
        Call this before any operation that reads vehicle coordinates.
        """
        with self._lock:
            positions_snapshot = dict(self._positions)

        for vehicle in self._vehicles:
            if vehicle.id in positions_snapshot:
                vehicle.lat, vehicle.lon = positions_snapshot[vehicle.id]

    def reset_positions(self, vehicles: List[Vehicle]) -> None:
        """Re-seed position cache from the (already-reset) vehicle objects."""
        with self._lock:
            self._positions = {v.id: (v.lat, v.lon) for v in vehicles}
