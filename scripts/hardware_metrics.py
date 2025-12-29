#!/usr/bin/env python3
"""
EMSN 2.0 - Hardware Metrics Collector
Verzamelt system metrics en stuurt ze naar PostgreSQL
"""

import os
import sys
import time
import psutil
import psycopg2
from datetime import datetime
from pathlib import Path

# Import core modules
sys.path.insert(0, str(Path(__file__).parent))
from core.config import get_postgres_config

# Configuration (from core module)
PG_CONFIG = get_postgres_config()

# Detect station name from hostname
HOSTNAME = os.uname().nodename.lower()
if 'zolder' in HOSTNAME:
    STATION = 'birdpi_zolder'
elif 'berging' in HOSTNAME:
    STATION = 'birdpi_berging'
else:
    STATION = HOSTNAME

INTERVAL_SECONDS = 300  # 5 minuten


def get_cpu_temperature():
    """Get CPU temperature on Raspberry Pi"""
    try:
        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
            temp = float(f.read().strip()) / 1000.0
            return round(temp, 1)
    except:
        return None


def get_metrics():
    """Collect all system metrics"""
    metrics = []
    timestamp = datetime.now()

    # CPU Temperature
    cpu_temp = get_cpu_temperature()
    if cpu_temp is not None:
        metrics.append({
            'timestamp': timestamp,
            'type': 'system',
            'name': 'cpu_temperature',
            'value': cpu_temp,
            'unit': 'celsius',
            'component': 'cpu'
        })

    # CPU Usage
    cpu_percent = psutil.cpu_percent(interval=1)
    metrics.append({
        'timestamp': timestamp,
        'type': 'system',
        'name': 'cpu_percent',
        'value': cpu_percent,
        'unit': 'percent',
        'component': 'cpu'
    })

    # Memory
    memory = psutil.virtual_memory()
    metrics.append({
        'timestamp': timestamp,
        'type': 'system',
        'name': 'memory_percent',
        'value': round(memory.percent, 1),
        'unit': 'percent',
        'component': 'memory'
    })
    metrics.append({
        'timestamp': timestamp,
        'type': 'system',
        'name': 'memory_used_mb',
        'value': round(memory.used / 1024 / 1024, 0),
        'unit': 'MB',
        'component': 'memory'
    })

    # Disk
    disk = psutil.disk_usage('/')
    metrics.append({
        'timestamp': timestamp,
        'type': 'system',
        'name': 'disk_percent',
        'value': round(disk.percent, 1),
        'unit': 'percent',
        'component': 'disk'
    })

    # Uptime
    uptime_seconds = time.time() - psutil.boot_time()
    metrics.append({
        'timestamp': timestamp,
        'type': 'system',
        'name': 'uptime_seconds',
        'value': round(uptime_seconds, 0),
        'unit': 'seconds',
        'component': 'system'
    })

    # Load average (1 min)
    load_avg = os.getloadavg()[0]
    metrics.append({
        'timestamp': timestamp,
        'type': 'system',
        'name': 'load_average_1m',
        'value': round(load_avg, 2),
        'unit': 'load',
        'component': 'cpu'
    })

    return metrics


def store_metrics(metrics):
    """Store metrics in PostgreSQL"""
    try:
        conn = psycopg2.connect(**PG_CONFIG)
        cur = conn.cursor()

        for m in metrics:
            cur.execute("""
                INSERT INTO performance_metrics
                (measurement_timestamp, metric_type, metric_name, metric_value, metric_unit, station, component)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                m['timestamp'],
                m['type'],
                m['name'],
                m['value'],
                m['unit'],
                STATION,
                m['component']
            ))

        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Error storing metrics: {e}")
        return False


def main():
    print(f"EMSN Hardware Metrics Collector")
    print(f"Station: {STATION}")
    print(f"Interval: {INTERVAL_SECONDS}s")
    print("-" * 40)

    while True:
        try:
            metrics = get_metrics()
            if store_metrics(metrics):
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Stored {len(metrics)} metrics")
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Failed to store metrics")
        except Exception as e:
            print(f"Error: {e}")

        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
