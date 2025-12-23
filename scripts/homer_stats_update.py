#!/usr/bin/env python3
"""
Homer Dashboard Stats Updater
Update de message banner in Homer met live statistieken uit de database.

Draait via systemd timer (bijv. elke 15 minuten).
"""

import psycopg2
import yaml
from pathlib import Path
from datetime import datetime
import logging

# Config
HOMER_CONFIG = Path("/mnt/nas-docker/homer/config.yml")
DB_CONFIG = {
    "host": "192.168.1.25",
    "port": 5433,
    "database": "emsn",
    "user": "postgres",
    "password": "IwnadBon2iN"
}

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_stats():
    """Haal live statistieken uit de database."""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    stats = {}

    # Archief totalen
    cur.execute("""
        SELECT
            COUNT(*) as total,
            COUNT(DISTINCT species) as species,
            ROUND(SUM(file_size_bytes)::numeric / 1073741824, 1) as gb
        FROM media_archive
    """)
    row = cur.fetchone()
    stats['archive_total'] = row[0]
    stats['archive_species'] = row[1]
    stats['archive_gb'] = row[2]

    # Vandaag detecties
    cur.execute("""
        SELECT COUNT(*) FROM bird_detections
        WHERE detection_timestamp >= CURRENT_DATE
    """)
    stats['today_detections'] = cur.fetchone()[0]

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

    cur.close()
    conn.close()

    return stats


def format_number(n):
    """Format grote nummers met k/M suffix."""
    if n >= 1000000:
        return f"{n/1000000:.1f}M"
    elif n >= 1000:
        return f"{n/1000:.0f}k"
    return str(n)


def update_homer_config(stats):
    """Update de Homer config met nieuwe stats."""
    if not HOMER_CONFIG.exists():
        logger.error(f"Homer config niet gevonden: {HOMER_CONFIG}")
        return False

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


def main():
    try:
        logger.info("Homer stats update gestart")

        # Haal stats
        stats = get_stats()
        logger.info(f"Stats: {stats}")

        # Update Homer
        if update_homer_config(stats):
            logger.info("Homer config succesvol bijgewerkt")
        else:
            logger.error("Homer config update mislukt")

    except Exception as e:
        logger.error(f"Error: {e}")
        raise


if __name__ == "__main__":
    main()
