#!/usr/bin/env python3
"""
EMSN Yearly Bird Activity Report Generator
Generates comprehensive annual reports using Claude API

Scheduled to run on January 2nd for the previous year.
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
from species_images import get_images_for_species_list, generate_species_gallery_markdown


class YearlyReportGenerator(ReportBase):
    """Generate comprehensive annual bird activity reports"""

    def __init__(self, style=None):
        super().__init__()
        self.get_style(style)

    def get_year_dates(self, year=None):
        """Get start and end dates for a year"""
        if year is None:
            year = datetime.now().year - 1

        start_date = datetime(year, 1, 1, 0, 0, 0)
        end_date = datetime(year, 12, 31, 23, 59, 59)

        return start_date, end_date, year

    def collect_data(self, start_date, end_date, year):
        """Collect comprehensive statistics for the year"""
        cur = self.conn.cursor()

        data = {
            "year": year,
            "period_start": start_date.strftime('%Y-%m-%d'),
            "period_end": end_date.strftime('%Y-%m-%d')
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

        # Detections per station
        cur.execute("""
            SELECT station, COUNT(*) as count
            FROM bird_detections
            WHERE detection_timestamp BETWEEN %s AND %s
            GROUP BY station
            ORDER BY count DESC
        """, (start_date, end_date))
        data["by_station"] = {row[0]: row[1] for row in cur.fetchall()}

        # Top 30 species for the year
        cur.execute("""
            SELECT
                common_name,
                species,
                COUNT(*) as count
            FROM bird_detections
            WHERE detection_timestamp BETWEEN %s AND %s
            GROUP BY common_name, species
            ORDER BY count DESC
            LIMIT 30
        """, (start_date, end_date))
        data["top_species"] = [
            {"common_name": row[0], "scientific_name": row[1], "count": row[2]}
            for row in cur.fetchall()
        ]

        # Monthly breakdown with trends
        cur.execute("""
            SELECT
                EXTRACT(MONTH FROM detection_timestamp) as month,
                COUNT(*) as detections,
                COUNT(DISTINCT species) as species,
                COUNT(DISTINCT DATE(detection_timestamp)) as active_days
            FROM bird_detections
            WHERE detection_timestamp BETWEEN %s AND %s
            GROUP BY month
            ORDER BY month
        """, (start_date, end_date))

        month_names = ['Januari', 'Februari', 'Maart', 'April', 'Mei', 'Juni',
                       'Juli', 'Augustus', 'September', 'Oktober', 'November', 'December']
        data["monthly_breakdown"] = [
            {
                "month": int(row[0]),
                "month_name": month_names[int(row[0]) - 1],
                "detections": row[1],
                "species": row[2],
                "active_days": row[3],
                "daily_avg": round(row[1] / row[3], 1) if row[3] > 0 else 0
            }
            for row in cur.fetchall()
        ]

        # Seasonal breakdown
        seasons = {
            'Winter (dec-feb)': [12, 1, 2],
            'Voorjaar (mrt-mei)': [3, 4, 5],
            'Zomer (jun-aug)': [6, 7, 8],
            'Herfst (sep-nov)': [9, 10, 11]
        }

        seasonal_data = []
        for season_name, months in seasons.items():
            cur.execute("""
                SELECT
                    COUNT(*) as detections,
                    COUNT(DISTINCT species) as species
                FROM bird_detections
                WHERE detection_timestamp BETWEEN %s AND %s
                AND EXTRACT(MONTH FROM detection_timestamp) = ANY(%s)
            """, (start_date, end_date, months))
            result = cur.fetchone()
            seasonal_data.append({
                "season": season_name,
                "detections": result[0],
                "species": result[1]
            })
        data["seasonal_breakdown"] = seasonal_data

        # Peak days (top 10)
        cur.execute("""
            SELECT
                DATE(detection_timestamp) as day,
                COUNT(*) as count,
                COUNT(DISTINCT species) as species
            FROM bird_detections
            WHERE detection_timestamp BETWEEN %s AND %s
            GROUP BY day
            ORDER BY count DESC
            LIMIT 10
        """, (start_date, end_date))
        data["peak_days"] = [
            {
                "date": row[0].strftime('%Y-%m-%d'),
                "detections": row[1],
                "species": row[2]
            }
            for row in cur.fetchall()
        ]

        # Rare sightings (species seen < 5 times with high confidence)
        cur.execute("""
            WITH species_counts AS (
                SELECT species, COUNT(*) as total
                FROM bird_detections
                WHERE detection_timestamp BETWEEN %s AND %s
                GROUP BY species
                HAVING COUNT(*) <= 5
            )
            SELECT
                d.common_name,
                d.species,
                d.detection_timestamp,
                d.confidence,
                d.station,
                sc.total as year_total
            FROM bird_detections d
            JOIN species_counts sc ON d.species = sc.species
            WHERE d.detection_timestamp BETWEEN %s AND %s
            AND d.confidence >= 0.70
            ORDER BY sc.total ASC, d.confidence DESC
            LIMIT 20
        """, (start_date, end_date, start_date, end_date))
        data["rare_sightings"] = [
            {
                "common_name": row[0],
                "scientific_name": row[1],
                "datetime": row[2].strftime('%Y-%m-%d %H:%M'),
                "confidence": float(row[3]),
                "station": row[4],
                "year_total": row[5]
            }
            for row in cur.fetchall()
        ]

        # Phenology: First sighting of each species
        cur.execute("""
            SELECT
                common_name,
                species,
                MIN(detection_timestamp) as first_seen,
                MAX(detection_timestamp) as last_seen,
                COUNT(*) as total
            FROM bird_detections
            WHERE detection_timestamp BETWEEN %s AND %s
            GROUP BY common_name, species
            ORDER BY first_seen
        """, (start_date, end_date))
        data["species_phenology"] = [
            {
                "common_name": row[0],
                "scientific_name": row[1],
                "first_seen": row[2].strftime('%Y-%m-%d'),
                "last_seen": row[3].strftime('%Y-%m-%d'),
                "days_present": (row[3] - row[2]).days + 1,
                "total": row[4]
            }
            for row in cur.fetchall()
        ]

        # Dual detections
        cur.execute("""
            SELECT COUNT(*)
            FROM bird_detections
            WHERE detection_timestamp BETWEEN %s AND %s
            AND dual_detection = true
        """, (start_date, end_date))
        data["dual_detections"] = cur.fetchone()[0]

        # Dual detection rate by species (top 10)
        cur.execute("""
            SELECT
                common_name,
                species,
                COUNT(*) as total,
                SUM(CASE WHEN dual_detection THEN 1 ELSE 0 END) as dual,
                ROUND(SUM(CASE WHEN dual_detection THEN 1 ELSE 0 END)::numeric / COUNT(*) * 100, 1) as dual_pct
            FROM bird_detections
            WHERE detection_timestamp BETWEEN %s AND %s
            GROUP BY common_name, species
            HAVING COUNT(*) >= 50
            ORDER BY dual_pct DESC
            LIMIT 10
        """, (start_date, end_date))
        data["dual_detection_leaders"] = [
            {
                "common_name": row[0],
                "scientific_name": row[1],
                "total": row[2],
                "dual": row[3],
                "dual_pct": float(row[4])
            }
            for row in cur.fetchall()
        ]

        # Hourly activity pattern (yearly average)
        cur.execute("""
            SELECT
                EXTRACT(HOUR FROM detection_timestamp) as hour,
                COUNT(*) as total,
                ROUND(COUNT(*)::numeric / 365, 1) as daily_avg
            FROM bird_detections
            WHERE detection_timestamp BETWEEN %s AND %s
            GROUP BY hour
            ORDER BY hour
        """, (start_date, end_date))
        data["hourly_pattern"] = [
            {
                "hour": int(row[0]),
                "total": row[1],
                "daily_avg": float(row[2])
            }
            for row in cur.fetchall()
        ]

        # Weather statistics
        cur.execute("""
            SELECT
                EXTRACT(MONTH FROM measurement_timestamp) as month,
                AVG(temp_outdoor) as avg_temp,
                MIN(temp_outdoor) as min_temp,
                MAX(temp_outdoor) as max_temp,
                AVG(humidity_outdoor) as avg_humidity,
                SUM(CASE WHEN rain_rate > 0 THEN 1 ELSE 0 END)::float / NULLIF(COUNT(*), 0) * 100 as rain_pct
            FROM weather_data
            WHERE measurement_timestamp BETWEEN %s AND %s
            AND temp_outdoor IS NOT NULL
            GROUP BY month
            ORDER BY month
        """, (start_date, end_date))

        weather_monthly = []
        for row in cur.fetchall():
            weather_monthly.append({
                "month": int(row[0]),
                "month_name": month_names[int(row[0]) - 1],
                "avg_temp": round(float(row[1]), 1) if row[1] else None,
                "min_temp": round(float(row[2]), 1) if row[2] else None,
                "max_temp": round(float(row[3]), 1) if row[3] else None,
                "avg_humidity": int(row[4]) if row[4] else None,
                "rain_pct": round(float(row[5]), 1) if row[5] else None
            })
        data["weather_monthly"] = weather_monthly

        # Overall weather stats
        cur.execute("""
            SELECT
                AVG(temp_outdoor) as avg_temp,
                MIN(temp_outdoor) as min_temp,
                MAX(temp_outdoor) as max_temp,
                AVG(humidity_outdoor) as avg_humidity,
                AVG(wind_speed) as avg_wind,
                MAX(wind_gust_speed) as max_gust
            FROM weather_data
            WHERE measurement_timestamp BETWEEN %s AND %s
            AND temp_outdoor IS NOT NULL
        """, (start_date, end_date))
        result = cur.fetchone()
        if result and result[0]:
            data["weather_summary"] = {
                "avg_temp": round(float(result[0]), 1),
                "min_temp": round(float(result[1]), 1),
                "max_temp": round(float(result[2]), 1),
                "avg_humidity": int(result[3]) if result[3] else None,
                "avg_wind": round(float(result[4]), 1) if result[4] else None,
                "max_gust": round(float(result[5]), 1) if result[5] else None
            }

        # Species accumulation curve
        cur.execute("""
            WITH first_sightings AS (
                SELECT
                    species,
                    MIN(DATE(detection_timestamp)) as first_date
                FROM bird_detections
                WHERE detection_timestamp BETWEEN %s AND %s
                GROUP BY species
            )
            SELECT
                first_date,
                COUNT(*) as new_species
            FROM first_sightings
            GROUP BY first_date
            ORDER BY first_date
        """, (start_date, end_date))

        cumulative = 0
        accumulation = []
        for row in cur.fetchall():
            cumulative += row[1]
            accumulation.append({
                "date": row[0].strftime('%Y-%m-%d'),
                "new": row[1],
                "cumulative": cumulative
            })
        data["species_accumulation"] = accumulation

        # Compare with previous year
        prev_start = datetime(year - 1, 1, 1)
        prev_end = datetime(year - 1, 12, 31, 23, 59, 59)

        cur.execute("""
            SELECT COUNT(*), COUNT(DISTINCT species)
            FROM bird_detections
            WHERE detection_timestamp BETWEEN %s AND %s
        """, (prev_start, prev_end))
        result = cur.fetchone()
        if result[0] > 0:
            data["previous_year"] = {
                "year": year - 1,
                "detections": result[0],
                "species": result[1],
                "detection_change": round((data["total_detections"] - result[0]) / result[0] * 100, 1),
                "species_change": data["unique_species"] - result[1]
            }

        # Milestones reached this year
        milestones_reached = []
        for milestone in [1000, 5000, 10000, 25000, 50000, 75000, 100000, 150000, 200000]:
            cur.execute("""
                SELECT MIN(detection_timestamp)
                FROM (
                    SELECT detection_timestamp,
                           ROW_NUMBER() OVER (ORDER BY detection_timestamp) as rn
                    FROM bird_detections
                ) sub
                WHERE rn = %s
            """, (milestone,))
            result = cur.fetchone()
            if result[0] and start_date <= result[0] <= end_date:
                milestones_reached.append({
                    "milestone": milestone,
                    "date": result[0].strftime('%Y-%m-%d')
                })
        data["milestones"] = milestones_reached

        # Project totals
        cur.execute("SELECT COUNT(*), COUNT(DISTINCT species), MIN(detection_timestamp) FROM bird_detections")
        result = cur.fetchone()
        data["project_totals"] = {
            "total_detections": result[0],
            "total_species": result[1],
            "project_start": result[2].strftime('%Y-%m-%d') if result[2] else None
        }

        cur.close()
        return data

    def generate_report(self, data):
        """Use Claude API to generate narrative report"""

        style_prompt = self.get_style_prompt()

        prompt = f"""{style_prompt}

