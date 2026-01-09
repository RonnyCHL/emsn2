#!/usr/bin/env python3
"""
EMSN 2.0 - NAS Metrics Collector

Haalt systeem metrics op van de Synology NAS via SSH en slaat ze op in PostgreSQL.
Draait via systemd timer.

Features:
- Credentials uit core.config (geen hardcoded passwords)
- MQTT status publishing
- Structured logging
- Type hints
- Proper error handling

Exit codes:
  0 = Success
  1 = Error (geen metrics opgehaald)
  2 = Database error
"""

import json
import logging
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import psycopg2

# Voeg project root toe voor imports
sys.path.insert(0, str(Path(__file__).parent))

from core.config import get_postgres_config, get_nas_config, get_mqtt_config

# MQTT configuratie
MQTT_TOPIC = "emsn2/nas/metrics"

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MQTTPublisher:
    """MQTT publisher voor NAS metrics."""

    def __init__(self) -> None:
        self.client: Any = None
        self.connected: bool = False

    def connect(self) -> bool:
        """Maak verbinding met MQTT broker."""
        try:
            import paho.mqtt.client as mqtt
            config = get_mqtt_config()

            self.client = mqtt.Client(client_id=f"nas-metrics-{datetime.now().timestamp():.0f}")
            if config.get('username') and config.get('password'):
                self.client.username_pw_set(config['username'], config['password'])

            self.client.connect(config['broker'], config['port'], keepalive=60)
            self.client.loop_start()
            self.connected = True
            return True

        except ImportError:
            logger.debug("paho-mqtt niet geïnstalleerd, MQTT uitgeschakeld")
            return False
        except Exception as e:
            logger.warning(f"MQTT connectie mislukt: {e}")
            return False

    def publish(self, metrics: dict[str, Any]) -> None:
        """Publish metrics naar MQTT."""
        if not self.connected or not self.client:
            return

        try:
            payload = {
                "timestamp": datetime.now().isoformat(),
                **{k: v for k, v in metrics.items() if k != 'timestamp'}
            }
            self.client.publish(MQTT_TOPIC, json.dumps(payload), retain=True, qos=1)
        except Exception as e:
            logger.warning(f"MQTT publish mislukt: {e}")

    def disconnect(self) -> None:
        """Sluit MQTT verbinding."""
        if self.client and self.connected:
            try:
                self.client.loop_stop()
                self.client.disconnect()
            except Exception:
                pass


def run_ssh_command(command: str) -> Optional[str]:
    """Voer een SSH commando uit op de NAS."""
    nas_config = get_nas_config()

    full_cmd = [
        "sshpass", "-p", nas_config['password'],
        "ssh", "-o", "StrictHostKeyChecking=no",
        f"{nas_config['user']}@{nas_config['host']}",
        command
    ]

    try:
        result = subprocess.run(full_cmd, capture_output=True, text=True, timeout=10)
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        logger.warning(f"SSH command timeout: {command}")
        return None
    except FileNotFoundError:
        logger.error("sshpass niet geïnstalleerd. Installeer met: sudo apt install sshpass")
        return None
    except Exception as e:
        logger.error(f"SSH error: {e}")
        return None


def parse_loadavg(output: Optional[str]) -> tuple[Optional[float], Optional[float], Optional[float]]:
    """Parse /proc/loadavg output."""
    if not output:
        return None, None, None

    parts = output.split()
    if len(parts) >= 3:
        try:
            return float(parts[0]), float(parts[1]), float(parts[2])
        except ValueError:
            return None, None, None

    return None, None, None


def parse_size_to_gb(size_str: str) -> Optional[float]:
    """Converteer size string (bijv. '17Gi', '4.3Gi', '96G') naar GB."""
    if not size_str:
        return None

    # Verwijder trailing 'i' als aanwezig (GiB vs GB)
    size_str = size_str.rstrip('i')

    match = re.match(r'([\d.]+)([KMGTP]?)', size_str)
    if not match:
        return None

    try:
        value = float(match.group(1))
        unit = match.group(2)

        multipliers = {'K': 1/1024/1024, 'M': 1/1024, 'G': 1, 'T': 1024, 'P': 1024*1024}
        return value * multipliers.get(unit, 1)
    except ValueError:
        return None


def parse_memory(output: Optional[str]) -> dict[str, Optional[float]]:
    """Parse free -h output."""
    if not output:
        return {}

    result: dict[str, Optional[float]] = {}
    lines = output.strip().split('\n')

    for line in lines:
        if line.startswith('Mem:'):
            parts = line.split()
            # Converteer naar GB
            result['mem_total_gb'] = parse_size_to_gb(parts[1])
            result['mem_used_gb'] = parse_size_to_gb(parts[2])
            result['mem_available_gb'] = parse_size_to_gb(parts[6]) if len(parts) > 6 else None

            if result['mem_total_gb'] and result['mem_used_gb']:
                result['mem_used_pct'] = (result['mem_used_gb'] / result['mem_total_gb']) * 100

        elif line.startswith('Swap:'):
            parts = line.split()
            result['swap_total_gb'] = parse_size_to_gb(parts[1])
            result['swap_used_gb'] = parse_size_to_gb(parts[2])

    return result


