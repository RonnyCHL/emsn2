#!/bin/bash
#
# Nestkast Screenshot Capture
# Maakt automatisch screenshots van alle nestkast cameras
#
# Schema:
#   - Ochtend: 08:00
#   - Middag: 14:00
#   - Nacht: 22:00, 00:00, 02:00, 04:00
#
# Draait via systemd timer

API_URL="http://192.168.1.178:8081/api/nestbox/capture/screenshot"
LOG_FILE="/var/log/nestbox-screenshot.log"

# Bepaal capture type op basis van uur
HOUR=$(date +%H)
case $HOUR in
    08) CAPTURE_TYPE="auto_morning" ;;
    14) CAPTURE_TYPE="auto_middag" ;;
    22|00|02|04) CAPTURE_TYPE="auto_night" ;;
    *) CAPTURE_TYPE="auto_other" ;;
esac

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE" 2>/dev/null
}

capture_screenshot() {
    local nestbox_id=$1

    log "Capturing screenshot for $nestbox_id ($CAPTURE_TYPE)"

    response=$(curl -s -X POST "$API_URL" \
        -H "Content-Type: application/json" \
        -d "{\"nestbox_id\": \"$nestbox_id\", \"capture_type\": \"$CAPTURE_TYPE\"}" \
        2>/dev/null)

    if echo "$response" | grep -q '"success"'; then
        log "SUCCESS: $nestbox_id - $(echo "$response" | grep -o '"file_path": "[^"]*"')"
    else
        log "ERROR: $nestbox_id - $response"
    fi
}

run_occupancy_detection() {
    # Draai realtime detectie na screenshots - detecteert EN registreert statuswijzigingen
    log "Running realtime occupancy detection..."

    SCRIPT_DIR="$(dirname "$0")"
    PYTHON="/home/ronny/emsn2/venv/bin/python3"
    DETECTOR="$SCRIPT_DIR/nestbox_realtime_detector.py"

    if [ -f "$PYTHON" ] && [ -f "$DETECTOR" ]; then
        result=$($PYTHON "$DETECTOR" --all --json 2>&1)

        if [ -n "$result" ]; then
            # Check voor statuswijzigingen
            changes=$(echo "$result" | python3 -c "import json,sys; data=json.load(sys.stdin); changes=[r for r in data if r.get('status_changed')]; print(len(changes))" 2>/dev/null)

            if [ "$changes" != "0" ] && [ -n "$changes" ]; then
                log "STATUSWIJZIGING: $changes nestkast(en) gewijzigd"
                # Log details
                echo "$result" | python3 -c "
import json, sys
data = json.load(sys.stdin)
for r in data:
    if r.get('status_changed'):
        print(f\"  -> {r['nestbox_id']}: {r['new_status']} ({r.get('species', '-')}) [{r['confidence']*100:.0f}%]\")
" 2>/dev/null | while read line; do log "$line"; done
            else
                log "Geen statuswijzigingen gedetecteerd"
            fi
        else
            log "WARN: Realtime detection returned no results"
        fi
    else
        log "WARN: Realtime detector niet gevonden, skip detection"
    fi
}

main() {
    log "=== Nestbox Screenshot Capture Started ($CAPTURE_TYPE) ==="

    # Capture alle 3 nestkasten
    for nestbox in voor midden achter; do
        capture_screenshot "$nestbox"
        sleep 2  # Kleine pauze tussen captures
    done

    # Draai occupancy detectie na nacht screenshots
    run_occupancy_detection

    log "=== Capture Complete ==="
}

main "$@"

# Altijd succesvol afsluiten (occupancy detection mag falen zonder dat de service faalt)
exit 0
