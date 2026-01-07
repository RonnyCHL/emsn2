---
name: mqtt-debug
description: Debug MQTT communicatie tussen stations. Toont live berichten, test connectivity en bridge status.
allowed-tools: Bash
---

# MQTT Debugging

## Wanneer Gebruiken

- Bij problemen met detectie notificaties
- Voor bridge troubleshooting
- Om data flow te verifiëren

## Live MQTT Monitor

### Alle EMSN Topics

```bash
mosquitto_sub -h 192.168.1.178 -t 'emsn2/#' -v
```

### BirdNET Detecties

```bash
# Alle detecties (beide stations)
mosquitto_sub -h 192.168.1.178 -t 'birdnet/+/detection' -v

# Alleen zolder
mosquitto_sub -h 192.168.1.178 -t 'birdnet/zolder/detection' -v

# Alleen berging
mosquitto_sub -h 192.168.1.178 -t 'birdnet/berging/detection' -v
```

### Bridge Status

```bash
mosquitto_sub -h 192.168.1.178 -t 'emsn2/bridge/#' -v
```

## Connectivity Tests

### Broker Bereikbaar?

```bash
# Quick test - wacht max 5 sec op bericht
mosquitto_sub -h 192.168.1.178 -t '$SYS/broker/uptime' -C 1 -W 5

# Publish test bericht
mosquitto_pub -h 192.168.1.178 -t 'test/claude' -m "test $(date)"
mosquitto_sub -h 192.168.1.178 -t 'test/claude' -C 1 -W 5
```

### Bridge Werkt?

```bash
# Publish op berging, ontvang op zolder
ssh ronny@192.168.1.87 'mosquitto_pub -h localhost -t "test/bridge" -m "from berging"'
mosquitto_sub -h 192.168.1.178 -t 'test/bridge' -C 1 -W 10
```

## Service Status

```bash
# Mosquitto broker (zolder)
ssh ronny@192.168.1.178 'systemctl status mosquitto --no-pager'

# MQTT publisher services
ssh ronny@192.168.1.178 'systemctl status birdnet-mqtt-publisher --no-pager'
ssh ronny@192.168.1.87 'systemctl status birdnet-mqtt-publisher --no-pager'

# Bridge monitor
ssh ronny@192.168.1.178 'systemctl status mqtt-bridge-monitor --no-pager'
```

## Mosquitto Logs

```bash
# Broker logs (zolder)
ssh ronny@192.168.1.178 'journalctl -u mosquitto -n 50 --no-pager'

# Bridge connectie logs
ssh ronny@192.168.1.87 'journalctl -u mosquitto -n 50 --no-pager | grep -i bridge'
```

## MQTT Topics Overzicht

| Topic | Bron | Inhoud |
|-------|------|--------|
| `birdnet/{station}/detection` | Pi's | Live detecties |
| `birdnet/{station}/stats` | Pi's | Dagelijkse stats |
| `emsn2/{station}/reboot` | Pi's | Reboot alerts (retained) |
| `emsn2/bridge/status` | Zolder | Bridge health |
| `emsn2/alerts` | Alle | Algemene alerts |

## Veelvoorkomende Problemen

| Probleem | Check | Oplossing |
|----------|-------|-----------|
| Geen berichten | `systemctl status mosquitto` | Restart broker |
| Bridge down | Berging logs | Check netwerk, restart mosquitto |
| Publisher stopt | Service logs | Check BirdNET-Pi database |
| Hoge latency | Network test | Check WiFi signaal |

## Configuratie Bestanden

- **Zolder broker:** `/etc/mosquitto/mosquitto.conf`
- **Berging bridge:** `/etc/mosquitto/conf.d/bridge.conf`
- **EMSN config:** `/home/ronny/emsn2/config/mosquitto-*.conf`
