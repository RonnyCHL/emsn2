#!/usr/bin/env python3
"""
BirdNET Audio/Spectrogram Archive Sync

Synchroniseert audio en spectrogrammen van BirdNET-Pi stations naar het 8TB NAS archief.
Registreert alle bestanden in de PostgreSQL media_archive tabel.

Structuur op archief:
  /mnt/nas-birdnet-archive/
    audio/
      zolder/2025/12/Koolmees-66-2025-12-22-birdnet-05:19:01.mp3
      berging/2025/12/...
    spectrograms/
      zolder/2025/12/Koolmees-66-2025-12-22-birdnet-05:19:01.mp3.png
      berging/2025/12/...

Auteur: EMSN 2.0
"""

import os
import sys
import logging
import argparse
import subprocess
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple, List, Dict
import psycopg2
from psycopg2.extras import execute_values

# Configuratie
ARCHIVE_BASE = Path("/mnt/nas-birdnet-archive")
STATIONS = {
    "zolder": {
        "host": "localhost",  # Lokaal op deze Pi
        "birdsongs_path": "/home/ronny/BirdSongs/Extracted/By_Date",
        "is_local": True
    },
    "berging": {
        "host": "192.168.1.87",
        "birdsongs_path": "/home/ronny/BirdSongs/Extracted/By_Date",
        "is_local": False,
        "ssh_user": "ronny"
    }
}

# Database configuratie
DB_CONFIG = {
    "host": "192.168.1.25",
    "port": 5433,
    "database": "emsn",
    "user": "birdpi_zolder",
    "password": os.environ.get("PG_PASS", "IwnadBon2iN")
}

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/home/ronny/emsn2/logs/archive_sync.log')
    ]
)
logger = logging.getLogger(__name__)


def parse_filename(filename: str) -> Optional[Dict]:
    """
    Parse BirdNET-Pi bestandsnaam naar metadata.

    Formaat: Soort-confidence-datum-birdnet-tijd.mp3
    Voorbeeld: Koolmees-66-2025-12-22-birdnet-05:19:01.mp3
    """
    # Regex voor BirdNET-Pi bestandsnamen
    pattern = r'^(.+?)-(\d+)-(\d{4}-\d{2}-\d{2})-birdnet-(\d{2}:\d{2}:\d{2})\.mp3$'
    match = re.match(pattern, filename)

    if not match:
        return None

    species, confidence, date_str, time_str = match.groups()

    try:
        detection_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        year = detection_date.year
        month = detection_date.month

        return {
            'species': species.replace('_', ' '),
            'confidence': int(confidence) / 100.0,
            'date': detection_date,
            'year': year,
            'month': month,
            'time': time_str
        }
    except ValueError:
        return None


def get_db_connection():
    """Maak database connectie."""
    return psycopg2.connect(**DB_CONFIG)


