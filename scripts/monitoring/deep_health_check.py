#!/usr/bin/env python3
"""
EMSN2 Deep Health Check - Ultieme Systeemdiagnose

Dit script voert een diepgaande gezondheidscontrole uit op ALLE aspecten
van het EMSN2 ecosysteem. Het is het meest complete diagnostic tool.

15 CATEGORIEËN:

1. NETWERK & BEREIKBAARHEID:
   - Ping alle apparaten (Zolder, Berging, Meteo, NAS, Ulanzi, Router)
   - Meet latency en packet loss
   - Test SSH connectiviteit

2. SERVICES & TIMERS:
   - Controleer alle systemd services per Pi
   - Controleer alle timers (sync, atmosbird, etc.)
   - Detecteer gefaalde services

3. HARDWARE METRICS (per Pi):
   - CPU temperatuur en throttling status
   - CPU/Memory/Swap usage
   - Disk usage alle mounts (root, USB, NAS)
   - Uptime

4. NAS & OPSLAG:
   - PostgreSQL connectiviteit en query performance
   - NAS mount status en beschikbaarheid
   - Disk space op alle locaties

5. API ENDPOINTS:
   - MQTT broker status en bridge connectiviteit
   - Reports API, Grafana, go2rtc, Homer
   - BirdNET-Pi web interfaces
   - Ulanzi AWTRIX

6. NESTKAST CAMERAS:
   - go2rtc stream status per camera
   - Producer status controle

7. ATMOSBIRD (HEMELMONITORING):
   - Pi Camera NoIR status
   - Lokale captures op USB (berging)
   - NAS archief captures
   - Sky observations database
   - ISS passes en timelapses

8. WEERSTATION (METEO):
   - Weather data frequentie
   - Huidige meteo waarden
   - Sensor status

9. DATA KWALITEIT & SYNC:
   - Laatste detecties per station
   - Sync status (SQLite vs PostgreSQL)
   - Detection gaps

10. LOGS & ERRORS:
    - Recente errors in journalctl
    - Error count per host

11. BIRDNET-Pi DATABASE INTEGRITEIT:
    - SQLite database integrity check
    - Laatste audio file timestamps
    - Database bestandsgrootte

12. MQTT BRIDGE STATUS:
    - Bridge connectie berging ↔ zolder
    - Message throughput
    - Laatste bridge heartbeat

13. INTERNET & CONNECTIVITEIT:
    - DNS resolution test
    - Internet bereikbaarheid (8.8.8.8)
    - NAS mount response time

14. SECURITY CHECKS:
    - Failed SSH login attempts
    - Sudo usage (laatste 24u)
    - Onverwachte processen

15. BACKUP & TRENDS:
    - PostgreSQL backup status
    - Detectie trends (vandaag vs gisteren)
    - Disk groei voorspelling
    - Vocalization model beschikbaarheid
    - Ulanzi display laatste notificatie

Auteur: Claude Code (IT Specialist EMSN2)
Versie: 3.0.0
"""

import os
import sys
import json
import socket
import subprocess
import time
from pathlib import Path
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum

# Voeg project root toe voor core modules
sys.path.insert(0, str(Path(__file__).parent.parent))

# ═══════════════════════════════════════════════════════════════
# CONFIGURATIE
# ═══════════════════════════════════════════════════════════════

class Status(Enum):
    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class CheckResult:
    """Resultaat van een individuele check"""
    name: str
    status: Status
    message: str
    details: Optional[Dict[str, Any]] = None
    duration_ms: Optional[float] = None


@dataclass
class CategoryResult:
    """Resultaten van een categorie checks"""
    name: str
    checks: List[CheckResult] = field(default_factory=list)

    @property
    def status(self) -> Status:
        if any(c.status == Status.CRITICAL for c in self.checks):
            return Status.CRITICAL
        if any(c.status == Status.WARNING for c in self.checks):
            return Status.WARNING
        if all(c.status == Status.OK for c in self.checks):
            return Status.OK
        return Status.UNKNOWN

    @property
    def ok_count(self) -> int:
        return sum(1 for c in self.checks if c.status == Status.OK)

    @property
    def warning_count(self) -> int:
        return sum(1 for c in self.checks if c.status == Status.WARNING)

    @property
    def critical_count(self) -> int:
        return sum(1 for c in self.checks if c.status == Status.CRITICAL)


# Netwerk configuratie
HOSTS = {
    'zolder': {'ip': '192.168.1.178', 'type': 'pi', 'desc': 'BirdNET-Pi Hoofd'},
    'berging': {'ip': '192.168.1.87', 'type': 'pi', 'desc': 'BirdNET-Pi + AtmosBird'},
    'meteo': {'ip': '192.168.1.156', 'type': 'pi', 'desc': 'Weerstation'},
    'nas': {'ip': '192.168.1.25', 'type': 'nas', 'desc': 'Synology DS224Plus'},
    'ulanzi': {'ip': '192.168.1.11', 'type': 'display', 'desc': 'AWTRIX Light'},
    'router': {'ip': '192.168.1.1', 'type': 'router', 'desc': 'Netwerk Gateway'},
}

# Services per host
SERVICES = {
    'zolder': [
        'birdnet-mqtt-publisher',
        'mqtt-bridge-monitor',
        'mosquitto',
        'reports-api',
        'ulanzi-bridge',
    ],
    'berging': [
        'birdnet-mqtt-publisher',
        'mosquitto',
    ],
    'meteo': [],
}

# Timers per host
TIMERS = {
    'zolder': [
        'lifetime-sync.timer',
        'nestbox-screenshot.timer',
    ],
    'berging': [
        'lifetime-sync.timer',
        'atmosbird-capture.timer',
        'atmosbird-analysis.timer',
        'atmosbird-timelapse.timer',
        'atmosbird-archive-sync.timer',
    ],
    'meteo': [
        'weather-publisher.timer',
    ],
}

# API Endpoints
API_ENDPOINTS = [
    {'name': 'Reports API', 'url': 'http://192.168.1.178:8081/health'},
    {'name': 'Screenshot Server', 'url': 'http://192.168.1.178:8082'},
    {'name': 'Grafana', 'url': 'http://192.168.1.25:3000/api/health'},
    {'name': 'go2rtc', 'url': 'http://192.168.1.25:1984/api/streams'},
    {'name': 'Homer Dashboard', 'url': 'http://192.168.1.25:8181'},
    {'name': 'Ulanzi AWTRIX', 'url': 'http://192.168.1.11/api/stats'},
    {'name': 'BirdNET-Pi Zolder', 'url': 'http://192.168.1.178:80'},
    {'name': 'BirdNET-Pi Berging', 'url': 'http://192.168.1.87:80'},
]

# NAS Mounts
NAS_MOUNTS = [
    {'path': '/mnt/nas-docker', 'name': 'Docker volumes'},
    {'path': '/mnt/nas-reports', 'name': 'AI Rapporten'},
    {'path': '/mnt/nas-birdnet-archive', 'name': 'BirdNET Archief (8TB)'},
]

# Thresholds
THRESHOLDS = {
    'disk_warning': 80,
    'disk_critical': 90,
    'memory_warning': 85,
    'memory_critical': 95,
    'cpu_temp_warning': 70,
    'cpu_temp_critical': 80,
    'latency_warning': 50,  # ms
    'latency_critical': 200,  # ms
    'detection_gap_warning': 2,  # hours
    'detection_gap_critical': 6,  # hours
    'sync_lag_warning': 1,  # hours
    'sync_lag_critical': 3,  # hours
}


# ═══════════════════════════════════════════════════════════════
# KLEUREN EN OUTPUT
# ═══════════════════════════════════════════════════════════════

class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    MAGENTA = '\033[0;35m'
    CYAN = '\033[0;36m'
    WHITE = '\033[1;37m'
    NC = '\033[0m'  # No Color
    BOLD = '\033[1m'


def status_color(status: Status) -> str:
    if status == Status.OK:
        return Colors.GREEN
    elif status == Status.WARNING:
        return Colors.YELLOW
    elif status == Status.CRITICAL:
        return Colors.RED
    return Colors.WHITE


def status_icon(status: Status) -> str:
    if status == Status.OK:
        return "✓"
    elif status == Status.WARNING:
        return "⚠"
    elif status == Status.CRITICAL:
        return "✗"
    return "?"


def print_header(title: str):
    print()
    print(f"{Colors.BLUE}{'═' * 70}{Colors.NC}")
    print(f"{Colors.BLUE}  {title}{Colors.NC}")
    print(f"{Colors.BLUE}{'═' * 70}{Colors.NC}")


def print_subheader(title: str):
    print(f"\n{Colors.CYAN}── {title} ──{Colors.NC}")


def print_check(result: CheckResult):
    color = status_color(result.status)
    icon = status_icon(result.status)
    duration = f" ({result.duration_ms:.0f}ms)" if result.duration_ms else ""
    print(f"  {color}{icon}{Colors.NC} {result.name}: {result.message}{duration}")


# ═══════════════════════════════════════════════════════════════
# CHECK FUNCTIES
# ═══════════════════════════════════════════════════════════════

def timed_check(func):
    """Decorator om check duur te meten"""
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        duration = (time.time() - start) * 1000
        if isinstance(result, CheckResult):
            result.duration_ms = duration
        return result
    return wrapper


