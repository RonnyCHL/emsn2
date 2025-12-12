# FlySafe Radar Dashboard Importeren in Grafana

## Stap 1: Open Grafana
Open in je browser: http://192.168.1.25:3000

## Stap 2: Importeer Dashboard
1. Klik links op het **+** icoon of ga naar **Dashboards** → **New** → **Import**
2. Klik op **Upload dashboard JSON file**
3. Selecteer: `/home/ronny/emsn2/grafana/flysafe_radar_dashboard.json`
4. Selecteer de **EMSN_PostgreSQL** datasource
5. Klik **Import**

## Dashboard Panels

Het dashboard bevat:
- **Current Migration Intensity** - Gauge met huidige radar intensiteit
- **Migration Intensity (7 Days)** - Tijdlijn van radar intensiteit
- **Intensity Distribution** - Staafdiagram van intensiteit categorieën
- **Radar vs Bird Detections** - Correlatie grafiek
- **Recent Observations** - Tabel met laatste metingen
- **Observations by Hour** - Taartdiagram per uur
- **Average Correlation Score** - Gemiddelde correlatie gauge
- **Correlation Distribution** - Histogram van correlatie scores
