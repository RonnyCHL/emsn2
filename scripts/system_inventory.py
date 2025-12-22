#!/usr/bin/env python3
"""
EMSN 2.0 - Centraal Systeem Inventarisatie Script
=================================================

Genereert een compleet overzicht van alle EMSN-systemen:
- Zolder Pi (lokaal, 192.168.1.178)
- Berging Pi (remote via SSH, 192.168.1.87)
- NAS PostgreSQL database (192.168.1.25)

Output:
- Markdown bestand met complete systeeminventarisatie
- Update van het EMSN Handboek met actuele data
- Detectie van nieuwe componenten sinds vorige run

Features v1.2.0:
- Nieuwe componenten detectie (services, timers, scripts, tabellen)
- State file tracking voor vergelijking met vorige inventarisatie
- "Nieuwe Componenten" sectie in rapport wanneer er wijzigingen zijn

Versie: 1.2.0
Auteur: EMSN Project
"""

import subprocess
import os
import sys
from datetime import datetime
from pathlib import Path
import json
import re
import argparse

# Probeer psycopg2 te importeren
try:
    import psycopg2
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

# Script versie
VERSION = "1.2.0"

# State file voor tracking van bekende componenten
STATE_FILE = Path("/home/ronny/emsn2/docs/.inventory_state.json")


def load_state() -> dict:
    """Laad vorige inventarisatie state."""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"   ⚠️ Kon state niet laden: {e}")
    return {}


def save_state(state: dict) -> bool:
    """Sla huidige inventarisatie state op."""
    try:
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"   ❌ Kon state niet opslaan: {e}")
        return False


def detect_new_components(current: dict, previous: dict) -> dict:
    """Detecteer nieuwe componenten sinds vorige run.

    Returns een dict met nieuwe componenten per categorie:
    {
        "zolder_services": ["nieuwe-service.service", ...],
        "zolder_timers": [...],
        "zolder_scripts": [...],
        "berging_services": [...],
        "berging_timers": [...],
        "database_tables": [...],
    }
    """
    new_components = {}

    # Zolder services
    curr_zolder_services = set(s['name'] for s in current.get('zolder', {}).get('services', []))
    prev_zolder_services = set(previous.get('zolder_services', []))
    new_zolder_services = curr_zolder_services - prev_zolder_services
    if new_zolder_services and prev_zolder_services:  # Alleen als er vorige data was
        new_components['zolder_services'] = sorted(new_zolder_services)

    # Zolder timers
    curr_zolder_timers = set(t['name'] for t in current.get('zolder', {}).get('timers', []))
    prev_zolder_timers = set(previous.get('zolder_timers', []))
    new_zolder_timers = curr_zolder_timers - prev_zolder_timers
    if new_zolder_timers and prev_zolder_timers:
        new_components['zolder_timers'] = sorted(new_zolder_timers)

    # Zolder scripts
    curr_zolder_scripts = set(s['path'] for s in current.get('zolder', {}).get('scripts', []))
    prev_zolder_scripts = set(previous.get('zolder_scripts', []))
    new_zolder_scripts = curr_zolder_scripts - prev_zolder_scripts
    if new_zolder_scripts and prev_zolder_scripts:
        new_components['zolder_scripts'] = sorted(new_zolder_scripts)

    # Berging services
    curr_berging_services = set(s['name'] for s in current.get('berging', {}).get('services', []))
    prev_berging_services = set(previous.get('berging_services', []))
    new_berging_services = curr_berging_services - prev_berging_services
    if new_berging_services and prev_berging_services:
        new_components['berging_services'] = sorted(new_berging_services)

    # Berging timers
    curr_berging_timers = set(t['name'] for t in current.get('berging', {}).get('timers', []))
    prev_berging_timers = set(previous.get('berging_timers', []))
    new_berging_timers = curr_berging_timers - prev_berging_timers
    if new_berging_timers and prev_berging_timers:
        new_components['berging_timers'] = sorted(new_berging_timers)

    # Database tabellen
    curr_tables = set(t['name'] for t in current.get('database', {}).get('tables', []))
    prev_tables = set(previous.get('database_tables', []))
    new_tables = curr_tables - prev_tables
    if new_tables and prev_tables:
        new_components['database_tables'] = sorted(new_tables)

    return new_components


def build_current_state(zolder_info: dict, berging_info: dict, db_info: dict) -> dict:
    """Bouw huidige state dict voor opslag."""
    return {
        "timestamp": datetime.now().isoformat(),
        "version": VERSION,
        "zolder_services": [s['name'] for s in zolder_info.get('services', [])],
        "zolder_timers": [t['name'] for t in zolder_info.get('timers', [])],
        "zolder_scripts": [s['path'] for s in zolder_info.get('scripts', [])],
        "berging_services": [s['name'] for s in berging_info.get('services', [])],
        "berging_timers": [t['name'] for t in berging_info.get('timers', [])],
        "database_tables": [t['name'] for t in db_info.get('tables', [])] if not db_info.get('error') else []
    }


