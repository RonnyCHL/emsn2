#!/usr/bin/env python3
"""
AtmosBird Timelapse Generator (Interactief) - EMSN

Maakt timelapse video's van AtmosBird hemel screenshots.
Dit script is voor handmatige/interactieve timelapse generatie.
Voor automatische dagelijkse timelapses: zie atmosbird_timelapse.py

INTERACTIEF (zonder argumenten):
    ./atmosbird_timelapse_generator.py

COMMAND LINE:
    # Laatste 7 dagen
    ./atmosbird_timelapse_generator.py -d 7

    # Specifieke periode met gewenste video duur (30 sec)
    ./atmosbird_timelapse_generator.py --start 2025-12-23 --end 2026-01-05 --duration 30

    # Alleen nacht (22:00-06:00) - sterrenhemel
    ./atmosbird_timelapse_generator.py -d 14 --night-only

    # Alleen dag
    ./atmosbird_timelapse_generator.py -d 7 --day-only

    # Handmatige fps instelling
    ./atmosbird_timelapse_generator.py -d 7 --fps 15
"""

import argparse
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Configuratie
SCREENSHOTS_BASE = Path("/mnt/nas-birdnet-archive/atmosbird/ruwe_foto")
OUTPUT_DIR = Path("/mnt/nas-birdnet-archive/gegenereerde_beelden/atmosbird")


def get_screenshots(start_date: datetime, end_date: datetime,
                    night_only: bool = False, day_only: bool = False) -> list:
    """Verzamel screenshots binnen de opgegeven periode."""
    screenshots = []

    if not SCREENSHOTS_BASE.exists():
        print(f"Error: Screenshots map niet gevonden: {SCREENSHOTS_BASE}")
        return []

    # Loop door alle jpg bestanden
    for jpg_file in sorted(SCREENSHOTS_BASE.rglob("*.jpg")):
        # Parse timestamp uit bestandsnaam: sky_20260105_192858.jpg
        try:
            name = jpg_file.stem
            parts = name.split('_')
            if len(parts) >= 3 and parts[0] == 'sky':
                date_str = parts[1]  # 20260105
                time_str = parts[2]  # 192858
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


def get_available_date_range() -> tuple:
    """Bepaal beschikbare datum range."""
    if not SCREENSHOTS_BASE.exists():
        return None, None

    all_files = list(SCREENSHOTS_BASE.rglob("*.jpg"))
    if not all_files:
        return None, None

    dates = []
    for jpg_file in all_files:
        try:
            name = jpg_file.stem
            parts = name.split('_')
            if len(parts) >= 2 and parts[0] == 'sky':
                date_str = parts[1]
                dates.append(datetime.strptime(date_str, "%Y%m%d"))
        except (ValueError, IndexError):
            continue

    if dates:
        return min(dates), max(dates)
    return None, None


def create_timelapse(screenshots: list, output_path: Path, fps: int = 10,
                     resolution: str = "1920x1080", show_timestamp: bool = True) -> bool:
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
                f"fontsize=28:fontcolor=white:x=10:y=h-50:"
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

        print(f"  Ongeldige keuze. Kies 1-{len(choices)}")


def input_number(prompt: str, default: int, min_val: int = 1, max_val: int = 999) -> int:
    """Vraag een nummer aan de gebruiker."""
    while True:
        user_input = input(f"{prompt} [{default}]: ").strip()

        if not user_input:
            return default

        try:
            val = int(user_input)
            if min_val <= val <= max_val:
                return val
            print(f"  Waarde moet tussen {min_val} en {max_val} liggen")
        except ValueError:
            print("  Ongeldige invoer. Voer een nummer in.")


