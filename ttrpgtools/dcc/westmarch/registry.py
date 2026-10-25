"""Villagers and monsters of the campaign, two tables in the campaign database next to the items table.

``people`` follows ``villagers.py``. The playable villagers each carry the rolls of a 0-level character
(``sheet``), made once with a generator seeded by the name. A player creates a character by taking a villager
over: the rolls become a character file, the row remembers who plays it. ``monsters`` comes from the stat lines the
extractor reads out of the owned rulebook (core.json, private). Play changes ``status`` and ``notes``.
"""

from __future__ import annotations

import hashlib
import json
import re
import random
from datetime import datetime

from ttrpgtools import dcc
from . import items, places, villagers

PEOPLE_STATUS = ["alive", "away", "missing", "dead"]
MONSTER_STATUS = ["not met", "rumored", "met", "slain"]
SCHEMA = """
CREATE TABLE IF NOT EXISTS people (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, occupation TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'alive', notes TEXT NOT NULL DEFAULT '', updated TEXT NOT NULL,
  locked INTEGER NOT NULL DEFAULT 0,   -- townsfolk nobody plays
  sheet TEXT,                          -- JSON: the rolls of the villager's 0-level character
  claimed_by TEXT,                     -- login of the player who took the villager over
  character_id TEXT,                   -- and the character that came of it
  debt_cp INTEGER                      -- owed to the tax office while nobody plays the villager (then the character owes it)
);
CREATE TABLE IF NOT EXISTS monsters (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, init TEXT, attack TEXT, ac INTEGER, hd TEXT, move TEXT, act TEXT,
  special TEXT, saves TEXT, alignment TEXT, page INTEGER,
  status TEXT NOT NULL DEFAULT 'not met', notes TEXT NOT NULL DEFAULT '', updated TEXT NOT NULL
);
"""
TABLES = {"people": PEOPLE_STATUS, "monsters": MONSTER_STATUS}


def nudged_luck(name: str) -> int | None:
    """The Luck fate gave instead to someone born with a modifier of +0, or None for the one in five it left alone.
    Drawn from the 3d6 odds outside the +0 band, above or below with equal chance, and the same for a name every time."""
    rng = random.Random(f"villager/{name}/luck")
    if rng.random() >= places.LUCK_NUDGE_CHANCE:
        return None
    up = rng.random() < 0.5
    while True:
        score = sum(rng.randint(1, 6) for _ in range(3))
        if (score > 12) if up else (score < 9):
            return score


def apply_luck_rule(content: dict) -> list[tuple[str, int, int]]:
    """Once per existing character: whoever was born with Luck +0 gets the same nudge the villagers got, retroactively.
    Returns (name, old Luck, new Luck) for those who changed."""
    changed = []
    for row in dcc.list_characters():
        ch = dcc.load_character(row["id"])
        if ch.get("luck_rule"):
            continue
        old = int(ch["abilities"]["luck"])
        new = nudged_luck(ch["name"]) if dcc.ability_mod(content, old) == 0 else None
        if new is not None:
            dcc.rebirth_luck(ch, content, new)
            changed.append((ch["name"], old, new))
        ch["luck_rule"] = True
        dcc.save_character(ch, row["id"])
    return changed


def start_copper(rolled: int) -> int:
    """The coin a new character starts with: ``places.START_PURSE_CP``, swayed by the 5d12 roll (5 to 60) from 0,8 to 1,2 times."""
    return round(places.START_PURSE_CP * (0.8 + 0.4 * (max(5, min(60, int(rolled))) - 5) / 55))


def occupation_entry(content: dict, name: str) -> dict | None:
    """An occupation of the rulebook's table, or one of the village's own trades (lives.role_entries)."""
    found = next((o for o in content["occupations"] if o["occupation"] == name), None)
    if found:
        return found
    from . import lives
    return next((o for o in lives.role_entries(content) if o["occupation"] == name), None)


def roll_villager(content: dict, name: str, occupation_name: str, abilities: dict | None = None) -> dict | None:
    """The rolls of one villager's 0-level character, the same for the same name every time. None when the
    occupation is not on the rulebook's table. ``abilities`` are the six scores a child inherited, in place of the 3d6 in order."""
    occupation = occupation_entry(content, occupation_name)
    if not occupation:
        return None
    rng = random.Random(f"villager/{name}")
    d = lambda n, sides: sum(rng.randint(1, sides) for _ in range(n))
    rolled = {a: d(3, 6) for a in dcc.ABILITIES}
    sheet = {"abilities": dict(abilities) if abilities else rolled, "occupation": occupation_name, "augur_roll": rng.randint(1, 30),
             "hp_roll": rng.randint(1, 4), "copper": start_copper(d(5, 12)), "equipment_roll": rng.randint(1, 24),
             "extras": {e["key"]: rng.randint(1, e["die"]) for e in dcc.occupation_extras(content, occupation)}, "luck_rule": 1}
    if not abilities and dcc.ability_mod(content, sheet["abilities"]["luck"]) == 0:  # its own generator: every other roll stays what it was
        sheet["abilities"]["luck"] = nudged_luck(name) or sheet["abilities"]["luck"]
    return sheet


