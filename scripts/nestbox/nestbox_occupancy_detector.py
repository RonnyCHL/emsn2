#!/usr/bin/env python3
"""
Nestkast Soort-Herkenning Detector - EMSN
Detecteert automatisch welke vogelsoort in een nestkast zit (of leeg).

Gebruikt MobileNetV2 model getraind op nestkast screenshots.
Werkt op dag EN nacht screenshots.
"""

import os
import sys
import torch
import torch.nn as nn
from torchvision import transforms, models
from PIL import Image
from datetime import datetime
from pathlib import Path
import argparse
import json
import psycopg2

# Voeg project root toe voor imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.config import get_postgres_config

# Configuratie - gebruik het nieuwe soort-herkenning model
MODEL_PATH = "/mnt/nas-birdnet-archive/nestbox/models/nestbox_species_model.pt"
FALLBACK_MODEL_PATH = "/mnt/nas-birdnet-archive/nestbox/models/nestbox_occupancy_model.pt"
INPUT_SIZE = 224
CONFIDENCE_THRESHOLD = 0.7  # Minimale confidence voor detectie

# Database configuratie via core.config
DB_CONFIG = get_postgres_config()


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

    # Probeer hoofdmodel, anders fallback
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

    return model, checkpoint


def predict_image(model, image_path, classes):
    """Voorspel welke soort in de nestkast zit (of leeg)"""
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

    # Bepaal of bezet (alles behalve 'leeg')
    is_occupied = detected_class.lower() != 'leeg'

    # Bepaal gedetecteerde soort (None als leeg)
    species = detected_class if is_occupied else None

    # Bouw probabiliteiten dict
    probs = {cls: probabilities[0][i].item() for i, cls in enumerate(classes)}

    return {
        'class': detected_class,
        'class_idx': class_idx,
        'confidence': conf,
        'is_occupied': is_occupied,
        'species': species,
        'probabilities': probs
    }


def analyze_screenshot(image_path, model=None, classes=None, verbose=False):
    """Analyseer een nestkast screenshot"""
    if model is None:
        model, checkpoint = load_model(MODEL_PATH)
        classes = checkpoint.get('classes', ['leeg', 'bezet'])

    result = predict_image(model, image_path, classes)

    if verbose:
        if result['species']:
            status = f"BEZET - {result['species']}"
        else:
            status = "LEEG"
        print(f"Afbeelding: {image_path}")
        print(f"Status: {status}")
        print(f"Confidence: {result['confidence']:.1%}")
        probs_str = ", ".join([f"{k}={v:.1%}" for k, v in result['probabilities'].items()])
        print(f"Probabiliteiten: {probs_str}")

    return result


def analyze_nestbox(nestbox_id, model=None, classes=None, latest_only=True, verbose=False):
    """Analyseer screenshots van een specifieke nestkast"""
    base_path = Path(f"/mnt/nas-birdnet-archive/nestbox/{nestbox_id}/screenshots")

    if not base_path.exists():
        print(f"Geen screenshots gevonden voor nestkast: {nestbox_id}")
        return None

    # Vind screenshots
    screenshots = sorted(base_path.rglob("*.jpg"))

    if not screenshots:
        print(f"Geen screenshots gevonden voor nestkast: {nestbox_id}")
        return None

    if latest_only:
        screenshots = [screenshots[-1]]

    if model is None:
        model, checkpoint = load_model(MODEL_PATH)
        classes = checkpoint.get('classes', ['leeg', 'bezet'])

    results = []
    for screenshot in screenshots:
        result = predict_image(model, screenshot, classes)
        result['image_path'] = str(screenshot)
        result['nestbox_id'] = nestbox_id
        result['timestamp'] = datetime.now().isoformat()
        results.append(result)

        if verbose:
            if result['species']:
                status = f"BEZET ({result['species']})"
            else:
                status = "LEEG"
            print(f"{screenshot.name}: {status} ({result['confidence']:.1%})")

    return results


