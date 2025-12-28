#!/usr/bin/env python3
"""
EMSN 2.0 - Vocalization Enricher Service

Verrijkt bird_detections in de database met vocalisatie type (zang/roep/alarm).
Draait periodiek en classificeert detecties waar vocalization_type NULL is.

Audio wordt opgehaald via:
- Lokaal filesystem voor zolder
- SSH voor berging (robuuster dan SSHFS mount)
"""

import sys
import time
import tempfile
import subprocess
import psycopg2
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.vocalization.vocalization_classifier import VocalizationClassifier

# Configuration
PG_CONFIG = {
    'host': '192.168.1.25',
    'port': 5433,
    'database': 'emsn',
    'user': 'birdpi_zolder',
    'password': 'IwnadBon2iN'
}

# BirdNET audio locations per station
AUDIO_PATHS = {
    'zolder': Path('/home/ronny/BirdSongs/Extracted/By_Date'),
    'berging': '/home/ronny/BirdSongs/Extracted/By_Date'  # Remote path on berging
}

# SSH config for berging
BERGING_SSH = {
    'host': '192.168.1.87',
    'user': 'ronny',
}

LOG_DIR = Path('/mnt/usb/logs')
BATCH_SIZE = 200  # TURBO MODE: verhoogd van 50 voor snellere backlog verwerking


