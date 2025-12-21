#!/usr/bin/env python3
"""
Train CNN op bestaande spectrogrammen - skip download fase.
V5: PyTorch versie met optimalisaties voor trage CPUs.
"""
import os
import sys
import random
import numpy as np
from pathlib import Path
import psycopg2
from datetime import datetime
import re

# PyTorch threading optimalisatie
import torch
torch.set_num_threads(6)  # Optimized voor Celeron J4125

# Voeg src toe aan path
sys.path.insert(0, '/app')

DATA_DIR = Path('/app/data')
MODELS_DIR = DATA_DIR / 'models'
LOGS_DIR = Path('/app/logs')

# Maximum samples per klasse - geoptimaliseerd voor snelheid + kwaliteit
MAX_PER_CLASS = 800

PG_HOST = os.environ.get('PG_HOST', '192.168.1.25')
PG_PORT = os.environ.get('PG_PORT', '5433')
PG_DB = os.environ.get('PG_DB', 'emsn')
PG_USER = os.environ.get('PG_USER', 'birdpi_zolder')
PG_PASS = os.environ.get('PG_PASS', 'REDACTED_DB_PASS')

def get_pg():
    return psycopg2.connect(host=PG_HOST, port=PG_PORT, database=PG_DB, user=PG_USER, password=PG_PASS)

def save_confusion_matrix(species_name, cm, class_names):
    """Save confusion matrix to database for dashboard visualization."""
    try:
        conn = get_pg()
        cur = conn.cursor()
        # Delete old data for this species
        cur.execute("DELETE FROM vocalization_confusion_matrix WHERE species_name = %s", (species_name,))
        # Insert new confusion matrix data
        for i, true_label in enumerate(class_names):
            for j, pred_label in enumerate(class_names):
                count = int(cm[i][j])
                cur.execute("""
                    INSERT INTO vocalization_confusion_matrix
                    (species_name, true_label, predicted_label, count)
                    VALUES (%s, %s, %s, %s)
                """, (species_name, true_label, pred_label, count))
        conn.commit()
        cur.close()
        conn.close()
        print(f"  Confusion matrix saved to database", flush=True)
    except Exception as e:
        print(f"  Warning: Could not save confusion matrix: {e}", flush=True)

def update_status(species, status, phase, progress, **kwargs):
    try:
        conn = get_pg()
        cur = conn.cursor()
        cur.execute("SELECT id FROM vocalization_training WHERE species_name = %s", (species,))
        if cur.fetchone():
            sql = "UPDATE vocalization_training SET status=%s, phase=%s, progress_pct=%s, updated_at=NOW()"
            vals = [status, phase, progress]
            # Auto-set completed_at when status is completed
            if status == 'completed':
                sql += ", completed_at=NOW()"
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
    except Exception as e:
        print(f"  DB update fout: {e}", flush=True)

def combine_spectrograms(spec_dir, max_per_class=MAX_PER_CLASS):
    """Combineer spectrogrammen met limiet per klasse."""
    X_list, y_list = [], []
    total_available = 0

    for cls in ['song', 'call', 'alarm']:
        cls_dir = spec_dir / cls
        if not cls_dir.exists():
            print(f"  {cls}: directory niet gevonden", flush=True)
            continue
        files = list(cls_dir.glob('*.npy'))
        total_available += len(files)
        print(f"  {cls}: {len(files)} files", end="", flush=True)

        if len(files) > max_per_class:
            files = random.sample(files, max_per_class)
            print(f" (sampled {max_per_class})", flush=True)
        else:
            print(flush=True)

        loaded = 0
        for f in files:
            try:
                X_list.append(np.load(f))
                y_list.append(cls)
                loaded += 1
            except:
                pass
        print(f"    Geladen: {loaded}", flush=True)

    print(f"  Totaal beschikbaar: {total_available}", flush=True)
    print(f"  Geladen voor training: {len(X_list)}", flush=True)

    if len(X_list) < 100:
        print("  ERROR: Te weinig data!", flush=True)
        return False

    X = np.stack(X_list)
    y = np.array(y_list)
    mem_mb = X.nbytes / 1024**2
    print(f"  Array: {X.shape} ({mem_mb:.1f} MB)", flush=True)

    np.save(spec_dir / 'X_spectrograms.npy', X)
    np.save(spec_dir / 'y_labels.npy', y)
    print(f"  Opgeslagen!", flush=True)
    return True

