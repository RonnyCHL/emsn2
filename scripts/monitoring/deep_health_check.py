#!/usr/bin/env python3
"""
EMSN2 Deep Health Check - Ultieme Systeemdiagnose

Dit script voert een diepgaande gezondheidscontrole uit op ALLE aspecten
van het EMSN2 ecosysteem. Het is het meest complete diagnostic tool.

29 CATEGORIEËN:

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

16. EXTRA MONITORING:
    - WiFi signaalsterkte (alleen Meteo Pi)
    - NTP synchronisatie status per host
    - Soorten diversiteit (unieke soorten vandaag vs gemiddeld)
    - Top soorten vandaag
    - Confidence distributie (microfoon kwaliteit indicator)

17. HARDWARE DIEPTE CHECKS:
    - SD-kaart gezondheid (wear errors, filesystem errors)
    - Kernel/dmesg errors (OOM kills, USB errors)
    - USB device aanwezigheid en mount status

18. BIRDNET SPECIFIEKE CHECKS:
    - BirdNET analyzer service status
    - Extraction service status
    - BirdNET model versie en aantal soorten

19. EXTERNE SERVICES & DATABASE:
    - Tuya Cloud API bereikbaarheid
    - GitHub repo sync status
    - Orphaned/duplicate records in database
    - PostgreSQL table sizes

20. VOCALIZATION SYSTEEM:
    - Vocalization enricher service status
    - Docker container status (NAS)
    - Verrijkingspercentage detecties

21. FLYSAFE RADAR & MIGRATIE:
    - FlySafe scraper timer status
    - Radar data recentheid

22. NESTKAST AI DETECTIE:
    - AI model beschikbaarheid (occupancy, species)
    - Events per nestkast
    - Screenshots vandaag

23. RAPPORT GENERATIE:
    - Weekly/Monthly/Yearly report timers
    - Reports directory status

24. ANOMALY DETECTION SYSTEEM:
    - Hardware/DataGap/Baseline checkers
    - Actieve anomalieën status

25. AUDIO & MICROFOON KWALITEIT:
    - ALSA audio devices
    - Dag/nacht detectie ratio

26. BACKUP & ARCHIVERING:
    - SD backup timers
    - Archive sync status
    - Archive ruimte beschikbaarheid

27. NETWERK DIEPTE:
    - Packet loss per host
    - DNS resolution performance
    - Gateway bereikbaarheid

28. REALTIME SERVICES:
    - Realtime dual detection service
    - Detection rate per station
    - Ulanzi notificatie frequentie

Auteur: Claude Code (IT Specialist EMSN2)
Versie: 4.0.0
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
# CREDENTIALS HELPER (centrale functie voor alle DB connecties)
# ═══════════════════════════════════════════════════════════════

_pg_config_cache: Optional[Dict[str, Any]] = None

def get_pg_config() -> Optional[Dict[str, Any]]:
    """
    Haal PostgreSQL config op via core.config module.
    Cached voor hergebruik tijdens health check run.
    """
    global _pg_config_cache

    if _pg_config_cache is not None:
        return _pg_config_cache

    try:
        from core.config import get_postgres_config
        _pg_config_cache = get_postgres_config()
        return _pg_config_cache
    except ImportError:
        # Fallback: lees direct uit .secrets
        secrets_file = Path(__file__).parent.parent.parent / '.secrets'
        if secrets_file.exists():
            config = {
                'host': '192.168.1.25',
                'port': 5433,
                'database': 'emsn',
                'user': 'birdpi_zolder',
                'password': None
            }
            with open(secrets_file) as f:
                for line in f:
                    if line.startswith('PG_PASS='):
                        config['password'] = line.strip().split('=', 1)[1]
                        break
            if config['password']:
                _pg_config_cache = config
                return config
        return None


def get_mqtt_config() -> Optional[Dict[str, Any]]:
    """Haal MQTT config op via core.config module."""
    try:
        from core.config import get_mqtt_config as _get_mqtt
        return _get_mqtt()
    except ImportError:
        # Fallback: lees direct uit .secrets
        secrets_file = Path(__file__).parent.parent.parent / '.secrets'
        if secrets_file.exists():
            config = {
                'broker': '192.168.1.178',
                'port': 1883,
                'username': None,
                'password': None
            }
            with open(secrets_file) as f:
                for line in f:
                    if line.startswith('MQTT_USER='):
                        config['username'] = line.strip().split('=', 1)[1]
                    elif line.startswith('MQTT_PASS='):
                        config['password'] = line.strip().split('=', 1)[1]
            if config['username'] and config['password']:
                return config
        return None


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
# AUTO-DISCOVERY CONFIGURATIE
# ═══════════════════════════════════════════════════════════════

# Patronen voor EMSN-gerelateerde services en timers
# Als een nieuwe service/timer matcht maar NIET in KNOWN_SERVICES staat,
# krijg je een waarschuwing dat er een nieuwe feature is zonder specifieke checks
EMSN_SERVICE_PATTERNS = [
    'emsn-*',
    'birdnet-*',
    'atmosbird-*',
    'lifetime-sync*',
    'mqtt-*',
    'mosquitto*',
    'vocalization-*',
    'flysafe-*',
    'nestbox-*',
    'weather-*',
    'ulanzi-*',
    'reports-api*',
    'anomaly-*',
    'dual-detection*',
    'realtime-*',
    'sd-backup-*',
    'database-*',
    'homer-*',
    'rarity-*',
    'screenshot-*',
    'system-inventory*',
    'timer-timeline*',
    'weekly-system-report*',
    'log-cleanup*',
    'health-check*',
    'hardware-*',
    'network-*',
    'reboot-alert*',
    'go2rtc-*',
    # Toekomstige systemen - voeg hier patronen toe
    'vleermuizen-*',
    'bat-*',
    'insecten-*',
    'moth-*',
]

# Alle BEKENDE services die we specifiek checken in categorieën 1-28
# Services hier worden NIET gemeld als "nieuw ontdekt"
KNOWN_SERVICES = {
    'zolder': [
        # Services
        'birdnet-mqtt-publisher.service',
        'mqtt-bridge-monitor.service',
        'mosquitto.service',
        'reports-api.service',
        'ulanzi-bridge.service',
        'vocalization-enricher.service',
        'realtime-dual-detection.service',
        'emsn-cooldown-display.service',
        'reboot-alert.service',
        # Timers
        'lifetime-sync.timer',
        'lifetime-sync-zolder.timer',
        'nestbox-screenshot.timer',
        'emsn-weekly-report.timer',
        'emsn-monthly-report.timer',
        'emsn-yearly-report.timer',
        'emsn-seasonal-report-spring.timer',
        'emsn-seasonal-report-summer.timer',
        'emsn-seasonal-report-autumn.timer',
        'emsn-seasonal-report-winter.timer',
        'anomaly-hardware-check.timer',
        'anomaly-datagap-check.timer',
        'anomaly-baseline-learn.timer',
        'flysafe-radar-day.timer',
        'flysafe-radar-night.timer',
        'dual-detection.timer',
        'mqtt-failover.timer',
        'rarity-cache.timer',
        'screenshot-cleanup.timer',
        'system-inventory.timer',
        'timer-timeline.timer',
        'homer-stats.timer',
        'database-backup.timer',
        'database-cleanup.timer',
        'log-cleanup.timer',
        'weekly-system-report.timer',
        'health-check.timer',
        'network-monitor.timer',
        'birdnet-archive-sync.timer',
        'backup-cleanup.timer',
        'emsn-dbmirror-zolder.timer',
        'nas-metrics-collector.timer',
        'sd-backup-daily.timer',
        'sd-backup-weekly.timer',
    ],
    'berging': [
        # Services
        'birdnet-mqtt-publisher.service',
        'mosquitto.service',
        'atmosbird-stream.service',
        'atmosbird-climate.service',
        'reboot-alert.service',
        # Timers
        'lifetime-sync.timer',
        'lifetime-sync-berging.timer',
        'atmosbird-capture.timer',
        'atmosbird-analysis.timer',
        'atmosbird-timelapse.timer',
        'atmosbird-archive-sync.timer',
        'sd-backup-daily.timer',
    ],
    'meteo': [
        # Services
        'reboot-alert.service',
        # Timers
        'weather-publisher.timer',
        'hardware-monitor.timer',
    ],
}

# Database tabellen die we kennen en monitoren
KNOWN_DATABASE_TABLES = [
    'bird_detections',
    'weather_data',
    'sky_observations',
    'iss_passes',
    'moon_observations',
    'meteor_detections',
    'star_brightness',
    'nestbox_events',
    'nestbox_media',
    'anomalies',
    'anomaly_check_log',
    'vocalization_training',
    'vocalization_model_versions',
    'radar_observations',
    'dual_detections',
    'species_baselines',
    # Toekomstige tabellen
    'bat_detections',
    'insect_detections',
]


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
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError):
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
# 16. EXTRA MONITORING CHECKS
# ═══════════════════════════════════════════════════════════════

@timed_check
def check_wifi_signal(host: str, ip: str) -> CheckResult:
    """Check WiFi signaalsterkte (alleen voor Meteo Pi)"""
    try:
        result = subprocess.run(
            ['ssh', '-o', 'ConnectTimeout=5', '-o', 'BatchMode=yes',
             f'ronny@{ip}',
             '''
             if iwconfig wlan0 2>/dev/null | grep -q "Signal level"; then
                 SIGNAL=$(iwconfig wlan0 2>/dev/null | grep "Signal level" | awk -F'=' '{print $3}' | awk '{print $1}')
                 QUALITY=$(iwconfig wlan0 2>/dev/null | grep "Link Quality" | awk -F'=' '{print $2}' | awk '{print $1}')
                 echo "SIGNAL:$SIGNAL"
                 echo "QUALITY:$QUALITY"
             else
                 echo "NO_WIFI"
             fi
             '''],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            output = result.stdout.strip()
            if 'NO_WIFI' in output:
                return CheckResult(
                    name=f"{host} WiFi",
                    status=Status.OK,
                    message="Geen WiFi (UTP verbinding)",
                )

            metrics = {}
            for line in output.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    metrics[key] = value.strip()

            signal = metrics.get('SIGNAL', '')
            quality = metrics.get('QUALITY', '')

            # Parse signal level (dBm)
            try:
                signal_dbm = int(signal.replace('dBm', '').strip())
                if signal_dbm < -80:
                    return CheckResult(
                        name=f"{host} WiFi",
                        status=Status.CRITICAL,
                        message=f"Zwak signaal: {signal_dbm}dBm (quality: {quality})",
                        details={'signal_dbm': signal_dbm, 'quality': quality}
                    )
                elif signal_dbm < -70:
                    return CheckResult(
                        name=f"{host} WiFi",
                        status=Status.WARNING,
                        message=f"Matig signaal: {signal_dbm}dBm (quality: {quality})",
                        details={'signal_dbm': signal_dbm, 'quality': quality}
                    )
                else:
                    return CheckResult(
                        name=f"{host} WiFi",
                        status=Status.OK,
                        message=f"Goed signaal: {signal_dbm}dBm (quality: {quality})",
                        details={'signal_dbm': signal_dbm, 'quality': quality}
                    )
            except ValueError:
                return CheckResult(
                    name=f"{host} WiFi",
                    status=Status.OK,
                    message=f"Signal: {signal}, Quality: {quality}",
                    details={'signal': signal, 'quality': quality}
                )

        return CheckResult(
            name=f"{host} WiFi",
            status=Status.UNKNOWN,
            message="Kan WiFi niet controleren"
        )

    except Exception as e:
        return CheckResult(
            name=f"{host} WiFi",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        )


@timed_check
def check_ntp_sync(host: str, ip: str) -> CheckResult:
    """Check NTP synchronisatie status"""
    try:
        result = subprocess.run(
            ['ssh', '-o', 'ConnectTimeout=5', '-o', 'BatchMode=yes',
             f'ronny@{ip}',
             '''
             if command -v timedatectl &> /dev/null; then
                 SYNCED=$(timedatectl show --property=NTPSynchronized --value)
                 OFFSET=$(timedatectl timesync-status 2>/dev/null | grep "Offset" | awk '{print $2}')
                 echo "SYNCED:$SYNCED"
                 echo "OFFSET:$OFFSET"
             else
                 echo "NO_TIMEDATECTL"
             fi
             '''],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            output = result.stdout.strip()
            if 'NO_TIMEDATECTL' in output:
                return CheckResult(
                    name=f"{host} NTP",
                    status=Status.UNKNOWN,
                    message="timedatectl niet beschikbaar"
                )

            metrics = {}
            for line in output.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    metrics[key] = value.strip()

            synced = metrics.get('SYNCED', 'no')
            offset = metrics.get('OFFSET', '')

            if synced.lower() == 'yes':
                return CheckResult(
                    name=f"{host} NTP",
                    status=Status.OK,
                    message=f"Gesynchroniseerd (offset: {offset})" if offset else "Gesynchroniseerd",
                    details={'synced': True, 'offset': offset}
                )
            else:
                return CheckResult(
                    name=f"{host} NTP",
                    status=Status.WARNING,
                    message="NIET gesynchroniseerd!",
                    details={'synced': False}
                )

        return CheckResult(
            name=f"{host} NTP",
            status=Status.UNKNOWN,
            message="Kan NTP niet controleren"
        )

    except Exception as e:
        return CheckResult(
            name=f"{host} NTP",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        )


@timed_check
def check_species_diversity() -> List[CheckResult]:
    """Check soorten diversiteit en top detecties"""
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
                name="Species Diversity",
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

        # Soorten diversiteit vandaag vs gemiddeld
        cursor.execute("""
            WITH daily_species AS (
                SELECT
                    detected_at::date as day,
                    COUNT(DISTINCT common_name) as unique_species
                FROM lifetime_detections
                WHERE deleted = false
                  AND detected_at >= NOW() - INTERVAL '30 days'
                GROUP BY detected_at::date
            )
            SELECT
                (SELECT unique_species FROM daily_species WHERE day = CURRENT_DATE) as today,
                (SELECT unique_species FROM daily_species WHERE day = CURRENT_DATE - 1) as yesterday,
                AVG(unique_species) as avg_30d
            FROM daily_species
        """)
        row = cursor.fetchone()

        if row:
            today_species, yesterday_species, avg_species = row
            today_species = today_species or 0
            yesterday_species = yesterday_species or 0
            avg_species = avg_species or 0

            if today_species < (avg_species * 0.3) and datetime.now().hour > 10:
                results.append(CheckResult(
                    name="Soorten Diversiteit",
                    status=Status.WARNING,
                    message=f"Weinig soorten vandaag: {today_species} (gem: {avg_species:.0f})",
                    details={'today': today_species, 'yesterday': yesterday_species, 'avg_30d': avg_species}
                ))
            else:
                results.append(CheckResult(
                    name="Soorten Diversiteit",
                    status=Status.OK,
                    message=f"{today_species} soorten vandaag (gisteren: {yesterday_species}, gem: {avg_species:.0f})",
                    details={'today': today_species, 'yesterday': yesterday_species, 'avg_30d': avg_species}
                ))

        # Top 5 soorten vandaag
        cursor.execute("""
            SELECT
                common_name,
                COUNT(*) as count
            FROM lifetime_detections
            WHERE deleted = false
              AND detected_at::date = CURRENT_DATE
            GROUP BY common_name
            ORDER BY count DESC
            LIMIT 5
        """)
        top_species = cursor.fetchall()

        if top_species:
            top_list = ", ".join([f"{s[0]}({s[1]})" for s in top_species[:3]])
            results.append(CheckResult(
                name="Top Soorten Vandaag",
                status=Status.OK,
                message=top_list,
                details={'top_5': [{'species': s[0], 'count': s[1]} for s in top_species]}
            ))

        conn.close()
        return results

    except Exception as e:
        return [CheckResult(
            name="Species Diversity",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        )]


@timed_check
def check_confidence_distribution() -> CheckResult:
    """Check confidence distributie als indicator voor microfoon kwaliteit"""
    try:
        secrets_file = Path("/home/ronny/emsn2/.secrets")
        pg_pass = None
        with open(secrets_file) as f:
            for line in f:
                if line.startswith('PG_PASSWORD='):
                    pg_pass = line.split('=', 1)[1].strip()
                    break

        if not pg_pass:
            return CheckResult(
                name="Confidence Check",
                status=Status.UNKNOWN,
                message="Credentials niet beschikbaar"
            )

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

        # Gemiddelde confidence per station vandaag vs gisteren
        cursor.execute("""
            SELECT
                station,
                AVG(confidence) FILTER (WHERE detected_at::date = CURRENT_DATE) as avg_today,
                AVG(confidence) FILTER (WHERE detected_at::date = CURRENT_DATE - 1) as avg_yesterday,
                AVG(confidence) FILTER (WHERE detected_at >= NOW() - INTERVAL '7 days') as avg_week
            FROM lifetime_detections
            WHERE deleted = false
              AND detected_at >= NOW() - INTERVAL '7 days'
            GROUP BY station
        """)

        results_text = []
        worst_status = Status.OK
        details = {}

        for row in cursor.fetchall():
            station, avg_today, avg_yesterday, avg_week = row
            avg_today = (avg_today or 0) * 100
            avg_yesterday = (avg_yesterday or 0) * 100
            avg_week = (avg_week or 0) * 100

            details[station] = {
                'today': avg_today,
                'yesterday': avg_yesterday,
                'week': avg_week
            }

            # Check voor significante daling
            if avg_today > 0 and avg_week > 0:
                if avg_today < (avg_week * 0.8):  # >20% lager dan weekgemiddelde
                    worst_status = Status.WARNING
                    results_text.append(f"{station}: {avg_today:.0f}% (↓)")
                else:
                    results_text.append(f"{station}: {avg_today:.0f}%")

        conn.close()

        if results_text:
            return CheckResult(
                name="Avg Confidence",
                status=worst_status,
                message=", ".join(results_text),
                details=details
            )
        else:
            return CheckResult(
                name="Avg Confidence",
                status=Status.OK,
                message="Geen data vandaag"
            )

    except Exception as e:
        return CheckResult(
            name="Confidence Check",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        )


# ═══════════════════════════════════════════════════════════════
# 17. HARDWARE DIEPTE CHECKS
# ═══════════════════════════════════════════════════════════════

@timed_check
def check_sd_card_health(host: str, ip: str) -> CheckResult:
    """Check SD-kaart gezondheid via wear indicators"""
    try:
        result = subprocess.run(
            ['ssh', '-o', 'ConnectTimeout=5', '-o', 'BatchMode=yes',
             f'ronny@{ip}',
             '''
             # Check voor SD card wear via kernel messages
             WEAR_ERRORS=$(dmesg 2>/dev/null | grep -ci "mmc0.*error\|mmcblk0.*error" || echo 0)

             # Check filesystem errors
             FS_ERRORS=$(dmesg 2>/dev/null | grep -ci "ext4.*error\|EXT4-fs error" || echo 0)

             # Check read-only remounts (teken van probleem)
             RO_MOUNTS=$(dmesg 2>/dev/null | grep -ci "remount.*read-only" || echo 0)

             # Disk I/O stats
             if [ -f /sys/block/mmcblk0/stat ]; then
                 READ_IOS=$(awk '{print $1}' /sys/block/mmcblk0/stat)
                 WRITE_IOS=$(awk '{print $5}' /sys/block/mmcblk0/stat)
             else
                 READ_IOS=0
                 WRITE_IOS=0
             fi

             echo "WEAR_ERRORS:$WEAR_ERRORS"
             echo "FS_ERRORS:$FS_ERRORS"
             echo "RO_MOUNTS:$RO_MOUNTS"
             echo "READ_IOS:$READ_IOS"
             echo "WRITE_IOS:$WRITE_IOS"
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

            wear_errors = int(metrics.get('WEAR_ERRORS', 0))
            fs_errors = int(metrics.get('FS_ERRORS', 0))
            ro_mounts = int(metrics.get('RO_MOUNTS', 0))

            total_errors = wear_errors + fs_errors + ro_mounts

            if ro_mounts > 0:
                return CheckResult(
                    name=f"{host} SD-kaart",
                    status=Status.CRITICAL,
                    message=f"Read-only remount gedetecteerd! ({ro_mounts}x)",
                    details=metrics
                )
            elif total_errors > 10:
                return CheckResult(
                    name=f"{host} SD-kaart",
                    status=Status.WARNING,
                    message=f"{total_errors} disk errors in dmesg",
                    details=metrics
                )
            else:
                return CheckResult(
                    name=f"{host} SD-kaart",
                    status=Status.OK,
                    message="Geen problemen gedetecteerd",
                    details=metrics
                )

        return CheckResult(
            name=f"{host} SD-kaart",
            status=Status.UNKNOWN,
            message="Kan SD-kaart niet controleren"
        )

    except Exception as e:
        return CheckResult(
            name=f"{host} SD-kaart",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        )


@timed_check
def check_kernel_errors(host: str, ip: str) -> CheckResult:
    """Check kernel/dmesg voor hardware errors"""
    try:
        result = subprocess.run(
            ['ssh', '-o', 'ConnectTimeout=5', '-o', 'BatchMode=yes',
             f'ronny@{ip}',
             '''
             # Tel verschillende error types in dmesg
             TOTAL_ERRORS=$(dmesg --level=err,crit,alert,emerg 2>/dev/null | wc -l || echo 0)
             USB_ERRORS=$(dmesg 2>/dev/null | grep -ci "usb.*error\|usb.*fail" || echo 0)
             TEMP_WARNINGS=$(dmesg 2>/dev/null | grep -ci "temperature\|thermal\|throttl" || echo 0)
             OOM_KILLS=$(dmesg 2>/dev/null | grep -ci "out of memory\|oom-killer" || echo 0)

             # Laatste kritieke error
             LAST_ERROR=$(dmesg --level=err,crit 2>/dev/null | tail -1 | cut -c1-80)

             echo "TOTAL_ERRORS:$TOTAL_ERRORS"
             echo "USB_ERRORS:$USB_ERRORS"
             echo "TEMP_WARNINGS:$TEMP_WARNINGS"
             echo "OOM_KILLS:$OOM_KILLS"
             echo "LAST_ERROR:$LAST_ERROR"
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

            total_errors = int(metrics.get('TOTAL_ERRORS', 0))
            oom_kills = int(metrics.get('OOM_KILLS', 0))
            last_error = metrics.get('LAST_ERROR', '')

            if oom_kills > 0:
                return CheckResult(
                    name=f"{host} Kernel",
                    status=Status.CRITICAL,
                    message=f"OOM killer actief geweest! ({oom_kills}x)",
                    details=metrics
                )
            elif total_errors > 50:
                return CheckResult(
                    name=f"{host} Kernel",
                    status=Status.WARNING,
                    message=f"{total_errors} kernel errors",
                    details=metrics
                )
            else:
                return CheckResult(
                    name=f"{host} Kernel",
                    status=Status.OK,
                    message=f"{total_errors} errors in dmesg",
                    details=metrics
                )

        return CheckResult(
            name=f"{host} Kernel",
            status=Status.UNKNOWN,
            message="Kan kernel logs niet controleren"
        )

    except Exception as e:
        return CheckResult(
            name=f"{host} Kernel",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        )


@timed_check
def check_usb_devices(host: str, ip: str) -> CheckResult:
    """Check of verwachte USB devices aanwezig zijn"""
    try:
        result = subprocess.run(
            ['ssh', '-o', 'ConnectTimeout=5', '-o', 'BatchMode=yes',
             f'ronny@{ip}',
             '''
             # Tel USB devices
             USB_COUNT=$(lsusb 2>/dev/null | wc -l || echo 0)

             # Check voor USB storage (voor audio opslag)
             USB_STORAGE=$(lsusb 2>/dev/null | grep -ci "mass storage\|flash\|disk" || echo 0)

             # Check voor audio devices (microfoon)
             USB_AUDIO=$(lsusb 2>/dev/null | grep -ci "audio\|sound\|mic" || echo 0)

             # Check mount status van USB disk
             USB_MOUNTED=$(mount | grep -c "/mnt/usb" || echo 0)

             # Lijst van USB devices
             USB_LIST=$(lsusb 2>/dev/null | grep -v "hub" | head -5)

             echo "USB_COUNT:$USB_COUNT"
             echo "USB_STORAGE:$USB_STORAGE"
             echo "USB_AUDIO:$USB_AUDIO"
             echo "USB_MOUNTED:$USB_MOUNTED"
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

            usb_count = int(metrics.get('USB_COUNT', 0))
            usb_mounted = int(metrics.get('USB_MOUNTED', 0))
            usb_audio = int(metrics.get('USB_AUDIO', 0))

            issues = []
            status = Status.OK

            # Voor zolder/berging verwachten we USB storage
            if host in ['zolder', 'berging'] and usb_mounted == 0:
                issues.append("USB niet gemount")
                status = Status.WARNING

            if usb_count < 2:  # Minimaal hub + iets
                issues.append(f"Weinig USB devices ({usb_count})")
                status = Status.WARNING

            if issues:
                return CheckResult(
                    name=f"{host} USB",
                    status=status,
                    message=", ".join(issues),
                    details=metrics
                )
            else:
                return CheckResult(
                    name=f"{host} USB",
                    status=Status.OK,
                    message=f"{usb_count} devices, storage gemount" if usb_mounted else f"{usb_count} devices",
                    details=metrics
                )

        return CheckResult(
            name=f"{host} USB",
            status=Status.UNKNOWN,
            message="Kan USB niet controleren"
        )

    except Exception as e:
        return CheckResult(
            name=f"{host} USB",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        )


# ═══════════════════════════════════════════════════════════════
# 18. BIRDNET SPECIFIEKE CHECKS
# ═══════════════════════════════════════════════════════════════

@timed_check
def check_birdnet_analyzer(host: str, ip: str) -> CheckResult:
    """Check BirdNET analyzer service status"""
    try:
        result = subprocess.run(
            ['ssh', '-o', 'ConnectTimeout=5', '-o', 'BatchMode=yes',
             f'ronny@{ip}',
             '''
             # Check birdnet_analysis service
             ANALYZER_STATUS=$(systemctl is-active birdnet_analysis.service 2>/dev/null || echo "not-found")

             # Check extraction service
             EXTRACTION_STATUS=$(systemctl is-active extraction.service 2>/dev/null || echo "not-found")

             # Check of BirdNET process draait
             BIRDNET_PROCS=$(pgrep -c -f "birdnet\|analyze" 2>/dev/null || echo 0)

             # Laatste analyse tijd (uit log)
             LAST_ANALYSIS=$(journalctl -u birdnet_analysis --since "1 hour ago" --no-pager 2>/dev/null | grep -c "Analyzed" || echo 0)

             echo "ANALYZER:$ANALYZER_STATUS"
             echo "EXTRACTION:$EXTRACTION_STATUS"
             echo "PROCS:$BIRDNET_PROCS"
             echo "RECENT_ANALYSES:$LAST_ANALYSIS"
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

            analyzer = metrics.get('ANALYZER', 'unknown')
            extraction = metrics.get('EXTRACTION', 'unknown')
            recent = int(metrics.get('RECENT_ANALYSES', 0))

            if analyzer != 'active':
                return CheckResult(
                    name=f"{host} BirdNET Analyzer",
                    status=Status.CRITICAL,
                    message=f"Analyzer niet actief! ({analyzer})",
                    details=metrics
                )
            elif extraction != 'active':
                return CheckResult(
                    name=f"{host} BirdNET Analyzer",
                    status=Status.WARNING,
                    message=f"Extraction service: {extraction}",
                    details=metrics
                )
            else:
                return CheckResult(
                    name=f"{host} BirdNET Analyzer",
                    status=Status.OK,
                    message=f"Actief ({recent} analyses laatste uur)",
                    details=metrics
                )

        return CheckResult(
            name=f"{host} BirdNET",
            status=Status.UNKNOWN,
            message="Kan BirdNET niet controleren"
        )

    except Exception as e:
        return CheckResult(
            name=f"{host} BirdNET",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        )


@timed_check
def check_birdnet_model_version(host: str, ip: str) -> CheckResult:
    """Check BirdNET model versie"""
    try:
        result = subprocess.run(
            ['ssh', '-o', 'ConnectTimeout=5', '-o', 'BatchMode=yes',
             f'ronny@{ip}',
             '''
             # Check model file
             MODEL_FILE=$(ls -la /home/ronny/BirdNET-Pi/model/*.tflite 2>/dev/null | head -1 | awk '{print $NF}')
             MODEL_SIZE=$(ls -la /home/ronny/BirdNET-Pi/model/*.tflite 2>/dev/null | head -1 | awk '{print $5}')

             # Check labels file voor versie hint
             LABEL_COUNT=$(wc -l < /home/ronny/BirdNET-Pi/model/labels.txt 2>/dev/null || echo 0)

             # BirdNET-Pi versie uit git
             cd /home/ronny/BirdNET-Pi && BIRDNET_VERSION=$(git describe --tags 2>/dev/null || git rev-parse --short HEAD 2>/dev/null || echo "unknown")

             echo "MODEL:$(basename "$MODEL_FILE" 2>/dev/null || echo unknown)"
             echo "SIZE:$MODEL_SIZE"
             echo "LABELS:$LABEL_COUNT"
             echo "VERSION:$BIRDNET_VERSION"
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

            model = metrics.get('MODEL', 'unknown')
            version = metrics.get('VERSION', 'unknown')
            labels = metrics.get('LABELS', '0')

            return CheckResult(
                name=f"{host} BirdNET Model",
                status=Status.OK,
                message=f"{model} ({labels} soorten), v{version}",
                details=metrics
            )

        return CheckResult(
            name=f"{host} BirdNET Model",
            status=Status.UNKNOWN,
            message="Kan model niet controleren"
        )

    except Exception as e:
        return CheckResult(
            name=f"{host} BirdNET Model",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        )


# ═══════════════════════════════════════════════════════════════
# 19. EXTERNE SERVICES & DATABASE CHECKS
# ═══════════════════════════════════════════════════════════════

@timed_check
def check_tuya_cameras() -> CheckResult:
    """Check Tuya camera API beschikbaarheid"""
    try:
        # Test of we de Tuya API kunnen bereiken
        import urllib.request

        # Tuya EU endpoint
        req = urllib.request.Request(
            'https://openapi.tuyaeu.com/',
            method='HEAD'
        )
        req.add_header('User-Agent', 'EMSN-Health-Check/1.0')

        start = time.time()
        with urllib.request.urlopen(req, timeout=10) as response:
            elapsed = (time.time() - start) * 1000
            return CheckResult(
                name="Tuya Cloud API",
                status=Status.OK,
                message=f"Bereikbaar ({elapsed:.0f}ms)",
                details={'response_time_ms': elapsed}
            )

    except urllib.error.HTTPError as e:
        # 401/403 is OK - API is bereikbaar maar auth nodig
        if e.code in [401, 403, 405]:
            return CheckResult(
                name="Tuya Cloud API",
                status=Status.OK,
                message=f"Bereikbaar (HTTP {e.code})"
            )
        return CheckResult(
            name="Tuya Cloud API",
            status=Status.WARNING,
            message=f"HTTP {e.code}"
        )
    except Exception as e:
        return CheckResult(
            name="Tuya Cloud API",
            status=Status.WARNING,
            message=f"Niet bereikbaar: {str(e)[:30]}"
        )


@timed_check
def check_github_sync() -> CheckResult:
    """Check of lokale repo up-to-date is met GitHub"""
    try:
        # Fetch latest zonder te pullen
        result = subprocess.run(
            ['git', '-C', '/home/ronny/emsn2', 'fetch', '--dry-run'],
            capture_output=True,
            text=True,
            timeout=30
        )

        # Check status
        result = subprocess.run(
            ['git', '-C', '/home/ronny/emsn2', 'status', '-uno'],
            capture_output=True,
            text=True,
            timeout=10
        )

        output = result.stdout

        if 'Your branch is up to date' in output:
            return CheckResult(
                name="GitHub Sync",
                status=Status.OK,
                message="Up-to-date met origin/main"
            )
        elif 'Your branch is ahead' in output:
            # Tel commits ahead
            commits = output.split('ahead')[1].split('commit')[0].strip().strip("by '")
            return CheckResult(
                name="GitHub Sync",
                status=Status.OK,
                message=f"Lokaal {commits} commits vooruit"
            )
        elif 'Your branch is behind' in output:
            return CheckResult(
                name="GitHub Sync",
                status=Status.WARNING,
                message="Lokaal achter op remote!"
            )
        elif 'diverged' in output:
            return CheckResult(
                name="GitHub Sync",
                status=Status.WARNING,
                message="Branch is diverged van remote"
            )
        else:
            return CheckResult(
                name="GitHub Sync",
                status=Status.OK,
                message="Sync OK"
            )

    except Exception as e:
        return CheckResult(
            name="GitHub Sync",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        )


@timed_check
def check_orphaned_records() -> CheckResult:
    """Check voor orphaned records in database"""
    try:
        secrets_file = Path("/home/ronny/emsn2/.secrets")
        pg_pass = None
        with open(secrets_file) as f:
            for line in f:
                if line.startswith('PG_PASSWORD='):
                    pg_pass = line.split('=', 1)[1].strip()
                    break

        if not pg_pass:
            return CheckResult(
                name="Orphaned Records",
                status=Status.UNKNOWN,
                message="Credentials niet beschikbaar"
            )

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

        # Check voor detecties zonder geldige audio (file_name check)
        cursor.execute("""
            SELECT COUNT(*)
            FROM lifetime_detections
            WHERE deleted = false
              AND (file_name IS NULL OR file_name = '')
        """)
        no_filename = cursor.fetchone()[0]

        # Check voor duplicate detecties (zelfde timestamp + station + soort)
        cursor.execute("""
            SELECT COUNT(*) FROM (
                SELECT station, detected_at, common_name, COUNT(*) as cnt
                FROM lifetime_detections
                WHERE deleted = false
                  AND detected_at >= NOW() - INTERVAL '7 days'
                GROUP BY station, detected_at, common_name
                HAVING COUNT(*) > 1
            ) dupes
        """)
        duplicates = cursor.fetchone()[0]

        conn.close()

        issues = []
        status = Status.OK

        if no_filename > 0:
            issues.append(f"{no_filename} zonder filename")
            status = Status.WARNING

        if duplicates > 10:
            issues.append(f"{duplicates} duplicaten")
            status = Status.WARNING

        if issues:
            return CheckResult(
                name="Data Integriteit",
                status=status,
                message=", ".join(issues),
                details={'no_filename': no_filename, 'duplicates': duplicates}
            )
        else:
            return CheckResult(
                name="Data Integriteit",
                status=Status.OK,
                message="Geen orphans of duplicaten",
                details={'no_filename': no_filename, 'duplicates': duplicates}
            )

    except Exception as e:
        return CheckResult(
            name="Data Integriteit",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        )


@timed_check
def check_table_sizes() -> CheckResult:
    """Check PostgreSQL table sizes"""
    try:
        secrets_file = Path("/home/ronny/emsn2/.secrets")
        pg_pass = None
        with open(secrets_file) as f:
            for line in f:
                if line.startswith('PG_PASSWORD='):
                    pg_pass = line.split('=', 1)[1].strip()
                    break

        if not pg_pass:
            return CheckResult(
                name="Table Sizes",
                status=Status.UNKNOWN,
                message="Credentials niet beschikbaar"
            )

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

        # Top 5 grootste tabellen
        cursor.execute("""
            SELECT
                tablename,
                pg_size_pretty(pg_total_relation_size(schemaname || '.' || tablename)) as size,
                pg_total_relation_size(schemaname || '.' || tablename) as bytes
            FROM pg_tables
            WHERE schemaname = 'public'
            ORDER BY pg_total_relation_size(schemaname || '.' || tablename) DESC
            LIMIT 5
        """)
        tables = cursor.fetchall()

        # Totale database grootte
        cursor.execute("""
            SELECT pg_size_pretty(pg_database_size('emsn'))
        """)
        total_size = cursor.fetchone()[0]

        conn.close()

        if tables:
            top_tables = ", ".join([f"{t[0]}({t[1]})" for t in tables[:3]])
            return CheckResult(
                name="Database Size",
                status=Status.OK,
                message=f"Totaal: {total_size} | Top: {top_tables}",
                details={'total': total_size, 'tables': [{'name': t[0], 'size': t[1]} for t in tables]}
            )
        else:
            return CheckResult(
                name="Database Size",
                status=Status.OK,
                message=f"Totaal: {total_size}"
            )

    except Exception as e:
        return CheckResult(
            name="Table Sizes",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        )


# ═══════════════════════════════════════════════════════════════
# 20. VOCALIZATION SYSTEEM
# ═══════════════════════════════════════════════════════════════

@timed_check
def check_vocalization_service() -> CheckResult:
    """Check vocalization enricher service status"""
    try:
        result = subprocess.run(
            ['ssh', '-o', 'ConnectTimeout=5', '-o', 'BatchMode=yes',
             f'ronny@{HOSTS["zolder"]["ip"]}',
             '''
             # Check vocalization enricher service
             SERVICE_STATUS=$(systemctl is-active vocalization-enricher.service 2>/dev/null || echo "not-found")

             # Laatste run uit logs
             LAST_RUN=$(journalctl -u vocalization-enricher --since "4 hours ago" --no-pager 2>/dev/null | grep -c "completed" || echo 0)

             # Check of service recent draaide
             LAST_TIME=$(systemctl show vocalization-enricher.service --property=ExecMainExitTimestamp 2>/dev/null | cut -d= -f2)

             echo "STATUS:$SERVICE_STATUS"
             echo "RECENT_RUNS:$LAST_RUN"
             echo "LAST_TIME:$LAST_TIME"
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

            status_val = metrics.get('STATUS', 'unknown')
            recent_runs = int(metrics.get('RECENT_RUNS', 0))

            # Oneshot service, dus inactive is OK als recent gedraaid
            if status_val == 'inactive' and recent_runs > 0:
                return CheckResult(
                    name="Vocalization Service",
                    status=Status.OK,
                    message=f"Oneshot OK ({recent_runs} runs laatste 4u)",
                    details=metrics
                )
            elif status_val == 'active':
                return CheckResult(
                    name="Vocalization Service",
                    status=Status.OK,
                    message="Actief bezig",
                    details=metrics
                )
            elif status_val == 'failed':
                return CheckResult(
                    name="Vocalization Service",
                    status=Status.WARNING,
                    message="Service gefaald",
                    details=metrics
                )
            else:
                return CheckResult(
                    name="Vocalization Service",
                    status=Status.OK,
                    message=f"Status: {status_val}",
                    details=metrics
                )

        return CheckResult(
            name="Vocalization Service",
            status=Status.UNKNOWN,
            message="Kan service niet controleren"
        )

    except Exception as e:
        return CheckResult(
            name="Vocalization Service",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        )


@timed_check
def check_vocalization_docker() -> CheckResult:
    """Check vocalization Docker container op NAS"""
    try:
        # Check of container draait via SSH naar NAS
        result = subprocess.run(
            ['ssh', '-o', 'ConnectTimeout=5', '-o', 'BatchMode=yes',
             'ronny@192.168.1.25',
             'sudo docker ps --filter "name=emsn-vocalization" --format "{{.Status}}" 2>/dev/null || echo "not-found"'],
            capture_output=True,
            text=True,
            timeout=15
        )

        if result.returncode == 0:
            status_output = result.stdout.strip()
            if 'Up' in status_output:
                return CheckResult(
                    name="Vocalization Docker",
                    status=Status.OK,
                    message=f"Container: {status_output[:30]}"
                )
            elif 'not-found' in status_output or not status_output:
                return CheckResult(
                    name="Vocalization Docker",
                    status=Status.WARNING,
                    message="Container niet gevonden"
                )
            else:
                return CheckResult(
                    name="Vocalization Docker",
                    status=Status.WARNING,
                    message=f"Container status: {status_output[:30]}"
                )

        return CheckResult(
            name="Vocalization Docker",
            status=Status.UNKNOWN,
            message="Kan Docker niet controleren"
        )

    except Exception as e:
        return CheckResult(
            name="Vocalization Docker",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        )


@timed_check
def check_vocalization_enrichment_rate() -> CheckResult:
    """Check hoeveel detecties vocalization type hebben"""
    try:
        secrets_file = Path("/home/ronny/emsn2/.secrets")
        pg_pass = None
        with open(secrets_file) as f:
            for line in f:
                if line.startswith('PG_PASSWORD='):
                    pg_pass = line.split('=', 1)[1].strip()
                    break

        if not pg_pass:
            return CheckResult(
                name="Vocalization Rate",
                status=Status.UNKNOWN,
                message="Credentials niet beschikbaar"
            )

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

        # Check enrichment rate laatste 7 dagen
        cursor.execute("""
            SELECT
                COUNT(*) as total,
                COUNT(vocalization_type) as enriched,
                ROUND(COUNT(vocalization_type)::numeric / NULLIF(COUNT(*), 0) * 100, 1) as pct
            FROM bird_detections
            WHERE detection_timestamp >= NOW() - INTERVAL '7 days'
        """)
        row = cursor.fetchone()
        conn.close()

        if row:
            total, enriched, pct = row
            pct = float(pct or 0)

            if pct >= 80:
                return CheckResult(
                    name="Vocalization Rate",
                    status=Status.OK,
                    message=f"{pct}% verrijkt ({enriched}/{total} laatste 7d)",
                    details={'total': total, 'enriched': enriched, 'percentage': pct}
                )
            elif pct >= 50:
                return CheckResult(
                    name="Vocalization Rate",
                    status=Status.OK,
                    message=f"{pct}% verrijkt (werk in gang)",
                    details={'total': total, 'enriched': enriched, 'percentage': pct}
                )
            else:
                return CheckResult(
                    name="Vocalization Rate",
                    status=Status.WARNING,
                    message=f"Slechts {pct}% verrijkt",
                    details={'total': total, 'enriched': enriched, 'percentage': pct}
                )

        return CheckResult(
            name="Vocalization Rate",
            status=Status.UNKNOWN,
            message="Geen data"
        )

    except Exception as e:
        return CheckResult(
            name="Vocalization Rate",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        )


# ═══════════════════════════════════════════════════════════════
# 21. FLYSAFE RADAR & MIGRATIE
# ═══════════════════════════════════════════════════════════════

@timed_check
def check_flysafe_scraper() -> CheckResult:
    """Check FlySafe radar scraper service"""
    try:
        result = subprocess.run(
            ['ssh', '-o', 'ConnectTimeout=5', '-o', 'BatchMode=yes',
             f'ronny@{HOSTS["zolder"]["ip"]}',
             '''
             # Check FlySafe timer status
             TIMER_STATUS=$(systemctl is-active flysafe-radar-day.timer 2>/dev/null || echo "not-found")

             # Check laatste run
             LAST_RUN=$(systemctl show flysafe-radar.service --property=ExecMainExitTimestamp 2>/dev/null | cut -d= -f2)

             echo "TIMER:$TIMER_STATUS"
             echo "LAST_RUN:$LAST_RUN"
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

            timer_status = metrics.get('TIMER', 'unknown')

            if timer_status == 'active':
                return CheckResult(
                    name="FlySafe Scraper",
                    status=Status.OK,
                    message="Timer actief",
                    details=metrics
                )
            else:
                return CheckResult(
                    name="FlySafe Scraper",
                    status=Status.WARNING,
                    message=f"Timer: {timer_status}",
                    details=metrics
                )

        return CheckResult(
            name="FlySafe Scraper",
            status=Status.UNKNOWN,
            message="Kan niet controleren"
        )

    except Exception as e:
        return CheckResult(
            name="FlySafe Scraper",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        )


@timed_check
def check_migration_data() -> CheckResult:
    """Check laatste radar/migratie data"""
    try:
        secrets_file = Path("/home/ronny/emsn2/.secrets")
        pg_pass = None
        with open(secrets_file) as f:
            for line in f:
                if line.startswith('PG_PASSWORD='):
                    pg_pass = line.split('=', 1)[1].strip()
                    break

        if not pg_pass:
            return CheckResult(
                name="Migration Data",
                status=Status.UNKNOWN,
                message="Credentials niet beschikbaar"
            )

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

        # Check of radar_observations tabel bestaat en data heeft
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'radar_observations'
            )
        """)
        table_exists = cursor.fetchone()[0]

        if table_exists:
            cursor.execute("""
                SELECT
                    MAX(observation_time) as last_obs,
                    COUNT(*) as total,
                    EXTRACT(EPOCH FROM (NOW() - MAX(observation_time)))/3600 as hours_ago
                FROM radar_observations
            """)
            row = cursor.fetchone()

            if row and row[0]:
                hours_ago = float(row[2] or 999)
                total = row[1]

                if hours_ago < 24:
                    return CheckResult(
                        name="Radar Data",
                        status=Status.OK,
                        message=f"Laatste: {hours_ago:.1f}u geleden ({total} totaal)"
                    )
                else:
                    return CheckResult(
                        name="Radar Data",
                        status=Status.WARNING,
                        message=f"Laatste: {hours_ago:.1f}u geleden"
                    )
            else:
                return CheckResult(
                    name="Radar Data",
                    status=Status.OK,
                    message="Tabel leeg (nieuw systeem)"
                )
        else:
            return CheckResult(
                name="Radar Data",
                status=Status.OK,
                message="Tabel niet aangemaakt"
            )

        conn.close()

    except Exception as e:
        return CheckResult(
            name="Radar Data",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        )


