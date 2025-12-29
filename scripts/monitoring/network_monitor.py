#!/usr/bin/env python3
"""
EMSN Network Monitor - Bewaakt alle netwerkapparaten en services
Slaat status op in PostgreSQL voor Grafana dashboard
"""

import subprocess
import socket
import time
import sys
import os
import json
import logging
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Logging setup
LOG_DIR = Path("/mnt/usb/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "network_monitor.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Core modules path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from core.config import get_postgres_config, get_mqtt_config
    _pg = get_postgres_config()
    _mqtt = get_mqtt_config()
except ImportError as e:
    logger.error(f"Failed to import core modules: {e}")
    sys.exit(1)

# PostgreSQL config (from core module)
PG_CONFIG = _pg

# ============================================================
# NETWERK APPARATEN CONFIGURATIE
# ============================================================
DEVICES = [
    # Raspberry Pi's
    {'name': 'emsn2-zolder', 'ip': '192.168.1.178', 'type': 'pi', 'description': 'Hoofdstation BirdNET-Pi'},
    {'name': 'emsn2-berging', 'ip': '192.168.1.87', 'type': 'pi', 'description': 'Tweede BirdNET-Pi station'},
    {'name': 'emsn2-meteo', 'ip': '192.168.1.156', 'type': 'pi', 'description': 'Davis weerstation integratie'},

    # NAS
    {'name': 'nas-synology', 'ip': '192.168.1.25', 'type': 'nas', 'description': 'Synology DS224Plus'},

    # IoT / Displays
    {'name': 'ulanzi-display', 'ip': '192.168.1.11', 'type': 'display', 'description': 'AWTRIX Light LED matrix'},

    # Router (voor baseline)
    {'name': 'router', 'ip': '192.168.1.1', 'type': 'router', 'description': 'Netwerk router'},
]

# ============================================================
# SERVICES CONFIGURATIE
# ============================================================
SERVICES = [
    # Grafana
    {'device': 'nas-synology', 'name': 'Grafana', 'type': 'http',
     'url': 'http://192.168.1.25:3000/api/health', 'port': 3000},

    # Homer Dashboard
    {'device': 'nas-synology', 'name': 'Homer', 'type': 'http',
     'url': 'http://192.168.1.25:8181', 'port': 8181},

    # PostgreSQL
    {'device': 'nas-synology', 'name': 'PostgreSQL', 'type': 'tcp',
     'port': 5433},

    # Go2RTC (camera streams)
    {'device': 'nas-synology', 'name': 'Go2RTC', 'type': 'http',
     'url': 'http://192.168.1.25:1984/api', 'port': 1984},

    # MQTT Broker (Zolder)
    {'device': 'emsn2-zolder', 'name': 'MQTT-Broker', 'type': 'tcp',
     'port': 1883},

    # Reports API (Zolder)
    {'device': 'emsn2-zolder', 'name': 'Reports-API', 'type': 'http',
     'url': 'http://192.168.1.178:8081/api/nestbox/list', 'port': 8081},

    # Ulanzi API
    {'device': 'ulanzi-display', 'name': 'AWTRIX-API', 'type': 'http',
     'url': 'http://192.168.1.11/api/stats', 'port': 80},

    # BirdNET-Pi Zolder
    {'device': 'emsn2-zolder', 'name': 'BirdNET-Pi', 'type': 'http',
     'url': 'http://192.168.1.178:80', 'port': 80},

    # BirdNET-Pi Berging
    {'device': 'emsn2-berging', 'name': 'BirdNET-Pi', 'type': 'http',
     'url': 'http://192.168.1.87:80', 'port': 80},
]


def ping_device(ip, count=3, timeout=2):
    """Ping een apparaat en return latency en packet loss"""
    try:
        result = subprocess.run(
            ['ping', '-c', str(count), '-W', str(timeout), ip],
            capture_output=True,
            text=True,
            timeout=timeout * count + 5
        )

        if result.returncode == 0:
            # Parse output voor latency
            lines = result.stdout.split('\n')
            for line in lines:
                if 'min/avg/max' in line or 'rtt min/avg/max' in line:
                    # Format: rtt min/avg/max/mdev = 0.123/0.456/0.789/0.012 ms
                    parts = line.split('=')[1].strip().split('/')
                    avg_latency = float(parts[1])
                    return True, avg_latency, 0.0

            # Fallback: parse individuele ping lines
            latencies = []
            for line in lines:
                if 'time=' in line:
                    time_part = line.split('time=')[1].split()[0]
                    latencies.append(float(time_part))

            if latencies:
                return True, sum(latencies) / len(latencies), 0.0
            return True, None, 0.0
        else:
            # Check packet loss
            for line in result.stdout.split('\n'):
                if 'packet loss' in line:
                    loss_pct = float(line.split('%')[0].split()[-1])
                    return loss_pct < 100, None, loss_pct
            return False, None, 100.0

    except subprocess.TimeoutExpired:
        return False, None, 100.0
    except Exception as e:
        logger.error(f"Ping error for {ip}: {e}")
        return False, None, 100.0


def check_tcp_port(host, port, timeout=5):
    """Check of een TCP poort open is"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        start = time.time()
        result = sock.connect_ex((host, port))
        elapsed = (time.time() - start) * 1000  # ms
        sock.close()

        if result == 0:
            return True, elapsed, None
        else:
            return False, None, f"Connection refused (code: {result})"
    except socket.timeout:
        return False, None, "Connection timeout"
    except Exception as e:
        return False, None, str(e)


def check_http_service(url, timeout=10):
    """Check of een HTTP service bereikbaar is"""
    try:
        import urllib.request
        import urllib.error

        start = time.time()
        req = urllib.request.Request(url, method='GET')
        req.add_header('User-Agent', 'EMSN-Network-Monitor/1.0')

        with urllib.request.urlopen(req, timeout=timeout) as response:
            elapsed = (time.time() - start) * 1000  # ms
            return True, elapsed, response.status, None

    except urllib.error.HTTPError as e:
        elapsed = (time.time() - start) * 1000
        # 401/403 betekent service draait, alleen auth nodig
        if e.code in [401, 403]:
            return True, elapsed, e.code, None
        return False, elapsed, e.code, str(e)
    except urllib.error.URLError as e:
        return False, None, None, str(e.reason)
    except Exception as e:
        return False, None, None, str(e)


def check_device(device):
    """Check een apparaat en return resultaat"""
    is_online, latency, packet_loss = ping_device(device['ip'])

    return {
        'device_name': device['name'],
        'device_ip': device['ip'],
        'device_type': device['type'],
        'is_online': is_online,
        'latency_ms': latency,
        'packet_loss_pct': packet_loss,
        'last_seen': datetime.now() if is_online else None
    }


def check_service(service, device_ip_map):
    """Check een service en return resultaat"""
    device_name = service['device']
    device_ip = device_ip_map.get(device_name)

    if not device_ip:
        return None

    if service['type'] == 'http':
        is_available, response_time, status_code, error = check_http_service(service['url'])
    elif service['type'] == 'tcp':
        is_available, response_time, error = check_tcp_port(device_ip, service['port'])
        status_code = None
    else:
        return None

    return {
        'device_name': device_name,
        'service_name': service['name'],
        'service_type': service['type'],
        'is_available': is_available,
        'response_time_ms': response_time,
        'status_code': status_code,
        'error_message': error if not is_available else None
    }


def save_to_database(device_results, service_results):
    """Sla resultaten op in PostgreSQL"""
    try:
        import psycopg2

        conn = psycopg2.connect(**PG_CONFIG)
        cursor = conn.cursor()

        # Device status opslaan
        for result in device_results:
            cursor.execute("""
                INSERT INTO network_status
                (device_name, device_ip, device_type, is_online, latency_ms,
                 packet_loss_pct, last_seen)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                result['device_name'],
                result['device_ip'],
                result['device_type'],
                result['is_online'],
                result['latency_ms'],
                result['packet_loss_pct'],
                result['last_seen']
            ))

        # Service status opslaan
        for result in service_results:
            if result:
                cursor.execute("""
                    INSERT INTO service_status
                    (device_name, service_name, service_type, is_available,
                     response_time_ms, status_code, error_message)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    result['device_name'],
                    result['service_name'],
                    result['service_type'],
                    result['is_available'],
                    result['response_time_ms'],
                    result['status_code'],
                    result['error_message']
                ))

        conn.commit()
        cursor.close()
        conn.close()

        logger.info(f"Saved {len(device_results)} device results and {len([r for r in service_results if r])} service results")
        return True

    except Exception as e:
        logger.error(f"Database error: {e}")
        return False


def publish_to_mqtt(device_results, service_results):
    """Publiceer status naar MQTT voor Home Assistant"""
    try:
        import paho.mqtt.client as mqtt

        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        client.username_pw_set(_mqtt.get('username'), _mqtt.get('password'))
        client.connect(_mqtt.get('broker', '192.168.1.178'), _mqtt.get('port', 1883), 60)

        # Samenvatting
        online_count = sum(1 for d in device_results if d['is_online'])
        total_count = len(device_results)

        available_services = sum(1 for s in service_results if s and s['is_available'])
        total_services = len([s for s in service_results if s])

        summary = {
            'timestamp': datetime.now().isoformat(),
            'devices_online': online_count,
            'devices_total': total_count,
            'services_available': available_services,
            'services_total': total_services,
            'all_healthy': online_count == total_count and available_services == total_services
        }

        client.publish('emsn2/network/status', json.dumps(summary), qos=1, retain=True)

        # Per apparaat
        for result in device_results:
            topic = f"emsn2/network/device/{result['device_name']}"
            payload = {
                'online': result['is_online'],
                'latency_ms': result['latency_ms'],
                'packet_loss': result['packet_loss_pct']
            }
            client.publish(topic, json.dumps(payload), qos=0, retain=True)

        client.disconnect()
        logger.info("Published to MQTT")

    except Exception as e:
        logger.warning(f"MQTT publish failed: {e}")


def main():
    """Main monitoring loop"""
    logger.info("=" * 60)
    logger.info("EMSN Network Monitor - Starting scan")
    logger.info("=" * 60)

    start_time = time.time()

    # Device IP map voor service checks
    device_ip_map = {d['name']: d['ip'] for d in DEVICES}

    # Parallel device checks
    device_results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(check_device, device): device for device in DEVICES}
        for future in as_completed(futures):
            result = future.result()
            device_results.append(result)
            status = "ONLINE" if result['is_online'] else "OFFLINE"
            latency = f"{result['latency_ms']:.1f}ms" if result['latency_ms'] else "N/A"
            logger.info(f"  {result['device_name']:20} [{result['device_ip']:15}] {status:8} {latency}")

    # Parallel service checks
    service_results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(check_service, service, device_ip_map): service for service in SERVICES}
        for future in as_completed(futures):
            result = future.result()
            if result:
                service_results.append(result)
                status = "OK" if result['is_available'] else "FAIL"
                response = f"{result['response_time_ms']:.0f}ms" if result['response_time_ms'] else "N/A"
                logger.info(f"  {result['device_name']:15} / {result['service_name']:15} {status:6} {response}")

    # Save to database
    save_to_database(device_results, service_results)

    # Publish to MQTT
    publish_to_mqtt(device_results, service_results)

    elapsed = time.time() - start_time
    logger.info(f"Scan completed in {elapsed:.1f}s")

    # Summary
    online = sum(1 for d in device_results if d['is_online'])
    available = sum(1 for s in service_results if s and s['is_available'])

    logger.info(f"Devices: {online}/{len(device_results)} online")
    logger.info(f"Services: {available}/{len(service_results)} available")


if __name__ == "__main__":
    main()
