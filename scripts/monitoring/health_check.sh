#!/usr/bin/env bash
#
# EMSN2 Health Check - Volledige systeemcontrole
# Controleert: Zolder, Berging, Meteo, NAS
#
set -euo pipefail

# Kleuren voor output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Hosts
ZOLDER="192.168.1.178"
BERGING="192.168.1.87"
METEO="192.168.1.156"
NAS="192.168.1.25"

# Counters
CHECKS_PASSED=0
CHECKS_FAILED=0
CHECKS_WARNING=0

print_header() {
    echo ""
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
}

print_subheader() {
    echo -e "\n${BLUE}── $1 ──${NC}"
}

check_ok() {
    echo -e "  ${GREEN}✓${NC} $1"
    ((CHECKS_PASSED++))
}

check_fail() {
    echo -e "  ${RED}✗${NC} $1"
    ((CHECKS_FAILED++))
}

check_warn() {
    echo -e "  ${YELLOW}⚠${NC} $1"
    ((CHECKS_WARNING++))
}

check_host_reachable() {
    local host=$1
    local name=$2
    if ping -c 1 -W 2 "$host" &>/dev/null; then
        check_ok "$name ($host) bereikbaar"
        return 0
    else
        check_fail "$name ($host) NIET bereikbaar"
        return 1
    fi
}

check_ssh_available() {
    local host=$1
    if timeout 5 ssh -o ConnectTimeout=3 -o BatchMode=yes "ronny@$host" 'echo ok' &>/dev/null; then
        return 0
    else
        return 1
    fi
}

check_ssh_service() {
    local host=$1
    local service=$2
    local status
    status=$(timeout 5 ssh -o ConnectTimeout=3 -o BatchMode=yes "ronny@$host" "systemctl is-active $service" 2>/dev/null || echo "error")

    case "$status" in
        active)
            check_ok "$service"
            ;;
        inactive)
            check_warn "$service (inactive)"
            ;;
        *)
            check_fail "$service ($status)"
            ;;
    esac
}

check_ssh_timer() {
    local host=$1
    local timer=$2
    local status
    status=$(timeout 5 ssh -o ConnectTimeout=3 -o BatchMode=yes "ronny@$host" "systemctl is-active $timer" 2>/dev/null || echo "error")

    if [[ "$status" == "active" ]]; then
        check_ok "$timer"
    else
        check_fail "$timer ($status)"
    fi
}

check_disk_usage() {
    local host=$1
    local path=$2
    local name=$3
    local usage
    usage=$(timeout 5 ssh -o ConnectTimeout=3 -o BatchMode=yes "ronny@$host" "df -h $path 2>/dev/null | tail -1 | awk '{print \$5}'" 2>/dev/null || echo "error")

    if [[ "$usage" == "error" ]]; then
        check_fail "$name - niet beschikbaar"
        return
    fi

    local percent=${usage%\%}
    if [[ "$percent" -lt 80 ]]; then
        check_ok "$name: $usage gebruikt"
    elif [[ "$percent" -lt 90 ]]; then
        check_warn "$name: $usage gebruikt"
    else
        check_fail "$name: $usage gebruikt (KRITIEK)"
    fi
}

check_mqtt_broker() {
    if timeout 5 mosquitto_sub -h "$ZOLDER" -t '$SYS/broker/uptime' -C 1 -W 3 &>/dev/null; then
        check_ok "MQTT Broker actief"
    else
        check_fail "MQTT Broker niet bereikbaar"
    fi
}

check_postgres() {
    local secrets_file="/home/ronny/emsn2/.secrets"
    if [[ -f "$secrets_file" ]]; then
        local pg_pass
        pg_pass=$(grep PG_PASSWORD "$secrets_file" 2>/dev/null | cut -d= -f2)
        if PGPASSWORD="$pg_pass" psql -h "$NAS" -p 5433 -U emsn -d emsn -c "SELECT 1" &>/dev/null; then
            check_ok "PostgreSQL database"
        else
            check_fail "PostgreSQL niet bereikbaar"
        fi
    else
        check_warn "PostgreSQL - .secrets niet gevonden"
    fi
}

check_api() {
    local url=$1
    local name=$2
    if curl -s --max-time 5 "$url" &>/dev/null; then
        check_ok "$name"
    else
        check_fail "$name niet bereikbaar"
    fi
}

check_nas_mount() {
    local path=$1
    local name=$2
    if mountpoint -q "$path" 2>/dev/null; then
        check_ok "$name gemount"
    else
        check_fail "$name NIET gemount"
    fi
}

run_host_checks() {
    local host=$1
    local name=$2
    shift 2
    local services=("$@")

    if ! check_ssh_available "$host"; then
        check_fail "SSH niet beschikbaar op $name (key/auth probleem)"
        return 1
    fi

    for service in "${services[@]}"; do
        check_ssh_service "$host" "$service"
    done
    return 0
}

run_timer_checks() {
    local host=$1
    shift
    local timers=("$@")

    for timer in "${timers[@]}"; do
        check_ssh_timer "$host" "$timer"
    done
}

# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

echo ""
echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║           EMSN2 SYSTEEM GEZONDHEIDSCONTROLE                  ║${NC}"
echo -e "${BLUE}║           $(date '+%Y-%m-%d %H:%M:%S')                              ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"

