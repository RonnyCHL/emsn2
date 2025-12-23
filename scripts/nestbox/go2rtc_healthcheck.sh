#!/bin/bash
#
# go2rtc Health Check voor Tuya Nestkast Cameras
# Controleert of alle streams actief zijn en herstart go2rtc indien nodig
#
# Draait via systemd timer elke 30 minuten

GO2RTC_API="http://192.168.1.25:1984/api"
NAS_IP="192.168.1.25"
LOG_FILE="/var/log/go2rtc-healthcheck.log"
STREAMS=("nestkast_voor" "nestkast_midden" "nestkast_achter")

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE" 2>/dev/null
}

check_stream_active() {
    local stream=$1
    # Check if stream has an active producer with an ID (not just URL)
    local response=$(curl -s --connect-timeout 5 "${GO2RTC_API}/streams" 2>/dev/null)

    if [ -z "$response" ]; then
        log "ERROR: Cannot reach go2rtc API"
        return 1
    fi

    # Check if stream has active producer (has "id" field, not just "url")
    if echo "$response" | python3 -c "
import json, sys
data = json.load(sys.stdin)
stream = data.get('$stream', {})
producers = stream.get('producers', [])
# Stream is active if any producer has an 'id' (active connection)
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

restart_go2rtc() {
    log "Restarting go2rtc container on NAS via SSH..."

    # Try SSH with key-based auth to restart go2rtc container
    # Note: ronny heeft sudoers regel op NAS: /etc/sudoers.d/ronny-docker
    # Dit staat passwordless docker access toe via: sudo /usr/local/bin/docker
    local docker_output
    docker_output=$(ssh -o BatchMode=yes -o ConnectTimeout=5 ronny@${NAS_IP} "sudo /usr/local/bin/docker restart go2rtc" 2>&1)
    local docker_exit=$?

    if [ $docker_exit -eq 0 ]; then
        log "SUCCESS: go2rtc container restarted via SSH"
        sleep 15  # Give go2rtc time to reconnect to Tuya
        return 0
    else
        log "WARN: Docker restart failed (exit $docker_exit): $docker_output"

        # Check if it's a permission issue
        if echo "$docker_output" | grep -q "permission denied"; then
            log "INFO: Docker group not active yet. On NAS run: sudo synoservicectl --restart sshd"
        fi

        log "Trying soft reconnect via stream access..."

        # Fallback: try to trigger reconnect by accessing streams
        for stream in "${STREAMS[@]}"; do
            log "Triggering reconnect for $stream..."
            timeout 5 ffprobe -v quiet "rtsp://${NAS_IP}:8554/$stream" 2>/dev/null &
        done
        wait
        sleep 10
        return 1
    fi
}

main() {
    log "=== go2rtc Health Check Started ==="

    local all_ok=true
    local failed_streams=()

    for stream in "${STREAMS[@]}"; do
        if check_stream_active "$stream"; then
            log "OK: $stream is active"
        else
            log "WARN: $stream is NOT active"
            all_ok=false
            failed_streams+=("$stream")
        fi
    done

    if [ "$all_ok" = false ]; then
        log "Found ${#failed_streams[@]} inactive streams: ${failed_streams[*]}"
        restart_go2rtc

        # Check again after restart attempt
        sleep 5
        local still_failed=()
        for stream in "${failed_streams[@]}"; do
            if ! check_stream_active "$stream"; then
                still_failed+=("$stream")
            fi
        done

        if [ ${#still_failed[@]} -gt 0 ]; then
            log "ERROR: Streams still inactive after reconnect attempt: ${still_failed[*]}"
            log "Manual intervention may be required (restart go2rtc via Synology DSM)"
        else
            log "SUCCESS: All streams reconnected"
        fi
    else
        log "All streams healthy"
    fi

    log "=== Health Check Complete ==="
}

main "$@"
