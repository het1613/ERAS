-- Migration: Database Persistence and Full Case Lifecycle
-- Run against existing volumes that already have the v1 schema.
-- Usage: docker exec eras-postgres psql -U eras_user -d eras_db -f /docker-entrypoint-initdb.d/migrate_v2.sql
-- Or:    docker exec eras-postgres psql -U eras_user -d eras_db < infrastructure/postgres/migrate_v2.sql

-- 1. Expand suggestions table: change id from SERIAL to VARCHAR, add structured fields
--    Drop the old SERIAL-based suggestions and recreate with VARCHAR PK.
--    (Any existing data will be lost since it was only in-memory anyway.)
DROP TABLE IF EXISTS suggestions CASCADE;
CREATE TABLE IF NOT EXISTS suggestions (
    id VARCHAR(64) PRIMARY KEY,
    session_id VARCHAR(36) NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    suggestion_type VARCHAR(50) NOT NULL,
    value TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    incident_code VARCHAR(20),
    incident_code_description VARCHAR(255),
    incident_code_category VARCHAR(100),
    priority VARCHAR(20),
    confidence DECIMAL(3, 2),
    matched_evidence JSONB,
    extracted_location VARCHAR(500),
    extracted_lat DECIMAL(10, 8),
    extracted_lon DECIMAL(11, 8),
    location_confidence DECIMAL(3, 2)
);
CREATE INDEX IF NOT EXISTS idx_suggestions_session_id ON suggestions(session_id);
CREATE INDEX IF NOT EXISTS idx_suggestions_status ON suggestions(status);

-- 2. Expand incidents table
ALTER TABLE incidents ADD COLUMN IF NOT EXISTS source VARCHAR(20) DEFAULT 'manual';
ALTER TABLE incidents ADD COLUMN IF NOT EXISTS assigned_vehicle_id VARCHAR(50);
ALTER TABLE incidents ADD COLUMN IF NOT EXISTS dispatch_metadata JSONB DEFAULT '{}';
CREATE INDEX IF NOT EXISTS idx_incidents_source ON incidents(source);

-- 3. New dispatches table
CREATE TABLE IF NOT EXISTS dispatches (
    id SERIAL PRIMARY KEY,
    incident_id VARCHAR(36) REFERENCES incidents(id) ON DELETE CASCADE,
    vehicle_id VARCHAR(50) NOT NULL,
    route JSONB,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_dispatches_status ON dispatches(status);
CREATE INDEX IF NOT EXISTS idx_dispatches_vehicle_id ON dispatches(vehicle_id);
CREATE INDEX IF NOT EXISTS idx_dispatches_incident_id ON dispatches(incident_id);

-- 4. New incident_events table
CREATE TABLE IF NOT EXISTS incident_events (
    id SERIAL PRIMARY KEY,
    incident_id VARCHAR(36) REFERENCES incidents(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,
    old_status VARCHAR(20),
    new_status VARCHAR(20),
    vehicle_id VARCHAR(50),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB
);
CREATE INDEX IF NOT EXISTS idx_incident_events_incident_id ON incident_events(incident_id);
CREATE INDEX IF NOT EXISTS idx_incident_events_timestamp ON incident_events(timestamp);
