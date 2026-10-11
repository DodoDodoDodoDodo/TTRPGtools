"""Bestiary: compendium XML import, search, custom monsters.

The compendium is the Fight Club 5 XML on the DnD_books share. Build with:

    python -m ttrpgtools.dnd5e.bestiary "/path/to/Complete_Compendium.xml"

Rebuilding replaces compendium rows only; pasted and hand-made monsters stay.
"""

from __future__ import annotations

import re
import sqlite3
import sys
import xml.etree.ElementTree as ET
from typing import Any, Iterable

from . import db
from .statblock import derive, first_int, legendary_uses_from_text, slugify

SIZES = {"T": "Tiny", "S": "Small", "M": "Medium", "L": "Large", "H": "Huge", "G": "Gargantuan"}

#: Substrings that mark a source as not published by Wizards of the Coast.
THIRD_PARTY_MARKERS = (
    "tome of beasts", "creature codex", "(3pp)", "homebrew", "monsters of the ", "monsters of feyland",
    "grim hollow", "grimw hollow", "humblewood", "tanares", "drakkenheim", "oathbreaker", "tal'dorei",
    "monsters without borders", "tasha's crucible", "heliana", "tony petrecca", "laserllama",
    "xanathar's lost notes", "spectre creations", "team superhydra", "sword coast legends",
    "illrigger", "winghorn", "stormchasers", "dmdave", "shmeckerel", "livestream", "tortle package",
    "chains of asmodeus", "minsc and boo", "unearthed arcana",
)

_RECHARGE_TAG = re.compile(r"^(?:D(\d)|(\d+)\s*/\s*(Day|Turn)|(SHORT|LONG|LR|SR))$", re.I)


def is_official(source: str) -> bool:
    low = source.lower()
    return not any(marker in low for marker in THIRD_PARTY_MARKERS)


def parse_sources(description: str) -> tuple[str, list[str]]:
    """Split the trailing "Source:" list off a description."""
    at = description.rfind("Source:")
    if at < 0:
        return description.strip(), []
    sources = []
    for line in re.split(r",\s*\n|\n", description[at + 7:]):
        name = re.sub(r"\s+p\.?\s*\d*.*$", "", line.strip().rstrip(",")).strip()
        if name:
            sources.append(name)
    return description[:at].strip(), sources


def _usage_from_tag(tag: str | None) -> dict | None:
    m = _RECHARGE_TAG.match((tag or "").strip())
    if not m:
        return None
    if m.group(1):
        return {"kind": "recharge", "max": 1, "recharge_min": int(m.group(1))}
    if m.group(2):
        return {"kind": "day" if m.group(3).lower() == "day" else "turn", "max": int(m.group(2))}
    return {"kind": "long" if m.group(4).upper() in ("LONG", "LR") else "short", "max": 1}


def _attack(raw: str) -> dict | None:
    """"Bite|+14|2d10+8". Sloppy rows drop or double a separator."""
    parts = [p.strip() for p in (raw or "").split("|")]
    if len(parts) < 2 or not any(parts):
        return None
    name, rest = parts[0], [p for p in parts[1:] if p]
    to_hit, dice = None, ""
    for part in rest:
        if "d" in part.lower() and re.search(r"\d+d\d+", part):
            dice = re.sub(r"\+?escapeDC\d+|\+?%\d+", "", part)
        elif re.fullmatch(r"[+-]*\d+", part):
            to_hit = int(part.replace("+-", "-").lstrip("+"))
    return {"name": name, "to_hit": to_hit, "dice": dice}


def _entries(monster: ET.Element, tag: str) -> list[dict]:
    entries = []
    for el in monster.findall(tag):
        name = (el.findtext("name") or "").strip()
        text = "\n".join((t.text or "").strip() for t in el.findall("text")).strip()
        if not name and not text:
            continue
        entry: dict[str, Any] = {"name": name, "text": text,
                                 "attacks": [a for a in (_attack(x.text or "") for x in el.findall("attack")) if a]}
        usage = _usage_from_tag(el.findtext("recharge"))
        if usage:
            entry["usage"] = usage
        entries.append(entry)
    return entries


