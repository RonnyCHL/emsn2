#!/usr/bin/env python3
"""
FlySafe Radar - BirdNET Correlation Analyzer
=============================================

Analyzes correlation between FlySafe radar migration intensity
and BirdNET bird detections.

For each radar observation:
- Counts bird detections within time window
- Calculates correlation score
- Updates radar_observations table

Author: Claude Sonnet 4.5 & Ronny Hullegie
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor

# Import core modules
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.config import get_postgres_config
from core.logging import get_logger

# Configuration (from core module)
DB_CONFIG = get_postgres_config()

# Correlation parameters
TIME_WINDOW_HOURS = 2  # Look for detections within +/- 2 hours of radar observation
MIN_CONFIDENCE = 0.7   # Only count high-confidence detections
CORRELATION_WEIGHT = 0.7  # Weight for high-confidence detections

# Centrale logger
logger = get_logger('flysafe_radar_correlation')


class RadarCorrelationAnalyzer:
    """Analyzes correlation between radar and BirdNET detections"""

    def __init__(self):
        self.conn = None

    def get_db_connection(self):
        """Create database connection"""
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            return conn
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise

    def get_uncorrelated_observations(self):
        """Get radar observations that need correlation analysis"""
        try:
            conn = self.get_db_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)

            query = """
                SELECT
                    id,
                    observation_date,
                    observation_time,
                    intensity_level,
                    intensity_category
                FROM radar_observations
                WHERE correlation_score IS NULL
                ORDER BY observation_date DESC, observation_time DESC
            """

            cur.execute(query)
            results = cur.fetchall()
            conn.close()

            logger.info(f"Found {len(results)} uncorrelated radar observations")
            return results

        except Exception as e:
            logger.error(f"Failed to fetch uncorrelated observations: {e}")
            return []

    def count_bird_detections(self, observation_date, observation_time, time_window_hours=2):
        """
        Count bird detections within time window of radar observation

        Returns dict with:
        - total_count: All detections in window
        - high_confidence_count: Detections >= MIN_CONFIDENCE
        - species_count: Unique species detected
        - avg_confidence: Average confidence of detections
        """
        try:
            conn = self.get_db_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)

            # Combine date and time to timestamp
            obs_timestamp = datetime.combine(observation_date, observation_time)

            # Calculate time window
            start_time = obs_timestamp - timedelta(hours=time_window_hours)
            end_time = obs_timestamp + timedelta(hours=time_window_hours)

            query = """
                SELECT
                    COUNT(*) as total_count,
                    COUNT(DISTINCT species) as species_count,
                    AVG(confidence) as avg_confidence,
                    SUM(CASE WHEN confidence >= %s THEN 1 ELSE 0 END) as high_confidence_count
                FROM bird_detections
                WHERE detection_timestamp >= %s
                  AND detection_timestamp <= %s
            """

            cur.execute(query, (MIN_CONFIDENCE, start_time, end_time))
            result = cur.fetchone()
            conn.close()

            return {
                'total_count': int(result['total_count']) if result['total_count'] else 0,
                'high_confidence_count': int(result['high_confidence_count']) if result['high_confidence_count'] else 0,
                'species_count': int(result['species_count']) if result['species_count'] else 0,
                'avg_confidence': float(result['avg_confidence']) if result['avg_confidence'] else 0.0
            }

        except Exception as e:
            logger.error(f"Failed to count bird detections: {e}")
            return {
                'total_count': 0,
                'high_confidence_count': 0,
                'species_count': 0,
                'avg_confidence': 0.0
            }

    def calculate_correlation_score(self, intensity_level, detection_stats):
        """
        Calculate correlation score between radar intensity and bird detections

        Score ranges from 0.0 to 1.0:
        - 0.0: No correlation (no detections despite high radar intensity, or vice versa)
        - 1.0: Perfect correlation (high intensity = many detections, low intensity = few detections)

        Formula considers:
        - Radar intensity level (0-100)
        - Number of high-confidence detections
        - Species diversity
        - Average confidence
        """

        # Normalize intensity to 0-1 scale
        normalized_intensity = intensity_level / 100.0

        # Get detection metrics
        high_conf_count = detection_stats['high_confidence_count']
        species_count = detection_stats['species_count']
        avg_confidence = detection_stats['avg_confidence']

        # Expected detections based on intensity
        # High intensity (100) should have ~50+ detections in 4-hour window
        # Low intensity (0) should have ~0 detections
        expected_detections = normalized_intensity * 50

        # Actual detection score (weighted by confidence and species diversity)
        detection_score = min(1.0, (high_conf_count + (species_count * 2)) / 50.0)

        # Calculate correlation
        # Perfect match: detection_score matches normalized_intensity
        # Use exponential decay for mismatch penalty
        diff = abs(normalized_intensity - detection_score)
        correlation = max(0.0, 1.0 - (diff * 1.5))  # Multiply diff for stricter penalty

        # Boost correlation if both are high (strong positive correlation)
        if normalized_intensity > 0.5 and detection_score > 0.5:
            correlation = min(1.0, correlation * 1.2)

        # Boost correlation if both are low (strong negative correlation = also good!)
        if normalized_intensity < 0.2 and detection_score < 0.2:
            correlation = min(1.0, correlation * 1.2)

        return round(correlation, 4)

    def update_correlation(self, observation_id, detection_count, correlation_score):
        """Update radar observation with correlation data"""
        try:
            conn = self.get_db_connection()
            cur = conn.cursor()

            query = """
                UPDATE radar_observations
                SET bird_detections_count = %s,
                    correlation_score = %s
                WHERE id = %s
            """

            cur.execute(query, (detection_count, correlation_score, observation_id))
            conn.commit()
            conn.close()

            logger.info(f"Updated observation {observation_id}: {detection_count} detections, score: {correlation_score}")
            return True

        except Exception as e:
            logger.error(f"Failed to update correlation: {e}")
            return False

    def analyze_all(self):
        """Analyze correlation for all uncorrelated observations"""
        logger.info("=== Starting Radar-BirdNET Correlation Analysis ===")

        observations = self.get_uncorrelated_observations()

        if not observations:
            logger.info("No uncorrelated observations found")
            return []

        results = []
        for obs in observations:
            obs_id = obs['id']
            obs_date = obs['observation_date']
            obs_time = obs['observation_time']
            intensity = obs['intensity_level']
            category = obs['intensity_category']

            logger.info(f"Analyzing observation {obs_id}: {obs_date} {obs_time} - {category} ({intensity})")

            # Count bird detections in time window
            detection_stats = self.count_bird_detections(
                obs_date,
                obs_time,
                time_window_hours=TIME_WINDOW_HOURS
            )

            # Calculate correlation score
            correlation_score = self.calculate_correlation_score(
                intensity,
                detection_stats
            )

            # Update database
            success = self.update_correlation(
                obs_id,
                detection_stats['high_confidence_count'],
                correlation_score
            )

            if success:
                results.append({
                    'id': obs_id,
                    'timestamp': f"{obs_date} {obs_time}",
                    'intensity': intensity,
                    'category': category,
                    'detections': detection_stats['high_confidence_count'],
                    'species': detection_stats['species_count'],
                    'correlation': correlation_score
                })

        logger.info(f"=== Correlation Analysis Complete: {len(results)} observations processed ===")
        return results

    def generate_report(self):
        """Generate correlation report"""
        try:
            conn = self.get_db_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)

            query = """
                SELECT
                    observation_date,
                    observation_time,
                    intensity_category,
                    intensity_level,
                    bird_detections_count,
                    correlation_score
                FROM radar_observations
                WHERE correlation_score IS NOT NULL
                ORDER BY observation_date DESC, observation_time DESC
                LIMIT 20
            """

            cur.execute(query)
            results = cur.fetchall()
            conn.close()

            print("\n" + "="*80)
            print("  RADAR-BIRDNET CORRELATION REPORT")
            print("="*80)
            print(f"\n{'Date':<12} {'Time':<10} {'Intensity':<12} {'Level':<6} {'Birds':<7} {'Score':<8}")
            print("-"*80)

            for row in results:
                date_str = row['observation_date'].strftime('%Y-%m-%d')
                time_str = row['observation_time'].strftime('%H:%M:%S')
                intensity = row['intensity_category'] or 'unknown'
                level = row['intensity_level'] or 0
                detections = row['bird_detections_count'] or 0
                score = row['correlation_score'] or 0.0

                print(f"{date_str:<12} {time_str:<10} {intensity:<12} {level:<6} {detections:<7} {score:<8.4f}")

            print("="*80)

            # Summary statistics
            if results:
                avg_correlation = sum(r['correlation_score'] or 0 for r in results) / len(results)
                print(f"\nAverage Correlation Score: {avg_correlation:.4f}")
                print(f"Total Observations: {len(results)}")

            print()

        except Exception as e:
            logger.error(f"Failed to generate report: {e}")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='FlySafe Radar - BirdNET Correlation Analyzer')
    parser.add_argument(
        '--report',
        action='store_true',
        help='Generate correlation report'
    )

    args = parser.parse_args()

    try:
        analyzer = RadarCorrelationAnalyzer()

        if args.report:
            analyzer.generate_report()
        else:
            analyzer.analyze_all()
            analyzer.generate_report()

    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
