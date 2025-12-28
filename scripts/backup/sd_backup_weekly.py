#!/usr/bin/env python3
"""
EMSN 2.0 - Wekelijkse SD Kaart Image Backup
Maakt een volledige gecomprimeerde image van de SD kaart

Draait wekelijks op zondag om 03:00 via systemd timer
Image is compatibel met Raspberry Pi Imager

Stappen:
1. Maak raw image met dd
2. Shrink image met pishrink (optioneel)
3. Comprimeer met gzip
4. Kopieer naar NAS
"""

import os
import sys
import subprocess
import shutil
import logging
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from pathlib import Path

# Voeg parent directory toe voor imports
sys.path.insert(0, str(Path(__file__).parent))
from backup_config import (
    STATION, IMAGES_DIR, LOCAL_LOG_DIR,
    EMAIL_CONFIG, NAS_BACKUP_BASE, RSYNC_EXCLUDES
)

# Logging setup
LOCAL_LOG_DIR.mkdir(parents=True, exist_ok=True)
log_file = LOCAL_LOG_DIR / 'sd_backup_weekly.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Tijdelijke locatie voor image
# Gebruik USB schijf als temp (meer ruimte dan /tmp)
# Fallback naar /tmp als USB niet beschikbaar
USB_TEMP = Path('/mnt/usb/sd-backup-temp')
TMP_TEMP = Path('/tmp/sd-backup')

def get_temp_dir():
    """Bepaal beste temp directory op basis van beschikbare ruimte"""
    # Probeer USB schijf eerst
    if USB_TEMP.parent.exists():
        try:
            usb_stat = os.statvfs(USB_TEMP.parent)
            usb_free = (usb_stat.f_frsize * usb_stat.f_bavail) / (1024**3)
            if usb_free > 10:
                return USB_TEMP
        except Exception:
            pass

    # Fallback naar /tmp
    return TMP_TEMP

TEMP_DIR = get_temp_dir()


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


def check_prerequisites():
    """Controleer of alle benodigdheden aanwezig zijn"""
    global TEMP_DIR
    TEMP_DIR = get_temp_dir()

    # Check NAS mount
    if not NAS_BACKUP_BASE.exists():
        raise RuntimeError(f"NAS backup directory niet gevonden: {NAS_BACKUP_BASE}")

    # Check of we root zijn (nodig voor dd)
    if os.geteuid() != 0:
        raise RuntimeError("Dit script moet als root draaien (sudo)")

    # Check disk space op temp directory
    temp_parent = TEMP_DIR.parent if not TEMP_DIR.exists() else TEMP_DIR
    tmp_stat = os.statvfs(temp_parent)
    free_gb = (tmp_stat.f_frsize * tmp_stat.f_bavail) / (1024**3)

    logger.info(f"Temp directory: {TEMP_DIR}")
    logger.info(f"Vrije ruimte: {free_gb:.1f} GB")

    if free_gb < 10:
        raise RuntimeError(f"Onvoldoende vrije ruimte in {temp_parent}: {free_gb:.1f}GB (minimaal 10GB nodig)")


def get_sd_device():
    """Vind de SD kaart device"""
    # Op Raspberry Pi is de SD kaart meestal /dev/mmcblk0
    if Path('/dev/mmcblk0').exists():
        return '/dev/mmcblk0'

    # Fallback: zoek naar root device
    result = subprocess.run(
        ['findmnt', '-n', '-o', 'SOURCE', '/'],
        capture_output=True, text=True
    )
    root_device = result.stdout.strip()

    # Haal partition nummer weg (bijv. /dev/mmcblk0p2 -> /dev/mmcblk0)
    if 'mmcblk' in root_device:
        return root_device.rstrip('0123456789').rstrip('p')
    elif root_device.startswith('/dev/sd'):
        return root_device.rstrip('0123456789')

    raise RuntimeError(f"Kan SD kaart device niet bepalen: {root_device}")


def get_sd_size_bytes(device: str) -> int:
    """Bepaal grootte van SD kaart in bytes"""
    result = subprocess.run(
        ['blockdev', '--getsize64', device],
        capture_output=True, text=True, check=True
    )
    return int(result.stdout.strip())


