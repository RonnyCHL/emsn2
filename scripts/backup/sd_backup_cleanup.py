#!/usr/bin/env python3
"""
EMSN 2.0 - Backup Cleanup Script
Verwijdert oude backups volgens retentiebeleid:
- Images: 7 dagen
- Daily rsync: 7 dagen
- Database dumps: 7 dagen

Draait dagelijks na de backup via systemd timer
"""

import os
import sys
import logging
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from pathlib import Path

# Voeg parent directory toe voor imports
sys.path.insert(0, str(Path(__file__).parent))
from backup_config import (
    STATION, IMAGES_DIR, DAILY_DIR, DATABASE_DIR, LOCAL_LOG_DIR,
    RETENTION_DAYS_IMAGES, RETENTION_DAYS_DAILY, RETENTION_DAYS_DATABASE,
    EMAIL_CONFIG, NAS_BACKUP_BASE
)

# Logging setup
LOCAL_LOG_DIR.mkdir(parents=True, exist_ok=True)
log_file = LOCAL_LOG_DIR / 'sd_backup_cleanup.log'

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

    except Exception as e:
        logger.error(f"Kon alert email niet versturen: {e}")


def get_age_days(path: Path) -> int:
    """Bepaal leeftijd van bestand/map in dagen"""
    try:
        mtime = path.stat().st_mtime
        age = datetime.now() - datetime.fromtimestamp(mtime)
        return age.days
    except Exception:
        return 0


def parse_date_from_name(name: str) -> datetime | None:
    """Probeer datum uit bestandsnaam te halen (YYYY-MM-DD formaat)"""
    import re
    match = re.search(r'(\d{4}-\d{2}-\d{2})', name)
    if match:
        try:
            return datetime.strptime(match.group(1), '%Y-%m-%d')
        except ValueError:
            pass
    return None


def cleanup_images(retention_days: int) -> tuple[int, int]:
    """Verwijder oude image bestanden"""
    deleted_count = 0
    deleted_size = 0
    cutoff_date = datetime.now() - timedelta(days=retention_days)

    if not IMAGES_DIR.exists():
        logger.warning(f"Images directory niet gevonden: {IMAGES_DIR}")
        return 0, 0

    for image_file in IMAGES_DIR.glob('*.img.gz'):
        # Probeer datum uit naam te halen
        file_date = parse_date_from_name(image_file.name)

        if file_date and file_date < cutoff_date:
            file_size = image_file.stat().st_size
            logger.info(f"Verwijder oud image: {image_file.name} (datum: {file_date.date()})")

            try:
                image_file.unlink()
                deleted_count += 1
                deleted_size += file_size
            except Exception as e:
                logger.error(f"Kon {image_file} niet verwijderen: {e}")

        elif not file_date and get_age_days(image_file) > retention_days:
            # Fallback: gebruik modification time
            file_size = image_file.stat().st_size
            logger.info(f"Verwijder oud image: {image_file.name} (leeftijd: {get_age_days(image_file)} dagen)")

            try:
                image_file.unlink()
                deleted_count += 1
                deleted_size += file_size
            except Exception as e:
                logger.error(f"Kon {image_file} niet verwijderen: {e}")

    return deleted_count, deleted_size


def cleanup_daily_backups(retention_days: int) -> tuple[int, int]:
    """Verwijder oude dagelijkse rsync backups"""
    deleted_count = 0
    deleted_size = 0
    cutoff_date = datetime.now() - timedelta(days=retention_days)

    if not DAILY_DIR.exists():
        logger.warning(f"Daily directory niet gevonden: {DAILY_DIR}")
        return 0, 0

    for backup_dir in DAILY_DIR.iterdir():
        if not backup_dir.is_dir():
            continue

        # Probeer datum uit mapnaam te halen
        dir_date = parse_date_from_name(backup_dir.name)

        should_delete = False
        if dir_date and dir_date < cutoff_date:
            should_delete = True
            reason = f"datum: {dir_date.date()}"
        elif not dir_date and get_age_days(backup_dir) > retention_days:
            should_delete = True
            reason = f"leeftijd: {get_age_days(backup_dir)} dagen"

        if should_delete:
            # Bereken grootte
            dir_size = sum(f.stat().st_size for f in backup_dir.rglob('*') if f.is_file())
            logger.info(f"Verwijder oude daily backup: {backup_dir.name} ({reason})")

            try:
                import shutil
                shutil.rmtree(backup_dir)
                deleted_count += 1
                deleted_size += dir_size
            except Exception as e:
                logger.error(f"Kon {backup_dir} niet verwijderen: {e}")

    return deleted_count, deleted_size


