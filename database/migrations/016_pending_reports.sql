-- Migration 016: Pending Reports Table
-- For the report review workflow: generate → review → approve → send

-- Table for pending reports waiting for review
CREATE TABLE IF NOT EXISTS pending_reports (
    id SERIAL PRIMARY KEY,

    -- Report identification
    report_type VARCHAR(50) NOT NULL,  -- 'weekly', 'monthly', 'seasonal', 'yearly'
    report_filename VARCHAR(255) NOT NULL,
    report_title VARCHAR(255),

    -- File paths
    markdown_path TEXT NOT NULL,
    pdf_path TEXT,

    -- Status tracking
    status VARCHAR(20) DEFAULT 'pending',  -- 'pending', 'approved', 'rejected', 'expired', 'sent'

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,  -- Auto-approve after this time (optional)
    reviewed_at TIMESTAMPTZ,
    sent_at TIMESTAMPTZ,

    -- Review data
    reviewer_notes TEXT,  -- Notes added by reviewer
    custom_text TEXT,     -- Custom text to be added to report
    custom_text_position VARCHAR(20) DEFAULT 'after_intro',  -- 'before_intro', 'after_intro', 'before_conclusion', 'after_conclusion'

    -- Notification tracking
    notification_sent BOOLEAN DEFAULT FALSE,
    notification_sent_at TIMESTAMPTZ,

    -- Metadata
    report_data JSONB,  -- Store report stats, highlights, etc.

    CONSTRAINT valid_status CHECK (status IN ('pending', 'approved', 'rejected', 'expired', 'sent'))
);

-- Index for quick lookups
CREATE INDEX IF NOT EXISTS idx_pending_reports_status ON pending_reports(status);
CREATE INDEX IF NOT EXISTS idx_pending_reports_created ON pending_reports(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_pending_reports_type ON pending_reports(report_type);

-- View for pending reports needing review
CREATE OR REPLACE VIEW pending_reports_active AS
SELECT
    id,
    report_type,
    report_title,
    report_filename,
    markdown_path,
    pdf_path,
    status,
    created_at,
    expires_at,
    CASE
        WHEN expires_at IS NOT NULL THEN
            EXTRACT(EPOCH FROM (expires_at - NOW())) / 3600
        ELSE NULL
    END as hours_until_expiry,
    notification_sent,
    custom_text IS NOT NULL as has_custom_text
FROM pending_reports
WHERE status = 'pending'
ORDER BY created_at DESC;

-- Grant permissions
GRANT ALL PRIVILEGES ON pending_reports TO birdpi_zolder;
GRANT USAGE, SELECT ON SEQUENCE pending_reports_id_seq TO birdpi_zolder;
GRANT SELECT ON pending_reports_active TO birdpi_zolder;

-- Add comment
COMMENT ON TABLE pending_reports IS 'Reports waiting for review before sending. Part of the report review workflow.';