@timed_check
def check_ping(host: str, ip: str) -> CheckResult:
    """Ping een host en meet latency"""
    try:
        result = subprocess.run(
            ['ping', '-c', '3', '-W', '2', ip],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            # Parse latency
            for line in result.stdout.split('\n'):
                if 'min/avg/max' in line or 'rtt min/avg/max' in line:
                    parts = line.split('=')[1].strip().split('/')
                    avg_latency = float(parts[1])

                    if avg_latency > THRESHOLDS['latency_critical']:
                        return CheckResult(
                            name=host,
                            status=Status.CRITICAL,
                            message=f"Hoge latency: {avg_latency:.1f}ms",
                            details={'latency_ms': avg_latency, 'ip': ip}
                        )
                    elif avg_latency > THRESHOLDS['latency_warning']:
                        return CheckResult(
                            name=host,
                            status=Status.WARNING,
                            message=f"Latency: {avg_latency:.1f}ms",
                            details={'latency_ms': avg_latency, 'ip': ip}
                        )
                    else:
                        return CheckResult(
                            name=host,
                            status=Status.OK,
                            message=f"OK ({avg_latency:.1f}ms)",
                            details={'latency_ms': avg_latency, 'ip': ip}
                        )

            return CheckResult(
                name=host,
                status=Status.OK,
                message="Bereikbaar",
                details={'ip': ip}
            )
        else:
            return CheckResult(
                name=host,
                status=Status.CRITICAL,
                message="NIET bereikbaar",
                details={'ip': ip}
            )
    except subprocess.TimeoutExpired:
        return CheckResult(
            name=host,
            status=Status.CRITICAL,
            message="Timeout",
            details={'ip': ip}
        )
    except Exception as e:
        return CheckResult(
            name=host,
            status=Status.UNKNOWN,
            message=f"Fout: {e}",
            details={'ip': ip}
        )


def check_ssh_available(host: str, ip: str) -> bool:
    """Check of SSH beschikbaar is"""
    try:
        result = subprocess.run(
            ['ssh', '-o', 'ConnectTimeout=3', '-o', 'BatchMode=yes',
             f'ronny@{ip}', 'echo ok'],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except:
        return False


@timed_check
def check_ssh_service(host: str, ip: str, service: str) -> CheckResult:
    """Check systemd service status via SSH"""
    try:
        result = subprocess.run(
            ['ssh', '-o', 'ConnectTimeout=3', '-o', 'BatchMode=yes',
             f'ronny@{ip}', f'systemctl is-active {service}'],
            capture_output=True,
            text=True,
            timeout=10
        )
        status_text = result.stdout.strip()

        if status_text == 'active':
            return CheckResult(
                name=service,
                status=Status.OK,
                message="actief"
            )
        elif status_text == 'inactive':
            return CheckResult(
                name=service,
                status=Status.WARNING,
                message="inactief"
            )
        else:
            return CheckResult(
                name=service,
                status=Status.CRITICAL,
                message=status_text or "gefaald"
            )
    except subprocess.TimeoutExpired:
        return CheckResult(
            name=service,
            status=Status.UNKNOWN,
            message="timeout"
        )
    except Exception as e:
        return CheckResult(
            name=service,
            status=Status.UNKNOWN,
            message=f"fout: {e}"
        )


@timed_check
def check_ssh_hardware(host: str, ip: str) -> List[CheckResult]:
    """Check hardware metrics via SSH"""
    results = []

    try:
        # Verzamel alle metrics in één SSH call
        commands = """
        echo "CPU_TEMP:$(vcgencmd measure_temp 2>/dev/null | sed 's/temp=//' | sed \"s/'C//\")"
        echo "CPU_USAGE:$(top -bn1 | grep 'Cpu(s)' | awk '{print $2}')"
        echo "MEM_USAGE:$(free | grep Mem | awk '{print int($3/$2 * 100)}')"
        echo "SWAP_USAGE:$(free | grep Swap | awk '{if($2>0) print int($3/$2 * 100); else print 0}')"
        echo "DISK_ROOT:$(df / | tail -1 | awk '{print $5}' | sed 's/%//')"
        echo "DISK_USB:$(df /mnt/usb 2>/dev/null | tail -1 | awk '{print $5}' | sed 's/%//' || echo 'N/A')"
        echo "UPTIME:$(uptime -p)"
        echo "THROTTLED:$(vcgencmd get_throttled 2>/dev/null | sed 's/throttled=//')"
        """

        result = subprocess.run(
            ['ssh', '-o', 'ConnectTimeout=5', '-o', 'BatchMode=yes',
             f'ronny@{ip}', commands],
            capture_output=True,
            text=True,
            timeout=15
        )

        if result.returncode != 0:
            return [CheckResult(
                name=f"{host} Hardware",
                status=Status.UNKNOWN,
                message="SSH niet beschikbaar"
            )]

        # Parse output
        metrics = {}
        for line in result.stdout.strip().split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                metrics[key] = value.strip()

        # CPU Temperature
        if 'CPU_TEMP' in metrics and metrics['CPU_TEMP']:
            try:
                temp = float(metrics['CPU_TEMP'])
                if temp >= THRESHOLDS['cpu_temp_critical']:
                    results.append(CheckResult(
                        name=f"{host} CPU Temp",
                        status=Status.CRITICAL,
                        message=f"{temp:.1f}°C (KRITIEK!)",
                        details={'temperature': temp}
                    ))
                elif temp >= THRESHOLDS['cpu_temp_warning']:
                    results.append(CheckResult(
                        name=f"{host} CPU Temp",
                        status=Status.WARNING,
                        message=f"{temp:.1f}°C",
                        details={'temperature': temp}
                    ))
                else:
                    results.append(CheckResult(
                        name=f"{host} CPU Temp",
                        status=Status.OK,
                        message=f"{temp:.1f}°C",
                        details={'temperature': temp}
                    ))
            except ValueError:
                pass

        # Memory Usage
        if 'MEM_USAGE' in metrics and metrics['MEM_USAGE']:
            try:
                mem = int(metrics['MEM_USAGE'])
                if mem >= THRESHOLDS['memory_critical']:
                    results.append(CheckResult(
                        name=f"{host} Memory",
                        status=Status.CRITICAL,
                        message=f"{mem}% (KRITIEK!)",
                        details={'percent': mem}
                    ))
                elif mem >= THRESHOLDS['memory_warning']:
                    results.append(CheckResult(
                        name=f"{host} Memory",
                        status=Status.WARNING,
                        message=f"{mem}%",
                        details={'percent': mem}
                    ))
                else:
                    results.append(CheckResult(
                        name=f"{host} Memory",
                        status=Status.OK,
                        message=f"{mem}%",
                        details={'percent': mem}
                    ))
            except ValueError:
                pass

        # Disk Usage Root
        if 'DISK_ROOT' in metrics and metrics['DISK_ROOT']:
            try:
                disk = int(metrics['DISK_ROOT'])
                if disk >= THRESHOLDS['disk_critical']:
                    results.append(CheckResult(
                        name=f"{host} Disk /",
                        status=Status.CRITICAL,
                        message=f"{disk}% (KRITIEK!)",
                        details={'percent': disk}
                    ))
                elif disk >= THRESHOLDS['disk_warning']:
                    results.append(CheckResult(
                        name=f"{host} Disk /",
                        status=Status.WARNING,
                        message=f"{disk}%",
                        details={'percent': disk}
                    ))
                else:
                    results.append(CheckResult(
                        name=f"{host} Disk /",
                        status=Status.OK,
                        message=f"{disk}%",
                        details={'percent': disk}
                    ))
            except ValueError:
                pass

        # Disk Usage USB
        if 'DISK_USB' in metrics and metrics['DISK_USB'] != 'N/A':
            try:
                disk = int(metrics['DISK_USB'])
                if disk >= THRESHOLDS['disk_critical']:
                    results.append(CheckResult(
                        name=f"{host} Disk USB",
                        status=Status.CRITICAL,
                        message=f"{disk}% (KRITIEK!)",
                        details={'percent': disk}
                    ))
                elif disk >= THRESHOLDS['disk_warning']:
                    results.append(CheckResult(
                        name=f"{host} Disk USB",
                        status=Status.WARNING,
                        message=f"{disk}%",
                        details={'percent': disk}
                    ))
                else:
                    results.append(CheckResult(
                        name=f"{host} Disk USB",
                        status=Status.OK,
                        message=f"{disk}%",
                        details={'percent': disk}
                    ))
            except ValueError:
                pass

        # Throttling
        if 'THROTTLED' in metrics and metrics['THROTTLED']:
            throttled = int(metrics['THROTTLED'], 16) if metrics['THROTTLED'].startswith('0x') else 0
            if throttled & 0x4:  # Currently throttled
                results.append(CheckResult(
                    name=f"{host} Throttling",
                    status=Status.CRITICAL,
                    message="ACTIEF THROTTLED!",
                    details={'value': hex(throttled)}
                ))
            elif throttled & 0x1:  # Under-voltage
                results.append(CheckResult(
                    name=f"{host} Throttling",
                    status=Status.WARNING,
                    message="Under-voltage gedetecteerd",
                    details={'value': hex(throttled)}
                ))
            elif throttled > 0:
                results.append(CheckResult(
                    name=f"{host} Throttling",
                    status=Status.WARNING,
                    message=f"Historisch: {hex(throttled)}",
                    details={'value': hex(throttled)}
                ))
            else:
                results.append(CheckResult(
                    name=f"{host} Throttling",
                    status=Status.OK,
                    message="Geen throttling",
                    details={'value': hex(throttled)}
                ))

        # Uptime
        if 'UPTIME' in metrics:
            results.append(CheckResult(
                name=f"{host} Uptime",
                status=Status.OK,
                message=metrics['UPTIME'],
                details={'uptime': metrics['UPTIME']}
            ))

        return results

    except Exception as e:
        return [CheckResult(
            name=f"{host} Hardware",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        )]


@timed_check
def check_api_endpoint(name: str, url: str) -> CheckResult:
    """Check of een API endpoint bereikbaar is"""
    try:
        import urllib.request
        import urllib.error

        start = time.time()
        req = urllib.request.Request(url, method='GET')
        req.add_header('User-Agent', 'EMSN-Deep-Health-Check/1.0')

        with urllib.request.urlopen(req, timeout=10) as response:
            elapsed = (time.time() - start) * 1000
            return CheckResult(
                name=name,
                status=Status.OK,
                message=f"OK ({elapsed:.0f}ms)",
                details={'status_code': response.status, 'response_time_ms': elapsed}
            )

    except urllib.error.HTTPError as e:
        if e.code in [401, 403]:
            return CheckResult(
                name=name,
                status=Status.OK,
                message=f"OK (auth required: {e.code})",
                details={'status_code': e.code}
            )
        return CheckResult(
            name=name,
            status=Status.WARNING,
            message=f"HTTP {e.code}",
            details={'status_code': e.code}
        )
    except urllib.error.URLError as e:
        return CheckResult(
            name=name,
            status=Status.CRITICAL,
            message=f"Niet bereikbaar: {e.reason}",
            details={'error': str(e.reason)}
        )
    except Exception as e:
        return CheckResult(
            name=name,
            status=Status.CRITICAL,
            message=f"Fout: {e}",
            details={'error': str(e)}
        )


@timed_check
def check_nas_mount(path: str, name: str) -> CheckResult:
    """Check of een NAS mount beschikbaar is"""
    try:
        if os.path.ismount(path):
            # Check disk usage
            import shutil
            total, used, free = shutil.disk_usage(path)
            percent = (used / total) * 100

            if percent >= THRESHOLDS['disk_critical']:
                return CheckResult(
                    name=name,
                    status=Status.CRITICAL,
                    message=f"Gemount maar {percent:.0f}% vol!",
                    details={'path': path, 'percent': percent, 'free_gb': free // (1024**3)}
                )
            elif percent >= THRESHOLDS['disk_warning']:
                return CheckResult(
                    name=name,
                    status=Status.WARNING,
                    message=f"Gemount, {percent:.0f}% gebruikt",
                    details={'path': path, 'percent': percent, 'free_gb': free // (1024**3)}
                )
            else:
                return CheckResult(
                    name=name,
                    status=Status.OK,
                    message=f"OK ({free // (1024**3)}GB vrij)",
                    details={'path': path, 'percent': percent, 'free_gb': free // (1024**3)}
                )
        else:
            return CheckResult(
                name=name,
                status=Status.CRITICAL,
                message="NIET gemount!",
                details={'path': path}
            )
    except Exception as e:
        return CheckResult(
            name=name,
            status=Status.CRITICAL,
            message=f"Fout: {e}",
            details={'path': path, 'error': str(e)}
        )


@timed_check
def check_mqtt_broker() -> CheckResult:
    """Check MQTT broker connectiviteit"""
    try:
        result = subprocess.run(
            ['mosquitto_sub', '-h', '192.168.1.178', '-t', '$SYS/broker/uptime',
             '-C', '1', '-W', '5'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            uptime = result.stdout.strip()
            return CheckResult(
                name="MQTT Broker",
                status=Status.OK,
                message=f"Actief (uptime: {uptime}s)",
                details={'uptime': uptime}
            )
        else:
            return CheckResult(
                name="MQTT Broker",
                status=Status.CRITICAL,
                message="Niet bereikbaar",
                details={'error': result.stderr}
            )
    except subprocess.TimeoutExpired:
        return CheckResult(
            name="MQTT Broker",
            status=Status.CRITICAL,
            message="Timeout"
        )
    except FileNotFoundError:
        return CheckResult(
            name="MQTT Broker",
            status=Status.UNKNOWN,
            message="mosquitto_sub niet geïnstalleerd"
        )
    except Exception as e:
        return CheckResult(
            name="MQTT Broker",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        )


@timed_check
def check_postgresql() -> CheckResult:
    """Check PostgreSQL database connectiviteit en performance"""
    try:
        # Lees credentials uit .secrets
        secrets_file = Path("/home/ronny/emsn2/.secrets")
        if not secrets_file.exists():
            return CheckResult(
                name="PostgreSQL",
                status=Status.UNKNOWN,
                message=".secrets niet gevonden"
            )

        pg_pass = None
        with open(secrets_file) as f:
            for line in f:
                if line.startswith('PG_PASSWORD='):
                    pg_pass = line.split('=', 1)[1].strip()
                    break

        if not pg_pass:
            return CheckResult(
                name="PostgreSQL",
                status=Status.UNKNOWN,
                message="PG_PASSWORD niet in .secrets"
            )

        # Test connectie en query
        import psycopg2

        start = time.time()
        conn = psycopg2.connect(
            host='192.168.1.25',
            port=5433,
            database='emsn',
            user='emsn',
            password=pg_pass,
            connect_timeout=5
        )

        cursor = conn.cursor()

        # Query performance test
        cursor.execute("SELECT COUNT(*) FROM lifetime_detections")
        count = cursor.fetchone()[0]

        cursor.execute("""
            SELECT MAX(detected_at)
            FROM lifetime_detections
            WHERE deleted = false
        """)
        last_detection = cursor.fetchone()[0]

        elapsed = (time.time() - start) * 1000
        conn.close()

        details = {
            'total_detections': count,
            'last_detection': str(last_detection) if last_detection else None,
            'query_time_ms': elapsed
        }

        if elapsed > 1000:
            return CheckResult(
                name="PostgreSQL",
                status=Status.WARNING,
                message=f"Traag ({elapsed:.0f}ms, {count} detecties)",
                details=details
            )
        else:
            return CheckResult(
                name="PostgreSQL",
                status=Status.OK,
                message=f"OK ({elapsed:.0f}ms, {count} detecties)",
                details=details
            )

    except ImportError:
        return CheckResult(
            name="PostgreSQL",
            status=Status.UNKNOWN,
            message="psycopg2 niet geïnstalleerd"
        )
    except Exception as e:
        return CheckResult(
            name="PostgreSQL",
            status=Status.CRITICAL,
            message=f"Fout: {e}"
        )


@timed_check
def check_detection_activity() -> List[CheckResult]:
    """Check recente detectie activiteit per station"""
    results = []

    try:
        secrets_file = Path("/home/ronny/emsn2/.secrets")
        pg_pass = None
        with open(secrets_file) as f:
            for line in f:
                if line.startswith('PG_PASSWORD='):
                    pg_pass = line.split('=', 1)[1].strip()
                    break

        if not pg_pass:
            return [CheckResult(
                name="Detectie Activiteit",
                status=Status.UNKNOWN,
                message="Credentials niet beschikbaar"
            )]

        import psycopg2

        conn = psycopg2.connect(
            host='192.168.1.25',
            port=5433,
            database='emsn',
            user='emsn',
            password=pg_pass,
            connect_timeout=5
        )
        cursor = conn.cursor()

        # Laatste detectie per station
        cursor.execute("""
            SELECT
                station,
                MAX(detected_at) as last_detection,
                EXTRACT(EPOCH FROM (NOW() - MAX(detected_at)))/3600 as hours_since,
                COUNT(*) FILTER (WHERE detected_at >= NOW() - INTERVAL '24 hours') as last_24h
            FROM lifetime_detections
            WHERE deleted = false
            GROUP BY station
        """)

        for row in cursor.fetchall():
            station, last_det, hours_since, count_24h = row

            if hours_since and hours_since >= THRESHOLDS['detection_gap_critical']:
                results.append(CheckResult(
                    name=f"Detecties {station}",
                    status=Status.CRITICAL,
                    message=f"Geen detecties voor {hours_since:.1f} uur!",
                    details={'hours_since': hours_since, 'last_24h': count_24h}
                ))
            elif hours_since and hours_since >= THRESHOLDS['detection_gap_warning']:
                results.append(CheckResult(
                    name=f"Detecties {station}",
                    status=Status.WARNING,
                    message=f"Gap: {hours_since:.1f} uur, {count_24h} laatste 24u",
                    details={'hours_since': hours_since, 'last_24h': count_24h}
                ))
            else:
                results.append(CheckResult(
                    name=f"Detecties {station}",
                    status=Status.OK,
                    message=f"{count_24h} laatste 24u",
                    details={'hours_since': hours_since, 'last_24h': count_24h}
                ))

        conn.close()
        return results

    except Exception as e:
        return [CheckResult(
            name="Detectie Activiteit",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        )]


@timed_check
def check_go2rtc_streams() -> List[CheckResult]:
    """Check go2rtc nestkast camera streams"""
    results = []

    try:
        import urllib.request
        import json as json_module

        req = urllib.request.Request('http://192.168.1.25:1984/api/streams')
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json_module.loads(response.read().decode())

            streams = ['nestkast_voor', 'nestkast_midden', 'nestkast_achter']
            for stream in streams:
                if stream in data:
                    stream_info = data[stream]
                    producers = stream_info.get('producers', [])
                    has_active = any('id' in p for p in producers)

                    if has_active:
                        results.append(CheckResult(
                            name=f"Camera {stream.split('_')[1]}",
                            status=Status.OK,
                            message="Stream actief"
                        ))
                    else:
                        results.append(CheckResult(
                            name=f"Camera {stream.split('_')[1]}",
                            status=Status.WARNING,
                            message="Geen actieve producer"
                        ))
                else:
                    results.append(CheckResult(
                        name=f"Camera {stream.split('_')[1]}",
                        status=Status.CRITICAL,
                        message="Stream niet gevonden"
                    ))

        return results

    except Exception as e:
        return [CheckResult(
            name="go2rtc Cameras",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        )]


def check_recent_logs(host: str, ip: str) -> List[CheckResult]:
    """Check recente error logs via SSH"""
    results = []

    try:
        # Check journalctl voor recente errors
        result = subprocess.run(
            ['ssh', '-o', 'ConnectTimeout=3', '-o', 'BatchMode=yes',
             f'ronny@{ip}',
             'journalctl --priority=err --since="1 hour ago" --no-pager -q | wc -l'],
            capture_output=True,
            text=True,
            timeout=15
        )

        if result.returncode == 0:
            error_count = int(result.stdout.strip())
            if error_count > 50:
                results.append(CheckResult(
                    name=f"{host} Errors (1u)",
                    status=Status.CRITICAL,
                    message=f"{error_count} errors!",
                    details={'error_count': error_count}
                ))
            elif error_count > 10:
                results.append(CheckResult(
                    name=f"{host} Errors (1u)",
                    status=Status.WARNING,
                    message=f"{error_count} errors",
                    details={'error_count': error_count}
                ))
            else:
                results.append(CheckResult(
                    name=f"{host} Errors (1u)",
                    status=Status.OK,
                    message=f"{error_count} errors",
                    details={'error_count': error_count}
                ))

    except Exception as e:
        results.append(CheckResult(
            name=f"{host} Logs",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        ))

    return results


@timed_check
def check_atmosbird_captures() -> List[CheckResult]:
    """Check AtmosBird captures - lokaal en NAS archief"""
    results = []
    berging_ip = HOSTS['berging']['ip']

    try:
        # Check lokale USB captures op berging
        result = subprocess.run(
            ['ssh', '-o', 'ConnectTimeout=5', '-o', 'BatchMode=yes',
             f'ronny@{berging_ip}',
             '''
             echo "LOCAL_COUNT:$(ls /mnt/usb/atmosbird/captures/ 2>/dev/null | wc -l)"
             echo "LOCAL_TODAY:$(ls /mnt/usb/atmosbird/captures/ 2>/dev/null | grep "$(date +%Y%m%d)" | wc -l)"
             echo "LOCAL_LATEST:$(ls -t /mnt/usb/atmosbird/captures/ 2>/dev/null | head -1)"
             echo "LOCAL_SPACE:$(df /mnt/usb 2>/dev/null | tail -1 | awk '{print $5}' | sed 's/%//')"
             '''],
            capture_output=True,
            text=True,
            timeout=15
        )

        if result.returncode == 0:
            metrics = {}
            for line in result.stdout.strip().split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    metrics[key] = value.strip()

            # Lokale captures
            local_count = int(metrics.get('LOCAL_COUNT', 0))
            local_today = int(metrics.get('LOCAL_TODAY', 0))
            local_latest = metrics.get('LOCAL_LATEST', '')

            if local_today == 0:
                results.append(CheckResult(
                    name="AtmosBird Lokaal",
                    status=Status.WARNING,
                    message=f"Geen captures vandaag! ({local_count} totaal)",
                    details={'total': local_count, 'today': local_today, 'latest': local_latest}
                ))
            elif local_today < 50:  # Verwacht ~144 per dag (elke 10 min)
                results.append(CheckResult(
                    name="AtmosBird Lokaal",
                    status=Status.WARNING,
                    message=f"Weinig captures: {local_today} vandaag",
                    details={'total': local_count, 'today': local_today, 'latest': local_latest}
                ))
            else:
                results.append(CheckResult(
                    name="AtmosBird Lokaal",
                    status=Status.OK,
                    message=f"{local_today} vandaag, {local_count} totaal",
                    details={'total': local_count, 'today': local_today, 'latest': local_latest}
                ))

            # USB disk space
            local_space = int(metrics.get('LOCAL_SPACE', 0))
            if local_space >= 90:
                results.append(CheckResult(
                    name="AtmosBird USB",
                    status=Status.CRITICAL,
                    message=f"USB {local_space}% vol!",
                    details={'percent': local_space}
                ))
            elif local_space >= 80:
                results.append(CheckResult(
                    name="AtmosBird USB",
                    status=Status.WARNING,
                    message=f"USB {local_space}% vol",
                    details={'percent': local_space}
                ))
        else:
            results.append(CheckResult(
                name="AtmosBird Lokaal",
                status=Status.UNKNOWN,
                message="SSH niet beschikbaar"
            ))

    except Exception as e:
        results.append(CheckResult(
            name="AtmosBird Lokaal",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        ))

    # Check NAS archief
    try:
        nas_path = Path('/mnt/nas-birdnet-archive/atmosbird/captures')
        if nas_path.exists():
            today = datetime.now().strftime('%Y%m%d')
            all_files = list(nas_path.glob('*.jpg'))
            today_files = [f for f in all_files if today in f.name]

            if len(today_files) == 0 and datetime.now().hour > 1:
                results.append(CheckResult(
                    name="AtmosBird NAS",
                    status=Status.WARNING,
                    message=f"Geen captures vandaag op NAS ({len(all_files)} totaal)",
                    details={'total': len(all_files), 'today': len(today_files)}
                ))
            else:
                results.append(CheckResult(
                    name="AtmosBird NAS",
                    status=Status.OK,
                    message=f"{len(today_files)} vandaag, {len(all_files)} totaal",
                    details={'total': len(all_files), 'today': len(today_files)}
                ))
        else:
            results.append(CheckResult(
                name="AtmosBird NAS",
                status=Status.CRITICAL,
                message="NAS archief niet bereikbaar",
                details={'path': str(nas_path)}
            ))
    except Exception as e:
        results.append(CheckResult(
            name="AtmosBird NAS",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        ))

    return results


@timed_check
def check_atmosbird_camera() -> CheckResult:
    """Check AtmosBird Pi Camera status"""
    berging_ip = HOSTS['berging']['ip']

    try:
        result = subprocess.run(
            ['ssh', '-o', 'ConnectTimeout=5', '-o', 'BatchMode=yes',
             f'ronny@{berging_ip}',
             'libcamera-hello --list-cameras 2>&1 | head -5'],
            capture_output=True,
            text=True,
            timeout=15
        )

        if result.returncode == 0:
            output = result.stdout.lower()
            if 'imx708' in output or 'available cameras' in output:
                return CheckResult(
                    name="AtmosBird Camera",
                    status=Status.OK,
                    message="Pi Camera NoIR gedetecteerd",
                    details={'output': result.stdout.strip()[:100]}
                )
            elif 'no cameras' in output:
                return CheckResult(
                    name="AtmosBird Camera",
                    status=Status.CRITICAL,
                    message="Geen camera gevonden!",
                    details={'output': result.stdout.strip()}
                )
        return CheckResult(
            name="AtmosBird Camera",
            status=Status.WARNING,
            message="Camera status onbekend",
            details={'output': result.stdout.strip()[:100] if result.stdout else result.stderr[:100]}
        )
    except Exception as e:
        return CheckResult(
            name="AtmosBird Camera",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        )


@timed_check
def check_atmosbird_data() -> List[CheckResult]:
    """Check AtmosBird database data (sky_observations)"""
    results = []

    try:
        secrets_file = Path("/home/ronny/emsn2/.secrets")
        pg_pass = None
        with open(secrets_file) as f:
            for line in f:
                if line.startswith('PG_PASSWORD='):
                    pg_pass = line.split('=', 1)[1].strip()
                    break

        if not pg_pass:
            return [CheckResult(
                name="AtmosBird Data",
                status=Status.UNKNOWN,
                message="Credentials niet beschikbaar"
            )]

        import psycopg2

        conn = psycopg2.connect(
            host='192.168.1.25',
            port=5433,
            database='emsn',
            user='emsn',
            password=pg_pass,
            connect_timeout=5
        )
        cursor = conn.cursor()

        # Sky observations
        cursor.execute("""
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE captured_at >= NOW() - INTERVAL '24 hours') as last_24h,
                MAX(captured_at) as last_capture,
                EXTRACT(EPOCH FROM (NOW() - MAX(captured_at)))/60 as minutes_since,
                AVG(brightness) FILTER (WHERE captured_at >= NOW() - INTERVAL '24 hours') as avg_brightness,
                AVG(cloud_coverage) FILTER (WHERE captured_at >= NOW() - INTERVAL '24 hours') as avg_clouds
            FROM sky_observations
        """)
        row = cursor.fetchone()

        if row:
            total, last_24h, last_capture, minutes_since, avg_brightness, avg_clouds = row

            if minutes_since and minutes_since > 30:  # Meer dan 30 min geen data
                results.append(CheckResult(
                    name="Sky Observations",
                    status=Status.WARNING,
                    message=f"Laatste {minutes_since:.0f} min geleden, {last_24h} laatste 24u",
                    details={'total': total, 'last_24h': last_24h, 'minutes_since': minutes_since}
                ))
            else:
                results.append(CheckResult(
                    name="Sky Observations",
                    status=Status.OK,
                    message=f"{last_24h} laatste 24u, brightness={avg_brightness:.1f}" if avg_brightness else f"{last_24h} laatste 24u",
                    details={'total': total, 'last_24h': last_24h, 'avg_brightness': avg_brightness, 'avg_clouds': avg_clouds}
                ))

        # ISS passes
        cursor.execute("""
            SELECT COUNT(*) FROM iss_passes WHERE pass_time >= NOW()
        """)
        upcoming_iss = cursor.fetchone()[0]
        results.append(CheckResult(
            name="ISS Passes",
            status=Status.OK,
            message=f"{upcoming_iss} aankomende passes",
            details={'upcoming': upcoming_iss}
        ))

        # Timelapses
        cursor.execute("""
            SELECT
                COUNT(*) as total,
                MAX(created_at) as last_timelapse
            FROM timelapses
            WHERE created_at >= NOW() - INTERVAL '7 days'
        """)
        row = cursor.fetchone()
        if row and row[0]:
            results.append(CheckResult(
                name="Timelapses",
                status=Status.OK,
                message=f"{row[0]} laatste week",
                details={'last_week': row[0]}
            ))

        conn.close()
        return results

    except Exception as e:
        return [CheckResult(
            name="AtmosBird Data",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        )]


@timed_check
def check_meteo_data() -> List[CheckResult]:
    """Check weerstation data"""
    results = []

    try:
        secrets_file = Path("/home/ronny/emsn2/.secrets")
        pg_pass = None
        with open(secrets_file) as f:
            for line in f:
                if line.startswith('PG_PASSWORD='):
                    pg_pass = line.split('=', 1)[1].strip()
                    break

        if not pg_pass:
            return [CheckResult(
                name="Meteo Data",
                status=Status.UNKNOWN,
                message="Credentials niet beschikbaar"
            )]

        import psycopg2

        conn = psycopg2.connect(
            host='192.168.1.25',
            port=5433,
            database='emsn',
            user='emsn',
            password=pg_pass,
            connect_timeout=5
        )
        cursor = conn.cursor()

        # Weather data
        cursor.execute("""
            SELECT
                COUNT(*) FILTER (WHERE measurement_timestamp >= NOW() - INTERVAL '24 hours') as last_24h,
                MAX(measurement_timestamp) as last_measurement,
                EXTRACT(EPOCH FROM (NOW() - MAX(measurement_timestamp)))/60 as minutes_since
            FROM weather_data
        """)
        row = cursor.fetchone()

        if row:
            last_24h, last_measurement, minutes_since = row

            if minutes_since and minutes_since > 30:
                results.append(CheckResult(
                    name="Weerdata",
                    status=Status.WARNING,
                    message=f"Laatste {minutes_since:.0f} min geleden",
                    details={'last_24h': last_24h, 'minutes_since': minutes_since}
                ))
            elif last_24h and last_24h > 0:
                results.append(CheckResult(
                    name="Weerdata",
                    status=Status.OK,
                    message=f"{last_24h} metingen laatste 24u",
                    details={'last_24h': last_24h, 'minutes_since': minutes_since}
                ))
            else:
                results.append(CheckResult(
                    name="Weerdata",
                    status=Status.WARNING,
                    message="Geen recente data",
                    details={'last_24h': last_24h}
                ))

        # Laatste temperatuur
        cursor.execute("""
            SELECT temp_outdoor, humidity_outdoor, barometer, wind_speed
            FROM weather_data
            ORDER BY measurement_timestamp DESC
            LIMIT 1
        """)
        row = cursor.fetchone()
        if row:
            temp, humidity, pressure, wind = row
            if temp is not None:
                results.append(CheckResult(
                    name="Huidige Meteo",
                    status=Status.OK,
                    message=f"{temp:.1f}°C, {humidity:.0f}% RH, {pressure:.0f}hPa" if humidity else f"{temp:.1f}°C",
                    details={'temp': temp, 'humidity': humidity, 'pressure': pressure, 'wind': wind}
                ))

        conn.close()
        return results

    except Exception as e:
        return [CheckResult(
            name="Meteo Data",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        )]


@timed_check
def check_sync_status() -> List[CheckResult]:
    """Check sync status tussen BirdNET-Pi SQLite en PostgreSQL"""
    results = []

    try:
        secrets_file = Path("/home/ronny/emsn2/.secrets")
        pg_pass = None
        with open(secrets_file) as f:
            for line in f:
                if line.startswith('PG_PASSWORD='):
                    pg_pass = line.split('=', 1)[1].strip()
                    break

        import psycopg2

        conn = psycopg2.connect(
            host='192.168.1.25',
            port=5433,
            database='emsn',
            user='emsn',
            password=pg_pass,
            connect_timeout=5
        )
        cursor = conn.cursor()

        # Laatste sync per station
        cursor.execute("""
            SELECT
                station,
                MAX(synced_at) as last_sync,
                EXTRACT(EPOCH FROM (NOW() - MAX(synced_at)))/3600 as hours_since
            FROM lifetime_detections
            GROUP BY station
        """)

        for row in cursor.fetchall():
            station, last_sync, hours_since = row

            if hours_since and hours_since > THRESHOLDS['sync_lag_critical']:
                results.append(CheckResult(
                    name=f"Sync {station}",
                    status=Status.CRITICAL,
                    message=f"Laatste sync {hours_since:.1f} uur geleden!",
                    details={'hours_since': hours_since}
                ))
            elif hours_since and hours_since > THRESHOLDS['sync_lag_warning']:
                results.append(CheckResult(
                    name=f"Sync {station}",
                    status=Status.WARNING,
                    message=f"Sync lag: {hours_since:.1f} uur",
                    details={'hours_since': hours_since}
                ))
            else:
                results.append(CheckResult(
                    name=f"Sync {station}",
                    status=Status.OK,
                    message=f"OK ({hours_since:.1f}u geleden)" if hours_since else "OK",
                    details={'hours_since': hours_since}
                ))

        conn.close()
        return results

    except Exception as e:
        return [CheckResult(
            name="Sync Status",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        )]


# ═══════════════════════════════════════════════════════════════
# 11. BIRDNET-Pi DATABASE INTEGRITEIT CHECKS
# ═══════════════════════════════════════════════════════════════

@timed_check
def check_sqlite_integrity(host: str, ip: str) -> List[CheckResult]:
    """Check BirdNET-Pi SQLite database integriteit"""
    results = []
    db_path = "/home/ronny/BirdNET-Pi/scripts/birds.db"

    try:
        # Integrity check
        result = subprocess.run(
            ['ssh', '-o', 'ConnectTimeout=5', '-o', 'BatchMode=yes',
             f'ronny@{ip}',
             f'''
             sqlite3 "{db_path}" "PRAGMA integrity_check;" 2>/dev/null | head -5
             '''],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            output = result.stdout.strip()
            if output == 'ok':
                results.append(CheckResult(
                    name=f"{host} SQLite Integrity",
                    status=Status.OK,
                    message="Database integer"
                ))
            else:
                results.append(CheckResult(
                    name=f"{host} SQLite Integrity",
                    status=Status.CRITICAL,
                    message=f"Corruptie gedetecteerd: {output[:50]}",
                    details={'output': output}
                ))
        else:
            results.append(CheckResult(
                name=f"{host} SQLite Integrity",
                status=Status.WARNING,
                message="Kan database niet controleren",
                details={'error': result.stderr}
            ))

        # Database grootte en laatste record
        result = subprocess.run(
            ['ssh', '-o', 'ConnectTimeout=5', '-o', 'BatchMode=yes',
             f'ronny@{ip}',
             f'''
             echo "SIZE:$(du -h "{db_path}" 2>/dev/null | cut -f1)"
             echo "RECORDS:$(sqlite3 "{db_path}" "SELECT COUNT(*) FROM detections;" 2>/dev/null)"
             echo "LAST:$(sqlite3 "{db_path}" "SELECT MAX(Date || ' ' || Time) FROM detections;" 2>/dev/null)"
             '''],
            capture_output=True,
            text=True,
            timeout=15
        )

        if result.returncode == 0:
            metrics = {}
            for line in result.stdout.strip().split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    metrics[key] = value.strip()

            db_size = metrics.get('SIZE', 'onbekend')
            records = metrics.get('RECORDS', '0')
            last_record = metrics.get('LAST', '')

            results.append(CheckResult(
                name=f"{host} SQLite Stats",
                status=Status.OK,
                message=f"{db_size}, {records} records",
                details={'size': db_size, 'records': records, 'last': last_record}
            ))

    except Exception as e:
        results.append(CheckResult(
            name=f"{host} SQLite",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        ))

    return results


@timed_check
def check_audio_recording(host: str, ip: str) -> CheckResult:
    """Check laatste audio opname (microfoon werkt?)"""
    try:
        result = subprocess.run(
            ['ssh', '-o', 'ConnectTimeout=5', '-o', 'BatchMode=yes',
             f'ronny@{ip}',
             '''
             AUDIO_DIR="/home/ronny/BirdNET-Pi/BirdSongs/Extracted/By_Date"
             TODAY=$(date +%Y-%m-%d)
             YESTERDAY=$(date -d yesterday +%Y-%m-%d)
             TODAY_COUNT=$(find "$AUDIO_DIR/$TODAY" -name "*.mp3" 2>/dev/null | wc -l)
             YESTERDAY_COUNT=$(find "$AUDIO_DIR/$YESTERDAY" -name "*.mp3" 2>/dev/null | wc -l)
             LATEST=$(find "$AUDIO_DIR" -name "*.mp3" -type f 2>/dev/null | xargs ls -t 2>/dev/null | head -1)
             echo "TODAY:$TODAY_COUNT"
             echo "YESTERDAY:$YESTERDAY_COUNT"
             echo "LATEST:$LATEST"
             '''],
            capture_output=True,
            text=True,
            timeout=20
        )

        if result.returncode == 0:
            metrics = {}
            for line in result.stdout.strip().split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    metrics[key] = value.strip()

            today_count = int(metrics.get('TODAY', 0))
            yesterday_count = int(metrics.get('YESTERDAY', 0))
            latest = metrics.get('LATEST', '')

            # Extraheer bestandsnaam
            latest_name = Path(latest).name if latest else 'geen'

            if today_count == 0 and datetime.now().hour > 6:
                return CheckResult(
                    name=f"{host} Audio",
                    status=Status.WARNING,
                    message=f"Geen audio vandaag! (gisteren: {yesterday_count})",
                    details={'today': today_count, 'yesterday': yesterday_count}
                )
            else:
                return CheckResult(
                    name=f"{host} Audio",
                    status=Status.OK,
                    message=f"{today_count} vandaag, {yesterday_count} gisteren",
                    details={'today': today_count, 'yesterday': yesterday_count, 'latest': latest_name}
                )

        return CheckResult(
            name=f"{host} Audio",
            status=Status.UNKNOWN,
            message="Kan audio niet controleren"
        )

    except Exception as e:
        return CheckResult(
            name=f"{host} Audio",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        )


# ═══════════════════════════════════════════════════════════════
# 12. MQTT BRIDGE STATUS CHECKS
# ═══════════════════════════════════════════════════════════════

@timed_check
def check_mqtt_bridge_status() -> List[CheckResult]:
    """Check MQTT bridge status tussen berging en zolder"""
    results = []

    try:
        # Check bridge monitor service
        result = subprocess.run(
            ['ssh', '-o', 'ConnectTimeout=5', '-o', 'BatchMode=yes',
             f'ronny@{HOSTS["zolder"]["ip"]}',
             'systemctl is-active mqtt-bridge-monitor'],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0 and result.stdout.strip() == 'active':
            results.append(CheckResult(
                name="Bridge Monitor",
                status=Status.OK,
                message="Service actief"
            ))
        else:
            results.append(CheckResult(
                name="Bridge Monitor",
                status=Status.WARNING,
                message=f"Service: {result.stdout.strip() or 'onbekend'}"
            ))

        # Check bridge status topic
        result = subprocess.run(
            ['mosquitto_sub', '-h', '192.168.1.178', '-t', 'emsn2/bridge/status',
             '-C', '1', '-W', '5'],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            try:
                bridge_data = json.loads(result.stdout.strip())
                status = bridge_data.get('status', 'unknown')
                last_check = bridge_data.get('last_check', '')

                if status == 'connected':
                    results.append(CheckResult(
                        name="Bridge Connectie",
                        status=Status.OK,
                        message="Berging ↔ Zolder verbonden",
                        details=bridge_data
                    ))
                else:
                    results.append(CheckResult(
                        name="Bridge Connectie",
                        status=Status.WARNING,
                        message=f"Status: {status}",
                        details=bridge_data
                    ))
            except json.JSONDecodeError:
                results.append(CheckResult(
                    name="Bridge Connectie",
                    status=Status.OK,
                    message=f"Actief: {result.stdout.strip()[:50]}"
                ))
        else:
            results.append(CheckResult(
                name="Bridge Connectie",
                status=Status.WARNING,
                message="Geen bridge status ontvangen"
            ))

        # Check message throughput op berging broker
        result = subprocess.run(
            ['mosquitto_sub', '-h', '192.168.1.87', '-t', '$SYS/broker/messages/received',
             '-C', '1', '-W', '5'],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            msg_count = result.stdout.strip()
            results.append(CheckResult(
                name="Berging Broker",
                status=Status.OK,
                message=f"Actief ({msg_count} msgs received)",
                details={'messages': msg_count}
            ))
        else:
            results.append(CheckResult(
                name="Berging Broker",
                status=Status.WARNING,
                message="Niet bereikbaar of traag"
            ))

    except FileNotFoundError:
        results.append(CheckResult(
            name="MQTT Bridge",
            status=Status.UNKNOWN,
            message="mosquitto_sub niet geïnstalleerd"
        ))
    except Exception as e:
        results.append(CheckResult(
            name="MQTT Bridge",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        ))

    return results


# ═══════════════════════════════════════════════════════════════
# 13. INTERNET & CONNECTIVITEIT CHECKS
# ═══════════════════════════════════════════════════════════════

@timed_check
def check_internet_connectivity() -> List[CheckResult]:
    """Check internet connectiviteit en DNS"""
    results = []

    # DNS resolution test
    try:
        start = time.time()
        socket.gethostbyname('google.com')
        elapsed = (time.time() - start) * 1000

        results.append(CheckResult(
            name="DNS Resolution",
            status=Status.OK,
            message=f"OK ({elapsed:.0f}ms)",
            details={'host': 'google.com', 'time_ms': elapsed}
        ))
    except socket.gaierror:
        results.append(CheckResult(
            name="DNS Resolution",
            status=Status.CRITICAL,
            message="DNS lookup mislukt!",
            details={'host': 'google.com'}
        ))
    except Exception as e:
        results.append(CheckResult(
            name="DNS Resolution",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        ))

    # Internet ping (8.8.8.8)
    try:
        result = subprocess.run(
            ['ping', '-c', '3', '-W', '3', '8.8.8.8'],
            capture_output=True,
            text=True,
            timeout=15
        )

        if result.returncode == 0:
            # Parse latency
            for line in result.stdout.split('\n'):
                if 'min/avg/max' in line or 'rtt min/avg/max' in line:
                    parts = line.split('=')[1].strip().split('/')
                    avg_latency = float(parts[1])

                    results.append(CheckResult(
                        name="Internet (8.8.8.8)",
                        status=Status.OK,
                        message=f"OK ({avg_latency:.1f}ms)",
                        details={'latency_ms': avg_latency}
                    ))
                    break
            else:
                results.append(CheckResult(
                    name="Internet (8.8.8.8)",
                    status=Status.OK,
                    message="Bereikbaar"
                ))
        else:
            results.append(CheckResult(
                name="Internet (8.8.8.8)",
                status=Status.CRITICAL,
                message="NIET bereikbaar!",
                details={'error': result.stderr}
            ))
    except subprocess.TimeoutExpired:
        results.append(CheckResult(
            name="Internet (8.8.8.8)",
            status=Status.CRITICAL,
            message="Timeout"
        ))
    except Exception as e:
        results.append(CheckResult(
            name="Internet (8.8.8.8)",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        ))

    # NAS mount response time
    for mount in NAS_MOUNTS[:1]:  # Test alleen eerste mount
        try:
            start = time.time()
            os.listdir(mount['path'])
            elapsed = (time.time() - start) * 1000

            if elapsed > 1000:
                results.append(CheckResult(
                    name="NAS Response",
                    status=Status.WARNING,
                    message=f"Traag: {elapsed:.0f}ms",
                    details={'path': mount['path'], 'time_ms': elapsed}
                ))
            else:
                results.append(CheckResult(
                    name="NAS Response",
                    status=Status.OK,
                    message=f"OK ({elapsed:.0f}ms)",
                    details={'path': mount['path'], 'time_ms': elapsed}
                ))
        except Exception as e:
            results.append(CheckResult(
                name="NAS Response",
                status=Status.CRITICAL,
                message=f"Fout: {e}"
            ))

    return results


# ═══════════════════════════════════════════════════════════════
# 14. SECURITY CHECKS
# ═══════════════════════════════════════════════════════════════

@timed_check
def check_security(host: str, ip: str) -> List[CheckResult]:
    """Check security-gerelateerde items via SSH"""
    results = []

    try:
        # Failed SSH login attempts (laatste 24u)
        result = subprocess.run(
            ['ssh', '-o', 'ConnectTimeout=5', '-o', 'BatchMode=yes',
             f'ronny@{ip}',
             '''
             FAILED=$(journalctl -u ssh --since "24 hours ago" 2>/dev/null | grep -c "Failed password" || echo 0)
             SUDO_COUNT=$(journalctl --since "24 hours ago" 2>/dev/null | grep -c "sudo:" || echo 0)
             echo "FAILED_SSH:$FAILED"
             echo "SUDO_COUNT:$SUDO_COUNT"
             '''],
            capture_output=True,
            text=True,
            timeout=20
        )

        if result.returncode == 0:
            metrics = {}
            for line in result.stdout.strip().split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    metrics[key] = value.strip()

            failed_ssh = int(metrics.get('FAILED_SSH', 0))
            sudo_count = int(metrics.get('SUDO_COUNT', 0))

            # Failed SSH logins
            if failed_ssh > 50:
                results.append(CheckResult(
                    name=f"{host} Failed SSH",
                    status=Status.CRITICAL,
                    message=f"{failed_ssh} mislukte pogingen (24u)!",
                    details={'count': failed_ssh}
                ))
            elif failed_ssh > 10:
                results.append(CheckResult(
                    name=f"{host} Failed SSH",
                    status=Status.WARNING,
                    message=f"{failed_ssh} mislukte pogingen (24u)",
                    details={'count': failed_ssh}
                ))
            else:
                results.append(CheckResult(
                    name=f"{host} Failed SSH",
                    status=Status.OK,
                    message=f"{failed_ssh} mislukte pogingen (24u)",
                    details={'count': failed_ssh}
                ))

            # Sudo usage
            results.append(CheckResult(
                name=f"{host} Sudo",
                status=Status.OK,
                message=f"{sudo_count} sudo acties (24u)",
                details={'count': sudo_count}
            ))

    except Exception as e:
        results.append(CheckResult(
            name=f"{host} Security",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        ))

    return results


# ═══════════════════════════════════════════════════════════════
# 15. BACKUP & TRENDS CHECKS
# ═══════════════════════════════════════════════════════════════

@timed_check
def check_backup_status() -> List[CheckResult]:
    """Check PostgreSQL backup status"""
    results = []

    backup_paths = [
        '/mnt/nas-birdnet-archive/backups/postgresql',
        '/mnt/nas-docker/backups',
    ]

    for backup_path in backup_paths:
        try:
            path = Path(backup_path)
            if path.exists():
                # Zoek laatste backup
                backups = list(path.glob('*.sql*')) + list(path.glob('*.dump'))
                if backups:
                    latest = max(backups, key=lambda x: x.stat().st_mtime)
                    age_hours = (time.time() - latest.stat().st_mtime) / 3600
                    size_mb = latest.stat().st_size / (1024 * 1024)

                    if age_hours > 168:  # 7 dagen
                        results.append(CheckResult(
                            name=f"Backup {path.name}",
                            status=Status.CRITICAL,
                            message=f"Laatste backup {age_hours/24:.0f} dagen oud!",
                            details={'file': latest.name, 'age_hours': age_hours, 'size_mb': size_mb}
                        ))
                    elif age_hours > 48:
                        results.append(CheckResult(
                            name=f"Backup {path.name}",
                            status=Status.WARNING,
                            message=f"Backup {age_hours:.0f}u oud, {size_mb:.1f}MB",
                            details={'file': latest.name, 'age_hours': age_hours, 'size_mb': size_mb}
                        ))
                    else:
                        results.append(CheckResult(
                            name=f"Backup {path.name}",
                            status=Status.OK,
                            message=f"OK ({age_hours:.0f}u oud, {size_mb:.1f}MB)",
                            details={'file': latest.name, 'age_hours': age_hours, 'size_mb': size_mb}
                        ))
                else:
                    results.append(CheckResult(
                        name=f"Backup {path.name}",
                        status=Status.WARNING,
                        message="Geen backups gevonden",
                        details={'path': str(path)}
                    ))
            else:
                # Pad bestaat niet, skip
                pass
        except Exception as e:
            results.append(CheckResult(
                name=f"Backup {Path(backup_path).name}",
                status=Status.UNKNOWN,
                message=f"Fout: {e}"
            ))

    if not results:
        results.append(CheckResult(
            name="Backups",
            status=Status.WARNING,
            message="Geen backup locaties gevonden"
        ))

    return results


@timed_check
def check_detection_trends() -> List[CheckResult]:
    """Check detectie trends (vandaag vs gisteren vs vorige week)"""
    results = []

    try:
        secrets_file = Path("/home/ronny/emsn2/.secrets")
        pg_pass = None
        with open(secrets_file) as f:
            for line in f:
                if line.startswith('PG_PASSWORD='):
                    pg_pass = line.split('=', 1)[1].strip()
                    break

        if not pg_pass:
            return [CheckResult(
                name="Detectie Trends",
                status=Status.UNKNOWN,
                message="Credentials niet beschikbaar"
            )]

        import psycopg2

        conn = psycopg2.connect(
            host='192.168.1.25',
            port=5433,
            database='emsn',
            user='emsn',
            password=pg_pass,
            connect_timeout=5
        )
        cursor = conn.cursor()

        # Vergelijk vandaag, gisteren en vorige week
        cursor.execute("""
            SELECT
                COUNT(*) FILTER (WHERE detected_at::date = CURRENT_DATE) as today,
                COUNT(*) FILTER (WHERE detected_at::date = CURRENT_DATE - 1) as yesterday,
                COUNT(*) FILTER (WHERE detected_at::date = CURRENT_DATE - 7) as week_ago,
                AVG(CASE WHEN detected_at >= NOW() - INTERVAL '7 days'
                    THEN 1 ELSE NULL END) * COUNT(*) FILTER (
                        WHERE detected_at >= NOW() - INTERVAL '7 days'
                    ) / 7 as avg_per_day
            FROM lifetime_detections
            WHERE deleted = false
        """)

        row = cursor.fetchone()
        if row:
            today, yesterday, week_ago, avg_per_day = row
            avg_per_day = avg_per_day or 0

            # Bereken afwijking
            if yesterday and yesterday > 0:
                change_pct = ((today - yesterday) / yesterday) * 100
            else:
                change_pct = 0

            if today < (avg_per_day * 0.3) and datetime.now().hour > 12:
                results.append(CheckResult(
                    name="Detectie Trend",
                    status=Status.WARNING,
                    message=f"Vandaag ({today}) ver onder gemiddelde ({avg_per_day:.0f}/dag)",
                    details={'today': today, 'yesterday': yesterday, 'week_ago': week_ago, 'avg': avg_per_day}
                ))
            else:
                results.append(CheckResult(
                    name="Detectie Trend",
                    status=Status.OK,
                    message=f"Vandaag: {today}, gisteren: {yesterday}, gemiddeld: {avg_per_day:.0f}/dag",
                    details={'today': today, 'yesterday': yesterday, 'week_ago': week_ago, 'avg': avg_per_day, 'change_pct': change_pct}
                ))

        conn.close()
        return results

    except Exception as e:
        return [CheckResult(
            name="Detectie Trends",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        )]


@timed_check
def check_disk_growth() -> List[CheckResult]:
    """Voorspel wanneer disks vol raken"""
    results = []

    # Check NAS archief groei
    try:
        archive_path = Path('/mnt/nas-birdnet-archive')
        if archive_path.exists():
            import shutil
            total, used, free = shutil.disk_usage(archive_path)
            percent_used = (used / total) * 100
            free_gb = free / (1024**3)
            total_gb = total / (1024**3)

            # Schat dagelijkse groei (ongeveer 500MB/dag voor audio + 50MB captures)
            daily_growth_gb = 0.55
            days_until_full = free_gb / daily_growth_gb if daily_growth_gb > 0 else float('inf')

            if days_until_full < 30:
                results.append(CheckResult(
                    name="NAS Archief Voorspelling",
                    status=Status.WARNING,
                    message=f"Vol over ~{days_until_full:.0f} dagen ({free_gb:.0f}GB vrij)",
                    details={'free_gb': free_gb, 'total_gb': total_gb, 'days_until_full': days_until_full}
                ))
            else:
                results.append(CheckResult(
                    name="NAS Archief Voorspelling",
                    status=Status.OK,
                    message=f"{free_gb:.0f}GB vrij, ~{days_until_full/30:.0f} maanden ruimte",
                    details={'free_gb': free_gb, 'total_gb': total_gb, 'days_until_full': days_until_full}
                ))

    except Exception as e:
        results.append(CheckResult(
            name="Disk Groei Voorspelling",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        ))

    return results


@timed_check
def check_vocalization_models() -> CheckResult:
    """Check vocalization model beschikbaarheid"""
    try:
        models_path = Path('/mnt/nas-docker/emsn-vocalization/data/models')

        if models_path.exists():
            models = list(models_path.glob('*.pt'))
            ultimate_models = [m for m in models if 'ultimate' in m.name.lower()]

            if len(models) == 0:
                return CheckResult(
                    name="Vocalization Models",
                    status=Status.WARNING,
                    message="Geen modellen gevonden",
                    details={'path': str(models_path)}
                )
            else:
                return CheckResult(
                    name="Vocalization Models",
                    status=Status.OK,
                    message=f"{len(models)} modellen ({len(ultimate_models)} ultimate)",
                    details={'total': len(models), 'ultimate': len(ultimate_models)}
                )
        else:
            return CheckResult(
                name="Vocalization Models",
                status=Status.WARNING,
                message="Models directory niet bereikbaar",
                details={'path': str(models_path)}
            )

    except Exception as e:
        return CheckResult(
            name="Vocalization Models",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        )


@timed_check
def check_ulanzi_status() -> CheckResult:
    """Check Ulanzi display laatste activiteit"""
    try:
        import urllib.request
        import json as json_module

        req = urllib.request.Request('http://192.168.1.11/api/stats')
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json_module.loads(response.read().decode())

            uptime = data.get('uptime', 0)
            battery = data.get('bat', 0)
            brightness = data.get('bri', 0)
            ram_free = data.get('ram', 0)

            uptime_str = f"{uptime//3600}u{(uptime%3600)//60}m" if uptime else "onbekend"

            return CheckResult(
                name="Ulanzi Display",
                status=Status.OK,
                message=f"Online (uptime: {uptime_str}, brightness: {brightness}%)",
                details={'uptime': uptime, 'brightness': brightness, 'ram_free': ram_free}
            )

    except urllib.error.URLError:
        return CheckResult(
            name="Ulanzi Display",
            status=Status.WARNING,
            message="Niet bereikbaar"
        )
    except Exception as e:
        return CheckResult(
            name="Ulanzi Display",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        )


# ═══════════════════════════════════════════════════════════════
# MAIN DIAGNOSE FUNCTIE
# ═══════════════════════════════════════════════════════════════

def run_deep_health_check() -> Dict[str, CategoryResult]:
    """Voer volledige diepgaande health check uit"""

    categories: Dict[str, CategoryResult] = {}
    start_time = time.time()

    # ─── BANNER ───────────────────────────────────────────────────
    print()
    print(f"{Colors.BLUE}╔══════════════════════════════════════════════════════════════════════╗{Colors.NC}")
    print(f"{Colors.BLUE}║{Colors.NC}          {Colors.BOLD}EMSN2 DIEPGAANDE SYSTEEM GEZONDHEIDSCONTROLE{Colors.NC}            {Colors.BLUE}║{Colors.NC}")
    print(f"{Colors.BLUE}║{Colors.NC}                    {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                             {Colors.BLUE}║{Colors.NC}")
    print(f"{Colors.BLUE}╚══════════════════════════════════════════════════════════════════════╝{Colors.NC}")

    # ─── 1. NETWERK BEREIKBAARHEID ────────────────────────────────
    print_header("1. NETWERK BEREIKBAARHEID")
    cat = CategoryResult(name="Netwerk")

    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {
            executor.submit(check_ping, name, info['ip']): name
            for name, info in HOSTS.items()
        }
        for future in as_completed(futures):
            result = future.result()
            cat.checks.append(result)
            print_check(result)

    categories['netwerk'] = cat

    # Bepaal welke hosts bereikbaar zijn via SSH
    ssh_available = {}
    for name, info in HOSTS.items():
        if info['type'] == 'pi':
            ssh_available[name] = check_ssh_available(name, info['ip'])

    # ─── 2. SERVICES & TIMERS ─────────────────────────────────────
    print_header("2. SERVICES & TIMERS")
    cat = CategoryResult(name="Services")

    for host in ['zolder', 'berging', 'meteo']:
        if not ssh_available.get(host, False):
            cat.checks.append(CheckResult(
                name=f"{host} services",
                status=Status.UNKNOWN,
                message="SSH niet beschikbaar"
            ))
            continue

        ip = HOSTS[host]['ip']

        # Services
        if SERVICES.get(host):
            print_subheader(f"{host.title()} Services")
            for service in SERVICES[host]:
                result = check_ssh_service(host, ip, service)
                cat.checks.append(result)
                print_check(result)

        # Timers
        if TIMERS.get(host):
            print_subheader(f"{host.title()} Timers")
            for timer in TIMERS[host]:
                result = check_ssh_service(host, ip, timer)
                cat.checks.append(result)
                print_check(result)

    categories['services'] = cat

    # ─── 3. HARDWARE METRICS ──────────────────────────────────────
    print_header("3. HARDWARE METRICS")
    cat = CategoryResult(name="Hardware")

    for host in ['zolder', 'berging', 'meteo']:
        if not ssh_available.get(host, False):
            cat.checks.append(CheckResult(
                name=f"{host} hardware",
                status=Status.UNKNOWN,
                message="SSH niet beschikbaar"
            ))
            continue

        print_subheader(f"{host.title()}")
        ip = HOSTS[host]['ip']
        results = check_ssh_hardware(host, ip)
        for result in results:
            cat.checks.append(result)
            print_check(result)

    categories['hardware'] = cat

    # ─── 4. NAS & OPSLAG ──────────────────────────────────────────
    print_header("4. NAS & OPSLAG")
    cat = CategoryResult(name="Opslag")

    print_subheader("NAS Mounts")
    for mount in NAS_MOUNTS:
        result = check_nas_mount(mount['path'], mount['name'])
        cat.checks.append(result)
        print_check(result)

    print_subheader("Database")
    result = check_postgresql()
    cat.checks.append(result)
    print_check(result)

    categories['opslag'] = cat

    # ─── 5. API ENDPOINTS ─────────────────────────────────────────
    print_header("5. API ENDPOINTS & SERVICES")
    cat = CategoryResult(name="APIs")

    print_subheader("MQTT")
    result = check_mqtt_broker()
    cat.checks.append(result)
    print_check(result)

    print_subheader("Web Services")
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(check_api_endpoint, ep['name'], ep['url']): ep['name']
            for ep in API_ENDPOINTS
        }
        for future in as_completed(futures):
            result = future.result()
            cat.checks.append(result)
            print_check(result)

    categories['apis'] = cat

    # ─── 6. CAMERA STREAMS ────────────────────────────────────────
    print_header("6. NESTKAST CAMERAS")
    cat = CategoryResult(name="Cameras")

    results = check_go2rtc_streams()
    for result in results:
        cat.checks.append(result)
        print_check(result)

    categories['cameras'] = cat

    # ─── 7. ATMOSBIRD (HEMELMONITORING) ─────────────────────────────
    print_header("7. ATMOSBIRD (HEMELMONITORING)")
    cat = CategoryResult(name="AtmosBird")

    print_subheader("Camera")
    if ssh_available.get('berging', False):
        result = check_atmosbird_camera()
        cat.checks.append(result)
        print_check(result)
    else:
        cat.checks.append(CheckResult(
            name="AtmosBird Camera",
            status=Status.UNKNOWN,
            message="SSH naar berging niet beschikbaar"
        ))

    print_subheader("Captures")
    results = check_atmosbird_captures()
    for result in results:
        cat.checks.append(result)
        print_check(result)

    print_subheader("Database")
    results = check_atmosbird_data()
    for result in results:
        cat.checks.append(result)
        print_check(result)

    categories['atmosbird'] = cat

    # ─── 8. WEERSTATION (METEO) ───────────────────────────────────
    print_header("8. WEERSTATION (METEO)")
    cat = CategoryResult(name="Meteo")

    results = check_meteo_data()
    for result in results:
        cat.checks.append(result)
        print_check(result)

    categories['meteo'] = cat

    # ─── 9. DATA KWALITEIT & SYNC ─────────────────────────────────
    print_header("9. DATA KWALITEIT & SYNC")
    cat = CategoryResult(name="Data")

    print_subheader("BirdNET Detecties")
    results = check_detection_activity()
    for result in results:
        cat.checks.append(result)
        print_check(result)

    print_subheader("Sync Status")
    results = check_sync_status()
    for result in results:
        cat.checks.append(result)
        print_check(result)

    categories['data'] = cat

    # ─── 10. LOGS & ERRORS ────────────────────────────────────────
    print_header("10. RECENTE LOGS & ERRORS")
    cat = CategoryResult(name="Logs")

    for host in ['zolder', 'berging']:
        if ssh_available.get(host, False):
            results = check_recent_logs(host, HOSTS[host]['ip'])
            for result in results:
                cat.checks.append(result)
                print_check(result)

    categories['logs'] = cat

    # ─── 11. BIRDNET-Pi DATABASE INTEGRITEIT ─────────────────────
    print_header("11. BIRDNET-Pi DATABASE INTEGRITEIT")
    cat = CategoryResult(name="SQLite")

    for host in ['zolder', 'berging']:
        if ssh_available.get(host, False):
            print_subheader(f"{host.title()}")
            ip = HOSTS[host]['ip']

            # SQLite integrity check
            results = check_sqlite_integrity(host, ip)
            for result in results:
                cat.checks.append(result)
                print_check(result)

            # Audio recording check
            result = check_audio_recording(host, ip)
            cat.checks.append(result)
            print_check(result)

    categories['sqlite'] = cat

    # ─── 12. MQTT BRIDGE STATUS ──────────────────────────────────
    print_header("12. MQTT BRIDGE STATUS")
    cat = CategoryResult(name="MQTT Bridge")

    results = check_mqtt_bridge_status()
    for result in results:
        cat.checks.append(result)
        print_check(result)

    categories['mqtt_bridge'] = cat

    # ─── 13. INTERNET & CONNECTIVITEIT ───────────────────────────
    print_header("13. INTERNET & CONNECTIVITEIT")
    cat = CategoryResult(name="Internet")

    results = check_internet_connectivity()
    for result in results:
        cat.checks.append(result)
        print_check(result)

    categories['internet'] = cat

    # ─── 14. SECURITY CHECKS ─────────────────────────────────────
    print_header("14. SECURITY CHECKS")
    cat = CategoryResult(name="Security")

    for host in ['zolder', 'berging', 'meteo']:
        if ssh_available.get(host, False):
            results = check_security(host, HOSTS[host]['ip'])
            for result in results:
                cat.checks.append(result)
                print_check(result)

    categories['security'] = cat

    # ─── 15. BACKUP & TRENDS ─────────────────────────────────────
    print_header("15. BACKUP & TRENDS")
    cat = CategoryResult(name="Backup/Trends")

    print_subheader("Backups")
    results = check_backup_status()
    for result in results:
        cat.checks.append(result)
        print_check(result)

    print_subheader("Detectie Trends")
    results = check_detection_trends()
    for result in results:
        cat.checks.append(result)
        print_check(result)

    print_subheader("Disk Groei")
    results = check_disk_growth()
    for result in results:
        cat.checks.append(result)
        print_check(result)

    print_subheader("Vocalization & Ulanzi")
    result = check_vocalization_models()
    cat.checks.append(result)
    print_check(result)

    result = check_ulanzi_status()
    cat.checks.append(result)
    print_check(result)

    categories['backup_trends'] = cat

    # ─── SAMENVATTING ─────────────────────────────────────────────
    elapsed = time.time() - start_time
    print_header("SAMENVATTING")

    total_ok = sum(c.ok_count for c in categories.values())
    total_warning = sum(c.warning_count for c in categories.values())
    total_critical = sum(c.critical_count for c in categories.values())
    total = total_ok + total_warning + total_critical

    print()
    print(f"  {Colors.BOLD}Categorie Overzicht:{Colors.NC}")
    print()
    for name, cat in categories.items():
        color = status_color(cat.status)
        icon = status_icon(cat.status)
        print(f"    {color}{icon}{Colors.NC} {name.title():20} "
              f"{Colors.GREEN}{cat.ok_count} OK{Colors.NC} / "
              f"{Colors.YELLOW}{cat.warning_count} warn{Colors.NC} / "
              f"{Colors.RED}{cat.critical_count} crit{Colors.NC}")

    print()
    print(f"  {Colors.BOLD}Totaal:{Colors.NC}")
    print()
    print(f"    {Colors.GREEN}Passed:   {total_ok}{Colors.NC}")
    print(f"    {Colors.YELLOW}Warning:  {total_warning}{Colors.NC}")
    print(f"    {Colors.RED}Critical: {total_critical}{Colors.NC}")
    print()

    if total_critical == 0 and total_warning == 0:
        print(f"  {Colors.GREEN}✓ Alle {total} checks geslaagd - systeem volledig gezond!{Colors.NC}")
    elif total_critical == 0:
        print(f"  {Colors.YELLOW}⚠ Systeem operationeel met {total_warning} waarschuwing(en){Colors.NC}")
    else:
        print(f"  {Colors.RED}✗ {total_critical} kritieke problemen gevonden!{Colors.NC}")

    print()
    print(f"  {Colors.CYAN}Diagnose voltooid in {elapsed:.1f} seconden{Colors.NC}")
    print()

    return categories


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    try:
        categories = run_deep_health_check()

        # Exit code gebaseerd op resultaten
        total_critical = sum(c.critical_count for c in categories.values())
        sys.exit(min(total_critical, 255))

    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Diagnose afgebroken door gebruiker{Colors.NC}")
        sys.exit(130)
    except Exception as e:
        print(f"\n{Colors.RED}Fatale fout: {e}{Colors.NC}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
