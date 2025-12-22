#!/usr/bin/env python3
"""
EMSN 2.0 - MQTT Cooldown Publisher

Publiceert Ulanzi cooldown status naar MQTT voor Home Assistant integratie.
Publiceert elke minuut de huidige cooldown status.

Topics:
- emsn2/ulanzi/cooldowns/count - Aantal soorten in cooldown
- emsn2/ulanzi/cooldowns/status - JSON met alle actieve cooldowns
- emsn2/ulanzi/stats/today - Statistieken vandaag
"""

import os
import sys
import json
import time
import psycopg2
import paho.mqtt.client as mqtt
from datetime import datetime
from pathlib import Path

# Import secrets voor credentials
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'config'))
try:
    from emsn_secrets import get_postgres_config, get_mqtt_config
    _pg = get_postgres_config()
    _mqtt = get_mqtt_config()
except ImportError:
    _pg = {
        'host': '192.168.1.25', 'port': 5433, 'database': 'emsn',
        'user': 'birdpi_zolder', 'password': os.environ.get('EMSN_DB_PASSWORD', '')
    }
    _mqtt = {
        'broker': '192.168.1.178', 'port': 1883,
        'username': 'ecomonitor', 'password': os.environ.get('EMSN_MQTT_PASSWORD', '')
    }

# Configuration (credentials uit secrets)
PG_CONFIG = {
    'host': _pg.get('host') or '192.168.1.25',
    'port': _pg.get('port') or 5433,
    'database': _pg.get('database') or 'emsn',
    'user': _pg.get('user') or 'birdpi_zolder',
    'password': _pg.get('password') or ''
}

MQTT_CONFIG = {
    'broker': _mqtt.get('broker') or '192.168.1.178',
    'port': _mqtt.get('port') or 1883,
    'username': _mqtt.get('username') or 'ecomonitor',
    'password': _mqtt.get('password') or '',
}

PUBLISH_INTERVAL = 60  # seconds


def get_db_connection():
    """Create database connection."""
    return psycopg2.connect(**PG_CONFIG)


def get_active_cooldowns(conn):
    """Get all active cooldowns."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT species_nl, rarity_tier, cooldown_seconds,
               last_notified, expires_at,
               EXTRACT(EPOCH FROM (expires_at - NOW())) as remaining_seconds
        FROM ulanzi_cooldown_status
        WHERE expires_at > NOW()
        ORDER BY expires_at ASC
    """)

    cooldowns = []
    for row in cursor.fetchall():
        cooldowns.append({
            'species': row[0],
            'rarity': row[1],
            'cooldown_seconds': row[2],
            'last_notified': row[3].isoformat() if row[3] else None,
            'expires_at': row[4].isoformat() if row[4] else None,
            'remaining_seconds': int(row[5]) if row[5] else 0
        })

    return cooldowns


def get_today_stats(conn):
    """Get notification statistics for today."""
    cursor = conn.cursor()

    # Notifications shown today
    cursor.execute("""
        SELECT COUNT(*) FROM ulanzi_notification_log
        WHERE was_shown = true AND timestamp >= NOW() - INTERVAL '24 hours'
    """)
    shown = cursor.fetchone()[0]

    # Notifications skipped today
    cursor.execute("""
        SELECT COUNT(*) FROM ulanzi_notification_log
        WHERE was_shown = false AND timestamp >= NOW() - INTERVAL '24 hours'
    """)
    skipped = cursor.fetchone()[0]

    # Unique species shown today
    cursor.execute("""
        SELECT COUNT(DISTINCT species_nl) FROM ulanzi_notification_log
        WHERE was_shown = true AND timestamp >= NOW() - INTERVAL '24 hours'
    """)
    unique_species = cursor.fetchone()[0]

    # Screenshots today
    cursor.execute("""
        SELECT COUNT(*) FROM ulanzi_screenshots
        WHERE timestamp >= NOW() - INTERVAL '24 hours'
    """)
    screenshots = cursor.fetchone()[0]

    # Last notification
    cursor.execute("""
        SELECT species_nl, timestamp FROM ulanzi_notification_log
        WHERE was_shown = true
        ORDER BY timestamp DESC LIMIT 1
    """)
    last = cursor.fetchone()

    return {
        'shown_24h': shown,
        'skipped_24h': skipped,
        'unique_species_24h': unique_species,
        'screenshots_24h': screenshots,
        'show_ratio': round(shown / (shown + skipped), 3) if (shown + skipped) > 0 else 0,
        'last_species': last[0] if last else None,
        'last_notification': last[1].isoformat() if last else None,
        'updated_at': datetime.now().isoformat()
    }


