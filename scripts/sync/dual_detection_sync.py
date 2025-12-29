#!/usr/bin/env python3
"""
EMSN 2.0 - Dual Detection Sync
Detecteert en markeert vogels die op beide stations (zolder + berging) zijn waargenomen
binnen een configureerbaar tijdsvenster.

Dit script draait alleen op het centrale station (zolder) omdat het beide datasets vergelijkt.

Refactored: 2025-12-29 - Gebruikt nu core modules voor logging en MQTT
"""

import psycopg2
from psycopg2.extras import execute_batch
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path for core modules
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / 'config'))

# Import EMSN core modules (vervangt gedupliceerde code)
from scripts.core.logging import EMSNLogger
from scripts.core.config import get_postgres_config, get_mqtt_config
from scripts.core.mqtt import MQTTPublisher as CoreMQTTPublisher

# Import Bayesian verification model
from bayesian_verification import BayesianVerificationModel, calculate_bayesian_verification_score

# Configuration
STATION_NAME = "zolder"  # Dit script draait alleen op zolder (centraal)
LOG_DIR = Path("/mnt/usb/logs")

# Dual detection parameters
TIME_WINDOW_SECONDS = 30  # Maximale tijd tussen detecties om als dual te markeren
MIN_CONFIDENCE = 0.7     # Minimale confidence voor dual detection

# PostgreSQL Configuration (from core config)
PG_CONFIG = get_postgres_config()

# MQTT Topics
MQTT_TOPICS = {
    'status': 'emsn2/dual/sync/status',
    'stats': 'emsn2/dual/sync/stats',
    'alert': 'emsn2/dual/detection/new'
}


class DualMQTTPublisher(CoreMQTTPublisher):
    """Dual detection-specifieke MQTT publisher met convenience methods."""

    def __init__(self, logger):
        super().__init__(logger)

    def publish_status(self, status, message, details=None):
        """Publish sync status update"""
        payload = {
            'timestamp': datetime.now().isoformat(),
            'status': status,
            'message': message
        }
        if details:
            payload.update(details)
        self.publish(MQTT_TOPICS['status'], payload, qos=1)

    def publish_stats(self, stats):
        """Publish dual detection statistics"""
        payload = {
            'timestamp': datetime.now().isoformat(),
            **stats
        }
        self.publish(MQTT_TOPICS['stats'], payload, qos=1, retain=True)

    def publish_new_dual(self, detection):
        """Publish alert for new dual detection"""
        self.publish(MQTT_TOPICS['alert'], detection, qos=1)


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

    # Initialize logger (gebruikt nu core EMSNLogger)
    logger = EMSNLogger('dual_detection', LOG_DIR)
    logger.info("=" * 80)
    logger.info("EMSN Dual Detection Sync")
    logger.info(f"Time window: {TIME_WINDOW_SECONDS}s | Min confidence: {MIN_CONFIDENCE}")
    logger.info("=" * 80)

    # Initialize MQTT publisher (gebruikt nu core MQTTPublisher)
    mqtt_pub = DualMQTTPublisher(logger)
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
