# EMSN Workflow Documentation

## Zolder Pi Configuration

### Overview
De Zolder Pi is geconfigureerd met twee USB drives voor database mirrors en audio archief opslag.

### USB Drives Setup

#### Drive Configuratie
- **sda1** (28.7GB) - Database Mirrors
  - UUID: `3d5f6386-461c-40d6-a994-d43fb447ede3`
  - Mount point: `/mnt/usb`
  - Label: EcoMonitor_Zolde
  - Filesystem: ext4

- **sdb1** (478GB) - Audio Archief
  - UUID: `37abb6e3-4f4d-42a4-b268-bdd816a3f319`
  - Mount point: `/mnt/audio`
  - Label: EMSN_Audio
  - Filesystem: ext4

#### Directory Structuur

##### /mnt/usb (Database Drive)
```
/mnt/usb/
├── database/     # Database bestanden en mirrors
├── logs/         # Log bestanden
├── backups/      # Backup storage
├── mirrors/      # Mirror data
├── analytics/    # Analytics data
├── config/       # Configuratie bestanden
├── export/       # Export data
└── temp/         # Tijdelijke bestanden
```

##### /mnt/audio (Audio Drive)
```
/mnt/audio/
├── BirdSongs/    # Vogelgeluiden archief
├── Extracted/    # Geëxtraheerde audio
└── logs/         # Audio processing logs
```

### Mount Script

Het USB mount script bevindt zich in: `scripts/mount-usb-drives.sh`

#### Gebruik
```bash
# Uitvoeren van het mount script
sudo /home/ronny/emsn2/scripts/mount-usb-drives.sh

# Controleer mount status
df -h | grep mnt

# Bekijk directory inhoud
ls -la /mnt/usb
ls -la /mnt/audio
```

#### Functionaliteit
Het script voert de volgende acties uit:
1. Maakt mount directories aan (`/mnt/usb`, `/mnt/audio`)
2. Maakt backup van `/etc/fstab` (als `/etc/fstab.backup`)
3. Voegt USB mount entries toe aan `/etc/fstab` met UUID
4. Mount de drives met `mount -a`
5. Maakt subdirectories aan in `/mnt/usb`
6. Verifieert de mount status

#### fstab Configuratie
De drives zijn persistent gemount via `/etc/fstab` met `nofail` optie:
```
# USB Drive sda1 - Database mirrors (28.7GB)
UUID=3d5f6386-461c-40d6-a994-d43fb447ede3  /mnt/usb   ext4    defaults,nofail  0  2

# USB Drive sdb1 - Audio archief (478GB)
UUID=37abb6e3-4f4d-42a4-b268-bdd816a3f319  /mnt/audio ext4    defaults,nofail  0  2
```

De `nofail` optie zorgt ervoor dat het systeem normaal opstart zelfs als een USB drive niet beschikbaar is.

### Onderhoud

#### Disk Gebruik Controleren
```bash
df -h /mnt/usb /mnt/audio
```

#### Mount Status Controleren
```bash
mount | grep mnt
```

#### Remount na Reboot
De drives worden automatisch gemount bij boot via `/etc/fstab`. Voor handmatige mount:
```bash
sudo mount -a
```

#### Troubleshooting

##### Drive niet gemount
```bash
# Controleer of drive wordt herkend
lsblk -f

# Controleer UUID's
sudo blkid

# Handmatig mounten
sudo mount /mnt/usb
sudo mount /mnt/audio
```

##### Permissions Issues
```bash
# Zet correcte permissions voor subdirectories
sudo chmod 755 /mnt/usb/database
sudo chown -R ronny:ronny /mnt/usb
```

### Backup Strategy

#### Database Backups
Database backups worden opgeslagen in `/mnt/usb/backups/`

#### Audio Archief
Audio bestanden worden permanent opgeslagen in `/mnt/audio/BirdSongs/`

### Monitoring

#### Disk Space Monitoring
Regelmatig disk usage controleren:
```bash
# Gedetailleerde disk usage
du -sh /mnt/usb/*
du -sh /mnt/audio/*

# Alerts bij >80% gebruik
df -h | awk '$5 > 80 {print $0}'
```

## Opmerkingen

- Beide drives gebruiken ext4 filesystem voor betrouwbaarheid
- UUID-based mounting voorkomt problemen bij device naam wijzigingen
- Backup van fstab gemaakt voor rollback mogelijkheid
- Scripts zijn getest op Raspberry Pi OS (Debian-based)

## Changelog

### 2025-12-05
- Initiële configuratie van USB mount script
- Aangemaakt subdirectories voor database gebruik
- Toegevoegd aan version control
