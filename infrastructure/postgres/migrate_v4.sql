-- migrate_v4.sql: Seed 40 ambulances into the vehicles table
-- Run on existing volumes: docker exec eras-postgres psql -U eras_user -d eras_db < infrastructure/postgres/migrate_v4.sql
-- Idempotent: deletes existing vehicles first

DELETE FROM vehicles;

INSERT INTO vehicles (id, lat, lon, status, vehicle_type) VALUES
    -- Kitchener (~14)
    ('ambulance-1',  43.4516, -80.4925, 'available', 'ambulance'),  -- Downtown Kitchener
    ('ambulance-2',  43.4480, -80.4860, 'available', 'ambulance'),  -- Kitchener City Hall area
    ('ambulance-3',  43.4420, -80.4980, 'available', 'ambulance'),  -- Victoria Park
    ('ambulance-4',  43.4350, -80.5050, 'available', 'ambulance'),  -- South Kitchener
    ('ambulance-5',  43.4290, -80.5150, 'available', 'ambulance'),  -- Homer Watson Blvd
    ('ambulance-6',  43.4450, -80.5200, 'available', 'ambulance'),  -- Westmount
    ('ambulance-7',  43.4380, -80.5300, 'available', 'ambulance'),  -- Doon area
    ('ambulance-8',  43.4550, -80.4750, 'available', 'ambulance'),  -- East Kitchener / Fairview
    ('ambulance-9',  43.4600, -80.5100, 'available', 'ambulance'),  -- Kitchener-Waterloo border
    ('ambulance-10', 43.4320, -80.4700, 'available', 'ambulance'),  -- Pioneer Park
    ('ambulance-11', 43.4200, -80.4850, 'available', 'ambulance'),  -- Huron Park
    ('ambulance-12', 43.4150, -80.5000, 'available', 'ambulance'),  -- Rosemount
    ('ambulance-13', 43.4470, -80.5400, 'available', 'ambulance'),  -- Forest Heights
    ('ambulance-14', 43.4260, -80.5250, 'available', 'ambulance'),  -- Brigadoon

    -- Waterloo (~8)
    ('ambulance-15', 43.4643, -80.5204, 'available', 'ambulance'),  -- Uptown Waterloo
    ('ambulance-16', 43.4723, -80.5449, 'available', 'ambulance'),  -- University of Waterloo
    ('ambulance-17', 43.4800, -80.5300, 'available', 'ambulance'),  -- North Waterloo / Columbia
    ('ambulance-18', 43.4900, -80.5200, 'available', 'ambulance'),  -- Laurelwood
    ('ambulance-19', 43.4750, -80.5050, 'available', 'ambulance'),  -- Lakeshore
    ('ambulance-20', 43.4850, -80.5500, 'available', 'ambulance'),  -- Beechwood
    ('ambulance-21', 43.4680, -80.5600, 'available', 'ambulance'),  -- Clair Hills
    ('ambulance-22', 43.4950, -80.5400, 'available', 'ambulance'),  -- Northfield

    -- Cambridge (~8)
    ('ambulance-23', 43.3600, -80.3150, 'available', 'ambulance'),  -- Galt downtown
    ('ambulance-24', 43.3785, -80.3290, 'available', 'ambulance'),  -- Cambridge Memorial area
    ('ambulance-25', 43.3950, -80.3450, 'available', 'ambulance'),  -- Preston
    ('ambulance-26', 43.3900, -80.3700, 'available', 'ambulance'),  -- Blair
    ('ambulance-27', 43.4000, -80.3200, 'available', 'ambulance'),  -- Hespeler
    ('ambulance-28', 43.3700, -80.3500, 'available', 'ambulance'),  -- South Cambridge
    ('ambulance-29', 43.3500, -80.3100, 'available', 'ambulance'),  -- South Galt
    ('ambulance-30', 43.3850, -80.3000, 'available', 'ambulance'),  -- East Hespeler

    -- Rural / Townships (~10)
    ('ambulance-31', 43.5950, -80.5500, 'available', 'ambulance'),  -- Elmira
    ('ambulance-32', 43.5350, -80.5550, 'available', 'ambulance'),  -- St. Jacobs
    ('ambulance-33', 43.3780, -80.7250, 'available', 'ambulance'),  -- New Hamburg
    ('ambulance-34', 43.4050, -80.6600, 'available', 'ambulance'),  -- Baden
    ('ambulance-35', 43.2850, -80.4500, 'available', 'ambulance'),  -- Ayr
    ('ambulance-36', 43.4730, -80.4100, 'available', 'ambulance'),  -- Breslau
    ('ambulance-37', 43.5500, -80.4800, 'available', 'ambulance'),  -- Conestogo
    ('ambulance-38', 43.4100, -80.4300, 'available', 'ambulance'),  -- Freeport / Hwy 8
    ('ambulance-39', 43.3300, -80.3600, 'available', 'ambulance'),  -- North Dumfries
    ('ambulance-40', 43.5100, -80.6200, 'available', 'ambulance');  -- Wellesley
