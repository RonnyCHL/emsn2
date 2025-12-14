#!/usr/bin/env python3
"""
EMSN MQTT Bridge Monitor
Monitors bridge status and sends alerts on disconnection
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

# Configuration
MQTT_BROKER = "192.168.1.178"
MQTT_PORT = 1883
MQTT_USER = "ecomonitor"
MQTT_PASS = "REDACTED_DB_PASS"

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
            "berging-to-zolder": {"connected": False, "last_seen": None},
            "zolder-to-berging": {"connected": False, "last_seen": None},
        }
        self.last_alert_time = {}
        self.alert_cooldown = timedelta(hours=1)  # Don't spam alerts
        self.load_state()

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
            self.bridge_status[bridge_name]["connected"] = connected
            self.bridge_status[bridge_name]["last_seen"] = datetime.now()

            if not connected and self.should_alert(bridge_name):
                self.send_alert(
                    f"MQTT Bridge Disconnected: {bridge_name}",
                    f"De MQTT bridge {bridge_name} is losgekoppeld.\n\n"
                    f"Tijdstip: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"Topic: {topic}\n\n"
                    f"Controleer de Mosquitto service op beide Pi's."
                )
                self.last_alert_time[bridge_name] = datetime.now()

            self.save_state()

        except Exception as e:
            logger.error(f"Error processing message: {e}")

    def run(self):
        """Main monitoring loop"""
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        client.username_pw_set(MQTT_USER, MQTT_PASS)
        client.on_connect = self.on_connect
        client.on_message = self.on_message

        try:
            client.connect(MQTT_BROKER, MQTT_PORT, 60)
            logger.info("Starting bridge monitor...")
            client.loop_forever()
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        except Exception as e:
            logger.error(f"Error: {e}")
        finally:
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
