#!/usr/bin/env python3
"""
Unit tests voor scripts/sync/lifetime_sync.py module.

Test de sync logica, configuratie en utility functies.
Tests worden geskipt als dependencies niet beschikbaar zijn.
"""

import sys
from pathlib import Path
from unittest import TestCase, main, skipIf
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

# Check if sync module can be imported
SYNC_MODULE_AVAILABLE = False
try:
    from sync.lifetime_sync import (
        StationConfig, SyncResult, STATIONS,
        connect_sqlite, connect_postgres,
        get_sqlite_detections, get_postgres_detections
    )
    SYNC_MODULE_AVAILABLE = True
except ImportError as e:
    pass


@skipIf(not SYNC_MODULE_AVAILABLE, "sync module dependencies not available")
class TestStationConfig(TestCase):
    """Tests voor StationConfig dataclass."""

    def test_station_config_creation(self):
        """Test dat StationConfig correct aangemaakt wordt."""
        config = StationConfig(
            name="test",
            sqlite_path=Path("/tmp/test.db"),
            pg_user="test_user",
            detected_by_field="detected_by_test",
        )

        self.assertEqual(config.name, "test")
        self.assertEqual(config.sqlite_path, Path("/tmp/test.db"))
        self.assertEqual(config.pg_user, "test_user")
        self.assertEqual(config.detected_by_field, "detected_by_test")

    def test_stations_dict_contains_zolder(self):
        """Test dat STATIONS dict zolder bevat."""
        self.assertIn("zolder", STATIONS)
        self.assertEqual(STATIONS["zolder"].name, "zolder")
        self.assertEqual(STATIONS["zolder"].pg_user, "birdpi_zolder")

    def test_stations_dict_contains_berging(self):
        """Test dat STATIONS dict berging bevat."""
        self.assertIn("berging", STATIONS)
        self.assertEqual(STATIONS["berging"].name, "berging")
        self.assertEqual(STATIONS["berging"].pg_user, "birdpi_berging")


@skipIf(not SYNC_MODULE_AVAILABLE, "sync module dependencies not available")
class TestSyncResult(TestCase):
    """Tests voor SyncResult dataclass."""

    def test_sync_result_default_values(self):
        """Test dat SyncResult standaard waarden heeft."""
        result = SyncResult()
        self.assertEqual(result.inserted, 0)
        self.assertEqual(result.updated, 0)
        self.assertEqual(result.soft_deleted, 0)
        self.assertEqual(result.errors, 0)

    def test_sync_result_custom_values(self):
        """Test dat SyncResult custom waarden accepteert."""
        result = SyncResult(inserted=10, updated=5, soft_deleted=2, errors=1)
        self.assertEqual(result.inserted, 10)
        self.assertEqual(result.updated, 5)
        self.assertEqual(result.soft_deleted, 2)
        self.assertEqual(result.errors, 1)


@skipIf(not SYNC_MODULE_AVAILABLE, "sync module dependencies not available")
class TestConnectSqlite(TestCase):
    """Tests voor connect_sqlite functie."""

    def test_connect_sqlite_nonexistent_db(self):
        """Test dat connect_sqlite None teruggeeft voor niet-bestaande db."""
        logger = MagicMock()
        # SQLite kan geen directory paden openen
        result = connect_sqlite(Path("/nonexistent/path/test.db"), logger)
        self.assertIsNone(result)
        logger.error.assert_called()

    @patch('sqlite3.connect')
    def test_connect_sqlite_locked_retry(self, mock_connect):
        """Test dat connect_sqlite retry doet bij locked database."""
        import sqlite3

        # First call raises locked error, second succeeds
        mock_conn = MagicMock()
        mock_connect.side_effect = [
            sqlite3.OperationalError("database is locked"),
            mock_conn,
        ]

        logger = MagicMock()
        with patch('time.sleep'):  # Skip actual sleep
            result = connect_sqlite(Path("/tmp/test.db"), logger)

        # Should have tried twice
        self.assertEqual(mock_connect.call_count, 2)
        logger.warning.assert_called()


@skipIf(not SYNC_MODULE_AVAILABLE, "sync module dependencies not available")
class TestConnectPostgres(TestCase):
    """Tests voor connect_postgres functie."""

    @patch('psycopg2.connect')
    def test_connect_postgres_success(self, mock_connect):
        """Test dat connect_postgres verbinding maakt."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        config = {
            "host": "localhost",
            "port": 5432,
            "database": "test",
            "user": "test",
            "password": "test",
        }
        logger = MagicMock()

        result = connect_postgres(config, logger)
        self.assertEqual(result, mock_conn)
        mock_connect.assert_called_once()

    @patch('psycopg2.connect')
    def test_connect_postgres_failure(self, mock_connect):
        """Test dat connect_postgres None teruggeeft bij failure."""
        import psycopg2

        mock_connect.side_effect = psycopg2.OperationalError("Connection refused")

        config = {
            "host": "localhost",
            "port": 5432,
            "database": "test",
            "user": "test",
            "password": "test",
        }
        logger = MagicMock()

        result = connect_postgres(config, logger)
        self.assertIsNone(result)
        logger.error.assert_called()


@skipIf(not SYNC_MODULE_AVAILABLE, "sync module dependencies not available")
class TestGetSqliteDetections(TestCase):
    """Tests voor get_sqlite_detections functie."""

    def test_get_sqlite_detections_empty(self):
        """Test dat lege database lege dict teruggeeft."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        result = get_sqlite_detections(mock_conn)
        self.assertEqual(result, {})


@skipIf(not SYNC_MODULE_AVAILABLE, "sync module dependencies not available")
class TestGetPostgresDetections(TestCase):
    """Tests voor get_postgres_detections functie."""

    def test_get_postgres_detections_empty(self):
        """Test dat lege database lege dicts teruggeeft."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        by_filename, by_datetime = get_postgres_detections(mock_conn, "zolder")
        self.assertEqual(by_filename, {})
        self.assertEqual(by_datetime, {})

    def test_get_postgres_detections_returns_tuple(self):
        """Test dat functie tuple van twee dicts teruggeeft."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        result = get_postgres_detections(mock_conn, "zolder")
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)


if __name__ == '__main__':
    main()