# Configuratie
CONFIG = {
    "zolder": {
        "hostname": "emsn2-zolder",
        "ip": "192.168.1.178",
        "is_local": True
    },
    "berging": {
        "hostname": "emsn2-berging",
        "ip": "192.168.1.87",
        "ssh_user": "ronny",
        "is_local": False
    },
    "nas": {
        "hostname": "DS224Plus",
        "ip": "192.168.1.25",
        "db_port": 5433,
        "db_name": "emsn",
        "db_user": "birdpi_zolder"
    }
}

# EMSN gerelateerde service patronen
SERVICE_PATTERNS = [
    "emsn", "birdnet", "mqtt", "ulanzi", "lifetime", "anomaly",
    "dual-detection", "hardware", "flysafe", "rarity", "screenshot",
    "backup", "atmosbird"
]

# Handboek pad
HANDBOOK_PATH = Path("/home/ronny/emsn2/docs/EMSN-Handboek-v1.0.md")


def run_local_command(cmd: str, timeout: int = 30) -> tuple[bool, str]:
    """Voer lokaal commando uit en return (success, output)."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        output = result.stdout.strip()
        if result.returncode != 0 and result.stderr:
            output += f"\n[stderr: {result.stderr.strip()}]"
        return result.returncode == 0, output
    except subprocess.TimeoutExpired:
        return False, "[TIMEOUT]"
    except Exception as e:
        return False, f"[ERROR: {e}]"


def run_ssh_command(host: str, user: str, cmd: str, timeout: int = 30) -> tuple[bool, str]:
    """Voer SSH commando uit en return (success, output)."""
    ssh_cmd = f'ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no {user}@{host} "{cmd}"'
    return run_local_command(ssh_cmd, timeout)


def get_system_info(is_local: bool, host: str = None, user: str = None) -> dict:
    """Verzamel basissysteem informatie."""
    info = {}

    commands = {
        "hostname": "hostname",
        "ip": "hostname -I | awk '{print $1}'",
        "os_version": "cat /etc/os-release | grep PRETTY_NAME | cut -d'\"' -f2",
        "kernel": "uname -r",
        "uptime": "uptime -p",
        "uptime_since": "uptime -s",
        "load": "cat /proc/loadavg | awk '{print $1, $2, $3}'",
        "uptime_days": "awk '{print int($1/86400)}' /proc/uptime"
    }

    for key, cmd in commands.items():
        if is_local:
            success, output = run_local_command(cmd)
        else:
            success, output = run_ssh_command(host, user, cmd)
        info[key] = output if success else "N/A"

    return info


def get_disk_usage(is_local: bool, host: str = None, user: str = None) -> list[dict]:
    """Verzamel disk usage informatie."""
    cmd = "df -h / /mnt/usb_birdnet /mnt/usb /mnt/nas-reports /mnt/nas-docker 2>/dev/null | tail -n +2"

    if is_local:
        success, output = run_local_command(cmd)
    else:
        success, output = run_ssh_command(host, user, cmd)

    if not success:
        return []

    disks = []
    for line in output.split('\n'):
        if line.strip():
            parts = line.split()
            if len(parts) >= 6:
                disks.append({
                    "filesystem": parts[0],
                    "size": parts[1],
                    "used": parts[2],
                    "available": parts[3],
                    "usage_percent": parts[4],
                    "mount": parts[5]
                })
    return disks


def get_systemd_services(is_local: bool, host: str = None, user: str = None) -> list[dict]:
    """Verzamel EMSN-gerelateerde systemd services."""
    pattern = '|'.join(SERVICE_PATTERNS)
    cmd = f'systemctl list-units --all --type=service 2>/dev/null | grep -E "({pattern})"'

    if is_local:
        success, output = run_local_command(cmd)
    else:
        success, output = run_ssh_command(host, user, cmd)

    if not success or not output:
        return []

    services = []
    for line in output.split('\n'):
        if line.strip():
            # Parse systemctl output
            parts = line.split()
            if len(parts) >= 4:
                name = parts[0].replace('●', '').strip()
                if '.service' in name:
                    services.append({
                        "name": name,
                        "load": parts[1] if len(parts) > 1 else "N/A",
                        "active": parts[2] if len(parts) > 2 else "N/A",
                        "sub": parts[3] if len(parts) > 3 else "N/A",
                        "description": ' '.join(parts[4:]) if len(parts) > 4 else ""
                    })
    return services


def get_systemd_timers(is_local: bool, host: str = None, user: str = None) -> list[dict]:
    """Verzamel EMSN-gerelateerde systemd timers."""
    pattern = '|'.join(SERVICE_PATTERNS)
    cmd = f'systemctl list-timers --all 2>/dev/null | grep -E "({pattern})"'

    if is_local:
        success, output = run_local_command(cmd)
    else:
        success, output = run_ssh_command(host, user, cmd)

    if not success or not output:
        return []

    timers = []
    for line in output.split('\n'):
        if line.strip() and '.timer' in line:
            parts = line.split()
            # Timer output: NEXT LEFT LAST PASSED UNIT ACTIVATES
            timer_name = None
            for part in parts:
                if '.timer' in part:
                    timer_name = part
                    break
            if timer_name:
                timers.append({
                    "name": timer_name,
                    "raw": line.strip()
                })
    return timers


def get_failed_services(is_local: bool, host: str = None, user: str = None) -> list[str]:
    """Check for failed services."""
    cmd = "systemctl --failed --no-legend 2>/dev/null"

    if is_local:
        success, output = run_local_command(cmd)
    else:
        success, output = run_ssh_command(host, user, cmd)

    if not success or not output:
        return []

    failed = []
    for line in output.split('\n'):
        if line.strip():
            parts = line.split()
            if parts:
                failed.append(parts[0])
    return failed


def get_python_scripts(base_path: str, is_local: bool, host: str = None, user: str = None) -> list[dict]:
    """Verzamel Python scripts met hun docstrings."""
    cmd = f'find {base_path} -name "*.py" -type f 2>/dev/null'

    if is_local:
        success, output = run_local_command(cmd)
    else:
        success, output = run_ssh_command(host, user, cmd)

    if not success or not output:
        return []

    scripts = []
    for filepath in output.split('\n'):
        if filepath.strip():
            # Haal eerste commentaar/docstring op
            head_cmd = f'head -10 "{filepath}" 2>/dev/null'
            if is_local:
                _, head_output = run_local_command(head_cmd)
            else:
                _, head_output = run_ssh_command(host, user, head_cmd)

            # Zoek docstring
            docstring = ""
            if '"""' in head_output:
                match = re.search(r'"""(.+?)"""', head_output, re.DOTALL)
                if match:
                    docstring = match.group(1).strip().split('\n')[0]

            scripts.append({
                "path": filepath,
                "name": os.path.basename(filepath),
                "description": docstring[:100] if docstring else ""
            })

    return sorted(scripts, key=lambda x: x['path'])


