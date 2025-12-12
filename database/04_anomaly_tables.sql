-- EMSN 2.0 - Anomaly Detection Tables
-- Schema for tracking and alerting on system anomalies

-- Table: anomalies
-- Stores all detected anomalies with severity levels
CREATE TABLE IF NOT EXISTS anomalies (
    id                  SERIAL PRIMARY KEY,
    timestamp           TIMESTAMPTZ DEFAULT NOW(),
    anomaly_type        VARCHAR(50) NOT NULL,
    severity            VARCHAR(20) NOT NULL,
    station_id          VARCHAR(20),
    species             VARCHAR(100),
    description         TEXT NOT NULL,
    metric_value        FLOAT,
    threshold_value     FLOAT,
    resolved_at         TIMESTAMPTZ,
    notified            BOOLEAN DEFAULT FALSE,
    metadata            JSONB,

    CONSTRAINT valid_severity CHECK (
        severity IN ('info', 'warning', 'critical', 'special', 'milestone')
    ),
    CONSTRAINT valid_anomaly_type CHECK (
        anomaly_type IN (
            'hardware_silence', 'hardware_low_confidence', 'hardware_audio_clip',
            'datagap_sync_lag', 'datagap_sync_failure', 'datagap_station_imbalance',
            'datagap_missing_records', 'datagap_growth_stopped',
            'species_unexpected', 'species_seasonal_deviation', 'species_disappeared',
            'special_first_of_year', 'special_milestone_detection', 'special_milestone_species',
            'weather_unexpected_activity', 'weather_unexpected_silence',
            'system_disk_space', 'system_temperature', 'system_uptime'
        )
    )
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_anomalies_type_time ON anomalies(anomaly_type, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_anomalies_severity ON anomalies(severity, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_anomalies_unresolved ON anomalies(resolved_at) WHERE resolved_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_anomalies_station ON anomalies(station_id, timestamp DESC) WHERE station_id IS NOT NULL;

-- Table: species_baselines
-- Stores learned "normal" behavior for each species
CREATE TABLE IF NOT EXISTS species_baselines (
    id                      SERIAL PRIMARY KEY,
    species_nl              VARCHAR(100) NOT NULL UNIQUE,
    species_scientific      VARCHAR(100),
    months_active           INTEGER[],              -- [3,4,5,6,7,8] for summer bird
    hours_active            INTEGER[],              -- [5,6,7,8,18,19,20] for morning/evening
    avg_confidence          FLOAT,
    avg_daily_count         FLOAT,
    min_daily_count         FLOAT,
    max_daily_count         FLOAT,
    detection_count         INTEGER,                -- Total used for baseline
    first_seen              TIMESTAMPTZ,
    last_seen               TIMESTAMPTZ,
    last_updated            TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT valid_confidence CHECK (avg_confidence >= 0 AND avg_confidence <= 1),
    CONSTRAINT valid_counts CHECK (detection_count >= 0)
);

-- Index for fast species lookup
CREATE INDEX IF NOT EXISTS idx_baselines_species ON species_baselines(species_nl);
CREATE INDEX IF NOT EXISTS idx_baselines_updated ON species_baselines(last_updated DESC);

-- Table: system_health_log
-- Tracks system health metrics over time
CREATE TABLE IF NOT EXISTS system_health_log (
    id                  SERIAL PRIMARY KEY,
    timestamp           TIMESTAMPTZ DEFAULT NOW(),
    station_id          VARCHAR(20) NOT NULL,
    metric_type         VARCHAR(50) NOT NULL,
    metric_value        FLOAT NOT NULL,
    metadata            JSONB,

    CONSTRAINT valid_metric_type CHECK (
        metric_type IN (
            'cpu_temp', 'disk_usage_percent', 'disk_free_gb',
            'detection_count_1h', 'detection_count_24h',
            'avg_confidence_1h', 'sync_lag_seconds',
            'unique_species_24h'
        )
    )
);

-- Index for health monitoring queries
CREATE INDEX IF NOT EXISTS idx_health_station_time ON system_health_log(station_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_health_metric_time ON system_health_log(metric_type, timestamp DESC);

-- Comments
COMMENT ON TABLE anomalies IS 'Stores all detected anomalies with severity levels and resolution status';
COMMENT ON TABLE species_baselines IS 'Learned normal behavior patterns for each bird species';
COMMENT ON TABLE system_health_log IS 'Time-series data for system health metrics';

COMMENT ON COLUMN anomalies.anomaly_type IS 'Type of anomaly detected (hardware, datagap, species, special, weather, system)';
COMMENT ON COLUMN anomalies.severity IS 'Severity level: info, warning, critical, special, milestone';
COMMENT ON COLUMN anomalies.metadata IS 'Additional context data as JSON (e.g., weather conditions, detection details)';

COMMENT ON COLUMN species_baselines.months_active IS 'Months (1-12) when this species is typically active';
COMMENT ON COLUMN species_baselines.hours_active IS 'Hours (0-23) when this species is typically active';
COMMENT ON COLUMN species_baselines.avg_daily_count IS 'Average number of detections per day';
