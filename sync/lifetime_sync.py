#!/usr/bin/env python3
"""
EMSN Lifetime Sync Script - Zolder Station
Synchronizes bird detections from local SQLite to central PostgreSQL database on NAS
"""

import sqlite3
import psycopg2
from psycopg2.extras import execute_batch
import json
import sys
from datetime import datetime
from pathlib import Path
import paho.mqtt.client as mqtt

# Configuration
SQLITE_DB = "/home/ronny/BirdNET-Pi/scripts/birds.db"
LOG_DIR = Path("/mnt/usb/logs")
STATION_NAME = "zolder"

# PostgreSQL Configuration
PG_CONFIG = {
    'host': '192.168.1.25',
    'port': 5433,
    'database': 'emsn',
    'user': 'birdpi_zolder',
    'password': 'REDACTED_DB_PASS'
}

# MQTT Configuration
MQTT_CONFIG = {
    'broker': '192.168.1.178',
    'port': 1883,
    'username': 'ecomonitor',
    'password': 'REDACTED_DB_PASS',
    'topic_status': 'emsn2/zolder/sync/status',
    'topic_stats': 'emsn2/zolder/sync/stats'
}

class SyncLogger:
    """Simple logger for sync operations"""

    def __init__(self, log_dir):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / f"lifetime_sync_{datetime.now().strftime('%Y%m%d')}.log"

    def log(self, level, message):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] [{level}] {message}"
        print(log_entry)
        with open(self.log_file, 'a') as f:
            f.write(log_entry + '\n')

    def info(self, message):
        self.log('INFO', message)

    def error(self, message):
        self.log('ERROR', message)

    def warning(self, message):
        self.log('WARNING', message)

    def success(self, message):
        self.log('SUCCESS', message)

class MQTTPublisher:
    """MQTT publisher for sync status updates"""

    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.client = None
        self.connected = False

    def connect(self):
        """Connect to MQTT broker"""
        try:
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
            self.client.username_pw_set(self.config['username'], self.config['password'])
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.connect(self.config['broker'], self.config['port'], 60)
            self.client.loop_start()
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect to MQTT broker: {e}")
            return False

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            self.connected = True
            self.logger.info("Connected to MQTT broker")
        else:
            self.logger.error(f"MQTT connection failed with code {reason_code}")

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
        self.connected = False
        self.logger.warning("Disconnected from MQTT broker")

    def publish_status(self, status, message, details=None):
        """Publish sync status update"""
        if not self.client:
            return

        payload = {
            'station': STATION_NAME,
            'timestamp': datetime.now().isoformat(),
            'status': status,
            'message': message
        }

        if details:
            payload.update(details)

        try:
            self.client.publish(
                self.config['topic_status'],
                json.dumps(payload),
                qos=1,
                retain=False
            )
        except Exception as e:
            self.logger.error(f"Failed to publish MQTT status: {e}")

    def publish_stats(self, stats):
        """Publish sync statistics"""
        if not self.client:
            return

        payload = {
            'station': STATION_NAME,
            'timestamp': datetime.now().isoformat(),
            **stats
        }

        try:
            self.client.publish(
                self.config['topic_stats'],
                json.dumps(payload),
                qos=1,
                retain=True
            )
        except Exception as e:
            self.logger.error(f"Failed to publish MQTT stats: {e}")

    def disconnect(self):
        """Disconnect from MQTT broker"""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()

