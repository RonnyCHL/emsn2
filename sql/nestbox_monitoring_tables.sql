-- =============================================================================
-- EMSN Nestkast Monitoring - Database Tabellen
-- =============================================================================
-- Tabellen voor broedseizoen tracking, events en media opslag
--
-- Uitvoeren op PostgreSQL (192.168.1.25:5433, database: emsn)
-- =============================================================================

-- Nestkasten definitie
CREATE TABLE IF NOT EXISTS nestboxes (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,        -- 'voor', 'midden', 'achter'
    display_name VARCHAR(100),                -- 'Nestkast Voor', etc.
    location VARCHAR(200),                    -- 'Voortuin', 'Achtertuin'
    camera_stream VARCHAR(200),               -- go2rtc stream naam
    device_id VARCHAR(100),                   -- Tuya device ID
    installed_date DATE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Broedseizoen per nestkast (1 record per broedpoging)
CREATE TABLE IF NOT EXISTS nestbox_seasons (
    id SERIAL PRIMARY KEY,
    nestbox_id INTEGER REFERENCES nestboxes(id),
    year INTEGER NOT NULL,
    species VARCHAR(100),                     -- Vogelsoort (wetenschappelijk)
    species_common VARCHAR(100),              -- Nederlandse naam

    -- Tijdlijn
    first_activity DATE,                      -- Eerste waarneming activiteit
    first_egg_date DATE,                      -- Eerste ei gelegd
    last_egg_date DATE,                       -- Laatste ei gelegd
    first_hatch_date DATE,                    -- Eerste ei uitgekomen
    fledge_date DATE,                         -- Uitvliegdatum
    end_date DATE,                            -- Einde broedpoging

    -- Aantallen
    eggs_count INTEGER DEFAULT 0,             -- Totaal eieren
    hatched_count INTEGER DEFAULT 0,          -- Uitgekomen eieren
    fledged_count INTEGER DEFAULT 0,          -- Succesvol uitgevlogen

    -- Status
    status VARCHAR(30) DEFAULT 'actief',      -- actief/succes/mislukt/verlaten
    failure_reason VARCHAR(100),              -- predatie/weer/verlaten/onbekend

    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(nestbox_id, year, first_activity)
);

-- Gebeurtenissen tijdlijn (elke observatie)
CREATE TABLE IF NOT EXISTS nestbox_events (
    id SERIAL PRIMARY KEY,
    season_id INTEGER REFERENCES nestbox_seasons(id),
    nestbox_id INTEGER REFERENCES nestboxes(id),

    event_type VARCHAR(50) NOT NULL,          -- bezet/ei/uitgekomen/uitgevlogen/mislukt/slapend/activiteit
    event_timestamp TIMESTAMP NOT NULL,

    -- Optionele details
    count INTEGER,                            -- Aantal (eieren, jongen)
    species VARCHAR(100),                     -- Bij eerste detectie

    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Index voor snelle queries
CREATE INDEX IF NOT EXISTS idx_nestbox_events_timestamp ON nestbox_events(event_timestamp);
CREATE INDEX IF NOT EXISTS idx_nestbox_events_type ON nestbox_events(event_type);
CREATE INDEX IF NOT EXISTS idx_nestbox_seasons_year ON nestbox_seasons(year);

-- Media opslag (screenshots en video's)
CREATE TABLE IF NOT EXISTS nestbox_media (
    id SERIAL PRIMARY KEY,
    nestbox_id INTEGER REFERENCES nestboxes(id),
    season_id INTEGER REFERENCES nestbox_seasons(id),  -- NULL voor niet-broedseizoen

    media_type VARCHAR(20) NOT NULL,          -- screenshot/video
    capture_type VARCHAR(30),                 -- auto_morning/auto_night/manual

    file_path VARCHAR(500) NOT NULL,          -- Relatief pad op 8TB schijf
    file_name VARCHAR(200),
    file_size_bytes BIGINT,
    duration_seconds INTEGER,                 -- Voor video's

    captured_at TIMESTAMP NOT NULL,

    -- ML/AI analyse (voor later)
    bird_detected BOOLEAN,                    -- Vogel aanwezig?
    bird_state VARCHAR(30),                   -- slapend/actief/broedend/voerend
    confidence FLOAT,

    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Index voor media queries
CREATE INDEX IF NOT EXISTS idx_nestbox_media_captured ON nestbox_media(captured_at);
CREATE INDEX IF NOT EXISTS idx_nestbox_media_type ON nestbox_media(media_type, capture_type);
CREATE INDEX IF NOT EXISTS idx_nestbox_media_nestbox ON nestbox_media(nestbox_id);

-- Slaap detectie log (voor ML training later)
CREATE TABLE IF NOT EXISTS nestbox_sleep_detections (
    id SERIAL PRIMARY KEY,
    nestbox_id INTEGER REFERENCES nestboxes(id),
    media_id INTEGER REFERENCES nestbox_media(id),

    detected_at TIMESTAMP NOT NULL,
    species VARCHAR(100),
    confidence FLOAT,

    -- Handmatige verificatie
    verified BOOLEAN DEFAULT FALSE,
    verified_correct BOOLEAN,                 -- Was detectie correct?
    verified_at TIMESTAMP,

    created_at TIMESTAMP DEFAULT NOW()
);

-- =============================================================================
-- Insert default nestkasten
-- =============================================================================

INSERT INTO nestboxes (name, display_name, location, camera_stream, device_id) VALUES
    ('voor', 'Nestkast Voor', 'Voortuin', 'nestkast_voor', 'bf80c5603b3392da01oyt1'),
    ('midden', 'Nestkast Midden', 'Zijkant huis', 'nestkast_midden', 'bf5ab17574f859aef9zbg1'),
    ('achter', 'Nestkast Achter', 'Achtertuin', 'nestkast_achter', 'bf0e510111cdf52517rddr')
ON CONFLICT (name) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    camera_stream = EXCLUDED.camera_stream,
    device_id = EXCLUDED.device_id;

-- =============================================================================
-- Views voor Grafana
-- =============================================================================

-- Huidige status per nestkast
CREATE OR REPLACE VIEW v_nestbox_current_status AS
SELECT
    nb.id,
    nb.name,
    nb.display_name,
    nb.location,
    ns.id as season_id,
    ns.species_common as species,
    ns.status,
    ns.eggs_count,
    ns.hatched_count,
    ns.fledged_count,
    (SELECT event_type FROM nestbox_events
     WHERE nestbox_id = nb.id
     ORDER BY event_timestamp DESC LIMIT 1) as last_event,
    (SELECT event_timestamp FROM nestbox_events
     WHERE nestbox_id = nb.id
     ORDER BY event_timestamp DESC LIMIT 1) as last_event_time,
    (SELECT COUNT(*) FROM nestbox_media
     WHERE nestbox_id = nb.id
     AND captured_at >= CURRENT_DATE) as media_today
FROM nestboxes nb
LEFT JOIN nestbox_seasons ns ON ns.nestbox_id = nb.id
    AND ns.year = EXTRACT(YEAR FROM NOW())
    AND ns.status = 'actief';

-- Media overzicht per dag
CREATE OR REPLACE VIEW v_nestbox_media_daily AS
SELECT
    DATE(captured_at) as date,
    nestbox_id,
    nb.display_name as nestbox,
    media_type,
    capture_type,
    COUNT(*) as count,
    SUM(file_size_bytes) as total_bytes
FROM nestbox_media nm
JOIN nestboxes nb ON nb.id = nm.nestbox_id
GROUP BY DATE(captured_at), nestbox_id, nb.display_name, media_type, capture_type
ORDER BY date DESC;

-- Slaap detecties voor analyse
CREATE OR REPLACE VIEW v_nestbox_sleep_analysis AS
SELECT
    DATE(nm.captured_at) as date,
    EXTRACT(HOUR FROM nm.captured_at) as hour,
    nb.display_name as nestbox,
    nm.bird_detected,
    nm.bird_state,
    nm.confidence,
    nm.file_path
FROM nestbox_media nm
JOIN nestboxes nb ON nb.id = nm.nestbox_id
WHERE nm.capture_type LIKE 'auto_night%'
ORDER BY nm.captured_at DESC;

-- =============================================================================
-- Trigger voor updated_at
-- =============================================================================

CREATE OR REPLACE FUNCTION update_modified_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_nestbox_seasons_modtime ON nestbox_seasons;
CREATE TRIGGER update_nestbox_seasons_modtime
    BEFORE UPDATE ON nestbox_seasons
    FOR EACH ROW EXECUTE FUNCTION update_modified_column();
