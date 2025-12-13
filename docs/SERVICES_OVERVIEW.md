# EMSN 2.0 Services Overzicht

**Station:** emsn2-zolder (192.168.1.178)
**Laatste update:** 13 december 2025

---

## Actieve Services Status

### Continu Draaiende Services

| Service | Status | Functie |
|---------|--------|---------|
| `ulanzi-bridge.service` | **ACTIVE** | MQTT → Ulanzi TC001 notificaties |
| `hardware-metrics.service` | **ACTIVE** | System metrics naar PostgreSQL |
| `emsn-cooldown-display.service` | **ACTIVE** | Cooldown status naar Home Assistant |
| `emsn-reports-api.service` | **FAILED** | Flask API voor rapporten web interface |

### Timer-gestuurde Services

| Timer | Interval | Service | Laatste Run |
|-------|----------|---------|-------------|
| `lifetime-sync.timer` | 5 min | Sync detecties naar PostgreSQL | Actief |
| `hardware-monitor.timer` | 1 min | Hardware metrics collectie | Actief |
| `dual-detection.timer` | 5 min | Dual station detectie matching | Actief |
| `emsn-dbmirror-zolder.timer` | 5 min | SQLite backup naar USB | Actief |
| `anomaly-datagap-check.timer` | 15 min | Check data gaps | Actief |
| `anomaly-hardware-check.timer` | 15 min | Check hardware anomalies | Actief |
| `flysafe-radar-day.timer` | 2 uur (dag) | FlySafe radar scraping | Actief |
| `flysafe-radar-night.timer` | 2 uur (nacht) | FlySafe radar scraping | Actief |
| `backup-cleanup.timer` | Dagelijks 04:00 | Oude backups verwijderen | Actief |
| `rarity-cache.timer` | Dagelijks 04:00 | Zeldzaamheid cache refresh | **INACTIVE** |
| `anomaly-baseline-learn.timer` | Zondag 03:00 | Species baselines leren | Gepland |
| `emsn-weekly-report.timer` | Maandag 07:00 | AI weekrapport genereren | Gepland |
| `emsn-monthly-report.timer` | 1e v/d maand 08:00 | AI maandrapport genereren | Gepland |

---

## Services per Module

### Sync Module
```
lifetime-sync.service      - SQLite → PostgreSQL sync
lifetime-sync.timer        - Elke 5 minuten

hardware-monitor.service   - Hardware metrics collectie
hardware-monitor.timer     - Elke minuut

dual-detection.service     - Dual station matching
dual-detection.timer       - Elke 5 minuten

emsn-dbmirror-zolder.service - SQLite backup
emsn-dbmirror-zolder.timer   - Elke 5 minuten
```

### Ulanzi Module
```
ulanzi-bridge.service         - MQTT listener (continu)
rarity-cache.service          - Cache refresh
rarity-cache.timer            - Dagelijks 04:00
emsn-cooldown-display.service - HA cooldown publisher (continu)
```

### FlySafe Module
```
flysafe-radar.service      - Radar scraper
flysafe-radar-day.timer    - 08:00-20:00, elke 2 uur
flysafe-radar-night.timer  - 20:00-08:00, elke 2 uur
```

### Anomaly Module
```
anomaly-baseline-learn.service - Weekly baseline learning
anomaly-baseline-learn.timer   - Zondag 03:00

anomaly-datagap-check.service  - Data gap detection
anomaly-datagap-check.timer    - Elke 15 minuten

anomaly-hardware-check.service - Hardware issue detection
anomaly-hardware-check.timer   - Elke 15 minuten
```

### Reports Module
```
emsn-weekly-report.service  - AI weekrapport
emsn-weekly-report.timer    - Maandag 07:00

emsn-monthly-report.service - AI maandrapport
emsn-monthly-report.timer   - 1e van de maand 08:00

emsn-reports-api.service    - Flask web API (continu)
```

