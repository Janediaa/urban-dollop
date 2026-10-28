import sqlite3
from pathlib import Path

def get_connection(db_path: str | Path) -> sqlite3.Connection:
    """Open a SQLite database connection.

    Args:
        db_path: Path to the database file.

    Returns:
        A configured SQLite connection.
    """
    # 1. convert db_path to a Path object if it's a string
    path_obj = Path(db_path)

    # 2. create the parent directory if it doesn't exist
    path_obj.parent.mkdir(parents=True, exist_ok=True)

    # 3. open sqlite3 connection and return it
    conn = sqlite3.connect(path_obj)

    # 4. foreign key support
    conn.execute("PRAGMA foreign_keys = ON;")

    return conn
    