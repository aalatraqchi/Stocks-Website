"""Minimal SQLite helper that replaces the CS50 library's SQL class."""

import sqlite3
from pathlib import Path


class Database:
    """Run parameterized queries against a SQLite database file.

    Mirrors the small part of the CS50 ``SQL`` API this app used:
    ``execute`` returns a list of dict rows for SELECT statements, the new
    row id for INSERT statements, and the number of affected rows otherwise.
    """

    def __init__(self, path):
        self.path = str(path)

    def _connect(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def execute(self, sql, *args):
        connection = self._connect()
        try:
            cursor = connection.execute(sql, args)
            keyword = sql.lstrip().split(None, 1)[0].upper()
            if keyword in ("SELECT", "WITH", "PRAGMA"):
                return [dict(row) for row in cursor.fetchall()]
            connection.commit()
            if keyword == "INSERT":
                return cursor.lastrowid
            return cursor.rowcount
        finally:
            connection.close()

    def init_schema(self, schema_path):
        """Create tables and indexes from a SQL file if they don't exist."""
        script = Path(schema_path).read_text(encoding="utf-8")
        connection = self._connect()
        try:
            connection.executescript(script)
            connection.commit()
        finally:
            connection.close()
