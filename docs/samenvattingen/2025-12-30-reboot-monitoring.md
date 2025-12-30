# Sessie 2025-12-30: Reboot Monitoring & Watchdog

## Aanleiding
VS Code Remote-SSH verbinding met zolder Pi viel weg. Onderzoek toonde aan dat de Pi was gereboot.

## Bevindingen

### Crash Analyse
- **Zolder Pi:** Watchdog reset gedetecteerd (systeem was vastgelopen)
- **Berging Pi:** Ook watchdog reset (mogelijk zelfde oorzaak)
- **Meteo Pi:** Draaide 33 dagen stabiel, OOM killer was ooit actief

De gelijktijdige crash van zolder en berging suggereert mogelijk:
- Stroomonderbreking
- Kernel issue
- Of toevallige samenloop

## Geïmplementeerd

### 1. Hardware Watchdog Configuratie
**Bestand:** `/etc/systemd/system.conf.d/watchdog.conf`

Systemd stuurt nu heartbeats naar de BCM2835 hardware watchdog:
- Timeout: 60 seconden
- Bij freeze: automatische reboot
- Geïnstalleerd op alle 3 Pi's

### 2. Reboot Alert Service
**Script:** `/home/ronny/emsn2/scripts/monitoring/reboot_alert.py`
**Service:** `/etc/systemd/system/reboot-alert.service`

Functionaliteit:
- Draait automatisch bij elke boot (oneshot)
- Detecteert type shutdown:
  - `clean` - Normale shutdown/reboot
  - `watchdog` - Hardware watchdog timeout
  - `oom` - Out-of-Memory killer
  - `crash` - Kernel panic
  - `power` - Stroomonderbreking/undervoltage
- Stuurt MQTT alert naar broker
- Slaat state op voor vergelijking

### MQTT Topics
| Topic | Beschrijving |
|-------|--------------|
| `emsn2/zolder/reboot` | Zolder reboot info (retained) |
| `emsn2/berging/reboot` | Berging reboot info (retained) |
| `emsn2/meteo/reboot` | Meteo reboot info (retained) |
| `emsn2/alerts` | Algemene alerts |

### Geïnstalleerd Op
- [x] Pi Zolder (192.168.1.178)
- [x] Pi Berging (192.168.1.87)
- [x] Pi Meteo (192.168.1.156)

## Documentatie Updates
- CLAUDE.md: Meteo Pi IP toegevoegd (192.168.1.156)
- CLAUDE.md: Nieuwe sectie "Reboot Monitoring & Watchdog"

## Voorbeeld MQTT Output
```json
{
  "timestamp": "2025-12-30T22:40:59.561552",
  "hostname": "emsn2-zolder",
  "reason": "Hardware watchdog timeout (systeem vastgelopen)",
  "shutdown_type": "watchdog",
  "details": {
    "kernel_panic": false,
    "oom_killer": false,
    "watchdog_reset": true,
    "power_loss": false
  }
}
```

## Volgende Stappen (optioneel)
- Home Assistant automation voor reboot alerts
- Grafana dashboard met reboot historie
- Onderzoek naar oorzaak gelijktijdige crash zolder/berging
