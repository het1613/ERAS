# ERAS Setup Guide

## Prerequisites

- Docker and Docker Compose
- Node.js 18+ (for local frontend development)
- Python 3.11+ (for local service development)

## Quick Start with Docker

1. **Start all services:**
   ```bash
   docker-compose up -d
   ```

2. **Check service status:**
   ```bash
   docker-compose ps
   ```

3. **View logs:**
   ```bash
   docker-compose logs -f [service-name]
   ```

4. **Stop all services:**
   ```bash
   docker-compose down
   ```

## Service Ports

- Audio Ingestion: `8001`
- Audio Processing: `8002`
- AI Suggestion Engine: `8003`
- Geospatial Dispatch: `8004`
- Dashboard API: `8005`
- Frontend: `3000`
- PostgreSQL: `5432`
- Redis: `6379`
- Kafka: `9092`
- Zookeeper: `2181`

## Local Development

### Backend Services

Each service can be run independently:

```bash
cd services/audio-ingestion
python -m uvicorn main:app --reload --port 8001
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Testing the System

1. **Upload an audio file:**
   ```bash
   curl -X POST http://localhost:8001/api/v1/audio/upload \
     -F "file=@test_audio.wav"
   ```

2. **Check sessions:**
   ```bash
   curl http://localhost:8005/api/v1/sessions
   ```

3. **Add a test vehicle:**
   ```bash
   curl -X POST http://localhost:8004/api/v1/vehicles/vehicle-001/location \
     -H "Content-Type: application/json" \
     -d '{"lat": 43.4723, "lng": -80.5449, "vehicle_type": "ambulance"}'
   ```

## Database Access

Connect to PostgreSQL:
```bash
docker exec -it eras-postgres-1 psql -U eras_user -d eras_db
```

