# EMSN 2.0 - Workflow & Ontwikkel Filosofie

**EcoMonitoring Systeem Nijverdal**
*"Je beschermt wat je kent" - A love letter to nature, written in Python*

---

## 🎯 Project Filosofie

### Kernprincipes

1. **"BirdPi = Heilig"** 🛡️
   - BirdNET-Pi installaties blijven **ALTIJD** onaangetast
   - Geen modificaties aan core BirdNET-Pi bestanden
   - Geen aanpassingen aan `/home/birdnet/BirdNET-Pi/`
   - Read-only toegang tot BirdNET-Pi databases
   - We bouwen **rondom** BirdNET-Pi, niet **in** BirdNET-Pi

2. **Non-Invasief Monitoren**
   - Externe sync scripts die data kopiëren
   - Geen directe writes naar BirdNET-Pi databases
   - USB-first storage voor longevity
   - Graceful degradation bij failures

3. **Reproduceerbaar & Gedocumenteerd**
   - Alles in Git version control
   - Complete scripts, geen patches
   - Stap-voor-stap verificatie
   - Comprehensive logging

4. **Wetenschappelijke Integriteit**
   - Append-only databases
   - Timestamp accuracy
   - Metadata preservation
   - Dual-station verification

---

## 🛠️ Ontwikkel Workflow

### Tools & Omgeving

**Primaire Development:**
- **VS Code** met Remote SSH
- **Claude Code** extensie voor Pi werk
- **Claude Chat** (claude.ai) voor planning & architectuur
- **GitHub** voor version control

**Hardware Overzicht:**
```
Station          IP              Role                    Audio
─────────────────────────────────────────────────────────────────
emsn2-zolder     192.168.1.178   Primary, MQTT broker    UR22mkII
emsn2-berging    192.168.1.87    Secondary, MQTT bridge  UR44 (4ch)
emsn2-meteo      TBD             Weather station         N/A
emsn2-bats       TBD             SonarPi (future)        Ultrasonic

NAS              192.168.1.25    Synology DS224+         N/A
Home Assistant   192.168.1.142   Automation & Dashboard  N/A
```

---

## 📋 Workflow Stappen

### Stap 1: Planning (Claude Chat)

**Gebruik:** claude.ai in browser

**Doel:** Architectuur, planning, uitleg

**Voorbeeld vragen:**
- "Hoe zou ik database mirrors moeten opzetten?"
- "Wat is de beste manier om audio te archiveren?"
- "Leg uit hoe MQTT bridge werkt"

**Output:** Plan, concepten, architectuur documenten

---

### Stap 2: Implementatie (Claude Code in VS Code)

**Gebruik:** Claude Code extensie in VS Code

**Workflow:**
1. Open VS Code
2. Maak **Remote SSH** verbinding naar Pi
3. Open **Claude Code** (sparkle ⚡ icoon in sidebar)
4. Beschrijf WAT je wilt in natuurlijke taal
5. Claude Code maakt scripts, test, en voert uit

**Voorbeeld opdrachten:**
```
"Maak een database sync script dat elke 5 minuten
draait en data van BirdNET-Pi kopieert naar USB mirror"

"Test of MQTT broker bereikbaar is en log naar
/mnt/usb/logs/mqtt_test.log"

"Maak systemd service voor database sync met
auto-restart en logging"
```

**Voordelen:**
- ✅ Geen handmatig copy-paste
- ✅ Directe executie op Pi
- ✅ Automatische verificatie
- ✅ Foutafhandeling ingebouwd

---

### Stap 3: Version Control (GitHub)

**Na succesvolle implementatie:**
```bash
# In VS Code terminal (op de Pi):
cd ~/emsn2

# Nieuwe bestanden toevoegen
git add scripts/nieuwe_script.py
git add config/nieuwe_config.yaml

# Commit met duidelijke message
git commit -m "feat: Add USB mount script for database mirrors

- Auto-mount sda1 (28GB) for database/logs
- Auto-mount sdb1 (478GB) for audio archive
- Update fstab with UUID-based mounts
- Create directory structure
- Tested on emsn2-zolder"

# Push naar GitHub
git push origin main
```

