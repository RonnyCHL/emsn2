#!/usr/bin/env python3
"""
EMSN Seasonal Bird Activity Report Generator
Generates quarterly narrative reports using Claude API

Seasons:
- Winter: December 1 - February 28/29
- Spring: March 1 - May 31
- Summer: June 1 - August 31
- Autumn: September 1 - November 30
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

# Season definitions
SEASONS = {
    'winter': {'months': [12, 1, 2], 'name': 'Winter', 'name_nl': 'Winter'},
    'spring': {'months': [3, 4, 5], 'name': 'Spring', 'name_nl': 'Voorjaar'},
    'summer': {'months': [6, 7, 8], 'name': 'Summer', 'name_nl': 'Zomer'},
    'autumn': {'months': [9, 10, 11], 'name': 'Autumn', 'name_nl': 'Herfst'}
}


class SeasonalReportGenerator(ReportBase):
    """Generate seasonal narrative bird activity reports"""

    def __init__(self, style=None):
        super().__init__()
        self.get_style(style)

    def get_season_dates(self, season=None, year=None):
        """Get start and end dates for a season

        If no season specified, returns the most recently completed season.
        """
        today = datetime.now()

        if season is None:
            # Determine the most recently completed season
            current_month = today.month
            if current_month in [3, 4, 5]:
                # Spring - last completed was Winter
                season = 'winter'
                year = today.year if current_month > 2 else today.year
            elif current_month in [6, 7, 8]:
                # Summer - last completed was Spring
                season = 'spring'
                year = today.year
            elif current_month in [9, 10, 11]:
                # Autumn - last completed was Summer
                season = 'summer'
                year = today.year
            else:  # 12, 1, 2
                # Winter - last completed was Autumn
                season = 'autumn'
                year = today.year if current_month == 12 else today.year - 1

        if year is None:
            year = today.year

        season_info = SEASONS[season]
        months = season_info['months']

        # Handle winter spanning two years
        if season == 'winter':
            # Winter of year X runs Dec X to Feb X+1
            start_date = datetime(year, 12, 1)
            # February end (handle leap year)
            if (year + 1) % 4 == 0 and ((year + 1) % 100 != 0 or (year + 1) % 400 == 0):
                end_date = datetime(year + 1, 2, 29, 23, 59, 59)
            else:
                end_date = datetime(year + 1, 2, 28, 23, 59, 59)
        else:
            start_date = datetime(year, months[0], 1)
            # Last day of the last month
            if months[-1] == 12:
                end_date = datetime(year, 12, 31, 23, 59, 59)
            else:
                next_month = datetime(year, months[-1] + 1, 1)
                end_date = next_month - timedelta(seconds=1)

        return start_date, end_date, season, year

    def collect_data(self, start_date, end_date, season, year):
        """Collect all statistics for the season"""
        cur = self.conn.cursor()

        season_info = SEASONS[season]

        data = {
            "period_start": start_date.strftime('%Y-%m-%d'),
            "period_end": end_date.strftime('%Y-%m-%d'),
            "season": season,
            "season_name": season_info['name_nl'],
            "year": year,
            "display_year": f"{year}/{year+1}" if season == 'winter' else str(year)
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

        # Top 20 species for the season
        cur.execute("""
            SELECT
                common_name,
                species,
                COUNT(*) as count
            FROM bird_detections
            WHERE detection_timestamp BETWEEN %s AND %s
            GROUP BY common_name, species
            ORDER BY count DESC
            LIMIT 20
        """, (start_date, end_date))
        data["top_species"] = [
            {"common_name": row[0], "scientific_name": row[1], "count": row[2]}
            for row in cur.fetchall()
        ]

        # Monthly breakdown
        cur.execute("""
            SELECT
                DATE_TRUNC('month', detection_timestamp) as month,
                COUNT(*) as detections,
                COUNT(DISTINCT species) as species
            FROM bird_detections
            WHERE detection_timestamp BETWEEN %s AND %s
            GROUP BY month
            ORDER BY month
        """, (start_date, end_date))
        data["monthly_breakdown"] = [
            {
                "month": row[0].strftime('%Y-%m'),
                "month_name": row[0].strftime('%B'),
                "detections": row[1],
                "species": row[2]
            }
            for row in cur.fetchall()
        ]

        # Peak detection day
        cur.execute("""
            SELECT
                DATE(detection_timestamp) as day,
                COUNT(*) as count
            FROM bird_detections
            WHERE detection_timestamp BETWEEN %s AND %s
            GROUP BY day
            ORDER BY count DESC
            LIMIT 1
        """, (start_date, end_date))
        result = cur.fetchone()
        if result:
            data["peak_day"] = {
                "date": result[0].strftime('%Y-%m-%d'),
                "count": result[1]
            }

        # Quietest day (with at least some activity)
        cur.execute("""
            SELECT
                DATE(detection_timestamp) as day,
                COUNT(*) as count
            FROM bird_detections
            WHERE detection_timestamp BETWEEN %s AND %s
            GROUP BY day
            HAVING COUNT(*) > 0
            ORDER BY count ASC
            LIMIT 1
        """, (start_date, end_date))
        result = cur.fetchone()
        if result:
            data["quietest_day"] = {
                "date": result[0].strftime('%Y-%m-%d'),
                "count": result[1]
            }

        # Rare/notable sightings (low frequency species with high confidence)
        cur.execute("""
            WITH species_counts AS (
                SELECT species, COUNT(*) as total
                FROM bird_detections
                WHERE detection_timestamp BETWEEN %s AND %s
                GROUP BY species
                HAVING COUNT(*) <= 10
            )
            SELECT
                d.common_name,
                d.species,
                d.detection_timestamp,
                d.confidence,
                d.station,
                sc.total as season_total
            FROM bird_detections d
            JOIN species_counts sc ON d.species = sc.species
            WHERE d.detection_timestamp BETWEEN %s AND %s
            AND d.confidence >= 0.75
            ORDER BY sc.total ASC, d.confidence DESC
            LIMIT 15
        """, (start_date, end_date, start_date, end_date))
        data["rare_sightings"] = [
            {
                "common_name": row[0],
                "scientific_name": row[1],
                "datetime": row[2].strftime('%Y-%m-%d %H:%M'),
                "confidence": float(row[3]),
                "station": row[4],
                "season_total": row[5]
            }
            for row in cur.fetchall()
        ]

        # First and last sightings of notable species (phenology)
        cur.execute("""
            WITH first_last AS (
                SELECT
                    common_name,
                    species,
                    MIN(detection_timestamp) as first_seen,
                    MAX(detection_timestamp) as last_seen,
                    COUNT(*) as total
                FROM bird_detections
                WHERE detection_timestamp BETWEEN %s AND %s
                GROUP BY common_name, species
                HAVING COUNT(*) >= 5
            )
            SELECT * FROM first_last
            ORDER BY total DESC
            LIMIT 30
        """, (start_date, end_date))
        data["phenology"] = [
            {
                "common_name": row[0],
                "scientific_name": row[1],
                "first_seen": row[2].strftime('%Y-%m-%d'),
                "last_seen": row[3].strftime('%Y-%m-%d'),
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

        # Activity by hour (average across season)
        cur.execute("""
            SELECT
                EXTRACT(HOUR FROM detection_timestamp) as hour,
                COUNT(*) as total,
                COUNT(*)::float / (SELECT COUNT(DISTINCT DATE(detection_timestamp))
                                   FROM bird_detections
                                   WHERE detection_timestamp BETWEEN %s AND %s) as daily_avg
            FROM bird_detections
            WHERE detection_timestamp BETWEEN %s AND %s
            GROUP BY hour
            ORDER BY hour
        """, (start_date, end_date, start_date, end_date))
        data["hourly_pattern"] = [
            {
                "hour": int(row[0]),
                "total": row[1],
                "daily_avg": round(row[2], 1)
            }
            for row in cur.fetchall()
        ]

        # Weather statistics for the season
        cur.execute("""
            SELECT
                AVG(temp_outdoor) as avg_temp,
                MIN(temp_outdoor) as min_temp,
                MAX(temp_outdoor) as max_temp,
                AVG(humidity_outdoor) as avg_humidity,
                AVG(wind_speed) as avg_wind,
                MAX(wind_gust_speed) as max_gust,
                SUM(CASE WHEN rain_rate > 0 THEN 1 ELSE 0 END)::float /
                    NULLIF(COUNT(*), 0) * 100 as rain_percentage
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
                "max_gust": round(float(result[5]), 1) if result[5] else None,
                "rain_percentage": round(float(result[6]), 1) if result[6] else None
            }

        # Temperature vs activity correlation
        cur.execute("""
            SELECT
                CASE
                    WHEN w.temp_outdoor < 0 THEN '<0'
                    WHEN w.temp_outdoor < 5 THEN '0-5'
                    WHEN w.temp_outdoor < 10 THEN '5-10'
                    WHEN w.temp_outdoor < 15 THEN '10-15'
                    WHEN w.temp_outdoor < 20 THEN '15-20'
                    WHEN w.temp_outdoor < 25 THEN '20-25'
                    ELSE '25+'
                END as temp_range,
                COUNT(DISTINCT d.id) as detections
            FROM bird_detections d
            JOIN weather_data w ON DATE_TRUNC('hour', d.detection_timestamp) = DATE_TRUNC('hour', w.measurement_timestamp)
            WHERE d.detection_timestamp BETWEEN %s AND %s
            AND w.temp_outdoor IS NOT NULL
            GROUP BY temp_range
            ORDER BY detections DESC
        """, (start_date, end_date))
        data["temp_activity"] = [
            {"range": row[0] + "°C", "detections": row[1]}
            for row in cur.fetchall()
        ]

        # Species accumulation (new species over time)
        cur.execute("""
            WITH daily_new AS (
                SELECT
                    DATE(detection_timestamp) as day,
                    species,
                    ROW_NUMBER() OVER (PARTITION BY species ORDER BY detection_timestamp) as rn
                FROM bird_detections
                WHERE detection_timestamp BETWEEN %s AND %s
            )
            SELECT day, COUNT(*) as new_species
            FROM daily_new
            WHERE rn = 1
            GROUP BY day
            ORDER BY day
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

        # Compare with same season previous year (if data exists)
        prev_start = start_date.replace(year=start_date.year - 1)
        prev_end = end_date.replace(year=end_date.year - 1)

        cur.execute("""
            SELECT COUNT(*), COUNT(DISTINCT species)
            FROM bird_detections
            WHERE detection_timestamp BETWEEN %s AND %s
        """, (prev_start, prev_end))
        result = cur.fetchone()
        if result[0] > 0:
            data["previous_year"] = {
                "detections": result[0],
                "species": result[1],
                "detection_change": round((data["total_detections"] - result[0]) / result[0] * 100, 1),
                "species_change": data["unique_species"] - result[1]
            }

        # Project totals
        cur.execute("SELECT COUNT(*), COUNT(DISTINCT species) FROM bird_detections")
        result = cur.fetchone()
        data["project_totals"] = {
            "total_detections": result[0],
            "total_species": result[1]
        }

        cur.close()
        return data

    def generate_report(self, data):
        """Use Claude API to generate narrative report"""

        style_prompt = self.get_style_prompt()

        prompt = f"""{style_prompt}

Je schrijft een seizoensrapport voor het EMSN vogelmonitoringsproject in Nijverdal, Overijssel.

DATA:
{json.dumps(data, indent=2, ensure_ascii=False)}

STRUCTUUR (gebruik markdown headers):

### Weersomstandigheden en activiteit
- Karakteriseer het seizoen meteorologisch
- Leg verbanden tussen weer en vogelactiviteit
- Vergelijk met normale waarden voor dit seizoen

### Soortenoverzicht
- Beschrijf de dominante soorten en hun aantallen
- Gebruik een markdown tabel voor top 10
- Benoem opvallende aan- of afwezigen
- Bespreek seizoensgebonden patronen (trekvogels, wintergasten, broedvogels)

### Fenologie
- Eerste en laatste waarnemingen van relevante soorten
- Aankomst/vertrek van trekvogels
- Vergelijk met verwachte data

### Bijzondere waarnemingen
- Zeldzame soorten met datum, tijd, confidence
- Context: waarom is deze waarneming bijzonder?
- Gebruik een markdown tabel

### Dagritme en activiteitspatronen
- Piek- en daluren
- Veranderingen door het seizoen heen
- Dual detections analyse

### Seizoensvergelijking
- Vergelijk met vorig jaar indien beschikbaar
- Trends en opvallende verschillen

### Conclusie
- Samenvattende observaties
- Wat vertelt dit seizoen ons over de lokale vogelpopulatie?

LENGTE: 800-1200 woorden

Genereer ALLEEN de inhoud, zonder de titel/header - die wordt automatisch toegevoegd.
"""

        return self.generate_with_claude(prompt, max_tokens=4000)

    def save_report(self, report_text, data):
        """Save report as markdown file"""

        REPORTS_PATH.mkdir(parents=True, exist_ok=True)

        # Filename: 2025-Herfst-Seizoensrapport.md
        filename = f"{data['display_year']}-{data['season_name']}-Seizoensrapport.md"
        filepath = REPORTS_PATH / filename

        # Create markdown with frontmatter
        markdown = f"""---
type: seizoensrapport
season: {data['season']}
season_name: {data['season_name']}
year: {data['display_year']}
period_start: {data['period_start']}
period_end: {data['period_end']}
total_detections: {data['total_detections']}
unique_species: {data['unique_species']}
generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
---

# EMSN Seizoensrapport {data['season_name']} {data['display_year']}

**Locatie:** Nijverdal, Overijssel
**Periode:** {data['period_start']} tot {data['period_end']}
**Stations:** Zolder, Berging
**Detecties:** {data['total_detections']:,} | **Soorten:** {data['unique_species']}

---

{report_text}

---

## Statistische bijlage

### Maandoverzicht

| Maand | Detecties | Soorten |
|-------|-----------|---------|
"""
        for month in data['monthly_breakdown']:
            markdown += f"| {month['month_name']} | {month['detections']:,} | {month['species']} |\n"

        markdown += f"""
### Top 20 soorten

| Rang | Soort | Wetenschappelijk | Detecties |
|------|-------|------------------|-----------|
"""
        for i, species in enumerate(data['top_species'], 1):
            markdown += f"| {i} | {species['common_name']} | *{species['scientific_name']}* | {species['count']:,} |\n"

        if data.get('weather_summary'):
            ws = data['weather_summary']
            markdown += f"""
### Weersamenvatting

| Parameter | Waarde |
|-----------|--------|
| Gemiddelde temperatuur | {ws['avg_temp']}°C |
| Minimum temperatuur | {ws['min_temp']}°C |
| Maximum temperatuur | {ws['max_temp']}°C |
| Gemiddelde luchtvochtigheid | {ws.get('avg_humidity', 'N/A')}% |
| Gemiddelde windsnelheid | {ws.get('avg_wind', 'N/A')} m/s |
| Maximale windstoot | {ws.get('max_gust', 'N/A')} m/s |
| Percentage met neerslag | {ws.get('rain_percentage', 'N/A')}% |
"""

        markdown += f"""
### Activiteit per temperatuurbereik

| Temperatuur | Detecties |
|-------------|-----------|
"""
        for temp in data.get('temp_activity', []):
            markdown += f"| {temp['range']} | {temp['detections']:,} |\n"

        markdown += f"""
### Projecttotalen

- **Totaal detecties (project):** {data['project_totals']['total_detections']:,}
- **Totaal soorten (project):** {data['project_totals']['total_species']}
- **Dual detections dit seizoen:** {data['dual_detections']:,}
"""

        if data.get('previous_year'):
            py = data['previous_year']
            markdown += f"""
### Vergelijking met {data['season_name']} {int(data['year'])-1}

| Metriek | Vorig jaar | Dit jaar | Verschil |
|---------|------------|----------|----------|
| Detecties | {py['detections']:,} | {data['total_detections']:,} | {py['detection_change']:+.1f}% |
| Soorten | {py['species']} | {data['unique_species']} | {py['species_change']:+d} |
"""

        markdown += f"""
---

*Geschreven door Ecologisch Monitoring Systeem Nijverdal - Ronny Hullegie*
*Meetlocatie: Nijverdal, Overijssel (52.36°N, 6.46°E)*
*Volgende seizoensrapport: {self._next_season_name(data['season'])} {self._next_season_year(data['season'], data['year'])}*

**Contact:** emsn@ronnyhullegie.nl | **Website:** www.ronnyhullegie.nl

© {data['year']} Ronny Hullegie. Alle rechten voorbehouden.
Licentie: CC BY-NC 4.0 (gebruik toegestaan met bronvermelding, niet commercieel)
"""

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(markdown)

        print(f"Rapport opgeslagen: {filepath}")
        return filepath

    def _next_season_name(self, current_season):
        """Get next season name"""
        order = ['winter', 'spring', 'summer', 'autumn']
        idx = order.index(current_season)
        next_season = order[(idx + 1) % 4]
        return SEASONS[next_season]['name_nl']

    def _next_season_year(self, current_season, current_year):
        """Get next season year"""
        if current_season == 'autumn':
            return f"{current_year}/{current_year + 1}"
        elif current_season == 'winter':
            return str(current_year + 1)
        else:
            return str(current_year)

    def run(self, season=None, year=None):
        """Main execution"""
        print("EMSN Seasonal Report Generator")
        print("=" * 60)

        # Get season dates
        start_date, end_date, season, year = self.get_season_dates(season, year)
        season_name = SEASONS[season]['name_nl']

        print(f"Seizoen: {season_name} {year}")
        print(f"Periode: {start_date.strftime('%Y-%m-%d')} tot {end_date.strftime('%Y-%m-%d')}")

        # Check if we have data for this period
        if end_date > datetime.now():
            print(f"WAARSCHUWING: Seizoen is nog niet afgelopen. Rapport bevat onvolledige data.")

        # Connect to database
        if not self.connect_db():
            return False

        print("Verzamelen data...")
        data = self.collect_data(start_date, end_date, season, year)

        if data["total_detections"] == 0:
            print(f"ERROR: Geen detecties gevonden voor {season_name} {year}")
            return False

        print(f"   - {data['total_detections']:,} detecties")
        print(f"   - {data['unique_species']} soorten")
        print(f"   - {data['dual_detections']:,} dual detections")

        # Generate report with Claude
        print("Genereren rapport met Claude AI...")
        report = self.generate_report(data)

        if not report:
            print("ERROR: Rapport generatie mislukt")
            return False

        print(f"   - {len(report)} karakters gegenereerd")

        # Save report
        print("Opslaan rapport...")
        filepath = self.save_report(report, data)

        # Update web index
        print("Bijwerken web index...")
        self.update_web_index()

        print(f"\nSeizoenrapport succesvol gegenereerd")
        print(f"Bestand: {filepath}")

        self.close_db()
        return True


def main():
    import argparse
    from report_base import get_available_styles

    parser = argparse.ArgumentParser(description='Generate EMSN seasonal bird report')
    parser.add_argument('--season', choices=['winter', 'spring', 'summer', 'autumn'],
                        help='Season to report on (default: most recent completed)')
    parser.add_argument('--year', type=int,
                        help='Year for the season (default: current/previous year)')
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

    generator = SeasonalReportGenerator(style=args.style)
    success = generator.run(season=args.season, year=args.year)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
