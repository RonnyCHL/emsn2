-- Add vocalization columns to bird_detections
ALTER TABLE bird_detections ADD COLUMN vocalization_type VARCHAR(20);
ALTER TABLE bird_detections ADD COLUMN vocalization_confidence NUMERIC(5,2);

-- Add comments
COMMENT ON COLUMN bird_detections.vocalization_type IS 'Type vocalisatie: song, call, of alarm';
COMMENT ON COLUMN bird_detections.vocalization_confidence IS 'Confidence score van vocalisatie classificatie (0-100)';

-- Create index for faster queries
CREATE INDEX IF NOT EXISTS idx_bird_detections_vocalization ON bird_detections(vocalization_type);

-- Verify
SELECT column_name, data_type FROM information_schema.columns
WHERE table_name = 'bird_detections' AND column_name LIKE 'vocal%';
