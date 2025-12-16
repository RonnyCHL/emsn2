-- Migration 015: Timer Timeline Table
-- Creates table for storing systemd timer information for Grafana visualization
-- Run as postgres user: psql -U postgres -d emsn -f 015_timer_timeline.sql

-- Create the timer_timeline table
CREATE TABLE IF NOT EXISTS timer_timeline (
    id SERIAL PRIMARY KEY,
    recorded_at TIMESTAMPTZ DEFAULT NOW(),
    timer_name VARCHAR(100) NOT NULL,
    timer_unit VARCHAR(100) NOT NULL,
    service_name VARCHAR(100),
    next_run TIMESTAMPTZ,
    last_run TIMESTAMPTZ,
    time_until_next INTERVAL,
    time_since_last INTERVAL,
    station VARCHAR(20) DEFAULT 'zolder',
    is_emsn_timer BOOLEAN DEFAULT FALSE,
    category VARCHAR(50)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_timer_timeline_recorded ON timer_timeline(recorded_at);
CREATE INDEX IF NOT EXISTS idx_timer_timeline_timer ON timer_timeline(timer_name);
CREATE INDEX IF NOT EXISTS idx_timer_timeline_next_run ON timer_timeline(next_run);
CREATE INDEX IF NOT EXISTS idx_timer_timeline_emsn ON timer_timeline(is_emsn_timer);
CREATE INDEX IF NOT EXISTS idx_timer_timeline_category ON timer_timeline(category);

-- Grant permissions to birdpi users
GRANT ALL PRIVILEGES ON timer_timeline TO birdpi_zolder;
GRANT ALL PRIVILEGES ON timer_timeline TO birdpi_berging;
GRANT USAGE, SELECT ON SEQUENCE timer_timeline_id_seq TO birdpi_zolder;
GRANT USAGE, SELECT ON SEQUENCE timer_timeline_id_seq TO birdpi_berging;

-- Create a view for Grafana that shows the timeline
CREATE OR REPLACE VIEW timer_timeline_current AS
WITH latest AS (
    SELECT station, MAX(recorded_at) as max_recorded
    FROM timer_timeline
    GROUP BY station
)
SELECT
    t.timer_name,
    t.service_name,
    t.next_run,
    t.last_run,
    t.category,
    t.station,
    t.is_emsn_timer,
    CASE
        WHEN t.next_run > NOW() THEN 'upcoming'
        WHEN t.next_run <= NOW() AND t.next_run > NOW() - INTERVAL '5 minutes' THEN 'running'
        ELSE 'completed'
    END as status,
    EXTRACT(EPOCH FROM (t.next_run - NOW())) as seconds_until_next,
    EXTRACT(EPOCH FROM (NOW() - t.last_run)) as seconds_since_last
FROM timer_timeline t
INNER JOIN latest l ON t.station = l.station AND t.recorded_at = l.max_recorded
WHERE t.is_emsn_timer = TRUE;

-- Grant view permissions
GRANT SELECT ON timer_timeline_current TO birdpi_zolder;
GRANT SELECT ON timer_timeline_current TO birdpi_berging;

-- Comment
COMMENT ON TABLE timer_timeline IS 'Systemd timer snapshots for Grafana timeline visualization';
COMMENT ON VIEW timer_timeline_current IS 'Current timer status for Grafana dashboard';
