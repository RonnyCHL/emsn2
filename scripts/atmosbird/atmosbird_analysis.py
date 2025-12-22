#!/usr/bin/env python3
"""
AtmosBird Advanced Analysis Script
Analyzes sky observations for ISS passes, moon phases, stars, and meteors
"""

import os
import sys
import psycopg2
from datetime import datetime, timedelta
import requests
import json
from pathlib import Path
import numpy as np
import cv2
from astral import LocationInfo
from astral.sun import sun
from astral.moon import phase
import ephem

# Configuration
STATION_ID = "berging"
LOCATION_LAT = 52.360179  # Berging camera locatie, Nijverdal
LOCATION_LON = 6.472626
LOCATION_ELEVATION = 12  # meters (geschat voor berging)

# Camera specs - Pi Camera NoIR Module 3 (imx708_wide_noir)
CAMERA_FOV_DIAGONAL = 120  # graden diagonaal gezichtsveld
CAMERA_FOV_HORIZONTAL = 102  # graden horizontaal (4:3 aspect)
CAMERA_FOV_VERTICAL = 67  # graden verticaal
CAMERA_POINTING = "zenith"  # camera kijkt recht omhoog

# Import secrets - probeer meerdere locaties
_secrets_paths = [
    Path(__file__).parent.parent.parent / 'config',  # Als in emsn2/scripts/atmosbird/
    Path.home() / 'emsn2' / 'config',                 # Fallback naar home directory
]
for _path in _secrets_paths:
    if _path.exists():
        sys.path.insert(0, str(_path))
        break

try:
    from emsn_secrets import get_postgres_config
    _pg = get_postgres_config()
except ImportError:
    _pg = {'host': '192.168.1.25', 'port': 5433, 'database': 'emsn',
           'user': 'birdpi_zolder', 'password': os.environ.get('EMSN_DB_PASSWORD', '')}

# Database configuration (from secrets)
DB_CONFIG = {
    'host': _pg.get('host', '192.168.1.25'),
    'port': _pg.get('port', 5433),
    'database': _pg.get('database', 'emsn'),
    'user': _pg.get('user', 'birdpi_zolder'),
    'password': _pg.get('password', '')
}

# ISS tracking API
ISS_PASSES_API = "https://api.n2yo.com/rest/v1/satellite/visualpasses"
ISS_NORAD_ID = 25544  # ISS NORAD catalog number

# Storage
DETECTION_DIR = "/mnt/usb/atmosbird/detecties"


