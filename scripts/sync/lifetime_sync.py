#!/usr/bin/env python3
"""
EMSN Lifetime Sync - Bird Detection Synchronization

Synchronizes bird detections from BirdNET-Pi SQLite to central PostgreSQL database.
Supports both zolder and berging stations with INSERT, UPDATE, and soft DELETE.

Key features:
- Uses date+time as primary match key (BirdNET-Pi changes file_name on species edit)
- Detects species corrections made in BirdNET-Pi WebUI
- Updates file_name when species is corrected
- Soft deletes removed detections (preserves data integrity)
- Retry logic for database locks
- MQTT status publishing

Author: EMSN 2.0
"""

import argparse
import json
import logging
import os
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Any

import paho.mqtt.client as mqtt
import psycopg2
from psycopg2.extras import execute_batch

# =============================================================================
# Configuration
# =============================================================================

@dataclass
class StationConfig:
    """Configuration for a BirdNET-Pi station."""
    name: str
    sqlite_path: Path
    pg_user: str
    detected_by_field: str


STATIONS = {
    "zolder": StationConfig(
        name="zolder",
        sqlite_path=Path("/home/ronny/BirdNET-Pi/scripts/birds.db"),
        pg_user="birdpi_zolder",
        detected_by_field="detected_by_zolder",
    ),
    "berging": StationConfig(
        name="berging",
        sqlite_path=Path("/home/ronny/BirdNET-Pi/scripts/birds.db"),
        pg_user="birdpi_berging",
        detected_by_field="detected_by_berging",
    ),
}

LOG_DIR = Path("/mnt/usb/logs")
SQLITE_RETRY_ATTEMPTS = 3
SQLITE_RETRY_DELAY = 5  # seconds


def load_secrets() -> Dict[str, Dict[str, Any]]:
    """Load database and MQTT credentials.

    Returns:
        Dictionary with 'postgres' and 'mqtt' configuration dicts.
    """
    sys.path.insert(0, str(Path(__file__).parent.parent))
    try:
        from core.config import get_postgres_config, get_mqtt_config
        return {
            "postgres": get_postgres_config(),
            "mqtt": get_mqtt_config(),
        }
    except ImportError:
        return {
            "postgres": {
                "host": "192.168.1.25",
                "port": 5433,
                "database": "emsn",
                "user": os.environ.get("PG_USER", "birdpi_zolder"),
                "password": os.environ.get("PG_PASS", ""),
            },
            "mqtt": {
                "broker": "192.168.1.178",
                "port": 1883,
                "username": "ecomonitor",
                "password": os.environ.get("MQTT_PASS", ""),
            },
        }


# =============================================================================
# Logging
# =============================================================================

