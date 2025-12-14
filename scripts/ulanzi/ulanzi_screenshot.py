#!/usr/bin/env python3
"""
EMSN 2.0 - Ulanzi Screenshot Service

Maakt screenshots van de Ulanzi TC001 display bij notificaties.
Slaat screenshots op naar NAS en logt in database.
"""

import json
import sys
import time
import requests
import psycopg2
from datetime import datetime
from pathlib import Path
from PIL import Image
import paho.mqtt.client as mqtt

# Add config path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'config'))
from ulanzi_config import ULANZI, MQTT as MQTT_CONFIG, PG_CONFIG, LOG_DIR

# Screenshot configuration
SCREENSHOT_DIR = Path("/mnt/nas-reports/ulanzi-screenshots")
# Delay moet lang genoeg zijn zodat de vogelnaam zichtbaar is
# Tekst scrollt van rechts naar links, vogelnaam komt na station-prefix
# 0.5s = te vroeg (alleen prefix zichtbaar)
# 4.0s = te laat (notificatie kan al voorbij zijn)
# 2.5s = sweet spot voor meeste notificaties
SCREENSHOT_DELAY_SECONDS = 2.5
MATRIX_WIDTH = 32
MATRIX_HEIGHT = 8
SCALE_FACTOR = 10  # Vergroot 10x voor leesbaarheid


