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

OBSIDIAN_PATH = Path("/mnt/nas/obsidian/EMSN/Rapporten")
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
            SELECT species, detection_timestamp, confidence_score, station_id
            FROM bird_detections
            WHERE detection_timestamp BETWEEN %s AND %s
            AND species IN (
                SELECT species
                FROM bird_detections
                WHERE detection_timestamp BETWEEN %s AND %s
                GROUP BY species
                HAVING COUNT(*) <= 5
            )
            ORDER BY confidence_score DESC
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
                AND d1.station_id != d2.station_id
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
                CASE WHEN w.precipitation_mm > 0 THEN 'rainy' ELSE 'dry' END as weather,
                COUNT(DISTINCT d.id) as detections
            FROM bird_detections d
            LEFT JOIN weather_data w
                ON DATE_TRUNC('hour', d.detection_timestamp) = DATE_TRUNC('hour', w.measurement_timestamp)
            WHERE d.detection_timestamp BETWEEN %s AND %s
            AND w.precipitation_mm IS NOT NULL
            GROUP BY weather
        """, (start_date, end_date))
        weather_data = dict(cur.fetchall())
        data["weather_correlation"] = {
            "rainy_days_detections": weather_data.get('rainy', 0),
            "dry_days_detections": weather_data.get('dry', 0)
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
- Maximaal 500 woorden
- Gebruik geen bullet points, schrijf vloeiende paragrafen

STRUCTUUR:
1. Opening (weerbeeld, seizoen, gevoel van de week)
2. Hoogtepunten van de week (top soorten, opmerkelijke momenten)
3. Interessante patronen (busiest/quietest hours, dual detections)
4. Zeldzame waarnemingen
5. Vergelijking met vorige week
6. Vooruitblik

TOON:
- Enthousiast maar niet overdreven
- Persoonlijk, alsof je tegen een vriend praat
- Informatief zonder technisch jargon
- Waardering voor de natuur
"""

        try:
            message = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
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

        print("\n✅ Weekrapport succesvol gegenereerd!")
        print(f"📄 Bestand: {filepath}")

        self.conn.close()
        return True


if __name__ == "__main__":
    generator = WeeklyReportGenerator()
    success = generator.run()
    sys.exit(0 if success else 1)
