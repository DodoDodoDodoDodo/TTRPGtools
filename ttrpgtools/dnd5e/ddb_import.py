"""D&D Beyond character JSON to our decision log (see character.py).

DDB stores every choice as a typed modifier; we read those back into picks.
What cannot be matched to the 2014 builder data (homebrew feats, custom items)
is kept as named entries and reported in `problems`, never silently dropped.
"""

from __future__ import annotations

import re
from typing import Any

from .character import ABILITIES, SKILLS, Data, _ability_bonuses, load_data

ABILITY_BY_ID = dict(zip(range(1, 7), ABILITIES))
ABILITY_BY_WORD = {"strength": "str", "dexterity": "dex", "constitution": "con",
                   "intelligence": "int", "wisdom": "wis", "charisma": "cha"}
SKILL_BY_SLUG = {s.replace(" ", "-"): s for s in SKILLS}


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _find(entries: dict, name: str, prefer: tuple = ("PHB",)) -> dict | None:
    hits = [e for e in entries.values() if _norm(e["name"]) == _norm(name)]
    hits.sort(key=lambda e: (e.get("source") not in prefer, e.get("source", "")))
    return hits[0] if hits else None


def _item_candidates(name: str) -> list[str]:
    """DDB "Crossbow, Hand" / "Rope, Hempen (50 feet)" to 5etools "Hand Crossbow" / "Hempen Rope (50 feet)"."""
    out = [name]
    m = re.match(r"^([^,(]+),\s*([^(]+?)(\s*\(.*\))?$", name)
    if m:
        out.append(f"{m.group(2).strip()} {m.group(1).strip()}{m.group(3) or ''}")
    out += [re.sub(r"s$", "", n) for n in out] + [f"{n} (20)" for n in out] + [f"{n} Armor" for n in out]
    return out


def _mods(ddb: dict, origin: str) -> list[dict]:
    return [m for m in (ddb.get("modifiers") or {}).get(origin) or [] if m]


#: DDB alignmentId -> name (ids as DDB's background page lists them)
DDB_ALIGNMENTS = {1: "Lawful Good", 2: "Neutral Good", 3: "Chaotic Good", 4: "Lawful Neutral", 5: "Neutral",
                  6: "Chaotic Neutral", 7: "Lawful Evil", 8: "Neutral Evil", 9: "Chaotic Evil"}


#: DDB customProficiencies: statId 1-6 and proficiencyLevel 1 (none) to 4 (expertise)
DDB_STATS = {1: "str", 2: "dex", 3: "con", 4: "int", 5: "wis", 6: "cha"}
DDB_PROFICIENCY_LEVELS = {2: "half", 3: "proficient", 4: "expertise"}


def _import_custom_skills(ddb: dict) -> list[dict]:
    """DDB custom proficiencies of type 1 are skills made up at the table ("Navigation"). Without a
    statId the skill keeps no ability; its bonus is then proficiency and misc only."""
    out = []
    for custom in ddb.get("customProficiencies") or []:
        if custom.get("type") != 1 or not custom.get("name"):
            continue
        out.append({"name": custom["name"], "ability": DDB_STATS.get(custom.get("statId")),
                    "proficiency": DDB_PROFICIENCY_LEVELS.get(custom.get("proficiencyLevel")),
                    "misc": (custom.get("miscBonus") or 0) + (custom.get("magicBonus") or 0), "override": custom.get("override")})
    return out


def _import_description(ddb: dict, looks: dict, char: dict) -> None:
    """Characteristics, personality and the Notes tab texts. Possessions and holdings have no field of their
    own here, so they go into the Other note under their DDB names."""
    for key in ("gender", "faith", "age", "hair", "eyes", "skin", "height", "weight"):
        if ddb.get(key) not in (None, ""):
            looks[key] = str(ddb[key])
    if ddb.get("alignmentId") in DDB_ALIGNMENTS:
        looks["alignment"] = DDB_ALIGNMENTS[ddb["alignmentId"]]
    traits = ddb.get("traits") or {}
    for ours, theirs in (("traits", "personalityTraits"), ("ideals", "ideals"), ("bonds", "bonds"), ("flaws", "flaws"), ("appearance", "appearance")):
        if (traits.get(theirs) or "").strip():
            looks[ours] = traits[theirs].strip()
    notes = ddb.get("notes") or {}
    for key in ("organizations", "allies", "enemies", "backstory"):
        if (notes.get(key) or "").strip():
            looks[key] = notes[key].strip()
    other = [(notes.get("otherNotes") or "").strip()]
    other += [f"{label}:\n{notes[key].strip()}" for key, label in (("personalPossessions", "Personal Possessions"), ("otherHoldings", "Other Holdings"))
              if (notes.get(key) or "").strip()]
    if any(other):
        char["notes"] = "\n\n".join(o for o in other if o)


