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

Phone (PSTN) --> Twilio --> audio-ingestion /ws/twilio-stream (mu-law 8kHz → PCM 16kHz) ──┐
Browser mic   --> Caller.tsx --> audio-ingestion /ws/stream                                ├──> Kafka "audio-chunks"
                                                                                          ┘
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

PostgreSQL 15. Tables: `sessions`, `transcripts`, `suggestions`, `vehicles`, `incidents`, `dispatches`, `incident_events`, `hospitals`.

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

The `hospitals` table stores hospital locations used by the optimizer and frontend:
```
id (SERIAL PK), name, lat, lon, address
```
Seeded in `init.sql` with 4 hospitals: St. Mary's General, Cambridge Memorial, Grand River Freeport Campus, Grand River Hospital. Exposed via `GET /hospitals` on dashboard-api.

**Incident statuses:** `open` → `dispatched` → `en_route` → `on_scene` → `transporting` → `at_hospital` → `resolved`

**Incident source:** `call_taker` (from suggestion acceptance or manual call-taker entry) or `manual` (from POST /incidents without source override). The dispatcher Cases tab only shows `call_taker` incidents.

Priority-to-weight mapping (auto-set when weight omitted): Purple=16, Red=8, Orange=4, Yellow=2, Green=1. Defined in `shared/types.py:PRIORITY_WEIGHT_MAP`.

**Important:** `init.sql` only runs on first postgres volume creation. For existing volumes, run migrations: `docker exec eras-postgres psql -U eras_user -d eras_db < infrastructure/postgres/migrate_v2.sql` (expanded suggestions, dispatches, incident_events tables) and `migrate_v4.sql` (seed 40 vehicles), `migrate_v6.sql` (reduce to 25 vehicles). Or recreate the volume: `docker compose down -v && docker compose up`.

## Incidents Flow

1. **Create (call taker via AI):** `POST /suggestions/{id}/accept` on dashboard-api creates incident with `source='call_taker'`, writes to DB, broadcasts `incident_created` over WebSocket.
2. **Create (call taker manual):** `POST /incidents` with `source='call_taker'` creates incident and broadcasts. Used by the Manual Incident Entry form in the call-taker UI.
3. **Create (testing):** `POST /incidents` without `source` (defaults to `'manual'`). These do NOT appear in dispatcher Cases tab.
4. **List/Get:** `GET /incidents[?status=open&source=call_taker]`, `GET /incidents/{id}` on dashboard-api reads from DB.
5. **Update:** `PATCH /incidents/{id}` on dashboard-api updates DB, logs to `incident_events`, broadcasts `incident_updated` over WebSocket.
6. **Dispatch is dispatcher-initiated (no auto-dispatch).** Incident creation does NOT trigger `find-best`. The dispatcher must click the "Dispatch" button on a case card, which triggers the frontend to call `find-best` (default mode) or enter manual ambulance selection mode.
7. **Find-Best:** `POST /assignments/find-best` runs ILP optimizer (loads hospitals from DB via `get_hospitals_from_db()`), fetches OSRM route preview, returns suggestion including `hospital` object (id, name, lat, lon, address). Accepts optional `exclude_vehicles` list. Does NOT change incident status. Stores route + hospital in `vehicle_assignments` for reuse on accept.
8. **Preview:** `POST /assignments/preview` takes `{incident_id, vehicle_id}`, fetches OSRM route for a specific vehicle-incident pair, finds nearest hospital. Returns same format as find-best without running the ILP optimizer. Used for manual ambulance selection.
9. **Accept:** `POST /assignments/{suggestion_id}/accept` marks vehicle as dispatched, publishes `vehicle-dispatches` Kafka event (includes `hospital_lat/lon/name`). Dashboard-api consumes the dispatch event and transitions incident to `dispatched`, sets `assigned_vehicle_id`, persists route in `dispatches` table.
10. **Decline:** `POST /assignments/{suggestion_id}/decline` removes suggestion from memory. No status changes.
11. **Decline-and-Reassign:** `POST /assignments/{suggestion_id}/decline-and-reassign` declines the current suggestion, persists declined vehicle in `dispatch_metadata` JSONB, re-runs find-best with excluded vehicles.

