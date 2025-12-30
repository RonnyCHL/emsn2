#!/usr/bin/env python3
"""
AtmosBird Timelapse Generator
Maak timelapses van hemel captures voor een willekeurige periode.

Gebruik:
    python3 create_timelapse.py --dagen 7          # Laatste week
    python3 create_timelapse.py --dagen 30         # Laatste maand
    python3 create_timelapse.py --van 2025-12-01 --tot 2025-12-31  # December
    python3 create_timelapse.py --dagen 7 --fps 60 # Snellere video
    python3 create_timelapse.py --dagen 7 --alleen-nacht  # Alleen nachtopnames
    python3 create_timelapse.py --dagen 7 --alleen-dag    # Alleen dagopnames
"""

import argparse
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
import sys
import os

# Configuratie
ARCHIEF_DIR = Path("/mnt/nas-birdnet-archive/atmosbird/ruwe_foto")
OUTPUT_DIR = Path("/mnt/nas-birdnet-archive/atmosbird/timelapse/custom")
TEMP_DIR = Path("/tmp/timelapse_frames")

# Standaard video instellingen
DEFAULT_FPS = 30
DEFAULT_CODEC = "libx264"
DEFAULT_QUALITY = "23"  # CRF waarde (lager = betere kwaliteit, 18-28 is normaal)


def log(message):
    """Print bericht met timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")


def verzamel_fotos(start_datum, eind_datum, alleen_dag=False, alleen_nacht=False):
    """Verzamel alle foto's binnen de opgegeven periode"""
    fotos = []

    log(f"Zoeken naar foto's van {start_datum.strftime('%d-%m-%Y')} tot {eind_datum.strftime('%d-%m-%Y')}...")

    # Loop door alle dagen in de periode
    huidige_dag = start_datum
    while huidige_dag <= eind_datum:
        dag_dir = ARCHIEF_DIR / huidige_dag.strftime("%Y/%m/%d")

        if dag_dir.exists():
            # Zoek alle jpg bestanden in deze dag
            dag_fotos = sorted(dag_dir.glob("*.jpg"))

            for foto in dag_fotos:
                # Haal tijd uit bestandsnaam (sky_YYYYMMDD_HHMMSS.jpg)
                try:
                    naam = foto.stem  # sky_20251230_143000
                    tijd_str = naam.split("_")[2]  # 143000
                    uur = int(tijd_str[:2])

                    # Filter op dag/nacht indien gewenst
                    is_dag = 7 <= uur <= 20  # 07:00 - 20:59 = dag

                    if alleen_dag and not is_dag:
                        continue
                    if alleen_nacht and is_dag:
                        continue

                    fotos.append(foto)
                except (IndexError, ValueError):
                    # Bestandsnaam niet in verwacht formaat, neem gewoon mee
                    fotos.append(foto)

        huidige_dag += timedelta(days=1)

    log(f"Gevonden: {len(fotos)} foto's")
    return sorted(fotos)


def maak_timelapse(fotos, output_path, fps=DEFAULT_FPS, resolutie=None):
    """Maak timelapse video van de foto's"""

    if len(fotos) == 0:
        log("Geen foto's gevonden voor de opgegeven periode!")
        return False

    # Maak temp directory voor symlinks (ffmpeg werkt beter met sequentiële nummering)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    # Verwijder oude temp bestanden
    for f in TEMP_DIR.glob("*.jpg"):
        f.unlink()

    log(f"Voorbereiden van {len(fotos)} frames...")

    # Maak symlinks met sequentiële nummering
    for i, foto in enumerate(fotos):
        link_path = TEMP_DIR / f"frame_{i:06d}.jpg"
        if link_path.exists():
            link_path.unlink()
        link_path.symlink_to(foto)

    # Bereken video duur
    duur_seconden = len(fotos) / fps
    minuten = int(duur_seconden // 60)
    seconden = int(duur_seconden % 60)

    log(f"Genereren timelapse: {len(fotos)} frames @ {fps} fps = {minuten}m {seconden}s")

    # FFmpeg commando
    cmd = [
        "ffmpeg",
        "-y",  # Overschrijf output
        "-framerate", str(fps),
        "-i", str(TEMP_DIR / "frame_%06d.jpg"),
        "-c:v", DEFAULT_CODEC,
        "-crf", DEFAULT_QUALITY,
        "-pix_fmt", "yuv420p",  # Compatibiliteit
        "-movflags", "+faststart",  # Web streaming
    ]

    # Optionele resolutie aanpassing
    if resolutie:
        cmd.extend(["-vf", f"scale={resolutie}"])

    cmd.append(str(output_path))

    log("FFmpeg wordt uitgevoerd...")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600  # 10 minuten timeout
        )

        if result.returncode != 0:
            log(f"FFmpeg error: {result.stderr}")
            return False

        # Controleer output
        if output_path.exists():
            grootte_mb = output_path.stat().st_size / (1024 * 1024)
            log(f"Timelapse gemaakt: {output_path}")
            log(f"Bestandsgrootte: {grootte_mb:.1f} MB")
            return True
        else:
            log("Output bestand niet aangemaakt!")
            return False

    except subprocess.TimeoutExpired:
        log("FFmpeg timeout - video te lang?")
        return False
    except Exception as e:
        log(f"Fout bij maken timelapse: {e}")
        return False
    finally:
        # Cleanup temp bestanden
        for f in TEMP_DIR.glob("*.jpg"):
            f.unlink()


