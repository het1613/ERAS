-- migrate_v6.sql: Reduce vehicle roster from 40 to 25 ambulances
-- Run on existing volumes: docker exec eras-postgres psql -U eras_user -d eras_db < infrastructure/postgres/migrate_v6.sql
-- Idempotent: deletes existing vehicles first

DELETE FROM vehicles;

INSERT INTO vehicles (id, lat, lon, status, vehicle_type) VALUES
    -- Kitchener (~9)
    ('ambulance-1',  43.4516, -80.4925, 'available', 'ambulance'),  -- Downtown Kitchener
    ('ambulance-2',  43.4480, -80.4860, 'available', 'ambulance'),  -- Kitchener City Hall area
    ('ambulance-3',  43.4420, -80.4980, 'available', 'ambulance'),  -- Victoria Park
    ('ambulance-4',  43.4350, -80.5050, 'available', 'ambulance'),  -- South Kitchener
    ('ambulance-5',  43.4290, -80.5150, 'available', 'ambulance'),  -- Homer Watson Blvd
    ('ambulance-6',  43.4450, -80.5200, 'available', 'ambulance'),  -- Westmount
    ('ambulance-7',  43.4380, -80.5300, 'available', 'ambulance'),  -- Doon area
    ('ambulance-8',  43.4550, -80.4750, 'available', 'ambulance'),  -- East Kitchener / Fairview
    ('ambulance-9',  43.4600, -80.5100, 'available', 'ambulance'),  -- Kitchener-Waterloo border

    -- Waterloo (~5)
    ('ambulance-10', 43.4643, -80.5204, 'available', 'ambulance'),  -- Uptown Waterloo
    ('ambulance-11', 43.4723, -80.5449, 'available', 'ambulance'),  -- University of Waterloo
    ('ambulance-12', 43.4800, -80.5300, 'available', 'ambulance'),  -- North Waterloo / Columbia
    ('ambulance-13', 43.4900, -80.5200, 'available', 'ambulance'),  -- Laurelwood
    ('ambulance-14', 43.4750, -80.5050, 'available', 'ambulance'),  -- Lakeshore

    -- Cambridge (~5)
    ('ambulance-15', 43.3600, -80.3150, 'available', 'ambulance'),  -- Galt downtown
    ('ambulance-16', 43.3785, -80.3290, 'available', 'ambulance'),  -- Cambridge Memorial area
    ('ambulance-17', 43.3950, -80.3450, 'available', 'ambulance'),  -- Preston
    ('ambulance-18', 43.3900, -80.3700, 'available', 'ambulance'),  -- Blair
    ('ambulance-19', 43.4000, -80.3200, 'available', 'ambulance'),  -- Hespeler

    -- Rural / Townships (~6)
    ('ambulance-20', 43.5950, -80.5500, 'available', 'ambulance'),  -- Elmira
    ('ambulance-21', 43.5350, -80.5550, 'available', 'ambulance'),  -- St. Jacobs
    ('ambulance-22', 43.3780, -80.7250, 'available', 'ambulance'),  -- New Hamburg
    ('ambulance-23', 43.4050, -80.6600, 'available', 'ambulance'),  -- Baden
    ('ambulance-24', 43.2850, -80.4500, 'available', 'ambulance'),  -- Ayr
    ('ambulance-25', 43.4730, -80.4100, 'available', 'ambulance');  -- Breslau
