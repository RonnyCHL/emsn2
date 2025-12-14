# Sessie Samenvatting: MQTT Bridge Configuratie

**Datum:** 14 december 2025
**Type:** MQTT infrastructuur uitbreiding

## Uitgevoerd

### MQTT Bridge Berging → Zolder

Berging Pi geconfigureerd als MQTT bridge naar de hoofdbroker op Zolder.

**Configuratie:** `/etc/mosquitto/conf.d/bridge-zolder.conf` op Berging

```
connection bridge-to-zolder
address 192.168.1.178:1883
remote_username ecomonitor
remote_password REDACTED_DB_PASS

# Berging → Zolder
topic emsn2/berging/# out 1
topic birdnet/berging/# out 1

# Zolder → Berging
topic emsn2/zolder/# in 1
topic birdnet/zolder/# in 1
```

### Werking

| Richting | Topics | Beschrijving |
|----------|--------|--------------|
| Berging → Zolder | emsn2/berging/# | Health metrics, sync stats, detecties |
| Berging → Zolder | birdnet/berging/# | BirdNET detectie events |
| Zolder → Berging | emsn2/zolder/# | Zolder data beschikbaar op Berging |

### Test Resultaat

```
emsn2/berging/test Bridge test 16:00:04
```

Messages van Berging komen direct door op Zolder broker.

## Voordelen

1. **Gecentraliseerde data** - Alle MQTT data beschikbaar op Zolder
2. **Redundantie** - Als Zolder tijdelijk down is, buffert Berging messages
3. **Monitoring** - Ulanzi en andere subscribers krijgen data van beide stations
4. **Schaalbaarheid** - Makkelijk extra stations toevoegen

## Bestanden

| Bestand | Locatie |
|---------|---------|
| Bridge config (repo) | /home/ronny/emsn2/config/mosquitto-bridge-berging.conf |
| Bridge config (actief) | Berging: /etc/mosquitto/conf.d/bridge-zolder.conf |
| CLAUDE.md | Bijgewerkt met MQTT sectie |

## MQTT Architectuur

```
┌─────────────────┐      ┌─────────────────┐
│   Pi Berging    │      │   Pi Zolder     │
│  192.168.1.87   │      │  192.168.1.178  │
│                 │      │                 │
│  ┌───────────┐  │      │  ┌───────────┐  │
│  │ Mosquitto │──┼──────┼─▶│ Mosquitto │  │
│  │  (bridge) │  │      │  │  (hoofd)  │  │
│  └───────────┘  │      │  └───────────┘  │
│       ▲         │      │       │         │
│       │         │      │       ▼         │
│  BirdNET-Pi     │      │  - Ulanzi       │
│  AtmosBird      │      │  - Subscribers  │
│  Health mon.    │      │  - BirdNET-Pi   │
└─────────────────┘      └─────────────────┘
```

---
*Gegenereerd door Claude Code sessie*
