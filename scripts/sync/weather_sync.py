#!/usr/bin/env python3
"""
EMSN Weather Sync Script - MeteoPi Station
Synchronizes weather data from local SQLite to central PostgreSQL database on NAS
"""

import sqlite3
import psycopg2
from psycopg2.extras import execute_batch
import json
import sys
from datetime import datetime
from pathlib import Path
import paho.mqtt.client as mqtt

# Import secrets
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'config'))
try:
    from emsn_secrets import get_postgres_config, get_mqtt_config
    _pg = get_postgres_config()
    _mqtt = get_mqtt_config()
except ImportError:
    import os
    _pg = {'host': '192.168.1.25', 'port': 5433, 'database': 'emsn',
           'user': 'meteopi', 'password': os.environ.get('EMSN_DB_PASSWORD', '')}
    _mqtt = {'broker': '192.168.1.178', 'port': 1883,
             'username': 'ecomonitor', 'password': os.environ.get('EMSN_MQTT_PASSWORD', '')}

# Configuration
SQLITE_DB = "/home/ronny/davis-integration/weather_production.db"
LOG_DIR = Path("/mnt/usb/logs")
STATION_NAME = "meteo"

# PostgreSQL Configuration (from secrets, override user for meteo)
PG_CONFIG = {
    'host': _pg.get('host', '192.168.1.25'),
    'port': _pg.get('port', 5433),
    'database': _pg.get('database', 'emsn'),
    'user': 'meteopi',
    'password': _pg.get('password', '')
}

# MQTT Configuration (from secrets)
MQTT_CONFIG = {
    'broker': _mqtt.get('broker', '192.168.1.178'),
    'port': _mqtt.get('port', 1883),
    'username': _mqtt.get('username', 'ecomonitor'),
    'password': _mqtt.get('password', ''),
    'topic_status': 'emsn2/meteo/sync/status',
    'topic_stats': 'emsn2/meteo/sync/stats',
    'topic_weather': 'emsn2/meteo/weather/current'
}

class SyncLogger:
    """Simple logger for sync operations"""

    def __init__(self, log_dir):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / f"weather_sync_{datetime.now().strftime('%Y%m%d')}.log"

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
    """MQTT publisher for weather updates"""

    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.client = None
        self.connected = False

    def connect(self):
        """Connect to MQTT broker"""
        try:
            self.client = mqtt.Client()
            self.client.username_pw_set(self.config['username'], self.config['password'])
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.connect(self.config['broker'], self.config['port'], 60)
            self.client.loop_start()
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect to MQTT broker: {e}")
            return False

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
            self.logger.info("Connected to MQTT broker")
        else:
            self.logger.error(f"MQTT connection failed with code {rc}")

    def _on_disconnect(self, client, userdata, rc):
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

    def publish_weather(self, weather_data):
        """Publish current weather data"""
        if not self.client:
            return

        try:
            self.client.publish(
                self.config['topic_weather'],
                json.dumps(weather_data),
                qos=0,
                retain=True
            )
        except Exception as e:
            self.logger.error(f"Failed to publish weather data: {e}")

    def disconnect(self):
        """Disconnect from MQTT broker"""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()

