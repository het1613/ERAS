-- ERAS Database Schema

-- Sessions table
CREATE TABLE IF NOT EXISTS sessions (
    id VARCHAR(36) PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) DEFAULT 'active'
);

-- Transcripts table
CREATE TABLE IF NOT EXISTS transcripts (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(36) NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Suggestions table (expanded to match full Suggestion Pydantic model)
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

-- Vehicles table
CREATE TABLE IF NOT EXISTS vehicles (
    id VARCHAR(50) PRIMARY KEY,
    lat DECIMAL(10, 8) NOT NULL,
    lon DECIMAL(11, 8) NOT NULL,
    status VARCHAR(20) DEFAULT 'available',
    vehicle_type VARCHAR(20) NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Incidents table (expanded with lifecycle statuses, assigned vehicle, source tracking)
-- Valid statuses: open, dispatched, en_route, on_scene, transporting, at_hospital, resolved
CREATE TABLE IF NOT EXISTS incidents (
    id VARCHAR(36) PRIMARY KEY,
    session_id VARCHAR(36) REFERENCES sessions(id) ON DELETE SET NULL,
    lat DECIMAL(10, 8) NOT NULL,
    lon DECIMAL(11, 8) NOT NULL,
    location VARCHAR(255),
    type VARCHAR(100),
    priority VARCHAR(20) DEFAULT 'Yellow',
    weight INT DEFAULT 1,
    status VARCHAR(20) DEFAULT 'open',
    source VARCHAR(20) DEFAULT 'manual',
    assigned_vehicle_id VARCHAR(50),
    dispatch_metadata JSONB DEFAULT '{}',
    reported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Dispatches table: persists active dispatch routes (replaces in-memory active_routes)
CREATE TABLE IF NOT EXISTS dispatches (
    id SERIAL PRIMARY KEY,
    incident_id VARCHAR(36) REFERENCES incidents(id) ON DELETE CASCADE,
    vehicle_id VARCHAR(50) NOT NULL,
    route JSONB,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- Incident events table: audit log of every status transition
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

-- Hospitals table
CREATE TABLE IF NOT EXISTS hospitals (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    lat DECIMAL(10, 8) NOT NULL,
    lon DECIMAL(11, 8) NOT NULL,
    address VARCHAR(500)
);

INSERT INTO hospitals (name, lat, lon, address) VALUES
    ('St. Mary''s General Hospital', 43.43863840, -80.50070577, '911 Queen''s Blvd, Kitchener, ON N2M 1B2'),
    ('Cambridge Memorial Hospital', 43.37850136, -80.32882889, '700 Coronation Blvd, Cambridge, ON N1R 3G2'),
    ('Grand River Hospital Freeport Campus', 43.42630976, -80.40818941, '3570 King St E, Kitchener, ON N2G 2M1'),
    ('Grand River Hospital', 43.45684165, -80.51168502, '835 King St W, Kitchener, ON N2G 1G3');

-- Seed 25 ambulances across the Waterloo Region
INSERT INTO vehicles (id, lat, lon, status, vehicle_type) VALUES
    -- Kitchener (~9)
    ('ambulance-1',  43.4516, -80.4925, 'available', 'ambulance'),
    ('ambulance-2',  43.4480, -80.4860, 'available', 'ambulance'),
    ('ambulance-3',  43.4420, -80.4980, 'available', 'ambulance'),
    ('ambulance-4',  43.4350, -80.5050, 'available', 'ambulance'),
    ('ambulance-5',  43.4290, -80.5150, 'available', 'ambulance'),
    ('ambulance-6',  43.4450, -80.5200, 'available', 'ambulance'),
    ('ambulance-7',  43.4380, -80.5300, 'available', 'ambulance'),
    ('ambulance-8',  43.4550, -80.4750, 'available', 'ambulance'),
    ('ambulance-9',  43.4600, -80.5100, 'available', 'ambulance'),
    -- Waterloo (~5)
    ('ambulance-10', 43.4643, -80.5204, 'available', 'ambulance'),
    ('ambulance-11', 43.4723, -80.5449, 'available', 'ambulance'),
    ('ambulance-12', 43.4800, -80.5300, 'available', 'ambulance'),
    ('ambulance-13', 43.4900, -80.5200, 'available', 'ambulance'),
    ('ambulance-14', 43.4750, -80.5050, 'available', 'ambulance'),
    -- Cambridge (~5)
    ('ambulance-15', 43.3600, -80.3150, 'available', 'ambulance'),
    ('ambulance-16', 43.3785, -80.3290, 'available', 'ambulance'),
    ('ambulance-17', 43.3950, -80.3450, 'available', 'ambulance'),
    ('ambulance-18', 43.3900, -80.3700, 'available', 'ambulance'),
    ('ambulance-19', 43.4000, -80.3200, 'available', 'ambulance'),
    -- Rural / Townships (~6)
    ('ambulance-20', 43.5950, -80.5500, 'available', 'ambulance'),
    ('ambulance-21', 43.5350, -80.5550, 'available', 'ambulance'),
    ('ambulance-22', 43.3780, -80.7250, 'available', 'ambulance'),
    ('ambulance-23', 43.4050, -80.6600, 'available', 'ambulance'),
    ('ambulance-24', 43.2850, -80.4500, 'available', 'ambulance'),
    ('ambulance-25', 43.4730, -80.4100, 'available', 'ambulance');

-- User study tables for A/B dispatch testing with NASA TLX
CREATE TABLE IF NOT EXISTS user_studies (
    id VARCHAR(36) PRIMARY KEY,
    round_order VARCHAR(20) NOT NULL,
    feedback TEXT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_study_rounds (
    id SERIAL PRIMARY KEY,
    study_id VARCHAR(36) NOT NULL REFERENCES user_studies(id) ON DELETE CASCADE,
    round_number INT NOT NULL,
    mode VARCHAR(20) NOT NULL,
    dispatch_times JSONB,
    avg_dispatch_time_ms FLOAT,
    tlx_mental_demand INT,
    tlx_physical_demand INT,
    tlx_temporal_demand INT,
    tlx_effort INT,
    tlx_performance INT,
    tlx_frustration INT,
    completed_at TIMESTAMP
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_transcripts_session_id ON transcripts(session_id);
CREATE INDEX IF NOT EXISTS idx_transcripts_timestamp ON transcripts(timestamp);
CREATE INDEX IF NOT EXISTS idx_suggestions_session_id ON suggestions(session_id);
CREATE INDEX IF NOT EXISTS idx_suggestions_status ON suggestions(status);
CREATE INDEX IF NOT EXISTS idx_vehicles_status ON vehicles(status);
CREATE INDEX IF NOT EXISTS idx_vehicles_type ON vehicles(vehicle_type);
CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status);
CREATE INDEX IF NOT EXISTS idx_incidents_session_id ON incidents(session_id);
CREATE INDEX IF NOT EXISTS idx_incidents_source ON incidents(source);
CREATE INDEX IF NOT EXISTS idx_dispatches_status ON dispatches(status);
CREATE INDEX IF NOT EXISTS idx_dispatches_vehicle_id ON dispatches(vehicle_id);
CREATE INDEX IF NOT EXISTS idx_dispatches_incident_id ON dispatches(incident_id);
CREATE INDEX IF NOT EXISTS idx_incident_events_incident_id ON incident_events(incident_id);
CREATE INDEX IF NOT EXISTS idx_incident_events_timestamp ON incident_events(timestamp);
