#!/bin/bash
#
# EMSN 2.0 - Installeer SD Backup Services
# Dit script installeert alle systemd services en timers voor de backup
#
# Gebruik: sudo ./install_backup_services.sh
#

set -e

# Kleuren voor output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}EMSN SD Backup Services Installer${NC}"
echo -e "${GREEN}========================================${NC}"

# Check root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Dit script moet als root draaien (sudo)${NC}"
    exit 1
fi

# Directories
SCRIPT_DIR="/home/ronny/emsn2/scripts/backup"
SYSTEMD_SRC="/home/ronny/emsn2/systemd/backup"
SYSTEMD_DST="/etc/systemd/system"
LOG_DIR="/var/log/emsn-backup"

echo -e "\n${YELLOW}Stap 1: Maak log directory${NC}"
mkdir -p "$LOG_DIR"
chown ronny:ronny "$LOG_DIR"
echo "  Log directory: $LOG_DIR"

echo -e "\n${YELLOW}Stap 2: Maak scripts executable${NC}"
chmod +x "$SCRIPT_DIR"/*.py
echo "  Scripts in $SCRIPT_DIR zijn nu executable"

echo -e "\n${YELLOW}Stap 3: Installeer pishrink.sh (optioneel, voor kleinere images)${NC}"
if [ ! -f /usr/local/bin/pishrink.sh ]; then
    echo "  Downloaden pishrink.sh..."
    curl -sL https://raw.githubusercontent.com/Drewsif/PiShrink/master/pishrink.sh -o /usr/local/bin/pishrink.sh
    chmod +x /usr/local/bin/pishrink.sh
    echo "  pishrink.sh geinstalleerd"
else
    echo "  pishrink.sh is al geinstalleerd"
fi

echo -e "\n${YELLOW}Stap 4: Installeer pigz (parallelle compressie)${NC}"
if ! command -v pigz &> /dev/null; then
    apt-get update -qq
    apt-get install -y -qq pigz
    echo "  pigz geinstalleerd"
else
    echo "  pigz is al geinstalleerd"
fi

echo -e "\n${YELLOW}Stap 5: Kopieer systemd services en timers${NC}"
for file in "$SYSTEMD_SRC"/*.service "$SYSTEMD_SRC"/*.timer; do
    if [ -f "$file" ]; then
        cp "$file" "$SYSTEMD_DST/"
        echo "  Gekopieerd: $(basename $file)"
    fi
done

echo -e "\n${YELLOW}Stap 6: Reload systemd daemon${NC}"
systemctl daemon-reload
echo "  Systemd daemon herladen"

echo -e "\n${YELLOW}Stap 7: Enable timers${NC}"
systemctl enable sd-backup-daily.timer
systemctl enable sd-backup-weekly.timer
systemctl enable sd-backup-database.timer
systemctl enable sd-backup-cleanup.timer
echo "  Alle backup timers enabled"

echo -e "\n${YELLOW}Stap 8: Start timers${NC}"
systemctl start sd-backup-daily.timer
systemctl start sd-backup-weekly.timer
systemctl start sd-backup-database.timer
systemctl start sd-backup-cleanup.timer
echo "  Alle backup timers gestart"

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}Installatie voltooid!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Timer status:"
systemctl list-timers --all | grep sd-backup
echo ""
echo -e "Volgende stappen:"
echo "  1. Test database backup:  sudo systemctl start sd-backup-database.service"
echo "  2. Test daily backup:     sudo systemctl start sd-backup-daily.service"
echo "  3. Bekijk logs:           journalctl -u sd-backup-database -f"
echo ""
echo "Backup locaties op NAS:"
echo "  /mnt/nas-birdnet-archive/sd-backups/$(hostname | sed 's/emsn2-//')/"
echo ""
