# Sessie Samenvatting: Ulanzi Dashboard Uitbreidingen

**Datum:** 14 december 2025
**Type:** Ulanzi display monitoring uitbreidingen

## Overzicht

Uitgebreide Ulanzi monitoring met live preview, screenshot server, smart cooldowns, en Home Assistant integratie.

## 1. Screenshot Server Uitbreiding

De screenshot server (`screenshot_server.py`) is uitgebreid met nieuwe endpoints:

| Endpoint | Beschrijving |
|----------|--------------|
| `/latest` | Laatste screenshot (PNG) |
| `/latest.json` | Info over laatste screenshot (JSON) |
| `/live` | Live screenshot direct van Ulanzi |
| `/status` | Server status en statistieken |

**URL:** http://192.168.1.178:8082

### Live Screenshot
De `/live` endpoint maakt direct een screenshot van de Ulanzi display via de `/api/screen` endpoint en schaalt deze 10x op voor leesbaarheid.

## 2. Grafana Dashboard Updates

Dashboard URL: http://192.168.1.25:3000/d/emsn-ulanzi-notifications/

### Nieuwe Panels

| Panel | Beschrijving |
|-------|--------------|
| Live Preview | Actuele Ulanzi display (auto-refresh 5s) |
| Quick Links | Buttons naar Screenshot Archief, Server Status, Ulanzi Web UI |
| Statistieken per Soort | Getoond/Overgeslagen ratio per soort (7 dagen) |
| Screenshot Galerij | Visuele preview van recente screenshots |
| Notificatie Heatmap | Heatmap van notificaties per soort per uur (7 dagen) |

### Verbeterde Panels

- **Actieve Cooldowns** - Nu met progress bars en HH:MM:SS format
- Dashboard refresh: 5 seconden (was 30s)

## 3. Screenshot Cleanup Job

**Service:** `screenshot-cleanup.service`
**Timer:** `screenshot-cleanup.timer` (dagelijks om 03:00)

Functionaliteit:
- Verwijdert screenshots ouder dan 30 dagen
- Ruimt database records op
- Verwijdert orphaned records (files die niet meer bestaan)
- Logging naar `/mnt/usb/logs/screenshot-cleanup.log`

## 4. Smart Cooldown System

Dynamische cooldown aanpassing op basis van:

### Tijd van de dag
| Periode | Uur | Multiplier |
|---------|-----|------------|
| Dawn | 05:00-08:00 | 0.5x (halve cooldown) |
| Morning | 08:00-12:00 | 0.75x |
| Afternoon | 12:00-17:00 | 1.0x (normaal) |
| Evening | 17:00-20:00 | 0.75x |
| Night | 20:00-05:00 | 1.5x (langere cooldown) |

### Seizoen
| Seizoen | Maanden | Multiplier |
|---------|---------|------------|
| Spring | Mar-Mei | 0.7x (broedseizoen/trek) |
| Summer | Jun-Aug | 0.9x |
| Autumn | Sep-Nov | 0.7x (herfsttrek) |
| Winter | Dec-Feb | 1.2x (minder activiteit) |

### Weekend
- Weekend: 0.8x (kortere cooldown)

### Voorbeeld
Zondagavond in december:
- Base cooldown: 3600s (common tier)
- Evening: × 0.75
- Winter: × 1.2
- Weekend: × 0.8
- **Resultaat:** 3600 × 0.75 × 1.2 × 0.8 = 2592s (~43 min)

## 5. MQTT Cooldown Publisher

**Service:** `mqtt-cooldown-publisher.service`

Publiceert elke minuut:

| Topic | Inhoud |
|-------|--------|
| `emsn2/ulanzi/cooldowns/count` | Aantal actieve cooldowns |
| `emsn2/ulanzi/cooldowns/status` | Volledige cooldown status (JSON) |
| `emsn2/ulanzi/stats/today` | Dagstatistieken |
| `emsn2/ulanzi/smart_cooldown` | Huidige smart cooldown multipliers |

## 6. Home Assistant Integratie

Configuratie: `/home/ronny/emsn2/config/homeassistant/ulanzi_sensors.yaml`

### Sensors
- Ulanzi Cooldowns Active
- Ulanzi Notifications Today
- Ulanzi Skipped Today
- Ulanzi Species Today
- Ulanzi Screenshots Today
- Ulanzi Show Ratio
- Ulanzi Last Species
- Ulanzi Time Period
- Ulanzi Season
- Ulanzi Cooldown Multiplier

## Nieuwe Bestanden

### Scripts
| Bestand | Beschrijving |
|---------|--------------|
| `scripts/ulanzi/screenshot_server.py` | Uitgebreide screenshot server |
| `scripts/ulanzi/screenshot_cleanup.py` | Cleanup script voor oude screenshots |
| `scripts/ulanzi/mqtt_cooldown_publisher.py` | MQTT publisher voor HA integratie |

### Systemd
| Bestand | Type | Beschrijving |
|---------|------|--------------|
| `screenshot-cleanup.service` | oneshot | Cleanup job |
| `screenshot-cleanup.timer` | timer | Dagelijks 03:00 |
| `mqtt-cooldown-publisher.service` | service | MQTT publisher |

### Config
| Bestand | Beschrijving |
|---------|--------------|
| `config/ulanzi_config.py` | Smart cooldown configuratie toegevoegd |
| `config/grafana/ulanzi-notifications-dashboard.json` | Bijgewerkt dashboard |
| `config/homeassistant/ulanzi_sensors.yaml` | HA sensor configuratie |

## Service Status

```bash
# Check services
systemctl status ulanzi-screenshot-server
systemctl status mqtt-cooldown-publisher
systemctl list-timers screenshot-cleanup.timer

# Test endpoints
curl http://192.168.1.178:8082/status
curl http://192.168.1.178:8082/latest.json

# Test MQTT
mosquitto_sub -h localhost -u ecomonitor -P REDACTED_DB_PASS \
  -t 'emsn2/ulanzi/#' -v
```

## Verificatie

- ✅ Screenshot server endpoints werken
- ✅ Live preview toont actuele Ulanzi display
- ✅ Cleanup timer geïnstalleerd
- ✅ Smart cooldown actief (huidige multiplier: 0.72x)
- ✅ MQTT data wordt gepubliceerd
- ✅ Home Assistant sensor configuratie klaar

---
*Gegenereerd door Claude Code sessie*