def save_to_database(result, capture_type=None):
    """Sla detectie resultaat op in database"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        # Haal probabiliteiten op (backward compatible)
        probs = result['probabilities']
        prob_leeg = probs.get('leeg', 0.0)
        # prob_bezet is 1 - prob_leeg als we soort-herkenning gebruiken
        prob_bezet = 1.0 - prob_leeg if 'bezet' not in probs else probs.get('bezet', 0.0)

        cur.execute("""
            INSERT INTO nestbox_occupancy
            (nestbox_id, is_occupied, confidence, prob_leeg, prob_bezet, image_path, capture_type, species)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            result['nestbox_id'],
            result['is_occupied'],
            result['confidence'],
            prob_leeg,
            prob_bezet,
            result.get('image_path'),
            capture_type,
            result.get('species')
        ))

        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Database error: {e}", file=sys.stderr)
        return False


def analyze_all_nestboxes(verbose=False, save_db=False, capture_type=None):
    """Analyseer alle nestkasten"""
    nestboxes = ['voor', 'midden', 'achter']
    model, checkpoint = load_model(MODEL_PATH)
    classes = checkpoint.get('classes', ['leeg', 'bezet'])

    if verbose:
        print(f"Model geladen: {checkpoint.get('architecture', 'mobilenet_v2')}")
        print(f"Classes: {classes}")
        print(f"Getraind op: {checkpoint.get('train_samples', '?')} samples")
        acc = checkpoint.get('best_val_acc', None)
        if acc:
            print(f"Beste accuracy: {acc:.1f}%")
        print()

    all_results = {}
    for nestbox_id in nestboxes:
        results = analyze_nestbox(nestbox_id, model=model, classes=classes, latest_only=True, verbose=verbose)
        if results:
            all_results[nestbox_id] = results[0]
            if save_db:
                if save_to_database(results[0], capture_type):
                    if verbose:
                        print(f"  -> Opgeslagen in database")

    return all_results


def main():
    parser = argparse.ArgumentParser(description='Nestkast Occupancy Detector')
    parser.add_argument('--image', '-i', help='Pad naar screenshot om te analyseren')
    parser.add_argument('--nestbox', '-n', choices=['voor', 'midden', 'achter'],
                        help='Analyseer specifieke nestkast')
    parser.add_argument('--all', '-a', action='store_true',
                        help='Analyseer alle nestkasten')
    parser.add_argument('--json', '-j', action='store_true',
                        help='Output als JSON')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Verbose output')
    parser.add_argument('--save-db', '-s', action='store_true',
                        help='Sla resultaten op in database')
    parser.add_argument('--capture-type', '-c', type=str, default=None,
                        help='Capture type (auto_morning, auto_night, etc.)')

    args = parser.parse_args()

    if args.image:
        result = analyze_screenshot(args.image, verbose=not args.json)
        if args.json:
            print(json.dumps(result, indent=2))

    elif args.nestbox:
        results = analyze_nestbox(args.nestbox, verbose=not args.json)
        if args.json and results:
            print(json.dumps(results, indent=2))

    elif args.all:
        results = analyze_all_nestboxes(verbose=not args.json, save_db=args.save_db, capture_type=args.capture_type)
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            print("\n=== Samenvatting ===")
            for nestbox_id, result in results.items():
                if result['species']:
                    status = f"BEZET ({result['species']})"
                else:
                    status = "LEEG"
                print(f"{nestbox_id}: {status} ({result['confidence']:.1%})")

    else:
        # Default: analyseer alle nestkasten en sla op
        print("Nestkast Soort-Herkenning Detector - EMSN")
        print("=" * 40)
        results = analyze_all_nestboxes(verbose=True, save_db=args.save_db, capture_type=args.capture_type)
        print("\n=== Samenvatting ===")
        for nestbox_id, result in results.items():
            if result['species']:
                status = f"BEZET ({result['species']})"
            else:
                status = "LEEG"
            print(f"{nestbox_id}: {status} ({result['confidence']:.1%})")


if __name__ == '__main__':
    main()
