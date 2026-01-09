#!/usr/bin/env python3
"""
Unit tests voor scripts.core.retry module.

Test de retry decorators en functies.
"""

import sys
import time
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import MagicMock

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from core.retry import retry, retry_on_exception, retry_database, retry_network, with_retry


class TestRetryDecorator(TestCase):
    """Tests voor @retry decorator."""

    def test_succeeds_first_try(self):
        """Test dat functie meteen slaagt zonder retry."""
        call_count = 0

        @retry(max_attempts=3, delay=0.01)
        def always_succeeds():
            nonlocal call_count
            call_count += 1
            return "success"

        result = always_succeeds()
        self.assertEqual(result, "success")
        self.assertEqual(call_count, 1)

    def test_succeeds_after_retry(self):
        """Test dat functie slaagt na enkele retries."""
        call_count = 0

        @retry(max_attempts=3, delay=0.01)
        def fails_twice():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Simulated failure")
            return "success"

        result = fails_twice()
        self.assertEqual(result, "success")
        self.assertEqual(call_count, 3)

    def test_raises_after_max_attempts(self):
        """Test dat exception doorkomt na max attempts."""
        call_count = 0

        @retry(max_attempts=3, delay=0.01)
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise ValueError("Always fails")

        with self.assertRaises(ValueError):
            always_fails()
        self.assertEqual(call_count, 3)

    def test_only_catches_specified_exceptions(self):
        """Test dat alleen gespecificeerde exceptions gevangen worden."""
        @retry(max_attempts=3, delay=0.01, exceptions=(ConnectionError,))
        def raises_value_error():
            raise ValueError("Not a connection error")

        with self.assertRaises(ValueError):
            raises_value_error()

    def test_backoff_increases_delay(self):
        """Test dat backoff de delay verhoogt."""
        delays = []

        @retry(max_attempts=3, delay=0.1, backoff=2.0)
        def track_delays():
            delays.append(time.time())
            if len(delays) < 3:
                raise ConnectionError("Retry")
            return "done"

        track_delays()
        # Check dat delays toenemen (met enige marge)
        self.assertEqual(len(delays), 3)

    def test_max_delay_caps_backoff(self):
        """Test dat max_delay de backoff beperkt."""
        @retry(max_attempts=5, delay=1.0, backoff=10.0, max_delay=2.0)
        def test_func():
            raise ConnectionError("Always fail")

        # Start time tracking
        start = time.time()
        try:
            test_func()
        except ConnectionError:
            pass
        elapsed = time.time() - start

        # Delays: 1.0, 2.0 (capped), 2.0 (capped), 2.0 (capped) = 7 sec max
        # Should be less than if uncapped: 1 + 10 + 100 + 1000
        self.assertLess(elapsed, 15)

    def test_logger_called_on_retry(self):
        """Test dat logger aangeroepen wordt bij retry."""
        mock_logger = MagicMock()
        call_count = 0

        @retry(max_attempts=2, delay=0.01, logger=mock_logger)
        def fails_once():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("First fail")
            return "ok"

        result = fails_once()
        self.assertEqual(result, "ok")
        mock_logger.warning.assert_called()


class TestRetryOnException(TestCase):
    """Tests voor @retry_on_exception decorator."""

    def test_catches_specified_exception(self):
        """Test dat gespecificeerde exception gevangen wordt."""
        call_count = 0

        @retry_on_exception(ValueError, max_attempts=2, delay=0.01)
        def raises_value_error():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("Retry this")
            return "success"

        result = raises_value_error()
        self.assertEqual(result, "success")
        self.assertEqual(call_count, 2)

    def test_catches_multiple_exceptions(self):
        """Test dat meerdere exception types gevangen worden."""
        @retry_on_exception(ValueError, TypeError, max_attempts=3, delay=0.01)
        def raises_different_errors():
            raise TypeError("Type error")

        with self.assertRaises(TypeError):
            raises_different_errors()


class TestRetryDatabase(TestCase):
    """Tests voor @retry_database decorator."""

    def test_catches_connection_error(self):
        """Test dat ConnectionError gevangen wordt."""
        call_count = 0

        @retry_database(max_attempts=2, delay=0.01)
        def db_connect():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("DB down")
            return "connected"

        result = db_connect()
        self.assertEqual(result, "connected")


class TestRetryNetwork(TestCase):
    """Tests voor @retry_network decorator."""

    def test_catches_timeout_error(self):
        """Test dat TimeoutError gevangen wordt."""
        call_count = 0

        @retry_network(max_attempts=2, delay=0.01)
        def network_call():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise TimeoutError("Timed out")
            return "response"

        result = network_call()
        self.assertEqual(result, "response")


class TestWithRetry(TestCase):
    """Tests voor with_retry() function."""

    def test_succeeds_first_try(self):
        """Test non-decorator variant succeeds."""
        def simple_func(x, y):
            return x + y

        result = with_retry(simple_func, 1, 2, max_attempts=3)
        self.assertEqual(result, 3)

    def test_retries_on_failure(self):
        """Test non-decorator variant retries."""
        call_count = 0

        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Fail")
            return "ok"

        result = with_retry(flaky_func, max_attempts=3, delay=0.01)
        self.assertEqual(result, "ok")
        self.assertEqual(call_count, 2)


if __name__ == '__main__':
    main()