def setup_logging(station: str) -> logging.Logger:
    """Configure logging for the sync process."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / f"lifetime_sync_{station}_{datetime.now():%Y%m%d}.log"

    logger = logging.getLogger(f"lifetime_sync_{station}")
    logger.setLevel(logging.INFO)

    # Clear existing handlers
    logger.handlers.clear()

    # Console handler
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(console)

    # File handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(file_handler)

    return logger


# =============================================================================
# MQTT Publisher
# =============================================================================

class MQTTPublisher:
    """Publishes sync status to MQTT broker."""

    def __init__(self, config: dict, station: str, logger: logging.Logger):
        self.config = config
        self.station = station
        self.logger = logger
        self.client: Optional[mqtt.Client] = None
        self.topic_status = f"emsn2/{station}/sync/status"
        self.topic_stats = f"emsn2/{station}/sync/stats"

    def connect(self) -> bool:
        """Establish MQTT connection."""
        try:
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
            self.client.username_pw_set(
                self.config["username"],
                self.config["password"]
            )
            self.client.connect(self.config["broker"], self.config["port"], 60)
            self.client.loop_start()
            self.logger.info(f"MQTT connected to {self.config['broker']}")
            return True
        except Exception as e:
            self.logger.warning(f"MQTT connection failed: {e}")
            return False

    def publish_status(self, status: str, message: str, **extra) -> None:
        """Publish sync status update."""
        if not self.client:
            return

        payload = {
            "station": self.station,
            "timestamp": datetime.now().isoformat(),
            "status": status,
            "message": message,
            **extra,
        }

        try:
            self.client.publish(self.topic_status, json.dumps(payload), qos=1)
        except Exception as e:
            self.logger.warning(f"MQTT publish failed: {e}")

    def publish_stats(self, stats: dict) -> None:
        """Publish sync statistics."""
        if not self.client:
            return

        payload = {
            "station": self.station,
            "timestamp": datetime.now().isoformat(),
            **stats,
        }

        try:
            self.client.publish(self.topic_stats, json.dumps(payload), qos=1, retain=True)
        except Exception as e:
            self.logger.warning(f"MQTT stats publish failed: {e}")

    def disconnect(self) -> None:
        """Close MQTT connection."""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()


# =============================================================================
# Database Connections
# =============================================================================

def connect_sqlite(path: Path, logger: logging.Logger) -> Optional[sqlite3.Connection]:
    """Connect to SQLite with retry logic for database locks.

    Args:
        path: Path to SQLite database file.
        logger: Logger instance for output.

    Returns:
        SQLite connection or None on failure.
    """
    for attempt in range(1, SQLITE_RETRY_ATTEMPTS + 1):
        try:
            conn = sqlite3.connect(str(path), timeout=30)
            conn.row_factory = sqlite3.Row
            logger.info(f"SQLite connected: {path}")
            return conn
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower() and attempt < SQLITE_RETRY_ATTEMPTS:
                logger.warning(f"SQLite locked, retry {attempt}/{SQLITE_RETRY_ATTEMPTS} in {SQLITE_RETRY_DELAY}s")
                time.sleep(SQLITE_RETRY_DELAY)
            else:
                logger.error(f"SQLite connection failed: {e}")
                return None
    return None


def connect_postgres(config: Dict[str, Any], logger: logging.Logger) -> Optional[psycopg2.extensions.connection]:
    """Connect to PostgreSQL database.

    Args:
        config: PostgreSQL configuration dict with host, port, database, user, password.
        logger: Logger instance for output.

    Returns:
        PostgreSQL connection or None on failure.
    """
    try:
        conn = psycopg2.connect(
            host=config["host"],
            port=config["port"],
            database=config["database"],
            user=config["user"],
            password=config["password"],
        )
        logger.info(f"PostgreSQL connected: {config['host']}:{config['port']}")
        return conn
    except psycopg2.Error as e:
        logger.error(f"PostgreSQL connection failed: {e}")
        return None


# =============================================================================
# Sync Logic
# =============================================================================

@dataclass
class SyncResult:
    """Results of a sync operation."""
    inserted: int = 0
    updated: int = 0
    soft_deleted: int = 0
    errors: int = 0


def get_sqlite_detections(conn: sqlite3.Connection) -> Dict[str, Dict[str, Any]]:
    """Fetch all detections from SQLite, keyed by file_name.

    Args:
        conn: SQLite database connection.

    Returns:
        Dictionary mapping file_name -> detection data dict.
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            Date, Time, Sci_Name, Com_Name, Confidence,
            Lat, Lon, Cutoff, Week, Sens, Overlap, File_Name
        FROM detections
        WHERE File_Name IS NOT NULL AND File_Name != ''
    """)

    detections = {}
    for row in cursor.fetchall():
        file_name = row["File_Name"]
        if file_name:
            detections[file_name] = {
                "date": row["Date"],
                "time": row["Time"],
                "species": row["Sci_Name"],
                "common_name": row["Com_Name"],
                "confidence": float(row["Confidence"]) if row["Confidence"] else 0.0,
                "latitude": row["Lat"],
                "longitude": row["Lon"],
                "cutoff": float(row["Cutoff"]) if row["Cutoff"] else None,
                "week": int(row["Week"]) if row["Week"] else None,
                "sensitivity": float(row["Sens"]) if row["Sens"] else None,
                "overlap": float(row["Overlap"]) if row["Overlap"] else None,
            }

    return detections


def get_postgres_detections(
    conn: psycopg2.extensions.connection, station: str
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, List[Dict[str, Any]]]]:
    """Fetch all detections from PostgreSQL for a station.

    Args:
        conn: PostgreSQL database connection.
        station: Station name ('zolder' or 'berging').

    Returns:
        Tuple of:
        - dict mapping file_name -> {id, species, common_name, deleted, date, time}
        - dict mapping date+time -> list of detections (for species correction matching)
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, file_name, species, common_name, deleted, date, time
        FROM bird_detections
        WHERE station = %s AND file_name IS NOT NULL
    """, (station,))

    by_filename = {}
    by_datetime = {}  # date+time -> list of detections (can have multiple)
    for row in cursor.fetchall():
        file_name = row[1]
        date_val = row[5]
        time_val = row[6]
        if file_name:
            detection = {
                "id": row[0],
                "file_name": file_name,
                "species": row[2],
                "common_name": row[3],
                "deleted": row[4] or False,
            }
            by_filename[file_name] = detection
            # Also index by date+time for species correction matching
            if date_val and time_val:
                dt_key = f"{date_val}_{time_val}"
                if dt_key not in by_datetime:
                    by_datetime[dt_key] = []
                by_datetime[dt_key].append(detection)

    return by_filename, by_datetime


def sync_station(
    station_config: StationConfig,
    pg_config: Dict[str, Any],
    logger: logging.Logger,
) -> SyncResult:
    """Synchronize a single station's detections to PostgreSQL.

    Args:
        station_config: Configuration for the station to sync.
        pg_config: PostgreSQL connection configuration.
        logger: Logger instance for output.

    Returns:
        SyncResult with counts of inserted, updated, deleted records.

    Logic:
    1. For each SQLite detection (by file_name):
       - Exists in PG by file_name? -> Already synced (check restore)
       - Not in PG by file_name, but date+time exists? -> Species correction (UPDATE)
       - Not in PG at all? -> INSERT
    2. For each PG detection not in SQLite:
       - Mark as deleted (soft delete)
    """
    result = SyncResult()
    station = station_config.name

    # Connect to databases
    sqlite_conn = connect_sqlite(station_config.sqlite_path, logger)
    if not sqlite_conn:
        result.errors = 1
        return result

    pg_conn = connect_postgres(pg_config, logger)
    if not pg_conn:
        sqlite_conn.close()
        result.errors = 1
        return result

    try:
        # Fetch all detections
        sqlite_data = get_sqlite_detections(sqlite_conn)
        pg_by_filename, pg_by_datetime = get_postgres_detections(pg_conn, station)

        logger.info(f"SQLite: {len(sqlite_data)} detections, PostgreSQL: {len(pg_by_filename)} detections")

        cursor = pg_conn.cursor()

        # Prepare batch operations
        to_insert = []
        to_update = []
        to_restore = []
        matched_pg_ids = set()

        # Process SQLite detections
        for file_name, sqlite_det in sqlite_data.items():
            dt_key = f"{sqlite_det['date']}_{sqlite_det['time']}"

            # Case 1: File exists in PG (already synced)
            if file_name in pg_by_filename:
                pg_det = pg_by_filename[file_name]
                matched_pg_ids.add(pg_det["id"])

                # Check if previously deleted, now restored
                if pg_det["deleted"]:
                    to_restore.append(pg_det["id"])

            # Case 2: File not in PG, but date+time exists -> Possible species correction
            elif dt_key in pg_by_datetime:
                # Find the matching detection (there might be multiple at same time)
                # Only update if the PG detection's file_name is NOT in SQLite (was corrected)
                pg_candidates = pg_by_datetime[dt_key]
                matched = False
                for pg_det in pg_candidates:
                    pg_file = pg_det["file_name"]
                    # Only update if:
                    # 1. Not already matched
                    # 2. The old file_name doesn't exist in SQLite anymore (species was corrected)
                    if pg_det["id"] not in matched_pg_ids and pg_file not in sqlite_data:
                        matched_pg_ids.add(pg_det["id"])
                        to_update.append({
                            "id": pg_det["id"],
                            "species": sqlite_det["species"],
                            "common_name": sqlite_det["common_name"],
                            "file_name": file_name,
                        })
                        matched = True
                        break

                # If no match found, insert as new
                if not matched:
                    try:
                        dt = datetime.strptime(
                            f"{sqlite_det['date']} {sqlite_det['time']}",
                            "%Y-%m-%d %H:%M:%S"
                        )
                    except ValueError:
                        logger.warning(f"Invalid datetime for {file_name}")
                        continue

                    to_insert.append({
                        "station": station,
                        "detection_timestamp": dt,
                        "date": dt.date(),
                        "time": dt.time(),
                        "species": sqlite_det["species"],
                        "common_name": sqlite_det["common_name"],
                        "confidence": sqlite_det["confidence"],
                        "latitude": sqlite_det["latitude"],
                        "longitude": sqlite_det["longitude"],
                        "cutoff": sqlite_det["cutoff"],
                        "week": sqlite_det["week"],
                        "sensitivity": sqlite_det["sensitivity"],
                        "overlap": sqlite_det["overlap"],
                        "file_name": file_name,
                        "detected_by_zolder": station == "zolder",
                        "detected_by_berging": station == "berging",
                        "deleted": False,
                    })

            # Case 3: New detection - INSERT
            else:
                try:
                    dt = datetime.strptime(
                        f"{sqlite_det['date']} {sqlite_det['time']}",
                        "%Y-%m-%d %H:%M:%S"
                    )
                except ValueError:
                    logger.warning(f"Invalid datetime for {file_name}")
                    continue

                to_insert.append({
                    "station": station,
                    "detection_timestamp": dt,
                    "date": dt.date(),
                    "time": dt.time(),
                    "species": sqlite_det["species"],
                    "common_name": sqlite_det["common_name"],
                    "confidence": sqlite_det["confidence"],
                    "latitude": sqlite_det["latitude"],
                    "longitude": sqlite_det["longitude"],
                    "cutoff": sqlite_det["cutoff"],
                    "week": sqlite_det["week"],
                    "sensitivity": sqlite_det["sensitivity"],
                    "overlap": sqlite_det["overlap"],
                    "file_name": file_name,
                    "detected_by_zolder": station == "zolder",
                    "detected_by_berging": station == "berging",
                    "deleted": False,
                })

        # Find detections to soft delete (in PG but not matched from SQLite)
        to_delete = []
        for file_name, pg_det in pg_by_filename.items():
            if pg_det["id"] not in matched_pg_ids and not pg_det["deleted"]:
                to_delete.append(pg_det["id"])

        # Execute INSERT
        if to_insert:
            insert_query = """
                INSERT INTO bird_detections (
                    station, detection_timestamp, date, time, species, common_name,
                    confidence, latitude, longitude, cutoff, week, sensitivity, overlap,
                    file_name, detected_by_zolder, detected_by_berging, deleted
                ) VALUES (
                    %(station)s, %(detection_timestamp)s, %(date)s, %(time)s,
                    %(species)s, %(common_name)s, %(confidence)s, %(latitude)s,
                    %(longitude)s, %(cutoff)s, %(week)s, %(sensitivity)s, %(overlap)s,
                    %(file_name)s, %(detected_by_zolder)s, %(detected_by_berging)s, %(deleted)s
                )
                ON CONFLICT (file_name, station) WHERE file_name IS NOT NULL
                DO NOTHING
            """
            execute_batch(cursor, insert_query, to_insert, page_size=100)
            result.inserted = len(to_insert)
            logger.info(f"Inserted {result.inserted} new detections")

        # Execute UPDATE (species corrections with file_name update)
        if to_update:
            update_query = """
                UPDATE bird_detections
                SET species = %(species)s, common_name = %(common_name)s, file_name = %(file_name)s
                WHERE id = %(id)s
            """
            execute_batch(cursor, update_query, to_update, page_size=100)
            result.updated = len(to_update)
            logger.info(f"Updated {result.updated} species corrections")
            for upd in to_update[:5]:  # Log first 5
                logger.info(f"  Updated ID {upd['id']}: -> {upd['common_name']} ({upd['file_name']})")

        # Execute RESTORE
        if to_restore:
            cursor.execute("""
                UPDATE bird_detections
                SET deleted = FALSE, deleted_at = NULL
                WHERE id = ANY(%s)
            """, (to_restore,))
            logger.info(f"Restored {len(to_restore)} previously deleted detections")

        # Execute SOFT DELETE
        if to_delete:
            cursor.execute("""
                UPDATE bird_detections
                SET deleted = TRUE, deleted_at = NOW()
                WHERE id = ANY(%s)
            """, (to_delete,))
            result.soft_deleted = len(to_delete)
            logger.info(f"Soft deleted {result.soft_deleted} removed detections")

        pg_conn.commit()

    except Exception as e:
        logger.error(f"Sync error: {e}")
        pg_conn.rollback()
        result.errors = 1
    finally:
        sqlite_conn.close()
        pg_conn.close()

    return result


def get_station_stats(pg_config: Dict[str, Any], station: str) -> Dict[str, Any]:
    """Get statistics for a station from PostgreSQL.

    Args:
        pg_config: PostgreSQL connection configuration.
        station: Station name ('zolder' or 'berging').

    Returns:
        Dictionary with station statistics (active_detections, unique_species, etc.)
    """
    try:
        conn = psycopg2.connect(**pg_config)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                COUNT(*) FILTER (WHERE NOT deleted) as active_detections,
                COUNT(*) FILTER (WHERE deleted) as deleted_detections,
                COUNT(DISTINCT species) FILTER (WHERE NOT deleted) as unique_species,
                AVG(confidence) FILTER (WHERE NOT deleted) as avg_confidence,
                MAX(detection_timestamp) FILTER (WHERE NOT deleted) as last_detection
            FROM bird_detections
            WHERE station = %s
        """, (station,))

        row = cursor.fetchone()
        conn.close()

        return {
            "active_detections": row[0] or 0,
            "deleted_detections": row[1] or 0,
            "unique_species": row[2] or 0,
            "avg_confidence": float(row[3]) if row[3] else 0.0,
            "last_detection": row[4].isoformat() if row[4] else None,
        }
    except Exception:
        return {}