class VocalizationEnricher:
    """Enriches bird detections with vocalization type."""

    def __init__(self):
        self.pg_conn = None
        self.classifier = None
        self.log_file = LOG_DIR / f"vocalization_enricher_{datetime.now().strftime('%Y%m%d')}.log"
        LOG_DIR.mkdir(parents=True, exist_ok=True)

    def log(self, level, message):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        entry = f"[{timestamp}] [{level}] {message}"
        print(entry)
        with open(self.log_file, 'a') as f:
            f.write(entry + '\n')

    def connect(self):
        """Connect to PostgreSQL database."""
        try:
            self.pg_conn = psycopg2.connect(**PG_CONFIG)
            self.log('INFO', 'Connected to PostgreSQL')
            return True
        except Exception as e:
            self.log('ERROR', f'Database connection failed: {e}')
            return False

    def init_classifier(self):
        """Initialize the vocalization classifier."""
        try:
            self.classifier = VocalizationClassifier()
            self.log('INFO', 'Vocalization classifier initialized')
            return True
        except Exception as e:
            self.log('ERROR', f'Failed to initialize classifier: {e}')
            return False

    def get_pending_detections(self, limit=BATCH_SIZE):
        """Get detections that need vocalization classification."""
        try:
            cursor = self.pg_conn.cursor()

            # Get all detections without vocalization type
            # Both stations now have audio access (berging via SSHFS)
            # No date limit - process entire history
            query = """
                SELECT id, station, common_name, date, time, file_name
                FROM bird_detections
                WHERE vocalization_type IS NULL
                  AND station IN ('zolder', 'berging')
                ORDER BY detection_timestamp DESC
                LIMIT %s
            """

            cursor.execute(query, (limit,))
            rows = cursor.fetchall()

            detections = []
            for row in rows:
                detections.append({
                    'id': row[0],
                    'station': row[1],
                    'common_name': row[2],
                    'date': row[3],
                    'time': row[4],
                    'file_name': row[5]
                })

            return detections

        except Exception as e:
            self.log('ERROR', f'Error fetching pending detections: {e}')
            return []

    def find_audio_file(self, detection):
        """Find the audio file for a detection.

        For zolder: returns local Path
        For berging: fetches via SSH and returns temp file path
        """
        station = detection['station']
        base_path = AUDIO_PATHS.get(station)

        if not base_path:
            return None

        # BirdNET-Pi organizes files as:
        # By_Date/YYYY-MM-DD/Species_Name/filename.mp3
        date_str = detection['date'].strftime('%Y-%m-%d')
        species_dir_name = detection['common_name'].replace(' ', '_')
        file_name = detection['file_name']

        if station == 'zolder':
            # Local filesystem access
            return self._find_local_audio(base_path, date_str, species_dir_name, file_name, detection)
        else:
            # Berging: fetch via SSH
            return self._fetch_berging_audio(base_path, date_str, species_dir_name, file_name)

    def _find_local_audio(self, base_path, date_str, species_dir_name, file_name, detection):
        """Find audio file on local filesystem (zolder)."""
        date_dir = base_path / date_str / species_dir_name

        if not date_dir.exists():
            return None

        if file_name:
            # Try exact match first
            audio_file = date_dir / file_name
            if audio_file.exists():
                return audio_file

            # Try with .mp3 extension
            if not file_name.endswith('.mp3'):
                audio_file = date_dir / f"{file_name}.mp3"
                if audio_file.exists():
                    return audio_file

        # Fallback: get most recent file in directory matching the time
        time_str = detection['time'].strftime('%H%M%S') if detection['time'] else None

        for audio_file in sorted(date_dir.glob('*.mp3'), reverse=True):
            if time_str and time_str in audio_file.name:
                return audio_file

        # Last resort: return any file
        files = list(date_dir.glob('*.mp3'))
        if files:
            return files[0]

        return None

    def _fetch_berging_audio(self, base_path, date_str, species_dir_name, file_name):
        """Fetch audio file from berging via SSH.

        Returns path to temporary file, or None if not found.
        """
        if not file_name:
            return None

        remote_path = f"{base_path}/{date_str}/{species_dir_name}/{file_name}"

        # Create temp file for the audio
        temp_file = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
        temp_path = temp_file.name
        temp_file.close()

        try:
            # Use scp to fetch the file
            cmd = [
                'scp', '-q', '-o', 'ConnectTimeout=5',
                f"{BERGING_SSH['user']}@{BERGING_SSH['host']}:{remote_path}",
                temp_path
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=30)

            if result.returncode == 0 and Path(temp_path).stat().st_size > 0:
                return Path(temp_path)
            else:
                # File not found or error
                Path(temp_path).unlink(missing_ok=True)
                return None

        except (subprocess.TimeoutExpired, Exception) as e:
            Path(temp_path).unlink(missing_ok=True)
            return None

    def classify_detection(self, detection):
        """Classify a single detection."""
        common_name = detection['common_name']
        station = detection['station']

        # Check if we have a model for this species
        if not self.classifier.has_model(common_name):
            return None, None

        # Find audio file
        audio_file = self.find_audio_file(detection)
        if not audio_file:
            return None, None

        # Classify
        try:
            result = self.classifier.classify(common_name, str(audio_file))
            if result:
                return result['type_nl'], result['confidence']
        except Exception as e:
            self.log('WARNING', f"Classification error for {common_name}: {e}")
        finally:
            # Cleanup temp files (berging audio fetched via SSH)
            if station == 'berging' and audio_file and '/tmp/' in str(audio_file):
                try:
                    Path(audio_file).unlink(missing_ok=True)
                except:
                    pass

        return None, None

    def update_detection(self, detection_id, voc_type, confidence):
        """Update a detection with vocalization info."""
        try:
            cursor = self.pg_conn.cursor()

            query = """
                UPDATE bird_detections
                SET vocalization_type = %s,
                    vocalization_confidence = %s
                WHERE id = %s
            """

            cursor.execute(query, (voc_type, confidence, detection_id))
            self.pg_conn.commit()
            return True

        except Exception as e:
            self.pg_conn.rollback()
            self.log('ERROR', f'Error updating detection {detection_id}: {e}')
            return False

    def process_batch(self):
        """Process a batch of pending detections."""
        detections = self.get_pending_detections()

        if not detections:
            self.log('INFO', 'No pending detections to process')
            return 0

        self.log('INFO', f'Processing {len(detections)} detections...')

        enriched = 0
        skipped = 0

        for det in detections:
            voc_type, confidence = self.classify_detection(det)

            if voc_type:
                if self.update_detection(det['id'], voc_type, confidence):
                    enriched += 1
                    self.log('INFO', f"  {det['common_name']}: {voc_type} ({confidence:.0f}%)")
            else:
                skipped += 1

        self.log('INFO', f'Batch complete: {enriched} enriched, {skipped} skipped')
        return enriched

    def run_once(self):
        """Run enrichment once."""
        self.log('INFO', '=' * 60)
        self.log('INFO', 'Vocalization Enricher - Single Run')
        self.log('INFO', '=' * 60)

        if not self.connect():
            return False

        if not self.init_classifier():
            return False

        try:
            total = 0
            while True:
                enriched = self.process_batch()
                total += enriched
                if enriched == 0:
                    break

            self.log('SUCCESS', f'Total enriched: {total} detections')
            return True

        finally:
            if self.pg_conn:
                self.pg_conn.close()

    def run_continuous(self, interval_minutes=5):
        """Run enrichment continuously."""
        self.log('INFO', '=' * 60)
        self.log('INFO', f'Vocalization Enricher - Continuous (every {interval_minutes} min)')
        self.log('INFO', '=' * 60)

        if not self.init_classifier():
            return False

        while True:
            try:
                if not self.pg_conn or self.pg_conn.closed:
                    if not self.connect():
                        time.sleep(60)
                        continue

                self.process_batch()

            except Exception as e:
                self.log('ERROR', f'Error in processing loop: {e}')
                if self.pg_conn:
                    try:
                        self.pg_conn.close()
                    except:
                        pass
                    self.pg_conn = None

            time.sleep(interval_minutes * 60)


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Enrich bird detections with vocalization type')
    parser.add_argument('--continuous', action='store_true', help='Run continuously')
    parser.add_argument('--interval', type=int, default=5, help='Interval in minutes (for continuous mode)')
    args = parser.parse_args()

    enricher = VocalizationEnricher()

    if args.continuous:
        enricher.run_continuous(args.interval)
    else:
        enricher.run_once()


if __name__ == '__main__':
    main()
