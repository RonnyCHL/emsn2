#!/usr/bin/env python3
"""
Nestkast Realtime Detectie Service - EMSN

Detecteert automatisch statusveranderingen in nestkasten en registreert
deze in de nestbox_events tabel. Houdt bij wanneer vogels komen/gaan.

Wordt aangeroepen na elke screenshot capture.
Registreert alleen WIJZIGINGEN in status (leeg->bezet of bezet->leeg).

Gebruik:
    # Na screenshot capture (wordt aangeroepen door nestbox_screenshot service)
    ./nestbox_realtime_detector.py --nestbox midden --image /path/to/screenshot.jpg

    # Analyseer alle nestkasten
    ./nestbox_realtime_detector.py --all

    # Dry-run (geen database wijzigingen)
    ./nestbox_realtime_detector.py --all --dry-run
"""

import os
import sys
import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

import torch
import torch.nn as nn
from torchvision import transforms, models
from PIL import Image
import psycopg2

# Configuratie
MODEL_PATH = "/mnt/nas-birdnet-archive/nestbox/models/nestbox_species_model.pt"
FALLBACK_MODEL_PATH = "/mnt/nas-birdnet-archive/nestbox/models/nestbox_occupancy_model.pt"
INPUT_SIZE = 224
CONFIDENCE_THRESHOLD = 0.50  # Minimale confidence voor statuswijziging (verlaagd voor daglicht detectie)

# Minimale tijd tussen status events (voorkom ruis)
MIN_EVENT_INTERVAL_MINUTES = 30

# Database configuratie
DB_CONFIG = {
    'host': '192.168.1.25',
    'port': 5433,
    'database': 'emsn',
    'user': 'postgres',
    'password': 'IwnadBon2iN'
}

NESTBOXES = ['voor', 'midden', 'achter']


def create_model(num_classes=2):
    """Maak MobileNetV2 model met aangepaste classifier"""
    model = models.mobilenet_v2(weights=None)
    num_features = model.classifier[1].in_features
    model.classifier = nn.Sequential(
        nn.Dropout(p=0.2),
        nn.Linear(num_features, 128),
        nn.ReLU(),
        nn.Dropout(p=0.2),
        nn.Linear(128, num_classes)
    )
    return model


def load_model(model_path=None):
    """Laad het getrainde model"""
    if model_path is None:
        model_path = MODEL_PATH

    if not os.path.exists(model_path):
        if os.path.exists(FALLBACK_MODEL_PATH):
            model_path = FALLBACK_MODEL_PATH
        else:
            raise FileNotFoundError(f"Model niet gevonden: {model_path}")

    checkpoint = torch.load(model_path, map_location='cpu')
    classes = checkpoint.get('classes', ['leeg', 'bezet'])

    model = create_model(num_classes=len(classes))
    model.load_state_dict(checkpoint['model_state_dict'])
    model.eval()

    return model, classes


def predict_image(model, image_path, classes):
    """Voorspel status van nestkast"""
    transform = transforms.Compose([
        transforms.Resize((INPUT_SIZE, INPUT_SIZE)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406],
                             std=[0.229, 0.224, 0.225])
    ])

    image = Image.open(image_path).convert('RGB')
    image_tensor = transform(image).unsqueeze(0)

    with torch.no_grad():
        outputs = model(image_tensor)
        probabilities = torch.softmax(outputs, dim=1)
        confidence, predicted = probabilities.max(1)

    class_idx = predicted.item()
    conf = confidence.item()
    detected_class = classes[class_idx]

    is_occupied = detected_class.lower() != 'leeg'
    species = detected_class if is_occupied else None

    return {
        'is_occupied': is_occupied,
        'species': species,
        'confidence': conf,
        'detected_class': detected_class
    }


def get_db_connection():
    """Maak database connectie"""
    return psycopg2.connect(**DB_CONFIG)


def get_current_status(conn, nestbox_id):
    """Haal huidige status op uit nestbox_events (laatste event)"""
    cur = conn.cursor()
    cur.execute("""
        SELECT event_type, species, event_timestamp
        FROM nestbox_events
        WHERE nestbox_id = %s
        ORDER BY event_timestamp DESC
        LIMIT 1
    """, (nestbox_id,))
    row = cur.fetchone()
    cur.close()

    if row:
        return {
            'event_type': row[0],
            'species': row[1],
            'timestamp': row[2]
        }
    return None


