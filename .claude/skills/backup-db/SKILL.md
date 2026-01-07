---
name: backup-db
description: Maak een backup van de PostgreSQL database op de NAS. Gebruik voor scheduled backups of voor grote wijzigingen.
allowed-tools: Bash
---

# Database Backup

## Wanneer Gebruiken

- Voor grote database wijzigingen
- Periodieke backups
- Voor migraties

## Quick Backup

```bash
# Credentials laden
source /home/ronny/emsn2/.secrets

# Backup naar NAS
PGPASSWORD=$PG_PASSWORD pg_dump \
    -h 192.168.1.25 \
    -p 5433 \
    -U emsn \
    -d emsn \
    -F c \
    -f "/mnt/nas-reports/backups/emsn_$(date +%Y%m%d_%H%M%S).dump"
```

## Backup met Compressie

```bash
PGPASSWORD=$PG_PASSWORD pg_dump \
    -h 192.168.1.25 \
    -p 5433 \
    -U emsn \
    -d emsn \
    | gzip > "/mnt/nas-reports/backups/emsn_$(date +%Y%m%d).sql.gz"
```

## Specifieke Tabellen

```bash
# Alleen lifetime_detections
PGPASSWORD=$PG_PASSWORD pg_dump \
    -h 192.168.1.25 \
    -p 5433 \
    -U emsn \
    -d emsn \
    -t lifetime_detections \
    -F c \
    -f "/mnt/nas-reports/backups/lifetime_detections_$(date +%Y%m%d).dump"
```

## Restore

```bash
# Volledige restore (LET OP: overschrijft bestaande data!)
PGPASSWORD=$PG_PASSWORD pg_restore \
    -h 192.168.1.25 \
    -p 5433 \
    -U emsn \
    -d emsn \
    -c \
    "/mnt/nas-reports/backups/emsn_YYYYMMDD.dump"
```

## Backup Locaties

| Type | Locatie |
|------|---------|
| Database dumps | `/mnt/nas-reports/backups/` |
| BirdNET SQLite | `/home/ronny/BirdNET-Pi/scripts/birds.db` |
| Config backups | `/mnt/nas-reports/config-backups/` |

## Automatische Cleanup

Oude backups verwijderen (ouder dan 30 dagen):

```bash
find /mnt/nas-reports/backups/ -name "emsn_*.dump" -mtime +30 -delete
find /mnt/nas-reports/backups/ -name "emsn_*.sql.gz" -mtime +30 -delete
```

## Verificatie

```bash
# Check backup integriteit
pg_restore --list "/mnt/nas-reports/backups/emsn_latest.dump" | head -20

# Check bestandsgrootte
ls -lh /mnt/nas-reports/backups/emsn_*.dump | tail -5
```