# ═══════════════════════════════════════════════════════════════
# 22. NESTKAST AI DETECTIE
# ═══════════════════════════════════════════════════════════════

@timed_check
def check_nestbox_models() -> CheckResult:
    """Check nestkast AI model beschikbaarheid"""
    try:
        models_path = Path("/mnt/nas-birdnet-archive/nestbox/models")
        occupancy_model = models_path / "nestbox_occupancy_model.pt"
        species_model = models_path / "nestbox_species_model.pt"

        issues = []
        if not models_path.exists():
            return CheckResult(
                name="Nestkast Models",
                status=Status.WARNING,
                message="Models directory niet gevonden"
            )

        if not occupancy_model.exists():
            issues.append("occupancy model ontbreekt")
        if not species_model.exists():
            issues.append("species model ontbreekt")

        if issues:
            return CheckResult(
                name="Nestkast Models",
                status=Status.WARNING,
                message=", ".join(issues)
            )
        else:
            # Get model sizes
            occ_size = occupancy_model.stat().st_size / 1024 / 1024
            spec_size = species_model.stat().st_size / 1024 / 1024
            return CheckResult(
                name="Nestkast Models",
                status=Status.OK,
                message=f"Occupancy ({occ_size:.1f}MB), Species ({spec_size:.1f}MB)"
            )

    except Exception as e:
        return CheckResult(
            name="Nestkast Models",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        )


