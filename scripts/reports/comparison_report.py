#!/usr/bin/env python3
"""
EMSN Comparison Report Generator
Generates reports comparing two time periods using Claude API
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


class ComparisonReportGenerator(ReportBase):
    """Generate comparison reports between two periods"""

    def __init__(self, style=None):
        super().__init__()
        self.get_style(style)

    def parse_period(self, period_str):
        """Parse period string like '2025-W01' or '2025-01' or '2025'"""
        if '-W' in period_str:
            # Week format: 2025-W01
            year, week = period_str.split('-W')
            year = int(year)
            week = int(week)
            # Get Monday of that week
            jan1 = datetime(year, 1, 1)
            days_to_monday = (7 - jan1.weekday()) % 7
            first_monday = jan1 + timedelta(days=days_to_monday)
            if jan1.weekday() <= 3:
                first_monday = jan1 - timedelta(days=jan1.weekday())
            start = first_monday + timedelta(weeks=week - 1)
            end = start + timedelta(days=6, hours=23, minutes=59, seconds=59)
            label = f"Week {week} {year}"
        elif len(period_str) == 7:
            # Month format: 2025-01
            year, month = period_str.split('-')
            year = int(year)
            month = int(month)
            start = datetime(year, month, 1)
            if month == 12:
                end = datetime(year + 1, 1, 1) - timedelta(seconds=1)
            else:
                end = datetime(year, month + 1, 1) - timedelta(seconds=1)
            month_names = ['januari', 'februari', 'maart', 'april', 'mei', 'juni',
                          'juli', 'augustus', 'september', 'oktober', 'november', 'december']
            label = f"{month_names[month - 1].capitalize()} {year}"
        else:
            # Year format: 2025
            year = int(period_str)
            start = datetime(year, 1, 1)
            end = datetime(year, 12, 31, 23, 59, 59)
            label = str(year)

        return start, end, label

    def collect_period_data(self, start, end, label):
        """Collect statistics for a single period"""
        cur = self.conn.cursor()

        data = {
            "label": label,
            "start": start.strftime('%Y-%m-%d'),
            "end": end.strftime('%Y-%m-%d')
        }

        # Total detections
        cur.execute("""
            SELECT COUNT(*)
            FROM bird_detections
            WHERE detection_timestamp BETWEEN %s AND %s
        """, (start, end))
        data["total_detections"] = cur.fetchone()[0]

        # Unique species
        cur.execute("""
            SELECT COUNT(DISTINCT species)
            FROM bird_detections
            WHERE detection_timestamp BETWEEN %s AND %s
        """, (start, end))
        data["unique_species"] = cur.fetchone()[0]

        # Top 15 species
        cur.execute("""
            SELECT common_name, species, COUNT(*) as count
            FROM bird_detections
            WHERE detection_timestamp BETWEEN %s AND %s
            GROUP BY common_name, species
            ORDER BY count DESC
            LIMIT 15
        """, (start, end))
        data["top_species"] = [
            {"common_name": row[0], "scientific_name": row[1], "count": row[2]}
            for row in cur.fetchall()
        ]

        # By station
        cur.execute("""
            SELECT station, COUNT(*) as count
            FROM bird_detections
            WHERE detection_timestamp BETWEEN %s AND %s
            GROUP BY station
        """, (start, end))
        data["by_station"] = {row[0]: row[1] for row in cur.fetchall()}

        # Dual detections
        cur.execute("""
            SELECT COUNT(*)
            FROM bird_detections
            WHERE detection_timestamp BETWEEN %s AND %s
            AND dual_detection = true
        """, (start, end))
        data["dual_detections"] = cur.fetchone()[0]

        # Peak hour
        cur.execute("""
            SELECT EXTRACT(HOUR FROM detection_timestamp)::int as hour, COUNT(*) as count
            FROM bird_detections
            WHERE detection_timestamp BETWEEN %s AND %s
            GROUP BY hour
            ORDER BY count DESC
            LIMIT 1
        """, (start, end))
        result = cur.fetchone()
        if result:
            data["peak_hour"] = result[0]
            data["peak_hour_count"] = result[1]

        cur.close()
        return data

    def collect_comparison_data(self, period1_str, period2_str):
        """Collect data for both periods"""
        start1, end1, label1 = self.parse_period(period1_str)
        start2, end2, label2 = self.parse_period(period2_str)

        data1 = self.collect_period_data(start1, end1, label1)
        data2 = self.collect_period_data(start2, end2, label2)

        # Calculate differences
        comparison = {
            "period1": data1,
            "period2": data2,
            "generated_date": datetime.now().strftime('%Y-%m-%d'),
            "differences": {}
        }

        # Detection change
        if data1["total_detections"] > 0:
            comparison["differences"]["detection_change"] = round(
                (data2["total_detections"] - data1["total_detections"]) / data1["total_detections"] * 100, 1
            )
        else:
            comparison["differences"]["detection_change"] = None

        # Species change
        comparison["differences"]["species_change"] = data2["unique_species"] - data1["unique_species"]

        # Species that appear in both
        species1 = set(s["scientific_name"] for s in data1["top_species"])
        species2 = set(s["scientific_name"] for s in data2["top_species"])
        comparison["differences"]["common_species"] = len(species1 & species2)
        comparison["differences"]["new_in_period2"] = len(species2 - species1)
        comparison["differences"]["missing_in_period2"] = len(species1 - species2)

        return comparison

    def generate_report(self, data):
        """Use Claude API to generate narrative report"""

        style_prompt = self.get_style_prompt()

        prompt = f"""{style_prompt}