# ─── NETWERK BEREIKBAARHEID ───────────────────────────────────
print_header "NETWERK BEREIKBAARHEID"

check_host_reachable "$ZOLDER" "Zolder" && ZOLDER_OK=0 || ZOLDER_OK=1
check_host_reachable "$BERGING" "Berging" && BERGING_OK=0 || BERGING_OK=1
check_host_reachable "$METEO" "Meteo" && METEO_OK=0 || METEO_OK=1
check_host_reachable "$NAS" "NAS" && NAS_OK=0 || NAS_OK=1

# ─── ZOLDER (192.168.1.178) ───────────────────────────────────
if [[ $ZOLDER_OK -eq 0 ]]; then
    print_header "ZOLDER (192.168.1.178) - BirdNET-Pi Hoofd"

    if check_ssh_available "$ZOLDER"; then
        print_subheader "Services"
        check_ssh_service "$ZOLDER" "birdnet-mqtt-publisher"
        check_ssh_service "$ZOLDER" "mqtt-bridge-monitor"
        check_ssh_service "$ZOLDER" "mosquitto"
        check_ssh_service "$ZOLDER" "reports-api"
        check_ssh_service "$ZOLDER" "ulanzi-bridge"

        print_subheader "Timers"
        check_ssh_timer "$ZOLDER" "lifetime-sync.timer"
        check_ssh_timer "$ZOLDER" "nestbox-screenshot.timer"

        print_subheader "Disk"
        check_disk_usage "$ZOLDER" "/" "Root filesystem"
        check_disk_usage "$ZOLDER" "/home" "Home directory"
    else
        check_fail "SSH niet beschikbaar (key/auth probleem)"
    fi
fi

# ─── BERGING (192.168.1.87) ───────────────────────────────────
if [[ $BERGING_OK -eq 0 ]]; then
    print_header "BERGING (192.168.1.87) - BirdNET-Pi + AtmosBird"

    if check_ssh_available "$BERGING"; then
        print_subheader "Services"
        check_ssh_service "$BERGING" "birdnet-mqtt-publisher"
        check_ssh_service "$BERGING" "mosquitto"

        print_subheader "Timers"
        check_ssh_timer "$BERGING" "lifetime-sync.timer"
        check_ssh_timer "$BERGING" "atmosbird-capture.timer"
        check_ssh_timer "$BERGING" "atmosbird-analysis.timer"
        check_ssh_timer "$BERGING" "atmosbird-timelapse.timer"
        check_ssh_timer "$BERGING" "atmosbird-archive-sync.timer"

        print_subheader "Disk"
        check_disk_usage "$BERGING" "/" "Root filesystem"
        check_disk_usage "$BERGING" "/mnt/usb" "USB opslag"
    else
        check_fail "SSH niet beschikbaar (key/auth probleem)"
    fi
fi

# ─── METEO (192.168.1.156) ────────────────────────────────────
if [[ $METEO_OK -eq 0 ]]; then
    print_header "METEO (192.168.1.156) - Weerstation"

    if check_ssh_available "$METEO"; then
        print_subheader "Timers"
        check_ssh_timer "$METEO" "weather-publisher.timer"

        print_subheader "Disk"
        check_disk_usage "$METEO" "/" "Root filesystem"
    else
        check_fail "SSH niet beschikbaar (key/auth probleem)"
    fi
fi

# ─── NAS (192.168.1.25) ───────────────────────────────────────
print_header "NAS (192.168.1.25) - Centrale Opslag"

print_subheader "NAS Mounts (lokaal)"
check_nas_mount "/mnt/nas-docker" "nas-docker"
check_nas_mount "/mnt/nas-reports" "nas-reports"
check_nas_mount "/mnt/nas-birdnet-archive" "nas-birdnet-archive"

print_subheader "Databases & Services"
check_postgres
check_api "http://$NAS:3000/api/health" "Grafana"
check_api "http://$NAS:1984/api/streams" "go2rtc"

# ─── MQTT & API ───────────────────────────────────────────────
print_header "CENTRALE SERVICES"

print_subheader "MQTT"
check_mqtt_broker

print_subheader "APIs"
check_api "http://$ZOLDER:8081/health" "Reports API"
check_api "http://$ZOLDER:8082" "Screenshot Server"

# ─── SAMENVATTING ─────────────────────────────────────────────
print_header "SAMENVATTING"

echo ""
echo -e "  ${GREEN}Passed:${NC}  $CHECKS_PASSED"
echo -e "  ${YELLOW}Warning:${NC} $CHECKS_WARNING"
echo -e "  ${RED}Failed:${NC}  $CHECKS_FAILED"
echo ""

TOTAL=$((CHECKS_PASSED + CHECKS_WARNING + CHECKS_FAILED))
if [[ $CHECKS_FAILED -eq 0 && $CHECKS_WARNING -eq 0 ]]; then
    echo -e "  ${GREEN}✓ Alle $TOTAL checks geslaagd - systeem gezond!${NC}"
elif [[ $CHECKS_FAILED -eq 0 ]]; then
    echo -e "  ${YELLOW}⚠ Systeem operationeel met $CHECKS_WARNING waarschuwing(en)${NC}"
else
    echo -e "  ${RED}✗ $CHECKS_FAILED kritieke problemen gevonden!${NC}"
fi

echo ""
exit $CHECKS_FAILED
