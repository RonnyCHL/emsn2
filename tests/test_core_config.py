#!/usr/bin/env python3
"""
Unit tests voor scripts.core.config module.

Test de configuratie loading functies.
"""

import sys
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from core.config import (
    get_postgres_config,
    get_mqtt_config,
    get_smtp_config,
    get_nas_config,
    get_grafana_config,
    clear_config_cache,
    get_project_root,
    get_config_dir,
    validate_config,
    ConfigValidationError,
    get_validated_postgres_config,
    get_validated_mqtt_config,
)


class TestGetPostgresConfig(TestCase):
    """Tests voor get_postgres_config functie."""

    def setUp(self):
        """Reset cache voor elke test."""
        clear_config_cache()

    def test_returns_dict(self):
        """Test dat functie een dictionary teruggeeft."""
        config = get_postgres_config()
        self.assertIsInstance(config, dict)

    def test_contains_required_keys(self):
        """Test dat config alle benodigde keys bevat."""
        config = get_postgres_config()
        required_keys = ['host', 'port', 'database', 'user', 'password']

        for key in required_keys:
            self.assertIn(key, config, f"Key '{key}' ontbreekt in config")

    def test_host_is_string(self):
        """Test dat host een string is."""
        config = get_postgres_config()
        self.assertIsInstance(config['host'], str)

    def test_port_is_int(self):
        """Test dat port een integer is."""
        config = get_postgres_config()
        self.assertIsInstance(config['port'], int)

    def test_caching_enabled_by_default(self):
        """Test dat caching standaard aan staat."""
        config1 = get_postgres_config()
        config2 = get_postgres_config()
        # Should return same object due to caching
        self.assertIs(config1, config2)

    def test_caching_can_be_disabled(self):
        """Test dat caching uitgeschakeld kan worden."""
        config1 = get_postgres_config()
        clear_config_cache()
        config2 = get_postgres_config(cached=False)
        # Different objects, but same content
        self.assertEqual(config1, config2)


class TestGetMQTTConfig(TestCase):
    """Tests voor get_mqtt_config functie."""

    def setUp(self):
        """Reset cache voor elke test."""
        clear_config_cache()

    def test_returns_dict(self):
        """Test dat functie een dictionary teruggeeft."""
        config = get_mqtt_config()
        self.assertIsInstance(config, dict)

    def test_contains_required_keys(self):
        """Test dat config alle benodigde keys bevat."""
        config = get_mqtt_config()
        required_keys = ['broker', 'port', 'username', 'password']

        for key in required_keys:
            self.assertIn(key, config, f"Key '{key}' ontbreekt in config")

    def test_broker_is_string(self):
        """Test dat broker een string is."""
        config = get_mqtt_config()
        self.assertIsInstance(config['broker'], str)

    def test_port_is_int(self):
        """Test dat port een integer is."""
        config = get_mqtt_config()
        self.assertIsInstance(config['port'], int)

    def test_default_port_1883(self):
        """Test dat standaard MQTT port 1883 is."""
        config = get_mqtt_config()
        self.assertEqual(config['port'], 1883)


class TestGetSMTPConfig(TestCase):
    """Tests voor get_smtp_config functie."""

    def setUp(self):
        """Reset cache voor elke test."""
        clear_config_cache()

    def test_returns_dict(self):
        """Test dat functie een dictionary teruggeeft."""
        config = get_smtp_config()
        self.assertIsInstance(config, dict)


class TestGetNASConfig(TestCase):
    """Tests voor get_nas_config functie."""

    def setUp(self):
        """Reset cache voor elke test."""
        clear_config_cache()

    def test_returns_dict(self):
        """Test dat functie een dictionary teruggeeft."""
        config = get_nas_config()
        self.assertIsInstance(config, dict)


class TestGetGrafanaConfig(TestCase):
    """Tests voor get_grafana_config functie."""

    def setUp(self):
        """Reset cache voor elke test."""
        clear_config_cache()

    def test_returns_dict(self):
        """Test dat functie een dictionary teruggeeft."""
        config = get_grafana_config()
        self.assertIsInstance(config, dict)


