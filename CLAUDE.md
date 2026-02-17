# ERAS - Emergency Response Assistance System

## Architecture

Microservices orchestrated by Docker Compose. React frontend (Vite) connects to `dashboard-api` which proxies to other services and pushes real-time updates via WebSocket.

```
frontend (React/Vite, :3000)
  |
  v
dashboard-api (FastAPI, :8000)  <-- REST + WebSocket gateway, incident CRUD, Kafka consumer
  |
  +---> geospatial-dispatch (FastAPI, :8002)  <-- vehicle tracking, assignment optimization
  +---> postgres (:5432)                       <-- sessions, transcripts, suggestions, incidents, vehicles
  +---> kafka (:9092 external / :29092 internal)
  |
audio-ingestion (:8001) --> kafka --> audio-processing --> kafka --> suggestion-engine --> kafka --> dashboard-api
```

## Key Directories

- `services/` — Each service has its own `main.py`, `Dockerfile`, `requirements.txt`
- `shared/` — Shared Python code mounted into all service containers
  - `types.py` — Pydantic models (AudioChunk, Transcript, Suggestion, Vehicle, Incident, etc.)
  - `kafka_client.py` — Kafka producer/consumer helpers
  - `db.py` — `get_connection()` returns psycopg2 connection via `DATABASE_URL` env var
- `infrastructure/postgres/init.sql` — DB schema (runs on first postgres init only)
- `frontend/src/` — React app with Vite

## Database

PostgreSQL 15. Tables: `sessions`, `transcripts`, `suggestions`, `vehicles`, `incidents`.

The `incidents` table is the source of truth for all incident state. Schema:
```
id (PK), session_id (FK->sessions), lat, lon, location, type, priority, weight, status, reported_at, updated_at
```

Priority-to-weight mapping (auto-set when weight omitted): Purple=16, Red=8, Orange=4, Yellow=2, Green=1. Defined in `shared/types.py:PRIORITY_WEIGHT_MAP`.

**Important:** `init.sql` only runs on first postgres volume creation. If you add tables, either recreate the volume (`docker compose down -v && docker compose up`) or run the SQL manually: `docker exec eras-postgres psql -U eras_user -d eras_db -c "SQL HERE"`.

## Incidents Flow

1. **Create:** `POST /incidents` on dashboard-api writes to DB, broadcasts `incident_created` over WebSocket
2. **List/Get:** `GET /incidents[?status=open]`, `GET /incidents/{id}` on dashboard-api reads from DB
3. **Update:** `PATCH /incidents/{id}` on dashboard-api updates DB, broadcasts `incident_updated` over WebSocket
4. **Dispatch:** `POST /assignments/find-best` on geospatial-dispatch accepts `{"incident_id": "..."}`, reads all open incidents from DB, runs ILP optimizer, returns best vehicle, sets incident status to `in_progress`
5. **Accept:** `POST /assignments/{suggestion_id}/accept` on geospatial-dispatch marks vehicle as dispatched, fetches OSRM route, publishes `vehicle-dispatches` Kafka event
6. **Arrival:** Simulator publishes `vehicle-arrivals` Kafka event when vehicle reaches destination. Dashboard-api consumes it, marks incident `resolved` in DB, broadcasts `incident_updated` via WebSocket. Geospatial-dispatch consumes it and resets vehicle status to `available`.

Frontend `useIncidents` hook fetches `GET /incidents` on mount, then listens for `incident_created`/`incident_updated` WebSocket messages.

## Vehicle Tracking

Vehicles are initialized in-memory (`MOCK_VEHICLES` in geospatial-dispatch) but their positions are updated in real-time from the `vehicle-locations` Kafka topic. `VehicleLocationTracker` runs a background Kafka consumer that updates `Vehicle.lat`/`.lon` in-place. Dashboard-api also consumes `vehicle-locations` and broadcasts to frontend via WebSocket. Frontend `useVehicleUpdates` hook follows same REST+WS pattern. The `vehicles` table exists in postgres but is not currently read/written by services — Kafka is the source of truth for positions.

## Dispatch Routing (OSRM)

When an assignment is accepted (`POST /assignments/{id}/accept`), geospatial-dispatch:
1. Fetches a driving route from OSRM (`https://router.project-osrm.org/route/v1/driving/...`) — free, no API key
2. Publishes a `VehicleDispatchEvent` to the `vehicle-dispatches` Kafka topic containing the full route geometry as `[[lat, lon], ...]`

**Kafka topic: `vehicle-dispatches`** — consumed by both the simulator and dashboard-api.