def create_compressed_image_stream(device: str, output_path: Path) -> bool:
    """
    Maak gecomprimeerd image door direct te streamen: dd | pigz > file
    Dit vereist geen lokale temp ruimte voor het raw image.
    """
    logger.info(f"Maak gecomprimeerd image van {device} naar {output_path}")

    # Sync eerst alle buffers
    subprocess.run(['sync'], check=True)

    # Bepaal SD grootte
    sd_size = get_sd_size_bytes(device)
    sd_size_gb = sd_size / (1024**3)
    logger.info(f"SD kaart grootte: {sd_size_gb:.1f} GB")

    # Gebruik pigz voor parallelle compressie, anders gzip
    gzip_cmd = 'pigz' if shutil.which('pigz') else 'gzip'

    # Stream direct: dd | pigz > output.img.gz
    cmd = f'dd if={device} bs=4M status=progress 2>&1 | {gzip_cmd} > {output_path}'

    logger.info(f"Streaming met compressie naar {output_path}")
    logger.info("Dit kan 30-60 minuten duren...")

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=False,  # Laat output door voor progress
            timeout=14400  # 4 uur timeout voor grote schijven
        )

        if result.returncode == 0 and output_path.exists():
            final_size = output_path.stat().st_size / (1024**3)
            compression = (1 - final_size / sd_size_gb) * 100
            logger.info(f"Image succesvol gemaakt: {final_size:.2f} GB ({compression:.0f}% compressie)")
            return True
        else:
            logger.error(f"dd|gzip gefaald met code {result.returncode}")
            return False

    except subprocess.TimeoutExpired:
        logger.error("Timeout na 4 uur")
        return False
    except Exception as e:
        logger.error(f"Fout: {e}")
        return False


def create_raw_image(device: str, output_path: Path) -> bool:
    """Maak raw image met dd (legacy, voor kleine SD kaarten)"""
    logger.info(f"Maak raw image van {device} naar {output_path}")

    # Sync eerst alle buffers
    subprocess.run(['sync'], check=True)

    # Bepaal SD grootte
    sd_size = get_sd_size_bytes(device)
    sd_size_gb = sd_size / (1024**3)
    logger.info(f"SD kaart grootte: {sd_size_gb:.1f} GB")

    cmd = [
        'dd',
        f'if={device}',
        f'of={output_path}',
        'bs=4M',
        'status=progress'
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=7200  # 2 uur timeout
        )

        if result.returncode == 0:
            logger.info("Raw image succesvol gemaakt")
            return True
        else:
            logger.error(f"dd gefaald: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        logger.error("dd timeout na 2 uur")
        return False
    except Exception as e:
        logger.error(f"dd fout: {e}")
        return False


def shrink_image(image_path: Path) -> bool:
    """
    Shrink image met pishrink.sh (indien geinstalleerd)
    Dit maakt het image kleiner door lege ruimte te verwijderen
    """
    pishrink = Path('/usr/local/bin/pishrink.sh')

    if not pishrink.exists():
        logger.info("pishrink.sh niet gevonden, skip shrinking")
        return True  # Niet fataal

    logger.info("Shrink image met pishrink...")

    try:
        result = subprocess.run(
            [str(pishrink), '-s', str(image_path)],
            capture_output=True,
            text=True,
            timeout=3600  # 1 uur timeout
        )

        if result.returncode == 0:
            logger.info("Image succesvol verkleind")
            return True
        else:
            logger.warning(f"pishrink waarschuwing: {result.stderr}")
            return True  # Niet fataal

    except Exception as e:
        logger.warning(f"pishrink fout (niet fataal): {e}")
        return True


def compress_image(image_path: Path, output_path: Path) -> bool:
    """Comprimeer image met gzip"""
    logger.info(f"Comprimeer image naar {output_path}")

    original_size = image_path.stat().st_size
    logger.info(f"Originele grootte: {original_size / (1024**3):.2f} GB")

    try:
        # Gebruik pigz voor parallelle compressie (sneller), anders gzip
        gzip_cmd = 'pigz' if shutil.which('pigz') else 'gzip'

        cmd = f"{gzip_cmd} -c {image_path} > {output_path}"
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=7200  # 2 uur timeout
        )

        if result.returncode == 0 and output_path.exists():
            compressed_size = output_path.stat().st_size
            ratio = (1 - compressed_size / original_size) * 100
            logger.info(f"Gecomprimeerde grootte: {compressed_size / (1024**3):.2f} GB ({ratio:.1f}% bespaard)")
            return True
        else:
            logger.error(f"Compressie gefaald: {result.stderr}")
            return False

    except Exception as e:
        logger.error(f"Compressie fout: {e}")
        return False


