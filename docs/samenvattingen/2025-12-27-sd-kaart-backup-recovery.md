# Sessie Samenvatting: SD Kaart Backup & Recovery Systeem

**Datum:** 27 december 2025
**Onderwerp:** Disaster Recovery voor SD kaarten Zolder en Berging

---

## Wat is er gemaakt?

Een compleet backup- en recovery systeem voor de Raspberry Pi's, zodat na een SD kaart crash het systeem binnen 15 minuten weer online kan zijn.

### Backup Scripts (`/home/ronny/emsn2/scripts/backup/`)

| Script | Functie |
|--------|---------|
| `backup_config.py` | Centrale configuratie (paden, credentials, exclusies) |
| `sd_backup_daily.py` | Dagelijkse rsync backup (excl. audio) |
| `sd_backup_weekly.py` | Wekelijkse volledige SD image (gecomprimeerd) |
| `sd_backup_database.py` | Uurlijkse birds.db dump |
| `sd_backup_cleanup.py` | Rotatie: verwijder backups ouder dan 7 dagen |
| `install_backup_services.sh` | Installer voor alle services |

### Systemd Services & Timers

| Timer | Tijdstip | Service |
|-------|----------|---------|
| `sd-backup-database.timer` | Elk uur (:15) | Database dump naar NAS |
| `sd-backup-daily.timer` | 02:00 | Rsync backup naar NAS |
| `sd-backup-cleanup.timer` | 02:30 | Rotatie oude backups |
| `sd-backup-weekly.timer` | Zondag 03:00 | Volledige SD image |

### Backup Locaties op NAS

```
/mnt/nas-birdnet-archive/sd-backups/
├── zolder/
│   ├── images/      # Wekelijkse .img.gz (~5GB)
│   ├── daily/       # Rsync snapshots
│   ├── database/    # Uurlijkse SQL dumps
│   └── config/      # Systeem configuratie
├── berging/
│   └── (zelfde structuur)
└── recovery/
    └── HANDLEIDING-SD-KAART-RECOVERY.md
```

---

## Installatie op beide Pi's

### Zolder (192.168.1.178)
- Backup scripts geinstalleerd
- Timers actief
- Eerste database backup: 28.030 records (476 KB)

### Berging (192.168.1.87)
- NFS client geinstalleerd (`nfs-common`)
- NAS mount toegevoegd aan `/etc/fstab`
- Backup scripts geinstalleerd
- Timers actief
- Eerste database backup: 60.277 records (1.0 MB)

---

## Uitgebreide Tests Uitgevoerd

| Test | Resultaat |
|------|-----------|
| Database backup beide Pi's | ✅ Valide SQL dumps |
| Cleanup script | ✅ Draait correct |
| Rsync dry-run | ✅ ~30GB te backuppen |
| Database integriteit | ✅ Correcte record counts |
| Config backup | ✅ 9-19 bestanden per Pi |
| Email alerting | ✅ Test email ontvangen |

---

## Recovery Procedure (samengevat)

1. Download nieuwste `.img.gz` van NAS
2. Schrijf met **Raspberry Pi Imager** naar nieuwe SD kaart
3. Boot de Pi
4. Herstel nieuwste database dump
5. Klaar! (~15 minuten)

Volledige handleiding: `/docs/HANDLEIDING-SD-KAART-RECOVERY.md`

---

## Geleerde Lessen (Claude)

### NFS vs CIFS mounts
- Zolder gebruikt NFS mount voor de 8TB USB schijf op NAS
- Berging had geen `nfs-common` geinstalleerd - moest eerst geinstalleerd worden
- NFS mount syntax: `192.168.1.25:/volumeUSB1/usbshare /mnt/nas-birdnet-archive nfs vers=3,_netdev,x-systemd.automount,nofail 0 0`

### Permission handling in Python
- `os.access(path, os.R_OK)` checken VOORDAT `path.exists()` aanroepen
- Anders krijg je PermissionError bij `/var/spool/cron/crontabs/`
- Altijd try/except PermissionError rond file operations

### Database backup strategie
- SQLite `.dump` commando geeft volledige SQL export
- Compressie met pigz (parallel gzip) bespaart ~93% ruimte
- birds.db van 6.6MB wordt 0.5MB gecomprimeerd

### Rsync met hard links
- `--link-dest` naar vorige backup bespaart enorm veel ruimte
- Alleen gewijzigde bestanden nemen nieuwe ruimte in
- Exclusies via bestand (`--exclude-from`) is schoner dan command line

### Systemd timer best practices
- `Persistent=true` zorgt dat gemiste runs alsnog uitgevoerd worden
- `RandomizedDelaySec` voorkomt dat alle Pi's tegelijk backuppen
- `Nice=19` en `IOSchedulingClass=idle` voor lage prioriteit bij zware taken

### Email alerting
- Niet bij elke fout mailen (spam)
- Gebruik error counter: pas na 3 opeenvolgende fouten alert sturen
- Reset counter na succesvolle alert

### Testen van backup systeem
- Altijd dry-run (`rsync -n`) eerst
- Controleer database integriteit met `grep -c "INSERT INTO"`
- Vergelijk record count met origineel
- Test email apart voordat je vertrouwt op alerting
