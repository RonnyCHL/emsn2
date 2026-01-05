#!/usr/bin/env python3
"""
Nestkast Timelapse Generator - EMSN

Maakt timelapse video's van nestkast screenshots.

INTERACTIEF (zonder argumenten):
    ./nestbox_timelapse.py

COMMAND LINE:
    # Laatste 7 dagen van midden nestkast
    ./nestbox_timelapse.py -n midden -d 7

    # Specifieke periode met gewenste video duur (30 sec)
    ./nestbox_timelapse.py -n midden --start 2025-12-23 --end 2026-01-05 --duration 30

    # Alleen nacht (22:00-06:00) - slapende vogel
    ./nestbox_timelapse.py -n midden -d 14 --night-only

    # Handmatige fps instelling
    ./nestbox_timelapse.py -n midden -d 7 --fps 15
"""

import argparse
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Configuratie
SCREENSHOTS_BASE = Path("/mnt/nas-birdnet-archive/nestbox")
OUTPUT_BASE = Path("/mnt/nas-birdnet-archive/gegenereerde_beelden/nestkasten")
NESTBOXES = ['voor', 'midden', 'achter']


def get_output_dir(nestbox_id: str) -> Path:
    """Geeft output directory voor een specifieke nestkast."""
    return OUTPUT_BASE / nestbox_id


def get_screenshots(nestbox_id: str, start_date: datetime, end_date: datetime,
                    night_only: bool = False, day_only: bool = False) -> list:
    """Verzamel screenshots binnen de opgegeven periode."""
    screenshots = []
    base_path = SCREENSHOTS_BASE / nestbox_id / "screenshots"

    if not base_path.exists():
        print(f"Error: Screenshots map niet gevonden: {base_path}")
        return []

    # Loop door alle jpg bestanden
    for jpg_file in sorted(base_path.rglob("*.jpg")):
        # Parse timestamp uit bestandsnaam: midden_20251223_211216.jpg
        try:
            name = jpg_file.stem
            parts = name.split('_')
            if len(parts) >= 3:
                date_str = parts[1]  # 20251223
                time_str = parts[2]  # 211216
                timestamp = datetime.strptime(f"{date_str}_{time_str}", "%Y%m%d_%H%M%S")

                # Check datum range
                if start_date <= timestamp <= end_date:
                    hour = timestamp.hour

                    # Filter op dag/nacht indien gewenst
                    if night_only and not (hour >= 22 or hour < 6):
                        continue
                    if day_only and (hour >= 22 or hour < 6):
                        continue

                    screenshots.append((timestamp, jpg_file))
        except (ValueError, IndexError):
            continue

    # Sorteer op timestamp
    screenshots.sort(key=lambda x: x[0])
    return screenshots


def get_available_date_range(nestbox_id: str) -> tuple:
    """Bepaal beschikbare datum range voor een nestkast."""
    base_path = SCREENSHOTS_BASE / nestbox_id / "screenshots"
    if not base_path.exists():
        return None, None

    dates = []
    for jpg_file in base_path.rglob("*.jpg"):
        try:
            parts = jpg_file.stem.split('_')
            if len(parts) >= 2:
                date_str = parts[1]
                dates.append(datetime.strptime(date_str, "%Y%m%d"))
        except (ValueError, IndexError):
            continue

    if dates:
        return min(dates), max(dates)
    return None, None