def get_last_occupancy_detection(conn, nestbox_id):
    """Haal laatste AI detectie op"""
    cur = conn.cursor()
    cur.execute("""
        SELECT is_occupied, species, confidence, timestamp
        FROM nestbox_occupancy
        WHERE nestbox_id = %s
        ORDER BY timestamp DESC
        LIMIT 1
    """, (nestbox_id,))
    row = cur.fetchone()
    cur.close()

    if row:
        return {
            'is_occupied': row[0],
            'species': row[1],
            'confidence': row[2],
            'timestamp': row[3]
        }
    return None


def save_occupancy_detection(conn, nestbox_id, result, image_path=None, capture_type=None):
    """Sla AI detectie op in nestbox_occupancy"""
    cur = conn.cursor()

    prob_leeg = 1.0 - result['confidence'] if result['is_occupied'] else result['confidence']
    prob_bezet = result['confidence'] if result['is_occupied'] else 1.0 - result['confidence']

    cur.execute("""
        INSERT INTO nestbox_occupancy
        (nestbox_id, is_occupied, confidence, prob_leeg, prob_bezet, image_path, capture_type, species)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        nestbox_id,
        result['is_occupied'],
        result['confidence'],
        prob_leeg,
        prob_bezet,
        image_path,
        capture_type,
        result.get('species')
    ))

    conn.commit()
    cur.close()


def register_status_change(conn, nestbox_id, new_status, species=None, image_path=None, notes=None):
    """Registreer statusverandering in nestbox_events"""
    cur = conn.cursor()

    # Bepaal event_type
    event_type = 'bezet' if new_status else 'leeg'

    cur.execute("""
        INSERT INTO nestbox_events
        (nestbox_id, event_timestamp, event_type, species, image_path, notes, observer)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (
        nestbox_id,
        datetime.now(),
        event_type,
        species if new_status else None,
        image_path,
        notes or f"Automatisch gedetecteerd door AI",
        'AI-detector'
    ))

    conn.commit()
    cur.close()


def should_register_change(current_event, new_is_occupied, new_species):
    """Bepaal of we een statuswijziging moeten registreren"""
    if current_event is None:
        # Geen eerdere events - altijd registreren
        return True

    current_type = current_event['event_type']
    current_is_occupied = current_type not in ['leeg', 'uitgevlogen', 'mislukt']

    # Check of status veranderd is
    if current_is_occupied != new_is_occupied:
        # Status is veranderd - check minimum interval
        time_since_last = datetime.now() - current_event['timestamp']
        if time_since_last >= timedelta(minutes=MIN_EVENT_INTERVAL_MINUTES):
            return True

    return False


