#!/usr/bin/env python3
"""
EMSN 2.0 - Database Mirror Sync

Beschrijving: Syncs BirdNET-Pi database to USB mirror with integrity checks
Auteur: Claude AI + Ronny
Datum: 2025-12-05
Station: All
"""

import os
import sys
import sqlite3
import logging
from pathlib import Path

# Paths
SOURCE_DB = "/home/ronny/BirdNET-Pi/scripts/birds.db"
MIRROR_DB = "/mnt/usb/database/birds_mirror.db"
LOG_PATH = "/mnt/usb/logs"

# Ensure log directory exists
os.makedirs(LOG_PATH, exist_ok=True)

# Logging setup (naar USB!)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"{LOG_PATH}/database_mirror_sync.log"),
        logging.StreamHandler(sys.stdout)  # Explicitly use stdout for systemd
    ]
)
logger = logging.getLogger(__name__)


def verify_prerequisites():
    """Verify all prerequisites before running"""
    checks = {
        "USB mounted": os.path.ismount("/mnt/usb"),
        "Source DB exists": os.path.exists(SOURCE_DB),
        "Mirror directory exists": os.path.exists(os.path.dirname(MIRROR_DB))
    }

    all_passed = True
    for check, result in checks.items():
        if result:
            logger.info(f"✓ {check}")
        else:
            logger.error(f"✗ {check}")
            all_passed = False

    return all_passed


def get_record_count(db_path):
    """Get the number of records in detections table"""
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM detections")
            return cursor.fetchone()[0]
    except Exception as e:
        logger.error(f"Failed to count records in {db_path}: {e}")
        return None


def check_integrity(db_path):
    """Run SQLite PRAGMA integrity_check"""
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check")
            return cursor.fetchone()[0] == "ok"
    except Exception as e:
        logger.error(f"Integrity check failed for {db_path}: {e}")
        return False


def sync_database():
    """Main sync function using SQLite backup API for atomic copy.

    Note: BirdNET-Pi writes continuously, so we use sqlite3 backup API
    to get a consistent snapshot. Record count comparison against live
    source is unreliable due to race conditions.
    """
    logger.info("Starting database mirror sync")

    # Use SQLite backup API for atomic, consistent copy
    source_conn = None
    dest_conn = None
    try:
        logger.info(f"Creating atomic backup of {SOURCE_DB}")
        source_conn = sqlite3.connect(SOURCE_DB)
        dest_conn = sqlite3.connect(MIRROR_DB)

        # SQLite backup API: creates consistent snapshot even with concurrent writes
        source_conn.backup(dest_conn)
        logger.info("Backup completed")
    except Exception as e:
        logger.error(f"Backup failed: {e}")
        return False
    finally:
        if dest_conn:
            dest_conn.close()
        if source_conn:
            source_conn.close()

    # Verify integrity of mirror
    logger.info("Running integrity check on mirror database")
    if not check_integrity(MIRROR_DB):
        logger.error("Mirror database failed integrity check!")
        return False

    logger.info("✓ Mirror database passed integrity check")

    # Get mirror record count (for logging only)
    mirror_count = get_record_count(MIRROR_DB)
    if mirror_count is None:
        logger.error("Cannot read mirror database")
        return False

    logger.info(f"✓ Mirror contains {mirror_count} records")
    logger.info(f"✓ Sync completed successfully")

    return True


def main():
    """Main execution"""
    logger.info("Script started")

    try:
        # Verificatie
        if not verify_prerequisites():
            logger.error("Prerequisites not met, exiting")
            sys.exit(1)

        # Sync database
        if not sync_database():
            logger.error("Database sync failed")
            sys.exit(1)

        logger.info("Script completed successfully")
        return 0

    except Exception as e:
        logger.error(f"Script failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