def convert_monster(el: ET.Element) -> dict:
    text = lambda tag: (el.findtext(tag) or "").strip()  # noqa: E731
    description, sources = parse_sources(text("description"))
    source = sources[0] if sources else "Unknown"

    legendary, lair, legendary_uses = [], [], None
    in_lair = False
    for entry in _entries(el, "legendary"):
        low = entry["name"].lower()
        usage = entry.pop("usage", None)
        if low.startswith(("lair action", "regional effect")):
            in_lair = True
            lair.append(entry)
        elif low.startswith("legendary action"):
            in_lair = False
            # The tag is wrong for some entries (Lich: 4/Turn); the rules text wins.
            legendary_uses = legendary_uses_from_text(entry["text"]) or (
                usage["max"] if usage and usage["kind"] == "turn" else None)
            entry["intro"] = True
            legendary.append(entry)
        else:
            (lair if in_lair else legendary).append(entry)

    traits = _entries(el, "trait")
    actions = _entries(el, "action")
    reactions = _entries(el, "reaction")
    for entry in traits + actions + reactions:
        # "N/Turn" on a plain action is a rule in its text, not a counter.
        if entry.get("usage", {}).get("kind") == "turn":
            del entry["usage"]

    slots_raw = [first_int(s) for s in text("slots").split(",") if s.strip()]
    ac_text = text("ac")
    hp_text = text("hp")
    formula = re.search(r"\(([^)]*d[^)]*)\)", hp_text)
    monster = {
        "name": text("name"),
        "size": SIZES.get(text("size")[:1].upper(), text("size")),
        "type": text("type"),
        "alignment": text("alignment"),
        "source": source,
        "sources": sources,
        "official": is_official(source),
        "ac": first_int(ac_text, 10),
        "ac_text": ac_text,
        "hp": first_int(hp_text, 1),
        "hp_formula": formula.group(1).replace(" ", "") if formula else "",
        "speed": text("speed"),
        "abilities": {k: first_int(text(k), 10) for k in ("str", "dex", "con", "int", "wis", "cha")},
        "saves": text("save") or text("Save"),
        "skills": text("skill") or text("skills"),
        "senses": text("senses") or text("sense"),
        "passive": first_int(text("passive"), 10),
        "languages": text("languages"),
        "resist": text("resist") or text("resistance"),
        "immune": text("immune") or text("imune") or text("immunity"),
        "vulnerable": text("vulnerable"),
        "condition_immune": text("conditionImmune") or text("conditionimmune"),
        "cr": text("cr"),
        "traits": traits,
        "actions": actions,
        "bonus_actions": [],
        "reactions": reactions,
        "legendary": legendary,
        "lair": lair,
        "legendary_uses": legendary_uses,
        # First number of <slots> is the cantrip count.
        "spell_slots": slots_raw[1:] if len(slots_raw) > 1 else [],
        "spells": [s.strip() for s in text("spells").split(",") if s.strip()],
        "environment": text("environment") or text("environemnt"),
        "description": description,
    }
    return derive(monster)


def _unique_id(base: str, taken: set[str]) -> str:
    candidate, n = base, 2
    while candidate in taken:
        candidate = f"{base}-{n}"
        n += 1
    taken.add(candidate)
    return candidate


def save_monster(conn: sqlite3.Connection, monster: dict, origin: str, monster_id: str | None = None) -> str:
    if not monster_id:
        taken = {r["id"] for r in conn.execute("SELECT id FROM monsters")}
        monster_id = _unique_id(slugify(f"{monster['name']}-{origin}"), taken)
    data = {k: v for k, v in monster.items() if k != "id"}
    conn.execute(
        "INSERT OR REPLACE INTO monsters (id, name, cr, type, source, origin, official, data) VALUES (?,?,?,?,?,?,?,?)",
        (monster_id, monster["name"], monster.get("cr_value"), monster.get("type"), monster.get("source"),
         origin, int(bool(monster.get("official"))), db.dumps(data)),
    )
    return monster_id


def build_from_compendium(xml_path: str, conn: sqlite3.Connection) -> dict:
    root = ET.parse(xml_path).getroot()
    conn.execute("DELETE FROM monsters WHERE origin = 'compendium'")
    taken = {r["id"] for r in conn.execute("SELECT id FROM monsters")}
    stats = {"imported": 0, "skipped": 0, "official": 0}
    for el in root.findall("monster"):
        monster = convert_monster(el)
        if not monster["name"]:
            stats["skipped"] += 1
            continue
        base = slugify(monster["name"])
        monster_id = base if base not in taken else slugify(f"{monster['name']}-{monster['source']}")
        save_monster(conn, monster, "compendium", _unique_id(monster_id, taken))
        stats["imported"] += 1
        stats["official"] += int(monster["official"])
    return stats


def get_monster(conn: sqlite3.Connection, monster_id: str) -> dict | None:
    return db.row_data(conn.execute("SELECT id, data FROM monsters WHERE id = ?", (monster_id,)).fetchone())


def search(conn: sqlite3.Connection, query: str = "", cr_min: float | None = None, cr_max: float | None = None,
           monster_type: str = "", official_only: bool = False, origin: str = "", limit: int = 60) -> list[dict]:
    where, args = ["1=1"], []
    for word in query.split():
        where.append("name LIKE ?")
        args.append(f"%{word}%")
    if cr_min is not None:
        where.append("cr >= ?")
        args.append(cr_min)
    if cr_max is not None:
        where.append("cr <= ?")
        args.append(cr_max)
    if monster_type:
        where.append("type LIKE ?")
        args.append(f"{monster_type}%")
    if official_only:
        where.append("(official = 1 OR origin != 'compendium')")
    if origin:
        where.append("origin = ?")
        args.append(origin)
    rows = conn.execute(
        f"SELECT id, name, cr, type, source, origin, official, "
        f"json_extract(data,'$.cr') AS cr_text, json_extract(data,'$.hp') AS hp, "
        f"json_extract(data,'$.ac') AS ac, json_extract(data,'$.xp') AS xp, json_extract(data,'$.size') AS size "
        f"FROM monsters WHERE {' AND '.join(where)} "
        f"ORDER BY (name LIKE ?) DESC, origin != 'compendium' DESC, official DESC, name COLLATE NOCASE LIMIT ?",
        (*args, f"{query.strip()}%", limit),
    ).fetchall()
    return [dict(r) for r in rows]


def main(argv: Iterable[str]) -> int:
    args = list(argv)
    if len(args) != 1:
        print(__doc__)
        return 2
    with db.session() as conn:
        stats = build_from_compendium(args[0], conn)
    print(f"{stats['imported']} monsters imported ({stats['official']} official), "
          f"{stats['skipped']} skipped -> {db.db_path()}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