### Full Case Lifecycle (via Kafka events from simulator):
1. **dispatched** → Vehicle dispatched to scene (from `vehicle-dispatches` Kafka topic)
2. **on_scene** → Vehicle arrived at scene (from `vehicle-arrivals` topic)
3. **transporting** → Vehicle leaving scene heading to assigned hospital (from `vehicle-transporting` topic, includes OSRM route + `hospital_lat/lon/name`)
4. **at_hospital** → Vehicle arrived at hospital (from `vehicle-at-hospital` topic)
5. **resolved** → Case complete, vehicle returning to available (from `vehicle-resolved` topic)

Each status transition is logged in `incident_events` and broadcast as `incident_updated` via WebSocket.

All assignment endpoints are proxied through dashboard-api (:8000) so the frontend only talks to one service.

## Vehicle Tracking

The vehicle roster (25 ambulances across the Waterloo Region) is seeded in PostgreSQL (`vehicles` table) and loaded at startup by both geospatial-dispatch and the simulator. Real-time positions are updated via the `vehicle-locations` Kafka topic. `VehicleLocationTracker` runs a background Kafka consumer that updates `Vehicle.lat`/`.lon` in-place.

**Adding/removing vehicles:** Edit the seed data in `init.sql` (for fresh volumes) and `migrate_v4.sql` (for existing volumes). Both geospatial-dispatch and the simulator load from DB on startup with retry logic.

**Vehicle status tracking:** Dashboard-api maintains an in-memory `vehicle_statuses` dict, updated from simulator status in `vehicle-locations` messages and lifecycle events. Every `vehicle_location` WS broadcast is enriched with `status`.

**Active routes persistence:** Dashboard-api persists active dispatch routes in the `dispatches` table (not in-memory). Populated on dispatch, cleared on arrival/completion. Exposed via `GET /active-routes` so frontend can recover routes after page refresh. Routes survive service restarts.

**Frontend** `useVehicleUpdates` hook: fetches `GET /vehicles` + `GET /active-routes` on mount, then receives live updates via WS. Reads vehicle status from `vehicle_location` messages. Reads routes from `vehicle_dispatched` WS messages + initial `active-routes` REST fetch.

## Dispatch Routing (OSRM)

When an assignment is accepted, geospatial-dispatch fetches a driving route from OSRM and publishes a `VehicleDispatchEvent` to `vehicle-dispatches`.

**Hospitals:** Loaded dynamically from the `hospitals` DB table. The ILP optimizer (`optimization.py`) computes the nearest hospital per incident; geospatial-dispatch maps the optimizer's `hospital_id` index to DB metadata and includes it in the dispatch suggestion and `VehicleDispatchEvent`. The simulator carries hospital info through `dispatched → on_scene → transporting` state transitions and routes to the assigned hospital (falls back to Grand River Hospital if dispatch event lacks hospital fields).

**Simulator** (`scripts/simulate_vehicle_locations.py`):
- Full lifecycle: `available → dispatched → on_scene (30s) → transporting (to hospital) → at_hospital (20s) → returning (30s) → available`
- Dispatched vehicles follow OSRM routes at ~60 km/h; idle vehicles random-walk
- Publishes events to: `vehicle-arrivals` (at scene), `vehicle-transporting` (leaving scene), `vehicle-at-hospital` (at hospital), `vehicle-resolved` (case complete)
- Start with: `KAFKA_BOOTSTRAP_SERVERS=localhost:9092 python scripts/simulate_vehicle_locations.py`

**Dashboard-API**: consumes all lifecycle Kafka topics, persists dispatch routes in `dispatches` table, transitions incident statuses, broadcasts updates via WebSocket.

