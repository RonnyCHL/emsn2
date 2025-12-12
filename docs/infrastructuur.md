# EMSN Infrastructuur

## Netwerk Overzicht

| Apparaat | IP | Functie |
|----------|-----|---------|
| Synology NAS | 192.168.1.25 | Database, Grafana, Homer, Web |
| EMSN2-Zolder (Pi) | 192.168.1.178 | Hoofdstation BirdNET-Pi |
| EMSN2-Berging (Pi) | 192.168.1.87 | Tweede station BirdNET-Pi |
| Ulanzi TC001 | 192.168.1.11 | LED Matrix Display |
| Davis WeatherLink | Online | Weerstation |

## Services op NAS (192.168.1.25)

| Service | Poort | Beschrijving |
|---------|-------|--------------|
| Homer | 8080 | Dashboard homepage |
| Grafana | 3000 | Data visualisatie |
| PostgreSQL | 5433 | Database |
| pgAdmin | 5050 | Database beheer |
| Nginx | 80 | Webserver (rapporten) |

## Database

- **Host:** 192.168.1.25
- **Port:** 5433
- **Database:** emsn
- **User:** birdpi_zolder
- **Password:** REDACTED_DB_PASS

### Belangrijke Tabellen

| Tabel | Beschrijving |
|-------|--------------|
| `bird_detections` | BirdNET detecties |
| `weather_data` | Davis weerstation data |
| `radar_observations` | FlySafe radar data |

### Verbinden

```bash
# Via psql
PGPASSWORD='REDACTED_DB_PASS' psql -h 192.168.1.25 -p 5433 -U birdpi_zolder -d emsn

# In Python
import psycopg2
conn = psycopg2.connect(
    host='192.168.1.25',
    port=5433,
    database='emsn',
    user='birdpi_zolder',
    password='REDACTED_DB_PASS'
)
```

## Raspberry Pi (Zolder - 192.168.1.178)

### Belangrijke Directories

```
/home/ronny/emsn2/           # Hoofdproject
├── scripts/                  # Python scripts
│   ├── flysafe/             # FlySafe radar scripts
│   └── ...
├── grafana/                  # Dashboard JSON bestanden
├── docs/                     # Documentatie
└── venv/                     # Python virtual environment

/mnt/usb/                     # USB opslag
├── logs/                     # Alle logbestanden
└── radar_images/             # Opgeslagen radar images
```

### Systemd Services

```bash
# FlySafe scraper (elk uur)
systemctl status flysafe-scraper.timer

# Database mirror
systemctl status emsn-dbmirror-zolder.timer

# Alle timers bekijken
systemctl list-timers
```

### Python Environment

```bash
# Activeer venv
source /home/ronny/emsn2/venv/bin/activate

# Of direct met venv python
/home/ronny/emsn2/venv/bin/python3 script.py

# Met environment variabelen
EMSN_DB_PASSWORD='REDACTED_DB_PASS' /home/ronny/emsn2/venv/bin/python3 script.py
```

## Ulanzi TC001 (192.168.1.11)

AWTRIX Light LED Matrix display.

### API Endpoints

```bash
# Notificatie sturen
curl -X POST http://192.168.1.11/api/notify \
  -H "Content-Type: application/json" \
  -d '{"text": "Test", "color": "#FF0000", "duration": 10}'

# Custom app
curl -X POST http://192.168.1.11/api/custom?name=bird \
  -H "Content-Type: application/json" \
  -d '{"text": "Vogeltrek!", "icon": "bird"}'
```

### Documentatie
https://blueforcer.github.io/awtrix-light/

## Weerstation

Davis weerstation data wordt automatisch naar de database gestuurd.

### Online Dashboard
https://www.weatherlink.com/bulletin/fb45f7a2-d3af-4227-b867-9481c2ae44fe

### Database Kolommen (weather_data)

```
temp_outdoor, temp_indoor
humidity_outdoor, humidity_indoor
wind_speed, wind_direction, wind_gust_speed
barometer
rain_rate, rain_day, rain_month
solar_radiation, uv_index
soil_temp_1, soil_temp_2
soil_moisture_1, soil_moisture_2
leaf_wetness_1, leaf_wetness_2
```

## Rapporten

AI-gegenereerde rapporten beschikbaar op:
http://192.168.1.25/rapporten/

Locatie op NAS: `/volume1/web/rapporten/`
