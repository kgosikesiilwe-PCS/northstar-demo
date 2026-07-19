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


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA_PATH.read_text())
        conn.commit()


def query_one(sql: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute(sql, tuple(params)).fetchone()


def query_all(sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
    with connect() as conn:
        return conn.execute(sql, tuple(params)).fetchall()


def execute(sql: str, params: Iterable[Any] = ()) -> int:
    with connect() as conn:
        cur = conn.execute(sql, tuple(params))
        conn.commit()
        return int(cur.lastrowid)
