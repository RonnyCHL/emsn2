#!/usr/bin/env python3
"""
EMSN 2.0 - Dagelijkse SD Kaart Backup
Maakt een incrementele rsync backup van het systeem naar NAS

Draait dagelijks om 02:00 via systemd timer
Excludeert audio bestanden en tijdelijke data
"""

import os
import sys
import subprocess
import logging
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from pathlib import Path

# Voeg parent directory toe voor imports
sys.path.insert(0, str(Path(__file__).parent))
from backup_config import (
    STATION, DAILY_DIR, LOCAL_LOG_DIR, RSYNC_EXCLUDES,
    EMAIL_CONFIG, NAS_BACKUP_BASE
)

# Logging setup
LOCAL_LOG_DIR.mkdir(parents=True, exist_ok=True)
log_file = LOCAL_LOG_DIR / 'sd_backup_daily.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def send_alert(subject: str, message: str):
    """Stuur email alert bij problemen"""
    if not EMAIL_CONFIG['smtp_user']:
        logger.warning("Email niet geconfigureerd, skip alert")
        return

    try:
        msg = MIMEText(message)
        msg['Subject'] = f"[EMSN Backup] {subject}"
        msg['From'] = EMAIL_CONFIG['from_addr']
        msg['To'] = EMAIL_CONFIG['to_addr']

        with smtplib.SMTP(EMAIL_CONFIG['smtp_host'], EMAIL_CONFIG['smtp_port']) as server:
            server.starttls()
            server.login(EMAIL_CONFIG['smtp_user'], EMAIL_CONFIG['smtp_pass'])
            server.send_message(msg)

        logger.info(f"Alert email verstuurd: {subject}")
    except Exception as e:
        logger.error(f"Kon alert email niet versturen: {e}")


def check_nas_mount():
    """Controleer of NAS gemount is"""
    if not NAS_BACKUP_BASE.exists():
        raise RuntimeError(f"NAS backup directory niet gevonden: {NAS_BACKUP_BASE}")

    # Test schrijfrechten
    test_file = NAS_BACKUP_BASE / '.write_test'
    try:
        test_file.touch()
        test_file.unlink()
    except Exception as e:
        raise RuntimeError(f"Geen schrijfrechten op NAS: {e}")


def create_exclude_file():
    """Maak tijdelijk exclude bestand voor rsync"""
    exclude_file = Path('/tmp/rsync_excludes.txt')

    with open(exclude_file, 'w') as f:
        for exclude in RSYNC_EXCLUDES:
            f.write(f"{exclude}\n")

    return exclude_file


def run_rsync_backup():
    """Voer rsync backup uit naar NAS"""
    today = datetime.now().strftime('%Y-%m-%d')
    target_dir = DAILY_DIR / today

    # Maak target directory
    target_dir.mkdir(parents=True, exist_ok=True)

    # Exclude bestand
    exclude_file = create_exclude_file()

    # Rsync commando
    # -a: archive mode (behoudt permissies, timestamps, etc.)
    # -v: verbose
    # -x: blijf op één filesystem (geen mounts volgen)
    # --delete: verwijder bestanden die niet meer bestaan
    # --exclude-from: gebruik exclude bestand
    # --link-dest: hard links naar vorige backup (bespaart ruimte)

    # Zoek vorige backup voor hard links
    previous_backups = sorted([d for d in DAILY_DIR.iterdir() if d.is_dir() and d.name != today])
    link_dest_arg = []
    if previous_backups:
        link_dest_arg = ['--link-dest', str(previous_backups[-1])]

    cmd = [
        'rsync',
        '-avx',
        '--delete',
        '--exclude-from', str(exclude_file),
        *link_dest_arg,
        '/',
        str(target_dir) + '/'
    ]

    logger.info(f"Start rsync backup naar {target_dir}")
    logger.info(f"Commando: {' '.join(cmd)}")

    start_time = datetime.now()

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600  # 1 uur timeout
        )

        duration = (datetime.now() - start_time).total_seconds()

        if result.returncode == 0:
            logger.info(f"Rsync backup succesvol in {duration:.0f} seconden")
            return True, duration
        elif result.returncode == 24:
            # Returncode 24: "Partial transfer due to vanished source files"
            # Dit is normaal bij een draaiend systeem
            logger.warning(f"Rsync voltooid met waarschuwingen (code 24) in {duration:.0f} seconden")
            return True, duration
        else:
            logger.error(f"Rsync gefaald met code {result.returncode}")
            logger.error(f"stderr: {result.stderr}")
            return False, duration

    except subprocess.TimeoutExpired:
        logger.error("Rsync timeout na 1 uur")
        return False, 3600
    except Exception as e:
        logger.error(f"Rsync fout: {e}")
        return False, 0
    finally:
        # Cleanup exclude file
        exclude_file.unlink(missing_ok=True)


def get_backup_size():
    """Bereken totale grootte van daily backups"""
    total_size = 0

    for backup_dir in DAILY_DIR.iterdir():
        if backup_dir.is_dir():
            for f in backup_dir.rglob('*'):
                if f.is_file():
                    total_size += f.stat().st_size

    return total_size


def main():
    """Hoofdfunctie"""
    logger.info("=" * 60)
    logger.info(f"EMSN Dagelijkse Backup - Station: {STATION}")
    logger.info(f"Start: {datetime.now().isoformat()}")
    logger.info("=" * 60)

    try:
        # Pre-flight checks
        check_nas_mount()
        logger.info("NAS mount OK")

        # Voer backup uit
        success, duration = run_rsync_backup()

        if success:
            # Bereken statistieken
            total_size_gb = get_backup_size() / (1024**3)

            logger.info("-" * 60)
            logger.info(f"Backup succesvol voltooid")
            logger.info(f"Duur: {duration:.0f} seconden")
            logger.info(f"Totale opslag daily backups: {total_size_gb:.2f} GB")
            logger.info("=" * 60)
            return 0
        else:
            send_alert(
                f"Dagelijkse backup GEFAALD - {STATION}",
                f"De dagelijkse rsync backup voor {STATION} is mislukt.\n\n"
                f"Controleer de logs: {log_file}\n\n"
                f"Tijd: {datetime.now().isoformat()}"
            )
            return 1

    except Exception as e:
        logger.exception(f"Kritieke fout: {e}")
        send_alert(
            f"Dagelijkse backup KRITIEKE FOUT - {STATION}",
            f"Er is een kritieke fout opgetreden:\n\n{str(e)}\n\n"
            f"Controleer de logs: {log_file}"
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
