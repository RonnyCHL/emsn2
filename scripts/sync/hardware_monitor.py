#!/usr/bin/env python3
"""
EMSN Hardware Monitor - Zolder Station
Collects comprehensive hardware metrics and stores them in PostgreSQL
"""

import psutil
import subprocess
import psycopg2
import json
import sys
from datetime import datetime
from pathlib import Path
import paho.mqtt.client as mqtt
import time
import os

# Import secrets
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'config'))
try:
    from emsn_secrets import get_postgres_config, get_mqtt_config
    _pg = get_postgres_config()
    _mqtt = get_mqtt_config()
except ImportError:
    _pg = {'host': '192.168.1.25', 'port': 5433, 'database': 'emsn',
           'user': 'birdpi_zolder', 'password': os.environ.get('EMSN_DB_PASSWORD', '')}
    _mqtt = {'broker': '192.168.1.178', 'port': 1883,
             'username': 'ecomonitor', 'password': os.environ.get('EMSN_MQTT_PASSWORD', '')}

# Configuration
STATION_NAME = "zolder"
LOG_DIR = Path("/mnt/usb/logs")

# PostgreSQL Configuration (from secrets)
PG_CONFIG = {
    'host': _pg.get('host', '192.168.1.25'),
    'port': _pg.get('port', 5433),
    'database': _pg.get('database', 'emsn'),
    'user': _pg.get('user', 'birdpi_zolder'),
    'password': _pg.get('password', '')
}

# MQTT Configuration (from secrets)
MQTT_CONFIG = {
    'broker': _mqtt.get('broker', '192.168.1.178'),
    'port': _mqtt.get('port', 1883),
    'username': _mqtt.get('username', 'ecomonitor'),
    'password': _mqtt.get('password', ''),
    'topic_health': 'emsn2/zolder/health/metrics',
    'topic_alerts': 'emsn2/zolder/health/alerts'
}

# Thresholds for health scoring
THRESHOLDS = {
    'cpu_temp_warning': 70.0,
    'cpu_temp_critical': 80.0,
    'cpu_usage_warning': 80.0,
    'cpu_usage_critical': 95.0,
    'memory_warning': 85.0,
    'memory_critical': 95.0,
    'disk_warning': 85.0,
    'disk_critical': 95.0
}

class HardwareLogger:
    """Logger for hardware monitoring"""

    def __init__(self, log_dir):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / f"hardware_monitor_{datetime.now().strftime('%Y%m%d')}.log"

    def log(self, level, message):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] [{level}] {message}"
        print(log_entry)
        with open(self.log_file, 'a') as f:
            f.write(log_entry + '\n')

    def info(self, message):
        self.log('INFO', message)

    def error(self, message):
        self.log('ERROR', message)

    def warning(self, message):
        self.log('WARNING', message)

    def debug(self, message):
        self.log('DEBUG', message)