def get_crontab(is_local: bool, host: str = None, user: str = None) -> str:
    """Haal crontab op."""
    cmd = "crontab -l 2>/dev/null || echo 'Geen crontab'"

    if is_local:
        success, output = run_local_command(cmd)
    else:
        success, output = run_ssh_command(host, user, cmd)

    return output if success else "N/A"


def get_mqtt_status(is_local: bool, host: str = None, user: str = None) -> dict:
    """Check MQTT broker status."""
    cmd = "systemctl is-active mosquitto 2>/dev/null && systemctl show mosquitto --property=ActiveEnterTimestamp --value 2>/dev/null"

    if is_local:
        success, output = run_local_command(cmd)
    else:
        success, output = run_ssh_command(host, user, cmd)

    lines = output.split('\n') if output else []
    return {
        "status": lines[0] if lines else "unknown",
        "since": lines[1] if len(lines) > 1 else "unknown"
    }


def get_git_status(repo_path: str, is_local: bool, host: str = None, user: str = None) -> dict:
    """Haal Git status op."""
    commands = {
        "branch": f"git -C {repo_path} branch --show-current 2>/dev/null",
        "last_commit": f"git -C {repo_path} log -1 --format='%h %s' 2>/dev/null",
        "status": f"git -C {repo_path} status --short 2>/dev/null",
        "uncommitted": f"git -C {repo_path} status --porcelain 2>/dev/null | wc -l"
    }

    info = {}
    for key, cmd in commands.items():
        if is_local:
            success, output = run_local_command(cmd)
        else:
            success, output = run_ssh_command(host, user, cmd)
        info[key] = output if success else "N/A"

    return info