def import_ddb(ddb: dict, data: Data | None = None) -> dict:
    data = data or load_data()
    problems: list[str] = []
    char: dict[str, Any] = {"name": ddb.get("name", ""), "problems": problems,
                            "source": {"ddb_id": ddb.get("id")}}

    char["abilities"] = {
        "method": "manual",
        "base": {ABILITY_BY_ID[s["id"]]: s["value"] or 10 for s in ddb.get("stats", [])},
        "bonus": {ABILITY_BY_ID[s["id"]]: s["value"] for s in ddb.get("bonusStats", []) if s.get("value")},
        "override": {ABILITY_BY_ID[s["id"]]: s["value"] for s in ddb.get("overrideStats", []) if s.get("value")},
    }

    # Race.
    r = ddb.get("race") or {}
    race = None
    if r.get("subRaceShortName"):
        race = next((x for x in sorted(data.races.values(), key=lambda x: x["source"] != "PHB")
                     if x.get("race") == r.get("baseRaceName") and _norm(x.get("subrace") or "") == _norm(r["subRaceShortName"])), None)
    race = race or _find({k: v for k, v in data.races.items() if not v.get("subrace")}, r.get("baseRaceName") or r.get("fullName", ""))
    race_mods = _mods(ddb, "race")
    if race:
        fixed = _ability_bonuses(race.get("ability"), 0, [])
        totals = {a: 0 for a in ABILITIES}
        for m in race_mods:
            if m["type"] == "bonus" and m["subType"].endswith("-score"):
                totals[ABILITY_BY_WORD.get(m["subType"][:-6], "")] = totals.get(ABILITY_BY_WORD.get(m["subType"][:-6], ""), 0) + (m.get("value") or 0)
        chosen = [a for a in ABILITIES if totals.get(a, 0) > fixed[a]]
        char["race"] = {"id": race["id"], "ability_choices": chosen,
                        "skills": [SKILL_BY_SLUG[m["subType"]] for m in race_mods
                                   if m["type"] == "proficiency" and m["subType"] in SKILL_BY_SLUG]}
    else:
        problems.append(f"Race {r.get('fullName')!r} is not in the 2014 builder data.")
        char["race"] = {}

    # Background.
    bdef = (ddb.get("background") or {}).get("definition") or {}
    bg = None
    if bdef.get("name"):
        bg = _find(data.backgrounds, bdef["name"]) or _find(data.backgrounds, bdef["name"].split("/")[0])
        if bg is None:
            problems.append(f"Background {bdef['name']!r} is not in the 2014 builder data.")
    bg_mods = _mods(ddb, "background")
    profs = [m["subType"] for m in bg_mods if m["type"] == "proficiency"]
    char["background"] = {"custom": {"skills": [SKILL_BY_SLUG[p] for p in profs if p in SKILL_BY_SLUG],
                                     "tools": [p.replace("-", " ") for p in profs if p not in SKILL_BY_SLUG]}}
    custom_name = ((ddb.get("background") or {}).get("customBackground") or {}).get("name")
    if custom_name:
        char["background"]["custom"]["name"] = custom_name
    if bg:
        char["background"]["id"] = bg["id"]
    for cp in ddb.get("customProficiencies") or []:
        problems.append(f"Custom DDB proficiency {cp.get('name')!r} is not modelled.")

    # Feats: race feat first if the race offers one, then ASI levels, the rest as bonus feats.
    feat_mods = _mods(ddb, "feat")
    feat_bonus = [ABILITY_BY_WORD[m["subType"][:-6]] for m in feat_mods
                  if m["type"] == "bonus" and m["subType"][:-6] in ABILITY_BY_WORD]
    feats = []
    for f in ddb.get("feats", []):
        name = f["definition"]["name"]
        found = _find(data.feats, name) or _find(data.feats, re.sub(r"\s*\(.*\)$", "", name))
        pick: dict[str, Any] = {"id": found["id"]} if found else {"name": name}
        if found and found.get("ability"):
            pick["ability_choices"] = [a for a in feat_bonus][:1]
        m = re.search(r"\((\w+)\)$", name)
        if m:
            pick["variant"] = m.group(1)
        feats.append(pick)
    if race and race.get("feats") and feats:
        char["race"]["feat"] = feats.pop(0)

    # Classes.
    class_mods = _mods(ddb, "class")
    asi_total = {a: 0 for a in ABILITIES}
    for m in class_mods:
        word = m["subType"][:-6] if m["subType"].endswith("-score") else ""
        if m["type"] == "bonus" and word in ABILITY_BY_WORD:
            asi_total[ABILITY_BY_WORD[word]] += m.get("value") or 0
    class_skills = [SKILL_BY_SLUG[m["subType"]] for m in class_mods if m["type"] == "proficiency" and m["subType"] in SKILL_BY_SLUG]
    expertise = sorted({SKILL_BY_SLUG[m["subType"]] for origin in ("class", "race", "background", "feat")
                        for m in _mods(ddb, origin) if m["type"] == "expertise" and m["subType"] in SKILL_BY_SLUG})
    option_names = [o["definition"]["name"] for o in (ddb.get("options") or {}).get("class") or []]
    spells_by_class = {cs.get("characterClassId"): cs.get("spells", []) for cs in ddb.get("classSpells", [])}
    classes = []
    ordered = sorted(ddb.get("classes", []), key=lambda c: not c.get("isStartingClass"))
    rolled = (ddb.get("preferences") or {}).get("hitPointType") == 2
    for i, c in enumerate(ordered):
        cls = data.classes.get(re.sub(r"[^a-z0-9]+", "-", c["definition"]["name"].lower()))
        if cls is None:
            problems.append(f"Class {c['definition']['name']!r} is not in the 2014 builder data.")
            continue
        entry: dict[str, Any] = {"id": cls["id"], "level": c["level"], "skills": class_skills if i == 0 else [],
                                 "expertise": expertise if i == 0 else [], "asi": {}}
        sub_name = (c.get("subclassDefinition") or {}).get("name")
        if sub_name:
            sub = next((s for s in cls["subclasses"] if _norm(s["name"]) == _norm(sub_name)), None)
            if sub:
                entry["subclass"] = sub["id"]
            else:
                problems.append(f"Subclass {sub_name!r} is not in the 2014 builder data.")
        asi_levels = [f["level"] for f in cls["features"] if f["name"] == "Ability Score Improvement" and f["level"] <= c["level"]]
        for lvl in asi_levels:
            if sum(asi_total.values()) >= 2:
                pick, budget = {}, 2
                for a in ABILITIES:
                    take = min(asi_total[a], budget)
                    if take:
                        pick[a] = take
                        asi_total[a] -= take
                        budget -= take
                entry["asi"][str(lvl)] = {"abilities": pick}
            elif feats:
                entry["asi"][str(lvl)] = {"feat": feats.pop(0)}
        entry["optionalfeatures"] = []
        for name in option_names:
            opt = _find(data.optionalfeatures, name)
            if opt and cls["id"] in _option_classes(cls, entry, data, opt):
                entry["optionalfeatures"].append(opt["id"])
        picks = {"cantrips": [], "known": [], "prepared": []}
        for s in spells_by_class.get(c.get("id"), []):
            spell = data.spell_by_name.get(s["definition"]["name"].lower())
            if spell is None or s.get("alwaysPrepared"):
                continue
            if spell["level"] == 0:
                picks["cantrips"].append(spell["id"])
            else:
                picks["known"].append(spell["id"])
                if s.get("prepared"):
                    picks["prepared"].append(spell["id"])
        entry["spells"] = picks
        classes.append(entry)
    char["classes"] = classes
    char["bonus_feats"] = feats

    deco = ddb.get("decorations") or {}
    looks = char.setdefault("description", {})
    prefs = ddb.get("preferences") or {}
    if "ignoreCoinWeight" in prefs:
        looks["coin_weight"] = not prefs["ignoreCoinWeight"]
    if deco.get("avatarUrl"):
        looks["avatar_url"] = deco["avatarUrl"]
    if deco.get("backdropAvatarUrl"):
        looks["backdrop_url"] = deco["backdropAvatarUrl"]  # a custom backdrop; the default one is the class's own
    if deco.get("themeColor", {}) and isinstance(deco.get("themeColor"), dict) and deco["themeColor"].get("themeColor"):
        looks["theme"] = deco["themeColor"]["themeColor"]

    _import_description(ddb, looks, char)
    if _import_custom_skills(ddb):
        char["custom_skills"] = _import_custom_skills(ddb)

    overrides = {}
    if ddb.get("overrideHitPoints"):
        overrides["hp_max"] = ddb["overrideHitPoints"]
    elif rolled and classes:
        _spread_rolls(classes, data, int(ddb.get("baseHitPoints") or 0))
        char.setdefault("description", {})["hp_mode"] = "rolled"
    if ddb.get("bonusHitPoints"):
        overrides["hp_bonus"] = ddb["bonusHitPoints"]
    char["overrides"] = overrides

    inventory = []
    for it in ddb.get("inventory", []):
        name = it["definition"]["name"]
        item = next((data.item_by_name.get(c.lower()) for c in _item_candidates(name) if data.item_by_name.get(c.lower())), None)
        slot = {"qty": it.get("quantity", 1), "equipped": bool(it.get("equipped")), "attuned": bool(it.get("isAttuned"))}
        if item:
            slot["id"] = item["id"]
        else:
            slot["custom"] = {"name": name, "weight": it["definition"].get("weight") or 0}
        inventory.append(slot)
    char["inventory"] = inventory
    char["currency"] = {k: ddb.get("currencies", {}).get(k, 0) for k in ("cp", "sp", "ep", "gp", "pp")}
    char["play"] = {"hp_current": None if not ddb.get("removedHitPoints") else None, "removed_hp": ddb.get("removedHitPoints", 0),
                    "temp_hp": ddb.get("temporaryHitPoints") or 0, "inspiration": bool(ddb.get("inspiration")),
                    "death_saves": {"success": (ddb.get("deathSaves") or {}).get("successCount") or 0,
                                    "failure": (ddb.get("deathSaves") or {}).get("failCount") or 0}}
    return char


