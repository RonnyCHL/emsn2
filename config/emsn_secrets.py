#!/usr/bin/env python3
"""
EMSN 2.0 - Centrale Secrets Loader

Leest credentials uit .secrets bestand (niet in git).
Alle scripts importeren credentials via dit bestand.

Gebruik:
    from config.secrets import POSTGRES, MQTT, SMTP, NAS, GRAFANA
"""

import os
from pathlib import Path

# Zoek .secrets bestand (relatief aan dit bestand of in home directory)
_SECRETS_LOCATIONS = [
    Path(__file__).parent.parent / '.secrets',  # /home/ronny/emsn2/.secrets
    Path.home() / 'emsn2' / '.secrets',
    Path.home() / '.secrets',
]

_secrets = {}


def _load_secrets():
    """Laad secrets uit .secrets bestand"""
    global _secrets

    secrets_file = None
    for loc in _SECRETS_LOCATIONS:
        if loc.exists():
            secrets_file = loc
            break

    if not secrets_file:
        raise FileNotFoundError(
            f".secrets bestand niet gevonden in: {[str(p) for p in _SECRETS_LOCATIONS]}"
        )

    with open(secrets_file) as f:
        for line in f:
            line = line.strip()
            # Skip comments en lege regels
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, value = line.split('=', 1)
                _secrets[key.strip()] = value.strip()

    return _secrets


def _get(key, default=None):
    """Haal een secret op, laad indien nodig"""
    if not _secrets:
        _load_secrets()
    return _secrets.get(key, default)


# PostgreSQL configuratie
POSTGRES = {
    'host': lambda: _get('PG_HOST', '192.168.1.25'),
    'port': lambda: int(_get('PG_PORT', '5433')),
    'database': lambda: _get('PG_DB', 'emsn'),
    'user': lambda: _get('PG_USER', 'birdpi_zolder'),
    'password': lambda: _get('PG_PASS'),
}


def get_postgres_config():
    """Retourneer PostgreSQL config dict voor psycopg2.connect()"""
    return {
        'host': POSTGRES['host'](),
        'port': POSTGRES['port'](),
        'database': POSTGRES['database'](),
        'user': POSTGRES['user'](),
        'password': POSTGRES['password'](),
    }


# MQTT configuratie
MQTT = {
    'broker': '192.168.1.178',
    'port': 1883,
    'username': lambda: _get('MQTT_USER', 'ecomonitor'),
    'password': lambda: _get('MQTT_PASS'),
}


def get_mqtt_config():
    """Retourneer MQTT config dict"""
    return {
        'broker': MQTT['broker'],
        'port': MQTT['port'],
        'username': MQTT['username'](),
        'password': MQTT['password'](),
    }


# NAS configuratie
NAS = {
    'host': lambda: _get('NAS_HOST', '192.168.1.25'),
    'user': lambda: _get('NAS_USER', 'ronny'),
    'password': lambda: _get('NAS_PASS'),
}


def get_nas_config():
    """Retourneer NAS config dict"""
    return {
        'host': NAS['host'](),
        'user': NAS['user'](),
        'password': NAS['password'](),
    }


# SMTP/Email configuratie
SMTP = {
    'host': lambda: _get('SMTP_HOST', 'smtp.strato.de'),
    'port': lambda: int(_get('SMTP_PORT', '587')),
    'user': lambda: _get('SMTP_USER'),
    'password': lambda: _get('SMTP_PASS'),
}


def get_smtp_config():
    """Retourneer SMTP config dict"""
    return {
        'host': SMTP['host'](),
        'port': SMTP['port'](),
        'user': SMTP['user'](),
        'password': SMTP['password'](),
    }


# Grafana configuratie
GRAFANA = {
    'user': lambda: _get('GRAFANA_USER', 'admin'),
    'password': lambda: _get('GRAFANA_PASS'),
    'api_token': lambda: _get('GRAFANA_API_TOKEN'),
}


def get_grafana_config():
    """Retourneer Grafana config dict"""
    return {
        'user': GRAFANA['user'](),
        'password': GRAFANA['password'](),
        'api_token': GRAFANA['api_token'](),
    }


# Voor direct testen
if __name__ == "__main__":
    print("EMSN Secrets Loader Test")
    print("=" * 40)

    try:
        pg = get_postgres_config()
        print(f"PostgreSQL: {pg['user']}@{pg['host']}:{pg['port']}/{pg['database']}")
        print(f"  Password: {'*' * len(pg['password']) if pg['password'] else 'NIET GEVONDEN'}")

        mqtt = get_mqtt_config()
        print(f"MQTT: {mqtt['username']}@{mqtt['broker']}:{mqtt['port']}")

        smtp = get_smtp_config()
        print(f"SMTP: {smtp['user']}@{smtp['host']}:{smtp['port']}")

        print("\n✅ Alle secrets succesvol geladen!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
