"""The monster schema every importer produces, and the helpers they share.

A monster is a plain dict:

    name, size, type, alignment, source, sources[], official
    ac, ac_text, hp, hp_formula, speed
    abilities {str,dex,con,int,wis,cha}, init_mod
    saves, skills, senses, passive, languages
    resist, immune, vulnerable, condition_immune
    cr (text, "1/2"), cr_value (float), xp
    traits[], actions[], bonus_actions[], reactions[], legendary[], villain[], lair[]
        each entry: {name, text, attacks: [{name, to_hit, dice, avg}]}
    legendary_uses
    spell_slots [level 1..9]
    resources [{key, name, kind, max, recharge_min}]
        kind: day | recharge | short | long | slot | legendary | legendary_resistance | encounter
    role (MCDM: Brute, Minion, Solo, Companion, ...), xp_override
    description

Text is kept verbatim. Only what the tracker counts or the difficulty maths
reads gets structure.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

ABILITIES = ["str", "dex", "con", "int", "wis", "cha"]

CR_XP = {
    "0": 10, "1/8": 25, "1/4": 50, "1/2": 100, "1": 200, "2": 450, "3": 700, "4": 1100,
    "5": 1800, "6": 2300, "7": 2900, "8": 3900, "9": 5000, "10": 5900, "11": 7200,
    "12": 8400, "13": 10000, "14": 11500, "15": 13000, "16": 15000, "17": 18000,
    "18": 20000, "19": 22000, "20": 25000, "21": 33000, "22": 41000, "23": 50000,
    "24": 62000, "25": 75000, "26": 90000, "27": 105000, "28": 120000, "29": 135000,
    "30": 155000,
}
CR_FRACTIONS = {"1/8": 0.125, "1/4": 0.25, "1/2": 0.5}

_DICE_TERM = re.compile(r"([+-]?)\s*(\d+)\s*d\s*(\d+)|([+-])\s*(\d+)(?![\dd])|^\s*(\d+)(?![\dd])")


def normalise_text(text: str) -> str:
    """Pasted web text carries typographic minus signs, dashes and hard spaces."""
    text = text.replace("−", "-").replace("–", "-").replace("—", "-")
    text = text.replace("’", "'").replace("‘", "'").replace(" ", " ")
    text = text.replace("½", "1/2").replace("¼", "1/4").replace("⅛", "1/8")
    return unicodedata.normalize("NFC", text)


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "monster"


def ability_mod(score: int) -> int:
    return (int(score) - 10) // 2


def cr_value(cr: str | None) -> float | None:
    cr = (cr or "").strip()
    if cr in CR_FRACTIONS:
        return CR_FRACTIONS[cr]
    try:
        return float(cr)
    except ValueError:
        return None


def dice_average(expr: str | None) -> float:
    """Average of "2d10 + 8"; tokens that are not dice or flat numbers are ignored."""
    if not expr:
        return 0.0
    total = 0.0
    for sign, count, faces, flat_sign, flat, lead in _DICE_TERM.findall(expr.replace(" ", "")):
        if count:
            value = int(count) * (int(faces) + 1) / 2
            total += -value if sign == "-" else value
        elif flat:
            total += -int(flat) if flat_sign == "-" else int(flat)
        elif lead:
            total += int(lead)
    return total


def first_int(text: str | None, default: int = 0) -> int:
    m = re.search(r"-?\d+", text or "")
    return int(m.group()) if m else default


_USAGE = re.compile(r"\((?:[^()]*?;\s*)?(Recharge\s+(\d)(?:\s*-\s*6)?|(\d+)\s*/\s*Day(?:\s+each)?|"
                    r"Recharges?\s+after\s+a\s+(Short|Long)[^()]*)\)", re.I)


def usage_from_name(name: str) -> dict | None:
    """"Fire Breath (Recharge 5-6)" -> recharge on 5+; "Teleport (3/Day)" -> three uses."""
    m = _USAGE.search(name or "")
    if not m:
        return None
    if m.group(2):
        return {"kind": "recharge", "max": 1, "recharge_min": int(m.group(2))}
    if m.group(3):
        return {"kind": "day", "max": int(m.group(3))}
    return {"kind": m.group(4).lower(), "max": 1}


_INNATE = re.compile(r"(\d+)\s*/\s*day(\s+each)?\s*:\s*([^\n]+)", re.I)
_SLOT_LINE = re.compile(r"(\d)(?:st|nd|rd|th)[ -]level\s*\((\d+)\s+slots?\)", re.I)
_LEGENDARY_COUNT = re.compile(r"can take (\d+) legendary actions?|Legendary Action Uses:\s*(\d+)", re.I)


def spell_slots_from_text(text: str) -> list[int]:
    slots = [0] * 9
    for level, count in _SLOT_LINE.findall(text or ""):
        slots[int(level) - 1] = int(count)
    while slots and slots[-1] == 0:
        slots.pop()
    return slots


def innate_spells_from_text(text: str) -> list[dict]:
    found = []
    for count, each, names in _INNATE.findall(text or ""):
        spells = [s.strip(" .") for s in re.split(r",\s*(?![^()]*\))", names) if s.strip(" .")]
        if each:
            found.extend({"name": s, "max": int(count)} for s in spells)
        elif spells:
            found.append({"name": ", ".join(spells), "max": int(count)})
    return found


def legendary_uses_from_text(text: str) -> int | None:
    m = _LEGENDARY_COUNT.search(text or "")
    return int(m.group(1) or m.group(2)) if m else None


def derive(monster: dict[str, Any]) -> dict[str, Any]:
    """Fill every derived field from the parsed ones. Idempotent."""
    m = monster
    m.setdefault("abilities", {})
    for key in ABILITIES:
        m["abilities"][key] = int(m["abilities"].get(key) or 10)
    m.setdefault("init_mod", ability_mod(m["abilities"]["dex"]))
    m["cr"] = (m.get("cr") or "").strip()
    m["cr_value"] = cr_value(m["cr"])
    # Minions and similar carry their own XP value; it wins over the CR table.
    m["xp"] = int(m["xp_override"]) if m.get("xp_override") is not None else CR_XP.get(m["cr"], 0)
    for section in ("traits", "actions", "bonus_actions", "reactions", "legendary", "villain", "lair"):
        m.setdefault(section, [])
        for entry in m[section]:
            entry.setdefault("attacks", [])
            for attack in entry["attacks"]:
                attack["avg"] = round(dice_average(attack.get("dice")), 1)

    spell_text = "\n".join(e["text"] for e in m["traits"] + m["actions"] if "spellcasting" in e["name"].lower())
    if not m.get("spell_slots"):
        m["spell_slots"] = spell_slots_from_text(spell_text)
    if m.get("legendary_uses") is None:
        header = " ".join(e["text"] for e in m["legendary"]) + " " + (m.get("legendary_intro") or "")
        m["legendary_uses"] = legendary_uses_from_text(header) or (3 if m["legendary"] else 0)

    resources: list[dict] = []

    def add(name: str, kind: str, maximum: int, **extra: Any) -> None:
        key = slugify(f"{kind}-{name}")
        if maximum > 0 and all(r["key"] != key for r in resources):
            resources.append({"key": key, "name": name, "kind": kind, "max": maximum, **extra})

    if m["legendary_uses"]:
        add("Legendary Actions", "legendary", m["legendary_uses"])
    for entry in m["villain"]:
        # MCDM villain actions: each usable once per encounter, one per round.
        add(entry["name"], "encounter", 1)
    for section in ("traits", "actions", "bonus_actions", "reactions"):
        for entry in m[section]:
            usage = entry.get("usage") or usage_from_name(entry["name"])
            if not usage:
                continue
            entry["usage"] = usage
            label = re.sub(r"\s*\([^()]*\)\s*$", "", entry["name"]).strip()
            if label.lower() == "legendary resistance":
                add(label, "legendary_resistance", usage["max"])
            else:
                add(label, usage["kind"], usage["max"],
                    **({"recharge_min": usage["recharge_min"]} if "recharge_min" in usage else {}))
    for level, count in enumerate(m["spell_slots"], start=1):
        add(f"Level {level} slots", "slot", count, level=level)
    for spell in innate_spells_from_text(spell_text):
        add(spell["name"], "day", spell["max"])
    m["resources"] = resources
    return m
