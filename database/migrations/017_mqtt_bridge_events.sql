-- Migration 017: MQTT Bridge Events Monitoring
-- Tracks bridge connection events for monitoring and alerting

-- Bridge events tabel
CREATE TABLE IF NOT EXISTS mqtt_bridge_events (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    bridge_name VARCHAR(50) NOT NULL,      -- 'berging-to-zolder', 'zolder-to-berging'
    event_type VARCHAR(20) NOT NULL,        -- 'connected', 'disconnected', 'error', 'restart'
    source VARCHAR(20) DEFAULT 'monitor',   -- 'monitor', 'failover', 'manual'
    message TEXT,
    duration_seconds INTEGER                -- Duration of previous state (for disconnects)
);

-- Index voor snelle queries
CREATE INDEX IF NOT EXISTS idx_mqtt_bridge_events_timestamp ON mqtt_bridge_events(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_mqtt_bridge_events_bridge ON mqtt_bridge_events(bridge_name, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_mqtt_bridge_events_type ON mqtt_bridge_events(event_type);

-- MQTT message stats per uur (voor performance)
CREATE TABLE IF NOT EXISTS mqtt_hourly_stats (
    id SERIAL PRIMARY KEY,
    hour_timestamp TIMESTAMPTZ NOT NULL,    -- Afgerond op heel uur
    station VARCHAR(20) NOT NULL,
    messages_total INTEGER DEFAULT 0,
    messages_shown INTEGER DEFAULT 0,
    messages_skipped INTEGER DEFAULT 0,
    skip_cooldown INTEGER DEFAULT 0,
    skip_antispam INTEGER DEFAULT 0,
    skip_burst INTEGER DEFAULT 0,
    skip_failed INTEGER DEFAULT 0,
    avg_confidence FLOAT,
    UNIQUE(hour_timestamp, station)
);

CREATE INDEX IF NOT EXISTS idx_mqtt_hourly_stats_time ON mqtt_hourly_stats(hour_timestamp DESC);

-- View voor bridge uptime berekening
CREATE OR REPLACE VIEW mqtt_bridge_uptime AS
WITH events_with_next AS (
    SELECT 
        id,
        timestamp,
        bridge_name,
        event_type,
        LEAD(timestamp) OVER (PARTITION BY bridge_name ORDER BY timestamp) as next_event,
        LEAD(event_type) OVER (PARTITION BY bridge_name ORDER BY timestamp) as next_event_type
    FROM mqtt_bridge_events
),
uptime_periods AS (
    SELECT 
        bridge_name,
        timestamp as period_start,
        COALESCE(next_event, NOW()) as period_end,
        event_type,
        EXTRACT(EPOCH FROM (COALESCE(next_event, NOW()) - timestamp)) as duration_seconds
    FROM events_with_next
)
SELECT 
    bridge_name,
    DATE_TRUNC('day', period_start) as day,
    SUM(CASE WHEN event_type = 'connected' THEN duration_seconds ELSE 0 END) as uptime_seconds,
    SUM(CASE WHEN event_type = 'disconnected' THEN duration_seconds ELSE 0 END) as downtime_seconds,
    ROUND(
        SUM(CASE WHEN event_type = 'connected' THEN duration_seconds ELSE 0 END) * 100.0 / 
        NULLIF(SUM(duration_seconds), 0), 2
    ) as uptime_percentage
FROM uptime_periods
WHERE period_start >= NOW() - INTERVAL '30 days'
GROUP BY bridge_name, DATE_TRUNC('day', period_start)
ORDER BY day DESC, bridge_name;

-- Functie om hourly stats te updaten
CREATE OR REPLACE FUNCTION update_mqtt_hourly_stats()
RETURNS void AS $$
DECLARE
    current_hour TIMESTAMPTZ;
BEGIN
    current_hour := DATE_TRUNC('hour', NOW());
    
    -- Update stats voor het huidige uur
    INSERT INTO mqtt_hourly_stats (
        hour_timestamp, station, messages_total, messages_shown, messages_skipped,
        skip_cooldown, skip_antispam, skip_burst, skip_failed, avg_confidence
    )
    SELECT 
        DATE_TRUNC('hour', timestamp) as hour_timestamp,
        station,
        COUNT(*) as messages_total,
        SUM(CASE WHEN was_shown THEN 1 ELSE 0 END) as messages_shown,
        SUM(CASE WHEN NOT was_shown THEN 1 ELSE 0 END) as messages_skipped,
        SUM(CASE WHEN skip_reason = 'cooldown' THEN 1 ELSE 0 END) as skip_cooldown,
        SUM(CASE WHEN skip_reason = 'anti_spam' THEN 1 ELSE 0 END) as skip_antispam,
        SUM(CASE WHEN skip_reason LIKE '%burst%' THEN 1 ELSE 0 END) as skip_burst,
        SUM(CASE WHEN skip_reason = 'send_failed' THEN 1 ELSE 0 END) as skip_failed,
        ROUND(AVG(confidence)::numeric, 4) as avg_confidence
    FROM ulanzi_notification_log
    WHERE timestamp >= current_hour - INTERVAL '1 hour'
      AND timestamp < current_hour + INTERVAL '1 hour'
    GROUP BY DATE_TRUNC('hour', timestamp), station
    ON CONFLICT (hour_timestamp, station) 
    DO UPDATE SET
        messages_total = EXCLUDED.messages_total,
        messages_shown = EXCLUDED.messages_shown,
        messages_skipped = EXCLUDED.messages_skipped,
        skip_cooldown = EXCLUDED.skip_cooldown,
        skip_antispam = EXCLUDED.skip_antispam,
        skip_burst = EXCLUDED.skip_burst,
        skip_failed = EXCLUDED.skip_failed,
        avg_confidence = EXCLUDED.avg_confidence;
END;
$$ LANGUAGE plpgsql;

COMMENT ON TABLE mqtt_bridge_events IS 'MQTT bridge connection events for monitoring';
COMMENT ON TABLE mqtt_hourly_stats IS 'Aggregated MQTT message stats per hour per station';
COMMENT ON VIEW mqtt_bridge_uptime IS 'Calculated bridge uptime percentages per day';