def interactive_mode() -> int:
    """Interactieve wizard voor timelapse generatie."""
    print("=" * 50)
    print("ATMOSBIRD TIMELAPSE GENERATOR")
    print("=" * 50)

    # Bepaal beschikbare periode
    min_date, max_date = get_available_date_range()
    if not min_date:
        print("\nError: Geen screenshots gevonden!")
        return 1

    print(f"\nBeschikbare periode: {min_date.strftime('%Y-%m-%d')} tot {max_date.strftime('%Y-%m-%d')}")

    # Kies periode type
    period_choice = input_choice(
        "Welke periode wil je gebruiken?",
        ["Laatste X dagen", "Specifieke datums"],
        default=0
    )

    if period_choice == "Laatste X dagen":
        days = input_number("Aantal dagen terug", default=7, min_val=1, max_val=365)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
    else:
        start_date = input_date("Startdatum (YYYY-MM-DD)", default=min_date)
        end_date = input_date("Einddatum (YYYY-MM-DD)", default=max_date)
        # Zet end_date naar einde van de dag
        end_date = end_date.replace(hour=23, minute=59, second=59)

    # Dag/nacht filter
    time_filter = input_choice(
        "Welke screenshots wil je gebruiken?",
        ["Alle screenshots", "Alleen overdag (06:00-22:00)", "Alleen 's nachts (22:00-06:00)"],
        default=0
    )

    night_only = time_filter == "Alleen 's nachts (22:00-06:00)"
    day_only = time_filter == "Alleen overdag (06:00-22:00)"

    # Zoek screenshots
    print(f"\nScreenshots zoeken...")
    screenshots = get_screenshots(start_date, end_date, night_only, day_only)

    if not screenshots:
        print("Geen screenshots gevonden voor deze periode/filter!")
        return 1

    print(f"  Gevonden: {len(screenshots)} screenshots")

    # Video duur bepalen
    duration_choice = input_choice(
        "Hoe wil je de video snelheid bepalen?",
        ["Gewenste video duur opgeven (aanbevolen)", "Handmatig fps instellen"],
        default=0
    )

    if duration_choice == "Gewenste video duur opgeven (aanbevolen)":
        target_duration = input_number("Gewenste video duur in seconden", default=30, min_val=5, max_val=300)
        fps = max(1, len(screenshots) // target_duration)
        actual_duration = len(screenshots) / fps
        print(f"  Berekende framerate: {fps} fps (video wordt {actual_duration:.1f} seconden)")
    else:
        fps = input_number("Framerate (fps)", default=10, min_val=1, max_val=60)
        actual_duration = len(screenshots) / fps
        print(f"  Video duur wordt: {actual_duration:.1f} seconden")

    # Samenvatting
    print("\n" + "=" * 50)
    print("SAMENVATTING")
    print("=" * 50)
    print(f"  Periode:     {start_date.strftime('%Y-%m-%d')} t/m {end_date.strftime('%Y-%m-%d')}")
    print(f"  Filter:      {time_filter}")
    print(f"  Screenshots: {len(screenshots)}")
    print(f"  Framerate:   {fps} fps")
    print(f"  Video duur:  {actual_duration:.1f} seconden")

    # Output bestandsnaam
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = ""
    if night_only:
        suffix = "_night"
    elif day_only:
        suffix = "_day"
    filename = f"atmosbird_{start_date.strftime('%Y%m%d')}-{end_date.strftime('%Y%m%d')}{suffix}.mp4"
    output_path = OUTPUT_DIR / filename
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
        resolution="1920x1080",
        show_timestamp=True
    )

    if success:
        size_mb = output_path.stat().st_size / 1024 / 1024
        print(f"\n" + "=" * 50)
        print("KLAAR!")
        print("=" * 50)
        print(f"  Video:    {output_path}")
        print(f"  Grootte:  {size_mb:.1f} MB")
        print(f"  Duur:     {actual_duration:.1f} seconden")
        return 0
    else:
        print("\nError: Timelapse genereren mislukt")
        return 1