@timed_check
def check_nestbox_events() -> CheckResult:
    """Check nestkast events activiteit"""
    try:
        secrets_file = Path("/home/ronny/emsn2/.secrets")
        pg_pass = None
        with open(secrets_file) as f:
            for line in f:
                if line.startswith('PG_PASSWORD='):
                    pg_pass = line.split('=', 1)[1].strip()
                    break

        if not pg_pass:
            return CheckResult(
                name="Nestkast Events",
                status=Status.UNKNOWN,
                message="Credentials niet beschikbaar"
            )

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

        # Check events per nestkast
        cursor.execute("""
            SELECT
                nestbox_id,
                COUNT(*) as events,
                MAX(event_timestamp) as last_event
            FROM nestbox_events
            GROUP BY nestbox_id
        """)
        rows = cursor.fetchall()
        conn.close()

        if rows:
            summary = []
            for nestbox_id, count, last_event in rows:
                summary.append(f"{nestbox_id}:{count}")

            return CheckResult(
                name="Nestkast Events",
                status=Status.OK,
                message=f"Events: {', '.join(summary)}",
                details={'per_nestbox': {r[0]: r[1] for r in rows}}
            )
        else:
            return CheckResult(
                name="Nestkast Events",
                status=Status.OK,
                message="Geen events (nieuw seizoen)"
            )

    except Exception as e:
        return CheckResult(
            name="Nestkast Events",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        )


