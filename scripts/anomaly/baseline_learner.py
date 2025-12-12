#!/usr/bin/env python3
"""
EMSN 2.0 - Species Baseline Learning

Analyzes historical detection data to create baselines for each species:
- Active months (seasonal patterns)
- Active hours (diurnal patterns)
- Average confidence
- Average daily detection count

Runs weekly to update baselines as more data accumulates.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import execute_batch
from collections import Counter

# Add config path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'config'))
from station_config import POSTGRES_CONFIG, POSTGRES_USERS

# Configuration
LOOKBACK_DAYS = 365
MIN_DETECTIONS_FOR_BASELINE = 20
MIN_MONTH_DETECTIONS = 5  # Month is "active" if >= 5 detections in that month
MIN_HOUR_DETECTIONS = 3   # Hour is "active" if >= 3 detections in that hour

class BaselineLearner:
    """Learn species baselines from historical data"""

    def __init__(self):
        self.conn = None
        self.log_entries = []

    def connect(self):
        """Connect to PostgreSQL"""
        try:
            self.conn = psycopg2.connect(
                host=POSTGRES_CONFIG['host'],
                port=POSTGRES_CONFIG['port'],
                database=POSTGRES_CONFIG['database'],
                user='postgres',
                password='REDACTED_DB_PASS'
            )
            self.log("INFO", "Connected to database")
            return True
        except Exception as e:
            self.log("ERROR", f"Database connection failed: {e}")
            return False

    def log(self, level, message):
        """Log message"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        entry = f"[{timestamp}] [{level}] {message}"
        print(entry)
        self.log_entries.append(entry)

    def get_species_detections(self, lookback_days=LOOKBACK_DAYS):
        """Get all species with their detections from last N days"""
        cursor = self.conn.cursor()

        query = """
            SELECT
                common_name,
                species,
                detection_timestamp,
                confidence
            FROM bird_detections
            WHERE detection_timestamp >= NOW() - INTERVAL '%s days'
              AND common_name IS NOT NULL
            ORDER BY common_name, detection_timestamp
        """

        cursor.execute(query, (lookback_days,))
        return cursor.fetchall()

    def calculate_baseline(self, species_detections):
        """
        Calculate baseline for a single species

        Args:
            species_detections: List of (common_name, species, timestamp, confidence)

        Returns:
            Dictionary with baseline metrics or None if insufficient data
        """
        if len(species_detections) < MIN_DETECTIONS_FOR_BASELINE:
            return None

        common_name = species_detections[0][0]
        species = species_detections[0][1]

        # Extract metrics
        months = [dt[2].month for dt in species_detections]
        hours = [dt[2].hour for dt in species_detections]
        confidences = [dt[3] for dt in species_detections]
        dates = [dt[2].date() for dt in species_detections]

        # Calculate active months (months with >= MIN_MONTH_DETECTIONS)
        month_counts = Counter(months)
        months_active = sorted([m for m, count in month_counts.items()
                               if count >= MIN_MONTH_DETECTIONS])

        # Calculate active hours (hours with >= MIN_HOUR_DETECTIONS)
        hour_counts = Counter(hours)
        hours_active = sorted([h for h, count in hour_counts.items()
                              if count >= MIN_HOUR_DETECTIONS])

        # Calculate average confidence
        avg_confidence = sum(confidences) / len(confidences)

        # Calculate daily detection statistics
        unique_days = len(set(dates))
        daily_counts = Counter(dates)
        daily_count_values = list(daily_counts.values())

        avg_daily_count = len(species_detections) / unique_days if unique_days > 0 else 0
        min_daily_count = min(daily_count_values) if daily_count_values else 0
        max_daily_count = max(daily_count_values) if daily_count_values else 0

        # First and last seen dates
        first_seen = min(dates)
        last_seen = max(dates)

        return {
            'species_nl': common_name,
            'species_scientific': species,
            'months_active': months_active,
            'hours_active': hours_active,
            'avg_confidence': avg_confidence,
            'avg_daily_count': avg_daily_count,
            'min_daily_count': min_daily_count,
            'max_daily_count': max_daily_count,
            'detection_count': len(species_detections),
            'first_seen': first_seen,
            'last_seen': last_seen,
        }

    def update_baselines(self):
        """Calculate and update all species baselines"""
        self.log("INFO", f"Starting baseline learning (lookback: {LOOKBACK_DAYS} days)")

        # Get all detections grouped by species
        detections = self.get_species_detections(LOOKBACK_DAYS)
        self.log("INFO", f"Retrieved {len(detections)} total detections")

        # Group by species
        species_data = {}
        for row in detections:
            common_name = row[0]
            if common_name not in species_data:
                species_data[common_name] = []
            species_data[common_name].append(row)

        self.log("INFO", f"Found {len(species_data)} unique species")

        # Calculate baselines
        baselines = []
        skipped = 0

        for common_name, detections in species_data.items():
            baseline = self.calculate_baseline(detections)
            if baseline:
                baselines.append(baseline)
            else:
                skipped += 1

        self.log("INFO", f"Calculated {len(baselines)} baselines, skipped {skipped} (insufficient data)")

        # Write to database
        if baselines:
            self.write_baselines(baselines)

        return len(baselines)

    def write_baselines(self, baselines):
        """Write baselines to database"""
        cursor = self.conn.cursor()

        # Use INSERT ... ON CONFLICT to upsert
        query = """
            INSERT INTO species_baselines (
                species_nl, species_scientific, months_active, hours_active,
                avg_confidence, avg_daily_count, min_daily_count, max_daily_count,
                detection_count, first_seen, last_seen, last_updated
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
            )
            ON CONFLICT (species_nl) DO UPDATE SET
                species_scientific = EXCLUDED.species_scientific,
                months_active = EXCLUDED.months_active,
                hours_active = EXCLUDED.hours_active,
                avg_confidence = EXCLUDED.avg_confidence,
                avg_daily_count = EXCLUDED.avg_daily_count,
                min_daily_count = EXCLUDED.min_daily_count,
                max_daily_count = EXCLUDED.max_daily_count,
                detection_count = EXCLUDED.detection_count,
                first_seen = EXCLUDED.first_seen,
                last_seen = EXCLUDED.last_seen,
                last_updated = NOW()
        """

        data = [
            (
                b['species_nl'],
                b['species_scientific'],
                b['months_active'],
                b['hours_active'],
                b['avg_confidence'],
                b['avg_daily_count'],
                b['min_daily_count'],
                b['max_daily_count'],
                b['detection_count'],
                b['first_seen'],
                b['last_seen'],
            )
            for b in baselines
        ]

        execute_batch(cursor, query, data, page_size=100)
        self.conn.commit()

        self.log("SUCCESS", f"Written {len(baselines)} baselines to database")

    def run(self):
        """Main execution"""
        start_time = datetime.now()
        self.log("INFO", "=" * 60)
        self.log("INFO", "EMSN Baseline Learning")
        self.log("INFO", "=" * 60)

        if not self.connect():
            return False

        try:
            count = self.update_baselines()
            duration = (datetime.now() - start_time).total_seconds()

            self.log("SUCCESS", f"Baseline learning completed in {duration:.1f}s")
            self.log("INFO", f"Updated {count} species baselines")

            return True

        except Exception as e:
            self.log("ERROR", f"Baseline learning failed: {e}")
            import traceback
            traceback.print_exc()
            return False

        finally:
            if self.conn:
                self.conn.close()


def main():
    learner = BaselineLearner()
    success = learner.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
