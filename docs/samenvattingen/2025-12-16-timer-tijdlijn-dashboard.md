# Sessie Samenvatting: Timer Tijdlijn Dashboard

**Datum:** 2025-12-16
**Focus:** Realtime Timer Tijdlijn Dashboard + Systeemonderhoud

---

## Wat is er gedaan

### 1. System Inventory v1.2.0 - Nieuwe Componenten Detectie
- **Bestand:** `/home/ronny/emsn2/scripts/system_inventory.py`
- Toegevoegd: state file tracking (`.inventory_state.json`)
- Nieuwe functies: `load_state()`, `save_state()`, `detect_new_components()`, `build_current_state()`
- Rapport toont nu "Nieuwe Componenten Sinds Vorige Run" sectie
- Vergelijkt services, timers, scripts, en database tabellen met vorige inventarisatie

### 2. Log Rotatie Uitgebreid
- **Bestand:** `/home/ronny/emsn2/config/emsn-logs.logrotate`
- Toegevoegd: BirdNET MQTT publisher logs (was 35MB!)
- Toegevoegd: Ulanzi bridge, dual detection, cooldown display, screenshot server logs
- Geforceerd geroteerd: logs nu van 35MB naar 0 bytes

### 3. Berging Git Sync
- 7 uncommitted files opgelost
- Lokale wijzigingen gebackupt naar `/tmp/berging-backup`
- 173 nieuwe bestanden gesynchroniseerd van origin
- Station-specifieke changes hersteld

### 4. Timer Tijdlijn Dashboard (Nieuw!)

**Doel:** Realtime overzicht van alle EMSN systemd timers in Grafana

**Componenten:**
- **Python script:** `/home/ronny/emsn2/scripts/timer_timeline.py`
  - Verzamelt timer data via `systemctl list-timers --all --output=json`
  - Categoriseert timers (rapporten, mqtt, anomaly, ulanzi, etc.)
  - Slaat op in PostgreSQL elke minuut

- **Database migratie:** `/home/ronny/emsn2/database/migrations/015_timer_timeline.sql`
  - Tabel: `timer_timeline`
  - View: `timer_timeline_current` (meest recente data per timer)

- **Systemd timer:** `/home/ronny/emsn2/systemd/timer-timeline.timer`
  - Draait elke minuut (`OnCalendar=*-*-* *:*:00`)
  - Service: `timer-timeline.service`

- **Grafana dashboard:** `/home/ronny/emsn2/grafana/emsn-timer-timeline.json`
  - UID: `emsn-timer-timeline`
  - Auto-refresh: 10 seconden
  - Panels:
    - Timer Status Overzicht (stats)
    - Timers per Categorie (pie chart)
    - Komende 2 uur tabel met countdown gauge
    - Tijdlijn bar gauge (seconden tot uitvoering)
    - Recent uitgevoerd tabel
    - Gepland (na 6 uur) tabel

- **Homer link:** Toegevoegd aan `/mnt/nas-docker/homer/config.yml`

---

## Technische Lessen Geleerd

### 1. Synology NAS Docker Commands
```bash
# Docker binary locatie op Synology DSM:
/var/packages/ContainerManager/target/usr/bin/docker

# Container herstarten via SSH:
sshpass -p 'PASSWORD' ssh ronny@192.168.1.25 \
  "echo 'PASSWORD' | sudo -S /var/packages/ContainerManager/target/usr/bin/docker restart homer"
```

### 2. PostgreSQL Permissies
- `birdpi_zolder` user kan geen tabellen aanmaken
- Migraties moeten als `postgres` user uitgevoerd worden:
```bash
PGPASSWORD='...' psql -h 192.168.1.25 -p 5433 -U postgres -d emsn -f migration.sql
```

### 3. Systemd Timer JSON Output
```bash
# Nieuwe feature in systemd - JSON output!
systemctl list-timers --all --output=json

# Output bevat:
# - "next" en "last" als microseconden sinds epoch
# - "left" en "passed" als microseconden duration
# - "unit" en "activates" voor timer/service namen
```

### 4. Grafana Datasource UID
- Let op: datasource UID is `emsn_postgres` (underscore), niet `emsn-postgres` (dash)
- Check met: `curl http://192.168.1.25:3000/api/datasources`

### 5. Homer Config Reload
- Homer cached de config.yml
- Container moet herstart worden voor wijzigingen
- Alleen `touch` van config is niet voldoende

---

## Database Schema

```sql
CREATE TABLE timer_timeline (
    id SERIAL PRIMARY KEY,
    recorded_at TIMESTAMPTZ DEFAULT NOW(),
    timer_name VARCHAR(100) NOT NULL,
    timer_unit VARCHAR(120),
    service_name VARCHAR(120),
    next_run TIMESTAMPTZ,
    last_run TIMESTAMPTZ,
    time_until_next INTERVAL,
    time_since_last INTERVAL,
    station VARCHAR(50) DEFAULT 'zolder',
    is_emsn_timer BOOLEAN DEFAULT FALSE,
    category VARCHAR(50)
);

CREATE INDEX idx_timer_timeline_recorded ON timer_timeline(recorded_at DESC);
CREATE INDEX idx_timer_timeline_station ON timer_timeline(station);
CREATE INDEX idx_timer_timeline_emsn ON timer_timeline(is_emsn_timer);

-- View voor meest recente data:
CREATE VIEW timer_timeline_current AS
SELECT ...
FROM timer_timeline
WHERE recorded_at = (SELECT MAX(recorded_at) FROM timer_timeline WHERE station = t.station);
```

---

## Timer Categorien

| Categorie | Patterns |
|-----------|----------|
| rapporten | report, seasonal |
| mqtt | mqtt, bridge |
| anomaly | anomaly, baseline |
| ulanzi | ulanzi, screenshot |
| flysafe | flysafe, radar |
| atmosbird | atmosbird |
| monitoring | hardware, health |
| sync | sync, mirror, lifetime |
| maintenance | backup, cleanup |
| inventaris | inventory |
| system | (default) |

---

## URLs

- **Timer Tijdlijn Dashboard:** http://192.168.1.25:3000/d/emsn-timer-timeline/emsn-timer-tijdlijn
- **Homer Dashboard:** http://192.168.1.25:8181/
- **Timer service status:** `systemctl status timer-timeline.timer`

---

## Volgende Stappen (Optioneel)

1. Berging Pi ook timer data laten verzamelen
2. Alerting toevoegen voor gemiste timer runs
3. Historische analyse van timer execution patterns
