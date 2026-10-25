"""5e character: decision log in, sheet out (2014 rules).

A character file holds only choices (race, classes and levels, ability method,
every pick a feature asks for, inventory, play state). `derive()` turns it into
every number the sheet shows, from the builder data written by builder_data.py.
Nothing derived is stored, so a fix here fixes every character.

Decision log shape (all keys optional except name):

    {"name": "...", "books": null,
     "abilities": {"method": "standard|pointbuy|manual", "base": {"str": 15, ...}},
     "race": {"id": "...", "ability_block": 0, "ability_choices": ["dex", "con"],
              "skills": [], "languages": [], "tools": [], "feat": {"id": "...", ...}},
     "background": {"id": "...", "skills": [], "languages": [], "tools": []},
     "classes": [{"id": "warlock", "level": 5, "subclass": "<subclass id>", "hp_rolls": [],
                  "skills": [], "expertise": [], "optionalfeatures": ["<id>"],
                  "asi": {"4": {"abilities": {"cha": 2}} | {"feat": {"id": "...", "ability_choices": [...]}}},
                  "spells": {"cantrips": [], "known": [], "prepared": []}}],
     "inventory": [{"id": "<item id>", "qty": 1, "equipped": true, "attuned": false}],
     "currency": {"cp": 0, "sp": 0, "ep": 0, "gp": 0, "pp": 0},
     "play": {"hp_current": null, "temp_hp": 0, "slots_used": {"1": 0}, "pact_used": 0,
              "counters_used": {}, "hit_dice_used": {}, "conditions": [], "exhaustion": 0,
              "inspiration": false, "death_saves": {"success": 0, "failure": 0}},
     "description": {}, "notes": ""}

The first class in `classes` is the starting class (saving throws, full skill list).
"""

from __future__ import annotations

import json
import math
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parents[2] / "content" / "dnd5e" / "private" / "builder"

ABILITIES = ("str", "dex", "con", "int", "wis", "cha")
ABILITY_NAMES = {"str": "Strength", "dex": "Dexterity", "con": "Constitution",
                 "int": "Intelligence", "wis": "Wisdom", "cha": "Charisma"}
SKILLS = {
    "acrobatics": "dex", "animal handling": "wis", "arcana": "int", "athletics": "str", "deception": "cha",
    "history": "int", "insight": "wis", "intimidation": "cha", "investigation": "int", "medicine": "wis",
    "nature": "int", "perception": "wis", "performance": "cha", "persuasion": "cha", "religion": "int",
    "sleight of hand": "dex", "stealth": "dex", "survival": "wis",
}
STANDARD_ARRAY = (15, 14, 13, 12, 10, 8)
#: PHB p. 108: Mystic Arcanum spell level -> warlock level
ARCANUM_AT = {6: 11, 7: 13, 8: 15, 9: 17}
#: PHB p. 15, Character Advancement: total XP needed for levels 1 to 20
XP_FOR_LEVEL = [0, 300, 900, 2700, 6500, 14000, 23000, 34000, 48000, 64000, 85000, 100000, 120000, 140000, 165000,
                195000, 225000, 265000, 305000, 355000]
POINT_BUY_COST = {8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9}
POINT_BUY_BUDGET = 27

#: The multiclass spellcaster table (PHB p. 165), indexed by caster level.
MULTICLASS_SLOTS = [
    [], [2], [3], [4, 2], [4, 3], [4, 3, 2], [4, 3, 3], [4, 3, 3, 1], [4, 3, 3, 2], [4, 3, 3, 3, 1],
    [4, 3, 3, 3, 2], [4, 3, 3, 3, 2, 1], [4, 3, 3, 3, 2, 1], [4, 3, 3, 3, 2, 1, 1], [4, 3, 3, 3, 2, 1, 1],
    [4, 3, 3, 3, 2, 1, 1, 1], [4, 3, 3, 3, 2, 1, 1, 1], [4, 3, 3, 3, 2, 1, 1, 1, 1],
    [4, 3, 3, 3, 3, 1, 1, 1, 1], [4, 3, 3, 3, 3, 2, 1, 1, 1], [4, 3, 3, 3, 3, 2, 2, 1, 1],
]

#: Skill expertise picks by class level; no data field carries these.
EXPERTISE = {"Rogue": {1: 2, 6: 2}, "Bard": {3: 2, 10: 2}}

#: Bonus proficiencies subclasses grant in prose only (5etools has no field for them).
SUBCLASS_PROFICIENCIES = {
    "Life Domain": {"armor": ["heavy"]}, "Nature Domain": {"armor": ["heavy"]},
    "Tempest Domain": {"armor": ["heavy"], "weapons": ["martial"]}, "War Domain": {"armor": ["heavy"], "weapons": ["martial"]},
    "Forge Domain": {"armor": ["heavy"]}, "Twilight Domain": {"armor": ["heavy"], "weapons": ["martial"]},
    "Order Domain": {"armor": ["heavy"]}, "Death Domain": {"weapons": ["martial"]},
    "The Hexblade": {"armor": ["medium", "shield"], "weapons": ["martial"]},
    "College of Valor": {"armor": ["medium", "shield"], "weapons": ["martial"]},
    "College of Swords": {"armor": ["medium"], "weapons": ["scimitar"]},
    "Bladesinging": {"armor": ["light"]},
    "Battle Smith": {"weapons": ["martial"]}, "Armorer": {"armor": ["heavy"]},
    "Assassin": {"tools": ["disguise kit", "poisoner's kit"]},
}

DRAGONS = {"Black": "acid", "Blue": "lightning", "Brass": "fire", "Bronze": "lightning", "Copper": "acid",
           "Gold": "fire", "Green": "poison", "Red": "fire", "Silver": "cold", "White": "cold"}
FAVORED_ENEMIES = ["Aberrations", "Beasts", "Celestials", "Constructs", "Dragons", "Elementals", "Fey", "Fiends", "Giants",
                   "Monstrosities", "Oozes", "Plants", "Undead", "Two humanoid races"]
TERRAINS = ["Arctic", "Coast", "Desert", "Forest", "Grassland", "Mountain", "Swamp", "Underdark"]

#: Picks a feature asks for. (origin, feature) -> how many by class level, and the list.
#: "options" means the choices are the named children of the feature's 5etools options block.
#: Only real one-time choices are listed; 5etools also uses options blocks for lists you get in full.
FEATURE_PICKS = {
    ("Ranger", "Favored Enemy"): ({1: 1, 6: 2, 14: 3}, FAVORED_ENEMIES),
    ("Ranger", "Natural Explorer"): ({1: 1, 6: 2, 10: 3}, TERRAINS),
    ("Draconic Bloodline", "Dragon Ancestor"): ({1: 1}, list(DRAGONS)),
    ("Hunter", "Hunter's Prey"): ({3: 1}, "options"), ("Hunter", "Hunter"): ({3: 1}, "options"),
    ("Hunter", "Defensive Tactics"): ({7: 1}, "options"), ("Hunter", "Multiattack"): ({11: 1}, "options"),
    ("Hunter", "Superior Hunter's Defense"): ({15: 1}, "options"),
    ("Path of the Totem Warrior", "Path of the Totem Warrior"): ({3: 1}, "options"),
    ("Path of the Totem Warrior", "Aspect of the Beast"): ({6: 1}, "options"),
    ("Path of the Totem Warrior", "Totemic Attunement"): ({14: 1}, "options"),
    ("Path of the Storm Herald", "Path of the Storm Herald"): ({3: 1}, "options"),
    ("Path of the Storm Herald", "Storm Soul"): ({6: 1}, "options"),
    ("Path of the Storm Herald", "Raging Storm"): ({14: 1}, "options"),
}


def _option_names(entries: Any) -> list[str]:
    if isinstance(entries, list):
        for e in entries:
            names = _option_names(e)
            if names:
                return names
    elif isinstance(entries, dict):
        if entries.get("type") == "options":
            return [c["name"] for c in entries.get("entries", []) if isinstance(c, dict) and c.get("name")]
        return _option_names(list(v for v in entries.values() if isinstance(v, (list, dict))))
    return []


def _keep_chosen(entries: Any, chosen: list[str]) -> Any:
    """The feature text with its options block cut down to the chosen children."""
    if isinstance(entries, list):
        return [_keep_chosen(e, chosen) for e in entries]
    if isinstance(entries, dict):
        if entries.get("type") == "options":
            return {**entries, "entries": [c for c in entries.get("entries", []) if isinstance(c, dict) and c.get("name") in chosen]}
        return {k: _keep_chosen(v, chosen) for k, v in entries.items()}
    return entries


#: Toggles on the sheet for effects that change numbers while they last (2014 text).
EFFECTS = {
    "Rage": "Barbarian: rage damage on Strength melee weapon attacks, resistance to bludgeoning, piercing and slashing.",
    "Bladesong": "Bladesinging: AC and concentration saves + Intelligence modifier (min 1), walking speed + 10 ft.",
    "Mage Armor": "Base AC 13 + Dexterity while wearing no armor.",
    "Shield of Faith": "+2 AC.",
    "Barkskin": "AC can't be less than 16.",
    "Haste": "+2 AC, speed doubled, advantage on Dexterity saves.",
    "Shield": "+5 AC until the start of your next turn.",
    "Bless": "+1d4 to attack rolls and saving throws.",
}
SPEED_ZERO = {"grappled", "restrained", "paralyzed", "petrified", "stunned", "unconscious"}

ARMOR_TYPES = {"LA": "light", "MA": "medium", "HA": "heavy", "S": "shield"}


# --- data -------------------------------------------------------------------

class Data:
    """Builder data with id indexes. Load once per process via `load_data()`."""

    def __init__(self, data_dir: Path = DATA_DIR):
        self.dir = Path(data_dir)
        read = lambda kind: json.loads((self.dir / f"{kind}.json").read_text())
        self.classes = {c["id"]: c for c in read("classes")}
        self.subclasses = {s["id"]: (c, s) for c in self.classes.values() for s in c["subclasses"]}
        self.races = {r["id"]: r for r in read("races")}
        self.backgrounds = {b["id"]: b for b in read("backgrounds")}
        self.feats = {f["id"]: f for f in read("feats")}
        self.optionalfeatures = {o["id"]: o for o in read("optionalfeatures")}
        self.spells = {s["id"]: s for s in read("spells")}
        self.items = {i["id"]: i for i in read("items")}
        self.spell_by_name = {}
        for s in self.spells.values():
            self.spell_by_name.setdefault(s["name"].lower(), s)
            self.spell_by_name[f"{s['name'].lower()}|{s['source'].lower()}"] = s
        self.item_by_name = {}
        for i in self.items.values():
            self.item_by_name.setdefault(i["name"].lower(), i)
            self.item_by_name[f"{i['name'].lower()}|{i['source'].lower()}"] = i


@lru_cache(maxsize=2)
def _cached(data_dir: str, stamp: float) -> Data:
    return Data(Path(data_dir))


def load_data(data_dir: Path = DATA_DIR) -> Data:
    meta = Path(data_dir) / "meta.json"
    return _cached(str(data_dir), meta.stat().st_mtime if meta.exists() else 0)


# --- helpers ----------------------------------------------------------------

_TAG = re.compile(r"\{@(\w+) ([^{}]*?)\}")


def plain(text: Any) -> str:
    """5etools {@tag text|source|display} markup to plain text."""
    if not isinstance(text, str):
        return ""
    for _ in range(4):
        new = _TAG.sub(lambda m: _tag_text(m.group(1), m.group(2)), text)
        if new == text:
            break
        text = new
    return text


def _tag_text(tag: str, body: str) -> str:
    parts = body.split("|")
    if tag in ("dice", "damage", "d20", "hit", "chance", "scaledice", "scaledamage"):
        return parts[-1] if tag.startswith("scale") else parts[0]
    if len(parts) >= 3 and parts[2]:
        return parts[2]
    return parts[0]


def modifier(score: int) -> int:
    return (score - 10) // 2


def proficiency_bonus(level: int) -> int:
    return 2 + (max(level, 1) - 1) // 4


