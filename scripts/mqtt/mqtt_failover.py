#!/usr/bin/env python3
"""
EMSN MQTT Failover Monitor
Checks bridge health and takes corrective action if needed
Run via timer every 5 minutes

Refactored: 2025-12-29 - Gebruikt nu core modules voor config
Modernized: 2026-01-09 - Type hints, proper exception handling
"""

import os
import sys
import json
import subprocess
import smtplib
from datetime import datetime, timedelta
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any, List
import yaml

# Add project root to path for core modules
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / 'config'))

# Import EMSN core modules
from scripts.core.config import get_mqtt_config, get_smtp_config
from scripts.core.network import HOSTS
from scripts.core.logging import get_logger

# Get config from core
_mqtt = get_mqtt_config()
_smtp = get_smtp_config()

# Configuration
LOG_DIR = Path("/mnt/usb/logs")
STATE_FILE = LOG_DIR / "mqtt_failover_state.json"
CONFIG_PATH = PROJECT_ROOT / "config"
EMAIL_FILE = CONFIG_PATH / "email.yaml"

# Credentials uit core.config (fallback naar env var)
SMTP_PASSWORD = _smtp.get('password') or os.getenv("EMSN_SMTP_PASSWORD")
MQTT_USER = _mqtt.get('username')
MQTT_PASS = _mqtt.get('password')

# Centrale logger
logger = get_logger('mqtt_failover')


