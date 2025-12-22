#!/usr/bin/env python3
"""
FlySafe Bird Migration Radar Scraper
=====================================

Scrapes KNMI FlySafe radar images and analyzes bird migration intensity
based on color coding in the radar images.

Radar Stations:
- Wier (Noord-Nederland)
- Herwijnen (Centraal Nederland)
- Glons (België)

Color Coding (typical radar intensity):
- Blue/Green: Low migration
- Yellow: Moderate migration
- Orange: High migration
- Red: Very high migration

Author: Claude Sonnet 4.5 & Ronny Hullegie
"""

import os
import sys
import requests
import json
from datetime import datetime, timedelta
from pathlib import Path
import logging
from urllib.parse import urlencode

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

# Database connection
import psycopg2
from psycopg2.extras import RealDictCursor

# Import color analyzer
from color_analyzer import RadarColorAnalyzer
from migration_alerts import MigrationAlertSystem

# Configuration
RADAR_STATIONS = {
    'herwijnen': {
        'name': 'Herwijnen',
        'region': 'central_netherlands',
        'lat': 51.837,
        'lon': 5.138
    },
    'wier': {
        'name': 'Wier',
        'region': 'north_netherlands',
        'lat': 53.400,
        'lon': 6.600
    }
}

# FlySafe URLs
FLYSAFE_BASE = "https://www.flysafe-birdtam.eu"
PROFILE_URL = f"{FLYSAFE_BASE}/profile.php"
MIGRATION_URL = f"{FLYSAFE_BASE}/migration.html"

# Storage paths
STORAGE_BASE = Path("/mnt/usb/flysafe")
IMAGES_DIR = STORAGE_BASE / "images"
LOGS_DIR = Path("/mnt/usb/logs")

# Import secrets
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'config'))
try:
    from emsn_secrets import get_postgres_config
    _pg = get_postgres_config()
except ImportError:
    _pg = {'host': '192.168.1.25', 'port': 5433, 'database': 'emsn',
           'user': 'birdpi_zolder', 'password': os.getenv('EMSN_DB_PASSWORD', '')}