class BirdDetectionSync:
    """Synchronizes bird detections from SQLite to PostgreSQL"""

    def __init__(self, logger, mqtt_publisher):
        self.logger = logger
        self.mqtt = mqtt_publisher
        self.sqlite_conn = None
        self.pg_conn = None

    def connect_databases(self):
        """Connect to both SQLite and PostgreSQL databases"""
        try:
            # Connect to SQLite
            self.logger.info(f"Connecting to SQLite database: {SQLITE_DB}")
            self.sqlite_conn = sqlite3.connect(SQLITE_DB)
            self.sqlite_conn.row_factory = sqlite3.Row

            # Connect to PostgreSQL
            self.logger.info(f"Connecting to PostgreSQL at {PG_CONFIG['host']}:{PG_CONFIG['port']}")
            self.pg_conn = psycopg2.connect(**PG_CONFIG)

            self.logger.success("Database connections established")
            return True

        except sqlite3.Error as e:
            self.logger.error(f"SQLite connection error: {e}")
            return False
        except psycopg2.Error as e:
            self.logger.error(f"PostgreSQL connection error: {e}")
            return False

    def get_sqlite_detections(self):
        """Fetch all detections from SQLite database"""
        try:
            cursor = self.sqlite_conn.cursor()

            # Query to get all bird detections
            query = """
                SELECT
                    Date,
                    Time,
                    Sci_Name,
                    Com_Name,
                    Confidence,
                    Lat,
                    Lon,
                    Cutoff,
                    Week,
                    Sens,
                    Overlap,
                    File_Name
                FROM detections
                ORDER BY Date, Time
            """

            cursor.execute(query)
            detections = cursor.fetchall()

            self.logger.info(f"Found {len(detections)} detections in SQLite database")
            return detections

        except sqlite3.Error as e:
            self.logger.error(f"Error reading from SQLite: {e}")
            return []

    def get_existing_detections(self):
        """Get set of existing detections in PostgreSQL for deduplication"""
        try:
            cursor = self.pg_conn.cursor()

            query = """
                SELECT detection_timestamp, species
                FROM bird_detections
                WHERE station = %s
            """

            cursor.execute(query, (STATION_NAME,))
            existing = set()

            for row in cursor.fetchall():
                # Create unique key from timestamp and species
                key = (row[0], row[1])
                existing.add(key)

            self.logger.info(f"Found {len(existing)} existing detections in PostgreSQL")
            return existing

        except psycopg2.Error as e:
            self.logger.error(f"Error reading from PostgreSQL: {e}")
            return set()

    def sync_detections(self):
        """Main sync logic: transfer new detections from SQLite to PostgreSQL"""

        # Get all detections from SQLite
        sqlite_detections = self.get_sqlite_detections()
        if not sqlite_detections:
            self.logger.warning("No detections found in SQLite database")
            return 0

        # Get existing detections from PostgreSQL
        existing_detections = self.get_existing_detections()

        # Prepare new detections for insertion
        new_detections = []
        skipped = 0

        for row in sqlite_detections:
            # Parse datetime
            date_str = row['Date']
            time_str = row['Time']

            try:
                detection_timestamp = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
            except ValueError:
                self.logger.warning(f"Invalid datetime format: {date_str} {time_str}")
                skipped += 1
                continue

            species = row['Sci_Name']

            # Check if this detection already exists
            key = (detection_timestamp, species)
            if key in existing_detections:
                skipped += 1
                continue

            # Parse confidence
            try:
                confidence = float(row['Confidence'])
            except (ValueError, TypeError):
                self.logger.warning(f"Invalid confidence value: {row['Confidence']}")
                confidence = 0.0

            # Prepare record for PostgreSQL
            detection = {
                'station': STATION_NAME,
                'detection_timestamp': detection_timestamp,
                'date': detection_timestamp.date(),
                'time': detection_timestamp.time(),
                'species': species,
                'common_name': row['Com_Name'],
                'confidence': confidence,
                'latitude': row['Lat'] if row['Lat'] else None,
                'longitude': row['Lon'] if row['Lon'] else None,
                'cutoff': float(row['Cutoff']) if row['Cutoff'] else None,
                'week': int(row['Week']) if row['Week'] else None,
                'sensitivity': float(row['Sens']) if row['Sens'] else None,
                'overlap': float(row['Overlap']) if row['Overlap'] else None,
                'file_name': row['File_Name'],
                'detected_by_zolder': True,
                'detected_by_berging': False,
                'dual_detection': False,
                'time_diff_seconds': None,
                'rarity_score': 0,
                'rarity_tier': None
            }

            new_detections.append(detection)

        # Insert new detections
        if new_detections:
            self.logger.info(f"Inserting {len(new_detections)} new detections (skipped {skipped} existing)")
            inserted = self.insert_detections(new_detections)
            return inserted
        else:
            self.logger.info(f"No new detections to sync (all {len(sqlite_detections)} already exist)")
            return 0

    def insert_detections(self, detections):
        """Batch insert detections into PostgreSQL"""
        try:
            cursor = self.pg_conn.cursor()

            insert_query = """
                INSERT INTO bird_detections (
                    station, detection_timestamp, date, time, species, common_name,
                    confidence, latitude, longitude, cutoff, week, sensitivity, overlap,
                    file_name, detected_by_zolder, detected_by_berging, dual_detection,
                    time_diff_seconds, rarity_score, rarity_tier
                ) VALUES (
                    %(station)s, %(detection_timestamp)s, %(date)s, %(time)s, %(species)s, %(common_name)s,
                    %(confidence)s, %(latitude)s, %(longitude)s, %(cutoff)s, %(week)s, %(sensitivity)s, %(overlap)s,
                    %(file_name)s, %(detected_by_zolder)s, %(detected_by_berging)s, %(dual_detection)s,
                    %(time_diff_seconds)s, %(rarity_score)s, %(rarity_tier)s
                )
            """

            # Use execute_batch for better performance
            execute_batch(cursor, insert_query, detections, page_size=100)
            self.pg_conn.commit()

            self.logger.success(f"Successfully inserted {len(detections)} detections")
            return len(detections)

        except psycopg2.Error as e:
            self.pg_conn.rollback()
            self.logger.error(f"Error inserting detections: {e}")
            return 0

    def get_statistics(self):
        """Get sync statistics from PostgreSQL"""
        try:
            cursor = self.pg_conn.cursor()

            stats_query = """
                SELECT
                    COUNT(*) as total_detections,
                    COUNT(DISTINCT species) as unique_species,
                    MIN(detection_timestamp) as first_detection,
                    MAX(detection_timestamp) as last_detection,
                    AVG(confidence) as avg_confidence
                FROM bird_detections
                WHERE station = %s
            """

            cursor.execute(stats_query, (STATION_NAME,))
            row = cursor.fetchone()

            if row:
                return {
                    'total_detections': row[0],
                    'unique_species': row[1],
                    'first_detection': row[2].isoformat() if row[2] else None,
                    'last_detection': row[3].isoformat() if row[3] else None,
                    'avg_confidence': float(row[4]) if row[4] else 0.0
                }

            return {}

        except psycopg2.Error as e:
            self.logger.error(f"Error getting statistics: {e}")
            return {}

    def close_connections(self):
        """Close database connections"""
        if self.sqlite_conn:
            self.sqlite_conn.close()
            self.logger.info("SQLite connection closed")

        if self.pg_conn:
            self.pg_conn.close()
            self.logger.info("PostgreSQL connection closed")

