"""Stat block text -> monster dict.

The text is what lands in the clipboard when a stat block is selected on a
D&D Beyond monster page (or a PDF, or a wiki) and copied. A line state machine:
the top section is matched line by line against known labels, the first
"Name. text" entry or section heading ends it, and everything after is entries
grouped by heading. Anything unrecognised stays as text; nothing is dropped.

Handles the 2014 layout and the 2024 one (MOD/SAVE ability table, "Initiative",
"Immunities", "Attack Roll: +7"), since D&D Beyond shows both.
"""

from __future__ import annotations

import re
from typing import Any

from .statblock import ABILITIES, derive, first_int, normalise_text

SECTION_HEADINGS = {
    "traits": "traits", "actions": "actions", "bonus actions": "bonus_actions", "reactions": "reactions",
    "legendary actions": "legendary", "mythic actions": "legendary", "lair actions": "lair",
    "regional effects": "lair",
}
SIZE_LINE = re.compile(
    r"^(Tiny|Small|Medium|Large|Huge|Gargantuan)(?:\s+or\s+\w+)?\s+([^,]+?)(?:,\s*(.+))?$", re.I)
LABELS = [
    ("ac", re.compile(r"^(?:Armor Class|AC)\b:?\s*(.*)$", re.I)),
    ("hp", re.compile(r"^(?:Hit Points|HP)\b:?\s*(.*)$", re.I)),
    ("speed", re.compile(r"^Speed\b:?\s*(.*)$", re.I)),
    ("initiative", re.compile(r"^Initiative\b:?\s*(.*)$", re.I)),
    ("saves", re.compile(r"^Saving Throws\b:?\s*(.*)$", re.I)),
    ("skills", re.compile(r"^Skills\b:?\s*(.*)$", re.I)),
    ("vulnerable", re.compile(r"^(?:Damage )?Vulnerabilities\b:?\s*(.*)$", re.I)),
    ("resist", re.compile(r"^(?:Damage )?Resistances\b:?\s*(.*)$", re.I)),
    ("immune", re.compile(r"^Damage Immunities\b:?\s*(.*)$", re.I)),
    ("condition_immune", re.compile(r"^Condition Immunities\b:?\s*(.*)$", re.I)),
    ("immunities_2024", re.compile(r"^Immunities\b:?\s*(.*)$", re.I)),
    ("senses", re.compile(r"^Senses\b:?\s*(.*)$", re.I)),
    ("languages", re.compile(r"^Languages\b:?\s*(.*)$", re.I)),
    ("cr", re.compile(r"^(?:Challenge|CR)\b:?\s*(.*)$", re.I)),
    ("pb", re.compile(r"^Proficiency Bonus\b:?\s*(.*)$", re.I)),
    ("gear", re.compile(r"^Gear\b:?\s*(.*)$", re.I)),
]
ABILITY_ROW = re.compile(r"(\d{1,2})\s*\(\s*([+-]?\d+)\s*\)")
ABILITY_NAME = re.compile(r"^(STR|DEX|CON|INT|WIS|CHA)\b", re.I)
#: "Bite." / "Fire Breath (Recharge 5-6)." / "Multiattack:" at the start of a line.
ENTRY_START = re.compile(r"^([A-Z][\w'’/ -]{1,60}?(?:\s*\([^)]{1,60}\))?)\s*[.:]\s+(\S.*)$")
CONDITIONS = ("blinded", "charmed", "deafened", "exhaustion", "frightened", "grappled", "incapacitated",
              "paralyzed", "petrified", "poisoned", "prone", "restrained", "stunned", "unconscious")
NOT_AN_ENTRY = re.compile(r"^(Hit|Miss|Failure|Success|Failure or Success|Trigger|Response|At will|"
                          r"Cantrips?|\d+/day|\d(?:st|nd|rd|th) level)\b", re.I)


class PasteError(ValueError):
    """The text does not look like a stat block."""


def _lines(text: str) -> list[str]:
    text = normalise_text(text)
    text = re.sub(r"[*_#>`]+", "", text)  # markdown from homebrew pages
    return [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]