class MQTTFailover:
    """MQTT failover monitor met automatische recovery."""

    def __init__(self) -> None:
        self.state: Dict[str, Any] = self.load_state()

    def load_state(self) -> Dict[str, Any]:
        """Load previous state from JSON file."""
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE) as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError, OSError) as e:
                logger.warning(f"Could not load state file: {e}")
        return {
            "last_check": None,
            "consecutive_failures": 0,
            "last_restart": None,
            "last_alert": None,
        }

    def save_state(self) -> None:
        """Save state to JSON file."""
        self.state["last_check"] = datetime.now().isoformat()
        with open(STATE_FILE, 'w') as f:
            json.dump(self.state, f, indent=2)

    def load_email_config(self) -> Optional[Dict[str, Any]]:
        """Load email configuration from YAML file."""
        if not EMAIL_FILE.exists():
            return None
        with open(EMAIL_FILE) as f:
            return yaml.safe_load(f)

    def send_alert(self, subject: str, body: str) -> bool:
        """Send email alert via SMTP."""
        config = self.load_email_config()
        if not config or not SMTP_PASSWORD:
            logger.warning("Email not configured")
            return False

        smtp_config = config.get('smtp', {})
        email_config = config.get('email', {})
        recipients: List[str] = config.get('recipients', [])

        if not recipients:
            return False

        try:
            msg = MIMEMultipart()
            msg['Subject'] = f"[EMSN MQTT] {subject}"
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
        except (smtplib.SMTPException, ConnectionError, OSError) as e:
            logger.error(f"Failed to send alert: {e}")
            return False

    def check_mosquitto_status(self, host: str = "localhost") -> bool:
        """Check if Mosquitto is running on specified host."""
        try:
            if host == "localhost":
                result = subprocess.run(
                    ["systemctl", "is-active", "mosquitto"],
                    capture_output=True, text=True, timeout=5
                )
                return result.stdout.strip() == "active"
            else:
                # Remote check via SSH
                result = subprocess.run(
                    ["ssh", "-o", "ConnectTimeout=5", f"ronny@{host}",
                     "systemctl", "is-active", "mosquitto"],
                    capture_output=True, text=True, timeout=10
                )
                return result.stdout.strip() == "active"
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError) as e:
            logger.error(f"Could not check Mosquitto status on {host}: {e}")
            return False

    def check_bridge_connected(self) -> Dict[str, Optional[bool]]:
        """Check if bridges are connected via MQTT notification topics."""
        bridges = {
            "berging-to-zolder": None,  # None = unknown, True = connected, False = disconnected
            "zolder-to-berging": None,
        }

        try:
            # Try to get bridge status from MQTT notification topics
            # These are retained messages published by mosquitto when bridge connects/disconnects
            result = subprocess.run(
                ["mosquitto_sub", "-h", "localhost", "-u", MQTT_USER, "-P", MQTT_PASS,
                 "-t", "emsn2/bridge/status", "-t", "emsn2/bridge/zolder-status",
                 "-W", "2", "-v"],
                capture_output=True, text=True, timeout=5
            )

            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                parts = line.split(' ', 1)
                if len(parts) == 2:
                    topic, payload = parts
                    if "bridge/status" in topic and "zolder" not in topic:
                        bridges["berging-to-zolder"] = payload.strip() == "1"
                    elif "bridge/zolder-status" in topic:
                        bridges["zolder-to-berging"] = payload.strip() == "1"

        except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError) as e:
            logger.warning(f"Could not check bridge status via MQTT: {e}")

        # If MQTT check didn't work, fall back to log parsing
        if all(v is None for v in bridges.values()):
            try:
                result = subprocess.run(
                    ["sudo", "grep", "-E", "bridge.*(connected|New bridge)",
                     "/var/log/mosquitto/mosquitto.log"],
                    capture_output=True, text=True, timeout=5
                )

                # Check last few bridge events
                lines = result.stdout.strip().split('\n')[-20:]
                for line in lines:
                    if "New bridge connected" in line or "bridge connected" in line.lower():
                        if "bridge-to-zolder" in line:
                            bridges["berging-to-zolder"] = True
                        if "bridge-to-berging" in line:
                            bridges["zolder-to-berging"] = True

            except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError) as e:
                logger.error(f"Could not check bridge status via logs: {e}")

        return bridges

    def restart_mosquitto(self, host: str = "localhost") -> bool:
        """Restart Mosquitto service on specified host."""
        try:
            if host == "localhost":
                result = subprocess.run(
                    ["sudo", "systemctl", "restart", "mosquitto"],
                    capture_output=True, text=True, timeout=30
                )
            else:
                result = subprocess.run(
                    ["ssh", "-o", "ConnectTimeout=5", f"ronny@{host}",
                     "sudo", "systemctl", "restart", "mosquitto"],
                    capture_output=True, text=True, timeout=30
                )

            success = result.returncode == 0
            if success:
                logger.info(f"Mosquitto restarted on {host}")
                self.state["last_restart"] = datetime.now().isoformat()
            else:
                logger.error(f"Failed to restart Mosquitto on {host}: {result.stderr}")

            return success

        except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError) as e:
            logger.error(f"Could not restart Mosquitto on {host}: {e}")
            return False

    def should_alert(self) -> bool:
        """Check if we should send an alert (1 hour cooldown)."""
        if not self.state.get("last_alert"):
            return True
        last = datetime.fromisoformat(self.state["last_alert"])
        return datetime.now() - last > timedelta(hours=1)

    def run(self) -> bool:
        """Main check routine. Returns True if all checks pass."""
        logger.info("Starting MQTT failover check")

        issues: List[str] = []
        actions: List[str] = []

        # Check Zolder Mosquitto
        zolder_ok = self.check_mosquitto_status("localhost")
        logger.info(f"Zolder Mosquitto: {'OK' if zolder_ok else 'DOWN'}")
        if not zolder_ok:
            issues.append("Zolder Mosquitto is down")

        # Check Berging Mosquitto
        berging_ok = self.check_mosquitto_status(HOSTS['berging'])
        logger.info(f"Berging Mosquitto: {'OK' if berging_ok else 'DOWN'}")
        if not berging_ok:
            issues.append("Berging Mosquitto is down")

        # Check bridge connections
        bridges = self.check_bridge_connected()
        if bridges:
            for name, connected in bridges.items():
                status_str = "connected" if connected else ("disconnected" if connected is False else "unknown")
                logger.info(f"Bridge {name}: {status_str}")
                # Only report as issue if explicitly False (disconnected), not None (unknown)
                if connected is False:
                    issues.append(f"Bridge {name} is disconnected")

        # Take action if there are issues
        if issues:
            self.state["consecutive_failures"] = self.state.get("consecutive_failures", 0) + 1
            logger.warning(f"Issues found ({self.state['consecutive_failures']} consecutive): {issues}")

            # After 3 consecutive failures, try to restart
            if self.state["consecutive_failures"] >= 3:
                logger.info("Attempting automatic recovery...")

                # Check when last restart was
                last_restart = self.state.get("last_restart")
                can_restart = True
                if last_restart:
                    last = datetime.fromisoformat(last_restart)
                    can_restart = datetime.now() - last > timedelta(minutes=15)

                if can_restart:
                    if not zolder_ok:
                        if self.restart_mosquitto("localhost"):
                            actions.append("Restarted Zolder Mosquitto")

                    if not berging_ok:
                        if self.restart_mosquitto(HOSTS['berging']):
                            actions.append("Restarted Berging Mosquitto")

                    # If only bridges are down, restart both to re-establish
                    if zolder_ok and berging_ok and bridges:
                        if not all(bridges.values()):
                            self.restart_mosquitto("localhost")
                            self.restart_mosquitto(HOSTS['berging'])
                            actions.append("Restarted both Mosquitto services to reconnect bridges")

            # Send alert if needed
            if self.should_alert():
                body = f"""EMSN MQTT Systeem heeft problemen gedetecteerd.

Tijdstip: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Problemen:
{chr(10).join('- ' + i for i in issues)}

Ondernomen acties:
{chr(10).join('- ' + a for a in actions) if actions else '- Geen (wachten op meer data)'}

Opeenvolgende fouten: {self.state['consecutive_failures']}

Controleer de MQTT services handmatig als dit probleem aanhoudt.
"""
                if self.send_alert("MQTT Problemen Gedetecteerd", body):
                    self.state["last_alert"] = datetime.now().isoformat()

        else:
            # All good, reset failure counter
            if self.state.get("consecutive_failures", 0) > 0:
                logger.info("All issues resolved, resetting failure counter")
            self.state["consecutive_failures"] = 0

        self.save_state()
        logger.info("Failover check completed")

        return len(issues) == 0


if __name__ == "__main__":
    failover = MQTTFailover()
    failover.run()
    # Altijd exit 0 - alerts worden via email/MQTT verzonden
    sys.exit(0)
