# Sessie Samenvatting 2025-12-22: AtmosBird ISS Tracking

## Overzicht
AtmosBird systeem geanalyseerd en uitgebreid met ISS tracking en astronomie features.

## Wat is AtmosBird?
24/7 luchtmonitoringsysteem op de berging Pi (192.168.1.87) met Pi Camera NoIR Module 3:
- Elke 10 minuten een foto van de lucht
- Cloud coverage, brightness en sky type analyse
- ISS tracking, maanfase, sterren en meteoor detectie
- Dagelijkse timelapses

## Uitgevoerde Wijzigingen

### 1. ISS TLE Data Update
- Nieuwe TLE data van Celestrak (2025-12-22)
- Nauwkeurigere ISS positieberekeningen

### 2. Camera Configuratie
```python
LOCATION_LAT = 52.360179  # Exacte berging locatie
LOCATION_LON = 6.472626
CAMERA_FOV_DIAGONAL = 120  # graden
CAMERA_FOV_HORIZONTAL = 102
CAMERA_FOV_VERTICAL = 67
CAMERA_POINTING = "zenith"  # recht omhoog
```

### 3. ISS Detectie Verbeterd
- ISS alleen gelogd als altitude >= 30° (binnen camera FOV)
- Passages worden nu opgeslagen in `iss_passes` tabel
- Inclusief altitude, azimuth en tijdstip

### 4. Maan Tracking
- `in_camera_fov` indicator toegevoegd
- Alleen als maan >30° boven horizon

### 5. Grafana Dashboard
Nieuwe panels toegevoegd aan "AtmosBird - Hemel Monitoring":
- 🛰️ ISS Passages (teller)
- 🌟 Meteoor Detecties (teller)
- ⭐ Heldere Nachten (teller)
- 🌙 Maan in Camera (teller)
- 🛰️ ISS Passages Log (detail tabel)

### 6. Opruiming
- Duplicate dashboards verwijderd (3 → 1)
- Homer link bijgewerkt naar nieuwe dashboard UID

### 7. Berging Configuratie
- `.secrets` bestand aangemaakt op berging
- Secrets loader met fallback paden

## Volgende ISS Passages (in camera)
| Datum/Tijd | Max Hoogte |
|------------|------------|
| 23 dec 05:42 | 72.6° |
| 23 dec 07:19 | 70.2° |
| 24 dec 04:54 | 62.0° |
| 24 dec 06:31 | 77.9° |

## Database Status
- `sky_observations`: 1257 records
- `moon_observations`: 2515 records
- `iss_passes`: 0 records (wacht op eerste detectie)
- `meteor_detections`: 0 records (99% bewolking)
- `star_brightness`: 0 records (bewolking te hoog)

## Bestanden Gewijzigd
- `scripts/atmosbird/atmosbird_analysis.py` - ISS/maan tracking verbeteringen
- `grafana/atmosbird-dashboard-final.json` - Nieuwe astronomie panels
- `/mnt/nas-docker/homer/config.yml` - Dashboard link update

## URLs
- **Dashboard:** http://192.168.1.25:3000/d/e93c556b-ff12-44b7-a66f-80bde253f8b7/atmosbird-hemel-monitoring
- **Homer:** http://192.168.1.25:8181

## Notities
- ISS TLE data moet periodiek worden geüpdatet (elke 1-2 weken)
- Sterren/meteoor detectie werkt alleen bij cloud_coverage < 50%
- Nederlandse winter = veel bewolking = weinig astronomie data
