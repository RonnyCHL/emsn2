# MQTT Monitoring Dashboard - 18 december 2025

## Samenvatting

Uitgebreid Grafana dashboard gemaakt voor MQTT systeem monitoring met bridge event tracking en alerts.

## Wat is er gedaan

### 1. Database Migratie (017_mqtt_bridge_events.sql)

Nieuwe tabellen aangemaakt:

**mqtt_bridge_events**
- Logt alle bridge connect/disconnect events
- Velden: timestamp, bridge_name, event_type, source, message, duration_seconds
- Inclusief indexes voor snelle queries

**mqtt_hourly_stats**
- Geaggregeerde MQTT stats per uur per station
- Voor performance bij lange tijdranges

**mqtt_bridge_uptime (view)**
- Berekent uptime percentages per dag per bridge

### 2. Bridge Monitor Script (v2.0)

[scripts/mqtt/bridge_monitor.py](../../scripts/mqtt/bridge_monitor.py) uitgebreid met:
- PostgreSQL database logging van bridge events
- Automatische reconnect bij database verbindingsverlies
- Logging van startup/shutdown events
- Duration tracking (hoe lang bridge connected was)

### 3. Grafana Dashboard

**Locatie:** [grafana/emsn-mqtt-monitoring.json](../../grafana/emsn-mqtt-monitoring.json)

**URL:** http://192.168.1.25:3000/d/emsn-mqtt-monitoring/

**Panels:**

| Sectie | Panels |
|--------|--------|
| **Overzicht** | Berichten (24u), Getoond, Geskipt, Success Rate, Actieve Cooldowns, Bridge Status |
| **Berichten Flow** | Gestapelde bar chart per uur, Getoond vs Geskipt pie, Per Station pie |
| **Rarity & Skip Analyse** | Rarity tier verdeling, Skip reasons bar, Top 15 gefilterde soorten, Actieve cooldowns tabel |
| **Bridge Status** | Uptime gauges (7d), Connects/Disconnects stats, Events tabel, Status timeline |
| **Statistieken** | Success rate trend, Confidence trend, Heatmap dag/uur, Dagelijkse bar chart |
| **Recent Activity** | Laatste 50 MQTT berichten tabel |

### 4. Grafana Alerts

4 alerts geconfigureerd in folder "EMSN Alerts":

| Alert | Conditie | For | Severity |
|-------|----------|-----|----------|
| **MQTT Success Rate Laag** | < 80% in laatste uur | 10m | warning |
| **MQTT Bridge Disconnected** | Disconnect event in 15 min | 0s | critical |
| **MQTT Send Failures Hoog** | >= 5 failures in uur | 5m | warning |
| **Geen MQTT Berichten** | 0 berichten in 2 uur | 30m | warning |

Email contact point: ronny@ronnyhullegie.nl

### 5. Homer Dashboard Link

Link toegevoegd aan Homer dashboard in "Systeem Monitoring" sectie:
- **MQTT Monitoring** - Bridge status & message flow

Homer config geherstructureerd met logische groepen:
- Vogel Dashboards, Weer & Omgeving, Systeem Monitoring, Data Kwaliteit
- Vogelstations, AI Rapporten, Hardware & IoT, Documentatie

### 6. Bugfixes

- **Datasource UID:** Gecorrigeerd van `emsn-postgres` naar `emsn_postgres`
- **Nederlandse vertalingen:** Dashboard titels en labels vertaald naar Nederlands

## Bestanden

| Bestand | Beschrijving |
|---------|--------------|
| `database/migrations/017_mqtt_bridge_events.sql` | Database migratie |
| `scripts/mqtt/bridge_monitor.py` | Updated bridge monitor v2.0 |
| `grafana/emsn-mqtt-monitoring.json` | Dashboard JSON |
| `grafana/emsn-mqtt-alerts.json` | Alerts definitie (backup) |

## Verificatie

```bash
# Check bridge events in database
PGPASSWORD='REDACTED_DB_PASS' psql -h 192.168.1.25 -p 5433 -U birdpi_zolder -d emsn \
  -c "SELECT * FROM mqtt_bridge_events ORDER BY timestamp DESC LIMIT 10;"

# Check bridge monitor service
systemctl status mqtt-bridge-monitor

# Check alerts
curl -s -u "admin:emsn2024" "http://192.168.1.25:3000/api/v1/provisioning/alert-rules"
```

## Links

- **Dashboard:** http://192.168.1.25:3000/d/emsn-mqtt-monitoring/
- **Homer:** http://192.168.1.25:8181/
- **Alerts:** http://192.168.1.25:3000/alerting/list

## Volgende stappen

- [ ] Monitoring van bridge latency toevoegen
- [ ] MQTT message throughput tracking
- [ ] Integration met Home Assistant voor bridge status sensors
