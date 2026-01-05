#!/usr/bin/env python3
"""
AtmosBird Sky Capture Script
Captures sky photos every 10 minutes with Pi Camera NoIR
Analyzes cloud coverage using AI model and stores to NAS + PostgreSQL

Refactored: 2025-12-30 - AI cloud classifier integration
"""

import os
import sys
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict

import numpy as np
from PIL import Image
import cv2
import psycopg2

# Add project root to path for core modules
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import EMSN core modules
from scripts.core.logging import EMSNLogger
from scripts.core.config import get_postgres_config

# Import AI cloud classifier
from cloud_classifier_inference import get_classifier, CloudClassifierONNX

# Configuration
CAMERA_WIDTH = 4608
CAMERA_HEIGHT = 2592
STATION_ID = "berging"

# Storage paths
NAS_BASE = "/mnt/usb/atmosbird"
RAW_PHOTO_DIR = f"{NAS_BASE}/ruwe_foto"
TEMP_DIR = "/tmp/atmosbird"

# AI Model path
MODEL_PATH = Path(__file__).parent / "cloud_classifier.onnx"

# Database configuration
DB_CONFIG = get_postgres_config()

# Fallback thresholds (only used when AI model unavailable)
DAYTIME_BRIGHTNESS_THRESHOLD = 100

# Module logger
_logger = EMSNLogger('atmosbird_capture', Path('/mnt/usb/logs'))