def _ability_scores(lines: list[str]) -> dict[str, int]:
    """2014: six "18 (+4)" in order. 2024: "STR 18 +4 +4" triplets, in any wrapping."""
    blob = " ".join(lines)
    rows = ABILITY_ROW.findall(blob)
    if len(rows) >= 6:
        return {key: int(score) for key, (score, _mod) in zip(ABILITIES, rows[:6])}
    found = {}
    for name, score in re.findall(r"\b(STR|DEX|CON|INT|WIS|CHA)\b\s*(\d{1,2})\b", blob, re.I):
        found.setdefault(name.lower(), int(score))
    if len(found) == 6:
        return found
    numbers = [int(n) for n in re.findall(r"(?<![+\-\d])\b(\d{1,2})\b", re.sub(r"\([^)]*\)", "", blob))]
    if len(numbers) >= 6 and not found:
        return dict(zip(ABILITIES, numbers[:6]))
    return found


def _saves_2024(lines: list[str], scores: dict[str, int]) -> str:
    """The 2024 table carries saves per ability; keep those that beat the plain modifier."""
    saves = []
    blob = " ".join(lines)
    for name, score, mod, save in re.findall(
            r"\b(STR|DEX|CON|INT|WIS|CHA)\b\s*(\d{1,2})\s*([+-]\d+)\s*([+-]\d+)", blob, re.I):
        if int(save) != int(mod):
            saves.append(f"{name.capitalize()} {save}")
    return ", ".join(saves)


def _split_entries(lines: list[str]) -> list[dict]:
    entries: list[dict] = []
    for line in lines:
        if not line:
            continue
        m = ENTRY_START.match(line)
        if m and not NOT_AN_ENTRY.match(m.group(1)) and len(m.group(1).split()) <= 7:
            entries.append({"name": m.group(1).strip(), "text": m.group(2).strip()})
        elif entries:
            joiner = "\n" if NOT_AN_ENTRY.match(line) else " "
            entries[-1]["text"] += joiner + line
        else:
            entries.append({"name": "", "text": line})
    return entries


def _attacks(entry: dict) -> list[dict]:
    text = entry["text"]
    to_hit = re.search(r"([+-]\s*\d+)\s+to\s+hit|Attack Roll:\s*([+-]\s*\d+)", text, re.I)
    if not to_hit:
        return []
    dice = re.search(r"Hit:\s*\d+\s*\(([^)]+)\)", text, re.I)
    bonus = (to_hit.group(1) or to_hit.group(2)).replace(" ", "")
    return [{"name": re.sub(r"\s*\([^)]*\)", "", entry["name"]), "to_hit": int(bonus),
             "dice": dice.group(1).replace(" ", "") if dice else ""}]


def _to_2014_wording(text: str) -> str:
    """The difficulty reader expects 2014 phrasing; 2024 blocks say the same thing differently."""
    text = re.sub(r"(Melee|Ranged|Melee or Ranged) Attack Roll:\s*([+-]\s*\d+)",
                  lambda m: f"{m.group(1)} Attack: {m.group(2).replace(' ', '')} to hit", text)
    return re.sub(r"(\w+) Saving Throw:\s*DC\s*(\d+)", r"DC \2 \1 saving throw", text)


