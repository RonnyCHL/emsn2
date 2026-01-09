#!/usr/bin/env python3
"""
AtmosBird Archive Sync Script
Synchroniseert foto's van lokale USB stick naar NAS 8TB archief.
- Rsync naar NAS met datum-structuur
- Update database archive_path
- Cleanup lokale bestanden ouder dan RETENTION_DAYS
- Genereer thumbnails voor snelle preview

Auteur: Claude Code voor EMSN 2.0
"""

import os
import sys
import subprocess
import psycopg2
from datetime import datetime, timedelta
from pathlib import Path
from PIL import Image

# Configuration
STATION_ID = "berging"
RETENTION_DAYS = 7  # Houd lokaal alleen laatste 7 dagen

# Paths
LOCAL_BASE = "/mnt/usb/atmosbird"
LOCAL_PHOTO_DIR = f"{LOCAL_BASE}/ruwe_foto"
LOCAL_TIMELAPSE_DIR = f"{LOCAL_BASE}/timelapse"

NAS_BASE = "/mnt/nas-birdnet-archive/atmosbird"
NAS_PHOTO_DIR = f"{NAS_BASE}/ruwe_foto"
NAS_TIMELAPSE_DIR = f"{NAS_BASE}/timelapse"
NAS_THUMBNAIL_DIR = f"{NAS_BASE}/thumbnails"

# Thumbnail settings
THUMBNAIL_SIZE = (320, 180)  # 16:9 aspect voor dashboard preview
THUMBNAIL_QUALITY = 75

# Import core modules
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.config import get_postgres_config
from core.logging import get_logger

DB_CONFIG = get_postgres_config()

# Centrale logger
logger = get_logger('atmosbird_archive_sync')