def create_timelapse(screenshots: list, output_path: Path, fps: int = 10,
                     resolution: str = "1280x720", show_timestamp: bool = True) -> bool:
    """Maak timelapse video met ffmpeg."""
    if not screenshots:
        print("Error: Geen screenshots om te verwerken")
        return False

    # Maak tijdelijke map voor genummerde symlinks
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        print(f"Voorbereiden van {len(screenshots)} frames...")

        # Maak genummerde symlinks voor ffmpeg
        for i, (timestamp, filepath) in enumerate(screenshots):
            link_name = tmppath / f"frame_{i:06d}.jpg"
            link_name.symlink_to(filepath)

        # FFmpeg commando
        input_pattern = str(tmppath / "frame_%06d.jpg")

        # Parse resolution
        width, height = resolution.split('x')

        # Bouw filter voor timestamp overlay
        if show_timestamp:
            filter_complex = (
                f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,"
                f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:"
                f"fontsize=24:fontcolor=white:x=10:y=h-40:"
                f"text='%{{frame_num}}/{len(screenshots)}':start_number=1"
            )
        else:
            filter_complex = (
                f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black"
            )

        cmd = [
            'ffmpeg', '-y',
            '-framerate', str(fps),
            '-i', input_pattern,
            '-vf', filter_complex,
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '23',
            '-pix_fmt', 'yuv420p',
            str(output_path)
        ]

        print(f"Genereren timelapse ({fps} fps)...")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"FFmpeg error: {result.stderr}")
            return False

    return True


def input_date(prompt: str, default: datetime = None) -> datetime:
    """Vraag een datum aan de gebruiker."""
    default_str = default.strftime('%Y-%m-%d') if default else ""
    while True:
        hint = f" [{default_str}]" if default_str else ""
        user_input = input(f"{prompt}{hint}: ").strip()

        if not user_input and default:
            return default

        try:
            return datetime.strptime(user_input, "%Y-%m-%d")
        except ValueError:
            print("  Ongeldige datum. Gebruik formaat: YYYY-MM-DD (bijv. 2025-12-25)")


def input_choice(prompt: str, choices: list, default: int = 0) -> str:
    """Toon een keuzemenu."""
    print(f"\n{prompt}")
    for i, choice in enumerate(choices):
        marker = " [standaard]" if i == default else ""
        print(f"  {i + 1}. {choice}{marker}")

    while True:
        user_input = input(f"Keuze (1-{len(choices)}): ").strip()
        if not user_input:
            return choices[default]
        try:
            idx = int(user_input) - 1
            if 0 <= idx < len(choices):
                return choices[idx]
        except ValueError:
            pass
        print(f"  Kies een nummer tussen 1 en {len(choices)}")


def input_number(prompt: str, default: int, min_val: int = 1, max_val: int = 300) -> int:
    """Vraag een getal aan de gebruiker."""
    while True:
        user_input = input(f"{prompt} [{default}]: ").strip()
        if not user_input:
            return default
        try:
            val = int(user_input)
            if min_val <= val <= max_val:
                return val
            print(f"  Kies een getal tussen {min_val} en {max_val}")
        except ValueError:
            print("  Voer een geldig getal in")


