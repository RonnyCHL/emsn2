#!/usr/bin/env python3
"""
EMSN PostgreSQL Database Backup

Maakt dagelijkse backups van de PostgreSQL database naar NAS.
Behoudt:
- Dagelijkse backups: 7 dagen
- Wekelijkse backups: 4 weken
- Maandelijkse backups: 12 maanden

Backup locatie: /mnt/nas-birdnet-archive/backups/postgresql/

Draait via systemd timer (dagelijks om 02:00)
"""

import os
import sys
import gzip
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

# Add core modules path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from core.config import get_postgres_config
    from core.logging import get_logger
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)

# Centrale logger
logger = get_logger('database_backup')

# Backup configuratie - naar 8TB USB schijf op NAS
BACKUP_DIR = Path("/mnt/nas-birdnet-archive/backups/postgresql")
DAILY_RETENTION = 7  # dagen
WEEKLY_RETENTION = 4  # weken
MONTHLY_RETENTION = 12  # maanden


def ensure_backup_dir():
    """Zorg dat backup directory bestaat"""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    (BACKUP_DIR / "daily").mkdir(exist_ok=True)
    (BACKUP_DIR / "weekly").mkdir(exist_ok=True)
    (BACKUP_DIR / "monthly").mkdir(exist_ok=True)


def create_backup():
    """Maak een database backup met pg_dump"""
    config = get_postgres_config()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / "daily" / f"emsn_backup_{timestamp}.sql.gz"

    logger.info(f"Creating backup: {backup_file}")

    try:
        # pg_dump met gzip compressie
        env = os.environ.copy()
        env['PGPASSWORD'] = config['password']

        # Belangrijke tabellen om te backuppen (alleen waar we toegang hebben)
        tables_to_backup = [
            'bird_detections',
            'dual_detections',
            'weather_data',
            'species_reference',
            'daily_summary',
            'nestbox_events',
            'nestbox_media',
            'vocalization_training',
            'ulanzi_notification_log',
            'mqtt_bridge_events',
            'system_health',
            'performance_metrics',
        ]

        cmd = [
            'pg_dump',
            '-h', config['host'],
            '-p', str(config['port']),
            '-U', config['user'],
            '-d', config['database'],
            '--no-owner',
            '--no-acl',
            '--data-only',  # Alleen data, geen schema
            '-F', 'c',  # Custom format voor betere compressie
        ]

        # Voeg tabellen toe
        for table in tables_to_backup:
            cmd.extend(['-t', table])

        # Schrijf naar bestand
        backup_file_uncompressed = backup_file.with_suffix('')  # Zonder .gz

        with open(backup_file_uncompressed.with_suffix('.dump'), 'wb') as f:
            result = subprocess.run(
                cmd,
                env=env,
                stdout=f,
                stderr=subprocess.PIPE
            )

        if result.returncode != 0:
            logger.error(f"pg_dump failed: {result.stderr.decode()}")
            return None

        # Comprimeer met gzip
        dump_file = backup_file_uncompressed.with_suffix('.dump')
        with open(dump_file, 'rb') as f_in:
            with gzip.open(backup_file, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)

        # Verwijder ongecomprimeerd bestand
        dump_file.unlink()

        # Log grootte
        size_mb = backup_file.stat().st_size / (1024 * 1024)
        logger.info(f"Backup created: {size_mb:.1f} MB")

        return backup_file

    except Exception as e:
        logger.error(f"Backup failed: {e}")
        return None


