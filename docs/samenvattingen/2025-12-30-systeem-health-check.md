# Sessie Samenvatting - 30 december 2025 (deel 2)

## Onderwerp
Systeem health check en failed services reparatie

## Overzicht
Na de database connection fix uit deel 1 is een grondige systeem health check uitgevoerd. Alle failed services zijn onderzocht en gerepareerd.

## Failed Services Gerepareerd

### 1. anomaly-baseline-learn.service
- **Probleem:** Network unreachable op 29 december (tijdens db problemen)
- **Actie:** Failed state gereset, timer actief (draait zondag 03:00)
- **Status:** Geen code wijziging nodig

### 2. emsn-dbmirror-zolder.service (ECHTE FIX)
- **Probleem:** Race condition bij database sync
  - Script las source count, kopieerde met shutil.copy2, vergeleek met mirror
  - BirdNET-Pi schrijft continu, dus source count veranderde tijdens kopie
  - Resultaat: ~50% van de runs faalde met "record count mismatch"

- **Root cause:** `shutil.copy2()` is geen atomic operatie voor SQLite databases

- **Oplossing:** SQLite backup API gebruiken
  ```python
  # OUD - race condition gevoelig
  shutil.copy2(SOURCE_DB, MIRROR_DB)

  # NIEUW - atomic, consistent snapshot
  source_conn = sqlite3.connect(SOURCE_DB)
  dest_conn = sqlite3.connect(MIRROR_DB)
  source_conn.backup(dest_conn)  # SQLite backup API
  ```

- **Bestand:** `scripts/database_mirror_sync.py`

### 3. sd-backup-cleanup.service (ECHTE FIX)
- **Probleem:** PermissionError bij itereren over daily backups
  - Daily backups bevatten volledige SD-kaart rsync (/, /etc, /usr, etc.)
  - Directories hebben root ownership met 700 permissies
  - `d.rglob('*')` faalde op onleesbare directories

- **Oplossing:** Error handling toegevoegd
  ```python
  def get_dir_size_safe(directory: Path) -> int:
      """Bereken directory grootte, negeer permission errors."""
      total = 0
      try:
          for f in directory.rglob('*'):
              try:
                  if f.is_file():
                      total += f.stat().st_size
              except (PermissionError, OSError):
                  continue
      except (PermissionError, OSError):
          pass
      return total
  ```

- **Bestand:** `scripts/backup/sd_backup_cleanup.py`
- **Gekopieerd naar:** berging

### 4. emsn-monthly-report.service
- **Probleem:** Failed op 29 december (netwerk/database onbereikbaar)
- **Actie:** Failed state gereset, handmatig getest - werkt correct
- **Status:** Geen code wijziging nodig

### 5. Berging services (sd-backup-cleanup, sd-backup-weekly)
- **Probleem:** Zelfde als zolder + netwerk issues op 28 december
- **Actie:**
  - Cleanup script gekopieerd van zolder
  - Failed states gereset
- **Status:** Timers actief

## Systeem Health Status

### Database
| Metric | Waarde |
|--------|--------|
| Connecties | 18 (max 100) |
| Idle in transaction | 0 |
| Detecties vandaag (zolder) | 904 |
| Detecties vandaag (berging) | 1089 |

### Disk Usage
| Systeem | / | /mnt/usb |
|---------|---|----------|
| Zolder | 17% | 2% |
| Berging | 19% | 21% |

### Services
- Alle failed services gereset
- Alle core services actief
- Alle timers draaien correct

## Bestanden Gewijzigd
- `scripts/database_mirror_sync.py` - SQLite backup API
- `scripts/backup/sd_backup_cleanup.py` - Permission error handling

## Geleerde Lessen

1. **SQLite kopieren tijdens actief gebruik:**
   - `shutil.copy2()` is niet safe voor databases met concurrent writes
   - Gebruik `sqlite3.Connection.backup()` voor atomic snapshots

2. **rsync full system backups:**
   - Bevatten directories met restrictieve permissies (root owned, 700)
   - Scripts die over deze backups itereren moeten permission errors afhandelen

## Verificatie Commando's
```bash
# Check geen failed services
systemctl --failed

# Check database connecties
psql -c "SELECT count(*) FROM pg_stat_activity WHERE state = 'idle in transaction';"

# Check recente detecties
psql -c "SELECT station, COUNT(*) FROM bird_detections WHERE date = CURRENT_DATE GROUP BY station;"
```
