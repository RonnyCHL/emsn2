# Sessie Samenvatting 27 December 2025 - Dashboard Fixes & MQTT Heartbeat

## Overzicht
Systematische doorgang van alle 26 EMSN Grafana dashboards om query errors te fixen, plus implementatie van MQTT bridge heartbeat monitoring.

## Uitgevoerde Werkzaamheden

### 1. Dashboard Query Fixes

#### Milestones & Records
- `scientific_name` kolom bestaat niet in `bird_detections`
- Queries herschreven met JOIN naar `species_reference` tabel

#### Variable Syntax (53 queries in 5 dashboards)
- Data Kwaliteit, Dubbele Detecties, Hardware Prestaties, Vogeltrek Monitor, Weer vs Vogels
- Fix: `= $var` → `= '${var}'`

#### Grafana Time Macros (53+ queries)
- **Probleem**: `${__timeFrom()}` werkte niet in sommige panels
- **Oplossing**: `${__timeFrom()}` → `$__timeFrom()` (zonder braces)
- Betreft: `$__timeFrom()`, `$__timeTo()`, `$__timeFilter()`, `$__interval`

#### Column Name Fixes (8 queries)
- Alerts & Events: `detected_at` → `timestamp`, `timestamp` → `event_timestamp`
- PDF Rapporten: `temperature` → `temp_outdoor`, `achieved_at` → `milestone_date`

#### MQTT Monitoring
- `ROUND(AVG(x), n)` → `ROUND(AVG(x)::numeric, n)` (PostgreSQL type casting)

#### Database Monitoring
- Actieve Stations query aangepast: telt nu Zolder + Berging + Meteo (was alleen BirdNET stations)

### 2. MQTT Bridge Heartbeat Implementatie

#### Probleem
- MQTT Bridge toonde "Offline" in dashboard
- Oude query checkte op events binnen 24 uur
- Bridge was 5 dagen stabiel → geen nieuwe events → "Offline"

#### Oplossing
**bridge_monitor.py uitgebreid met heartbeat:**
```python
self.heartbeat_interval = 300  # 5 minuten

def send_heartbeat(self):
    """Send periodic heartbeat to indicate monitor is alive"""
    bridges_ok = all(b["connected"] for b in self.bridge_status.values())
    status = "healthy" if bridges_ok else "degraded"
    self.log_bridge_event('monitor', 'heartbeat', message)
```

**Run loop aangepast:**
- `loop_forever()` → `loop_start()` + eigen while loop
- Heartbeat check elke minuut, verzenden elke 5 minuten

**Dashboard query aangepast:**
```sql
SELECT CASE
  WHEN EXISTS (
    SELECT 1 FROM mqtt_bridge_events
    WHERE event_type IN ('heartbeat', 'connected')
    AND timestamp >= NOW() - INTERVAL '10 minutes'
  )
  AND NOT EXISTS (
    SELECT 1 FROM mqtt_bridge_events
    WHERE event_type = 'disconnected'
    AND timestamp >= NOW() - INTERVAL '10 minutes'
  )
  THEN 1 ELSE 0
END
```

## Geleerde Lessen (voor Claude)

### Grafana Macro Syntax
- **BELANGRIJK**: Gebruik `$__timeFrom()` NIET `${__timeFrom()}`
- De braces `{}` syntax werkt niet consistent in alle Grafana versies/panels
- Dit veroorzaakt `syntax error at or near "$"` errors

### PostgreSQL Type Casting
- `ROUND(double precision, integer)` bestaat NIET in PostgreSQL
- `AVG()` retourneert `double precision`
- Fix: `ROUND(AVG(x)::numeric, n)`

### Dashboard Status Monitoring
- Heartbeat-based monitoring is betrouwbaarder dan event-based
- Event-based faalt als systeem stabiel is (geen events = lijkt offline)
- Heartbeat elke 5 minuten + check window van 10 minuten = goede marge

### Tabel/Kolom Namen EMSN Database
- `bird_detections.station` (niet `station_id` of `source_station`)
- `bird_detections.station` waarden: `'zolder'`, `'berging'` (niet `'birdpi_zolder'`)
- `system_events.event_timestamp` (niet `timestamp`)
- `anomalies.timestamp` (niet `detected_at`)
- `weather_data.temp_outdoor` (niet `temperature`)
- `milestones.milestone_date` (niet `achieved_at`)

## Bestanden Gewijzigd
- `/home/ronny/emsn2/scripts/mqtt/bridge_monitor.py` - heartbeat toegevoegd
- 26 Grafana dashboards via API - diverse query fixes

## Services Herstart
- `mqtt-bridge-monitor.service` - voor heartbeat functionaliteit

## Validatie
- 25/26 dashboards valideren correct tegen database
- 1 dashboard (Data Explorer) heeft numerieke variable die test niet kan simuleren maar werkt in Grafana
- MQTT Bridge toont nu "Online" in Systeem Overzicht
- Actieve Stations toont nu 3 (Zolder, Berging, Meteo)
