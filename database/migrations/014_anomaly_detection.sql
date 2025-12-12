-- EMSN 2.0 - Anomaly Detection System
-- Migration 014: Anomaly detection tables

-- ============================================================================
-- Table: anomalies
-- ============================================================================
-- Stores all detected anomalies with severity levels and resolution tracking

CREATE TABLE IF NOT EXISTS anomalies (
    id              SERIAL PRIMARY KEY,
    timestamp       TIMESTAMPTZ DEFAULT NOW(),
    anomaly_type    VARCHAR(50) NOT NULL,
    severity        VARCHAR(20) NOT NULL,
    station_id      VARCHAR(20),            -- 'zolder', 'berging', 'meteo', 'dual', NULL for system-wide
    species         VARCHAR(100),           -- NULL for hardware/data anomalies
    description     TEXT NOT NULL,
    metric_value    FLOAT,                  -- Actual measured value
    threshold_value FLOAT,                  -- Expected threshold
    resolved_at     TIMESTAMPTZ,            -- NULL = still active
    notified        BOOLEAN DEFAULT FALSE,  -- Has alert been sent?
    metadata        JSONB,                  -- Extra context (e.g. weather conditions)

    CONSTRAINT valid_severity CHECK (
        severity IN ('info', 'warning', 'critical', 'special', 'milestone')
    ),

    CONSTRAINT valid_anomaly_type CHECK (
        anomaly_type IN (
            -- Hardware
            'silence_daytime', 'silence_total', 'low_confidence_cluster',
            'meteo_silence', 'meteo_sensor_failure',
            -- Data gaps
            'sync_lag', 'sync_failure', 'station_imbalance', 'database_growth_stalled',
            -- Species
            'unexpected_species', 'seasonal_deviation', 'disappeared_species',
            -- Weather correlation
            'activity_high_wind', 'silence_ideal_weather',
            -- Positive events (kept for completeness, but mainly in ulanzi_bridge)
            'first_of_year', 'detection_milestone', 'species_milestone'
        )
    )
);

-- Indexes for performance
CREATE INDEX idx_anomalies_type_time ON anomalies(anomaly_type, timestamp DESC);
CREATE INDEX idx_anomalies_severity ON anomalies(severity, timestamp DESC);
CREATE INDEX idx_anomalies_station ON anomalies(station_id, timestamp DESC);
CREATE INDEX idx_anomalies_unresolved ON anomalies(resolved_at) WHERE resolved_at IS NULL;
CREATE INDEX idx_anomalies_species ON anomalies(species) WHERE species IS NOT NULL;

-- ============================================================================
-- Table: species_baselines
-- ============================================================================
-- Learned baselines for each species based on historical data

CREATE TABLE IF NOT EXISTS species_baselines (
    id                  SERIAL PRIMARY KEY,
    species_nl          VARCHAR(100) NOT NULL UNIQUE,
    species_sci         VARCHAR(100),
    months_active       INTEGER[],              -- Array like [3,4,5,6,7,8] for summer bird
    hours_active        INTEGER[],              -- Array like [5,6,7,8,18,19,20] for dawn/dusk
    avg_confidence      FLOAT,
    avg_daily_count     FLOAT,                  -- Average detections per day
    detection_count     INTEGER,                -- Total detections used for baseline
    first_seen          DATE,
    last_seen           DATE,
    last_updated        TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT valid_months CHECK (
        months_active <@ ARRAY[1,2,3,4,5,6,7,8,9,10,11,12]
    ),
    CONSTRAINT valid_hours CHECK (
        hours_active <@ ARRAY[0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23]
    )
);

CREATE INDEX idx_baselines_species ON species_baselines(species_nl);
CREATE INDEX idx_baselines_updated ON species_baselines(last_updated DESC);

-- ============================================================================
-- Table: anomaly_check_log
-- ============================================================================
-- Track when each anomaly checker ran (for debugging/monitoring)