**Commit Message Conventies:**
- `feat:` - Nieuwe feature
- `fix:` - Bug fix
- `docs:` - Documentatie
- `config:` - Configuratie wijziging
- `test:` - Tests toevoegen

---

### Stap 4: Uitrollen naar Andere Pi's

**Op andere Pi (bijvoorbeeld Berging):**
```bash
# SSH naar berging
ssh ronny@192.168.1.87

# Navigate to project
cd ~/emsn2

# Pull latest changes
git pull origin main

# Pas aan voor deze Pi (indien nodig)
# Bijvoorbeeld: verschillende UUIDs, IP adressen

# Test uitvoeren
./scripts/nieuwe_script.py --test

# Als OK: enable service
sudo systemctl enable nieuwe-service
sudo systemctl start nieuwe-service
```

---

## 🚫 Wat NOOIT Te Doen

### VERBODEN Acties

❌ **Modificeer NOOIT:**
- `/home/birdnet/BirdNET-Pi/scripts/*.py`
- `/home/birdnet/BirdNET-Pi/scripts/birds.db` (direct schrijven)
- BirdNET-Pi systemd services
- BirdNET-Pi cron jobs
- Apprise configuratie van BirdNET-Pi

❌ **Geen Direct Database Writes:**
```python
# FOUT - Direct schrijven naar BirdNET-Pi database
conn = sqlite3.connect('/home/birdnet/BirdNET-Pi/scripts/birds.db')
conn.execute("DELETE FROM detections WHERE ...")  # NOOIT DOEN!
```

❌ **Geen Incomplete Scripts:**
```bash
# FOUT - "Voeg dit toe aan je bestaande script..."
# Geef ALTIJD complete, werkende scripts
```

❌ **Geen Hardcoded Paths zonder Verificatie:**
```python
# FOUT - Aanname zonder check
DB_PATH = "/mnt/usb/database/mirror.db"  # Bestaat deze directory?

# GOED - Check eerst
if not os.path.exists("/mnt/usb"):
    logger.error("USB not mounted!")
    sys.exit(1)
```

---

## ✅ Wat WEL Te Doen

### Best Practices

✅ **Read-Only Access:**
```python
# GOED - Read-only copy
source_db = "/home/birdnet/BirdNET-Pi/scripts/birds.db"
mirror_db = "/mnt/usb/database/birds_mirror.db"

# Copy, don't modify source
shutil.copy2(source_db, mirror_db)
```

✅ **Graceful Degradation:**
```python
# GOED - Fail gracefully
try:
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT)
except:
    logger.warning("MQTT niet bereikbaar, skip notificatie")
    # Continue met andere taken
```

✅ **Complete Scripts:**
```python
#!/usr/bin/env python3
"""
Complete, werkend script met:
- Imports
- Configuratie
- Error handling
- Logging
- Main execution
"""
```

✅ **Comprehensive Logging:**
```python
# GOED - Log naar USB, niet naar SD
LOG_PATH = "/mnt/usb/logs"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"{LOG_PATH}/script_name.log"),
        logging.StreamHandler()
    ]
)
```

✅ **Verificatie Stappen:**
```python
def verify_setup():
    """Verify all prerequisites before running"""
    checks = {
        "USB mounted": os.path.ismount("/mnt/usb"),
        "NAS reachable": os.path.ismount("/mnt/nas"),
        "Source DB exists": os.path.exists(SOURCE_DB),
        "MQTT broker up": test_mqtt_connection()
    }

    for check, result in checks.items():
        if result:
            logger.info(f"✓ {check}")
        else:
            logger.error(f"✗ {check}")
            return False
    return True
```

---

