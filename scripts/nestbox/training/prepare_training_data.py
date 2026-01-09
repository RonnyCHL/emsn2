#!/usr/bin/env python3
"""
Nestkast Training Data Preparation

Selecteert en labelt beelden voor model training:
- Leeg: daglicht beelden (09:00-17:00) van alle kasten
- Bezet: nachtbeelden (00:00-06:00) van midden met koolmees

Strategie:
1. Daglicht = lege kast (vogel is overdag weg)
2. Nacht = bezet bij midden (koolmees slaapt daar)
3. Mix van alle kasten voor variatie
"""

import os
import shutil
from pathlib import Path
from datetime import datetime
import random

# Configuratie
NAS_BASE = Path("/mnt/nas-birdnet-archive/nestbox")
OUTPUT_DIR = Path("/home/ronny/emsn2/scripts/nestbox/training/data")
NESTBOXES = ['voor', 'midden', 'achter']

# Tijdvensters voor labeling
NIGHT_HOURS = range(0, 7)     # 00:00 - 06:59 = nacht (bezet voor midden)
DAY_HOURS = range(9, 17)      # 09:00 - 16:59 = dag (leeg voor alle)
EVENING_HOURS = range(17, 24) # 17:00 - 23:59 = avond (bezet voor midden)

# Sample sizes
MAX_LEEG_PER_BOX = 150   # Max leeg beelden per nestkast
MAX_BEZET = 200           # Max bezet beelden (alleen midden)


def get_hour_from_filename(filename):
    """Extract hour from filename like midden_20260108_020015.jpg"""
    try:
        # Format: {nestbox}_{YYYYMMDD}_{HHMMSS}.jpg
        time_part = filename.split('_')[2].split('.')[0]
        hour = int(time_part[:2])
        return hour
    except (IndexError, ValueError):
        return None


def is_night_image(filename):
    """Check if image is from night hours"""
    hour = get_hour_from_filename(filename)
    return hour is not None and hour in NIGHT_HOURS


def is_day_image(filename):
    """Check if image is from day hours"""
    hour = get_hour_from_filename(filename)
    return hour is not None and hour in DAY_HOURS


def is_evening_image(filename):
    """Check if image is from evening hours"""
    hour = get_hour_from_filename(filename)
    return hour is not None and hour in EVENING_HOURS


def collect_images():
    """Collect and label images"""
    leeg_images = []
    bezet_images = []

    for nestbox in NESTBOXES:
        screenshot_dir = NAS_BASE / nestbox / "screenshots"
        if not screenshot_dir.exists():
            print(f"⚠️  {nestbox}: screenshot dir niet gevonden")
            continue

        # Verzamel alle jpg bestanden
        all_images = list(screenshot_dir.rglob("*.jpg"))
        print(f"\n📁 {nestbox}: {len(all_images)} beelden gevonden")

        box_leeg = []
        box_bezet = []

        for img_path in all_images:
            filename = img_path.name

            if is_day_image(filename):
                # Daglicht = altijd leeg (vogel is weg)
                box_leeg.append(img_path)
            elif nestbox == 'midden':
                # Alleen midden heeft 's nachts een koolmees
                if is_night_image(filename) or is_evening_image(filename):
                    # Check of het van januari 2026 is (toen koolmees er zat)
                    if '2026/01' in str(img_path) or '202601' in filename:
                        box_bezet.append(img_path)
                    else:
                        # Oudere nachbeelden zijn waarschijnlijk leeg
                        box_leeg.append(img_path)

        print(f"   - Dag (leeg kandidaten): {len(box_leeg)}")
        print(f"   - Nacht/avond (bezet kandidaten): {len(box_bezet)}")

        # Sample en voeg toe
        if box_leeg:
            sampled = random.sample(box_leeg, min(len(box_leeg), MAX_LEEG_PER_BOX))
            leeg_images.extend(sampled)
            print(f"   ✓ {len(sampled)} leeg beelden geselecteerd")

        if box_bezet:
            bezet_images.extend(box_bezet)

    # Sample bezet als er teveel zijn
    if len(bezet_images) > MAX_BEZET:
        bezet_images = random.sample(bezet_images, MAX_BEZET)

    return leeg_images, bezet_images


def copy_images(leeg_images, bezet_images):
    """Copy images to training directories"""
    # Maak output directories
    leeg_dir = OUTPUT_DIR / "leeg"
    bezet_dir = OUTPUT_DIR / "bezet"

    leeg_dir.mkdir(parents=True, exist_ok=True)
    bezet_dir.mkdir(parents=True, exist_ok=True)

    # Leeg bestaande bestanden op
    for f in leeg_dir.glob("*.jpg"):
        f.unlink()
    for f in bezet_dir.glob("*.jpg"):
        f.unlink()

    print(f"\n📋 Kopiëren trainingsdata...")

    # Kopieer leeg beelden
    for i, img_path in enumerate(leeg_images):
        # Gebruik unieke naam met nestkast prefix
        new_name = f"leeg_{img_path.parent.parent.parent.name}_{img_path.name}"
        dest = leeg_dir / new_name
        shutil.copy2(img_path, dest)
    print(f"   ✓ {len(leeg_images)} leeg beelden gekopieerd")

    # Kopieer bezet beelden
    for i, img_path in enumerate(bezet_images):
        new_name = f"bezet_{img_path.parent.parent.parent.name}_{img_path.name}"
        dest = bezet_dir / new_name
        shutil.copy2(img_path, dest)
    print(f"   ✓ {len(bezet_images)} bezet beelden gekopieerd")


def main():
    print("=" * 60)
    print("NESTKAST TRAINING DATA PREPARATION")
    print("=" * 60)
    print(f"\nBron: {NAS_BASE}")
    print(f"Doel: {OUTPUT_DIR}")

    # Collect images
    leeg_images, bezet_images = collect_images()

    print(f"\n📊 Totaal geselecteerd:")
    print(f"   - Leeg:  {len(leeg_images)} beelden")
    print(f"   - Bezet: {len(bezet_images)} beelden")

    if not leeg_images or not bezet_images:
        print("\n❌ Onvoldoende data voor training!")
        return

    # Copy to training directories
    copy_images(leeg_images, bezet_images)

    print(f"\n✅ Training data klaar in: {OUTPUT_DIR}")
    print(f"\nVolgende stap: Upload naar Google Drive en train in Colab")


if __name__ == '__main__':
    random.seed(42)  # Reproduceerbaar
    main()
