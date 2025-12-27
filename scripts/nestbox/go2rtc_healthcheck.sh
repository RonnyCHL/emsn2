#!/bin/bash
#
# go2rtc Health Check voor Tuya Nestkast Cameras
# Monitort stream status - GEEN automatische restarts
#
# Met preload in go2rtc.yaml blijven streams automatisch actief.
# Dit script logt alleen de status voor monitoring doeleinden.
#
# Draait via systemd timer elke 30 minuten
#

GO2RTC_API="http://192.168.1.25:1984/api"
LOG_FILE="/var/log/go2rtc-healthcheck.log"
STREAMS=("nestkast_voor" "nestkast_midden" "nestkast_achter")

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE" 2>/dev/null
}

check_stream_active() {
    local stream=$1
    local response=$(curl -s --connect-timeout 5 "${GO2RTC_API}/streams" 2>/dev/null)

    if [ -z "$response" ]; then
        return 1
    fi

    # Check if stream has active producer (has "id" field)
    if echo "$response" | python3 -c "
import json, sys
data = json.load(sys.stdin)
stream = data.get('$stream', {})
producers = stream.get('producers', [])
for p in producers:
    if 'id' in p:
        sys.exit(0)
sys.exit(1)
" 2>/dev/null; then
        return 0
    else
        return 1
    fi
}

main() {
    log "=== go2rtc Health Check ==="

    local online=0
    local offline=0
    local offline_streams=()

    # Check go2rtc API bereikbaarheid
    if ! curl -s --connect-timeout 5 "${GO2RTC_API}/streams" > /dev/null 2>&1; then
        log "ERROR: go2rtc API niet bereikbaar"
        exit 1
    fi

    for stream in "${STREAMS[@]}"; do
        if check_stream_active "$stream"; then
            log "OK: $stream"
            ((online++))
        else
            log "OFFLINE: $stream"
            ((offline++))
            offline_streams+=("$stream")
        fi
    done

    log "Status: $online online, $offline offline"

    if [ $offline -gt 0 ]; then
        log "Offline streams: ${offline_streams[*]}"
        log "INFO: Preload zal automatisch proberen te reconnecten"
        # Exit 1 zodat we in logs kunnen zien dat er iets mis is
        exit 1
    fi

    exit 0
}

main "$@"
