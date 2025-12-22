#!/usr/bin/env python3
"""
Monitor current training and automatically start full pipeline when done.
Run this script after the current train_existing.py completes.
"""
import os
import sys
import time
import psycopg2
from datetime import datetime
from pathlib import Path

sys.path.insert(0, '/app')

# Try to load from secrets.py first (when running on Pi)
_secrets_loaded = False
try:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'config'))
    from emsn_secrets import get_postgres_config
    _pg = get_postgres_config()
    _secrets_loaded = True
except ImportError:
    _pg = {}

# Configuration (secrets or environment variables)
PG_HOST = _pg.get('host') or os.environ.get('PG_HOST', '192.168.1.25')
PG_PORT = _pg.get('port') or os.environ.get('PG_PORT', '5433')
PG_DB = _pg.get('database') or os.environ.get('PG_DB', 'emsn')
PG_USER = _pg.get('user') or os.environ.get('PG_USER', 'birdpi_zolder')
PG_PASS = _pg.get('password') or os.environ.get('PG_PASS', '')

def get_training_status():
    """Check how many species are currently training."""
    conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, database=PG_DB, user=PG_USER, password=PG_PASS)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM vocalization_training WHERE status = 'training'")
    training = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM vocalization_training WHERE status = 'completed'")
    completed = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM vocalization_training WHERE status = 'pending'")
    pending = cur.fetchone()[0]
    cur.close()
    conn.close()
    return training, completed, pending

def main():
    print(f"[{datetime.now()}] Auto-continue monitor started")
    print("Waiting for current 14-species training to complete...")
    
    while True:
        training, completed, pending = get_training_status()
        print(f"[{datetime.now()}] Training: {training}, Completed: {completed}, Pending: {pending}")
        
        # If nothing is training and we have 14 completed, start full pipeline
        if training == 0 and completed >= 14:
            print(f"[{datetime.now()}] Initial training complete! Starting full pipeline...")
            os.system("python3 /app/full_pipeline.py")
            break
        
        # Wait 60 seconds before checking again
        time.sleep(60)

if __name__ == "__main__":
    main()
