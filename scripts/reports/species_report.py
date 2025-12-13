#!/usr/bin/env python3
"""
EMSN Species-Specific Report Generator
Generates detailed reports about a single bird species using Claude API
"""

import sys
import os
import json
from datetime import datetime, timedelta
from pathlib import Path
import psycopg2

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from report_base import ReportBase, REPORTS_PATH


class SpeciesReportGenerator(ReportBase):
    """Generate detailed species-specific reports"""

    def __init__(self, style=None):
        super().__init__()
        self.get_style(style)

    def collect_data(self, species_name):
        """Collect all statistics for the specified species"""
        cur = self.conn.cursor()

        # First get the scientific name
        cur.execute("""
            SELECT species, common_name
            FROM bird_detections
            WHERE common_name ILIKE %s OR species ILIKE %s
            LIMIT 1
        """, (species_name, species_name))
        result = cur.fetchone()

        if not result:
            return None

        scientific_name = result[0]
        common_name = result[1]

        data = {
            "common_name": common_name,
            "scientific_name": scientific_name,
            "generated_date": datetime.now().strftime('%Y-%m-%d')
        }

        # Total detections
        cur.execute("""
            SELECT COUNT(*)
            FROM bird_detections
            WHERE species = %s
        """, (scientific_name,))
        data["total_detections"] = cur.fetchone()[0]

        # Date range
        cur.execute("""
            SELECT MIN(detection_timestamp), MAX(detection_timestamp)
            FROM bird_detections
            WHERE species = %s
        """, (scientific_name,))
        result = cur.fetchone()
        data["first_detection"] = result[0].strftime('%Y-%m-%d %H:%M') if result[0] else None
        data["last_detection"] = result[1].strftime('%Y-%m-%d %H:%M') if result[1] else None

        # Detections per station
        cur.execute("""
            SELECT station, COUNT(*) as count
            FROM bird_detections
            WHERE species = %s
            GROUP BY station
            ORDER BY count DESC
        """, (scientific_name,))
        data["by_station"] = {row[0]: row[1] for row in cur.fetchall()}

        # Monthly distribution
        cur.execute("""
            SELECT
                EXTRACT(MONTH FROM detection_timestamp)::int as month,
                COUNT(*) as count
            FROM bird_detections
            WHERE species = %s
            GROUP BY month
            ORDER BY month
        """, (scientific_name,))
        month_names = ['Jan', 'Feb', 'Mrt', 'Apr', 'Mei', 'Jun',
                       'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dec']
        data["monthly_distribution"] = [
            {"month": row[0], "month_name": month_names[row[0] - 1], "count": row[1]}
            for row in cur.fetchall()
        ]

        # Yearly trend
        cur.execute("""
            SELECT
                EXTRACT(YEAR FROM detection_timestamp)::int as year,
                COUNT(*) as count
            FROM bird_detections
            WHERE species = %s
            GROUP BY year
            ORDER BY year
        """, (scientific_name,))
        data["yearly_trend"] = [
            {"year": row[0], "count": row[1]}
            for row in cur.fetchall()
        ]

        # Hourly activity pattern
        cur.execute("""
            SELECT
                EXTRACT(HOUR FROM detection_timestamp)::int as hour,
                COUNT(*) as count
            FROM bird_detections
            WHERE species = %s
            GROUP BY hour
            ORDER BY hour
        """, (scientific_name,))
        data["hourly_pattern"] = [
            {"hour": row[0], "count": row[1]}
            for row in cur.fetchall()
        ]

        # Peak activity hour
        if data["hourly_pattern"]:
            peak = max(data["hourly_pattern"], key=lambda x: x["count"])
            data["peak_hour"] = peak["hour"]
            data["peak_hour_count"] = peak["count"]

        # Seasonal distribution
        cur.execute("""
            SELECT
                CASE
                    WHEN EXTRACT(MONTH FROM detection_timestamp) IN (12, 1, 2) THEN 'Winter'
                    WHEN EXTRACT(MONTH FROM detection_timestamp) IN (3, 4, 5) THEN 'Voorjaar'
                    WHEN EXTRACT(MONTH FROM detection_timestamp) IN (6, 7, 8) THEN 'Zomer'
                    ELSE 'Herfst'
                END as season,
                COUNT(*) as count
            FROM bird_detections
            WHERE species = %s
            GROUP BY season
            ORDER BY count DESC
        """, (scientific_name,))
        data["seasonal_distribution"] = [
            {"season": row[0], "count": row[1]}
            for row in cur.fetchall()
        ]

        # Confidence distribution
        cur.execute("""
            SELECT
                CASE
                    WHEN confidence >= 0.9 THEN '90-100%'
                    WHEN confidence >= 0.8 THEN '80-90%'
                    WHEN confidence >= 0.7 THEN '70-80%'
                    WHEN confidence >= 0.6 THEN '60-70%'
                    ELSE '<60%'
                END as confidence_range,
                COUNT(*) as count
            FROM bird_detections
            WHERE species = %s
            GROUP BY confidence_range
            ORDER BY count DESC
        """, (scientific_name,))
        data["confidence_distribution"] = [
            {"range": row[0], "count": row[1]}
            for row in cur.fetchall()
        ]

        # Average confidence
        cur.execute("""
            SELECT AVG(confidence), MIN(confidence), MAX(confidence)
            FROM bird_detections
            WHERE species = %s
        """, (scientific_name,))
        result = cur.fetchone()
        data["confidence_stats"] = {
            "average": round(float(result[0]) * 100, 1) if result[0] else 0,
            "min": round(float(result[1]) * 100, 1) if result[1] else 0,
            "max": round(float(result[2]) * 100, 1) if result[2] else 0
        }

        # Dual detections
        cur.execute("""
            SELECT COUNT(*)
            FROM bird_detections
            WHERE species = %s AND dual_detection = true
        """, (scientific_name,))
        data["dual_detections"] = cur.fetchone()[0]
        data["dual_detection_rate"] = round(
            data["dual_detections"] / data["total_detections"] * 100, 1
        ) if data["total_detections"] > 0 else 0

        # Peak days (top 10)
        cur.execute("""
            SELECT DATE(detection_timestamp) as day, COUNT(*) as count
            FROM bird_detections
            WHERE species = %s
            GROUP BY day
            ORDER BY count DESC
            LIMIT 10
        """, (scientific_name,))
        data["peak_days"] = [
            {"date": row[0].strftime('%Y-%m-%d'), "count": row[1]}
            for row in cur.fetchall()
        ]

        # Weather correlation (if available)
        cur.execute("""
            SELECT
                CASE
                    WHEN w.temp_outdoor < 5 THEN '<5°C'
                    WHEN w.temp_outdoor < 10 THEN '5-10°C'
                    WHEN w.temp_outdoor < 15 THEN '10-15°C'
                    WHEN w.temp_outdoor < 20 THEN '15-20°C'
                    WHEN w.temp_outdoor < 25 THEN '20-25°C'
                    ELSE '25+°C'
                END as temp_range,
                COUNT(DISTINCT d.id) as detections
            FROM bird_detections d
            JOIN weather_data w ON DATE_TRUNC('hour', d.detection_timestamp) = DATE_TRUNC('hour', w.measurement_timestamp)
            WHERE d.species = %s AND w.temp_outdoor IS NOT NULL
            GROUP BY temp_range
            ORDER BY detections DESC
        """, (scientific_name,))
        data["temperature_activity"] = [
            {"range": row[0], "count": row[1]}
            for row in cur.fetchall()
        ]

        # Species rank
        cur.execute("""
            WITH species_counts AS (
                SELECT species, COUNT(*) as total,
                       ROW_NUMBER() OVER (ORDER BY COUNT(*) DESC) as rank
                FROM bird_detections
                GROUP BY species
            )
            SELECT rank, (SELECT COUNT(DISTINCT species) FROM bird_detections) as total_species
            FROM species_counts
            WHERE species = %s
        """, (scientific_name,))
        result = cur.fetchone()
        if result:
            data["species_rank"] = result[0]
            data["total_species_count"] = result[1]

        cur.close()
        return data

    def generate_report(self, data):
        """Use Claude API to generate narrative report"""

        style_prompt = self.get_style_prompt()

        prompt = f"""{style_prompt}

Je schrijft een gedetailleerd soort-specifiek rapport over de {data['common_name']} (*{data['scientific_name']}*)
voor het EMSN vogelmonitoringsproject in Nijverdal, Overijssel.

DATA:
{json.dumps(data, indent=2, ensure_ascii=False)}

STRUCTUUR (gebruik markdown headers):

### Soortprofiel
- Algemene informatie over deze soort
- Rol in het ecosysteem
- Typisch gedrag en habitat

### Waarnemingsoverzicht
- Totaal aantal detecties
- Periode van waarnemingen
- Rangschikking t.o.v. andere soorten

### Seizoenspatronen
- Wanneer is de soort het meest actief?
- Verschuivingen door het jaar heen
- Vergelijk met wat je zou verwachten voor deze soort

### Dagritme
- Piekuren van activiteit
- Vergelijk met typisch gedrag van deze soort
- Mogelijke verklaringen

### Locatievoorkeuren
- Verdeling over stations
- Dual detections analyse
- Wat zegt dit over het territorium?

### Trends
- Jaarlijkse ontwikkeling
- Opvallende veranderingen
- Mogelijke oorzaken

### Conclusie
- Samenvatting van de belangrijkste bevindingen
- Wat vertelt dit over de lokale populatie?

LENGTE: 600-900 woorden
"""

        return self.generate_with_claude(prompt, max_tokens=3000)

    def save_report(self, report_text, data):
        """Save report as markdown file"""

        REPORTS_PATH.mkdir(parents=True, exist_ok=True)

        # Sanitize species name for filename
        safe_name = data['common_name'].replace(' ', '-').replace('/', '-')
        filename = f"Soort-{safe_name}.md"
        filepath = REPORTS_PATH / filename

        markdown = f"""---
type: species
species: {data['scientific_name']}
common_name: {data['common_name']}
total_detections: {data['total_detections']}
generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
---

# {data['common_name']} (*{data['scientific_name']}*)

**Locatie:** Nijverdal, Overijssel
**Totaal detecties:** {data['total_detections']:,}
**Periode:** {data['first_detection']} - {data['last_detection']}
**Rangschikking:** #{data.get('species_rank', 'N/A')} van {data.get('total_species_count', 'N/A')} soorten

---

{report_text}

---

## Statistische bijlage

### Maandverdeling

| Maand | Detecties |
|-------|-----------|
"""
        for month in data['monthly_distribution']:
            markdown += f"| {month['month_name']} | {month['count']:,} |\n"

        markdown += """
### Seizoensverdeling

| Seizoen | Detecties |
|---------|-----------|
"""
        for season in data['seasonal_distribution']:
            markdown += f"| {season['season']} | {season['count']:,} |\n"

        markdown += """
### Uurverdeling

| Uur | Detecties |
|-----|-----------|
"""
        for hour in data['hourly_pattern']:
            markdown += f"| {hour['hour']:02d}:00 | {hour['count']:,} |\n"

        markdown += f"""
### Confidence statistieken

| Metriek | Waarde |
|---------|--------|
| Gemiddeld | {data['confidence_stats']['average']}% |
| Minimum | {data['confidence_stats']['min']}% |
| Maximum | {data['confidence_stats']['max']}% |

### Dual detections

- **Totaal dual detections:** {data['dual_detections']:,}
- **Dual detection rate:** {data['dual_detection_rate']}%

### Per station

| Station | Detecties |
|---------|-----------|
"""
        for station, count in data['by_station'].items():
            markdown += f"| {station.capitalize()} | {count:,} |\n"

        if data['peak_days']:
            markdown += """
### Top 10 piekdagen

| Datum | Detecties |
|-------|-----------|
"""
            for day in data['peak_days']:
                markdown += f"| {day['date']} | {day['count']:,} |\n"

        markdown += f"""
---

*Automatisch gegenereerd door EMSN 2.0 met Claude AI*
"""

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(markdown)

        print(f"Rapport opgeslagen: {filepath}")
        return filepath

    def run(self, species):
        """Main execution"""
        print("EMSN Species Report Generator")
        print("=" * 60)
        print(f"Soort: {species}")

        if not self.connect_db():
            return False

        print("Verzamelen data...")
        data = self.collect_data(species)

        if not data:
            print(f"ERROR: Soort '{species}' niet gevonden in database")
            return False

        print(f"   - {data['total_detections']:,} detecties")
        print(f"   - {data['common_name']} (*{data['scientific_name']}*)")

        print("Genereren rapport met Claude AI...")
        report = self.generate_report(data)

        if not report:
            print("ERROR: Rapport generatie mislukt")
            return False

        print(f"   - {len(report)} karakters gegenereerd")

        print("Opslaan rapport...")
        filepath = self.save_report(report, data)

        print("Bijwerken web index...")
        self.update_web_index()

        print(f"\nSoort-rapport succesvol gegenereerd")
        print(f"Bestand: {filepath}")

        self.close_db()
        return True


def main():
    import argparse
    from report_base import get_available_styles

    parser = argparse.ArgumentParser(description='Generate EMSN species-specific bird report')
    parser.add_argument('--species', type=str, required=True,
                        help='Species name (Dutch or scientific)')
    parser.add_argument('--style', type=str, default=None,
                        help='Writing style (default: wetenschappelijk)')
    parser.add_argument('--list-styles', action='store_true',
                        help='List available writing styles and exit')

    args = parser.parse_args()

    if args.list_styles:
        styles = get_available_styles()
        print("Beschikbare schrijfstijlen:")
        for name, info in styles.items():
            print(f"  {name}: {info['description']}")
        sys.exit(0)

    generator = SpeciesReportGenerator(style=args.style)
    success = generator.run(species=args.species)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
