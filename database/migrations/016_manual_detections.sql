-- Migration 016: Voeg kolommen toe voor handmatige vogelwaarnemingen
-- Datum: 2025-12-17
-- Beschrijving: Ondersteuning voor handmatig ingevoerde detecties via Home Assistant
--
-- Voer uit als postgres user op de NAS:
-- PGPASSWORD='<postgres_wachtwoord>' psql -h localhost -p 5433 -U postgres -d emsn -f 016_manual_detections.sql

-- Voeg source kolom toe (birdnet of manual)
ALTER TABLE bird_detections
ADD COLUMN IF NOT EXISTS source VARCHAR(20) DEFAULT 'birdnet';

-- Voeg signal_quality kolom toe voor handmatige entries
ALTER TABLE bird_detections
ADD COLUMN IF NOT EXISTS signal_quality VARCHAR(20);

-- Voeg notes kolom toe voor opmerkingen
ALTER TABLE bird_detections
ADD COLUMN IF NOT EXISTS notes TEXT;

-- Voeg commentaar toe
COMMENT ON COLUMN bird_detections.source IS 'Bron van detectie: birdnet of manual';
COMMENT ON COLUMN bird_detections.signal_quality IS 'Geluidskwaliteit bij handmatige invoer: duidelijk, zwak, ver_weg';
COMMENT ON COLUMN bird_detections.notes IS 'Handmatige opmerkingen bij de waarneming';

-- Index voor filteren op source
CREATE INDEX IF NOT EXISTS idx_bird_detections_source ON bird_detections(source);

-- Grant rechten aan birdpi_zolder user
GRANT SELECT, INSERT, UPDATE ON bird_detections TO birdpi_zolder;

-- Bevestig migratie
SELECT 'Migration 016 completed: manual_detections columns added' AS status;