def _choose_list(blocks: list | None, chosen: list[str], universe: list[str]) -> list[str]:
    """Fixed picks from a 5etools proficiency block plus the player's picks, capped by count."""
    out: list[str] = []
    if not blocks:
        return out
    block = blocks[0]
    allowed_count = 0
    allowed_from: list[str] | None = None
    for key, value in block.items():
        if key == "choose":
            allowed_count += value.get("count", 1)
            allowed_from = [plain(x).lower() for x in value.get("from", [])]
        elif key == "any":
            allowed_count += value
            allowed_from = None
        elif key.startswith("any") and isinstance(value, int):
            allowed_count += value
        elif value is True:
            out.append(plain(key).lower())
    picks = [c for c in chosen if (allowed_from is None or c in allowed_from) and c not in out][:allowed_count]
    return out + picks


def _progression_allowed(prog: dict, level: int) -> int:
    p = prog["progression"]
    return p[level - 1] if isinstance(p, list) else max([v for k, v in p.items() if int(k) <= level] or [0])


def active_options(entry: dict, cls: dict, sub: dict | None, level: int, data) -> list[str]:
    """The class's chosen optional features (invocations, styles, maneuvers...) that count at this level:
    after a level is removed, the latest picks beyond the table's count drop out."""
    progs = (cls.get("optionalfeatureProgression") or []) + ((sub or {}).get("optionalfeatureProgression") or [])
    kept, used = [], {}
    for oid in entry.get("optionalfeatures", []):
        opt = data.optionalfeatures.get(oid)
        if not opt:
            continue
        prog = next((i for i, p in enumerate(progs) if set(opt.get("featureType", [])) & set(p["featureType"])), None)
        if prog is None:
            kept.append(oid)
            continue
        if used.get(prog, 0) < _progression_allowed(progs[prog], level):
            used[prog] = used.get(prog, 0) + 1
            kept.append(oid)
    return kept


def _feat_options(feat: dict, choice: dict, data) -> list[str]:
    """Optional features picked through a feat (Eldritch Adept, Fighting Initiate, Martial Adept,
    Metamagic Adept): only ids of the feature types the feat names, at most as many as it grants."""
    out = []
    for prog in feat.get("optionalfeatureProgression") or []:
        count = sum(v for v in (prog.get("progression") or {}).values() if isinstance(v, int))
        fits = [o for o in choice.get("optionalfeatures", []) if o in data.optionalfeatures and o not in out
                and set(data.optionalfeatures[o].get("featureType", [])) & set(prog["featureType"])]
        out.extend(fits[:count])
    return out


def origin_blocks(blocks: list | None) -> list | None:
    """Tasha's Customizing Your Origin (TCE p. 8): every racial increase may go to any ability, so a block's
    fixed and chosen increases become the same amounts on abilities of choice (Hill Dwarf +2 Con +1 Wis -> +2/+1)."""
    if not blocks:
        return blocks
    out = []
    for block in blocks:
        weights = [v for k, v in block.items() if k in ABILITIES and isinstance(v, int)]
        choose = block.get("choose") or {}
        if "weighted" in choose:
            weights += choose["weighted"].get("weights", [])
        elif choose:
            weights += [choose.get("amount", 1)] * choose.get("count", 1)
        out.append({"choose": {"weighted": {"from": list(ABILITIES), "weights": sorted(weights, reverse=True)}}} if weights else block)
    return out


def _ability_bonuses(blocks: list | None, block_index: int, chosen: list[str]) -> dict[str, int]:
    """5etools `ability` block: fixed increases plus "choose" (count/amount or weighted)."""
    bonus = {a: 0 for a in ABILITIES}
    if not blocks:
        return bonus
    block = blocks[min(block_index, len(blocks) - 1)]
    for key, value in block.items():
        if key in ABILITIES:
            bonus[key] += value
    choose = block.get("choose")
    if choose:
        if "weighted" in choose:
            weights = choose["weighted"].get("weights", [])
            frm = choose["weighted"].get("from", list(ABILITIES))
            for ability, weight in zip([c for c in chosen if c in frm], weights):
                bonus[ability] += weight
        else:
            frm = choose.get("from", list(ABILITIES))
            amount = choose.get("amount", 1)
            for ability in [c for c in chosen if c in frm][:choose.get("count", 1)]:
                bonus[ability] += amount
    return bonus


def _spell_ref(data: Data, ref: str) -> dict | None:
    ref = plain(ref).lower().split("#")[0]
    return data.spell_by_name.get(ref) or data.spell_by_name.get(ref.split("|")[0])


def _item_ref(data: Data, ref: str) -> dict | None:
    ref = ref.lower()
    return data.item_by_name.get(ref) or data.item_by_name.get(ref.split("|")[0])


def _table_column(cls_or_sub: dict, label: str, level: int, groups_key: str = "classTableGroups") -> Any:
    for group in cls_or_sub.get(groups_key, []) or []:
        for i, col in enumerate(group.get("colLabels", [])):
            if plain(col).lower() == label.lower() and group.get("rows"):
                cell = group["rows"][min(level, len(group["rows"])) - 1][i]
                if isinstance(cell, dict):
                    return cell.get("value", cell.get("toRoll", [{}])[0].get("faces") if cell.get("toRoll") else None)
                return cell
    return None


def _table_text(cls: dict, label: str, level: int) -> str | None:
    """A class table cell as printed: dice as "3d6", bonuses as "+2"."""
    for group in cls.get("classTableGroups", []) or []:
        for i, col in enumerate(group.get("colLabels", [])):
            if plain(col).lower() == label.lower() and group.get("rows"):
                cell = group["rows"][min(level, len(group["rows"])) - 1][i]
                if isinstance(cell, dict) and cell.get("toRoll"):
                    return "+".join(f"{d.get('number', 1)}d{d['faces']}" for d in cell["toRoll"])
                if isinstance(cell, dict):
                    value = cell.get("value")
                    return f"+{value}" if cell.get("type") == "bonus" else str(value)
                return plain(str(cell))
    return None


def class_values(class_rows) -> dict[str, str]:
    """The number a feature scales to at the current level, keyed by feature name, for the Features tab."""
    out = {}
    for _, cls, sub, level in class_rows:
        name = cls["name"]
        if name == "Rogue":
            out["Sneak Attack"] = _table_text(cls, "Sneak Attack", level)
        elif name == "Monk":
            out["Martial Arts"] = _table_text(cls, "Martial Arts", level)
        elif name == "Barbarian":
            out["Rage"] = f"{_table_text(cls, 'Rage Damage', level)} rage damage"
        elif name == "Bard":  # PHB p. 54
            out["Bardic Inspiration"] = "d12" if level >= 15 else "d10" if level >= 10 else "d8" if level >= 5 else "d6"
        if (sub or {}).get("name") == "Battle Master" and level >= 3:  # PHB p. 73-74
            out["Combat Superiority"] = "d12" if level >= 18 else "d10" if level >= 10 else "d8"
    return {k: v for k, v in out.items() if v}


def _slot_row(cls_or_sub: dict, level: int, groups_key: str = "classTableGroups") -> list[int]:
    for group in cls_or_sub.get(groups_key, []) or []:
        rows = group.get("rowsSpellProgression")
        if rows:
            row = rows[min(level, len(rows)) - 1]
            while row and row[-1] == 0:
                row = row[:-1]
            return list(row)
    return []


# --- derivation -------------------------------------------------------------