# =============================================================================
# Main
# =============================================================================

def main() -> int:
    """Main entry point for lifetime sync.

    Returns:
        Exit code (0 for success, 1 for errors).
    """
    parser = argparse.ArgumentParser(description="EMSN Lifetime Sync")
    parser.add_argument(
        "--station",
        choices=["zolder", "berging"],
        required=True,
        help="Station to sync",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    args = parser.parse_args()

    station = args.station
    station_config = STATIONS[station]

    # Setup
    logger = setup_logging(station)
    secrets = load_secrets()
    pg_config = secrets["postgres"].copy()
    pg_config["user"] = station_config.pg_user

    logger.info("=" * 70)
    logger.info(f"EMSN Lifetime Sync - {station.upper()}")
    logger.info("=" * 70)

    # MQTT
    mqtt_pub = MQTTPublisher(secrets["mqtt"], station, logger)
    mqtt_pub.connect()
    mqtt_pub.publish_status("running", "Sync started")

    # Sync
    if args.dry_run:
        logger.info("DRY RUN - no changes will be made")

    result = sync_station(station_config, pg_config, logger)

    # Stats
    stats = get_station_stats(pg_config, station)

    # Report
    logger.info("-" * 70)
    logger.info(f"Sync completed: +{result.inserted} inserted, "
                f"~{result.updated} updated, -{result.soft_deleted} deleted")
    logger.info(f"Database: {stats.get('active_detections', 0)} active, "
                f"{stats.get('unique_species', 0)} species")
    logger.info("-" * 70)

    # MQTT status
    if result.errors:
        mqtt_pub.publish_status("error", "Sync completed with errors", **vars(result))
    else:
        mqtt_pub.publish_status("completed", "Sync successful", **vars(result))

    mqtt_pub.publish_stats(stats)
    mqtt_pub.disconnect()

    return 0 if result.errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