def cleanup_database_backups(retention_days: int) -> tuple[int, int]:
    """Verwijder oude database dumps"""
    deleted_count = 0
    deleted_size = 0
    cutoff_date = datetime.now() - timedelta(days=retention_days)

    if not DATABASE_DIR.exists():
        logger.warning(f"Database directory niet gevonden: {DATABASE_DIR}")
        return 0, 0

    for db_file in DATABASE_DIR.glob('*.sql.gz'):
        # Parse datum-tijd uit bestandsnaam (birds-YYYY-MM-DD-HH.sql.gz)
        import re
        match = re.search(r'(\d{4}-\d{2}-\d{2})-(\d{2})', db_file.name)

        if match:
            try:
                file_date = datetime.strptime(f"{match.group(1)} {match.group(2)}", '%Y-%m-%d %H')
                if file_date < cutoff_date:
                    file_size = db_file.stat().st_size
                    logger.info(f"Verwijder oude database dump: {db_file.name}")

                    try:
                        db_file.unlink()
                        deleted_count += 1
                        deleted_size += file_size
                    except Exception as e:
                        logger.error(f"Kon {db_file} niet verwijderen: {e}")
            except ValueError:
                pass
        elif get_age_days(db_file) > retention_days:
            file_size = db_file.stat().st_size
            logger.info(f"Verwijder oude database dump: {db_file.name} (leeftijd: {get_age_days(db_file)} dagen)")

            try:
                db_file.unlink()
                deleted_count += 1
                deleted_size += file_size
            except Exception as e:
                logger.error(f"Kon {db_file} niet verwijderen: {e}")

    return deleted_count, deleted_size


def get_storage_stats() -> dict:
    """Verzamel opslagstatistieken"""
    stats = {
        'images': {'count': 0, 'size': 0},
        'daily': {'count': 0, 'size': 0},
        'database': {'count': 0, 'size': 0},
    }

    if IMAGES_DIR.exists():
        for f in IMAGES_DIR.glob('*.img.gz'):
            stats['images']['count'] += 1
            stats['images']['size'] += f.stat().st_size

    if DAILY_DIR.exists():
        for d in DAILY_DIR.iterdir():
            if d.is_dir():
                stats['daily']['count'] += 1
                stats['daily']['size'] += sum(f.stat().st_size for f in d.rglob('*') if f.is_file())

    if DATABASE_DIR.exists():
        for f in DATABASE_DIR.glob('*.sql.gz'):
            stats['database']['count'] += 1
            stats['database']['size'] += f.stat().st_size

    return stats


def main():
    """Hoofdfunctie"""
    logger.info("=" * 60)
    logger.info(f"EMSN Backup Cleanup - Station: {STATION}")
    logger.info(f"Start: {datetime.now().isoformat()}")
    logger.info(f"Retentie: Images={RETENTION_DAYS_IMAGES}d, Daily={RETENTION_DAYS_DAILY}d, DB={RETENTION_DAYS_DATABASE}d")
    logger.info("=" * 60)

    total_deleted = 0
    total_size = 0

    try:
        # Cleanup images
        logger.info("\n--- Cleanup Images ---")
        count, size = cleanup_images(RETENTION_DAYS_IMAGES)
        total_deleted += count
        total_size += size
        logger.info(f"Images: {count} verwijderd ({size / (1024**3):.2f} GB)")

        # Cleanup daily backups
        logger.info("\n--- Cleanup Daily Backups ---")
        count, size = cleanup_daily_backups(RETENTION_DAYS_DAILY)
        total_deleted += count
        total_size += size
        logger.info(f"Daily: {count} verwijderd ({size / (1024**3):.2f} GB)")

        # Cleanup database dumps
        logger.info("\n--- Cleanup Database Dumps ---")
        count, size = cleanup_database_backups(RETENTION_DAYS_DATABASE)
        total_deleted += count
        total_size += size
        logger.info(f"Database: {count} verwijderd ({size / (1024**2):.0f} MB)")

        # Statistieken
        stats = get_storage_stats()

        logger.info("\n" + "-" * 60)
        logger.info("Huidige opslag:")
        logger.info(f"  Images: {stats['images']['count']} bestanden, {stats['images']['size'] / (1024**3):.2f} GB")
        logger.info(f"  Daily:  {stats['daily']['count']} backups, {stats['daily']['size'] / (1024**3):.2f} GB")
        logger.info(f"  Database: {stats['database']['count']} dumps, {stats['database']['size'] / (1024**2):.0f} MB")
        logger.info("-" * 60)
        logger.info(f"Totaal verwijderd: {total_deleted} items ({total_size / (1024**3):.2f} GB)")
        logger.info("=" * 60)

        return 0

    except Exception as e:
        logger.exception(f"Kritieke fout: {e}")
        send_alert(
            f"Backup cleanup GEFAALD - {STATION}",
            f"De backup cleanup is mislukt.\n\n"
            f"Fout: {str(e)}\n\n"
            f"Controleer de logs: {log_file}"
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