def build_character(content: dict, name: str, sheet: dict, alignment: str = "neutral", owner: str | None = None) -> dict:
    occupation = occupation_entry(content, sheet["occupation"])
    augur = next(a for a in content["luck_augurs"] if a["roll"] == sheet["augur_roll"])
    item = next(e for e in content["equipment"] if e["roll"] == sheet["equipment_roll"])
    return dcc.new_character(name, sheet["abilities"], occupation, augur, sheet["hp_roll"], sheet["copper"], item["item"],
                             alignment, owner, content, sheet.get("extras") or {})


def connect():
    db = items.connect()
    db.executescript(SCHEMA)
    have = {row["name"] for row in db.execute("PRAGMA table_info(people)")}
    for column, kind in (("locked", "INTEGER NOT NULL DEFAULT 0"), ("sheet", "TEXT"), ("claimed_by", "TEXT"), ("character_id", "TEXT"), ("debt_cp", "INTEGER"),
                         ("born_day", "INTEGER"), ("sex", "TEXT"), ("race", "TEXT"), ("spouse_id", "INTEGER"), ("mother_id", "INTEGER"), ("father_id", "INTEGER"),
                         ("genes", "TEXT"), ("died_day", "INTEGER"), ("cause", "TEXT"), ("seat", "TEXT"), ("household_id", "INTEGER")):   # the last nine: ageing (lives.py); children born in play have no row in villagers.py
        if column not in have:  # a database from before villagers were playable
            db.execute(f"ALTER TABLE people ADD COLUMN {column} {kind}")
    now = datetime.now().isoformat(timespec="seconds")
    content = dcc.load_content() if dcc.content_available() else None
    with db:  # follow the files: add who is missing, lock the townsfolk, roll who has no character yet, drop who left the file
        for locked, rows in ((1, villagers.TOWNSFOLK), (0, villagers.VILLAGERS)):
            db.executemany("INSERT OR IGNORE INTO people (name, occupation, updated) VALUES (?, ?, ?)", [(n, o, now) for n, o in rows])
            db.executemany("UPDATE people SET locked = ?, occupation = ? WHERE name = ? AND seat IS NULL AND born_day IS NULL AND (locked != ? OR occupation != ?)",
                           [(locked, o, n, locked, o) for n, o in rows])   # not a villager who has since taken a seat or grown old enough to have a life of their own
        if content:
            db.execute("UPDATE people SET sheet = NULL WHERE claimed_by IS NULL AND sheet IS NOT NULL AND sheet NOT LIKE '%\"luck_rule\"%'")  # rolled before the Luck rule
            for row in db.execute("SELECT id, name, occupation FROM people WHERE locked = 0 AND sheet IS NULL AND genes IS NULL").fetchall():   # a child gets its rolls at eighteen
                sheet = roll_villager(content, row["name"], row["occupation"])
                if sheet:
                    db.execute("UPDATE people SET sheet = ? WHERE id = ?", (json.dumps(sheet), row["id"]))
            db.executemany(
                "INSERT OR IGNORE INTO monsters (name, init, attack, ac, hd, move, act, special, saves, alignment, page, updated) "
                "VALUES (:name, :init, :attack, :ac, :hd, :move, :act, :special, :saves, :alignment, :page, :updated)",
                [{**m, "updated": now} for m in content.get("monsters", [])])
        db.execute("UPDATE people SET debt_cp = CASE WHEN claimed_by IS NULL THEN ? ELSE 0 END WHERE debt_cp IS NULL", (dcc.cost_in_cp(places.TAX_DEBT),))
        names = [n for n, _ in villagers.TOWNSFOLK + villagers.VILLAGERS]
        if names:
            marks = ",".join("?" * len(names))
            db.execute(f"DELETE FROM people WHERE name NOT IN ({marks}) AND claimed_by IS NULL AND notes = '' AND status = 'alive' AND genes IS NULL AND mother_id IS NULL", names)   # not the villagers born since
    return db


_followed: set = set()   # database files the villagers' sync has run on in this process


def _reader():
    """A connection for the three lists below: they only read, so the full sync of ``connect`` runs once per file, not on every call
    (``closed_reason`` asks about every shop several times a night)."""
    key = str(items.DB_PATH)
    if key in _followed:
        return items.connect()
    _followed.add(key)
    return connect()


