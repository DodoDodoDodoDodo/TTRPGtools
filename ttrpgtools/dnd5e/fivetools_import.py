"""Monsters from a 5etools-format JSON file (core data or a homebrew book file).

    python -m ttrpgtools.dnd5e.fivetools_import book.json [--source FleeMortals] [--corrections fixes.json]

Rows are stored with origin "book". Importing a file again replaces the rows of
the sources it contains and nothing else.

The format marks up its text with tags such as {@hit 4} and {@damage 1d6 + 2}.
They are rewritten into the printed wording, so the text reads like the book and
the difficulty reader sees "+4 to hit" and "5 (1d6 + 2) slashing damage".
"""

from __future__ import annotations

import json
import re
import sqlite3
import sys
from typing import Any

from . import db
from pathlib import Path

from .bestiary import _unique_id, save_monster
from .fivetools_copy import Library
from .statblock import derive, first_int, slugify

SIZES = {"T": "Tiny", "S": "Small", "M": "Medium", "L": "Large", "H": "Huge", "G": "Gargantuan", "V": "Varies"}
ALIGNMENTS = {"L": "lawful", "N": "neutral", "NX": "neutral", "NY": "neutral", "C": "chaotic", "G": "good",
              "E": "evil", "U": "unaligned", "A": "any alignment"}
ATTACKS = {"mw": "Melee Weapon Attack:", "rw": "Ranged Weapon Attack:", "ms": "Melee Spell Attack:",
           "rs": "Ranged Spell Attack:", "mw,rw": "Melee or Ranged Weapon Attack:",
           "ms,rs": "Melee or Ranged Spell Attack:", "m": "Melee Attack:", "r": "Ranged Attack:"}
#: MCDM encounter roles, stored by the converters as capitalised type tags.
ROLES = {"Ambusher", "Artillery", "Brute", "Companion", "Controller", "Leader", "Minion", "Retainer",
         "Skirmisher", "Soldier", "Solo", "Support"}
ABILITY_NAMES = {"str": "Str", "dex": "Dex", "con": "Con", "int": "Int", "wis": "Wis", "cha": "Cha"}
_TAG = re.compile(r"\{@(\w+)(?:\s+([^{}]*))?\}")


def _tag(match: re.Match) -> str:
    name, body = match.group(1), (match.group(2) or "")
    parts = body.split("|")
    first = parts[0].strip()
    if name == "atk":
        return ATTACKS.get(first, "Attack:")
    if name == "hit":
        return first if first.startswith(("+", "-")) else "+" + first
    if name == "h":
        return "Hit: "
    if name == "dc":
        return "DC " + first
    if name == "recharge":
        return f"(Recharge {first}-6)" if first and first != "6" else "(Recharge 6)"
    if name in ("sup", "cite", "footnote"):
        return ""
    if name == "chance":
        return first + " percent"
    # {@creature goblin|MM|goblins}: the last part, when present, is the printed text.
    return (parts[2] if len(parts) > 2 and parts[2].strip() else first).strip()


def plain(text: Any) -> str:
    text = str(text)
    for _ in range(6):  # tags nest
        replaced = _TAG.sub(_tag, text)
        if replaced == text:
            break
        text = replaced
    return re.sub(r"[ \t]{2,}", " ", text).replace(" ,", ",").replace(" .", ".").strip()


def flatten(entries: Any) -> str:
    """Entries are strings or nested objects (lists, items, tables); text comes out in reading order."""
    if entries is None:
        return ""
    if isinstance(entries, (str, int, float)):
        return plain(entries)
    if isinstance(entries, list):
        return "\n".join(part for part in (flatten(e) for e in entries) if part)
    kind = entries.get("type")
    if kind == "list":
        return "\n".join("• " + flatten(item) for item in entries.get("items", []))
    if kind == "table":
        rows = [" | ".join(plain(c) for c in entries.get("colLabels", []))] if entries.get("colLabels") else []
        rows += [" | ".join(flatten(c) for c in row) for row in entries.get("rows", [])]
        return "\n".join(rows)
    body = flatten(entries.get("entries") if "entries" in entries else entries.get("entry"))
    name = plain(entries["name"]) if entries.get("name") else ""
    return f"{name}. {body}" if name and body else name or body