def get_smart_cooldown_info():
    """Get current smart cooldown multipliers."""
    hour = datetime.now().hour
    month = datetime.now().month
    is_weekend = datetime.now().weekday() >= 5

    # Time period
    if 5 <= hour < 8:
        time_period = 'dawn'
        time_mult = 0.5
    elif 8 <= hour < 12:
        time_period = 'morning'
        time_mult = 0.75
    elif 12 <= hour < 17:
        time_period = 'afternoon'
        time_mult = 1.0
    elif 17 <= hour < 20:
        time_period = 'evening'
        time_mult = 0.75
    else:
        time_period = 'night'
        time_mult = 1.5

    # Season
    if month in (3, 4, 5):
        season = 'spring'
        season_mult = 0.7
    elif month in (6, 7, 8):
        season = 'summer'
        season_mult = 0.9
    elif month in (9, 10, 11):
        season = 'autumn'
        season_mult = 0.7
    else:
        season = 'winter'
        season_mult = 1.2

    weekend_mult = 0.8 if is_weekend else 1.0
    total_mult = round(time_mult * season_mult * weekend_mult, 2)

    return {
        'time_period': time_period,
        'time_multiplier': time_mult,
        'season': season,
        'season_multiplier': season_mult,
        'is_weekend': is_weekend,
        'weekend_multiplier': weekend_mult,
        'total_multiplier': total_mult
    }


def main():
    """Main loop."""
    print(f"MQTT Cooldown Publisher starting...")
    print(f"Broker: {MQTT_CONFIG['broker']}:{MQTT_CONFIG['port']}")
    print(f"Publish interval: {PUBLISH_INTERVAL}s")

    # Setup MQTT
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.username_pw_set(MQTT_CONFIG['username'], MQTT_CONFIG['password'])

    try:
        client.connect(MQTT_CONFIG['broker'], MQTT_CONFIG['port'], 60)
        client.loop_start()
        print("Connected to MQTT broker")
    except Exception as e:
        print(f"Failed to connect to MQTT: {e}")
        return

    # Main loop
    conn = None
    while True:
        try:
            # Reconnect to DB if needed
            if not conn or conn.closed:
                conn = get_db_connection()
                print("Connected to database")

            # Get data
            cooldowns = get_active_cooldowns(conn)
            stats = get_today_stats(conn)
            smart_info = get_smart_cooldown_info()

            # Publish cooldown count
            client.publish(
                'emsn2/ulanzi/cooldowns/count',
                len(cooldowns),
                retain=True
            )

            # Publish full cooldown status
            client.publish(
                'emsn2/ulanzi/cooldowns/status',
                json.dumps({
                    'count': len(cooldowns),
                    'cooldowns': cooldowns,
                    'smart_cooldown': smart_info,
                    'updated_at': datetime.now().isoformat()
                }),
                retain=True
            )

            # Publish today stats
            client.publish(
                'emsn2/ulanzi/stats/today',
                json.dumps(stats),
                retain=True
            )

            # Publish smart cooldown info
            client.publish(
                'emsn2/ulanzi/smart_cooldown',
                json.dumps(smart_info),
                retain=True
            )

            print(f"[{datetime.now().strftime('%H:%M:%S')}] Published: "
                  f"{len(cooldowns)} cooldowns, {stats['shown_24h']} shown today, "
                  f"smart mult={smart_info['total_multiplier']}")

        except psycopg2.Error as e:
            print(f"Database error: {e}")
            conn = None
        except Exception as e:
            print(f"Error: {e}")

        time.sleep(PUBLISH_INTERVAL)


if __name__ == "__main__":
    main()
