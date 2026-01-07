---
name: sync-status
description: Controleer de lifetime sync status tussen BirdNET-Pi SQLite en PostgreSQL. Toont laatste sync tijd, record counts en eventuele problemen.
allowed-tools: Bash, Read
---

# Sync Status Check

## Wanneer Gebruiken

- Controleren of sync correct werkt
- Na problemen met detecties
- Voor data verificatie

## Quick Status

### Laatste Sync Runs

```bash
# Zolder laatste sync
ssh ronny@192.168.1.178 'journalctl -u lifetime-sync.service -n 20 --no-pager'

# Berging laatste sync
ssh ronny@192.168.1.87 'journalctl -u lifetime-sync.service -n 20 --no-pager'
```

### Timer Status

```bash
# Wanneer draait de volgende sync?
ssh ronny@192.168.1.178 'systemctl list-timers lifetime-sync.timer --no-pager'
ssh ronny@192.168.1.87 'systemctl list-timers lifetime-sync.timer --no-pager'
```

## Record Counts Vergelijken

### SQLite (Bron)

```bash
# Zolder BirdNET-Pi database
ssh ronny@192.168.1.178 'sqlite3 /home/ronny/BirdNET-Pi/scripts/birds.db "SELECT COUNT(*) FROM detections"'

# Berging BirdNET-Pi database
ssh ronny@192.168.1.87 'sqlite3 /home/ronny/BirdNET-Pi/scripts/birds.db "SELECT COUNT(*) FROM detections"'
```

### PostgreSQL (Doel)

```bash
# Totaal per station
PGPASSWORD=$(grep PG_PASSWORD /home/ronny/emsn2/.secrets | cut -d= -f2) \
psql -h 192.168.1.25 -p 5433 -U emsn -d emsn -c "
SELECT station, COUNT(*) as total,
       COUNT(*) FILTER (WHERE deleted = false) as active,
       MAX(detected_at) as laatste
FROM lifetime_detections
GROUP BY station
ORDER BY station;
"
```

## Sync Discrepanties Opsporen

```bash
# Detecties van vandaag vergelijken
PGPASSWORD=$(grep PG_PASSWORD /home/ronny/emsn2/.secrets | cut -d= -f2) \
psql -h 192.168.1.25 -p 5433 -U emsn -d emsn -c "
SELECT station,
       COUNT(*) as pg_count,
       MIN(detected_at)::date as datum
FROM lifetime_detections
WHERE detected_at >= CURRENT_DATE
  AND deleted = false
GROUP BY station, detected_at::date;
"
```

## Handmatige Sync Triggeren

```bash
# Force sync op specifieke Pi
ssh ronny@192.168.1.178 'sudo systemctl start lifetime-sync.service'
ssh ronny@192.168.1.87 'sudo systemctl start lifetime-sync.service'
```

## Sync Script Locatie

- **Actief script:** `/home/ronny/sync/lifetime_sync.py` (op elke Pi)
- **Nieuwste versie:** `/home/ronny/emsn2/scripts/sync/lifetime_sync.py`

## Bekende Sync Logica

De sync matcht op **datum+tijd**, niet alleen file_name, omdat:
- BirdNET-Pi WebUI wijzigt file_name bij soortcorrectie
- Oud: `Grasmus-91-2025-12-28-birdnet-07:03:27.mp3`
- Nieuw: `Roodborst-91-2025-12-28-birdnet-07:03:27.mp3`

Dit wordt correct afgehandeld als UPDATE, niet als DELETE+INSERT.
