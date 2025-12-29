#!/usr/bin/env python3
"""
EMSN 2.0 - Data Gap Anomaly Checker

Checks for data quality issues:
- Database sync lag
- Station imbalance
- Database growth stalled

Runs every 15 minutes via systemd timer
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import psycopg2

# Add scripts path for core modules
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.logging import EMSNLogger
from core.config import get_postgres_config

# Configuration
SYNC_LAG_HOURS = 1
STATION_IMBALANCE_RATIO = 10  # Warn if one station has 10x more detections
DATABASE_GROWTH_STALLED_HOURS = 4


class DataGapChecker:
    def __init__(self):
        self.conn = None
        self.anomalies_found = []
        self.logger = EMSNLogger('data-gap-checker')

    def connect(self):
        try:
            pg_config = get_postgres_config()
            self.conn = psycopg2.connect(**pg_config)
            return True
        except Exception as e:
            self.log("ERROR", f"Database connection failed: {e}")
            return False

    def log(self, level, message):
        self.logger.log(level, message)

    def check_station_imbalance(self):
        """Check if one station has significantly more detections than the other"""
        cursor = self.conn.cursor()

        query = """
            SELECT
                station,
                COUNT(*) as detection_count
            FROM bird_detections
            WHERE detection_timestamp >= NOW() - INTERVAL '2 hours'
            GROUP BY station
        """

        cursor.execute(query)
        results = {row[0]: row[1] for row in cursor.fetchall()}

        zolder_count = results.get('zolder', 0)
        berging_count = results.get('berging', 0)

        if berging_count == 0 and zolder_count > 10:
            ratio = float('inf')
        elif zolder_count == 0 and berging_count > 10:
            ratio = float('inf')
        elif berging_count > 0:
            ratio = zolder_count / berging_count
        else:
            return  # Not enough data

        if ratio > STATION_IMBALANCE_RATIO or ratio < (1/STATION_IMBALANCE_RATIO):
            self.create_anomaly(
                anomaly_type='station_imbalance',
                severity='warning',
                station_id=None,
                description=f"Station imbalance: Zolder={zolder_count}, Berging={berging_count} (ratio: {ratio:.1f}:1)",
                metric_value=ratio,
                threshold_value=STATION_IMBALANCE_RATIO
            )

    def check_database_growth(self):
        """Check if database has stopped growing (no new detections)"""
        cursor = self.conn.cursor()

        query = """
            SELECT
                MAX(detection_timestamp) as last_detection,
                EXTRACT(EPOCH FROM (NOW() - MAX(detection_timestamp)))/3600 as hours_since
            FROM bird_detections
        """

        cursor.execute(query)
        row = cursor.fetchone()

        if row and row[1] and row[1] >= DATABASE_GROWTH_STALLED_HOURS:
            hours_since = row[1]
            self.create_anomaly(
                anomaly_type='database_growth_stalled',
                severity='warning',
                station_id=None,
                description=f"No new detections in {hours_since:.1f} hours (database growth stalled)",
                metric_value=hours_since,
                threshold_value=DATABASE_GROWTH_STALLED_HOURS
            )

    def create_anomaly(self, anomaly_type, severity, station_id, description, metric_value, threshold_value):
        cursor = self.conn.cursor()

        # Check if already exists
        query = """
            SELECT id FROM anomalies
            WHERE anomaly_type = %s
              AND resolved_at IS NULL
              AND timestamp >= NOW() - INTERVAL '12 hours'
            LIMIT 1
        """

        cursor.execute(query, (anomaly_type,))
        if cursor.fetchone():
            self.log("INFO", f"Anomaly already active: {anomaly_type}")
            return

        # Insert new anomaly
        cursor.execute("""
            INSERT INTO anomalies (
                anomaly_type, severity, station_id, description,
                metric_value, threshold_value, notified
            ) VALUES (%s, %s, %s, %s, %s, %s, FALSE)
        """, (anomaly_type, severity, station_id, description, metric_value, threshold_value))
        self.conn.commit()

        self.anomalies_found.append({'type': anomaly_type, 'severity': severity})
        self.log(severity.upper(), f"ANOMALY: {description}")

    def run(self):
        start_time = datetime.now()
        self.log("INFO", "Data gap check starting")

        if not self.connect():
            return False

        try:
            self.check_station_imbalance()
            self.check_database_growth()

            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO anomaly_check_log (check_type, anomalies_found, duration_ms)
                VALUES ('data_gap', %s, %s)
            """, (len(self.anomalies_found), duration_ms))
            self.conn.commit()

            self.log("INFO", f"Data gap check completed: {len(self.anomalies_found)} anomalies found")
            return True

        except Exception as e:
            self.log("ERROR", f"Data gap check failed: {e}")
            import traceback
            traceback.print_exc()
            return False

        finally:
            if self.conn:
                self.conn.close()


def main():
    checker = DataGapChecker()
    success = checker.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