**Frontend call-taker & dispatch UI** (`frontend/src/`):
- `components/CallTaker.tsx` — Call-taker screen. Shows live transcript, AI suggestions with editable fields, and a **Manual Incident Entry** card always at the top of AI Suggestions (creates incidents with `source='call_taker'` via `POST /incidents`).
- `hooks/useDispatchSuggestion.ts` — Queue-based dispatch suggestion management (FIFO queue, not single suggestion). Exposes `findBest` (clears queue, calls optimizer), `preview` (replaces front of queue for specific vehicle), `accept`/`decline`/`declineAndReassign` (pop front). Also exposes `queueLength`. WS `dispatch_suggestion` messages append to queue.
- `hooks/useIncidents.ts` — REST + WebSocket incident sync. Uses client-side monotonic counter (`seq`) for ordering so newest incidents always sort first regardless of server timestamps.
- `contexts/DispatchTestContext.tsx` — Dispatch test orchestration (6 timed incidents) and `manualMode` toggle. Shared between NavBar and Dashboard.
- `components/types.ts` — `CaseStatus` type includes all lifecycle statuses. `CaseInfo` includes `source` and `assigned_vehicle_id`. `Hospital` interface. `DispatchSuggestion` includes optional `hospital`.
- `components/CaseCard.tsx` — Shows full lifecycle progress bar: Open → Dispatched → En Route → On Scene → Transporting → At Hospital → Resolved. Shows assigned vehicle name. "Dispatch" button shown for open cases without active dispatch.
- `components/CasePanel.tsx` — "Active Cases" (non-resolved) section. Sorted by arrival order (newest first from `useIncidents`).
- `components/Dashboard.tsx` — Filters incidents to `source=call_taker` for the Cases tab. `handleDispatch` respects `manualMode`: default calls `findBest`, manual enters ambulance selection. `handleAmbulanceClick` calls `preview` when `dispatchingIncidentId` is set. Uses `focusedIncidentSeq` counter to ensure map always re-pans.
- `components/MapPanel.tsx` — Renders dispatch suggestions (with hospital name), routes, ambulance markers, and dynamic hospital markers. Shows "Select an ambulance to dispatch" banner when in manual selection mode (`dispatchingIncidentId` set, no suggestion yet).
- `components/NavBar.tsx` — "Manual" toggle button (switches dispatch mode), "Start Test" button, test progress badge, "Reset" button.
- `components/TestResultsModal.tsx` — Results table after dispatch test completes, showing per-incident time-to-dispatch and average.

**Key types** in `shared/types.py`: `VehicleDispatchEvent` (includes optional `hospital_lat/lon/name`), `VehicleArrivalEvent`, `VehicleTransportingEvent` (includes optional `hospital_lat/lon/name`), `VehicleAtHospitalEvent`, `AssignmentSuggestion` (includes optional `hospital_id/name/lat/lon/address`), `GRAND_RIVER_HOSPITAL`, `INCIDENT_STATUSES`.

**Graceful degradation**: if OSRM is unreachable, dispatch still succeeds but no route is published — vehicle falls back to random walk in the simulator.

## Running

```bash
docker compose up --build        # all services
cd frontend && npm run dev       # frontend on :3000
DATABASE_URL=postgresql://eras_user:eras_pass@localhost:5432/eras_db KAFKA_BOOTSTRAP_SERVERS=localhost:9092 python scripts/simulate_vehicle_locations.py  # vehicle movement simulator
```

Env vars (with defaults in docker-compose.yml):
- `DATABASE_URL` — postgres connection string (set on dashboard-api, geospatial-dispatch, and vehicle-simulator)
- `KAFKA_BOOTSTRAP_SERVERS` — `kafka:29092` inside Docker, `localhost:9092` for local scripts
- `GEOSPATIAL_DISPATCH_URL` — internal URL for dashboard-api to reach geospatial-dispatch
- `VITE_API_URL` — frontend API base URL (defaults to `http://localhost:8000`)
- `TWILIO_STREAM_URL` — public WSS URL for Twilio Media Streams (set on audio-ingestion, e.g. `wss://<ngrok-subdomain>.ngrok-free.app/ws/twilio-stream`)
- `STT_PROVIDER` — `whisperx` (default, local inference) or `deepgram` (Deepgram Nova-3 API). Set on audio-processing.
- `DEEPGRAM_API_KEY` — required when `STT_PROVIDER=deepgram`. Get from https://console.deepgram.com

## Phone Call Integration (Twilio)

Real phone callers can dial a Twilio number and have their call appear in the dashboard identically to browser-based audio. Both input methods coexist — phone sessions and browser sessions appear side by side.

**How it works:** Caller dials Twilio number → Twilio opens a WebSocket to `audio-ingestion /ws/twilio-stream` → audio is converted from mu-law 8kHz to PCM 16kHz → published as `AudioChunk` to Kafka → same downstream pipeline as browser audio.

