#!/usr/bin/env python3
"""
FlySafe Radar Timelapse Generator
=================================

Creates timelapse videos from saved radar images to visualize
bird migration patterns over time.

Requirements:
- ffmpeg (for video generation)
- PIL/Pillow (for image processing)

Author: EMSN Team
"""

import os
import subprocess
import shutil
from datetime import datetime, timedelta
from pathlib import Path
import logging
from PIL import Image, ImageDraw, ImageFont

# Configuration
STORAGE_BASE = Path("/mnt/usb/flysafe")
IMAGES_DIR = STORAGE_BASE / "images"
TIMELAPSE_DIR = STORAGE_BASE / "timelapses"
LOGS_DIR = Path("/mnt/usb/logs")

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOGS_DIR / "timelapse-generator.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class TimelapseGenerator:
    """Generates timelapse videos from radar images"""

    def __init__(self):
        TIMELAPSE_DIR.mkdir(parents=True, exist_ok=True)

    def get_images_for_period(self, station, start_date, end_date):
        """Get all radar images for a date range"""
        images = []
        current_date = start_date

        while current_date <= end_date:
            date_path = IMAGES_DIR / station / current_date.strftime('%Y/%m/%d')

            if date_path.exists():
                for img_file in sorted(date_path.glob('radar_*.png')):
                    images.append({
                        'path': img_file,
                        'timestamp': self._extract_timestamp(img_file.name)
                    })

            current_date += timedelta(days=1)

        logger.info(f"Found {len(images)} images for {station} from {start_date} to {end_date}")
        return sorted(images, key=lambda x: x['timestamp'])

    def _extract_timestamp(self, filename):
        """Extract timestamp from filename like radar_herwijnen_20251212_195731.png"""
        try:
            parts = filename.replace('.png', '').split('_')
            date_str = parts[2]
            time_str = parts[3]
            return datetime.strptime(f"{date_str}_{time_str}", '%Y%m%d_%H%M%S')
        except (IndexError, ValueError):
            return datetime.now()

    def add_timestamp_overlay(self, image_path, timestamp, output_path):
        """Add timestamp overlay to image"""
        try:
            img = Image.open(image_path)

            # Create draw object
            draw = ImageDraw.Draw(img)

            # Try to use a nice font, fallback to default
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
            except (IOError, OSError):
                font = ImageFont.load_default()

            # Format timestamp
            text = timestamp.strftime('%Y-%m-%d %H:%M')

            # Add semi-transparent background for text
            bbox = draw.textbbox((10, 10), text, font=font)
            padding = 5
            draw.rectangle(
                [bbox[0] - padding, bbox[1] - padding,
                 bbox[2] + padding, bbox[3] + padding],
                fill=(0, 0, 0, 180)
            )

            # Draw text
            draw.text((10, 10), text, fill=(255, 255, 255), font=font)

            img.save(output_path)
            return True

        except Exception as e:
            logger.error(f"Failed to add overlay: {e}")
            # Just copy original if overlay fails
            shutil.copy(image_path, output_path)
            return False

    def create_timelapse(self, station, start_date, end_date, fps=4, output_name=None):
        """
        Create timelapse video from radar images

        Args:
            station: Radar station name
            start_date: Start date (datetime or string YYYY-MM-DD)
            end_date: End date (datetime or string YYYY-MM-DD)
            fps: Frames per second (default 4)
            output_name: Custom output filename
        """
        # Parse dates if strings
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, '%Y-%m-%d')

        logger.info(f"Creating timelapse for {station}: {start_date.date()} to {end_date.date()}")

        # Get images
        images = self.get_images_for_period(station, start_date, end_date)

        if not images:
            logger.warning("No images found for timelapse")
            return None

        # Create temp directory for processed frames
        temp_dir = TIMELAPSE_DIR / f"temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Process images with timestamp overlay
            logger.info(f"Processing {len(images)} frames...")
            for i, img_info in enumerate(images):
                frame_path = temp_dir / f"frame_{i:05d}.png"
                self.add_timestamp_overlay(
                    img_info['path'],
                    img_info['timestamp'],
                    frame_path
                )

            # Generate output filename
            if output_name is None:
                output_name = f"timelapse_{station}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.mp4"

            output_path = TIMELAPSE_DIR / output_name

            # Create video with ffmpeg
            logger.info(f"Generating video at {fps} fps...")

            cmd = [
                'ffmpeg', '-y',
                '-framerate', str(fps),
                '-i', str(temp_dir / 'frame_%05d.png'),
                '-c:v', 'libx264',
                '-pix_fmt', 'yuv420p',
                '-crf', '23',
                '-preset', 'medium',
                str(output_path)
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                logger.info(f"Timelapse created: {output_path}")
                return str(output_path)
            else:
                logger.error(f"ffmpeg error: {result.stderr}")
                return None

        finally:
            # Cleanup temp directory
            if temp_dir.exists():
                shutil.rmtree(temp_dir)

    def create_daily_timelapse(self, station, date=None):
        """Create timelapse for a single day"""
        if date is None:
            date = datetime.now().date()
        elif isinstance(date, str):
            date = datetime.strptime(date, '%Y-%m-%d').date()

        start = datetime.combine(date, datetime.min.time())
        end = datetime.combine(date, datetime.max.time())

        return self.create_timelapse(
            station, start, end, fps=2,
            output_name=f"timelapse_{station}_{date.strftime('%Y%m%d')}_daily.mp4"
        )

    def create_weekly_timelapse(self, station, end_date=None):
        """Create timelapse for the last 7 days"""
        if end_date is None:
            end_date = datetime.now()
        elif isinstance(end_date, str):
            end_date = datetime.strptime(end_date, '%Y-%m-%d')

        start_date = end_date - timedelta(days=7)

        return self.create_timelapse(
            station, start_date, end_date, fps=6,
            output_name=f"timelapse_{station}_{end_date.strftime('%Y%m%d')}_weekly.mp4"
        )

    def create_gif(self, station, start_date, end_date, output_name=None):
        """Create animated GIF from radar images (for sharing)"""
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, '%Y-%m-%d')

        images = self.get_images_for_period(station, start_date, end_date)

        if not images:
            logger.warning("No images found for GIF")
            return None

        # Limit to max 50 frames for GIF
        if len(images) > 50:
            step = len(images) // 50
            images = images[::step][:50]

        if output_name is None:
            output_name = f"radar_{station}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.gif"

        output_path = TIMELAPSE_DIR / output_name

        try:
            frames = []
            for img_info in images:
                img = Image.open(img_info['path'])
                # Resize for smaller GIF
                img = img.resize((320, 215), Image.Resampling.LANCZOS)
                frames.append(img)

            if frames:
                frames[0].save(
                    output_path,
                    save_all=True,
                    append_images=frames[1:],
                    duration=250,  # 250ms per frame
                    loop=0
                )
                logger.info(f"GIF created: {output_path}")
                return str(output_path)

        except Exception as e:
            logger.error(f"Failed to create GIF: {e}")
            return None


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='FlySafe Radar Timelapse Generator')
    parser.add_argument('--station', default='herwijnen', help='Radar station')
    parser.add_argument('--start', help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', help='End date (YYYY-MM-DD)')
    parser.add_argument('--daily', action='store_true', help='Create daily timelapse')
    parser.add_argument('--weekly', action='store_true', help='Create weekly timelapse')
    parser.add_argument('--gif', action='store_true', help='Create GIF instead of video')
    parser.add_argument('--fps', type=int, default=4, help='Frames per second')
    parser.add_argument('--list', action='store_true', help='List available images')

    args = parser.parse_args()

    generator = TimelapseGenerator()

    if args.list:
        # List available images
        today = datetime.now()
        week_ago = today - timedelta(days=7)
        images = generator.get_images_for_period(args.station, week_ago, today)
        print(f"\nAvailable images for {args.station} (last 7 days): {len(images)}")
        if images:
            print(f"First: {images[0]['timestamp']}")
            print(f"Last:  {images[-1]['timestamp']}")
        return

    if args.daily:
        generator.create_daily_timelapse(args.station, args.start)
    elif args.weekly:
        generator.create_weekly_timelapse(args.station, args.end)
    elif args.start and args.end:
        if args.gif:
            generator.create_gif(args.station, args.start, args.end)
        else:
            generator.create_timelapse(args.station, args.start, args.end, fps=args.fps)
    else:
        print("Please specify --daily, --weekly, or --start/--end dates")
        print("Use --list to see available images")


if __name__ == '__main__':
    main()
