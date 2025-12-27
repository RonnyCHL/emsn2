# SD Kaart Recovery Handleiding

## EMSN 2.0 - Nood Recovery Procedure

**Doel:** Binnen 15 minuten weer online na een SD kaart crash
**Laatste update:** December 2024
**Auteur:** EMSN Backup Systeem

---

## Inhoud

1. [Overzicht Backup Systeem](#1-overzicht-backup-systeem)
2. [Wat Je Nodig Hebt](#2-wat-je-nodig-hebt)
3. [Stap-voor-Stap Recovery](#3-stap-voor-stap-recovery)
4. [Na de Recovery](#4-na-de-recovery)
5. [Troubleshooting](#5-troubleshooting)
6. [Backup Structuur](#6-backup-structuur)

---

## 1. Overzicht Backup Systeem

### Wat wordt er gebackupt?

| Type | Frequentie | Retentie | Inhoud |
|------|------------|----------|--------|
| **Wekelijkse Image** | Zondag 03:00 | 7 dagen | Volledige SD kaart (gecomprimeerd) |
| **Dagelijkse Rsync** | 02:00 | 7 dagen | Alle bestanden (excl. audio) |
| **Database Dump** | Elk uur | 7 dagen | birds.db (alle detecties) |
| **Configuratie** | Elk uur | Altijd | Systeem config bestanden |

### Wat wordt NIET gebackupt?

- Audio bestanden (.mp3, .wav) - te groot
- Tijdelijke bestanden (/tmp, /var/cache)
- NAS mounts (om loops te voorkomen)

### Backup Locatie

```
NAS 8TB USB Schijf (192.168.1.25)
├── /mnt/nas-birdnet-archive/sd-backups/
    ├── zolder/
    │   ├── images/      ← Wekelijkse .img.gz bestanden
    │   ├── daily/       ← Dagelijkse rsync snapshots
    │   ├── database/    ← Uurlijkse database dumps
    │   └── config/      ← Configuratie bestanden
    ├── berging/
    │   └── (zelfde structuur)
    └── recovery/
        └── HANDLEIDING-SD-KAART-RECOVERY.md (dit bestand)
```

---

## 2. Wat Je Nodig Hebt

### Hardware

- [ ] **Nieuwe SD kaart** (minimaal 32GB, A2 klasse aanbevolen)
- [ ] **SD kaart lezer** (USB of ingebouwd in laptop)
- [ ] **Computer** met Raspberry Pi Imager
- [ ] **Netwerkkabel** (optioneel, voor eerste boot)

### Software

- [ ] **Raspberry Pi Imager** - Download van https://www.raspberrypi.com/software/
  - Windows: .exe installer
  - macOS: .dmg installer
  - Linux: `sudo apt install rpi-imager`

### Toegang

- [ ] **NAS toegang** - Via Verkenner of Finder:
  - Windows: `\\192.168.1.25\volumeUSB1\usbshare\sd-backups\`
  - macOS: `smb://192.168.1.25/volumeUSB1/usbshare/sd-backups/`
- [ ] **NAS credentials:** Zie `.secrets` bestand (NAS_USER/NAS_PASS)

---

## 3. Stap-voor-Stap Recovery

### STAP 1: Bepaal Welke Pi Gecrasht Is

| Pi | Hostname | IP Adres | Rol |
|----|----------|----------|-----|
| Zolder | emsn2-zolder | 192.168.1.178 | Hoofd Pi, MQTT broker, API |
| Berging | emsn2-berging | 192.168.1.87 | BirdNET-Pi, Camera |

### STAP 2: Kopieer Image naar Lokale Computer

1. **Open NAS in Verkenner/Finder**
   ```
   Windows: \\192.168.1.25\volumeUSB1\usbshare\sd-backups\
   macOS:   smb://192.168.1.25/volumeUSB1/usbshare/sd-backups/
   ```

2. **Navigeer naar de juiste map**
   - Voor Zolder: `zolder/images/`
   - Voor Berging: `berging/images/`

3. **Kopieer het NIEUWSTE .img.gz bestand**
   - Bestandsnaam format: `emsn2-zolder-2024-12-22.img.gz`
   - Kies de meest recente datum
   - Kopieer naar lokale schijf (Downloads map is prima)

4. **BELANGRIJK: Pak het bestand NIET uit!**
   - Raspberry Pi Imager kan .gz bestanden direct lezen

### STAP 3: Image Schrijven met Raspberry Pi Imager

1. **Start Raspberry Pi Imager**

2. **Klik op "CHOOSE OS"**
   - Scroll naar beneden
   - Klik op **"Use custom"**
   - Selecteer het gedownloade `.img.gz` bestand

3. **Klik op "CHOOSE STORAGE"**
   - Selecteer je nieuwe SD kaart
   - **LET OP:** Controleer goed dat je de juiste schijf selecteert!

4. **Klik op het tandwiel icoon (⚙️) voor geavanceerde opties**

   **BELANGRIJK:** Pas NIETS aan! De image bevat al de juiste configuratie:
   - Hostname is al ingesteld
   - WiFi is al geconfigureerd
   - SSH is al enabled
   - Gebruiker ronny bestaat al

5. **Klik op "WRITE"**
   - Bevestig dat je wilt schrijven
   - Wacht tot het proces klaar is (5-15 minuten)
   - Wacht op verificatie

6. **Eject de SD kaart veilig**

### STAP 4: Eerste Boot

1. **Plaats de SD kaart in de Raspberry Pi**

2. **Sluit netwerkkabel aan** (optioneel maar aanbevolen voor eerste boot)

3. **Sluit voeding aan**

4. **Wacht 2-3 minuten** voor volledige boot

5. **Test connectiviteit**
   ```bash
   # Vanaf een andere computer:
   ping 192.168.1.178   # Voor Zolder
   ping 192.168.1.87    # Voor Berging
   ```

### STAP 5: Herstel Recente Database

De wekelijkse image kan tot 7 dagen oud zijn. Herstel de nieuwste database:

1. **SSH naar de Pi**
   ```bash
   ssh ronny@192.168.1.178   # Voor Zolder
   ssh ronny@192.168.1.87    # Voor Berging
   ```

2. **Stop BirdNET service tijdelijk**
   ```bash
   sudo systemctl stop birdnet_analysis.service
   ```

3. **Herstel database van laatste dump**
   ```bash
   # Bekijk beschikbare dumps
   ls -la /mnt/nas-birdnet-archive/sd-backups/zolder/database/

   # Kies de nieuwste en herstel
   LATEST=$(ls -t /mnt/nas-birdnet-archive/sd-backups/zolder/database/*.sql.gz | head -1)

   # Backup huidige database (voor zekerheid)
   cp /home/ronny/BirdNET-Pi/scripts/birds.db /home/ronny/BirdNET-Pi/scripts/birds.db.old

   # Herstel van dump
   zcat "$LATEST" | sqlite3 /home/ronny/BirdNET-Pi/scripts/birds.db
   ```

4. **Start BirdNET service**
   ```bash
   sudo systemctl start birdnet_analysis.service
   ```

5. **Controleer of detecties binnenkomen**
   ```bash
   tail -f /var/log/syslog | grep -i birdnet
   ```

---

## 4. Na de Recovery

### Controleer Services

```bash
# Bekijk status van alle EMSN services
systemctl list-units --type=service | grep -E "(emsn|birdnet|mqtt|ulanzi)"

# Bekijk actieve timers
systemctl list-timers --all | grep -E "(sd-backup|emsn)"
```

### Controleer MQTT

```bash
# Test MQTT verbinding
mosquitto_pub -h localhost -u ecomonitor -P 'IwnadBon2iN' -t test -m "recovery test"

# Bekijk MQTT broker status
sudo systemctl status mosquitto
```

### Controleer NAS Mounts

```bash
# Check of NAS gemount is
df -h | grep nas

# Als niet gemount, herstart mount
sudo mount -a
```

### Test Backup Systeem

```bash
# Handmatige database backup test
sudo systemctl start sd-backup-database.service
journalctl -u sd-backup-database -f
```

---

## 5. Troubleshooting

### Probleem: Pi Boot Niet

**Symptomen:** Geen groen LED knipperen, geen netwerk

**Oplossingen:**
1. Probeer een andere SD kaart
2. Controleer of image correct geschreven is (opnieuw schrijven)
3. Controleer voeding (minimaal 3A voor Pi 4)

### Probleem: Geen Netwerk Na Boot

**Symptomen:** Pi boot, maar niet bereikbaar via SSH

**Oplossingen:**
1. Sluit monitor en toetsenbord aan
2. Check IP met `ip addr`
3. Controleer `/etc/dhcpcd.conf` voor statisch IP:
   ```
   # Zolder
   interface eth0
   static ip_address=192.168.1.178/24
   static routers=192.168.1.1
   static domain_name_servers=192.168.1.1
   ```

### Probleem: NAS Niet Bereikbaar

**Symptomen:** `/mnt/nas-birdnet-archive` is leeg

**Oplossingen:**
```bash
# Check mount status
mount | grep nas

# Handmatig mounten
sudo mount -t nfs 192.168.1.25:/volumeUSB1/usbshare /mnt/nas-birdnet-archive

# Check fstab
cat /etc/fstab | grep nas
```

### Probleem: BirdNET Start Niet

**Symptomen:** Geen detecties, service crashed

**Oplossingen:**
```bash
# Bekijk logs
journalctl -u birdnet_analysis -n 50

# Herstart service
sudo systemctl restart birdnet_analysis.service

# Check database integriteit
sqlite3 /home/ronny/BirdNET-Pi/scripts/birds.db "PRAGMA integrity_check;"
```

### Probleem: MQTT Werkt Niet

**Symptomen:** Geen berichten op broker

**Oplossingen:**
```bash
# Check Mosquitto status
sudo systemctl status mosquitto

# Check configuratie
sudo mosquitto -c /etc/mosquitto/mosquitto.conf -v

# Herstart
sudo systemctl restart mosquitto
```

---

## 6. Backup Structuur

### Mappenstructuur Detail

```
/mnt/nas-birdnet-archive/sd-backups/
│
├── zolder/
│   │
│   ├── images/                          # Wekelijkse volledige images
│   │   ├── emsn2-zolder-2024-12-15.img.gz   (5.2 GB)
│   │   ├── emsn2-zolder-2024-12-22.img.gz   (5.3 GB)
│   │   └── emsn2-zolder-2024-12-29.img.gz   (5.1 GB)
│   │
│   ├── daily/                           # Dagelijkse rsync snapshots
│   │   ├── 2024-12-25/                  # Hard links naar vorige dag
│   │   ├── 2024-12-26/                  # Alleen gewijzigde bestanden
│   │   ├── 2024-12-27/
│   │   └── ...
│   │
│   ├── database/                        # Uurlijkse database dumps
│   │   ├── birds-2024-12-27-00.sql.gz   (12 MB)
│   │   ├── birds-2024-12-27-01.sql.gz   (12 MB)
│   │   ├── birds-2024-12-27-02.sql.gz   (12 MB)
│   │   └── ... (168 bestanden max)
│   │
│   └── config/                          # Configuratie backup
│       └── latest/
│           ├── fstab
│           ├── hostname
│           ├── mosquitto.conf
│           └── ...
│
├── berging/
│   └── (identieke structuur)
│
└── recovery/
    └── HANDLEIDING-SD-KAART-RECOVERY.md
```

### Opslagverbruik Schatting

| Component | Per Week | Totaal (7 dagen) |
|-----------|----------|------------------|
| Images (per Pi) | ~5 GB | ~5 GB |
| Daily rsync | ~100 MB | ~700 MB |
| Database | ~12 MB/uur | ~2 GB |
| Config | ~10 MB | ~10 MB |
| **Totaal per Pi** | | **~8 GB** |
| **Totaal beide Pi's** | | **~16 GB** |

---

## Contactgegevens

**NAS IP:** 192.168.1.25
**Pi Zolder:** 192.168.1.178
**Pi Berging:** 192.168.1.87
**SSH User:** ronny

**Belangrijke bestanden:**
- Credentials: `/home/ronny/emsn2/.secrets`
- Backup logs: `/var/log/emsn-backup/`
- BirdNET database: `/home/ronny/BirdNET-Pi/scripts/birds.db`

---

## Changelog

- **2024-12-27:** Initiële versie handleiding
