# Sessie Samenvatting: Homer Color Picker + Live Stats

**Datum:** 2026-01-09 (avond)
**Focus:** Homer dashboard verbeteringen

## Wat is gedaan

### 1. Homer Color Picker
- **Wrapper HTML pagina** gemaakt (`/mnt/nas-docker/homer/assets/index.html`)
- Homer draait in iframe, color picker overlay erbuiten (bypass Homer's sanitization)
- **8 preset kleuren:** Natuur, Oceaan, Sunset, Paars, Grijs, Roze, Teal, Goud
- Custom kleur picker met HSL conversie voor automatisch kleurenschema
- Persistent via localStorage
- **Elementen die meekleuren:**
  - Header/navbar
  - Message box (status balk)
  - Section titel iconen
  - Card iconen
  - Links en hover effecten
  - Card hover borders

### 2. Homer Live Stats Update
- **Script:** `scripts/homer/update_homer_stats.py`
- Haalt live data uit PostgreSQL:
  - Totaal detecties (geformatteerd als "125k+")
  - Unieke soorten
  - Database grootte
  - Vandaag detecties
  - Top soort van vandaag
  - Station online status (zolder/berging)
- **Timer:** elke 5 minuten (via systemd)
- Status balk kleurt groen/geel/rood op basis van station status

### 3. Grafana Error Dashboard (eerder in sessie)
- Fixed `disk_usage_root` → `disk_usage` column naam
- Removed non-existent `sync_log` table queries
- Added complete Meteo section:
  - Temperatuur, humidity, pressure stats
  - Wind speed, rain, solar radiation
  - Time series graphs

## Bestanden

### Nieuw
- `scripts/homer/update_homer_stats.py` - Live stats naar Homer config
- `systemd/homer-stats-update.service` - Systemd service
- `systemd/homer-stats-update.timer` - 5 minuten interval

### Op NAS (niet in git)
- `/mnt/nas-docker/homer/assets/index.html` - Wrapper met color picker
- `/mnt/nas-docker/homer/assets/custom.css` - Color picker styling
- `/mnt/nas-docker/homer/assets/custom.js` - Originele JS (nu via index.html)

## Services Status
```bash
# Timer actief
sudo systemctl status homer-stats-update.timer

# Handmatig triggeren
sudo systemctl start homer-stats-update.service
```

## URLs
- Homer Dashboard: http://192.168.1.25:8181/assets/index.html
- Direct Homer (zonder color picker): http://192.168.1.25:8181/?standalone=true

## Git
- Commit: `441a6e8` - feat: Homer live stats update + color picker support
