"""The one table that knows where every item of the campaign is.

``data/westmarch/campaign.sqlite``, table ``items``: one row per stack of
things, with its holder. A shop shelf, a character's pack and a trader's pack
are all just holders, so a sale is a quantity leaving one holder and reaching
another, and "who has what" is a single query.

The rest of the code works on plain lists of dicts in memory. ``load`` turns a
holder's rows into such a list and ``replace`` writes a list back, so this
module is the only place that touches the table.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from ttrpgtools import dcc

DB_PATH = Path(os.environ.get("WESTMARCH_DB") or dcc.REPO_DIR / "data" / "westmarch" / "campaign.sqlite")

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
  id              INTEGER PRIMARY KEY,
  holder_type     TEXT NOT NULL,              -- 'shop', 'pc' (a character) or 'bot' (a trader)
  holder_id       TEXT NOT NULL,
  position        INTEGER NOT NULL,           -- order on the shelf or in the pack
  name            TEXT NOT NULL,
  kind            TEXT NOT NULL,              -- weapon, armor, shield, ammo, gear, mount, trade, other, service
  qty             INTEGER,                    -- on a shelf, NULL means it never runs out
  slug            TEXT,                       -- shelf only: the item's id within its shop
  units           INTEGER,                    -- shelf only: pieces per purchase (20 arrows)
  base_cp         INTEGER,                    -- shelf only: usual price in copper
  target          INTEGER,                    -- shelf only: listed quantity; made up to it from material, or brought up to it by villagers
  gone            INTEGER NOT NULL DEFAULT 0, -- shelf only: taken off offer by the admin
  curve_period    INTEGER,
  curve_amplitude REAL,
  curve_phase     INTEGER,
  detail          TEXT,
  equipped        INTEGER NOT NULL DEFAULT 0, -- pack only
  mithril         INTEGER NOT NULL DEFAULT 0, -- pack only
  cost            TEXT,                       -- pack only: what was paid or the listed price, as text
  notes           TEXT,
  paid_cp         INTEGER,                    -- trader packs: purchase price, to sell only at a profit
  bought_day      INTEGER,
  extra           TEXT,                       -- JSON for anything without a column
  updated         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS items_holder ON items (holder_type, holder_id, position);
CREATE INDEX IF NOT EXISTS items_name ON items (name);
"""
PLAIN = ("name", "kind", "qty", "units", "base_cp", "target", "detail", "cost", "notes", "paid_cp", "bought_day")
FLAGS = ("gone", "equipped", "mithril")
CURVE = ("period", "amplitude", "phase")
KNOWN = set(PLAIN) | set(FLAGS) | {"id", "curve"}


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=20)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")      # one disk sync per commit was half the night's time; a crash can lose the last commits, never corrupt
    db.execute("PRAGMA synchronous=NORMAL")
    db.executescript(SCHEMA)
    return db


def _to_dict(row: sqlite3.Row) -> dict:
    """A table row as the dict the shop and inventory code works with. Shelf rows carry id, base price and curve;
    pack rows carry equipped and cost; a key without a value is left out, except ``qty``."""
    item = {"name": row["name"], "kind": row["kind"], "qty": row["qty"]}
    shelf = row["holder_type"] == "shop"
    if shelf:
        item["id"] = row["slug"]
        item["curve"] = {key: row["curve_" + key] for key in CURVE}
        if row["gone"]:
            item["gone"] = True
    else:
        item["equipped"] = bool(row["equipped"])
        item["cost"] = row["cost"]
        item["notes"] = row["notes"] or ""
        if row["mithril"]:
            item["mithril"] = True
    for key in ("units", "base_cp", "target", "detail", "paid_cp", "bought_day") + (("notes",) if shelf else ()):
        if row[key] is not None:
            item[key] = row[key]
    item.update(json.loads(row["extra"]) if row["extra"] else {})
    return item


def load(holder_type: str, holder_id: str, db: sqlite3.Connection | None = None) -> list[dict]:
    own = db is None
    db = db or connect()
    try:
        rows = db.execute("SELECT * FROM items WHERE holder_type = ? AND holder_id = ? ORDER BY position", (holder_type, holder_id)).fetchall()
        return [_to_dict(row) for row in rows]
    finally:
        if own:
            db.close()


def replace(holder_type: str, holder_id: str, items: list[dict], db: sqlite3.Connection | None = None) -> None:
    """Make the holder's rows equal to this list, in one transaction."""
    own = db is None
    db = db or connect()
    now = datetime.now().isoformat(timespec="seconds")
    try:
        with db:
            db.execute("DELETE FROM items WHERE holder_type = ? AND holder_id = ?", (holder_type, holder_id))
            for position, item in enumerate(items):
                curve = item.get("curve") or {}
                extra = {k: v for k, v in item.items() if k not in KNOWN}
                db.execute(
                    "INSERT INTO items (holder_type, holder_id, position, name, kind, qty, slug, units, base_cp, target, gone, curve_period, "
                    "curve_amplitude, curve_phase, detail, equipped, mithril, cost, notes, paid_cp, bought_day, extra, updated) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (holder_type, holder_id, position, item["name"], item["kind"], item.get("qty"), item.get("id"), item.get("units"),
                     item.get("base_cp"), item.get("target"), int(bool(item.get("gone"))), curve.get("period"), curve.get("amplitude"),
                     curve.get("phase"), item.get("detail") or None, int(bool(item.get("equipped"))), int(bool(item.get("mithril"))),
                     None if item.get("cost") is None else str(item["cost"]), item.get("notes") or None, item.get("paid_cp"),
                     item.get("bought_day"), json.dumps(extra, ensure_ascii=False) if extra else None, now))
    finally:
        if own:
            db.close()


def everything() -> list[dict]:
    """Every row with its holder, for the admin's ledger."""
    db = connect()
    try:
        return [dict(row) for row in db.execute("SELECT * FROM items ORDER BY holder_type, holder_id, position")]
    finally:
        db.close()


# ------------------------------------------------------------------ characters keep their pack in the table
class CharacterPacks:
    """Plugged into ``dcc.INVENTORY_STORE``: a character file no longer holds its inventory, the table does."""

    @staticmethod
    def read(character_id: str, character: dict) -> None:
        if character.get("inventory_in_table"):
            character["inventory"] = load("pc", character_id)

    @staticmethod
    def write(character_id: str, character: dict) -> dict:
        """Store the pack in the table; returns the character as it goes into its file (without the pack)."""
        replace("pc", character_id, dcc.ensure_inventory(character))
        return {**{k: v for k, v in character.items() if k != "inventory"}, "inventory_in_table": True}

    @staticmethod
    def forget(character_id: str) -> None:
        replace("pc", character_id, [])
