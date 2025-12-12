#!/usr/bin/env python3
"""
EMSN 2.0 - Hardware Anomaly Checker

Checks for hardware-related anomalies:
- Silence (daytime and total)
- Low confidence clusters
- Meteo sensor failures

Runs every 15 minutes via systemd timer
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import psycopg2

# Add config path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'config'))
from station_config import POSTGRES_CONFIG, POSTGRES_USERS

# Configuration
SILENCE_DAYTIME_HOURS = 2    # Warning if no detections for 2 hours during daytime
SILENCE_TOTAL_HOURS = 6      # Critical if no detections for 6 hours total
LOW_CONFIDENCE_COUNT = 10    # Warning if 10+ consecutive detections all <65%
LOW_CONFIDENCE_THRESHOLD = 0.65
DAYTIME_START = 6            # 06:00
DAYTIME_END = 22             # 22:00
METEO_SILENCE_HOURS = 2      # Warning if no weather data for 2 hours


class HardwareChecker:
    """Check for hardware anomalies"""

    def __init__(self):
        self.conn = None
        self.anomalies_found = []

    def connect(self):
        """Connect to PostgreSQL"""
        try:
            self.conn = psycopg2.connect(
                host=POSTGRES_CONFIG['host'],
                port=POSTGRES_CONFIG['port'],
                database=POSTGRES_CONFIG['database'],
                user=POSTGRES_USERS['zolder']['user'],
                password=POSTGRES_USERS['zolder']['password']
            )
            return True
        except Exception as e:
            print(f"[ERROR] Database connection failed: {e}")
            return False

    def log(self, level, message):
        """Log message"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] [{level}] {message}")

    def check_station_silence(self, station_id):
        """Check if a bird detection station has been silent"""
        cursor = self.conn.cursor()

        # Get last detection time for this station
        query = """
            SELECT
                MAX(detection_timestamp) as last_detection,
                EXTRACT(EPOCH FROM (NOW() - MAX(detection_timestamp)))/3600 as hours_since
            FROM bird_detections
            WHERE station = %s
        """

        cursor.execute(query, (station_id,))
        row = cursor.fetchone()

        if not row or not row[0]:
            self.log("WARNING", f"No detections found for station {station_id}")
            return

        last_detection, hours_since = row

        # Check current hour
        current_hour = datetime.now().hour
        is_daytime = DAYTIME_START <= current_hour < DAYTIME_END

        # Check for daytime silence
        if is_daytime and hours_since >= SILENCE_DAYTIME_HOURS:
            self.create_anomaly(
                anomaly_type='silence_daytime',
                severity='warning',
                station_id=station_id,
                description=f"No detections for {hours_since:.1f} hours during daytime",
                metric_value=hours_since,
                threshold_value=SILENCE_DAYTIME_HOURS
            )

        # Check for total silence (critical)
        if hours_since >= SILENCE_TOTAL_HOURS:
            self.create_anomaly(
                anomaly_type='silence_total',
                severity='critical',
                station_id=station_id,
                description=f"No detections for {hours_since:.1f} hours (possible hardware failure)",
                metric_value=hours_since,
                threshold_value=SILENCE_TOTAL_HOURS
            )

    def check_low_confidence_cluster(self, station_id):
        """Check for cluster of low confidence detections (possible mic issue)"""
        cursor = self.conn.cursor()

        # Get last N detections
        query = """
            SELECT confidence
            FROM bird_detections
            WHERE station = %s
            ORDER BY detection_timestamp DESC
            LIMIT %s
        """

        cursor.execute(query, (station_id, LOW_CONFIDENCE_COUNT))
        confidences = [row[0] for row in cursor.fetchall()]

        if len(confidences) < LOW_CONFIDENCE_COUNT:
            return  # Not enough data

        # Check if all are below threshold
        all_low = all(c < LOW_CONFIDENCE_THRESHOLD for c in confidences)

        if all_low:
            avg_conf = sum(confidences) / len(confidences)
            self.create_anomaly(
                anomaly_type='low_confidence_cluster',
                severity='warning',
                station_id=station_id,
                description=f"Last {LOW_CONFIDENCE_COUNT} detections all below {LOW_CONFIDENCE_THRESHOLD*100:.0f}% confidence (avg: {avg_conf*100:.1f}%)",
                metric_value=avg_conf,
                threshold_value=LOW_CONFIDENCE_THRESHOLD
            )

    def check_meteo_silence(self):
        """Check if meteo station has stopped sending data"""
        cursor = self.conn.cursor()

        # Get last weather measurement
        query = """
            SELECT
                MAX(measurement_timestamp) as last_measurement,
                EXTRACT(EPOCH FROM (NOW() - MAX(measurement_timestamp)))/3600 as hours_since
            FROM weather_data
        """

        cursor.execute(query)
        row = cursor.fetchone()

        if not row or not row[0]:
            self.log("WARNING", "No weather data found")
            return

        last_measurement, hours_since = row

        if hours_since >= METEO_SILENCE_HOURS:
            self.create_anomaly(
                anomaly_type='meteo_silence',
                severity='warning',
                station_id='meteo',
                description=f"No weather data for {hours_since:.1f} hours",
                metric_value=hours_since,
                threshold_value=METEO_SILENCE_HOURS
            )

    def check_meteo_sensor_failure(self):
        """Check for sensor failures (NULL values or out-of-range)"""
        cursor = self.conn.cursor()

        # Check recent measurements for NULL values
        query = """
            SELECT
                COUNT(*) as total_measurements,
                SUM(CASE WHEN temp_outdoor IS NULL THEN 1 ELSE 0 END) as null_temp,
                SUM(CASE WHEN humidity_outdoor IS NULL THEN 1 ELSE 0 END) as null_humidity,
                SUM(CASE WHEN barometer IS NULL THEN 1 ELSE 0 END) as null_pressure,
                SUM(CASE WHEN wind_speed IS NULL THEN 1 ELSE 0 END) as null_wind
            FROM weather_data
            WHERE measurement_timestamp >= NOW() - INTERVAL '1 hour'
        """

        cursor.execute(query)
        row = cursor.fetchone()

        if not row or row[0] == 0:
            return  # No recent data

        total, null_temp, null_humidity, null_pressure, null_wind = row

        # If >50% of recent measurements have NULL values, sensor likely failed
        null_ratio = (null_temp + null_humidity + null_pressure + null_wind) / (total * 4)

        if null_ratio > 0.5:
            self.create_anomaly(
                anomaly_type='meteo_sensor_failure',
                severity='warning',
                station_id='meteo',
                description=f"High rate of NULL sensor values ({null_ratio*100:.1f}% in last hour)",
                metric_value=null_ratio,
                threshold_value=0.5
            )

    def create_anomaly(self, anomaly_type, severity, station_id, description, metric_value, threshold_value):
        """Create anomaly record in database (if not already active)"""

        # Check if this anomaly already exists and is active
        cursor = self.conn.cursor()

        query = """
            SELECT id FROM anomalies
            WHERE anomaly_type = %s
              AND station_id = %s
              AND resolved_at IS NULL
              AND timestamp >= NOW() - INTERVAL '12 hours'
            LIMIT 1
        """

        cursor.execute(query, (anomaly_type, station_id))
        existing = cursor.fetchone()

        if existing:
            self.log("INFO", f"Anomaly already active: {anomaly_type} for {station_id}")
            return  # Don't create duplicate

        # Insert new anomaly
        insert_query = """
            INSERT INTO anomalies (
                anomaly_type, severity, station_id, description,
                metric_value, threshold_value, notified
            ) VALUES (
                %s, %s, %s, %s, %s, %s, FALSE
            )
        """

        cursor.execute(insert_query, (
            anomaly_type, severity, station_id, description,
            metric_value, threshold_value
        ))
        self.conn.commit()

        self.anomalies_found.append({
            'type': anomaly_type,
            'severity': severity,
            'station': station_id,
            'description': description
        })

        self.log(severity.upper(), f"ANOMALY: {description}")

    def run(self):
        """Main execution"""
        start_time = datetime.now()
        self.log("INFO", "Hardware anomaly check starting")

        if not self.connect():
            return False

        try:
            # Check bird detection stations
            for station in ['zolder', 'berging']:
                self.check_station_silence(station)
                self.check_low_confidence_cluster(station)

            # Check meteo station
            self.check_meteo_silence()
            self.check_meteo_sensor_failure()

            # Log check completion
            cursor = self.conn.cursor()
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            cursor.execute("""
                INSERT INTO anomaly_check_log (check_type, anomalies_found, duration_ms)
                VALUES ('hardware', %s, %s)
            """, (len(self.anomalies_found), duration_ms))
            self.conn.commit()

            self.log("INFO", f"Hardware check completed: {len(self.anomalies_found)} anomalies found")
            return True

        except Exception as e:
            self.log("ERROR", f"Hardware check failed: {e}")
            import traceback
            traceback.print_exc()
            return False

        finally:
            if self.conn:
                self.conn.close()


def main():
    checker = HardwareChecker()
    success = checker.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
