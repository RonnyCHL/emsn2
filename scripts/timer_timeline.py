#!/usr/bin/env python3
"""
EMSN Timer Timeline Collector
=============================

Verzamelt systemd timer informatie en slaat op in PostgreSQL
voor visualisatie in Grafana als een tijdlijn dashboard.

Versie: 1.0.0
"""

import subprocess
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

try:
    import psycopg2
    from psycopg2.extras import execute_values
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

# Import secrets voor credentials
sys.path.insert(0, str(Path(__file__).parent.parent / 'config'))
try:
    from emsn_secrets import get_postgres_config
    _pg = get_postgres_config()
except ImportError:
    _pg = {
        'host': '192.168.1.25', 'port': 5433, 'database': 'emsn',
        'user': 'birdpi_zolder', 'password': os.environ.get('EMSN_DB_PASSWORD', '')
    }

# EMSN timer patterns om te filteren
EMSN_PATTERNS = [
    "emsn", "birdnet", "mqtt", "ulanzi", "lifetime", "anomaly",
    "dual-detection", "hardware", "flysafe", "rarity", "screenshot",
    "backup", "atmosbird", "system-inventory"
]

# Database configuratie (credentials uit secrets)
DB_CONFIG = {
    "host": _pg.get('host') or '192.168.1.25',
    "port": _pg.get('port') or 5433,
    "database": _pg.get('database') or 'emsn',
    "user": _pg.get('user') or 'birdpi_zolder',
    "password": _pg.get('password') or ''
}