def _entries(raw: list | None) -> list[dict]:
    out = []
    for entry in raw or []:
        name = plain(entry.get("name") or "")
        text = flatten(entry.get("entries"))
        if name or text:
            out.append({"name": name, "text": text, "attacks": _attacks(name, text)})
    return out


def _attacks(name: str, text: str) -> list[dict]:
    to_hit = re.search(r"([+-]\d+) to hit", text)
    if not to_hit:
        return []
    dice = re.search(r"Hit:\s*\d+\s*\(([^)]+)\)", text)
    return [{"name": re.sub(r"\s*\([^)]*\)", "", name), "to_hit": int(to_hit.group(1)),
             "dice": dice.group(1).replace(" ", "") if dice else ""}]


def _damage_list(raw: list | None, key: str) -> str:
    """["fire", {"resist": ["bludgeoning", ...], "note": "from mundane attacks"}] -> printed form."""
    simple, special = [], []
    for item in raw or []:
        if isinstance(item, str):
            simple.append(item)
        elif item.get("special"):
            special.append(plain(item["special"]))
        else:
            inner = _damage_list(item.get(key) or [], key).replace("; ", ", ")
            special.append(" ".join(p for p in (plain(item.get("preNote", "")), inner,
                                                plain(item.get("note", ""))) if p))
    return "; ".join(p for p in (", ".join(simple), *special) if p)


def _type(raw: Any) -> tuple[str, str]:
    """-> (type text, role)"""
    if isinstance(raw, str):
        return raw, ""
    tags, role = [], ""
    for tag in raw.get("tags") or []:
        text = tag if isinstance(tag, str) else f"{tag.get('prefix', '')} {tag.get('tag', '')}".strip()
        if text in ROLES:
            role = text
        else:
            tags.append(text)
    base = raw.get("type")
    if isinstance(base, dict):
        base = " or ".join(base.get("choose") or [])
    if raw.get("swarmSize"):
        base = f"swarm of {SIZES.get(raw['swarmSize'], raw['swarmSize'])} {base}s"
    return str(base) + (f" ({', '.join(tags)})" if tags else ""), role


def _alignment(monster: dict) -> str:
    words = []
    for code in monster.get("alignment") or []:
        if isinstance(code, dict):
            words.append(plain(code.get("special") or " ".join(ALIGNMENTS.get(c, c) for c in code.get("alignment", []))))
        else:
            words.append(ALIGNMENTS.get(code, code))
    text = " ".join(words)
    text = {"neutral neutral": "neutral", "lawful neutral chaotic good neutral evil": "any alignment"}.get(text, text)
    return (monster.get("alignmentPrefix") or "") + text


def _ac(raw: list) -> tuple[int, str]:
    parts, value = [], None
    for item in raw or []:
        if isinstance(item, int):
            number, text = item, str(item)
        elif "special" in item:
            text = plain(item["special"])
            found = re.search(r"\d+", text)
            number = int(found.group()) if found else 10
        else:
            number = int(item.get("ac") or 10)
            source = ", ".join(plain(f) for f in item.get("from") or [])
            text = str(number) + (f" ({source})" if source else "")
            if item.get("condition"):
                text += " " + plain(item["condition"])
        value = number if value is None else value
        parts.append(text)
    return (value if value is not None else 10), ", ".join(parts)


def _speed(raw: Any) -> str:
    if not isinstance(raw, dict):
        return str(raw or "")
    parts = []
    for mode in ("walk", "burrow", "climb", "fly", "swim"):
        if mode not in raw:
            continue
        value = raw[mode]
        if isinstance(value, dict):
            text = f"{value.get('number', 0)} ft. {plain(value.get('condition', ''))}".strip()
        elif value is True:
            text = "equal to walking speed"
        else:
            text = f"{value} ft."
        parts.append(text if mode == "walk" else f"{mode} {text}")
    return ", ".join(parts)


