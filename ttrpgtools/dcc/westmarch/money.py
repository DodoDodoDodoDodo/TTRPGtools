"""Where the village's money is, and how that changes night by night.

Coin is never made or lost by play: it moves between purses, tills, the bank and the Finanzamt (``town.move``). The
amount only changes when the bank issues or retires coin. ``supply`` adds it all up; ``record`` writes one row per
night to the ``economy`` table, with the town's debt and a price index, so the experiment leaves a trail.
"""

from __future__ import annotations

import json

from ttrpgtools import dcc
from . import debts, materials, registry, town

SCHEMA = """
CREATE TABLE IF NOT EXISTS economy (
  day INTEGER PRIMARY KEY, date TEXT NOT NULL,
  characters_cp INTEGER, villagers_cp INTEGER, traders_cp INTEGER, tills_cp INTEGER, bank_cp INTEGER, finanzamt_cp INTEGER,
  money_cp INTEGER,           -- everything above
  circulating_cp INTEGER,     -- without the bank's vault and the Finanzamt
  debt_cp INTEGER, price_index REAL
);
"""


def supply(state: dict) -> dict:
    """Coppers by holder. Villagers nobody plays hold the copper rolled for them until somebody takes them over."""
    characters = sum(dcc.coins_total_cp(dcc.load_character(row["id"])["coins"]) for row in dcc.list_characters()
                     if not dcc.load_character(row["id"]).get("dead"))
    db = registry.connect()
    try:
        if state.get("household_mode"):
            from . import households
            households.reconcile(state, db)
        sheets = [json.loads(r["sheet"]) for r in db.execute("SELECT sheet FROM people WHERE status != 'dead' AND claimed_by IS NULL AND sheet IS NOT NULL")]
    finally:
        db.close()
    out = {"characters_cp": characters, "villagers_cp": 0 if state.get("household_mode") else sum(int(s["copper"]) for s in sheets),   # the purses are the households' (households.py)
           "traders_cp": sum(dcc.coins_total_cp(b["coins"]) for b in state.get("bots", {}).values()),
           "tills_cp": sum(int(s.get("till", 0)) for s in state["shops"].values()),
           "library_cp": int(state["money"].get("library", 0)), "caravan_cp": int(state["money"].get("caravan", 0)),
           "households_cp": int(state["money"].get("households", 0)),
           "bank_cp": int(state["money"]["bank"]), "finanzamt_cp": int(state["money"]["finanzamt"])}
    out["money_cp"] = sum(out.values())
    out["circulating_cp"] = out["money_cp"] - out["bank_cp"] - out["finanzamt_cp"] - out["caravan_cp"]
    return out


def _table(db) -> None:
    db.executescript(SCHEMA)
    have = {r["name"] for r in db.execute("PRAGMA table_info(economy)")}
    if "library_cp" not in have:
        db.execute("ALTER TABLE economy ADD COLUMN library_cp INTEGER")
    if "goods" not in have:
        db.execute("ALTER TABLE economy ADD COLUMN goods TEXT")  # JSON: grams of each material, raw and bound in things


def record(state: dict, day: int) -> dict:
    row = {**supply(state), "day": day, "date": town.today().isoformat(), "debt_cp": debts.town_total()["total_cp"],
           "price_index": town.price_index(state, day),
           "goods": json.dumps({m: {"raw_g": c["raw_g"], "things_g": c["things_g"]} for m, c in materials.census(state).items()})}
    db = registry.connect()
    try:
        _table(db)
        with db:
            db.execute("INSERT OR REPLACE INTO economy (day, date, characters_cp, villagers_cp, traders_cp, tills_cp, bank_cp, finanzamt_cp, "
                       "money_cp, circulating_cp, debt_cp, price_index, library_cp, goods) VALUES (:day, :date, :characters_cp, :villagers_cp, :traders_cp, "
                       ":tills_cp, :bank_cp, :finanzamt_cp, :money_cp, :circulating_cp, :debt_cp, :price_index, :library_cp, :goods)", row)
    finally:
        db.close()
    return row


def history(limit: int = 60) -> list[dict]:
    db = registry.connect()
    try:
        _table(db)
        return [dict(r) for r in db.execute("SELECT * FROM economy ORDER BY day DESC LIMIT ?", (limit,))]
    finally:
        db.close()


def fund_villagers(state: dict) -> dict:
    """Bring the copper of every villager nobody plays up to the starting purse (``registry.start_copper`` of the old roll), paid from the
    Finanzamt so the amount of coin does not change; any shortfall is left unpaid. Returns {"villagers", "paid_cp", "short_cp"}."""
    done = {"villagers": 0, "paid_cp": 0, "short_cp": 0}
    if state.get("household_mode"):   # nobody has a purse of their own: the sheet's copper is only what a player's character starts with
        return done
    db = registry.connect()
    try:
        with db:
            for row in db.execute("SELECT id, sheet FROM people WHERE status != 'dead' AND claimed_by IS NULL AND sheet IS NOT NULL").fetchall():
                sheet = json.loads(row["sheet"])
                want = registry.start_copper(int(sheet["copper"]))
                raise_by = want - int(sheet["copper"])
                if raise_by <= 0:
                    continue
                if state["money"]["finanzamt"] < raise_by:
                    done["short_cp"] += raise_by
                    continue
                state["money"]["finanzamt"] -= raise_by
                sheet["copper"] = want
                db.execute("UPDATE people SET sheet = ? WHERE id = ?", (json.dumps(sheet), row["id"]))
                done["villagers"] += 1
                done["paid_cp"] += raise_by
    finally:
        db.close()
    return done