## 📁 Project Structuur
```
~/emsn2/
├── config/
│   ├── settings.json          # Main config
│   ├── secrets.yaml          # Credentials (gitignored)
│   └── species_config.yaml   # Species parameters
├── scripts/
│   ├── database_sync.py      # Sync BirdNET → USB
│   ├── lifetime_sync.py      # USB → NAS/PostgreSQL
│   ├── mqtt_publisher.py     # Real-time notifications
│   └── backup_verify.py      # Backup verification
├── services/
│   ├── ecomonitor-dbsync-zolder.service
│   ├── ecomonitor-lifetime-zolder.service
│   └── ecomonitor-mqtt-zolder.service
├── logs/                     # Symlink → /mnt/usb/logs
├── docs/
│   ├── EMSN_Workflow.md     # Dit document
│   ├── Setup_Guide.md       # Installation
│   └── Architecture.md      # System design
├── tests/
│   └── test_*.py            # Unit tests
└── README.md                # Project overview
```

---

## 🔧 Technische Standaarden

### Python Scripts

**Template:**
```python
#!/usr/bin/env python3
"""
EMSN 2.0 - [Script Naam]

Beschrijving: Wat doet dit script
Auteur: Claude AI + Ronny
Datum: YYYY-MM-DD
Station: [Zolder/Berging/All]
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path

# Configuratie laden
CONFIG_PATH = "/home/ronny/emsn2/config/settings.json"
with open(CONFIG_PATH, 'r') as f:
    config = json.load(f)

# Logging setup (naar USB!)
LOG_PATH = "/mnt/usb/logs"
os.makedirs(LOG_PATH, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"{LOG_PATH}/{Path(__file__).stem}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def main():
    """Main execution"""
    logger.info("Script started")

    try:
        # Verificatie
        if not verify_prerequisites():
            logger.error("Prerequisites not met, exiting")
            sys.exit(1)

        # Hoofdlogica
        result = do_work()

        # Cleanup
        cleanup()

        logger.info(f"Script completed successfully: {result}")
        return 0

    except Exception as e:
        logger.error(f"Script failed: {e}", exc_info=True)
        return 1

if __name__ == "__main__":
    sys.exit(main())
```

### Systemd Services

**Template:**
```ini
[Unit]
Description=EMSN 2.0 - [Service Naam]
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=ronny
WorkingDirectory=/home/ronny/emsn2
ExecStart=/home/ronny/emsn2/venv/bin/python3 /home/ronny/emsn2/scripts/script_name.py
Restart=always
RestartSec=10

# Logging
StandardOutput=append:/mnt/usb/logs/service_name.log
StandardError=append:/mnt/usb/logs/service_name.error.log

# Security
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

---

## 🧪 Testing Protocol

### Voor Elke Feature

1. **Unit Test** - Test individuele functies
2. **Integration Test** - Test met echte hardware
3. **Duration Test** - Draai 24 uur
4. **Failover Test** - Test bij network/USB failure
5. **Reboot Test** - Verify na reboot

**Test Checklist:**
```bash
# 1. Dry-run mode
./script.py --dry-run

# 2. Verbose logging
./script.py --verbose

# 3. Check logs
tail -f /mnt/usb/logs/script.log

# 4. Verify output
ls -lah /expected/output/path

# 5. Monitor resources
htop

# 6. Check MQTT (if applicable)
mosquitto_sub -h localhost -t 'emsn/#' -v
```

---

## 📊 Monitoring & Verificatie

### Daily Checks

**Via Grafana Dashboard (planned):**
- Disk space trending
- Detection counts per station
- Service uptime
- Backup status

**Via Commandline:**
```bash
# Disk space
df -h | grep -E 'mnt|Filesystem'

# Service status
systemctl status ecomonitor-*

