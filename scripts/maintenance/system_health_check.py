#!/usr/bin/env python3
"""
EMSN System Health Check & Alerting

Controleert systeem gezondheid en stuurt alerts via:
- MQTT (voor Home Assistant)
- Email (voor kritieke issues)

Checks:
- Disk space
- Memory usage
- Failed systemd services
- Database connectivity
- NAS mount status
- MQTT broker status
- Recent errors in logs

Draait via systemd timer (elke 5 minuten)
"""

import os
import sys
import json
import subprocess
import logging
from datetime import datetime
from pathlib import Path

# Add config path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'config'))

try:
    import psutil
    import paho.mqtt.client as mqtt
    from emsn_secrets import get_mqtt_config, get_postgres_config
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)

# Logging
LOG_DIR = Path("/mnt/usb/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "health_check.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Thresholds
DISK_WARNING_PERCENT = 80
DISK_CRITICAL_PERCENT = 90
MEMORY_WARNING_PERCENT = 85
MEMORY_CRITICAL_PERCENT = 95
SWAP_WARNING_PERCENT = 70

# MQTT Topics
MQTT_TOPIC_HEALTH = "emsn2/zolder/health"
MQTT_TOPIC_ALERT = "emsn2/alerts"

# State file voor deduplicatie
STATE_FILE = Path("/mnt/usb/logs/health_check_state.json")


class HealthChecker:
    def __init__(self):
        self.issues = []
        self.warnings = []
        self.mqtt_client = None
        self.previous_state = self.load_state()

    def load_state(self):
        """Laad vorige state voor deduplicatie"""
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE) as f:
                    return json.load(f)
            except:
                pass
        return {"alerts": []}

    def save_state(self):
        """Sla huidige state op"""
        try:
            with open(STATE_FILE, 'w') as f:
                json.dump({
                    "alerts": [i['id'] for i in self.issues],
                    "last_check": datetime.now().isoformat()
                }, f)
        except Exception as e:
            logger.warning(f"Could not save state: {e}")

    def add_issue(self, issue_id, severity, message):
        """Voeg een issue toe (CRITICAL of WARNING)"""
        issue = {
            "id": issue_id,
            "severity": severity,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        if severity == "CRITICAL":
            self.issues.append(issue)
            logger.error(f"CRITICAL: {message}")
        else:
            self.warnings.append(issue)
            logger.warning(f"WARNING: {message}")

    def check_disk_space(self):
        """Check disk space op belangrijke mounts"""
        mounts_to_check = [
            ('/', 'root'),
            ('/mnt/usb', 'usb'),
            ('/mnt/nas-reports', 'nas-reports'),
            ('/mnt/nas-birdnet-archive', 'nas-archive'),
        ]

        for mount_point, name in mounts_to_check:
            try:
                usage = psutil.disk_usage(mount_point)
                percent = usage.percent

                if percent >= DISK_CRITICAL_PERCENT:
                    self.add_issue(
                        f"disk_{name}_critical",
                        "CRITICAL",
                        f"Disk {name} ({mount_point}) is {percent}% vol!"
                    )
                elif percent >= DISK_WARNING_PERCENT:
                    self.add_issue(
                        f"disk_{name}_warning",
                        "WARNING",
                        f"Disk {name} ({mount_point}) is {percent}% vol"
                    )
            except (FileNotFoundError, PermissionError):
                # Mount niet beschikbaar
                if 'nas' in name:
                    self.add_issue(
                        f"mount_{name}_failed",
                        "CRITICAL",
                        f"NAS mount {mount_point} niet beschikbaar!"
                    )

    def check_memory(self):
        """Check memory en swap usage"""
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()

        if mem.percent >= MEMORY_CRITICAL_PERCENT:
            self.add_issue(
                "memory_critical",
                "CRITICAL",
                f"Memory usage is {mem.percent}%!"
            )
        elif mem.percent >= MEMORY_WARNING_PERCENT:
            self.add_issue(
                "memory_warning",
                "WARNING",
                f"Memory usage is {mem.percent}%"
            )

        if swap.percent >= SWAP_WARNING_PERCENT:
            self.add_issue(
                "swap_warning",
                "WARNING",
                f"Swap usage is {swap.percent}%"
            )

    def check_services(self):
        """Check voor gefaalde systemd services"""
        try:
            result = subprocess.run(
                ['systemctl', '--failed', '--no-legend', '--plain'],
                capture_output=True,
                text=True
            )
            failed = [line.split()[0] for line in result.stdout.strip().split('\n') if line]

            # Filter voor EMSN gerelateerde services
            emsn_failed = [s for s in failed if any(
                x in s for x in ['emsn', 'birdnet', 'mqtt', 'ulanzi', 'nestbox']
            )]

            for service in emsn_failed:
                self.add_issue(
                    f"service_{service}",
                    "CRITICAL",
                    f"Service {service} is gefaald!"
                )
        except Exception as e:
            logger.warning(f"Could not check services: {e}")

    def check_database(self):
        """Check database connectivity"""
        try:
            import psycopg2
            config = get_postgres_config()
            conn = psycopg2.connect(
                host=config['host'],
                port=config['port'],
                database=config['database'],
                user=config['user'],
                password=config['password'],
                connect_timeout=5
            )
            conn.close()
        except Exception as e:
            self.add_issue(
                "database_connection",
                "CRITICAL",
                f"Database niet bereikbaar: {e}"
            )

    def check_mqtt_broker(self):
        """Check MQTT broker connectivity"""
        try:
            config = get_mqtt_config()
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
            client.username_pw_set(config['username'], config['password'])
            client.connect(config['broker'], config['port'], 5)
            client.disconnect()
            self.mqtt_client = None  # Reset for later use
        except Exception as e:
            self.add_issue(
                "mqtt_broker",
                "CRITICAL",
                f"MQTT broker niet bereikbaar: {e}"
            )

    def check_recent_errors(self):
        """Check voor recente errors in belangrijke logs"""
        error_logs = [
            '/mnt/usb/logs/birdnet-mqtt-publisher.error.log',
            '/mnt/usb/logs/emsn-reports-api.error.log',
        ]

        for log_path in error_logs:
            try:
                if Path(log_path).exists():
                    # Check laatste 10 regels voor errors
                    result = subprocess.run(
                        ['tail', '-10', log_path],
                        capture_output=True,
                        text=True
                    )
                    if 'ERROR' in result.stdout or 'CRITICAL' in result.stdout:
                        log_name = Path(log_path).stem
                        self.add_issue(
                            f"log_errors_{log_name}",
                            "WARNING",
                            f"Recente errors in {log_name}"
                        )
            except Exception:
                pass

    def publish_status(self):
        """Publiceer health status naar MQTT"""
        try:
            config = get_mqtt_config()
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
            client.username_pw_set(config['username'], config['password'])
            client.connect(config['broker'], config['port'], 60)

            # Health status
            status = {
                "timestamp": datetime.now().isoformat(),
                "status": "critical" if self.issues else ("warning" if self.warnings else "healthy"),
                "issues_count": len(self.issues),
                "warnings_count": len(self.warnings),
                "disk_root_percent": psutil.disk_usage('/').percent,
                "memory_percent": psutil.virtual_memory().percent,
                "swap_percent": psutil.swap_memory().percent,
            }

            client.publish(MQTT_TOPIC_HEALTH, json.dumps(status), qos=1)

            # Publiceer nieuwe alerts
            for issue in self.issues:
                if issue['id'] not in self.previous_state.get('alerts', []):
                    alert_msg = {
                        "type": "alert",
                        "severity": issue['severity'],
                        "message": issue['message'],
                        "timestamp": issue['timestamp']
                    }
                    client.publish(MQTT_TOPIC_ALERT, json.dumps(alert_msg), qos=1)
                    logger.info(f"Published alert: {issue['message']}")

            client.disconnect()

        except Exception as e:
            logger.error(f"Could not publish to MQTT: {e}")

    def run(self):
        """Voer alle checks uit"""
        logger.info("=== Health Check Started ===")

        self.check_disk_space()
        self.check_memory()
        self.check_services()
        self.check_database()
        self.check_mqtt_broker()
        self.check_recent_errors()

        # Publiceer resultaten
        self.publish_status()

        # Sla state op voor deduplicatie
        self.save_state()

        # Summary
        if self.issues:
            logger.error(f"Found {len(self.issues)} CRITICAL issues!")
            for issue in self.issues:
                logger.error(f"  - {issue['message']}")
        if self.warnings:
            logger.warning(f"Found {len(self.warnings)} warnings")
        if not self.issues and not self.warnings:
            logger.info("All checks passed - system healthy")

        logger.info("=== Health Check Completed ===")

        # Altijd 0 teruggeven - alerts worden via MQTT gepubliceerd
        return 0


if __name__ == "__main__":
    checker = HealthChecker()
    checker.run()
    sys.exit(0)
