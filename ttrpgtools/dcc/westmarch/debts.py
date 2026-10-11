"""The town's debt to the tax office.

Every villager owes, played or not. A player character carries the debt in the character file (``tax_debt_cp``);
a villager nobody plays carries it in the ``people`` table (``debt_cp``). When someone dies, what they owed is
split evenly among everyone still alive, so the town as a whole owes the same as before. Each night the debt grows:
about ``places.INTEREST_MONTHLY`` a month on average, weighted by the phase of the debtor's own moon.
"""

from __future__ import annotations

import hashlib
from datetime import date, timedelta

from ttrpgtools import dcc
from . import clauses, places, registry, town

DAYS_PER_MONTH = 30.44


def moon_of(name: str, chosen: str | None = None) -> str:
    """A character's chosen moon; anyone without one (villagers nobody plays, old characters) gets theirs from the name."""
    ids = [m["id"] for m in places.MOONS]
    return chosen if chosen in ids else ids[int(hashlib.sha1(name.encode()).hexdigest()[:6], 16) % len(ids)]


def _mean_weight(moon_id: str) -> float:
    spec = next(m for m in places.MOONS if m["id"] == moon_id)
    if spec.get("real"):
        return sum(places.INTEREST_BY_PHASE.values()) / len(places.INTEREST_BY_PHASE)
    return sum(places.INTEREST_BY_PHASE[phase] * nights for phase, nights in spec["cycle"]) / sum(n for _, n in spec["cycle"])


def nightly_rate(moon_id: str, on: date, monthly: float | None = None) -> float:
    """The share of a debt added on this night for someone under this moon; ``monthly`` is the average rate it works out to."""
    weight = places.INTEREST_BY_PHASE[town.moon(on, moon_id)["phase"]]
    return (places.INTEREST_MONTHLY if monthly is None else monthly) / DAYS_PER_MONTH * weight / _mean_weight(moon_id)


def _living_characters() -> list[tuple[str, dict]]:
    out = []
    for row in dcc.list_characters():
        ch = dcc.load_character(row["id"])
        if not ch.get("dead"):
            town.tax_debt(ch)
            out.append((row["id"], ch))
    return out


def _villagers(db) -> list:
    """Villagers nobody plays who are not dead (away or missing still owe): they hold their own share of the town's debt."""
    return db.execute("SELECT id, name, debt_cp FROM people WHERE status != 'dead' AND claimed_by IS NULL ORDER BY id").fetchall()


def town_total() -> dict:
    db = registry.connect()
    try:
        folk = _villagers(db)
    finally:
        db.close()
    characters = _living_characters()
    return {"total_cp": sum(ch["tax_debt_cp"] for _, ch in characters) + sum(r["debt_cp"] for r in folk),
            "characters": len(characters), "villagers": len(folk)}


def spread(amount_cp: int, skip_character: str | None = None, skip_villager: int | None = None) -> int:
    """Split a debt evenly among everyone alive except the one it came from. Odd coppers go to the first in line,
    so not a copper is lost. Returns how many people now share it."""
    amount_cp = int(amount_cp)
    db = registry.connect()
    try:
        characters = [(cid, ch) for cid, ch in _living_characters() if cid != skip_character]
        folk = [r for r in _villagers(db) if r["id"] != skip_villager]
        heirs = len(characters) + len(folk)
        if amount_cp <= 0 or not heirs:
            return 0
        share, odd = divmod(amount_cp, heirs)
        for n, (cid, ch) in enumerate(characters):  # characters are saved before the table is written: their packs use the same database
            ch["tax_debt_cp"] += share + (1 if n < odd else 0)
            dcc.save_character(ch, cid)
        with db:
            for n, row in enumerate(folk, start=len(characters)):
                db.execute("UPDATE people SET debt_cp = debt_cp + ? WHERE id = ?", (share + (1 if n < odd else 0), row["id"]))
        return heirs
    finally:
        db.close()


def gather(amount_cp: int, for_character: str) -> int:
    """The reverse of ``spread``, for a death recorded by mistake: take the amount back from everyone else, as far as
    their debts allow. Returns what was collected."""
    db = registry.connect()
    try:
        characters = [(cid, ch) for cid, ch in _living_characters() if cid != for_character]
        folk = _villagers(db)
        heirs = len(characters) + len(folk)
        if amount_cp <= 0 or not heirs:
            return 0
        share, odd = divmod(int(amount_cp), heirs)
        got = 0
        for n, (cid, ch) in enumerate(characters):
            take = min(ch["tax_debt_cp"], share + (1 if n < odd else 0))
            ch["tax_debt_cp"] -= take; got += take
            dcc.save_character(ch, cid)
        with db:
            for n, row in enumerate(folk, start=len(characters)):
                take = min(row["debt_cp"], share + (1 if n < odd else 0))
                db.execute("UPDATE people SET debt_cp = debt_cp - ? WHERE id = ?", (take, row["id"])); got += take
        return got
    finally:
        db.close()


def villager_owes(name: str) -> int:
    """What an unplayed villager owes the tax office (0 for anyone unknown, dead or played: a played villager's debt is the character's)."""
    db = registry.connect()
    try:
        row = db.execute("SELECT debt_cp FROM people WHERE name = ? AND status != 'dead' AND claimed_by IS NULL", (name,)).fetchone()
        return int(row["debt_cp"] or 0) if row else 0
    finally:
        db.close()


def villager_pays(name: str, cp: int) -> int:
    """Take ``cp`` off an unplayed villager's debt, never below zero. Returns what was taken; the caller moves the coin."""
    db = registry.connect()
    try:
        with db:
            owed = db.execute("SELECT debt_cp FROM people WHERE name = ? AND status != 'dead' AND claimed_by IS NULL", (name,)).fetchone()
            take = min(int(cp), int(owed["debt_cp"] or 0)) if owed else 0
            if take > 0:
                db.execute("UPDATE people SET debt_cp = debt_cp - ? WHERE name = ?", (take, name))
        return max(take, 0)
    finally:
        db.close()


def accrue(day: int) -> int:
    """One night's interest for everyone alive, each under their own moon. Returns the coppers added to the town."""
    on = places.EPOCH + timedelta(days=day - 1)
    added = 0
    db = registry.connect()
    try:
        for cid, ch in _living_characters():
            moon = moon_of(ch["name"], ch.get("moon"))
            more = round(ch["tax_debt_cp"] * nightly_rate(moon, on))
            loan = round(int(ch.get("library_loan_cp", 0)) * nightly_rate(moon, on, places.LIBRARY_INTEREST_MONTHLY))  # coin owed to the library's pot
            if clauses.clause_of(ch) == "no_interest":
                loan = 0   # this character's clause: the library asks them for no interest
            if more or loan:
                ch["tax_debt_cp"] += more
                ch["interest_cp"] = int(ch.get("interest_cp", 0)) + more
                ch["library_loan_cp"] = int(ch.get("library_loan_cp", 0)) + loan
                dcc.save_character(ch, cid)
                added += more
        with db:
            for row in _villagers(db):
                more = round(row["debt_cp"] * nightly_rate(moon_of(row["name"]), on))
                if more:
                    db.execute("UPDATE people SET debt_cp = debt_cp + ? WHERE id = ?", (more, row["id"]))
                    added += more
        return added
    finally:
        db.close()