Je schrijft een uitgebreid jaaroverzicht voor het EMSN vogelmonitoringsproject in Nijverdal, Overijssel.

DATA:
{json.dumps(data, indent=2, ensure_ascii=False)}

STRUCTUUR (gebruik markdown headers):

### Het jaar in vogelvlucht
- Karakteriseer {data['year']} in 2-3 alinea's
- Wat maakte dit jaar bijzonder?
- Grote lijnen en trends

### Seizoensverloop
- Beschrijf elk seizoen kort
- Hoogte- en dieptepunten per seizoen
- Trekvogelbewegingen

### Soortendiversiteit
- Analyse van de {data['unique_species']} waargenomen soorten
- Top soorten met context
- Gebruik markdown tabel voor top 10
- Opvallende aan- of afwezigen

### Fenologie
- Eerste en laatste waarnemingen
- Vroege/late aankomsten vergeleken met normaal
- Interessante patronen in presentie

### Bijzondere waarnemingen
- Zeldzame soorten met context
- Gebruik markdown tabel
- Waarom zijn deze waarnemingen significant?

### Weer en vogelactiviteit
- Jaaroverzicht weer
- Correlaties tussen weer en activiteit
- Extreme weersomstandigheden en hun effect

### Activiteitspatronen
- Dagritme
- Maandelijkse fluctuaties
- Dual detections analyse
- Verschillen tussen stations

