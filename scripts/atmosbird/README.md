# AtmosBird - 24/7 Sky Monitoring System

AtmosBird is een geautomatiseerd luchtmonitoringsysteem dat elke 10 minuten de lucht fotografeert en analyseert met een Pi Camera NoIR op het berging station.

## Features

### Phase 1: Basis Setup ✅
- **Hardware**: Pi Camera NoIR Module 3 (imx708_wide_noir)
- **Resolutie**: 4608x2592 pixels
- **Capture frequentie**: Elke 10 minuten
- **Cloud coverage detectie** met adaptieve thresholding
- **Brightness analyse** (mean + std)
- **Dag/nacht detectie**
- **Sky type classificatie**: clear, partly_cloudy, overcast
- **NAS opslag** in georganiseerde directory structuur: `/atmosbird/ruwe_foto/YYYY/MM/DD/`

### Phase 2: Advanced Analysis ✅
- **ISS tracking**: Detecteert wanneer ISS zichtbaar is
- **Moon phase tracking**: Volgt maanfase, positie, en helderheid
- **Star brightness analyse**: Telt sterren, berekent Bortle scale
- **Meteor detection**: Frame differencing voor meteorendetectie
- **Automated analysis**: Draait elke 15 minuten

### Phase 3: Timelapse Generation ✅
- **Dagelijkse timelapses**: Gegenereerd om 00:30 voor vorige dag
- **Day/Night splits**: Aparte timelapses voor dag en nacht
- **Video formaat**: MP4 (H.264, 24fps)
- **Metadata tracking**: Opgeslagen in database

### Phase 4: Additional Features (Future)
- Bird silhouette detection
- Weather correlation
- Seasonal analysis
- Monthly compilation timelapses

### Phase 5: Grafana Dashboard ✅
- Live sky preview
- Cloud coverage trends
- Moon phase progress
- Star observations
- Meteor detections
- Timelapse library
- System health monitoring

## Database Schema

### sky_observations
Hoofdtabel met alle luchtfoto observaties:
- `observation_timestamp`: Tijdstip van waarneming
- `sky_type`: clear, partly_cloudy, overcast
- `cloud_coverage`: Bewolkingspercentage (0-100)
- `brightness`: Gemiddelde helderheid
- `image_path`: Pad naar foto op NAS
- `quality_score`: Contraststcore

### moon_observations
Maan tracking data:
- `phase_name`: Maanfase naam
- `illumination_percent`: Verlichtingspercentage
- `age_days`: Leeftijd sinds nieuwe maan
- `altitude_degrees`: Hoogte boven horizon
- `detected_in_image`: Zichtbaar in foto

