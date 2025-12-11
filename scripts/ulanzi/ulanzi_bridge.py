#!/usr/bin/env python3
"""
EMSN 2.0 - Ulanzi Bridge Service

Luistert naar MQTT detectie berichten en stuurt notificaties naar de Ulanzi TC001.
Voert anti-spam filtering uit gebaseerd op rarity tiers.
"""

import json
import re
import sys
import time
import requests
import psycopg2
from datetime import datetime, timedelta
from pathlib import Path
import paho.mqtt.client as mqtt

# Add config path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'config'))
from ulanzi_config import (
    ULANZI, MQTT as MQTT_CONFIG, PG_CONFIG,
    RARITY_TIERS, CONFIDENCE_COLORS, CONFIDENCE_THRESHOLDS,
    DISPLAY, SPECIAL_EVENTS, LOG_DIR
)


class UlanziLogger:
    """Simple logger"""

    def __init__(self):
        self.log_dir = Path(LOG_DIR)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / f"ulanzi_bridge_{datetime.now().strftime('%Y%m%d')}.log"

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


class RarityCache:
    """Cache voor species rarity tiers"""

    def __init__(self, logger):
        self.logger = logger
        self.cache = {}
        self.last_refresh = None
        self.pg_conn = None

    def connect(self):
        """Connect to PostgreSQL"""
        try:
            self.pg_conn = psycopg2.connect(**PG_CONFIG)
            return True
        except Exception as e:
            self.logger.error(f"Database connection failed: {e}")
            return False

    def refresh(self):
        """Refresh rarity cache from database"""
        if not self.pg_conn:
            if not self.connect():
                return False

        try:
            cursor = self.pg_conn.cursor()

            # Get detection counts per species in last 30 days
            cursor.execute("""
                SELECT
                    common_name,
                    species,
                    COUNT(*) as detection_count
                FROM bird_detections
                WHERE detection_timestamp >= NOW() - INTERVAL '30 days'
                GROUP BY common_name, species
            """)

            self.cache = {}
            for row in cursor.fetchall():
                common_name, species, count = row
                tier = self._get_tier(count)
                self.cache[common_name] = {
                    'species': species,
                    'count': count,
                    'tier': tier,
                    'tier_config': RARITY_TIERS[tier]
                }

            self.last_refresh = datetime.now()
            self.logger.info(f"Rarity cache refreshed: {len(self.cache)} species")
            return True

        except Exception as e:
            self.logger.error(f"Error refreshing rarity cache: {e}")
            return False

    def _get_tier(self, count):
        """Determine rarity tier based on count"""
        for tier_name, tier_config in RARITY_TIERS.items():
            if tier_config['min_count'] <= count <= tier_config['max_count']:
                return tier_name
        return 'very_common'

    def get_species_info(self, common_name):
        """Get species info including rarity tier"""
        # Refresh if cache is older than 1 hour
        if not self.last_refresh or (datetime.now() - self.last_refresh).seconds > 3600:
            self.refresh()

        if common_name in self.cache:
            return self.cache[common_name]

        # Unknown species = rare
        return {
            'species': None,
            'count': 0,
            'tier': 'rare',
            'tier_config': RARITY_TIERS['rare']
        }


class CooldownManager:
    """Manages notification cooldowns per species"""

    def __init__(self):
        self.last_notification = {}

    def can_notify(self, common_name, tier_config, is_special=False):
        """Check if notification is allowed based on cooldown"""
        if is_special:
            return True

        cooldown = tier_config['cooldown_seconds']
        if cooldown == 0:
            return True

        last_time = self.last_notification.get(common_name)
        if not last_time:
            return True

        elapsed = (datetime.now() - last_time).total_seconds()
        return elapsed >= cooldown

    def record_notification(self, common_name):
        """Record that a notification was sent"""
        self.last_notification[common_name] = datetime.now()


