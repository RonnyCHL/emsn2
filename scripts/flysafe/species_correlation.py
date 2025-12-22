#!/usr/bin/env python3
"""
FlySafe Species-Radar Correlation Analysis
==========================================

Analyzes which bird species correlate most strongly with
radar migration intensity.

Features:
- Per-species correlation with radar data
- Species grouping (thrushes, geese, waders, etc.)
- Migration timing per species
- Detection confidence analysis

Author: EMSN Team
"""

import os
import json
from datetime import datetime, timedelta
from pathlib import Path
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from collections import defaultdict

# Import secrets
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'config'))
try:
    from emsn_secrets import get_postgres_config
    _pg = get_postgres_config()
except ImportError:
    _pg = {'host': '192.168.1.25', 'port': 5433, 'database': 'emsn',
           'user': 'birdpi_zolder', 'password': os.getenv('EMSN_DB_PASSWORD', '')}

# Configuration (from secrets)
DB_CONFIG = {
    'host': _pg.get('host', '192.168.1.25'),
    'port': _pg.get('port', 5433),
    'database': _pg.get('database', 'emsn'),
    'user': _pg.get('user', 'birdpi_zolder'),
    'password': _pg.get('password', '') or os.getenv('EMSN_DB_PASSWORD', '')
}

LOGS_DIR = Path("/mnt/usb/logs")
REPORTS_DIR = Path("/mnt/usb/flysafe/reports")

# Species groups for aggregated analysis
SPECIES_GROUPS = {
    'Lijsters': [
        'Turdus pilaris',      # Kramsvogel
        'Turdus iliacus',      # Koperwiek
        'Turdus philomelos',   # Zanglijster
        'Turdus viscivorus',   # Grote Lijster
    ],
    'Ganzen': [
        'Anser anser',         # Grauwe gans
        'Branta leucopsis',    # Brandgans
        'Anser albifrons',     # Kolgans
        'Branta canadensis',   # Canadese gans
        'Anser fabalis',       # Taigarietgans
    ],
    'Vinken': [
        'Fringilla coelebs',   # Vink
        'Fringilla montifringilla', # Keep
        'Carduelis carduelis', # Putter
        'Carduelis spinus',    # Sijs
    ],
    'Kraaiachtigen': [
        'Corvus frugilegus',   # Roek
        'Corvus monedula',     # Kauw
        'Corvus corone',       # Zwarte kraai
    ],
    'Steltlopers': [
        'Vanellus vanellus',   # Kievit
        'Pluvialis apricaria', # Goudplevier
        'Numenius arquata',    # Wulp
    ],
    'Roofvogels': [
        'Buteo buteo',         # Buizerd
        'Accipiter nisus',     # Sperwer
        'Falco tinnunculus',   # Torenvalk
    ],
    'Duiven': [
        'Columba palumbus',    # Houtduif
        'Streptopelia decaocto', # Turkse tortel
    ],
    'Meeuwen': [
        'Larus canus',         # Stormmeeuw
        'Larus argentatus',    # Zilvermeeuw
        'Chroicocephalus ridibundus', # Kokmeeuw
    ]
}

