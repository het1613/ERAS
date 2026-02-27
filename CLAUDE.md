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
  +---> postgres (:5432)                       <-- sessions, transcripts, suggestions, incidents, dispatches, incident_events, vehicles
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
- `infrastructure/postgres/migrate_v2.sql` — Migration for existing volumes (expanded suggestions, dispatches, incident_events tables)
- `frontend/src/` — React app with Vite

## Database

PostgreSQL 15. Tables: `sessions`, `transcripts`, `suggestions`, `vehicles`, `incidents`, `dispatches`, `incident_events`.

**All data is persisted to PostgreSQL.** Sessions, transcripts, and suggestions are written to DB on Kafka consumption. Only ephemeral vehicle statuses remain in-memory (they rebuild from live Kafka messages on restart).

The `incidents` table is the source of truth for all incident state. Schema:
```
id (PK), session_id (FK->sessions), lat, lon, location, type, priority, weight,
status, source, assigned_vehicle_id, dispatch_metadata (JSONB), reported_at, updated_at
```

The `suggestions` table stores all structured fields from the Suggestion Pydantic model (id is VARCHAR PK matching the suggestion engine's ID, not SERIAL).

The `dispatches` table persists active dispatch routes (replaces old in-memory `active_routes` dict):
```
id (SERIAL PK), incident_id (FK), vehicle_id, route (JSONB), status (active/completed), created_at, completed_at
```

The `incident_events` table is an audit log of every status transition:
```
id (SERIAL PK), incident_id (FK), event_type, old_status, new_status, vehicle_id, timestamp, metadata (JSONB)
```

**Incident statuses:** `open` → `dispatched` → `en_route` → `on_scene` → `transporting` → `at_hospital` → `resolved`

**Incident source:** `call_taker` (from suggestion acceptance or manual call-taker entry) or `manual` (from POST /incidents without source override). The dispatcher Cases tab only shows `call_taker` incidents.

Priority-to-weight mapping (auto-set when weight omitted): Purple=16, Red=8, Orange=4, Yellow=2, Green=1. Defined in `shared/types.py:PRIORITY_WEIGHT_MAP`.

**Important:** `init.sql` only runs on first postgres volume creation. For existing volumes, run the migration: `docker exec eras-postgres psql -U eras_user -d eras_db < infrastructure/postgres/migrate_v2.sql`. Or recreate the volume: `docker compose down -v && docker compose up`.

## Incidents Flow

1. **Create (call taker via AI):** `POST /suggestions/{id}/accept` on dashboard-api creates incident with `source='call_taker'`, writes to DB, broadcasts `incident_created` over WebSocket, auto-triggers dispatch optimization.
2. **Create (call taker manual):** `POST /incidents` with `source='call_taker'` creates incident, broadcasts, and auto-triggers dispatch (same as AI-accepted). Used by the Manual Incident Entry form in the call-taker UI.
3. **Create (testing):** `POST /incidents` without `source` (defaults to `'manual'`). These do NOT appear in dispatcher Cases tab.
4. **List/Get:** `GET /incidents[?status=open&source=call_taker]`, `GET /incidents/{id}` on dashboard-api reads from DB.
5. **Update:** `PATCH /incidents/{id}` on dashboard-api updates DB, logs to `incident_events`, broadcasts `incident_updated` over WebSocket.
6. **Auto-Dispatch (server-side):** When call-taker accepts a suggestion or creates a manual call-taker incident, dashboard-api creates the incident AND immediately calls geospatial-dispatch `find-best`. The result is broadcast via a `dispatch_suggestion` WebSocket message.
7. **Find-Best:** `POST /assignments/find-best` runs ILP optimizer, fetches OSRM route preview, returns suggestion. Accepts optional `exclude_vehicles` list. Does NOT change incident status. Stores route in `vehicle_assignments` for reuse on accept.
8. **Accept:** `POST /assignments/{suggestion_id}/accept` marks vehicle as dispatched, publishes `vehicle-dispatches` Kafka event. Dashboard-api consumes the dispatch event and transitions incident to `dispatched`, sets `assigned_vehicle_id`, persists route in `dispatches` table.
9. **Decline:** `POST /assignments/{suggestion_id}/decline` removes suggestion from memory. No status changes.
10. **Decline-and-Reassign:** `POST /assignments/{suggestion_id}/decline-and-reassign` declines the current suggestion, persists declined vehicle in `dispatch_metadata` JSONB, re-runs find-best with excluded vehicles.

### Full Case Lifecycle (via Kafka events from simulator):
1. **dispatched** → Vehicle dispatched to scene (from `vehicle-dispatches` Kafka topic)
2. **on_scene** → Vehicle arrived at scene (from `vehicle-arrivals` topic)
3. **transporting** → Vehicle leaving scene heading to Grand River Hospital (from `vehicle-transporting` topic, includes OSRM route)
4. **at_hospital** → Vehicle arrived at hospital (from `vehicle-at-hospital` topic)
5. **resolved** → Case complete, vehicle returning to available (from `vehicle-resolved` topic)

Each status transition is logged in `incident_events` and broadcast as `incident_updated` via WebSocket.

All assignment endpoints are proxied through dashboard-api (:8000) so the frontend only talks to one service.

## Vehicle Tracking

Vehicles are initialized in-memory (`MOCK_VEHICLES` in geospatial-dispatch) but their positions are updated in real-time from the `vehicle-locations` Kafka topic. `VehicleLocationTracker` runs a background Kafka consumer that updates `Vehicle.lat`/`.lon` in-place. The `vehicles` table exists in postgres but is not currently read/written by services — Kafka is the source of truth for positions.

**Vehicle status tracking:** Dashboard-api maintains an in-memory `vehicle_statuses` dict, updated from simulator status in `vehicle-locations` messages and lifecycle events. Every `vehicle_location` WS broadcast is enriched with `status`.

**Active routes persistence:** Dashboard-api persists active dispatch routes in the `dispatches` table (not in-memory). Populated on dispatch, cleared on arrival/completion. Exposed via `GET /active-routes` so frontend can recover routes after page refresh. Routes survive service restarts.

**Frontend** `useVehicleUpdates` hook: fetches `GET /vehicles` + `GET /active-routes` on mount, then receives live updates via WS. Reads vehicle status from `vehicle_location` messages. Reads routes from `vehicle_dispatched` WS messages + initial `active-routes` REST fetch.

## Dispatch Routing (OSRM)

When an assignment is accepted, geospatial-dispatch fetches a driving route from OSRM and publishes a `VehicleDispatchEvent` to `vehicle-dispatches`.

**Hospital:** Grand River Hospital at 835 King St W, Kitchener, ON N2G 1G3 (43.455280, -80.505836). After on-scene time, the simulator fetches an OSRM route from the scene to the hospital and the ambulance follows it.

**Simulator** (`scripts/simulate_vehicle_locations.py`):
- Full lifecycle: `available → dispatched → on_scene (30s) → transporting (to hospital) → at_hospital (20s) → returning (30s) → available`
- Dispatched vehicles follow OSRM routes at ~60 km/h; idle vehicles random-walk
- Publishes events to: `vehicle-arrivals` (at scene), `vehicle-transporting` (leaving scene), `vehicle-at-hospital` (at hospital), `vehicle-resolved` (case complete)
- Start with: `KAFKA_BOOTSTRAP_SERVERS=localhost:9092 python scripts/simulate_vehicle_locations.py`

**Dashboard-API**: consumes all lifecycle Kafka topics, persists dispatch routes in `dispatches` table, transitions incident statuses, broadcasts updates via WebSocket.

**Frontend call-taker & dispatch UI** (`frontend/src/`):
- `components/CallTaker.tsx` — Call-taker screen. Shows live transcript, AI suggestions with editable fields, and a **Manual Incident Entry** card always at the top of AI Suggestions (creates incidents with `source='call_taker'` via `POST /incidents`).
- `hooks/useDispatchSuggestion.ts` — manages active dispatch suggestion state.
- `components/types.ts` — `CaseStatus` type includes all lifecycle statuses. `CaseInfo` includes `source` and `assigned_vehicle_id`.
- `components/CaseCard.tsx` — Shows full lifecycle progress bar: Open → Dispatched → En Route → On Scene → Transporting → At Hospital → Resolved. Shows assigned vehicle name.
- `components/CasePanel.tsx` — "Active Cases" (non-resolved) and "Past Cases" (resolved, collapsible) sections.
- `components/Dashboard.tsx` — Filters incidents to `source=call_taker` for the Cases tab. Builds `dispatchInfoMap` directly from incident status (status is granular enough).
- `components/MapPanel.tsx` — Renders dispatch suggestions, routes, and ambulance markers.

**Key types** in `shared/types.py`: `VehicleDispatchEvent`, `VehicleArrivalEvent`, `VehicleTransportingEvent`, `VehicleAtHospitalEvent`, `GRAND_RIVER_HOSPITAL`, `INCIDENT_STATUSES`.

**Graceful degradation**: if OSRM is unreachable, dispatch still succeeds but no route is published — vehicle falls back to random walk in the simulator.

## Running

```bash
docker compose up --build        # all services
cd frontend && npm run dev       # frontend on :3000
KAFKA_BOOTSTRAP_SERVERS=localhost:9092 python scripts/simulate_vehicle_locations.py  # vehicle movement simulator
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
- `vehicle-arrivals` — arrival at scene events (produced by simulator, consumed by dashboard-api → sets `on_scene` + geospatial-dispatch)
- `vehicle-transporting` — leaving scene heading to hospital (produced by simulator, consumed by dashboard-api → sets `transporting`)
- `vehicle-at-hospital` — arrived at hospital (produced by simulator, consumed by dashboard-api → sets `at_hospital`)
- `vehicle-resolved` — case complete (produced by simulator, consumed by dashboard-api → sets `resolved` + geospatial-dispatch → resets vehicle to `available`)

## Testing Endpoints

```bash
# Create incident manually (source=manual by default, won't show in dispatcher Cases tab)
curl -X POST http://localhost:8000/incidents -H "Content-Type: application/json" \
  -d '{"lat":43.47,"lon":-80.54,"location":"234 Columbia St","type":"Cardiac Arrest","priority":"Purple"}'

# Create incident as call_taker (shows in Cases tab, auto-dispatches)
curl -X POST http://localhost:8000/incidents -H "Content-Type: application/json" \
  -d '{"lat":43.47,"lon":-80.54,"location":"234 Columbia St","type":"Cardiac Arrest","priority":"Purple","source":"call_taker"}'

# List all incidents
curl http://localhost:8000/incidents

# List only call-taker incidents (what dispatcher sees)
curl "http://localhost:8000/incidents?source=call_taker"

# Update incident status
curl -X PATCH http://localhost:8000/incidents/{id} -H "Content-Type: application/json" \
  -d '{"status":"resolved"}'

# Find best vehicle assignment (via dashboard-api proxy)
curl -X POST http://localhost:8000/assignments/find-best -H "Content-Type: application/json" \
  -d '{"incident_id":"<uuid>"}'

# Accept assignment (triggers OSRM route + Kafka dispatch event)
curl -X POST http://localhost:8000/assignments/{suggestion_id}/accept

# Decline assignment (clears suggestion, no dispatch)
curl -X POST http://localhost:8000/assignments/{suggestion_id}/decline

# Decline and reassign (suggests next best vehicle, excluding declined one)
curl -X POST http://localhost:8000/assignments/{suggestion_id}/decline-and-reassign \
  -H "Content-Type: application/json" \
  -d '{"incident_id":"<uuid>","declined_vehicle_id":"ambulance-1"}'

# Get active dispatch routes (persisted across restarts)
curl http://localhost:8000/active-routes
```

## Known Limitations / TODOs

- Vehicle initial state is hardcoded (`MOCK_VEHICLES`); positions update live via Kafka but the roster itself isn't dynamic
- Vehicle statuses in dashboard-api are still in-memory (ephemeral) — they rebuild from Kafka on restart, which is acceptable for real-time positions
- `on_event` startup/shutdown handlers are deprecated — should migrate to FastAPI lifespan
- No authentication on any endpoint
- ILP optimizer still uses Euclidean distance for assignment scoring; only post-accept routing uses OSRM
- OSRM uses public demo server (`router.project-osrm.org`) — should self-host for production
- Full lifecycle depends on simulator running; without it, incidents must be manually resolved via `PATCH /incidents/{id}`
- Only one dispatch suggestion can be active at a time in the frontend (`useDispatchSuggestion` stores a single suggestion). Queuing/multi-incident dispatch is not yet supported.
