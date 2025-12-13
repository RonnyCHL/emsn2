# EMSN 2.0 Opschoon Handleiding

**Datum:** 13 december 2025
**Status:** Voorstel - nog niet uitgevoerd

---

## 1. Duplicaat Analyse

### 1.1 Sync Scripts - DRIE Locaties!

| Locatie | Status | Gebruikt door |
|---------|--------|---------------|
| `/home/ronny/sync/` | **ACTIEF** | systemd services |
| `/home/ronny/emsn2/sync/` | Verouderd | Niets |
| `/home/ronny/emsn2/scripts/sync/` | Nieuwste code | Niets (nog) |

**Verschillen gevonden:**

| Bestand | `/home/ronny/sync/` | `emsn2/sync/` | `emsn2/scripts/sync/` |
|---------|---------------------|---------------|----------------------|
| `lifetime_sync.py` | Basis versie | Basis versie | **+110 regels** bi-directional sync, deletions |
| `hardware_monitor.py` | Aanwezig | Aanwezig | Aanwezig (identiek) |
| `weather_sync.py` | - | Aanwezig | - |
| `bayesian_verification.py` | - | - | Aanwezig |
| `dual_detection_sync.py` | - | - | Aanwezig |
| `__init__.py` | - | Aanwezig | Aanwezig |

**Conclusie:** `scripts/sync/lifetime_sync.py` bevat belangrijke updates (bi-directional sync, deletion support) die nog niet actief zijn!

### 1.2 Services Mappen

| Map | Inhoud | Status |
|-----|--------|--------|
| `emsn2/services/` | 4 oude db-mirror services | **Te verwijderen** |
| `emsn2/systemd/` | 34 service/timer files | **Actief** |

De `services/` map bevat alleen `emsn-dbmirror-*` files die al in `/etc/systemd/system/` staan.

---

## 2. Aanbevolen Acties

### Fase 1: Consolideer Sync Scripts

```bash
# 1. Backup maken van actieve scripts
cp -r /home/ronny/sync /home/ronny/sync.backup.$(date +%Y%m%d)

# 2. Kopieer nieuwste versies naar actieve locatie
cp /home/ronny/emsn2/scripts/sync/lifetime_sync.py /home/ronny/sync/
cp /home/ronny/emsn2/scripts/sync/hardware_monitor.py /home/ronny/sync/
cp /home/ronny/emsn2/scripts/sync/bayesian_verification.py /home/ronny/sync/
cp /home/ronny/emsn2/scripts/sync/dual_detection_sync.py /home/ronny/sync/

# 3. Verwijder duplicate mappen in emsn2
rm -rf /home/ronny/emsn2/sync/

# 4. Test de services
sudo systemctl restart lifetime-sync.service
sudo journalctl -u lifetime-sync.service -f
```

### Fase 2: Opruimen Services Map

```bash
# Verwijder oude services map (al geinstalleerd via systemd/)
rm -rf /home/ronny/emsn2/services/
```

### Fase 3: Symlink Creeren (Optioneel)

Om `/home/ronny/sync/` binnen het git project te houden:

```bash
# Verplaats scripts naar emsn2
mv /home/ronny/sync/* /home/ronny/emsn2/scripts/sync/

# Maak symlink
ln -s /home/ronny/emsn2/scripts/sync /home/ronny/sync

# Update systemd services om direct naar emsn2 te verwijzen (beter):
# ExecStart=/usr/bin/python3 /home/ronny/emsn2/scripts/sync/lifetime_sync.py
```

---

## 3. Te Verwijderen Bestanden

### Zeker verwijderen:
- [ ] `/home/ronny/emsn2/sync/` - Duplicaat van scripts/sync (verouderd)
- [ ] `/home/ronny/emsn2/services/` - Duplicaat van systemd/ (verouderd)

### Na consolidatie verwijderen:
- [ ] `/home/ronny/sync/` - Als scripts naar emsn2 verplaatst zijn

### Te behouden:
- [x] `/home/ronny/emsn2/scripts/sync/` - Nieuwste code
- [x] `/home/ronny/emsn2/systemd/` - Alle service files

