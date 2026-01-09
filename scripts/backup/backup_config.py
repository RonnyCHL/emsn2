#!/usr/bin/env python3
"""
EMSN 2.0 - SD Kaart Backup Configuratie
Centrale configuratie voor alle backup scripts
"""

import os
from pathlib import Path
from typing import Dict, List

# Bepaal welke Pi dit is
HOSTNAME = os.uname().nodename

# Station mapping
STATION_MAP = {
    'emsn2-zolder': 'zolder',
    'emsn2-berging': 'berging',
    'raspberrypi': 'zolder',  # Fallback
}
STATION = STATION_MAP.get(HOSTNAME, 'unknown')

# Basis paden
NAS_BACKUP_BASE = Path('/mnt/nas-birdnet-archive/sd-backups')
STATION_BACKUP_DIR = NAS_BACKUP_BASE / STATION
LOCAL_LOG_DIR = Path('/var/log/emsn-backup')

# Backup directories per station
IMAGES_DIR = STATION_BACKUP_DIR / 'images'
DAILY_DIR = STATION_BACKUP_DIR / 'daily'
DATABASE_DIR = STATION_BACKUP_DIR / 'database'
CONFIG_DIR = STATION_BACKUP_DIR / 'config'

# BirdNET-Pi locaties
BIRDNET_BASE = Path('/home/ronny/BirdNET-Pi')
BIRDNET_DB = BIRDNET_BASE / 'scripts' / 'birds.db'
BIRDNET_SCRIPTS = BIRDNET_BASE / 'scripts'

# EMSN2 locaties
EMSN2_BASE = Path('/home/ronny/emsn2')
SYNC_DIR = Path('/home/ronny/sync')

# Retentie configuratie
RETENTION_DAYS_IMAGES = 7       # Wekelijkse images: 7 dagen
RETENTION_DAYS_DAILY = 7        # Dagelijkse rsync: 7 dagen
RETENTION_DAYS_DATABASE = 7     # Database dumps: 7 dagen (168 uurlijkse)

# Rsync exclusies - bestanden/mappen die NIET mee moeten
RSYNC_EXCLUDES = [
    # Audio bestanden (te groot)
    '/home/ronny/BirdNET-Pi/scripts/*.mp3',
    '/home/ronny/BirdNET-Pi/scripts/*.wav',
    '/home/ronny/BirdNET-Pi/Extracted/**',
    '/home/ronny/BirdNET-Pi/By_Date/**',
    '/home/ronny/BirdNET-Pi/By_Common_Name/**',
    '/home/ronny/BirdNET-Pi/By_Scientific_Name/**',

    # Tijdelijke bestanden
    '/tmp/**',
    '/var/tmp/**',
    '/var/cache/**',
    '/var/log/**',

    # Swap en kernel
    '/swapfile',
    '/swap',
    '*.swap',

    # Proc/sys/dev (virtuele filesystems)
    '/proc/**',
    '/sys/**',
    '/dev/**',
    '/run/**',

    # NAS mounts (geen recursieve backups!)
    '/mnt/nas-*/**',
    '/mnt/usb/**',

    # Python caches
    '**/__pycache__/**',
    '**/*.pyc',
    '**/.pytest_cache/**',

    # Git objects (worden hersteld via git clone)
    '**/.git/objects/**',
]

# Belangrijke configuratie bestanden voor aparte backup
CONFIG_FILES = [
    # Systeem
    '/etc/fstab',
    '/etc/hostname',
    '/etc/hosts',
    '/etc/network/interfaces',
    '/etc/dhcpcd.conf',
    '/etc/wpa_supplicant/wpa_supplicant.conf',

    # MQTT
    '/etc/mosquitto/mosquitto.conf',
    '/etc/mosquitto/conf.d/',

    # Systemd services (custom)
    '/etc/systemd/system/birdnet-*.service',
    '/etc/systemd/system/mqtt-*.service',
    '/etc/systemd/system/emsn-*.service',
    '/etc/systemd/system/ulanzi-*.service',
    '/etc/systemd/system/nestbox-*.service',
    '/etc/systemd/system/sd-backup-*.service',
    '/etc/systemd/system/sd-backup-*.timer',

    # Crontabs
    '/var/spool/cron/crontabs/ronny',
    '/etc/crontab',

    # EMSN configuratie
    '/home/ronny/emsn2/.secrets',
    '/home/ronny/emsn2/config/',
]

# Email configuratie (laden uit .secrets)
def load_secrets() -> Dict[str, str]:
    """Laad credentials uit .secrets bestand.

    Returns:
        Dictionary met key-value pairs uit .secrets bestand.
    """
    secrets: Dict[str, str] = {}
    secrets_file = EMSN2_BASE / '.secrets'

    if secrets_file.exists():
        with open(secrets_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    secrets[key.strip()] = value.strip()

    return secrets

SECRETS = load_secrets()

EMAIL_CONFIG = {
    'smtp_host': SECRETS.get('SMTP_HOST', 'smtp.strato.de'),
    'smtp_port': int(SECRETS.get('SMTP_PORT', 587)),
    'smtp_user': SECRETS.get('SMTP_USER', ''),
    'smtp_pass': SECRETS.get('SMTP_PASS', ''),
    'from_addr': SECRETS.get('SMTP_USER', ''),
    'to_addr': 'ronny@ronnyhullegie.nl',
}
