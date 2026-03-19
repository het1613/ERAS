-- Migration v5: User study tables for A/B dispatch testing with NASA TLX

CREATE TABLE IF NOT EXISTS user_studies (
    id VARCHAR(36) PRIMARY KEY,
    round_order VARCHAR(20) NOT NULL,  -- "manual_first" or "optimizer_first"
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_study_rounds (
    id SERIAL PRIMARY KEY,
    study_id VARCHAR(36) NOT NULL REFERENCES user_studies(id) ON DELETE CASCADE,
    round_number INT NOT NULL,
    mode VARCHAR(20) NOT NULL,         -- "manual" or "optimizer"
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