class UlanziNotifier:
    """Sends notifications to Ulanzi TC001"""

    def __init__(self, logger):
        self.logger = logger
        self.api_base = ULANZI['api_base']

    def get_color(self, confidence, is_dual=False):
        """Get color based on confidence level"""
        if is_dual:
            return CONFIDENCE_COLORS['dual']

        if confidence >= CONFIDENCE_THRESHOLDS['excellent']:
            return CONFIDENCE_COLORS['excellent']
        elif confidence >= CONFIDENCE_THRESHOLDS['good']:
            return CONFIDENCE_COLORS['good']
        elif confidence >= CONFIDENCE_THRESHOLDS['medium']:
            return CONFIDENCE_COLORS['medium']
        else:
            return CONFIDENCE_COLORS['low']

    def format_message(self, station, common_name, confidence, is_dual=False, is_new_species=False):
        """Format notification message"""
        conf_pct = int(confidence * 100)

        if is_new_species:
            return f"{station}-***NIEUW 2025***-{common_name}-{conf_pct}%"
        elif is_dual:
            return f"Dubbel-{common_name}-{conf_pct}%"
        else:
            return f"{station}-{common_name}-{conf_pct}%"

    def calculate_duration(self, message):
        """Calculate display duration based on message length"""
        base = DISPLAY['base_duration_ms']
        per_char = DISPLAY['per_char_duration_ms']
        calculated = base + (len(message) * per_char)
        return min(calculated, DISPLAY['max_duration_ms'])

    def send_notification(self, message, color, sound=None, duration=None):
        """Send notification to Ulanzi via HTTP API"""
        if duration is None:
            duration = self.calculate_duration(message)

        # Convert hex color to RGB list
        color_hex = color.lstrip('#')
        color_rgb = [int(color_hex[i:i+2], 16) for i in (0, 2, 4)]

        payload = {
            'text': message,
            'color': color_rgb,
            'duration': duration // 1000,  # AWTRIX uses seconds
            'scrollSpeed': DISPLAY['scroll_speed'],
        }

        if sound:
            payload['rtttl'] = sound  # AWTRIX uses rtttl for custom sounds

        try:
            url = f"{self.api_base}/notify"
            response = requests.post(url, json=payload, timeout=5)

            if response.status_code == 200:
                self.logger.success(f"Notification sent: {message}")
                return True
            else:
                self.logger.error(f"Ulanzi API error: {response.status_code}")
                return False

        except Exception as e:
            self.logger.error(f"Failed to send notification: {e}")
            return False