def absent() -> list[dict]:
    """Villagers who are not alive and present: their shops and inns stay shut."""
    db = _reader()
    try:
        return [dict(r) for r in db.execute("SELECT name, status FROM people WHERE status != 'alive'")]
    finally:
        db.close()


def living() -> list[dict]:
    db = _reader()
    try:
        return [dict(r) for r in db.execute("SELECT name, occupation FROM people WHERE status = 'alive' ORDER BY id")]
    finally:
        db.close()


def producers() -> list[dict]:
    """Villagers who are alive and played by nobody: they are the ones at home, working at their trade."""
    db = _reader()
    try:
        return [dict(r) for r in db.execute("SELECT name, occupation FROM people WHERE status = 'alive' AND claimed_by IS NULL ORDER BY id")]
    finally:
        db.close()


GRAVEYARD_SHOWN = 200   # the villagers lying here; the older dead are forgotten (lives.py deletes them)


def graveyard(limit: int = GRAVEYARD_SHOWN) -> list[dict]:
    """The villagers nobody played who died most recently, newest first."""
    db = connect()
    try:
        out = []
        for r in db.execute("SELECT name, occupation, race, sex, born_day, died_day, cause FROM people WHERE status = 'dead' AND claimed_by IS NULL "
                            "ORDER BY died_day IS NULL, died_day DESC, id DESC LIMIT ?", (limit,)):
            age = None if r["born_day"] is None or r["died_day"] is None else round((r["died_day"] - r["born_day"]) / 365)
            out.append({"name": r["name"], "job": r["occupation"], "race": r["race"], "age": age, "year": None if r["died_day"] is None else round(r["died_day"] / 365),
                        "cause": r["cause"] or ""})
        return out
    finally:
        db.close()


def rows(table: str, judge: bool = False, state: dict | None = None) -> list[dict]:
    """A register for showing. For a playable villager nobody has taken yet, ``preview`` holds what a player may know
    before choosing: five abilities, hit points, weapon, goods, coin. Luck and the birth augur stay hidden until the
    villager is taken (the admin sees both); the hit points shown leave out what the augur may add."""
    if table not in TABLES:
        raise dcc.DCCError("No such table.")
    db = connect()
    try:
        where = " WHERE status != 'dead'" if table == "people" else ""   # the dead are in the graveyard (``graveyard``), not on the village tab
        out = [dict(r) for r in db.execute(f"SELECT * FROM {table}{where} ORDER BY name COLLATE NOCASE")]
    finally:
        db.close()
    if table != "people":
        return out
    content = dcc.load_content() if dcc.content_available() else None
    names = {r["id"]: r["name"] for r in out}
    from . import town
    today = town.campaign_day()
    for row in out:
        row["age"] = round((today - row["born_day"]) / 365) if row.get("born_day") is not None and row["status"] != "dead" else None   # of a village that lives (lives.py)
        row["spouse"] = names.get(row.get("spouse_id"))
        genes = json.loads(row.pop("genes") or "null")
        sheet = json.loads(row.pop("sheet") or "null")
        if judge and genes and not sheet and row.get("mother_id"):   # the admin sees a child's inherited scores long before the eighteenth birthday
            row["inherited"] = {"abilities": genes["abilities"], "parents_jobs": genes["jobs"]}
        if row["claimed_by"] and row["character_id"] and dcc.character_path(row["character_id"]).exists():
            row["debt_cp"] = int(dcc.load_character(row["character_id"]).get("tax_debt_cp") or 0)  # a played villager's debt is the character's
        if state is not None and state.get("household_mode") and row.get("household_id") is not None:
            row["household_cp"] = int((state.get("households") or {}).get(str(row["household_id"]), 0))
        row["playable"] = bool(sheet) and not row["locked"] and not row["claimed_by"] and row["status"] == "alive"
        if sheet and content and not row["claimed_by"]:
            ch = build_character(content, row["name"], sheet)
            plain_hp = max(1, int(sheet["hp_roll"]) + dcc.ability_mod(content, ch["abilities"]["stamina"]))  # without whatever the augur adds
            row["preview"] = {"abilities": {a: v for a, v in ch["abilities"].items() if a != "luck"}, "hp": plain_hp,
                              "weapon": ch["occupation"].get("weapon", ""), "goods": ch["occupation"].get("trade_goods", "").replace("*", ""),
                              "copper": sheet["copper"], "item": next(i["name"] for i in ch["inventory"] if i["kind"] == "gear")}
            if judge:
                row["preview"].update(abilities=ch["abilities"], hp=ch["hp_max"], augur=ch["birth_augur"]["augur"])
    return out


