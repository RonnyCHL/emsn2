#!/usr/bin/env python3
"""
Nestkast Screenshot Cleanup - EMSN

Ruimt oude lege nestkast screenshots op om schijfruimte te besparen.
Behoudt bezette beelden en twijfelgevallen voor analyse.

Strategie:
- Beelden ouder dan RETENTION_DAYS worden geëvalueerd
- Alleen LEEG beelden met hoge confidence (>90%) worden verwijderd
- Bezette beelden worden ALTIJD bewaard
- Twijfelgevallen (lage confidence) worden bewaard

Draait dagelijks via systemd timer.
Modernized: 2026-01-09 - Type hints toegevoegd
"""

import os
import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

import psycopg2
from psycopg2.extensions import connection as PgConnection

# Voeg project root toe voor imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.config import get_postgres_config

# Configuratie
NAS_BASE = Path("/mnt/nas-birdnet-archive/nestbox")
NESTBOXES = ['voor', 'midden', 'achter']

# Cleanup parameters
RETENTION_DAYS = 180  # 6 maanden
MIN_CONFIDENCE_FOR_DELETE = 0.90  # Alleen verwijderen bij >90% zeker leeg


def get_db_connection() -> PgConnection:
    """Maak database connectie via core.config."""
    return psycopg2.connect(**get_postgres_config())


def get_image_classification(conn: PgConnection, image_path: Path) -> Optional[Dict[str, Any]]:
    """Haal AI classificatie op voor een afbeelding."""
    cur = conn.cursor()
    cur.execute("""
        SELECT is_occupied, confidence, prob_leeg
        FROM nestbox_occupancy
        WHERE image_path = %s
        ORDER BY timestamp DESC
        LIMIT 1
    """, (str(image_path),))
    row = cur.fetchone()
    cur.close()

    if row:
        return {
            'is_occupied': row[0],
            'confidence': row[1],
            'prob_leeg': row[2]
        }
    return None


def get_date_from_path(image_path: Path) -> datetime:
    """Extract datum uit bestandspad of naam."""
    # Probeer uit pad: .../screenshots/2026/01/08/bestand.jpg
    parts = image_path.parts
    try:
        # Zoek jaar/maand/dag in pad
        for i, part in enumerate(parts):
            if part.isdigit() and len(part) == 4 and int(part) > 2020:
                year = int(part)
                month = int(parts[i+1])
                day = int(parts[i+2])
                return datetime(year, month, day)
    except (IndexError, ValueError):
        pass

    # Probeer uit bestandsnaam: midden_20260108_200012.jpg
    try:
        name = image_path.stem
        date_part = name.split('_')[1]
        return datetime.strptime(date_part, '%Y%m%d')
    except (IndexError, ValueError):
        pass

    # Fallback: file modification time
    return datetime.fromtimestamp(image_path.stat().st_mtime)


def should_delete(classification: Optional[Dict[str, Any]], image_date: datetime, cutoff_date: datetime) -> Tuple[bool, str]:
    """Bepaal of een afbeelding verwijderd mag worden."""
    # Alleen beelden ouder dan cutoff
    if image_date >= cutoff_date:
        return False, "te recent"

    # Geen classificatie? Bewaren voor zekerheid
    if classification is None:
        return False, "geen classificatie"

    # Bezet? Altijd bewaren
    if classification['is_occupied']:
        return False, "bezet"

    # Leeg maar lage confidence? Bewaren
    if classification['confidence'] < MIN_CONFIDENCE_FOR_DELETE:
        return False, f"lage confidence ({classification['confidence']:.0%})"

    # Leeg met hoge confidence - mag weg
    return True, f"leeg ({classification['confidence']:.0%})"


def cleanup_nestbox(nestbox_id: str, conn: PgConnection, cutoff_date: datetime,
                    dry_run: bool = False, verbose: bool = False) -> Dict[str, Any]:
    """Cleanup oude screenshots voor één nestkast."""
    screenshot_dir = NAS_BASE / nestbox_id / "screenshots"
    if not screenshot_dir.exists():
        if verbose:
            print(f"[{nestbox_id}] Screenshot directory niet gevonden")
        return {'scanned': 0, 'deleted': 0, 'kept': 0, 'bytes_freed': 0}

    stats = {
        'scanned': 0,
        'deleted': 0,
        'kept': 0,
        'bytes_freed': 0,
        'kept_reasons': {}
    }

    # Scan alle jpg bestanden
    for image_path in screenshot_dir.rglob("*.jpg"):
        stats['scanned'] += 1

        image_date = get_date_from_path(image_path)
        classification = get_image_classification(conn, str(image_path))

        delete, reason = should_delete(classification, image_date, cutoff_date)

        if delete:
            file_size = image_path.stat().st_size
            if not dry_run:
                image_path.unlink()
            stats['deleted'] += 1
            stats['bytes_freed'] += file_size
            if verbose:
                action = "[DRY-RUN] Zou verwijderen" if dry_run else "Verwijderd"
                print(f"  {action}: {image_path.name} - {reason}")
        else:
            stats['kept'] += 1
            stats['kept_reasons'][reason] = stats['kept_reasons'].get(reason, 0) + 1

    return stats