def parse(text: str) -> dict[str, Any]:
    lines = _lines(text)
    while lines and not lines[0]:
        lines.pop(0)
    if len([ln for ln in lines if ln]) < 4:
        raise PasteError("Too short for a stat block.")

    monster: dict[str, Any] = {"name": lines[0].title() if lines[0].isupper() else lines[0], "source": "Pasted",
                               "sources": ["Pasted"], "official": False}
    fields: dict[str, str] = {}
    ability_lines: list[str] = []
    sections: dict[str, list[str]] = {key: [] for key in set(SECTION_HEADINGS.values())}
    current = None
    last_field = None
    in_abilities = False

    for line in lines[1:]:
        if not line:
            continue
        heading = SECTION_HEADINGS.get(line.lower().rstrip(":"))
        if heading:
            current, last_field, in_abilities = heading, None, False
            continue
        if current is None:
            size = SIZE_LINE.match(line)
            if size and "size" not in monster:
                monster["size"] = size.group(1).capitalize()
                monster["type"] = size.group(2).strip().lower()
                monster["alignment"] = (size.group(3) or "").strip()
                continue
            label = next(((key, m) for key, rx in LABELS if (m := rx.match(line))), None)
            if label:
                key, m = label
                fields[key] = m.group(1).strip()
                last_field, in_abilities = key, False
                # 2024 puts Initiative on the AC line.
                if key == "ac" and (init := re.search(r"Initiative\s*([+-]\s*\d+)", line, re.I)):
                    fields["initiative"] = init.group(1)
                    fields["ac"] = line[:init.start()].split("Class")[-1].replace("AC", "").strip(" :")
                continue
            if ABILITY_NAME.match(line) or re.fullmatch(r"(MOD|SAVE|\s)+", line, re.I) \
                    or (in_abilities and re.match(r"^[\d(+\-]", line)) or ABILITY_ROW.fullmatch(line):
                ability_lines.append(line)
                in_abilities, last_field = True, None
                continue
            entry = ENTRY_START.match(line)
            if entry and ability_lines and not NOT_AN_ENTRY.match(entry.group(1)) \
                    and len(entry.group(1).split()) <= 7:
                current = "traits"  # 2014 blocks have no "Traits" heading
                sections[current].append(line)
                continue
            if last_field:
                fields[last_field] = (fields[last_field] + " " + line).strip()
            continue
        sections[current].append(line)

    if "ac" not in fields and "hp" not in fields:
        raise PasteError("No Armor Class or Hit Points line found.")

    scores = _ability_scores(ability_lines)
    formula = re.search(r"\(([^)]*d[^)]*)\)", fields.get("hp", ""))
    immunities = fields.get("immune", "")
    condition_immunities = fields.get("condition_immune", "")
    if fields.get("immunities_2024"):
        # One list in 2024: damage types and conditions, separated by ";".
        parts = [p.strip() for p in re.split(r"[;,]", fields["immunities_2024"]) if p.strip()]
        immunities = ", ".join(p for p in parts if p.lower() not in CONDITIONS)
        condition_immunities = ", ".join(p for p in parts if p.lower() in CONDITIONS)
    cr_text = fields.get("cr", "")
    cr = re.match(r"\s*(\d+/\d+|\d+)", cr_text)
    passive = re.search(r"passive Perception\s*(\d+)", fields.get("senses", ""), re.I)

    monster.update({
        "ac": first_int(fields.get("ac"), 10), "ac_text": fields.get("ac", ""),
        "hp": first_int(fields.get("hp"), 1), "hp_formula": formula.group(1).replace(" ", "") if formula else "",
        "speed": fields.get("speed", ""),
        "abilities": scores,
        "saves": fields.get("saves") or _saves_2024(ability_lines, scores),
        "skills": fields.get("skills", ""), "senses": fields.get("senses", ""),
        "passive": int(passive.group(1)) if passive else 10,
        "languages": fields.get("languages", ""),
        "resist": fields.get("resist", ""), "immune": immunities, "vulnerable": fields.get("vulnerable", ""),
        "condition_immune": condition_immunities,
        "cr": cr.group(1) if cr else "",
        "gear": fields.get("gear", ""),
        "size": monster.get("size", ""), "type": monster.get("type", ""), "alignment": monster.get("alignment", ""),
        "description": "",
    })
    if "initiative" in fields:
        monster["init_mod"] = first_int(fields["initiative"])

    for key, raw in sections.items():
        entries = _split_entries(raw)
        if key == "legendary" and entries and (not entries[0]["name"] or "legendary action" in entries[0]["text"].lower()[:200]
                                                and not _attacks(entries[0])):
            intro = entries[0]
            if not intro["name"] or intro["name"].lower().startswith("legendary action"):
                monster["legendary_intro"] = (intro["name"] + ": " if intro["name"] else "") + intro["text"]
                entries = entries[1:]
        for entry in entries:
            entry["text"] = _to_2014_wording(entry["text"])
            entry["attacks"] = _attacks(entry)
        monster[key] = [e for e in entries if e["name"] or e["text"]]

    problems = []
    if len(scores) < 6:
        problems.append("Ability scores not found; defaulted to 10.")
    if not monster["cr"]:
        problems.append("Challenge rating not found.")
    if not monster.get("actions"):
        problems.append("No actions found.")
    monster = derive(monster)
    monster["import_problems"] = problems
    return monster
