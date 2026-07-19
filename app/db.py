from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any, Iterable

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB = BASE_DIR / "instance" / "northstar.sqlite3"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

# ── PostgreSQL support ────────────────────────────────────────────────────────
# When DATABASE_URL is set (Render provides this for Postgres add-ons),
# use psycopg2. Otherwise fall back to SQLite for local development.

_USE_PG = bool(os.getenv("DATABASE_URL"))

if _USE_PG:
    import psycopg2
    import psycopg2.extras

    def _pg_url() -> str:
        url = os.getenv("DATABASE_URL", "")
        # Render uses postgres:// but psycopg2 needs postgresql://
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        return url

    class _PGRow(dict):
        """Dict that also supports attribute and index access like sqlite3.Row."""
        def __getitem__(self, key):
            if isinstance(key, int):
                return list(self.values())[key]
            return super().__getitem__(key)
        def get(self, key, default=None):
            return super().get(key, default)
        def keys(self):
            return super().keys()

    def connect():
        conn = psycopg2.connect(_pg_url(), cursor_factory=psycopg2.extras.RealDictCursor)
        conn.autocommit = False
        return conn

    def execute(sql: str, params: Iterable[Any] = ()) -> None:
        sql = _adapt(sql)
        conn = connect()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, list(params))
            conn.commit()
        finally:
            conn.close()

    def query(sql: str, params: Iterable[Any] = ()) -> list[_PGRow]:
        sql = _adapt(sql)
        conn = connect()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, list(params))
                return [_PGRow(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def query_one(sql: str, params: Iterable[Any] = ()) -> _PGRow | None:
        rows = query(sql, params)
        return rows[0] if rows else None

    def last_insert_id(conn=None) -> int:
        rows = query("SELECT lastval() AS id")
        return rows[0]["id"] if rows else 0

    def _adapt(sql: str) -> str:
        """Convert SQLite ? placeholders to PostgreSQL %s."""
        return sql.replace("?", "%s")

    def init_db() -> None:
        schema = SCHEMA_PATH.read_text()
        # Adapt schema for PostgreSQL
        schema = schema.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
        schema = schema.replace("AUTOINCREMENT", "")
        schema = schema.replace("TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
                                "TIMESTAMPTZ NOT NULL DEFAULT NOW()")
        schema = schema.replace("TEXT NOT NULL DEFAULT (datetime('now'))",
                                "TIMESTAMPTZ NOT NULL DEFAULT NOW()")
        conn = connect()
        try:
            with conn.cursor() as cur:
                cur.execute(schema)
            conn.commit()
        finally:
            conn.close()

    def db_path() -> Path:
        return Path("postgresql://[render]")

else:
    # ── SQLite (local dev) ────────────────────────────────────────────────────

    def db_path() -> Path:
        configured = os.getenv("NORTHSTAR_DB_PATH")
        if configured:
            path = Path(configured)
            if not path.is_absolute():
                path = BASE_DIR / path
        else:
            path = DEFAULT_DB
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def connect() -> sqlite3.Connection:
        conn = sqlite3.connect(db_path())
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def execute(sql: str, params: Iterable[Any] = ()) -> None:
        with connect() as conn:
            conn.execute(sql, list(params))
            conn.commit()

    def query(sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        with connect() as conn:
            return conn.execute(sql, list(params)).fetchall()

    def query_one(sql: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
        with connect() as conn:
            return conn.execute(sql, list(params)).fetchone()

    def last_insert_id(conn=None) -> int:
        with connect() as c:
            return c.execute("SELECT last_insert_rowid()").fetchone()[0]

    def init_db() -> None:
        schema = SCHEMA_PATH.read_text()
        with connect() as conn:
            conn.executescript(schema)
            conn.commit()