@timed_check
def check_nestbox_screenshots_today() -> CheckResult:
    """Check nestkast screenshots vandaag"""
    try:
        base_path = Path("/mnt/nas-birdnet-archive/nestbox")
        today = datetime.now().strftime('%Y-%m-%d')

        total_today = 0
        per_box = {}

        for nestbox in ['voor', 'midden', 'achter']:
            screenshots_dir = base_path / nestbox / 'screenshots'
            if screenshots_dir.exists():
                # Tel screenshots van vandaag
                count = len(list(screenshots_dir.glob(f'*{today}*.jpg')))
                per_box[nestbox] = count
                total_today += count

        if total_today > 0:
            summary = ", ".join([f"{k}:{v}" for k, v in per_box.items() if v > 0])
            return CheckResult(
                name="Screenshots Vandaag",
                status=Status.OK,
                message=f"{total_today} totaal ({summary})",
                details=per_box
            )
        else:
            return CheckResult(
                name="Screenshots Vandaag",
                status=Status.WARNING,
                message="Geen screenshots vandaag",
                details=per_box
            )

    except Exception as e:
        return CheckResult(
            name="Screenshots Vandaag",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        )


# ═══════════════════════════════════════════════════════════════
# 23. RAPPORT GENERATIE
# ═══════════════════════════════════════════════════════════════