def analyze_nestbox(nestbox_id, image_path=None, model=None, classes=None,
                    dry_run=False, verbose=False):
    """Analyseer nestkast en registreer eventuele statuswijziging"""

    # Bepaal image path als niet opgegeven
    if image_path is None:
        base_path = Path(f"/mnt/nas-birdnet-archive/nestbox/{nestbox_id}/screenshots")
        screenshots = sorted(base_path.rglob("*.jpg"))
        if not screenshots:
            if verbose:
                print(f"[{nestbox_id}] Geen screenshots gevonden")
            return None
        image_path = str(screenshots[-1])

    # Laad model indien nodig
    if model is None:
        model, classes = load_model()

    # Voorspel status
    result = predict_image(model, image_path, classes)

    if verbose:
        status = f"BEZET ({result['species']})" if result['is_occupied'] else "LEEG"
        print(f"[{nestbox_id}] Detectie: {status} ({result['confidence']:.1%})")

    # Database operaties
    conn = get_db_connection()

    try:
        # Haal huidige status op
        current_event = get_current_status(conn, nestbox_id)

        if verbose and current_event:
            print(f"[{nestbox_id}] Huidige status: {current_event['event_type']} "
                  f"(sinds {current_event['timestamp']})")

        # Sla detectie altijd op in occupancy tabel
        if not dry_run:
            save_occupancy_detection(conn, nestbox_id, result, image_path)

        # Check of we statuswijziging moeten registreren
        if result['confidence'] >= CONFIDENCE_THRESHOLD:
            if should_register_change(current_event, result['is_occupied'], result.get('species')):
                new_status = "bezet" if result['is_occupied'] else "leeg"

                if verbose:
                    old_status = current_event['event_type'] if current_event else "onbekend"
                    print(f"[{nestbox_id}] STATUS WIJZIGING: {old_status} -> {new_status}")

                if not dry_run:
                    notes = f"AI detectie met {result['confidence']:.1%} confidence"
                    register_status_change(
                        conn, nestbox_id,
                        result['is_occupied'],
                        species=result.get('species'),
                        image_path=image_path,
                        notes=notes
                    )
                    if verbose:
                        print(f"[{nestbox_id}] Event geregistreerd in database")
                else:
                    if verbose:
                        print(f"[{nestbox_id}] [DRY-RUN] Zou event registreren")

                return {
                    'nestbox_id': nestbox_id,
                    'status_changed': True,
                    'new_status': new_status,
                    'species': result.get('species'),
                    'confidence': result['confidence']
                }
        else:
            if verbose:
                print(f"[{nestbox_id}] Confidence te laag ({result['confidence']:.1%} < {CONFIDENCE_THRESHOLD:.0%})")

        return {
            'nestbox_id': nestbox_id,
            'status_changed': False,
            'detected_status': 'bezet' if result['is_occupied'] else 'leeg',
            'confidence': result['confidence']
        }

    finally:
        conn.close()


def analyze_all_nestboxes(dry_run=False, verbose=False):
    """Analyseer alle nestkasten"""
    model, classes = load_model()

    if verbose:
        print("=" * 50)
        print("NESTKAST REALTIME DETECTIE")
        print("=" * 50)
        print(f"Model: {MODEL_PATH}")
        print(f"Confidence threshold: {CONFIDENCE_THRESHOLD:.0%}")
        print(f"Min. interval tussen events: {MIN_EVENT_INTERVAL_MINUTES} min")
        print()

    results = []
    for nestbox_id in NESTBOXES:
        result = analyze_nestbox(
            nestbox_id,
            model=model,
            classes=classes,
            dry_run=dry_run,
            verbose=verbose
        )
        if result:
            results.append(result)
        if verbose:
            print()

    return results


def main():
    parser = argparse.ArgumentParser(
        description='Nestkast Realtime Detectie Service',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--nestbox', '-n', choices=NESTBOXES,
                        help='Specifieke nestkast analyseren')
    parser.add_argument('--image', '-i', help='Pad naar screenshot')
    parser.add_argument('--all', '-a', action='store_true',
                        help='Alle nestkasten analyseren')
    parser.add_argument('--dry-run', '-d', action='store_true',
                        help='Geen database wijzigingen maken')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Verbose output')
    parser.add_argument('--json', '-j', action='store_true',
                        help='Output als JSON')

    args = parser.parse_args()

    if args.nestbox:
        result = analyze_nestbox(
            args.nestbox,
            image_path=args.image,
            dry_run=args.dry_run,
            verbose=args.verbose and not args.json
        )
        if args.json and result:
            print(json.dumps(result, indent=2, default=str))
        elif result and result.get('status_changed'):
            print(f"Status gewijzigd naar: {result['new_status']}")

    elif args.all:
        results = analyze_all_nestboxes(
            dry_run=args.dry_run,
            verbose=args.verbose and not args.json
        )
        if args.json:
            print(json.dumps(results, indent=2, default=str))
        else:
            changes = [r for r in results if r.get('status_changed')]
            if changes:
                print(f"\n{len(changes)} statuswijziging(en) geregistreerd")
            elif args.verbose:
                print("Geen statuswijzigingen")

    else:
        # Default: alle nestkasten met verbose
        analyze_all_nestboxes(dry_run=args.dry_run, verbose=True)


if __name__ == '__main__':
    main()
