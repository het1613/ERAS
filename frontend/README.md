# Frontend Dashboard

React + TypeScript (Vite) split-screen dispatch dashboard.

## Layout

- **Left panel** -- tabbed: Ambulances | Cases | Transcripts (bottom nav switches between them)
- **Right panel** -- Google Maps with ambulance markers (OverlayView)

## Real-Time Vehicle Positions

Live ambulance positions flow from Kafka through the dashboard-api WebSocket to map markers and sidebar cards.

### Data Flow

```
Kafka (vehicle-locations)
  -> dashboard-api WS broadcast {"type": "vehicle_location", "data": {vehicle_id, lat, lon, timestamp}}
  -> useVehicleUpdates hook (merges lat/lon into Map<string, VehicleData>)
  -> Dashboard converts VehicleData[] -> UnitInfo[] via vehicleToUnit()
  -> MapPanel (markers reposition) + AmbulancePanel (coords update in cards)
```

### Key Hook: `useVehicleUpdates` (`src/hooks/useVehicleUpdates.ts`)

- **On mount**: `GET /vehicles` fetches initial vehicle list from dashboard-api (proxied from geospatial-dispatch)
- **WebSocket**: connects to `ws://<VITE_API_URL>/ws`, filters for `type: "vehicle_location"` messages
- **State**: `Map<string, VehicleData>` keyed by vehicle ID; WS messages merge `lat`/`lon` into existing entries
- **Returns**: `{ vehicles: VehicleData[], connected: boolean, loading: boolean }`

### Type Mapping (vehicleToUnit in Dashboard.tsx)

| Backend `status` | Frontend `UnitStatus` |
|---|---|
| `"available"` | `"Available"` |
| `"dispatched"` | `"Dispatched"` |
| `"offline"` | `"Returning"` |

Vehicle ID formatting: `"ambulance-1"` -> `"Ambulance 1"` (replace hyphens/underscores, title-case).

## Key Components

| File | Purpose |
|---|---|
| `Dashboard.tsx` | Top-level layout, owns `useVehicleUpdates`, converts `VehicleData` -> `UnitInfo`, passes to children |
| `MapPanel.tsx` | Google Maps with `OverlayView` markers; re-renders on `units` prop change |
| `AmbulancePanel.tsx` | Sidebar card list; defines `UnitInfo`, `VehicleData` interfaces |
| `AmbulanceCard.tsx` | Individual vehicle card (status, coords, crew) |
| `TranscriptPanel.tsx` | Separate WS connection for transcripts/suggestions (independent of vehicle updates) |
| `hooks/useVehicleUpdates.ts` | Custom hook for vehicle REST fetch + WS live updates |

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000` | Dashboard API base URL |
| `VITE_GOOGLE_MAPS_API_KEY` | (required) | Google Maps JavaScript API key |

## Development

```bash
npm install
npm run dev    # Vite dev server on port 3000
```

Requires backend services running (`docker compose up`).

## Testing Vehicle Updates

1. `docker compose up -d` (starts all backend services + Kafka)
2. `npm run dev` (start frontend)
3. `KAFKA_BOOTSTRAP_SERVERS=localhost:9092 python scripts/simulate_vehicle_locations.py` (start GPS simulator)
4. Open `http://localhost:3000` -- markers should move every ~2s
