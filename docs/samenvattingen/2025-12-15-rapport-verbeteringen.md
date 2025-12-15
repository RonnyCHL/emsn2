# Sessie Samenvatting: Rapport Systeem Verbeteringen

**Datum:** 15 december 2025
**Onderwerp:** 7 verbeteringen aan het EMSN rapport systeem

## Uitgevoerde taken

### 1. Grafieken in PDF rapporten (matplotlib)
Nieuwe module `report_charts.py` gemaakt met:
- `top_species_bar()` - Horizontale balk grafiek top 10 soorten
- `hourly_activity()` - Lijn grafiek activiteit per uur
- `daily_activity()` - Staaf grafiek dagelijkse activiteit
- `temperature_vs_activity()` - Dual-axis grafiek temp vs vogels
- `species_pie()` - Taartdiagram verdeling soorten
- `weather_conditions()` - Multi-panel weer impact grafiek
- `comparison_chart()` - Week-over-week vergelijking
- `monthly_trend()` - Maandelijkse trend lijn

EMSN kleurenpalet: donkerblauw (#1a365d) tot lichtblauw (#90cdf4)

### 2. Vergelijking met vorige periode
- `comparison_last_week` data toegevoegd met: prev_detections, prev_species, prev_week_number
- Vergelijkingsgrafiek toont week-over-week veranderingen visueel
- Percentage verandering in detecties en soorten

### 3. Rapport templates kort/uitgebreid
- `--format kort|uitgebreid` argument toegevoegd
- Kort formaat: 150-200 woorden, alleen top_species + comparison chart
- Uitgebreid formaat: 400-600 woorden, alle 7 grafieken
- Bestandsnaam krijgt `-kort` suffix voor korte versie

### 4. Automatische highlights sectie
Nieuwe module `report_highlights.py` met detectie van:
- **Seizoens vogels:** Eerste/laatste zomer- en wintergasten
- **Records:** Dagrecords per soort
- **Ongewone tijden:** Nachtelijke activiteit van dagvogels
- **Zeldzame soorten:** Soorten met <10 detecties ooit
- **Nieuwe soorten:** Eerste detecties ooit
- **Mijlpalen:** 10k, 25k, 50k+ detectie marks

SEASONAL_BIRDS, NOCTURNAL_SPECIES, RARE_SPECIES configuratie ingebouwd.

### 5. Rapport planning in web interface
Nieuwe "Planning" tab met:
- Overzicht automatische systemd timers
- Quick action knoppen: Week, Week-kort, Week+Spectrograms, Maand, Seizoen
- Recente generatie geschiedenis (laatste 10 rapporten)

API endpoints:
- `GET /api/schedule` - Timers overzicht
- `GET /api/schedule/history` - Generatie geschiedenis
- `POST /api/schedule/quick-generate` - Direct rapport genereren

### 6. Interactieve HTML web versie
Nieuwe pagina `view-interactive.html` met:
- Chart.js interactieve grafieken (hover, zoom)
- Toggle tussen interactieve en tekst weergave
- Stats overzicht kaarten
- Top species bar chart en hourly activity line chart
- Responsive design

API endpoint:
- `GET /api/report-data?file=...` - Geparseerde rapport data

Rapport cards hebben nu 3 knoppen: Interactief, Tekst, PDF

### 7. Spectrogrammen in rapporten
Nieuwe module `report_spectrograms.py`:
- Zoekt automatisch PNG spectrogrammen uit BirdNET-Pi recordings
- Selecteert beste spectrogrammen op confidence
- Kopieert naar `spectrograms/` subdirectory
- Genereert markdown sectie met afbeeldingen

Opties:
- `--spectrograms` flag voor weekly_report.py
- "Weekrapport+" knop in web interface
- Max 6 spectrogrammen (uitgebreid) of 3 (kort)

BirdSongs locatie: `/home/ronny/BirdSongs/Extracted/By_Date/{date}/{species}/`

## Nieuwe bestanden

```
scripts/reports/
├── report_charts.py      # Matplotlib grafieken generator
├── report_highlights.py  # Automatische highlight detectie
└── report_spectrograms.py # Spectrogram finder/copier

reports-web/
├── view-interactive.html # Interactieve rapport viewer
├── api.py               # Uitgebreid met schedule + report-data APIs
├── index.html           # Nieuwe Planning tab
├── app.js              # Schedule tab JavaScript
└── style.css           # Schedule styling
```

## Belangrijke technische details

### Matplotlib Backend
Non-interactive `Agg` backend voor server-side rendering:
```python
import matplotlib
matplotlib.use('Agg')
```

### Chart.js CDN
```html
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
```

### Systemd Timers (bestaand)
- `emsn-weekly-report.timer` - Maandag 07:00
- `emsn-monthly-report.timer` - 1e van de maand 08:00
- `emsn-seasonal-report-*.timer` - Begin nieuw seizoen 07:00
- `emsn-yearly-report.timer` - 2 januari 08:00

### Spectrogram bestandsformaat
```
{Species}-{confidence}-{date}-birdnet-{time}.mp3.png
Ekster-72-2025-12-08-birdnet-08:04:23.mp3.png
```

## Command line voorbeelden

```bash
# Standaard weekrapport (uitgebreid)
python weekly_report.py

# Kort weekrapport
python weekly_report.py --format kort

# Met spectrogrammen
python weekly_report.py --spectrograms

# Kort met spectrogrammen
python weekly_report.py --format kort --spectrograms

# Andere stijl
python weekly_report.py --style natuurblog
```

## Web Interface URLs

- Rapporten overzicht: http://192.168.1.178:8081/
- Interactief rapport: http://192.168.1.178:8081/view-interactive.html?report=2025-W50-Weekrapport.md
- Planning tab: http://192.168.1.178:8081/ → "Planning" tab

## Status

Alle 7 taken succesvol geïmplementeerd en getest.
