#!/usr/bin/env python3
"""
EMSN 2.0 - Backup Cleanup Script
Verwijdert oude database backups ouder dan retentieperiode
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Configuratie
BACKUP_DIRS = [
    '/mnt/usb/database/backups',
]
RETENTION_DAYS = 7
LOG_DIR = Path('/mnt/usb/logs')

# Logging setup
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'backup_cleanup.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def get_file_age_days(filepath):
    """Get file age in days based on modification time"""
    mtime = os.path.getmtime(filepath)
    age = datetime.now() - datetime.fromtimestamp(mtime)
    return age.days


def cleanup_old_backups(backup_dir, retention_days=RETENTION_DAYS):
    """Remove backup files older than retention period"""
    backup_path = Path(backup_dir)

    if not backup_path.exists():
        logger.warning(f"Backup directory does not exist: {backup_dir}")
        return 0

    deleted_count = 0
    deleted_size = 0

    # Find all .db files in backup directory
    for filepath in backup_path.glob('*.db'):
        age_days = get_file_age_days(filepath)

        if age_days > retention_days:
            file_size = filepath.stat().st_size
            logger.info(f"Deleting old backup: {filepath.name} (age: {age_days} days, size: {file_size / 1024 / 1024:.2f} MB)")

            try:
                filepath.unlink()
                deleted_count += 1
                deleted_size += file_size
            except Exception as e:
                logger.error(f"Failed to delete {filepath}: {e}")
        else:
            logger.debug(f"Keeping backup: {filepath.name} (age: {age_days} days)")

    return deleted_count, deleted_size


def main():
    """Main execution"""
    logger.info("=" * 60)
    logger.info("EMSN Backup Cleanup Started")
    logger.info(f"Retention period: {RETENTION_DAYS} days")
    logger.info("=" * 60)

    total_deleted = 0
    total_size = 0

    for backup_dir in BACKUP_DIRS:
        logger.info(f"Processing: {backup_dir}")
        deleted, size = cleanup_old_backups(backup_dir)
        total_deleted += deleted
        total_size += size

    logger.info("-" * 60)
    if total_deleted > 0:
        logger.info(f"Cleanup completed: {total_deleted} files deleted ({total_size / 1024 / 1024:.2f} MB)")
    else:
        logger.info("Cleanup completed: No old backups to delete")
    logger.info("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
