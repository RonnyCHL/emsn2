#!/usr/bin/env python3
"""
EMSN 2.0 - Dual Detection Sync
Detecteert en markeert vogels die op beide stations (zolder + berging) zijn waargenomen
binnen een configureerbaar tijdsvenster.

Dit script draait alleen op het centrale station (zolder) omdat het beide datasets vergelijkt.
"""

import psycopg2
from psycopg2.extras import execute_batch
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
import paho.mqtt.client as mqtt

# Import Bayesian verification model
from bayesian_verification import BayesianVerificationModel, calculate_bayesian_verification_score

# Configuration
STATION_NAME = "zolder"  # Dit script draait alleen op zolder (centraal)
LOG_DIR = Path("/mnt/usb/logs")

# Dual detection parameters
TIME_WINDOW_SECONDS = 30  # Maximale tijd tussen detecties om als dual te markeren
MIN_CONFIDENCE = 0.7     # Minimale confidence voor dual detection

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
    'topic_status': 'emsn2/dual/sync/status',
    'topic_stats': 'emsn2/dual/sync/stats',
    'topic_alert': 'emsn2/dual/detection/new'
}


class SyncLogger:
    """Simple logger for sync operations"""

    def __init__(self, log_dir):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / f"dual_detection_{datetime.now().strftime('%Y%m%d')}.log"

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
    """MQTT publisher for dual detection updates"""

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
        """Publish dual detection statistics"""
        if not self.client:
            return

        payload = {
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

    def publish_new_dual(self, detection):
        """Publish alert for new dual detection"""
        if not self.client:
            return

        try:
            self.client.publish(
                self.config['topic_alert'],
                json.dumps(detection),
                qos=1,
                retain=False
            )
        except Exception as e:
            self.logger.error(f"Failed to publish dual detection alert: {e}")

    def disconnect(self):
        """Disconnect from MQTT broker"""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()


class DualDetectionSync:
    """Detects and marks dual detections between zolder and berging stations"""

    def __init__(self, logger, mqtt_publisher):
        self.logger = logger
        self.mqtt = mqtt_publisher
        self.pg_conn = None
        self.bayesian_model = None

    def connect_database(self):
        """Connect to PostgreSQL database"""
        try:
            self.logger.info(f"Connecting to PostgreSQL at {PG_CONFIG['host']}:{PG_CONFIG['port']}")
            self.pg_conn = psycopg2.connect(**PG_CONFIG)
            self.logger.success("Database connection established")

            # Initialize Bayesian model with database connection
            self.logger.info("Initializing Bayesian verification model...")
            self.bayesian_model = BayesianVerificationModel(self.pg_conn, self.logger)
            self.bayesian_model.load_species_statistics()
            self.logger.success(f"Bayesian model initialized with {len(self.bayesian_model.species_stats)} species")

            return True
        except psycopg2.Error as e:
            self.logger.error(f"PostgreSQL connection error: {e}")
            return False

    def find_new_dual_detections(self):
        """Find potential dual detections that haven't been processed yet"""
        try:
            cursor = self.pg_conn.cursor()

            # Find matching detections between zolder and berging
            # within the time window, where dual_detection is still false
            query = """
                WITH potential_duals AS (
                    SELECT
                        z.id as zolder_id,
                        z.species,
                        z.common_name,
                        z.detection_timestamp as zolder_time,
                        z.confidence as zolder_confidence,
                        z.file_name as zolder_file,
                        b.id as berging_id,
                        b.detection_timestamp as berging_time,
                        b.confidence as berging_confidence,
                        b.file_name as berging_file,
                        ABS(EXTRACT(EPOCH FROM (b.detection_timestamp - z.detection_timestamp))) as time_diff
                    FROM bird_detections z
                    JOIN bird_detections b ON z.species = b.species
                        AND z.station = 'zolder'
                        AND b.station = 'berging'
                        AND ABS(EXTRACT(EPOCH FROM (b.detection_timestamp - z.detection_timestamp))) <= %s
                    WHERE z.dual_detection = false
                      AND b.dual_detection = false
                      AND z.confidence >= %s
                      AND b.confidence >= %s
                )
                SELECT DISTINCT ON (zolder_id, berging_id)
                    zolder_id,
                    species,
                    common_name,
                    zolder_time,
                    zolder_confidence,
                    zolder_file,
                    berging_id,
                    berging_time,
                    berging_confidence,
                    berging_file,
                    time_diff
                FROM potential_duals
                ORDER BY zolder_id, berging_id, time_diff ASC
            """

            cursor.execute(query, (TIME_WINDOW_SECONDS, MIN_CONFIDENCE, MIN_CONFIDENCE))
            results = cursor.fetchall()

            self.logger.info(f"Found {len(results)} potential new dual detections")
            return results

        except psycopg2.Error as e:
            self.logger.error(f"Error finding dual detections: {e}")
            return []

    def process_dual_detections(self, detections):
        """Process and store dual detections"""
        if not detections:
            return 0, 0

        # Track which detection IDs we've already processed to avoid duplicates
        processed_zolder = set()
        processed_berging = set()

        dual_records = []
        update_ids_zolder = []
        update_ids_berging = []

        for row in detections:
            (zolder_id, species, common_name, zolder_time, zolder_conf,
             zolder_file, berging_id, berging_time, berging_conf,
             berging_file, time_diff) = row

            # Skip if we've already processed either detection
            if zolder_id in processed_zolder or berging_id in processed_berging:
                continue

            processed_zolder.add(zolder_id)
            processed_berging.add(berging_id)

            # Calculate metrics
            conf_diff = abs(float(zolder_conf) - float(berging_conf))
            avg_conf = (float(zolder_conf) + float(berging_conf)) / 2

            # Calculate Bayesian verification score
            bayesian_result = self.bayesian_model.calculate_dual_verification_score(
                species=species,
                zolder_confidence=float(zolder_conf),
                berging_confidence=float(berging_conf),
                time_diff_seconds=float(time_diff)
            )
            verification_score = bayesian_result['verification_score']

            # Use the earlier timestamp as detection_time
            detection_time = min(zolder_time, berging_time)

            dual_record = {
                'species': species,
                'detection_time': detection_time,
                'zolder_detection_id': zolder_id,
                'zolder_confidence': zolder_conf,
                'zolder_file_name': zolder_file,
                'berging_detection_id': berging_id,
                'berging_confidence': berging_conf,
                'berging_file_name': berging_file,
                'time_difference_seconds': int(time_diff),
                'confidence_difference': round(conf_diff, 4),
                'avg_confidence': round(avg_conf, 4),
                'verification_score': round(verification_score, 4)
            }

            dual_records.append(dual_record)
            update_ids_zolder.append(zolder_id)
            update_ids_berging.append(berging_id)

            # Log significant dual detections
            self.logger.info(f"  Dual: {common_name} ({species}) - diff: {int(time_diff)}s, score: {verification_score:.2f}")

            # Publish MQTT alert for new dual detection
            if self.mqtt:
                self.mqtt.publish_new_dual({
                    'species': species,
                    'common_name': common_name,
                    'detection_time': detection_time.isoformat(),
                    'time_diff_seconds': int(time_diff),
                    'avg_confidence': round(avg_conf, 4),
                    'verification_score': round(verification_score, 4)
                })

        # Insert into dual_detections table
        inserted = self.insert_dual_detections(dual_records)

        # Update bird_detections table
        updated = self.update_bird_detections(update_ids_zolder, update_ids_berging)

        return inserted, updated

    def insert_dual_detections(self, records):
        """Insert records into dual_detections table"""
        if not records:
            return 0

        try:
            cursor = self.pg_conn.cursor()

            insert_query = """
                INSERT INTO dual_detections (
                    species, detection_time,
                    zolder_detection_id, zolder_confidence, zolder_file_name,
                    berging_detection_id, berging_confidence, berging_file_name,
                    time_difference_seconds, confidence_difference,
                    avg_confidence, verification_score
                ) VALUES (
                    %(species)s, %(detection_time)s,
                    %(zolder_detection_id)s, %(zolder_confidence)s, %(zolder_file_name)s,
                    %(berging_detection_id)s, %(berging_confidence)s, %(berging_file_name)s,
                    %(time_difference_seconds)s, %(confidence_difference)s,
                    %(avg_confidence)s, %(verification_score)s
                )
            """

            execute_batch(cursor, insert_query, records, page_size=100)
            self.pg_conn.commit()

            self.logger.success(f"Inserted {len(records)} dual detection records")
            return len(records)

        except psycopg2.Error as e:
            self.pg_conn.rollback()
            self.logger.error(f"Error inserting dual detections: {e}")
            return 0

    def update_bird_detections(self, zolder_ids, berging_ids):
        """Update bird_detections table to mark dual detections"""
        if not zolder_ids and not berging_ids:
            return 0

        try:
            cursor = self.pg_conn.cursor()
            updated = 0

            # Update zolder detections
            if zolder_ids:
                cursor.execute("""
                    UPDATE bird_detections
                    SET dual_detection = true,
                        detected_by_berging = true
                    WHERE id = ANY(%s)
                """, (zolder_ids,))
                updated += cursor.rowcount

            # Update berging detections
            if berging_ids:
                cursor.execute("""
                    UPDATE bird_detections
                    SET dual_detection = true,
                        detected_by_zolder = true
                    WHERE id = ANY(%s)
                """, (berging_ids,))
                updated += cursor.rowcount

            self.pg_conn.commit()
            self.logger.success(f"Updated {updated} bird detection records")
            return updated

        except psycopg2.Error as e:
            self.pg_conn.rollback()
            self.logger.error(f"Error updating bird detections: {e}")
            return 0

    def get_statistics(self):
        """Get dual detection statistics"""
        try:
            cursor = self.pg_conn.cursor()

            # Overall stats
            cursor.execute("""
                SELECT
                    COUNT(*) as total_duals,
                    COUNT(DISTINCT species) as unique_species,
                    AVG(verification_score) as avg_verification,
                    AVG(time_difference_seconds) as avg_time_diff,
                    MIN(detection_time) as first_dual,
                    MAX(detection_time) as last_dual
                FROM dual_detections
            """)
            row = cursor.fetchone()

            # Top species
            cursor.execute("""
                SELECT species, COUNT(*) as count
                FROM dual_detections
                GROUP BY species
                ORDER BY count DESC
                LIMIT 5
            """)
            top_species = cursor.fetchall()

            stats = {
                'total_dual_detections': row[0] or 0,
                'unique_species': row[1] or 0,
                'avg_verification_score': float(row[2]) if row[2] else 0,
                'avg_time_diff_seconds': float(row[3]) if row[3] else 0,
                'first_detection': row[4].isoformat() if row[4] else None,
                'last_detection': row[5].isoformat() if row[5] else None,
                'top_species': [{'species': s[0], 'count': s[1]} for s in top_species]
            }

            return stats

        except psycopg2.Error as e:
            self.logger.error(f"Error getting statistics: {e}")
            return {}

    def recalculate_all_verification_scores(self):
        """Recalculate verification scores for all existing dual detections using Bayesian model"""
        try:
            cursor = self.pg_conn.cursor()

            # Fetch all existing dual detections
            cursor.execute("""
                SELECT id, species, zolder_confidence, berging_confidence, time_difference_seconds
                FROM dual_detections
            """)
            records = cursor.fetchall()

            self.logger.info(f"Recalculating Bayesian scores for {len(records)} dual detections...")

            updated = 0
            for row in records:
                dual_id, species, zolder_conf, berging_conf, time_diff = row

                # Calculate new Bayesian verification score
                bayesian_result = self.bayesian_model.calculate_dual_verification_score(
                    species=species,
                    zolder_confidence=float(zolder_conf),
                    berging_confidence=float(berging_conf),
                    time_diff_seconds=float(time_diff)
                )
                new_score = bayesian_result['verification_score']

                # Update the record
                cursor.execute("""
                    UPDATE dual_detections
                    SET verification_score = %s
                    WHERE id = %s
                """, (new_score, dual_id))
                updated += 1

            self.pg_conn.commit()
            self.logger.success(f"Recalculated {updated} verification scores with Bayesian model")
            return updated

        except psycopg2.Error as e:
            self.pg_conn.rollback()
            self.logger.error(f"Error recalculating scores: {e}")
            return 0

    def close_connection(self):
        """Close database connection"""
        if self.pg_conn:
            self.pg_conn.close()
            self.logger.info("Database connection closed")


def main():
    """Main execution function"""

    # Initialize logger
    logger = SyncLogger(LOG_DIR)
    logger.info("=" * 80)
    logger.info("EMSN Dual Detection Sync")
    logger.info(f"Time window: {TIME_WINDOW_SECONDS}s | Min confidence: {MIN_CONFIDENCE}")
    logger.info("=" * 80)

    # Initialize MQTT publisher
    mqtt_pub = MQTTPublisher(MQTT_CONFIG, logger)
    mqtt_pub.connect()

    # Publish start status
    mqtt_pub.publish_status('running', 'Dual detection sync started')

    try:
        # Initialize sync handler
        sync = DualDetectionSync(logger, mqtt_pub)

        # Connect to database
        if not sync.connect_database():
            logger.error("Failed to connect to database")
            mqtt_pub.publish_status('error', 'Database connection failed')
            sys.exit(1)

        # Find and process dual detections
        logger.info("Searching for new dual detections...")
        detections = sync.find_new_dual_detections()

        if detections:
            logger.info("Processing dual detections...")
            inserted, updated = sync.process_dual_detections(detections)
        else:
            inserted, updated = 0, 0
            logger.info("No new dual detections found")

        # Get statistics
        stats = sync.get_statistics()

        # Log results
        logger.info("-" * 80)
        logger.success(f"Sync completed:")
        logger.info(f"  - New dual detections: {inserted}")
        logger.info(f"  - Records updated: {updated}")
        logger.info(f"  - Total dual detections: {stats.get('total_dual_detections', 0)}")
        logger.info(f"  - Unique species: {stats.get('unique_species', 0)}")
        logger.info("-" * 80)

        # Publish completion status
        mqtt_pub.publish_status(
            'completed',
            'Dual detection sync completed',
            {
                'new_duals': inserted,
                'records_updated': updated
            }
        )

        # Publish statistics
        mqtt_pub.publish_stats(stats)

        # Close connection
        sync.close_connection()

        logger.success("Dual detection sync completed successfully")

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        mqtt_pub.publish_status('error', f'Sync failed: {str(e)}')
        sys.exit(1)

    finally:
        mqtt_pub.disconnect()


if __name__ == "__main__":
    main()
