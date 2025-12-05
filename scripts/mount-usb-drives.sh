#!/bin/bash
#
# USB Mount Script voor Zolder Pi
# Mounted sda1 (28.7GB) op /mnt/usb voor database mirrors
# Mounted sdb1 (478GB) op /mnt/audio voor audio archief
#

set -e

echo "=== Zolder Pi USB Mount Script ==="
echo ""

# Controleer of script als root wordt uitgevoerd
if [ "$EUID" -ne 0 ]; then
    echo "Fout: Dit script moet als root worden uitgevoerd"
    echo "Gebruik: sudo $0"
    exit 1
fi

# Kleurencodes voor output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# UUID's
UUID_SDA1="3d5f6386-461c-40d6-a994-d43fb447ede3"
UUID_SDB1="37abb6e3-4f4d-42a4-b268-bdd816a3f319"

# Mount points
MOUNT_USB="/mnt/usb"
MOUNT_AUDIO="/mnt/audio"

echo -e "${YELLOW}Stap 1: Aanmaken mount directories${NC}"
# Maak mount directories aan als ze nog niet bestaan
mkdir -p "$MOUNT_USB"
mkdir -p "$MOUNT_AUDIO"
echo -e "${GREEN}✓ Mount directories aangemaakt${NC}"
echo ""

echo -e "${YELLOW}Stap 2: Backup /etc/fstab${NC}"
# Backup fstab
if [ ! -f /etc/fstab.backup ]; then
    cp /etc/fstab /etc/fstab.backup
    echo -e "${GREEN}✓ Backup gemaakt: /etc/fstab.backup${NC}"
else
    echo -e "${GREEN}✓ Backup bestaat al: /etc/fstab.backup${NC}"
fi
echo ""

echo -e "${YELLOW}Stap 3: Update /etc/fstab${NC}"
# Controleer of entries al bestaan
if grep -q "$UUID_SDA1" /etc/fstab; then
    echo -e "${YELLOW}⚠ sda1 entry bestaat al in /etc/fstab${NC}"
else
    echo "# USB Drive sda1 - Database mirrors (28.7GB)" >> /etc/fstab
    echo "UUID=$UUID_SDA1  $MOUNT_USB   ext4    defaults,nofail  0  2" >> /etc/fstab
    echo -e "${GREEN}✓ sda1 entry toegevoegd aan /etc/fstab${NC}"
fi

if grep -q "$UUID_SDB1" /etc/fstab; then
    echo -e "${YELLOW}⚠ sdb1 entry bestaat al in /etc/fstab${NC}"
else
    echo "# USB Drive sdb1 - Audio archief (478GB)" >> /etc/fstab
    echo "UUID=$UUID_SDB1  $MOUNT_AUDIO ext4    defaults,nofail  0  2" >> /etc/fstab
    echo -e "${GREEN}✓ sdb1 entry toegevoegd aan /etc/fstab${NC}"
fi
echo ""

echo -e "${YELLOW}Stap 4: Mount de drives${NC}"
# Mount alle drives uit fstab
mount -a
echo -e "${GREEN}✓ Drives gemount${NC}"
echo ""

echo -e "${YELLOW}Stap 5: Maak subdirectories in /mnt/usb${NC}"
# Maak subdirectories voor database gebruik
mkdir -p "$MOUNT_USB/database"
mkdir -p "$MOUNT_USB/logs"
mkdir -p "$MOUNT_USB/backups"
mkdir -p "$MOUNT_USB/mirrors"

# Zet permissions
chmod 755 "$MOUNT_USB/database"
chmod 755 "$MOUNT_USB/logs"
chmod 755 "$MOUNT_USB/backups"
chmod 755 "$MOUNT_USB/mirrors"

echo -e "${GREEN}✓ Subdirectories aangemaakt:${NC}"
echo "  - $MOUNT_USB/database"
echo "  - $MOUNT_USB/logs"
echo "  - $MOUNT_USB/backups"
echo "  - $MOUNT_USB/mirrors"
echo ""

echo -e "${YELLOW}Stap 6: Verificatie${NC}"
echo ""
echo "=== Mount Status ==="
df -h | grep -E "Filesystem|$MOUNT_USB|$MOUNT_AUDIO"
echo ""

echo "=== Directory Structuur ==="
echo "USB Drive (database):"
ls -lah "$MOUNT_USB" 2>/dev/null || echo "Niet gemount"
echo ""
echo "Audio Drive:"
ls -lah "$MOUNT_AUDIO" 2>/dev/null || echo "Niet gemount"
echo ""

echo "=== /etc/fstab entries ==="
grep -E "$UUID_SDA1|$UUID_SDB1" /etc/fstab
echo ""

echo -e "${GREEN}=== Mount script succesvol uitgevoerd ===${NC}"
echo ""
echo "Mount points:"
echo "  Database mirror: $MOUNT_USB"
echo "  Audio archief:   $MOUNT_AUDIO"
echo ""
echo "Tip: Gebruik 'df -h' om disk gebruik te controleren"
