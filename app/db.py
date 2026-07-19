from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any, Iterable

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB = BASE_DIR / "instance" / "northstar.sqlite3"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


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
