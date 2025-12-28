#!/bin/bash
# Vocalization Enricher: Turbo mode voor backlog, daarna continuous
# Dit script verwerkt eerst de hele backlog en start dan de service in continuous mode

LOG_FILE="/mnt/usb/logs/vocalization_turbo_$(date +%Y%m%d_%H%M%S).log"
SCRIPT_DIR="$(dirname "$0")"
VENV="/home/ronny/emsn2/venv/bin/python3"
ENRICHER="$SCRIPT_DIR/vocalization_enricher.py"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=== Vocalization Enricher Turbo Mode ==="
log "Stap 1: Backlog verwerken (run_once mode)..."

# Run once om hele backlog te verwerken
$VENV $ENRICHER 2>&1 | tee -a "$LOG_FILE"

log "=== Backlog verwerking voltooid ==="
log "Stap 2: Batch size terugzetten naar 50..."

# Batch size terugzetten naar normaal
sed -i 's/BATCH_SIZE = 200.*# TURBO MODE.*/BATCH_SIZE = 50  # Normaal: 50 per batch/' "$ENRICHER"

log "Stap 3: Continuous mode starten (interval 5 min)..."

# Start continuous mode
exec $VENV $ENRICHER --continuous --interval 5