class AtmosBirdArchiveSync:
    def __init__(self):
        self.conn = None
        self.stats = {
            'synced': 0,
            'thumbnails': 0,
            'cleaned': 0,
            'db_updated': 0,
            'errors': 0
        }

    def connect_db(self):
        """Connect to PostgreSQL database"""
        try:
            self.conn = psycopg2.connect(**DB_CONFIG)
            logger.info("Database verbonden")
            return True
        except Exception as e:
            logger.error(f"Database connectie mislukt: {e}")
            return False

    def close_db(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            logger.info("Database verbinding gesloten")

    def check_nas_mount(self):
        """Verify NAS is mounted and accessible"""
        if not os.path.ismount('/mnt/nas-birdnet-archive'):
            logger.error("NAS niet gemount op /mnt/nas-birdnet-archive")
            return False

        # Check write access
        test_file = Path(NAS_BASE) / '.write_test'
        try:
            test_file.touch()
            test_file.unlink()
            logger.info("NAS mount OK en schrijfbaar")
            return True
        except Exception as e:
            logger.error(f"NAS niet schrijfbaar: {e}")
            return False

    def sync_photos(self):
        """Rsync photos from local USB to NAS archive"""
        logger.info("Start foto sync naar NAS...")

        # Ensure destination exists
        Path(NAS_PHOTO_DIR).mkdir(parents=True, exist_ok=True)

        # Rsync with archive mode, preserving structure
        cmd = [
            'rsync', '-av', '--progress',
            '--ignore-existing',  # Skip files that exist on destination
            f'{LOCAL_PHOTO_DIR}/',
            f'{NAS_PHOTO_DIR}/'
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)

            if result.returncode == 0:
                # Count synced files from rsync output
                lines = result.stdout.split('\n')
                for line in lines:
                    if line.endswith('.jpg') and not line.startswith('sending'):
                        self.stats['synced'] += 1

                logger.info(f"Foto sync compleet: {self.stats['synced']} nieuwe bestanden")
            else:
                logger.error(f"Rsync error: {result.stderr}")
                self.stats['errors'] += 1

        except subprocess.TimeoutExpired:
            logger.error("Rsync timeout na 1 uur")
            self.stats['errors'] += 1
        except Exception as e:
            logger.error(f"Rsync exception: {e}")
            self.stats['errors'] += 1

    def sync_timelapses(self):
        """Rsync timelapses from local USB to NAS archive"""
        logger.info("Start timelapse sync naar NAS...")

        Path(NAS_TIMELAPSE_DIR).mkdir(parents=True, exist_ok=True)

        cmd = [
            'rsync', '-av', '--progress',
            '--ignore-existing',
            f'{LOCAL_TIMELAPSE_DIR}/',
            f'{NAS_TIMELAPSE_DIR}/'
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
            if result.returncode == 0:
                logger.info("Timelapse sync compleet")
            else:
                logger.error(f"Timelapse rsync error: {result.stderr}")
        except Exception as e:
            logger.error(f"Timelapse rsync exception: {e}")

    def generate_thumbnails(self):
        """Generate thumbnails for archived photos on NAS"""
        logger.info("Genereer thumbnails...")

        Path(NAS_THUMBNAIL_DIR).mkdir(parents=True, exist_ok=True)

        # Walk through NAS photo directory
        for root, dirs, files in os.walk(NAS_PHOTO_DIR):
            for filename in files:
                if not filename.endswith('.jpg'):
                    continue

                src_path = Path(root) / filename

                # Preserve directory structure for thumbnails
                rel_path = src_path.relative_to(NAS_PHOTO_DIR)
                thumb_path = Path(NAS_THUMBNAIL_DIR) / rel_path

                # Skip if thumbnail exists
                if thumb_path.exists():
                    continue

                try:
                    # Create thumbnail directory
                    thumb_path.parent.mkdir(parents=True, exist_ok=True)

                    # Generate thumbnail
                    with Image.open(src_path) as img:
                        img.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
                        img.save(thumb_path, 'JPEG', quality=THUMBNAIL_QUALITY)

                    self.stats['thumbnails'] += 1

                except Exception as e:
                    logger.warning(f"Thumbnail fout voor {filename}: {e}")

        logger.info(f"Thumbnails gegenereerd: {self.stats['thumbnails']}")

    def update_database_paths(self):
        """Update archive_path in database for synced files"""
        logger.info("Update database archive_path...")

        if not self.conn:
            logger.error("Geen database connectie")
            return

        cursor = self.conn.cursor()

        try:
            # Find records without archive_path but with existing NAS file
            cursor.execute("""
                SELECT id, image_path
                FROM sky_observations
                WHERE image_path IS NOT NULL
                  AND archive_path IS NULL
            """)

            rows = cursor.fetchall()

            for obs_id, local_path in rows:
                if not local_path:
                    continue

                # Convert local path to NAS path
                # /mnt/usb/atmosbird/ruwe_foto/2025/12/27/sky_xxx.jpg
                # -> /mnt/nas-birdnet-archive/atmosbird/ruwe_foto/2025/12/27/sky_xxx.jpg
                nas_path = local_path.replace(LOCAL_BASE, NAS_BASE)

                # Verify file exists on NAS
                if os.path.exists(nas_path):
                    cursor.execute("""
                        UPDATE sky_observations
                        SET archive_path = %s
                        WHERE id = %s
                    """, (nas_path, obs_id))
                    self.stats['db_updated'] += 1

            self.conn.commit()
            logger.info(f"Database geüpdatet: {self.stats['db_updated']} records")

        except Exception as e:
            logger.error(f"Database update fout: {e}")
            self.conn.rollback()
            self.stats['errors'] += 1
        finally:
            cursor.close()

    def cleanup_local_old_files(self):
        """Remove local files older than RETENTION_DAYS"""
        logger.info(f"Cleanup lokale bestanden ouder dan {RETENTION_DAYS} dagen...")

        cutoff_date = datetime.now() - timedelta(days=RETENTION_DAYS)

        for root, dirs, files in os.walk(LOCAL_PHOTO_DIR):
            for filename in files:
                if not filename.endswith('.jpg'):
                    continue

                file_path = Path(root) / filename

                # Check file modification time
                mtime = datetime.fromtimestamp(file_path.stat().st_mtime)

                if mtime < cutoff_date:
                    # Verify it exists on NAS before deleting
                    nas_path = str(file_path).replace(LOCAL_BASE, NAS_BASE)

                    if os.path.exists(nas_path):
                        try:
                            file_path.unlink()
                            self.stats['cleaned'] += 1
                        except Exception as e:
                            logger.warning(f"Kon {filename} niet verwijderen: {e}")
                    else:
                        logger.warning(f"Skip cleanup {filename}: niet op NAS gevonden")

        logger.info(f"Lokaal opgeruimd: {self.stats['cleaned']} bestanden")

        # Cleanup empty directories
        self._cleanup_empty_dirs(LOCAL_PHOTO_DIR)

    def _cleanup_empty_dirs(self, path):
        """Remove empty directories recursively"""
        for root, dirs, files in os.walk(path, topdown=False):
            for dir_name in dirs:
                dir_path = Path(root) / dir_name
                try:
                    if not any(dir_path.iterdir()):
                        dir_path.rmdir()
                        logger.debug(f"Lege directory verwijderd: {dir_path}")
                except Exception:
                    pass

    def run(self):
        """Execute full sync cycle"""
        logger.info("=" * 60)
        logger.info("AtmosBird Archive Sync gestart")
        logger.info("=" * 60)

        start_time = datetime.now()

        # Pre-flight checks
        if not self.check_nas_mount():
            logger.error("Sync afgebroken: NAS niet beschikbaar")
            return False

        if not self.connect_db():
            logger.warning("Sync zonder database update")

        # Execute sync steps
        self.sync_photos()
        self.sync_timelapses()
        self.generate_thumbnails()

        if self.conn:
            self.update_database_paths()
            self.close_db()

        self.cleanup_local_old_files()

        # Summary
        duration = (datetime.now() - start_time).total_seconds()

        logger.info("=" * 60)
        logger.info("Sync voltooid!")
        logger.info(f"  Foto's gesynct:      {self.stats['synced']}")
        logger.info(f"  Thumbnails gemaakt:  {self.stats['thumbnails']}")
        logger.info(f"  Database updates:    {self.stats['db_updated']}")
        logger.info(f"  Lokaal opgeruimd:    {self.stats['cleaned']}")
        logger.info(f"  Errors:              {self.stats['errors']}")
        logger.info(f"  Duur:                {duration:.1f} seconden")
        logger.info("=" * 60)

        return self.stats['errors'] == 0


def main():
    syncer = AtmosBirdArchiveSync()
    success = syncer.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