### AtmosBird Module (Berging station)
```
atmosbird-capture.service   - Sky foto capture
atmosbird-capture.timer     - Elke 10 minuten

atmosbird-analysis.service  - ISS/maan/meteoor analyse
atmosbird-analysis.timer    - Elk uur

atmosbird-timelapse.service - Dagelijkse timelapse
atmosbird-timelapse.timer   - Dagelijks 06:00
```

### Overige
```
backup-cleanup.service - Oude backup cleanup
backup-cleanup.timer   - Dagelijks 04:00

hardware-metrics.service - Metrics collector (continu)
```

---

## Handige Commando's

### Status Bekijken
```bash
# Alle EMSN timers
systemctl list-timers | grep -E "(emsn|atmosbird|flysafe|ulanzi|anomaly|dual|lifetime|hardware|backup|rarity)"

# Alle EMSN services
systemctl list-units --type=service | grep -E "(emsn|atmosbird|flysafe|ulanzi|anomaly|dual|lifetime|hardware|backup|rarity)"

# Specifieke service status
systemctl status ulanzi-bridge.service
```

### Logs Bekijken
```bash
# Realtime logs van service
journalctl -u lifetime-sync.service -f

# Logs van vandaag
journalctl -u ulanzi-bridge.service --since today

# Alle EMSN logs
journalctl | grep -E "(emsn|ulanzi|flysafe|anomaly)"
```

### Service Beheer
```bash
# Herstart service
sudo systemctl restart ulanzi-bridge.service

# Handmatig timer triggeren
sudo systemctl start lifetime-sync.service

# Service enablen/disablen
sudo systemctl enable anomaly-baseline-learn.timer
sudo systemctl disable anomaly-baseline-learn.timer
```

---

## Bekende Problemen

### emsn-reports-api.service - FAILED
**Status:** Auto-restart loop
**Oorzaak:** Waarschijnlijk ontbrekende dependencies of port conflict
**Fix:**
```bash
journalctl -u emsn-reports-api.service -n 50
```

### emsn-monthly-report.service - FAILED
**Status:** Failed
**Oorzaak:** Mogelijk geen data voor huidige maand
**Fix:** Wacht tot einde maand of test handmatig

### rarity-cache.timer - INACTIVE
**Status:** Timer niet actief
**Fix:**
```bash
sudo systemctl enable --now rarity-cache.timer
```

---

## Service Bestanden Locaties

| Bron | Doel |
|------|------|
| `/home/ronny/emsn2/systemd/*.service` | Kopieer naar `/etc/systemd/system/` |
| `/home/ronny/emsn2/systemd/*.timer` | Kopieer naar `/etc/systemd/system/` |

**Installatie nieuwe service:**
```bash
sudo cp /home/ronny/emsn2/systemd/NEW.service /etc/systemd/system/
sudo cp /home/ronny/emsn2/systemd/NEW.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now NEW.timer
```

---

## Architectuur Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         EMSN 2.0 Zolder                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │ BirdNET-Pi   │    │   MQTT       │    │  PostgreSQL  │      │
│  │ (SQLite)     │───▶│  Broker      │───▶│  (NAS)       │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│         │                   │                   ▲               │
│         │                   │                   │               │
│         ▼                   ▼                   │               │
│  ┌──────────────┐    ┌──────────────┐          │               │
│  │ lifetime-    │    │ ulanzi-      │          │               │
│  │ sync.service │────│ bridge       │──────────┘               │
│  └──────────────┘    └──────────────┘                          │
│         │                   │                                   │
│         │                   ▼                                   │
│         │            ┌──────────────┐                          │
│         │            │ Ulanzi TC001 │                          │
│         │            │ Display      │                          │
│         │            └──────────────┘                          │
│         │                                                       │
│         ▼                                                       │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │ dual-        │    │ anomaly-     │    │ flysafe-     │      │
│  │ detection    │    │ checkers     │    │ radar        │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

*Gegenereerd door Claude Code - 13 december 2025*
