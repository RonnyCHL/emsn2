#!/usr/bin/env python3
"""
FlySafe Migration Alerts
========================

Sends alerts to Ulanzi display and optionally email when
high bird migration intensity is detected.

Author: EMSN Team
"""

import os
import json
import logging
from datetime import datetime
from pathlib import Path
import requests

# Configuration
ULANZI_IP = "192.168.1.11"
MQTT_BROKER = "192.168.1.178"  # EMSN Zolder
MQTT_PORT = 1883

# Alert thresholds
ALERT_THRESHOLDS = {
    'low': 25,       # Green notification
    'moderate': 50,  # Yellow notification
    'high': 75,      # Orange notification
    'very_high': 90  # Red notification with animation
}

# State file to track daily alerts
STATE_FILE = Path("/mnt/usb/logs/migration_alert_state.json")

# Logging
LOGS_DIR = Path("/mnt/usb/logs")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOGS_DIR / "migration-alerts.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class MigrationAlertSystem:
    """Handles migration alerts to various outputs"""

    def __init__(self):
        self.last_alert_level = None
        self.last_alert_time = None
        self._load_state()

    def _load_state(self):
        """Load alert state from file"""
        try:
            if STATE_FILE.exists():
                with open(STATE_FILE, 'r') as f:
                    state = json.load(f)
                    self.last_alert_date = state.get('last_alert_date')
                    self.last_alert_level = state.get('last_alert_level')
            else:
                self.last_alert_date = None
        except Exception as e:
            logger.warning(f"Could not load state: {e}")
            self.last_alert_date = None

    def _save_state(self):
        """Save alert state to file"""
        try:
            state = {
                'last_alert_date': self.last_alert_date,
                'last_alert_level': self.last_alert_level,
                'updated_at': datetime.now().isoformat()
            }
            with open(STATE_FILE, 'w') as f:
                json.dump(state, f)
        except Exception as e:
            logger.warning(f"Could not save state: {e}")

    def _already_alerted_today(self):
        """Check if we already sent an alert today"""
        if not self.last_alert_date:
            return False
        today = datetime.now().strftime('%Y-%m-%d')
        return self.last_alert_date == today

    def get_alert_color(self, intensity):
        """Get color based on intensity level"""
        if intensity >= ALERT_THRESHOLDS['very_high']:
            return "#FF0000"  # Red
        elif intensity >= ALERT_THRESHOLDS['high']:
            return "#FF8800"  # Orange
        elif intensity >= ALERT_THRESHOLDS['moderate']:
            return "#FFFF00"  # Yellow
        elif intensity >= ALERT_THRESHOLDS['low']:
            return "#00FF00"  # Green
        else:
            return "#0088FF"  # Blue (minimal)

    def get_alert_icon(self, intensity):
        """Get icon name for Ulanzi based on intensity"""
        if intensity >= ALERT_THRESHOLDS['high']:
            return "bird"  # Flying bird icon
        elif intensity >= ALERT_THRESHOLDS['moderate']:
            return "bird"
        else:
            return "bird"

    def get_intensity_text(self, intensity):
        """Get Dutch text for intensity level"""
        if intensity >= ALERT_THRESHOLDS['very_high']:
            return "ZEER HOOG"
        elif intensity >= ALERT_THRESHOLDS['high']:
            return "HOOG"
        elif intensity >= ALERT_THRESHOLDS['moderate']:
            return "MATIG"
        elif intensity >= ALERT_THRESHOLDS['low']:
            return "LAAG"
        else:
            return "MINIMAAL"

    def send_ulanzi_alert(self, intensity, category=None):
        """Send alert to Ulanzi AWTRIX display via HTTP API"""
        try:
            color = self.get_alert_color(intensity)
            text = self.get_intensity_text(intensity)

            # AWTRIX Light API payload
            payload = {
                "text": f"Vogeltrek: {text} ({intensity}%)",
                "icon": "bird",
                "color": color,
                "duration": 10,
                "pushIcon": 2,  # Icon moves with text
            }

            # Add rainbow effect for very high intensity
            if intensity >= ALERT_THRESHOLDS['very_high']:
                payload["rainbow"] = True
                payload["duration"] = 15

            # Add blinking for high intensity
            elif intensity >= ALERT_THRESHOLDS['high']:
                payload["blinkText"] = 500
                payload["duration"] = 12

            url = f"http://{ULANZI_IP}/api/notify"
            response = requests.post(url, json=payload, timeout=5)

            if response.status_code == 200:
                logger.info(f"Ulanzi alert sent: {text} ({intensity}%)")
                return True
            else:
                logger.warning(f"Ulanzi alert failed: {response.status_code}")
                return False

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send Ulanzi alert: {e}")
            return False

    def send_ulanzi_custom_app(self, intensity, detections=0):
        """Update custom app on Ulanzi with migration status"""
        try:
            color = self.get_alert_color(intensity)
            text = f"{intensity}%"

            # Custom app payload for persistent display
            payload = {
                "text": text,
                "icon": "bird",
                "color": color,
                "lifetime": 7200,  # 2 hours until next update
                "textCase": 0,
            }

            # Add bird count if available
            if detections > 0:
                payload["text"] = f"{intensity}% | {detections} vogels"

            url = f"http://{ULANZI_IP}/api/custom?name=vogeltrek"
            response = requests.post(url, json=payload, timeout=5)

            if response.status_code == 200:
                logger.info(f"Ulanzi custom app updated: {intensity}%")
                return True
            else:
                logger.warning(f"Ulanzi custom app update failed: {response.status_code}")
                return False

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to update Ulanzi custom app: {e}")
            return False

    def check_and_alert(self, intensity, bird_detections=0, force=False):
        """
        Check if alert should be sent based on intensity
        Only sends ONE alert per day (first high intensity detection)
        """
        current_level = None

        # Determine current level
        for level, threshold in sorted(ALERT_THRESHOLDS.items(),
                                       key=lambda x: x[1], reverse=True):
            if intensity >= threshold:
                current_level = level
                break

        # Check if we should send notification
        should_notify = False
        today = datetime.now().strftime('%Y-%m-%d')

        if force:
            # Force flag bypasses daily limit (for testing)
            should_notify = True
            logger.info(f"Force alert requested: {intensity}%")
        elif self._already_alerted_today():
            # Already alerted today, skip
            logger.debug(f"Already alerted today, skipping ({intensity}%)")
            should_notify = False
        elif intensity >= ALERT_THRESHOLDS['high']:
            # First high intensity of the day
            should_notify = True
            logger.info(f"First high intensity alert of the day: {intensity}%")

        if should_notify:
            self.send_ulanzi_alert(intensity)
            self.last_alert_level = current_level
            self.last_alert_time = datetime.now()
            self.last_alert_date = today
            self._save_state()

        return should_notify