### Vergelijking en trends
- Vergelijk met vorig jaar indien beschikbaar
- Langetermijntrends
- Wat kunnen we concluderen?

### Vooruitblik {data['year'] + 1}
- Verwachtingen voor komend jaar
- Aandachtspunten voor monitoring

LENGTE: 1500-2000 woorden

Genereer ALLEEN de inhoud, zonder de titel/header - die wordt automatisch toegevoegd.
"""

        return self.generate_with_claude(prompt, max_tokens=6000)

    def save_report(self, report_text, data):
        """Save report as markdown file"""

        REPORTS_PATH.mkdir(parents=True, exist_ok=True)

        filename = f"{data['year']}-Jaaroverzicht.md"
        filepath = REPORTS_PATH / filename

        # Create markdown with frontmatter
        markdown = f"""---
type: jaaroverzicht
year: {data['year']}
period_start: {data['period_start']}
period_end: {data['period_end']}
total_detections: {data['total_detections']}
unique_species: {data['unique_species']}
generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
---

![EMSN Logo](logo.png)

# EMSN Jaaroverzicht {data['year']}

**Locatie:** Nijverdal, Overijssel
**Periode:** {data['period_start']} tot {data['period_end']}
**Stations:** Zolder, Berging
**Detecties:** {data['total_detections']:,} | **Soorten:** {data['unique_species']}

