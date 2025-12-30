# Sessie Samenvatting - 30 december 2025 (deel 3)

## Onderwerp
Database optimalisatie en lifetime-sync service fixes

## Overzicht
Voortzetting van de systeem health check met focus op database groei en service configuratie.

## Verbeteringen Doorgevoerd

### 1. ulanzi_notification_log Retentie Geoptimaliseerd
- **Analyse:** 1 miljoen records in 19 dagen (~52K/dag)
  - 855K burst_duplicate (85%)
  - 128K cooldown (13%)
  - 5K daadwerkelijk getoond (0.5%)

- **Probleem:** 30 dagen retentie voor 98% "niet-getoonde" notificaties is overkill

- **Oplossing:** Retentie van 30 naar 7 dagen
  ```python
  # OUD
  'ulanzi_notification_log': ('timestamp', 30),

  # NIEUW - 7 dagen voldoende voor analyse
  'ulanzi_notification_log': ('timestamp', 7),
  ```

- **Impact:**
  - Database grootte: 148MB → ~35MB (na 1 week)
  - Records: ~1M → ~364K max
  - 23K oude records direct verwijderd

- **Bestand:** `scripts/maintenance/database_cleanup.py`

### 2. lifetime-sync Service Fix (Berging)
- **Probleem 1:** Service miste `--station berging` argument
  - Nieuw script vereist station parameter
  - Oude service file niet geüpdatet bij kopiëren

- **Probleem 2:** `ProtectHome=read-only` blokkeerde SQLite toegang
  - SQLite maakt journal file aan, zelfs bij read-only
  - Service kon database niet openen

- **Oplossingen:**
  ```bash
  # ExecStart aangepast
  ExecStart=/usr/bin/python3 /home/ronny/sync/lifetime_sync.py --station berging

  # EnvironmentFile toegevoegd voor credentials
  EnvironmentFile=/home/ronny/.env

  # ProtectHome uitgeschakeld voor SQLite toegang
  ProtectHome=no
  ```

- **Locatie:** `/etc/systemd/system/lifetime-sync.service` (berging)

### 3. lifetime-sync Service Fix (Zolder)
- **Probleem:** Zelfde `ProtectHome=read-only` conflict
- **Oplossing:** `ProtectHome=no`
- **Locatie:** `/etc/systemd/system/lifetime-sync.service` (zolder)

## FK Constraint Volgorde in Cleanup
- `ulanzi_screenshots` → `ulanzi_notification_log` (FK relatie)
- Cleanup volgorde aangepast: child tables eerst
  ```python
  CLEANUP_CONFIG = {
      'ulanzi_screenshots': ('timestamp', 7),      # Child eerst
      'ulanzi_notification_log': ('timestamp', 7), # Dan parent
      # ...
  }
  ```

## Finale Status

### Database
| Metric | Waarde |
|--------|--------|
| Connecties | Normaal |
| Idle in transaction | 0-1 (tijdelijk) |
| ulanzi_notification_log | 979K records (7 dagen) |
| Dead tuples | Normaal (autovacuum actief) |

### Services
| Station | Failed Services |
|---------|-----------------|
| Zolder | 0 |
| Berging | 0 |

### Sync Status
| Station | SQLite | PostgreSQL | Status |
|---------|--------|------------|--------|
| Zolder | 35,221 | 35,221 | Synced |
| Berging | 70,190 | 70,190 | Synced |

## Bestanden Gewijzigd
- `scripts/maintenance/database_cleanup.py` - Retentie 30→7 dagen, FK volgorde
- `/etc/systemd/system/lifetime-sync.service` (zolder) - ProtectHome=no
- `/etc/systemd/system/lifetime-sync.service` (berging) - station arg, .env, ProtectHome=no

## Geleerde Lessen

1. **systemd ProtectHome en SQLite:**
   - `ProtectHome=read-only` blokkeert SQLite journal files
   - SQLite vereist write access voor locking, zelfs bij read-only queries
   - Oplossing: `ProtectHome=no` of ReadWritePaths naar SQLite directory

2. **Service files bij script updates:**
   - Bij kopiëren van nieuw script: check of ExecStart argumenten kloppen
   - Bij nieuwe env vars: voeg EnvironmentFile toe

3. **Database log tabellen:**
   - Log tabellen kunnen snel groeien
   - Analyseer was_shown/skip_reason om relevante data te identificeren
   - 98% skipped = korte retentie voldoende

## Verificatie Commando's
```bash
# Check beide stations geen failed services
systemctl --failed
ssh emsn2-berging "systemctl --failed"

# Check sync werkt
sudo systemctl start lifetime-sync.service
journalctl -u lifetime-sync.service --since "1 minute ago" | tail -5

# Check database cleanup
/home/ronny/emsn2/venv/bin/python3 /home/ronny/emsn2/scripts/maintenance/database_cleanup.py
```
