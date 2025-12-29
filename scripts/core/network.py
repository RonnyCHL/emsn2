#!/usr/bin/env python3
"""
EMSN 2.0 - Netwerk Configuratie

Centrale definitie van alle netwerk adressen en poorten.
Vervangt 107+ hardcoded IP-adressen verspreid over scripts.

Gebruik:
    from scripts.core.network import HOSTS, PORTS, get_host

    # Direct gebruik
    nas_ip = HOSTS['nas']
    pg_port = PORTS['postgres']

    # Via functie (met validatie)
    zolder_ip = get_host('zolder')
"""

from typing import Dict, Optional


# Alle netwerk hosts in het EMSN systeem
HOSTS: Dict[str, str] = {
    # Raspberry Pi's
    'zolder': '192.168.1.178',      # Pi Zolder - BirdNET-Pi, MQTT broker (hoofd), API server
    'berging': '192.168.1.87',      # Pi Berging - BirdNET-Pi, AtmosBird, MQTT bridge

    # NAS en services
    'nas': '192.168.1.25',          # Synology NAS - PostgreSQL, Grafana, opslag
    'postgres': '192.168.1.25',     # Alias voor NAS (PostgreSQL draait op NAS)
    'grafana': '192.168.1.25',      # Alias voor NAS (Grafana draait op NAS)

    # Displays en IoT
    'ulanzi': '192.168.1.11',       # Ulanzi TC001 LED matrix display

    # Netwerk infrastructuur
    'router': '192.168.1.1',        # Router (voor ping tests)
    'gateway': '192.168.1.1',       # Alias voor router

    # MQTT brokers (voor clarity)
    'mqtt_primary': '192.168.1.178',   # Zolder is primary broker
    'mqtt_secondary': '192.168.1.87',  # Berging is bridge/secondary

    # Localhost aliassen
    'localhost': '127.0.0.1',
    'local': '127.0.0.1',
}


# Standaard poorten
PORTS: Dict[str, int] = {
    # Database
    'postgres': 5433,               # PostgreSQL op NAS (custom port)
    'postgres_default': 5432,       # Standaard PostgreSQL port

    # MQTT
    'mqtt': 1883,                   # Standaard MQTT port
    'mqtt_tls': 8883,               # MQTT over TLS

    # Web services
    'grafana': 3000,                # Grafana dashboard
    'homer': 8181,                  # Homer dashboard
    'reports_api': 8081,            # EMSN Reports API
    'screenshot_server': 8082,      # Ulanzi screenshot server
    'go2rtc': 1984,                 # go2rtc streaming

    # RTSP streaming
    'rtsp': 8554,                   # RTSP streams

    # SSH
    'ssh': 22,
}


# URLs voor services
URLS: Dict[str, str] = {
    'grafana': f"http://{HOSTS['grafana']}:{PORTS['grafana']}",
    'homer': f"http://{HOSTS['nas']}:{PORTS['homer']}",
    'reports_api': f"http://{HOSTS['zolder']}:{PORTS['reports_api']}",
    'screenshot_server': f"http://{HOSTS['zolder']}:{PORTS['screenshot_server']}",
    'go2rtc': f"http://{HOSTS['nas']}:{PORTS['go2rtc']}",
    'ulanzi_api': f"http://{HOSTS['ulanzi']}/api",
}


# Station namen mapping
STATIONS: Dict[str, str] = {
    'zolder': HOSTS['zolder'],
    'berging': HOSTS['berging'],
}


def get_host(name: str) -> str:
    """
    Haal IP adres op voor gegeven host naam.

    Args:
        name: Host naam (bijv. 'zolder', 'nas', 'berging')

    Returns:
        IP adres als string

    Raises:
        KeyError: Als host naam niet bekend is
    """
    name_lower = name.lower()
    if name_lower not in HOSTS:
        valid_hosts = ', '.join(sorted(HOSTS.keys()))
        raise KeyError(
            f"Onbekende host: '{name}'. "
            f"Geldige hosts: {valid_hosts}"
        )
    return HOSTS[name_lower]


def get_port(name: str) -> int:
    """
    Haal poort op voor gegeven service naam.

    Args:
        name: Service naam (bijv. 'postgres', 'mqtt', 'grafana')

    Returns:
        Poort nummer

    Raises:
        KeyError: Als service naam niet bekend is
    """
    name_lower = name.lower()
    if name_lower not in PORTS:
        valid_ports = ', '.join(sorted(PORTS.keys()))
        raise KeyError(
            f"Onbekende service: '{name}'. "
            f"Geldige services: {valid_ports}"
        )
    return PORTS[name_lower]


def get_url(name: str) -> str:
    """
    Haal URL op voor gegeven service.

    Args:
        name: Service naam (bijv. 'grafana', 'reports_api')

    Returns:
        Volledige URL

    Raises:
        KeyError: Als service niet bekend is
    """
    name_lower = name.lower()
    if name_lower not in URLS:
        valid_urls = ', '.join(sorted(URLS.keys()))
        raise KeyError(
            f"Onbekende service URL: '{name}'. "
            f"Geldige services: {valid_urls}"
        )
    return URLS[name_lower]


def get_station_ip(station: str) -> str:
    """
    Haal IP adres op voor gegeven station.

    Args:
        station: Station naam ('zolder' of 'berging')

    Returns:
        IP adres
    """
    return STATIONS.get(station.lower(), HOSTS.get(station.lower()))


# SSH configuratie per host
SSH_CONFIG: Dict[str, Dict[str, str]] = {
    'berging': {
        'host': HOSTS['berging'],
        'user': 'ronny',
    },
    'zolder': {
        'host': HOSTS['zolder'],
        'user': 'ronny',
    },
    'nas': {
        'host': HOSTS['nas'],
        'user': 'ronny',
    },
}


def get_ssh_config(host: str) -> Dict[str, str]:
    """
    Haal SSH configuratie op voor gegeven host.

    Args:
        host: Host naam

    Returns:
        Dict met host en user
    """
    host_lower = host.lower()
    if host_lower in SSH_CONFIG:
        return SSH_CONFIG[host_lower]

    # Fallback: gebruik host IP met default user
    return {
        'host': get_host(host),
        'user': 'ronny',
    }


# Test functie
if __name__ == "__main__":
    print("EMSN Network Configuration")
    print("=" * 40)

    print("\nHosts:")
    for name, ip in sorted(HOSTS.items()):
        print(f"  {name:20} = {ip}")

    print("\nPorts:")
    for name, port in sorted(PORTS.items()):
        print(f"  {name:20} = {port}")

    print("\nURLs:")
    for name, url in sorted(URLS.items()):
        print(f"  {name:20} = {url}")