class TestClearConfigCache(TestCase):
    """Tests voor clear_config_cache functie."""

    def test_clears_cache(self):
        """Test dat cache correct geleegd wordt."""
        # Load config to populate cache
        get_postgres_config()
        get_mqtt_config()

        # Clear cache
        clear_config_cache()

        # Subsequent calls should re-load
        # (We can't directly test this without inspecting internals,
        # but we can verify no exceptions are raised)
        config = get_postgres_config()
        self.assertIsInstance(config, dict)


class TestGetProjectRoot(TestCase):
    """Tests voor get_project_root functie."""

    def test_returns_path(self):
        """Test dat functie een Path teruggeeft."""
        root = get_project_root()
        self.assertIsInstance(root, Path)

    def test_path_exists(self):
        """Test dat path naar bestaande directory wijst."""
        root = get_project_root()
        self.assertTrue(root.exists())

    def test_is_directory(self):
        """Test dat path een directory is."""
        root = get_project_root()
        self.assertTrue(root.is_dir())

    def test_contains_scripts_dir(self):
        """Test dat root de scripts directory bevat."""
        root = get_project_root()
        scripts_dir = root / 'scripts'
        self.assertTrue(scripts_dir.exists())


class TestGetConfigDir(TestCase):
    """Tests voor get_config_dir functie."""

    def test_returns_path(self):
        """Test dat functie een Path teruggeeft."""
        config_dir = get_config_dir()
        self.assertIsInstance(config_dir, Path)

    def test_path_exists(self):
        """Test dat path naar bestaande directory wijst."""
        config_dir = get_config_dir()
        self.assertTrue(config_dir.exists())

    def test_is_config_subdirectory(self):
        """Test dat path de config subdirectory is."""
        config_dir = get_config_dir()
        self.assertEqual(config_dir.name, 'config')


class TestValidateConfig(TestCase):
    """Tests voor validate_config functie."""

    def test_valid_config_passes(self):
        """Test dat geldige config geen exception gooit."""
        config = {'host': '192.168.1.25', 'port': 5433, 'user': 'test'}
        # Should not raise
        validate_config(config, ['host', 'port', 'user'], 'Test')

    def test_missing_key_raises(self):
        """Test dat ontbrekende key ConfigValidationError gooit."""
        config = {'host': '192.168.1.25', 'port': 5433}
        with self.assertRaises(ConfigValidationError) as ctx:
            validate_config(config, ['host', 'port', 'user'], 'Test')
        self.assertIn('Ontbrekende keys', str(ctx.exception))
        self.assertIn('user', str(ctx.exception))

    def test_empty_value_raises(self):
        """Test dat lege value ConfigValidationError gooit."""
        config = {'host': '192.168.1.25', 'port': 5433, 'user': ''}
        with self.assertRaises(ConfigValidationError) as ctx:
            validate_config(config, ['host', 'port', 'user'], 'Test')
        self.assertIn('Lege values', str(ctx.exception))

    def test_none_value_raises(self):
        """Test dat None value ConfigValidationError gooit."""
        config = {'host': '192.168.1.25', 'port': None}
        with self.assertRaises(ConfigValidationError) as ctx:
            validate_config(config, ['host', 'port'], 'Test')
        self.assertIn('Lege values', str(ctx.exception))

    def test_error_mentions_config_name(self):
        """Test dat error message de config naam bevat."""
        config = {}
        with self.assertRaises(ConfigValidationError) as ctx:
            validate_config(config, ['key'], 'PostgreSQL')
        self.assertIn('PostgreSQL', str(ctx.exception))


class TestValidatedConfigs(TestCase):
    """Tests voor validated config functies."""

    def setUp(self):
        """Reset cache voor elke test."""
        clear_config_cache()

    def test_validated_postgres_returns_dict(self):
        """Test dat get_validated_postgres_config dict teruggeeft."""
        # This will raise if config is invalid
        config = get_validated_postgres_config()
        self.assertIsInstance(config, dict)

    def test_validated_mqtt_returns_dict(self):
        """Test dat get_validated_mqtt_config dict teruggeeft."""
        config = get_validated_mqtt_config()
        self.assertIsInstance(config, dict)


if __name__ == '__main__':
    main()