def _spellcasting(blocks: list | None) -> tuple[list[dict], list[int], list[str]]:
    """-> (trait entries, spell slots by level, spell names)"""
    traits, slots, names = [], [], []
    for block in blocks or []:
        lines = [flatten(block.get("headerEntries"))]
        if block.get("will"):
            lines.append("At will: " + ", ".join(plain(s) for s in block["will"]))
        for key, spells in (block.get("daily") or {}).items():
            count = re.match(r"\d+", key).group()
            each = " each" if key.endswith("e") and len(spells) > 1 else ""
            lines.append(f"{count}/day{each}: " + ", ".join(plain(s) for s in spells))
        for level, data in sorted((block.get("spells") or {}).items(), key=lambda kv: int(kv[0])):
            spells = ", ".join(plain(s) for s in data.get("spells", []))
            if int(level) == 0:
                lines.append("Cantrips (at will): " + spells)
            else:
                count = int(data.get("slots") or 0)
                suffix = {1: "st", 2: "nd", 3: "rd"}.get(int(level), "th")
                lines.append(f"{level}{suffix} level ({count} slots): " + spells)
                while len(slots) < int(level):
                    slots.append(0)
                slots[int(level) - 1] = max(slots[int(level) - 1], count)
        lines.append(flatten(block.get("footerEntries")))
        for group in [block.get("will") or []] + list((block.get("daily") or {}).values()) \
                + [d.get("spells", []) for d in (block.get("spells") or {}).values()]:
            names.extend(plain(s) for s in group)
        traits.append({"name": plain(block.get("name") or "Spellcasting"),
                       "text": "\n".join(line for line in lines if line), "attacks": []})
    return traits, slots, names


def convert_monster(raw: dict, source_name: str, groups: dict[str, dict]) -> dict:
    type_text, role = _type(raw.get("type") or "")
    ac, ac_text = _ac(raw.get("ac") or [])
    hp = raw.get("hp") or {}
    hp_special = plain(hp.get("special", "")) if "special" in hp else ""
    hp_value = hp.get("average")
    if hp_value is None:
        found = re.search(r"\d+", hp_special)
        hp_value = int(found.group()) if found else 1
    cr = raw.get("cr")
    xp_override = None
    if isinstance(cr, dict):
        xp_override, cr = cr.get("xp"), cr.get("cr")
    spell_traits, slots, spells = _spellcasting(raw.get("spellcasting"))
    action_spells = [t for t, b in zip(spell_traits, raw.get("spellcasting") or []) if b.get("displayAs") == "action"]
    senses = raw.get("senses") or []

    header = flatten(raw.get("legendaryHeader"))
    legendary = _entries(raw.get("legendary")) + _entries(raw.get("mythic"))
    is_villain = "villain action" in header.lower()
    group = groups.get((raw.get("legendaryGroup") or {}).get("name", ""), {})
    lair = []
    if group.get("lairActions"):
        lair.append({"name": "Lair Actions", "text": flatten(group["lairActions"]), "attacks": []})
    if group.get("regionalEffects"):
        lair.append({"name": "Regional Effects", "text": flatten(group["regionalEffects"]), "attacks": []})

    monster: dict[str, Any] = {
        "name": raw["name"],
        "size": " or ".join(SIZES.get(s, s) for s in raw.get("size") or []),
        "type": type_text, "role": role, "alignment": _alignment(raw),
        "source": source_name, "sources": [source_name + (f" p. {raw['page']}" if raw.get("page") else "")],
        # Third-party books the table owns are shown alongside the official ones.
        "official": True,
        "ac": ac, "ac_text": ac_text,
        "hp": int(hp_value), "hp_formula": (hp.get("formula") or "").replace(" ", ""), "hp_text": hp_special,
        "speed": _speed(raw.get("speed")),
        "abilities": {k: first_int(str(raw.get(k) or ""), 10) for k in ABILITY_NAMES},
        "saves": ", ".join(f"{ABILITY_NAMES.get(k, k)} {v}" for k, v in (raw.get("save") or {}).items()),
        "skills": ", ".join(f"{k.title()} {v}" for k, v in (raw.get("skill") or {}).items()
                            if isinstance(v, str)),
        "senses": ", ".join(plain(s) for s in senses), "passive": first_int(str(raw.get("passive") or ""), 10),
        "languages": ", ".join(plain(x) for x in raw.get("languages") or []),
        "resist": _damage_list(raw.get("resist"), "resist"),
        "immune": _damage_list(raw.get("immune"), "immune"),
        "vulnerable": _damage_list(raw.get("vulnerable"), "vulnerable"),
        "condition_immune": _damage_list(raw.get("conditionImmune"), "conditionImmune"),
        "cr": str(cr or ""), "xp_override": xp_override,
        "traits": _entries(raw.get("trait")) + [t for t in spell_traits if t not in action_spells],
        "actions": _entries(raw.get("action")) + action_spells,
        "bonus_actions": _entries(raw.get("bonus")), "reactions": _entries(raw.get("reaction")),
        "legendary": [] if is_villain else legendary,
        "villain": legendary if is_villain else [],
        "lair": lair,
        "spell_slots": slots, "spells": spells, "description": "",
    }
    if is_villain:
        monster["villain_intro"], monster["legendary_uses"] = header, 0
    elif legendary:
        monster["legendary_intro"] = header
        monster["legendary_uses"] = int(raw.get("legendaryActions") or 0) or None
    if raw.get("pbNote"):
        monster["pb_note"] = plain(raw["pbNote"])
    monster = derive(monster)
    for pool in raw.get("resource") or []:
        monster["resources"].append({"key": slugify("pool-" + pool["name"]), "name": pool["name"], "kind": "day",
                                     "max": int(pool.get("value") or 1)})
    return monster


