"""Campaigns: a name, the DM who started it and the builder characters playing in it. The encounter manager
will take its party from here. Stored in the same SQLite file as the encounters (db.py)."""

from __future__ import annotations

import re
import secrets
from datetime import datetime, timezone

from . import db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _row(conn, campaign_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()
    if row is None:
        return None
    members = [m["character_id"] for m in conn.execute(
        "SELECT character_id FROM campaign_members WHERE campaign_id = ? ORDER BY joined", (campaign_id,))]
    return {**(db.row_data(row) or {}), "id": row["id"], "name": row["name"], "dm": row["dm"], "created": row["created"], "characters": members}


def all_campaigns(path=None) -> list[dict]:
    with db.session(path) as conn:
        ids = [r["id"] for r in conn.execute("SELECT id FROM campaigns ORDER BY created")]
        return [_row(conn, i) for i in ids]


def get(campaign_id: str, path=None) -> dict | None:
    with db.session(path) as conn:
        return _row(conn, campaign_id)


def create(name: str, dm: str | None, description: str = "", path=None) -> dict:
    name = name.strip()
    if not name:
        raise ValueError("A campaign needs a name.")
    campaign_id = f"{re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')[:40] or 'campaign'}-{secrets.token_hex(2)}"
    with db.session(path) as conn:
        conn.execute("INSERT INTO campaigns (id, name, dm, created, data) VALUES (?, ?, ?, ?, ?)",
                     (campaign_id, name, dm, _now(), db.dumps({"description": description.strip()})))
        return _row(conn, campaign_id)


def join(campaign_id: str, character_id: str, by: str | None, path=None) -> dict:
    with db.session(path) as conn:
        if _row(conn, campaign_id) is None:
            raise KeyError(campaign_id)
        conn.execute("INSERT OR IGNORE INTO campaign_members (campaign_id, character_id, added_by, joined) VALUES (?, ?, ?, ?)",
                     (campaign_id, character_id, by, _now()))
        return _row(conn, campaign_id)


def leave(campaign_id: str, character_id: str, path=None) -> dict:
    with db.session(path) as conn:
        conn.execute("DELETE FROM campaign_members WHERE campaign_id = ? AND character_id = ?", (campaign_id, character_id))
        campaign = _row(conn, campaign_id)
        if campaign is None:
            raise KeyError(campaign_id)
        return campaign


def of_character(character_id: str, path=None) -> list[dict]:
    """The campaigns this character plays in: id, name, DM."""
    with db.session(path) as conn:
        rows = conn.execute("SELECT c.id, c.name, c.dm FROM campaigns c JOIN campaign_members m ON m.campaign_id = c.id "
                            "WHERE m.character_id = ? ORDER BY m.joined", (character_id,))
        return [dict(r) for r in rows]


def by_character(path=None) -> dict[str, list[str]]:
    """character id -> campaign names, for the character list."""
    with db.session(path) as conn:
        out: dict[str, list[str]] = {}
        for r in conn.execute("SELECT m.character_id, c.name FROM campaign_members m JOIN campaigns c ON c.id = m.campaign_id ORDER BY m.joined"):
            out.setdefault(r["character_id"], []).append(r["name"])
        return out


def delete(campaign_id: str, path=None) -> None:
    """The campaign and its member list; the characters themselves stay."""
    with db.session(path) as conn:
        conn.execute("DELETE FROM campaign_members WHERE campaign_id = ?", (campaign_id,))
        conn.execute("DELETE FROM campaigns WHERE id = ?", (campaign_id,))