class WeatherDataSync:
    """Synchronizes weather data from SQLite to PostgreSQL"""

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

    def get_unsynced_weather_data(self):
        """Fetch unsynced weather data from SQLite"""
        try:
            cursor = self.sqlite_conn.cursor()

            query = """
                SELECT
                    timestamp,
                    temperatuur,
                    temperatuur_binnen,
                    luchtvochtigheid,
                    luchtvochtigheid_binnen,
                    luchtdruk,
                    luchtdruk_trend,
                    windsnelheid,
                    windrichting,
                    windstoot,
                    regen_vandaag,
                    regenintensiteit,
                    uv_index,
                    zonnestraling
                FROM weather_data
                WHERE synced_to_nas = 0
                ORDER BY timestamp
            """

            cursor.execute(query)
            weather_data = cursor.fetchall()

            self.logger.info(f"Found {len(weather_data)} unsynced weather records")
            return weather_data

        except sqlite3.Error as e:
            self.logger.error(f"Error reading from SQLite: {e}")
            return []

    def calculate_barometer_trend(self, trend_value):
        """Convert numeric trend to text"""
        if trend_value is None:
            return None
        if trend_value > 0.05:
            return 'rising'
        elif trend_value < -0.05:
            return 'falling'
        else:
            return 'steady'

    def sync_weather_data(self):
        """Main sync logic: transfer new weather data from SQLite to PostgreSQL"""

        # Get unsynced data
        weather_records = self.get_unsynced_weather_data()
        if not weather_records:
            self.logger.info("No new weather data to sync")
            return 0

        # Prepare records for PostgreSQL
        pg_records = []
        sqlite_ids = []

        for row in weather_records:
            try:
                measurement_time = datetime.fromisoformat(row['timestamp'])
            except (ValueError, TypeError):
                self.logger.warning(f"Invalid timestamp: {row['timestamp']}")
                continue

            # Map SQLite columns to PostgreSQL
            record = {
                'measurement_timestamp': measurement_time,
                'temp_outdoor': float(row['temperatuur']) if row['temperatuur'] else None,
                'temp_indoor': float(row['temperatuur_binnen']) if row['temperatuur_binnen'] else None,
                'humidity_outdoor': int(row['luchtvochtigheid']) if row['luchtvochtigheid'] else None,
                'humidity_indoor': int(row['luchtvochtigheid_binnen']) if row['luchtvochtigheid_binnen'] else None,
                'barometer': float(row['luchtdruk']) if row['luchtdruk'] else None,
                'barometer_trend': self.calculate_barometer_trend(row['luchtdruk_trend']),
                'wind_speed': float(row['windsnelheid']) if row['windsnelheid'] else None,
                'wind_direction': int(row['windrichting']) if row['windrichting'] else None,
                'wind_gust_speed': float(row['windstoot']) if row['windstoot'] else None,
                'rain_day': float(row['regen_vandaag']) if row['regen_vandaag'] else None,
                'rain_rate': float(row['regenintensiteit']) if row['regenintensiteit'] else None,
                'uv_index': float(row['uv_index']) if row['uv_index'] else None,
                'solar_radiation': int(row['zonnestraling']) if row['zonnestraling'] else None,
            }

            pg_records.append(record)

        # Insert into PostgreSQL
        if pg_records:
            self.logger.info(f"Inserting {len(pg_records)} weather records")
            inserted = self.insert_weather_data(pg_records)

            if inserted > 0:
                # Mark as synced in SQLite
                self.mark_as_synced(len(pg_records))

            return inserted
        else:
            self.logger.warning("No valid records to sync")
            return 0

    def insert_weather_data(self, records):
        """Batch insert weather data into PostgreSQL"""
        try:
            cursor = self.pg_conn.cursor()

            insert_query = """
                INSERT INTO weather_data (
                    measurement_timestamp, temp_outdoor, temp_indoor,
                    humidity_outdoor, humidity_indoor, barometer, barometer_trend,
                    wind_speed, wind_direction, wind_gust_speed,
                    rain_day, rain_rate, uv_index, solar_radiation
                ) VALUES (
                    %(measurement_timestamp)s, %(temp_outdoor)s, %(temp_indoor)s,
                    %(humidity_outdoor)s, %(humidity_indoor)s, %(barometer)s, %(barometer_trend)s,
                    %(wind_speed)s, %(wind_direction)s, %(wind_gust_speed)s,
                    %(rain_day)s, %(rain_rate)s, %(uv_index)s, %(solar_radiation)s
                )
            """

            execute_batch(cursor, insert_query, records, page_size=100)
            self.pg_conn.commit()

            self.logger.success(f"Successfully inserted {len(records)} weather records")
            return len(records)

        except psycopg2.Error as e:
            self.pg_conn.rollback()
            self.logger.error(f"Error inserting weather data: {e}")
            return 0

    def mark_as_synced(self, count):
        """Mark records as synced in SQLite"""
        try:
            cursor = self.sqlite_conn.cursor()

            # Mark the oldest N unsynced records
            cursor.execute("""
                UPDATE weather_data
                SET synced_to_nas = 1
                WHERE id IN (
                    SELECT id FROM weather_data
                    WHERE synced_to_nas = 0
                    ORDER BY timestamp
                    LIMIT ?
                )
            """, (count,))

            self.sqlite_conn.commit()
            self.logger.info(f"Marked {count} records as synced in SQLite")

        except sqlite3.Error as e:
            self.logger.error(f"Error marking records as synced: {e}")

    def get_latest_weather(self):
        """Get latest weather reading for MQTT"""
        try:
            cursor = self.sqlite_conn.cursor()

            cursor.execute("""
                SELECT * FROM weather_data
                ORDER BY timestamp DESC
                LIMIT 1
            """)

            row = cursor.fetchone()
            if row:
                return {
                    'timestamp': row['timestamp'],
                    'temp_outdoor': row['temperatuur'],
                    'temp_indoor': row['temperatuur_binnen'],
                    'humidity': row['luchtvochtigheid'],
                    'barometer': row['luchtdruk'],
                    'wind_speed': row['windsnelheid'],
                    'wind_direction': row['windrichting'],
                    'rain_today': row['regen_vandaag'],
                    'uv_index': row['uv_index'],
                    'solar_radiation': row['zonnestraling']
                }
            return None

        except sqlite3.Error as e:
            self.logger.error(f"Error getting latest weather: {e}")
            return None

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
    logger.info("EMSN Weather Sync - MeteoPi Station")
    logger.info("=" * 80)

    # Initialize MQTT publisher
    mqtt_pub = MQTTPublisher(MQTT_CONFIG, logger)
    mqtt_pub.connect()

    # Publish start status
    mqtt_pub.publish_status('running', 'Weather sync started')

    try:
        # Initialize sync handler
        sync = WeatherDataSync(logger, mqtt_pub)

        # Connect to databases
        if not sync.connect_databases():
            logger.error("Failed to connect to databases")
            mqtt_pub.publish_status('error', 'Database connection failed')
            sys.exit(1)

        # Perform sync
        logger.info("Starting weather data synchronization...")
        synced_count = sync.sync_weather_data()

        # Get latest weather for MQTT
        latest_weather = sync.get_latest_weather()
        if latest_weather:
            mqtt_pub.publish_weather(latest_weather)

        # Log results
        logger.info("-" * 80)
        logger.success(f"Sync completed: {synced_count} weather records transferred")
        logger.info("-" * 80)

        # Publish completion status
        mqtt_pub.publish_status(
            'completed',
            f'Weather sync completed successfully',
            {'synced_count': synced_count}
        )

        # Close connections
        sync.close_connections()

        logger.success("Weather sync completed successfully")

    except Exception as e:
        logger.error(f"Unexpected error during sync: {e}")
        mqtt_pub.publish_status('error', f'Sync failed: {str(e)}')
        sys.exit(1)

    finally:
        mqtt_pub.disconnect()

if __name__ == "__main__":
    main()