def copy_to_nas(source: Path, dest_dir: Path) -> bool:
    """Kopieer image naar NAS"""
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / source.name

    logger.info(f"Kopieer naar NAS: {dest_path}")

    try:
        shutil.copy2(source, dest_path)

        # Verify kopie
        if dest_path.exists():
            source_size = source.stat().st_size
            dest_size = dest_path.stat().st_size

            if source_size == dest_size:
                logger.info("Kopie naar NAS succesvol geverifieerd")
                return True
            else:
                logger.error(f"Grootte mismatch: {source_size} != {dest_size}")
                return False
        else:
            logger.error("Bestemmingsbestand niet gevonden na kopie")
            return False

    except Exception as e:
        logger.error(f"Kopie naar NAS gefaald: {e}")
        return False


def cleanup_temp():
    """Ruim tijdelijke bestanden op"""
    if TEMP_DIR.exists():
        logger.info(f"Cleanup {TEMP_DIR}")
        shutil.rmtree(TEMP_DIR, ignore_errors=True)


def main():
    """Hoofdfunctie"""
    logger.info("=" * 60)
    logger.info(f"EMSN Wekelijkse Image Backup - Station: {STATION}")
    logger.info(f"Start: {datetime.now().isoformat()}")
    logger.info("=" * 60)

    start_time = datetime.now()
    today = start_time.strftime('%Y-%m-%d')

    # Bestandsnamen
    image_name = f"emsn2-{STATION}-{today}.img"
    compressed_name = f"{image_name}.gz"

    try:
        # Check of we root zijn
        if os.geteuid() != 0:
            raise RuntimeError("Dit script moet als root draaien (sudo)")

        # Check NAS mount
        if not NAS_BACKUP_BASE.exists():
            raise RuntimeError(f"NAS backup directory niet gevonden: {NAS_BACKUP_BASE}")

        # Maak output directory op NAS
        IMAGES_DIR.mkdir(parents=True, exist_ok=True)

        # Bepaal SD device
        sd_device = get_sd_device()
        logger.info(f"SD device: {sd_device}")

        # Direct streamen naar NAS: dd | pigz > NAS/image.gz
        # Dit vereist geen lokale temp ruimte!
        final_path = IMAGES_DIR / compressed_name

        if not create_compressed_image_stream(sd_device, final_path):
            raise RuntimeError("Maken gecomprimeerd image gefaald")

        # Success!
        duration = (datetime.now() - start_time).total_seconds() / 60
        final_size = (IMAGES_DIR / compressed_name).stat().st_size / (1024**3)

        logger.info("-" * 60)
        logger.info(f"Image backup succesvol voltooid!")
        logger.info(f"Bestand: {IMAGES_DIR / compressed_name}")
        logger.info(f"Grootte: {final_size:.2f} GB")
        logger.info(f"Duur: {duration:.0f} minuten")
        logger.info("=" * 60)

        # Stuur success notificatie
        send_alert(
            f"Wekelijkse backup OK - {STATION}",
            f"De wekelijkse SD image backup is succesvol voltooid.\n\n"
            f"Bestand: {compressed_name}\n"
            f"Grootte: {final_size:.2f} GB\n"
            f"Duur: {duration:.0f} minuten\n\n"
            f"Locatie: {IMAGES_DIR}"
        )

        return 0

    except Exception as e:
        logger.exception(f"Kritieke fout: {e}")
        send_alert(
            f"Wekelijkse backup GEFAALD - {STATION}",
            f"De wekelijkse SD image backup is mislukt.\n\n"
            f"Fout: {str(e)}\n\n"
            f"Controleer de logs: {log_file}"
        )
        return 1

    finally:
        cleanup_temp()


if __name__ == "__main__":
    sys.exit(main())
