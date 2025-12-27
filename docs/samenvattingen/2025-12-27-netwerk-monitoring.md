# Sessie Samenvatting: Netwerk Monitoring Dashboard

**Datum:** 2025-12-27
**Onderwerp:** Complete netwerk monitoring infrastructuur voor EMSN

## Wat is gemaakt

### 1. Database Tabellen (PostgreSQL)
Twee nieuwe tabellen in de `emsn` database:

**network_status** - Apparaat monitoring
- device_name, device_ip, device_type
- is_online, latency_ms, packet_loss_pct
- timestamp, last_seen

**service_status** - Service monitoring
- device_name, service_name, service_type
- is_available, response_time_ms, status_code
- error_message, timestamp

### 2. Monitoring Script
**Locatie:** `/home/ronny/emsn2/scripts/monitoring/network_monitor.py`

Monitort elke minuut:

| Apparaat | IP | Type |
|----------|-----|------|
| emsn2-zolder | 192.168.1.178 | Raspberry Pi |
| emsn2-berging | 192.168.1.87 | Raspberry Pi |
| emsn2-meteo | 192.168.1.156 | Raspberry Pi |
| nas-synology | 192.168.1.25 | Synology NAS |
| ulanzi-display | 192.168.1.11 | AWTRIX LED |
| router | 192.168.1.1 | Router |

| Service | Apparaat | Type |
|---------|----------|------|
| Grafana | nas-synology | HTTP |
| Homer | nas-synology | HTTP |
| PostgreSQL | nas-synology | TCP |
| Go2RTC | nas-synology | HTTP |
| MQTT-Broker | emsn2-zolder | TCP |
| Reports-API | emsn2-zolder | HTTP |
| AWTRIX-API | ulanzi-display | HTTP |
| BirdNET-Pi | emsn2-zolder | HTTP |
| BirdNET-Pi | emsn2-berging | HTTP |

### 3. Systemd Timer
**Bestanden:**
- `/home/ronny/emsn2/systemd/network-monitor.service`
- `/home/ronny/emsn2/systemd/network-monitor.timer`

Draait elke minuut via systemd timer.

### 4. Grafana Dashboard
**Locatie:** `/home/ronny/emsn2/grafana/emsn-network-monitoring.json`
**URL:** http://192.168.1.25:3000/d/emsn-network-monitoring/

**Panels:**
- Beschrijving header (h: 7)
- Overzicht: Apparaten Online, Services Beschikbaar, Gem. Latency, Packet Loss, Metingen Vandaag, Laatste Scan
- Apparaat Status tabel (ONLINE/OFFLINE)
- Service Status tabel (OK/FAIL)
- Latency per Apparaat grafiek (1u)
- Service Response Time grafiek (1u)
- Uptime gauges per apparaat (24u)
- Service Uptime gauges (24u)
- Incidenten tabellen (offline momenten, service failures)

### 5. Homer Dashboard Link
Link toegevoegd in sectie "Netwerk & Services":
- **Naam:** Netwerk Monitoring
- **URL:** http://192.168.1.25:3000/d/emsn-network-monitoring/

## Technische Details

- **Datasource type:** `grafana-postgresql-datasource` (niet `postgresql`)
- **MQTT publicatie:** Status naar `emsn2/network/status` en per apparaat
- **Parallel checks:** ThreadPoolExecutor met max 10 workers
- **Logging:** `/mnt/usb/logs/network_monitor.log`

## Problemen Opgelost

1. **Permission denied tables:** Opgelost met postgres superuser
2. **Homer poort:** 8181 ipv 8080
3. **Reports-API endpoint:** `/api/nestbox/list` ipv `/health`
4. **Grafana datasource type:** `grafana-postgresql-datasource`
5. **"No data" Laatste Scan:** Numerieke query ipv text string
6. **Nederlandse weergave:** Unit `s` voor seconden weergave