**Audio conversion:** Twilio sends 8kHz mu-law (G.711) audio. The endpoint converts it to 16kHz 16-bit PCM using Python's `audioop` stdlib module (available in Python 3.10; use `audioop-lts` package if upgrading to 3.13+).

**Endpoints added to audio-ingestion:**
- `WS /ws/twilio-stream` — Handles Twilio Media Stream JSON protocol (`connected`, `start`, `media`, `stop` events)
- `POST /twilio/voice` — Returns TwiML XML greeting + Media Stream connection. Used as the Twilio phone number's Voice webhook.

**AudioChunk metadata:** `call_source` (`"phone"` or `None`) and `caller_number` fields are optional on `AudioChunk` in `shared/types.py`. Backward-compatible — downstream services ignore them if absent.

### Setup

Prerequisites: Twilio account with a phone number, ngrok installed and authenticated.

1. **Start ngrok:** `ngrok http 8001` — copy the forwarding URL (e.g., `https://abc123.ngrok-free.app`)
2. **Update `TWILIO_STREAM_URL`** in `docker-compose.yml` under `audio-ingestion` environment: `wss://<ngrok-url>/ws/twilio-stream`
3. **Configure Twilio webhook:** In Twilio Console → Phone Numbers → your number → Voice Configuration → set "A call comes in" to Webhook, URL: `https://<ngrok-url>/twilio/voice`, Method: HTTP POST
4. **Rebuild:** `docker compose up --build`
5. **Call the number** — speech flows through to the CallTaker dashboard

**Important: ngrok URL changes on every restart** (free plan). Each time you restart ngrok, you must:
1. Update `TWILIO_STREAM_URL` in `docker-compose.yml` with the new URL
2. Update the Twilio Voice webhook URL in the Twilio Console
3. Rebuild: `docker compose up --build`

To avoid this, claim a free static domain at https://dashboard.ngrok.com/domains and run `ngrok http 8001 --url=YOUR_STATIC_DOMAIN`.

### Notes
- Phone audio transcription quality is slightly lower than browser mic (8kHz vs 16kHz source)
- Expect ~7-10 seconds end-to-end latency (vs 6-8 for browser) due to Twilio network hop
- Only inbound caller audio is processed (`track="inbound_track"`)
- Twilio free trial gives $15 credit; a Canadian number costs ~$1.15 CAD/month + ~$0.0085 USD/min incoming

## Speech-to-Text (STT)

Toggled via `STT_PROVIDER` env var in `.env` (loaded automatically by Docker Compose).

**WhisperX** (`STT_PROVIDER=whisperx`, default): Local inference using `small.en` model on CPU with int8 quantization. No API key needed. Uses `initial_prompt` with rolling session context (~200 chars) for continuity across chunks.