# Recent logs
tail -50 /mnt/usb/logs/*.log

# Database integrity
sqlite3 /mnt/usb/database/birds_mirror.db "PRAGMA integrity_check"

# MQTT status
mosquitto_sub -h localhost -t 'emsn/+/status' -C 5
```

---

## 🆘 Troubleshooting

### Common Issues

**USB niet gemount:**
```bash
# Check mount
mount | grep mnt

# Force mount
sudo mount -a

# Check fstab
cat /etc/fstab | grep UUID

# Logs
journalctl -u mount-usb-drives.service
```

**Service draait niet:**
```bash
# Status check
sudo systemctl status service-name

# Logs
sudo journalctl -u service-name -f

# Restart
sudo systemctl restart service-name

# Daemon reload (na service file edit)
sudo systemctl daemon-reload
```

**Database locked:**
```bash
# Check locks
lsof /path/to/database.db

# Kill stale connections
sudo systemctl restart ecomonitor-*

# Verify integrity
sqlite3 database.db "PRAGMA integrity_check"
```

---

## 📚 Communicatie Conventies

### Met Claude Chat (claude.ai)

**Gebruik voor:**
- Architectuur vragen
- Conceptuele uitleg
- Planning nieuwe features
- Design decisions

**Voorbeeld:**
> "Ik wil graag anomalie detectie toevoegen. Wat is de beste aanpak
> voor real-time outlier detection bij vogeldetecties?"

### Met Claude Code (VS Code)

**Gebruik voor:**
- Scripts maken
- Code uitvoeren
- Testen
- Debugging

**Voorbeeld:**
> "Maak een script dat MQTT topics test en resultaat logt naar
> /mnt/usb/logs/mqtt_test.log"

### Feedback Loop

**Altijd:**
1. Geef Claude output van commando's
2. Meld wat werkt en wat niet
3. Upload screenshots bij problemen
4. Vraag om uitleg bij onduidelijkheden

**Ronny bepaalt:**
- Wat er gebeurt
- Wanneer het gebeurt
- Welke features prioriteit hebben

**Claude helpt met:**
- Structuur & best practices
- Complete oplossingen
- Verificatie & testing
- Documentatie

---

## 🎯 Feature Development Checklist

Bij nieuwe feature ontwikkeling:

- [ ] **Planning** - Bespreek in Claude Chat
- [ ] **Design** - Maak architecture document
- [ ] **Implementation** - Gebruik Claude Code
- [ ] **Testing** - Volg test protocol
- [ ] **Documentation** - Update relevante .md files
- [ ] **Git Commit** - Met duidelijke message
- [ ] **Deploy** - Uitrollen naar andere Pi's
- [ ] **Monitor** - 24-48 uur observeren
- [ ] **Iterate** - Verbeteren op basis van logs

---

## 🔄 Update & Maintenance

### Weekly

- Check disk space alle stations
- Verify backup integrity
- Review logs voor errors
- Update dependencies indien nodig

### Monthly

- Full system audit (zoals Complete_System_Audit)
- Database optimization
- Cloud backup verification
- Service restart fresh

### Quarterly

- SD card full backup
- Review & prune old logs
- Update documentation
- Performance benchmarking

---

## 📖 Belangrijke Documenten

**Start hier:**
1. `EMSN_Workflow.md` (dit document)
2. `Setup_Guide.md` - Fresh Pi installatie
3. `Architecture.md` - System design

**Reference:**
- `EMSN_deel_1.md` t/m `deel_5.md` - Historical development
- `Complete_System_Audit.md` - Current state analysis
- `USB_Mounting_Samenvatting.md` - USB setup details

**GitHub Repository:**
- https://github.com/RonnyCH1/emsn2.git

---

## 🎓 Key Learnings (EMSN 1.0 → 2.0)

1. **SQLite over network = bad** → PostgreSQL = good
2. **Cron jobs = onvoorspelbaar** → systemd timers = betrouwbaar
3. **SD card writes = slijtage** → USB first = longevity
4. **Hardcoded configs = fragile** → YAML/JSON = flexibel
5. **Manual backups = vergeten** → Automated 3-tier = safe
6. **Single station = bias** → Dual detection = validation

---

## ✨ EMSN 2.0 Vision

> "A love letter to nature, written in Python"

**Missie:**
Democratiseer biodiversiteit monitoring door een robuust, reproduceerbaar
systeem te bouwen dat anderen kunnen repliceren.

**Waarden:**
- Wetenschappelijke integriteit
- Open source transparantie
- Non-invasieve monitoring
- Community-driven development

**Impact:**
Van hobby-project naar potentieel blueprint voor citizen science netwerken.

---

*Document Version: 1.0*
*Laatste Update: 2025-01-05*
*Onderhouden door: Ronny + Claude AI*