def import_file(path: str, conn: sqlite3.Connection, only_source: str | None = None,
                corrections: dict[str, dict] | None = None) -> dict:
    """``corrections`` maps a monster name to raw fields that replace the file's values,
    for places where the file disagrees with the printed book."""
    data = json.load(open(path, encoding="utf-8"))
    for raw in data.get("monster") or []:
        raw.update((corrections or {}).get(raw.get("name"), {}))
    names = {s["json"]: s.get("full") or s["json"] for s in (data.get("_meta") or {}).get("sources", [])}
    groups = {g["name"]: g for g in data.get("legendaryGroup") or []}
    monsters = [m for m in data.get("monster") or [] if not only_source or m.get("source") == only_source]
    stats = {"imported": 0, "skipped": [], "sources": sorted({names.get(m.get("source"), m.get("source"))
                                                               for m in monsters})}
    for source in stats["sources"]:
        conn.execute("DELETE FROM monsters WHERE origin = 'book' AND source = ?", (source,))
    taken = {r["id"] for r in conn.execute("SELECT id FROM monsters")}
    library = Library(Path(path).parent, {"XDMG", "XMM", "XPHB", "RHW"}) if (Path(path).parent / "index.json").exists() else None
    for raw in monsters:
        if "_copy" in raw:
            if library is None:
                stats["skipped"].append(raw.get("name", "?") + " (copy of another entry)")
                continue
            raw = library.resolve(raw)
        source = names.get(raw.get("source"), raw.get("source") or "Unknown")
        monster = convert_monster(raw, source, groups)
        base = slugify(monster["name"])
        monster_id = _unique_id(base if base not in taken else slugify(f"{monster['name']}-{source}"), taken)
        save_monster(conn, monster, "book", monster_id)
        stats["imported"] += 1
    if library is not None:
        stats["skipped"].extend(library.unknown)
    return stats


def main(argv: list[str]) -> int:
    if not argv or argv[0].startswith("-"):
        print(__doc__)
        return 2
    only = argv[argv.index("--source") + 1] if "--source" in argv else None
    corrections = json.load(open(argv[argv.index("--corrections") + 1], encoding="utf-8")) \
        if "--corrections" in argv else None
    with db.session() as conn:
        stats = import_file(argv[0], conn, only, corrections)
    print(f"{stats['imported']} monsters imported from {', '.join(stats['sources'])} -> {db.db_path()}")
    for name in stats["skipped"]:
        print("skipped:", name)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
