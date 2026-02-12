# Dashboard API Service

FastAPI gateway that aggregates REST endpoints and provides a WebSocket bridge from Kafka to the frontend.

## Responsibilities

1. **REST proxy** -- forwards `/vehicles`, `/assignments` to `geospatial-dispatch:8002`
2. **In-memory session store** -- accumulates transcripts and suggestions keyed by `session_id`
3. **Kafka-to-WebSocket bridge** -- consumes Kafka topics in a background thread and broadcasts JSON messages to all connected WebSocket clients via `ConnectionManager.broadcast()`

## Kafka Topics Consumed

| Topic | Handler | Stored? | WS message type |
|---|---|---|---|
| `transcripts` | `process_transcript_message()` | Yes (`transcripts_by_session`) | `{"type": "transcript", "data": {...}}` |
| `suggestions` | `process_suggestion_message()` | Yes (`suggestions_by_session`) | `{"type": "suggestion", "data": {...}}` |
| `vehicle-locations` | `process_vehicle_location_message()` | No (pass-through) | `{"type": "vehicle_location", "data": {...}}` |

Consumer group: `dashboard-api-service`. Auto-offset: latest.

### WebSocket Message Format (vehicle_location)

```json
{
  "type": "vehicle_location",
  "data": {
    "vehicle_id": "ambulance-1",
    "lat": 43.4723,
    "lon": -80.5449,
    "timestamp": "2026-01-22T22:20:13.226897"
  }
}
```

## Architecture Notes

- Kafka consumer runs in a **daemon thread** (`kafka_consumer_thread()`), started on FastAPI `startup` event
- Thread-to-async bridge: `asyncio.run_coroutine_threadsafe()` schedules `broadcast()` on the stored `event_loop`
- Adding a new Kafka topic: (1) add topic string to `create_consumer(topics=[...])`, (2) write a `process_*_message()` function, (3) add `elif topic ==` branch in consumer loop

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/sessions` | List sessions with transcript/suggestion counts |
| `GET` | `/sessions/{id}/transcript` | Transcripts for a session |
| `GET` | `/sessions/{id}/suggestions` | Suggestions for a session |
| `GET` | `/sessions/{id}/assignment` | Vehicle assignment (proxied to geospatial-dispatch) |
| `GET` | `/vehicles` | Vehicle list (proxied to geospatial-dispatch) |
| `WS` | `/ws` | Real-time updates (transcripts, suggestions, vehicle locations) |

## Key Files

| File | Purpose |
|---|---|
| `main.py` | All routes, WebSocket handler, Kafka consumer, broadcast logic |
| `requirements.txt` | Python dependencies |
| `Dockerfile` | Container build |
