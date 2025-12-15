#!/usr/bin/env python3
"""
EMSN Report Highlights Module
Automatically detects interesting patterns and anomalies in bird detection data
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import psycopg2


class ReportHighlights:
    """Detect and generate highlights for bird activity reports"""

    # Seasonal birds and their expected periods (month ranges)
    SEASONAL_BIRDS = {
        # Winter visitors (Oct-Mar)
        'Kramsvogel': {'start': 10, 'end': 3, 'type': 'wintergast'},
        'Koperwiek': {'start': 10, 'end': 3, 'type': 'wintergast'},
        'Keep': {'start': 10, 'end': 3, 'type': 'wintergast'},
        'Kolgans': {'start': 10, 'end': 3, 'type': 'wintergast'},
        'Grauwe Gans': {'start': 10, 'end': 3, 'type': 'wintergast'},
        'Sijs': {'start': 10, 'end': 3, 'type': 'wintergast'},
        'Pestvogel': {'start': 11, 'end': 2, 'type': 'wintergast'},

        # Summer visitors (Apr-Sep)
        'Zwartkop': {'start': 4, 'end': 9, 'type': 'zomergast'},
        'Tjiftjaf': {'start': 3, 'end': 10, 'type': 'zomergast'},
        'Fitis': {'start': 4, 'end': 9, 'type': 'zomergast'},
        'Gierzwaluw': {'start': 5, 'end': 8, 'type': 'zomergast'},
        'Boerenzwaluw': {'start': 4, 'end': 9, 'type': 'zomergast'},
        'Huiszwaluw': {'start': 4, 'end': 9, 'type': 'zomergast'},
        'Koekoek': {'start': 4, 'end': 7, 'type': 'zomergast'},
        'Wielewaal': {'start': 5, 'end': 8, 'type': 'zomergast'},
        'Nachtegaal': {'start': 4, 'end': 7, 'type': 'zomergast'},
        'Spotvogel': {'start': 5, 'end': 8, 'type': 'zomergast'},
        'Grauwe Vliegenvanger': {'start': 5, 'end': 9, 'type': 'zomergast'},
        'Bonte Vliegenvanger': {'start': 5, 'end': 8, 'type': 'zomergast'},
    }

    # Nocturnal species (primarily active at night)
    NOCTURNAL_SPECIES = [
        'Bosuil', 'Kerkuil', 'Ransuil', 'Steenuil', 'Oehoe',
        'Nachtzwaluw', 'Houtsnip', 'Waterral'
    ]

    # Rare species for the Netherlands
    RARE_SPECIES = [
        'Roerdomp', 'Woudaap', 'Kwak', 'Purperreiger', 'Ooievaar',
        'Zwarte Ooievaar', 'Lepelaar', 'Zeearend', 'Visarend',
        'Slechtvalk', 'Kraanvogel', 'Kwartelkoning', 'Porseleinhoen',
        'Watersnip', 'Houtsnip', 'Velduil', 'IJsvogel', 'Hop',
        'Draaihals', 'Zwarte Specht', 'Middelste Bonte Specht',
        'Kleine Bonte Specht', 'Boomleeuwerik', 'Duinpieper',
        'Grote Pieper', 'Beflijster', 'Blauwborst', 'Snor',
        'Sprinkhaanzanger', 'Bosrietzanger', 'Braamsluiper',
        'Orpheusspotvogel', 'Vuurgoudhaan', 'Grauwe Klauwier',
        'Klapekster', 'Notenkraker', 'Roek', 'Raaf',
        'Appelvink', 'Kruisbek', 'Barmsijs', 'Europese Kanarie'
    ]

    def __init__(self, conn):
        """
        Initialize highlights detector

        Args:
            conn: PostgreSQL database connection
        """
        self.conn = conn

    def get_all_highlights(self, start_date: datetime, end_date: datetime) -> Dict[str, List[Dict]]:
        """
        Get all highlights for a given period

        Returns dict with categories:
        - seasonal_firsts: First arrivals of seasonal birds
        - seasonal_lasts: Last sightings of seasonal birds
        - records: Record counts
        - unusual_times: Detections at unusual hours
        - rare_species: Rare species detections
        - new_species: Species never seen before
        - milestones: Detection count milestones
        """
        highlights = {
            'seasonal_firsts': self._get_seasonal_firsts(start_date, end_date),
            'seasonal_lasts': self._get_seasonal_lasts(start_date, end_date),
            'records': self._get_records(start_date, end_date),
            'unusual_times': self._get_unusual_times(start_date, end_date),
            'rare_species': self._get_rare_species(start_date, end_date),
            'new_species': self._get_new_species(start_date, end_date),
            'milestones': self._get_milestones(start_date, end_date),
        }
        return highlights

    def _get_seasonal_firsts(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Detect first arrivals of seasonal birds this season"""
        cur = self.conn.cursor()
        firsts = []

        current_month = start_date.month
        current_year = start_date.year

        for species, info in self.SEASONAL_BIRDS.items():
            # Check if we're in the expected arrival period
            in_arrival_period = False
            if info['start'] <= info['end']:
                in_arrival_period = info['start'] <= current_month <= info['start'] + 1
            else:  # Wraps around year (e.g., Oct-Mar)
                in_arrival_period = current_month >= info['start'] or current_month <= 1

            if not in_arrival_period:
                continue

            # Check if this species was detected this period
            cur.execute("""
                SELECT MIN(detection_timestamp), COUNT(*)
                FROM bird_detections
                WHERE common_name ILIKE %s
                AND detection_timestamp BETWEEN %s AND %s
            """, (f'%{species}%', start_date, end_date))
            result = cur.fetchone()

            if result[0]:  # Species was detected
                # Check if this is the first detection this season
                season_start = datetime(current_year if current_month >= info['start'] else current_year - 1,
                                        info['start'], 1)
                cur.execute("""
                    SELECT MIN(detection_timestamp)
                    FROM bird_detections
                    WHERE common_name ILIKE %s
                    AND detection_timestamp >= %s
                    AND detection_timestamp < %s
                """, (f'%{species}%', season_start, start_date))
                earlier = cur.fetchone()[0]

                if not earlier:  # This is the first this season!
                    firsts.append({
                        'species': species,
                        'type': info['type'],
                        'first_detection': result[0].strftime('%Y-%m-%d %H:%M'),
                        'count_this_period': result[1],
                        'message': f"Eerste {species} van het seizoen! ({info['type'].capitalize()})"
                    })

        cur.close()
        return firsts

    def _get_seasonal_lasts(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Detect last sightings of seasonal birds before they leave"""
        cur = self.conn.cursor()
        lasts = []

        current_month = start_date.month

        for species, info in self.SEASONAL_BIRDS.items():
            # Check if we're near the end of the expected period
            near_departure = False
            if info['start'] <= info['end']:
                near_departure = info['end'] - 1 <= current_month <= info['end']
            else:
                near_departure = current_month == info['end'] or (current_month >= 1 and current_month <= info['end'])

            if not near_departure:
                continue

            # Check if detected this period but not after
            cur.execute("""
                SELECT MAX(detection_timestamp), COUNT(*)
                FROM bird_detections
                WHERE common_name ILIKE %s
                AND detection_timestamp BETWEEN %s AND %s
            """, (f'%{species}%', start_date, end_date))
            result = cur.fetchone()

            if result[0] and result[1] <= 10:  # Low count might indicate departure
                lasts.append({
                    'species': species,
                    'type': info['type'],
                    'last_detection': result[0].strftime('%Y-%m-%d %H:%M'),
                    'count_this_period': result[1],
                    'message': f"Mogelijk laatste {species} van het seizoen (slechts {result[1]} detecties)"
                })

        cur.close()
        return lasts

    def _get_records(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Detect record counts (daily, weekly)"""
        cur = self.conn.cursor()
        records = []

        # Check for daily records per species
        cur.execute("""
            WITH current_daily AS (
                SELECT
                    common_name,
                    DATE(detection_timestamp) as day,
                    COUNT(*) as count
                FROM bird_detections
                WHERE detection_timestamp BETWEEN %s AND %s
                GROUP BY common_name, day
            ),
            historical_max AS (
                SELECT
                    common_name,
                    MAX(daily_count) as max_count
                FROM (
                    SELECT common_name, DATE(detection_timestamp), COUNT(*) as daily_count
                    FROM bird_detections
                    WHERE detection_timestamp < %s
                    GROUP BY common_name, DATE(detection_timestamp)
                ) sub
                GROUP BY common_name
            )
            SELECT
                c.common_name,
                c.day,
                c.count as current_count,
                COALESCE(h.max_count, 0) as previous_max
            FROM current_daily c
            LEFT JOIN historical_max h ON c.common_name = h.common_name
            WHERE c.count > COALESCE(h.max_count, 0)
            AND c.count >= 10
            ORDER BY (c.count - COALESCE(h.max_count, 0)) DESC
            LIMIT 5
        """, (start_date, end_date, start_date))

        for row in cur.fetchall():
            records.append({
                'species': row[0],
                'date': row[1].strftime('%Y-%m-%d'),
                'count': row[2],
                'previous_record': row[3],
                'message': f"Dagrecord {row[0]}: {row[2]} detecties (vorige record: {row[3]})"
            })

        cur.close()
        return records

    def _get_unusual_times(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Detect birds at unusual times (nocturnal during day, diurnal at night)"""
        cur = self.conn.cursor()
        unusual = []

        # Nocturnal species detected during daytime (10:00-16:00)
        for species in self.NOCTURNAL_SPECIES:
            cur.execute("""
                SELECT detection_timestamp, confidence, station
                FROM bird_detections
                WHERE common_name ILIKE %s
                AND detection_timestamp BETWEEN %s AND %s
                AND EXTRACT(HOUR FROM detection_timestamp) BETWEEN 10 AND 16
                AND confidence > 0.7
                ORDER BY confidence DESC
                LIMIT 1
            """, (f'%{species}%', start_date, end_date))
            result = cur.fetchone()

            if result:
                unusual.append({
                    'species': species,
                    'time': result[0].strftime('%Y-%m-%d %H:%M'),
                    'confidence': float(result[1]),
                    'station': result[2],
                    'type': 'nocturnal_daylight',
                    'message': f"{species} gedetecteerd overdag om {result[0].strftime('%H:%M')} (nachtactieve soort)"
                })

        # Common diurnal species detected late at night (23:00-04:00)
        diurnal_species = ['Merel', 'Koolmees', 'Pimpelmees', 'Roodborst', 'Huismus', 'Vink']
        for species in diurnal_species:
            cur.execute("""
                SELECT detection_timestamp, confidence, station
                FROM bird_detections
                WHERE common_name ILIKE %s
                AND detection_timestamp BETWEEN %s AND %s
                AND (EXTRACT(HOUR FROM detection_timestamp) >= 23
                     OR EXTRACT(HOUR FROM detection_timestamp) <= 4)
                AND confidence > 0.8
                ORDER BY confidence DESC
                LIMIT 1
            """, (f'%{species}%', start_date, end_date))
            result = cur.fetchone()

            if result:
                unusual.append({
                    'species': species,
                    'time': result[0].strftime('%Y-%m-%d %H:%M'),
                    'confidence': float(result[1]),
                    'station': result[2],
                    'type': 'diurnal_night',
                    'message': f"{species} gedetecteerd om {result[0].strftime('%H:%M')} (ongewoon nachtelijk)"
                })

        cur.close()
        return unusual[:5]  # Limit to top 5

    def _get_rare_species(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Detect rare species"""
        cur = self.conn.cursor()
        rare = []

        for species in self.RARE_SPECIES:
            cur.execute("""
                SELECT
                    detection_timestamp,
                    confidence,
                    station,
                    (SELECT COUNT(*) FROM bird_detections WHERE common_name ILIKE %s) as total_ever
                FROM bird_detections
                WHERE common_name ILIKE %s
                AND detection_timestamp BETWEEN %s AND %s
                AND confidence > 0.6
                ORDER BY confidence DESC
                LIMIT 1
            """, (f'%{species}%', f'%{species}%', start_date, end_date))
            result = cur.fetchone()

            if result:
                rare.append({
                    'species': species,
                    'time': result[0].strftime('%Y-%m-%d %H:%M'),
                    'confidence': float(result[1]),
                    'station': result[2],
                    'total_ever': result[3],
                    'message': f"Zeldzame soort: {species} (totaal ooit: {result[3]} detecties)"
                })

        cur.close()
        return sorted(rare, key=lambda x: x['total_ever'])[:10]  # Rarest first

    def _get_new_species(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Detect species never recorded before"""
        cur = self.conn.cursor()

        cur.execute("""
            SELECT DISTINCT common_name, species, MIN(detection_timestamp) as first, COUNT(*) as count
            FROM bird_detections
            WHERE detection_timestamp BETWEEN %s AND %s
            AND common_name NOT IN (
                SELECT DISTINCT common_name
                FROM bird_detections
                WHERE detection_timestamp < %s
            )
            GROUP BY common_name, species
            ORDER BY count DESC
        """, (start_date, end_date, start_date))

        new_species = []
        for row in cur.fetchall():
            new_species.append({
                'common_name': row[0],
                'scientific_name': row[1],
                'first_detection': row[2].strftime('%Y-%m-%d %H:%M'),
                'count': row[3],
                'message': f"NIEUW: {row[0]} ({row[1]}) - eerste detectie ooit!"
            })

        cur.close()
        return new_species

    def _get_milestones(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Detect detection count milestones"""
        cur = self.conn.cursor()
        milestones = []

        # Total detections milestone
        cur.execute("SELECT COUNT(*) FROM bird_detections WHERE detection_timestamp <= %s", (end_date,))
        total = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM bird_detections WHERE detection_timestamp < %s", (start_date,))
        before = cur.fetchone()[0]

        for milestone in [1000, 5000, 10000, 25000, 50000, 75000, 100000, 150000, 200000]:
            if before < milestone <= total:
                milestones.append({
                    'type': 'total_detections',
                    'value': milestone,
                    'message': f"Mijlpaal bereikt: {milestone:,} totale detecties!"
                })

        # Species count milestone
        cur.execute("SELECT COUNT(DISTINCT species) FROM bird_detections WHERE detection_timestamp <= %s", (end_date,))
        total_species = cur.fetchone()[0]

        for milestone in [50, 75, 100, 125, 150, 175, 200]:
            cur.execute("""
                SELECT COUNT(DISTINCT species)
                FROM bird_detections
                WHERE detection_timestamp < %s
            """, (start_date,))
            before_species = cur.fetchone()[0]

            if before_species < milestone <= total_species:
                milestones.append({
                    'type': 'total_species',
                    'value': milestone,
                    'message': f"Mijlpaal bereikt: {milestone} verschillende soorten geregistreerd!"
                })

        cur.close()
        return milestones

    def format_highlights_markdown(self, highlights: Dict[str, List[Dict]]) -> str:
        """Format highlights as markdown section"""
        md = "## Highlights\n\n"

        # New species (most important)
        if highlights['new_species']:
            md += "### Nieuwe Soorten\n\n"
            for h in highlights['new_species']:
                md += f"- **{h['message']}** ({h['count']} detecties)\n"
            md += "\n"

        # Milestones
        if highlights['milestones']:
            md += "### Mijlpalen\n\n"
            for h in highlights['milestones']:
                md += f"- {h['message']}\n"
            md += "\n"

        # Seasonal firsts
        if highlights['seasonal_firsts']:
            md += "### Seizoensgebonden Eerste Waarnemingen\n\n"
            for h in highlights['seasonal_firsts']:
                md += f"- {h['message']} - {h['first_detection']}\n"
            md += "\n"

        # Records
        if highlights['records']:
            md += "### Records\n\n"
            for h in highlights['records']:
                md += f"- {h['message']}\n"
            md += "\n"

        # Rare species
        if highlights['rare_species']:
            md += "### Zeldzame Soorten\n\n"
            for h in highlights['rare_species']:
                md += f"- {h['message']} ({h['confidence']:.0%} zekerheid)\n"
            md += "\n"

        # Unusual times
        if highlights['unusual_times']:
            md += "### Ongewone Waarnemingstijden\n\n"
            for h in highlights['unusual_times']:
                md += f"- {h['message']}\n"
            md += "\n"

        return md if len(md) > 20 else ""  # Return empty if no highlights


def test_highlights():
    """Test highlights detection"""
    import os

    conn = psycopg2.connect(
        host="192.168.1.25",
        port=5433,
        database="emsn",
        user="birdpi_zolder",
        password=os.getenv("EMSN_DB_PASSWORD", "REDACTED_DB_PASS")
    )

    highlights = ReportHighlights(conn)

    # Test with last week
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)

    all_highlights = highlights.get_all_highlights(start_date, end_date)

    print("=== HIGHLIGHTS TEST ===")
    for category, items in all_highlights.items():
        print(f"\n{category.upper()}:")
        for item in items[:3]:  # Show first 3
            print(f"  - {item.get('message', item)}")

    print("\n=== MARKDOWN OUTPUT ===")
    print(highlights.format_highlights_markdown(all_highlights))

    conn.close()


if __name__ == "__main__":
    test_highlights()