def interactive_mode():
    """Interactieve modus voor timelapse generatie."""
    print("=" * 50)
    print("   NESTKAST TIMELAPSE GENERATOR")
    print("=" * 50)

    # 1. Kies nestkast
    nestbox = input_choice("Welke nestkast?", NESTBOXES, default=1)

    # Toon beschikbare data
    min_date, max_date = get_available_date_range(nestbox)
    if min_date and max_date:
        print(f"\n  Beschikbare data: {min_date.strftime('%Y-%m-%d')} t/m {max_date.strftime('%Y-%m-%d')}")

        # Tel screenshots
        total = len(list((SCREENSHOTS_BASE / nestbox / "screenshots").rglob("*.jpg")))
        print(f"  Totaal: {total} screenshots")

    # 2. Kies periode methode
    period_method = input_choice(
        "Hoe wil je de periode kiezen?",
        ["Laatste X dagen", "Specifieke datums"],
        default=0
    )

    if period_method == "Laatste X dagen":
        days = input_number("Aantal dagen terug", default=7, min_val=1, max_val=365)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
    else:
        default_start = max_date - timedelta(days=7) if max_date else datetime.now() - timedelta(days=7)
        default_end = max_date if max_date else datetime.now()

        print("\n  Voer datums in (formaat: YYYY-MM-DD)")
        start_date = input_date("Start datum", default=default_start)
        end_date = input_date("Eind datum", default=default_end)
        end_date = end_date.replace(hour=23, minute=59, second=59)

    # 3. Dag/nacht filter
    time_filter = input_choice(
        "Welke screenshots gebruiken?",
        ["Alle (dag + nacht)", "Alleen overdag (06:00-22:00)", "Alleen 's nachts (22:00-06:00)"],
        default=0
    )

    night_only = (time_filter == "Alleen 's nachts (22:00-06:00)")
    day_only = (time_filter == "Alleen overdag (06:00-22:00)")

    # Verzamel screenshots om aantal te tonen
    screenshots = get_screenshots(nestbox, start_date, end_date, night_only=night_only, day_only=day_only)

    if not screenshots:
        print("\n❌ Geen screenshots gevonden voor de gekozen periode.")
        return 1

    print(f"\n  Gevonden: {len(screenshots)} screenshots")
    print(f"  Periode: {screenshots[0][0].strftime('%Y-%m-%d %H:%M')} - {screenshots[-1][0].strftime('%Y-%m-%d %H:%M')}")

    # 4. Video duur
    duration_method = input_choice(
        "Hoe wil je de video snelheid bepalen?",
        ["Kies video duur (seconden)", "Kies framerate (fps)"],
        default=0
    )

    if duration_method == "Kies video duur (seconden)":
        # Bereken redelijke default
        default_duration = min(30, max(10, len(screenshots) // 10))
        duration = input_number("Gewenste video duur in seconden", default=default_duration, min_val=5, max_val=300)
        fps = max(1, len(screenshots) // duration)
        print(f"  → Berekende framerate: {fps} fps")
    else:
        fps = input_number("Framerate (frames per seconde)", default=10, min_val=1, max_val=60)
        duration = len(screenshots) / fps

    # Bereken en toon video info
    actual_duration = len(screenshots) / fps
    print(f"\n  Video duur: {actual_duration:.1f} seconden")

    # 5. Bevestiging
    print("\n" + "=" * 50)
    print("SAMENVATTING")
    print("=" * 50)
    print(f"  Nestkast:    {nestbox}")
    print(f"  Periode:     {start_date.strftime('%Y-%m-%d')} t/m {end_date.strftime('%Y-%m-%d')}")
    print(f"  Filter:      {time_filter}")
    print(f"  Screenshots: {len(screenshots)}")
    print(f"  Framerate:   {fps} fps")
    print(f"  Video duur:  {actual_duration:.1f} seconden")

    # Output bestandsnaam
    output_dir = get_output_dir(nestbox)
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = ""
    if night_only:
        suffix = "_night"
    elif day_only:
        suffix = "_day"
    filename = f"{nestbox}_{start_date.strftime('%Y%m%d')}-{end_date.strftime('%Y%m%d')}{suffix}.mp4"
    output_path = output_dir / filename
    print(f"  Output:      {output_path}")

    confirm = input("\nDoorgaan? [J/n]: ").strip().lower()
    if confirm and confirm not in ['j', 'y', 'ja', 'yes']:
        print("Geannuleerd.")
        return 0

    # Maak timelapse
    print()
    success = create_timelapse(
        screenshots, output_path,
        fps=fps,
        resolution="1280x720",
        show_timestamp=True
    )

    if success:
        size_mb = output_path.stat().st_size / 1024 / 1024
        print(f"\n" + "=" * 50)
        print("✅ KLAAR!")
        print("=" * 50)
        print(f"  Video:    {output_path}")
        print(f"  Grootte:  {size_mb:.1f} MB")
        print(f"  Duur:     {actual_duration:.1f} seconden")
        return 0
    else:
        print("\n❌ Error: Timelapse genereren mislukt")
        return 1


def main():
    parser = argparse.ArgumentParser(
        description='Nestkast Timelapse Generator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument('-n', '--nestbox', choices=NESTBOXES,
                        help='Nestkast ID (voor, midden, achter)')
    parser.add_argument('-d', '--days', type=int, default=None,
                        help='Aantal dagen terug')
    parser.add_argument('--start', type=str, default=None,
                        help='Start datum (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, default=None,
                        help='Eind datum (YYYY-MM-DD)')
    parser.add_argument('--duration', type=int, default=None,
                        help='Gewenste video duur in seconden (fps wordt berekend)')
    parser.add_argument('--fps', type=int, default=None,
                        help='Frames per seconde (standaard: 10, of berekend uit --duration)')
    parser.add_argument('--resolution', type=str, default='1280x720',
                        help='Video resolutie (standaard: 1280x720)')
    parser.add_argument('--night-only', action='store_true',
                        help='Alleen nacht screenshots (22:00-06:00)')
    parser.add_argument('--day-only', action='store_true',
                        help='Alleen dag screenshots (06:00-22:00)')
    parser.add_argument('--no-timestamp', action='store_true',
                        help='Geen frame teller overlay')
    parser.add_argument('-o', '--output', type=str, default=None,
                        help='Output bestandsnaam (optioneel)')
    parser.add_argument('--list', action='store_true',
                        help='Toon alleen beschikbare screenshots, maak geen video')

    args = parser.parse_args()

    # Als geen nestkast opgegeven, start interactieve modus
    if not args.nestbox:
        return interactive_mode()

    # Command-line modus
    # Bepaal datum range
    if args.start and args.end:
        start_date = datetime.strptime(args.start, "%Y-%m-%d")
        end_date = datetime.strptime(args.end, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
    elif args.days:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=args.days)
    else:
        # Default: laatste 7 dagen
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)

    print(f"=== Nestkast Timelapse Generator ===")
    print(f"Nestkast: {args.nestbox}")
    print(f"Periode: {start_date.strftime('%Y-%m-%d %H:%M')} - {end_date.strftime('%Y-%m-%d %H:%M')}")

    if args.night_only:
        print("Filter: Alleen nacht (22:00-06:00)")
    elif args.day_only:
        print("Filter: Alleen dag (06:00-22:00)")

    # Verzamel screenshots
    screenshots = get_screenshots(
        args.nestbox, start_date, end_date,
        night_only=args.night_only, day_only=args.day_only
    )

    print(f"Gevonden: {len(screenshots)} screenshots")

    if not screenshots:
        print("Geen screenshots gevonden voor de opgegeven periode.")
        return 1

    # Toon eerste en laatste
    print(f"Eerste: {screenshots[0][0].strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Laatste: {screenshots[-1][0].strftime('%Y-%m-%d %H:%M:%S')}")

    if args.list:
        print("\n=== Screenshots ===")
        for ts, path in screenshots:
            print(f"  {ts.strftime('%Y-%m-%d %H:%M:%S')} - {path.name}")
        return 0

    # Bepaal fps
    if args.duration:
        fps = max(1, len(screenshots) // args.duration)
        print(f"Gewenste duur: {args.duration}s → berekende fps: {fps}")
    elif args.fps:
        fps = args.fps
    else:
        fps = 10

    # Bepaal output bestandsnaam
    if args.output:
        output_path = Path(args.output)
    else:
        output_dir = get_output_dir(args.nestbox)
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = ""
        if args.night_only:
            suffix = "_night"
        elif args.day_only:
            suffix = "_day"

        filename = f"{args.nestbox}_{start_date.strftime('%Y%m%d')}-{end_date.strftime('%Y%m%d')}{suffix}.mp4"
        output_path = output_dir / filename

    # Bereken video duur
    duration_sec = len(screenshots) / fps
    print(f"\nVideo duur: {duration_sec:.1f} seconden ({len(screenshots)} frames @ {fps} fps)")
    print(f"Output: {output_path}")
    print()

    # Maak timelapse
    success = create_timelapse(
        screenshots, output_path,
        fps=fps,
        resolution=args.resolution,
        show_timestamp=not args.no_timestamp
    )

    if success:
        size_mb = output_path.stat().st_size / 1024 / 1024
        print(f"\n=== Klaar! ===")
        print(f"Video: {output_path}")
        print(f"Grootte: {size_mb:.1f} MB")
        print(f"Duur: {duration_sec:.1f} seconden")
        return 0
    else:
        print("\nError: Timelapse genereren mislukt")
        return 1


if __name__ == '__main__':
    sys.exit(main())