def derive(char: dict, data: Data | None = None) -> dict:
    data = data or load_data()
    problems: list[str] = []
    sheet: dict[str, Any] = {"name": char.get("name", ""), "problems": problems}

    # Classes and levels.
    class_rows = []
    for entry in char.get("classes", []):
        cls = data.classes.get(entry.get("id"))
        if cls is None:
            problems.append(f"Unknown class {entry.get('id')!r}.")
            continue
        sub = None
        if entry.get("subclass"):
            found = data.subclasses.get(entry["subclass"])
            if found and found[0]["id"] == cls["id"]:
                sub = found[1]
            else:
                problems.append(f"Unknown subclass {entry['subclass']!r} for {cls['name']}.")
        level = max(1, min(20, int(entry.get("level", 1))))
        class_rows.append((entry, cls, sub, level))
    total_level = sum(r[3] for r in class_rows) or 1
    prof = proficiency_bonus(total_level)
    sheet["level"] = total_level
    sheet["proficiency_bonus"] = prof
    if (char.get("preferences") or {}).get("advancement") == "xp":
        total_xp = max(0, int(char.get("xp") or 0))
        sheet["xp"] = {"total": total_xp, "level_by_xp": sum(1 for need in XP_FOR_LEVEL if total_xp >= need),
                       "current": XP_FOR_LEVEL[total_level - 1], "next": XP_FOR_LEVEL[total_level] if total_level < 20 else None}
    sheet["classes"] = [{"id": c["id"], "name": c["name"], "level": lv, "subclass": s["name"] if s else None,
                         "subclass_id": s["id"] if s else None, "hit_die": c["hd"]["faces"]}
                        for _, c, s, lv in class_rows]

    race = data.races.get((char.get("race") or {}).get("id"))
    if race and race["name"] == "Custom Lineage":  # TCE p. 8, Variable Trait: darkvision 60 ft. OR one skill
        trait = (char.get("race") or {}).get("variable_trait")
        race = {k: v for k, v in race.items() if not (k == "darkvision" and trait != "darkvision")
                and not (k == "skillProficiencies" and trait != "skill")}
    background = data.backgrounds.get((char.get("background") or {}).get("id"))
    if (char.get("race") or {}).get("id") and race is None:
        problems.append(f"Unknown race {char['race']['id']!r}.")
    if (char.get("background") or {}).get("id") and background is None:
        problems.append(f"Unknown background {char['background']['id']!r}.")
    sheet["race"] = race["name"] if race else None
    custom_bg = (char.get("background") or {}).get("custom") or {}
    sheet["background"] = custom_bg.get("name") or (background["name"] if background else ("Custom background" if custom_bg else None))

    # Feats: race feat (Variant Human, Custom Lineage) plus ASI-level feats.
    feats: list[tuple[dict, dict]] = []
    race_choice = char.get("race") or {}
    if race_choice.get("feat", {}).get("id"):
        feat = data.feats.get(race_choice["feat"]["id"])
        if feat:
            feats.append((feat, race_choice["feat"]))
    for pick in char.get("bonus_feats", []):
        feat = data.feats.get(pick.get("id"))
        if feat:
            feats.append((feat, pick))
        elif pick.get("name"):
            problems.append(f"Feat {pick['name']!r} is not in the 2014 books; it has no effect here.")
    asi_bonus = {a: 0 for a in ABILITIES}
    for entry, cls, sub, level in class_rows:
        for lvl, pick in (entry.get("asi") or {}).items():
            if int(lvl) > level:
                continue
            if pick.get("feat", {}).get("id"):
                feat = data.feats.get(pick["feat"]["id"])
                if feat:
                    feats.append((feat, pick["feat"]))
                else:
                    problems.append(f"Unknown feat {pick['feat']['id']!r}.")
            for ability, amount in (pick.get("abilities") or {}).items():
                asi_bonus[ability] = asi_bonus.get(ability, 0) + amount

    # Ability scores.
    raw = (char.get("abilities") or {}).get("base") or {}
    base = {a: int(raw[a]) if raw.get(a) not in (None, "") else 10 for a in ABILITIES}
    race_blocks = race.get("ability") if race else None
    if (char.get("preferences") or {}).get("customize_origin"):
        race_blocks = origin_blocks(race_blocks)
    race_bonus = _ability_bonuses(race_blocks, race_choice.get("ability_block", 0),
                                  race_choice.get("ability_choices", []))
    feat_bonus = {a: 0 for a in ABILITIES}
    for feat, choice in feats:
        for a, v in _ability_bonuses(feat.get("ability"), choice.get("ability_block", 0),
                                     choice.get("ability_choices", [])).items():
            feat_bonus[a] += v
    flat = {a: int((char.get("abilities") or {}).get("bonus", {}).get(a) or 0) for a in ABILITIES}
    override = (char.get("abilities") or {}).get("override") or {}
    scores = {a: int(override[a]) if override.get(a) else min(20, base[a] + race_bonus[a] + asi_bonus[a] + feat_bonus[a]) + flat[a]
              for a in ABILITIES}
    mods = {a: modifier(scores[a]) for a in ABILITIES}
    sheet["abilities"] = {a: {"name": ABILITY_NAMES[a], "score": scores[a], "modifier": mods[a], "base": base[a],
                              "race": race_bonus[a], "asi": asi_bonus[a], "feat": feat_bonus[a],
                              "bonus": flat[a], "override": override.get(a)} for a in ABILITIES}
    method = (char.get("abilities") or {}).get("method", "manual")
    if method == "pointbuy":
        spent = sum(POINT_BUY_COST.get(base[a], 99) for a in ABILITIES)
        sheet["point_buy"] = {"spent": spent, "budget": POINT_BUY_BUDGET}
        if spent > POINT_BUY_BUDGET or any(base[a] not in POINT_BUY_COST for a in ABILITIES):
            problems.append(f"Point buy spends {spent} of {POINT_BUY_BUDGET} points or uses a score outside 8 to 15.")
    elif method == "standard" and all(raw.get(a) not in (None, "") for a in ABILITIES) and sorted(base.values(), reverse=True) != list(STANDARD_ARRAY):
        problems.append("Standard array: the six base scores must be 15, 14, 13, 12, 10 and 8.")

    if len(class_rows) > 1:
        for _, cls, _, _ in class_rows:
            req = (cls.get("multiclassing") or {}).get("requirements") or {}
            plain_req = {a: v for a, v in req.items() if a in ABILITIES}
            if plain_req and not all(scores[a] >= v for a, v in plain_req.items()):
                problems.append(f"Multiclassing into or out of {cls['name']} needs " +
                                ", ".join(f"{a.upper()} {v}" for a, v in plain_req.items()) + " (PHB p. 163).")
            # 5etools "or": [{"str": 13, "dex": 13}] is Strength 13 or Dexterity 13 (the fighter, PHB p. 163)
            alternatives = [(a, v) for alt in req.get("or") or [] for a, v in alt.items()]
            if alternatives and not any(scores[a] >= v for a, v in alternatives):
                problems.append(f"Multiclassing into or out of {cls['name']} needs " +
                                " or ".join(f"{a.upper()} {v}" for a, v in alternatives) + " (PHB p. 163).")

    # Proficiencies.
    starting = class_rows[0] if class_rows else None
    saves = set(starting[1].get("proficiency", [])) if starting else set()
    skills: set[str] = set()
    tools: list[str] = []
    languages: list[str] = []
    armor: set[str] = set()
    weapons: set[str] = set()
    for i, (entry, cls, sub, level) in enumerate(class_rows):
        profs = cls.get("startingProficiencies", {}) if i == 0 else (cls.get("multiclassing") or {}).get("proficienciesGained", {})
        skills.update(_choose_list(profs.get("skills"), entry.get("skills", []), list(SKILLS)))
        armor.update(plain(a).lower() for a in profs.get("armor", []) if isinstance(a, str))
        weapons.update(plain(w).lower() for w in profs.get("weapons", []) if isinstance(w, str))
        tools.extend(plain(t) for t in profs.get("tools", []) if isinstance(t, str))
    for entry, cls, sub, level in class_rows:
        extra = SUBCLASS_PROFICIENCIES.get((sub or {}).get("name"), {})
        armor.update(extra.get("armor", []))
        weapons.update(extra.get("weapons", []))
        tools.extend(extra.get("tools", []))
    if race:
        skills.update(_choose_list(race.get("skillProficiencies"), race_choice.get("skills", []), list(SKILLS)))
        languages.extend(_choose_list(race.get("languageProficiencies"), race_choice.get("languages", []), []))
        weapons.update(plain(w).split("|")[0].lower() for block in race.get("weaponProficiencies", []) or []
                       for w, v in block.items() if v is True)
        armor.update(a for block in race.get("armorProficiencies", []) or [] for a, v in block.items() if v is True)
    bg_choice = char.get("background") or {}
    if bg_choice.get("custom"):
        # PHB p. 125, Customizing a Background: the player's own skill, tool and language picks replace the book's.
        custom = bg_choice["custom"]
        skills.update(s for s in custom.get("skills", []) if s in SKILLS)
        tools.extend(custom.get("tools", []))
        languages.extend(custom.get("languages", []))
    elif background:
        bg_skills = _choose_list(background.get("skillProficiencies"), bg_choice.get("skills", []), list(SKILLS))
        # PHB p. 125: a background skill the character already has may be swapped for any other skill
        overlap = [x for x in bg_skills if x in skills]
        sheet["background_overlap"] = overlap
        skills.update(bg_skills)
        skills.update([x for x in bg_choice.get("replacement_skills", []) if x in SKILLS and x not in skills][:len(overlap)])
        languages.extend(_choose_list(background.get("languageProficiencies"), bg_choice.get("languages", []), []))
        tools.extend(_choose_list(background.get("toolProficiencies"), bg_choice.get("tools", []), []))
    for feat, choice in feats:
        skills.update(_choose_list(feat.get("skillProficiencies"), choice.get("skills", []), list(SKILLS)))
        tools.extend(_choose_list(feat.get("toolProficiencies"), choice.get("tools", []), []))
        languages.extend(_choose_list(feat.get("languageProficiencies"), choice.get("languages", []), []))
        # Skilled (PHB p. 170): three picks, each a skill or a tool, stored as "skill:arcana" / "tool:lute".
        for block in feat.get("skillToolLanguageProficiencies", []) or []:
            count = sum(c.get("count", 1) for c in block.get("choose", []))
            for pick in choice.get("skill_tool", [])[:count]:
                kind, _, name = pick.partition(":")
                if kind == "skill" and name in SKILLS:
                    skills.add(name)
                elif kind == "tool" and name:
                    tools.append(name)
        for block in feat.get("savingThrowProficiencies", []) or []:
            if "choose" in block:
                saves.update(a for a in choice.get("ability_choices", [])[:1])
            saves.update(a for a, v in block.items() if v is True)
        armor.update(a for block in feat.get("armorProficiencies", []) or [] for a, v in block.items() if v is True)
        weapons.update(plain(w).split("|")[0].lower() for block in feat.get("weaponProficiencies", []) or []
                       for w, v in block.items() if v is True)
    skills &= set(SKILLS)

    expertise: set[str] = set()
    for entry, cls, sub, level in class_rows:
        allowed = sum(n for lv, n in EXPERTISE.get(cls["name"], {}).items() if lv <= level)
        # PHB p. 96: a rogue may take thieves' tools instead of a skill
        expertise.update([s for s in entry.get("expertise", []) if s in skills or (cls["name"] == "Rogue" and s == "thieves' tools")][:allowed])
    for feat, choice in feats:
        if feat.get("expertise"):
            expertise.update([s for s in choice.get("expertise", []) if s in skills][:1])

    jack = any(cls["name"] == "Bard" and level >= 2 for _, cls, _, level in class_rows)
    athlete = any((sub or {}).get("name") == "Champion" and level >= 7 for _, _, sub, level in class_rows)
    feat_names = {f["name"] for f, _ in feats}
    sheet["saving_throws"] = {a: {"modifier": mods[a] + (prof if a in saves else 0), "proficient": a in saves}
                              for a in ABILITIES}
    sheet["skills"] = {}
    for skill, ability in SKILLS.items():
        if skill in expertise:
            bonus, mark = 2 * prof, "expertise"
        elif skill in skills:
            bonus, mark = prof, "proficient"
        elif athlete and ability in ("str", "dex", "con"):
            bonus, mark = math.ceil(prof / 2), "half"  # Remarkable Athlete rounds up (PHB p. 72)
        elif jack:
            bonus, mark = prof // 2, "half"
        else:
            bonus, mark = 0, None
        sheet["skills"][skill] = {"ability": ability, "modifier": mods[ability] + bonus, "proficiency": mark}
    # skills made up at the table (DDB's custom skills): [{"name", "ability", "proficiency": None|"half"|"proficient"|"expertise", "misc", "override"}]
    level_bonus = {"half": prof // 2, "proficient": prof, "expertise": 2 * prof}
    sheet["custom_skills"] = []
    for custom in char.get("custom_skills") or []:
        ability = custom.get("ability") if custom.get("ability") in ABILITIES else None
        mark = custom.get("proficiency") if custom.get("proficiency") in level_bonus else None
        total = (mods[ability] if ability else 0) + level_bonus.get(mark, 0) + int(custom.get("misc") or 0)
        if custom.get("override") not in (None, ""):
            total = int(custom["override"])
        sheet["custom_skills"].append({"name": str(custom.get("name") or "Custom skill"), "ability": ability,
                                       "modifier": total, "proficiency": mark})
    observant = "Observant" in feat_names
    sheet["passives"] = {
        "perception": 10 + sheet["skills"]["perception"]["modifier"] + (5 if observant else 0),
        "investigation": 10 + sheet["skills"]["investigation"]["modifier"] + (5 if observant else 0),
        "insight": 10 + sheet["skills"]["insight"]["modifier"],
    }
    sheet["initiative"] = mods["dex"] + (math.ceil(prof / 2) if athlete else prof // 2 if jack else 0) + (5 if "Alert" in feat_names else 0)
    # proficiencies added by hand in the sheet's Proficiencies pane: [{"type": "armor"|"weapons"|"tools"|"languages", "name": ...}]
    for custom in char.get("custom_proficiencies") or []:
        name = str(custom.get("name") or "").strip().lower()
        if name and custom.get("type") in ("armor", "weapons"):
            (armor if custom["type"] == "armor" else weapons).add(name)
        elif name and custom.get("type") in ("tools", "languages"):
            (tools if custom["type"] == "tools" else languages).append(name)
    sheet["proficiencies"] = {"armor": sorted(armor), "weapons": sorted(weapons),
                              "tools": sorted(f"{t} (expertise)" if t in expertise else t for t in set(tools)),
                              "languages": sorted(set(languages))}

    # Hit points.
    hp = 0
    use_rolls = (char.get("description") or {}).get("hp_mode") == "rolled"
    for i, (entry, cls, sub, level) in enumerate(class_rows):
        die = cls["hd"]["faces"]
        rolls = list(entry.get("hp_rolls") or []) if use_rolls else []
        for lv in range(1, level + 1):
            if i == 0 and lv == 1:
                gain = die
            else:
                idx = lv - (2 if i == 0 else 1)
                gain = rolls[idx] if 0 <= idx < len(rolls) and rolls[idx] else die // 2 + 1
            hp += max(1, gain + mods["con"])
    if "Tough" in feat_names:
        hp += 2 * total_level
    if race and race.get("subrace") == "Hill":
        hp += total_level
    for _, cls, sub, level in class_rows:
        if sub and sub["name"] == "Draconic Bloodline":
            hp += level
    overrides = char.get("overrides") or {}
    hp += int(overrides.get("hp_bonus") or 0)
    if overrides.get("hp_max"):
        hp = int(overrides["hp_max"])
    play = char.get("play") or {}
    sheet["hp"] = {"max": hp, "current": play.get("hp_current", hp) if play.get("hp_current") is not None else hp,
                   "temp": play.get("temp_hp", 0)}
    sheet["hit_dice"] = [{"class": cls["name"], "class_id": cls["id"], "die": cls["hd"]["faces"], "total": level,
                          "used": (play.get("hit_dice_used") or {}).get(cls["id"], 0)} for _, cls, _, level in class_rows]

    # Inventory, armour class, attacks.
    artificer_cls = next((cls for _, cls, _, _ in class_rows if cls["name"] == "Artificer"), None)
    artificer_level = next((level for _, cls, _, level in class_rows if cls["name"] == "Artificer"), 0)
    inventory = []
    for slot in char.get("inventory", []):
        item = data.items.get(slot.get("id"))
        if item is None and slot.get("custom"):
            item = {"id": None, "name": slot["custom"].get("name", "Item"), "weight": slot["custom"].get("weight", 0)}
        if item is None:
            problems.append(f"Unknown item {slot.get('id')!r}.")
            continue
        if slot.get("infusion") in data.optionalfeatures:
            item = _infused(item, data.optionalfeatures[slot["infusion"]]["name"], artificer_level)
        inventory.append((slot, item))
    infused = [slot for slot, _ in inventory if slot.get("infusion") in data.optionalfeatures]
    if artificer_level:  # TCE p. 12: infused items at a time, from the class table
        infused_max = int(_table_column(artificer_cls, "Infused Items", artificer_level) or 0)
        sheet["infusions"] = {"used": len(infused), "max": infused_max}
        if len(infused) > infused_max:
            problems.append(f"{len(infused)} items infused, {infused_max} allowed.")
    # Saving throws from items (Cloak/Ring of Protection) and the paladin's Aura of Protection (PHB p. 85)
    save_bonus = _item_bonus(inventory, "bonusSavingThrow")
    if any(cls["name"] == "Paladin" and level >= 6 for _, cls, _, level in class_rows):
        save_bonus += max(1, mods["cha"])
    for a in ABILITIES:
        sheet["saving_throws"][a]["modifier"] += save_bonus
    check_bonus = _item_bonus(inventory, "bonusAbilityCheck")  # Stone of Good Luck
    for entry in [*sheet["skills"].values(), *sheet["custom_skills"]]:
        entry["modifier"] += check_bonus
    # DMG p. 136: three attuned items; artificers 4, 5, 6 at levels 10, 14, 18 (ERLW, TCE p. 14)
    attune_max = 3 + sum(1 for _, cls, _, level in class_rows if cls["name"] == "Artificer" for at in (10, 14, 18) if level >= at)
    attuned = sum(1 for slot, item in inventory if slot.get("attuned") and item.get("reqAttune"))
    sheet["attunement"] = {"used": attuned, "max": attune_max}
    if attuned > attune_max:
        problems.append(f"{attuned} items attuned, {attune_max} allowed.")
    containers = {slot.get("uid"): item for slot, item in inventory if slot.get("uid") and item.get("containerCapacity")}
    sheet["inventory"] = [{"id": item.get("id"), "name": item["name"], "qty": slot.get("qty", 1),
                           "equipped": bool(slot.get("equipped")), "attuned": bool(slot.get("attuned")),
                           "weight": item.get("weight", 0), "type": item.get("type"), "uid": slot.get("uid"),
                           "inside": slot.get("inside") if slot.get("inside") in containers else None,
                           "container": bool(item.get("containerCapacity")),
                           "rarity": item.get("rarity"), "attunement": bool(item.get("reqAttune"))}
                          for slot, item in inventory]
    # Contents of a Bag of Holding and its kin weigh nothing (DMG p. 153); everything else counts.
    weight = sum((item.get("weight") or 0) * (slot.get("qty") or 1) for slot, item in inventory
                 if not (containers.get(slot.get("inside")) or {}).get("containerCapacity", {}).get("weightless"))
    sheet["currency"] = {c: int((char.get("currency") or {}).get(c, 0) or 0) for c in ("cp", "sp", "ep", "gp", "pp")}
    settings = char.get("description") or {}
    # DDB's coins in containers: a container slot's own purse; coins in a Bag of Holding weigh nothing
    sheet["container_coins"] = [{"uid": slot.get("uid"), "name": item["name"],
                                 "coins": {c: int((slot.get("coins") or {}).get(c, 0) or 0) for c in ("cp", "sp", "ep", "gp", "pp")},
                                 "weightless": bool((item.get("containerCapacity") or {}).get("weightless"))}
                                for slot, item in inventory if item.get("containerCapacity") and slot.get("coins")]
    if settings.get("coin_weight", True):  # coins count unless switched off, as on DDB (Dodo, 2026-10-22)
        weight += sum(sheet["currency"].values()) / 50  # PHB p. 143: fifty coins weigh a pound
        weight += sum(sum(box["coins"].values()) for box in sheet["container_coins"] if not box["weightless"]) / 50
    # PHB p. 176: Tiny halves, each size above Medium doubles; Powerful Build counts one size larger
    sizes = (race or {}).get("size") or ["M"]
    size = (char.get("race") or {}).get("size") if (char.get("race") or {}).get("size") in sizes else sizes[-1]
    powerful = "Powerful Build" in ((race or {}).get("traitTags") or []) \
        or any(e.get("name") == "Powerful Build" for e in (race or {}).get("entries", []) if isinstance(e, dict))
    size_step = {"T": -1, "S": 0, "M": 0, "L": 1, "H": 2, "G": 3}.get(size, 0) + (1 if powerful else 0)
    capacity = int(scores["str"] * 15 * (2 ** size_step if size_step >= 0 else 0.5))
    status = None
    mode = settings.get("encumbrance")
    if mode == "none":  # DDB's "No Encumbrance" preference: weight is still totalled, never penalised
        status = None
    elif mode == "variant":  # PHB p. 176
        status = "heavily encumbered" if weight > scores["str"] * 10 else "encumbered" if weight > scores["str"] * 5 else None
    elif weight > capacity:
        status = "over capacity"
    sheet["encumbrance"] = {"weight": round(weight, 2), "capacity": capacity, "push_drag_lift": capacity * 2, "status": status,
                            "variant": mode == "variant", "disabled": mode == "none"}

    equipped = [(slot, item) for slot, item in inventory if slot.get("equipped")]
    worn = next((item for _, item in equipped if ARMOR_TYPES.get(item.get("type")) in ("light", "medium", "heavy")), None)
    shield = next((item for _, item in equipped if item.get("type") == "S"), None)
    style_ids = [o for entry, cls, sub, level in class_rows for o in active_options(entry, cls, sub, level, data)]
    style_ids += [o for feat, choice in feats for o in _feat_options(feat, choice, data)]  # Fighting Initiate
    fighting_styles = {data.optionalfeatures[o]["name"] for o in style_ids if o in data.optionalfeatures
                       and any(t.startswith("FS") for t in data.optionalfeatures[o].get("featureType", []))}
    ac_options = []
    item_bonus = sum(int(str(item.get("bonusAc", 0)).replace("+", "") or 0) for slot, item in equipped
                     if item.get("bonusAc") and (not item.get("reqAttune") or slot.get("attuned"))
                     and item.get("type") not in ("LA", "MA", "HA", "S"))
    if worn:
        kind = ARMOR_TYPES[worn["type"]]
        armor_bonus = int(str(worn.get("bonusAc", 0)).replace("+", "") or 0)
        dex_part = mods["dex"] if kind == "light" else min(mods["dex"], 3 if "Medium Armor Master" in feat_names else 2) if kind == "medium" else 0
        parts = [("Armor", worn["ac"] + armor_bonus, worn["name"]), ("Dexterity Bonus", dex_part, None)]
        if "Defense" in fighting_styles:
            parts.append(("Fighting Style", 1, "Defense"))
        ac_options.append((sum(v for _, v, _ in parts), worn["name"], parts))
    else:
        ac_options.append((10 + mods["dex"], "Unarmored", [("Unarmored", 10, None), ("Dexterity Bonus", mods["dex"], None)]))
        names = {cls["name"] for _, cls, _, _ in class_rows}
        if "Barbarian" in names:
            ac_options.append((10 + mods["dex"] + mods["con"], "Unarmored Defense (Barbarian)",
                               [("Unarmored Defense", 10, "Barbarian"), ("Dexterity Bonus", mods["dex"], None), ("Constitution Bonus", mods["con"], None)]))
        if "Monk" in names and not shield:
            ac_options.append((10 + mods["dex"] + mods["wis"], "Unarmored Defense (Monk)",
                               [("Unarmored Defense", 10, "Monk"), ("Dexterity Bonus", mods["dex"], None), ("Wisdom Bonus", mods["wis"], None)]))
        if any(sub and sub["name"] == "Draconic Bloodline" for _, _, sub, _ in class_rows):
            ac_options.append((13 + mods["dex"], "Draconic Resilience", [("Draconic Resilience", 13, None), ("Dexterity Bonus", mods["dex"], None)]))
        natural = (race or {}).get("ac")
        if isinstance(natural, list):
            for nat in natural:
                if isinstance(nat, dict) and nat.get("ac"):
                    dex_part = mods["dex"] if "dex" in json.dumps(nat.get("from", "")) else 0
                    ac_options.append((nat["ac"] + dex_part, "Natural armor", [("Natural Armor", nat["ac"], None), ("Dexterity Bonus", dex_part, None)]))
    ac, how, parts = max(ac_options, key=lambda o: o[0])
    parts = list(parts)
    if shield:
        shield_ac = 2 + int(str(shield.get("bonusAc", 0)).replace("+", "") or 0)
        ac += shield_ac
        how += " + shield"
        parts.append(("Shield", shield_ac, shield["name"]))
    ac += item_bonus
    if item_bonus:
        parts.append(("Magic Bonus", item_bonus, None))
    # parts: (label, value, source) as DDB's Armor Class pane lists them; the first is the base
    sheet["armor_class"] = {"value": ac, "how": how, "parts": parts}

    attacks = []
    martial_arts = next((cls for _, cls, _, _ in class_rows if cls["name"] == "Monk"), None)
    monk_level = next((level for _, cls, _, level in class_rows if cls["name"] == "Monk"), 0)
    unarmed_die = _table_text(martial_arts, "Martial Arts", monk_level) if martial_arts else None

    def bigger_die(a: str, b: str | None) -> str:
        faces = lambda d: int(re.sub(r"^\d*d", "", d)) if d and re.fullmatch(r"\d*d\d+", d) else 0
        return b if b and faces(b) > faces(a) else a
    for slot, item in equipped:
        if item.get("type") not in ("M", "R"):
            continue
        props = set(item.get("property", []))
        ranged = item["type"] == "R"
        finesse = "F" in props
        # PHB p. 78: monk weapons (shortsword, simple melee without two-handed or heavy) use Dex and the Martial Arts die
        monk_weapon = bool(martial_arts) and not ranged and (item["name"].lower().endswith("shortsword") or (
            item.get("weaponCategory") == "simple" and not props & {"2H", "H"}))
        ability = "dex" if ranged or ((finesse or monk_weapon) and mods["dex"] > mods["str"]) else "str"
        name_lower = item["name"].lower()
        category = item.get("weaponCategory")
        proficient = (category in weapons) or (name_lower in weapons) or (name_lower + "s" in weapons)
        magic = int(str(item.get("bonusWeapon", 0)).replace("+", "") or 0)
        to_hit = mods[ability] + (prof if proficient else 0) + magic + (2 if ranged and "Archery" in fighting_styles else 0)
        dmg_bonus = mods[ability] + magic
        if not ranged and "Dueling" in fighting_styles and "2H" not in props:
            dmg_bonus += 2
        die = bigger_die(item.get("dmg1", "1"), unarmed_die) if monk_weapon else item.get("dmg1", "1")
        attacks.append({"name": item["name"], "item_id": item.get("id"), "to_hit": to_hit, "ability": ability,
                        "damage": f"{die}{'+' if dmg_bonus >= 0 else ''}{dmg_bonus}",
                        "versatile": f"{item['dmg2']}{'+' if dmg_bonus >= 0 else ''}{dmg_bonus}" if item.get("dmg2") else None,
                        "damage_type": item.get("dmgType"), "range": item.get("range"),
                        "properties": sorted(props), "proficient": proficient})
    # PHB p. 195: two light melee weapons give a bonus-action attack with the other one, without a positive
    # ability modifier to damage unless the Two-Weapon Fighting style; Dual Wielder drops the light requirement
    dual = "Dual Wielder" in feat_names
    melee = [a for a in attacks if (data.items.get(a["item_id"]) or {}).get("type") == "M"]
    if len(melee) >= 2 and all(dual or "L" in a["properties"] for a in melee[:2]):
        main, off = melee[0], melee[1]
        mod = mods[off["ability"]] + int(str((data.items.get(off["item_id"]) or {}).get("bonusWeapon", 0)).replace("+", "") or 0)
        bonus = mod if mod < 0 or "Two-Weapon Fighting" in fighting_styles else mod - mods[off["ability"]]
        die = off["damage"].split("+")[0].split("-")[0]
        attacks.append({**off, "name": f"{off['name']} (off-hand)", "offhand": True, "versatile": None,
                        "damage": f"{die}{'+' if bonus >= 0 else ''}{bonus}" if bonus else die})
    unarmed_ability = "dex" if martial_arts and mods["dex"] > mods["str"] else "str"
    unarmed_damage = (f"{unarmed_die}{'+' if mods[unarmed_ability] >= 0 else ''}{mods[unarmed_ability]}" if unarmed_die
                      else str(max(0, 1 + mods[unarmed_ability])))  # PHB p. 195: 1 + Strength modifier
    attacks.append({"name": "Unarmed Strike", "item_id": None, "to_hit": mods[unarmed_ability] + prof,
                    "ability": unarmed_ability,
                    "damage": unarmed_damage,
                    "versatile": None, "damage_type": "B", "range": None, "properties": [], "proficient": True})
    sheet["attacks"] = attacks

    # Speed.
    speed = race.get("speed", 30) if race else 30
    walk = speed.get("walk", 30) if isinstance(speed, dict) else speed
    others = {k: (walk if v is True else v) for k, v in speed.items() if k != "walk"} if isinstance(speed, dict) else {}
    heavy = worn and ARMOR_TYPES.get(worn["type"]) == "heavy"
    for _, cls, _, level in class_rows:
        if cls["name"] == "Barbarian" and level >= 5 and not heavy:
            walk += 10
        if cls["name"] == "Monk" and not worn and not shield:
            bonus = _table_column(cls, "Unarmored Movement", level)
            walk += int(re.sub(r"\D", "", str(bonus)) or 0)
    dwarf = bool(race and race.get("race") == "Dwarf")  # "Your speed is not reduced by wearing heavy armor."
    if heavy and not dwarf and worn.get("strength") and scores["str"] < int(worn["strength"]):
        walk -= 10
    if "Mobile" in feat_names:  # PHB p. 168
        walk += 10
    walk -= {"encumbered": 10, "heavily encumbered": 20}.get(sheet["encumbrance"]["status"], 0)
    sheet["speed"] = {"walk": walk, **{k: v for k, v in others.items() if isinstance(v, int)}}
    for slot, item in inventory:  # Winged Boots, Cloak of the Manta Ray, Boots of Striding and Springing...
        mod = item.get("modifySpeed")
        if mod and slot.get("equipped") and (not item.get("reqAttune") or slot.get("attuned")):
            for mode, value in (mod.get("static") or {}).items():
                sheet["speed"][mode] = max(sheet["speed"].get(mode, 0), int(value))
            for mode, source in (mod.get("equal") or {}).items():
                sheet["speed"][mode] = max(sheet["speed"].get(mode, 0), sheet["speed"].get(source, 0))
            # "multiply" (Boots of Speed) only while activated: left to the player
    for mode, value in (char.get("custom_speeds") or {}).items():
        if mode in ("fly", "swim", "climb", "burrow") and int(value or 0) > 0:
            sheet["speed"][mode] = max(sheet["speed"].get(mode, 0), int(value))
    darkvision = race.get("darkvision") if race else None
    for _, cls, sub, level in class_rows:
        name = (sub or {}).get("name")
        if name == "Shadow Magic":
            darkvision = max(darkvision or 0, 120)  # Eyes of the Dark
        elif name == "Gloom Stalker" and level >= 3:
            darkvision = (darkvision + 30) if darkvision else 60  # Umbral Sight
        elif name == "Twilight Domain":
            darkvision = max(darkvision or 0, 300)  # Eyes of Night
    sheet["senses"] = {"darkvision": darkvision} if darkvision else {}
    # senses, speeds and defenses added by hand in their panes (DDB's customize): the larger value wins
    for sense, value in (char.get("custom_senses") or {}).items():
        if sense in ("darkvision", "blindsight", "tremorsense", "truesight") and int(value or 0) > 0:
            sheet["senses"][sense] = max(sheet["senses"].get(sense, 0), int(value))

    resist = {r for r in (race or {}).get("resist", []) if isinstance(r, str)}
    if race and race.get("race") == "Dragonborn" and race_choice.get("ancestry") in DRAGONS:
        resist.add(DRAGONS[race_choice["ancestry"]])
    immune = {i for i in (race or {}).get("immune", []) if isinstance(i, str)}
    condition_immune = {c for c in (race or {}).get("conditionImmune", []) if isinstance(c, str)}
    vulnerable: set[str] = set()
    for slot, item in inventory:  # equipped items, attuned where they require it
        if slot.get("equipped") and (not item.get("reqAttune") or slot.get("attuned")):
            resist |= {r for r in item.get("resist", []) if isinstance(r, str)}
            immune |= {i for i in item.get("immune", []) if isinstance(i, str)}
            condition_immune |= {c for c in item.get("conditionImmune", []) if isinstance(c, str)}
            vulnerable |= {v for v in item.get("vulnerable", []) if isinstance(v, str)}
    for _, cls, sub, level in class_rows:  # always-on class and subclass defenses
        name, sub_name = cls["name"], (sub or {}).get("name")
        if (name == "Monk" and level >= 10) or (sub_name == "Circle of the Land" and level >= 10):
            immune.add("poison"); condition_immune.add("poisoned")  # Purity of Body, Nature's Ward
        if sub_name == "Storm Sorcery" and level >= 6:
            resist |= {"lightning", "thunder"}  # Heart of the Storm (XGE p. 52)
        if sub_name == "Oath of Devotion" and level >= 7:
            condition_immune.add("charmed")  # Aura of Devotion
        if sub_name == "Oath of the Ancients" and level >= 7:
            resist.add("damage from spells")  # Aura of Warding
    for custom in char.get("custom_defenses") or []:
        target = {"resist": resist, "immune": immune, "condition_immune": condition_immune, "vulnerable": vulnerable}.get(custom.get("type"))
        if target is not None and str(custom.get("name") or "").strip():
            target.add(str(custom["name"]).strip().lower())
    sheet["defenses"] = {"resist": sorted(resist), "immune": sorted(immune),
                         "condition_immune": sorted(condition_immune), "vulnerable": sorted(vulnerable)}
    sheet["race_ancestry"] = race_choice.get("ancestry") if race and race.get("race") == "Dragonborn" else None

    # Active effects and conditions: applied before overrides, listed so the sheet can say why a number moved.
    effects = [e for e in play.get("effects", []) if e in EFFECTS]
    conditions = set(play.get("conditions", []))
    exhaustion = int(play.get("exhaustion") or 0)
    notes = []
    class_names = {cls["name"]: level for _, cls, _, level in class_rows}
    subclass_names = {sub["name"] for _, _, sub, _ in class_rows if sub}
    if "Mage Armor" in effects and not worn:
        if 13 + mods["dex"] + (2 + int(str(shield.get("bonusAc", 0)).replace("+", "") or 0) if shield else 0) + item_bonus > sheet["armor_class"]["value"]:
            sheet["armor_class"] = {"value": 13 + mods["dex"] + (2 if shield else 0) + item_bonus, "how": "Mage Armor" + (" + shield" if shield else ""),
                                    "parts": [("Mage Armor", 13, None), ("Dexterity Bonus", mods["dex"], None)] + [x for x in sheet["armor_class"]["parts"] if x[0] in ("Shield", "Magic Bonus")]}
    if "Bladesong" in effects and "Bladesinging" in subclass_names and not heavy and not shield and (not worn or ARMOR_TYPES.get(worn["type"]) == "light"):
        sheet["armor_class"]["value"] += max(1, mods["int"])
        sheet["armor_class"]["how"] += ", Bladesong"
        sheet["armor_class"]["parts"].append(("Bladesong", max(1, mods["int"]), None))
        sheet["speed"]["walk"] += 10
    for name, bonus in (("Shield of Faith", 2), ("Haste", 2), ("Shield", 5)):
        if name in effects:
            sheet["armor_class"]["value"] += bonus
            sheet["armor_class"]["how"] += f", {name}"
            sheet["armor_class"]["parts"].append((name, bonus, None))
    if "Barkskin" in effects and sheet["armor_class"]["value"] < 16:
        sheet["armor_class"] = {"value": 16, "how": "Barkskin (minimum 16)", "parts": [("Barkskin", 16, "minimum 16")]}
    if "Haste" in effects:
        sheet["speed"] = {k: v * 2 for k, v in sheet["speed"].items()}
    if "Rage" in effects and "Barbarian" in class_names:
        rage_damage = int(re.sub(r"\D", "", str(_table_column(data.classes["barbarian"], "Rage Damage", class_names["Barbarian"]))) or 2)
        for attack in sheet["attacks"]:
            if attack["ability"] == "str" and "R" != (data.items.get(attack["item_id"] or "", {}).get("type")):
                attack["damage"] += f"+{rage_damage}"
                attack["rage"] = rage_damage
        totem = any((entry.get("feature_choices") or {}).get("Path of the Totem Warrior|Path of the Totem Warrior") == ["Bear"]
                    for entry, *_ in class_rows)
        sheet["defenses"]["resist"] = sorted(set(sheet["defenses"]["resist"]) | (
            {"acid", "cold", "fire", "force", "lightning", "necrotic", "poison", "radiant", "thunder", "bludgeoning", "piercing", "slashing"}
            if totem else {"bludgeoning", "piercing", "slashing"}))
        notes.append("Raging: advantage on Strength checks and saving throws; no spellcasting or concentration.")
    if "Bless" in effects:
        notes.append("Blessed: add 1d4 to attack rolls and saving throws.")
    if conditions & SPEED_ZERO or exhaustion >= 5:
        sheet["speed"] = {k: 0 for k in sheet["speed"]}
    elif exhaustion >= 2:
        sheet["speed"] = {k: v // 2 for k, v in sheet["speed"].items()}
    if exhaustion >= 4:
        sheet["hp"]["max"] //= 2
        sheet["hp"]["current"] = min(sheet["hp"]["current"], sheet["hp"]["max"])
    exhaustion_notes = {1: "disadvantage on ability checks", 3: "disadvantage on attack rolls and saving throws", 6: "death"}
    notes += [f"Exhaustion {lv}: {text}." for lv, text in exhaustion_notes.items() if exhaustion >= lv]
    for cond in sorted(conditions):
        if cond in ("blinded", "frightened", "poisoned", "prone", "restrained"):
            notes.append(f"{cond.title()}: see the condition for its disadvantages.")
        elif cond in ("paralyzed", "stunned", "unconscious", "petrified"):
            notes.append(f"{cond.title()}: incapacitated; fails Strength and Dexterity saves.")
    sheet["effects"] = {"active": effects, "available": _available_effects(class_names, subclass_names), "notes": notes}

    # Spellcasting.
    sheet["spellcasting"] = _spellcasting(char, data, class_rows, mods, prof, play, problems)
    for caster in sheet["spellcasting"]["casters"]:  # Rod of the Pact Keeper, Wand of the War Mage, Robe of the Archmagi
        caster["save_dc"] += _item_bonus(inventory, "bonusSpellSaveDc")
        caster["attack"] += _item_bonus(inventory, "bonusSpellAttack")
    total_level = sum(level for *_, level in class_rows)
    granted = []
    if race:
        granted += granted_spells(race["name"], race.get("additionalSpells"), race_choice, total_level, mods, prof, data)
    for feat, choice in feats:
        granted += granted_spells(feat["name"], feat.get("additionalSpells"), choice, total_level, mods, prof, data)
    sheet["spellcasting"]["granted"] = granted

    # DDB-style overrides: set or add, applied last, marked so the sheet can show an asterisk.
    applied = []

    def num(key):
        value = overrides.get(key)
        return int(value) if value not in (None, "") else None

    if num("ac") is not None:
        sheet["armor_class"] = {"value": num("ac"), "how": "set by hand", "overridden": True, "parts": [("Override AC", num("ac"), None)]}
        applied.append("AC")
    elif num("ac_bonus"):
        sheet["armor_class"]["value"] += num("ac_bonus")
        sheet["armor_class"]["how"] += f", {num('ac_bonus'):+d} by hand"
        sheet["armor_class"]["parts"].append(("Misc Bonus", num("ac_bonus"), None))
        sheet["armor_class"]["overridden"] = True
        applied.append("AC bonus")
    if num("speed") is not None:
        sheet["speed"]["walk"] = num("speed")
        sheet["speed"]["overridden"] = True
        applied.append("speed")
    if num("initiative_bonus"):
        sheet["initiative"] += num("initiative_bonus")
        sheet["initiative_overridden"] = True
        applied.append("initiative")
    for a, bonus in (overrides.get("save_bonus") or {}).items():
        if bonus and a in sheet["saving_throws"]:
            sheet["saving_throws"][a]["modifier"] += int(bonus)
            sheet["saving_throws"][a]["overridden"] = True
            applied.append(f"{a.upper()} save")
    for skill, bonus in (overrides.get("skill_bonus") or {}).items():
        if bonus and skill in sheet["skills"]:
            sheet["skills"][skill]["modifier"] += int(bonus)
            sheet["skills"][skill]["overridden"] = True
            applied.append(skill)
    for caster in sheet["spellcasting"]["casters"]:
        if num("spell_dc_bonus"):
            caster["save_dc"] += num("spell_dc_bonus")
        if num("spell_attack_bonus"):
            caster["attack"] += num("spell_attack_bonus")
    if num("spell_dc_bonus") or num("spell_attack_bonus"):
        applied.append("spellcasting")
    if overrides.get("hp_max") or overrides.get("hp_bonus"):
        sheet["hp"]["overridden"] = True
        applied.append("hit points")
    sheet["passives"] = {
        "perception": 10 + sheet["skills"]["perception"]["modifier"] + (5 if observant else 0),
        "investigation": 10 + sheet["skills"]["investigation"]["modifier"] + (5 if observant else 0),
        "insight": 10 + sheet["skills"]["insight"]["modifier"],
    }
    play_state = char.get("play") or {}
    # PHB p. 175: disadvantage on the check makes a passive score 5 lower; poisoned and exhaustion 1+ give it on all checks
    if "poisoned" in (play_state.get("conditions") or []) or int(play_state.get("exhaustion") or 0) >= 1:
        sheet["passives"] = {k: v - 5 for k, v in sheet["passives"].items()}
        sheet["passives_disadvantage"] = True
    sheet["overrides_applied"] = applied

    # Features, with the picks they ask for.
    features = []
    picks_out = []

    def with_pick(entry, origin, f, level, cls_name):
        rule = FEATURE_PICKS.get((origin, f["name"]))
        item = {"origin": origin, "name": f["name"], "level": f["level"], "book": f["book"], "page": f.get("page"),
                "entries": f["entries"], "kind": "class", "class": cls_name}
        if not rule:
            return item
        counts, options = rule
        count = max([n for lv, n in counts.items() if lv <= level] or [0])
        names = _option_names(f["entries"]) if options == "options" else options
        if not count or not names:
            return item
        key = f"{origin}|{f['name']}"
        chosen = [c for c in (entry.get("feature_choices") or {}).get(key, []) if c in names][:count]
        picks_out.append({"key": key, "class": entry.get("id"), "origin": origin, "feature": f["name"],
                          "count": count, "options": names, "chosen": chosen})
        item["chosen"] = chosen
        if options == "options" and chosen:
            item["entries"] = _keep_chosen(f["entries"], chosen)
        return item

    for entry, cls, sub, level in class_rows:
        for f in cls["features"]:
            if f["level"] <= level and (not f.get("variant") or f["name"] in entry.get("variant_features", [])):
                features.append(with_pick(entry, cls["name"], f, level, cls["name"]))
        if sub:
            for f in sub["features"]:
                if f["level"] <= level:
                    features.append(with_pick(entry, sub["name"], f, level, cls["name"]))
        for oid in active_options(entry, cls, sub, level, data):
            opt = data.optionalfeatures.get(oid)
            if opt:
                features.append({"origin": cls["name"], "name": opt["name"], "level": None, "book": opt["book"], "page": opt.get("page"),
                                 "entries": opt.get("entries", []), "optionalfeature": oid, "kind": "class", "class": cls["name"]})
    sheet["feature_picks"] = picks_out
    # PHB p. 164: Extra Attack from two classes does not add up; only the fighter's (2) and (3) raise it.
    extra = [int(m.group(1) or 1) for f in features if (m := re.match(r"^Extra Attack(?: \((\d)\))?$", f["name"]))]
    sheet["attacks_per_action"] = 1 + max(extra, default=0)
    if race:
        for e in race.get("entries", []):
            if isinstance(e, dict) and e.get("name"):
                features.append({"origin": race["name"], "name": e["name"], "level": None, "book": race["book"], "page": race.get("page"),
                                 "entries": e.get("entries", []), "kind": "race"})
    # PHB p. 125: a customized background may take its feature from any other background
    feature_source = data.backgrounds.get(((char.get("background") or {}).get("custom") or {}).get("feature_from")) or background
    if feature_source:
        for e in feature_source.get("entries", []):
            for sub_e in ([e] + (e.get("entries", []) if isinstance(e, dict) else [])):
                if isinstance(sub_e, dict) and str(sub_e.get("name", "")).startswith("Feature:"):
                    features.append({"origin": feature_source["name"], "name": sub_e["name"][9:].strip(), "level": None,
                                     "book": feature_source["book"], "page": feature_source.get("page"), "entries": sub_e.get("entries", []), "kind": "background"})
    for feat, choice in feats:
        # Elemental Adept (PHB p. 166): the damage type chosen shows in the name
        shown = f"{feat['name']} ({choice['damage_type'].title()})" if choice.get("damage_type") else feat["name"]
        features.append({"origin": "Feat", "name": shown, "level": None, "book": feat["book"], "page": feat.get("page"),
                         "entries": feat.get("entries", []), "feat": feat["id"], "kind": "feat"})
        for oid in _feat_options(feat, choice, data):
            opt = data.optionalfeatures[oid]
            features.append({"origin": feat["name"], "name": opt["name"], "level": None, "book": opt["book"], "page": opt.get("page"),
                             "entries": opt.get("entries", []), "optionalfeature": oid, "kind": "feat"})
    sheet["features"] = features
    sheet["save_notes"] = save_notes(features)

    # Limited-use counters.
    sheet["counters"] = _counters(class_rows, mods, prof, play)
    sheet["class_values"] = class_values(class_rows)
    # magic item charges (DMG p. 141): one counter per carried item; dawn recharges are a dice roll the player makes
    seen: dict[str, int] = {}
    for slot, item in inventory:
        if isinstance(item.get("charges"), int) and item["charges"] > 0:
            seen[item["name"]] = seen.get(item["name"], 0) + 1
            name = item["name"] + (f" #{seen[item['name']]}" if seen[item["name"]] > 1 else "")
            regain = plain(str(item.get("rechargeAmount") or "")).strip()
            sheet["counters"].append({"name": name, "max": item["charges"], "reset": item.get("recharge") or "none",
                                      "regain": regain or None, "origin": "Item", "item": item.get("id"),
                                      "used": int((play.get("counters_used") or {}).get(name, 0)), "activation": "other"})
    druid = next(((level, sub) for _, cls, sub, level in class_rows if cls["name"] == "Druid" and level >= 2), None)
    if druid:  # PHB p. 66 Beast Shapes table; Circle of the Moon, PHB p. 69
        level, sub = druid
        max_cr = 1 if level >= 8 else 0.5 if level >= 4 else 0.25
        if (sub or {}).get("name") == "Circle of the Moon":
            max_cr = max(1, level // 3)
        sheet["wild_shape"] = {"max_cr": max_cr, "swim": level >= 4, "fly": level >= 8}
    for spell in sheet["spellcasting"]["granted"]:  # "1/long rest" race and feat spells: tracked like other uses
        m = re.fullmatch(r"(\d+)/(long|short) rest", spell.get("usage") or "")
        if m:
            spell["counter"] = f"{spell['name']} ({spell['source']})"
            sheet["counters"].append({"name": spell["counter"], "max": int(m.group(1)), "reset": m.group(2), "origin": spell["source"],
                                      "used": int((play.get("counters_used") or {}).get(spell["counter"], 0)), "activation": "other", "spell": spell["id"]})
    for caster in sheet["spellcasting"]["casters"]:
        for card in caster["list"]:
            if card.get("arcanum"):
                card["counter"] = f"Mystic Arcanum ({card['level']}th level)"
            if card.get("signature"):
                card["counter"] = f"Signature Spell: {card['name']}"
                sheet["counters"].append({"name": card["counter"], "max": 1, "reset": "short", "origin": "Wizard",
                                          "used": int((play.get("counters_used") or {}).get(card["counter"], 0)), "activation": "other"})
    used = play.get("counters_used") or {}
    traits = [(race["name"], e) for e in (race or {}).get("entries", []) if isinstance(e, dict) and e.get("name")]
    traits += [("Feat", {"name": f["name"], "entries": f.get("entries", [])}) for f, _ in feats]
    for origin, entry in traits:
        uses = trait_uses(entry, prof, total_level)
        if uses and not any(c["name"] == entry["name"] for c in sheet["counters"]):
            sheet["counters"].append({"name": entry["name"], "max": uses[0], "reset": uses[1], "origin": origin,
                                      "used": int(used.get(entry["name"], 0)), "activation": "other"})
    sheet["play"] = {"conditions": play.get("conditions", []), "exhaustion": play.get("exhaustion", 0),
                     "inspiration": bool(play.get("inspiration")),
                     "death_saves": play.get("death_saves", {"success": 0, "failure": 0})}
    sheet["choices_open"] = open_choices(char, data, class_rows, race, background, skills, sheet.get("background_overlap"))
    for pick in sheet["feature_picks"]:
        if len(pick["chosen"]) < pick["count"]:
            sheet["choices_open"].append({"step": "class", "class": pick["class"],
                                          "what": f"{pick['origin']}, {pick['feature']}: choose {pick['count'] - len(pick['chosen'])}."})
    if race and race.get("race") == "Dragonborn" and race_choice.get("ancestry") not in DRAGONS:
        sheet["choices_open"].append({"step": "race", "what": "Dragonborn: choose a draconic ancestry."})
    if (char.get("abilities") or {}).get("method") == "standard" and any(raw.get(a) in (None, "") for a in ABILITIES):
        sheet["choices_open"].append({"step": "abilities", "what": "Standard array: assign all six scores."})
    for caster in sheet["spellcasting"]["casters"]:
        if len(caster["cantrips"]) < caster["cantrips_known"]:
            sheet["choices_open"].append({"step": "spells", "class": caster["class_id"],
                                          "what": f"{caster['class']}: choose {caster['cantrips_known'] - len(caster['cantrips'])} more cantrips."})
        if caster["spells_known"] is not None and len(caster["known"]) < caster["spells_known"]:
            sheet["choices_open"].append({"step": "spells", "class": caster["class_id"],
                                          "what": f"{caster['class']}: choose {caster['spells_known'] - len(caster['known'])} more spells known."})
    return sheet


def _available_effects(class_names: dict, subclass_names: set) -> list[dict]:
    names = [n for n in EFFECTS if n not in ("Rage", "Bladesong")]
    if "Barbarian" in class_names:
        names.insert(0, "Rage")
    if "Bladesinging" in subclass_names:
        names.insert(0, "Bladesong")
    return [{"name": n, "text": EFFECTS[n]} for n in names]


def _eval_prepared(formula: str, level: int, mods: dict) -> int:
    expr = formula.replace("<$level$>", str(level))
    for a in ABILITIES:
        expr = expr.replace(f"<${a}_mod$>", str(mods[a]))
    if not re.fullmatch(r"[\d\s+\-*/()]+", expr):
        return 0
    return max(1, math.floor(eval(expr)))  # the expression is digits and operators only


def _origin_expanded(char: dict, data: Data) -> list[str]:
    """Spells a race or background adds to the character's class spell lists (5etools additionalSpells
    "expanded", keys "s<spell level>"): the Eberron dragonmarks (ERLW), the Ravnica guilds (GGR) and the
    Strixhaven colleges (SCC)."""
    out = []
    sources = [data.races.get((char.get("race") or {}).get("id")), data.backgrounds.get((char.get("background") or {}).get("id"))]
    for source in filter(None, sources):
        for block in source.get("additionalSpells") or []:
            for names in (block.get("expanded") or {}).values():
                for name in names if isinstance(names, list) else []:
                    if not isinstance(name, str):
                        continue
                    key = name.split("#")[0].lower()
                    spell = data.spell_by_name.get(key) or data.spell_by_name.get(key.split("|")[0])
                    if spell and spell["id"] not in out:
                        out.append(spell["id"])
    return out


def _spellcasting(char, data, class_rows, mods, prof, play, problems) -> dict:
    casters = []
    origin_expanded = _origin_expanded(char, data)
    caster_level = 0.0
    single = len([r for r in class_rows if (r[1].get("casterProgression") or (r[2] or {}).get("casterProgression"))
                  and (r[1].get("casterProgression") or (r[2] or {}).get("casterProgression")) != "pact"]) == 1
    slots: list[int] = []
    pact = None
    for entry, cls, sub, level in class_rows:
        source = cls if cls.get("casterProgression") else sub if sub and sub.get("casterProgression") else None
        if source is None:
            continue
        progression = source["casterProgression"]
        ability = source.get("spellcastingAbility") or cls.get("spellcastingAbility")
        info: dict[str, Any] = {
            "class": cls["name"], "class_id": cls["id"], "ability": ability,
            "save_dc": 8 + prof + mods[ability], "attack": prof + mods[ability], "progression": progression,
        }
        cantrips = source.get("cantripProgression")
        info["cantrips_known"] = cantrips[level - 1] if cantrips else 0
        known = source.get("spellsKnownProgression")
        info["spells_known"] = known[level - 1] if known else None
        info["prepared_max"] = _eval_prepared(cls["preparedSpells"], level, mods) if cls.get("preparedSpells") else None
        picks = entry.get("spells") or {}
        info["cantrips"] = [_spell_card(data, s) for s in picks.get("cantrips", []) if s in data.spells]
        info["known"] = [_spell_card(data, s) for s in picks.get("known", []) if s in data.spells]
        info["prepared"] = [s for s in picks.get("prepared", []) if s in data.spells]
        info["always_prepared"] = [_spell_card(data, s["id"]) for s in _granted_spells(data, sub, level, "prepared")]
        always = {s["id"] for s in info["always_prepared"]}
        info["prepared"] = [s for s in info["prepared"] if s not in always]  # domain/oath spells never count
        info["expanded"] = [s["id"] for s in _granted_spells(data, sub, level, "expanded")] + origin_expanded
        # PHB p. 54-55: Magical Secrets (any class's list, counted in Spells Known); Lore's two extra do not count
        info["secrets_max"] = sum(2 for at in (10, 14, 18) if cls["name"] == "Bard" and level >= at)
        info["secrets_extra"] = 2 if sub and sub["name"] == "College of Lore" and level >= 6 else 0
        info["secrets"] = [_spell_card(data, s) for s in picks.get("secrets", []) if s in data.spells]
        # PHB p. 108: Mystic Arcanum, one warlock spell each of 6th to 9th level, cast once per long rest
        info["arcanum_levels"] = [lv for lv, at in ARCANUM_AT.items() if cls["name"] == "Warlock" and level >= at]
        arcanum = picks.get("arcanum") or {}
        info["arcanum"] = [_spell_card(data, arcanum[str(lv)]) for lv in info["arcanum_levels"] if arcanum.get(str(lv)) in data.spells]
        # PHB p. 115: Spell Mastery (wizard 18: a 1st- and a 2nd-level spell at will) and Signature Spells
        # (wizard 20: two 3rd-level spells always prepared, each once per short rest without a slot)
        wizard = cls["name"] == "Wizard"
        info["mastery_levels"] = [1, 2] if wizard and level >= 18 else []
        mastery = picks.get("mastery") or {}
        info["mastery"] = [_spell_card(data, mastery[str(lv)]) for lv in info["mastery_levels"] if mastery.get(str(lv)) in data.spells]
        info["signature_max"] = 2 if wizard and level >= 20 else 0
        info["signature"] = [_spell_card(data, x) for x in (picks.get("signature") or [])[:info["signature_max"]] if x in data.spells]
        # One list for the sheet: every spell this class can cast today, flagged by why.
        known_ids = [c["id"] for c in info["known"]]
        listed: dict[str, dict] = {}
        for card in info["cantrips"]:
            listed[card["id"]] = {**card, "prepared": True, "always": False}
        for card in info["always_prepared"]:
            listed[card["id"]] = {**card, "prepared": True, "always": True}
        for card in info["secrets"]:
            listed[card["id"]] = {**card, "prepared": True, "always": False, "note": "Magical Secrets"}
        for card in info["arcanum"]:
            listed[card["id"]] = {**card, "prepared": True, "always": False, "note": "Mystic Arcanum", "usage": "1/long rest", "arcanum": True}
        for card in info["mastery"]:
            listed[card["id"]] = {**card, "prepared": True, "always": True, "note": "Spell Mastery", "usage": "at will"}
        for card in info["signature"]:
            listed[card["id"]] = {**card, "prepared": True, "always": True, "note": "Signature Spell", "signature": True}
        prepares = info["prepared_max"] is not None
        for sid in dict.fromkeys(known_ids + info["prepared"]):
            if sid in listed:
                continue
            listed[sid] = {**_spell_card(data, sid), "always": False,
                           "prepared": (sid in info["prepared"]) if prepares else True}
            # PHB p. 114: a wizard casts any ritual in the spellbook as a ritual without preparing it
            if cls["name"] == "Wizard" and not listed[sid]["prepared"] and data.spells[sid].get("meta", {}).get("ritual"):
                listed[sid]["ritual_only"] = True
        info["list"] = sorted(listed.values(), key=lambda c: (c["level"], c["name"]))
        if progression == "pact":
            count = _table_column(cls, "Spell Slots", level)
            slot_level = _table_column(cls, "Slot Level", level)
            pact = {"count": int(count or 0), "level": int(re.sub(r"\D", "", plain(str(slot_level))) or 1),
                    "used": int(play.get("pact_used", 0))}
            info["max_spell_level"] = pact["level"]
        else:
            if single:
                slots = _slot_row(source, level, "classTableGroups" if source is cls else "subclassTableGroups")
            caster_level += {"full": level, "1/2": level // 2, "1/3": level // 3,
                             "artificer": math.ceil(level / 2)}.get(progression, 0)
        if info["cantrips_known"] and len(info["cantrips"]) > info["cantrips_known"]:
            problems.append(f"{cls['name']}: {len(info['cantrips'])} cantrips chosen, {info['cantrips_known']} allowed.")
        # PHB p. 75, 98: Eldritch Knight (abjuration, evocation) and Arcane Trickster (enchantment, illusion);
        # the spells learned at levels 3, 8, 14 and 20 may come from any school
        schools = {"Eldritch Knight": ["A", "V"], "Arcane Trickster": ["E", "I"]}.get((sub or {}).get("name"))
        if schools:
            free = sum(1 for at in (3, 8, 14, 20) if level >= at)
            outside = sum(1 for c in info["known"] if c.get("school") not in schools)
            info["school_limit"] = {"schools": schools, "free": free, "outside": outside}
            if outside > free:
                problems.append(f"{sub['name']}: {outside} spells from other schools, {free} allowed.")
        counted = len(info["known"]) + max(0, len(info["secrets"]) - info["secrets_extra"])
        if info["spells_known"] is not None and counted > info["spells_known"]:
            problems.append(f"{cls['name']}: {counted} spells known, {info['spells_known']} allowed.")
        if len(info["secrets"]) > info["secrets_max"] + info["secrets_extra"]:
            problems.append(f"{cls['name']}: {len(info['secrets'])} Magical Secrets, {info['secrets_max'] + info['secrets_extra']} allowed.")
        if info["prepared_max"] is not None and len(info["prepared"]) > info["prepared_max"]:
            problems.append(f"{cls['name']}: {len(info['prepared'])} spells prepared, {info['prepared_max']} allowed.")
        casters.append(info)
    if not single and caster_level:
        slots = MULTICLASS_SLOTS[min(20, int(caster_level))]
    used = play.get("slots_used") or {}
    for info in casters:
        if info["progression"] != "pact":
            info["max_spell_level"] = len(slots)
    return {"casters": casters,
            "slots": [{"level": i + 1, "max": n, "used": int(used.get(str(i + 1), 0))} for i, n in enumerate(slots) if n],
            "pact": pact}


# additionalSpells frequency keys -> what the sheet shows
_USAGE = {"daily": "{n}/long rest", "rest": "{n}/short rest", "will": "at will", "ritual": "ritual only"}


def spell_slots_of(block: dict):
    """Every spell entry of an additionalSpells block, in a fixed order, with the key a player's picks
    are stored under: (kind, character level or 0, usage, entry, key). The builder walks the same order."""
    for kind in ("innate", "known"):
        for level_key, body in (block.get(kind) or {}).items():
            level = 0 if level_key == "_" else int(re.sub(r"\D", "", level_key) or 0)
            groups = [("_", body)] if isinstance(body, list) else body.items()
            for freq, value in groups:
                if isinstance(value, dict):  # daily / rest: {"1": [...], "1e": [...]}
                    parts = [(_USAGE.get(freq, "{n}").format(n=re.sub(r"\D", "", n) or n), v) for n, v in value.items()]
                else:
                    parts = [(_USAGE.get(freq) or ("known" if kind == "known" else "at will"), value)]
                for usage, entries in parts:
                    for i, entry in enumerate(entries if isinstance(entries, list) else [entries]):
                        yield kind, level, usage, entry, f"{kind}|{level_key}|{freq}|{usage}|{i}"


def granted_spells(source: str, blocks: list | None, choice: dict, char_level: int, mods: dict, prof: int, data: Data) -> list[dict]:
    """Spells a race or feat grants (5etools additionalSpells): fixed ones plus the player's picks
    (choice["spell_picks"][key]), with the casting ability, DC, attack and how often they can be cast.
    Several blocks (Magic Initiate's class lists) are alternatives: choice["spell_block"] picks one."""
    if not blocks:
        return []
    block = blocks[min(int(choice.get("spell_block") or 0), len(blocks) - 1)]
    ability = block.get("ability")
    if isinstance(ability, dict):
        options = ability.get("choose") or []
        ability = choice.get("spell_ability") if choice.get("spell_ability") in options else (options[0] if options else None)
    elif ability == "inherit":  # Fey Touched, Shadow Touched: the ability the feat increased
        ability = (choice.get("ability_choices") or [None])[0]
    out = []
    picks = choice.get("spell_picks") or {}
    for kind, level, usage, entry, key in spell_slots_of(block):
        if level > char_level:
            continue
        if isinstance(entry, dict) and "choose" in entry:
            count = (entry["choose"].get("count") if isinstance(entry["choose"], dict) else None) or entry.get("count") or 1
            names = [data.spells[sid]["name"] for sid in picks.get(key, [])[:count] if sid in data.spells]
        else:
            names = [str(entry)]
        for name in names:
            spell = data.spell_by_name.get(name.split("#")[0].lower())
            if not spell:
                continue
            mod = mods.get(ability, 0) if ability else 0
            out.append({**_spell_card(data, spell["id"]), "source": source, "ability": ability,
                        "usage": "cantrip" if spell["level"] == 0 else usage,
                        "save_dc": 8 + prof + mod, "attack_bonus": prof + mod})
    return out


def _spell_card(data: Data, spell_id: str) -> dict:
    s = data.spells[spell_id]
    duration = s.get("duration", [{}])[0]
    scaling = next((e.get("scaling") for e in s.get("scalingLevelDice", []) or [] if isinstance(e, dict)), None) \
        if isinstance(s.get("scalingLevelDice"), list) else (s.get("scalingLevelDice") or {}).get("scaling")
    return {"id": s["id"], "name": s["name"], "level": s["level"], "school": s.get("school"),
            "attack": bool(s.get("spellAttack")), "save": (s.get("savingThrow") or [None])[0],
            "damage_types": s.get("damageInflict", []), "scaling": scaling,
            "dice": next(iter(re.findall(r"\{@damage (\d+d\d+)", json.dumps(s.get("entries", [])))), None),
            # {@scaledamage 8d6|3-9|1d6}: base dice and what each slot level above the spell's own adds
            "scaledamage": next(iter(re.findall(r"\{@scaledamage (\d+d\d+)\|[^|]*\|(\d+d\d+)", json.dumps(s.get("entriesHigherLevel", [])))), None),
            "conditions": s.get("conditionInflict", []),
            "ritual": bool((s.get("meta") or {}).get("ritual")), "concentration": bool(duration.get("concentration")),
            "time": s.get("time"), "range": s.get("range"), "components": s.get("components"),
            "duration": s.get("duration"), "book": s["book"],
            # cast with a higher slot it does more (PHB "At Higher Levels"): DDB's level-scaled spells
            "upcast": bool(s.get("entriesHigherLevel")) and s["level"] > 0}


def _granted_spells(data: Data, sub: dict | None, level: int, kind: str) -> list[dict]:
    """Subclass `additionalSpells`: "prepared" keys are class levels, "expanded" keys are "s<spell level>"."""
    out = []
    for block in (sub or {}).get("additionalSpells", []) or []:
        for key, spells in (block.get(kind) or {}).items():
            gate = int(key) if key.isdigit() else None
            if gate is not None and gate > level:
                continue
            for ref in spells:
                if isinstance(ref, str):
                    spell = _spell_ref(data, ref)
                    if spell:
                        out.append(spell)
    return out


#: How each limited-use resource is activated (2014 text), for the sheet's action filters.
COUNTER_ACTIVATION = {
    "Rage": "bonus", "Bardic Inspiration": "bonus", "Second Wind": "bonus", "Channel Divinity": "action",
    "Wild Shape": "action", "Action Surge": "special", "Indomitable": "special", "Ki Points": "other",
    "Divine Sense": "action", "Lay on Hands": "action", "Sorcery Points": "other", "Arcane Recovery": "other",
    "Flash of Genius": "reaction", "Superiority Dice": "other",
}


def save_notes(features: list[dict]) -> list[dict]:
    """DDB's Saving Throw Modifiers box: each "advantage on ... saving throws ..." clause in the character's
    race traits, class features and feats (Dwarven Resilience, Gnome Cunning, Danger Sense, Fey Ancestry...)."""
    out, seen = [], set()
    for f in features:
        text = plain(" ".join(e for e in _strings(f.get("entries", []))))
        for sentence in re.split(r"(?<=\.)\s+", text):
            m = re.search(r"advantage on ((?:[^.]*?)saving throws?[^.]*)", sentence, re.I)
            if not m:
                continue
            clause = re.split(r",? and (?:magic|you|it|your)\b|; ", m.group(1))[0].strip().rstrip(".")
            when = re.match(r"(While [^,]+),", sentence)
            if when:
                clause = f"{clause} ({when.group(1).lower()})"
            if clause.lower() not in seen:
                seen.add(clause.lower())
                out.append({"source": f["name"], "text": clause})
    return out


def _strings(entries) -> list[str]:
    out = []
    for e in entries or []:
        if isinstance(e, str):
            out.append(e)
        elif isinstance(e, dict):
            out += _strings(e.get("entries") or e.get("items") or [])
    return out


def trait_uses(entry: dict, prof: int, total_level: int) -> tuple[int, str] | None:
    """Uses of a race trait or feat, read from its own wording: (max, "short"|"long"), or None.
    Traits that cast a spell are left out: their spells carry the use (granted_spells)."""
    text = json.dumps(entry.get("entries", []))
    if "{@spell" in text:
        return None
    reach = re.search(r"[Ww]hen you reach (\d+)(?:st|nd|rd|th) level", text)
    if reach and total_level < int(reach.group(1)):
        return None
    reset = "short" if re.search(r"(?:finish|complete) a short or long rest", text) else "long"
    if re.search(r"number of times equal to your proficiency bonus", text, re.I):
        return prof, reset
    luck = re.search(r"you have (\d+) luck points", text, re.I)
    if luck:
        return int(luck.group(1)), "long"
    if re.search(r"can't (?:use|do) (?:it|this|so|that|this (?:trait|feature|ability)) again until you (?:finish|complete) a (?:short or )?long rest", text):
        return 1, reset
    return None


def _infused(item: dict, infusion: str, artificer_level: int) -> dict:
    """An item carrying an artificer infusion (TCE p. 20-23): the numeric ones change the item, the rest are text."""
    bonus = f"+{2 if artificer_level >= 10 else 1}"
    item = {**item, "name": f"{item['name']} ({infusion})"}
    if infusion == "Enhanced Weapon" and item.get("type") in ("M", "R"):
        item["bonusWeapon"] = bonus
    elif infusion == "Enhanced Defense" and item.get("type") in ("LA", "MA", "HA", "S"):
        item["bonusAc"] = bonus
    return item


def _item_bonus(inventory, key: str) -> int:
    """Sum of an item bonus (5etools `bonusSavingThrow`, `bonusSpellAttack`...) over equipped items, attuned where required."""
    return sum(int(str(item.get(key)).replace("+", "") or 0) for slot, item in inventory
               if item.get(key) and slot.get("equipped") and (not item.get("reqAttune") or slot.get("attuned")))


def _counters(class_rows, mods, prof, play) -> list[dict]:
    used = play.get("counters_used") or {}
    out = []

    def add(name, maximum, reset, origin):
        # PHB p. 164: Channel Divinity from a second class adds its options, not uses
        twin = next((c for c in out if c["name"] == name), None)
        if twin and maximum:
            twin["max"] = max(twin["max"], maximum)
            twin["origin"] += f", {origin}"
        elif maximum:
            out.append({"name": name, "max": maximum, "reset": reset, "origin": origin, "used": int(used.get(name, 0)),
                        "activation": COUNTER_ACTIVATION.get(name, "other")})

    for _, cls, sub, level in class_rows:
        name = cls["name"]
        if name == "Barbarian":
            rages = _table_column(cls, "Rages", level)
            add("Rage", 99 if str(rages).lower() == "unlimited" else int(rages or 0), "long", name)
        elif name == "Bard":
            add("Bardic Inspiration", max(1, mods["cha"]), "short" if level >= 5 else "long", name)
        elif name == "Cleric" and level >= 2:
            add("Channel Divinity", 3 if level >= 18 else 2 if level >= 6 else 1, "short", name)
        elif name == "Druid" and level >= 2:
            add("Wild Shape", 2, "short", name)
        elif name == "Fighter":
            add("Second Wind", 1, "short", name)
            if level >= 2:
                add("Action Surge", 2 if level >= 17 else 1, "short", name)
            if level >= 9:
                add("Indomitable", 3 if level >= 17 else 2 if level >= 13 else 1, "long", name)
        elif name == "Monk" and level >= 2:
            add("Ki Points", int(_table_column(cls, "Ki Points", level) or 0), "short", name)
        elif name == "Paladin":
            add("Divine Sense", 1 + mods["cha"], "long", name)
            add("Lay on Hands", 5 * level, "long", name)
            if level >= 3:
                add("Channel Divinity", 1, "short", name)
        elif name == "Sorcerer" and level >= 2:
            add("Sorcery Points", int(_table_column(cls, "Sorcery Points", level) or 0), "long", name)
        elif name == "Wizard":
            add("Arcane Recovery", 1, "long", name)
        if name == "Warlock":
            for spell_level, at in ARCANUM_AT.items():
                if level >= at:
                    add(f"Mystic Arcanum ({spell_level}th level)", 1, "long", name)
        elif name == "Artificer" and level >= 7:
            add("Flash of Genius", max(1, mods["int"]), "long", name)
        if sub and sub["name"] == "Battle Master" and level >= 3:
            add("Superiority Dice", 6 if level >= 15 else 5 if level >= 7 else 4, "short", sub["name"])
    return out


def open_choices(char, data, class_rows, race, background, skills, sheet_overlap=None) -> list[dict]:
    """What the builder still has to ask for: one entry per unanswered pick."""
    todo = []
    if not char.get("race", {}).get("id"):
        todo.append({"step": "race", "what": "Choose a race."})
    if not class_rows:
        todo.append({"step": "class", "what": "Choose a class."})
    if not char.get("background", {}).get("id") and not char.get("background", {}).get("custom"):
        todo.append({"step": "background", "what": "Choose a background."})
    overlap = len(sheet_overlap or [])
    if overlap > len((char.get("background") or {}).get("replacement_skills", [])):
        todo.append({"step": "background", "what": f"Background: {overlap} skill(s) you already have; pick replacement(s) (PHB p. 125)."})
    if race and race["name"] == "Custom Lineage" and not (char.get("race") or {}).get("variable_trait"):
        todo.append({"step": "race", "what": "Custom Lineage: choose darkvision or a skill (Variable Trait)."})
    sources = [("race", race, char.get("race") or {})]
    if not (char.get("background") or {}).get("custom"):
        sources.append(("background", background, char.get("background") or {}))
    for label, source, picks in sources:
        for key, field in (("skillProficiencies", "skills"), ("languageProficiencies", "languages"), ("toolProficiencies", "tools")):
            block = ((source or {}).get(key) or [{}])[0]
            need = sum(v.get("count", 1) if k == "choose" else v for k, v in block.items()
                       if k == "choose" or (k.startswith("any") and isinstance(v, int)))
            if need and len(picks.get(field, [])) < need:
                todo.append({"step": label, "what": f"{source['name']}: choose {need - len(picks.get(field, []))} {field}."})
    for i, (entry, cls, sub, level) in enumerate(class_rows):
        allowed = sum(n for lv, n in EXPERTISE.get(cls["name"], {}).items() if lv <= level)
        if allowed and len(entry.get("expertise", [])) < allowed:
            todo.append({"step": "class", "class": cls["id"], "what": f"{cls['name']}: choose {allowed - len(entry.get('expertise', []))} skills for expertise."})
        sub_level = next((f["level"] for f in cls["features"] if f.get("gainSubclassFeature")), None)
        if sub_level and level >= sub_level and not sub:
            subclass_title = cls.get("subclassTitle", "subclass")
            article = "an" if subclass_title[0].lower() in "aeiou" else "a"
            todo.append({"step": "class", "class": cls["id"], "what": f"{cls['name']}: choose {article} {subclass_title}."})
        profs = cls.get("startingProficiencies", {}) if i == 0 else (cls.get("multiclassing") or {}).get("proficienciesGained", {})
        block = (profs.get("skills") or [{}])[0]
        need = block.get("choose", {}).get("count", 0) + block.get("any", 0)
        if need and len(entry.get("skills", [])) < need:
            todo.append({"step": "class", "class": cls["id"], "what": f"{cls['name']}: choose {need} skills."})
        for lv in (entry.get("asi_levels") or [f["level"] for f in cls["features"] if f["name"] == "Ability Score Improvement"]):
            if lv <= level and str(lv) not in (entry.get("asi") or {}):
                todo.append({"step": "class", "class": cls["id"], "what": f"{cls['name']} level {lv}: ability score improvement or feat."})
        for prog in (cls.get("optionalfeatureProgression") or []) + ((sub or {}).get("optionalfeatureProgression") or []):
            allowed = _progression_allowed(prog, level)
            have = sum(1 for o in entry.get("optionalfeatures", []) if o in data.optionalfeatures
                       and set(data.optionalfeatures[o].get("featureType", [])) & set(prog["featureType"]))
            if have < allowed:
                todo.append({"step": "class", "class": cls["id"], "what": f"{cls['name']}: choose {allowed - have} more {prog['name']}."})
    return todo