class RaspberryPiMetrics:
    """Raspberry Pi specific metrics collector"""

    def __init__(self, logger):
        self.logger = logger

    def get_cpu_temperature(self):
        """Get CPU temperature using vcgencmd"""
        try:
            result = subprocess.run(
                ['vcgencmd', 'measure_temp'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                # Output format: temp=42.8'C
                temp_str = result.stdout.strip().replace("temp=", "").replace("'C", "")
                return float(temp_str)
        except Exception as e:
            self.logger.warning(f"Failed to get CPU temperature: {e}")
        return None

    def get_throttling_status(self):
        """Get throttling status using vcgencmd"""
        try:
            result = subprocess.run(
                ['vcgencmd', 'get_throttled'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                # Output format: throttled=0x0
                throttled_hex = result.stdout.strip().replace("throttled=", "")
                throttled_value = int(throttled_hex, 16)

                # Decode throttling bits
                status = {
                    'under_voltage_now': bool(throttled_value & 0x1),
                    'freq_capped_now': bool(throttled_value & 0x2),
                    'throttled_now': bool(throttled_value & 0x4),
                    'soft_temp_limit_now': bool(throttled_value & 0x8),
                    'under_voltage_occurred': bool(throttled_value & 0x10000),
                    'freq_capped_occurred': bool(throttled_value & 0x20000),
                    'throttled_occurred': bool(throttled_value & 0x40000),
                    'soft_temp_limit_occurred': bool(throttled_value & 0x80000)
                }

                return throttled_value, status
        except Exception as e:
            self.logger.warning(f"Failed to get throttling status: {e}")
        return None, {}

class SystemMetrics:
    """System metrics collector"""

    def __init__(self, logger, rpi_metrics):
        self.logger = logger
        self.rpi = rpi_metrics
        self.previous_net_io = None
        self.previous_net_time = None

    def get_cpu_metrics(self):
        """Get CPU usage and load metrics"""
        try:
            # CPU percentage (average over 1 second)
            cpu_percent = psutil.cpu_percent(interval=1)

            # Load averages (1, 5, 15 minutes)
            load_1, load_5, load_15 = os.getloadavg()

            # Temperature
            cpu_temp = self.rpi.get_cpu_temperature()

            return {
                'cpu_usage': cpu_percent,
                'cpu_temp': cpu_temp,
                'load_1min': load_1,
                'load_5min': load_5,
                'load_15min': load_15
            }
        except Exception as e:
            self.logger.error(f"Failed to get CPU metrics: {e}")
            return {}

    def get_memory_metrics(self):
        """Get memory usage metrics"""
        try:
            mem = psutil.virtual_memory()

            return {
                'memory_total': mem.total // (1024 * 1024),  # MB
                'memory_available': mem.available // (1024 * 1024),  # MB
                'memory_used': mem.used // (1024 * 1024),  # MB
                'memory_percent': mem.percent
            }
        except Exception as e:
            self.logger.error(f"Failed to get memory metrics: {e}")
            return {}

    def get_disk_metrics(self):
        """Get disk usage for all mount points"""
        try:
            disks = {}

            # Root filesystem
            root = psutil.disk_usage('/')
            disks['root'] = {
                'total': root.total,
                'used': root.used,
                'free': root.free,
                'percent': root.percent
            }

            # USB mounts
            for mount_point in ['/mnt/usb', '/mnt/audio']:
                if os.path.ismount(mount_point):
                    disk = psutil.disk_usage(mount_point)
                    disks[mount_point] = {
                        'total': disk.total,
                        'used': disk.used,
                        'free': disk.free,
                        'percent': disk.percent
                    }

            return disks
        except Exception as e:
            self.logger.error(f"Failed to get disk metrics: {e}")
            return {}

    def get_network_metrics(self):
        """Get network I/O metrics for eth0"""
        try:
            net_io = psutil.net_io_counters(pernic=True)

            if 'eth0' in net_io:
                eth0 = net_io['eth0']

                metrics = {
                    'bytes_sent': eth0.bytes_sent,
                    'bytes_recv': eth0.bytes_recv,
                    'packets_sent': eth0.packets_sent,
                    'packets_recv': eth0.packets_recv,
                    'errors_in': eth0.errin,
                    'errors_out': eth0.errout,
                    'drops_in': eth0.dropin,
                    'drops_out': eth0.dropout
                }

                # Calculate rate if we have previous measurement
                if self.previous_net_io and self.previous_net_time:
                    time_diff = time.time() - self.previous_net_time
                    if time_diff > 0:
                        metrics['tx_rate_kbps'] = (eth0.bytes_sent - self.previous_net_io.bytes_sent) * 8 / (time_diff * 1024)
                        metrics['rx_rate_kbps'] = (eth0.bytes_recv - self.previous_net_io.bytes_recv) * 8 / (time_diff * 1024)

                # Store for next calculation
                self.previous_net_io = eth0
                self.previous_net_time = time.time()

                return metrics
            else:
                self.logger.warning("eth0 interface not found")
                return {}
        except Exception as e:
            self.logger.error(f"Failed to get network metrics: {e}")
            return {}

    def get_uptime(self):
        """Get system uptime in hours"""
        try:
            boot_time = psutil.boot_time()
            uptime_seconds = time.time() - boot_time
            uptime_hours = uptime_seconds / 3600
            return uptime_hours
        except Exception as e:
            self.logger.error(f"Failed to get uptime: {e}")
            return None

    def check_service_status(self, service_name):
        """Check if a systemd service is running"""
        try:
            result = subprocess.run(
                ['systemctl', 'is-active', service_name],
                capture_output=True,
                text=True,
                timeout=5
            )
            status = result.stdout.strip()
            return 'running' if status == 'active' else 'stopped'
        except Exception as e:
            self.logger.debug(f"Service {service_name} status check failed: {e}")
            return 'unknown'

    def test_network_latency(self, host='192.168.1.1'):
        """Test network latency with ping"""
        try:
            result = subprocess.run(
                ['ping', '-c', '1', '-W', '2', host],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                # Parse ping output for latency
                for line in result.stdout.split('\n'):
                    if 'time=' in line:
                        time_str = line.split('time=')[1].split()[0]
                        return float(time_str)
            return None
        except Exception as e:
            self.logger.debug(f"Network latency test failed: {e}")
            return None

class HealthScoreCalculator:
    """Calculate overall health score based on metrics"""

    def __init__(self, logger):
        self.logger = logger

    def calculate_score(self, metrics):
        """Calculate health score (0-100, higher is better)"""
        score = 100
        issues = []

        # CPU temperature
        if metrics.get('cpu_temp'):
            if metrics['cpu_temp'] >= THRESHOLDS['cpu_temp_critical']:
                score -= 30
                issues.append(f"CPU temp critical: {metrics['cpu_temp']:.1f}°C")
            elif metrics['cpu_temp'] >= THRESHOLDS['cpu_temp_warning']:
                score -= 15
                issues.append(f"CPU temp high: {metrics['cpu_temp']:.1f}°C")

        # CPU usage
        if metrics.get('cpu_usage'):
            if metrics['cpu_usage'] >= THRESHOLDS['cpu_usage_critical']:
                score -= 20
                issues.append(f"CPU usage critical: {metrics['cpu_usage']:.1f}%")
            elif metrics['cpu_usage'] >= THRESHOLDS['cpu_usage_warning']:
                score -= 10
                issues.append(f"CPU usage high: {metrics['cpu_usage']:.1f}%")

        # Memory usage
        if metrics.get('memory_percent'):
            if metrics['memory_percent'] >= THRESHOLDS['memory_critical']:
                score -= 20
                issues.append(f"Memory critical: {metrics['memory_percent']:.1f}%")
            elif metrics['memory_percent'] >= THRESHOLDS['memory_warning']:
                score -= 10
                issues.append(f"Memory high: {metrics['memory_percent']:.1f}%")

        # Disk usage (root)
        if metrics.get('disk_usage'):
            if metrics['disk_usage'] >= THRESHOLDS['disk_critical']:
                score -= 20
                issues.append(f"Disk critical: {metrics['disk_usage']:.1f}%")
            elif metrics['disk_usage'] >= THRESHOLDS['disk_warning']:
                score -= 10
                issues.append(f"Disk high: {metrics['disk_usage']:.1f}%")

        # Throttling
        if metrics.get('throttled_now'):
            score -= 25
            issues.append("System is being throttled")

        # Service status
        if metrics.get('birdnet_status') != 'running':
            score -= 5
            issues.append("BirdNET service not running")

        # Ensure score doesn't go below 0
        score = max(0, score)

        return score, issues

class HardwareMonitor:
    """Main hardware monitoring class"""

    def __init__(self, logger):
        self.logger = logger
        self.rpi_metrics = RaspberryPiMetrics(logger)
        self.system_metrics = SystemMetrics(logger, self.rpi_metrics)
        self.health_calculator = HealthScoreCalculator(logger)
        self.pg_conn = None
        self.mqtt_client = None

    def connect_postgresql(self):
        """Connect to PostgreSQL database"""
        try:
            self.logger.info(f"Connecting to PostgreSQL at {PG_CONFIG['host']}:{PG_CONFIG['port']}")
            self.pg_conn = psycopg2.connect(**PG_CONFIG)
            self.logger.info("PostgreSQL connection established")
            return True
        except psycopg2.Error as e:
            self.logger.error(f"PostgreSQL connection error: {e}")
            return False

    def connect_mqtt(self):
        """Connect to MQTT broker"""
        try:
            self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
            self.mqtt_client.username_pw_set(MQTT_CONFIG['username'], MQTT_CONFIG['password'])
            self.mqtt_client.connect(MQTT_CONFIG['broker'], MQTT_CONFIG['port'], 60)
            self.mqtt_client.loop_start()
            self.logger.info("MQTT connection established")
            return True
        except Exception as e:
            self.logger.warning(f"MQTT connection failed: {e}")
            return False

    def collect_metrics(self):
        """Collect all hardware metrics"""
        self.logger.info("Collecting hardware metrics...")

        metrics = {
            'timestamp': datetime.now()
        }

        # CPU metrics
        cpu = self.system_metrics.get_cpu_metrics()
        metrics.update(cpu)

        # Memory metrics
        memory = self.system_metrics.get_memory_metrics()
        metrics.update(memory)

        # Disk metrics
        disks = self.system_metrics.get_disk_metrics()
        if 'root' in disks:
            metrics['disk_usage'] = disks['root']['percent']
            metrics['disk_total'] = disks['root']['total']
            metrics['disk_available'] = disks['root']['free']

        # Store USB disk info separately
        metrics['disks'] = disks

        # Network metrics
        network = self.system_metrics.get_network_metrics()
        metrics.update(network)

        # Network latency
        latency = self.system_metrics.test_network_latency()
        metrics['network_latency_ms'] = int(latency) if latency else None

        # Uptime
        uptime = self.system_metrics.get_uptime()
        metrics['uptime_hours'] = uptime

        # Throttling status
        throttled_value, throttled_status = self.rpi_metrics.get_throttling_status()
        metrics['throttled_value'] = throttled_value
        metrics['throttled_now'] = throttled_status.get('throttled_now', False)
        metrics['throttled_status'] = throttled_status

        # Service status
        metrics['birdnet_status'] = self.system_metrics.check_service_status('birdnet_analysis.service')
        metrics['mqtt_status'] = 'running' if self.mqtt_client else 'stopped'
        metrics['database_status'] = 'running' if self.pg_conn else 'stopped'

        # Network status
        if latency is not None and latency < 100:
            metrics['network_status'] = 'good'
        elif latency is not None and latency < 500:
            metrics['network_status'] = 'degraded'
        else:
            metrics['network_status'] = 'poor'

        # Calculate health score
        health_score, issues = self.health_calculator.calculate_score(metrics)
        metrics['overall_health_score'] = health_score
        metrics['health_issues'] = issues

        self.logger.info(f"Metrics collected - Health Score: {health_score}/100")
        if issues:
            for issue in issues:
                self.logger.warning(f"Health issue: {issue}")

        return metrics

    def save_to_database(self, metrics):
        """Save metrics to PostgreSQL"""
        if not self.pg_conn:
            self.logger.error("No PostgreSQL connection")
            return False

        try:
            cursor = self.pg_conn.cursor()

            insert_query = """
                INSERT INTO system_health (
                    station, measurement_timestamp, cpu_usage, cpu_temp,
                    memory_usage, memory_total, memory_available,
                    disk_usage, disk_total, disk_available,
                    network_latency_ms, network_status,
                    birdnet_status, mqtt_status, database_status,
                    overall_health_score
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """

            cursor.execute(insert_query, (
                STATION_NAME,
                metrics['timestamp'],
                metrics.get('cpu_usage'),
                metrics.get('cpu_temp'),
                metrics.get('memory_percent'),
                metrics.get('memory_total'),
                metrics.get('memory_available'),
                metrics.get('disk_usage'),
                metrics.get('disk_total'),
                metrics.get('disk_available'),
                metrics.get('network_latency_ms'),
                metrics.get('network_status'),
                metrics.get('birdnet_status'),
                metrics.get('mqtt_status'),
                metrics.get('database_status'),
                metrics.get('overall_health_score')
            ))

            self.pg_conn.commit()
            self.logger.info("Metrics saved to PostgreSQL")
            return True

        except psycopg2.Error as e:
            self.pg_conn.rollback()
            self.logger.error(f"Failed to save metrics to database: {e}")
            return False

    def publish_to_mqtt(self, metrics):
        """Publish metrics to MQTT"""
        if not self.mqtt_client:
            return

        try:
            # Prepare payload
            payload = {
                'station': STATION_NAME,
                'timestamp': metrics['timestamp'].isoformat(),
                'cpu': {
                    'usage': metrics.get('cpu_usage'),
                    'temp': metrics.get('cpu_temp'),
                    'load_1min': metrics.get('load_1min'),
                    'load_5min': metrics.get('load_5min'),
                    'load_15min': metrics.get('load_15min')
                },
                'memory': {
                    'percent': metrics.get('memory_percent'),
                    'total_mb': metrics.get('memory_total'),
                    'available_mb': metrics.get('memory_available')
                },
                'disk': {
                    'percent': metrics.get('disk_usage'),
                    'total_gb': metrics.get('disk_total', 0) // (1024**3),
                    'available_gb': metrics.get('disk_available', 0) // (1024**3)
                },
                'network': {
                    'latency_ms': metrics.get('network_latency_ms'),
                    'status': metrics.get('network_status')
                },
                'uptime_hours': round(metrics.get('uptime_hours', 0), 2),
                'health_score': metrics.get('overall_health_score'),
                'throttled': metrics.get('throttled_now', False)
            }

            self.mqtt_client.publish(
                MQTT_CONFIG['topic_health'],
                json.dumps(payload),
                qos=0,
                retain=True
            )

            # Publish alerts if health score is low
            if metrics.get('overall_health_score', 100) < 80 and metrics.get('health_issues'):
                alert_payload = {
                    'station': STATION_NAME,
                    'timestamp': metrics['timestamp'].isoformat(),
                    'health_score': metrics['overall_health_score'],
                    'issues': metrics['health_issues']
                }
                self.mqtt_client.publish(
                    MQTT_CONFIG['topic_alerts'],
                    json.dumps(alert_payload),
                    qos=1,
                    retain=False
                )

            self.logger.info("Metrics published to MQTT")

        except Exception as e:
            self.logger.error(f"Failed to publish to MQTT: {e}")

    def run(self):
        """Main monitoring run"""
        # Connect to databases
        self.connect_postgresql()
        self.connect_mqtt()

        # Collect metrics
        metrics = self.collect_metrics()

        # Save to database
        if self.pg_conn:
            self.save_to_database(metrics)

        # Publish to MQTT
        if self.mqtt_client:
            self.publish_to_mqtt(metrics)

        # Cleanup
        if self.pg_conn:
            self.pg_conn.close()
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()

def main():
    """Main execution function"""
    logger = HardwareLogger(LOG_DIR)
    logger.info("=" * 80)
    logger.info("EMSN Hardware Monitor - Zolder Station")
    logger.info("=" * 80)

    try:
        monitor = HardwareMonitor(logger)
        monitor.run()
        logger.info("Hardware monitoring completed successfully")

    except Exception as e:
        logger.error(f"Hardware monitoring failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
