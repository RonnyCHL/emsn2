# Grafana Dashboards - EMSN

## Toegang

- **URL:** http://192.168.1.25:3000
- **API Key:** `REDACTED_GRAFANA_TOKEN`
- **Datasource UID:** `emsn_postgres`

## Dashboards Overzicht

| Dashboard | UID | Beschrijving |
|-----------|-----|--------------|
| EMSN Meteo Station | `emsn-meteo` | Davis weerstation data |
| FlySafe Radar | `flysafe-radar` | KNMI vogeltrek radar |
| AtmosBird Sky Monitoring | `2c0ceb74-ce77-46f5-bd2c-a60f88960ebc` | 24/7 lucht monitoring |
| Weather vs Birds | `emsn-weather-birds` | Weer correlaties |
| Dual Detections | `emsn-dual-detections` | Beide stations detecties |
| Species Deep Dive | `emsn-species-deep-dive` | Per soort analyse |
| Vogeltrek Monitor | `emsn-migration-monitor` | Migratie patronen |
| Anomaly Detection | `emsn-anomaly-detection` | Afwijkingen detectie |
| Data Kwaliteit | `emsn-data-quality` | Data validatie |
| Hardware Prestaties | `emsn-hardware-performance` | Systeem monitoring |
| Database Monitoring | `emsn-database-monitoring` | PostgreSQL stats |
| PDF Rapporten | `emsn-pdf-reports` | Rapport generatie stats |

## Dashboard JSON Bestanden

Locatie: `/home/ronny/emsn2/grafana/`

```
grafana/
├── emsn_meteo_dashboard.json
├── flysafe_radar_dashboard.json
├── flysafe_radar_dashboard_v2.json
└── ... (andere dashboards)
```

## Nieuw Dashboard Aanmaken

### 1. JSON bestand maken

```json
{
  "annotations": {"list": []},
  "editable": true,
  "panels": [
    {
      "datasource": {"type": "postgres", "uid": "emsn_postgres"},
      "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
      "id": 1,
      "targets": [{
        "datasource": {"type": "postgres", "uid": "emsn_postgres"},
        "rawSql": "SELECT ... FROM ...",
        "format": "time_series",
        "rawQuery": true,
        "refId": "A"
      }],
      "title": "Panel Titel",
      "type": "timeseries"
    }
  ],
  "refresh": "5m",
  "schemaVersion": 39,
  "tags": ["emsn"],
  "time": {"from": "now-24h", "to": "now"},
  "title": "Dashboard Titel",
  "uid": "dashboard-uid",
  "version": 1
}
```

### 2. Importeren via API

```bash
# Maak import wrapper
jq -n --slurpfile dash /pad/naar/dashboard.json \
  '{"dashboard": $dash[0], "overwrite": true, "folderId": 0}' > /tmp/import.json

# Importeer naar Grafana
curl -s -X POST http://192.168.1.25:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer REDACTED_GRAFANA_TOKEN" \
  -d @/tmp/import.json
```

### 3. Handmatig importeren (UI)

1. Ga naar http://192.168.1.25:3000
2. Klik op + (Create) → Import
3. Plak JSON of upload bestand
4. Klik "Load" → "Import"

## Veelgebruikte Panel Types

### Stat Panel (huidige waarde)
```json
{
  "type": "stat",
  "options": {
    "colorMode": "value",
    "graphMode": "area",
    "reduceOptions": {"calcs": ["lastNotNull"]}
  },
  "fieldConfig": {
    "defaults": {
      "unit": "celsius",
      "thresholds": {
        "steps": [
          {"color": "blue", "value": null},
          {"color": "green", "value": 10},
          {"color": "red", "value": 25}
        ]
      }
    }
  }
}
```

### Time Series Panel (grafiek)
```json
{
  "type": "timeseries",
  "fieldConfig": {
    "defaults": {
      "custom": {
        "drawStyle": "line",
        "lineInterpolation": "smooth",
        "fillOpacity": 20
      }
    }
  }
}
```

### Bar Chart Panel
```json
{
  "type": "barchart",
  "options": {
    "orientation": "vertical",
    "barWidth": 0.8
  }
}
```

**Let op:** Bar charts vereisen een string veld voor de x-as:
```sql
-- FOUT: Bar charts require a string or time field
SELECT EXTRACT(HOUR FROM time) as hour, COUNT(*) as count ...

-- GOED: Cast naar string
SELECT LPAD(EXTRACT(HOUR FROM time)::int::text, 2, '0') || ':00' as "Uur", COUNT(*) ...
```

## Geldige Kleuropties

```
fixed, shades, thresholds, palette-classic, palette-classic-by-name,
continuous-GrYlRd, continuous-RdYlGr, continuous-BlYlRd, continuous-YlRd,
continuous-BlPu, continuous-YlBl, continuous-blues, continuous-reds,
continuous-greens, continuous-purples
```

**Let op:** `continuous-YlOrRd` bestaat NIET in deze Grafana versie!

## SQL Query Tips

### Time Series Format
```sql
SELECT
  measurement_timestamp as time,  -- moet "time" heten
  temp_outdoor as "Temperatuur"
FROM weather_data
WHERE measurement_timestamp >= NOW() - INTERVAL '24 hours'
ORDER BY time
```

### Table Format (voor stats)
```sql
SELECT temp_outdoor as "Temp"
FROM weather_data
ORDER BY measurement_timestamp DESC
LIMIT 1
```

## Troubleshooting

### "No data" in panel
1. Check datasource UID: moet `emsn_postgres` zijn
2. Check kolomnamen in query
3. Test query in pgAdmin

### Dashboard laadt niet
1. Check JSON syntax
2. Check color modes (alleen geldige opties)
3. Check panel IDs (moeten uniek zijn)

### API import faalt
```bash
# Check API key geldigheid
curl -s http://192.168.1.25:3000/api/org \
  -H "Authorization: Bearer REDACTED_GRAFANA_TOKEN"
```
