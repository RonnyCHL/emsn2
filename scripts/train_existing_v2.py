#!/usr/bin/env python3
"""
Train CNN op bestaande spectrogrammen - skip download fase.
V2: Met sampling limiet per klasse om geheugen te sparen.
"""
import os
import sys
import random
import numpy as np
from pathlib import Path
import psycopg2
from datetime import datetime
import subprocess

DATA_DIR = Path('/app/data')
MODELS_DIR = DATA_DIR / 'models'
LOGS_DIR = Path('/app/logs')

# Maximum samples per klasse (song/call/alarm) om geheugen te sparen
MAX_PER_CLASS = 2000

PG_HOST = os.environ.get('PG_HOST', '192.168.1.25')
PG_PORT = os.environ.get('PG_PORT', '5433')
PG_DB = os.environ.get('PG_DB', 'emsn')
PG_USER = os.environ.get('PG_USER', 'birdpi_zolder')
PG_PASS = os.environ.get('PG_PASS', 'REDACTED_DB_PASS')

def get_pg():
    return psycopg2.connect(host=PG_HOST, port=PG_PORT, database=PG_DB, user=PG_USER, password=PG_PASS)

def update_status(species, status, phase, progress, **kwargs):
    conn = get_pg()
    cur = conn.cursor()
    cur.execute("SELECT id FROM vocalization_training WHERE species_name = %s", (species,))
    if cur.fetchone():
        sql = "UPDATE vocalization_training SET status=%s, phase=%s, progress_pct=%s, updated_at=NOW()"
        vals = [status, phase, progress]
        for k,v in kwargs.items():
            sql += f", {k}=%s"
            vals.append(v)
        sql += " WHERE species_name=%s"
        vals.append(species)
        cur.execute(sql, vals)
    else:
        cur.execute("""INSERT INTO vocalization_training
            (species_name, status, phase, progress_pct, started_at, updated_at)
            VALUES (%s,%s,%s,%s,NOW(),NOW())""", (species, status, phase, progress))
    conn.commit()
    cur.close()
    conn.close()

def combine_spectrograms(spec_dir, max_per_class=MAX_PER_CLASS):
    """Combineer spectrogrammen met limiet per klasse om geheugen te sparen."""
    X_list, y_list = [], []
    total_available = 0

    for cls in ['song', 'call', 'alarm']:
        cls_dir = spec_dir / cls
        if not cls_dir.exists():
            print(f"  {cls}: directory niet gevonden")
            continue
        files = list(cls_dir.glob('*.npy'))
        total_available += len(files)
        print(f"  {cls}: {len(files)} files", end="")

        # Sample als teveel bestanden
        if len(files) > max_per_class:
            files = random.sample(files, max_per_class)
            print(f" (sampled {max_per_class})")
        else:
            print()

        loaded = 0
        for f in files:
            try:
                X_list.append(np.load(f))
                y_list.append(cls)
                loaded += 1
            except Exception as e:
                pass

        print(f"    Loaded: {loaded}")

    print(f"  Totaal beschikbaar: {total_available}")
    print(f"  Geladen voor training: {len(X_list)}")

    if len(X_list) < 100:
        print("  ERROR: Te weinig data!")
        return False

    X = np.stack(X_list)
    y = np.array(y_list)

    mem_mb = X.nbytes / 1024**2
    print(f"  Array: {X.shape} ({mem_mb:.1f} MB)")

    np.save(spec_dir / 'X_spectrograms.npy', X)
    np.save(spec_dir / 'y_labels.npy', y)
    print(f"  Opgeslagen!")
    return True

def train_species(name, dirname):
    spec_dir = DATA_DIR / f'spectrograms-{dirname}'
    model_path = MODELS_DIR / f'{dirname}_cnn_v1.keras'

    if model_path.exists():
        print(f"SKIP {name} - model exists")
        update_status(name, 'completed', 'Model bestaat al', 100)
        return

    if not spec_dir.exists():
        print(f"SKIP {name} - no spectrograms directory")
        return

    print(f"\n{'='*60}")
    print(f"Training: {name}")
    print(f"{'='*60}")

    update_status(name, 'training', 'Combineren', 55)

    # Check of al gecombineerd
    x_file = spec_dir / 'X_spectrograms.npy'
    if x_file.exists():
        print(f"  X_spectrograms.npy bestaat al, skip combineren")
    else:
        if not combine_spectrograms(spec_dir):
            update_status(name, 'failed', 'Te weinig data', 0, error_message='< 100 spectrograms')
            return

    update_status(name, 'training', 'CNN training', 60)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\n  Starting CNN training...")
    try:
        result = subprocess.run([
            sys.executable, '-m', 'src.classifiers.cnn_classifier',
            '--data-dir', str(spec_dir),
            '--output-model', str(model_path),
            '--output-dir', str(LOGS_DIR),
            '--epochs', '50',
            '--batch-size', '32',
            '--patience', '10'
        ], capture_output=True, text=True, timeout=7200)

        print("  Training output (last 500 chars):")
        print(result.stdout[-500:] if result.stdout else "  No stdout")

        if result.stderr:
            print("  Stderr (last 300 chars):")
            print(result.stderr[-300:])
    except subprocess.TimeoutExpired:
        update_status(name, 'failed', 'Timeout', 0, error_message='Timeout na 2 uur')
        print(f"  TIMEOUT!")
        return
    except Exception as e:
        update_status(name, 'failed', 'Error', 0, error_message=str(e)[:200])
        print(f"  ERROR: {e}")
        return

    if model_path.exists():
        # Parse accuracy
        acc = 0.0
        for line in result.stdout.split('\n'):
            if 'Test Accuracy' in line:
                try:
                    # Extract percentage like "85.50%"
                    import re
                    match = re.search(r'(\d+\.?\d*)%', line)
                    if match:
                        acc = float(match.group(1)) / 100
                except: pass

        update_status(name, 'completed', 'Voltooid', 100, accuracy=acc)
        print(f"\n  SUCCESS! Accuracy: {acc:.1%}")
    else:
        err_msg = result.stderr[:200] if result.stderr else 'Model file niet gemaakt'
        update_status(name, 'failed', 'Model niet gemaakt', 0, error_message=err_msg)
        print(f"\n  FAILED - model niet gecreëerd")

# Main
SPECIES = [
    ('Roodborst', 'roodborst'),
    ('Ekster', 'ekster'),
    ('Pimpelmees', 'pimpelmees'),
    ('Koolmees', 'koolmees'),
    ('Houtduif', 'houtduif'),
    ('Merel', 'merel'),
    ('Grauwe Gans', 'grauwe_gans'),
    ('Koperwiek', 'koperwiek'),
    ('Winterkoning', 'winterkoning'),
    ('Vink', 'vink'),
    ('Turkse Tortel', 'turkse_tortel'),
    ('Kolgans', 'kolgans'),
    ('Roek', 'roek'),
    ('Boomkruiper', 'boomkruiper'),
]

if __name__ == '__main__':
    print("=" * 60)
    print("EMSN 2.0 - Train Existing Spectrograms V2")
    print(f"Max samples per class: {MAX_PER_CLASS}")
    print("=" * 60)

    for name, dirname in SPECIES:
        train_species(name, dirname)

    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)
