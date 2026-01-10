#!/usr/bin/env python3
"""
EMSN Monthly Bird Activity Report Generator
Generates narrative monthly reports using Claude API
"""

import sys
import os
import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
import psycopg2
from anthropic import Anthropic

# Import core modules
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
from core.config import get_postgres_config
from species_images import get_images_for_species_list, generate_species_gallery_markdown

# Configuration (from core module)
_pg = get_postgres_config()
DB_HOST = _pg['host']
DB_PORT = _pg['port']
DB_NAME = _pg['database']
DB_USER = _pg['user']
DB_PASSWORD = _pg['password']

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    print("❌ ANTHROPIC_API_KEY environment variable not set")
    sys.exit(1)

OBSIDIAN_PATH = Path("/home/ronny/emsn2/reports")
LOG_DIR = Path("/mnt/usb/logs")


class MonthlyReportGenerator:
    """Generate monthly narrative bird activity reports"""

    def __init__(self):
        self.client = Anthropic(api_key=ANTHROPIC_API_KEY)
        self.conn = None

    def connect_db(self):
        """Connect to PostgreSQL database"""
        try:
            self.conn = psycopg2.connect(
                host=DB_HOST,
                port=DB_PORT,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD
            )
            return True
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            return False

    def get_month_dates(self):
        """Get start and end dates for last month"""
        today = datetime.now()
        # First day of current month
        first_of_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        # Last day of previous month
        last_day_prev_month = first_of_month - timedelta(days=1)
        # First day of previous month
        first_day_prev_month = last_day_prev_month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        # End of last day
        end_prev_month = last_day_prev_month.replace(hour=23, minute=59, second=59)

        return first_day_prev_month, end_prev_month

    def collect_data(self, start_date, end_date):
        """Collect all statistics for the report period"""
        cur = self.conn.cursor()

        month_name_nl = [
            "januari", "februari", "maart", "april", "mei", "juni",
            "juli", "augustus", "september", "oktober", "november", "december"
        ][start_date.month - 1]

        data = {
            "period": f"{start_date.strftime('%Y-%m-%d')} tot {end_date.strftime('%Y-%m-%d')}",
            "month": start_date.month,
            "month_name": month_name_nl,
            "year": start_date.year
        }

        # Total detections
        cur.execute("""
            SELECT COUNT(*)
            FROM bird_detections
            WHERE detection_timestamp BETWEEN %s AND %s
        """, (start_date, end_date))
        data["total_detections"] = cur.fetchone()[0]

        # Unique species
        cur.execute("""
            SELECT COUNT(DISTINCT species)
            FROM bird_detections
            WHERE detection_timestamp BETWEEN %s AND %s
        """, (start_date, end_date))
        data["unique_species"] = cur.fetchone()[0]

        # Top species
        cur.execute("""
            SELECT species, COUNT(*) as count
            FROM bird_detections
            WHERE detection_timestamp BETWEEN %s AND %s
            GROUP BY species
            ORDER BY count DESC
            LIMIT 15
        """, (start_date, end_date))
        data["top_species"] = [
            {"name": row[0], "count": row[1]}
            for row in cur.fetchall()
        ]

        # Rare sightings (species with < 10 detections in the month)
        cur.execute("""
            SELECT species, detection_timestamp, confidence, station
            FROM bird_detections
            WHERE detection_timestamp BETWEEN %s AND %s
            AND species IN (
                SELECT species
                FROM bird_detections
                WHERE detection_timestamp BETWEEN %s AND %s
                GROUP BY species
                HAVING COUNT(*) <= 10
            )
            ORDER BY confidence DESC
            LIMIT 10
        """, (start_date, end_date, start_date, end_date))
        data["rare_sightings"] = [
            {
                "species": row[0],
                "time": row[1].strftime('%Y-%m-%d %H:%M'),
                "confidence": float(row[2]),
                "station": row[3]
            }
            for row in cur.fetchall()
        ]

        # Dual detections
        cur.execute("""
            SELECT COUNT(DISTINCT d1.id)
            FROM bird_detections d1
            INNER JOIN bird_detections d2
                ON d1.species = d2.species
                AND d1.station != d2.station
                AND ABS(EXTRACT(EPOCH FROM (d1.detection_timestamp - d2.detection_timestamp))) <= 5
            WHERE d1.detection_timestamp BETWEEN %s AND %s
        """, (start_date, end_date))
        data["dual_detections"] = cur.fetchone()[0]

        # Activity by week
        cur.execute("""
            SELECT
                EXTRACT(WEEK FROM detection_timestamp) as week,
                COUNT(*) as count
            FROM bird_detections
            WHERE detection_timestamp BETWEEN %s AND %s
            GROUP BY EXTRACT(WEEK FROM detection_timestamp)
            ORDER BY week
        """, (start_date, end_date))
        data["activity_by_week"] = [
            {"week": int(row[0]), "detections": row[1]}
            for row in cur.fetchall()
        ]

        # Activity by day of week
        cur.execute("""
            SELECT
                TO_CHAR(detection_timestamp, 'Day') as day_name,
                COUNT(*) as count
            FROM bird_detections
            WHERE detection_timestamp BETWEEN %s AND %s
            GROUP BY day_name, EXTRACT(DOW FROM detection_timestamp)
            ORDER BY EXTRACT(DOW FROM detection_timestamp)
        """, (start_date, end_date))
        data["activity_by_day"] = [
            {"day": row[0].strip(), "detections": row[1]}
            for row in cur.fetchall()
        ]

        # Busiest day overall
        cur.execute("""
            SELECT DATE(detection_timestamp) as day, COUNT(*) as count
            FROM bird_detections
            WHERE detection_timestamp BETWEEN %s AND %s
            GROUP BY day
            ORDER BY count DESC
            LIMIT 1
        """, (start_date, end_date))
        result = cur.fetchone()
        if result:
            data["busiest_day"] = {
                "date": result[0].strftime('%Y-%m-%d'),
                "count": result[1]
            }

        # Weather trends
        cur.execute("""
            SELECT
                CASE
                    WHEN w.rain_rate > 5 THEN 'heavy_rain'
                    WHEN w.rain_rate > 0 THEN 'light_rain'
                    ELSE 'dry'
                END as weather,
                COUNT(DISTINCT d.id) as detections,
                AVG(w.temp_outdoor) as avg_temp
            FROM bird_detections d
            LEFT JOIN weather_data w
                ON DATE_TRUNC('hour', d.detection_timestamp) = DATE_TRUNC('hour', w.measurement_timestamp)
            WHERE d.detection_timestamp BETWEEN %s AND %s
            AND w.rain_rate IS NOT NULL
            GROUP BY weather
        """, (start_date, end_date))
        weather_data = {}
        for row in cur.fetchall():
            weather_data[row[0]] = {
                "detections": row[1],
                "avg_temp": float(row[2]) if row[2] else None
            }
        data["weather_trends"] = weather_data

        # Extended weather analysis

        # 1. Temperature statistics (this month vs previous month)
        cur.execute("""
            SELECT
                MIN(temp_outdoor) as min_temp,
                MAX(temp_outdoor) as max_temp,
                AVG(temp_outdoor) as avg_temp,
                DATE(measurement_timestamp) as day
            FROM weather_data
            WHERE measurement_timestamp BETWEEN %s AND %s
            AND temp_outdoor IS NOT NULL
            GROUP BY day
            ORDER BY day
        """, (start_date, end_date))

        daily_temps = []
        for row in cur.fetchall():
            daily_temps.append({
                "day": row[3].strftime('%Y-%m-%d'),
                "min": float(row[0]) if row[0] else None,
                "max": float(row[1]) if row[1] else None,
                "avg": float(row[2]) if row[2] else None
            })

        # Overall month stats
        if daily_temps:
            month_min = min(d["min"] for d in daily_temps if d["min"] is not None)
            month_max = max(d["max"] for d in daily_temps if d["max"] is not None)
            month_avg = sum(d["avg"] for d in daily_temps if d["avg"] is not None) / len([d for d in daily_temps if d["avg"] is not None])

            # Find warmest and coldest day
            warmest_day = max(daily_temps, key=lambda x: x["max"] if x["max"] else -999)
            coldest_day = min(daily_temps, key=lambda x: x["min"] if x["min"] else 999)
        else:
            month_min = month_max = month_avg = None
            warmest_day = coldest_day = None

        # Previous month temperature for comparison
        # Calculate previous month dates (go back one month from start_date)
        if start_date.month == 1:
            prev_month_year = start_date.year - 1
            prev_month_num = 12
        else:
            prev_month_year = start_date.year
            prev_month_num = start_date.month - 1
        prev_start = datetime(prev_month_year, prev_month_num, 1)
        # Last day of previous month
        if prev_month_num == 12:
            next_month_first = datetime(prev_month_year + 1, 1, 1)
        else:
            next_month_first = datetime(prev_month_year, prev_month_num + 1, 1)
        prev_end = next_month_first - timedelta(seconds=1)

        cur.execute("""
            SELECT AVG(temp_outdoor)
            FROM weather_data
            WHERE measurement_timestamp BETWEEN %s AND %s
            AND temp_outdoor IS NOT NULL
        """, (prev_start, prev_end))
        prev_month_avg_temp = cur.fetchone()[0]

        temp_comparison = None
        temp_comparison_value = None
        if month_avg and prev_month_avg_temp:
            temp_diff = month_avg - float(prev_month_avg_temp)
            temp_comparison = f"{'kouder' if temp_diff < 0 else 'warmer'}"
            temp_comparison_value = abs(temp_diff)

        # Weekly temperature variation
        cur.execute("""
            SELECT
                EXTRACT(WEEK FROM measurement_timestamp) as week,
                AVG(temp_outdoor) as avg_temp
            FROM weather_data
            WHERE measurement_timestamp BETWEEN %s AND %s
            AND temp_outdoor IS NOT NULL
            GROUP BY week
            ORDER BY week
        """, (start_date, end_date))

        weekly_temps = []
        for row in cur.fetchall():
            weekly_temps.append({
                "week": int(row[0]),
                "avg_temp": round(float(row[1]), 1) if row[1] else None
            })

        data["temperature_stats"] = {
            "month_min": round(month_min, 1) if month_min else None,
            "month_max": round(month_max, 1) if month_max else None,
            "month_avg": round(month_avg, 1) if month_avg else None,
            "warmest_day": warmest_day["day"] if warmest_day else None,
            "warmest_temp": warmest_day["max"] if warmest_day else None,
            "coldest_day": coldest_day["day"] if coldest_day else None,
            "coldest_temp": coldest_day["min"] if coldest_day else None,
            "comparison_prev_month": temp_comparison,
            "temp_diff": round(temp_comparison_value, 1) if temp_comparison_value else None,
            "weekly_temps": weekly_temps,
            "daily_temps": daily_temps
        }

        # 2. Optimal conditions analysis - bird activity by temperature
        cur.execute("""
            SELECT
                CASE
                    WHEN w.temp_outdoor < 0 THEN '<0°C'
                    WHEN w.temp_outdoor >= 0 AND w.temp_outdoor < 5 THEN '0-5°C'
                    WHEN w.temp_outdoor >= 5 AND w.temp_outdoor < 10 THEN '5-10°C'
                    WHEN w.temp_outdoor >= 10 AND w.temp_outdoor < 15 THEN '10-15°C'
                    WHEN w.temp_outdoor >= 15 AND w.temp_outdoor < 20 THEN '15-20°C'
                    WHEN w.temp_outdoor >= 20 THEN '≥20°C'
                END as temp_bracket,
                COUNT(DISTINCT d.id) as detections,
                AVG(w.temp_outdoor) as avg_temp_in_bracket
            FROM bird_detections d
            LEFT JOIN weather_data w
                ON DATE_TRUNC('hour', d.detection_timestamp) = DATE_TRUNC('hour', w.measurement_timestamp)
            WHERE d.detection_timestamp BETWEEN %s AND %s
            AND w.temp_outdoor IS NOT NULL
            GROUP BY temp_bracket
            ORDER BY detections DESC
        """, (start_date, end_date))

        temp_activity = []
        for row in cur.fetchall():
            temp_activity.append({
                "bracket": row[0],
                "detections": row[1],
                "avg_temp": round(float(row[2]), 1) if row[2] else None
            })

        optimal_temp_bracket = temp_activity[0] if temp_activity else None

        data["optimal_conditions"] = {
            "by_temperature": temp_activity,
            "optimal_bracket": optimal_temp_bracket["bracket"] if optimal_temp_bracket else None,
            "optimal_detections": optimal_temp_bracket["detections"] if optimal_temp_bracket else None
        }

        # 3. Wind analysis
        cur.execute("""
            SELECT
                AVG(wind_speed) as avg_wind,
                MAX(wind_gust_speed) as max_gust,
                MIN(wind_speed) as min_wind
            FROM weather_data
            WHERE measurement_timestamp BETWEEN %s AND %s
            AND wind_speed IS NOT NULL
        """, (start_date, end_date))
        result = cur.fetchone()
        avg_wind = float(result[0]) if result[0] else None
        max_gust = float(result[1]) if result[1] else None
        min_wind = float(result[2]) if result[2] else None

        # Bird activity on calm vs windy days
        cur.execute("""
            SELECT
                CASE
                    WHEN w.wind_speed < 2 THEN 'windstil'
                    WHEN w.wind_speed >= 2 AND w.wind_speed < 5 THEN 'lichte wind'
                    WHEN w.wind_speed >= 5 AND w.wind_speed < 10 THEN 'matige wind'
                    WHEN w.wind_speed >= 10 THEN 'harde wind'
                END as wind_category,
                COUNT(DISTINCT d.id) as detections
            FROM bird_detections d
            LEFT JOIN weather_data w
                ON DATE_TRUNC('hour', d.detection_timestamp) = DATE_TRUNC('hour', w.measurement_timestamp)
            WHERE d.detection_timestamp BETWEEN %s AND %s
            AND w.wind_speed IS NOT NULL
            GROUP BY wind_category
            ORDER BY detections DESC
        """, (start_date, end_date))

        wind_activity = []
        for row in cur.fetchall():
            wind_activity.append({
                "category": row[0],
                "detections": row[1]
            })

        # Wind by week
        cur.execute("""
            SELECT
                EXTRACT(WEEK FROM measurement_timestamp) as week,
                AVG(wind_speed) as avg_wind
            FROM weather_data
            WHERE measurement_timestamp BETWEEN %s AND %s
            AND wind_speed IS NOT NULL
            GROUP BY week
            ORDER BY week
        """, (start_date, end_date))

        weekly_wind = []
        for row in cur.fetchall():
            weekly_wind.append({
                "week": int(row[0]),
                "avg_wind": round(float(row[1]), 1) if row[1] else None
            })

        data["wind_analysis"] = {
            "avg_speed": round(avg_wind, 1) if avg_wind else None,
            "max_gust": round(max_gust, 1) if max_gust else None,
            "min_speed": round(min_wind, 1) if min_wind else None,
            "activity_by_wind": wind_activity,
            "weekly_wind": weekly_wind
        }

        # 4. Humidity & Pressure
        cur.execute("""
            SELECT
                AVG(humidity_outdoor) as avg_humidity,
                AVG(barometer) as avg_pressure,
                MIN(barometer) as min_pressure,
                MAX(barometer) as max_pressure,
                MIN(humidity_outdoor) as min_humidity,
                MAX(humidity_outdoor) as max_humidity
            FROM weather_data
            WHERE measurement_timestamp BETWEEN %s AND %s
            AND humidity_outdoor IS NOT NULL
            AND barometer IS NOT NULL
        """, (start_date, end_date))
        result = cur.fetchone()

        data["humidity_pressure"] = {
            "avg_humidity": int(result[0]) if result[0] else None,
            "min_humidity": int(result[4]) if result[4] else None,
            "max_humidity": int(result[5]) if result[5] else None,
            "avg_pressure": round(float(result[1]), 1) if result[1] else None,
            "min_pressure": round(float(result[2]), 1) if result[2] else None,
            "max_pressure": round(float(result[3]), 1) if result[3] else None
        }

        # Bird activity by pressure (low vs high)
        cur.execute("""
            WITH pressure_avg AS (
                SELECT AVG(barometer) as avg_p
                FROM weather_data
                WHERE measurement_timestamp BETWEEN %s AND %s
                AND barometer IS NOT NULL
            )
            SELECT
                CASE
                    WHEN w.barometer < (SELECT avg_p FROM pressure_avg) THEN 'lage druk'
                    ELSE 'hoge druk'
                END as pressure_category,
                COUNT(DISTINCT d.id) as detections
            FROM bird_detections d
            LEFT JOIN weather_data w
                ON DATE_TRUNC('hour', d.detection_timestamp) = DATE_TRUNC('hour', w.measurement_timestamp)
            WHERE d.detection_timestamp BETWEEN %s AND %s
            AND w.barometer IS NOT NULL
            GROUP BY pressure_category
        """, (start_date, end_date, start_date, end_date))

        pressure_activity = {}
        for row in cur.fetchall():
            pressure_activity[row[0]] = row[1]

        data["humidity_pressure"]["activity_by_pressure"] = pressure_activity

        # 5. Day/Night temperature difference
        cur.execute("""
            SELECT
                AVG(CASE WHEN EXTRACT(HOUR FROM measurement_timestamp) BETWEEN 6 AND 20
                    THEN temp_outdoor END) as day_temp,
                AVG(CASE WHEN EXTRACT(HOUR FROM measurement_timestamp) NOT BETWEEN 6 AND 20
                    THEN temp_outdoor END) as night_temp
            FROM weather_data
            WHERE measurement_timestamp BETWEEN %s AND %s
            AND temp_outdoor IS NOT NULL
        """, (start_date, end_date))
        result = cur.fetchone()

        day_temp = float(result[0]) if result[0] else None
        night_temp = float(result[1]) if result[1] else None

        data["day_night_temp"] = {
            "day_avg": round(day_temp, 1) if day_temp else None,
            "night_avg": round(night_temp, 1) if night_temp else None,
            "difference": round(day_temp - night_temp, 1) if (day_temp and night_temp) else None
        }

        # 6. Rain statistics
        cur.execute("""
            SELECT
                SUM(CASE WHEN rain_rate > 0 THEN 1 ELSE 0 END) as rainy_hours,
                COUNT(*) as total_hours,
                AVG(CASE WHEN rain_rate > 0 THEN rain_rate END) as avg_rain_rate,
                MAX(rain_rate) as max_rain_rate
            FROM weather_data
            WHERE measurement_timestamp BETWEEN %s AND %s
        """, (start_date, end_date))
        result = cur.fetchone()

        data["rain_stats"] = {
            "rainy_hours": result[0] if result[0] else 0,
            "total_hours": result[1] if result[1] else 0,
            "rainy_percentage": round((result[0] / result[1] * 100), 1) if result[1] else 0,
            "avg_rain_rate": round(float(result[2]), 2) if result[2] else 0,
            "max_rain_rate": round(float(result[3]), 2) if result[3] else 0
        }

        # Comparison with previous month
        prev_start = (start_date - timedelta(days=1)).replace(day=1)
        prev_end = start_date - timedelta(days=1)

        cur.execute("""
            SELECT COUNT(*), COUNT(DISTINCT species)
            FROM bird_detections
            WHERE detection_timestamp BETWEEN %s AND %s
        """, (prev_start, prev_end))
        prev_detections, prev_species = cur.fetchone()

        if prev_detections > 0:
            detection_change = ((data["total_detections"] - prev_detections) / prev_detections) * 100
            data["comparison_last_month"] = {
                "detections_change": f"{detection_change:+.0f}%",
                "species_change": f"{data['unique_species'] - prev_species:+d}",
                "prev_detections": prev_detections,
                "prev_species": prev_species
            }
        else:
            data["comparison_last_month"] = {
                "detections_change": "N/A",
                "species_change": "N/A"
            }

        # Year-to-date stats
        year_start = start_date.replace(month=1, day=1)
        cur.execute("""
            SELECT COUNT(*), COUNT(DISTINCT species)
            FROM bird_detections
            WHERE detection_timestamp BETWEEN %s AND %s
        """, (year_start, end_date))
        ytd_detections, ytd_species = cur.fetchone()
        data["year_to_date"] = {
            "total_detections": ytd_detections,
            "unique_species": ytd_species
        }

        # New species this month
        cur.execute("""
            SELECT DISTINCT species
            FROM bird_detections
            WHERE detection_timestamp BETWEEN %s AND %s
            AND species NOT IN (
                SELECT DISTINCT species
                FROM bird_detections
                WHERE detection_timestamp < %s
            )
        """, (start_date, end_date, start_date))
        data["new_species_this_month"] = [row[0] for row in cur.fetchall()]

        # Milestones
        cur.execute("""
            SELECT COUNT(*)
            FROM bird_detections
            WHERE detection_timestamp <= %s
        """, (end_date,))
        total_all_time = cur.fetchone()[0]
        data["total_all_time"] = total_all_time

        cur.close()
        return data

    def generate_report(self, data):
        """Use Claude API to generate narrative report"""

        prompt = f"""Je bent een natuurjournalist die schrijft voor een vogelmonitoring project
in Nijverdal, Nederland. Schrijf een uitgebreide, verhalende samenvatting van
de vogelactiviteit van de afgelopen maand.

DATA:
{json.dumps(data, indent=2, ensure_ascii=False)}

RICHTLIJNEN:
- Schrijf in het Nederlands
- Begin met een seizoensgebonden opening over de maand {data['month_name']}
- Beschrijf de algemene trends en patronen
- Highlight de top soorten en hun gedrag
- Bespreek zeldzame waarnemingen in detail
- Analyseer weersinvloeden op vogelactiviteit in detail
- Vergelijk met vorige maand en zoek verklaringen
- Eindig met vooruitblik naar volgende maand/seizoen
- Maximaal 1000 woorden
- Gebruik geen bullet points, schrijf vloeiende paragrafen
- Maak het rijk aan detail en inzicht

STRUCTUUR:
1. Opening: Seizoensbeeld en algemene indruk van {data['month_name']}
2. Weer & Vogels: Uitgebreide analyse van het weer en de invloed op vogelactiviteit
   - Temperatuurverloop door de maand (per week, min/max, gemiddeld)
   - Vergelijking met vorige maand
   - Warmste en koudste dag
   - Optimale temperaturen voor vogelactiviteit
   - Wind patronen en invloed (gemiddeld, stoten, per week)
   - Regenval statistieken en impact
   - Luchtvochtigheid en luchtdruk trends
   - Dag/nacht temperatuurverschillen
3. Hoogtepunten: Meest opvallende waarnemingen en momenten
4. Patronen: Wekelijkse trends, drukste dagen, activiteitspatronen
5. Soortbespreking: Top 5 soorten met context en gedrag
6. Zeldzaamheden: Bijzondere waarnemingen in detail
7. Vergelijking: Trends t.o.v. vorige maand (zowel vogels als weer)
8. Vooruitblik: Wat te verwachten komende maand

WEER & VOGELS SECTIE - ZEER BELANGRIJK:
Deze sectie moet uitgebreid en analytisch zijn, gebruik alle beschikbare weerdata:
- Beschrijf het temperatuurverloop: "De maand {data['month_name']} kende een gemiddelde temperatuur van X°C,
  variërend van Y°C op de koudste dag tot Z°C op de warmste dag"
- Analyseer wekelijkse trends: "De eerste week was kouder met gemiddeld X°C, terwijl week drie..."
- Leg verbanden: "Vogels waren het actiefst bij temperaturen tussen X en Y graden, met Z detecties"
- Windanalyse: "Gemiddelde windsnelheid was X m/s met een maximum van Y m/s. Bij windstille momenten..."
- Regenimpact: "Het regende X% van de tijd, met name in week Y. Op droge dagen zagen we Z% meer activiteit"
- Luchtdruk: "Bij lage luchtdruk (X detecties) vs hoge luchtdruk (Y detecties)"
- Dag/nacht: "Overdag was het gemiddeld X°C warmer dan 's nachts"

TOON:
- Enthousiast en betrokken
- Analytisch maar toegankelijk
- Persoonlijk en reflectief
- Waardering voor natuurlijke processen en seizoenen
- Focus op het samenspel tussen weer en vogelgedrag
"""

        try:
            message = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=3000,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            return message.content[0].text

        except Exception as e:
            print(f"❌ Claude API error: {e}")
            return None

    def save_report(self, report_text, data):
        """Save report as markdown file"""

        # Create Obsidian directory if it doesn't exist
        OBSIDIAN_PATH.mkdir(parents=True, exist_ok=True)

        # Filename: 2025-12-Maandrapport.md
        filename = f"{data['year']}-{data['month']:02d}-Maandrapport.md"
        filepath = OBSIDIAN_PATH / filename

        # Create markdown with frontmatter
        markdown = f"""---
type: maandrapport
month: {data['month']}
month_name: {data['month_name']}
year: {data['year']}
period: {data['period']}
total_detections: {data['total_detections']}
unique_species: {data['unique_species']}
generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
---

![EMSN Logo](logo.png)

# {data['month_name'].capitalize()} {data['year']} - Vogelactiviteit

**Periode:** {data['period']}
**Detecties:** {data['total_detections']:,}
**Soorten:** {data['unique_species']}

---

{report_text}

---

## Statistieken

### Top 15 Soorten
"""

        for i, species in enumerate(data['top_species'], 1):
            markdown += f"{i}. **{species['name']}**: {species['count']:,} detecties\n"

        if data['rare_sightings']:
            markdown += "\n### Zeldzame Waarnemingen\n\n"
            for sighting in data['rare_sightings']:
                markdown += f"- **{sighting['species']}** op {sighting['time']} ({sighting['confidence']:.1%} zekerheid, station {sighting['station']})\n"

        if data.get('new_species_this_month'):
            markdown += "\n### Nieuwe Soorten deze Maand\n\n"
            for species in data['new_species_this_month']:
                markdown += f"- {species}\n"

        markdown += "\n### Activiteit per Week\n\n"
        for week_data in data['activity_by_week']:
            markdown += f"- **Week {week_data['week']}**: {week_data['detections']:,} detecties\n"

        if data.get('busiest_day'):
            markdown += f"\n### Drukste Dag\n\n"
            markdown += f"**{data['busiest_day']['date']}**: {data['busiest_day']['count']:,} detecties\n"

        markdown += f"\n### Overige Gegevens\n\n"
        markdown += f"- **Dual detections:** {data['dual_detections']:,}\n"
        markdown += f"- **Totaal dit jaar:** {data['year_to_date']['total_detections']:,} detecties\n"
        markdown += f"- **Soorten dit jaar:** {data['year_to_date']['unique_species']}\n"
        markdown += f"- **Totaal all-time:** {data['total_all_time']:,} detecties\n"

        if data['comparison_last_month']['detections_change'] != 'N/A':
            markdown += f"\n### Vergelijking met vorige maand\n\n"
            markdown += f"- **Detecties:** {data['comparison_last_month']['detections_change']}\n"
            markdown += f"- **Soorten:** {data['comparison_last_month']['species_change']}\n"

        # Weather statistics section
        markdown += f"\n### Weerdata\n\n"

        temp_stats = data.get('temperature_stats', {})
        if temp_stats.get('month_avg'):
            markdown += f"**Temperatuur:**\n"
            markdown += f"- Gemiddeld: {temp_stats['month_avg']}°C\n"
            markdown += f"- Min/Max: {temp_stats['month_min']}°C / {temp_stats['month_max']}°C\n"
            if temp_stats.get('warmest_day'):
                markdown += f"- Warmste dag: {temp_stats['warmest_day']} ({temp_stats['warmest_temp']}°C)\n"
            if temp_stats.get('coldest_day'):
                markdown += f"- Koudste dag: {temp_stats['coldest_day']} ({temp_stats['coldest_temp']}°C)\n"
            if temp_stats.get('comparison_prev_month'):
                markdown += f"- T.o.v. vorige maand: {temp_stats['temp_diff']}°C {temp_stats['comparison_prev_month']}\n"

            if temp_stats.get('weekly_temps'):
                markdown += f"\n**Temperatuur per Week:**\n"
                for week_temp in temp_stats['weekly_temps']:
                    markdown += f"- Week {week_temp['week']}: {week_temp['avg_temp']}°C\n"
            markdown += f"\n"

        day_night = data.get('day_night_temp', {})
        if day_night.get('day_avg'):
            markdown += f"**Dag/Nacht:**\n"
            markdown += f"- Overdag (6-20u): {day_night['day_avg']}°C\n"
            markdown += f"- 's Nachts: {day_night['night_avg']}°C\n"
            markdown += f"- Verschil: {day_night['difference']}°C\n\n"

        optimal = data.get('optimal_conditions', {})
        if optimal.get('optimal_bracket'):
            markdown += f"**Optimale Temperatuur voor Vogels:**\n"
            markdown += f"- Meeste activiteit: {optimal['optimal_bracket']} ({optimal['optimal_detections']:,} detecties)\n"
            if optimal.get('by_temperature'):
                markdown += f"\n**Activiteit per Temperatuur Bracket:**\n"
                for temp_data in optimal['by_temperature']:
                    markdown += f"- {temp_data['bracket']}: {temp_data['detections']:,} detecties (gem. {temp_data['avg_temp']}°C)\n"
            markdown += f"\n"

        wind = data.get('wind_analysis', {})
        if wind.get('avg_speed') is not None:
            markdown += f"**Wind:**\n"
            markdown += f"- Gemiddelde snelheid: {wind['avg_speed']} m/s\n"
            markdown += f"- Maximale windstoot: {wind['max_gust']} m/s\n"
            markdown += f"- Minimale windsnelheid: {wind['min_speed']} m/s\n"

            if wind.get('weekly_wind'):
                markdown += f"\n**Wind per Week:**\n"
                for week_wind in wind['weekly_wind']:
                    markdown += f"- Week {week_wind['week']}: {week_wind['avg_wind']} m/s\n"

            if wind.get('activity_by_wind'):
                markdown += f"\n**Activiteit per Windsterkte:**\n"
                for wind_data in wind['activity_by_wind']:
                    markdown += f"- {wind_data['category'].capitalize()}: {wind_data['detections']:,} detecties\n"
            markdown += f"\n"

        rain = data.get('rain_stats', {})
        if rain.get('total_hours'):
            markdown += f"**Regenval:**\n"
            markdown += f"- Percentage met regen: {rain['rainy_percentage']}%\n"
            markdown += f"- Uren met regen: {rain['rainy_hours']} van {rain['total_hours']}\n"
            if rain['avg_rain_rate'] > 0:
                markdown += f"- Gemiddelde regenintensiteit: {rain['avg_rain_rate']} mm/u\n"
                markdown += f"- Maximale regenintensiteit: {rain['max_rain_rate']} mm/u\n"
            markdown += f"\n"

        humidity = data.get('humidity_pressure', {})
        if humidity.get('avg_humidity'):
            markdown += f"**Luchtvochtigheid & Druk:**\n"
            markdown += f"- Gemiddelde luchtvochtigheid: {humidity['avg_humidity']}%\n"
            markdown += f"- Range luchtvochtigheid: {humidity['min_humidity']}% - {humidity['max_humidity']}%\n"
            markdown += f"- Gemiddelde luchtdruk: {humidity['avg_pressure']} hPa\n"
            markdown += f"- Range luchtdruk: {humidity['min_pressure']} - {humidity['max_pressure']} hPa\n"
            if humidity.get('activity_by_pressure'):
                markdown += f"\n**Activiteit per Luchtdruk:**\n"
                markdown += f"- Bij lage druk: {humidity['activity_by_pressure'].get('lage druk', 0):,} detecties\n"
                markdown += f"- Bij hoge druk: {humidity['activity_by_pressure'].get('hoge druk', 0):,} detecties\n"

        # Add species images gallery if available
        species_images = data.get('species_images', [])
        if species_images:
            markdown += "\n---\n\n"
            markdown += generate_species_gallery_markdown(species_images)

        markdown += f"""
---

*Geschreven door Ecologisch Monitoring Systeem Nijverdal - Ronny Hullegie*
*Meetlocatie: Nijverdal, Overijssel (52.36°N, 6.46°E)*

**Contact:** emsn@ronnyhullegie.nl | **Website:** www.ronnyhullegie.nl

© {data['year']} Ronny Hullegie. Alle rechten voorbehouden.
Licentie: CC BY-NC 4.0 (gebruik toegestaan met bronvermelding, niet commercieel)
"""

        # Write file
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(markdown)

        print(f"✅ Rapport opgeslagen: {filepath}")
        return filepath

    def run(self):
        """Main execution"""
        print("🐦 EMSN Monthly Report Generator")
        print("=" * 60)

        # Get month dates
        start_date, end_date = self.get_month_dates()
        month_name = ["januari", "februari", "maart", "april", "mei", "juni",
                      "juli", "augustus", "september", "oktober", "november", "december"][start_date.month - 1]
        print(f"Maand: {month_name} {start_date.year}")
        print(f"   Periode: {start_date.strftime('%Y-%m-%d')} tot {end_date.strftime('%Y-%m-%d')}")

        # Connect to database
        if not self.connect_db():
            return False

        print("Verzamelen data...")
        data = self.collect_data(start_date, end_date)
        print(f"   - {data['total_detections']:,} detecties")
        print(f"   - {data['unique_species']} soorten")
        print(f"   - {data['dual_detections']:,} dual detections")

        # Fetch species images for top 5 species
        print("📷 Ophalen vogelfoto's...")
        try:
            top_species_for_images = [
                {'name': s['name'], 'scientific_name': s.get('scientific_name', '')}
                for s in data['top_species'][:5]
            ]
            data['species_images'] = get_images_for_species_list(top_species_for_images, max_images=5)
            print(f"   - {len(data['species_images'])} foto's opgehaald")
        except Exception as e:
            print(f"   ⚠️  Kon vogelfoto's niet ophalen: {e}")
            data['species_images'] = []

        # Generate report with Claude
        print("🤖 Genereren rapport met Claude AI...")
        report = self.generate_report(data)

        if not report:
            print("❌ Rapport generatie mislukt")
            return False

        print(f"   - {len(report)} karakters gegenereerd")

        # Save report
        print("💾 Opslaan rapport...")
        filepath = self.save_report(report, data)

        # Update web index
        print("🔄 Bijwerken web index...")
        try:
            subprocess.run([
                '/home/ronny/emsn2/venv/bin/python3',
                '/home/ronny/emsn2/reports-web/generate_index.py'
            ], check=True, capture_output=True)
        except Exception as e:
            print(f"⚠️  Kon web index niet bijwerken: {e}")

        print("\n✅ Maandrapport succesvol gegenereerd!")
        print(f"📄 Bestand: {filepath}")

        self.conn.close()
        return True


if __name__ == "__main__":
    generator = MonthlyReportGenerator()
    success = generator.run()
    sys.exit(0 if success else 1)