---

{report_text}

---

## Statistische bijlage

### Maandoverzicht

| Maand | Detecties | Soorten | Actieve dagen | Gem./dag |
|-------|-----------|---------|---------------|----------|
"""
        for month in data['monthly_breakdown']:
            markdown += f"| {month['month_name']} | {month['detections']:,} | {month['species']} | {month['active_days']} | {month['daily_avg']} |\n"

        markdown += f"""
### Seizoensoverzicht

| Seizoen | Detecties | Soorten |
|---------|-----------|---------|
"""
        for season in data['seasonal_breakdown']:
            markdown += f"| {season['season']} | {season['detections']:,} | {season['species']} |\n"

        markdown += f"""
### Top 30 soorten

| Rang | Soort | Wetenschappelijk | Detecties |
|------|-------|------------------|-----------|
"""
        for i, species in enumerate(data['top_species'], 1):
            markdown += f"| {i} | {species['common_name']} | *{species['scientific_name']}* | {species['count']:,} |\n"

        markdown += f"""
### Piekdagen

| Datum | Detecties | Soorten |
|-------|-----------|---------|
"""
        for day in data['peak_days']:
            markdown += f"| {day['date']} | {day['detections']:,} | {day['species']} |\n"

        if data.get('rare_sightings'):
            markdown += f"""
### Zeldzame waarnemingen

| Datum | Soort | Confidence | Station | Totaal {data['year']} |
|-------|-------|------------|---------|------------|
"""
            seen = set()
            for sighting in data['rare_sightings']:
                key = sighting['scientific_name']
                if key not in seen:
                    seen.add(key)
                    markdown += f"| {sighting['datetime']} | {sighting['common_name']} (*{sighting['scientific_name']}*) | {sighting['confidence']:.1%} | {sighting['station']} | {sighting['year_total']} |\n"

        if data.get('dual_detection_leaders'):
            markdown += f"""
### Dual detection leiders

| Soort | Totaal | Dual | Percentage |
|-------|--------|------|------------|
"""
            for species in data['dual_detection_leaders']:
                markdown += f"| {species['common_name']} (*{species['scientific_name']}*) | {species['total']:,} | {species['dual']:,} | {species['dual_pct']}% |\n"

        if data.get('weather_monthly'):
            markdown += f"""