---

## 4. Systemd Services Update Nodig

De volgende services verwijzen naar `/home/ronny/sync/` maar moeten naar `/home/ronny/emsn2/scripts/sync/`:

| Service | Huidige ExecStart | Nieuwe ExecStart |
|---------|-------------------|------------------|
| `lifetime-sync.service` | `/home/ronny/sync/lifetime_sync.py` | `/home/ronny/emsn2/scripts/sync/lifetime_sync.py` |
| `hardware-monitor.service` | `/home/ronny/sync/hardware_monitor.py` | `/home/ronny/emsn2/scripts/sync/hardware_monitor.py` |

**Update commando's:**
```bash
sudo sed -i 's|/home/ronny/sync/|/home/ronny/emsn2/scripts/sync/|g' /etc/systemd/system/lifetime-sync.service
sudo sed -i 's|/home/ronny/sync/|/home/ronny/emsn2/scripts/sync/|g' /etc/systemd/system/hardware-monitor.service
sudo sed -i 's|WorkingDirectory=/home/ronny/sync|WorkingDirectory=/home/ronny/emsn2/scripts/sync|g' /etc/systemd/system/lifetime-sync.service
sudo sed -i 's|WorkingDirectory=/home/ronny/sync|WorkingDirectory=/home/ronny/emsn2/scripts/sync|g' /etc/systemd/system/hardware-monitor.service
sudo systemctl daemon-reload
```

---

## 5. Configuratie Consolidatie

### Hardcoded Wachtwoorden Gevonden In:

| Bestand | Wachtwoord |
|---------|------------|
| `config/ulanzi_config.py` | MQTT + PostgreSQL |
| `scripts/sync/*.py` | PostgreSQL |
| `scripts/flysafe/*.py` | PostgreSQL |
| `scripts/reports/*.py` | PostgreSQL + Anthropic API |

**Aanbeveling:** Verplaats naar environment variables of `.env` file:

```bash
# /home/ronny/emsn2/.env (niet in git!)
EMSN_DB_HOST=192.168.1.25
EMSN_DB_PORT=5433
EMSN_DB_NAME=emsn
EMSN_DB_USER=birdpi_zolder
EMSN_DB_PASSWORD=REDACTED_DB_PASS
MQTT_BROKER=192.168.1.178
MQTT_USER=ecomonitor
MQTT_PASSWORD=REDACTED_DB_PASS
ANTHROPIC_API_KEY=sk-ant-...
```

---

## 6. Checklist voor Opschonen

### Stap 1: Backup (VERPLICHT)
- [ ] `cp -r /home/ronny/sync /home/ronny/sync.backup`
- [ ] `cd /home/ronny/emsn2 && git stash` (indien uncommitted changes)

### Stap 2: Verwijder Duplicaten
- [ ] `rm -rf /home/ronny/emsn2/sync/`
- [ ] `rm -rf /home/ronny/emsn2/services/`

### Stap 3: Update Systemd Services
- [ ] Update `lifetime-sync.service` pad
- [ ] Update `hardware-monitor.service` pad
- [ ] `sudo systemctl daemon-reload`

### Stap 4: Test Services
- [ ] `sudo systemctl restart lifetime-sync && journalctl -u lifetime-sync -f`
- [ ] `sudo systemctl restart hardware-monitor && journalctl -u hardware-monitor -f`

### Stap 5: Verwijder oude /home/ronny/sync
- [ ] `rm -rf /home/ronny/sync/` (na succesvolle test)

### Stap 6: Git Commit
- [ ] `git add -A && git commit -m "chore: Cleanup duplicate sync and services folders"`

---

## 7. Risico's

| Risico | Impact | Mitigatie |
|--------|--------|-----------|
| Service stopt met werken | Hoog | Backup + test per service |
| Verkeerde versie actief | Medium | Diff check voor consolidatie |
| Git history verloren | Laag | Git mv gebruiken ipv rm/cp |

---

*Gegenereerd door Claude Code - 13 december 2025*