### star_brightness
Sterren analyse (alleen 's nachts):
- `star_count`: Aantal gedetecteerde sterren
- `avg_star_brightness`: Gemiddelde sterhelderheid
- `sky_background_brightness`: Achtergrondhelderheid
- `bortle_scale_estimate`: Lichtvervuiling indicator (1-9)
- `seeing_quality_score`: Atmosferische seeing quality

### meteor_detections
Meteoordetecties:
- `confidence_score`: Betrouwbaarheidsscore (0-100)
- `streak_length_pixels`: Lengte van het spoor
- `brightness_delta`: Helderheidstoename
- `bbox_x/y/width/height`: Bounding box locatie

### timelapses
Timelapse metadata:
- `timelapse_type`: daily, day_only, night_only, monthly
- `frame_count`: Aantal frames
- `duration_seconds`: Video lengte
- `video_path`: Pad naar video
- `avg_cloud_coverage`: Gemiddelde bewolking

### atmosbird_health
Systeemgezondheid:
- `disk_usage_percent`: Schijfgebruik
- `photos_captured_today`: Foto's vandaag
- `last_capture_success`: Status laatste capture

## Scripts

### atmosbird_capture.py
Hoofdscript voor foto capture en basis analyse.

**Wat het doet:**
1. Maakt foto met rpicam-still op max resolutie
2. Analyseert cloud coverage met OpenCV
3. Berekent brightness en contrast
4. Detecteert dag/nacht
5. Classificeert sky type
6. Slaat foto op naar NAS
7. Schrijft metadata naar PostgreSQL
8. Update health metrics

**Draait**: Elke 10 minuten via systemd timer

### atmosbird_analysis.py
Geavanceerde analyse script voor astronomische waarnemingen.

**Wat het doet:**
1. **ISS tracking**: Berekent ISS positie met PyEphem
2. **Moon analysis**: Fase, positie, helderheid
3. **Star detection**: Telt sterren, berekent Bortle scale
4. **Meteor detection**: Frame differencing tussen opeenvolgende foto's
5. Schrijft alle resultaten naar database

**Draait**: Elke 15 minuten via systemd timer

### atmosbird_timelapse.py
Dagelijkse timelapse generator.

**Wat het doet:**
1. Haalt alle observaties van vorige dag op
2. Genereert 3 timelapses:
   - **Daily**: Alle foto's (24h)
   - **Day only**: Alleen overdag (brightness > 80)
   - **Night only**: Alleen 's nachts (brightness ≤ 80)
3. Gebruikt ffmpeg voor video encoding
4. Slaat metadata op in database

**Draait**: Dagelijks om 00:30 via systemd timer

**Handmatig draaien voor specifieke datum:**
```bash
python3 atmosbird_timelapse.py 2025-12-12
```

## Installatie

### 1. Hardware Setup
```bash
# Controleer camera
rpicam-hello --list-cameras
# Zou moeten tonen: imx708_wide_noir
```

### 2. Dependencies
```bash
pip install opencv-python-headless numpy pillow psycopg2-binary pyephem astral requests --break-system-packages
sudo apt-get install ffmpeg
```

### 3. NAS Directories
```bash
sudo mkdir -p /mnt/usb/atmosbird/{ruwe_foto,timelapse,detecties}
sudo chown -R ronny:ronny /mnt/usb/atmosbird
```

### 4. Scripts
```bash
# Kopieer scripts naar /home/ronny/
cp atmosbird_*.py /home/ronny/
chmod +x /home/ronny/atmosbird_*.py
```

### 5. Systemd Timers
```bash
# Kopieer systemd units
sudo cp ../systemd/atmosbird-*.service /etc/systemd/system/
sudo cp ../systemd/atmosbird-*.timer /etc/systemd/system/

# Reload en start timers
sudo systemctl daemon-reload
sudo systemctl enable atmosbird-capture.timer atmosbird-analysis.timer atmosbird-timelapse.timer
sudo systemctl start atmosbird-capture.timer atmosbird-analysis.timer atmosbird-timelapse.timer

# Controleer status
systemctl list-timers atmosbird*
```

## Storage Structuur

```
/mnt/usb/atmosbird/
├── ruwe_foto/
│   └── YYYY/
│       └── MM/
│           └── DD/
│               └── sky_YYYYMMDD_HHMMSS.jpg
├── timelapse/
│   └── YYYY/
│       └── MM/
│           ├── sky_daily_YYYYMMDD.mp4
│           ├── sky_day_YYYYMMDD.mp4
│           └── sky_night_YYYYMMDD.mp4
└── detecties/
    └── meteors/
        └── meteor_YYYYMMDD_HHMMSS_crop.jpg
```

## Grafana Dashboard

Dashboard URL: `http://192.168.1.25:3000/d/atmosbird-sky-monitoring`

### Panels:
1. **Latest Sky Capture** - Meest recente foto
2. **Total Sky Observations** - Totaal aantal waarnemingen
3. **Observations Today** - Vandaag vastgelegd
4. **Total Timelapses** - Gegenereerde timelapses
5. **Disk Usage** - Schijfgebruik gauge
6. **Last Capture Success** - Status laatste capture
7. **Cloud Coverage Trend** - 7-dagen trend
8. **Sky Brightness Trend** - Helderheid over tijd
9. **Sky Type Distribution** - Pie chart bewolking
10. **Moon Phase Progress** - Maanfase tracking
11. **Star Observations** - Sterren data (nachten)
12. **Meteor Detections** - Meteoor counter
13. **Meteor Detection Details** - Details van detecties
14. **Recent Timelapses** - Timelapse library
15. **Observations per Hour** - Activiteit per uur
16. **System Health** - Systeemstatus

## Monitoring

### Logs
```bash
# Capture logs
tail -f /mnt/usb/logs/atmosbird-capture.log

# Analysis logs
tail -f /mnt/usb/logs/atmosbird-analysis.log

# Timelapse logs
tail -f /mnt/usb/logs/atmosbird-timelapse.log
```

### Database Queries
```sql
-- Laatste observaties
SELECT * FROM sky_observations ORDER BY observation_timestamp DESC LIMIT 10;

-- Maan vandaag
SELECT * FROM moon_observations WHERE observation_timestamp >= CURRENT_DATE;

-- Alle meteoor detecties
SELECT * FROM meteor_detections ORDER BY confidence_score DESC;

-- Tijdlapse overzicht
SELECT * FROM timelapses ORDER BY created_timestamp DESC;

-- Health status
SELECT * FROM atmosbird_health ORDER BY measurement_timestamp DESC LIMIT 1;
```

### Manual Test Runs
```bash
# Test capture
python3 /home/ronny/atmosbird_capture.py

# Test analysis
python3 /home/ronny/atmosbird_analysis.py

# Test timelapse (for today)
python3 /home/ronny/atmosbird_timelapse.py $(date +%Y-%m-%d)
```

## Configuration

### Thresholds
In `atmosbird_capture.py`:
- `DAYTIME_BRIGHTNESS_THRESHOLD = 100` - Dag/nacht grens
- `CLOUD_THRESHOLD_CLEAR = 20` - Onbewolkt onder 20%
- `CLOUD_THRESHOLD_OVERCAST = 80` - Bewolkt boven 80%

### ISS TLE Updates
ISS orbital data moet regelmatig worden geüpdatet in `atmosbird_analysis.py`.

Haal actuele TLE op van: https://celestrak.org/NORAD/elements/gp.php?CATNR=25544&FORMAT=TLE

### Capture Settings
```python
CAMERA_WIDTH = 4608
CAMERA_HEIGHT = 2592
```

## Future Enhancements

- [ ] Bird silhouette detection (integratie met EMSN bird data)
- [ ] Weather correlation (integratie met weather_data)
- [ ] Seasonal sky analysis
- [ ] Monthly timelapse compilations
- [ ] Automatic ISS TLE updates
- [ ] Image-based meteor verification
- [ ] Aurora detection (voor noorderlicht)
- [ ] Satellite trail detection
- [ ] Light pollution mapping over tijd

## Technische Details

**Hardware:**
- Raspberry Pi (berging station)
- Pi Camera Module 3 NoIR (imx708_wide_noir)
- NAS storage via USB

**Software Stack:**
- Python 3.13
- OpenCV voor beeldanalyse
- PyEphem voor astronomische berekeningen
- ffmpeg voor video encoding
- PostgreSQL voor metadata
- Grafana voor visualisatie

**Astronomische Berekeningen:**
- ISS positie: PyEphem met TLE data
- Maan fase: Ephem moon calculations
- Sterren detectie: Brightness thresholding + contour detection
- Bortle scale: Sky background brightness mapping

**Cloud Coverage Algorithm:**
1. Gaussian blur voor noise reductie
2. Adaptive thresholding
3. Pixel percentage berekening
4. Verschillende aanpak voor dag/nacht

## Auteurs

- Claude Sonnet 4.5 (AI Assistant)
- Ronny (EMSN Project Owner)

## License

Deel van het EMSN 2.0 (Ecologisch Monitoring Systeem Nijverdal) project.