class UlanziBridge:
    """Main bridge service"""

    def __init__(self):
        self.logger = UlanziLogger()
        self.rarity_cache = RarityCache(self.logger)
        self.cooldown = CooldownManager()
        self.notifier = UlanziNotifier(self.logger)
        self.mqtt_client = None
        self.running = False
        self.presence_home = True  # Default: assume home

    def parse_apprise_message(self, payload):
        """Parse Apprise notification message to extract detection info"""
        # Apprise body format from body.txt:
        # "A $comname ($sciname) was just detected with a confidence of $confidence ($reason)"

        try:
            text = payload.decode('utf-8') if isinstance(payload, bytes) else payload

            # Try to parse the standard format
            # Example: "A Eurasian Magpie (Pica pica) was just detected with a confidence of 0.87 (detection)"
            pattern = r"A (.+?) \((.+?)\) was just detected with a confidence of ([\d.]+)"
            match = re.search(pattern, text)

            if match:
                common_name = match.group(1)
                scientific_name = match.group(2)
                confidence = float(match.group(3))

                return {
                    'common_name': common_name,
                    'scientific_name': scientific_name,
                    'confidence': confidence,
                    'raw': text
                }

            self.logger.warning(f"Could not parse message: {text[:100]}")
            return None

        except Exception as e:
            self.logger.error(f"Error parsing message: {e}")
            return None

    def on_mqtt_connect(self, client, userdata, flags, reason_code, properties):
        """MQTT connection callback"""
        if reason_code == 0:
            self.logger.success("Connected to MQTT broker")

            # Subscribe to detection topics
            topics = [
                (MQTT_CONFIG['topics']['zolder_detection'], 1),
                (MQTT_CONFIG['topics']['berging_detection'], 1),
                (MQTT_CONFIG['topics']['presence'], 1),
            ]
            client.subscribe(topics)
            self.logger.info(f"Subscribed to {len(topics)} topics")
        else:
            self.logger.error(f"MQTT connection failed: {reason_code}")

    def on_mqtt_message(self, client, userdata, msg):
        """MQTT message callback"""
        topic = msg.topic

        # Handle presence updates
        if 'presence' in topic:
            try:
                self.presence_home = msg.payload.decode().lower() in ('true', '1', 'home')
                self.logger.info(f"Presence updated: {'home' if self.presence_home else 'away'}")
            except:
                pass
            return

        # Skip if not home
        if not self.presence_home:
            self.logger.info("Skipping notification (not home)")
            return

        # Determine station from topic
        if 'zolder' in topic:
            station = 'Zolder'
        elif 'berging' in topic:
            station = 'Berging'
        else:
            station = 'Unknown'

        # Parse the detection message
        detection = self.parse_apprise_message(msg.payload)
        if not detection:
            return

        # Check confidence threshold
        if detection['confidence'] < CONFIDENCE_THRESHOLDS['min_display']:
            self.logger.info(f"Skipping low confidence: {detection['common_name']} ({detection['confidence']:.0%})")
            return

        # Get species rarity info
        species_info = self.rarity_cache.get_species_info(detection['common_name'])
        tier_config = species_info['tier_config']

        # Check cooldown
        if not self.cooldown.can_notify(detection['common_name'], tier_config):
            self.logger.info(f"Skipping (cooldown): {detection['common_name']}")
            return

        # Format and send notification
        message = self.notifier.format_message(
            station=station,
            common_name=detection['common_name'],
            confidence=detection['confidence']
        )

        color = self.notifier.get_color(detection['confidence'])
        sound = tier_config['sound'] if tier_config['play_sound'] else None

        if self.notifier.send_notification(message, color, sound):
            self.cooldown.record_notification(detection['common_name'])

            # Log to database
            self.log_notification(detection, station, species_info['tier'], True)
        else:
            self.log_notification(detection, station, species_info['tier'], False, 'send_failed')

    def log_notification(self, detection, station, tier, was_shown, skip_reason=None):
        """Log notification to database"""
        try:
            if not self.rarity_cache.pg_conn:
                self.rarity_cache.connect()

            cursor = self.rarity_cache.pg_conn.cursor()
            cursor.execute("""
                INSERT INTO ulanzi_notification_log
                (species_nl, station, confidence, rarity_tier, was_shown, skip_reason, notification_type)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                detection['common_name'],
                station.lower(),
                detection['confidence'],
                tier,
                was_shown,
                skip_reason,
                'standard'
            ))
            self.rarity_cache.pg_conn.commit()
        except Exception as e:
            self.logger.error(f"Error logging notification: {e}")

    def start(self):
        """Start the bridge service"""
        self.logger.info("=" * 60)
        self.logger.info("EMSN Ulanzi Bridge Service Starting")
        self.logger.info("=" * 60)

        # Initialize rarity cache
        self.rarity_cache.refresh()

        # Setup MQTT client
        self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.mqtt_client.username_pw_set(
            MQTT_CONFIG['username'],
            MQTT_CONFIG['password']
        )
        self.mqtt_client.on_connect = self.on_mqtt_connect
        self.mqtt_client.on_message = self.on_mqtt_message

        try:
            self.mqtt_client.connect(
                MQTT_CONFIG['broker'],
                MQTT_CONFIG['port'],
                60
            )

            self.running = True
            self.logger.success("Bridge service started")

            # Run forever
            self.mqtt_client.loop_forever()

        except KeyboardInterrupt:
            self.logger.info("Shutting down...")
        except Exception as e:
            self.logger.error(f"Error: {e}")
        finally:
            self.running = False
            if self.mqtt_client:
                self.mqtt_client.disconnect()


def main():
    bridge = UlanziBridge()
    bridge.start()


if __name__ == "__main__":
    main()