@timed_check
def check_report_timers() -> List[CheckResult]:
    """Check rapport timer status"""
    results = []
    report_timers = [
        ('emsn-weekly-report.timer', 'Weekly Report'),
        ('emsn-monthly-report.timer', 'Monthly Report'),
        ('emsn-yearly-report.timer', 'Yearly Report'),
    ]

    try:
        for timer, name in report_timers:
            result = subprocess.run(
                ['ssh', '-o', 'ConnectTimeout=5', '-o', 'BatchMode=yes',
                 f'ronny@{HOSTS["zolder"]["ip"]}',
                 f'systemctl is-active {timer} 2>/dev/null || echo "not-found"'],
                capture_output=True,
                text=True,
                timeout=10
            )

            status_val = result.stdout.strip()
            if status_val == 'active':
                results.append(CheckResult(
                    name=f"{name} Timer",
                    status=Status.OK,
                    message="Actief"
                ))
            else:
                results.append(CheckResult(
                    name=f"{name} Timer",
                    status=Status.WARNING,
                    message=f"Status: {status_val}"
                ))

    except Exception as e:
        results.append(CheckResult(
            name="Report Timers",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        ))

    return results


@timed_check
def check_reports_directory() -> CheckResult:
    """Check rapport output directory"""
    try:
        reports_dir = Path("/mnt/nas-reports")

        if not reports_dir.exists():
            return CheckResult(
                name="Reports Directory",
                status=Status.CRITICAL,
                message="NAS reports niet gemount"
            )

        # Tel rapporten
        pdf_count = len(list(reports_dir.glob('**/*.pdf')))
        html_count = len(list(reports_dir.glob('**/*.html')))

        # Check vrije ruimte
        import shutil
        total, used, free = shutil.disk_usage(reports_dir)
        free_gb = free / (1024**3)

        return CheckResult(
            name="Reports Directory",
            status=Status.OK,
            message=f"{pdf_count} PDFs, {html_count} HTML ({free_gb:.1f}GB vrij)",
            details={'pdfs': pdf_count, 'htmls': html_count, 'free_gb': free_gb}
        )

    except Exception as e:
        return CheckResult(
            name="Reports Directory",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        )


# ═══════════════════════════════════════════════════════════════
# 24. ANOMALY DETECTION SYSTEEM
# ═══════════════════════════════════════════════════════════════

@timed_check
def check_anomaly_services() -> List[CheckResult]:
    """Check anomaly detection services"""
    results = []
    anomaly_timers = [
        ('anomaly-hardware-check.timer', 'Hardware Checker'),
        ('anomaly-datagap-check.timer', 'Data Gap Checker'),
        ('anomaly-baseline-learn.timer', 'Baseline Learner'),
    ]

    try:
        for timer, name in anomaly_timers:
            result = subprocess.run(
                ['ssh', '-o', 'ConnectTimeout=5', '-o', 'BatchMode=yes',
                 f'ronny@{HOSTS["zolder"]["ip"]}',
                 f'systemctl is-active {timer} 2>/dev/null || echo "not-found"'],
                capture_output=True,
                text=True,
                timeout=10
            )

            status_val = result.stdout.strip()
            if status_val == 'active':
                results.append(CheckResult(
                    name=f"{name}",
                    status=Status.OK,
                    message="Timer actief"
                ))
            else:
                results.append(CheckResult(
                    name=f"{name}",
                    status=Status.WARNING,
                    message=f"Timer: {status_val}"
                ))

    except Exception as e:
        results.append(CheckResult(
            name="Anomaly Services",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        ))

    return results


