# EMSN 2.0 - Systeem Handboek

**Ecologisch Monitoring Systeem Nijverdal - Biodiversity Monitoring**

**Versie:** 1.0
**Datum:** 04 januari 2026
**Auteur:** Ronny Hullegie / Claude Code

---

## Inhoudsopgave

1. [Systeem Overzicht](#1-systeem-overzicht)
2. [Hardware Architectuur](#2-hardware-architectuur)
3. [Software Componenten](#3-software-componenten)
4. [Services & Timers](#4-services--timers)
5. [Database Schema](#5-database-schema)
6. [MQTT Infrastructuur](#6-mqtt-infrastructuur)
7. [Rapporten Systeem](#7-rapporten-systeem)
8. [Monitoring & Alerting](#8-monitoring--alerting)
9. [Onderhoud & Troubleshooting](#9-onderhoud--troubleshooting)
10. [Gevonden Problemen & Oplossingen](#10-gevonden-problemen--oplossingen)
11. [Optimalisatie Aanbevelingen](#11-optimalisatie-aanbevelingen)
12. [Appendix](#12-appendix)

---

## 1. Systeem Overzicht

### 1.1 Projectdoel

EMSN 2.0 is een biodiversiteitsmonitoringssysteem dat vogelgeluiden detecteert en analyseert met behulp van BirdNET-Pi op twee locaties in Nijverdal. Het systeem combineert:

- **Audio-analyse** via BirdNET-Pi (machine learning vogelherkenning)
- **Camera-observaties** via AtmosBird (luchtfoto's en timelapses)
- **Weerdata** integratie
- **Migratie-radar** correlatie via FlySafe
- **AI-gegenereerde rapporten** via Claude API

### 1.2 Huidige Status (december 2025)

| Component | Status | Details |
|-----------|--------|---------|
| Zolder Pi | ✅ Online | 4 dagen uptime, primaire node |
| Berging Pi | ✅ Online | N/A dagen uptime, secundaire node |
| NAS Database | ✅ Online | 427 MB, 111,100 detecties |
| MQTT Broker | ✅ Active | Bidirectionele bridge actief |
| Rapporten | ⚠️ Gefixd | Monthly report SQL bug verholpen |
| Ulanzi Display | ✅ Active | LED matrix notificaties |

### 1.3 Statistieken

- **Totaal vogeldetecties:** 111,100
- **Unieke soorten:** 126 (in referentietabel)
- **Dual detections:** 23,348 (beide stations)
- **Weerdata metingen:** 56,059
- **System health records:** 115,517

---

## 2. Hardware Architectuur

### 2.1 Netwerk Topologie

```
                    Internet
                        │
                   [Router]
                        │
        ┌───────────────┼───────────────┐
        │               │               │
   ┌────┴────┐    ┌────┴────┐    ┌────┴────┐
   │ Zolder  │◄──►│   NAS   │◄──►│ Berging │
   │   Pi    │    │DS224Plus│    │   Pi    │
   └────┬────┘    └────┬────┘    └────┬────┘
        │              │               │
   [Microfoon]    [PostgreSQL]   [Microfoon]
        │              │          [Camera]
   [Ulanzi]       [Grafana]
```

### 2.2 Hardware Specificaties

#### Pi Zolder (Primair)
| Eigenschap | Waarde |
|------------|--------|
| **Hostname** | emsn2-zolder |
| **IP** | 192.168.1.178 |
| **Model** | Raspberry Pi 5 |
| **OS** | Debian 13 (trixie) |
| **Kernel** | 6.12.47+rpt-rpi-2712 |
| **Opslag** | 235GB SD + 29GB USB |
| **Rol** | BirdNET-Pi, MQTT Broker, API Server |

#### Pi Berging (Secundair)
| Eigenschap | Waarde |
|------------|--------|
| **Hostname** | emsn2-berging |
| **IP** | 192.168.1.87 |
| **Model** | Raspberry Pi 4 |
| **OS** | Debian (bookworm-based) |
| **Kernel** | 6.12.47+rpt-rpi-v8 |
| **Opslag** | 235GB SD + 29GB USB |
| **Rol** | BirdNET-Pi, AtmosBird, MQTT Bridge |

#### NAS (Synology DS224Plus)
| Eigenschap | Waarde |
|------------|--------|
| **Hostname** | DS224Plus |
| **IP** | 192.168.1.25 |
| **Opslag** | 3.5TB beschikbaar |
| **Services** | PostgreSQL (5433), Grafana (3000), Homer (8181) |
| **Shares** | docker, emsn-AIRapporten |

#### Ulanzi TC001
| Eigenschap | Waarde |
|------------|--------|
| **IP** | 192.168.1.11 |
| **Firmware** | AWTRIX Light |
| **Display** | 32x8 pixel LED matrix |
| **Integratie** | MQTT notificaties |

### 2.3 Mounts & Opslag

**Zolder Pi:**
```
/                    235G (8% gebruikt)
/mnt/usb             29G  (1% gebruikt)
/mnt/nas-reports     3.5T (1% gebruikt) - NAS share
/mnt/nas-docker      3.5T (1% gebruikt) - NAS share
```

**Berging Pi:**
```
/                    235G (12% gebruikt)
/mnt/usb             29G  (6% gebruikt)
```

---

## 3. Software Componenten

### 3.1 Repository Structuur

```
/home/ronny/emsn2/
├── config/              # Configuratiebestanden
│   ├── email.yaml       # Email configuratie
│   ├── mosquitto-*.conf # MQTT configuratie
│   └── ulanzi_config.py # Ulanzi instellingen
├── docs/                # Documentatie
│   └── samenvattingen/  # Sessie samenvattingen
├── scripts/             # Python scripts
│   ├── anomaly/         # Anomalie detectie
│   ├── atmosbird/       # Camera scripts
│   ├── flysafe/         # Migratie radar
│   ├── mqtt/            # MQTT scripts
│   ├── reports/         # Rapport generators
│   ├── sync/            # Data synchronisatie
│   └── ulanzi/          # Display scripts
├── systemd/             # Service bestanden
└── venv/                # Python virtual environment
```

### 3.2 Python Scripts Overzicht

#### Anomaly Detection (`scripts/anomaly/`)
| Script | Beschrijving | Timer |
|--------|--------------|-------|
| `baseline_learner.py` | Leert species baselines voor anomalie detectie | Wekelijks |
| `data_gap_checker.py` | Detecteert hiaten in data flow | 15 min |
| `hardware_checker.py` | Monitort hardware anomalieën | 15 min |

#### AtmosBird (`scripts/atmosbird/`)
| Script | Beschrijving | Timer |
|--------|--------------|-------|
| `atmosbird_capture.py` | Maakt luchtfoto's met Pi Camera NoIR | 10 min |
| `atmosbird_analysis.py` | Analyseert ISS, maan, sterren, meteoren | 15 min |
| `atmosbird_timelapse.py` | Genereert dagelijkse timelapses | Dagelijks |

#### FlySafe (`scripts/flysafe/`)
| Script | Beschrijving | Timer |
|--------|--------------|-------|
| `flysafe_scraper.py` | Scrapt vogeltrekradar data | 2x dag |
| `radar_correlation.py` | Correleert radar met detecties | - |
| `migration_alerts.py` | Stuurt alerts bij piekmigratie | - |
| `seasonal_analysis.py` | Seizoensanalyse van trek | - |

#### MQTT (`scripts/mqtt/`)
| Script | Beschrijving | Service |
|--------|--------------|---------|
| `birdnet_mqtt_publisher.py` | Publiceert detecties naar MQTT | Continu |
| `bridge_monitor.py` | Monitort MQTT bridge status | Continu |
| `mqtt_failover.py` | Failover bij bridge problemen | 5 min |

#### Reports (`scripts/reports/`)
| Script | Beschrijving | Timer |
|--------|--------------|-------|
| `weekly_report.py` | Wekelijks AI rapport | Maandag 07:00 |
| `monthly_report.py` | Maandelijks AI rapport | 1e van maand |
| `seasonal_report.py` | Seizoensrapport | Kwartaal |
| `yearly_report.py` | Jaaroverzicht | 2 januari |
| `species_report.py` | Soort-specifiek rapport | On-demand |
| `comparison_report.py` | Vergelijkingsrapport | On-demand |

#### Sync (`scripts/sync/`)
| Script | Beschrijving | Timer |
|--------|--------------|-------|
| `lifetime_sync.py` | Synct BirdNET → PostgreSQL | 5 min |
| `dual_detection_sync.py` | Detecteert dual detections | 5 min |
| `weather_sync.py` | Synct weerdata | Timer |
| `hardware_monitor.py` | Hardware metrics → DB | 1 min |

#### Ulanzi (`scripts/ulanzi/`)
| Script | Beschrijving | Service |
|--------|--------------|---------|
| `ulanzi_bridge.py` | MQTT → Ulanzi notificaties | Continu |
| `ulanzi_screenshot.py` | Maakt screenshots van display | Continu |
| `screenshot_server.py` | HTTP server voor screenshots | Continu |
| `cooldown_display.py` | Publiceert cooldown naar MQTT | Continu |
| `rarity_cache_refresh.py` | Ververst zeldzaamheids cache | Dagelijks |
| `screenshot_cleanup.py` | Verwijdert oude screenshots | Dagelijks |

### 3.3 Geinstalleerde Python Packages

```
anthropic          0.75.0    # Claude AI API
Flask              3.1.2     # Web API
flask-cors         6.0.1     # CORS support
matplotlib         3.10.8    # Grafieken
numpy              2.3.5     # Numeriek
paho-mqtt          2.1.0     # MQTT client
pillow             12.0.0    # Afbeeldingen
psycopg2-binary    2.9.11    # PostgreSQL
pydantic           2.12.5    # Data validatie
PyYAML             6.0.3     # YAML parsing
requests           2.32.5    # HTTP client
```

---

## 4. Services & Timers

### 4.1 Zolder Services

#### Continu Draaiende Services
| Service | Status | Beschrijving |
|---------|--------|--------------|
| `birdnet-mqtt-publisher` | ✅ Active | Publiceert detecties naar MQTT |
| `mqtt-bridge-monitor` | ✅ Active | Monitort bridge health |
| `mqtt-cooldown-publisher` | ✅ Active | Cooldown status naar MQTT |
| `emsn-cooldown-display` | ✅ Active | Cooldown naar Home Assistant |
| `ulanzi-bridge` | ✅ Active | MQTT → Ulanzi display |
| `ulanzi-screenshot` | ✅ Active | Maakt screenshots |
| `ulanzi-screenshot-server` | ✅ Active | HTTP server screenshots |
| `emsn-reports-api` | ✅ Active | Web API (port 8081) |
| `hardware-metrics` | ✅ Active | Hardware monitoring |
| `mosquitto` | ✅ Active | MQTT broker |

#### BirdNET-Pi Services
| Service | Status | Beschrijving |
|---------|--------|--------------|
| `birdnet_analysis` | ✅ Active | Audio analyse |
| `birdnet_recording` | ✅ Active | Audio opname |
| `birdnet_log` | ✅ Active | Logging |
| `birdnet_stats` | ✅ Active | Statistieken |

### 4.2 Zolder Timers

| Timer | Interval | Volgende run |
|-------|----------|--------------|
| `hardware-monitor.timer` | 1 min | +1 min |
| `lifetime-sync.timer` | 5 min | +5 min |
| `dual-detection.timer` | 5 min | +5 min |
| `emsn-dbmirror-zolder.timer` | 5 min | +5 min |
| `mqtt-failover.timer` | 5 min | +5 min |
| `anomaly-datagap-check.timer` | 15 min | +15 min |
| `anomaly-hardware-check.timer` | 15 min | +15 min |
| `flysafe-radar-day.timer` | 06:00 | Morgen |
| `flysafe-radar-night.timer` | 22:00 | Vanavond |
| `screenshot-cleanup.timer` | 03:00 | Morgen |
| `rarity-cache.timer` | 04:00 | Morgen |
| `backup-cleanup.timer` | 04:04 | Zondag |
| `anomaly-baseline-learn.timer` | Zondag 03:00 | Zondag |
| `emsn-weekly-report.timer` | Maandag 07:00 | Maandag |
| `emsn-monthly-report.timer` | 1e van maand 08:00 | 1 januari |
| `emsn-yearly-report.timer` | 2 januari 08:00 | 2 januari |
| `emsn-seasonal-report-*.timer` | Per seizoen | Maart/Juni/Sept/Dec |

### 4.3 Berging Services

| Service | Status | Beschrijving |
|---------|--------|--------------|
| `birdnet-mqtt-publisher` | ✅ Active | Detecties naar MQTT |
| `birdnet_analysis` | ✅ Active | Audio analyse |
| `birdnet_recording` | ✅ Active | Audio opname |
| `birdnet_stats` | ✅ Active | Statistieken |
| `mosquitto` | ✅ Active | MQTT bridge |
| `lifetime-sync` | Via timer | Sync naar PostgreSQL |
| `hardware-monitor` | Via timer | Hardware metrics |

### 4.4 Berging Timers

| Timer | Interval | Beschrijving |
|-------|----------|--------------|
| `atmosbird-capture.timer` | 10 min | Luchtfoto's |
| `atmosbird-analysis.timer` | 15 min | ISS/maan analyse |
| `atmosbird-timelapse.timer` | 00:30 | Dagelijkse timelapse |
| `emsn-dbmirror-berging.timer` | 5 min | Database mirror |

---

## 5. Database Schema

### 5.1 Belangrijkste Tabellen

#### bird_detections (103 MB, 53.293 rows)
Primaire tabel voor vogeldetecties.

| Kolom | Type | Beschrijving |
|-------|------|--------------|
| id | BIGINT | Primary key |
| station | VARCHAR(50) | 'zolder' of 'berging' |
| detection_timestamp | TIMESTAMP | Detectie tijdstip |
| date | DATE | Detectie datum |
| time | TIME | Detectie tijd |
| species | VARCHAR(150) | Wetenschappelijke naam |
| common_name | VARCHAR(150) | Nederlandse naam |
| confidence | NUMERIC(5,4) | 0.0000-1.0000 |
| latitude/longitude | NUMERIC | GPS coördinaten |
| cutoff | NUMERIC(5,4) | BirdNET cutoff |
| week | INTEGER | Weeknummer |
| sensitivity | NUMERIC(5,4) | BirdNET sensitivity |
| overlap | NUMERIC(5,4) | Audio overlap |
| file_name | VARCHAR(255) | Audio bestand |
| detected_by_zolder | BOOLEAN | Gedetecteerd op zolder |
| detected_by_berging | BOOLEAN | Gedetecteerd in berging |
| dual_detection | BOOLEAN | Op beide stations |
| time_diff_seconds | INTEGER | Verschil in seconden |
| rarity_score | INTEGER | Zeldzaamheid (0-100) |
| rarity_tier | VARCHAR(20) | Tier classificatie |
| added_to_db | TIMESTAMP | Toegevoegd aan DB |

#### system_health (8 MB, 37.706 rows)
Hardware en systeem metrics.

| Kolom | Type | Beschrijving |
|-------|------|--------------|
| station | VARCHAR(50) | Station ID |
| measurement_timestamp | TIMESTAMP | Meetmoment |
| cpu_usage | NUMERIC(5,2) | CPU % |
| cpu_temp | NUMERIC(4,1) | Temperatuur °C |
| memory_usage | NUMERIC(5,2) | RAM % |
| disk_usage | NUMERIC(5,2) | Disk % |
| network_latency_ms | INTEGER | Netwerk latency |
| birdnet_status | VARCHAR(20) | BirdNET status |
| mqtt_status | VARCHAR(20) | MQTT status |
| overall_health_score | INTEGER | Score 0-100 |

#### weather_data (7 MB, 29.983 rows)
Weerstation metingen.

#### dual_detections (3 MB, 7.473 rows)
Vogels gedetecteerd op beide stations.

#### species_reference (148 rows)
Referentietabel met alle soorten.

### 5.2 Views

| View | Beschrijving |
|------|--------------|
| `recent_activity` | Laatste 100 detecties |
| `daily_statistics` | Dagelijkse statistieken |
| `station_comparison` | Vergelijking stations |
| `active_anomalies` | Actieve anomalieën |
| `anomaly_summary_24h` | Anomalie samenvatting |
| `bird_weather_correlation` | Weer-vogel correlatie |

### 5.3 Database Grootte

| Tabel | Grootte | Rijen |
|-------|---------|-------|
| bird_detections | 103 MB | 53.293 |
| system_health | 8 MB | 37.706 |
| weather_data | 7 MB | 29.983 |
| dual_detections | 3 MB | 7.473 |
| ulanzi_notification_log | 2 MB | 9.512 |
| performance_metrics | 1 MB | 10.290 |
| **Totaal** | **N/A** | - |

---

## 6. MQTT Infrastructuur

### 6.1 Broker Configuratie

**Zolder (Primary Broker):**
- Host: 192.168.1.178:1883
- Credentials: ecomonitor / REDACTED_DB_PASS
- Bridge naar Berging: Bidirectioneel

**Berging (Bridge):**
- Host: 192.168.1.87:1883
- Connected to: Zolder broker
- Mode: Bidirectioneel

### 6.2 Topic Structuur

```
emsn2/
├── zolder/
│   ├── detection         # Live detecties
│   ├── stats             # Statistieken
│   └── health            # System health
├── berging/
│   ├── detection
│   ├── stats
│   └── health
├── bridge/
│   └── status            # Bridge status
└── ulanzi/
    ├── cooldown          # Cooldown status
    └── notification      # Notificaties

birdnet/
├── zolder/
│   ├── detection         # BirdNET detecties
│   └── stats
└── berging/
    ├── detection
    └── stats
```

### 6.3 Message Formaat

**Detectie bericht:**
```json
{
  "station": "zolder",
  "timestamp": "2025-12-16T18:30:00",
  "species": "Turdus merula",
  "common_name": "Merel",
  "confidence": 0.89,
  "rarity_score": 15,
  "file_name": "2025-12-16-birdnet-18:30:00.wav"
}
```

---

## 7. Rapporten Systeem

### 7.1 Rapport Types

| Type | Frequentie | Timer | Output |
|------|------------|-------|--------|
| Weekly | Maandag 07:00 | `emsn-weekly-report.timer` | MD + PDF |
| Monthly | 1e dag 08:00 | `emsn-monthly-report.timer` | MD |
| Seasonal | Per seizoen | 4 timers | MD |
| Yearly | 2 januari | `emsn-yearly-report.timer` | MD |
| Species | On-demand | - | MD |
| Comparison | On-demand | - | MD |

### 7.2 Rapport Locaties

- **Lokaal:** `/home/ronny/emsn2/reports/`
- **NAS:** `/mnt/nas-reports/`
- **Web:** http://192.168.1.178:8081

### 7.3 Claude AI Integratie

Alle rapporten worden gegenereerd met Claude API:
- Model: claude-3-haiku of claude-3-sonnet
- Stijlen: formeel, casual, wetenschappelijk, familie
- Taal: Nederlands

### 7.4 Email Configuratie

```yaml
smtp:
  server: smtp.strato.de
  port: 587
  username: rapporten@ronnyhullegie.nl
  password: REDACTED_SMTP_PASS
```

---

## 8. Monitoring & Alerting

### 8.1 Grafana Dashboards

URL: http://192.168.1.25:3000

| Dashboard | Beschrijving |
|-----------|--------------|
| EMSN Overview | Hoofddashboard |
| Bird Detections | Detecties over tijd |
| System Health | Hardware metrics |
| Ulanzi Notifications | Display statistieken |
| AtmosBird | Camera data |

### 8.2 Anomalie Detectie

Het systeem detecteert automatisch:
- **Data gaps:** Geen detecties > 1 uur
- **Hardware issues:** CPU > 80%, Temp > 70°C
- **Species anomalies:** Onverwachte soorten/tijden
- **Network issues:** Latency > 100ms

### 8.3 Alerting Kanalen

1. **MQTT:** Real-time alerts naar subscribers
2. **Ulanzi:** LED display notificaties
3. **Grafana:** Dashboard alerts
4. **Email:** Wekelijkse rapporten

---

## 9. Onderhoud & Troubleshooting

### 9.1 Dagelijks Onderhoud

```bash
# Check service status
systemctl status birdnet-mqtt-publisher
systemctl status mqtt-bridge-monitor
systemctl --failed

# Check logs
tail -f /mnt/usb/logs/birdnet_mqtt_zolder.log
journalctl -u emsn-weekly-report -f

# Check database connectie
PGPASSWORD='REDACTED_DB_PASS' psql -h 192.168.1.25 -p 5433 -U birdpi_zolder -d emsn -c "SELECT COUNT(*) FROM bird_detections;"
```

### 9.2 Wekelijks Onderhoud

```bash
# Disk usage check
df -h
du -sh /mnt/usb/logs/*

# Log rotatie check
ls -la /mnt/usb/logs/*.log | head -10

# Git sync (beide Pi's)
cd /home/ronny/emsn2 && git pull

# Python venv update
/home/ronny/emsn2/venv/bin/pip list --outdated
```

### 9.3 Troubleshooting Commando's

```bash
# Service herstart
sudo systemctl restart birdnet-mqtt-publisher

# Timer status
systemctl list-timers --all | grep emsn

# MQTT test
mosquitto_sub -h 192.168.1.178 -u ecomonitor -P REDACTED_DB_PASS -t "birdnet/#" -v

# SSH naar Berging
ssh ronny@192.168.1.87

# Database query
PGPASSWORD='REDACTED_DB_PASS' psql -h 192.168.1.25 -p 5433 -U birdpi_zolder -d emsn
```

### 9.4 Backup & Recovery

#### SD Kaart Backup Systeem (Nieuw december 2025)

Complete disaster recovery oplossing voor beide Pi's met streaming naar NAS.

**Backup Schema:**

| Type | Frequentie | Tijd | Retentie | Grootte |
|------|------------|------|----------|---------|
| **Wekelijkse Image** | Zondag | 03:00 | 7 dagen | ~40GB/Pi (gecomprimeerd) |
| **Dagelijkse Rsync** | Dagelijks | 02:00 | 7 dagen | ~100MB/dag (incrementeel) |
| **Database Dump** | Elk uur | :15 | 7 dagen | ~12MB/uur |
| **Cleanup** | Dagelijks | 02:30 | - | Verwijdert oude backups |

**Backup Locaties (NAS 8TB USB):**
```
/mnt/nas-birdnet-archive/sd-backups/
├── zolder/
│   ├── images/      # Wekelijkse .img.gz bestanden
│   ├── daily/       # Dagelijkse rsync snapshots
│   ├── database/    # Uurlijkse database dumps
│   └── config/      # Configuratie bestanden
├── berging/
│   └── (zelfde structuur)
└── recovery/
    └── HANDLEIDING-SD-KAART-RECOVERY.md
```

**Scripts:** `/home/ronny/emsn2/scripts/backup/`
- `sd_backup_daily.py` - Rsync incrementele backup
- `sd_backup_weekly.py` - Streaming image backup (dd | pigz → NAS)
- `sd_backup_database.py` - SQLite database dump
- `sd_backup_cleanup.py` - Retentie management

**Logs:** `/var/log/emsn-backup/`

**Recovery tijd:** ~15 minuten met Raspberry Pi Imager

**Crash Recovery Hardening:**
- NAS mounts met `nofail` optie (boot niet geblokkeerd)
- SQLite WAL mode (write-ahead logging)
- Hardware watchdog (bcm2835_wdt) - herstart bij hang

#### Recovery Procedure

**Bij SD kaart crash:**
1. Download nieuwste `.img.gz` van NAS (`images/` map)
2. Schrijf naar nieuwe SD met Raspberry Pi Imager (Use Custom)
3. Boot Pi - netwerk/SSH werkt direct
4. Herstel database van laatste dump:
   ```bash
   LATEST=$(ls -t /mnt/nas-birdnet-archive/sd-backups/zolder/database/*.sql.gz | head -1)
   zcat "$LATEST" | sqlite3 /home/ronny/BirdNET-Pi/scripts/birds.db
   ```
5. Herstart BirdNET service

**Volledige handleiding:** `/mnt/nas-birdnet-archive/sd-backups/recovery/HANDLEIDING-SD-KAART-RECOVERY.md`

#### Andere Backups

- Database mirror naar PostgreSQL: 5 min (beide stations)
- Git repository: Handmatig pushen

---

## 10. Gevonden Problemen & Oplossingen

### 10.1 Kritieke Problemen (Opgelost)

#### Monthly Report SQL Bug
**Probleem:** `GROUP BY week` in plaats van `GROUP BY EXTRACT(WEEK FROM detection_timestamp)`

**Oplossing:** SQL query aangepast in `monthly_report.py`

```python
# Voor:
GROUP BY week

# Na:
GROUP BY EXTRACT(WEEK FROM detection_timestamp)
```

#### Missing subprocess Import
**Probleem:** `subprocess` module niet geïmporteerd in `monthly_report.py`

**Oplossing:** Import toegevoegd

### 10.2 Waarschuwingen

#### Grote Log Bestanden
**Probleem:** `birdnet-mqtt-publisher.error.log` is 35MB

**Aanbeveling:**
- Implementeer log rotatie
- Check waarom er zoveel errors zijn
- Voeg logrotate config toe

#### Berging Git Status
**Probleem:** 7 uncommitted bestanden op Berging

**Aanbeveling:**
- Sync git repository naar Zolder
- Of commit lokale wijzigingen

#### Lege Database Tabellen
**Probleem:** Meerdere tabellen zijn leeg (meteor_detections, iss_passes, etc.)

**Aanbeveling:**
- Check of AtmosBird correct werkt
- Verifieer ISS/meteor detectie logica

---

## 11. Optimalisatie Aanbevelingen

### 11.1 Hoge Prioriteit

1. **Log Rotatie Implementeren**
   - Configureer logrotate voor alle EMSN logs
   - Max 7 dagen of 10MB per log

2. **Monthly Report Timer Resetten**
   ```bash
   sudo systemctl reset-failed emsn-monthly-report.service
   ```

3. **Git Repository Synchroniseren**
   ```bash
   # Op Berging
   cd /home/ronny/emsn2
   git stash
   git pull
   git stash pop
   ```

### 11.2 Medium Prioriteit

1. **Database Indexen**
   - Voeg index toe op `detection_timestamp` als deze er niet is
   - Analyseer slow queries

2. **Service Monitoring**
   - Implementeer healthcheck endpoint
   - Voeg Prometheus metrics toe

3. **Backup Strategie**
   - Automatische PostgreSQL backups naar NAS
   - Git auto-push na wijzigingen

### 11.3 Lage Prioriteit

1. **AtmosBird Verbeteren**
   - Meteor detectie activeren
   - ISS pass notifications

2. **Dashboard Uitbreiden**
   - Real-time kaart view
   - Species trends over tijd

3. **Mobile App**
   - Push notificaties voor zeldzame vogels
   - Quick stats view

---

## 12. Appendix

### 12.1 Belangrijke URLs

| Service | URL | Beschrijving |
|---------|-----|--------------|
| Reports API | http://192.168.1.178:8081 | Rapporten web interface |
| Grafana | http://192.168.1.25:3000 | Dashboards |
| Homer | http://192.168.1.25:8181 | Start pagina |
| BirdNET Zolder | http://192.168.1.178 | BirdNET-Pi interface |
| BirdNET Berging | http://192.168.1.87 | BirdNET-Pi interface |
| Screenshot Server | http://192.168.1.178:8082 | Ulanzi screenshots |

### 12.2 Credentials

| Service | Username | Password |
|---------|----------|----------|
| PostgreSQL | birdpi_zolder | REDACTED_DB_PASS |
| MQTT | ecomonitor | REDACTED_DB_PASS |
| Grafana | admin | emsn2024 |
| NAS Shares | ronny | REDACTED_DB_PASS |
| SMTP | rapporten@ronnyhullegie.nl | REDACTED_SMTP_PASS |

### 12.3 SSH Toegang

```bash
# Zolder (lokaal of vanaf Berging)
ssh ronny@192.168.1.178

# Berging
ssh ronny@192.168.1.87
```

### 12.4 Belangrijke Paden

```
Zolder:
/home/ronny/emsn2/           # Project root
/home/ronny/BirdNET-Pi/      # BirdNET installatie
/mnt/usb/logs/               # Log bestanden
/mnt/nas-reports/            # NAS reports share
/etc/systemd/system/         # Systemd units

Database:
PostgreSQL: 192.168.1.25:5433
Database: emsn
```

### 12.5 Contact & Support

- **Project eigenaar:** Ronny Hullegie
- **GitHub:** https://github.com/[repo]
- **Email:** rapporten@ronnyhullegie.nl

---

*Dit handboek is gegenereerd op 16 december 2025*
*EMSN 2.0 - EcoMonitoring Systeem Nijverdal*
