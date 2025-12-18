#!/usr/bin/env python3
"""
EMSN MQTT Bridge Monitor v2.0
Monitors bridge status, sends alerts on disconnection, and logs events to PostgreSQL
"""

import os
import json
import time
import logging
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
import paho.mqtt.client as mqtt
import yaml
import psycopg2
from psycopg2.extras import RealDictCursor

# Configuration
MQTT_BROKER = "192.168.1.178"
MQTT_PORT = 1883
MQTT_USER = "ecomonitor"
MQTT_PASS = "REDACTED_DB_PASS"

# Database configuration
DB_CONFIG = {
    'host': '192.168.1.25',
    'port': 5433,
    'database': 'emsn',
    'user': 'birdpi_zolder',
    'password': os.getenv('EMSN_DB_PASSWORD', 'REDACTED_DB_PASS')
}

# Topics to monitor
BRIDGE_TOPICS = [
    "emsn2/bridge/status",        # Berging -> Zolder bridge status
    "emsn2/bridge/zolder-status", # Zolder -> Berging bridge status
]

# Email config
CONFIG_PATH = Path("/home/ronny/emsn2/config")
EMAIL_FILE = CONFIG_PATH / "email.yaml"
SMTP_PASSWORD = os.getenv("EMSN_SMTP_PASSWORD")