**Deepgram** (`STT_PROVIDER=deepgram`): Deepgram Nova-3 API. Requires `DEEPGRAM_API_KEY` in `.env` ($200 free credit on signup at https://console.deepgram.com). Options enabled: `smart_format`, `numerals` (converts spoken numbers to digits), `keyterm` (Waterloo region address boosting).

**Keyterms:** `services/audio-processing/waterloo_keyterms.json` contains Waterloo region street/neighbourhood names loaded at startup and passed as `keyterm` to Deepgram Nova-3. Add entries to improve recognition of local addresses. No boost syntax — Nova-3 keyterms are plain strings.

**Switching:** Set `STT_PROVIDER` in `.env` and rebuild: `docker compose up --build audio-processing`. Both providers output to the same Kafka `transcripts` topic with identical `Transcript` format.

## Kafka Topics

- `audio-chunks` — raw audio from ingestion
- `transcripts` — transcribed text from audio-processing
- `suggestions` — AI suggestions from suggestion-engine
- `vehicle-locations` — real-time GPS positions (produced by simulator, consumed by dashboard-api + geospatial-dispatch)
- `vehicle-dispatches` — dispatch events with OSRM routes + assigned hospital (produced by geospatial-dispatch on accept, consumed by simulator + dashboard-api)
- `vehicle-arrivals` — arrival at scene events (produced by simulator, consumed by dashboard-api → sets `on_scene` + geospatial-dispatch)
- `vehicle-transporting` — leaving scene heading to assigned hospital, includes `hospital_lat/lon/name` (produced by simulator, consumed by dashboard-api → sets `transporting`)
- `vehicle-at-hospital` — arrived at hospital (produced by simulator, consumed by dashboard-api → sets `at_hospital`)
- `vehicle-resolved` — case complete (produced by simulator, consumed by dashboard-api → sets `resolved` + geospatial-dispatch → resets vehicle to `available`)

## Testing Endpoints

```bash
# Create incident manually (source=manual by default, won't show in dispatcher Cases tab)
curl -X POST http://localhost:8000/incidents -H "Content-Type: application/json" \
  -d '{"lat":43.47,"lon":-80.54,"location":"234 Columbia St","type":"Cardiac Arrest","priority":"Purple"}'

# Create incident as call_taker (shows in Cases tab, dispatcher must manually dispatch)
curl -X POST http://localhost:8000/incidents -H "Content-Type: application/json" \
  -d '{"lat":43.47,"lon":-80.54,"location":"234 Columbia St","type":"Cardiac Arrest","priority":"Purple","source":"call_taker"}'

# List all incidents
curl http://localhost:8000/incidents

# List only call-taker incidents (what dispatcher sees)
curl "http://localhost:8000/incidents?source=call_taker"

# Update incident status
curl -X PATCH http://localhost:8000/incidents/{id} -H "Content-Type: application/json" \
  -d '{"status":"resolved"}'

# Find best vehicle assignment via optimizer (via dashboard-api proxy)
curl -X POST http://localhost:8000/assignments/find-best -H "Content-Type: application/json" \
  -d '{"incident_id":"<uuid>"}'

# Preview assignment for a specific vehicle (no optimizer, just OSRM route + nearest hospital)
curl -X POST http://localhost:8000/assignments/preview -H "Content-Type: application/json" \
  -d '{"incident_id":"<uuid>","vehicle_id":"ambulance-1"}'

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

# List hospitals (dynamic, from DB)
curl http://localhost:8000/hospitals
```

## Known Limitations / TODOs

- Vehicle roster is seeded in DB (25 ambulances); adding/removing requires editing SQL seed files and restarting services
- Vehicle statuses in dashboard-api are still in-memory (ephemeral) — they rebuild from Kafka on restart, which is acceptable for real-time positions
- Hospital roster is dynamic (from DB) but geospatial-dispatch queries the DB on every `find-best` call — could cache if performance matters
- `on_event` startup/shutdown handlers are deprecated — should migrate to FastAPI lifespan
- No authentication on any endpoint
- ILP optimizer still uses Euclidean distance for assignment scoring; only post-accept routing uses OSRM
- OSRM uses public demo server (`router.project-osrm.org`) — should self-host for production
- Full lifecycle depends on simulator running; without it, incidents must be manually resolved via `PATCH /incidents/{id}`
- `useDispatchSuggestion` uses a FIFO queue but only the front suggestion is shown at a time. Multi-incident simultaneous dispatch is not yet supported.

## Dispatch Test & Manual Mode

**Dispatch Test** (`contexts/DispatchTestContext.tsx`): Creates 6 hardcoded incidents at 10s intervals, tracks time from creation to `dispatched` status via WebSocket, shows results modal with per-incident timing. Triggered via "Start Test" button in NavBar. Resets system first, then creates incidents. 2-minute timeout fallback.

**Manual Mode** (toggled via "Manual" button in NavBar): Two dispatch modes shared via `DispatchTestContext`:
- **Default (optimizer):** Clicking "Dispatch" on a case calls `POST /assignments/find-best` → optimizer suggestion shown immediately on map. Clicking a different ambulance calls `POST /assignments/preview` to replace the suggestion with that vehicle's route.
- **Manual mode:** Clicking "Dispatch" enters ambulance selection mode (map pans to incident, banner shown). User must click an ambulance marker to get a route preview via `POST /assignments/preview`.

In both modes, the dispatcher accepts/declines the suggestion via the map tooltip. Accepting dispatches the vehicle; declining clears the suggestion.

**Incident inflow simulator** (`scripts/simulate_incident_inflow.py`): Creates batches of incidents for user testing. Calls `find-best` explicitly after each incident creation (no auto-dispatch). Supports `--count 10|20|40|80` with configurable delay. SCENARIO_10 includes 4 auto-accepted low-priority incidents (for reroute testing) and 6 user-handled incidents.