def main():
    """Main execution function"""

    # Initialize logger
    logger = SyncLogger(LOG_DIR)
    logger.info("=" * 80)
    logger.info("EMSN Lifetime Sync - Zolder Station")
    logger.info("=" * 80)

    # Initialize MQTT publisher
    mqtt_pub = MQTTPublisher(MQTT_CONFIG, logger)
    mqtt_pub.connect()

    # Publish start status
    mqtt_pub.publish_status('running', 'Lifetime sync started')

    try:
        # Initialize sync handler
        sync = BirdDetectionSync(logger, mqtt_pub)

        # Connect to databases
        if not sync.connect_databases():
            logger.error("Failed to connect to databases")
            mqtt_pub.publish_status('error', 'Database connection failed')
            sys.exit(1)

        # Perform sync
        logger.info("Starting synchronization...")
        synced_count = sync.sync_detections()

        # Get statistics
        stats = sync.get_statistics()

        # Log results
        logger.info("-" * 80)
        logger.success(f"Sync completed: {synced_count} new detections transferred")
        logger.info(f"Total detections in database: {stats.get('total_detections', 0)}")
        logger.info(f"Unique species: {stats.get('unique_species', 0)}")
        logger.info(f"Average confidence: {stats.get('avg_confidence', 0):.4f}")
        logger.info("-" * 80)

        # Publish completion status
        mqtt_pub.publish_status(
            'completed',
            f'Sync completed successfully',
            {
                'synced_count': synced_count,
                'total_detections': stats.get('total_detections', 0)
            }
        )

        # Publish statistics
        mqtt_pub.publish_stats(stats)

        # Close connections
        sync.close_connections()

        logger.success("Lifetime sync completed successfully")

    except Exception as e:
        logger.error(f"Unexpected error during sync: {e}")
        mqtt_pub.publish_status('error', f'Sync failed: {str(e)}')
        sys.exit(1)

    finally:
        mqtt_pub.disconnect()

if __name__ == "__main__":
    main()