def check_table_exists(conn) -> bool:
    """Check of de timer_timeline tabel bestaat."""
    cur = conn.cursor()
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name = 'timer_timeline'
        );
    """)
    exists = cur.fetchone()[0]
    cur.close()
    return exists


def get_timer_category(timer_name: str) -> str:
    """Bepaal de categorie van een timer."""
    name_lower = timer_name.lower()

    if "report" in name_lower or "seasonal" in name_lower:
        return "rapporten"
    elif "mqtt" in name_lower or "bridge" in name_lower:
        return "mqtt"
    elif "anomaly" in name_lower or "baseline" in name_lower:
        return "anomaly"
    elif "ulanzi" in name_lower or "screenshot" in name_lower:
        return "ulanzi"
    elif "flysafe" in name_lower or "radar" in name_lower:
        return "flysafe"
    elif "atmosbird" in name_lower:
        return "atmosbird"
    elif "hardware" in name_lower or "health" in name_lower:
        return "monitoring"
    elif "sync" in name_lower or "mirror" in name_lower or "lifetime" in name_lower:
        return "sync"
    elif "backup" in name_lower or "cleanup" in name_lower:
        return "maintenance"
    elif "inventory" in name_lower:
        return "inventaris"
    else:
        return "system"


def is_emsn_timer(timer_name: str) -> bool:
    """Check of een timer EMSN-gerelateerd is."""
    name_lower = timer_name.lower()
    return any(pattern in name_lower for pattern in EMSN_PATTERNS)


def get_timers_json() -> list:
    """Haal timer data op via systemctl --output=json."""
    try:
        result = subprocess.run(
            ["systemctl", "list-timers", "--all", "--output=json"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except Exception as e:
        print(f"Error getting timers: {e}")
    return []


def microseconds_to_datetime(us: int) -> datetime:
    """Converteer microseconden (Unix epoch) naar datetime."""
    if not us:  # None of 0
        return None
    return datetime.fromtimestamp(us / 1_000_000)


def microseconds_to_timedelta(us: int) -> timedelta:
    """Converteer microseconden naar timedelta."""
    if not us:  # None of 0
        return None
    return timedelta(microseconds=us)


def collect_and_store(station: str = "zolder"):
    """Verzamel timer data en sla op in PostgreSQL."""

    if not HAS_PSYCOPG2:
        print("psycopg2 niet geinstalleerd")
        return False

    timers = get_timers_json()
    if not timers:
        print("Geen timer data")
        return False

    try:
        conn = psycopg2.connect(**DB_CONFIG)

        if not check_table_exists(conn):
            print("❌ Tabel timer_timeline bestaat niet. Run eerst de migratie:")
            print("   psql -U postgres -d emsn -f database/migrations/015_timer_timeline.sql")
            return False

        cur = conn.cursor()

        # Verwijder oude records van vandaag voor deze station (we houden alleen laatste)
        cur.execute("""
            DELETE FROM timer_timeline
            WHERE station = %s
            AND recorded_at > NOW() - INTERVAL '1 hour'
        """, (station,))

        now = datetime.now()
        records = []

        for timer in timers:
            timer_unit = timer.get("unit", "")
            service_name = timer.get("activates", "")
            timer_name = timer_unit.replace(".timer", "")

            # Parse timestamps
            next_us = timer.get("next", 0)
            last_us = timer.get("last", 0)
            left_us = timer.get("left", 0)
            passed_us = timer.get("passed", 0)

            next_run = microseconds_to_datetime(next_us)
            last_run = microseconds_to_datetime(last_us)
            time_until = microseconds_to_timedelta(left_us)
            time_since = microseconds_to_timedelta(passed_us)

            is_emsn = is_emsn_timer(timer_name)
            category = get_timer_category(timer_name)

            records.append((
                now,
                timer_name,
                timer_unit,
                service_name,
                next_run,
                last_run,
                time_until,
                time_since,
                station,
                is_emsn,
                category
            ))

        # Bulk insert
        execute_values(cur, """
            INSERT INTO timer_timeline
            (recorded_at, timer_name, timer_unit, service_name, next_run,
             last_run, time_until_next, time_since_last, station, is_emsn_timer, category)
            VALUES %s
        """, records)

        conn.commit()

        # Count EMSN timers
        emsn_count = sum(1 for r in records if r[9])
        print(f"✅ {len(records)} timers opgeslagen ({emsn_count} EMSN-gerelateerd)")

        cur.close()
        conn.close()
        return True

    except Exception as e:
        print(f"❌ Database error: {e}")
        return False


def get_timeline_json(hours_ahead: int = 24, station: str = "zolder") -> dict:
    """
    Genereer JSON voor de tijdlijn.
    Kan ook gebruikt worden als API endpoint.
    """
    if not HAS_PSYCOPG2:
        return {"error": "psycopg2 not installed"}

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        # Haal meest recente data op
        cur.execute("""
            WITH latest AS (
                SELECT MAX(recorded_at) as max_recorded
                FROM timer_timeline
                WHERE station = %s
            )
            SELECT
                timer_name,
                service_name,
                next_run,
                last_run,
                is_emsn_timer,
                category,
                EXTRACT(EPOCH FROM (next_run - NOW())) as seconds_until
            FROM timer_timeline t, latest l
            WHERE t.recorded_at = l.max_recorded
            AND t.station = %s
            AND t.is_emsn_timer = TRUE
            AND t.next_run IS NOT NULL
            AND t.next_run < NOW() + INTERVAL '%s hours'
            ORDER BY next_run ASC
        """, (station, station, hours_ahead))

        now = datetime.now()
        timers = []

        for row in cur.fetchall():
            timer_name, service_name, next_run, last_run, is_emsn, category, seconds_until = row

            timers.append({
                "name": timer_name,
                "service": service_name,
                "next_run": next_run.isoformat() if next_run else None,
                "last_run": last_run.isoformat() if last_run else None,
                "category": category,
                "seconds_until": int(seconds_until) if seconds_until else None,
                "status": "upcoming" if seconds_until and seconds_until > 0 else "passed"
            })

        cur.close()
        conn.close()

        return {
            "generated_at": now.isoformat(),
            "station": station,
            "hours_ahead": hours_ahead,
            "timers": timers
        }

    except Exception as e:
        return {"error": str(e)}


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="EMSN Timer Timeline Collector")
    parser.add_argument("--station", default="zolder", help="Station naam")
    parser.add_argument("--json", action="store_true", help="Output JSON tijdlijn")
    parser.add_argument("--hours", type=int, default=24, help="Uren vooruit voor JSON")
    args = parser.parse_args()

    if args.json:
        result = get_timeline_json(args.hours, args.station)
        print(json.dumps(result, indent=2, default=str))
    else:
        print(f"🕐 EMSN Timer Timeline Collector")
        print(f"   Station: {args.station}")
        success = collect_and_store(args.station)
        return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