@timed_check
def check_active_anomalies() -> CheckResult:
    """Check actieve anomalieën in database"""
    try:
        secrets_file = Path("/home/ronny/emsn2/.secrets")
        pg_pass = None
        with open(secrets_file) as f:
            for line in f:
                if line.startswith('PG_PASSWORD='):
                    pg_pass = line.split('=', 1)[1].strip()
                    break

        if not pg_pass:
            return CheckResult(
                name="Active Anomalies",
                status=Status.UNKNOWN,
                message="Credentials niet beschikbaar"
            )

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

        # Check of anomalies tabel bestaat
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'anomalies'
            )
        """)
        table_exists = cursor.fetchone()[0]

        if not table_exists:
            conn.close()
            return CheckResult(
                name="Anomaly Status",
                status=Status.OK,
                message="Anomaly tabel nog niet aangemaakt"
            )

        # Tel actieve anomalies per severity
        cursor.execute("""
            SELECT
                severity,
                COUNT(*)
            FROM anomalies
            WHERE resolved_at IS NULL
            GROUP BY severity
        """)
        rows = cursor.fetchall()
        conn.close()

        if rows:
            severity_counts = {r[0]: r[1] for r in rows}
            critical = severity_counts.get('critical', 0)
            warning = severity_counts.get('warning', 0)

            if critical > 0:
                return CheckResult(
                    name="Anomaly Status",
                    status=Status.CRITICAL,
                    message=f"{critical} kritiek, {warning} waarschuwingen",
                    details=severity_counts
                )
            elif warning > 0:
                return CheckResult(
                    name="Anomaly Status",
                    status=Status.WARNING,
                    message=f"{warning} actieve waarschuwingen",
                    details=severity_counts
                )
            else:
                return CheckResult(
                    name="Anomaly Status",
                    status=Status.OK,
                    message="Geen actieve anomalieën"
                )
        else:
            return CheckResult(
                name="Anomaly Status",
                status=Status.OK,
                message="Geen actieve anomalieën"
            )

    except Exception as e:
        return CheckResult(
            name="Anomaly Status",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        )


# ═══════════════════════════════════════════════════════════════
# 25. AUDIO & MICROFOON KWALITEIT
# ═══════════════════════════════════════════════════════════════

@timed_check
def check_audio_device(host: str, ip: str) -> CheckResult:
    """Check ALSA audio device status"""
    try:
        result = subprocess.run(
            ['ssh', '-o', 'ConnectTimeout=5', '-o', 'BatchMode=yes',
             f'ronny@{ip}',
             '''
             # Check ALSA capture devices
             CAPTURE_DEVICES=$(arecord -l 2>/dev/null | grep -c "card" || echo 0)

             # Check of USB audio device aanwezig is
             USB_AUDIO=$(lsusb 2>/dev/null | grep -ci "audio\|sound\|microphone" || echo 0)

             # Check ALSA volume levels
             AMIXER_OUTPUT=$(amixer -c 0 sget Capture 2>/dev/null | grep -o "[0-9]*%" | head -1 || echo "unknown")

             echo "CAPTURE_DEVICES:$CAPTURE_DEVICES"
             echo "USB_AUDIO:$USB_AUDIO"
             echo "VOLUME:$AMIXER_OUTPUT"
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

            capture_devices = int(metrics.get('CAPTURE_DEVICES', 0))
            usb_audio = int(metrics.get('USB_AUDIO', 0))
            volume = metrics.get('VOLUME', 'unknown')

            if capture_devices == 0:
                return CheckResult(
                    name=f"{host} Audio",
                    status=Status.CRITICAL,
                    message="Geen capture devices gevonden!",
                    details=metrics
                )
            elif usb_audio == 0 and host in ['zolder', 'berging']:
                return CheckResult(
                    name=f"{host} Audio",
                    status=Status.WARNING,
                    message="USB audio device niet gevonden",
                    details=metrics
                )
            else:
                return CheckResult(
                    name=f"{host} Audio",
                    status=Status.OK,
                    message=f"{capture_devices} device(s), volume: {volume}",
                    details=metrics
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


@timed_check
def check_day_night_ratio() -> CheckResult:
    """Check dag/nacht detectie ratio (indicator voor microfoon gezondheid)"""
    try:
        secrets_file = Path("/home/ronny/emsn2/.secrets")
        pg_pass = None
        with open(secrets_file) as f:
            for line in f:
                if line.startswith('PG_PASSWORD='):
                    pg_pass = line.split('=', 1)[1].strip()
                    break

        if not pg_pass:
            return CheckResult(
                name="Dag/Nacht Ratio",
                status=Status.UNKNOWN,
                message="Credentials niet beschikbaar"
            )

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

        # Tel dag (6-22) vs nacht (22-6) detecties laatste 7 dagen
        cursor.execute("""
            SELECT
                CASE
                    WHEN EXTRACT(HOUR FROM detection_timestamp) BETWEEN 6 AND 21 THEN 'dag'
                    ELSE 'nacht'
                END as period,
                COUNT(*)
            FROM bird_detections
            WHERE detection_timestamp >= NOW() - INTERVAL '7 days'
            GROUP BY period
        """)
        rows = cursor.fetchall()
        conn.close()

        if rows:
            periods = {r[0]: r[1] for r in rows}
            day_count = periods.get('dag', 0)
            night_count = periods.get('nacht', 0)
            total = day_count + night_count

            if total > 0:
                day_pct = (day_count / total) * 100

                # Normale ratio is 80-95% overdag
                if 75 <= day_pct <= 98:
                    return CheckResult(
                        name="Dag/Nacht Ratio",
                        status=Status.OK,
                        message=f"{day_pct:.1f}% dag / {100-day_pct:.1f}% nacht",
                        details={'dag': day_count, 'nacht': night_count}
                    )
                elif day_pct < 75:
                    return CheckResult(
                        name="Dag/Nacht Ratio",
                        status=Status.WARNING,
                        message=f"Veel nachtdetecties ({100-day_pct:.1f}%) - check ruis",
                        details={'dag': day_count, 'nacht': night_count}
                    )
                else:
                    return CheckResult(
                        name="Dag/Nacht Ratio",
                        status=Status.OK,
                        message=f"{day_pct:.1f}% dag (winter patroon?)",
                        details={'dag': day_count, 'nacht': night_count}
                    )

        return CheckResult(
            name="Dag/Nacht Ratio",
            status=Status.OK,
            message="Onvoldoende data"
        )

    except Exception as e:
        return CheckResult(
            name="Dag/Nacht Ratio",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        )


# ═══════════════════════════════════════════════════════════════
# 26. BACKUP & ARCHIVERING
# ═══════════════════════════════════════════════════════════════

@timed_check
def check_sd_backup_timers() -> List[CheckResult]:
    """Check SD backup timer status"""
    results = []
    backup_timers = [
        ('sd-backup-daily.timer', 'Daily Backup', 'zolder'),
        ('sd-backup-daily.timer', 'Daily Backup', 'berging'),
        ('sd-backup-weekly.timer', 'Weekly Backup', 'zolder'),
    ]

    for timer, name, host in backup_timers:
        try:
            result = subprocess.run(
                ['ssh', '-o', 'ConnectTimeout=5', '-o', 'BatchMode=yes',
                 f'ronny@{HOSTS[host]["ip"]}',
                 f'systemctl is-active {timer} 2>/dev/null || echo "not-found"'],
                capture_output=True,
                text=True,
                timeout=10
            )

            status_val = result.stdout.strip()
            if status_val == 'active':
                results.append(CheckResult(
                    name=f"{host} {name}",
                    status=Status.OK,
                    message="Timer actief"
                ))
            elif status_val == 'not-found':
                results.append(CheckResult(
                    name=f"{host} {name}",
                    status=Status.OK,
                    message="Timer niet geconfigureerd"
                ))
            else:
                results.append(CheckResult(
                    name=f"{host} {name}",
                    status=Status.WARNING,
                    message=f"Timer: {status_val}"
                ))

        except Exception as e:
            results.append(CheckResult(
                name=f"{host} {name}",
                status=Status.UNKNOWN,
                message=f"Fout: {e}"
            ))

    return results


@timed_check
def check_archive_sync() -> CheckResult:
    """Check BirdNET archive sync status"""
    try:
        result = subprocess.run(
            ['ssh', '-o', 'ConnectTimeout=5', '-o', 'BatchMode=yes',
             f'ronny@{HOSTS["zolder"]["ip"]}',
             '''
             # Check birdnet-archive-sync timer
             TIMER_STATUS=$(systemctl is-active birdnet-archive-sync.timer 2>/dev/null || echo "not-found")

             # Laatste sync tijd
             LAST_SYNC=$(systemctl show birdnet-archive-sync.service --property=ExecMainExitTimestamp 2>/dev/null | cut -d= -f2)

             echo "TIMER:$TIMER_STATUS"
             echo "LAST_SYNC:$LAST_SYNC"
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

            timer_status = metrics.get('TIMER', 'unknown')

            if timer_status == 'active':
                return CheckResult(
                    name="Archive Sync",
                    status=Status.OK,
                    message="Timer actief",
                    details=metrics
                )
            else:
                return CheckResult(
                    name="Archive Sync",
                    status=Status.WARNING,
                    message=f"Timer: {timer_status}",
                    details=metrics
                )

        return CheckResult(
            name="Archive Sync",
            status=Status.UNKNOWN,
            message="Kan niet controleren"
        )

    except Exception as e:
        return CheckResult(
            name="Archive Sync",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        )


@timed_check
def check_archive_space() -> CheckResult:
    """Check beschikbare ruimte op archive"""
    try:
        archive_path = Path("/mnt/nas-birdnet-archive")

        if not archive_path.exists():
            return CheckResult(
                name="Archive Space",
                status=Status.CRITICAL,
                message="Archive niet gemount"
            )

        import shutil
        total, used, free = shutil.disk_usage(archive_path)
        total_tb = total / (1024**4)
        free_tb = free / (1024**4)
        used_pct = (used / total) * 100

        if used_pct > 90:
            return CheckResult(
                name="Archive Space",
                status=Status.CRITICAL,
                message=f"{used_pct:.1f}% vol ({free_tb:.2f}TB vrij van {total_tb:.2f}TB)"
            )
        elif used_pct > 80:
            return CheckResult(
                name="Archive Space",
                status=Status.WARNING,
                message=f"{used_pct:.1f}% vol ({free_tb:.2f}TB vrij)"
            )
        else:
            return CheckResult(
                name="Archive Space",
                status=Status.OK,
                message=f"{free_tb:.2f}TB vrij ({100-used_pct:.1f}%)"
            )

    except Exception as e:
        return CheckResult(
            name="Archive Space",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        )


# ═══════════════════════════════════════════════════════════════
# 27. NETWERK DIEPTE
# ═══════════════════════════════════════════════════════════════

@timed_check
def check_packet_loss(host: str, ip: str) -> CheckResult:
    """Check packet loss naar host"""
    try:
        result = subprocess.run(
            ['ping', '-c', '10', '-W', '1', ip],
            capture_output=True,
            text=True,
            timeout=15
        )

        output = result.stdout

        # Parse packet loss percentage
        if 'packet loss' in output:
            loss_match = output.split('packet loss')[0].split()[-1]
            loss_pct = float(loss_match.replace('%', '').replace(',', ''))

            if loss_pct == 0:
                return CheckResult(
                    name=f"{host} Packet Loss",
                    status=Status.OK,
                    message="0% verlies (10 pings)"
                )
            elif loss_pct < 10:
                return CheckResult(
                    name=f"{host} Packet Loss",
                    status=Status.WARNING,
                    message=f"{loss_pct}% verlies"
                )
            else:
                return CheckResult(
                    name=f"{host} Packet Loss",
                    status=Status.CRITICAL,
                    message=f"{loss_pct}% verlies!"
                )

        return CheckResult(
            name=f"{host} Packet Loss",
            status=Status.UNKNOWN,
            message="Kon packet loss niet bepalen"
        )

    except subprocess.TimeoutExpired:
        return CheckResult(
            name=f"{host} Packet Loss",
            status=Status.CRITICAL,
            message="Ping timeout"
        )
    except Exception as e:
        return CheckResult(
            name=f"{host} Packet Loss",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        )


@timed_check
def check_dns_resolution() -> CheckResult:
    """Check DNS resolution performance"""
    try:
        import time

        domains = ['google.com', 'github.com', 'anthropic.com']
        times = []

        for domain in domains:
            start = time.time()
            try:
                socket.gethostbyname(domain)
                elapsed = (time.time() - start) * 1000
                times.append(elapsed)
            except socket.gaierror:
                pass

        if times:
            avg_time = sum(times) / len(times)
            if avg_time < 50:
                return CheckResult(
                    name="DNS Resolution",
                    status=Status.OK,
                    message=f"Gemiddeld {avg_time:.1f}ms ({len(times)}/{len(domains)} succesvol)"
                )
            elif avg_time < 200:
                return CheckResult(
                    name="DNS Resolution",
                    status=Status.WARNING,
                    message=f"Traag: {avg_time:.1f}ms gemiddeld"
                )
            else:
                return CheckResult(
                    name="DNS Resolution",
                    status=Status.CRITICAL,
                    message=f"Zeer traag: {avg_time:.1f}ms"
                )
        else:
            return CheckResult(
                name="DNS Resolution",
                status=Status.CRITICAL,
                message="Alle DNS lookups gefaald"
            )

    except Exception as e:
        return CheckResult(
            name="DNS Resolution",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        )


@timed_check
def check_gateway() -> CheckResult:
    """Check default gateway bereikbaarheid"""
    try:
        # Get default gateway
        result = subprocess.run(
            ['ip', 'route', 'show', 'default'],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0 and 'via' in result.stdout:
            gateway = result.stdout.split('via')[1].split()[0]

            # Ping gateway
            ping_result = subprocess.run(
                ['ping', '-c', '3', '-W', '1', gateway],
                capture_output=True,
                text=True,
                timeout=10
            )

            if ping_result.returncode == 0:
                # Parse latency
                if 'avg' in ping_result.stdout:
                    avg_match = ping_result.stdout.split('/')[-3]
                    avg_latency = float(avg_match)
                    return CheckResult(
                        name="Gateway",
                        status=Status.OK,
                        message=f"{gateway} bereikbaar ({avg_latency:.1f}ms)"
                    )
                return CheckResult(
                    name="Gateway",
                    status=Status.OK,
                    message=f"{gateway} bereikbaar"
                )
            else:
                return CheckResult(
                    name="Gateway",
                    status=Status.CRITICAL,
                    message=f"Gateway {gateway} niet bereikbaar!"
                )

        return CheckResult(
            name="Gateway",
            status=Status.WARNING,
            message="Geen default gateway gevonden"
        )

    except Exception as e:
        return CheckResult(
            name="Gateway",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        )


# ═══════════════════════════════════════════════════════════════
# 28. REALTIME SERVICES
# ═══════════════════════════════════════════════════════════════

@timed_check
def check_realtime_dual_detection() -> CheckResult:
    """Check realtime dual detection service"""
    try:
        result = subprocess.run(
            ['ssh', '-o', 'ConnectTimeout=5', '-o', 'BatchMode=yes',
             f'ronny@{HOSTS["zolder"]["ip"]}',
             '''
             # Check realtime dual detection service
             SERVICE_STATUS=$(systemctl is-active realtime-dual-detection.service 2>/dev/null || echo "not-found")

             # Check of proces draait
             PROC_COUNT=$(pgrep -c -f "realtime_dual_detection" 2>/dev/null || echo 0)

             # Laatste logs
             LAST_DUAL=$(journalctl -u realtime-dual-detection --since "1 hour ago" --no-pager 2>/dev/null | grep -c "DUAL" || echo 0)

             echo "STATUS:$SERVICE_STATUS"
             echo "PROCS:$PROC_COUNT"
             echo "RECENT_DUALS:$LAST_DUAL"
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

            status_val = metrics.get('STATUS', 'unknown')
            procs = int(metrics.get('PROCS', 0))
            recent_duals = int(metrics.get('RECENT_DUALS', 0))

            if status_val == 'active' and procs > 0:
                return CheckResult(
                    name="Realtime Dual Detection",
                    status=Status.OK,
                    message=f"Actief ({recent_duals} duals laatste uur)",
                    details=metrics
                )
            elif status_val == 'active':
                return CheckResult(
                    name="Realtime Dual Detection",
                    status=Status.WARNING,
                    message="Service actief maar geen proces",
                    details=metrics
                )
            elif status_val == 'not-found':
                return CheckResult(
                    name="Realtime Dual Detection",
                    status=Status.OK,
                    message="Service niet geconfigureerd",
                    details=metrics
                )
            else:
                return CheckResult(
                    name="Realtime Dual Detection",
                    status=Status.WARNING,
                    message=f"Status: {status_val}",
                    details=metrics
                )

        return CheckResult(
            name="Realtime Dual Detection",
            status=Status.UNKNOWN,
            message="Kan niet controleren"
        )

    except Exception as e:
        return CheckResult(
            name="Realtime Dual Detection",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        )


@timed_check
def check_mqtt_message_rate() -> CheckResult:
    """Check MQTT message rate"""
    try:
        secrets_file = Path("/home/ronny/emsn2/.secrets")
        pg_pass = None
        with open(secrets_file) as f:
            for line in f:
                if line.startswith('PG_PASSWORD='):
                    pg_pass = line.split('=', 1)[1].strip()
                    break

        if not pg_pass:
            return CheckResult(
                name="MQTT Rate",
                status=Status.UNKNOWN,
                message="Credentials niet beschikbaar"
            )

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

        # Tel detecties per uur laatste 6 uur
        cursor.execute("""
            SELECT
                DATE_TRUNC('hour', detection_timestamp) as hour,
                station,
                COUNT(*)
            FROM bird_detections
            WHERE detection_timestamp >= NOW() - INTERVAL '6 hours'
            GROUP BY hour, station
            ORDER BY hour DESC
        """)
        rows = cursor.fetchall()
        conn.close()

        if rows:
            # Bereken gemiddelde per station
            per_station = {}
            for hour, station, count in rows:
                if station not in per_station:
                    per_station[station] = []
                per_station[station].append(count)

            summary = []
            for station, counts in per_station.items():
                avg = sum(counts) / len(counts) if counts else 0
                summary.append(f"{station}:{avg:.0f}/u")

            return CheckResult(
                name="Detection Rate",
                status=Status.OK,
                message=f"Gemiddeld: {', '.join(summary)}",
                details=per_station
            )

        return CheckResult(
            name="Detection Rate",
            status=Status.WARNING,
            message="Geen recente detecties"
        )

    except Exception as e:
        return CheckResult(
            name="Detection Rate",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        )


@timed_check
def check_ulanzi_notifications() -> CheckResult:
    """Check Ulanzi notificatie frequentie"""
    try:
        # Check logs van ulanzi-bridge
        result = subprocess.run(
            ['ssh', '-o', 'ConnectTimeout=5', '-o', 'BatchMode=yes',
             f'ronny@{HOSTS["zolder"]["ip"]}',
             '''
             # Tel notificaties vandaag
             TODAY=$(date +%Y%m%d)
             LOG_FILE="/mnt/usb/logs/ulanzi_bridge_${TODAY}.log"

             if [ -f "$LOG_FILE" ]; then
                 NOTIF_COUNT=$(grep -c "Sending notification" "$LOG_FILE" 2>/dev/null || echo 0)
                 FILTERED_COUNT=$(grep -c "Filtered" "$LOG_FILE" 2>/dev/null || echo 0)
                 echo "NOTIFICATIONS:$NOTIF_COUNT"
                 echo "FILTERED:$FILTERED_COUNT"
             else
                 echo "NOTIFICATIONS:0"
                 echo "FILTERED:0"
             fi
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

            notifications = int(metrics.get('NOTIFICATIONS', 0))
            filtered = int(metrics.get('FILTERED', 0))

            return CheckResult(
                name="Ulanzi Notificaties",
                status=Status.OK,
                message=f"{notifications} verzonden, {filtered} gefilterd vandaag",
                details=metrics
            )

        return CheckResult(
            name="Ulanzi Notificaties",
            status=Status.UNKNOWN,
            message="Kan logs niet lezen"
        )

    except Exception as e:
        return CheckResult(
            name="Ulanzi Notificaties",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        )


# ═══════════════════════════════════════════════════════════════
# 29. AUTO-DISCOVERY & NIEUWE FEATURES
# ═══════════════════════════════════════════════════════════════

def matches_emsn_pattern(service_name: str) -> bool:
    """Check of een service naam matcht met EMSN patronen"""
    import fnmatch
    for pattern in EMSN_SERVICE_PATTERNS:
        if fnmatch.fnmatch(service_name, pattern):
            return True
    return False


@timed_check
def discover_services(host: str, ip: str) -> Tuple[List[str], List[str], List[str]]:
    """
    Ontdek alle EMSN-gerelateerde services op een host.
    Retourneert: (alle_services, bekende_services, nieuwe_services)
    """
    try:
        # Haal alle services en timers op
        result = subprocess.run(
            ['ssh', '-o', 'ConnectTimeout=5', '-o', 'BatchMode=yes',
             f'ronny@{ip}',
             '''
             # Lijst alle services en timers
             systemctl list-units --type=service --all --plain --no-legend 2>/dev/null | awk '{print $1}'
             systemctl list-units --type=timer --all --plain --no-legend 2>/dev/null | awk '{print $1}'
             systemctl list-unit-files --type=service --plain --no-legend 2>/dev/null | awk '{print $1}'
             systemctl list-unit-files --type=timer --plain --no-legend 2>/dev/null | awk '{print $1}'
             '''],
            capture_output=True,
            text=True,
            timeout=20
        )

        if result.returncode != 0:
            return [], [], []

        # Parse alle units
        all_units = set()
        for line in result.stdout.strip().split('\n'):
            unit = line.strip()
            if unit and (unit.endswith('.service') or unit.endswith('.timer')):
                all_units.add(unit)

        # Filter op EMSN patronen
        emsn_services = [s for s in all_units if matches_emsn_pattern(s)]

        # Vergelijk met bekende services
        known = set(KNOWN_SERVICES.get(host, []))
        nieuwe = [s for s in emsn_services if s not in known]
        bekende = [s for s in emsn_services if s in known]

        return sorted(emsn_services), sorted(bekende), sorted(nieuwe)

    except Exception as e:
        return [], [], []


@timed_check
def check_new_services(host: str, ip: str) -> CheckResult:
    """Check voor nieuwe/onbekende EMSN services"""
    try:
        alle, bekende, nieuwe = discover_services(host, ip)

        if nieuwe:
            return CheckResult(
                name=f"{host} Nieuwe Services",
                status=Status.WARNING,
                message=f"{len(nieuwe)} nieuwe: {', '.join(nieuwe[:3])}{'...' if len(nieuwe) > 3 else ''}",
                details={
                    'nieuwe_services': nieuwe,
                    'totaal_emsn': len(alle),
                    'bekende': len(bekende),
                    'actie': 'Voeg toe aan KNOWN_SERVICES en maak specifieke checks'
                }
            )
        elif alle:
            return CheckResult(
                name=f"{host} Service Discovery",
                status=Status.OK,
                message=f"Alle {len(alle)} EMSN services bekend",
                details={'services': bekende}
            )
        else:
            return CheckResult(
                name=f"{host} Service Discovery",
                status=Status.UNKNOWN,
                message="Geen EMSN services gevonden"
            )

    except Exception as e:
        return CheckResult(
            name=f"{host} Service Discovery",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        )


@timed_check
def check_new_database_tables() -> CheckResult:
    """Check voor nieuwe database tabellen die niet gemonitord worden"""
    try:
        secrets_file = Path("/home/ronny/emsn2/.secrets")
        pg_pass = None
        with open(secrets_file) as f:
            for line in f:
                if line.startswith('PG_PASSWORD='):
                    pg_pass = line.split('=', 1)[1].strip()
                    break

        if not pg_pass:
            return CheckResult(
                name="Database Tables Discovery",
                status=Status.UNKNOWN,
                message="Credentials niet beschikbaar"
            )

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

        # Haal alle tabellen op
        cursor.execute("""
            SELECT tablename
            FROM pg_tables
            WHERE schemaname = 'public'
            ORDER BY tablename
        """)
        all_tables = [row[0] for row in cursor.fetchall()]
        conn.close()

        # Vergelijk met bekende tabellen
        known = set(KNOWN_DATABASE_TABLES)
        nieuwe = [t for t in all_tables if t not in known]

        # Filter system tabellen
        system_prefixes = ['pg_', 'sql_', 'information_']
        nieuwe = [t for t in nieuwe if not any(t.startswith(p) for p in system_prefixes)]

        if nieuwe:
            return CheckResult(
                name="Nieuwe DB Tabellen",
                status=Status.WARNING,
                message=f"{len(nieuwe)} onbekend: {', '.join(nieuwe[:3])}{'...' if len(nieuwe) > 3 else ''}",
                details={
                    'nieuwe_tabellen': nieuwe,
                    'totaal': len(all_tables),
                    'actie': 'Voeg toe aan KNOWN_DATABASE_TABLES en overweeg monitoring'
                }
            )
        else:
            return CheckResult(
                name="Database Tables",
                status=Status.OK,
                message=f"Alle {len(all_tables)} tabellen bekend"
            )

    except Exception as e:
        return CheckResult(
            name="Database Discovery",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        )


@timed_check
def check_new_systemd_files() -> CheckResult:
    """Check voor nieuwe systemd files in emsn2/systemd/ die niet geïnstalleerd zijn"""
    try:
        systemd_dir = Path("/home/ronny/emsn2/systemd")
        if not systemd_dir.exists():
            return CheckResult(
                name="Systemd Files",
                status=Status.UNKNOWN,
                message="Systemd directory niet gevonden"
            )

        # Vind alle .service en .timer files in repo
        repo_files = set()
        for ext in ['*.service', '*.timer']:
            for f in systemd_dir.glob(ext):
                repo_files.add(f.name)
            # Ook in subdirs
            for f in systemd_dir.glob(f'**/{ext}'):
                repo_files.add(f.name)

        # Check welke geïnstalleerd zijn op zolder
        result = subprocess.run(
            ['ssh', '-o', 'ConnectTimeout=5', '-o', 'BatchMode=yes',
             f'ronny@{HOSTS["zolder"]["ip"]}',
             'ls /etc/systemd/system/*.service /etc/systemd/system/*.timer 2>/dev/null | xargs -n1 basename'],
            capture_output=True,
            text=True,
            timeout=15
        )

        installed = set()
        if result.returncode == 0:
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    installed.add(line.strip())

        # Vind files in repo die niet geïnstalleerd zijn
        niet_geinstalleerd = repo_files - installed

        if niet_geinstalleerd:
            return CheckResult(
                name="Systemd Files Sync",
                status=Status.WARNING,
                message=f"{len(niet_geinstalleerd)} niet geïnstalleerd: {', '.join(list(niet_geinstalleerd)[:3])}...",
                details={
                    'niet_geinstalleerd': list(niet_geinstalleerd),
                    'repo_files': len(repo_files),
                    'installed': len(installed)
                }
            )
        else:
            return CheckResult(
                name="Systemd Files Sync",
                status=Status.OK,
                message=f"Alle {len(repo_files)} repo files geïnstalleerd"
            )

    except Exception as e:
        return CheckResult(
            name="Systemd Files",
            status=Status.UNKNOWN,
            message=f"Fout: {e}"
        )


@timed_check
def check_failed_services_discovery(host: str, ip: str) -> CheckResult:
    """Check voor gefaalde EMSN services die mogelijk nieuw zijn"""
    try:
        result = subprocess.run(
            ['ssh', '-o', 'ConnectTimeout=5', '-o', 'BatchMode=yes',
             f'ronny@{ip}',
             '''
             # Vind gefaalde services
             systemctl --failed --plain --no-legend 2>/dev/null | awk '{print $1}'
             '''],
            capture_output=True,
            text=True,
            timeout=15
        )

        if result.returncode == 0:
            failed = []
            for line in result.stdout.strip().split('\n'):
                service = line.strip()
                if service and matches_emsn_pattern(service):
                    failed.append(service)

            if failed:
                return CheckResult(
                    name=f"{host} Failed Services",
                    status=Status.CRITICAL,
                    message=f"{len(failed)} gefaald: {', '.join(failed[:3])}",
                    details={'failed_services': failed}
                )
            else:
                return CheckResult(
                    name=f"{host} Failed Services",
                    status=Status.OK,
                    message="Geen gefaalde EMSN services"
                )

        return CheckResult(
            name=f"{host} Failed Services",
            status=Status.UNKNOWN,
            message="Kan niet controleren"
        )

    except Exception as e:
        return CheckResult(
            name=f"{host} Failed",
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

    # ─── 16. EXTRA MONITORING ────────────────────────────────────
    print_header("16. EXTRA MONITORING")
    cat = CategoryResult(name="Extra")

    print_subheader("WiFi & NTP")
    # WiFi alleen voor meteo (andere Pi's zijn UTP)
    if ssh_available.get('meteo', False):
        result = check_wifi_signal('meteo', HOSTS['meteo']['ip'])
        cat.checks.append(result)
        print_check(result)

    # NTP sync voor alle hosts
    for host in ['zolder', 'berging', 'meteo']:
        if ssh_available.get(host, False):
            result = check_ntp_sync(host, HOSTS[host]['ip'])
            cat.checks.append(result)
            print_check(result)

    print_subheader("BirdNET Analyse")
    results = check_species_diversity()
    for result in results:
        cat.checks.append(result)
        print_check(result)

    result = check_confidence_distribution()
    cat.checks.append(result)
    print_check(result)

    categories['extra'] = cat

    # ─── 17. HARDWARE DIEPTE ─────────────────────────────────────
    print_header("17. HARDWARE DIEPTE CHECKS")
    cat = CategoryResult(name="Hardware Diepte")

    for host in ['zolder', 'berging', 'meteo']:
        if ssh_available.get(host, False):
            print_subheader(f"{host.title()}")
            ip = HOSTS[host]['ip']

            result = check_sd_card_health(host, ip)
            cat.checks.append(result)
            print_check(result)

            result = check_kernel_errors(host, ip)
            cat.checks.append(result)
            print_check(result)

            result = check_usb_devices(host, ip)
            cat.checks.append(result)
            print_check(result)

    categories['hardware_deep'] = cat

    # ─── 18. BIRDNET SPECIFIEK ───────────────────────────────────
    print_header("18. BIRDNET SPECIFIEKE CHECKS")
    cat = CategoryResult(name="BirdNET")

    for host in ['zolder', 'berging']:
        if ssh_available.get(host, False):
            print_subheader(f"{host.title()}")
            ip = HOSTS[host]['ip']

            result = check_birdnet_analyzer(host, ip)
            cat.checks.append(result)
            print_check(result)

            result = check_birdnet_model_version(host, ip)
            cat.checks.append(result)
            print_check(result)

    categories['birdnet'] = cat

    # ─── 19. EXTERNE SERVICES & DATABASE ─────────────────────────
    print_header("19. EXTERNE SERVICES & DATABASE")
    cat = CategoryResult(name="Extern/DB")

    print_subheader("Externe Services")
    result = check_tuya_cameras()
    cat.checks.append(result)
    print_check(result)

    result = check_github_sync()
    cat.checks.append(result)
    print_check(result)

    print_subheader("Database Analyse")
    result = check_orphaned_records()
    cat.checks.append(result)
    print_check(result)

    result = check_table_sizes()
    cat.checks.append(result)
    print_check(result)

    categories['extern_db'] = cat

    # ─── 20. VOCALIZATION SYSTEEM ─────────────────────────────────
    print_header("20. VOCALIZATION SYSTEEM")
    cat = CategoryResult(name="Vocalization")

    print_subheader("Service & Docker")
    result = check_vocalization_service()
    cat.checks.append(result)
    print_check(result)

    result = check_vocalization_docker()
    cat.checks.append(result)
    print_check(result)

    print_subheader("Verrijking")
    result = check_vocalization_enrichment_rate()
    cat.checks.append(result)
    print_check(result)

    categories['vocalization'] = cat

    # ─── 21. FLYSAFE RADAR & MIGRATIE ─────────────────────────────
    print_header("21. FLYSAFE RADAR & MIGRATIE")
    cat = CategoryResult(name="FlySafe")

    result = check_flysafe_scraper()
    cat.checks.append(result)
    print_check(result)

    result = check_migration_data()
    cat.checks.append(result)
    print_check(result)

    categories['flysafe'] = cat

    # ─── 22. NESTKAST AI DETECTIE ─────────────────────────────────
    print_header("22. NESTKAST AI DETECTIE")
    cat = CategoryResult(name="Nestkast AI")

    print_subheader("AI Models")
    result = check_nestbox_models()
    cat.checks.append(result)
    print_check(result)

    print_subheader("Events & Screenshots")
    result = check_nestbox_events()
    cat.checks.append(result)
    print_check(result)

    result = check_nestbox_screenshots_today()
    cat.checks.append(result)
    print_check(result)

    categories['nestkast_ai'] = cat

    # ─── 23. RAPPORT GENERATIE ────────────────────────────────────
    print_header("23. RAPPORT GENERATIE")
    cat = CategoryResult(name="Rapporten")

    print_subheader("Report Timers")
    results = check_report_timers()
    for result in results:
        cat.checks.append(result)
        print_check(result)

    print_subheader("Reports Directory")
    result = check_reports_directory()
    cat.checks.append(result)
    print_check(result)

    categories['rapporten'] = cat

    # ─── 24. ANOMALY DETECTION SYSTEEM ────────────────────────────
    print_header("24. ANOMALY DETECTION SYSTEEM")
    cat = CategoryResult(name="Anomaly")

    print_subheader("Checker Services")
    results = check_anomaly_services()
    for result in results:
        cat.checks.append(result)
        print_check(result)

    print_subheader("Actieve Anomalieën")
    result = check_active_anomalies()
    cat.checks.append(result)
    print_check(result)

    categories['anomaly'] = cat

    # ─── 25. AUDIO & MICROFOON KWALITEIT ──────────────────────────
    print_header("25. AUDIO & MICROFOON KWALITEIT")
    cat = CategoryResult(name="Audio")

    for host in ['zolder', 'berging']:
        if ssh_available.get(host, False):
            result = check_audio_device(host, HOSTS[host]['ip'])
            cat.checks.append(result)
            print_check(result)

    print_subheader("Detectie Patronen")
    result = check_day_night_ratio()
    cat.checks.append(result)
    print_check(result)

    categories['audio'] = cat

    # ─── 26. BACKUP & ARCHIVERING ─────────────────────────────────
    print_header("26. BACKUP & ARCHIVERING")
    cat = CategoryResult(name="Backup/Archive")

    print_subheader("SD Backup Timers")
    results = check_sd_backup_timers()
    for result in results:
        cat.checks.append(result)
        print_check(result)

    print_subheader("Archive Sync & Space")
    result = check_archive_sync()
    cat.checks.append(result)
    print_check(result)

    result = check_archive_space()
    cat.checks.append(result)
    print_check(result)

    categories['backup_archive'] = cat

    # ─── 27. NETWERK DIEPTE ───────────────────────────────────────
    print_header("27. NETWERK DIEPTE")
    cat = CategoryResult(name="Netwerk Diepte")

    print_subheader("Packet Loss")
    for host in ['zolder', 'berging', 'nas']:
        result = check_packet_loss(host, HOSTS[host]['ip'])
        cat.checks.append(result)
        print_check(result)

    print_subheader("DNS & Gateway")
    result = check_dns_resolution()
    cat.checks.append(result)
    print_check(result)

    result = check_gateway()
    cat.checks.append(result)
    print_check(result)

    categories['netwerk_diepte'] = cat

    # ─── 28. REALTIME SERVICES ────────────────────────────────────
    print_header("28. REALTIME SERVICES")
    cat = CategoryResult(name="Realtime")

    result = check_realtime_dual_detection()
    cat.checks.append(result)
    print_check(result)

    result = check_mqtt_message_rate()
    cat.checks.append(result)
    print_check(result)

    result = check_ulanzi_notifications()
    cat.checks.append(result)
    print_check(result)

    categories['realtime'] = cat

    # ─── 29. AUTO-DISCOVERY & NIEUWE FEATURES ─────────────────────
    print_header("29. AUTO-DISCOVERY & NIEUWE FEATURES")
    cat = CategoryResult(name="Discovery")

    print_subheader("Service Discovery")
    for host in ['zolder', 'berging', 'meteo']:
        if ssh_available.get(host, False):
            result = check_new_services(host, HOSTS[host]['ip'])
            cat.checks.append(result)
            print_check(result)

            result = check_failed_services_discovery(host, HOSTS[host]['ip'])
            cat.checks.append(result)
            print_check(result)

    print_subheader("Database & Systemd Discovery")
    result = check_new_database_tables()
    cat.checks.append(result)
    print_check(result)

    result = check_new_systemd_files()
    cat.checks.append(result)
    print_check(result)

    categories['discovery'] = cat

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