def parse_disk(output: Optional[str]) -> dict[str, Optional[float]]:
    """Parse df -h output."""
    if not output:
        return {}

    result: dict[str, Optional[float]] = {}
    lines = output.strip().split('\n')

    for line in lines:
        if '/volume1' in line:
            parts = line.split()
            if len(parts) >= 5:
                total_gb = parse_size_to_gb(parts[1])
                avail_gb = parse_size_to_gb(parts[3])

                result['disk_total_tb'] = total_gb / 1024 if total_gb else None
                result['disk_used_gb'] = parse_size_to_gb(parts[2])
                result['disk_available_tb'] = avail_gb / 1024 if avail_gb else None

                try:
                    result['disk_used_pct'] = float(parts[4].rstrip('%'))
                except ValueError:
                    result['disk_used_pct'] = None
            break

    return result


def collect_nas_metrics() -> dict[str, Any]:
    """Verzamel alle NAS metrics."""
    metrics: dict[str, Any] = {'timestamp': datetime.now()}

    # CPU Load
    loadavg = run_ssh_command("cat /proc/loadavg")
    load1, load5, load15 = parse_loadavg(loadavg)
    metrics['cpu_load_1min'] = load1
    metrics['cpu_load_5min'] = load5
    metrics['cpu_load_15min'] = load15

    # Memory
    memory = run_ssh_command("free -h")
    metrics.update(parse_memory(memory))

    # Disk
    disk = run_ssh_command("df -h /volume1")
    metrics.update(parse_disk(disk))

    return metrics


def save_to_database(metrics: dict[str, Any]) -> bool:
    """Sla metrics op in PostgreSQL."""
    try:
        pg_config = get_postgres_config()
        conn = psycopg2.connect(**pg_config)
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO nas_metrics (
                timestamp, cpu_load_1min, cpu_load_5min, cpu_load_15min,
                mem_total_gb, mem_used_gb, mem_available_gb, mem_used_pct,
                swap_total_gb, swap_used_gb,
                disk_total_tb, disk_used_gb, disk_available_tb, disk_used_pct
            ) VALUES (
                %(timestamp)s, %(cpu_load_1min)s, %(cpu_load_5min)s, %(cpu_load_15min)s,
                %(mem_total_gb)s, %(mem_used_gb)s, %(mem_available_gb)s, %(mem_used_pct)s,
                %(swap_total_gb)s, %(swap_used_gb)s,
                %(disk_total_tb)s, %(disk_used_gb)s, %(disk_available_tb)s, %(disk_used_pct)s
            )
        """, metrics)

        conn.commit()
        cur.close()
        conn.close()

        logger.info(
            f"NAS metrics opgeslagen - Load: {metrics.get('cpu_load_1min', 'N/A')}, "
            f"Mem: {metrics.get('mem_used_pct', 0):.1f}%, "
            f"Disk: {metrics.get('disk_used_pct', 0):.1f}%"
        )
        return True

    except psycopg2.Error as e:
        logger.error(f"Database error: {e}")
        return False


def cleanup_old_metrics(days: int = 7) -> int:
    """Verwijder metrics ouder dan X dagen. Returns aantal verwijderde records."""
    try:
        pg_config = get_postgres_config()
        conn = psycopg2.connect(**pg_config)
        cur = conn.cursor()

        cur.execute("""
            DELETE FROM nas_metrics
            WHERE timestamp < NOW() - INTERVAL '%s days'
        """, (days,))

        deleted = cur.rowcount
        conn.commit()
        cur.close()
        conn.close()

        if deleted > 0:
            logger.info(f"Opgeruimd: {deleted} oude metrics verwijderd")

        return deleted

    except psycopg2.Error as e:
        logger.error(f"Cleanup error: {e}")
        return 0


def main() -> int:
    """Hoofdfunctie."""
    mqtt = MQTTPublisher()

    logger.info("NAS Metrics Collector gestart")

    try:
        # MQTT verbinding (optioneel)
        mqtt.connect()

        # Verzamel metrics
        metrics = collect_nas_metrics()

        if metrics.get('cpu_load_1min') is None:
            logger.error("Kon geen metrics ophalen van NAS")
            return 1

        # Publish naar MQTT
        mqtt.publish(metrics)

        # Sla op in database
        if not save_to_database(metrics):
            return 2

        # Opruimen van oude data
        cleanup_old_metrics(days=7)

        return 0

    except Exception as e:
        logger.exception(f"Onverwachte error: {e}")
        return 1

    finally:
        mqtt.disconnect()


if __name__ == "__main__":
    sys.exit(main())