def get_database_info() -> dict:
    """Verzamel PostgreSQL database informatie."""
    if not HAS_PSYCOPG2:
        return {"error": "psycopg2 niet geinstalleerd"}

    # Try to load from secrets.py first
    db_password = None
    try:
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent / 'config'))
        from emsn_secrets import get_postgres_config
        _pg = get_postgres_config()
        db_password = _pg.get('password', '')
    except ImportError:
        pass
    db_password = db_password or os.environ.get('EMSN_DB_PASSWORD', '')

    try:
        conn = psycopg2.connect(
            host=CONFIG['nas']['ip'],
            port=CONFIG['nas']['db_port'],
            database=CONFIG['nas']['db_name'],
            user=CONFIG['nas']['db_user'],
            password=db_password,
            connect_timeout=10
        )
        cur = conn.cursor()

        info = {"tables": [], "total_size": "N/A"}

        # Database grootte
        cur.execute("SELECT pg_size_pretty(pg_database_size(%s))", (CONFIG['nas']['db_name'],))
        info['total_size'] = cur.fetchone()[0]

        # Tabellen met row counts en grootte
        cur.execute("""
            SELECT
                t.table_name,
                pg_size_pretty(pg_total_relation_size(quote_ident(t.table_name)::text)) as size,
                (SELECT count(*) FROM information_schema.columns c WHERE c.table_name = t.table_name) as columns
            FROM information_schema.tables t
            WHERE t.table_schema = 'public'
            ORDER BY pg_total_relation_size(quote_ident(t.table_name)::text) DESC
        """)

        for row in cur.fetchall():
            table_name = row[0]
            # Get row count
            try:
                cur.execute(f"SELECT COUNT(*) FROM {table_name}")
                row_count = cur.fetchone()[0]
            except:
                row_count = "N/A"

            info['tables'].append({
                "name": table_name,
                "size": row[1],
                "columns": row[2],
                "rows": row_count
            })

        # Recente data check
        cur.execute("SELECT MAX(detection_timestamp) FROM bird_detections")
        info['last_detection'] = str(cur.fetchone()[0])

        cur.execute("SELECT MAX(measurement_timestamp) FROM system_health")
        info['last_health'] = str(cur.fetchone()[0])

        # Totaal detecties
        cur.execute("SELECT COUNT(*) FROM bird_detections")
        info['total_detections'] = cur.fetchone()[0]

        # Unieke soorten
        cur.execute("SELECT COUNT(DISTINCT species) FROM bird_detections")
        info['unique_species'] = cur.fetchone()[0]

        # Dual detections
        cur.execute("SELECT COUNT(*) FROM dual_detections")
        info['dual_detections'] = cur.fetchone()[0]

        # Weather data count
        cur.execute("SELECT COUNT(*) FROM weather_data")
        info['weather_count'] = cur.fetchone()[0]

        # System health count
        cur.execute("SELECT COUNT(*) FROM system_health")
        info['health_count'] = cur.fetchone()[0]

        conn.close()
        return info

    except Exception as e:
        return {"error": str(e)}


