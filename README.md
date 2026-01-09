# EMSN 2.0

**EcoMonitoring Systeem Nijverdal**

> *"Je beschermt wat je kent"*

Een gedistribueerd biodiversiteitsmonitoring systeem voor real-time detectie en analyse van vogels, weer, en atmosferische condities.

---

## Overzicht

EMSN 2.0 is een netwerk van Raspberry Pi's dat continu de lokale biodiversiteit monitort:

- **Vogeldetectie** via BirdNET-Pi op 2 stations
- **Weermonitoring** via Davis Vantage Pro 2
- **Sky monitoring** via Pi NoIR camera (AtmosBird)
- **Vogeltrek radar** via KNMI FlySafe integratie
- **Real-time notificaties** op Ulanzi TC001 display
- **AI-gegenereerde rapporten** via Claude API
- **Centrale database** op Synology NAS

---

## Stations

| Station | IP | Hardware | Functie |
|---------|-----|----------|---------|
| **emsn2-zolder** | 192.168.1.178 | RPi 5, Steinberg UR22mkII | BirdNET-Pi, Centrale hub |
| **emsn2-berging** | 192.168.1.87 | RPi 4B, Steinberg UR44 | BirdNET-Pi, AtmosBird |
| **emsn2-meteo** | 192.168.1.156 | RPi Zero 2W | Davis Vantage Pro 2 |
| **Synology NAS** | 192.168.1.25 | DS918+ | PostgreSQL, Storage |
| **Ulanzi TC001** | 192.168.1.11 | ESP32 | Real-time display |

---

## Architectuur

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           EMSN 2.0 Network                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐              │
│   │   Zolder    │     │   Berging   │     │    Meteo    │              │
│   │  BirdNET-Pi │     │  BirdNET-Pi │     │ Davis VP2   │              │
│   │  (Central)  │     │  AtmosBird  │     │             │              │
│   └──────┬──────┘     └──────┬──────┘     └──────┬──────┘              │
│          │                   │                   │                      │
│          └───────────────────┼───────────────────┘                      │
│                              │                                          │
│                              ▼                                          │
│                    ┌─────────────────┐                                  │
│                    │   MQTT Broker   │                                  │
│                    │ (192.168.1.178) │                                  │
│                    └────────┬────────┘                                  │
│                             │                                           │
│          ┌──────────────────┼──────────────────┐                       │
│          ▼                  ▼                  ▼                        │
│   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐                  │
│   │ PostgreSQL  │   │   Ulanzi    │   │   Home      │                  │
│   │   (NAS)     │   │   TC001     │   │ Assistant   │                  │
│   │  :5433      │   │             │   │             │                  │
│   └─────────────┘   └─────────────┘   └─────────────┘                  │
│          │                                                              │
│          ▼                                                              │
│   ┌─────────────┐                                                      │
│   │  Grafana    │                                                      │
│   │ Dashboards  │                                                      │
│   └─────────────┘                                                      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Modules

### Sync (`scripts/sync/`)
Synchronisatie tussen lokale SQLite databases en centrale PostgreSQL.

| Script | Functie | Timer |
|--------|---------|-------|
| `lifetime_sync.py` | Detecties → PostgreSQL | 5 min |
| `hardware_monitor.py` | System metrics | 1 min |
| `dual_detection_sync.py` | Match dual-station detecties | 5 min |
| `bayesian_verification.py` | Betrouwbaarheidsberekening | - |

### Ulanzi (`scripts/ulanzi/`)
Real-time notificaties op Ulanzi TC001 display.

| Script | Functie |
|--------|---------|
| `ulanzi_bridge.py` | MQTT → Display notificaties |
| `rarity_cache_refresh.py` | Zeldzaamheid tier berekening |
| `cooldown_display.py` | Anti-spam cooldown status |

**Features:**
- 5-tier zeldzaamheidssysteem (legendary → very common)
- RTTTL melodieën per tier
- Nederlandse vogelnamen
- Anti-spam met configureerbare cooldowns
- Milestone notificaties (nieuwe soorten)

### FlySafe (`scripts/flysafe/`)
KNMI vogeltrek radar integratie.

| Script | Functie |
|--------|---------|
| `flysafe_scraper.py` | Download radar images |
| `color_analyzer.py` | Analyseer migratie intensiteit |
| `radar_correlation.py` | Correleer radar vs BirdNET |
| `migration_alerts.py` | Alerts bij hoge migratie |
| `migration_forecast.py` | Voorspel migratie activiteit |

### AtmosBird (`scripts/atmosbird/`)
24/7 sky monitoring met Pi NoIR camera.

| Script | Functie |
|--------|---------|
| `atmosbird_capture.py` | Foto's elke 10 min |
| `atmosbird_analysis.py` | ISS, maan, meteoor detectie |
| `atmosbird_timelapse.py` | Dagelijkse timelapse video |

### Anomaly Detection (`scripts/anomaly/`)
Automatische detectie van problemen.

| Script | Functie |
|--------|---------|
| `baseline_learner.py` | Leer normale patronen per soort |
| `data_gap_checker.py` | Detecteer sync problemen |
| `hardware_checker.py` | Detecteer hardware issues |

### Reports (`scripts/reports/`)
AI-gegenereerde rapporten via Claude API.

| Script | Functie | Schedule |
|--------|---------|----------|
| `weekly_report.py` | Weekrapport in Markdown | Maandag 07:00 |
| `monthly_report.py` | Maandrapport | 1e van maand |

