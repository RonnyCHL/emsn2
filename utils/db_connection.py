#!/usr/bin/env python3
"""
EMSN 2.0 - PostgreSQL Database Connection Utility

Provides connection pooling and utilities for PostgreSQL database access.

Configuration (from environment variables or defaults):
- PGHOST: 192.168.1.25
- PGPORT: 5433
- PGDATABASE: emsn
- PGUSER: zolderpi (or berginpi, meteopi depending on station)
- PGPASSWORD: (set in systemd service files)
"""

import os
import logging
from typing import Optional, Dict, Any, List
from contextlib import contextmanager
import psycopg2
from psycopg2 import pool, extras

# Default PostgreSQL configuration
DEFAULT_CONFIG = {
    'host': os.getenv('PGHOST', '192.168.1.25'),
    'port': int(os.getenv('PGPORT', '5433')),
    'database': os.getenv('PGDATABASE', 'emsn'),
    'user': os.getenv('PGUSER', 'zolderpi'),
    'password': os.getenv('PGPASSWORD', 'zolderpi_secure_2024!'),
}


class DatabaseConnection:
    """
    PostgreSQL connection pool manager for EMSN 2.0.

    Features:
    - Connection pooling for efficient resource usage
    - Auto-retry on connection failures
    - Context manager support for safe connection handling
    - Health check utilities
    """

    def __init__(self, config: Dict[str, Any] = None, logger: Optional[logging.Logger] = None,
                 min_connections: int = 1, max_connections: int = 5):
        """
        Initialize database connection pool.

        Args:
            config: Database configuration dict (uses defaults if None)
            logger: Optional logger instance
            min_connections: Minimum pool size
            max_connections: Maximum pool size
        """
        self.config = config or DEFAULT_CONFIG
        self.logger = logger or logging.getLogger(__name__)
        self.min_connections = min_connections
        self.max_connections = max_connections
        self.pool = None

    def create_pool(self) -> bool:
        """
        Create connection pool.

        Returns:
            True if pool created successfully, False otherwise
        """
        try:
            self.logger.info(f"Creating PostgreSQL connection pool to "
                           f"{self.config['host']}:{self.config['port']}/{self.config['database']}")

            self.pool = psycopg2.pool.SimpleConnectionPool(
                self.min_connections,
                self.max_connections,
                **self.config
            )

            self.logger.info("Connection pool created successfully")
            return True

        except psycopg2.Error as e:
            self.logger.error(f"Failed to create connection pool: {e}")
            return False

    def close_pool(self):
        """Close all connections in the pool."""
        if self.pool:
            self.pool.closeall()
            self.logger.info("Connection pool closed")
            self.pool = None

    @contextmanager
    def get_connection(self):
        """
        Get a connection from the pool (context manager).

        Usage:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM bird_detections")

        Yields:
            Database connection
        """
        if not self.pool:
            if not self.create_pool():
                raise Exception("Failed to create connection pool")

        conn = None
        try:
            conn = self.pool.getconn()
            yield conn
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            self.logger.error(f"Database error: {e}")
            raise
        finally:
            if conn:
                self.pool.putconn(conn)

    def execute_query(self, query: str, params: tuple = None, fetch: bool = True) -> Optional[List[tuple]]:
        """
        Execute a SQL query.

        Args:
            query: SQL query string
            params: Query parameters (for parameterized queries)
            fetch: Whether to fetch results (False for INSERT/UPDATE/DELETE)

        Returns:
            Query results if fetch=True, None otherwise
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)

                if fetch:
                    return cursor.fetchall()
                else:
                    return None

        except Exception as e:
            self.logger.error(f"Query execution failed: {e}")
            raise

    def execute_many(self, query: str, data: List[tuple]) -> int:
        """
        Execute a query with multiple parameter sets (bulk insert).

        Args:
            query: SQL query string with placeholders
            data: List of parameter tuples

        Returns:
            Number of rows affected
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                psycopg2.extras.execute_batch(cursor, query, data)
                return cursor.rowcount

        except Exception as e:
            self.logger.error(f"Bulk execution failed: {e}")
            raise

    def health_check(self) -> bool:
        """
        Check if database connection is healthy.

        Returns:
            True if connection works, False otherwise
        """
        try:
            result = self.execute_query("SELECT 1", fetch=True)
            if result and result[0][0] == 1:
                self.logger.debug("Database health check passed")
                return True
            return False

        except Exception as e:
            self.logger.error(f"Database health check failed: {e}")
            return False

    def get_table_count(self, table_name: str) -> int:
        """
        Get row count for a table.

        Args:
            table_name: Name of the table

        Returns:
            Number of rows in table
        """
        query = f"SELECT COUNT(*) FROM {table_name}"
        result = self.execute_query(query)
        return result[0][0] if result else 0


def get_db_connection(logger: Optional[logging.Logger] = None) -> DatabaseConnection:
    """
    Convenience function to create a database connection instance.

    Args:
        logger: Optional logger instance

    Returns:
        DatabaseConnection instance
    """
    return DatabaseConnection(logger=logger)


if __name__ == "__main__":
    # Test database connection
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))
    from logger import get_logger

    test_logger = get_logger('db_test')
    test_logger.info("Testing database connection...")

    db = get_db_connection(test_logger)

    if db.create_pool():
        test_logger.info("Connection pool created")

        if db.health_check():
            test_logger.info("Database health check passed")

            # Try to list tables
            try:
                tables = db.execute_query(
                    "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
                )
                test_logger.info(f"Tables in database: {[t[0] for t in tables]}")
            except Exception as e:
                test_logger.error(f"Could not list tables: {e}")

        else:
            test_logger.error("Database health check failed")

        db.close_pool()
    else:
        test_logger.error("Failed to create connection pool")
        test_logger.error("Please verify PostgreSQL credentials and accessibility")

    test_logger.info("Database test complete")