def main():
    parser = argparse.ArgumentParser(
        description='AtmosBird Timelapse Generator (Interactief)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Voorbeelden:
  %(prog)s                           # Interactieve modus
  %(prog)s -d 7                      # Laatste 7 dagen
  %(prog)s -d 7 --duration 30        # Laatste 7 dagen, 30 sec video
  %(prog)s --start 2025-12-01 --end 2025-12-31 --night-only
  %(prog)s -d 14 --fps 15            # Handmatige fps
  %(prog)s --list                    # Toon beschikbare data
        """
    )

    parser.add_argument('-d', '--days', type=int, help='Aantal dagen terug vanaf nu')
    parser.add_argument('--start', type=str, help='Startdatum (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, help='Einddatum (YYYY-MM-DD)')
    parser.add_argument('--duration', type=int, help='Gewenste video duur in seconden')
    parser.add_argument('--fps', type=int, help='Framerate (frames per seconde)')
    parser.add_argument('--night-only', action='store_true', help='Alleen nacht screenshots (22:00-06:00)')
    parser.add_argument('--day-only', action='store_true', help='Alleen dag screenshots (06:00-22:00)')
    parser.add_argument('--resolution', type=str, default='1920x1080', help='Video resolutie (default: 1920x1080)')
    parser.add_argument('--no-timestamp', action='store_true', help='Geen timestamp overlay')
    parser.add_argument('-o', '--output', type=str, help='Output bestandspad')
    parser.add_argument('--list', action='store_true', help='Toon beschikbare data en stop')

    args = parser.parse_args()

    # Als geen argumenten, start interactieve modus
    if len(sys.argv) == 1:
        return interactive_mode()

    # List mode
    if args.list:
        min_date, max_date = get_available_date_range()
        if min_date:
            print(f"Beschikbare periode: {min_date.strftime('%Y-%m-%d')} tot {max_date.strftime('%Y-%m-%d')}")

            # Tel screenshots
            if args.days:
                end_date = datetime.now()
                start_date = end_date - timedelta(days=args.days)
            elif args.start:
                start_date = datetime.strptime(args.start, "%Y-%m-%d")
                end_date = datetime.strptime(args.end, "%Y-%m-%d") if args.end else datetime.now()
                end_date = end_date.replace(hour=23, minute=59, second=59)
            else:
                start_date = min_date
                end_date = max_date

            screenshots = get_screenshots(start_date, end_date, args.night_only, args.day_only)
            print(f"{len(screenshots)} screenshots gevonden voor {start_date.strftime('%Y-%m-%d')} - {end_date.strftime('%Y-%m-%d')}")
        else:
            print("Geen screenshots gevonden")
        return 0

    # Command line mode
    if args.days:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=args.days)
    elif args.start:
        start_date = datetime.strptime(args.start, "%Y-%m-%d")
        end_date = datetime.strptime(args.end, "%Y-%m-%d") if args.end else datetime.now()
        end_date = end_date.replace(hour=23, minute=59, second=59)
    else:
        print("Error: Geef --days of --start/--end op")
        return 1

    print(f"Periode: {start_date.strftime('%Y-%m-%d')} tot {end_date.strftime('%Y-%m-%d')}")

    # Verzamel screenshots
    screenshots = get_screenshots(start_date, end_date, args.night_only, args.day_only)

    if not screenshots:
        print("Geen screenshots gevonden!")
        return 1

    print(f"Gevonden: {len(screenshots)} screenshots")

    # Bepaal fps
    if args.duration:
        fps = max(1, len(screenshots) // args.duration)
        print(f"Gewenste duur: {args.duration}s -> berekende fps: {fps}")
    elif args.fps:
        fps = args.fps
    else:
        fps = 10

    # Bepaal output bestandsnaam
    if args.output:
        output_path = Path(args.output)
    else:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        suffix = ""
        if args.night_only:
            suffix = "_night"
        elif args.day_only:
            suffix = "_day"

        filename = f"atmosbird_{start_date.strftime('%Y%m%d')}-{end_date.strftime('%Y%m%d')}{suffix}.mp4"
        output_path = OUTPUT_DIR / filename

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
        print(f"\nTimelapse opgeslagen: {output_path}")
        return 0
    else:
        print("\nError: Timelapse genereren mislukt")
        return 1


if __name__ == '__main__':
    sys.exit(main())
