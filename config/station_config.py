#!/usr/bin/env python3
"""
EMSN 2.0 - Centrale Station Configuratie
Automatische detectie van station op basis van hostname
"""

import socket
import os
import sys
from pathlib import Path

# Import secrets voor credentials
sys.path.insert(0, str(Path(__file__).parent))
try:
    from emsn_secrets import get_postgres_config as _get_pg, get_mqtt_config as _get_mqtt
    _pg_secrets = _get_pg()
    _mqtt_secrets = _get_mqtt()
except ImportError:
    _pg_secrets = {'password': os.environ.get('EMSN_DB_PASSWORD', '')}
    _mqtt_secrets = {'password': os.environ.get('EMSN_MQTT_PASSWORD', '')}

# Station definities
STATIONS = {
    'emsn2-zolder': {
        'name': 'zolder',
        'display_name': 'Zolder Station',
        'type': 'birdnet',
        'ip': '192.168.1.178',
    },
    'emsn2-berging': {
        'name': 'berging',
        'display_name': 'Berging Station',
        'type': 'birdnet',
        'ip': '192.168.1.87',
    },
    'emsn2-meteo': {
        'name': 'meteo',
        'display_name': 'Meteo Station',
        'type': 'weather',
        'ip': '192.168.1.156',
    },
}

# Centrale database configuratie
POSTGRES_CONFIG = {
    'host': '192.168.1.25',
    'port': 5433,
    'database': 'emsn',
}

# Station-specifieke database users (password uit secrets)
_db_pass = _pg_secrets.get('password', '')
POSTGRES_USERS = {
    'zolder': {'user': 'birdpi_zolder', 'password': _db_pass},
    'berging': {'user': 'birdpi_zolder', 'password': _db_pass},
    'meteo': {'user': 'meteopi', 'password': _db_pass},
}

# MQTT configuratie (password uit secrets)
MQTT_CONFIG = {
    'broker': '192.168.1.178',
    'port': 1883,
    'username': _mqtt_secrets.get('username', 'ecomonitor'),
    'password': _mqtt_secrets.get('password', ''),
}

# Paths
PATHS = {
    'birdnet': {
        'sqlite_db': '/home/ronny/BirdNET-Pi/scripts/birds.db',
        'log_dir': '/mnt/usb/logs',
    },
    'weather': {
        'sqlite_db': '/home/ronny/davis-integration/weather_production.db',
        'log_dir': '/home/ronny/sync',
    },
}


def get_hostname():
    """Get current hostname"""
    return socket.gethostname()


def get_station_config():
    """Get configuration for current station based on hostname"""
    hostname = get_hostname()

    if hostname not in STATIONS:
        raise ValueError(f"Unknown station hostname: {hostname}")

    station = STATIONS[hostname]
    station_name = station['name']
    station_type = station['type']

    # Build complete configuration
    config = {
        'station': station,
        'station_name': station_name,
        'station_type': station_type,

        # PostgreSQL config with station-specific credentials
        'postgres': {
            **POSTGRES_CONFIG,
            **POSTGRES_USERS.get(station_name, POSTGRES_USERS['zolder']),
        },

        # MQTT config with station-specific topics
        'mqtt': {
            **MQTT_CONFIG,
            'topic_prefix': f"emsn2/{station_name}",
            'topics': {
                'health': f"emsn2/{station_name}/health/metrics",
                'alerts': f"emsn2/{station_name}/health/alerts",
                'sync_status': f"emsn2/{station_name}/sync/status",
                'sync_stats': f"emsn2/{station_name}/sync/stats",
            },
        },

        # Paths based on station type
        'paths': PATHS.get(station_type, PATHS['birdnet']),
    }

    return config


def get_postgres_config():
    """Get PostgreSQL configuration for current station"""
    config = get_station_config()
    return config['postgres']


def get_mqtt_config():
    """Get MQTT configuration for current station"""
    config = get_station_config()
    return config['mqtt']


def get_station_name():
    """Get station name for current host"""
    config = get_station_config()
    return config['station_name']


# For direct testing
if __name__ == "__main__":
    print(f"Hostname: {get_hostname()}")
    try:
        config = get_station_config()
        print(f"Station: {config['station_name']}")
        print(f"Type: {config['station_type']}")
        print(f"PostgreSQL: {config['postgres']['host']}:{config['postgres']['port']}")
        print(f"MQTT Topics: {config['mqtt']['topics']}")
    except ValueError as e:
        print(f"Error: {e}")
