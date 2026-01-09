#!/usr/bin/env python3
"""
EMSN 2.0 - Retry Decorator Module

Provides retry logic for network operations, database connections, and other
transient failures. Use these decorators to make scripts more robust.

Gebruik:
    from scripts.core.retry import retry, retry_on_exception

    @retry(max_attempts=3, delay=2.0)
    def connect_to_database():
        return psycopg2.connect(**config)

    @retry_on_exception(psycopg2.OperationalError, max_attempts=5)
    def execute_query(conn, query):
        return conn.execute(query)
"""

import functools
import time
from typing import Callable, Type, Tuple, Optional, Any, Union
import logging


def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    max_delay: float = 60.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    logger: Optional[logging.Logger] = None,
) -> Callable:
    """
    Decorator die een functie automatisch herhaalt bij exceptions.

    Args:
        max_attempts: Maximum aantal pogingen (default: 3).
        delay: Initiële wachttijd in seconden tussen pogingen (default: 1.0).
        backoff: Factor waarmee delay vermenigvuldigd wordt na elke poging (default: 2.0).
        max_delay: Maximum wachttijd in seconden (default: 60.0).
        exceptions: Tuple van exception types om te vangen (default: alle Exceptions).
        logger: Optionele logger voor waarschuwingen (default: None).

    Returns:
        Decorated functie met retry logica.

    Example:
        @retry(max_attempts=3, delay=2.0, exceptions=(ConnectionError, TimeoutError))
        def fetch_data():
            return requests.get(url)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            current_delay = delay
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt == max_attempts:
                        if logger:
                            logger.error(
                                f"{func.__name__} failed after {max_attempts} attempts: {e}"
                            )
                        raise

                    if logger:
                        logger.warning(
                            f"{func.__name__} attempt {attempt}/{max_attempts} failed: {e}. "
                            f"Retrying in {current_delay:.1f}s..."
                        )

                    time.sleep(current_delay)
                    current_delay = min(current_delay * backoff, max_delay)

            # Should not reach here, but just in case
            raise last_exception  # type: ignore

        return wrapper
    return decorator


def retry_on_exception(
    *exception_types: Type[Exception],
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    logger: Optional[logging.Logger] = None,
) -> Callable:
    """
    Shorthand decorator voor retry op specifieke exception types.

    Args:
        *exception_types: Exception types om te vangen.
        max_attempts: Maximum aantal pogingen (default: 3).
        delay: Initiële wachttijd in seconden (default: 1.0).
        backoff: Exponential backoff factor (default: 2.0).
        logger: Optionele logger voor waarschuwingen.

    Returns:
        Decorated functie met retry logica.

    Example:
        @retry_on_exception(sqlite3.OperationalError, max_attempts=5)
        def query_database():
            return cursor.execute(sql)
    """
    if not exception_types:
        exception_types = (Exception,)

    return retry(
        max_attempts=max_attempts,
        delay=delay,
        backoff=backoff,
        exceptions=exception_types,
        logger=logger,
    )


def retry_database(
    max_attempts: int = 3,
    delay: float = 2.0,
    logger: Optional[logging.Logger] = None,
) -> Callable:
    """
    Gespecialiseerde retry decorator voor database operaties.

    Vangt veelvoorkomende database exceptions:
    - psycopg2.OperationalError (connection issues)
    - sqlite3.OperationalError (database locked)
    - ConnectionError, TimeoutError

    Args:
        max_attempts: Maximum aantal pogingen (default: 3).
        delay: Initiële wachttijd in seconden (default: 2.0).
        logger: Optionele logger voor waarschuwingen.

    Returns:
        Decorated functie met database-specifieke retry logica.

    Example:
        @retry_database(max_attempts=5)
        def save_detection(conn, data):
            cursor = conn.cursor()
            cursor.execute(INSERT_SQL, data)
            conn.commit()
    """
    # Import here to avoid hard dependency
    try:
        import psycopg2
        pg_exceptions: Tuple[Type[Exception], ...] = (psycopg2.OperationalError,)
    except ImportError:
        pg_exceptions = ()

    try:
        import sqlite3
        sqlite_exceptions: Tuple[Type[Exception], ...] = (sqlite3.OperationalError,)
    except ImportError:
        sqlite_exceptions = ()

    db_exceptions = (
        ConnectionError,
        TimeoutError,
        *pg_exceptions,
        *sqlite_exceptions,
    )

    return retry(
        max_attempts=max_attempts,
        delay=delay,
        backoff=2.0,
        exceptions=db_exceptions,
        logger=logger,
    )


def retry_network(
    max_attempts: int = 3,
    delay: float = 1.0,
    logger: Optional[logging.Logger] = None,
) -> Callable:
    """
    Gespecialiseerde retry decorator voor netwerk operaties.

    Vangt veelvoorkomende netwerk exceptions:
    - ConnectionError, ConnectionRefusedError, ConnectionResetError
    - TimeoutError, socket.timeout
    - urllib.error.URLError
    - OSError (network unreachable)

    Args:
        max_attempts: Maximum aantal pogingen (default: 3).
        delay: Initiële wachttijd in seconden (default: 1.0).
        logger: Optionele logger voor waarschuwingen.

    Returns:
        Decorated functie met netwerk-specifieke retry logica.

    Example:
        @retry_network(max_attempts=5)
        def fetch_api_data(url):
            return urllib.request.urlopen(url).read()
    """
    import socket
    try:
        import urllib.error
        url_exceptions: Tuple[Type[Exception], ...] = (urllib.error.URLError,)
    except ImportError:
        url_exceptions = ()

    network_exceptions = (
        ConnectionError,
        ConnectionRefusedError,
        ConnectionResetError,
        TimeoutError,
        socket.timeout,
        OSError,
        *url_exceptions,
    )

    return retry(
        max_attempts=max_attempts,
        delay=delay,
        backoff=2.0,
        exceptions=network_exceptions,
        logger=logger,
    )


def retry_mqtt(
    max_attempts: int = 3,
    delay: float = 2.0,
    logger: Optional[logging.Logger] = None,
) -> Callable:
    """
    Gespecialiseerde retry decorator voor MQTT operaties.

    Args:
        max_attempts: Maximum aantal pogingen (default: 3).
        delay: Initiële wachttijd in seconden (default: 2.0).
        logger: Optionele logger voor waarschuwingen.

    Returns:
        Decorated functie met MQTT-specifieke retry logica.

    Example:
        @retry_mqtt(max_attempts=5)
        def publish_message(client, topic, payload):
            return client.publish(topic, payload)
    """
    import socket

    mqtt_exceptions = (
        ConnectionError,
        ConnectionRefusedError,
        TimeoutError,
        socket.timeout,
        OSError,
    )

    return retry(
        max_attempts=max_attempts,
        delay=delay,
        backoff=2.0,
        exceptions=mqtt_exceptions,
        logger=logger,
    )


# Convenience function for non-decorator usage
def with_retry(
    func: Callable,
    *args,
    max_attempts: int = 3,
    delay: float = 1.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    logger: Optional[logging.Logger] = None,
    **kwargs,
) -> Any:
    """
    Voer een functie uit met retry logica (non-decorator variant).

    Args:
        func: De functie om uit te voeren.
        *args: Positional arguments voor de functie.
        max_attempts: Maximum aantal pogingen.
        delay: Wachttijd tussen pogingen.
        exceptions: Tuple van exception types om te vangen.
        logger: Optionele logger.
        **kwargs: Keyword arguments voor de functie.

    Returns:
        Resultaat van de functie.

    Example:
        result = with_retry(
            requests.get,
            "http://api.example.com",
            max_attempts=3,
            exceptions=(ConnectionError,)
        )
    """
    current_delay = delay

    for attempt in range(1, max_attempts + 1):
        try:
            return func(*args, **kwargs)
        except exceptions as e:
            if attempt == max_attempts:
                if logger:
                    logger.error(f"Function failed after {max_attempts} attempts: {e}")
                raise

            if logger:
                logger.warning(
                    f"Attempt {attempt}/{max_attempts} failed: {e}. "
                    f"Retrying in {current_delay:.1f}s..."
                )

            time.sleep(current_delay)
            current_delay *= 2.0

    raise RuntimeError("Should not reach here")