# Flatten for easy lookup
SPECIES_TO_GROUP = {}
for group, species_list in SPECIES_GROUPS.items():
    for sp in species_list:
        SPECIES_TO_GROUP[sp] = group

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOGS_DIR / "species-correlation.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class SpeciesCorrelationAnalyzer:
    """Analyzes species-specific radar correlations"""

    def __init__(self):
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    def get_db_connection(self):
        """Create database connection"""
        return psycopg2.connect(**DB_CONFIG)

    def get_species_radar_correlation(self, days=30, min_detections=5):
        """
        Calculate correlation between each species and radar intensity

        Returns species ranked by correlation strength
        """
        try:
            conn = self.get_db_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)

            query = """
                WITH radar_hourly AS (
                    -- Aggregate radar to hourly for better matching
                    SELECT
                        observation_date,
                        DATE_TRUNC('hour', observation_time)::time as hour,
                        AVG(intensity_level) as intensity
                    FROM radar_observations
                    WHERE observation_date >= CURRENT_DATE - INTERVAL '%s days'
                    GROUP BY observation_date, DATE_TRUNC('hour', observation_time)
                ),
                species_hourly AS (
                    -- Count detections per species per hour
                    SELECT
                        date,
                        DATE_TRUNC('hour', time)::time as hour,
                        species,
                        common_name,
                        COUNT(*) as detections,
                        AVG(confidence) as avg_confidence
                    FROM bird_detections
                    WHERE date >= CURRENT_DATE - INTERVAL '%s days'
                      AND confidence >= 0.7
                    GROUP BY date, DATE_TRUNC('hour', time), species, common_name
                )
                SELECT
                    sh.species,
                    sh.common_name,
                    COUNT(*) as data_points,
                    SUM(sh.detections) as total_detections,
                    AVG(sh.avg_confidence) as avg_confidence,
                    AVG(rh.intensity) as avg_radar_intensity,
                    -- Pearson correlation coefficient
                    CORR(sh.detections::float, rh.intensity) as correlation,
                    -- Additional stats
                    STDDEV(sh.detections) as detection_stddev,
                    MAX(sh.detections) as max_hourly_detections
                FROM species_hourly sh
                JOIN radar_hourly rh
                    ON sh.date = rh.observation_date
                    AND sh.hour = rh.hour
                GROUP BY sh.species, sh.common_name
                HAVING SUM(sh.detections) >= %s
                ORDER BY correlation DESC NULLS LAST
            """

            cur.execute(query, (days, days, min_detections))
            results = cur.fetchall()
            conn.close()

            return results

        except Exception as e:
            logger.error(f"Failed to get species correlation: {e}")
            return []

    def get_group_correlations(self, days=30):
        """
        Calculate correlation for species groups
        """
        try:
            conn = self.get_db_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)

            # Get all detections with radar match
            query = """
                WITH radar_hourly AS (
                    SELECT
                        observation_date,
                        DATE_TRUNC('hour', observation_time)::time as hour,
                        AVG(intensity_level) as intensity
                    FROM radar_observations
                    WHERE observation_date >= CURRENT_DATE - INTERVAL '%s days'
                    GROUP BY observation_date, DATE_TRUNC('hour', observation_time)
                )
                SELECT
                    bd.species,
                    bd.date,
                    DATE_TRUNC('hour', bd.time)::time as hour,
                    COUNT(*) as detections,
                    rh.intensity
                FROM bird_detections bd
                JOIN radar_hourly rh
                    ON bd.date = rh.observation_date
                    AND DATE_TRUNC('hour', bd.time)::time = rh.hour
                WHERE bd.date >= CURRENT_DATE - INTERVAL '%s days'
                  AND bd.confidence >= 0.7
                GROUP BY bd.species, bd.date, DATE_TRUNC('hour', bd.time), rh.intensity
            """

            cur.execute(query, (days, days))
            results = cur.fetchall()
            conn.close()

            # Aggregate by group
            group_data = defaultdict(lambda: {'detections': [], 'intensities': []})

            for row in results:
                species = row['species']
                group = SPECIES_TO_GROUP.get(species, 'Overig')
                group_data[group]['detections'].append(float(row['detections']))
                group_data[group]['intensities'].append(float(row['intensity'] or 0))

            # Calculate correlation per group
            group_correlations = []
            for group, data in group_data.items():
                if len(data['detections']) >= 5:
                    # Calculate Pearson correlation manually
                    n = len(data['detections'])
                    sum_x = sum(data['detections'])
                    sum_y = sum(data['intensities'])
                    sum_xy = sum(x * y for x, y in zip(data['detections'], data['intensities']))
                    sum_x2 = sum(x ** 2 for x in data['detections'])
                    sum_y2 = sum(y ** 2 for y in data['intensities'])

                    numerator = n * sum_xy - sum_x * sum_y
                    denominator = ((n * sum_x2 - sum_x ** 2) * (n * sum_y2 - sum_y ** 2)) ** 0.5

                    correlation = numerator / denominator if denominator != 0 else 0

                    group_correlations.append({
                        'group': group,
                        'data_points': n,
                        'total_detections': int(sum_x),
                        'correlation': round(correlation, 4),
                        'avg_intensity_when_detected': round(sum_y / n, 1)
                    })

            return sorted(group_correlations, key=lambda x: x['correlation'], reverse=True)

        except Exception as e:
            logger.error(f"Failed to get group correlations: {e}")
            return []

    def get_nocturnal_vs_diurnal(self, days=30):
        """
        Compare species correlation during day vs night
        Night: 20:00 - 06:00 (peak migration time)
        """
        try:
            conn = self.get_db_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)

            query = """
                WITH radar_with_period AS (
                    SELECT
                        observation_date,
                        observation_time,
                        intensity_level,
                        CASE
                            WHEN EXTRACT(HOUR FROM observation_time) >= 20
                              OR EXTRACT(HOUR FROM observation_time) < 6
                            THEN 'night'
                            ELSE 'day'
                        END as period
                    FROM radar_observations
                    WHERE observation_date >= CURRENT_DATE - INTERVAL '%s days'
                ),
                birds_with_period AS (
                    SELECT
                        species,
                        common_name,
                        date,
                        time,
                        confidence,
                        CASE
                            WHEN EXTRACT(HOUR FROM time) >= 20
                              OR EXTRACT(HOUR FROM time) < 6
                            THEN 'night'
                            ELSE 'day'
                        END as period
                    FROM bird_detections
                    WHERE date >= CURRENT_DATE - INTERVAL '%s days'
                      AND confidence >= 0.7
                )
                SELECT
                    bp.species,
                    bp.common_name,
                    bp.period,
                    COUNT(*) as detections,
                    AVG(rp.intensity_level) as avg_radar_intensity
                FROM birds_with_period bp
                JOIN radar_with_period rp
                    ON bp.date = rp.observation_date
                    AND bp.period = rp.period
                GROUP BY bp.species, bp.common_name, bp.period
                HAVING COUNT(*) >= 5
                ORDER BY bp.species, bp.period
            """

            cur.execute(query, (days, days))
            results = cur.fetchall()
            conn.close()

            # Restructure for comparison
            species_periods = defaultdict(dict)
            for row in results:
                sp = row['common_name'] or row['species']
                period = row['period']
                species_periods[sp][period] = {
                    'detections': row['detections'],
                    'avg_radar': float(row['avg_radar_intensity'] or 0)
                }

            # Calculate night/day ratio
            comparisons = []
            for species, periods in species_periods.items():
                if 'night' in periods and 'day' in periods:
                    night_det = periods['night']['detections']
                    day_det = periods['day']['detections']
                    ratio = night_det / day_det if day_det > 0 else float('inf')

                    comparisons.append({
                        'species': species,
                        'night_detections': night_det,
                        'day_detections': day_det,
                        'night_day_ratio': round(ratio, 2),
                        'night_radar_avg': periods['night']['avg_radar'],
                        'day_radar_avg': periods['day']['avg_radar'],
                        'primarily_nocturnal': ratio > 1.5
                    })

            return sorted(comparisons, key=lambda x: x['night_day_ratio'], reverse=True)

        except Exception as e:
            logger.error(f"Failed to get nocturnal comparison: {e}")
            return []

    def get_peak_migration_species(self, days=30):
        """
        Find which species are detected most during high radar intensity
        """
        try:
            conn = self.get_db_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)

            query = """
                WITH high_intensity_periods AS (
                    SELECT observation_date, observation_time
                    FROM radar_observations
                    WHERE observation_date >= CURRENT_DATE - INTERVAL '%s days'
                      AND intensity_level >= 50
                )
                SELECT
                    bd.species,
                    bd.common_name,
                    COUNT(*) as detections_during_high_radar,
                    AVG(bd.confidence) as avg_confidence
                FROM bird_detections bd
                JOIN high_intensity_periods hip
                    ON bd.date = hip.observation_date
                    AND ABS(EXTRACT(EPOCH FROM (bd.time - hip.observation_time::time))) < 7200
                WHERE bd.date >= CURRENT_DATE - INTERVAL '%s days'
                  AND bd.confidence >= 0.7
                GROUP BY bd.species, bd.common_name
                ORDER BY detections_during_high_radar DESC
                LIMIT 20
            """

            cur.execute(query, (days, days))
            results = cur.fetchall()
            conn.close()

            return results

        except Exception as e:
            logger.error(f"Failed to get peak migration species: {e}")
            return []

    def generate_report(self, days=30):
        """Generate comprehensive species correlation report"""
        logger.info(f"Generating species correlation report for last {days} days")

        report = {
            'generated_at': datetime.now().isoformat(),
            'period_days': days,
            'species_correlations': [],
            'group_correlations': [],
            'nocturnal_analysis': [],
            'peak_migration_species': [],
            'summary': {}
        }

        # Individual species correlations
        species_corr = self.get_species_radar_correlation(days)
        report['species_correlations'] = [dict(row) for row in species_corr]

        # Group correlations
        group_corr = self.get_group_correlations(days)
        report['group_correlations'] = group_corr

        # Nocturnal vs diurnal
        nocturnal = self.get_nocturnal_vs_diurnal(days)
        report['nocturnal_analysis'] = nocturnal

        # Peak migration species
        peak_species = self.get_peak_migration_species(days)
        report['peak_migration_species'] = [dict(row) for row in peak_species]

        # Summary
        if species_corr:
            positive_corr = [s for s in species_corr if s['correlation'] and s['correlation'] > 0.3]
            report['summary']['species_with_positive_correlation'] = len(positive_corr)
            if positive_corr:
                report['summary']['top_correlated_species'] = positive_corr[0]['common_name'] or positive_corr[0]['species']

        if group_corr:
            report['summary']['top_correlated_group'] = group_corr[0]['group']
            report['summary']['group_correlation'] = group_corr[0]['correlation']

        if nocturnal:
            nocturnal_species = [n for n in nocturnal if n['primarily_nocturnal']]
            report['summary']['nocturnal_migrants'] = len(nocturnal_species)

        # Save report
        report_file = REPORTS_DIR / f"species_correlation_{datetime.now().strftime('%Y%m%d')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)

        logger.info(f"Report saved to {report_file}")
        return report

    def print_report(self, report):
        """Print human-readable report"""
        print("\n" + "="*70)
        print("  SOORT-SPECIFIEKE RADAR CORRELATIE")
        print("="*70)

        # Top correlated species
        print("\n🔝 Top Soorten met Radar Correlatie:")
        print("-"*70)
        for sp in report['species_correlations'][:15]:
            corr = sp['correlation']
            if corr:
                name = sp['common_name'] or sp['species']
                bar_len = int(abs(corr) * 20)
                if corr > 0:
                    bar = '+' * bar_len
                    indicator = '📈'
                else:
                    bar = '-' * bar_len
                    indicator = '📉'
                print(f"  {indicator} {name:30} r={corr:+.3f} [{bar:20}] ({sp['total_detections']} det)")

        # Group correlations
        if report['group_correlations']:
            print("\n📊 Soortgroep Correlaties:")
            print("-"*70)
            for g in report['group_correlations']:
                corr = g['correlation']
                indicator = '🟢' if corr > 0.3 else '🟡' if corr > 0 else '🔴'
                print(f"  {indicator} {g['group']:20} r={corr:+.4f} ({g['total_detections']} detecties)")

        # Nocturnal analysis
        if report['nocturnal_analysis']:
            print("\n🌙 Nacht vs Dag Analyse:")
            print("-"*70)
            nocturnal = [n for n in report['nocturnal_analysis'] if n['primarily_nocturnal']][:10]
            if nocturnal:
                print("  Voornamelijk nachtelijke trekkers:")
                for n in nocturnal:
                    print(f"    • {n['species']:25} Nacht/Dag ratio: {n['night_day_ratio']:.1f}x")

        # Peak migration species
        if report['peak_migration_species']:
            print("\n⚡ Meest Actief bij Hoge Radar Intensiteit:")
            print("-"*70)
            for sp in report['peak_migration_species'][:10]:
                name = sp['common_name'] or sp['species']
                print(f"  • {name:30} {sp['detections_during_high_radar']} detecties")

        print("\n" + "="*70 + "\n")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='FlySafe Species-Radar Correlation Analysis')
    parser.add_argument('--days', type=int, default=30, help='Number of days to analyze')
    parser.add_argument('--json', action='store_true', help='Output raw JSON')

    args = parser.parse_args()

    analyzer = SpeciesCorrelationAnalyzer()
    report = analyzer.generate_report(days=args.days)

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        analyzer.print_report(report)


if __name__ == '__main__':
    main()