### Maandelijkse weerdata

| Maand | Gem. temp | Min | Max | Luchtvocht. | Neerslag% |
|-------|-----------|-----|-----|-------------|-----------|
"""
            for w in data['weather_monthly']:
                markdown += f"| {w['month_name']} | {w['avg_temp']}°C | {w['min_temp']}°C | {w['max_temp']}°C | {w['avg_humidity']}% | {w['rain_pct']}% |\n"

        if data.get('weather_summary'):
            ws = data['weather_summary']
            markdown += f"""
### Weersamenvatting {data['year']}

| Parameter | Waarde |
|-----------|--------|
| Gemiddelde temperatuur | {ws['avg_temp']}°C |
| Minimum temperatuur | {ws['min_temp']}°C |
| Maximum temperatuur | {ws['max_temp']}°C |
| Gemiddelde luchtvochtigheid | {ws.get('avg_humidity', 'N/A')}% |
| Gemiddelde windsnelheid | {ws.get('avg_wind', 'N/A')} m/s |
| Maximale windstoot | {ws.get('max_gust', 'N/A')} m/s |
"""

        if data.get('milestones'):
            markdown += f"""
### Mijlpalen bereikt in {data['year']}

| Mijlpaal | Datum |
|----------|-------|
"""
            for m in data['milestones']:
                markdown += f"| {m['milestone']:,} detecties | {m['date']} |\n"

        if data.get('previous_year'):
            py = data['previous_year']
            markdown += f"""
### Vergelijking met {py['year']}

| Metriek | {py['year']} | {data['year']} | Verschil |
|---------|------|------|----------|
| Detecties | {py['detections']:,} | {data['total_detections']:,} | {py['detection_change']:+.1f}% |
| Soorten | {py['species']} | {data['unique_species']} | {py['species_change']:+d} |
"""

        markdown += f"""
### Projecttotalen

- **Totaal detecties (alle jaren):** {data['project_totals']['total_detections']:,}
- **Totaal soorten (alle jaren):** {data['project_totals']['total_species']}
- **Project gestart:** {data['project_totals']['project_start']}
- **Dual detections {data['year']}:** {data['dual_detections']:,}
- **Detecties per station:**
"""
        for station, count in data['by_station'].items():
            markdown += f"  - {station.capitalize()}: {count:,}\n"

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

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(markdown)

        print(f"Rapport opgeslagen: {filepath}")
        return filepath

    def run(self, year=None):
        """Main execution"""
        print("EMSN Yearly Report Generator")
        print("=" * 60)

        start_date, end_date, year = self.get_year_dates(year)

        print(f"Jaar: {year}")
        print(f"Periode: {start_date.strftime('%Y-%m-%d')} tot {end_date.strftime('%Y-%m-%d')}")

        # Check if year is complete
        if end_date > datetime.now():
            print(f"WAARSCHUWING: Jaar {year} is nog niet afgelopen. Rapport bevat onvolledige data.")

        if not self.connect_db():
            return False

        print("Verzamelen data...")
        data = self.collect_data(start_date, end_date, year)

        if data["total_detections"] == 0:
            print(f"ERROR: Geen detecties gevonden voor {year}")
            return False

        print(f"   - {data['total_detections']:,} detecties")
        print(f"   - {data['unique_species']} soorten")
        print(f"   - {data['dual_detections']:,} dual detections")
        print(f"   - {len(data['monthly_breakdown'])} maanden met data")

        # Fetch species images for top 5 species
        print("Ophalen vogelfoto's...")
        try:
            top_species_for_images = [
                {'name': s['name'], 'scientific_name': s.get('scientific_name', '')}
                for s in data['top_species'][:5]
            ]
            data['species_images'] = get_images_for_species_list(top_species_for_images, max_images=5)
            print(f"   - {len(data['species_images'])} foto's opgehaald")
        except Exception as e:
            print(f"   WARNING: Kon vogelfoto's niet ophalen: {e}")
            data['species_images'] = []

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

        print(f"\nJaaroverzicht succesvol gegenereerd")
        print(f"Bestand: {filepath}")

        self.close_db()
        return True


def main():
    import argparse
    from report_base import get_available_styles

    parser = argparse.ArgumentParser(description='Generate EMSN yearly bird report')
    parser.add_argument('--year', type=int,
                        help='Year to report on (default: previous year)')
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

    generator = YearlyReportGenerator(style=args.style)
    success = generator.run(year=args.year)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