def generate_markdown_report(zolder_info: dict, berging_info: dict, db_info: dict,
                             new_components: dict = None, previous_timestamp: str = None) -> str:
    """Genereer Markdown rapport."""

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    md = f"""# EMSN 2.0 - Systeem Inventarisatie

**Gegenereerd:** {timestamp}
**Script versie:** {VERSION}
**Gegenereerd op:** {zolder_info.get('system', {}).get('hostname', 'onbekend')}

---

## Samenvatting

| Systeem | Status | Uptime | IP Adres |
|---------|--------|--------|----------|
| Zolder Pi | {'✅ Online' if zolder_info.get('system') else '❌ Offline'} | {zolder_info.get('system', {}).get('uptime', 'N/A')} | {CONFIG['zolder']['ip']} |
| Berging Pi | {'✅ Online' if berging_info.get('system') else '❌ Offline'} | {berging_info.get('system', {}).get('uptime', 'N/A')} | {CONFIG['berging']['ip']} |
| NAS Database | {'✅ Online' if not db_info.get('error') else '❌ Offline'} | - | {CONFIG['nas']['ip']} |

"""

    # Problemen sectie
    problems = []
    if zolder_info.get('failed_services'):
        for svc in zolder_info['failed_services']:
            problems.append(f"- ❌ **Zolder:** Service `{svc}` is FAILED")
    if berging_info.get('failed_services'):
        for svc in berging_info['failed_services']:
            problems.append(f"- ❌ **Berging:** Service `{svc}` is FAILED")
    if db_info.get('error'):
        problems.append(f"- ❌ **Database:** {db_info['error']}")

    if problems:
        md += """### ⚠️ Gevonden Problemen

"""
        md += '\n'.join(problems)
        md += "\n\n"
    else:
        md += """### ✅ Geen Kritieke Problemen Gevonden

"""

    # ============ NIEUWE COMPONENTEN SECTIE ============
    if new_components:
        md += """### 🆕 Nieuwe Componenten Sinds Vorige Run

"""
        if previous_timestamp:
            md += f"*Vergeleken met inventarisatie van: {previous_timestamp}*\n\n"

        if new_components.get('zolder_services'):
            md += "**Zolder - Nieuwe Services:**\n"
            for svc in new_components['zolder_services']:
                md += f"- `{svc}`\n"
            md += "\n"

        if new_components.get('zolder_timers'):
            md += "**Zolder - Nieuwe Timers:**\n"
            for timer in new_components['zolder_timers']:
                md += f"- `{timer}`\n"
            md += "\n"

        if new_components.get('zolder_scripts'):
            md += "**Zolder - Nieuwe Scripts:**\n"
            for script in new_components['zolder_scripts']:
                md += f"- `{script}`\n"
            md += "\n"

        if new_components.get('berging_services'):
            md += "**Berging - Nieuwe Services:**\n"
            for svc in new_components['berging_services']:
                md += f"- `{svc}`\n"
            md += "\n"

        if new_components.get('berging_timers'):
            md += "**Berging - Nieuwe Timers:**\n"
            for timer in new_components['berging_timers']:
                md += f"- `{timer}`\n"
            md += "\n"

        if new_components.get('database_tables'):
            md += "**Database - Nieuwe Tabellen:**\n"
            for table in new_components['database_tables']:
                md += f"- `{table}`\n"
            md += "\n"

        md += "> **Let op:** Deze nieuwe componenten zijn nog niet gedocumenteerd in het handboek.\n"
        md += "> Overweeg om de documentatie bij te werken!\n\n"

    # ============ ZOLDER SECTIE ============
    md += """---

## 🏠 Zolder Pi (192.168.1.178)

### Systeem Informatie

| Eigenschap | Waarde |
|------------|--------|
"""
    sys_info = zolder_info.get('system', {})
    md += f"| Hostname | {sys_info.get('hostname', 'N/A')} |\n"
    md += f"| IP Adres | {sys_info.get('ip', 'N/A')} |\n"
    md += f"| OS | {sys_info.get('os_version', 'N/A')} |\n"
    md += f"| Kernel | {sys_info.get('kernel', 'N/A')} |\n"
    md += f"| Uptime | {sys_info.get('uptime', 'N/A')} |\n"
    md += f"| Online sinds | {sys_info.get('uptime_since', 'N/A')} |\n"
    md += f"| Load Average | {sys_info.get('load', 'N/A')} |\n"

    # Disk usage
    md += """
### Disk Usage

| Mount | Grootte | Gebruikt | Beschikbaar | Gebruik |
|-------|---------|----------|-------------|---------|
"""
    for disk in zolder_info.get('disks', []):
        md += f"| {disk['mount']} | {disk['size']} | {disk['used']} | {disk['available']} | {disk['usage_percent']} |\n"

    # Services
    md += """
### Systemd Services

| Service | Status | Staat | Beschrijving |
|---------|--------|-------|--------------|
"""
    for svc in zolder_info.get('services', []):
        status_icon = "✅" if svc['active'] == 'active' else "⚪" if svc['active'] == 'inactive' else "❌"
        md += f"| {svc['name']} | {status_icon} {svc['active']} | {svc['sub']} | {svc['description'][:50]}... |\n"

    # Timers
    md += """
### Systemd Timers

| Timer | Details |
|-------|---------|
"""
    for timer in zolder_info.get('timers', []):
        md += f"| {timer['name']} | {timer['raw'][:80]}... |\n"

    # MQTT
    mqtt = zolder_info.get('mqtt', {})
    md += f"""
### MQTT Broker (Mosquitto)

- **Status:** {mqtt.get('status', 'N/A')}
- **Actief sinds:** {mqtt.get('since', 'N/A')}

"""

    # Git status
    git = zolder_info.get('git', {})
    md += f"""
### Git Repository

- **Branch:** {git.get('branch', 'N/A')}
- **Laatste commit:** {git.get('last_commit', 'N/A')}
- **Uncommitted changes:** {git.get('uncommitted', '0')} bestanden

"""

    # Scripts
    md += """
### Python Scripts

| Script | Pad | Beschrijving |
|--------|-----|--------------|
"""
    for script in zolder_info.get('scripts', [])[:30]:  # Max 30
        md += f"| {script['name']} | `{script['path']}` | {script['description'][:40]}... |\n"

    # ============ BERGING SECTIE ============
    md += """
---

## 🏚️ Berging Pi (192.168.1.87)

### Systeem Informatie

| Eigenschap | Waarde |
|------------|--------|
"""
    sys_info = berging_info.get('system', {})
    md += f"| Hostname | {sys_info.get('hostname', 'N/A')} |\n"
    md += f"| IP Adres | {sys_info.get('ip', 'N/A')} |\n"
    md += f"| OS | {sys_info.get('os_version', 'N/A')} |\n"
    md += f"| Kernel | {sys_info.get('kernel', 'N/A')} |\n"
    md += f"| Uptime | {sys_info.get('uptime', 'N/A')} |\n"
    md += f"| Online sinds | {sys_info.get('uptime_since', 'N/A')} |\n"

    # Disk usage
    md += """
### Disk Usage

| Mount | Grootte | Gebruikt | Beschikbaar | Gebruik |
|-------|---------|----------|-------------|---------|
"""
    for disk in berging_info.get('disks', []):
        md += f"| {disk['mount']} | {disk['size']} | {disk['used']} | {disk['available']} | {disk['usage_percent']} |\n"

    # Services
    md += """
### Systemd Services

| Service | Status | Staat | Beschrijving |
|---------|--------|-------|--------------|
"""
    for svc in berging_info.get('services', []):
        status_icon = "✅" if svc['active'] == 'active' else "⚪" if svc['active'] == 'inactive' else "❌"
        md += f"| {svc['name']} | {status_icon} {svc['active']} | {svc['sub']} | {svc['description'][:50]}... |\n"

    # Timers
    md += """
### Systemd Timers

| Timer | Details |
|-------|---------|
"""
    for timer in berging_info.get('timers', []):
        md += f"| {timer['name']} | {timer['raw'][:80]}... |\n"

    # Git status
    git = berging_info.get('git', {})
    md += f"""
### Git Repository

- **Branch:** {git.get('branch', 'N/A')}
- **Laatste commit:** {git.get('last_commit', 'N/A')}
- **Uncommitted changes:** {git.get('uncommitted', '0')} bestanden

"""

    # ============ DATABASE SECTIE ============
    md += """
---

## 🗄️ NAS PostgreSQL Database (192.168.1.25)

"""

    if db_info.get('error'):
        md += f"**❌ Fout:** {db_info['error']}\n\n"
    else:
        md += f"""### Database Overzicht

- **Database:** {CONFIG['nas']['db_name']}
- **Grootte:** {db_info.get('total_size', 'N/A')}
- **Laatste vogeldetectie:** {db_info.get('last_detection', 'N/A')}
- **Laatste health check:** {db_info.get('last_health', 'N/A')}

### Tabellen

| Tabel | Grootte | Kolommen | Rijen |
|-------|---------|----------|-------|
"""
        for table in db_info.get('tables', []):
            rows = table['rows']
            if isinstance(rows, int):
                rows = f"{rows:,}"
            md += f"| {table['name']} | {table['size']} | {table['columns']} | {rows} |\n"

    # ============ APPENDIX ============
    md += """
---

## 📋 Appendix

### Netwerk Overzicht

| Systeem | IP | Functie |
|---------|-----|---------|
| Pi Zolder | 192.168.1.178 | BirdNET-Pi, MQTT broker, API server |
| Pi Berging | 192.168.1.87 | BirdNET-Pi, AtmosBird, MQTT bridge |
| NAS | 192.168.1.25 | PostgreSQL, Grafana, Opslag |
| Ulanzi | 192.168.1.11 | LED Matrix Display |
| Homer | http://192.168.1.25:8181 | Dashboard |

### Belangrijke URLs

- **Reports API:** http://192.168.1.178:8081
- **Grafana:** http://192.168.1.25:3000
- **Homer Dashboard:** http://192.168.1.25:8181

### MQTT Topics

- `emsn2/{station}/#` - Systeem data
- `birdnet/{station}/detection` - Live detecties
- `birdnet/{station}/stats` - Statistieken
- `emsn2/bridge/status` - Bridge status

---

*Dit rapport is automatisch gegenereerd door system_inventory.py*
"""

    return md


