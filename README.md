# ERAS (Emergency Response Assistance System)

## Overview

ERAS is a microservices-based emergency dispatch system designed to enhance emergency response operations. The system processes incoming emergency calls in real-time, extracts critical information, generates actionable suggestions for dispatchers, and facilitates optimal resource allocation.

## Architecture

### System Components

The system consists of **5 Python microservices**, **1 React frontend**, and supporting infrastructure:

1. **Audio Ingestion Service** (`services/audio-ingestion/`)
   - Receives audio file uploads from dispatchers
   - Chunks and publishes audio data to Kafka

2. **Audio Processing Service** (`services/audio-processing/`)
   - Consumes audio chunks from Kafka
   - Performs Speech-to-Text transcription
   - Publishes transcripts to Kafka

3. **Suggestion Engine** (`services/suggestion-engine/`)
   - Consumes transcripts from Kafka
   - Generates suggestions
   - Publishes suggestions to Kafka

4. **Geospatial Dispatch Service** (`services/geospatial-dispatch/`)
   - Manages vehicle tracking and locations
   - Provides vehicle assignment recommendations
   - Handles route suggestions
   - Port: `8002`

5. **Dashboard API Service** (`services/dashboard-api/`)
   - Aggregated REST API for frontend
   - WebSocket server for real-time updates
   - Consumes from Kafka and broadcasts to clients
   - Port: `8000`

6. **Frontend Dashboard** (`frontend/`)
   - React + TypeScript application
   - Split-screen layout: transcripts (left) and map (right)
   - Real-time updates via WebSocket
   - Port: `3000` (development)
   
### Infrastructure

- **Kafka + Zookeeper**: Message queue for event-driven communication
- **PostgreSQL**: Persistent storage for sessions, transcripts, suggestions, and vehicles
- **Docker Compose**: Orchestration for all services

### Data Flow

```
Audio File Upload
    ↓
Audio Ingestion Service
    ↓
Kafka: audio-chunks topic
    ↓
Audio Processing Service
    ↓
Kafka: transcripts topic
    ↓
Suggestion Engine ──→ Kafka: suggestions topic
    ↓                                         ↓
Dashboard API ←──────────────────────────────┘
    ↓
WebSocket → Frontend Dashboard
    ↓
Geospatial Dispatch Service (for vehicle assignments)
```


### Project Structure

```
ERAS/
├── services/                   # Microservices
│   ├── audio-ingestion/        # Audio file upload service
│   ├── audio-processing/       # STT processing worker
│   ├── suggestion-engine/      # AI suggestion generator
│   ├── geospatial-dispatch/    # Vehicle management service
│   └── dashboard-api/          # Frontend API gateway
├── frontend/                   # React application
│   ├── src/
│   │   ├── components/         # React components
│   │   ├── App.tsx             # Main app component
│   │   └── main.tsx            # Entry point
│   ├── package.json
│   └── vite.config.ts
├── shared/                     # Shared Python utilities
│   ├── types.py                # Data models (Pydantic)
│   └── kafka_client.py         # Kafka producer/consumer helpers
├── infrastructure/             # Infrastructure configuration
│   └── postgres/
│       └── init.sql            # Database schema
├── docker-compose.yml          # Service orchestration
├── .env.example                # Environment variables template
└── README.md                   # This file
```

## Local Setup

### Installation Steps

1. **Clone the repository**
   ```bash
   git clone https://github.com/het1613/ERAS.git
   cd ERAS
   ```

2. **Verify Docker is running**
   ```bash
   docker --version
   docker-compose --version
   ```

3. **Set up environment variables**
   
   Create a `.env` file in the project root if you want to customize defaults:
   ```env
   POSTGRES_DB=eras_db
   POSTGRES_USER=eras_user
   POSTGRES_PASSWORD=eras_pass
   KAFKA_BOOTSTRAP_SERVERS=localhost:9092
   ```

4. **Install frontend dependencies**
   ```bash
   cd frontend
   npm install
   cd ..
   ```

### Environment Variables

Key environment variables (with defaults):

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_DB` | `eras_db` | PostgreSQL database name |
| `POSTGRES_USER` | `eras_user` | PostgreSQL username |
| `POSTGRES_PASSWORD` | `eras_pass` | PostgreSQL password |
| `KAFKA_BOOTSTRAP_SERVERS` | `kafka:29092` | Kafka broker address (internal) |
| `GEOSPATIAL_DISPATCH_URL` | `http://geospatial-dispatch:8002` | Geospatial service URL (internal) |

## How to Run

### Starting the Backend

```bash
# Start all infrastructure and services
docker-compose up -d
```

This will start:
- Zookeeper and Kafka (message queue infrastructure)
- PostgreSQL (database)
- All 5 microservices
- Services will be accessible on their respective ports

### Starting the Frontend

After backend services are running, start the frontend development server:

```bash
cd frontend
npm run dev
```

The frontend will be available at: `http://localhost:3000`

### Verifying Services Are Running

Check service status:
```bash
docker-compose ps
```

All services should show `Up` status. You can also check logs:
```bash
# All services
docker-compose logs

# Specific service
docker-compose logs dashboard-api
docker-compose logs audio-ingestion
```

### Stopping the System

```bash
# Stop all services (keeps data)
docker-compose down

# Stop and remove volumes (clears database)
docker-compose down -v
```

## Service Endpoints

### Dashboard API (`http://localhost:8000`)
- `GET /health` - Health check
- `GET /sessions` - List all active sessions
- `GET /sessions/{id}/transcript` - Get transcripts for a session
- `GET /sessions/{id}/suggestions` - Get suggestions for a session
- `GET /sessions/{id}/assignment` - Get vehicle assignment for a session
- `GET /vehicles` - Get all vehicles (proxied from geospatial service)
- `WS /ws` - WebSocket endpoint for real-time updates

### Audio Ingestion (`http://localhost:8001`)
- `GET /health` - Health check
- `POST /ingest` - Upload audio file (multipart/form-data)

### Geospatial Dispatch (`http://localhost:8002`)
- `GET /health` - Health check
- `GET /vehicles` - List vehicles (with optional `?status=available` filter)
- `GET /vehicles/{id}` - Get specific vehicle
- `GET /assignments/{session_id}` - Get/generate vehicle assignment
  - Optional query params: `?lat=43.4643&lon=-80.5204`
- `POST /assignments/{session_id}/accept` - Accept vehicle assignment

## Development

### Building Services

Services are automatically built when starting with `docker-compose up`. To rebuild:

```bash
# Rebuild all services
docker-compose build

# Rebuild specific service
docker-compose build dashboard-api
```

### Viewing Logs

```bash
# All services (follow mode)
docker-compose logs -f

# Specific service
docker-compose logs -f dashboard-api
docker-compose logs -f audio-processing

# Last 100 lines of a service
docker-compose logs --tail=100 suggestion-engine
```

### Making Code Changes

1. **Python services**: Edit files in `services/<service-name>/main.py`
2. **Rebuild the service**: `docker-compose build <service-name>`
3. **Restart the service**: `docker-compose restart <service-name>`

TODO: Mount volumes to avoid rebuilds

### Database Access

Connect to PostgreSQL:
```bash
# Using docker exec
docker exec -it eras-postgres psql -U eras_user -d eras_db

# Or using connection string
psql postgresql://eras_user:eras_pass@localhost:5432/eras_db
```