def cleanup_empty_directories(base_path: Path, dry_run: bool = False, verbose: bool = False) -> int:
    """Verwijder lege directories na cleanup."""
    removed = 0
    for dirpath, dirnames, filenames in os.walk(base_path, topdown=False):
        if not dirnames and not filenames:
            if not dry_run:
                os.rmdir(dirpath)
            removed += 1
            if verbose:
                action = "[DRY-RUN] Zou verwijderen" if dry_run else "Verwijderd"
                print(f"  {action} lege map: {dirpath}")
    return removed


def main() -> None:
    """Main entry point voor nestbox cleanup."""
    parser = argparse.ArgumentParser(
        description='Nestkast Screenshot Cleanup',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--nestbox', '-n', choices=NESTBOXES,
                        help='Specifieke nestkast opschonen')
    parser.add_argument('--dry-run', '-d', action='store_true',
                        help='Simuleer cleanup zonder te verwijderen')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Toon details per bestand')
    parser.add_argument('--days', type=int, default=RETENTION_DAYS,
                        help=f'Retentie in dagen (default: {RETENTION_DAYS})')

    args = parser.parse_args()

    retention_days = args.days
    cutoff_date = datetime.now() - timedelta(days=retention_days)

    print("=" * 60)
    print("NESTKAST SCREENSHOT CLEANUP")
    print("=" * 60)
    print(f"Retentie: {retention_days} dagen ({retention_days // 30} maanden)")
    print(f"Min. confidence voor delete: {MIN_CONFIDENCE_FOR_DELETE:.0%}")
    print(f"Cutoff datum: {cutoff_date:%Y-%m-%d}")
    if args.dry_run:
        print("MODE: DRY-RUN (geen wijzigingen)")
    print()

    conn = get_db_connection()

    nestboxes = [args.nestbox] if args.nestbox else NESTBOXES
    total_stats = {
        'scanned': 0,
        'deleted': 0,
        'kept': 0,
        'bytes_freed': 0
    }

    try:
        for nestbox_id in nestboxes:
            print(f"📁 {nestbox_id.upper()}")
            stats = cleanup_nestbox(nestbox_id, conn, cutoff_date,
                                   dry_run=args.dry_run,
                                   verbose=args.verbose)

            print(f"   Gescand: {stats['scanned']}")
            print(f"   Verwijderd: {stats['deleted']}")
            print(f"   Bewaard: {stats['kept']}")
            if stats['bytes_freed'] > 0:
                mb_freed = stats['bytes_freed'] / (1024 * 1024)
                print(f"   Vrijgemaakt: {mb_freed:.1f} MB")

            if args.verbose and stats.get('kept_reasons'):
                print("   Redenen bewaard:")
                for reason, count in sorted(stats['kept_reasons'].items()):
                    print(f"     - {reason}: {count}")
            print()

            # Aggregeer totalen
            for key in total_stats:
                total_stats[key] += stats.get(key, 0)

            # Cleanup lege directories
            cleanup_empty_directories(
                NAS_BASE / nestbox_id / "screenshots",
                dry_run=args.dry_run,
                verbose=args.verbose
            )

    finally:
        conn.close()

    # Totaal overzicht
    print("=" * 60)
    print("TOTAAL")
    print("=" * 60)
    print(f"Gescand: {total_stats['scanned']} beelden")
    print(f"Verwijderd: {total_stats['deleted']} beelden")
    print(f"Bewaard: {total_stats['kept']} beelden")

    if total_stats['bytes_freed'] > 0:
        mb_freed = total_stats['bytes_freed'] / (1024 * 1024)
        gb_freed = total_stats['bytes_freed'] / (1024 * 1024 * 1024)
        if gb_freed >= 1:
            print(f"Vrijgemaakt: {gb_freed:.2f} GB")
        else:
            print(f"Vrijgemaakt: {mb_freed:.1f} MB")

    if args.dry_run:
        print("\n⚠️  DRY-RUN - geen bestanden verwijderd")
        print("Draai zonder --dry-run om daadwerkelijk op te schonen")


if __name__ == '__main__':
    main()
