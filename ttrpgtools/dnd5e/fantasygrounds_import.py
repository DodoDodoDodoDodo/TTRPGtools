"""Monsters and their pictures from a Fantasy Grounds module (.mod: a zip with db.xml and images).

A monster the bestiary already has keeps its stat block and gains the module's picture; a monster it lacks is
added from the module (origin ``fantasygrounds``). AC, HP or CR that differ from the bestiary are reported, not
changed: the printed book decides. Pictures go to content/dnd5e/private/monster-art/<book slug>/ (private).

    python -m ttrpgtools.dnd5e.fantasygrounds_import MODULE --book "Curse of Strahd" [--inner CoS.mod] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import io
import os
import re
import sqlite3
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from . import db
from .bestiary import _unique_id, save_monster
from .fivetools_import import _attacks
from .statblock import derive, slugify

ART_DIR = Path(os.environ.get("TTRPG_MONSTER_ART") or Path(__file__).resolve().parents[2] / "content" / "dnd5e" / "private" / "monster-art")
ABILITIES = {"strength": "str", "dexterity": "dex", "constitution": "con", "intelligence": "int", "wisdom": "wis", "charisma": "cha"}
#: a module's tokens for unnamed extras are a capital letter on a disc (tokens/campaign/G.png): not art
LETTER_TOKEN = re.compile(r"/[A-Z]\.png$")


def open_module(path: str, inner: str | None = None) -> zipfile.ZipFile:
    archive = zipfile.ZipFile(path)
    return zipfile.ZipFile(io.BytesIO(archive.read(inner))) if inner else archive


def _text(el: ET.Element | None) -> str:
    return (el.text or "").strip() if el is not None else ""


def _list(record: ET.Element, tag: str) -> list[dict]:
    return [{"name": _text(item.find("name")), "text": _text(item.find("desc")).replace("\\n", "\n")}
            for item in (record.find(tag) if record.find(tag) is not None else [])
            if _text(item.find("name")) or _text(item.find("desc"))]


def _description(record: ET.Element) -> str:
    text = record.find("text")
    if text is None:
        return ""
    return "\n\n".join("".join(p.itertext()).strip() for p in text if p.tag in ("p", "li") and "".join(p.itertext()).strip())


def convert(record: ET.Element, book: str) -> dict:
    """One Fantasy Grounds NPC record as a bestiary monster (the compendium's field names)."""
    get = lambda tag: _text(record.find(tag))
    senses = get("senses")
    passive = re.search(r"passive Perception (\d+)", senses)
    actions = _list(record, "actions")
    for action in actions:
        action["attacks"] = _attacks(action["name"], action["text"])
    legendary = _list(record, "legendaryactions")
    for entry in legendary:  # the module's "Options" entry is the legendary intro
        if entry["name"].lower() == "options":
            entry["intro"] = True
    spell_names = [re.sub(r"\s*[-(].*$", "", s["name"]).strip().lower() for s in _list(record, "spells") + _list(record, "innatespells")]
    slots = record.find("spellslots")
    ac = get("ac")
    monster = {
        "name": get("name"), "size": get("size"), "type": get("type"), "alignment": get("alignment"),
        "source": book, "sources": [book], "official": True,
        "ac": int(ac) if ac.isdigit() else 10, "ac_text": f"{ac} {get('actext')}".strip(),
        "hp": int(get("hp") or 0), "hp_formula": get("hd").strip("() ").replace(" ", ""),
        "speed": get("speed"),
        "abilities": {short: int(_text(record.find(f"abilities/{long}/score")) or 10) for long, short in ABILITIES.items()},
        "saves": get("savingthrows"), "skills": get("skills"),
        "senses": re.sub(r",?\s*passive Perception \d+", "", senses).strip(" ,"), "passive": int(passive.group(1)) if passive else None,
        "languages": get("languages"),
        "resist": get("damageresistances"), "immune": get("damageimmunities"), "vulnerable": get("damagevulnerabilities"),
        "condition_immune": get("conditionimmunities"),
        "cr": get("cr") or "0",
        "traits": _list(record, "traits"), "actions": actions, "bonus_actions": [], "reactions": _list(record, "reactions"),
        "legendary": legendary, "lair": _list(record, "lairactions"),
        "spell_slots": [int(_text(slots.find(f"level{n}")) or 0) for n in range(1, 10)] if slots is not None else [],
        "spells": sorted(set(spell_names)), "environment": "", "description": _description(record),
    }
    while monster["spell_slots"] and not monster["spell_slots"][-1]:
        monster["spell_slots"].pop()
    return derive(monster)


def picture(module: zipfile.ZipFile, record: ET.Element) -> str | None:
    """The module's portrait of this monster (an image of the same name), else its token unless that is a letter."""
    name = _text(record.find("name")).lower()
    for f in module.namelist():
        if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp")) and os.path.splitext(os.path.basename(f))[0].lower() == name and "map" not in f.lower():
            return f
    token = _text(record.find("token")).split("@")[0]
    return token if token in module.namelist() and not LETTER_TOKEN.search(token) else None


def import_module(module: zipfile.ZipFile, book: str, conn: sqlite3.Connection, dry_run: bool = False) -> dict:
    root = ET.fromstring(module.read("db.xml"))
    section = root.find("npc")
    records = [r for r in (section.iter() if section is not None else []) if r.tag.startswith("id-") and r.find("abilities") is not None]
    rows = [dict(r) for r in conn.execute("SELECT id, name, source, data FROM monsters")]
    by_name: dict[str, list[dict]] = {}
    for row in rows:
        by_name.setdefault(row["name"].lower(), []).append(row)
    from_book = [r for r in rows if (r["source"] or "") == book]
    taken = {r["id"] for r in rows}
    art_dir = ART_DIR / slugify(book)
    stats = {"records": len(records), "pictures": 0, "matched": 0, "added": 0, "differ": [], "added_names": []}
    for record in records:
        monster = convert(record, book)
        name = monster["name"]
        hits = by_name.get(name.lower(), [])
        # "Strahd" in the module is "Strahd von Zarovich" in the book: one book entry that starts with the name
        if not hits:
            longer = [r for r in from_book if r["name"].lower().startswith(name.lower() + " ")]
            hits = longer if len(longer) == 1 else []
        target = next((h for h in hits if (h["source"] or "") == book), hits[0] if hits else None)
        art = picture(module, record)
        image = None
        if art:
            image = f"{slugify(book)}/{slugify(name)}{os.path.splitext(art)[1].lower()}"
            stats["pictures"] += 1
            if not dry_run:
                art_dir.mkdir(parents=True, exist_ok=True)
                (ART_DIR / image).write_bytes(module.read(art))
        if target:
            stats["matched"] += 1
            data = json.loads(target["data"])
            ours = (str(data.get("ac")), str(data.get("hp")), str(data.get("cr")))
            theirs = (str(monster["ac"]), str(monster["hp"]), str(monster["cr"]))
            if ours != theirs:
                stats["differ"].append(f"{name}: bestiary AC/HP/CR {'/'.join(ours)}, module {'/'.join(theirs)}")
            if image and not dry_run:
                data["image"] = image
                conn.execute("UPDATE monsters SET data = ? WHERE id = ?", (db.dumps(data), target["id"]))
        else:
            stats["added"] += 1
            stats["added_names"].append(name)
            if image:
                monster["image"] = image
            if not dry_run:
                base = slugify(name)
                save_monster(conn, monster, "fantasygrounds", _unique_id(base if base not in taken else slugify(f"{name}-{book}"), taken))
    return stats


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("module")
    parser.add_argument("--book", required=True, help="the book the module's monsters come from, as the bestiary names it")
    parser.add_argument("--inner", help="the .mod inside a .zip, e.g. CoS.mod")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    with db.session() as conn:
        stats = import_module(open_module(args.module, args.inner), args.book, conn, args.dry_run)
    print(f"{stats['records']} monsters: {stats['matched']} already in the bestiary, {stats['added']} added, {stats['pictures']} pictures")
    for line in stats["differ"]:
        print("  differs:", line)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