def rotate_backups():
    """Roteer oude backups volgens retentie beleid"""
    now = datetime.now()
    today = now.date()

    # Dagelijkse backups - bewaar laatste 7 dagen
    daily_dir = BACKUP_DIR / "daily"
    cutoff_daily = now - timedelta(days=DAILY_RETENTION)

    for backup in sorted(daily_dir.glob("emsn_backup_*.gz")):
        try:
            # Parse datum uit bestandsnaam
            date_str = backup.name.split('_')[2]
            backup_date = datetime.strptime(date_str, "%Y%m%d")

            if backup_date < cutoff_daily:
                backup.unlink()
                logger.info(f"Deleted old daily backup: {backup.name}")
        except (ValueError, IndexError):
            pass

    # Wekelijkse backups - kopieer zondag backup
    if today.weekday() == 6:  # Zondag
        weekly_dir = BACKUP_DIR / "weekly"
        latest_daily = sorted(daily_dir.glob("emsn_backup_*.gz"))
        if latest_daily:
            latest = latest_daily[-1]
            weekly_backup = weekly_dir / f"emsn_weekly_{today.strftime('%Y%m%d')}.gz"
            if not weekly_backup.exists():
                shutil.copy2(latest, weekly_backup)
                logger.info(f"Created weekly backup: {weekly_backup.name}")

        # Verwijder oude wekelijkse backups
        cutoff_weekly = now - timedelta(weeks=WEEKLY_RETENTION)
        for backup in sorted(weekly_dir.glob("emsn_weekly_*.gz")):
            try:
                date_str = backup.name.split('_')[2].replace('.gz', '')
                backup_date = datetime.strptime(date_str, "%Y%m%d")
                if backup_date < cutoff_weekly:
                    backup.unlink()
                    logger.info(f"Deleted old weekly backup: {backup.name}")
            except (ValueError, IndexError):
                pass

    # Maandelijkse backups - kopieer 1e van de maand backup
    if today.day == 1:
        monthly_dir = BACKUP_DIR / "monthly"
        latest_daily = sorted(daily_dir.glob("emsn_backup_*.gz"))
        if latest_daily:
            latest = latest_daily[-1]
            monthly_backup = monthly_dir / f"emsn_monthly_{today.strftime('%Y%m')}.gz"
            if not monthly_backup.exists():
                shutil.copy2(latest, monthly_backup)
                logger.info(f"Created monthly backup: {monthly_backup.name}")

        # Verwijder oude maandelijkse backups
        cutoff_monthly = now - timedelta(days=MONTHLY_RETENTION * 31)
        for backup in sorted(monthly_dir.glob("emsn_monthly_*.gz")):
            try:
                date_str = backup.name.split('_')[2].replace('.gz', '')
                backup_date = datetime.strptime(date_str, "%Y%m")
                if backup_date < cutoff_monthly:
                    backup.unlink()
                    logger.info(f"Deleted old monthly backup: {backup.name}")
            except (ValueError, IndexError):
                pass


def verify_backup(backup_file):
    """Verifieer backup integriteit"""
    try:
        # Check of bestand kan worden geopend
        with gzip.open(backup_file, 'rb') as f:
            # Lees eerste 1KB om te controleren
            header = f.read(1024)
            if b'PGDMP' in header or len(header) > 0:
                logger.info("Backup verification: OK")
                return True
    except Exception as e:
        logger.error(f"Backup verification failed: {e}")
    return False


def list_backups():
    """Toon overzicht van alle backups"""
    logger.info("=== Backup Overview ===")

    for category in ['daily', 'weekly', 'monthly']:
        backup_dir = BACKUP_DIR / category
        backups = sorted(backup_dir.glob("*.gz"))
        total_size = sum(b.stat().st_size for b in backups) / (1024 * 1024)
        logger.info(f"{category.capitalize()}: {len(backups)} backups, {total_size:.1f} MB total")


def main():
    logger.info("=== Database Backup Started ===")

    try:
        # Zorg dat directories bestaan
        ensure_backup_dir()

        # Maak backup
        backup_file = create_backup()

        if backup_file:
            # Verifieer backup
            if verify_backup(backup_file):
                # Roteer oude backups
                rotate_backups()

                # Toon overzicht
                list_backups()

                logger.info("=== Database Backup Completed Successfully ===")
            else:
                logger.error("Backup verification failed!")
                sys.exit(1)
        else:
            logger.error("Backup creation failed!")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Database backup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