class UlanziScreenshot:
    """Maakt en beheert Ulanzi screenshots"""

    def __init__(self):
        self.api_base = ULANZI['api_base']
        self.screenshot_dir = SCREENSHOT_DIR
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self.pg_conn = None
        self.mqtt_client = None
        self.log_file = Path(LOG_DIR) / f"ulanzi_screenshot_{datetime.now().strftime('%Y%m%d')}.log"

    def log(self, level, message):
        """Simple logging"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        entry = f"[{timestamp}] [{level}] {message}"
        print(entry)
        with open(self.log_file, 'a') as f:
            f.write(entry + '\n')

    def connect_db(self):
        """Connect to PostgreSQL"""
        try:
            self.pg_conn = psycopg2.connect(**PG_CONFIG)
            self.log('INFO', 'Connected to PostgreSQL')
            return True
        except Exception as e:
            self.log('ERROR', f'Database connection failed: {e}')
            return False

    def get_screen_pixels(self):
        """Get current screen pixels from Ulanzi API"""
        try:
            response = requests.get(f"{self.api_base}/screen", timeout=5)
            if response.status_code == 200:
                return response.json()
            else:
                self.log('ERROR', f'Screen API error: {response.status_code}')
                return None
        except Exception as e:
            self.log('ERROR', f'Failed to get screen: {e}')
            return None

    def pixels_to_image(self, pixels):
        """Convert pixel array to PIL Image"""
        # Ulanzi returns flat array of RGB integers (0xRRGGBB format)
        # Matrix is 32x8 pixels

        if len(pixels) != MATRIX_WIDTH * MATRIX_HEIGHT:
            self.log('WARNING', f'Unexpected pixel count: {len(pixels)}')

        # Create image at native resolution
        img = Image.new('RGB', (MATRIX_WIDTH, MATRIX_HEIGHT), color='black')

        for i, pixel in enumerate(pixels[:MATRIX_WIDTH * MATRIX_HEIGHT]):
            x = i % MATRIX_WIDTH
            y = i // MATRIX_WIDTH

            # Convert integer to RGB tuple
            r = (pixel >> 16) & 0xFF
            g = (pixel >> 8) & 0xFF
            b = pixel & 0xFF

            img.putpixel((x, y), (r, g, b))

        # Scale up for visibility
        scaled = img.resize(
            (MATRIX_WIDTH * SCALE_FACTOR, MATRIX_HEIGHT * SCALE_FACTOR),
            Image.NEAREST  # Keep pixels sharp
        )

        return scaled

    def take_screenshot(self, species_nl=None, detection_id=None, trigger_type='notification'):
        """Take a screenshot and save it"""
        pixels = self.get_screen_pixels()
        if not pixels:
            return None

        # Create image
        img = self.pixels_to_image(pixels)

        # Generate filename
        timestamp = datetime.now()
        date_dir = self.screenshot_dir / timestamp.strftime('%Y-%m-%d')
        date_dir.mkdir(parents=True, exist_ok=True)

        if species_nl:
            # Sanitize species name for filename
            safe_name = species_nl.replace(' ', '_').replace('/', '-')[:30]
            filename = f"{timestamp.strftime('%H%M%S')}_{safe_name}.png"
        else:
            filename = f"{timestamp.strftime('%H%M%S')}.png"

        filepath = date_dir / filename

        # Save image
        img.save(filepath, 'PNG')
        file_size = filepath.stat().st_size

        self.log('INFO', f'Screenshot saved: {filepath} ({file_size} bytes)')

        # Log to database
        self.log_screenshot(
            timestamp=timestamp,
            detection_id=detection_id,
            species_nl=species_nl,
            filename=filename,
            filepath=str(filepath),
            file_size=file_size,
            trigger_type=trigger_type
        )

        return str(filepath)

    def log_screenshot(self, timestamp, detection_id, species_nl, filename, filepath, file_size, trigger_type):
        """Log screenshot to database"""
        if not self.pg_conn:
            if not self.connect_db():
                return

        try:
            cursor = self.pg_conn.cursor()
            cursor.execute("""
                INSERT INTO ulanzi_screenshots
                (timestamp, detection_id, species_nl, filename, filepath, file_size, trigger_type)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (timestamp, detection_id, species_nl, filename, filepath, file_size, trigger_type))
            self.pg_conn.commit()
        except Exception as e:
            self.log('ERROR', f'Failed to log screenshot: {e}')
            try:
                self.pg_conn.rollback()
            except:
                pass

    def get_recent_screenshots(self, limit=20):
        """Get recent screenshots for dashboard"""
        if not self.pg_conn:
            if not self.connect_db():
                return []

        try:
            cursor = self.pg_conn.cursor()
            cursor.execute("""
                SELECT timestamp, species_nl, filename, filepath, trigger_type
                FROM ulanzi_screenshots
                ORDER BY timestamp DESC
                LIMIT %s
            """, (limit,))

            return [{
                'timestamp': row[0].isoformat(),
                'species_nl': row[1],
                'filename': row[2],
                'filepath': row[3],
                'trigger_type': row[4]
            } for row in cursor.fetchall()]
        except Exception as e:
            self.log('ERROR', f'Failed to get screenshots: {e}')
            return []

    def on_mqtt_connect(self, client, userdata, flags, reason_code, properties):
        """MQTT connection callback"""
        if reason_code == 0:
            self.log('INFO', 'Connected to MQTT broker')
            # Subscribe to notification confirmations
            client.subscribe('emsn2/ulanzi/screenshot/trigger', 1)
            client.subscribe('emsn2/ulanzi/screenshot/request', 1)
        else:
            self.log('ERROR', f'MQTT connection failed: {reason_code}')

    def on_mqtt_message(self, client, userdata, msg):
        """MQTT message callback"""
        topic = msg.topic

        try:
            if 'trigger' in topic:
                # Automatic trigger after notification
                data = json.loads(msg.payload.decode('utf-8'))
                species_nl = data.get('species_nl')
                detection_id = data.get('detection_id')

                # Wait for the text to scroll so the species name is visible
                time.sleep(SCREENSHOT_DELAY_SECONDS)

                filepath = self.take_screenshot(
                    species_nl=species_nl,
                    detection_id=detection_id,
                    trigger_type='notification'
                )

                if filepath:
                    # Publish confirmation
                    client.publish('emsn2/ulanzi/screenshot/taken', json.dumps({
                        'filepath': filepath,
                        'species_nl': species_nl,
                        'timestamp': datetime.now().isoformat()
                    }))

            elif 'request' in topic:
                # Manual screenshot request
                filepath = self.take_screenshot(trigger_type='manual')
                if filepath:
                    client.publish('emsn2/ulanzi/screenshot/taken', json.dumps({
                        'filepath': filepath,
                        'timestamp': datetime.now().isoformat()
                    }))

        except Exception as e:
            self.log('ERROR', f'Error processing message: {e}')

    def start(self):
        """Start the screenshot service"""
        self.log('INFO', '=' * 60)
        self.log('INFO', 'EMSN Ulanzi Screenshot Service Starting')
        self.log('INFO', '=' * 60)

        # Connect to database
        self.connect_db()

        # Setup MQTT client
        self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.mqtt_client.username_pw_set(MQTT_CONFIG['username'], MQTT_CONFIG['password'])
        self.mqtt_client.on_connect = self.on_mqtt_connect
        self.mqtt_client.on_message = self.on_mqtt_message

        try:
            self.mqtt_client.connect(MQTT_CONFIG['broker'], MQTT_CONFIG['port'], 60)
            self.log('INFO', 'Screenshot service started')
            self.mqtt_client.loop_forever()
        except KeyboardInterrupt:
            self.log('INFO', 'Shutting down...')
        except Exception as e:
            self.log('ERROR', f'Error: {e}')
        finally:
            if self.mqtt_client:
                self.mqtt_client.disconnect()


def main():
    service = UlanziScreenshot()
    service.start()


if __name__ == "__main__":
    main()