**Simulator** (`scripts/simulate_vehicle_locations.py`):
- Runs a background thread consuming `vehicle-dispatches`; stores route waypoints in a thread-safe `vehicle_routes` dict
- Each 2s tick: dispatched vehicles advance along waypoints at ~60 km/h (Haversine interpolation); non-dispatched vehicles random-walk
- On arrival: route is removed, publishes `VehicleArrivalEvent` to `vehicle-arrivals` Kafka topic, then resumes random walk; prints `[ROUTED]`/`[RANDOM]`/`[ARRIVED]` per vehicle
- Start with: `KAFKA_BOOTSTRAP_SERVERS=localhost:9092 python scripts/simulate_vehicle_locations.py`

**Dashboard-API**: consumes `vehicle-dispatches`, broadcasts `{type: "vehicle_dispatched", data: {vehicle_id, incident_id, route: [{lat, lng}...]}}` via WebSocket. Route coords are converted from `[lat, lon]` to `{lat, lng}` for Google Maps.

**Frontend**:
- `useVehicleUpdates` hook: maintains `routeMap` state (Map<vehicleId, LatLngLiteral[]>), handles `vehicle_dispatched` WS messages. Clears route when corresponding incident is resolved (`incident_updated` with `status: "resolved"`), using an `incidentToVehicleRef` mapping.
- `MapPanel`: renders `<Polyline>` from `@react-google-maps/api` for each active route (blue, 4px stroke). Accepts `routes` prop from `Dashboard.tsx`.

**Key types** in `shared/types.py`: `VehicleDispatchEvent` (vehicle_id, incident_id, incident_lat, incident_lon, route, timestamp), `VehicleArrivalEvent` (vehicle_id, incident_id, timestamp).

**Graceful degradation**: if OSRM is unreachable, dispatch still succeeds but no route is published — vehicle falls back to random walk in the simulator.

## Running

```bash
docker compose up --build        # all services
cd frontend && npm run dev       # frontend on :3000
```

Env vars (with defaults in docker-compose.yml):
- `DATABASE_URL` — postgres connection string (set on dashboard-api and geospatial-dispatch)
- `KAFKA_BOOTSTRAP_SERVERS` — `kafka:29092` inside Docker, `localhost:9092` for local scripts
- `GEOSPATIAL_DISPATCH_URL` — internal URL for dashboard-api to reach geospatial-dispatch
- `VITE_API_URL` — frontend API base URL (defaults to `http://localhost:8000`)

## Kafka Topics

- `audio-chunks` — raw audio from ingestion
- `transcripts` — transcribed text from audio-processing
- `suggestions` — AI suggestions from suggestion-engine
- `vehicle-locations` — real-time GPS positions (produced by simulator, consumed by dashboard-api + geospatial-dispatch)
- `vehicle-dispatches` — dispatch events with OSRM routes (produced by geospatial-dispatch on accept, consumed by simulator + dashboard-api)
- `vehicle-arrivals` — arrival events (produced by simulator on route completion, consumed by dashboard-api to auto-resolve incident + geospatial-dispatch to reset vehicle to available)

## Testing Endpoints

```bash
# Create incident
curl -X POST http://localhost:8000/incidents -H "Content-Type: application/json" \
  -d '{"lat":43.47,"lon":-80.54,"location":"234 Columbia St","type":"Cardiac Arrest","priority":"Purple"}'

# List incidents
curl http://localhost:8000/incidents

# Update incident status
curl -X PATCH http://localhost:8000/incidents/{id} -H "Content-Type: application/json" \
  -d '{"status":"resolved"}'

# Find best vehicle assignment
curl -X POST http://localhost:8002/assignments/find-best -H "Content-Type: application/json" \
  -d '{"incident_id":"<uuid>"}'

# Accept assignment (triggers OSRM route fetch + Kafka dispatch event)
curl -X POST http://localhost:8002/assignments/{suggestion_id}/accept
```

## Known Limitations / TODOs

- Vehicle initial state is hardcoded (`MOCK_VEHICLES`); positions update live via Kafka but the roster itself isn't dynamic
- Sessions/transcripts/suggestions still stored in-memory in dashboard-api (TODO: migrate to postgres)
- `on_event` startup/shutdown handlers are deprecated — should migrate to FastAPI lifespan
- No authentication on any endpoint
- ILP optimizer still uses Euclidean distance for assignment scoring; only post-accept routing uses OSRM
- OSRM uses public demo server (`router.project-osrm.org`) — should self-host for production
- Arrival auto-resolve depends on simulator running; without it, incidents must be manually resolved via `PATCH /incidents/{id}`
