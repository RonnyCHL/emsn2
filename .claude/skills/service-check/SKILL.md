---
name: service-check
description: Voer een gezondheidscontrole uit op alle EMSN systemen - Zolder, Berging, Meteo, NAS, AtmosBird, Nestkast cameras. Gebruik wanneer de gebruiker vraagt om health check, systeem check, gezondheidscontrole, of diagnose.
allowed-tools: Bash, Read
---

# EMSN2 Gezondheidscontrole

## Wanneer Gebruiken

Gebruik deze skill wanneer Ronny vraagt om:
- "gezondheidscontrole"
- "health check"
- "systeem check"
- "check alles"
- "diagnose"
- "hoe staat het systeem ervoor"

## Het Commando

```bash
python3 /home/ronny/emsn2/scripts/monitoring/deep_health_check.py
```

## Wat Het Controleert (15 Categorieën)

### 1. Netwerk Bereikbaarheid
- Ping naar alle 6 apparaten (Zolder, Berging, Meteo, NAS, Ulanzi, Router)
- Latency metingen
- SSH beschikbaarheid

### 2. Services & Timers
**Zolder:** birdnet-mqtt-publisher, mqtt-bridge-monitor, mosquitto, reports-api, ulanzi-bridge, lifetime-sync.timer, nestbox-screenshot.timer

**Berging:** birdnet-mqtt-publisher, mosquitto, lifetime-sync.timer, atmosbird-*.timers

**Meteo:** weather-publisher.timer

### 3. Hardware Metrics (per Pi)
- CPU temperatuur en throttling status
- CPU/Memory/Swap usage
- Disk usage (root, USB)
- Uptime

### 4. NAS & Opslag
- NAS mount status (docker, reports, archive)
- PostgreSQL database connectiviteit
- Disk space op alle locaties

### 5. API Endpoints
- MQTT broker connectiviteit
- Reports API, Screenshot Server
- Grafana, go2rtc, Homer
- BirdNET-Pi web interfaces
- Ulanzi AWTRIX

### 6. Nestkast Cameras
- go2rtc stream status (voor, midden, achter)
- Producer status controle

### 7. AtmosBird (Hemelmonitoring)
- Pi Camera NoIR status
- Lokale captures op USB (berging)
- NAS archief captures (vandaag en totaal)
- Sky observations database
- ISS passes en timelapses

### 8. Weerstation (Meteo)
- Weather data frequentie
- Huidige meteo waarden (temp, humidity, pressure)
- Data gaps detectie

### 9. Data Kwaliteit & Sync
- Laatste detecties per station
- Sync status (SQLite → PostgreSQL)
- Detection gaps detectie

### 10. Logs & Errors
- Recente errors in journalctl (laatste uur)
- Error count per host

### 11. BirdNET-Pi Database Integriteit
- SQLite database PRAGMA integrity_check
- Database grootte en record count
- Audio file count vandaag vs gisteren
- Microfoon functioneert check

### 12. MQTT Bridge Status
- Bridge monitor service status
- Berging ↔ Zolder connectie status
- Message throughput op beide brokers

### 13. Internet & Connectiviteit
- DNS resolution test (google.com)
- Internet bereikbaarheid (ping 8.8.8.8)
- NAS mount response tijd

### 14. Security Checks
- Failed SSH login attempts (laatste 24u)
- Sudo usage logging
- Per host security audit

### 15. Backup & Trends
- PostgreSQL backup status en leeftijd
- Detectie trends (vandaag vs gisteren vs gemiddelde)
- Disk groei voorspelling (dagen tot vol)
- Vocalization model beschikbaarheid
- Ulanzi display status

## Output Interpretatie

| Symbool | Betekenis |
|---------|-----------|
| ✓ (groen) | Check geslaagd |
| ⚠ (geel) | Waarschuwing (let op) |
| ✗ (rood) | Kritiek (actie vereist) |

## Thresholds

| Metric | Warning | Critical |
|--------|---------|----------|
| Disk usage | 80% | 90% |
| Memory usage | 85% | 95% |
| CPU temp | 70°C | 80°C |
| Latency | 50ms | 200ms |
| Detection gap | 2 uur | 6 uur |
| Sync lag | 1 uur | 3 uur |
| AtmosBird captures | <50/dag | 0/dag |
| Backup leeftijd | 48 uur | 7 dagen |
| Failed SSH logins | 10 | 50 |
| NAS response | 1000ms | - |

## Snelle Check (Alternatief)

Voor een snellere, minder uitgebreide check:
```bash
/home/ronny/emsn2/scripts/monitoring/health_check.sh
```
