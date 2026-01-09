#!/usr/bin/env python3
"""
EMSN Log Cleanup Script

Verwijdert oude log bestanden die niet door logrotate worden beheerd:
- Oude geroteerde logs (.log.1, .log.2, etc.)
- Gedateerde logs ouder dan retentie
- Gecomprimeerde logs ouder dan retentie

Draait via systemd timer (dagelijks om 04:00)
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add core modules path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.logging import get_logger

# Centrale logger
logger = get_logger('log_cleanup')

# Configuration
RETENTION_DAYS = 14  # Keep logs for 14 days
MAX_LOG_SIZE_MB = 50  # Warn about logs larger than this


def get_file_age_days(filepath):
    """Get age of file in days"""
    try:
        mtime = Path(filepath).stat().st_mtime
        age = datetime.now() - datetime.fromtimestamp(mtime)
        return age.days
    except (OSError, IOError):
        return 0


def cleanup_numbered_logs():
    """Remove old numbered log rotations (.log.1, .log.2, etc.)"""
    deleted_count = 0
    deleted_size = 0

    for pattern in ['*.log.[0-9]', '*.log.[0-9][0-9]']:
        for log_file in LOG_DIR.glob(pattern):
            try:
                age = get_file_age_days(log_file)
                if age > RETENTION_DAYS:
                    size = log_file.stat().st_size
                    log_file.unlink()
                    deleted_count += 1
                    deleted_size += size
                    logger.info(f"Deleted old numbered log: {log_file.name} ({age} days old)")
            except Exception as e:
                logger.warning(f"Could not delete {log_file}: {e}")

    return deleted_count, deleted_size


def cleanup_dated_logs():
    """Remove old dated logs (*.log-YYYYMMDD)"""
    deleted_count = 0
    deleted_size = 0

    cutoff_date = datetime.now() - timedelta(days=RETENTION_DAYS)

    for log_file in LOG_DIR.glob('*.log-*'):
        try:
            # Extract date from filename
            name = log_file.name
            if '-2025' in name or '-2024' in name:
                # Try to parse date
                parts = name.split('-')
                for i, part in enumerate(parts):
                    if part.startswith('2025') or part.startswith('2024'):
                        try:
                            date_str = part[:8]  # YYYYMMDD
                            file_date = datetime.strptime(date_str, '%Y%m%d')
                            if file_date < cutoff_date:
                                size = log_file.stat().st_size
                                log_file.unlink()
                                deleted_count += 1
                                deleted_size += size
                                logger.info(f"Deleted old dated log: {log_file.name}")
                        except ValueError:
                            pass
                        break
        except Exception as e:
            logger.warning(f"Could not process {log_file}: {e}")

    return deleted_count, deleted_size


def cleanup_compressed_logs():
    """Remove old compressed logs (.gz)"""
    deleted_count = 0
    deleted_size = 0

    for log_file in LOG_DIR.glob('*.gz'):
        try:
            age = get_file_age_days(log_file)
            if age > RETENTION_DAYS:
                size = log_file.stat().st_size
                log_file.unlink()
                deleted_count += 1
                deleted_size += size
                logger.info(f"Deleted old compressed log: {log_file.name} ({age} days old)")
        except Exception as e:
            logger.warning(f"Could not delete {log_file}: {e}")

    return deleted_count, deleted_size


def check_large_logs():
    """Report logs larger than threshold"""
    large_logs = []
    for log_file in LOG_DIR.glob('*.log*'):
        try:
            size_mb = log_file.stat().st_size / (1024 * 1024)
            if size_mb > MAX_LOG_SIZE_MB:
                large_logs.append((log_file.name, size_mb))
        except (OSError, IOError):
            pass

    return large_logs


def main():
    """Main cleanup function"""
    logger.info("=" * 60)
    logger.info("EMSN Log Cleanup - Starting")
    logger.info("=" * 60)

    total_deleted = 0
    total_size = 0

    # Cleanup numbered logs
    count, size = cleanup_numbered_logs()
    total_deleted += count
    total_size += size

    # Cleanup dated logs
    count, size = cleanup_dated_logs()
    total_deleted += count
    total_size += size

    # Cleanup compressed logs
    count, size = cleanup_compressed_logs()
    total_deleted += count
    total_size += size

    # Report summary
    if total_deleted > 0:
        size_mb = total_size / (1024 * 1024)
        logger.info(f"Deleted {total_deleted} old log files ({size_mb:.1f} MB)")
    else:
        logger.info("No old log files to delete")

    # Check for large logs
    large_logs = check_large_logs()
    if large_logs:
        logger.warning("Large log files detected:")
        for name, size_mb in large_logs:
            logger.warning(f"  {name}: {size_mb:.1f} MB")

    # Report current log directory size
    try:
        total_log_size = sum(f.stat().st_size for f in LOG_DIR.glob('*') if f.is_file())
        logger.info(f"Total log directory size: {total_log_size / (1024 * 1024):.1f} MB")
    except Exception:
        pass

    logger.info("=" * 60)
    logger.info("EMSN Log Cleanup - Completed")
    logger.info("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