class SkyCapture:
    """Captures and analyzes sky images for cloud coverage detection."""

    def __init__(self):
        self.timestamp = datetime.now()
        self.temp_image_path: Optional[str] = None
        self.final_image_path: Optional[str] = None
        self.conn: Optional[psycopg2.extensions.connection] = None
        self.logger = _logger
        self.ai_classifier: Optional[CloudClassifierONNX] = None

        Path(TEMP_DIR).mkdir(parents=True, exist_ok=True)
        self._init_ai_classifier()

    def _init_ai_classifier(self) -> None:
        """Initialize AI cloud classifier if available."""
        if MODEL_PATH.exists():
            try:
                self.ai_classifier = get_classifier(MODEL_PATH)
                if self.ai_classifier:
                    self.log("INFO", "AI cloud classifier loaded")
            except Exception as e:
                self.log("WARNING", f"AI classifier init failed: {e}")
                self.ai_classifier = None
        else:
            self.log("WARNING", f"AI model not found: {MODEL_PATH}")

    def log(self, level: str, message: str) -> None:
        """Log message via core logger."""
        self.logger.log(level, message)

    def connect_db(self) -> bool:
        """Connect to PostgreSQL database."""
        try:
            self.conn = psycopg2.connect(**DB_CONFIG)
            self.log("INFO", "Connected to database")
            return True
        except Exception as e:
            self.log("ERROR", f"Database connection failed: {e}")
            return False

    def capture_photo(self) -> bool:
        """Capture photo with rpicam-still."""
        try:
            self.temp_image_path = (
                f"{TEMP_DIR}/capture_{self.timestamp.strftime('%Y%m%d_%H%M%S')}.jpg"
            )

            cmd = [
                "rpicam-still",
                "-o", self.temp_image_path,
                "--width", str(CAMERA_WIDTH),
                "--height", str(CAMERA_HEIGHT),
                "--rotation", "180",
                "--timeout", "2000",
                "--quality", "95",
                "--encoding", "jpg",
                "-n"
            ]

            self.log("INFO", f"Capturing photo: {CAMERA_WIDTH}x{CAMERA_HEIGHT}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode != 0:
                self.log("ERROR", f"Capture failed: {result.stderr}")
                return False

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

    def analyze_image(self) -> Optional[Dict]:
        """Analyze captured image for cloud coverage and brightness."""
        try:
            # Load image for brightness analysis
            img = cv2.imread(self.temp_image_path)
            if img is None:
                self.log("ERROR", "Failed to load image for analysis")
                return None

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            brightness_mean = float(np.mean(gray))
            brightness_std = float(np.std(gray))
            contrast_score = brightness_std
            is_daytime = brightness_mean > DAYTIME_BRIGHTNESS_THRESHOLD

            # Use AI classifier for cloud detection
            if self.ai_classifier:
                result = self._analyze_with_ai()
                if result:
                    cloud_coverage = result['cloud_coverage_percent']
                    sky_type = self._map_class_to_sky_type(result['class_name'])
                    confidence = result['confidence']
                    self.log(
                        "INFO",
                        f"AI Analysis: {result['class_name']} ({confidence:.0%}), "
                        f"clouds={cloud_coverage:.1f}%"
                    )
                else:
                    cloud_coverage, sky_type = self._analyze_fallback(gray, brightness_mean)
            else:
                cloud_coverage, sky_type = self._analyze_fallback(gray, brightness_mean)

            self.log(
                "INFO",
                f"Analysis: brightness={brightness_mean:.1f}, clouds={cloud_coverage:.1f}%, "
                f"contrast={contrast_score:.1f}, daytime={is_daytime}, type={sky_type}"
            )

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

    def _analyze_with_ai(self) -> Optional[Dict]:
        """Run AI cloud classifier on image."""
        try:
            return self.ai_classifier.predict(self.temp_image_path)
        except Exception as e:
            self.log("WARNING", f"AI analysis failed, using fallback: {e}")
            return None

    def _map_class_to_sky_type(self, class_name: str) -> str:
        """Map AI class name to database sky_type."""
        mapping = {
            'helder': 'clear',
            'gedeeltelijk': 'partly_cloudy',
            'bewolkt': 'overcast'
        }
        return mapping.get(class_name, 'partly_cloudy')

    def _analyze_fallback(self, gray_image: np.ndarray, brightness: float) -> tuple:
        """Fallback cloud analysis when AI model unavailable."""
        try:
            blurred = cv2.GaussianBlur(gray_image, (21, 21), 0)

            if brightness > DAYTIME_BRIGHTNESS_THRESHOLD:
                adaptive_thresh = cv2.adaptiveThreshold(
                    blurred, 255,
                    cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    cv2.THRESH_BINARY,
                    51, 10
                )
                cloud_pixels = np.sum(adaptive_thresh > 200)
                cloud_coverage = (cloud_pixels / adaptive_thresh.size) * 100
            else:
                variance = cv2.Laplacian(blurred, cv2.CV_64F).var()
                cloud_coverage = max(0, min(100, 100 - (variance / 100)))

            cloud_coverage = max(0, min(100, cloud_coverage))

            if cloud_coverage < 20:
                sky_type = "clear"
            elif cloud_coverage > 80:
                sky_type = "overcast"
            else:
                sky_type = "partly_cloudy"

            self.log("INFO", "Using fallback cloud analysis")
            return cloud_coverage, sky_type

        except Exception as e:
            self.log("WARNING", f"Fallback analysis error: {e}")
            return 50.0, "partly_cloudy"

    def store_photo(self) -> bool:
        """Store photo to NAS with organized directory structure."""
        try:
            year = self.timestamp.strftime("%Y")
            month = self.timestamp.strftime("%m")
            day = self.timestamp.strftime("%d")

            target_dir = Path(RAW_PHOTO_DIR) / year / month / day
            target_dir.mkdir(parents=True, exist_ok=True)

            filename = f"sky_{self.timestamp.strftime('%Y%m%d_%H%M%S')}.jpg"
            self.final_image_path = str(target_dir / filename)

            shutil.move(self.temp_image_path, self.final_image_path)
            self.log("INFO", f"Photo stored: {self.final_image_path}")
            return True

        except Exception as e:
            self.log("ERROR", f"Storage failed: {e}")
            return False

    def save_to_database(self, analysis: Dict) -> Optional[int]:
        """Save observation to PostgreSQL."""
        try:
            cursor = self.conn.cursor()

            query = """
                INSERT INTO sky_observations (
                    observation_timestamp, sky_type, cloud_coverage,
                    brightness, image_path, quality_score
                ) VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
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

    def update_health_metrics(self, success: bool) -> None:
        """Update AtmosBird health metrics."""
        try:
            cursor = self.conn.cursor()

            stat = os.statvfs(NAS_BASE)
            disk_usage_percent = ((stat.f_blocks - stat.f_bavail) / stat.f_blocks) * 100

            today_start = self.timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
            cursor.execute(
                "SELECT COUNT(*) FROM sky_observations WHERE observation_timestamp >= %s",
                (today_start,)
            )
            photos_today = cursor.fetchone()[0]

            query = """
                INSERT INTO atmosbird_health (
                    measurement_timestamp, station_id, disk_usage_percent,
                    photos_captured_today, last_capture_success, last_capture_timestamp
                ) VALUES (%s, %s, %s, %s, %s, %s)
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

    def cleanup(self) -> None:
        """Cleanup temporary files and close connections."""
        try:
            if self.temp_image_path and os.path.exists(self.temp_image_path):
                os.remove(self.temp_image_path)

            if self.conn:
                self.conn.close()

        except Exception as e:
            self.log("WARNING", f"Cleanup error: {e}")

    def run(self) -> bool:
        """Main execution flow."""
        try:
            self.log("INFO", "=== AtmosBird Capture Started ===")

            if not self.connect_db():
                return False

            if not self.capture_photo():
                self.update_health_metrics(False)
                return False

            analysis = self.analyze_image()
            if not analysis:
                self.update_health_metrics(False)
                return False

            if not self.store_photo():
                self.update_health_metrics(False)
                return False

            observation_id = self.save_to_database(analysis)
            if not observation_id:
                self.update_health_metrics(False)
                return False

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
