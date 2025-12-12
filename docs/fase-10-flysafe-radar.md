# Fase 10: FlySafe Radar Integratie

## Overzicht

FlySafe integreert KNMI BirdTAM radar data met BirdNET detecties om vogeltrek te monitoren en voorspellen.

## Componenten

### Scripts (`/home/ronny/emsn2/scripts/flysafe/`)

| Script | Functie |
|--------|---------|
| `flysafe_scraper.py` | Haalt radar images op van KNMI, analyseert kleuren |
| `color_analyzer.py` | Analyseert radar image kleuren naar intensiteit (0-100) |
| `radar_correlation.py` | Correleert radar met BirdNET detecties |
| `migration_alerts.py` | Stuurt alerts naar Ulanzi display |
| `timelapse_generator.py` | Maakt video/GIF van radar images |
| `seasonal_analysis.py` | Analyseert seizoenspatronen |
| `migration_forecast.py` | Voorspelt vogeltrek activiteit |
| `species_correlation.py` | Soort-specifieke radar correlatie |

### Database Tabellen

#### `radar_observations`
```sql
CREATE TABLE radar_observations (
    id SERIAL PRIMARY KEY,
    observation_date DATE NOT NULL,
    observation_time TIME NOT NULL,
    station_id VARCHAR(50),
    station_name VARCHAR(100),
    region VARCHAR(50),
    image_url TEXT,
    local_image_path TEXT,
    intensity_level INTEGER,           -- 0-100
    bird_detections_count INTEGER,     -- Gekoppelde BirdNET detecties
    correlation_score DECIMAL(5,2),    -- Correlatie score
    dominant_colors JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Systemd Timer

```
/etc/systemd/system/flysafe-scraper.service
/etc/systemd/system/flysafe-scraper.timer
```

Draait elk uur om :05.

## Radar Stations

| Station | Regio | Coördinaten |
|---------|-------|-------------|
| Herwijnen | central_netherlands | 51.837, 5.138 |
| Den Helder | north_netherlands | 52.953, 4.790 |

## Kleur Analyse

De radar images gebruiken kleuren om vogeldichtheid aan te geven:

| Kleur | RGB Range | Intensiteit |
|-------|-----------|-------------|
| Donkerblauw | (0,0,100-150) | 10-20 (laag) |
| Lichtblauw | (100-150,150-200,200-255) | 20-40 |
| Groen | (0-100,150-255,0-100) | 40-60 |
| Geel | (200-255,200-255,0-100) | 60-80 |
| Oranje/Rood | (200-255,0-150,0-100) | 80-100 (hoog) |

## Alert Systeem

### Drempels
- **Groen (< 25):** Minimale trek
- **Geel (25-50):** Lichte trek
- **Oranje (50-75):** Matige trek
- **Rood (> 75):** Intensieve trek

### Ulanzi Notificatie
```python
# Alert naar Ulanzi TC001
url = "http://192.168.1.11/api/notify"
payload = {
    "text": f"Vogeltrek: {intensity}%",
    "icon": "bird",
    "color": color_hex,
    "duration": 30
}
```

## Voorspelling Model

`migration_forecast.py` gebruikt gewogen factoren:

| Factor | Gewicht | Bron |
|--------|---------|------|
| Seizoen | 30% | Datum (maart-mei, aug-nov = piek) |
| Weer | 25% | Davis weerstation |
| Historisch | 15% | Radar data laatste 7 dagen |
| Tijd van dag | 15% | Nacht = meer trek |
| Detectie trend | 15% | BirdNET laatste 24 uur |

### Ideale Omstandigheden
- Wind < 8 m/s
- Temperatuur 5-15°C
- Stijgende luchtdruk (> 1020 hPa)
- Geen regen
- Heldere nachten

## Grafana Dashboard

**UID:** `flysafe-radar`
**URL:** http://192.168.1.25:3000/d/flysafe-radar/

### Panels
1. Huidige Radar Status (stat)
2. Radar vs BirdNET Trend (timeseries)
3. Trekvogels Vandaag (stat)
4. Correlatie Score (gauge)
5. Detecties per Uur (barchart)
6. Radar Intensiteit per Uur (barchart)
7. Top Trekvogels (table)
8. Weer Condities (stat panels)

## Bekende Trekvogels

```python
MIGRATORY_SPECIES = [
    'Koperwiek', 'Kramsvogel', 'Zanglijster', 'Grote Lijster',
    'Kolgans', 'Grauwe Gans', 'Brandgans',
    'Keep', 'Vink', 'Sijs', 'Putter',
    'Goudplevier', 'Kievit', 'Wulp',
    'Spreeuw', 'Roek', 'Kauw',
    'Graspieper', 'Boompieper'
]
```

## Commando's

```bash
# Handmatig scrapen
cd /home/ronny/emsn2/scripts/flysafe
python3 flysafe_scraper.py

# Specifiek station
python3 flysafe_scraper.py --stations herwijnen

# Correlatie draaien
python3 radar_correlation.py

# Voorspelling
python3 migration_forecast.py
python3 migration_forecast.py --24h  # Komende 24 uur
python3 migration_forecast.py --json  # JSON output

# Alert test
python3 migration_alerts.py --test 75

# Timelapse genereren
python3 timelapse_generator.py --days 7

# Seizoensanalyse
python3 seasonal_analysis.py
```

## Logs

```
/mnt/usb/logs/flysafe-scraper.log
/mnt/usb/logs/migration-alerts.log
/mnt/usb/logs/migration-forecast.log
```

## Troubleshooting

### Scraper faalt
```bash
# Check timer status
systemctl status flysafe-scraper.timer

# Bekijk logs
journalctl -u flysafe-scraper -f
```

### Database permission denied
```sql
-- Als birdpi_zolder geen UPDATE rechten heeft
GRANT UPDATE ON radar_observations TO birdpi_zolder;
```

### Geen correlatie data
- Check of `radar_correlation.py` gedraaid heeft
- Correlatie kijkt naar detecties ±2 uur rond radar observatie
