---
name: atmosbird-check
description: Controleer AtmosBird hemelmonitoring systeem op Pi Berging. Check captures, analyses, timelapses en NAS sync.
allowed-tools: Bash, Read
---

# AtmosBird Health Check

## Wanneer Gebruiken

- Controleren of sky captures werken
- Troubleshooting timelapse generatie
- Verificatie NAS archivering

## Quick Status

### Alle Timers

```bash
ssh ronny@192.168.1.87 'systemctl list-timers atmosbird-* --no-pager'
```

### Service Status

```bash
ssh ronny@192.168.1.87 'systemctl status atmosbird-capture.timer atmosbird-analysis.timer atmosbird-timelapse.timer atmosbird-archive-sync.timer --no-pager'
```

## Laatste Captures

### Lokale USB Opslag

```bash
# Recente captures (laatste 10)
ssh ronny@192.168.1.87 'ls -lt /mnt/usb/atmosbird/captures/ | head -10'

# Vandaag's captures tellen
ssh ronny@192.168.1.87 'ls /mnt/usb/atmosbird/captures/ | grep "$(date +%Y%m%d)" | wc -l'
```

### NAS Archief

```bash
# Check NAS mount
ssh ronny@192.168.1.87 'df -h /mnt/nas-birdnet-archive'

# Recente archives
ls -lt /mnt/nas-birdnet-archive/atmosbird/captures/ | head -10
```

## Analyse Resultaten

### Database Check

```bash
PGPASSWORD=$(grep PG_PASSWORD /home/ronny/emsn2/.secrets | cut -d= -f2) \
psql -h 192.168.1.25 -p 5433 -U emsn -d emsn -c "
SELECT
    DATE(captured_at) as datum,
    COUNT(*) as captures,
    AVG(brightness)::numeric(5,2) as gem_brightness,
    AVG(cloud_coverage)::numeric(5,2) as gem_clouds
FROM sky_observations
WHERE captured_at >= CURRENT_DATE - INTERVAL '3 days'
GROUP BY DATE(captured_at)
ORDER BY datum DESC;
"
```

### ISS Passes

```bash
PGPASSWORD=$(grep PG_PASSWORD /home/ronny/emsn2/.secrets | cut -d= -f2) \
psql -h 192.168.1.25 -p 5433 -U emsn -d emsn -c "
SELECT pass_time, magnitude, max_elevation, visible
FROM iss_passes
WHERE pass_time >= NOW()
ORDER BY pass_time
LIMIT 5;
"
```

## Timelapse Status

### Recente Timelapses

```bash
# Lokaal gegenereerd
ssh ronny@192.168.1.87 'ls -lt /mnt/usb/atmosbird/timelapses/ | head -5'

# Op NAS
ls -lt /mnt/nas-birdnet-archive/atmosbird/timelapses/ | head -5
```

### Generatie Logs

```bash
ssh ronny@192.168.1.87 'journalctl -u atmosbird-timelapse.service -n 30 --no-pager'
```

## Sync Status

### Archive Sync Logs

```bash
ssh ronny@192.168.1.87 'journalctl -u atmosbird-archive-sync.service -n 20 --no-pager'
```

### Disk Usage

```bash
# Lokale USB (29GB, 7 dagen retentie)
ssh ronny@192.168.1.87 'df -h /mnt/usb && du -sh /mnt/usb/atmosbird/*'

# NAS archief (8TB)
df -h /mnt/nas-birdnet-archive
du -sh /mnt/nas-birdnet-archive/atmosbird/*
```

## Handmatig Triggeren

```bash
# Nieuwe capture forceren
ssh ronny@192.168.1.87 'sudo systemctl start atmosbird-capture.service'

# Analyse forceren
ssh ronny@192.168.1.87 'sudo systemctl start atmosbird-analysis.service'

# Timelapse genereren
ssh ronny@192.168.1.87 'sudo systemctl start atmosbird-timelapse.service'

# Sync naar NAS forceren
ssh ronny@192.168.1.87 'sudo systemctl start atmosbird-archive-sync.service'
```

## Camera Info

- **Model:** Pi Camera NoIR Module 3 (imx708_wide_noir)
- **FOV:** 120° diagonaal
- **Locatie:** Berging (192.168.1.87)
- **Coordinaten:** 52.360179, 6.472626

## Veelvoorkomende Problemen

| Probleem | Check | Oplossing |
|----------|-------|-----------|
| Geen captures | Camera status | `libcamera-hello --list-cameras` |
| NAS niet bereikbaar | Mount status | `mount -a` |
| Timelapse mislukt | FFmpeg logs | Check disk space |
| Analyse errors | Python deps | Check loguru, opencv |
