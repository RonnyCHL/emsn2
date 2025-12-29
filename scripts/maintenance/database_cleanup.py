#!/usr/bin/env python3
"""
EMSN Database Cleanup Script
Verwijdert oude records uit tabellen om database groei te beperken

Tabellen en retentie:
- ulanzi_notification_log: 30 dagen
- system_health: 90 dagen
- performance_metrics: 60 dagen
- anomaly_check_log: 30 dagen

Draait via systemd timer (dagelijks om 03:00)
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Add core modules path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import psycopg2
    from core.config import get_postgres_config
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)

# Logging
LOG_DIR = Path("/mnt/usb/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "database_cleanup.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Cleanup configuratie: tabel -> (kolom, dagen retentie)
CLEANUP_CONFIG = {
    'ulanzi_notification_log': ('timestamp', 30),
    'system_health': ('measurement_timestamp', 90),
    'performance_metrics': ('measurement_timestamp', 60),
    'anomaly_check_log': ('check_timestamp', 30),
    'nas_metrics': ('timestamp', 60),
    'mqtt_hourly_stats': ('hour_timestamp', 90),
    'mqtt_bridge_events': ('timestamp', 60),
    'ulanzi_screenshots': ('timestamp', 30),
}


def get_connection():
    """Maak database connectie"""
    config = get_postgres_config()
    return psycopg2.connect(
        host=config['host'],
        port=config['port'],
        database=config['database'],
        user=config['user'],
        password=config['password']
    )


def cleanup_table(conn, table_name, timestamp_column, retention_days):
    """Verwijder oude records uit een tabel"""
    cutoff_date = datetime.now() - timedelta(days=retention_days)

    try:
        cursor = conn.cursor()

        # Eerst count hoeveel records verwijderd worden
        cursor.execute(f"""
            SELECT COUNT(*) FROM {table_name}
            WHERE {timestamp_column} < %s
        """, (cutoff_date,))
        count = cursor.fetchone()[0]

        if count > 0:
            # Verwijder oude records
            cursor.execute(f"""
                DELETE FROM {table_name}
                WHERE {timestamp_column} < %s
            """, (cutoff_date,))
            conn.commit()
            logger.info(f"Deleted {count} records from {table_name} (older than {retention_days} days)")
        else:
            logger.info(f"No old records to delete from {table_name}")

        return count

    except Exception as e:
        logger.error(f"Error cleaning {table_name}: {e}")
        conn.rollback()
        return 0


def vacuum_table(conn, table_name):
    """Vacuum een tabel om ruimte vrij te maken"""
    try:
        # Vacuum vereist autocommit
        old_isolation = conn.isolation_level
        conn.set_isolation_level(0)
        cursor = conn.cursor()
        cursor.execute(f"VACUUM ANALYZE {table_name}")
        conn.set_isolation_level(old_isolation)
        logger.info(f"Vacuumed {table_name}")
    except Exception as e:
        logger.warning(f"Could not vacuum {table_name}: {e}")


def get_table_sizes(conn):
    """Haal tabel groottes op voor logging"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT tablename,
               pg_size_pretty(pg_total_relation_size('public.' || tablename)) as size
        FROM pg_tables
        WHERE schemaname = 'public'
        ORDER BY pg_total_relation_size('public.' || tablename) DESC
        LIMIT 10
    """)
    return cursor.fetchall()


def main():
    logger.info("=== Database Cleanup Started ===")

    try:
        conn = get_connection()

        # Log huidige groottes
        logger.info("Current table sizes (top 10):")
        for table, size in get_table_sizes(conn):
            logger.info(f"  {table}: {size}")

        # Cleanup elke tabel
        total_deleted = 0
        for table, (column, days) in CLEANUP_CONFIG.items():
            deleted = cleanup_table(conn, table, column, days)
            total_deleted += deleted

            # Vacuum als er veel verwijderd is
            if deleted > 1000:
                vacuum_table(conn, table)

        logger.info(f"Total records deleted: {total_deleted}")

        # Log nieuwe groottes
        if total_deleted > 0:
            logger.info("New table sizes (top 10):")
            for table, size in get_table_sizes(conn):
                logger.info(f"  {table}: {size}")

        conn.close()
        logger.info("=== Database Cleanup Completed ===")

    except Exception as e:
        logger.error(f"Database cleanup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
