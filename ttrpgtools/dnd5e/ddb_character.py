"""Player characters from D&D Beyond's character JSON.

The endpoint serves characters whose privacy is set to public, without login.
It is undocumented, so every import is also stored locally and a PC can always
be entered or corrected by hand. The response has no CORS header: the fetch
has to happen here, not in the browser.

D&D Beyond stores choices, not results. Hit points, ability scores and armour
class are recomputed here from the parts; AC is the least certain and is
flagged as an estimate.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any

from .statblock import ABILITIES, ability_mod, slugify

ENDPOINT = "https://character-service.dndbeyond.com/character/v5/character/{id}"
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
STAT_NAMES = {1: "strength", 2: "dexterity", 3: "constitution", 4: "intelligence", 5: "wisdom", 6: "charisma"}
STAT_KEYS = dict(zip(STAT_NAMES, ABILITIES))
RESET = {1: "short", 2: "long"}
LIGHT, MEDIUM, HEAVY, SHIELD = 1, 2, 3, 4

#: Multiclass spellcaster table (PHB 2014 p. 165), slots for caster levels 1-20.
FULL_CASTER_SLOTS = [
    [2], [3], [4, 2], [4, 3], [4, 3, 2], [4, 3, 3], [4, 3, 3, 1], [4, 3, 3, 2], [4, 3, 3, 3, 1],
    [4, 3, 3, 3, 2], [4, 3, 3, 3, 2, 1], [4, 3, 3, 3, 2, 1], [4, 3, 3, 3, 2, 1, 1], [4, 3, 3, 3, 2, 1, 1],
    [4, 3, 3, 3, 2, 1, 1, 1], [4, 3, 3, 3, 2, 1, 1, 1], [4, 3, 3, 3, 2, 1, 1, 1, 1], [4, 3, 3, 3, 3, 1, 1, 1, 1],
    [4, 3, 3, 3, 3, 2, 1, 1, 1], [4, 3, 3, 3, 3, 2, 2, 1, 1],
]


class DDBError(ValueError):
    """The character could not be fetched or read."""


def character_id(reference: str) -> str:
    """Accepts a bare id or any D&D Beyond character URL."""
    m = re.search(r"(?:characters?/)?(\d{5,12})", reference.strip())
    if not m:
        raise DDBError("No character id found. Paste the character's URL or its number.")
    return m.group(1)


def fetch(reference: str, timeout: float = 15) -> dict:
    url = ENDPOINT.format(id=character_id(reference))
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise DDBError("Your character is probably set to Private on D&D Beyond. There: Edit, then Home, scroll all "
                           "the way down to Character Privacy and set it to Public. Then import again.") from exc
        if exc.code == 404:
            raise DDBError("D&D Beyond knows no character with that number.") from exc
        raise DDBError(f"D&D Beyond answered with HTTP {exc.code}.") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise DDBError(f"D&D Beyond could not be reached: {exc}") from exc
    if not payload.get("success") or not payload.get("data"):
        raise DDBError(payload.get("message") or "D&D Beyond returned no character.")
    return payload["data"]


def _active_modifiers(data: dict) -> list[dict]:
    """Modifiers that apply now: item modifiers count only while the item is worn (and attuned if it must be)."""
    active_items = set()
    for item in data.get("inventory") or []:
        definition = item.get("definition") or {}
        if item.get("equipped") and (item.get("isAttuned") or not definition.get("canAttune")):
            active_items.add(definition.get("id"))
    modifiers = []
    for group, entries in (data.get("modifiers") or {}).items():
        for m in entries or []:
            if group == "item" and m.get("componentId") not in active_items:
                continue
            modifiers.append(m)
    return modifiers


def _total(modifiers: list[dict], kind: str, sub_type: str) -> int:
    return sum(int(m.get("fixedValue") or m.get("value") or 0) for m in modifiers
               if m.get("type") == kind and m.get("subType") == sub_type)


def _by_id(rows: list[dict] | None) -> dict[int, int | None]:
    return {r["id"]: r.get("value") for r in rows or []}


def _slots(classes: list[dict]) -> tuple[list[int], list[int]]:
    """(spell slots by level, pact slots by level)."""
    caster_level, casters, single_table = 0, 0, None
    pact = []
    for c in classes:
        definition = c["definition"]
        rules = definition.get("spellRules") or {}
        table = rules.get("levelSpellSlots") or []
        if not definition.get("canCastSpells") and not (c.get("subclassDefinition") or {}).get("canCastSpells"):
            continue
        if not definition.get("canCastSpells"):
            # Eldritch Knight, Arcane Trickster: the subclass casts, as a third caster.
            rules = (c["subclassDefinition"].get("spellRules") or {})
            table = rules.get("levelSpellSlots") or []
        level = c["level"]
        if definition["name"] == "Warlock":
            pact = list(table[level]) if level < len(table) else []
            continue
        divisor = rules.get("multiClassSpellSlotDivisor") or 1
        # Artificer rounds up, the other partial casters round down.
        caster_level += -(-level // divisor) if definition["name"] == "Artificer" else level // divisor
        casters += 1
        single_table = list(table[level]) if level < len(table) else []
    if casters == 1:
        slots = single_table or []
    elif casters > 1 and caster_level:
        slots = list(FULL_CASTER_SLOTS[min(20, caster_level) - 1])
    else:
        slots = []

    def trim(values: list[int]) -> list[int]:
        values = list(values)
        while values and values[-1] == 0:
            values.pop()
        return values

    return trim(slots), trim(pact)


def _armor_class(data: dict, modifiers: list[dict], mods: dict[str, int], class_names: set[str]) -> tuple[int, str]:
    armor, shield = None, 0
    for item in data.get("inventory") or []:
        definition = item.get("definition") or {}
        if not item.get("equipped") or not definition.get("armorClass"):
            continue
        if definition.get("armorTypeId") == SHIELD:
            shield = max(shield, int(definition["armorClass"]))
        elif armor is None or definition["armorClass"] > armor["armorClass"]:
            armor = definition
    dex = mods["dex"]
    if armor:
        kind = armor.get("armorTypeId")
        base = int(armor["armorClass"]) + (dex if kind == LIGHT else min(2, dex) if kind == MEDIUM else 0)
        how = armor.get("name") or "armour"
    else:
        base, how = 10 + dex, "unarmoured"
        if "Barbarian" in class_names:
            base, how = 10 + dex + mods["con"], "Unarmored Defense"
        elif "Monk" in class_names and not shield:
            base, how = 10 + dex + mods["wis"], "Unarmored Defense"
        natural = _total(modifiers, "set", "unarmored-armor-class")
        if natural:
            base, how = max(base, 10 + dex + natural), "unarmoured"
    bonus = _total(modifiers, "bonus", "armor-class") + _total(modifiers, "bonus", "armored-armor-class") * bool(armor) \
        + _total(modifiers, "bonus", "unarmored-armor-class") * (not armor)
    parts = [how] + (["shield"] if shield else []) + ([f"+{bonus} bonuses"] if bonus else [])
    return base + shield + bonus, ", ".join(parts)


def parse_character(data: dict) -> dict[str, Any]:
    """D&D Beyond character data -> our PC dict."""
    modifiers = _active_modifiers(data)
    classes = sorted(data.get("classes") or [], key=lambda c: (not c.get("isStartingClass"), -c["level"]))
    if not classes:
        raise DDBError("The character has no class yet.")
    level = sum(c["level"] for c in classes)
    pb = 2 + (level - 1) // 4
    class_names = {c["definition"]["name"] for c in classes}

    base, bonus, override = _by_id(data.get("stats")), _by_id(data.get("bonusStats")), _by_id(data.get("overrideStats"))
    abilities = {}
    for stat_id, name in STAT_NAMES.items():
        score = (base.get(stat_id) or 10) + (bonus.get(stat_id) or 0) + _total(modifiers, "bonus", f"{name}-score")
        score = min(20, score) if score > (base.get(stat_id) or 10) else score
        score = max(score, _total(modifiers, "set", f"{name}-score"))
        abilities[STAT_KEYS[stat_id]] = override.get(stat_id) or score
    mods = {key: ability_mod(value) for key, value in abilities.items()}

    hp_max = data.get("overrideHitPoints") or (
        (data.get("baseHitPoints") or 0) + mods["con"] * level + (data.get("bonusHitPoints") or 0)
        + _total(modifiers, "bonus", "hit-points-per-level") * level + _total(modifiers, "bonus", "hit-points"))
    hp_max = max(1, int(hp_max))
    ac, ac_how = _armor_class(data, modifiers, mods, class_names)

    resources: list[dict] = []
    slots, pact = _slots(classes)
    used = {s["level"]: s.get("used") or 0 for s in data.get("spellSlots") or []}
    pact_used = {s["level"]: s.get("used") or 0 for s in data.get("pactMagic") or []}
    for slot_level, count in enumerate(slots, start=1):
        if count:
            resources.append({"key": f"slot-{slot_level}", "name": f"Level {slot_level} slots", "kind": "slot",
                              "max": count, "level": slot_level, "spent": min(count, used.get(slot_level, 0))})
    for slot_level, count in enumerate(pact, start=1):
        if count:
            resources.append({"key": f"pact-{slot_level}", "name": f"Pact slots (level {slot_level})",
                              "kind": "short", "max": count, "level": slot_level,
                              "spent": min(count, pact_used.get(slot_level, 0))})
    seen = set()
    for group in (data.get("actions") or {}).values():
        for action in group or []:
            limited = action.get("limitedUse")
            if not limited or not action.get("name"):
                continue
            maximum = int(limited.get("maxUses") or 0)
            if limited.get("useProficiencyBonus"):
                maximum = max(maximum, 0) + pb if limited.get("proficiencyBonusOperator") == 1 and maximum else pb
            if limited.get("statModifierUsesId"):
                maximum = max(1, maximum + mods[STAT_KEYS[limited["statModifierUsesId"]]])
            key = slugify(action["name"])
            # Pools such as a summon's hit points hide in this list too.
            if not 0 < maximum <= 30 or key in seen:
                continue
            seen.add(key)
            resources.append({"key": key, "name": action["name"], "kind": RESET.get(limited.get("resetType"), "day"),
                              "max": maximum, "spent": min(maximum, int(limited.get("numberUsed") or 0))})

    initiative = mods["dex"] + _total(modifiers, "bonus", "initiative")
    main = classes[0]["definition"]["name"]
    return {
        "name": data.get("name") or "Unnamed",
        "level": level, "cls": main.lower(),
        "classes": [{"name": c["definition"]["name"], "level": c["level"],
                     "subclass": (c.get("subclassDefinition") or {}).get("name")} for c in classes],
        "race": ((data.get("race") or {}).get("fullName")) or "",
        "hp": hp_max, "hp_current": max(0, hp_max - int(data.get("removedHitPoints") or 0)),
        "temp_hp": int(data.get("temporaryHitPoints") or 0),
        "ac": ac, "ac_how": ac_how, "ac_estimated": True,
        "abilities": abilities, "init_mod": initiative,
        "resources": resources,
        "ddb_id": str(data.get("id") or ""), "ddb_url": data.get("readonlyUrl") or "",
        "source": "ddb",
    }


def import_character(reference: str) -> dict:
    return parse_character(fetch(reference))