# State tracking
LOG_DIR = Path("/mnt/usb/logs")
STATE_FILE = LOG_DIR / "bridge_monitor_state.json"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "bridge_monitor.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class BridgeMonitor:
    def __init__(self):
        self.bridge_status = {
            "berging-to-zolder": {"connected": False, "last_seen": None, "connected_since": None},
            "zolder-to-berging": {"connected": False, "last_seen": None, "connected_since": None},
        }
        self.last_alert_time = {}
        self.alert_cooldown = timedelta(hours=1)  # Don't spam alerts
        self.db_conn = None
        self.load_state()
        self.connect_db()

    def connect_db(self):
        """Connect to PostgreSQL database"""
        try:
            self.db_conn = psycopg2.connect(**DB_CONFIG)
            self.db_conn.autocommit = True
            logger.info("Connected to PostgreSQL database")
        except Exception as e:
            logger.warning(f"Could not connect to database: {e}")
            self.db_conn = None

    def ensure_db_connection(self):
        """Ensure database connection is alive"""
        if self.db_conn is None:
            self.connect_db()
            return
        try:
            with self.db_conn.cursor() as cur:
                cur.execute("SELECT 1")
        except Exception:
            logger.warning("Database connection lost, reconnecting...")
            self.connect_db()

    def log_bridge_event(self, bridge_name, event_type, message=None, duration_seconds=None):
        """Log bridge event to PostgreSQL"""
        self.ensure_db_connection()
        if not self.db_conn:
            return

        try:
            with self.db_conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO mqtt_bridge_events
                    (bridge_name, event_type, source, message, duration_seconds)
                    VALUES (%s, %s, %s, %s, %s)
                """, (bridge_name, event_type, 'monitor', message, duration_seconds))
            logger.info(f"Logged bridge event: {bridge_name} -> {event_type}")
        except Exception as e:
            logger.error(f"Failed to log bridge event: {e}")

    def load_state(self):
        """Load previous state from file"""
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE) as f:
                    data = json.load(f)
                    self.last_alert_time = {
                        k: datetime.fromisoformat(v)
                        for k, v in data.get("last_alert_time", {}).items()
                    }
                logger.info("Loaded previous state")
            except Exception as e:
                logger.warning(f"Could not load state: {e}")

    def save_state(self):
        """Save state to file"""
        try:
            data = {
                "last_alert_time": {
                    k: v.isoformat()
                    for k, v in self.last_alert_time.items()
                },
                "bridge_status": {
                    k: {
                        "connected": v["connected"],
                        "last_seen": v["last_seen"].isoformat() if v["last_seen"] else None
                    }
                    for k, v in self.bridge_status.items()
                }
            }
            with open(STATE_FILE, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save state: {e}")

    def load_email_config(self):
        """Load email configuration"""
        if not EMAIL_FILE.exists():
            return None
        with open(EMAIL_FILE) as f:
            return yaml.safe_load(f)

    def send_alert(self, subject, body):
        """Send email alert"""
        config = self.load_email_config()
        if not config or not SMTP_PASSWORD:
            logger.warning("Email not configured, skipping alert")
            return False

        smtp_config = config.get('smtp', {})
        email_config = config.get('email', {})
        recipients = config.get('recipients', [])

        if not recipients:
            return False

        try:
            msg = MIMEMultipart()
            msg['Subject'] = f"[EMSN Alert] {subject}"
            msg['From'] = f"{email_config.get('from_name')} <{email_config.get('from_address')}>"
            msg['To'] = ', '.join(recipients)

            msg.attach(MIMEText(body, 'plain', 'utf-8'))

            server = smtplib.SMTP(smtp_config.get('host'), smtp_config.get('port', 587))
            if smtp_config.get('use_tls', True):
                server.starttls()
            server.login(smtp_config.get('username'), SMTP_PASSWORD)
            server.sendmail(email_config.get('from_address'), recipients, msg.as_string())
            server.quit()

            logger.info(f"Alert sent: {subject}")
            return True
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
            return False

    def should_alert(self, bridge_name):
        """Check if we should send an alert (cooldown)"""
        last = self.last_alert_time.get(bridge_name)
        if not last:
            return True
        return datetime.now() - last > self.alert_cooldown

    def on_connect(self, client, userdata, flags, rc, properties=None):
        """MQTT connection callback"""
        if rc == 0:
            logger.info("Connected to MQTT broker")
            for topic in BRIDGE_TOPICS:
                client.subscribe(topic)
                logger.info(f"Subscribed to {topic}")
        else:
            logger.error(f"Connection failed with code {rc}")

    def on_message(self, client, userdata, msg):
        """MQTT message callback"""
        try:
            topic = msg.topic
            payload = msg.payload.decode()

            logger.info(f"Bridge status: {topic} = {payload}")

            # Parse bridge status (Mosquitto sends 0/1 for disconnect/connect)
            if "bridge/status" in topic:
                bridge_name = "berging-to-zolder"
            elif "bridge/zolder-status" in topic:
                bridge_name = "zolder-to-berging"
            else:
                return

            connected = payload == "1"
            was_connected = self.bridge_status[bridge_name]["connected"]
            now = datetime.now()

            # State changed - log event
            if connected != was_connected:
                if connected:
                    # Just connected
                    self.bridge_status[bridge_name]["connected_since"] = now
                    self.log_bridge_event(bridge_name, 'connected',
                                          f"Bridge {bridge_name} connected")
                else:
                    # Just disconnected - calculate how long it was connected
                    connected_since = self.bridge_status[bridge_name].get("connected_since")
                    duration = None
                    if connected_since:
                        duration = int((now - connected_since).total_seconds())
                    self.log_bridge_event(bridge_name, 'disconnected',
                                          f"Bridge {bridge_name} disconnected",
                                          duration_seconds=duration)
                    self.bridge_status[bridge_name]["connected_since"] = None

            self.bridge_status[bridge_name]["connected"] = connected
            self.bridge_status[bridge_name]["last_seen"] = now

            if not connected and self.should_alert(bridge_name):
                self.send_alert(
                    f"MQTT Bridge Disconnected: {bridge_name}",
                    f"De MQTT bridge {bridge_name} is losgekoppeld.\n\n"
                    f"Tijdstip: {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"Topic: {topic}\n\n"
                    f"Controleer de Mosquitto service op beide Pi's."
                )
                self.last_alert_time[bridge_name] = now

            self.save_state()

        except Exception as e:
            logger.error(f"Error processing message: {e}")

    def run(self):
        """Main monitoring loop"""
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        client.username_pw_set(MQTT_USER, MQTT_PASS)
        client.on_connect = self.on_connect
        client.on_message = self.on_message

        # Log startup event
        self.log_bridge_event('monitor', 'startup', 'Bridge monitor service started')

        try:
            client.connect(MQTT_BROKER, MQTT_PORT, 60)
            logger.info("Starting bridge monitor...")
            client.loop_forever()
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        except Exception as e:
            logger.error(f"Error: {e}")
        finally:
            self.log_bridge_event('monitor', 'shutdown', 'Bridge monitor service stopped')
            if self.db_conn:
                self.db_conn.close()
            client.disconnect()


def check_once():
    """One-time check of bridge status (for timer-based monitoring)"""
    import subprocess

    logger.info("Performing one-time bridge status check")

    # Check Zolder mosquitto log for bridge status
    try:
        result = subprocess.run(
            ["sudo", "grep", "-E", "bridge.*(connected|disconnected)",
             "/var/log/mosquitto/mosquitto.log"],
            capture_output=True, text=True, timeout=10
        )

        lines = result.stdout.strip().split('\n')[-5:]  # Last 5 bridge events

        if lines and lines[0]:
            logger.info("Recent bridge events:")
            for line in lines:
                logger.info(f"  {line}")
        else:
            logger.info("No recent bridge events in log")

    except Exception as e:
        logger.error(f"Could not check logs: {e}")

    # Check if bridges are currently connected
    try:
        result = subprocess.run(
            ["mosquitto_sub", "-h", "localhost", "-u", MQTT_USER, "-P", MQTT_PASS,
             "-t", "emsn2/bridge/#", "-W", "2", "-v"],
            capture_output=True, text=True, timeout=5
        )
        if result.stdout:
            logger.info(f"Bridge topics: {result.stdout.strip()}")
    except:
        pass


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        check_once()
    else:
        monitor = BridgeMonitor()
        monitor.run()