def check_latest_radar_and_alert():
    """Check latest radar observation and send alert if needed"""
    import sys
    import psycopg2
    from psycopg2.extras import RealDictCursor

    # Import core modules
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from core.config import get_postgres_config

    DB_CONFIG = get_postgres_config()

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Get latest radar observation
        cur.execute("""
            SELECT intensity_level, intensity_category, bird_detections_count
            FROM radar_observations
            ORDER BY observation_date DESC, observation_time DESC
            LIMIT 1
        """)

        result = cur.fetchone()
        conn.close()

        if result:
            intensity = result['intensity_level'] or 0
            detections = result['bird_detections_count'] or 0

            alert_system = MigrationAlertSystem()
            alert_system.check_and_alert(intensity, detections)

            return {
                'intensity': intensity,
                'detections': detections,
                'alerted': True
            }

        return None

    except Exception as e:
        logger.error(f"Failed to check radar and alert: {e}")
        return None


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='FlySafe Migration Alert System')
    parser.add_argument('--test', type=int, help='Test alert with given intensity (0-100)')
    parser.add_argument('--check', action='store_true', help='Check latest radar and alert')

    args = parser.parse_args()

    alert_system = MigrationAlertSystem()

    if args.test is not None:
        logger.info(f"Testing alert with intensity: {args.test}")
        alert_system.check_and_alert(args.test, bird_detections=42, force=True)
    elif args.check:
        result = check_latest_radar_and_alert()
        if result:
            logger.info(f"Checked and alerted: {result}")
    else:
        # Default: check latest radar
        check_latest_radar_and_alert()


if __name__ == '__main__':
    main()
