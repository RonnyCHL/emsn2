#!/usr/bin/env python3
"""
EMSN 2.0 - Centrale Configuratie Module

Wrapper rond emsn_secrets.py met caching en fallback handling.
Alle scripts gebruiken deze module voor configuratie.

Gebruik:
    from scripts.core.config import get_postgres_config, get_mqtt_config

    pg_config = get_postgres_config()
    conn = psycopg2.connect(**pg_config)
"""

import sys
from pathlib import Path
from typing import Dict, Any, Optional

# Voeg config directory toe aan path
_PROJECT_ROOT = Path(__file__).parent.parent.parent
_CONFIG_DIR = _PROJECT_ROOT / 'config'
if str(_CONFIG_DIR) not in sys.path:
    sys.path.insert(0, str(_CONFIG_DIR))

# Cache voor configs
_config_cache: Dict[str, Any] = {}


def _load_secrets_module():
    """Laad emsn_secrets module met goede error handling"""
    try:
        import emsn_secrets
        return emsn_secrets
    except ImportError as e:
        raise ImportError(
            f"emsn_secrets module niet gevonden. "
            f"Controleer dat {_CONFIG_DIR / 'emsn_secrets.py'} bestaat.\n"
            f"Originele error: {e}"
        )
    except FileNotFoundError as e:
        raise FileNotFoundError(
            f".secrets bestand niet gevonden. "
            f"Maak dit bestand aan met de juiste credentials.\n"
            f"Originele error: {e}"
        )


def get_postgres_config(cached: bool = True) -> Dict[str, Any]:
    """
    Haal PostgreSQL configuratie op.

    Args:
        cached: Gebruik cached config indien beschikbaar (default: True)

    Returns:
        Dict met host, port, database, user, password
    """
    cache_key = 'postgres'

    if cached and cache_key in _config_cache:
        return _config_cache[cache_key]

    secrets = _load_secrets_module()
    config = secrets.get_postgres_config()

    if cached:
        _config_cache[cache_key] = config

    return config


def get_mqtt_config(cached: bool = True) -> Dict[str, Any]:
    """
    Haal MQTT broker configuratie op.

    Args:
        cached: Gebruik cached config indien beschikbaar (default: True)

    Returns:
        Dict met broker, port, username, password
    """
    cache_key = 'mqtt'

    if cached and cache_key in _config_cache:
        return _config_cache[cache_key]

    secrets = _load_secrets_module()
    config = secrets.get_mqtt_config()

    if cached:
        _config_cache[cache_key] = config

    return config


def get_smtp_config(cached: bool = True) -> Dict[str, Any]:
    """
    Haal SMTP/email configuratie op.

    Args:
        cached: Gebruik cached config indien beschikbaar (default: True)

    Returns:
        Dict met host, port, user, password
    """
    cache_key = 'smtp'

    if cached and cache_key in _config_cache:
        return _config_cache[cache_key]

    secrets = _load_secrets_module()
    config = secrets.get_smtp_config()

    if cached:
        _config_cache[cache_key] = config

    return config


def get_nas_config(cached: bool = True) -> Dict[str, Any]:
    """
    Haal NAS configuratie op.

    Args:
        cached: Gebruik cached config indien beschikbaar (default: True)

    Returns:
        Dict met host, user, password
    """
    cache_key = 'nas'

    if cached and cache_key in _config_cache:
        return _config_cache[cache_key]

    secrets = _load_secrets_module()
    config = secrets.get_nas_config()

    if cached:
        _config_cache[cache_key] = config

    return config


def get_grafana_config(cached: bool = True) -> Dict[str, Any]:
    """
    Haal Grafana configuratie op.

    Args:
        cached: Gebruik cached config indien beschikbaar (default: True)

    Returns:
        Dict met user, password, api_token
    """
    cache_key = 'grafana'

    if cached and cache_key in _config_cache:
        return _config_cache[cache_key]

    secrets = _load_secrets_module()
    config = secrets.get_grafana_config()

    if cached:
        _config_cache[cache_key] = config

    return config


def clear_config_cache():
    """Wis de config cache (handig voor testing)"""
    global _config_cache
    _config_cache = {}


class ConfigValidationError(Exception):
    """Exception voor ontbrekende of ongeldige configuratie."""
    pass


def validate_config(config: Dict[str, Any], required_keys: list, config_name: str) -> None:
    """
    Valideer dat alle vereiste keys aanwezig zijn in config.

    Args:
        config: De configuratie dictionary om te valideren.
        required_keys: Lijst met vereiste key namen.
        config_name: Naam van de config voor error messages.

    Raises:
        ConfigValidationError: Als vereiste keys ontbreken of leeg zijn.
    """
    missing = []
    empty = []

    for key in required_keys:
        if key not in config:
            missing.append(key)
        elif config[key] is None or config[key] == '':
            empty.append(key)

    errors = []
    if missing:
        errors.append(f"Ontbrekende keys: {', '.join(missing)}")
    if empty:
        errors.append(f"Lege values: {', '.join(empty)}")

    if errors:
        raise ConfigValidationError(
            f"{config_name} configuratie ongeldig. {'; '.join(errors)}. "
            f"Controleer het .secrets bestand."
        )


def get_validated_postgres_config(cached: bool = True) -> Dict[str, Any]:
    """
    Haal PostgreSQL configuratie op met validatie.

    Args:
        cached: Gebruik cached config indien beschikbaar (default: True)

    Returns:
        Dict met host, port, database, user, password

    Raises:
        ConfigValidationError: Als vereiste configuratie ontbreekt.
    """
    config = get_postgres_config(cached)
    validate_config(config, ['host', 'port', 'database', 'user', 'password'], 'PostgreSQL')
    return config


def get_validated_mqtt_config(cached: bool = True) -> Dict[str, Any]:
    """
    Haal MQTT configuratie op met validatie.

    Args:
        cached: Gebruik cached config indien beschikbaar (default: True)

    Returns:
        Dict met broker, port, username, password

    Raises:
        ConfigValidationError: Als vereiste configuratie ontbreekt.
    """
    config = get_mqtt_config(cached)
    validate_config(config, ['broker', 'port', 'username', 'password'], 'MQTT')
    return config


def get_validated_smtp_config(cached: bool = True) -> Dict[str, Any]:
    """
    Haal SMTP configuratie op met validatie.

    Args:
        cached: Gebruik cached config indien beschikbaar (default: True)

    Returns:
        Dict met host, port, user, password

    Raises:
        ConfigValidationError: Als vereiste configuratie ontbreekt.
    """
    config = get_smtp_config(cached)
    validate_config(config, ['host', 'port', 'user', 'password'], 'SMTP')
    return config


def get_project_root() -> Path:
    """Retourneer het project root pad"""
    return _PROJECT_ROOT


def get_config_dir() -> Path:
    """Retourneer het config directory pad"""
    return _CONFIG_DIR


# Export ook de network module functies indien beschikbaar
try:
    from .network import HOSTS, get_host, PORTS
except ImportError:
    # Network module nog niet aangemaakt
    HOSTS = None
    PORTS = None
    get_host = None
