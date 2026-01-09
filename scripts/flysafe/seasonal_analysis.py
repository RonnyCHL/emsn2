#!/usr/bin/env python3
"""
FlySafe Seasonal Migration Analysis
====================================

Analyzes bird migration patterns across seasons by combining
radar data with BirdNET detections.

Features:
- Peak migration day identification
- Species correlation with radar intensity
- Seasonal patterns and trends
- Migration prediction insights

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

# Import core modules
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.config import get_postgres_config

# Configuration (from core module)
DB_CONFIG = get_postgres_config()

LOGS_DIR = Path("/mnt/usb/logs")
REPORTS_DIR = Path("/mnt/usb/flysafe/reports")

# Known migratory species in Netherlands
MIGRATORY_SPECIES = [
    # Lijsters (Thrushes)
    'Turdus pilaris',      # Kramsvogel
    'Turdus iliacus',      # Koperwiek
    'Turdus philomelos',   # Zanglijster
    'Turdus merula',       # Merel (partial migrant)

    # Ganzen (Geese)
    'Anser anser',         # Grauwe gans
    'Branta leucopsis',    # Brandgans
    'Anser albifrons',     # Kolgans

    # Steltlopers (Waders)
    'Vanellus vanellus',   # Kievit
    'Pluvialis apricaria', # Goudplevier

    # Zangvogels (Songbirds)
    'Fringilla coelebs',   # Vink
    'Fringilla montifringilla', # Keep
    'Alauda arvensis',     # Veldleeuwerik
    'Anthus pratensis',    # Graspieper
    'Sturnus vulgaris',    # Spreeuw

    # Roofvogels (Raptors)
    'Buteo buteo',         # Buizerd
    'Accipiter nisus',     # Sperwer

    # Kraaiachtigen (Corvids)
    'Corvus frugilegus',   # Roek
]

# Centrale logger
from core.logging import get_logger
logger = get_logger('flysafe_seasonal_analysis')


class SeasonalAnalyzer:
    """Analyzes seasonal bird migration patterns"""

    def __init__(self):
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    def get_db_connection(self):
        """Create database connection"""
        return psycopg2.connect(**DB_CONFIG)

    def get_peak_migration_days(self, days=90):
        """
        Identify days with highest migration activity
        Based on radar intensity + bird detection counts
        """
        try:
            conn = self.get_db_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)

            query = """
                WITH daily_stats AS (
                    SELECT
                        observation_date,
                        AVG(intensity_level) as avg_intensity,
                        MAX(intensity_level) as max_intensity,
                        SUM(bird_detections_count) as total_detections,
                        COUNT(*) as observations
                    FROM radar_observations
                    WHERE observation_date >= CURRENT_DATE - INTERVAL '%s days'
                    GROUP BY observation_date
                ),
                bird_daily AS (
                    SELECT
                        date,
                        COUNT(*) as birdnet_detections,
                        COUNT(DISTINCT species) as species_count
                    FROM bird_detections
                    WHERE date >= CURRENT_DATE - INTERVAL '%s days'
                    GROUP BY date
                )
                SELECT
                    ds.observation_date as date,
                    ds.avg_intensity,
                    ds.max_intensity,
                    ds.total_detections as radar_correlations,
                    ds.observations,
                    COALESCE(bd.birdnet_detections, 0) as birdnet_total,
                    COALESCE(bd.species_count, 0) as species_diversity,
                    -- Combined migration score
                    (ds.avg_intensity * 0.4 +
                     LEAST(ds.max_intensity, 100) * 0.3 +
                     LEAST(COALESCE(bd.birdnet_detections, 0) / 10.0, 100) * 0.3) as migration_score
                FROM daily_stats ds
                LEFT JOIN bird_daily bd ON ds.observation_date = bd.date
                ORDER BY migration_score DESC
                LIMIT 20
            """

            cur.execute(query, (days, days))
            results = cur.fetchall()
            conn.close()

            return results

        except Exception as e:
            logger.error(f"Failed to get peak migration days: {e}")
            return []

    def get_species_radar_correlation(self, days=90):
        """
        Calculate which species correlate most with radar migration intensity
        """
        try:
            conn = self.get_db_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)

            query = """
                WITH radar_daily AS (
                    SELECT
                        observation_date,
                        AVG(intensity_level) as avg_intensity
                    FROM radar_observations
                    WHERE observation_date >= CURRENT_DATE - INTERVAL '%s days'
                    GROUP BY observation_date
                ),
                species_daily AS (
                    SELECT
                        date,
                        species,
                        common_name,
                        COUNT(*) as detections
                    FROM bird_detections
                    WHERE date >= CURRENT_DATE - INTERVAL '%s days'
                      AND confidence >= 0.7
                    GROUP BY date, species, common_name
                )
                SELECT
                    sd.species,
                    sd.common_name,
                    COUNT(DISTINCT sd.date) as days_detected,
                    SUM(sd.detections) as total_detections,
                    AVG(sd.detections) as avg_daily_detections,
                    AVG(rd.avg_intensity) as avg_radar_when_detected,
                    -- Simple correlation proxy
                    CORR(sd.detections::float, rd.avg_intensity) as correlation
                FROM species_daily sd
                JOIN radar_daily rd ON sd.date = rd.observation_date
                GROUP BY sd.species, sd.common_name
                HAVING COUNT(DISTINCT sd.date) >= 3
                ORDER BY correlation DESC NULLS LAST
                LIMIT 30
            """

            cur.execute(query, (days, days))
            results = cur.fetchall()
            conn.close()

            return results

        except Exception as e:
            logger.error(f"Failed to get species correlation: {e}")
            return []

    def get_hourly_patterns(self, days=30):
        """Analyze migration patterns by hour of day"""
        try:
            conn = self.get_db_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)

            query = """
                SELECT
                    EXTRACT(HOUR FROM observation_time) as hour,
                    AVG(intensity_level) as avg_intensity,
                    MAX(intensity_level) as max_intensity,
                    COUNT(*) as observations,
                    AVG(bird_detections_count) as avg_detections
                FROM radar_observations
                WHERE observation_date >= CURRENT_DATE - INTERVAL '%s days'
                GROUP BY EXTRACT(HOUR FROM observation_time)
                ORDER BY hour
            """

            cur.execute(query, (days,))
            results = cur.fetchall()
            conn.close()

            return results

        except Exception as e:
            logger.error(f"Failed to get hourly patterns: {e}")
            return []

    def get_migratory_species_stats(self, days=90):
        """Get statistics for known migratory species"""
        try:
            conn = self.get_db_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)

            # Create species list for query
            species_list = tuple(MIGRATORY_SPECIES)

            query = """
                SELECT
                    species,
                    common_name,
                    COUNT(*) as total_detections,
                    COUNT(DISTINCT date) as days_detected,
                    MIN(date) as first_detection,
                    MAX(date) as last_detection,
                    AVG(confidence) as avg_confidence
                FROM bird_detections
                WHERE species IN %s
                  AND date >= CURRENT_DATE - INTERVAL '%s days'
                  AND confidence >= 0.7
                GROUP BY species, common_name
                ORDER BY total_detections DESC
            """

            cur.execute(query, (species_list, days))
            results = cur.fetchall()
            conn.close()

            return results

        except Exception as e:
            logger.error(f"Failed to get migratory species stats: {e}")
            return []

    def get_weekly_trends(self, weeks=12):
        """Get weekly migration trends"""
        try:
            conn = self.get_db_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)

            query = """
                WITH weekly_radar AS (
                    SELECT
                        DATE_TRUNC('week', observation_date) as week_start,
                        AVG(intensity_level) as avg_intensity,
                        MAX(intensity_level) as max_intensity,
                        SUM(bird_detections_count) as total_correlations
                    FROM radar_observations
                    WHERE observation_date >= CURRENT_DATE - INTERVAL '%s weeks'
                    GROUP BY DATE_TRUNC('week', observation_date)
                ),
                weekly_birds AS (
                    SELECT
                        DATE_TRUNC('week', date) as week_start,
                        COUNT(*) as bird_detections,
                        COUNT(DISTINCT species) as species_count
                    FROM bird_detections
                    WHERE date >= CURRENT_DATE - INTERVAL '%s weeks'
                      AND confidence >= 0.7
                    GROUP BY DATE_TRUNC('week', date)
                )
                SELECT
                    wr.week_start,
                    wr.avg_intensity,
                    wr.max_intensity,
                    wr.total_correlations,
                    COALESCE(wb.bird_detections, 0) as bird_detections,
                    COALESCE(wb.species_count, 0) as species_count
                FROM weekly_radar wr
                LEFT JOIN weekly_birds wb ON wr.week_start = wb.week_start
                ORDER BY wr.week_start
            """

            cur.execute(query, (weeks, weeks))
            results = cur.fetchall()
            conn.close()

            return results

        except Exception as e:
            logger.error(f"Failed to get weekly trends: {e}")
            return []

    def generate_report(self, days=90):
        """Generate comprehensive seasonal analysis report"""
        logger.info(f"Generating seasonal analysis report for last {days} days")

        report = {
            'generated_at': datetime.now().isoformat(),
            'period_days': days,
            'peak_migration_days': [],
            'species_correlations': [],
            'hourly_patterns': [],
            'migratory_species': [],
            'weekly_trends': [],
            'summary': {}
        }

        # Peak migration days
        peak_days = self.get_peak_migration_days(days)
        report['peak_migration_days'] = [dict(row) for row in peak_days]

        # Species correlations
        correlations = self.get_species_radar_correlation(days)
        report['species_correlations'] = [dict(row) for row in correlations]

        # Hourly patterns
        hourly = self.get_hourly_patterns(min(days, 30))
        report['hourly_patterns'] = [dict(row) for row in hourly]

        # Migratory species
        migratory = self.get_migratory_species_stats(days)
        report['migratory_species'] = [dict(row) for row in migratory]

        # Weekly trends
        weekly = self.get_weekly_trends(days // 7)
        report['weekly_trends'] = [dict(row) for row in weekly]

        # Summary
        if peak_days:
            report['summary']['top_migration_day'] = str(peak_days[0]['date'])
            report['summary']['top_migration_score'] = float(peak_days[0]['migration_score'] or 0)

        if correlations:
            top_correlated = [c for c in correlations if c['correlation'] and c['correlation'] > 0.3]
            report['summary']['top_correlated_species'] = [c['common_name'] or c['species'] for c in top_correlated[:5]]

        if migratory:
            report['summary']['migratory_species_detected'] = len(migratory)
            report['summary']['total_migratory_detections'] = sum(m['total_detections'] for m in migratory)

        # Save report
        report_file = REPORTS_DIR / f"seasonal_analysis_{datetime.now().strftime('%Y%m%d')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)

        logger.info(f"Report saved to {report_file}")
        return report

    def print_summary(self, report):
        """Print human-readable summary"""
        print("\n" + "="*70)
        print("  SEIZOENSANALYSE VOGELTREK")
        print("="*70)

        summary = report.get('summary', {})

        if 'top_migration_day' in summary:
            print(f"\n📅 Piek Migratiedag: {summary['top_migration_day']}")
            print(f"   Score: {summary['top_migration_score']:.1f}")

        print("\n🔝 Top 5 Piek Dagen:")
        print("-"*70)
        for i, day in enumerate(report['peak_migration_days'][:5], 1):
            print(f"  {i}. {day['date']} - Score: {day['migration_score']:.1f}")
            print(f"     Radar: {day['avg_intensity']:.0f}% | BirdNET: {day['birdnet_total']} | Soorten: {day['species_diversity']}")

        if report['species_correlations']:
            print("\n🐦 Soorten met Hoogste Radar Correlatie:")
            print("-"*70)
            for sp in report['species_correlations'][:10]:
                corr = sp['correlation']
                if corr and corr > 0:
                    name = sp['common_name'] or sp['species']
                    print(f"  • {name}: r={corr:.3f} ({sp['total_detections']} detecties)")

        if report['migratory_species']:
            print("\n✈️ Trekvogels Gedetecteerd:")
            print("-"*70)
            for sp in report['migratory_species'][:10]:
                name = sp['common_name'] or sp['species']
                print(f"  • {name}: {sp['total_detections']} detecties op {sp['days_detected']} dagen")

        if report['hourly_patterns']:
            print("\n⏰ Piek Uren (Radar Intensiteit):")
            print("-"*70)
            sorted_hours = sorted(report['hourly_patterns'],
                                  key=lambda x: x['avg_intensity'] or 0, reverse=True)
            for h in sorted_hours[:5]:
                print(f"  {int(h['hour']):02d}:00 - Gem: {h['avg_intensity']:.1f}% | Max: {h['max_intensity']}%")

        print("\n" + "="*70 + "\n")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='FlySafe Seasonal Migration Analysis')
    parser.add_argument('--days', type=int, default=90, help='Number of days to analyze')
    parser.add_argument('--json', action='store_true', help='Output raw JSON')
    parser.add_argument('--save', action='store_true', help='Save report to file')

    args = parser.parse_args()

    analyzer = SeasonalAnalyzer()
    report = analyzer.generate_report(days=args.days)

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        analyzer.print_summary(report)


if __name__ == '__main__':
    main()
