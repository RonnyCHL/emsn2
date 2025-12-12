# EMSN 2.0 - Anomaly Detection System

## 📋 Overzicht

Het Anomaly Detection systeem monitort automatisch EMSN voor hardware problemen, data quality issues, en onverwachte patronen.

## 🔄 Componenten

### 1. Database Schema

**Tabellen:**
- `anomalies` - Alle gedetecteerde anomalieën
- `species_baselines` - Geleerde baselines per soort
- `anomaly_check_log` - Check uitvoering log

**Views:**
- `active_anomalies` - Huidige actieve anomalieën
- `anomaly_summary_24h` - 24-uurs samenvatting

### 2. Anomaly Checkers

| Checker | Interval | Beschrijving |
|---------|----------|--------------|
| **hardware_checker.py** | 15 min | Stilte, low confidence, meteo |
| **data_gap_checker.py** | 15 min | Station imbalance, database growth |
| **baseline_learner.py** | Zondag 03:00 | Update species baselines |

### 3. Systemd Services

```bash
# Status checken
systemctl status anomaly-hardware-check.timer
systemctl status anomaly-datagap-check.timer
systemctl status anomaly-baseline-learn.timer

# Timers bekijken
systemctl list-timers "anomaly-*"

# Logs bekijken
journalctl -u anomaly-hardware-check.service -f
journalctl -u anomaly-datagap-check.service -f
```

## 🚨 Anomalie Types

### Hardware Anomalies

| Type | Trigger | Severity |
|------|---------|----------|
| silence_daytime | Geen detecties > 2u (06:00-22:00) | ⚠️ Warning |
| silence_total | Geen detecties > 6u | 🔴 Critical |
| low_confidence_cluster | 10+ detecties allemaal <65% | ⚠️ Warning |
| meteo_silence | Geen meteo data > 2u | ⚠️ Warning |
| meteo_sensor_failure | >50% NULL values | ⚠️ Warning |

### Data Gap Anomalies

| Type | Trigger | Severity |
|------|---------|----------|
| station_imbalance | Ratio Zolder:Berging > 10:1 | ⚠️ Warning |
| database_growth_stalled | > 4u geen nieuwe records | ⚠️ Warning |

## 📊 Grafana Dashboard

**Installatie:**

1. Open Grafana UI
2. Ga naar Dashboards → Import
3. Upload `/home/ronny/emsn2/grafana/anomaly-dashboard.json`
4. Selecteer PostgreSQL datasource: `emsn`

**Panels:**
- Active Anomalies (tabel)
- Anomalies by Type (bar chart)
- Anomalies by Severity (pie chart)
- Anomalies Timeline (timeseries)
- Hardware/Data Gap counts (stats)
- Check Performance (tabel)
- Species Baselines (tabel)

## 🔧 Handmatige Uitvoering

```bash
# Baseline learning
python3 /home/ronny/emsn2/scripts/anomaly/baseline_learner.py

# Hardware check
python3 /home/ronny/emsn2/scripts/anomaly/hardware_checker.py

# Data gap check
python3 /home/ronny/emsn2/scripts/anomaly/data_gap_checker.py
```

## 📈 Database Queries

### Actieve anomalieën bekijken
```sql
SELECT * FROM active_anomalies;
```

### Anomalieën per type (laatste 24u)
```sql
SELECT * FROM anomaly_summary_24h;
```

### Species baselines
```sql
SELECT species_nl, detection_count, months_active, hours_active,
       ROUND(avg_confidence::numeric, 2) as avg_conf
FROM species_baselines
ORDER BY detection_count DESC
LIMIT 20;
```

### Anomalie history voor een station
```sql
SELECT timestamp, anomaly_type, severity, description
FROM anomalies
WHERE station_id = 'zolder'
  AND timestamp > NOW() - INTERVAL '7 days'
ORDER BY timestamp DESC;
```

### Auto-resolve oude anomalieën
```sql
SELECT auto_resolve_old_anomalies();
```

## 🎯 Troubleshooting

### Checker draait niet
```bash
# Check timer status
systemctl status anomaly-hardware-check.timer

# Check laatste uitvoering
journalctl -u anomaly-hardware-check.service -n 50

# Handmatig starten
sudo systemctl start anomaly-hardware-check.service
```

### Te veel false positives
Pas thresholds aan in de checker scripts:
- `SILENCE_DAYTIME_HOURS` - hardware_checker.py
- `STATION_IMBALANCE_RATIO` - data_gap_checker.py
- `MIN_DETECTIONS_FOR_BASELINE` - baseline_learner.py

### Baselines updaten
```bash
# Force baseline herberekening
python3 /home/ronny/emsn2/scripts/anomaly/baseline_learner.py
```

## 📝 Logging

Alle checkers loggen naar:
- Systemd journal (`journalctl`)
- Database tabel `anomaly_check_log`

## 🔮 Toekomstige Uitbreidingen

Zie `EMSN_Master_Checklist.md` Fase 14 voor:
- Species anomaly checker (seizoensafwijkingen, verdwenen soorten)
- Weer correlatie checker
- Home Assistant notificaties
- MQTT alerting

## ✅ Status

**Geïmplementeerd:**
- ✅ Database schema
- ✅ Species baseline learning
- ✅ Hardware anomaly detection
- ✅ Data gap detection
- ✅ Systemd timers
- ✅ Grafana dashboard basis

**TODO:**
- ⏳ Species anomaly detection
- ⏳ Weer correlatie analysis
- ⏳ Home Assistant integratie
- ⏳ MQTT alerting
