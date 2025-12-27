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

### Systemd Services & Timers (`/etc/systemd/system/`)

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
│   ├── images/      # Wekelijkse .img.gz bestanden (~5GB)
│   ├── daily/       # Dagelijkse rsync snapshots
│   ├── database/    # Uurlijkse SQL dumps (~0.5MB)
│   └── config/      # Systeem configuratie
├── berging/
│   └── (zelfde structuur)
└── recovery/
    └── HANDLEIDING-SD-KAART-RECOVERY.md
```

---

## Recovery Handleiding

Een uitgebreide handleiding is opgeslagen op twee locaties:
1. **NAS:** `/mnt/nas-birdnet-archive/sd-backups/recovery/HANDLEIDING-SD-KAART-RECOVERY.md`
2. **Git:** `/home/ronny/emsn2/docs/HANDLEIDING-SD-KAART-RECOVERY.md`

### Recovery in 5 stappen:
1. Kopieer nieuwste `.img.gz` van NAS naar lokale computer
2. Schrijf naar nieuwe SD kaart met **Raspberry Pi Imager**
3. Boot de Pi
4. Herstel nieuwste database dump
5. Controleer services

---

## Technische Details

### Wat wordt WEL gebackupt:
- Volledige filesystem (rsync)
- BirdNET-Pi database (birds.db)
- Systeem configuratie (fstab, hostname, mosquitto, etc.)
- EMSN scripts en configuratie

### Wat wordt NIET gebackupt (te groot):
- Audio bestanden (.mp3, .wav)
- BirdNET Extracted/By_Date mappen
- Tijdelijke bestanden (/tmp, /var/cache)
- NAS mounts

### Tools geinstalleerd:
- `pishrink.sh` - Verkleint SD images
- `pigz` - Parallelle gzip compressie (sneller)

---

## Volgende Stappen

1. **Wachten op eerste backups:**
   - Database backup om 20:15
   - Daily rsync vannacht 02:00
   - Wekelijkse image zondag 03:00

2. **Berging Pi:** Dezelfde installatie uitvoeren op emsn2-berging

3. **Test recovery:** Na eerste volledige backup een test-restore doen

---

## Bestanden

### Nieuwe bestanden:
- `/home/ronny/emsn2/scripts/backup/` (hele map)
- `/home/ronny/emsn2/systemd/backup/` (hele map)
- `/home/ronny/emsn2/docs/HANDLEIDING-SD-KAART-RECOVERY.md`
- `/mnt/nas-birdnet-archive/sd-backups/` (backup structuur)

### Timer status:
```
sd-backup-database.timer  - Elk uur om :15
sd-backup-daily.timer     - Dagelijks 02:00
sd-backup-cleanup.timer   - Dagelijks 02:30
sd-backup-weekly.timer    - Zondag 03:00
```
