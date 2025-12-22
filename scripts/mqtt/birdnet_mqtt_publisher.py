#!/usr/bin/env python3
"""
EMSN BirdNET MQTT Publisher
Monitors BirdNET-Pi SQLite database and publishes new detections to MQTT
"""

import os
import sys
import json
import time
import sqlite3
import logging
import socket
from datetime import datetime
from pathlib import Path
import paho.mqtt.client as mqtt

# Import secrets voor credentials
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'config'))
try:
    from emsn_secrets import get_mqtt_config
    _mqtt = get_mqtt_config()
except ImportError:
    _mqtt = {'username': 'ecomonitor', 'password': os.environ.get('EMSN_MQTT_PASSWORD', '')}

# Configuration
STATION_NAME = os.getenv("EMSN_STATION", socket.gethostname().replace("emsn2-", ""))
BIRDNET_DB = Path("/home/ronny/BirdNET-Pi/scripts/birds.db")

MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")  # Use localhost for local broker
MQTT_PORT = 1883
MQTT_USER = _mqtt.get('username', 'ecomonitor')
MQTT_PASS = _mqtt.get('password', '')

# Topics
TOPIC_DETECTION = f"birdnet/{STATION_NAME}/detection"
TOPIC_STATS = f"birdnet/{STATION_NAME}/stats"

# State
STATE_FILE = Path(f"/mnt/usb/logs/birdnet_mqtt_{STATION_NAME}_state.json")
CHECK_INTERVAL = 30  # seconds

# Logging
LOG_DIR = Path("/mnt/usb/logs")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / f"birdnet_mqtt_{STATION_NAME}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class BirdNetMQTTPublisher:
    def __init__(self):
        self.last_detection_id = self.load_last_id()
        self.client = None
        self.connected = False

    def load_last_id(self):
        """Load last processed detection ID"""
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE) as f:
                    data = json.load(f)
                    return data.get("last_detection_id", 0)
            except:
                pass
        return 0

    def save_last_id(self):
        """Save last processed detection ID"""
        try:
            with open(STATE_FILE, 'w') as f:
                json.dump({"last_detection_id": self.last_detection_id}, f)
        except Exception as e:
            logger.warning(f"Could not save state: {e}")

    def connect_mqtt(self):
        """Connect to MQTT broker"""
        try:
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
            self.client.username_pw_set(MQTT_USER, MQTT_PASS)

            def on_connect(client, userdata, flags, rc, properties=None):
                if rc == 0:
                    logger.info(f"Connected to MQTT broker at {MQTT_BROKER}")
                    self.connected = True
                else:
                    logger.error(f"MQTT connection failed: {rc}")
                    self.connected = False

            def on_disconnect(client, userdata, flags, rc, properties=None):
                logger.warning("Disconnected from MQTT broker")
                self.connected = False

            self.client.on_connect = on_connect
            self.client.on_disconnect = on_disconnect

            self.client.connect(MQTT_BROKER, MQTT_PORT, 60)
            self.client.loop_start()

            # Wait for connection
            time.sleep(1)
            return self.connected

        except Exception as e:
            logger.error(f"MQTT connection error: {e}")
            return False

    def get_new_detections(self):
        """Get new detections from BirdNET database"""
        if not BIRDNET_DB.exists():
            logger.warning(f"BirdNET database not found: {BIRDNET_DB}")
            return []

        try:
            conn = sqlite3.connect(str(BIRDNET_DB))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Get new detections since last check
            cursor.execute("""
                SELECT * FROM detections
                WHERE rowid > ?
                ORDER BY rowid ASC
                LIMIT 100
            """, (self.last_detection_id,))

            detections = []
            for row in cursor.fetchall():
                detection = dict(row)
                detection['rowid'] = row['rowid'] if 'rowid' in row.keys() else self.last_detection_id + 1
                detections.append(detection)

            conn.close()
            return detections

        except Exception as e:
            logger.error(f"Database error: {e}")
            return []

    def publish_detection(self, detection):
        """Publish a detection to MQTT"""
        try:
            # Build message
            msg = {
                "station": STATION_NAME,
                "timestamp": detection.get("Date", "") + " " + detection.get("Time", ""),
                "species": detection.get("Com_Name", "Unknown"),
                "scientific_name": detection.get("Sci_Name", ""),
                "confidence": detection.get("Confidence", 0),
                "file": detection.get("File_Name", ""),
                "latitude": detection.get("Lat", 0),
                "longitude": detection.get("Lon", 0),
            }

            # Publish
            result = self.client.publish(
                TOPIC_DETECTION,
                json.dumps(msg),
                qos=1
            )

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"Published: {msg['species']} ({msg['confidence']:.2f})")
                return True
            else:
                logger.warning(f"Publish failed: {result.rc}")
                return False

        except Exception as e:
            logger.error(f"Publish error: {e}")
            return False

    def publish_stats(self):
        """Publish daily statistics"""
        if not BIRDNET_DB.exists():
            return

        try:
            conn = sqlite3.connect(str(BIRDNET_DB))
            cursor = conn.cursor()

            # Today's stats
            today = datetime.now().strftime("%Y-%m-%d")
            cursor.execute("""
                SELECT COUNT(*) as count,
                       COUNT(DISTINCT Com_Name) as species,
                       AVG(Confidence) as avg_conf
                FROM detections
                WHERE Date = ?
            """, (today,))

            row = cursor.fetchone()

            # Top species today
            cursor.execute("""
                SELECT Com_Name, COUNT(*) as count
                FROM detections
                WHERE Date = ?
                GROUP BY Com_Name
                ORDER BY count DESC
                LIMIT 5
            """, (today,))

            top_species = [{"species": r[0], "count": r[1]} for r in cursor.fetchall()]

            conn.close()

            msg = {
                "station": STATION_NAME,
                "date": today,
                "timestamp": datetime.now().isoformat(),
                "total_detections": row[0] or 0,
                "unique_species": row[1] or 0,
                "avg_confidence": round(row[2] or 0, 3),
                "top_species": top_species
            }

            self.client.publish(
                TOPIC_STATS,
                json.dumps(msg),
                qos=1
            )

            logger.info(f"Published stats: {msg['total_detections']} detections, {msg['unique_species']} species")

        except Exception as e:
            logger.error(f"Stats error: {e}")

    def run(self):
        """Main loop"""
        logger.info(f"Starting BirdNET MQTT Publisher for station: {STATION_NAME}")
        logger.info(f"Database: {BIRDNET_DB}")
        logger.info(f"Last detection ID: {self.last_detection_id}")

        if not self.connect_mqtt():
            logger.error("Could not connect to MQTT broker")
            return

        stats_interval = 300  # Publish stats every 5 minutes
        last_stats_time = 0

        try:
            while True:
                if not self.connected:
                    logger.warning("Reconnecting to MQTT...")
                    self.connect_mqtt()
                    time.sleep(5)
                    continue

                # Check for new detections
                detections = self.get_new_detections()

                for detection in detections:
                    if self.publish_detection(detection):
                        # Update last ID after successful publish
                        rowid = detection.get('rowid', self.last_detection_id)
                        if rowid > self.last_detection_id:
                            self.last_detection_id = rowid
                            self.save_last_id()

                # Publish stats periodically
                now = time.time()
                if now - last_stats_time > stats_interval:
                    self.publish_stats()
                    last_stats_time = now

                time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            if self.client:
                self.client.loop_stop()
                self.client.disconnect()


if __name__ == "__main__":
    publisher = BirdNetMQTTPublisher()
    publisher.run()
