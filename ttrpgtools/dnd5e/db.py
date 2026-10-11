"""One SQLite file holds the bestiary, the parties, the encounters and live combat state.

Rows carry a JSON ``data`` column; the few columns beside it exist only to be
searched or sorted on. WAL mode lets the two gunicorn workers read while one writes.
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

REPO_DIR = Path(__file__).resolve().parent.parent.parent

SCHEMA = """
CREATE TABLE IF NOT EXISTS monsters (
    id       TEXT PRIMARY KEY,
    name     TEXT NOT NULL,
    cr       REAL,
    type     TEXT,
    source   TEXT,
    origin   TEXT NOT NULL,          -- compendium | paste | manual
    official INTEGER NOT NULL DEFAULT 0,
    data     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS monsters_name ON monsters(name COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS monsters_cr ON monsters(cr);

CREATE TABLE IF NOT EXISTS pcs (
    id      TEXT PRIMARY KEY,
    name    TEXT NOT NULL,
    owner   TEXT,
    data    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS encounters (
    id       TEXT PRIMARY KEY,
    name     TEXT NOT NULL,
    owner    TEXT,
    updated  TEXT NOT NULL,
    data     TEXT NOT NULL           -- plan: pc ids, monster ids with counts, notes
);

CREATE TABLE IF NOT EXISTS combats (
    id           TEXT PRIMARY KEY,
    encounter_id TEXT,
    name         TEXT NOT NULL,
    updated      TEXT NOT NULL,
    version      INTEGER NOT NULL DEFAULT 0,
    data         TEXT NOT NULL,      -- live state
    undo         TEXT NOT NULL DEFAULT '[]'
);
"""


def db_path() -> Path:
    return Path(os.environ.get("TTRPG_DND5E_DB") or REPO_DIR / "data" / "dnd5e.sqlite")


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    p = Path(path) if path else db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.executescript(SCHEMA)
    return conn


@contextmanager
def session(path: Path | str | None = None) -> Iterator[sqlite3.Connection]:
    conn = connect(path)
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def row_data(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    data = json.loads(row["data"])
    data["id"] = row["id"]
    return data
