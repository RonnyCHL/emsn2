#!/usr/bin/env python3
"""
Unit tests voor scripts.core.network module.

Test de netwerk configuratie constanten en functies.
"""

import sys
from pathlib import Path
from unittest import TestCase, main

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from core.network import HOSTS, PORTS, get_host


class TestHOSTS(TestCase):
    """Tests voor HOSTS dictionary."""

    def test_hosts_is_dict(self):
        """Test dat HOSTS een dictionary is."""
        self.assertIsInstance(HOSTS, dict)

    def test_contains_zolder(self):
        """Test dat zolder host aanwezig is."""
        self.assertIn('zolder', HOSTS)

    def test_contains_berging(self):
        """Test dat berging host aanwezig is."""
        self.assertIn('berging', HOSTS)

    def test_contains_ulanzi(self):
        """Test dat ulanzi host aanwezig is."""
        self.assertIn('ulanzi', HOSTS)

    def test_contains_nas(self):
        """Test dat NAS host aanwezig is."""
        self.assertIn('nas', HOSTS)

    def test_zolder_ip_format(self):
        """Test dat zolder IP correct formaat heeft."""
        ip = HOSTS['zolder']
        self.assertIsInstance(ip, str)
        # Should be valid IPv4 format
        parts = ip.split('.')
        self.assertEqual(len(parts), 4)

    def test_berging_ip_format(self):
        """Test dat berging IP correct formaat heeft."""
        ip = HOSTS['berging']
        parts = ip.split('.')
        self.assertEqual(len(parts), 4)

    def test_nas_ip_format(self):
        """Test dat NAS IP correct formaat heeft."""
        ip = HOSTS['nas']
        parts = ip.split('.')
        self.assertEqual(len(parts), 4)


class TestPORTS(TestCase):
    """Tests voor PORTS dictionary."""

    def test_ports_is_dict(self):
        """Test dat PORTS een dictionary is."""
        self.assertIsInstance(PORTS, dict)

    def test_contains_postgres(self):
        """Test dat postgres port aanwezig is."""
        self.assertIn('postgres', PORTS)

    def test_contains_mqtt(self):
        """Test dat mqtt port aanwezig is."""
        self.assertIn('mqtt', PORTS)

    def test_contains_grafana(self):
        """Test dat grafana port aanwezig is."""
        self.assertIn('grafana', PORTS)

    def test_postgres_port_is_int(self):
        """Test dat postgres port een integer is."""
        self.assertIsInstance(PORTS['postgres'], int)

    def test_mqtt_port_is_1883(self):
        """Test dat MQTT port 1883 is."""
        self.assertEqual(PORTS['mqtt'], 1883)

    def test_grafana_port_is_3000(self):
        """Test dat Grafana port 3000 is."""
        self.assertEqual(PORTS['grafana'], 3000)


class TestGetHost(TestCase):
    """Tests voor get_host functie."""

    def test_returns_correct_host(self):
        """Test dat get_host correct IP teruggeeft."""
        self.assertEqual(get_host('zolder'), HOSTS['zolder'])
        self.assertEqual(get_host('berging'), HOSTS['berging'])
        self.assertEqual(get_host('nas'), HOSTS['nas'])

    def test_raises_for_unknown(self):
        """Test dat get_host KeyError gooit voor onbekende host."""
        with self.assertRaises(KeyError):
            get_host('nonexistent_host')

    def test_case_insensitive(self):
        """Test dat get_host case-insensitive is."""
        # Both 'zolder' and 'Zolder' should work
        self.assertEqual(get_host('zolder'), get_host('Zolder'))
        self.assertEqual(get_host('NAS'), HOSTS['nas'])


class TestNetworkIntegration(TestCase):
    """Integratie tests voor netwerk configuratie."""

    def test_all_hosts_have_valid_ips(self):
        """Test dat alle hosts geldige IP-adressen hebben."""
        for name, ip in HOSTS.items():
            parts = ip.split('.')
            self.assertEqual(
                len(parts), 4,
                f"Host '{name}' heeft geen geldige IP: {ip}"
            )
            for part in parts:
                num = int(part)
                self.assertGreaterEqual(
                    num, 0,
                    f"Host '{name}' heeft ongeldige IP octet: {part}"
                )
                self.assertLessEqual(
                    num, 255,
                    f"Host '{name}' heeft ongeldige IP octet: {part}"
                )

    def test_all_ports_are_valid(self):
        """Test dat alle ports geldige waarden hebben."""
        for name, port in PORTS.items():
            self.assertIsInstance(
                port, int,
                f"Port '{name}' is geen integer: {port}"
            )
            self.assertGreater(
                port, 0,
                f"Port '{name}' moet positief zijn: {port}"
            )
            self.assertLess(
                port, 65536,
                f"Port '{name}' moet < 65536 zijn: {port}"
            )


if __name__ == '__main__':
    main()