def update_handbook(zolder_info: dict, berging_info: dict, db_info: dict) -> bool:
    """Update het EMSN Handboek met actuele data."""

    if not HANDBOOK_PATH.exists():
        print(f"   ⚠️ Handboek niet gevonden: {HANDBOOK_PATH}")
        return False

    try:
        # Lees huidige handboek
        with open(HANDBOOK_PATH, 'r', encoding='utf-8') as f:
            content = f.read()

        timestamp = datetime.now().strftime("%d %B %Y").replace(
            "January", "januari").replace("February", "februari").replace(
            "March", "maart").replace("April", "april").replace(
            "May", "mei").replace("June", "juni").replace(
            "July", "juli").replace("August", "augustus").replace(
            "September", "september").replace("October", "oktober").replace(
            "November", "november").replace("December", "december")

        # Update datum
        content = re.sub(
            r'\*\*Datum:\*\* \d+ \w+ \d+',
            f'**Datum:** {timestamp}',
            content
        )

        # Update huidige status tabel in sectie 1.2
        zolder_uptime = zolder_info.get('system', {}).get('uptime_days', '?')
        berging_uptime = berging_info.get('system', {}).get('uptime_days', '?')
        db_size = db_info.get('total_size', 'N/A')
        total_detections = db_info.get('total_detections', 'N/A')
        if isinstance(total_detections, int):
            total_detections = f"{total_detections:,}"

        # Update status tabel
        zolder_status = '✅ Online' if zolder_info.get('system') else '❌ Offline'
        berging_status = '✅ Online' if berging_info.get('system') else '❌ Offline'
        db_status = '✅ Online' if not db_info.get('error') else '❌ Offline'

        # Zoek en vervang de status tabel
        status_pattern = r'\| Zolder Pi \| .+ \| .+ \|'
        content = re.sub(
            status_pattern,
            f'| Zolder Pi | {zolder_status} | {zolder_uptime} dagen uptime, primaire node |',
            content
        )

        status_pattern = r'\| Berging Pi \| .+ \| .+ \|'
        content = re.sub(
            status_pattern,
            f'| Berging Pi | {berging_status} | {berging_uptime} dagen uptime, secundaire node |',
            content
        )

        status_pattern = r'\| NAS Database \| .+ \| .+ \|'
        content = re.sub(
            status_pattern,
            f'| NAS Database | {db_status} | {db_size}, {total_detections} detecties |',
            content
        )

        # Update statistieken
        if not db_info.get('error'):
            unique_species = db_info.get('unique_species', 'N/A')
            dual_detections = db_info.get('dual_detections', 'N/A')
            weather_count = db_info.get('weather_count', 'N/A')
            health_count = db_info.get('health_count', 'N/A')

            if isinstance(dual_detections, int):
                dual_detections = f"{dual_detections:,}"
            if isinstance(weather_count, int):
                weather_count = f"{weather_count:,}"
            if isinstance(health_count, int):
                health_count = f"{health_count:,}"

            # Update statistieken regels
            # Pattern: match het label en de cijfers, behoud de rest van de regel
            content = re.sub(
                r'(\*\*Totaal vogeldetecties:\*\* )[\d,]+',
                f'\\g<1>{total_detections}',
                content
            )
            content = re.sub(
                r'(\*\*Unieke soorten:\*\* )\d+',
                f'\\g<1>{unique_species}',
                content
            )
            content = re.sub(
                r'(\*\*Dual detections:\*\* )[\d,]+',
                f'\\g<1>{dual_detections}',
                content
            )
            content = re.sub(
                r'(\*\*Weerdata metingen:\*\* )[\d,]+',
                f'\\g<1>{weather_count}',
                content
            )
            content = re.sub(
                r'(\*\*System health records:\*\* )[\d,]+',
                f'\\g<1>{health_count}',
                content
            )

        # Update database grootte in sectie 5.3
        content = re.sub(
            r'\| \*\*Totaal\*\* \| \*\*[\d]+ MB\*\* \| - \|',
            f'| **Totaal** | **{db_size}** | - |',
            content
        )

        # Schrijf bijgewerkt handboek
        with open(HANDBOOK_PATH, 'w', encoding='utf-8') as f:
            f.write(content)

        return True

    except Exception as e:
        print(f"   ❌ Fout bij updaten handboek: {e}")
        return False