# Database configuration (from secrets)
DB_CONFIG = {
    'host': _pg.get('host', '192.168.1.25'),
    'port': _pg.get('port', 5433),
    'database': _pg.get('database', 'emsn'),
    'user': _pg.get('user', 'birdpi_zolder'),
    'password': _pg.get('password', '') or os.getenv('EMSN_DB_PASSWORD', '')
}

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOGS_DIR / "flysafe-scraper.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class FlySafeScraper:
    """Scrapes FlySafe radar data and stores in database"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'EMSN Bird Monitoring System/2.0'
        })

        # Ensure directories exist
        IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

    def get_db_connection(self):
        """Create database connection"""
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            return conn
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise

    def fetch_radar_image(self, station='herwijnen', subwindow='SE'):
        """
        Fetch BirdTAM migration graph image

        Images are available at:
        ./images/graphs/BirdTAM_[Station]_[Subwindow].png

        Station: Wier or Glons (Herwijnen not in migration data)
        Subwindow: NW (north-west) or SE (south-east)

        For Herwijnen, we'll use Wier_SE (North-Netherlands region)

        Returns: bytes of PNG image or None
        """
        try:
            # Map stations to migration radar names
            migration_station_map = {
                'herwijnen': 'Wier',  # Closest match
                'wier': 'Wier',
                'glons': 'Glons'
            }

            migration_station = migration_station_map.get(station.lower(), 'Wier')

            # Construct image URL
            image_filename = f"BirdTAM_{migration_station}_{subwindow}.png"
            image_url = f"{FLYSAFE_BASE}/images/graphs/{image_filename}"

            logger.info(f"Fetching BirdTAM image: {image_url}")

            response = self.session.get(image_url, timeout=30)
            response.raise_for_status()

            logger.info(f"Successfully fetched image ({len(response.content)} bytes)")
            return response.content

        except Exception as e:
            logger.error(f"Failed to fetch radar image: {e}")
            return None

    def save_image(self, image_data, station, timestamp):
        """Save radar image to disk"""
        if not image_data:
            return None

        # Organize by date
        date_str = timestamp.strftime('%Y/%m/%d')
        save_dir = IMAGES_DIR / station / date_str
        save_dir.mkdir(parents=True, exist_ok=True)

        filename = f"radar_{station}_{timestamp.strftime('%Y%m%d_%H%M%S')}.png"
        filepath = save_dir / filename

        with open(filepath, 'wb') as f:
            f.write(image_data)

        logger.info(f"Saved image: {filepath}")
        return str(filepath)

    def analyze_radar_data(self, station='herwijnen', subwindow='SE'):
        """
        Fetch and analyze current radar data

        Downloads BirdTAM migration graph and performs color analysis
        """
        timestamp = datetime.now()

        logger.info(f"Analyzing radar data for {station} at {timestamp}")

        # Map to migration radar
        migration_station_map = {
            'herwijnen': 'Wier',
            'wier': 'Wier',
            'glons': 'Glons'
        }
        migration_station = migration_station_map.get(station.lower(), 'Wier')

        # Construct URLs
        image_filename = f"BirdTAM_{migration_station}_{subwindow}.png"
        radar_url = f"{FLYSAFE_BASE}/images/graphs/{image_filename}"

        # Fetch image
        image_data = self.fetch_radar_image(station, subwindow)
        image_path = None
        intensity = None
        intensity_score = None
        direction = None
        color_distribution = None

        if image_data:
            image_path = self.save_image(image_data, station, timestamp)

            # Perform color analysis on saved image
            if image_path:
                try:
                    analyzer = RadarColorAnalyzer()
                    analysis_result = analyzer.analyze_image(image_path, region='netherlands')

                    if analysis_result:
                        intensity = analysis_result['intensity']
                        intensity_score = analysis_result['intensity_score']
                        direction = analysis_result.get('direction')
                        color_distribution = analysis_result['color_distribution']

                        logger.info(f"Color analysis: {intensity} (score: {intensity_score})")
                    else:
                        logger.warning("Color analysis failed")
                except Exception as e:
                    logger.error(f"Color analysis error: {e}")

        # Prepare data structure
        radar_entry = {
            'timestamp': timestamp,
            'station': station,
            'migration_station': migration_station,
            'subwindow': subwindow,
            'region': RADAR_STATIONS[station]['region'],
            'image_path': image_path,
            'radar_url': radar_url if image_data else None,
            'intensity': intensity,
            'intensity_score': intensity_score,
            'direction': direction,
            'altitude_band': None,
            'bird_density': None,
            'raw_data': {
                'station_info': RADAR_STATIONS[station],
                'migration_station': migration_station,
                'subwindow': subwindow,
                'fetch_time': timestamp.isoformat(),
                'image_fetched': image_data is not None,
                'color_distribution': color_distribution
            }
        }

        return radar_entry

    def store_radar_data(self, radar_entry):
        """Store radar data in database using radar_observations table"""
        conn = None
        try:
            conn = self.get_db_connection()
            cur = conn.cursor()

            # Use existing radar_observations table structure
            timestamp = radar_entry['timestamp']

            query = """
                INSERT INTO radar_observations (
                    observation_date,
                    observation_time,
                    radar_image_url,
                    local_image_path,
                    intensity_level,
                    intensity_category,
                    bird_detections_count,
                    correlation_score
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s
                )
                RETURNING id
            """

            # Use actual intensity_score if available, otherwise map from category
            intensity_score = radar_entry.get('intensity_score')
            intensity_category = radar_entry.get('intensity')

            if intensity_score is not None:
                # Use actual calculated score (0-100)
                intensity_level = int(round(intensity_score))
            else:
                # Fallback to mapping if no score available
                intensity_mapping = {
                    'minimal': 10,
                    'low': 30,
                    'moderate': 50,
                    'high': 75,
                    'very_high': 95
                }
                intensity_level = intensity_mapping.get(intensity_category, 0)

            # Ensure we have a category
            if not intensity_category:
                intensity_category = 'unknown'

            cur.execute(query, (
                timestamp.date(),
                timestamp.time(),
                radar_entry.get('radar_url'),  # Will be None for now
                radar_entry.get('image_path'),
                intensity_level,
                intensity_category,
                0,  # bird_detections_count - will be filled by correlation script
                None  # correlation_score - will be calculated later
            ))

            result_id = cur.fetchone()[0]
            conn.commit()

            logger.info(f"Stored radar data with ID: {result_id}")
            return result_id

        except Exception as e:
            logger.error(f"Failed to store radar data: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()

    def run(self, stations=None):
        """Run scraper for specified stations"""
        if stations is None:
            stations = ['herwijnen']  # Default to central NL

        logger.info(f"=== FlySafe Scraper Started ===")
        logger.info(f"Stations: {', '.join(stations)}")

        results = []
        for station in stations:
            if station not in RADAR_STATIONS:
                logger.warning(f"Unknown station: {station}")
                continue

            try:
                radar_entry = self.analyze_radar_data(station)
                entry_id = self.store_radar_data(radar_entry)
                results.append({
                    'station': station,
                    'id': entry_id,
                    'timestamp': radar_entry['timestamp']
                })
            except Exception as e:
                logger.error(f"Failed to process {station}: {e}")

        logger.info(f"=== FlySafe Scraper Completed: {len(results)} entries ===")

        # Send alerts if high migration detected
        if results:
            try:
                # Get the latest intensity from last analyzed station
                last_entry = results[-1]
                # Query DB for intensity
                conn = self.get_db_connection()
                cur = conn.cursor()
                cur.execute("""
                    SELECT intensity_level, bird_detections_count
                    FROM radar_observations WHERE id = %s
                """, (last_entry['id'],))
                row = cur.fetchone()
                conn.close()

                if row:
                    intensity = row[0] or 0
                    detections = row[1] or 0
                    alert_system = MigrationAlertSystem()
                    alert_system.check_and_alert(intensity, detections)
                    logger.info(f"Alert check completed: intensity={intensity}")
            except Exception as e:
                logger.warning(f"Alert system error: {e}")

        return results


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='FlySafe Bird Migration Radar Scraper')
    parser.add_argument(
        '--stations',
        nargs='+',
        default=['herwijnen'],
        choices=list(RADAR_STATIONS.keys()),
        help='Radar stations to scrape'
    )
    parser.add_argument(
        '--list-stations',
        action='store_true',
        help='List available radar stations'
    )

    args = parser.parse_args()

    if args.list_stations:
        print("\nAvailable Radar Stations:")
        for key, info in RADAR_STATIONS.items():
            print(f"  {key}: {info['name']} ({info['region']})")
        return

    try:
        scraper = FlySafeScraper()
        scraper.run(stations=args.stations)
    except Exception as e:
        logger.error(f"Scraper failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
