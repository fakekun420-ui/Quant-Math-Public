"""
PostgreSQL Database Connector
Provides data storage and retrieval with metadata tracking
"""

import psycopg2
from psycopg2 import pool, sql
from psycopg2.extras import RealDictCursor
from typing import List, Dict, Any, Optional
import pandas as pd
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def DataStore(*args, **kwargs):
    """
    Factory: returns the SQLite-backed store when called with db_path,
    otherwise the PostgreSQL-based store.

    SQLite mode:
        DataStore(db_path="data.db")

    PostgreSQL mode:
        DataStore(dbname=..., user=..., password=...)
    """
    if 'db_path' in kwargs:
        from .sqlite_store import SQLiteDataStore
        return SQLiteDataStore(**kwargs)

    return _PostgreSQLDataStore(*args, **kwargs)


class _PostgreSQLDataStore:
    """
    PostgreSQL-based data store with time zone awareness
    """

    def __init__(
        self,
        dbname: str,
        user: str,
        password: str,
        host: str = 'localhost',
        port: int = 5432,
        minconn: int = 1,
        maxconn: int = 10
    ):
        """
        Initialize connection pool

        Args:
            dbname: Database name
            user: Database user
            password: Database password
            host: Database host
            port: Database port
            minconn: Minimum connection pool size
            maxconn: Maximum connection pool size
        """
        self.pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=minconn,
            maxconn=maxconn,
            dbname=dbname,
            user=user,
            password=password,
            host=host,
            port=port
        )
        logger.info(f"DataStore initialized with connection pool: {minconn}-{maxconn}")

    def _get_connection(self):
        """Get a connection from the pool"""
        return self.pool.getconn()

    def _return_connection(self, conn):
        """Return a connection to the pool"""
        self.pool.putconn(conn)

    def save(
        self,
        table: str,
        data: List[Dict[str, Any]],
        if_exists: str = 'append',
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Save data to database with metadata tracking

        Args:
            table: Target table name
            data: List of dictionaries representing rows
            if_exists: 'fail', 'replace', or 'append'
            metadata: Additional metadata to store with data

        Returns:
            Number of rows inserted
        """
        if not data:
            logger.warning(f"No data to save to {table}")
            return 0

        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                # Get column names from first row
                columns = list(data[0].keys())
                columns_str = ', '.join(columns)
                placeholders = ', '.join(['%s'] * len(columns))
                insert_query = f"INSERT INTO {table} ({columns_str}) VALUES ({placeholders})"

                # Insert data
                values = [tuple(row.values()) for row in data]
                cursor.executemany(insert_query, values)

                # Get row count
                row_count = cursor.rowcount

                # Save metadata if provided
                if metadata:
                    metadata['table_name'] = table
                    metadata['inserted_at'] = datetime.utcnow()
                    metadata['record_count'] = row_count
                    metadata['columns'] = columns

                    cols_str = ', '.join(metadata.keys())
                    ph_str = ', '.join(['%s'] * len(metadata))
                    insert_meta = f"INSERT INTO data_metadata ({cols_str}) VALUES ({ph_str})"

                    meta_values = tuple(metadata.values())
                    cursor.execute(insert_meta, meta_values)

                conn.commit()
                logger.info(f"Saved {row_count} rows to {table} with metadata")
                return row_count

        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to save data to {table}: {e}")
            raise
        finally:
            self._return_connection(conn)

    def query(
        self,
        query: str,
        params: Optional[tuple] = None,
        fetch: str = 'all'
    ) -> pd.DataFrame:
        """
        Query data from database

        Args:
            query: SQL query string
            params: Query parameters
            fetch: 'all', 'one', or 'none'

        Returns:
            DataFrame with results
        """
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, params or ())

                if fetch == 'all':
                    result = cursor.fetchall()
                elif fetch == 'one':
                    result = cursor.fetchone()
                else:
                    return pd.DataFrame()

                df = pd.DataFrame(result)
                logger.info(f"Query executed successfully: {query[:100]}...")

                return df

        except Exception as e:
            logger.error(f"Query failed: {e}")
            raise
        finally:
            self._return_connection(conn)

    def get_table_schema(self, table: str) -> List[Dict[str, Any]]:
        """
        Get schema information for a table

        Args:
            table: Table name

        Returns:
            List of column information dictionaries
        """
        query = """
        SELECT
            column_name,
            data_type,
            is_nullable,
            column_default
        FROM information_schema.columns
        WHERE table_name = %s
        ORDER BY ordinal_position
        """

        df = self.query(query, (table,))

        return [
            {
                'column': row['column_name'],
                'data_type': row['data_type'],
                'nullable': row['is_nullable'],
                'default': row['column_default']
            }
            for _, row in df.iterrows()
        ]

    def check_data_quality(
        self,
        table: str,
        columns: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Check data quality for a table

        Args:
            table: Table name
            columns: Specific columns to check (all if None)

        Returns:
            Dictionary with quality metrics
        """
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                if columns:
                    col_list = ', '.join([f'"{col}"' for col in columns])
                    query = f"""
                    SELECT
                        COUNT(*) as total_rows,
                        COUNT({col_list}) as non_null_values,
                        COUNT(*) - COUNT({col_list}) as null_values,
                        MIN({col_list}) as min_value,
                        MAX({col_list}) as max_value
                    FROM {table}
                    """
                else:
                    query = f"""
                    SELECT
                        COUNT(*) as total_rows,
                        COUNT(*) as non_null_values,
                        COUNT(*) - COUNT(*) as null_values
                    FROM {table}
                    """

                cursor.execute(query)
                result = cursor.fetchone()

                metrics = {
                    'table': table,
                    'total_rows': result[0],
                    'non_null_rows': result[1],
                    'null_rows': result[2],
                    'completeness': result[1] / result[0] if result[0] > 0 else 0.0
                }

                if columns and result[3] and result[4]:
                    metrics['min_value'] = float(result[3])
                    metrics['max_value'] = float(result[4])
                    metrics['value_range'] = float(result[4]) - float(result[3])

                conn.commit()
                return metrics

        except Exception as e:
            conn.rollback()
            logger.error(f"Data quality check failed for {table}: {e}")
            raise
        finally:
            self._return_connection(conn)

    def cleanup_old_data(self, table: str, days_threshold: int = 365) -> int:
        """
        Remove data older than specified threshold

        Args:
            table: Table name
            days_threshold: Days threshold for cleanup

        Returns:
            Number of rows deleted
        """
        query = f"""
        DELETE FROM {table}
        WHERE timestamp < NOW() - INTERVAL '{days_threshold} days'
        """

        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(query)
                row_count = cursor.rowcount
                conn.commit()
                logger.info(f"Cleaned up {row_count} rows from {table}")
                return row_count

        except Exception as e:
            conn.rollback()
            logger.error(f"Cleanup failed for {table}: {e}")
            raise
        finally:
            self._return_connection(conn)

    def close(self):
        """Close all connections in the pool"""
        self.pool.closeall()
        logger.info("DataStore connection pool closed")
