# Geospatial Dispatch Service

The Geospatial Dispatch Service is a FastAPI application responsible for tracking emergency vehicles and providing optimal dispatch assignments for incidents. It uses a weighted optimization model to prioritize high-urgency incidents and minimize total travel time.

## How it Works

The core of this service is an optimization model that assigns available ambulances to active incidents. The model can be used for both batch processing a list of existing incidents and for finding an optimal assignment for a new, single incident in the context of the current system state.

### Stateful Optimization

The service is **stateful**. It maintains an in-memory list of all incidents that have been reported but not yet assigned to a vehicle. When a new incident comes in via the `/assignments/find-best` endpoint, the service runs its optimization model against all available ambulances and all currently unassigned incidents. This ensures that the assignment for the new incident is globally optimal, not just the best choice in a vacuum.

### Cost Function

The assignment process is formulated as a k-assignment problem, a type of Integer Linear Program (ILP). The objective is to minimize a "weighted cost" for each assignment. The cost for assigning a specific ambulance to a specific incident is:

```
cost = (distance_from_ambulance_to_incident + distance_from_incident_to_hospital) / incident_weight
```

- **Distances**: The model calculates the distance from an available ambulance to the incident and from the incident to the nearest hospital. This is currently a simplified Euclidean distance, designed to be replaceable with a real routing service.
- **Incident Weight**: Each incident has a `weight` representing its urgency. A higher weight results in a lower cost, making it a higher priority.

### Optimization

The service uses the `pulp` library to solve the ILP. It determines the optimal set of assignments that minimizes the total weighted cost for all available ambulances and unassigned incidents.

## API Endpoints

The service exposes the following endpoints:

- `GET /health`: A health check endpoint.
- `GET /vehicles`: Returns a list of all vehicles. Can be filtered by status (e.g., `?status=available`).
- `GET /vehicles/{vehicle_id}`: Returns the details of a specific vehicle.
- `POST /assignments/find-best`: **Finds the globally optimal ambulance for a new incident.** This endpoint adds the new incident to a list of unassigned incidents and runs the optimization model to find the best assignment based on the current state of all vehicles and incidents.
- `GET /assignments/{suggestion_id}`: Retrieves a previously generated assignment suggestion by its suggestion ID.
- `POST /assignments/{suggestion_id}/accept`: Marks the vehicle in the suggested assignment as "dispatched", making it unavailable for future assignments.

## Real-Time Vehicle Location Tracking

Vehicle positions update in real-time via the `vehicle-locations` Kafka topic. This is handled by `vehicle_tracker.py`.

### Architecture

- `VehicleLocationTracker` (in `vehicle_tracker.py`) runs a Kafka consumer in a background daemon thread
- Maintains a thread-safe `dict` of latest positions (`threading.Lock`-protected)
- `update_vehicle_positions()` is called at the top of `get_vehicles()`, `get_vehicle()`, and `find_best_assignment()` to patch `Vehicle.lat`/`Vehicle.lon` in-place before any reads
- `optimization.py` requires **zero changes** -- it reads `v.lat`/`v.lon` from Vehicle objects which are updated in-place
- **Graceful degradation**: if Kafka is unavailable or no messages arrive, vehicles keep their hardcoded starting positions

### Kafka Message Format

```
Topic: vehicle-locations
Key: "ambulance-1" (bytes)
Value: {"vehicle_id": "ambulance-1", "lat": 43.4723, "lon": -80.5449, "timestamp": "2026-01-01T00:00:00"}
```

Consumer config: `auto_offset_reset="latest"`, group `geospatial-dispatch-service`.

### Vehicle Location Simulator

A standalone script for development/demo that publishes random-walk GPS updates:

```bash
# From project root (requires kafka-python installed locally)
KAFKA_BOOTSTRAP_SERVERS=localhost:9092 python scripts/simulate_vehicle_locations.py
```

Moves each ambulance ~200m every 2 seconds from their initial positions.

### Key Files

| File | Purpose |
|------|---------|
| `vehicle_tracker.py` | `VehicleLocationTracker` class -- Kafka consumer thread + position update logic |
| `main.py` | Instantiates tracker, starts consumer on startup, calls `update_vehicle_positions()` in endpoints |
| `shared/types.py` | `VehicleLocation` Pydantic model (Kafka message schema) |
| `scripts/simulate_vehicle_locations.py` | GPS simulator for dev/demo |

**Note**: The service currently operates with mock data for vehicles, incidents, and hospitals, which is defined in `main.py`. Vehicle positions are updated in real-time when the `vehicle-locations` Kafka topic is active.

## Running the Service for Local Testing

This service is designed to be run as part of the Docker-based environment for the entire ERAS project.

1.  **Build the service's Docker image:**
    ```bash
    docker-compose build geospatial-dispatch
    ```

2.  **Start the service (and its dependencies):**
    ```bash
    docker-compose up -d geospatial-dispatch
    ```
The service will be available at `http://localhost:8002`.

## Testing the API

You can test the assignment endpoints using `curl`.

### 1. Get a Globally Optimized Assignment for a New Incident

Send a `POST` request with the incident's location and weight. The service will return the best assignment, considering all other unassigned incidents and available ambulances.

```bash
curl -X POST http://localhost:8002/assignments/find-best \
-H "Content-Type: application/json" \
-d '{"lat": 43.45, "lon": -80.5, "weight": 10}'
```

The response will be an `AssignmentSuggestion` with a unique `suggestion_id`:
```json
{
  "suggestion_id": "a-unique-suggestion-id",
  "suggested_vehicle_id": "ambulance-2",
  "route": "Optimized route for ambulance-2 to new incident at (lat: 43.4500, lon: -80.5000). Total unweighted distance: 15.98 km.",
  "timestamp": "2026-01-22T22:20:13.226897"
}
```
If you send another request for a different incident, the service will find the best assignment from the *remaining* available ambulances.

### 2. Accept the Assignment

To accept a suggestion, make a `POST` request using the `suggestion_id` returned in the suggestion. This updates the status of the assigned vehicle to "dispatched".

```bash
curl -X POST http://localhost:8002/assignments/{suggestion_id}/accept
```

The response will confirm the acceptance:
```json
{
  "status": "accepted",
  "suggestion_id": "{suggestion_id}",
  "vehicle_id": "ambulance-2"
}
```

## Dependencies

- `fastapi`: Web framework
- `uvicorn`: ASGI server
- `pulp`: ILP optimization library
- `numpy`, `pandas`: For numerical operations
- `kafka-python`: Used for real-time vehicle location tracking via Kafka consumer