def train_species(name, dirname):
    spec_dir = DATA_DIR / f'spectrograms-{dirname}'
    model_path = MODELS_DIR / f'{dirname}_cnn_v1.pt'

    if model_path.exists():
        print(f"SKIP {name} - model bestaat al", flush=True)
        update_status(name, 'completed', 'Model bestaat al', 100)
        return

    if not spec_dir.exists():
        print(f"SKIP {name} - geen spectrogrammen directory", flush=True)
        return

    print(f"\n{'='*60}", flush=True)
    print(f"Training: {name}", flush=True)
    print(f"{'='*60}", flush=True)

    update_status(name, 'training', 'Combineren', 55)

    # Check of al gecombineerd
    x_file = spec_dir / 'X_spectrograms.npy'
    # Altijd opnieuw combineren met lagere sample size
    if not combine_spectrograms(spec_dir):
        update_status(name, 'failed', 'Te weinig data', 0, error_message='< 100 spectrograms')
        return

    update_status(name, 'training', 'PyTorch CNN training', 60)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\n  PyTorch CNN training starten...", flush=True)
    
    try:
        from src.classifiers.cnn_classifier_pytorch import CNNVocalizationClassifier, plot_training_history, plot_confusion_matrix
        
        classifier = CNNVocalizationClassifier()
        X, y, class_names = classifier.load_data(str(spec_dir))
        
        # Progress callback
        def on_epoch_end(current_epoch, total_epochs, val_acc):
            progress = 60 + int((current_epoch / total_epochs) * 35)
            phase = f'Epoch {current_epoch}/{total_epochs}'
            update_status(name, 'training', phase, progress, accuracy=val_acc)
            print(f"  [Callback] Epoch {current_epoch}/{total_epochs} - val_acc: {val_acc:.4f}", flush=True)
        
        update_status(name, 'training', 'Model training', 70)
        
        # Geoptimaliseerde training parameters voor snelheid + betrouwbaarheid
        results = classifier.train(
            X, y,
            test_size=0.2,
            epochs=25,      # Verlaagd van 30 - early stopping vangt dit op
            batch_size=128, # Verhoogd van 64 - snellere epochs, stabielere gradients
            patience=5,     # Verlaagd van 7 - sneller stoppen bij convergentie
            progress_callback=on_epoch_end
        )
        
        classifier.save(str(model_path))
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        history_path = LOGS_DIR / f"{dirname}_training_history_{timestamp}.png"
        cm_path = LOGS_DIR / f"{dirname}_confusion_matrix_{timestamp}.png"
        
        plot_training_history(results['history'], str(history_path))
        plot_confusion_matrix(
            results['confusion_matrix'],
            class_names,
            str(cm_path),
            results['accuracy']
        )

        acc = results['accuracy']
        print(f"\n  Test Accuracy: {acc:.2%}", flush=True)

        # Save confusion matrix to database (aparte try-except zodat dit nooit completion blokkeert)
        try:
            save_confusion_matrix(name, results['confusion_matrix'], class_names)
        except Exception as cm_err:
            print(f"  Warning: Confusion matrix opslaan mislukt: {cm_err}", flush=True)

        # Update status ALTIJD na succesvolle training
        if model_path.exists():
            update_status(name, 'completed', 'Voltooid', 100, accuracy=acc)
            print(f"\n  SUCCESS! Model opgeslagen: {model_path}", flush=True)
        else:
            update_status(name, 'failed', 'Model niet opgeslagen', 0)
            print(f"\n  FAILED - model niet gecreëerd", flush=True)

    except Exception as e:
        import traceback
        error_msg = str(e)[:200]
        print(f"\n  ERROR: {error_msg}", flush=True)
        traceback.print_exc()
        update_status(name, 'failed', 'Training error', 0, error_message=error_msg)

# Soorten lijst
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
    print("=" * 60, flush=True)
    print("EMSN 2.0 - Train Existing Spectrograms V5 (Optimized PyTorch)", flush=True)
    print(f"Max samples per class: {MAX_PER_CLASS}", flush=True)
    print(f"PyTorch threads: {torch.get_num_threads()}", flush=True)
    print("=" * 60, flush=True)

    for name, dirname in SPECIES:
        train_species(name, dirname)

    print("\n" + "=" * 60, flush=True)
    print("KLAAR", flush=True)
    print("=" * 60, flush=True)

    # Automatisch doorgaan met volledige pipeline voor alle 232 Nederlandse soorten
    print("\n" + "=" * 60, flush=True)
    print("STARTEN VOLLEDIGE PIPELINE VOOR 232 SOORTEN", flush=True)
    print("=" * 60, flush=True)

    import subprocess
    subprocess.run([sys.executable, '/app/full_pipeline.py'], check=False)