def _spread_rolls(classes: list[dict], data: Data, dice_total: int) -> None:
    """DDB keeps only the sum of rolled hit dice; spread it over the levels so derive() reproduces it."""
    slots = []
    for i, entry in enumerate(classes):
        die = data.classes[entry["id"]]["hd"]["faces"]
        count = entry["level"] - (1 if i == 0 else 0)
        slots.append((entry, die, count))
        if i == 0:
            dice_total -= die
    for entry, die, count in slots:
        entry["hp_rolls"] = [die // 2 + 1] * count
    remainder = dice_total - sum(sum(e["hp_rolls"]) for e, _, _ in slots)
    for entry, die, count in slots:
        for j in range(count):
            step = max(1 - entry["hp_rolls"][j], min(die - entry["hp_rolls"][j], remainder))
            entry["hp_rolls"][j] += step
            remainder -= step


def _option_classes(cls: dict, entry: dict, data: Data, opt: dict) -> set[str]:
    """Which class an optional feature belongs to, by its featureType and the class/subclass progressions."""
    types = set(opt.get("featureType", []))
    progressions = list(cls.get("optionalfeatureProgression") or [])
    sub = data.subclasses.get(entry.get("subclass") or "", (None, None))[1]
    progressions += list((sub or {}).get("optionalfeatureProgression") or [])
    return {cls["id"]} if any(types & set(p["featureType"]) for p in progressions) else set()
