# Sessie Samenvatting: MQTT Infrastructuur Uitbreiding

**Datum:** 14 december 2025
**Type:** MQTT infrastructuur uitbreiding en monitoring

## Overzicht

Uitgebreide MQTT infrastructuur met bidirectionele bridges, monitoring, BirdNET publishing, en automatic failover.

## 1. Bidirectionele Bridge

### Configuratie

**Berging → Zolder** (al geconfigureerd)
- Config: `/etc/mosquitto/conf.d/bridge-zolder.conf`
- Topics: `emsn2/berging/#`, `birdnet/berging/#`

**Zolder → Berging** (nieuw)
- Config: `/etc/mosquitto/conf.d/bridge-berging.conf`
- Topics: `emsn2/zolder/#`, `birdnet/zolder/#`

**Berging Listener** (nieuw)
- Config: `/etc/mosquitto/conf.d/listener.conf`
- Staat remote connecties toe

### Architectuur

```
┌─────────────────┐                    ┌─────────────────┐
│   Pi Berging    │◀──── bridge ──────▶│   Pi Zolder     │
│  192.168.1.87   │                    │  192.168.1.178  │
│                 │                    │                 │
│  Mosquitto      │                    │  Mosquitto      │
│  + bridge       │                    │  + bridge       │
│  + listener     │                    │  (hoofdbroker)  │
└─────────────────┘                    └─────────────────┘
```

## 2. Bridge Status Monitoring

**Service:** `mqtt-bridge-monitor.service`
- Continu luisteren naar bridge status topics
- Email alerts bij disconnecties (1 uur cooldown)
- State tracking in `/mnt/usb/logs/bridge_monitor_state.json`

**Status Topics:**
- `emsn2/bridge/status` - Berging → Zolder bridge
- `emsn2/bridge/zolder-status` - Zolder → Berging bridge

## 3. BirdNET MQTT Publishing

**Service:** `birdnet-mqtt-publisher.service` (op beide Pi's)

Monitort lokale BirdNET-Pi SQLite database en publiceert nieuwe detecties naar MQTT.

**Topics:**
- `birdnet/{station}/detection` - Individuele detecties
- `birdnet/{station}/stats` - Dagelijkse statistieken (elke 5 min)

**Message Format (detection):**
```json
{
  "station": "zolder",
  "timestamp": "2025-12-14 16:08:13",
  "species": "Koperwiek",
  "scientific_name": "Turdus iliacus",
  "confidence": 0.99,
  "file": "...",
  "latitude": 52.xxx,
  "longitude": 6.xxx
}
```

**Installatie:**
- Zolder: Draait op localhost, STATION=zolder
- Berging: Draait op localhost, STATION=berging

## 4. MQTT Failover

**Service:** `mqtt-failover.timer` (elke 5 minuten)

Automatische health check en recovery:
1. Check Mosquitto status op beide Pi's
2. Check bridge connecties via MQTT topics
3. Na 3 opeenvolgende fouten: automatische restart
4. Email alert bij problemen (1 uur cooldown)
5. Minimaal 15 minuten tussen restarts

**Acties:**
- Restart Mosquitto bij service down
- Restart beide services bij bridge problemen
- Email notificatie bij issues

## Nieuwe Bestanden

### Config (repo)
| Bestand | Beschrijving |
|---------|--------------|
| `config/mosquitto-bridge-zolder.conf` | Zolder → Berging bridge |
| `config/mosquitto-bridge-berging.conf` | Berging → Zolder bridge |
| `config/mosquitto-listener-berging.conf` | Berging remote listener |

### Scripts
| Bestand | Beschrijving |
|---------|--------------|
| `scripts/mqtt/bridge_monitor.py` | Continu bridge monitoring |
| `scripts/mqtt/birdnet_mqtt_publisher.py` | BirdNET → MQTT |
| `scripts/mqtt/mqtt_failover.py` | Health check en recovery |

### Systemd
| Bestand | Type | Beschrijving |
|---------|------|--------------|
| `mqtt-bridge-monitor.service` | service | Continu monitoring |
| `birdnet-mqtt-publisher.service` | service | BirdNET publishing |
| `mqtt-failover.service` | oneshot | Health check |
| `mqtt-failover.timer` | timer | Elke 5 min |

## Geïnstalleerde Pakketten

- `paho-mqtt` - MQTT client library (beide Pi's)

## Verificatie

```bash
# Check bridge status
mosquitto_sub -h localhost -u ecomonitor -P REDACTED_DB_PASS \
  -t 'emsn2/bridge/#' -W 3 -v

# Check BirdNET detecties
mosquitto_sub -h localhost -u ecomonitor -P REDACTED_DB_PASS \
  -t 'birdnet/+/detection' -v

# Check services
systemctl status mqtt-bridge-monitor
systemctl status birdnet-mqtt-publisher
systemctl list-timers mqtt-failover.timer
```

## Test Resultaten

- ✅ Bidirectionele bridge werkt
- ✅ Bridge monitor ontvangt status updates
- ✅ BirdNET publisher publiceert detecties
- ✅ Failover check detecteert status correct
- ✅ Email alerts worden verzonden

---
*Gegenereerd door Claude Code sessie*
