#!/usr/bin/env python3
"""
Unit tests voor scripts.core.logging module.

Test de EMSNLogger class en get_logger functie.
"""

import sys
import tempfile
import json
from pathlib import Path
from datetime import datetime
from unittest import TestCase, main
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from core.logging import EMSNLogger, get_logger


class TestEMSNLogger(TestCase):
    """Tests voor EMSNLogger class."""

    def setUp(self):
        """Setup test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_log_dir = Path(self.temp_dir)

    def tearDown(self):
        """Cleanup test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_logger_creation(self):
        """Test dat logger correct aangemaakt wordt."""
        logger = EMSNLogger('test_script', log_dir=self.test_log_dir, console=False)

        self.assertEqual(logger.name, 'test_script')
        self.assertEqual(logger.log_dir, self.test_log_dir)
        self.assertFalse(logger.console)

    def test_logger_creates_log_directory(self):
        """Test dat log directory automatisch wordt aangemaakt."""
        new_log_dir = self.test_log_dir / 'new_subdir'
        self.assertFalse(new_log_dir.exists())

        logger = EMSNLogger('test_script', log_dir=new_log_dir, console=False)
        self.assertTrue(new_log_dir.exists())

    def test_log_file_naming(self):
        """Test dat logbestand juiste naam krijgt met datum."""
        logger = EMSNLogger('my_script', log_dir=self.test_log_dir, console=False)

        expected_date = datetime.now().strftime('%Y%m%d')
        expected_filename = f"my_script_{expected_date}.log"

        self.assertEqual(logger.log_file.name, expected_filename)

    def test_info_logging(self):
        """Test INFO level logging."""
        logger = EMSNLogger('test', log_dir=self.test_log_dir, console=False)
        logger.info('Test info message')

        content = logger.log_file.read_text()
        self.assertIn('[INFO]', content)
        self.assertIn('Test info message', content)

    def test_error_logging(self):
        """Test ERROR level logging."""
        logger = EMSNLogger('test', log_dir=self.test_log_dir, console=False)
        logger.error('Test error message')

        content = logger.log_file.read_text()
        self.assertIn('[ERROR]', content)
        self.assertIn('Test error message', content)

    def test_warning_logging(self):
        """Test WARNING level logging."""
        logger = EMSNLogger('test', log_dir=self.test_log_dir, console=False)
        logger.warning('Test warning message')

        content = logger.log_file.read_text()
        self.assertIn('[WARNING]', content)
        self.assertIn('Test warning message', content)

    def test_success_logging(self):
        """Test SUCCESS level logging (EMSN-specifiek)."""
        logger = EMSNLogger('test', log_dir=self.test_log_dir, console=False)
        logger.success('Operation completed')

        content = logger.log_file.read_text()
        self.assertIn('[SUCCESS]', content)
        self.assertIn('Operation completed', content)

    def test_debug_logging(self):
        """Test DEBUG level logging."""
        logger = EMSNLogger('test', log_dir=self.test_log_dir, console=False)
        logger.debug('Debug info')

        content = logger.log_file.read_text()
        self.assertIn('[DEBUG]', content)
        self.assertIn('Debug info', content)

    def test_critical_logging(self):
        """Test CRITICAL level logging."""
        logger = EMSNLogger('test', log_dir=self.test_log_dir, console=False)
        logger.critical('Critical error')

        content = logger.log_file.read_text()
        self.assertIn('[CRITICAL]', content)
        self.assertIn('Critical error', content)

    def test_warn_alias(self):
        """Test dat warn() alias werkt voor warning()."""
        logger = EMSNLogger('test', log_dir=self.test_log_dir, console=False)
        logger.warn('Test warn alias')

        content = logger.log_file.read_text()
        self.assertIn('[WARNING]', content)
        self.assertIn('Test warn alias', content)

    def test_json_format(self):
        """Test JSON format logging."""
        logger = EMSNLogger('test', log_dir=self.test_log_dir, console=False, json_format=True)
        logger.info('JSON test message')

        content = logger.log_file.read_text()
        log_entry = json.loads(content.strip())

        self.assertEqual(log_entry['level'], 'INFO')
        self.assertEqual(log_entry['message'], 'JSON test message')
        self.assertEqual(log_entry['logger'], 'test')
        self.assertIn('timestamp', log_entry)

    def test_timestamp_format(self):
        """Test dat timestamp correct geformatteerd is."""
        logger = EMSNLogger('test', log_dir=self.test_log_dir, console=False)
        logger.info('Timestamp test')

        content = logger.log_file.read_text()
        # Check datetime format: YYYY-MM-DD HH:MM:SS
        import re
        pattern = r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}'
        self.assertTrue(re.search(pattern, content))

    def test_repr(self):
        """Test __repr__ method."""
        logger = EMSNLogger('my_logger', log_dir=self.test_log_dir, console=False)
        repr_str = repr(logger)

        self.assertIn('EMSNLogger', repr_str)
        self.assertIn('my_logger', repr_str)


class TestGetLogger(TestCase):
    """Tests voor get_logger convenience functie."""

    def setUp(self):
        """Setup test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_log_dir = Path(self.temp_dir)

    def tearDown(self):
        """Cleanup test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_logger_returns_emsnlogger(self):
        """Test dat get_logger een EMSNLogger teruggeeft."""
        logger = get_logger('test_name', log_dir=self.test_log_dir)
        self.assertIsInstance(logger, EMSNLogger)

    def test_get_logger_with_name(self):
        """Test dat naam correct wordt doorgegeven."""
        logger = get_logger('my_special_logger', log_dir=self.test_log_dir)
        self.assertEqual(logger.name, 'my_special_logger')

    def test_get_logger_with_json_format(self):
        """Test dat json_format correct wordt doorgegeven."""
        logger = get_logger('test', log_dir=self.test_log_dir, json_format=True)
        self.assertTrue(logger.json_format)

    def test_get_logger_with_mqtt_topic(self):
        """Test dat mqtt_topic correct wordt doorgegeven."""
        logger = get_logger('test', log_dir=self.test_log_dir, mqtt_topic='test/logs')
        self.assertEqual(logger.mqtt_topic, 'test/logs')


class TestLoggerMQTT(TestCase):
    """Tests voor MQTT functionaliteit."""

    def setUp(self):
        """Setup test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_log_dir = Path(self.temp_dir)

    def tearDown(self):
        """Cleanup test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_mqtt_not_connected_without_topic(self):
        """Test dat MQTT niet verbindt zonder topic."""
        logger = EMSNLogger('test', log_dir=self.test_log_dir, console=False)
        self.assertFalse(logger._mqtt_connected)

    def test_disconnect_without_connection(self):
        """Test dat disconnect() niet crasht zonder connectie."""
        logger = EMSNLogger('test', log_dir=self.test_log_dir, console=False)
        # Should not raise
        logger.disconnect()


class TestLoggerDateRotation(TestCase):
    """Tests voor datum rotatie functionaliteit."""

    def setUp(self):
        """Setup test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_log_dir = Path(self.temp_dir)

    def tearDown(self):
        """Cleanup test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_initial_date(self):
        """Test dat initiële datum correct wordt gezet."""
        logger = EMSNLogger('test', log_dir=self.test_log_dir, console=False)
        expected_date = datetime.now().strftime('%Y%m%d')
        self.assertEqual(logger._current_date, expected_date)


if __name__ == '__main__':
    main()