class SkyAnalyzer:
    def __init__(self):
        self.conn = None
        self.observer = None
        self.setup_observer()

    def log(self, level, message):
        """Log message with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}", flush=True)

    def connect_db(self):
        """Connect to PostgreSQL database"""
        try:
            self.conn = psycopg2.connect(**DB_CONFIG)
            self.log("INFO", "Connected to database")
            return True
        except Exception as e:
            self.log("ERROR", f"Database connection failed: {e}")
            return False

    def setup_observer(self):
        """Setup PyEphem observer for astronomical calculations"""
        self.observer = ephem.Observer()
        self.observer.lat = str(LOCATION_LAT)
        self.observer.lon = str(LOCATION_LON)
        self.observer.elevation = LOCATION_ELEVATION

    def check_iss_visibility(self, observation_time):
        """
        Check if ISS is visible at observation time
        Uses PyEphem for ISS position calculation
        """
        try:
            # Create ISS TLE (Two-Line Element) object
            # Updated from Celestrak on 2025-12-22
            iss = ephem.readtle(
                "ISS (ZARYA)             ",
                "1 25544U 98067A   25355.95645853  .00010990  00000+0  20227-3 0  9999",
                "2 25544  51.6324  96.8363 0003164 283.4657  76.5979 15.49714244544284"
            )

            # Set observer time
            self.observer.date = observation_time

            # Compute ISS position
            iss.compute(self.observer)

            # Get altitude (elevation above horizon) in degrees
            altitude_deg = float(iss.alt) * 180.0 / np.pi
            azimuth_deg = float(iss.az) * 180.0 / np.pi

            # Camera kijkt recht omhoog (zenith) met 120° diagonaal FOV
            # Dus ISS moet minimaal 90° - (120°/2) = 30° boven horizon zijn
            # om in het gezichtsveld te vallen
            min_altitude_for_fov = 90 - (CAMERA_FOV_DIAGONAL / 2)  # = 30°
            is_in_camera_fov = altitude_deg >= min_altitude_for_fov

            # Check if it's twilight/night
            sun_obj = ephem.Sun()
            sun_obj.compute(self.observer)
            sun_alt = float(sun_obj.alt) * 180.0 / np.pi
            is_dark = sun_alt < -6  # Nautical twilight

            # ISS is zichtbaar in camera als:
            # 1. In camera FOV (>30° altitude)
            # 2. Het donker genoeg is
            # 3. ISS verlicht door zon (altijd het geval als ISS boven horizon en observer in duisternis)
            visible_in_camera = is_in_camera_fov and is_dark

            if is_in_camera_fov or altitude_deg > 10:
                self.log("INFO", f"ISS: alt={altitude_deg:.1f}°, az={azimuth_deg:.1f}°, "
                               f"in_camera_fov={is_in_camera_fov}, sun_alt={sun_alt:.1f}°, "
                               f"visible_in_camera={visible_in_camera}")

            return {
                'visible': visible_in_camera,
                'in_camera_fov': is_in_camera_fov,
                'altitude': altitude_deg if is_in_camera_fov else None,
                'azimuth': azimuth_deg if is_in_camera_fov else None
            }

        except Exception as e:
            self.log("WARNING", f"ISS calculation error: {e}")
            return {'visible': False, 'altitude': None, 'azimuth': None}

    def analyze_moon(self, observation_time):
        """
        Analyze moon position and phase
        """
        try:
            # Set observer time
            self.observer.date = observation_time

            # Create moon object
            moon = ephem.Moon()
            moon.compute(self.observer)

            # Get moon position
            altitude_deg = float(moon.alt) * 180.0 / np.pi
            azimuth_deg = float(moon.az) * 180.0 / np.pi

            # Moon phase (0-100% illumination)
            illumination = moon.phase

            # Determine phase name
            phase_names = [
                "New Moon", "Waxing Crescent", "First Quarter", "Waxing Gibbous",
                "Full Moon", "Waning Gibbous", "Last Quarter", "Waning Crescent"
            ]
            phase_index = int((illumination / 100.0) * 8) % 8
            phase_name = phase_names[phase_index]

            # Moon is visible if above horizon
            is_visible = altitude_deg > 0

            # Check of maan in camera FOV is (>30° altitude voor zenith-pointing camera)
            min_altitude_for_fov = 90 - (CAMERA_FOV_DIAGONAL / 2)  # = 30°
            is_in_camera_fov = altitude_deg >= min_altitude_for_fov

            # Calculate moon age (days since new moon)
            previous_new = ephem.previous_new_moon(observation_time)
            moon_age = observation_time - previous_new.datetime()

            self.log("INFO", f"Moon: {phase_name}, {illumination:.1f}% illuminated, "
                           f"alt={altitude_deg:.1f}°, in_camera_fov={is_in_camera_fov}")

            return {
                'visible': is_visible,
                'in_camera_fov': is_in_camera_fov,
                'altitude': altitude_deg,
                'azimuth': azimuth_deg,
                'phase_name': phase_name,
                'illumination': illumination,
                'age_days': moon_age.days
            }

        except Exception as e:
            self.log("ERROR", f"Moon analysis error: {e}")
            return None

    def analyze_stars(self, image_path, brightness_mean):
        """
        Analyze star visibility and brightness
        Only performs analysis for nighttime images
        """
        try:
            # Only analyze if it's dark (low brightness)
            if brightness_mean > 80:
                return None  # Too bright for stars

            # Load image
            img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
            if img is None:
                return None

            # Reduce image size for faster processing
            scale = 0.25
            small = cv2.resize(img, None, fx=scale, fy=scale)

            # Apply Gaussian blur to reduce noise
            blurred = cv2.GaussianBlur(small, (5, 5), 0)

            # Detect bright spots (potential stars)
            # Use adaptive thresholding to find local maxima
            threshold = np.percentile(blurred, 99.5)  # Top 0.5% brightest pixels
            _, stars_mask = cv2.threshold(blurred, threshold, 255, cv2.THRESH_BINARY)

            # Count star-like features
            contours, _ = cv2.findContours(stars_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            # Filter contours by size (stars should be small)
            star_contours = [c for c in contours if 1 <= cv2.contourArea(c) <= 50]
            star_count = len(star_contours)

            # Calculate average brightness of detected stars
            if star_count > 0:
                star_pixels = blurred[stars_mask > 0]
                avg_star_brightness = float(np.mean(star_pixels))
                brightest_star = float(np.max(star_pixels))
            else:
                avg_star_brightness = 0
                brightest_star = 0

            # Calculate sky background brightness (excluding stars)
            background_mask = stars_mask == 0
            if np.sum(background_mask) > 0:
                sky_background = float(np.mean(blurred[background_mask]))
            else:
                sky_background = float(np.mean(blurred))

            # Estimate Bortle scale (light pollution)
            # Lower background = darker sky = better for astronomy
            if sky_background < 20:
                bortle = 1  # Excellent dark sky
            elif sky_background < 35:
                bortle = 3  # Rural sky
            elif sky_background < 50:
                bortle = 5  # Suburban sky
            elif sky_background < 70:
                bortle = 7  # Suburban/urban transition
            else:
                bortle = 9  # Inner city sky

            # Calculate seeing quality (lower variance = better seeing)
            seeing_quality = float(100 - min(100, np.std(blurred)))

            self.log("INFO", f"Stars: count={star_count}, brightness={avg_star_brightness:.1f}, "
                           f"background={sky_background:.1f}, Bortle={bortle}")

            return {
                'star_count': star_count,
                'avg_star_brightness': avg_star_brightness,
                'brightest_star': brightest_star,
                'sky_background': sky_background,
                'bortle_scale': bortle,
                'seeing_quality': seeing_quality
            }

        except Exception as e:
            self.log("ERROR", f"Star analysis error: {e}")
            return None

    def detect_meteor(self, current_image_path, previous_image_path):
        """
        Detect potential meteors using frame differencing
        Looks for bright streaks that appear only in current frame
        """
        try:
            if not previous_image_path or not os.path.exists(previous_image_path):
                return None

            # Load images
            current = cv2.imread(current_image_path, cv2.IMREAD_GRAYSCALE)
            previous = cv2.imread(previous_image_path, cv2.IMREAD_GRAYSCALE)

            if current is None or previous is None:
                return None

            # Resize for faster processing
            scale = 0.25
            current_small = cv2.resize(current, None, fx=scale, fy=scale)
            previous_small = cv2.resize(previous, None, fx=scale, fy=scale)

            # Calculate absolute difference
            diff = cv2.absdiff(current_small, previous_small)

            # Apply threshold to find significant changes
            threshold = 30
            _, diff_thresh = cv2.threshold(diff, threshold, 255, cv2.THRESH_BINARY)

            # Find contours of changed regions
            contours, _ = cv2.findContours(diff_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            # Look for meteor-like features (elongated bright streaks)
            potential_meteors = []
            for contour in contours:
                area = cv2.contourArea(contour)
                if area < 10 or area > 1000:  # Filter by size
                    continue

                # Get bounding rectangle
                x, y, w, h = cv2.boundingRect(contour)

                # Check aspect ratio (meteors are elongated)
                aspect_ratio = max(w, h) / (min(w, h) + 1)
                if aspect_ratio > 3:  # Elongated shape
                    # Calculate brightness increase
                    roi_current = current_small[y:y+h, x:x+w]
                    roi_previous = previous_small[y:y+h, x:x+w]
                    brightness_delta = float(np.mean(roi_current) - np.mean(roi_previous))

                    if brightness_delta > 20:  # Significant brightness increase
                        potential_meteors.append({
                            'bbox': (x, y, w, h),
                            'brightness_delta': brightness_delta,
                            'streak_length': max(w, h),
                            'confidence': min(100, brightness_delta * aspect_ratio / 10)
                        })

            if potential_meteors:
                # Return highest confidence detection
                best = max(potential_meteors, key=lambda m: m['confidence'])
                self.log("WARNING", f"Potential meteor detected! Confidence={best['confidence']:.1f}%")
                return best
            else:
                return None

        except Exception as e:
            self.log("ERROR", f"Meteor detection error: {e}")
            return None

    def process_recent_observations(self, lookback_minutes=20):
        """
        Process recent observations for advanced analysis
        """
        try:
            cursor = self.conn.cursor()

            # Get recent observations without advanced analysis
            cutoff_time = datetime.now() - timedelta(minutes=lookback_minutes)

            query = """
                SELECT id, observation_timestamp, image_path, brightness, cloud_coverage
                FROM sky_observations
                WHERE observation_timestamp >= %s
                ORDER BY observation_timestamp DESC
            """

            cursor.execute(query, (cutoff_time,))
            observations = cursor.fetchall()

            self.log("INFO", f"Processing {len(observations)} recent observations")

            previous_image = None

            for obs_id, obs_time, image_path, brightness, cloud_coverage in observations:
                self.log("INFO", f"Analyzing observation {obs_id} at {obs_time}")

                # ISS visibility check
                iss_data = self.check_iss_visibility(obs_time)
                if iss_data['visible']:
                    self.save_iss_observation(obs_id, obs_time, iss_data)

                # Moon analysis
                moon_data = self.analyze_moon(obs_time)
                if moon_data:
                    self.save_moon_observation(obs_id, obs_time, moon_data)

                # Star analysis (only for dark skies)
                if brightness < 80 and cloud_coverage < 50:
                    star_data = self.analyze_stars(image_path, brightness)
                    if star_data:
                        self.save_star_observation(obs_id, obs_time, star_data)

                # Meteor detection (compare with previous frame)
                if previous_image and brightness < 100:
                    meteor_data = self.detect_meteor(image_path, previous_image)
                    if meteor_data and meteor_data['confidence'] > 50:
                        self.save_meteor_detection(obs_id, obs_time, meteor_data)

                previous_image = image_path

            self.conn.commit()
            self.log("INFO", "Analysis completed successfully")

        except Exception as e:
            self.log("ERROR", f"Processing error: {e}")
            if self.conn:
                self.conn.rollback()

    def save_iss_observation(self, obs_id, obs_time, iss_data):
        """Save ISS visibility to iss_passes table"""
        try:
            cursor = self.conn.cursor()

            # Schat pass duration (10 min tussen foto's, dus we schatten 5 min voor/na)
            pass_start = obs_time - timedelta(minutes=5)
            pass_end = obs_time + timedelta(minutes=5)

            cursor.execute("""
                INSERT INTO iss_passes (
                    pass_start, pass_end, max_elevation_degrees,
                    duration_seconds, observation_id, notes
                ) VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                RETURNING id
            """, (
                pass_start, pass_end, iss_data.get('altitude'),
                600,  # 10 min geschatte duration
                obs_id,
                f"Detected in camera FOV at {iss_data.get('altitude', 0):.1f}° alt, {iss_data.get('azimuth', 0):.1f}° az"
            ))

            result = cursor.fetchone()
            if result:
                self.log("INFO", f"ISS PASS LOGGED! ID={result[0]}, observation={obs_id}, "
                               f"altitude={iss_data.get('altitude', 0):.1f}°")
            else:
                self.log("INFO", f"ISS pass already logged for this timeframe")

        except Exception as e:
            self.log("WARNING", f"Failed to save ISS data: {e}")

    def save_moon_observation(self, obs_id, obs_time, moon_data):
        """Save moon observation to database"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO moon_observations (
                    observation_id, observation_timestamp, phase_name,
                    illumination_percent, age_days, altitude_degrees,
                    azimuth_degrees, detected_in_image
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (
                obs_id, obs_time, moon_data['phase_name'],
                moon_data['illumination'], moon_data['age_days'],
                moon_data['altitude'], moon_data['azimuth'],
                moon_data['visible']
            ))
            self.log("INFO", f"Moon observation saved for {obs_id}")
        except Exception as e:
            self.log("WARNING", f"Failed to save moon data: {e}")

    def save_star_observation(self, obs_id, obs_time, star_data):
        """Save star brightness observation to database"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO star_brightness (
                    observation_id, observation_timestamp, star_count,
                    avg_star_brightness, brightest_star_magnitude,
                    seeing_quality_score, sky_background_brightness,
                    bortle_scale_estimate
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (
                obs_id, obs_time, star_data['star_count'],
                star_data['avg_star_brightness'], star_data['brightest_star'],
                star_data['seeing_quality'], star_data['sky_background'],
                star_data['bortle_scale']
            ))
            self.log("INFO", f"Star observation saved for {obs_id}: {star_data['star_count']} stars detected")
        except Exception as e:
            self.log("WARNING", f"Failed to save star data: {e}")

    def save_meteor_detection(self, obs_id, obs_time, meteor_data):
        """Save meteor detection to database"""
        try:
            cursor = self.conn.cursor()
            x, y, w, h = meteor_data['bbox']
            cursor.execute("""
                INSERT INTO meteor_detections (
                    observation_id, detection_timestamp, frame_diff_score,
                    streak_length_pixels, brightness_delta, confidence_score,
                    bbox_x, bbox_y, bbox_width, bbox_height
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                obs_id, obs_time, meteor_data['brightness_delta'],
                meteor_data['streak_length'], meteor_data['brightness_delta'],
                meteor_data['confidence'], x, y, w, h
            ))
            meteor_id = cursor.fetchone()[0]
            self.log("WARNING", f"METEOR DETECTED! ID={meteor_id}, confidence={meteor_data['confidence']:.1f}%")
        except Exception as e:
            self.log("WARNING", f"Failed to save meteor detection: {e}")

    def cleanup(self):
        """Cleanup resources"""
        if self.conn:
            self.conn.close()

    def run(self):
        """Main execution"""
        try:
            self.log("INFO", "=== AtmosBird Advanced Analysis Started ===")

            if not self.connect_db():
                return False

            # Process recent observations
            self.process_recent_observations(lookback_minutes=30)

            self.log("INFO", "=== AtmosBird Advanced Analysis Completed ===")
            return True

        except Exception as e:
            self.log("ERROR", f"Unexpected error: {e}")
            return False
        finally:
            self.cleanup()


def main():
    analyzer = SkyAnalyzer()
    success = analyzer.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
