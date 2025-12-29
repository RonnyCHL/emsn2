#!/usr/bin/env python3
"""
EMSN 2.0 - Screenshot Cleanup Script

Verwijdert oude screenshots ouder dan 30 dagen.
Draait dagelijks via systemd timer.
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
import logging
import psycopg2

# Import core modules
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.config import get_postgres_config

# Configuratie
SCREENSHOT_DIR = Path("/mnt/nas-reports/ulanzi-screenshots")
MAX_AGE_DAYS = 30
DB_CONFIG = get_postgres_config()

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_db_connection():
    """Maak database connectie."""
    return psycopg2.connect(**DB_CONFIG)


def cleanup_screenshots():
    """Verwijder screenshots ouder dan MAX_AGE_DAYS."""
    cutoff_date = datetime.now() - timedelta(days=MAX_AGE_DAYS)
    cutoff_str = cutoff_date.strftime('%Y-%m-%d')

    logger.info(f"Starting cleanup - removing screenshots older than {cutoff_str}")

    deleted_files = 0
    deleted_dirs = 0
    freed_bytes = 0

    # Loop door date directories
    for date_dir in SCREENSHOT_DIR.iterdir():
        if not date_dir.is_dir():
            continue

        # Parse directory name als datum
        try:
            dir_date = datetime.strptime(date_dir.name, '%Y-%m-%d')
        except ValueError:
            continue  # Skip non-date directories

        if dir_date < cutoff_date:
            # Verwijder alle files in deze directory
            for screenshot in date_dir.iterdir():
                if screenshot.is_file():
                    freed_bytes += screenshot.stat().st_size
                    screenshot.unlink()
                    deleted_files += 1

            # Verwijder de lege directory
            try:
                date_dir.rmdir()
                deleted_dirs += 1
                logger.info(f"Removed directory: {date_dir.name}")
            except OSError:
                logger.warning(f"Could not remove directory: {date_dir.name}")

    logger.info(f"Cleanup complete: {deleted_files} files, {deleted_dirs} directories")
    logger.info(f"Freed {freed_bytes / 1024 / 1024:.2f} MB")

    return deleted_files, deleted_dirs, freed_bytes


def cleanup_database():
    """Verwijder oude records uit ulanzi_screenshots tabel."""
    cutoff_date = datetime.now() - timedelta(days=MAX_AGE_DAYS)

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Tel oude records
        cursor.execute(
            "SELECT COUNT(*) FROM ulanzi_screenshots WHERE timestamp < %s",
            (cutoff_date,)
        )
        count = cursor.fetchone()[0]

        if count > 0:
            # Verwijder oude records
            cursor.execute(
                "DELETE FROM ulanzi_screenshots WHERE timestamp < %s",
                (cutoff_date,)
            )
            conn.commit()
            logger.info(f"Removed {count} old records from database")
        else:
            logger.info("No old database records to remove")

        cursor.close()
        conn.close()

        return count

    except Exception as e:
        logger.error(f"Database cleanup error: {e}")
        return 0


def cleanup_orphaned_db_records():
    """Verwijder database records voor niet-bestaande files."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Haal alle records op
        cursor.execute("SELECT id, filepath FROM ulanzi_screenshots")
        records = cursor.fetchall()

        orphaned = []
        for record_id, filepath in records:
            if filepath and not Path(filepath).exists():
                orphaned.append(record_id)

        if orphaned:
            cursor.execute(
                "DELETE FROM ulanzi_screenshots WHERE id = ANY(%s)",
                (orphaned,)
            )
            conn.commit()
            logger.info(f"Removed {len(orphaned)} orphaned database records")

        cursor.close()
        conn.close()

        return len(orphaned)

    except Exception as e:
        logger.error(f"Orphan cleanup error: {e}")
        return 0


def main():
    """Main cleanup functie."""
    logger.info("=" * 50)
    logger.info("EMSN Screenshot Cleanup Started")
    logger.info("=" * 50)

    # Controleer of directory bestaat
    if not SCREENSHOT_DIR.exists():
        logger.error(f"Screenshot directory not found: {SCREENSHOT_DIR}")
        sys.exit(1)

    # Cleanup screenshots
    files, dirs, freed = cleanup_screenshots()

    # Cleanup database
    db_count = cleanup_database()

    # Cleanup orphaned records
    orphan_count = cleanup_orphaned_db_records()

    logger.info("=" * 50)
    logger.info("Cleanup Summary:")
    logger.info(f"  Files deleted: {files}")
    logger.info(f"  Directories removed: {dirs}")
    logger.info(f"  Space freed: {freed / 1024 / 1024:.2f} MB")
    logger.info(f"  DB records removed: {db_count}")
    logger.info(f"  Orphaned records: {orphan_count}")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
