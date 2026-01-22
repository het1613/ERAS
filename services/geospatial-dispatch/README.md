# Geospatial Dispatch Service

The Geospatial Dispatch Service is a FastAPI application responsible for tracking emergency vehicles and providing optimal dispatch assignments for incidents. It uses a weighted optimization model to prioritize high-urgency incidents and minimize total travel time.

## How it Works

The core of this service is an optimization model that assigns available ambulances to active incidents. The model operates in rounds, making a batch of assignments in each round until all incidents are served.

### Cost Function

The assignment process is formulated as a k-assignment problem, which is a type of Integer Linear Program (ILP). The objective is to minimize a "weighted cost" for each assignment. The cost for assigning a specific ambulance to a specific incident is calculated as:

```
cost = (distance_from_ambulance_to_incident + distance_from_incident_to_hospital) / incident_weight
```

- **Distances**: The model calculates the distance from an available ambulance to the incident location, and from the incident location to the nearest hospital. Currently, this is a simplified Euclidean distance, but it is designed to be replaceable with a real routing service.
- **Incident Weight**: Each incident has a `weight` that represents its urgency or severity. A higher weight results in a lower overall cost, making the incident a higher priority for assignment.

### Optimization

The service uses the `pulp` library to solve the ILP. In each round, it determines the optimal set of assignments (up to the number of available ambulances) that minimizes the total weighted cost for that round. After an ambulance is assigned, its position is updated to the location of the hospital it was sent to for the next round of assignments.

## API Endpoints

The service exposes the following endpoints:

- `GET /health`: A health check endpoint.
- `GET /vehicles`: Returns a list of all vehicles. Can be filtered by status (e.g., `?status=available`).
- `GET /vehicles/{vehicle_id}`: Returns the details of a specific vehicle.
- `GET /assignments/{session_id}`: Generates or retrieves an assignment suggestion for a given session ID. This endpoint triggers the optimization model.
- `POST /assignments/{session_id}/accept`: Marks the vehicle in the suggested assignment as "dispatched".

**Note**: The service currently operates with mock data for vehicles, incidents, and hospitals, which is defined in `main.py`.

## Running the Service

1.  Install the dependencies:
    ```bash
    pip install -r requirements.txt
    ```

2.  Run the FastAPI application:
    ```bash
    uvicorn main:app --host 0.0.0.0 --port 8002
    ```

## Testing the API

You can test the assignment endpoints using a tool like `curl`. The `session_id` can be any unique string you choose for the request.

### 1. Get an Assignment Suggestion

This will trigger the optimization model and return a suggested vehicle assignment.

```bash
curl -X GET http://localhost:8002/assignments/session-123
```

The response will look something like this:
```json
{
  "session_id": "session-123",
  "suggested_vehicle_id": "ambulance-1",
  "route": "Optimized route for ambulance-1 to incident 7 (lat: 43.3456, lon: -80.7593). Total unweighted distance: 54.32 km.",
  "timestamp": "2023-11-21T12:34:56.789Z"
}
```

### 2. Accept the Assignment

To accept the suggestion, make a `POST` request using the same `session_id`. This will update the status of the assigned vehicle to "dispatched".

```bash
curl -X POST http://localhost:8002/assignments/session-123/accept
```

The response will confirm the acceptance:
```json
{
  "status": "accepted",
  "session_id": "session-123",
  "vehicle_id": "ambulance-1"
}
```

## Dependencies

- `fastapi`: Web framework
- `uvicorn`: ASGI server
- `pulp`: ILP optimization library
- `numpy`, `pandas`: For numerical operations
- `kafka-python`: Included for potential future integration with a Kafka-based event stream.