---

## Projectstructuur

```
emsn2/
├── config/                 # Centrale configuratie
│   ├── station_config.py   # Station autodétectie
│   ├── ulanzi_config.py    # Ulanzi TC001 settings
│   └── dutch_bird_names.json
│
├── scripts/                # Alle Python scripts
│   ├── sync/               # Database synchronisatie
│   ├── ulanzi/             # Display notificaties
│   ├── flysafe/            # Vogeltrek radar
│   ├── atmosbird/          # Sky monitoring
│   ├── anomaly/            # Anomalie detectie
│   └── reports/            # AI rapporten
│
├── systemd/                # Service & timer files
├── utils/                  # Gedeelde utilities
│   ├── db_connection.py    # PostgreSQL connection pool
│   ├── mqtt_publisher.py   # MQTT client
│   └── logger.py           # Unified logging
│
├── database/               # SQL schema & migrations
├── grafana/                # Dashboard JSON exports
├── docs/                   # Documentatie
├── reports/                # Gegenereerde rapporten
└── reports-web/            # Web interface
```

---

## Installatie

### Prerequisites
- Raspberry Pi OS (64-bit)
- Python 3.11+
- PostgreSQL 15+ (op NAS)
- Mosquitto MQTT broker

### Setup
```bash
# Clone repository
git clone https://github.com/emsn/emsn2.git
cd emsn2

# Maak virtual environment
python3 -m venv venv
source venv/bin/activate

# Installeer dependencies
pip install -r requirements.txt

# Kopieer systemd services
sudo cp systemd/*.service systemd/*.timer /etc/systemd/system/
sudo systemctl daemon-reload

# Enable services
sudo systemctl enable --now lifetime-sync.timer
sudo systemctl enable --now ulanzi-bridge.service
```

---

## Configuratie

### Environment Variables
```bash
# Database
export EMSN_DB_HOST=192.168.1.25
export EMSN_DB_PORT=5433
export EMSN_DB_NAME=emsn
export EMSN_DB_USER=birdpi_zolder
export EMSN_DB_PASSWORD=***

# MQTT
export MQTT_BROKER=192.168.1.178
export MQTT_USER=ecomonitor
export MQTT_PASSWORD=***

# AI Reports
export ANTHROPIC_API_KEY=sk-ant-***
```

---

## Grafana Dashboards

| Dashboard | Beschrijving |
|-----------|--------------|
| `emsn_meteo_dashboard.json` | Weer + vogels overzicht |
| `flysafe_radar_dashboard.json` | Vogeltrek radar |
| `atmosbird-dashboard.json` | Sky monitoring |
| `emsn-anomaly-detection.json` | Anomalie alerts |

Import via Grafana UI: Dashboards → Import → Upload JSON

---

## MQTT Topics

| Topic | Beschrijving |
|-------|--------------|
| `emsn2/zolder/detection/new` | Nieuwe detectie zolder |
| `emsn2/berging/detection/new` | Nieuwe detectie berging |
| `emsn2/dual/detection/new` | Dual-station detectie |
| `emsn2/hardware/{station}` | Hardware metrics |
| `emsn2/ulanzi/notify` | Display notificaties |
| `emsn2/presence/home` | Home Assistant presence |
| `weather/meteo/*` | Weerdata |

---

## Database Schema

Belangrijkste tabellen in PostgreSQL:

| Tabel | Beschrijving |
|-------|--------------|
| `bird_detections` | Alle vogeldetecties |
| `weather_data` | Weermetingen |
| `hardware_metrics` | System metrics |
| `radar_observations` | FlySafe radar data |
| `atmosbird_observations` | Sky foto's |
| `species_baselines` | Geleerde patronen |
| `anomaly_alerts` | Gedetecteerde anomalieën |
| `species_rarity_cache` | Zeldzaamheid cache |

---

## Documentatie

| Document | Beschrijving |
|----------|--------------|
| [SERVICES_OVERVIEW.md](docs/SERVICES_OVERVIEW.md) | Alle systemd services |
| [CLEANUP_GUIDE.md](docs/CLEANUP_GUIDE.md) | Opschoon handleiding |
| [EMSN_Workflow.md](docs/EMSN_Workflow.md) | Workflow documentatie |
| [ANOMALY_DETECTION.md](docs/ANOMALY_DETECTION.md) | Anomalie systeem |
| [fase-10-flysafe-radar.md](docs/fase-10-flysafe-radar.md) | FlySafe integratie |

---

## Development Timeline

| Datum | Fase | Beschrijving |
|-------|------|--------------|
| 26 nov 2025 | 1 | Project setup |
| 5-6 dec | 2 | PostgreSQL sync, hardware monitoring |
| 10 dec | - | MQTT v2, bi-directional sync |
| 11 dec | 11 | Ulanzi notificaties, rarity tiers |
| 12 dec | 14 | Anomaly detection |
| 12 dec | - | AtmosBird sky monitoring |
| 12 dec | 13 | AI Reports met Claude |
| 12 dec | 10 | FlySafe radar integratie |

---

## Statistieken

- **~10.500 regels** Python code
- **28 Python scripts**
- **34 systemd service/timer files**
- **10 Grafana dashboards**
- **34 git commits**

---

## Credits

Ontwikkeld door Ronny Hullegie met assistentie van Claude AI.

---

*Een liefdesbrief aan de natuur, geschreven in Python*