def main():
    """Main functie."""
    parser = argparse.ArgumentParser(description='EMSN Systeem Inventarisatie')
    parser.add_argument('--no-handbook', action='store_true',
                        help='Handboek niet bijwerken')
    parser.add_argument('--handbook-only', action='store_true',
                        help='Alleen handboek bijwerken, geen nieuw rapport')
    args = parser.parse_args()

    print("🔍 EMSN Systeem Inventarisatie")
    print("=" * 50)

    # Zolder (lokaal)
    print("\n📡 Verzamelen Zolder Pi data...")
    zolder_info = {
        "system": get_system_info(is_local=True),
        "disks": get_disk_usage(is_local=True),
        "services": get_systemd_services(is_local=True),
        "timers": get_systemd_timers(is_local=True),
        "failed_services": get_failed_services(is_local=True),
        "scripts": get_python_scripts("/home/ronny/emsn2/scripts", is_local=True),
        "crontab": get_crontab(is_local=True),
        "mqtt": get_mqtt_status(is_local=True),
        "git": get_git_status("/home/ronny/emsn2", is_local=True)
    }
    print(f"   ✅ {len(zolder_info['services'])} services, {len(zolder_info['scripts'])} scripts")

    # Berging (remote)
    print("\n📡 Verzamelen Berging Pi data (via SSH)...")
    berging_config = CONFIG['berging']
    berging_info = {
        "system": get_system_info(
            is_local=False,
            host=berging_config['ip'],
            user=berging_config['ssh_user']
        ),
        "disks": get_disk_usage(
            is_local=False,
            host=berging_config['ip'],
            user=berging_config['ssh_user']
        ),
        "services": get_systemd_services(
            is_local=False,
            host=berging_config['ip'],
            user=berging_config['ssh_user']
        ),
        "timers": get_systemd_timers(
            is_local=False,
            host=berging_config['ip'],
            user=berging_config['ssh_user']
        ),
        "failed_services": get_failed_services(
            is_local=False,
            host=berging_config['ip'],
            user=berging_config['ssh_user']
        ),
        "crontab": get_crontab(
            is_local=False,
            host=berging_config['ip'],
            user=berging_config['ssh_user']
        ),
        "git": get_git_status(
            "/home/ronny/emsn2",
            is_local=False,
            host=berging_config['ip'],
            user=berging_config['ssh_user']
        )
    }
    print(f"   ✅ {len(berging_info['services'])} services gevonden")

    # Database
    print("\n📡 Verzamelen Database data...")
    db_info = get_database_info()
    if db_info.get('error'):
        print(f"   ⚠️ Database fout: {db_info['error']}")
    else:
        print(f"   ✅ {len(db_info.get('tables', []))} tabellen, {db_info.get('total_size', 'N/A')}")

    # Laad vorige state en detecteer nieuwe componenten
    print("\n🔄 Vergelijken met vorige inventarisatie...")
    previous_state = load_state()
    previous_timestamp = previous_state.get('timestamp', None)

    # Bouw current state dict voor vergelijking
    current_data = {
        "zolder": zolder_info,
        "berging": berging_info,
        "database": db_info
    }

    new_components = detect_new_components(current_data, previous_state)

    if new_components:
        total_new = sum(len(v) for v in new_components.values())
        print(f"   🆕 {total_new} nieuwe component(en) gevonden!")
        for category, items in new_components.items():
            print(f"      - {category}: {len(items)}")
    elif previous_timestamp:
        print(f"   ✅ Geen nieuwe componenten sinds {previous_timestamp}")
    else:
        print(f"   ℹ️ Eerste run - baseline wordt opgeslagen")

    # Genereer rapport (tenzij --handbook-only)
    if not args.handbook_only:
        print("\n📝 Genereren Markdown rapport...")
        report = generate_markdown_report(
            zolder_info, berging_info, db_info,
            new_components=new_components,
            previous_timestamp=previous_timestamp
        )

        # Schrijf naar bestand
        output_dir = Path("/home/ronny/emsn2/docs")
        output_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d")
        output_file = output_dir / f"systeem-inventarisatie-{timestamp}.md"

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report)

        print(f"   ✅ Rapport opgeslagen: {output_file}")

    # Update handboek (tenzij --no-handbook)
    if not args.no_handbook:
        print("\n📚 Bijwerken EMSN Handboek...")
        if update_handbook(zolder_info, berging_info, db_info):
            print(f"   ✅ Handboek bijgewerkt: {HANDBOOK_PATH}")
        else:
            print(f"   ⚠️ Handboek niet bijgewerkt")

    # Print samenvatting
    print("\n" + "=" * 50)
    print("📊 SAMENVATTING")
    print("=" * 50)

    total_services = len(zolder_info['services']) + len(berging_info['services'])
    total_scripts = len(zolder_info['scripts'])
    failed = zolder_info['failed_services'] + berging_info['failed_services']

    print(f"   Services: {total_services}")
    print(f"   Scripts: {total_scripts}")
    print(f"   Database tabellen: {len(db_info.get('tables', []))}")

    if not db_info.get('error'):
        print(f"   Vogeldetecties: {db_info.get('total_detections', 'N/A'):,}")

    if failed:
        print(f"\n   ⚠️ FAILED SERVICES: {', '.join(failed)}")
    else:
        print(f"\n   ✅ Geen failed services")

    # Sla huidige state op voor volgende run
    if not args.handbook_only:
        print("\n💾 Opslaan state voor volgende run...")
        new_state = build_current_state(zolder_info, berging_info, db_info)
        if save_state(new_state):
            print(f"   ✅ State opgeslagen: {STATE_FILE}")
        else:
            print(f"   ⚠️ State niet opgeslagen")

    return 0


if __name__ == "__main__":
    sys.exit(main())
