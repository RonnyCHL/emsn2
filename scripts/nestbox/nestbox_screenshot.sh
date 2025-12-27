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
    # Draai bij elke screenshot
    log "Running occupancy detection..."
    if true; then

        # Activeer venv en draai detector
        SCRIPT_DIR="$(dirname "$0")"
        if [ -f "/home/ronny/emsn2/venv/bin/python3" ]; then
            result=$(/home/ronny/emsn2/venv/bin/python3 "$SCRIPT_DIR/nestbox_occupancy_detector.py" --all --json --save-db --capture-type "$CAPTURE_TYPE" 2>/dev/null)

            if [ -n "$result" ]; then
                log "Occupancy detection result: $result"

                # Parse resultaten en log per nestkast
                for nestbox in voor midden achter; do
                    is_occupied=$(echo "$result" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('$nestbox',{}).get('is_occupied',''))" 2>/dev/null)
                    confidence=$(echo "$result" | python3 -c "import json,sys; d=json.load(sys.stdin); print(f\"{d.get('$nestbox',{}).get('confidence',0)*100:.0f}\")" 2>/dev/null)

                    if [ "$is_occupied" = "True" ]; then
                        log "BEZET: $nestbox (${confidence}% confidence) - slapende vogel gedetecteerd!"
                    fi
                done
            else
                log "WARN: Occupancy detection returned no results"
            fi
        else
            log "WARN: Python venv niet gevonden, skip occupancy detection"
        fi
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
