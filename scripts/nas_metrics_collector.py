#!/usr/bin/env python3
"""
NAS Metrics Collector voor EMSN 2.0
Haalt systeem metrics op van de Synology NAS via SSH en slaat ze op in PostgreSQL.
"""

import subprocess
import psycopg2
import re
from datetime import datetime

# Configuratie
NAS_HOST = "192.168.1.25"
NAS_USER = "ronny"
NAS_PASS = "IwnadBon2iN"

PG_HOST = "192.168.1.25"
PG_PORT = 5433
PG_DB = "emsn"
PG_USER = "birdpi_zolder"
PG_PASS = "IwnadBon2iN"


def run_ssh_command(command):
    """Voer een SSH commando uit op de NAS."""
    full_cmd = [
        "sshpass", "-p", NAS_PASS,
        "ssh", "-o", "StrictHostKeyChecking=no",
        f"{NAS_USER}@{NAS_HOST}",
        command
    ]
    try:
        result = subprocess.run(full_cmd, capture_output=True, text=True, timeout=10)
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        print(f"SSH command timeout: {command}")
        return None
    except Exception as e:
        print(f"SSH error: {e}")
        return None


def parse_loadavg(output):
    """Parse /proc/loadavg output."""
    if not output:
        return None, None, None
    parts = output.split()
    if len(parts) >= 3:
        return float(parts[0]), float(parts[1]), float(parts[2])
    return None, None, None


def parse_memory(output):
    """Parse free -h output."""
    if not output:
        return {}

    result = {}
    lines = output.strip().split('\n')

    for line in lines:
        if line.startswith('Mem:'):
            parts = line.split()
            # Converteer naar GB
            result['mem_total_gb'] = parse_size_to_gb(parts[1])
            result['mem_used_gb'] = parse_size_to_gb(parts[2])
            result['mem_available_gb'] = parse_size_to_gb(parts[6]) if len(parts) > 6 else None
            if result['mem_total_gb'] and result['mem_used_gb']:
                result['mem_used_pct'] = (result['mem_used_gb'] / result['mem_total_gb']) * 100
        elif line.startswith('Swap:'):
            parts = line.split()
            result['swap_total_gb'] = parse_size_to_gb(parts[1])
            result['swap_used_gb'] = parse_size_to_gb(parts[2])

    return result


def parse_size_to_gb(size_str):
    """Converteer size string (bijv. '17Gi', '4.3Gi', '96G') naar GB."""
    if not size_str:
        return None

    # Verwijder trailing 'i' als aanwezig (GiB vs GB)
    size_str = size_str.rstrip('i')

    match = re.match(r'([\d.]+)([KMGTP]?)', size_str)
    if not match:
        return None

    value = float(match.group(1))
    unit = match.group(2)

    multipliers = {'K': 1/1024/1024, 'M': 1/1024, 'G': 1, 'T': 1024, 'P': 1024*1024}
    return value * multipliers.get(unit, 1)


def parse_disk(output):
    """Parse df -h output."""
    if not output:
        return {}

    result = {}
    lines = output.strip().split('\n')

    for line in lines:
        if '/volume1' in line:
            parts = line.split()
            if len(parts) >= 5:
                result['disk_total_tb'] = parse_size_to_gb(parts[1]) / 1024  # Naar TB
                result['disk_used_gb'] = parse_size_to_gb(parts[2])
                result['disk_available_tb'] = parse_size_to_gb(parts[3]) / 1024  # Naar TB
                result['disk_used_pct'] = float(parts[4].rstrip('%'))
            break

    return result


def collect_nas_metrics():
    """Verzamel alle NAS metrics."""
    metrics = {'timestamp': datetime.now()}

    # CPU Load
    loadavg = run_ssh_command("cat /proc/loadavg")
    load1, load5, load15 = parse_loadavg(loadavg)
    metrics['cpu_load_1min'] = load1
    metrics['cpu_load_5min'] = load5
    metrics['cpu_load_15min'] = load15

    # Memory
    memory = run_ssh_command("free -h")
    metrics.update(parse_memory(memory))

    # Disk
    disk = run_ssh_command("df -h /volume1")
    metrics.update(parse_disk(disk))

    return metrics


def save_to_database(metrics):
    """Sla metrics op in PostgreSQL."""
    conn = None
    try:
        conn = psycopg2.connect(
            host=PG_HOST,
            port=PG_PORT,
            database=PG_DB,
            user=PG_USER,
            password=PG_PASS
        )
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO nas_metrics (
                timestamp, cpu_load_1min, cpu_load_5min, cpu_load_15min,
                mem_total_gb, mem_used_gb, mem_available_gb, mem_used_pct,
                swap_total_gb, swap_used_gb,
                disk_total_tb, disk_used_gb, disk_available_tb, disk_used_pct
            ) VALUES (
                %(timestamp)s, %(cpu_load_1min)s, %(cpu_load_5min)s, %(cpu_load_15min)s,
                %(mem_total_gb)s, %(mem_used_gb)s, %(mem_available_gb)s, %(mem_used_pct)s,
                %(swap_total_gb)s, %(swap_used_gb)s,
                %(disk_total_tb)s, %(disk_used_gb)s, %(disk_available_tb)s, %(disk_used_pct)s
            )
        """, metrics)

        conn.commit()
        print(f"[{metrics['timestamp']}] NAS metrics opgeslagen - Load: {metrics.get('cpu_load_1min', 'N/A')}, Mem: {metrics.get('mem_used_pct', 'N/A'):.1f}%, Disk: {metrics.get('disk_used_pct', 'N/A'):.1f}%")

    except Exception as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()


def cleanup_old_metrics(days=7):
    """Verwijder metrics ouder dan X dagen."""
    conn = None
    try:
        conn = psycopg2.connect(
            host=PG_HOST,
            port=PG_PORT,
            database=PG_DB,
            user=PG_USER,
            password=PG_PASS
        )
        cur = conn.cursor()

        cur.execute(f"""
            DELETE FROM nas_metrics
            WHERE timestamp < NOW() - INTERVAL '{days} days'
        """)

        deleted = cur.rowcount
        conn.commit()

        if deleted > 0:
            print(f"Opgeruimd: {deleted} oude metrics verwijderd")

    except Exception as e:
        print(f"Cleanup error: {e}")
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    print("NAS Metrics Collector gestart...")

    # Verzamel en sla metrics op
    metrics = collect_nas_metrics()

    if metrics.get('cpu_load_1min') is not None:
        save_to_database(metrics)
    else:
        print("Kon geen metrics ophalen van NAS")

    # Opruimen van oude data (eens per run)
    cleanup_old_metrics(days=7)
