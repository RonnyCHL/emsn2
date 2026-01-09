#!/usr/bin/env python3
"""
Update Homer dashboard met actuele EMSN statistieken.

Dit script haalt live data uit PostgreSQL en update de Homer config.yml
met actuele aantallen detecties, soorten, etc.

Draait via systemd timer elke 15 minuten.
"""

import sys
from pathlib import Path

# Voeg scripts directory toe aan path voor imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import yaml
import psycopg2
from datetime import date
import logging
from scripts.core.config import get_postgres_config

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuratie
HOMER_CONFIG = Path("/mnt/nas-docker/homer/assets/config.yml")


def get_stats() -> dict:
    """Haal actuele statistieken uit PostgreSQL."""
    stats = {}

    try:
        pg_config = get_postgres_config()
        conn = psycopg2.connect(**pg_config)
        cur = conn.cursor()

        # Totaal aantal detecties
        cur.execute("SELECT COUNT(*) FROM bird_detections WHERE NOT deleted")
        stats['total_detections'] = cur.fetchone()[0]

        # Aantal unieke soorten
        cur.execute("SELECT COUNT(DISTINCT common_name) FROM bird_detections WHERE NOT deleted")
        stats['unique_species'] = cur.fetchone()[0]

        # Detecties vandaag
        cur.execute("""
            SELECT COUNT(*) FROM bird_detections
            WHERE date = CURRENT_DATE AND NOT deleted
        """)
        stats['today_detections'] = cur.fetchone()[0]

        # Top soort vandaag
        cur.execute("""
            SELECT common_name, COUNT(*) as cnt
            FROM bird_detections
            WHERE date = CURRENT_DATE AND NOT deleted
            GROUP BY common_name
            ORDER BY cnt DESC
            LIMIT 1
        """)
        result = cur.fetchone()
        stats['top_species'] = result[0] if result else "Geen"
        stats['top_count'] = result[1] if result else 0

        # Database grootte (schatting gebaseerd op detecties)
        cur.execute("""
            SELECT pg_size_pretty(pg_database_size('emsn'))
        """)
        stats['db_size'] = cur.fetchone()[0]

        # Check station status (laatste health check < 10 min geleden)
        cur.execute("""
            SELECT station,
                   measurement_timestamp > NOW() - INTERVAL '10 minutes' as online
            FROM system_health
            WHERE station IN ('zolder', 'berging')
            AND measurement_timestamp = (
                SELECT MAX(measurement_timestamp)
                FROM system_health sh2
                WHERE sh2.station = system_health.station
            )
        """)
        station_status = {row[0]: row[1] for row in cur.fetchall()}
        stats['zolder_online'] = station_status.get('zolder', False)
        stats['berging_online'] = station_status.get('berging', False)

        cur.close()
        conn.close()

    except Exception as e:
        logger.error(f"Database error: {e}")
        return None

    return stats


def format_number(n: int) -> str:
    """Format grote getallen leesbaar."""
    if n >= 1000:
        return f"{n // 1000}k+"
    return str(n)


def update_homer_config(stats: dict) -> bool:
    """Update Homer config.yml met nieuwe statistieken."""

    if not HOMER_CONFIG.exists():
        logger.error(f"Homer config niet gevonden: {HOMER_CONFIG}")
        return False

    try:
        # Lees huidige config
        with open(HOMER_CONFIG, 'r') as f:
            config = yaml.safe_load(f)

        # Bepaal status tekst
        if stats['zolder_online'] and stats['berging_online']:
            status_title = "Beide Stations Actief"
            status_style = "is-success"
        elif stats['zolder_online'] or stats['berging_online']:
            online = "Zolder" if stats['zolder_online'] else "Berging"
            status_title = f"Alleen {online} Actief"
            status_style = "is-warning"
        else:
            status_title = "Stations Offline"
            status_style = "is-danger"

        # Bouw message content
        content_parts = [
            f"{format_number(stats['total_detections'])} opnames",
            f"{stats['unique_species']} soorten",
            f"{stats['db_size']}",
            f"Vandaag: {stats['today_detections']}",
            f"Top: {stats['top_species']}"
        ]
        content = " | ".join(content_parts)

        # Update config
        config['message'] = {
            'style': status_style,
            'title': status_title,
            'icon': 'fas fa-dove',
            'content': content
        }

        # Schrijf terug
        with open(HOMER_CONFIG, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

        logger.info(f"Homer config updated: {content}")
        return True

    except Exception as e:
        logger.error(f"Config update error: {e}")
        return False


def main():
    """Main entry point."""
    logger.info("Starting Homer stats update...")

    stats = get_stats()
    if stats is None:
        logger.error("Failed to get stats")
        return 1

    logger.info(f"Stats: {stats['total_detections']} detecties, {stats['unique_species']} soorten, {stats['today_detections']} vandaag")

    if update_homer_config(stats):
        logger.info("Homer config successfully updated")
        return 0
    else:
        logger.error("Failed to update Homer config")
        return 1


if __name__ == "__main__":
    exit(main())