CREATE TABLE IF NOT EXISTS anomaly_check_log (
    id              SERIAL PRIMARY KEY,
    check_timestamp TIMESTAMPTZ DEFAULT NOW(),
    check_type      VARCHAR(50) NOT NULL,
    anomalies_found INTEGER DEFAULT 0,
    duration_ms     INTEGER,
    error_message   TEXT
);

CREATE INDEX idx_check_log_type_time ON anomaly_check_log(check_type, check_timestamp DESC);

-- ============================================================================
-- View: active_anomalies
-- ============================================================================
-- Quick view of currently active (unresolved) anomalies

CREATE OR REPLACE VIEW active_anomalies AS
SELECT
    id,
    timestamp,
    anomaly_type,
    severity,
    station_id,
    species,
    description,
    metric_value,
    threshold_value,
    notified,
    NOW() - timestamp as age
FROM anomalies
WHERE resolved_at IS NULL
ORDER BY
    CASE severity
        WHEN 'critical' THEN 1
        WHEN 'warning' THEN 2
        WHEN 'info' THEN 3
        WHEN 'special' THEN 4
        WHEN 'milestone' THEN 5
    END,
    timestamp DESC;

-- ============================================================================
-- View: anomaly_summary_24h
-- ============================================================================
-- Summary of anomalies in last 24 hours for dashboard

CREATE OR REPLACE VIEW anomaly_summary_24h AS
SELECT
    anomaly_type,
    severity,
    station_id,
    COUNT(*) as count,
    MAX(timestamp) as last_occurrence,
    SUM(CASE WHEN resolved_at IS NULL THEN 1 ELSE 0 END) as active_count
FROM anomalies
WHERE timestamp > NOW() - INTERVAL '24 hours'
GROUP BY anomaly_type, severity, station_id
ORDER BY
    CASE severity
        WHEN 'critical' THEN 1
        WHEN 'warning' THEN 2
        WHEN 'info' THEN 3
    END,
    count DESC;

-- ============================================================================
-- Function: auto_resolve_anomalies
-- ============================================================================
-- Automatically resolve certain anomaly types when conditions return to normal

CREATE OR REPLACE FUNCTION auto_resolve_old_anomalies()
RETURNS INTEGER AS $$
DECLARE
    resolved_count INTEGER := 0;
    rows_affected INTEGER;
BEGIN
    -- Auto-resolve silence anomalies older than 12 hours (station likely recovered)
    UPDATE anomalies
    SET resolved_at = NOW()
    WHERE resolved_at IS NULL
      AND anomaly_type IN ('silence_daytime', 'silence_total', 'meteo_silence')
      AND timestamp < NOW() - INTERVAL '12 hours';

    GET DIAGNOSTICS rows_affected = ROW_COUNT;
    resolved_count := rows_affected;

    -- Auto-resolve sync lag if newer than 1 hour (likely temporary)
    UPDATE anomalies
    SET resolved_at = NOW()
    WHERE resolved_at IS NULL
      AND anomaly_type = 'sync_lag'
      AND timestamp < NOW() - INTERVAL '1 hour';

    GET DIAGNOSTICS rows_affected = ROW_COUNT;
    resolved_count := resolved_count + rows_affected;

    RETURN resolved_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Grants
-- ============================================================================

GRANT SELECT, INSERT, UPDATE ON anomalies TO birdpi_zolder;
GRANT SELECT, INSERT, UPDATE ON species_baselines TO birdpi_zolder;
GRANT SELECT, INSERT ON anomaly_check_log TO birdpi_zolder;
GRANT SELECT ON active_anomalies TO birdpi_zolder;
GRANT SELECT ON anomaly_summary_24h TO birdpi_zolder;
GRANT USAGE ON SEQUENCE anomalies_id_seq TO birdpi_zolder;
GRANT USAGE ON SEQUENCE species_baselines_id_seq TO birdpi_zolder;
GRANT USAGE ON SEQUENCE anomaly_check_log_id_seq TO birdpi_zolder;

-- Done!
