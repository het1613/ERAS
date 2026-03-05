-- Migration v3: Add hospitals table with address column and seed data
-- Run against existing volumes that already have the v2 schema.
-- Usage: docker exec eras-postgres psql -U eras_user -d eras_db < infrastructure/postgres/migrate_v3.sql

CREATE TABLE IF NOT EXISTS hospitals (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    lat DECIMAL(10, 8) NOT NULL,
    lon DECIMAL(11, 8) NOT NULL,
    address VARCHAR(500)
);

-- Seed hospital data (only insert if table is empty to avoid duplicates on re-run)
INSERT INTO hospitals (name, lat, lon, address)
SELECT * FROM (VALUES
    ('St. Mary''s General Hospital', 43.43863840::DECIMAL(10,8), (-80.50070577)::DECIMAL(11,8), '911 Queen''s Blvd, Kitchener, ON N2M 1B2'::VARCHAR(500)),
    ('Cambridge Memorial Hospital', 43.37850136::DECIMAL(10,8), (-80.32882889)::DECIMAL(11,8), '700 Coronation Blvd, Cambridge, ON N1R 3G2'::VARCHAR(500)),
    ('Grand River Hospital Freeport Campus', 43.42630976::DECIMAL(10,8), (-80.40818941)::DECIMAL(11,8), '3570 King St E, Kitchener, ON N2G 2M1'::VARCHAR(500)),
    ('Grand River Hospital', 43.45684165::DECIMAL(10,8), (-80.51168502)::DECIMAL(11,8), '835 King St W, Kitchener, ON N2G 1G3'::VARCHAR(500))
) AS v(name, lat, lon, address)
WHERE NOT EXISTS (SELECT 1 FROM hospitals);
