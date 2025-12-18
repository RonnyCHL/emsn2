# Nieuwe Grafana Dashboards - 18 december 2025

## Samenvatting

6 nieuwe Grafana dashboards gemaakt en Homer dashboard bijgewerkt met nieuwe secties.

## Nieuwe Dashboards

### 1. Vleermuizen Monitoring
**UID:** `emsn-bat-monitoring`
**URL:** http://192.168.1.25:3000/d/emsn-bat-monitoring/

Monitoring voor vleermuisdetecties (bat_detections tabel):
- Detecties stats (24u, 7d, totaal)
- Soorten overzicht
- Nachtelijke activiteit heatmap
- Piekfrequentie per soort
- Detecties tijdlijn

### 2. Nestkast Monitoring
**UID:** `emsn-nestbox-monitoring`
**URL:** http://192.168.1.25:3000/d/emsn-nestbox-monitoring/

Broedseizoen tracking (nestbox_events tabel):
- Actieve nestkasten
- Eieren/kuikens/uitgevlogen stats
- Broedseizoen tijdlijn
- Broedsucces per nestkast
- Jaarlijkse statistieken

### 3. Milestones & Records
**UID:** `emsn-milestones`
**URL:** http://192.168.1.25:3000/d/emsn-milestones/

Hall of Fame voor bijzondere momenten:
- Eerste detectie per soort
- Nieuwe soorten per maand
- Top 15 meest gedetecteerd
- Hoogste confidence per soort
- Record dagen (meeste detecties)
- Zeldzame soorten Hall of Fame

### 4. Systeem Overzicht
**UID:** `emsn-system-overview`
**URL:** http://192.168.1.25:3000/d/emsn-system-overview/

Executive KPI dashboard:
- Station status (Zolder, Berging, MQTT Bridge, Ulanzi, Weerstation)
- KPI's vandaag (detecties, soorten, zeldzaam, confidence)
- Totaal statistieken
- Trends (30d)
- Database & opslag overzicht
- Recente activiteit

### 5. Biodiversiteit Index
**UID:** `emsn-biodiversity`
**URL:** http://192.168.1.25:3000/d/emsn-biodiversity/

Ecologische diversiteitsmetrieken:
- Shannon Diversity Index (H')
- Simpson's Diversity Index (1-D)
- Pielou's Evenness (J)
- Species Richness
- Diversiteit trends (90d)
- Rank-Abundance curve
- Zeldzaamheid verdeling
- Activiteit heatmap
- Maandelijkse vergelijking

### 6. Alerts & Events
**UID:** `emsn-alerts-events`
**URL:** http://192.168.1.25:3000/d/emsn-alerts-events/

Centrale plek voor alle systeem events:
- Anomalies (24u, totaal, per type, severity)
- Systeem events
- MQTT bridge events
- MQTT notificatie failures
- Skip reasons analyse

## Homer Dashboard Updates

Nieuwe secties toegevoegd:
- **Systeem Overzicht** (bovenaan): Systeem Status, Alerts & Events
- **Natuur Monitoring** (nieuw): Vleermuizen, Nestkast Monitoring

Bestaande secties uitgebreid:
- **Vogel Dashboards**: Milestones & Records, Biodiversiteit Index

## Bestanden

| Bestand | Beschrijving |
|---------|--------------|
| `grafana/emsn-bat-monitoring.json` | Vleermuizen dashboard |
| `grafana/emsn-nestbox-monitoring.json` | Nestkast dashboard |
| `grafana/emsn-milestones.json` | Milestones & Records dashboard |
| `grafana/emsn-system-overview.json` | Systeem Overzicht dashboard |
| `grafana/emsn-biodiversity.json` | Biodiversiteit Index dashboard |
| `grafana/emsn-alerts-events.json` | Alerts & Events dashboard |

## Database Tabellen Gebruikt

| Tabel | Rows | Dashboards |
|-------|------|------------|
| `bird_detections` | 58,642 | Alle dashboards |
| `bat_detections` | 0 | Vleermuizen |
| `nestbox_events` | 0 | Nestkast |
| `milestones` | 1 | Milestones |
| `anomalies` | 10 | Alerts & Events |
| `system_events` | 2 | Alerts & Events |
| `mqtt_bridge_events` | varies | Alerts & Events, System Overview |
| `ulanzi_notification_log` | varies | Alerts & Events, System Overview |
| `weather_data` | varies | System Overview |

## Verificatie

```bash
# Check alle nieuwe dashboards
curl -s -u "admin:emsn2024" "http://192.168.1.25:3000/api/search?query=emsn" | jq '.[] | {title, uid, url}'

# Check Homer
curl -s http://192.168.1.25:8181/ | grep -c "Systeem Overzicht"
```

## Links

- **Homer:** http://192.168.1.25:8181/
- **Grafana:** http://192.168.1.25:3000/
- **Nieuwe dashboards:** Zie URLs hierboven

## Opmerkingen

- Vleermuizen en Nestkast dashboards zijn klaar voor gebruik zodra er data binnenkomt
- Biodiversiteit dashboard berekent Shannon, Simpson en Evenness indices realtime
- Systeem Overzicht is ideaal als "home" dashboard voor dagelijks gebruik
