#!/usr/bin/env python3
"""
AtmosBird Sky Capture Script
Captures sky photos every 10 minutes with Pi Camera NoIR
Analyzes cloud coverage, brightness, and stores to NAS + PostgreSQL
"""

import os
import sys
import time
import psycopg2
from datetime import datetime
from pathlib import Path
import subprocess
import numpy as np
from PIL import Image
import cv2

# Configuration
CAMERA_WIDTH = 4608
CAMERA_HEIGHT = 2592
STATION_ID = "berging"

# Storage paths
NAS_BASE = "/mnt/usb/atmosbird"
RAW_PHOTO_DIR = f"{NAS_BASE}/ruwe_foto"
TIMELAPSE_DIR = f"{NAS_BASE}/timelapse"
DETECTION_DIR = f"{NAS_BASE}/detecties"
TEMP_DIR = "/tmp/atmosbird"

# Import secrets
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'config'))
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

# Analysis thresholds
DAYTIME_BRIGHTNESS_THRESHOLD = 100  # Mean brightness > 100 = daytime
CLOUD_THRESHOLD_CLEAR = 20          # < 20% clouds = clear
CLOUD_THRESHOLD_OVERCAST = 80       # > 80% clouds = overcast


class SkyCapture:
    def __init__(self):
        self.timestamp = datetime.now()
        self.temp_image_path = None
        self.final_image_path = None
        self.conn = None

        # Create temp directory
        Path(TEMP_DIR).mkdir(parents=True, exist_ok=True)

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

    def capture_photo(self):
        """Capture photo with rpicam-still"""
        try:
            # Generate temporary filename
            self.temp_image_path = f"{TEMP_DIR}/capture_{self.timestamp.strftime('%Y%m%d_%H%M%S')}.jpg"

            # Capture command with highest quality
            cmd = [
                "rpicam-still",
                "-o", self.temp_image_path,
                "--width", str(CAMERA_WIDTH),
                "--height", str(CAMERA_HEIGHT),
                "--timeout", "2000",
                "--quality", "95",
                "--encoding", "jpg",
                "-n"  # No preview
            ]

            self.log("INFO", f"Capturing photo: {CAMERA_WIDTH}x{CAMERA_HEIGHT}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode != 0:
                self.log("ERROR", f"Capture failed: {result.stderr}")
                return False

            # Verify file exists
            if not os.path.exists(self.temp_image_path):
                self.log("ERROR", "Capture file not created")
                return False

            file_size = os.path.getsize(self.temp_image_path)
            self.log("INFO", f"Photo captured: {file_size / 1024 / 1024:.2f} MB")
            return True

        except subprocess.TimeoutExpired:
            self.log("ERROR", "Capture timeout")
            return False
        except Exception as e:
            self.log("ERROR", f"Capture error: {e}")
            return False

    def analyze_image(self):
        """Analyze captured image for cloud coverage and brightness"""
        try:
            # Load image
            img = cv2.imread(self.temp_image_path)
            if img is None:
                self.log("ERROR", "Failed to load image for analysis")
                return None

            # Convert to grayscale for analysis
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            # Calculate brightness statistics
            brightness_mean = float(np.mean(gray))
            brightness_std = float(np.std(gray))

            # Calculate contrast (using standard deviation as proxy)
            contrast_score = brightness_std

            # Detect day/night based on brightness
            is_daytime = brightness_mean > DAYTIME_BRIGHTNESS_THRESHOLD

            # Calculate cloud coverage
            # Cloud detection algorithm:
            # 1. Apply adaptive thresholding to find bright/dark regions
            # 2. Clouds are typically brighter and more uniform than clear sky
            cloud_coverage = self._calculate_cloud_coverage(gray, brightness_mean)

            # Determine sky type
            if cloud_coverage < CLOUD_THRESHOLD_CLEAR:
                sky_type = "clear"
            elif cloud_coverage > CLOUD_THRESHOLD_OVERCAST:
                sky_type = "overcast"
            else:
                sky_type = "partly_cloudy"

            self.log("INFO", f"Analysis: brightness={brightness_mean:.1f}, clouds={cloud_coverage:.1f}%, "
                            f"contrast={contrast_score:.1f}, daytime={is_daytime}, type={sky_type}")

            return {
                'brightness_mean': brightness_mean,
                'brightness_std': brightness_std,
                'contrast_score': contrast_score,
                'is_daytime': is_daytime,
                'cloud_coverage_percent': cloud_coverage,
                'sky_type': sky_type
            }

        except Exception as e:
            self.log("ERROR", f"Analysis failed: {e}")
            return None

    def _calculate_cloud_coverage(self, gray_image, mean_brightness):
        """
        Calculate cloud coverage percentage
        Uses adaptive thresholding and texture analysis
        """
        try:
            # For daytime: clouds are brighter, uniform regions
            # For nighttime: use different approach based on star visibility

            # Apply Gaussian blur to reduce noise
            blurred = cv2.GaussianBlur(gray_image, (21, 21), 0)

            # Adaptive thresholding
            adaptive_thresh = cv2.adaptiveThreshold(
                blurred, 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                51, 10
            )

            # Calculate percentage of "cloud" pixels (bright, uniform areas)
            if mean_brightness > DAYTIME_BRIGHTNESS_THRESHOLD:
                # Daytime: bright areas are clouds
                cloud_pixels = np.sum(adaptive_thresh > 200)
            else:
                # Nighttime: uniform dark areas are clouds (block stars)
                # Use texture variance as indicator
                variance = cv2.Laplacian(blurred, cv2.CV_64F).var()
                # Low variance = smooth = clouds
                cloud_coverage = max(0, min(100, 100 - (variance / 100)))
                return cloud_coverage

            total_pixels = adaptive_thresh.size
            cloud_coverage = (cloud_pixels / total_pixels) * 100

            # Clamp to 0-100
            return max(0, min(100, cloud_coverage))

        except Exception as e:
            self.log("WARNING", f"Cloud calculation error: {e}")
            return 50  # Default to 50% if calculation fails

    def store_photo(self):
        """Store photo to NAS with organized directory structure"""
        try:
            # Create directory structure: /atmosbird/ruwe_foto/YYYY/MM/DD/
            year = self.timestamp.strftime("%Y")
            month = self.timestamp.strftime("%m")
            day = self.timestamp.strftime("%d")

            target_dir = Path(RAW_PHOTO_DIR) / year / month / day
            target_dir.mkdir(parents=True, exist_ok=True)

            # Generate filename
            filename = f"sky_{self.timestamp.strftime('%Y%m%d_%H%M%S')}.jpg"
            self.final_image_path = str(target_dir / filename)

            # Move file from temp to final location
            import shutil
            shutil.move(self.temp_image_path, self.final_image_path)

            self.log("INFO", f"Photo stored: {self.final_image_path}")
            return True

        except Exception as e:
            self.log("ERROR", f"Storage failed: {e}")
            return False

    def save_to_database(self, analysis):
        """Save observation to PostgreSQL"""
        try:
            cursor = self.conn.cursor()

            # Get file size
            file_size = os.path.getsize(self.final_image_path)

            # Insert into sky_observations table
            query = """
                INSERT INTO sky_observations (
                    observation_timestamp, sky_type, cloud_coverage,
                    brightness, image_path, quality_score
                ) VALUES (
                    %s, %s, %s, %s, %s, %s
                ) RETURNING id
            """

            cursor.execute(query, (
                self.timestamp,
                analysis['sky_type'],
                int(analysis['cloud_coverage_percent']),
                analysis['brightness_mean'],
                self.final_image_path,
                int(analysis['contrast_score'])
            ))

            observation_id = cursor.fetchone()[0]
            self.conn.commit()

            self.log("INFO", f"Saved to database: observation_id={observation_id}")
            return observation_id

        except Exception as e:
            self.log("ERROR", f"Database save failed: {e}")
            if self.conn:
                self.conn.rollback()
            return None

    def update_health_metrics(self, success):
        """Update AtmosBird health metrics"""
        try:
            cursor = self.conn.cursor()

            # Get disk usage
            stat = os.statvfs(NAS_BASE)
            disk_usage_percent = ((stat.f_blocks - stat.f_bavail) / stat.f_blocks) * 100

            # Count photos captured today
            today_start = self.timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
            cursor.execute(
                "SELECT COUNT(*) FROM sky_observations WHERE observation_timestamp >= %s",
                (today_start,)
            )
            photos_today = cursor.fetchone()[0]

            # Insert health record
            query = """
                INSERT INTO atmosbird_health (
                    measurement_timestamp, station_id, disk_usage_percent,
                    photos_captured_today, last_capture_success, last_capture_timestamp
                ) VALUES (
                    %s, %s, %s, %s, %s, %s
                )
            """

            cursor.execute(query, (
                self.timestamp,
                STATION_ID,
                disk_usage_percent,
                photos_today,
                success,
                self.timestamp
            ))

            self.conn.commit()
            self.log("INFO", f"Health updated: {photos_today} photos today, {disk_usage_percent:.1f}% disk")

        except Exception as e:
            self.log("WARNING", f"Health update failed: {e}")

    def cleanup(self):
        """Cleanup temporary files and close connections"""
        try:
            # Remove temp file if still exists
            if self.temp_image_path and os.path.exists(self.temp_image_path):
                os.remove(self.temp_image_path)

            # Close database connection
            if self.conn:
                self.conn.close()

        except Exception as e:
            self.log("WARNING", f"Cleanup error: {e}")

    def run(self):
        """Main execution flow"""
        try:
            self.log("INFO", "=== AtmosBird Capture Started ===")

            # Connect to database
            if not self.connect_db():
                return False

            # Capture photo
            if not self.capture_photo():
                self.update_health_metrics(False)
                return False

            # Analyze image
            analysis = self.analyze_image()
            if not analysis:
                self.update_health_metrics(False)
                return False

            # Store photo to NAS
            if not self.store_photo():
                self.update_health_metrics(False)
                return False

            # Save to database
            observation_id = self.save_to_database(analysis)
            if not observation_id:
                self.update_health_metrics(False)
                return False

            # Update health metrics
            self.update_health_metrics(True)

            self.log("INFO", "=== AtmosBird Capture Completed Successfully ===")
            return True

        except Exception as e:
            self.log("ERROR", f"Unexpected error: {e}")
            return False

        finally:
            self.cleanup()


def main():
    capture = SkyCapture()
    success = capture.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
