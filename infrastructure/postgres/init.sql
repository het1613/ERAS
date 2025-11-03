-- ERAS Database Schema

-- Sessions table
CREATE TABLE IF NOT EXISTS sessions (
    session_id VARCHAR(255) PRIMARY KEY,
    caller_info JSONB,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    incident_code VARCHAR(50),
    dispatched_vehicles JSONB DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Processed transcripts table
CREATE TABLE IF NOT EXISTS transcripts (
    transcript_id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL REFERENCES sessions(session_id),
    transcript TEXT NOT NULL,
    confidence FLOAT,
    language VARCHAR(10) DEFAULT 'en',
    entities JSONB,
    incident_type VARCHAR(50),
    location JSONB,
    severity VARCHAR(50),
    timestamp TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- AI suggestions table
CREATE TABLE IF NOT EXISTS suggestions (
    suggestion_id VARCHAR(255) PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL REFERENCES sessions(session_id),
    type VARCHAR(50) NOT NULL,
    content JSONB NOT NULL,
    confidence FLOAT,
    status VARCHAR(50) DEFAULT 'pending',
    timestamp TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Vehicles table
CREATE TABLE IF NOT EXISTS vehicles (
    vehicle_id VARCHAR(255) PRIMARY KEY,
    vehicle_type VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL,
    location JSONB NOT NULL,
    current_incident_id VARCHAR(255),
    metadata JSONB,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Dispatch commands table
CREATE TABLE IF NOT EXISTS dispatch_commands (
    command_id VARCHAR(255) PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL REFERENCES sessions(session_id),
    vehicle_id VARCHAR(255) NOT NULL REFERENCES vehicles(vehicle_id),
    incident_id VARCHAR(255) NOT NULL,
    route JSONB,
    status VARCHAR(50) DEFAULT 'pending',
    timestamp TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
CREATE INDEX IF NOT EXISTS idx_transcripts_session ON transcripts(session_id);
CREATE INDEX IF NOT EXISTS idx_suggestions_session ON suggestions(session_id);
CREATE INDEX IF NOT EXISTS idx_suggestions_status ON suggestions(status);
CREATE INDEX IF NOT EXISTS idx_vehicles_status ON vehicles(status);
CREATE INDEX IF NOT EXISTS idx_dispatch_commands_session ON dispatch_commands(session_id);

