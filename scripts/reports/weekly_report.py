#!/usr/bin/env python3
"""
EMSN Weekly Bird Activity Report Generator
Generates narrative reports using Claude API
"""

import sys
import os
import json
from datetime import datetime, timedelta
from pathlib import Path
import psycopg2
from anthropic import Anthropic

# Configuration
DB_HOST = "192.168.1.25"
DB_PORT = 5433
DB_NAME = "emsn"
DB_USER = "birdpi_zolder"
DB_PASSWORD = os.getenv("EMSN_DB_PASSWORD", "REDACTED_DB_PASS")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    print("❌ ANTHROPIC_API_KEY environment variable not set")
    sys.exit(1)

OBSIDIAN_PATH = Path("/home/ronny/emsn2/reports")
LOG_DIR = Path("/mnt/usb/logs")


class WeeklyReportGenerator:
    """Generate weekly narrative bird activity reports"""

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

    def get_week_dates(self):
        """Get start and end dates for last week"""
        today = datetime.now()
        # Last Monday
        days_since_monday = (today.weekday() - 0) % 7
        if days_since_monday == 0:
            days_since_monday = 7
        last_monday = today - timedelta(days=days_since_monday)
        last_monday = last_monday.replace(hour=0, minute=0, second=0, microsecond=0)

        # Last Sunday
        last_sunday = last_monday + timedelta(days=6, hours=23, minutes=59, seconds=59)

        return last_monday, last_sunday

    def collect_data(self, start_date, end_date):
        """Collect all statistics for the report period"""
        cur = self.conn.cursor()

        data = {
            "period": f"{start_date.strftime('%Y-%m-%d')} tot {end_date.strftime('%Y-%m-%d')}",
            "week_number": start_date.isocalendar()[1],
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
            LIMIT 10
        """, (start_date, end_date))
        data["top_species"] = [
            {"name": row[0], "count": row[1]}
            for row in cur.fetchall()
        ]

        # Rare sightings (species with < 5 detections in the week)
        cur.execute("""
            SELECT species, detection_timestamp, confidence, station
            FROM bird_detections
            WHERE detection_timestamp BETWEEN %s AND %s
            AND species IN (
                SELECT species
                FROM bird_detections
                WHERE detection_timestamp BETWEEN %s AND %s
                GROUP BY species
                HAVING COUNT(*) <= 5
            )
            ORDER BY confidence DESC
            LIMIT 5
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

        # Dual detections (same species detected on both stations within 5 seconds)
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

        # Busiest hour
        cur.execute("""
            SELECT EXTRACT(HOUR FROM detection_timestamp) as hour, COUNT(*) as count
            FROM bird_detections
            WHERE detection_timestamp BETWEEN %s AND %s
            GROUP BY hour
            ORDER BY count DESC
            LIMIT 1
        """, (start_date, end_date))
        result = cur.fetchone()
        if result:
            hour = int(result[0])
            data["busiest_hour"] = f"{hour:02d}:00-{hour+1:02d}:00"
            data["busiest_hour_count"] = result[1]

        # Quietest hour (only daylight hours 6-20)
        cur.execute("""
            SELECT EXTRACT(HOUR FROM detection_timestamp) as hour, COUNT(*) as count
            FROM bird_detections
            WHERE detection_timestamp BETWEEN %s AND %s
            AND EXTRACT(HOUR FROM detection_timestamp) BETWEEN 6 AND 20
            GROUP BY hour
            ORDER BY count ASC
            LIMIT 1
        """, (start_date, end_date))
        result = cur.fetchone()
        if result:
            hour = int(result[0])
            data["quietest_hour"] = f"{hour:02d}:00-{hour+1:02d}:00"
            data["quietest_hour_count"] = result[1]

        # Weather correlation (if weather data available)
        cur.execute("""
            SELECT
                CASE WHEN w.rain_rate > 0 THEN 'rainy' ELSE 'dry' END as weather,
                COUNT(DISTINCT d.id) as detections
            FROM bird_detections d
            LEFT JOIN weather_data w
                ON DATE_TRUNC('hour', d.detection_timestamp) = DATE_TRUNC('hour', w.measurement_timestamp)
            WHERE d.detection_timestamp BETWEEN %s AND %s
            AND w.rain_rate IS NOT NULL
            GROUP BY weather
        """, (start_date, end_date))
        weather_data = dict(cur.fetchall())
        data["weather_correlation"] = {
            "rainy_days_detections": weather_data.get('rainy', 0),
            "dry_days_detections": weather_data.get('dry', 0)
        }

        # Extended weather analysis

        # 1. Temperature statistics (this week vs previous week)
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

        # Overall week stats
        if daily_temps:
            week_min = min(d["min"] for d in daily_temps if d["min"] is not None)
            week_max = max(d["max"] for d in daily_temps if d["max"] is not None)
            week_avg = sum(d["avg"] for d in daily_temps if d["avg"] is not None) / len([d for d in daily_temps if d["avg"] is not None])

            # Find warmest and coldest day
            warmest_day = max(daily_temps, key=lambda x: x["max"] if x["max"] else -999)
            coldest_day = min(daily_temps, key=lambda x: x["min"] if x["min"] else 999)
        else:
            week_min = week_max = week_avg = None
            warmest_day = coldest_day = None

        # Previous week temperature for comparison
        prev_start = start_date - timedelta(days=7)
        prev_end = end_date - timedelta(days=7)
        cur.execute("""
            SELECT AVG(temp_outdoor)
            FROM weather_data
            WHERE measurement_timestamp BETWEEN %s AND %s
            AND temp_outdoor IS NOT NULL
        """, (prev_start, prev_end))
        prev_week_avg_temp = cur.fetchone()[0]

        temp_comparison = None
        if week_avg and prev_week_avg_temp:
            temp_diff = week_avg - float(prev_week_avg_temp)
            temp_comparison = f"{'kouder' if temp_diff < 0 else 'warmer'}"
            temp_comparison_value = abs(temp_diff)

        data["temperature_stats"] = {
            "week_min": round(week_min, 1) if week_min else None,
            "week_max": round(week_max, 1) if week_max else None,
            "week_avg": round(week_avg, 1) if week_avg else None,
            "warmest_day": warmest_day["day"] if warmest_day else None,
            "warmest_temp": warmest_day["max"] if warmest_day else None,
            "coldest_day": coldest_day["day"] if coldest_day else None,
            "coldest_temp": coldest_day["min"] if coldest_day else None,
            "comparison_prev_week": temp_comparison,
            "temp_diff": round(temp_comparison_value, 1) if temp_comparison else None,
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
                MAX(wind_gust_speed) as max_gust
            FROM weather_data
            WHERE measurement_timestamp BETWEEN %s AND %s
            AND wind_speed IS NOT NULL
        """, (start_date, end_date))
        result = cur.fetchone()
        avg_wind = float(result[0]) if result[0] else None
        max_gust = float(result[1]) if result[1] else None

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

        data["wind_analysis"] = {
            "avg_speed": round(avg_wind, 1) if avg_wind else None,
            "max_gust": round(max_gust, 1) if max_gust else None,
            "activity_by_wind": wind_activity
        }

        # 4. Humidity & Pressure
        cur.execute("""
            SELECT
                AVG(humidity_outdoor) as avg_humidity,
                AVG(barometer) as avg_pressure,
                MIN(barometer) as min_pressure,
                MAX(barometer) as max_pressure
            FROM weather_data
            WHERE measurement_timestamp BETWEEN %s AND %s
            AND humidity_outdoor IS NOT NULL
            AND barometer IS NOT NULL
        """, (start_date, end_date))
        result = cur.fetchone()

        data["humidity_pressure"] = {
            "avg_humidity": int(result[0]) if result[0] else None,
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

        # Comparison with previous week
        prev_start = start_date - timedelta(days=7)
        prev_end = end_date - timedelta(days=7)

        cur.execute("""
            SELECT COUNT(*), COUNT(DISTINCT species)
            FROM bird_detections
            WHERE detection_timestamp BETWEEN %s AND %s
        """, (prev_start, prev_end))
        prev_detections, prev_species = cur.fetchone()

        if prev_detections > 0:
            detection_change = ((data["total_detections"] - prev_detections) / prev_detections) * 100
            data["comparison_last_week"] = {
                "detections_change": f"{detection_change:+.0f}%",
                "species_change": f"{data['unique_species'] - prev_species:+d}"
            }
        else:
            data["comparison_last_week"] = {
                "detections_change": "N/A",
                "species_change": "N/A"
            }

        # Check for milestones
        cur.execute("""
            SELECT COUNT(*)
            FROM bird_detections
            WHERE detection_timestamp <= %s
        """, (end_date,))
        total_all_time = cur.fetchone()[0]

        milestones = []
        for milestone in [1000, 5000, 10000, 25000, 50000, 75000, 100000]:
            if total_all_time >= milestone and total_all_time - data["total_detections"] < milestone:
                milestones.append(f"{milestone:,} detecties bereikt deze week!")

        data["milestones"] = milestones
        data["total_all_time"] = total_all_time

        # New species this year
        cur.execute("""
            SELECT DISTINCT species
            FROM bird_detections
            WHERE EXTRACT(YEAR FROM detection_timestamp) = %s
            AND detection_timestamp BETWEEN %s AND %s
            AND species NOT IN (
                SELECT DISTINCT species
                FROM bird_detections
                WHERE detection_timestamp < %s
            )
        """, (start_date.year, start_date, end_date, start_date))
        data["new_species_this_week"] = [row[0] for row in cur.fetchall()]

        cur.close()
        return data

    def generate_report(self, data):
        """Use Claude API to generate narrative report"""

        prompt = f"""Je bent een natuurjournalist die schrijft voor een vogelmonitoring project
in Nijverdal, Nederland. Schrijf een warme, verhalende samenvatting van
de vogelactiviteit van de afgelopen week.

DATA:
{json.dumps(data, indent=2, ensure_ascii=False)}

RICHTLIJNEN:
- Schrijf in het Nederlands
- Begin met een pakkende opening over het seizoen of weer
- Noem specifieke tijden en soorten (gebruik Nederlandse namen)
- Highlight zeldzame waarnemingen en bijzonderheden
- Maak het persoonlijk en levendig, alsof je een dagboek schrijft
- Vermeld dual detections (vogels die op beide stations tegelijk gehoord werden)
- Eindig met een vooruitblik of seizoensgebonden observatie
- Maximaal 600 woorden
- Gebruik geen bullet points, schrijf vloeiende paragrafen

STRUCTUUR:
1. Opening (weerbeeld, seizoen, gevoel van de week)
2. Weer & Vogels: Bespreek de weersomstandigheden en hoe deze de vogelactiviteit beïnvloedden
   - Temperatuurverloop (min/max/gemiddeld, vergelijking met vorige week)
   - Bij welke temperaturen waren vogels het actiefst?
   - Invloed van wind, regen, luchtvochtigheid en luchtdruk
   - Warmste vs koudste dag
3. Hoogtepunten van de week (top soorten, opmerkelijke momenten)
4. Interessante patronen (busiest/quietest hours, dual detections)
5. Zeldzame waarnemingen
6. Vergelijking met vorige week (zowel vogels als weer)
7. Vooruitblik

WEER & VOGELS SECTIE:
- Beschrijf het weerbeeld van de week (temperatuur, wind, neerslag)
- Leg verbanden tussen weer en vogelgedrag
- Gebruik de temperature_stats, optimal_conditions, wind_analysis en humidity_pressure data
- Bespreek bijvoorbeeld: "Deze week was het gemiddeld X graden, met als koudste punt Y graden op dag Z"
- Analyseer: "Vogels waren het actiefst bij temperaturen tussen X en Y graden"
- Vermeld opvallende weerpatronen zoals harde wind, veel regen, of extreme druk

TOON:
- Enthousiast maar niet overdreven
- Persoonlijk, alsof je tegen een vriend praat
- Informatief zonder technisch jargon
- Waardering voor de natuur en het samenspel tussen weer en vogels
"""

        try:
            message = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=2000,
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

        # Filename: 2025-W50-Weekrapport.md
        filename = f"{data['year']}-W{data['week_number']:02d}-Weekrapport.md"
        filepath = OBSIDIAN_PATH / filename

        # Create markdown with frontmatter
        markdown = f"""---
type: weekrapport
week: {data['week_number']}
year: {data['year']}
period: {data['period']}
total_detections: {data['total_detections']}
unique_species: {data['unique_species']}
generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
---

# Week {data['week_number']} - Vogelactiviteit

**Periode:** {data['period']}
**Detecties:** {data['total_detections']:,}
**Soorten:** {data['unique_species']}

---

{report_text}

---

## 📊 Statistieken

### Top 10 Soorten
"""

        for i, species in enumerate(data['top_species'], 1):
            markdown += f"{i}. **{species['name']}**: {species['count']:,} detecties\n"

        if data['rare_sightings']:
            markdown += "\n### 🦅 Zeldzame Waarnemingen\n\n"
            for sighting in data['rare_sightings']:
                markdown += f"- **{sighting['species']}** op {sighting['time']} ({sighting['confidence']:.1%} zekerheid, station {sighting['station']})\n"

        if data['milestones']:
            markdown += "\n### 🎉 Mijlpalen\n\n"
            for milestone in data['milestones']:
                markdown += f"- {milestone}\n"

        markdown += f"\n### 🔢 Overige Gegevens\n\n"
        markdown += f"- **Dual detections:** {data['dual_detections']:,}\n"
        markdown += f"- **Drukste uur:** {data['busiest_hour']} ({data.get('busiest_hour_count', 0):,} detecties)\n"
        markdown += f"- **Rustigste uur:** {data['quietest_hour']} ({data.get('quietest_hour_count', 0):,} detecties)\n"
        markdown += f"- **Totaal t/m deze week:** {data['total_all_time']:,} detecties\n"

        if data['comparison_last_week']['detections_change'] != 'N/A':
            markdown += f"\n### 📈 Vergelijking met vorige week\n\n"
            markdown += f"- **Detecties:** {data['comparison_last_week']['detections_change']}\n"
            markdown += f"- **Nieuwe soorten:** {data['comparison_last_week']['species_change']}\n"

        # Weather statistics section
        markdown += f"\n### 🌤️ Weerdata\n\n"

        temp_stats = data.get('temperature_stats', {})
        if temp_stats.get('week_avg'):
            markdown += f"**Temperatuur:**\n"
            markdown += f"- Gemiddeld: {temp_stats['week_avg']}°C\n"
            markdown += f"- Min/Max: {temp_stats['week_min']}°C / {temp_stats['week_max']}°C\n"
            if temp_stats.get('warmest_day'):
                markdown += f"- Warmste dag: {temp_stats['warmest_day']} ({temp_stats['warmest_temp']}°C)\n"
            if temp_stats.get('coldest_day'):
                markdown += f"- Koudste dag: {temp_stats['coldest_day']} ({temp_stats['coldest_temp']}°C)\n"
            if temp_stats.get('comparison_prev_week'):
                markdown += f"- T.o.v. vorige week: {temp_stats['temp_diff']}°C {temp_stats['comparison_prev_week']}\n"
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
                markdown += f"- Alle temperatuur brackets:\n"
                for temp_data in optimal['by_temperature']:
                    markdown += f"  - {temp_data['bracket']}: {temp_data['detections']:,} detecties\n"
            markdown += f"\n"

        wind = data.get('wind_analysis', {})
        if wind.get('avg_speed') is not None:
            markdown += f"**Wind:**\n"
            markdown += f"- Gemiddelde snelheid: {wind['avg_speed']} m/s\n"
            markdown += f"- Maximale windstoot: {wind['max_gust']} m/s\n"
            if wind.get('activity_by_wind'):
                markdown += f"- Activiteit per windsterkte:\n"
                for wind_data in wind['activity_by_wind']:
                    markdown += f"  - {wind_data['category'].capitalize()}: {wind_data['detections']:,} detecties\n"
            markdown += f"\n"

        humidity = data.get('humidity_pressure', {})
        if humidity.get('avg_humidity'):
            markdown += f"**Luchtvochtigheid & Druk:**\n"
            markdown += f"- Gemiddelde luchtvochtigheid: {humidity['avg_humidity']}%\n"
            markdown += f"- Gemiddelde luchtdruk: {humidity['avg_pressure']} hPa\n"
            markdown += f"- Druk range: {humidity['min_pressure']} - {humidity['max_pressure']} hPa\n"
            if humidity.get('activity_by_pressure'):
                markdown += f"- Activiteit bij lage druk: {humidity['activity_by_pressure'].get('lage druk', 0):,} detecties\n"
                markdown += f"- Activiteit bij hoge druk: {humidity['activity_by_pressure'].get('hoge druk', 0):,} detecties\n"

        markdown += f"\n---\n\n*Automatisch gegenereerd door Claude AI*\n"

        # Write file
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(markdown)

        print(f"✅ Rapport opgeslagen: {filepath}")
        return filepath

    def run(self):
        """Main execution"""
        print("🐦 EMSN Weekly Report Generator")
        print("=" * 60)

        # Get week dates
        start_date, end_date = self.get_week_dates()
        print(f"📅 Periode: {start_date.strftime('%Y-%m-%d')} tot {end_date.strftime('%Y-%m-%d')}")

        # Connect to database
        if not self.connect_db():
            return False

        print("📊 Verzamelen data...")
        data = self.collect_data(start_date, end_date)
        print(f"   - {data['total_detections']:,} detecties")
        print(f"   - {data['unique_species']} soorten")
        print(f"   - {data['dual_detections']:,} dual detections")

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

        print("\n✅ Weekrapport succesvol gegenereerd!")
        print(f"📄 Bestand: {filepath}")

        self.conn.close()
        return True


if __name__ == "__main__":
    generator = WeeklyReportGenerator()
    success = generator.run()
    sys.exit(0 if success else 1)
