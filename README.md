# ERAS (Emergency Response Assistance System)

AI-assisted emergency dispatch system designed to enhance the efficiency, accuracy, and speed of emergency response operations.

## Architecture

Microservices-based architecture with the following components:

- **Audio Ingestion Service**: Handles audio input streams
- **Audio Processing Service**: STT and ML extraction
- **AI Suggestion Engine**: Generates actionable suggestions
- **Geospatial Dispatch Service**: Vehicle tracking and routing
- **Dashboard API**: Backend API for frontend
- **Dashboard Frontend**: React-based web interface

## Tech Stack

- **Backend**: Python (FastAPI)
- **Frontend**: TypeScript, React.js, Leaflet.js
- **Message Queue**: Kafka
- **Database**: PostgreSQL, Redis
- **Real-time**: WebSockets (Socket.io)
- **Containerization**: Docker, Docker Compose

## Quick Start

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop all services
docker-compose down
```

## Development

Each service can be run independently:

```bash
# Audio Ingestion Service
cd services/audio-ingestion
python -m uvicorn main:app --reload --port 8001

# Audio Processing Service
cd services/audio-processing
python -m uvicorn main:app --reload --port 8002

# AI Suggestion Engine
cd services/ai-suggestion-engine
python -m uvicorn main:app --reload --port 8003

# Geospatial Dispatch Service
cd services/geospatial-dispatch
python -m uvicorn main:app --reload --port 8004

# Dashboard API
cd services/dashboard-api
python -m uvicorn main:app --reload --port 8005

# Frontend
cd frontend
npm install
npm run dev
```

## Project Structure

```
ERAS/
├── services/              # Microservices
│   ├── audio-ingestion/
│   ├── audio-processing/
│   ├── ai-suggestion-engine/
│   ├── geospatial-dispatch/
│   └── dashboard-api/
├── frontend/              # React dashboard
├── shared/                # Shared utilities and types
├── infrastructure/        # Infrastructure configs
└── docker-compose.yml     # Service orchestration
```