def main():
    parser = argparse.ArgumentParser(
        description="Maak een timelapse van AtmosBird hemel captures",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Voorbeelden:
  %(prog)s --dagen 7                    Laatste week
  %(prog)s --dagen 30                   Laatste maand
  %(prog)s --van 2025-12-01 --tot 2025-12-31   Specifieke periode
  %(prog)s --dagen 7 --fps 60           Snellere video (60 fps)
  %(prog)s --dagen 7 --alleen-nacht     Alleen nachtopnames
  %(prog)s --dagen 14 --resolutie 1280:720    Lagere resolutie
        """
    )

    # Periode opties
    periode = parser.add_argument_group("Periode")
    periode.add_argument("--dagen", type=int, help="Aantal dagen terug vanaf nu")
    periode.add_argument("--van", type=str, help="Start datum (YYYY-MM-DD)")
    periode.add_argument("--tot", type=str, help="Eind datum (YYYY-MM-DD)")

    # Filter opties
    filters = parser.add_argument_group("Filters")
    filters.add_argument("--alleen-dag", action="store_true", help="Alleen dagopnames (07:00-21:00)")
    filters.add_argument("--alleen-nacht", action="store_true", help="Alleen nachtopnames (21:00-07:00)")

    # Video opties
    video = parser.add_argument_group("Video instellingen")
    video.add_argument("--fps", type=int, default=DEFAULT_FPS, help=f"Frames per seconde (standaard: {DEFAULT_FPS})")
    video.add_argument("--resolutie", type=str, help="Output resolutie (bijv. 1920:1080 of 1280:720)")
    video.add_argument("--output", type=str, help="Output bestandspad (optioneel)")

    args = parser.parse_args()

    # Bepaal periode
    if args.dagen:
        eind_datum = datetime.now()
        start_datum = eind_datum - timedelta(days=args.dagen)
    elif args.van and args.tot:
        start_datum = datetime.strptime(args.van, "%Y-%m-%d")
        eind_datum = datetime.strptime(args.tot, "%Y-%m-%d")
    else:
        parser.print_help()
        print("\nFout: Geef --dagen OF --van en --tot op!")
        sys.exit(1)

    # Check conflicterende filters
    if args.alleen_dag and args.alleen_nacht:
        print("Fout: Kies --alleen-dag OF --alleen-nacht, niet beide!")
        sys.exit(1)

    # Verzamel foto's
    fotos = verzamel_fotos(
        start_datum,
        eind_datum,
        alleen_dag=args.alleen_dag,
        alleen_nacht=args.alleen_nacht
    )

    if len(fotos) == 0:
        log("Geen foto's gevonden! Controleer de periode en het archief pad.")
        sys.exit(1)

    # Bepaal output bestandsnaam
    if args.output:
        output_path = Path(args.output)
    else:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        # Genereer bestandsnaam
        periode_str = f"{start_datum.strftime('%Y%m%d')}-{eind_datum.strftime('%Y%m%d')}"

        if args.alleen_dag:
            type_str = "_dag"
        elif args.alleen_nacht:
            type_str = "_nacht"
        else:
            type_str = ""

        output_path = OUTPUT_DIR / f"timelapse_{periode_str}{type_str}.mp4"

    # Maak timelapse
    log("=" * 50)
    log("AtmosBird Timelapse Generator")
    log("=" * 50)
    log(f"Periode: {start_datum.strftime('%d-%m-%Y')} tot {eind_datum.strftime('%d-%m-%Y')}")
    log(f"Aantal dagen: {(eind_datum - start_datum).days + 1}")
    log(f"FPS: {args.fps}")
    if args.alleen_dag:
        log("Filter: Alleen dag (07:00-21:00)")
    elif args.alleen_nacht:
        log("Filter: Alleen nacht (21:00-07:00)")
    log("=" * 50)

    success = maak_timelapse(
        fotos,
        output_path,
        fps=args.fps,
        resolutie=args.resolutie
    )

    if success:
        log("=" * 50)
        log("Klaar!")
        log(f"Video: {output_path}")
        log("=" * 50)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
