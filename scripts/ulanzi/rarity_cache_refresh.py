#!/usr/bin/env python3
"""
EMSN 2.0 - Rarity Cache Refresh

Dagelijkse refresh van de species rarity cache in PostgreSQL.
Draait via systemd timer om 04:00.
"""

import psycopg2
import sys
from datetime import datetime
from pathlib import Path

# Add config path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'config'))
from ulanzi_config import PG_CONFIG, RARITY_TIERS, RARITY_LOOKBACK_DAYS, LOG_DIR


def get_tier(count):
    """Determine rarity tier based on detection count"""
    for tier_name, tier_config in RARITY_TIERS.items():
        if tier_config['min_count'] <= count <= tier_config['max_count']:
            return tier_name
    return 'very_common'


def refresh_rarity_cache():
    """Refresh the species_rarity_cache table"""
    print(f"[{datetime.now()}] Starting rarity cache refresh...")

    try:
        conn = psycopg2.connect(**PG_CONFIG)
        cursor = conn.cursor()

        # Get detection counts per species in lookback period
        cursor.execute(f"""
            SELECT
                common_name,
                COUNT(*) as detection_count
            FROM bird_detections
            WHERE detection_timestamp >= NOW() - INTERVAL '{RARITY_LOOKBACK_DAYS} days'
            GROUP BY common_name
        """)

        species_counts = cursor.fetchall()
        print(f"Found {len(species_counts)} species with detections")

        # Clear and repopulate cache
        cursor.execute("TRUNCATE TABLE species_rarity_cache")

        for common_name, count in species_counts:
            tier = get_tier(count)
            cursor.execute("""
                INSERT INTO species_rarity_cache (species_nl, detection_count, rarity_tier)
                VALUES (%s, %s, %s)
            """, (common_name, count, tier))

        conn.commit()

        # Log summary
        cursor.execute("""
            SELECT rarity_tier, COUNT(*)
            FROM species_rarity_cache
            GROUP BY rarity_tier
            ORDER BY rarity_tier
        """)

        print("Rarity distribution:")
        for tier, count in cursor.fetchall():
            print(f"  {tier}: {count} species")

        print(f"[{datetime.now()}] Rarity cache refresh completed")

        conn.close()
        return True

    except Exception as e:
        print(f"[{datetime.now()}] Error: {e}")
        return False


if __name__ == "__main__":
    success = refresh_rarity_cache()
    sys.exit(0 if success else 1)
