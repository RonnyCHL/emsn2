# Sessie Samenvatting - 9 januari 2026

## Nestkast Species Detectie & Database Permissies

### Wijzigingen

#### 1. Species Detectie - Koolmees
- Detector aangepast: bij "bezet" wordt nu automatisch "Koolmees" ingevuld
- Bestand: `scripts/nestbox/nestbox_realtime_detector.py`
- Reden: alle huidige bezette beelden zijn 100% Koolmees
- Later uitbreiden naar multi-class model voor andere soorten

#### 2. Database Permissie Fix
**Probleem:** Detecties stopten om 16:50 door "permission denied" error.

**Oorzaak:**
- Scripts verbinden als `birdpi_zolder`, niet als `postgres`
- Na tabel recreatie/migratie gaan GRANT permissies verloren

**Oplossing:**
- Permissies handmatig hersteld voor `birdpi_zolder`
- Automatisch herstel script gemaakt

#### 3. Automatische Permissie Herstel
Nieuwe dagelijkse timer die permissies controleert en herstelt:

| Bestand | Beschrijving |
|---------|--------------|
| `scripts/db/ensure_permissions.py` | Herstel script voor alle users |
| `systemd/db-permissions.service` | Systemd service |
| `systemd/db-permissions.timer` | Dagelijkse timer (05:00) |

**Users en rechten:**
- `birdpi_zolder` - Full access (Pi Zolder)
- `birdpi_berging` - Read + write detecties
- `meteopi` - Read + write weather
- `emsn_readonly` - Read only (Grafana)
- `emsn_admin` - Full access (admin tools)

#### 4. Nieuwe Skill: /fix-db-permissions
- Locatie: `.claude/skills/fix-db-permissions/SKILL.md`
- Gebruik bij "permission denied" errors
- Bevat quick fix commando's en troubleshooting

#### 5. CLAUDE.md Update
- Nieuwe sectie "Database Permissies" toegevoegd
- Users en rechten tabel
- Geleerde les over permissies na migraties

### Actieve Timers op Zolder

| Timer | Interval | Beschrijving |
|-------|----------|--------------|
| `nestbox-screenshot.timer` | Elke 5 min | Screenshots maken |
| `nestbox-cleanup.timer` | Dagelijks 04:00 | Oude lege beelden opruimen |
| `db-permissions.timer` | Dagelijks 05:00 | Permissies controleren |

### Database Fix
Event in `nestbox_events` geüpdatet: `species = 'bezet'` → `species = 'Koolmees'`

### Status
- Dashboard toont nu correct "Koolmees" als soort
- Detecties werken weer (permissie probleem opgelost)
- Automatische permissie controle actief
