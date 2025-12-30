-- EMSN Migration: Fix media_archive foreign key constraint
-- Datum: 2025-12-30
-- Probleem: Detecties kunnen niet verwijderd worden als ze in media_archive staan
-- Oplossing: ON DELETE SET NULL - archief blijft behouden, detection_id wordt NULL
--
-- Uitvoeren op NAS:
-- sudo docker exec -i emsn-postgres psql -U postgres -d emsn -f /path/to/fix_media_archive_fk.sql
-- Of via pgAdmin/DBeaver als postgres user

BEGIN;

-- Drop oude constraint
ALTER TABLE media_archive
DROP CONSTRAINT IF EXISTS media_archive_detection_id_fkey;

-- Nieuwe constraint met ON DELETE SET NULL
-- Als een detectie verwijderd wordt, blijft het archief bestaan maar detection_id wordt NULL
ALTER TABLE media_archive
ADD CONSTRAINT media_archive_detection_id_fkey
FOREIGN KEY (detection_id)
REFERENCES bird_detections(id)
ON DELETE SET NULL;

COMMIT;

-- Verificatie
SELECT
    tc.constraint_name,
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name,
    rc.delete_rule
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
JOIN information_schema.referential_constraints AS rc
    ON rc.constraint_name = tc.constraint_name
WHERE tc.table_name = 'media_archive'
  AND tc.constraint_type = 'FOREIGN KEY';
