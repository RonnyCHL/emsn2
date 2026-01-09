#!/usr/bin/env python3
"""
EMSN 2.0 - Homer Dashboard Stats Updater

Update de message banner in Homer met live statistieken uit de database.
Draait via systemd timer (bijv. elke 15 minuten).

Features:
- Haalt stats uit PostgreSQL via core.config (geen hardcoded credentials)
- MQTT status publishing
- Structured logging
- Type hints

Exit codes:
  0 = Success
  1 = Error
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import psycopg2
import yaml

# Voeg project root toe voor imports
sys.path.insert(0, str(Path(__file__).parent))

from core.config import get_postgres_config, get_mqtt_config

# Config
HOMER_CONFIG = Path("/mnt/nas-docker/homer/config.yml")
MQTT_TOPIC = "emsn2/homer/stats"

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MQTTPublisher:
    """MQTT publisher voor Homer stats."""

    def __init__(self) -> None:
        self.client: Any = None
        self.connected: bool = False

    def connect(self) -> bool:
        """Maak verbinding met MQTT broker."""
        try:
            import paho.mqtt.client as mqtt
            config = get_mqtt_config()

            self.client = mqtt.Client(client_id=f"homer-stats-{datetime.now().timestamp():.0f}")
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

    def publish(self, stats: dict) -> None:
        """Publish stats naar MQTT."""
        if not self.connected or not self.client:
            return

        try:
            payload = {
                "timestamp": datetime.now().isoformat(),
                **stats
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


def get_stats() -> dict[str, Any]:
    """Haal live statistieken uit de database."""
    pg_config = get_postgres_config()

    conn = psycopg2.connect(**pg_config)
    cur = conn.cursor()

    stats: dict[str, Any] = {}

    try:
        # Archief totalen
        cur.execute("""
            SELECT
                COUNT(*) as total,
                COUNT(DISTINCT species) as species,
                ROUND(SUM(file_size_bytes)::numeric / 1073741824, 1) as gb
            FROM media_archive
        """)
        row = cur.fetchone()
        stats['archive_total'] = row[0] if row else 0
        stats['archive_species'] = row[1] if row else 0
        stats['archive_gb'] = row[2] if row else 0

        # Vandaag detecties
        cur.execute("""
            SELECT COUNT(*) FROM bird_detections
            WHERE detection_timestamp >= CURRENT_DATE
        """)
        result = cur.fetchone()
        stats['today_detections'] = result[0] if result else 0

        # Top soort vandaag
        cur.execute("""
            SELECT species, COUNT(*) as cnt
            FROM bird_detections
            WHERE detection_timestamp >= CURRENT_DATE
            GROUP BY species
            ORDER BY cnt DESC
            LIMIT 1
        """)
        row = cur.fetchone()
        if row:
            stats['top_species'] = row[0]
            stats['top_count'] = row[1]
        else:
            stats['top_species'] = None
            stats['top_count'] = 0

        # Stations online check (laatste 15 min detecties)
        cur.execute("""
            SELECT station, COUNT(*)
            FROM bird_detections
            WHERE detection_timestamp >= NOW() - INTERVAL '15 minutes'
            GROUP BY station
        """)
        stations_active = cur.fetchall()
        stats['stations_online'] = len(stations_active)

    finally:
        cur.close()
        conn.close()

    return stats


def format_number(n: int | float) -> str:
    """Format grote nummers met k/M suffix."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    elif n >= 1_000:
        return f"{n / 1_000:.0f}k"
    return str(int(n))


def update_homer_config(stats: dict[str, Any]) -> bool:
    """Update de Homer config met nieuwe stats."""
    if not HOMER_CONFIG.exists():
        logger.error(f"Homer config niet gevonden: {HOMER_CONFIG}")
        return False

    try:
        # Lees huidige config
        with open(HOMER_CONFIG, 'r') as f:
            config = yaml.safe_load(f)

        # Bepaal message style en content
        if stats['stations_online'] == 0:
            style = "is-danger"
            title = "Geen Stations Online"
            icon = "fas fa-exclamation-triangle"
        elif stats['stations_online'] == 1:
            style = "is-warning"
            title = "1 Station Online"
            icon = "fas fa-dove"
        else:
            style = "is-success"
            title = "Systeem Actief"
            icon = "fas fa-dove"

        # Build content string
        content_parts = [
            f"{format_number(stats['archive_total'])}+ opnames",
            f"{stats['archive_species']} soorten",
            f"{stats['archive_gb']} GB"
        ]

        if stats['today_detections'] > 0:
            content_parts.append(f"Vandaag: {stats['today_detections']}")

        if stats['top_species']:
            # Korte naam voor top soort
            short_name = stats['top_species'].split()[0] if ' ' in stats['top_species'] else stats['top_species']
            content_parts.append(f"Top: {short_name}")

        content = " | ".join(content_parts)

        # Update message
        config['message'] = {
            'style': style,
            'title': title,
            'icon': icon,
            'content': content
        }

        # Schrijf config terug
        with open(HOMER_CONFIG, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

        logger.info(f"Homer updated: {content}")
        return True

    except yaml.YAMLError as e:
        logger.error(f"YAML parse error: {e}")
        return False
    except PermissionError as e:
        logger.error(f"Geen schrijfrechten op Homer config: {e}")
        return False
    except Exception as e:
        logger.error(f"Onverwachte fout bij Homer update: {e}")
        return False


def main() -> int:
    """Hoofdfunctie."""
    mqtt = MQTTPublisher()

    try:
        logger.info("Homer stats update gestart")

        # MQTT verbinding (optioneel)
        mqtt.connect()

        # Haal stats
        stats = get_stats()
        logger.info(f"Stats: archive={stats['archive_total']}, today={stats['today_detections']}, stations={stats['stations_online']}")

        # Publish naar MQTT
        mqtt.publish(stats)

        # Update Homer
        if update_homer_config(stats):
            logger.info("Homer config succesvol bijgewerkt")
            return 0
        else:
            logger.error("Homer config update mislukt")
            return 1

    except psycopg2.Error as e:
        logger.error(f"Database error: {e}")
        return 1
    except Exception as e:
        logger.exception(f"Onverwachte error: {e}")
        return 1
    finally:
        mqtt.disconnect()


if __name__ == "__main__":
    sys.exit(main())
