"""
SQLite-backed data store for local / mobile environments.

Provides the same interface as the PostgreSQL DataStore:
    store = DataStore(db_path="data.db")
    store.save(table_name, df)
    rows = store.query(sql)
    store.close()
"""

import sqlite3
import logging
from typing import List, Dict, Any

import pandas as pd

logger = logging.getLogger(__name__)


class SQLiteDataStore:
    """
    SQLite data store with DataFrame support.
    """

    def __init__(self, db_path: str = "quantmath.db"):
        """
        Initialize SQLite connection.

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        logger.info(f"Initialized SQLite data store at {db_path}")

    def save(self, table_name: str, df: pd.DataFrame,
             if_exists: str = "replace") -> int:
        """
        Save a DataFrame to a table.

        Args:
            table_name: Target table name
            df: DataFrame to persist
            if_exists: 'replace', 'append' or 'fail'

        Returns:
            Number of rows written
        """
        df.to_sql(table_name, self.conn, if_exists=if_exists, index=False)
        return len(df)

    def query(self, sql: str, params: tuple = ()) -> pd.DataFrame:
        """
        Execute a SQL query and return the result as a DataFrame.

        Args:
            sql: SQL query string
            params: Optional query parameters

        Returns:
            Query results as DataFrame
        """
        return pd.read_sql_query(sql, self.conn, params=params)

    def execute(self, sql: str) -> None:
        """Execute a raw SQL statement and commit."""
        self.conn.execute(sql)
        self.conn.commit()

    def tables(self) -> List[str]:
        """List all tables in the database."""
        cur = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")
        return [row[0] for row in cur.fetchall()]

    def close(self):
        """Close the database connection."""
        if self.conn is not None:
            self.conn.close()
            self.conn = None
            logger.info("Closed SQLite data store")


# Backwards-compatible alias
DataStore = SQLiteDataStore
