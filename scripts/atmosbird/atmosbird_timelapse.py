#!/usr/bin/env python3
"""
AtmosBird Timelapse Generator
Creates daily timelapse videos from sky observations
"""

import os
import sys
import psycopg2
from datetime import datetime, timedelta
from pathlib import Path
import subprocess
import shutil

# Configuration
STATION_ID = "berging"
TIMELAPSE_DIR = "/mnt/usb/atmosbird/timelapse"
TEMP_DIR = "/tmp/atmosbird_timelapse"
FPS = 24  # Frames per second for output video

# Database configuration
DB_CONFIG = {
    'host': '192.168.1.25',
    'port': 5433,
    'database': 'emsn',
    'user': 'postgres',
    'password': 'REDACTED_DB_PASS'
}


class TimelapseGenerator:
    def __init__(self, date=None):
        """
        Initialize timelapse generator
        date: datetime object for which day to generate (default: yesterday)
        """
        self.conn = None
        if date:
            self.target_date = date
        else:
            # Default to yesterday (run at midnight for previous day)
            self.target_date = datetime.now() - timedelta(days=1)

        self.temp_dir = Path(TEMP_DIR) / self.target_date.strftime("%Y%m%d")
        self.temp_dir.mkdir(parents=True, exist_ok=True)

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

    def get_observations(self, daytime_only=False, nighttime_only=False):
        """
        Get all observations for target date
        """
        try:
            cursor = self.conn.cursor()

            # Define time range
            start_time = self.target_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_time = start_time + timedelta(days=1)

            query = """
                SELECT id, observation_timestamp, image_path, brightness, cloud_coverage, sky_type
                FROM sky_observations
                WHERE observation_timestamp >= %s AND observation_timestamp < %s
            """

            # Add day/night filter if requested
            if daytime_only:
                query += " AND brightness > 80"
            elif nighttime_only:
                query += " AND brightness <= 80"

            query += " ORDER BY observation_timestamp ASC"

            cursor.execute(query, (start_time, end_time))
            observations = cursor.fetchall()

            self.log("INFO", f"Found {len(observations)} observations for {self.target_date.strftime('%Y-%m-%d')}")
            return observations

        except Exception as e:
            self.log("ERROR", f"Failed to get observations: {e}")
            return []

    def create_timelapse(self, observations, output_name, timelapse_type="daily"):
        """
        Create timelapse video from observations
        """
        try:
            if len(observations) < 2:
                self.log("WARNING", f"Not enough frames ({len(observations)}) for timelapse")
                return None

            self.log("INFO", f"Creating timelapse '{output_name}' from {len(observations)} frames")

            # Create symlinks to images in temp directory with sequential naming
            symlink_dir = self.temp_dir / "frames"
            symlink_dir.mkdir(parents=True, exist_ok=True)

            for idx, obs in enumerate(observations):
                obs_id, obs_time, image_path, brightness, clouds, sky_type = obs

                if not os.path.exists(image_path):
                    self.log("WARNING", f"Image not found: {image_path}")
                    continue

                # Create symlink with sequential name
                symlink_path = symlink_dir / f"frame_{idx:05d}.jpg"
                if symlink_path.exists():
                    symlink_path.unlink()

                symlink_path.symlink_to(image_path)

            # Count actual frames
            frame_count = len(list(symlink_dir.glob("frame_*.jpg")))
            if frame_count < 2:
                self.log("WARNING", f"Not enough valid frames ({frame_count}) for timelapse")
                return None

            # Calculate duration
            duration_seconds = frame_count / FPS

            # Create output directory
            output_dir = Path(TIMELAPSE_DIR) / self.target_date.strftime("%Y") / self.target_date.strftime("%m")
            output_dir.mkdir(parents=True, exist_ok=True)

            output_path = output_dir / f"{output_name}.mp4"

            # Use ffmpeg to create timelapse
            cmd = [
                "ffmpeg",
                "-y",  # Overwrite output file
                "-framerate", str(FPS),
                "-pattern_type", "glob",
                "-i", str(symlink_dir / "frame_*.jpg"),
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-crf", "23",  # Quality (lower = better, 23 is good balance)
                "-preset", "medium",
                str(output_path)
            ]

            self.log("INFO", f"Running ffmpeg: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if result.returncode != 0:
                self.log("ERROR", f"ffmpeg failed: {result.stderr}")
                return None

            if not output_path.exists():
                self.log("ERROR", "Output file not created")
                return None

            file_size = os.path.getsize(output_path)
            self.log("INFO", f"Timelapse created: {output_path} ({file_size / 1024 / 1024:.2f} MB, "
                            f"{duration_seconds:.1f}s @ {FPS}fps)")

            # Calculate statistics from observations
            avg_cloud = sum(obs[4] for obs in observations) / len(observations) if observations else 0
            start_time = observations[0][1]
            end_time = observations[-1][1]

            return {
                'path': str(output_path),
                'file_size': file_size,
                'duration': duration_seconds,
                'frame_count': frame_count,
                'fps': FPS,
                'timelapse_type': timelapse_type,
                'start_time': start_time,
                'end_time': end_time,
                'avg_cloud': avg_cloud
            }

        except subprocess.TimeoutExpired:
            self.log("ERROR", "ffmpeg timeout")
            return None
        except Exception as e:
            self.log("ERROR", f"Timelapse creation failed: {e}")
            return None

    def save_timelapse_metadata(self, metadata):
        """Save timelapse metadata to database"""
        try:
            cursor = self.conn.cursor()

            query = """
                INSERT INTO timelapses (
                    created_timestamp, timelapse_type, start_time, end_time,
                    frame_count, fps, video_path, file_size_bytes,
                    duration_seconds, avg_cloud_coverage
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                ) RETURNING id
            """

            cursor.execute(query, (
                datetime.now(),
                metadata['timelapse_type'],
                metadata['start_time'],
                metadata['end_time'],
                metadata['frame_count'],
                metadata['fps'],
                metadata['path'],
                metadata['file_size'],
                metadata['duration'],
                metadata['avg_cloud']
            ))

            timelapse_id = cursor.fetchone()[0]
            self.conn.commit()

            self.log("INFO", f"Timelapse metadata saved: ID={timelapse_id}")
            return timelapse_id

        except Exception as e:
            self.log("ERROR", f"Failed to save metadata: {e}")
            if self.conn:
                self.conn.rollback()
            return None

    def cleanup(self):
        """Cleanup temporary files"""
        try:
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
                self.log("INFO", "Cleaned up temporary files")
        except Exception as e:
            self.log("WARNING", f"Cleanup failed: {e}")

        if self.conn:
            self.conn.close()

    def run(self):
        """Main execution"""
        try:
            self.log("INFO", f"=== AtmosBird Timelapse Generator Started ===")
            self.log("INFO", f"Target date: {self.target_date.strftime('%Y-%m-%d')}")

            if not self.connect_db():
                return False

            # Generate full day timelapse
            all_obs = self.get_observations()
            if all_obs:
                date_str = self.target_date.strftime("%Y%m%d")
                timelapse = self.create_timelapse(
                    all_obs,
                    f"sky_daily_{date_str}",
                    timelapse_type="daily"
                )
                if timelapse:
                    self.save_timelapse_metadata(timelapse)

            # Generate daytime-only timelapse
            day_obs = self.get_observations(daytime_only=True)
            if len(day_obs) >= 10:  # Minimum 10 frames for meaningful timelapse
                date_str = self.target_date.strftime("%Y%m%d")
                timelapse = self.create_timelapse(
                    day_obs,
                    f"sky_day_{date_str}",
                    timelapse_type="day_only"
                )
                if timelapse:
                    self.save_timelapse_metadata(timelapse)

            # Generate nighttime-only timelapse
            night_obs = self.get_observations(nighttime_only=True)
            if len(night_obs) >= 10:
                date_str = self.target_date.strftime("%Y%m%d")
                timelapse = self.create_timelapse(
                    night_obs,
                    f"sky_night_{date_str}",
                    timelapse_type="night_only"
                )
                if timelapse:
                    self.save_timelapse_metadata(timelapse)

            self.log("INFO", "=== AtmosBird Timelapse Generator Completed ===")
            return True

        except Exception as e:
            self.log("ERROR", f"Unexpected error: {e}")
            return False
        finally:
            self.cleanup()


def main():
    # Support custom date via command line argument
    if len(sys.argv) > 1:
        try:
            date = datetime.strptime(sys.argv[1], "%Y-%m-%d")
        except ValueError:
            print(f"Invalid date format. Use YYYY-MM-DD")
            sys.exit(1)
    else:
        date = None  # Use yesterday

    generator = TimelapseGenerator(date)
    success = generator.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
