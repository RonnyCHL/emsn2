#!/usr/bin/env python3
"""
EMSN Monthly Bird Activity Report Generator
Generates narrative monthly reports using Claude API
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
            GROUP BY week
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
                AVG(w.temperature_c) as avg_temp
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
- Analyseer weersinvloeden op vogelactiviteit
- Vergelijk met vorige maand en zoek verklaringen
- Eindig met vooruitblik naar volgende maand/seizoen
- Maximaal 800 woorden
- Gebruik geen bullet points, schrijf vloeiende paragrafen
- Maak het rijk aan detail en inzicht

STRUCTUUR:
1. Opening: Seizoensbeeld en algemene indruk van {data['month_name']}
2. Hoogtepunten: Meest opvallende waarnemingen en momenten
3. Patronen: Wekelijkse trends, drukste dagen, activiteitspatronen
4. Soortbespreking: Top 5 soorten met context en gedrag
5. Zeldzaamheden: Bijzondere waarnemingen in detail
6. Weer & Activiteit: Invloed van weersomstandigheden
7. Vergelijking: Trends t.o.v. vorige maand
8. Vooruitblik: Wat te verwachten komende maand

TOON:
- Enthousiast en betrokken
- Analytisch maar toegankelijk
- Persoonlijk en reflectief
- Waardering voor natuurlijke processen en seizoenen
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

# {data['month_name'].capitalize()} {data['year']} - Vogelactiviteit

**Periode:** {data['period']}
**Detecties:** {data['total_detections']:,}
**Soorten:** {data['unique_species']}

---

{report_text}

---

## 📊 Statistieken

### Top 15 Soorten
"""

        for i, species in enumerate(data['top_species'], 1):
            markdown += f"{i}. **{species['name']}**: {species['count']:,} detecties\n"

        if data['rare_sightings']:
            markdown += "\n### 🦅 Zeldzame Waarnemingen\n\n"
            for sighting in data['rare_sightings']:
                markdown += f"- **{sighting['species']}** op {sighting['time']} ({sighting['confidence']:.1%} zekerheid, station {sighting['station']})\n"

        if data.get('new_species_this_month'):
            markdown += "\n### 🎉 Nieuwe Soorten deze Maand\n\n"
            for species in data['new_species_this_month']:
                markdown += f"- {species}\n"

        markdown += "\n### 📈 Activiteit per Week\n\n"
        for week_data in data['activity_by_week']:
            markdown += f"- **Week {week_data['week']}**: {week_data['detections']:,} detecties\n"

        if data.get('busiest_day'):
            markdown += f"\n### 📅 Drukste Dag\n\n"
            markdown += f"**{data['busiest_day']['date']}**: {data['busiest_day']['count']:,} detecties\n"

        markdown += f"\n### 🔢 Overige Gegevens\n\n"
        markdown += f"- **Dual detections:** {data['dual_detections']:,}\n"
        markdown += f"- **Totaal dit jaar:** {data['year_to_date']['total_detections']:,} detecties\n"
        markdown += f"- **Soorten dit jaar:** {data['year_to_date']['unique_species']}\n"
        markdown += f"- **Totaal all-time:** {data['total_all_time']:,} detecties\n"

        if data['comparison_last_month']['detections_change'] != 'N/A':
            markdown += f"\n### 📊 Vergelijking met vorige maand\n\n"
            markdown += f"- **Detecties:** {data['comparison_last_month']['detections_change']}\n"
            markdown += f"- **Soorten:** {data['comparison_last_month']['species_change']}\n"

        markdown += f"\n---\n\n*Automatisch gegenereerd door Claude AI*\n"

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
        print(f"📅 Maand: {month_name} {start_date.year}")
        print(f"   Periode: {start_date.strftime('%Y-%m-%d')} tot {end_date.strftime('%Y-%m-%d')}")

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

        print("\n✅ Maandrapport succesvol gegenereerd!")
        print(f"📄 Bestand: {filepath}")

        self.conn.close()
        return True


if __name__ == "__main__":
    generator = MonthlyReportGenerator()
    success = generator.run()
    sys.exit(0 if success else 1)