Je schrijft een vergelijkingsrapport voor het EMSN vogelmonitoringsproject in Nijverdal, Overijssel.
Vergelijk {data['period1']['label']} met {data['period2']['label']}.

DATA:
{json.dumps(data, indent=2, ensure_ascii=False)}

STRUCTUUR (gebruik markdown headers):

### Samenvatting
- Kernverschillen in één alinea
- Meest opvallende verandering

### Detectievergelijking
- Totale aantallen
- Percentuele verandering
- Mogelijke verklaringen

### Soortendiversiteit
- Vergelijk het aantal unieke soorten
- Welke soorten verdwenen/verschenen?
- Top 5 van beide periodes

### Activiteitspatronen
- Vergelijk piekuren
- Vergelijk stationverdeling
- Dual detections

### Analyse
- Wat verklaren de verschillen?
- Seizoenseffecten?
- Andere factoren?

### Conclusie
- Hoofdconclusie
- Trends om in de gaten te houden

LENGTE: 500-700 woorden
"""

        return self.generate_with_claude(prompt, max_tokens=2500)

    def save_report(self, report_text, data):
        """Save report as markdown file"""

        REPORTS_PATH.mkdir(parents=True, exist_ok=True)

        p1 = data['period1']['label'].replace(' ', '-')
        p2 = data['period2']['label'].replace(' ', '-')
        filename = f"Vergelijking-{p1}-vs-{p2}.md"
        filepath = REPORTS_PATH / filename

        markdown = f"""---
type: comparison
period1: {data['period1']['label']}
period2: {data['period2']['label']}
generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
---

# Vergelijking: {data['period1']['label']} vs {data['period2']['label']}

**Locatie:** Nijverdal, Overijssel
**Gegenereerd:** {data['generated_date']}

---

{report_text}

---

## Statistieken

### {data['period1']['label']}

| Metriek | Waarde |
|---------|--------|
| Periode | {data['period1']['start']} - {data['period1']['end']} |
| Detecties | {data['period1']['total_detections']:,} |
| Soorten | {data['period1']['unique_species']} |
| Dual detections | {data['period1']['dual_detections']:,} |
| Piekuur | {data['period1'].get('peak_hour', 'N/A')}:00 |

### {data['period2']['label']}

| Metriek | Waarde |
|---------|--------|
| Periode | {data['period2']['start']} - {data['period2']['end']} |
| Detecties | {data['period2']['total_detections']:,} |
| Soorten | {data['period2']['unique_species']} |
| Dual detections | {data['period2']['dual_detections']:,} |
| Piekuur | {data['period2'].get('peak_hour', 'N/A')}:00 |

### Verschillen

| Metriek | Verschil |
|---------|----------|
| Detecties | {data['differences']['detection_change']:+.1f}% |
| Soorten | {data['differences']['species_change']:+d} |
| Gedeelde topsoorten | {data['differences']['common_species']} |

---

*Geschreven door Ecologisch Monitoring Systeem Nijverdal - Ronny Hullegie*
*Meetlocatie: Nijverdal, Overijssel (52.36°N, 6.46°E)*

**Contact:** emsn@ronnyhullegie.nl | **Website:** www.ronnyhullegie.nl

© {datetime.now().year} Ronny Hullegie. Alle rechten voorbehouden.
Licentie: CC BY-NC 4.0 (gebruik toegestaan met bronvermelding, niet commercieel)
"""

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(markdown)

        print(f"Rapport opgeslagen: {filepath}")
        return filepath

    def run(self, period1, period2):
        """Main execution"""
        print("EMSN Comparison Report Generator")
        print("=" * 60)
        print(f"Periode 1: {period1}")
        print(f"Periode 2: {period2}")

        if not self.connect_db():
            return False

        print("Verzamelen data...")
        data = self.collect_comparison_data(period1, period2)

        if data["period1"]["total_detections"] == 0 and data["period2"]["total_detections"] == 0:
            print("ERROR: Geen data gevonden voor beide periodes")
            return False

        print(f"   - Periode 1: {data['period1']['total_detections']:,} detecties")
        print(f"   - Periode 2: {data['period2']['total_detections']:,} detecties")

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

        print(f"\nVergelijkingsrapport succesvol gegenereerd")
        print(f"Bestand: {filepath}")

        self.close_db()
        return True


def main():
    import argparse
    from report_base import get_available_styles

    parser = argparse.ArgumentParser(description='Generate EMSN comparison report')
    parser.add_argument('--period1', type=str, required=True,
                        help='First period (e.g., 2025-W01, 2025-01, or 2025)')
    parser.add_argument('--period2', type=str, required=True,
                        help='Second period (e.g., 2025-W02, 2025-02, or 2024)')
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

    generator = ComparisonReportGenerator(style=args.style)
    success = generator.run(period1=args.period1, period2=args.period2)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
