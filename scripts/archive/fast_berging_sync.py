#!/usr/bin/env python3
"""
Fast Berging Sync - Bulk rsync per directory met parallel processing.
Veel sneller dan file-by-file sync.
"""

import subprocess
import psycopg2
from pathlib import Path
from datetime import datetime
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

# Config
ARCHIVE_BASE = Path("/mnt/nas-birdnet-archive")
BERGING_HOST = "192.168.1.87"
BERGING_USER = "ronny"
BERGING_PATH = "/home/ronny/BirdSongs/Extracted/By_Date"

DB_CONFIG = {
    "host": "192.168.1.25",
    "port": 5433,
    "database": "emsn",
    "user": "postgres",
    "password": "IwnadBon2iN"
}

# Regex voor BirdNET bestandsnamen
FILENAME_PATTERN = re.compile(
    r'^(.+)-(\d+)-(\d{4}-\d{2}-\d{2})-birdnet-(\d{2}:\d{2}:\d{2})\.mp3$'
)

def get_date_dirs():
    """Haal lijst van date directories op van Berging."""
    cmd = f"ssh {BERGING_USER}@{BERGING_HOST} 'ls -1 {BERGING_PATH}'"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error getting directories: {result.stderr}")
        return []

    dates = [d.strip() for d in result.stdout.strip().split('\n') if d.strip() and re.match(r'\d{4}-\d{2}-\d{2}', d.strip())]
    return sorted(dates)

def sync_date_directory(date_str):
    """Sync een hele date directory via rsync."""
    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        year = date_obj.strftime('%Y')
        month = date_obj.strftime('%m')

        # Maak directories
        audio_dir = ARCHIVE_BASE / "audio" / "berging" / year / month
        spec_dir = ARCHIVE_BASE / "spectrograms" / "berging" / year / month
        audio_dir.mkdir(parents=True, exist_ok=True)
        spec_dir.mkdir(parents=True, exist_ok=True)

        remote_path = f"{BERGING_USER}@{BERGING_HOST}:{BERGING_PATH}/{date_str}/"

        # Sync audio files (.mp3) - rsync hele directory in één keer
        audio_cmd = [
            "rsync", "-az", "--include=*/", "--include=*.mp3", "--exclude=*",
            remote_path, str(audio_dir) + "/"
        ]

        # Sync spectrograms (.mp3.png)
        spec_cmd = [
            "rsync", "-az", "--include=*/", "--include=*.mp3.png", "--exclude=*",
            remote_path, str(spec_dir) + "/"
        ]

        # Voer beide rsync parallel uit
        audio_result = subprocess.run(audio_cmd, capture_output=True, text=True, timeout=600)
        spec_result = subprocess.run(spec_cmd, capture_output=True, text=True, timeout=600)

        return date_str, True, ""

    except Exception as e:
        return date_str, False, str(e)

def register_files_in_db():
    """Registreer alle gesynced berging files in database."""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    # Haal al geregistreerde files op
    cur.execute("SELECT archive_audio_path FROM media_archive WHERE station = 'berging'")
    existing = set(row[0] for row in cur.fetchall())

    registered = 0
    audio_base = ARCHIVE_BASE / "audio" / "berging"
    spec_base = ARCHIVE_BASE / "spectrograms" / "berging"

    # Scan alle audio files
    for audio_file in audio_base.rglob("*.mp3"):
        rel_path = str(audio_file.relative_to(ARCHIVE_BASE))

        if rel_path in existing:
            continue

        # Parse bestandsnaam
        match = FILENAME_PATTERN.match(audio_file.name)
        if not match:
            continue

        species = match.group(1).replace('_', ' ')
        confidence = int(match.group(2)) / 100.0
        date_str = match.group(3)

        # Vind spectrogram
        spec_rel = rel_path.replace('/audio/', '/spectrograms/') + '.png'
        spec_file = ARCHIVE_BASE / spec_rel

        # File size
        file_size = audio_file.stat().st_size

        # Insert in database
        cur.execute("""
            INSERT INTO media_archive (
                station, original_audio_filename, original_spectrogram_filename,
                archive_audio_path, archive_spectrogram_path, file_size_bytes,
                detection_date, species, confidence
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
        """, (
            'berging',
            audio_file.name,
            audio_file.name + '.png' if spec_file.exists() else None,
            rel_path,
            spec_rel if spec_file.exists() else None,
            file_size,
            date_str,
            species,
            confidence
        ))

        registered += 1

        if registered % 1000 == 0:
            conn.commit()
            print(f"  Geregistreerd: {registered} files...")

    conn.commit()
    cur.close()
    conn.close()

    return registered

def main():
    print("=" * 60)
    print("FAST BERGING SYNC - Bulk rsync per directory")
    print("=" * 60)

    # Stap 1: Haal alle date directories op
    print("\n[1/3] Ophalen date directories van Berging...")
    dates = get_date_dirs()
    print(f"  Gevonden: {len(dates)} date directories")

    if not dates:
        print("Geen directories gevonden!")
        return

    # Stap 2: Sync directories parallel (4 tegelijk)
    print(f"\n[2/3] Syncing directories (parallel)...")
    completed = 0
    failed = 0

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(sync_date_directory, d): d for d in dates}

        for future in as_completed(futures):
            date_str, success, error = future.result()
            completed += 1

            if success:
                print(f"  [{completed}/{len(dates)}] {date_str} OK")
            else:
                failed += 1
                print(f"  [{completed}/{len(dates)}] {date_str} FAILED: {error}")

    print(f"\n  Sync complete: {completed - failed} OK, {failed} failed")

    # Stap 3: Registreer in database
    print(f"\n[3/3] Registreren files in database...")
    new_files = register_files_in_db()
    print(f"  Nieuw geregistreerd: {new_files} files")

    print("\n" + "=" * 60)
    print("DONE!")
    print("=" * 60)

if __name__ == "__main__":
    main()