def get_archived_files(station: str) -> set:
    """Haal set van reeds gearchiveerde bestanden op."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT original_audio_filename FROM media_archive WHERE station = %s",
                (station,)
            )
            return {row[0] for row in cur.fetchall()}


def find_detection_id(conn, station: str, species: str, date: datetime.date,
                      time_str: str, confidence: float) -> Optional[int]:
    """
    Zoek matching detection_id in bird_detections tabel.
    """
    with conn.cursor() as cur:
        # Probeer exacte match op basis van station, species, date en tijd
        cur.execute("""
            SELECT id FROM bird_detections
            WHERE station = %s
              AND species LIKE %s
              AND date = %s
              AND time::text LIKE %s
            ORDER BY ABS(confidence - %s)
            LIMIT 1
        """, (station, f'%{species}%', date, f'{time_str}%', confidence))

        row = cur.fetchone()
        return row[0] if row else None


def list_remote_files(station_config: dict, path: str) -> List[str]:
    """Lijst bestanden op remote host via SSH."""
    host = station_config['host']
    user = station_config.get('ssh_user', 'ronny')

    cmd = f"ssh -o ConnectTimeout=10 {user}@{host} 'find {path} -type f \\( -name \"*.mp3\" -o -name \"*.png\" \\) 2>/dev/null'"

    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            return [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
    except subprocess.TimeoutExpired:
        logger.error(f"Timeout bij ophalen bestandslijst van {host}")
    except Exception as e:
        logger.error(f"Fout bij ophalen bestandslijst: {e}")

    return []


def list_local_files(path: str) -> List[str]:
    """Lijst lokale bestanden."""
    files = []
    path = Path(path)

    if path.exists():
        for ext in ['*.mp3', '*.png']:
            files.extend([str(f) for f in path.rglob(ext)])

    return files


def copy_file(source: str, dest: str, is_local: bool, station_config: dict) -> bool:
    """Kopieer bestand naar archief."""
    dest_path = Path(dest)
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        if is_local:
            # Lokale copy
            subprocess.run(['cp', source, dest], check=True)
        else:
            # Remote copy via rsync
            host = station_config['host']
            user = station_config.get('ssh_user', 'ronny')
            cmd = f"rsync -az {user}@{host}:{source} {dest}"
            subprocess.run(cmd, shell=True, check=True, timeout=60)

        return True
    except Exception as e:
        logger.error(f"Fout bij kopieren {source}: {e}")
        return False


def get_file_size(filepath: str, is_local: bool, station_config: dict) -> int:
    """Haal bestandsgrootte op."""
    try:
        if is_local:
            return os.path.getsize(filepath)
        else:
            host = station_config['host']
            user = station_config.get('ssh_user', 'ronny')
            cmd = f"ssh {user}@{host} 'stat -c%s {filepath}'"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                return int(result.stdout.strip())
    except Exception:
        pass
    return 0


def sync_station(station: str, dry_run: bool = False, limit: int = None) -> Tuple[int, int]:
    """
    Synchroniseer alle audio/spectrogrammen van een station.

    Returns: (aantal_gekopieerd, aantal_fouten)
    """
    config = STATIONS[station]
    is_local = config.get('is_local', False)
    source_path = config['birdsongs_path']

    logger.info(f"Start sync voor station: {station} ({'lokaal' if is_local else config['host']})")

    # Haal reeds gearchiveerde bestanden op
    archived = get_archived_files(station)
    logger.info(f"  {len(archived)} bestanden reeds gearchiveerd")

    # Haal lijst van alle mp3 bestanden op
    if is_local:
        all_files = list_local_files(source_path)
    else:
        all_files = list_remote_files(config, source_path)

    # Filter alleen mp3 bestanden (niet png, die volgen automatisch)
    mp3_files = [f for f in all_files if f.endswith('.mp3')]
    logger.info(f"  {len(mp3_files)} mp3 bestanden gevonden op bron")

    # Bepaal welke nog niet gearchiveerd zijn
    to_archive = []
    for filepath in mp3_files:
        filename = os.path.basename(filepath)
        if filename not in archived:
            to_archive.append(filepath)

    logger.info(f"  {len(to_archive)} nieuwe bestanden te archiveren")

    if limit:
        to_archive = to_archive[:limit]
        logger.info(f"  Gelimiteerd tot {limit} bestanden")

    if dry_run:
        logger.info("  DRY RUN - geen bestanden worden gekopieerd")
        return len(to_archive), 0

    # Database connectie voor batch inserts
    conn = get_db_connection()
    copied = 0
    errors = 0
    batch_records = []

    for filepath in to_archive:
        filename = os.path.basename(filepath)
        spectrogram_path = filepath + '.png'
        spectrogram_filename = filename + '.png'

        # Parse metadata uit bestandsnaam
        metadata = parse_filename(filename)
        if not metadata:
            logger.warning(f"  Kan bestandsnaam niet parsen: {filename}")
            errors += 1
            continue

        # Bepaal archief paden
        year = metadata['year']
        month = f"{metadata['month']:02d}"

        archive_audio_path = f"audio/{station}/{year}/{month}/{filename}"
        archive_spectrogram_path = f"spectrograms/{station}/{year}/{month}/{spectrogram_filename}"

        full_audio_dest = ARCHIVE_BASE / archive_audio_path
        full_spectrogram_dest = ARCHIVE_BASE / archive_spectrogram_path

        # Kopieer audio
        if copy_file(filepath, str(full_audio_dest), is_local, config):
            # Kopieer spectrogram (als die bestaat)
            copy_file(spectrogram_path, str(full_spectrogram_dest), is_local, config)

            # Haal bestandsgrootte op
            file_size = get_file_size(filepath, is_local, config)

            # Zoek detection_id
            detection_id = find_detection_id(
                conn, station, metadata['species'],
                metadata['date'], metadata['time'], metadata['confidence']
            )

            # Voeg toe aan batch
            batch_records.append((
                detection_id,
                station,
                filename,
                spectrogram_filename,
                archive_audio_path,
                archive_spectrogram_path,
                file_size,
                metadata['date'],
                metadata['species'],
                metadata['confidence']
            ))

            copied += 1

            if copied % 100 == 0:
                logger.info(f"  Voortgang: {copied} bestanden gekopieerd...")
                # Batch insert
                if batch_records:
                    insert_archive_records(conn, batch_records)
                    batch_records = []
        else:
            errors += 1

    # Insert remaining records
    if batch_records:
        insert_archive_records(conn, batch_records)

    conn.close()

    logger.info(f"  Klaar: {copied} gekopieerd, {errors} fouten")
    return copied, errors


def insert_archive_records(conn, records: List[tuple]):
    """Batch insert van archief records."""
    query = """
        INSERT INTO media_archive (
            detection_id, station, original_audio_filename, original_spectrogram_filename,
            archive_audio_path, archive_spectrogram_path, file_size_bytes,
            detection_date, species, confidence
        ) VALUES %s
        ON CONFLICT (station, original_audio_filename) DO NOTHING
    """

    with conn.cursor() as cur:
        execute_values(cur, query, records)
    conn.commit()


def main():
    parser = argparse.ArgumentParser(description='BirdNET Audio/Spectrogram Archive Sync')
    parser.add_argument('--station', choices=['zolder', 'berging', 'all'],
                        default='all', help='Station om te synchroniseren')
    parser.add_argument('--dry-run', action='store_true',
                        help='Toon wat er zou gebeuren zonder te kopieren')
    parser.add_argument('--limit', type=int,
                        help='Limiteer aantal bestanden per station')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Verbose output')

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Check of archief mount beschikbaar is
    if not ARCHIVE_BASE.exists():
        logger.error(f"Archief mount niet beschikbaar: {ARCHIVE_BASE}")
        sys.exit(1)

    # Maak logs directory
    Path('/home/ronny/emsn2/logs').mkdir(parents=True, exist_ok=True)

    stations = ['zolder', 'berging'] if args.station == 'all' else [args.station]

    total_copied = 0
    total_errors = 0

    for station in stations:
        copied, errors = sync_station(station, args.dry_run, args.limit)
        total_copied += copied
        total_errors += errors

    logger.info(f"Totaal: {total_copied} bestanden gearchiveerd, {total_errors} fouten")

    # Exit code
    sys.exit(0 if total_errors == 0 else 1)


if __name__ == '__main__':
    main()
