#!/usr/bin/env python3
"""
EMSN 2.0 - Cooldown MQTT Publisher for Home Assistant

Publiceert actieve cooldowns naar MQTT voor Home Assistant dashboard.
Refresh elke 30 seconden.
"""

import json
import sys
import time
import psycopg2
import paho.mqtt.client as mqtt
from datetime import datetime, timedelta
from pathlib import Path

# Add config path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'config'))
from ulanzi_config import MQTT as MQTT_CONFIG, PG_CONFIG, RARITY_TIERS, LOG_DIR


class CooldownDisplayLogger:
    """Simple logger"""

    def __init__(self):
        self.log_dir = Path(LOG_DIR)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / f"cooldown_display_{datetime.now().strftime('%Y%m%d')}.log"

    def log(self, level, message):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        entry = f"[{timestamp}] [{level}] {message}"
        print(entry)
        with open(self.log_file, 'a') as f:
            f.write(entry + '\n')

    def info(self, msg): self.log('INFO', msg)
    def error(self, msg): self.log('ERROR', msg)
    def warning(self, msg): self.log('WARNING', msg)
    def success(self, msg): self.log('SUCCESS', msg)


class CooldownPublisher:
    """Publishes active cooldowns to MQTT for Home Assistant"""

    def __init__(self):
        self.logger = CooldownDisplayLogger()
        self.pg_conn = None
        self.mqtt_client = None

    def connect_db(self):
        """Connect to PostgreSQL"""
        try:
            if self.pg_conn:
                try:
                    self.pg_conn.close()
                except (Exception, OSError):
                    pass  # Connection cleanup is non-critical
            self.pg_conn = psycopg2.connect(**PG_CONFIG)
            self.pg_conn.autocommit = True  # Voorkom idle in transaction
            self.logger.success("Connected to database")
            return True
        except Exception as e:
            self.logger.error(f"Database connection failed: {e}")
            return False

    def ensure_db_connection(self):
        """Ensure database connection is alive, reconnect if needed"""
        try:
            if self.pg_conn is None:
                return self.connect_db()
            # Test connection
            cursor = self.pg_conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            return True
        except Exception:
            self.logger.warning("Database connection lost, reconnecting...")
            return self.connect_db()

    def get_rarity_tier(self, species_nl):
        """Get rarity tier for a species based on detection count in last 30 days"""
        try:
            with self.pg_conn.cursor() as cursor:
                cursor.execute("""
                    SELECT COUNT(*) as detection_count
                    FROM bird_detections
                    WHERE common_name = %s
                    AND detection_timestamp >= NOW() - INTERVAL '30 days'
                """, (species_nl,))

                count = cursor.fetchone()[0]

            # Determine tier
            for tier_name, tier_config in RARITY_TIERS.items():
                if tier_config['min_count'] <= count <= tier_config['max_count']:
                    return tier_name, tier_config

            return 'abundant', RARITY_TIERS['abundant']

        except Exception as e:
            self.logger.error(f"Error getting rarity tier: {e}")
            return 'common', RARITY_TIERS['common']

    def get_active_cooldowns(self):
        """Get active cooldowns from notification log"""
        try:
            with self.pg_conn.cursor() as cursor:
                # Get last notification per species (only recent ones within 2 hours)
                # Calculate elapsed time in the database to avoid timezone issues
                cursor.execute("""
                    WITH ranked_notifications AS (
                        SELECT
                            species_nl,
                            timestamp,
                            rarity_tier,
                            EXTRACT(EPOCH FROM (NOW() - timestamp))::integer as elapsed_seconds,
                            ROW_NUMBER() OVER (PARTITION BY species_nl ORDER BY timestamp DESC) as rn
                        FROM ulanzi_notification_log
                        WHERE was_shown = true
                        AND timestamp >= NOW() - INTERVAL '2 hours'
                    )
                    SELECT species_nl, elapsed_seconds, rarity_tier
                    FROM ranked_notifications
                    WHERE rn = 1
                    ORDER BY elapsed_seconds ASC
                """)

                rows = cursor.fetchall()

            cooldowns = []

            for row in rows:
                species_nl, elapsed_seconds, db_tier = row

                # Get current tier and cooldown (may have changed since last notification)
                tier_name, tier_config = self.get_rarity_tier(species_nl)
                cooldown_seconds = tier_config['cooldown_seconds']

                # Only show if still in cooldown period
                if elapsed_seconds < cooldown_seconds:
                    remaining_seconds = cooldown_seconds - elapsed_seconds
                    cooldowns.append({
                        'species': species_nl,
                        'elapsed': elapsed_seconds,
                        'remaining': remaining_seconds,
                        'tier': tier_name,
                        'cooldown_total': cooldown_seconds
                    })

            return cooldowns

        except Exception as e:
            self.logger.error(f"Error getting cooldowns: {e}")
            return []

    def format_time(self, seconds):
        """Format seconds to readable time (HH:MM:SS or MM:SS)"""
        if seconds >= 3600:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            secs = seconds % 60
            return f"{hours}u{minutes:02d}m"
        elif seconds >= 60:
            minutes = seconds // 60
            secs = seconds % 60
            return f"{minutes}m{secs:02d}s"
        else:
            return f"{seconds}s"

    def connect_mqtt(self):
        """Connect to MQTT broker"""
        try:
            self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
            self.mqtt_client.username_pw_set(
                MQTT_CONFIG['username'],
                MQTT_CONFIG['password']
            )
            self.mqtt_client.connect(
                MQTT_CONFIG['broker'],
                MQTT_CONFIG['port'],
                60
            )
            self.mqtt_client.loop_start()
            self.logger.success("Connected to MQTT broker")
            return True
        except Exception as e:
            self.logger.error(f"MQTT connection failed: {e}")
            return False

    def publish_cooldowns(self, cooldowns):
        """Publish cooldown data to MQTT for Home Assistant"""
        try:
            # Prepare data for Home Assistant
            cooldown_list = []
            for cd in cooldowns:
                cooldown_list.append({
                    'species': cd['species'],
                    'remaining_seconds': cd['remaining'],
                    'remaining_formatted': self.format_time(cd['remaining']),
                    'tier': cd['tier'],
                    'cooldown_total': cd['cooldown_total']
                })

            payload = {
                'total_active': len(cooldowns),
                'cooldowns': cooldown_list,
                'timestamp': datetime.now().isoformat()
            }

            # Publish to MQTT
            topic = 'emsn2/ulanzi/cooldowns'
            self.mqtt_client.publish(topic, json.dumps(payload), qos=1, retain=True)

            self.logger.info(f"Published {len(cooldowns)} cooldowns to MQTT")
            return True

        except Exception as e:
            self.logger.error(f"Failed to publish cooldowns: {e}")
            return False

    def run(self):
        """Main loop - publish cooldowns every 30 seconds"""
        self.logger.info("=" * 60)
        self.logger.info("EMSN Cooldown MQTT Publisher Starting")
        self.logger.info("=" * 60)

        if not self.connect_db():
            return

        if not self.connect_mqtt():
            return

        try:
            while True:
                # Ensure database connection is alive
                if not self.ensure_db_connection():
                    self.logger.error("Failed to connect to database, retrying in 30s...")
                    time.sleep(30)
                    continue

                cooldowns = self.get_active_cooldowns()
                self.publish_cooldowns(cooldowns)
                time.sleep(30)  # Update every 30 seconds

        except KeyboardInterrupt:
            self.logger.info("Shutting down...")
        except Exception as e:
            self.logger.error(f"Error in main loop: {e}")
        finally:
            if self.mqtt_client:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
            if self.pg_conn:
                self.pg_conn.close()


def main():
    publisher = CooldownPublisher()
    publisher.run()


if __name__ == "__main__":
    main()