def claim(person_id: int, user: str | None, alignment: str, moon: str, state: dict | None = None) -> str:
    """A player takes a villager over: the stored rolls become their character, with enough XP for 1st level.
    Returns the new character's id."""
    if moon not in [m["id"] for m in places.MOONS]:
        raise dcc.DCCError("Choose one of the three moons.")
    content = dcc.load_content()
    db = connect()
    try:
        row = db.execute("SELECT * FROM people WHERE id = ?", (int(person_id),)).fetchone()
        if not row or row["locked"] or not row["sheet"]:
            raise dcc.DCCError("That villager is not for playing.")
        if row["claimed_by"]:
            raise dcc.DCCError(f"{row['name']} is already played by {row['claimed_by']}.")
        if row["status"] != "alive":
            raise dcc.DCCError(f"{row['name']} is {row['status']}.")
        ch = build_character(content, row["name"], json.loads(row["sheet"]), alignment, user)
        if state is not None and state.get("household_mode"):   # the starting purse is the household's to give, as far as it holds it; the character then has a purse of its own
            from . import households, town
            town.set_purse(ch, households.debit(state, db, row["household_id"], dcc.coins_total_cp(ch["coins"])))
        ch["moon"], ch["xp"], ch["villager"], ch["luck_rule"] = moon, int(content["xp_thresholds"]["1"]), row["id"], True
        ch["tax_debt_cp"] = int(row["debt_cp"] or 0)  # the villager's debt, with whatever the dead have added to it, is now the character's
        from . import town
        for thing in dcc.ensure_inventory(ch):  # a hen is the one living thing with a moon: the fullest on the day it hatched, by its keeper's Luck
            if re.search(r"\b(hen|chicken|rooster)\b", thing["name"].lower()):
                hatched = town.campaign_day() - 20 - int(hashlib.sha1(f"hen/{row['id']}".encode()).hexdigest(), 16) % 400   # some day in the last year or so
                mark = town.roll_mark(hatched, row["name"], int(ch["abilities"]["luck"]), f"hen/{row['id']}")
                if mark:
                    thing["mark"] = mark
                    thing["notes"] = (thing.get("notes") or "").rstrip() + (" " if thing.get("notes") else "") + town.mark_text(mark, thing["kind"])
        character_id = dcc.new_character_id(row["name"])
        dcc.save_character(ch, character_id)  # before this table is written: the pack goes to the same database
        with db:
            db.execute("UPDATE people SET claimed_by = ?, character_id = ?, debt_cp = 0, household_id = NULL, updated = ? WHERE id = ?",
                       (user or "local", character_id, datetime.now().isoformat(timespec="seconds"), row["id"]))
            if state is not None and state.get("household_mode"):   # the last adult of a house who is taken over leaves its purse to nobody: the house is dissolved (households.py)
                from . import households
                households.dissolve_if_empty(db, state, row["household_id"])
        return character_id
    finally:
        db.close()


def follow_character(character_id: str, status: str) -> None:
    """The villager shares the fate of the character that came of them."""
    db = connect()
    try:
        with db:
            db.execute("UPDATE people SET status = ?, updated = ? WHERE character_id = ?", (status, datetime.now().isoformat(timespec="seconds"), character_id))
    finally:
        db.close()


def update(table: str, row_id: int, status: str | None = None, notes: str | None = None) -> None:
    if table not in TABLES:
        raise dcc.DCCError("No such table.")
    if status is not None and status not in TABLES[table]:
        raise dcc.DCCError(f"Status is one of: {', '.join(TABLES[table])}.")
    passed_on = None
    db = connect()
    try:
        with db:
            if status is not None:
                if table == "people" and status == "dead":  # a villager nobody plays dies: what they owed falls to everyone else
                    row = db.execute("SELECT status, claimed_by, debt_cp FROM people WHERE id = ?", (int(row_id),)).fetchone()
                    if row and row["status"] != "dead" and not row["claimed_by"] and row["debt_cp"]:
                        passed_on = int(row["debt_cp"])
                        db.execute("UPDATE people SET debt_cp = 0 WHERE id = ?", (int(row_id),))
                db.execute(f"UPDATE {table} SET status = ?, updated = ? WHERE id = ?", (status, datetime.now().isoformat(timespec="seconds"), int(row_id)))
            if notes is not None:
                db.execute(f"UPDATE {table} SET notes = ?, updated = ? WHERE id = ?", (str(notes)[:500], datetime.now().isoformat(timespec="seconds"), int(row_id)))
    finally:
        db.close()
    if passed_on:
        from . import debts
        debts.spread(passed_on, skip_villager=int(row_id))
