
import sqlite3
import tempfile
from pathlib import Path

from src.database.connection import get_connection


def test_get_connection_creates_database_with_foreign_keys_enabled():
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "nested" / "database" / "test.db"

        conn = get_connection(db_path)

        assert isinstance(conn, sqlite3.Connection)

        try:
            cursor = conn.execute("PRAGMA foreign_keys")
            assert cursor.fetchone()[0] == 1
        finally:
            conn.close()

        assert db_path.exists()