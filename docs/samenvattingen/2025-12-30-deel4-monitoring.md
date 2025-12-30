# Sessie Samenvatting - 30 december 2025 (deel 4)

## Onderwerp
Wekelijks systeemrapport, log cleanup en Grafana alerts

## Overzicht
Implementatie van proactieve monitoring en automatische cleanup om systeemgezondheid te waarborgen.

## Nieuwe Functionaliteiten

### 1. Weekly System Report
Wekelijks automatisch rapport met volledige systeemcheck, verzonden per email.

**Controles per station:**
- Disk usage (/, /mnt/usb)
- Memory en swap
- Failed systemd services
- Log file sizes
- Uptime

**Database controles:**
- Connectie status
- Idle in transaction
- Tabel groottes
- Dead tuples (VACUUM nodig?)
- Detectie statistieken

**Email:**
- Verzonden naar: rapporten@ronnyhullegie.nl
- Subject bevat status (✅ OK of ⚠️ ISSUES)
- Markdown rapport als bijlage

**Bestanden:**
- `scripts/maintenance/weekly_system_report.py`
- `systemd/weekly-system-report.service`
- `systemd/weekly-system-report.timer` (zondag 08:00)

### 2. Automated Log Cleanup
Dagelijkse cleanup van oude log bestanden die niet door logrotate worden beheerd.

**Wat wordt opgeruimd:**
- Genummerde rotaties (.log.1, .log.2, etc.) ouder dan 14 dagen
- Gedateerde logs (.log-YYYYMMDD) ouder dan 14 dagen
- Gecomprimeerde logs (.gz) ouder dan 14 dagen

**Waarschuwingen:**
- Logs groter dan 50MB worden gerapporteerd

**Bestanden:**
- `scripts/maintenance/log_cleanup.py`
- `systemd/log-cleanup.service`
- `systemd/log-cleanup.timer` (dagelijks 04:00)

**Geïnstalleerd op:** Zolder en Berging

### 3. Grafana Alerts (System Health)
Nieuwe alerts toegevoegd voor proactieve monitoring.

| Alert | Threshold | Severity |
|-------|-----------|----------|
| Disk Usage Kritiek | >85% | Critical |
| Memory Usage Hoog | >90% | Warning |
| Database Idle Transactions | ≥3 connecties >5min | Warning |

**Bestaande MQTT alerts:**
- MQTT Success Rate Laag (<80%)
- MQTT Bridge Disconnected
- MQTT Send Failures Hoog (≥5)
- Geen MQTT Berichten (2 uur)

**Totaal:** 7 alerts actief

## Log Cleanup Resultaten

### Zolder
- Verwijderd: 33 oude log files (24.5 MB)
- Extra: Grote lifetime_sync/ulanzi logs verwijderd
- Resultaat: 306MB → 55MB

### Berging
- Verwijderd: 20 oude log files (29.4 MB)
- Resultaat: 21.4 MB

## Database Index Review

**Conclusie:** 9MB aan ongebruikte secundaire indexes, maar:
- Primary keys zijn nodig voor inserts/updates
- 9MB is verwaarloosbaar vs totale DB grootte
- Geen actie nodig

**Meest gebruikte indexes:**
1. bird_detections_pkey: 36M scans
2. idx_bird_species: 25M scans
3. idx_archive_detection_id: 11M scans

## Timer Overzicht

```
weekly-system-report.timer  Sun 08:00
log-cleanup.timer           *-*-* 04:00
```

## Bestanden Toegevoegd
- `scripts/maintenance/weekly_system_report.py`
- `scripts/maintenance/log_cleanup.py`
- `systemd/weekly-system-report.service`
- `systemd/weekly-system-report.timer`
- `systemd/log-cleanup.service`
- `systemd/log-cleanup.timer`

## Test Resultaten

### Weekly Report
```
2025-12-30 11:35:48 - Report email sent to rapporten@ronnyhullegie.nl
```

### Log Cleanup
```
Zolder: Deleted 33 old log files (24.5 MB)
Berging: Deleted 20 old log files (29.4 MB)
```

## Verificatie Commando's
```bash
# Check timers
systemctl list-timers | grep -E "(weekly|log-cleanup)"

# Check Grafana alerts
curl -s -u admin:emsn2024 "http://192.168.1.25:3000/api/v1/provisioning/alert-rules" | python3 -m json.tool

# Handmatig weekly report draaien
/home/ronny/emsn2/venv/bin/python3 /home/ronny/emsn2/scripts/maintenance/weekly_system_report.py

# Handmatig log cleanup draaien
/home/ronny/emsn2/venv/bin/python3 /home/ronny/emsn2/scripts/maintenance/log_cleanup.py
```
