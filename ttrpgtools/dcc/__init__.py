"""Dungeon Crawl Classics: content access, character rules, funnel generation, storage.

Characters are plain dicts saved as JSON under ``characters/dcc/``. Rules
content comes from ``content/dcc/private/core.json`` (built by
``scripts/dcc_extract.py`` from the owned PDFs; gitignored). Everything here is
pure except ``load_content`` and the storage helpers.
"""

from __future__ import annotations

import json
import random
import re
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

REPO_DIR = Path(__file__).resolve().parent.parent.parent
CONTENT_PATH = REPO_DIR / "content" / "dcc" / "private" / "core.json"
CHARACTERS_DIR = REPO_DIR / "characters" / "dcc"

ABILITIES = ["strength", "agility", "stamina", "personality", "intelligence", "luck"]
ABILITY_LABELS = {"strength": "Str", "agility": "Agi", "stamina": "Sta", "personality": "Per",
                  "intelligence": "Int", "luck": "Luck"}
CLASSES = ["cleric", "thief", "warrior", "wizard", "dwarf", "elf", "halfling"]
HIT_DIE = {"cleric": 8, "thief": 6, "warrior": 12, "wizard": 4, "dwarf": 10, "elf": 6, "halfling": 6}
RACE_CLASS = {"dwarven": "dwarf", "elven": "elf", "halfling": "halfling"}
BASE_SPEED = {"dwarf": 20, "halfling": 20}
ALIGNMENTS = ["lawful", "neutral", "chaotic"]
CASTER_ABILITY = {"wizard": "intelligence", "elf": "intelligence", "cleric": "personality"}
#: Governing ability per thief skill (core rulebook, thief class entry).
THIEF_SKILL_ABILITY = {
    "Backstab": None, "Sneak Silently": "agility", "Hide in Shadows": "agility", "Pick Pockets": "agility",
    "Climb Sheer Surfaces": "agility", "Pick Lock": "agility", "Find Trap": "intelligence",
    "Disable Trap": "agility", "Forge Document": "agility", "Disguise Self": "personality",
    "Read Languages": "intelligence", "Handle Poison": None, "Use Scroll": "intelligence",
}
#: Armor check penalty "applies to checks to climb, jump, balance, swim, move silently" (p. 70).
ARMOR_PENALTY_SKILLS = ("Sneak Silently", "Climb Sheer Surfaces")
MAX_LEVEL = 10
#: Table 5-8 lists four cleric spells for wizards; a wizard level that differs from the cleric level means -2 to the check.
WIZARD_CLERIC_SPELLS = {"Detect Magic": 1, "Detect Evil": 2, "Binding": 3, "Paralysis": 3}
PATRON_PAIR = ("Patron Bond", "Invoke Patron")
RACE_LANGUAGE = {"dwarf": "Dwarf", "elf": "Elf", "halfling": "Halfling"}
#: Table 1-3 footnotes.
FARMER_TYPES = ["potato", "wheat", "turnip", "corn", "rice", "parsnip", "radish", "rutabaga"]
FARM_ANIMALS = ["sheep", "goat", "cow", "duck", "goose", "mule"]
CART_CONTENTS = ["tomatoes", "nothing", "straw", "your dead", "dirt", "rocks"]
OCCUPATION_AMMO = {"Sling": "Sling stones", "Dart": None, "Shortbow": "Arrows", "Longbow": "Arrows", "Crossbow": "Quarrels"}
TRADE_ARMOR = {"hide armor": ("Hide", "armor"), "leather armor": ("Leather", "armor"), "shield": ("Shield", "shield")}


class DCCError(ValueError):
    """A rule was violated (wrong class for race, too many spells, ...)."""


# ------------------------------------------------------------------ content
@lru_cache(maxsize=1)
def load_content(path: str | None = None) -> dict:
    p = Path(path) if path else CONTENT_PATH
    if not p.exists():
        raise FileNotFoundError(
            f"{p} missing. Build it with: python scripts/dcc_extract.py <Ref_Book.pdf> <core_rulebook.pdf>")
    return json.loads(p.read_text(encoding="utf-8"))


def content_available() -> bool:
    return CONTENT_PATH.exists()


def ability_mod(content: dict, score: int) -> int:
    score = max(3, min(18, int(score)))
    return int(content["ability_mods"][str(score)]["mod"])


def spells_known_adjustment(content: dict, score: int) -> int:
    text = content["ability_mods"][str(max(3, min(18, int(score))))]["wizard_spells_known"]
    m = re.search(r"([+-]\d+)", text)
    return int(m.group(1)) if m else 0


def max_spell_level_by_ability(content: dict, score: int) -> int:
    text = content["ability_mods"][str(max(3, min(18, int(score))))]["max_spell_level"]
    return int(text) if text.strip().isdigit() else 0


def weapon_row(content: dict, name: str) -> dict | None:
    """Table 3-1 row for a weapon name; occupation weapons like 'Pick (as club)'
    resolve to their 'as' weapon."""
    m = re.search(r"\(as (\w[\w ]*)\)", name)
    base = m.group(1) if m else name
    base = {"axe": "Handaxe", "hand axe": "Handaxe", "bow": "Shortbow", "hammer": "Warhammer",
            "shovel": "Staff"}.get(base.strip().lower(), base.strip())
    for w in content["weapons"]:
        if w["name"].lower() == base.lower():
            return w
    return None


def armor_row(content: dict, name: str | None) -> dict | None:
    if not name:
        return None
    for a in content["armor"]:
        if a["name"].lower() == name.lower():
            return a
    return None


def class_row(content: dict, klass: str | None, level: int) -> dict | None:
    if not klass or level < 1:
        return None
    return content["classes"][klass].get(str(min(level, MAX_LEVEL)))


def _as_wizard_spell(spell: dict) -> dict:
    level = WIZARD_CLERIC_SPELLS[spell["name"]]
    out = {**spell, "level": level, "as_cleric": True}
    if level != spell["level"]:
        out["check_penalty"] = -2
        out["note"] = ("As the cleric spell, learned at a different level: -2 to spell checks, and a natural 1 "
                       "carries a 50% chance of major corruption or misfire on the generic tables.")
    return out


def spell_list(content: dict, klass: str | None, character: dict | None = None) -> list[dict]:
    """Spells a class can learn. Wizards and elves use table 5-8: the wizard
    spells, four cleric spells at their wizard level, and the patron spells of
    the patron they are bonded to (all patrons when no character is given)."""
    if klass in ("wizard", "elf"):
        out = [s for s in content["spells"] if s["class"] == "wizard"]
        out += [_as_wizard_spell(s) for s in content["spells"] if s["class"] == "cleric" and s["name"] in WIZARD_CLERIC_SPELLS]
        patron = (character.get("patron") or "").strip().lower() if character else None
        bonded = character is None or klass == "elf" or "Patron Bond" in character.get("spells", [])
        for s in content["spells"]:
            if s["class"] == "patron" and bonded and (patron is None or (patron and patron in s.get("patron", "").lower())):
                out.append(s)
        return sorted(out, key=lambda s: (s["level"], s["name"]))
    if klass == "cleric":
        return [s for s in content["spells"] if s["class"] == "cleric"]
    return []


def find_spell(content: dict, name: str, klass: str | None = None) -> dict | None:
    """Spell by name; for a wizard or elf the shared cleric spells come back at their wizard level."""
    wanted = name.lower()
    match = [s for s in content["spells"] if s["name"].lower() == wanted]
    if not match:
        return None
    if klass in ("wizard", "elf"):
        own = next((s for s in match if s["class"] in ("wizard", "patron")), None)
        if own:
            return own
        shared = next((s for s in match if s["name"] in WIZARD_CLERIC_SPELLS), None)
        return _as_wizard_spell(shared) if shared else match[0]
    return next((s for s in match if s["class"] == klass), match[0])


# ------------------------------------------------------------------ characters
def _plus(n: int) -> str:
    return f"+{n}" if n >= 0 else str(n)


def _int(s: str) -> int:
    m = re.match(r"^([+-]?\d+)", str(s).strip())
    return int(m.group(1)) if m else 0


def effective_abilities(character: dict) -> dict:
    """Scores after temporary loss (spellburn, poison, disapproval illness); heals 1 per day."""
    dmg = character.get("ability_damage") or {}
    out = {a: int(character["abilities"][a]) - int(dmg.get(a, 0)) for a in ABILITIES}
    # Burned Luck is gone (p. 19), so every Luck-based roll except the birth augur and the class's fixed lucky roll follows it down.
    out["luck"] = int(character.get("luck_current", character["abilities"]["luck"])) - int(dmg.get("luck", 0))
    return out


def race_of(character: dict) -> str | None:
    occ = (character.get("occupation") or {}).get("occupation", "")
    first = occ.split(" ")[0].lower() if occ else ""
    return RACE_CLASS.get(first)


def occupation_extras(content: dict, occupation: dict) -> list[dict]:
    """The extra dice table 1-3's footnotes ask for: ammunition for a missile
    weapon, the farmer's crop, the pushcart's load."""
    out = []
    weapon = weapon_row(content, occupation.get("weapon", ""))
    if weapon and weapon["name"] in OCCUPATION_AMMO:
        what = OCCUPATION_AMMO[weapon["name"]] or f"{weapon['name'].lower()}s"
        out.append({"key": "ammo", "die": 6, "label": f"Number of {what.lower()}", "options": None})
    if occupation.get("occupation") == "Farmer":
        out.append({"key": "farmer_type", "die": 8, "label": "Farmer type", "options": FARMER_TYPES})
    if "pushcart" in occupation.get("trade_goods", "").lower():
        out.append({"key": "cart", "die": 6, "label": "What is in the pushcart", "options": CART_CONTENTS})
    return out


def coins_in_text(text: str) -> dict | None:
    """'5 gp, 10 sp, 200 cp' -> coins; None when the text is anything but coins."""
    parts = [p.strip() for p in text.replace("*", "").split(",")]
    coins = {"cp": 0, "sp": 0, "gp": 0}
    for part in parts:
        m = re.fullmatch(r"(\d+) (cp|sp|gp)", part)
        if not m:
            return None
        coins[m.group(2)] += int(m.group(1))
    return coins


def new_character(name: str, abilities: dict, occupation: dict, augur: dict, hp_roll: int,
                  copper: int, equipment_item: str, alignment: str = "neutral", owner: str | None = None,
                  content: dict | None = None, extras: dict | None = None) -> dict:
    """A 0-level character. ``extras`` holds the footnote rolls of table 1-3
    (``ammo`` 1-6, ``farmer_type`` 1-8, ``cart`` 1-6, ``animal`` 1-6 for a
    second farmer or herder in the same party)."""
    content = content or load_content()
    extras = extras or {}
    if not 1 <= int(hp_roll) <= 4:
        raise DCCError("0-level hit points are a 1d4 roll (1 to 4).")
    if alignment not in ALIGNMENTS:
        raise DCCError("Alignment is lawful, neutral or chaotic.")
    for a in ABILITIES:
        if not 3 <= int(abilities[a]) <= 18:
            raise DCCError(f"{a.capitalize()} is a 3d6 roll (3 to 18).")
    luck_mod = ability_mod(content, abilities["luck"])
    sta_mod = ability_mod(content, abilities["stamina"])
    aug_hp = luck_mod if "hp_per_level" in augur_targets(augur["applies_to"]) else 0
    hp = max(1, int(hp_roll) + sta_mod + aug_hp)
    occupation = dict(occupation)
    if occupation.get("occupation") == "Farmer" and extras.get("farmer_type"):
        occupation["detail"] = f"{FARMER_TYPES[int(extras['farmer_type']) - 1]} farmer"
    coins = {"cp": int(copper), "sp": 0, "gp": 0}
    inventory = []

    def item(name, kind, qty=1, equipped=False, notes=""):
        inventory.append({"name": name, "kind": kind, "qty": int(qty), "cost": None, "equipped": equipped, "notes": notes})

    weapon = occupation.get("weapon", "")
    if weapon:
        row = weapon_row(content, weapon)
        ammo = max(1, min(6, int(extras.get("ammo") or 1)))
        if row and row["name"] == "Dart":
            item(weapon, "weapon", ammo, True)
        else:
            item(weapon, "weapon", 1, True)
            if row and OCCUPATION_AMMO.get(row["name"]):
                item(OCCUPATION_AMMO[row["name"]], "ammo", ammo)
    goods = occupation.get("trade_goods", "").replace("*", "").strip()
    if goods:
        as_coins = coins_in_text(goods)
        if as_coins:
            coins = {k: coins[k] + as_coins[k] for k in coins}
        elif goods.lower() in TRADE_ARMOR:
            worn, kind = TRADE_ARMOR[goods.lower()]
            item(worn, kind, 1, True, "from the occupation")
        else:
            if extras.get("animal") and goods.lower() in ("hen", "sow", "herding dog"):
                goods = FARM_ANIMALS[int(extras["animal"]) - 1].capitalize()
            if "pushcart" in goods.lower() and extras.get("cart"):
                goods = f"Pushcart ({CART_CONTENTS[int(extras['cart']) - 1]})"
            item(goods, "trade")
    if equipment_item:
        item(equipment_item, "gear")
    race = RACE_CLASS.get(occupation.get("occupation", "").split(" ")[0].lower())
    languages = ["Common"]
    if race and int(abilities["intelligence"]) >= 8:
        languages.append(RACE_LANGUAGE[race])
    character = {
        "system": "dcc", "name": name, "owner": owner, "created": date.today().isoformat(),
        "abilities": {a: int(abilities[a]) for a in ABILITIES},
        "luck_current": int(abilities["luck"]),
        "birth_augur": {**augur, "modifier": luck_mod},
        "occupation": occupation, "alignment": alignment, "level": 0, "class": None, "xp": 0,
        "hp_max": hp, "hp_current": hp, "coins": coins, "inventory": inventory,
        "spells": [], "patron": None, "languages": languages, "notes": "", "disapproval": 1,
        "history": [{"event": "0-level", "hp_roll": int(hp_roll), "copper": int(copper),
                     **({"augur_hp": aug_hp} if aug_hp else {})}],
    }
    sync_legacy_fields(character)
    return character


def roll_funnel_character(rng: random.Random, content: dict, name: str, alignment: str = "neutral",
                          owner: str | None = None, party: list[dict] | None = None) -> dict:
    """One 0-level character per the core rules: 3d6 in order, d100 occupation,
    d30 birth augur, 1d4 hp, 5d12 cp, one d24 item, plus the footnote dice.
    ``party`` is the characters rolled so far: a second farmer or herder gets a
    random farm animal instead of the listed one."""
    d = lambda n, sides: sum(rng.randint(1, sides) for _ in range(n))
    abilities = {a: d(3, 6) for a in ABILITIES}
    roll = rng.randint(1, 100)
    occupation = next(o for o in content["occupations"] if o["roll"][0] <= roll <= o["roll"][1])
    augur_roll = rng.randint(1, 30)
    augur = next(a for a in content["luck_augurs"] if a["roll"] == augur_roll)
    item_roll = rng.randint(1, 24)
    item = next(e for e in content["equipment"] if e["roll"] == item_roll)
    extras = {e["key"]: rng.randint(1, e["die"]) for e in occupation_extras(content, occupation)}
    seen = [(c.get("occupation") or {}).get("occupation") for c in party or []]
    if occupation["occupation"] in seen and re.search(r"[^*]\*\*$", occupation.get("trade_goods", "")):
        extras["animal"] = rng.randint(1, 6)
    return new_character(name, abilities, {**occupation, "rolled": roll}, augur, rng.randint(1, 4), d(5, 12),
                         item["item"], alignment, owner, content, extras)


def rebirth_luck(character: dict, content: dict, luck: int) -> None:
    """Change the Luck a character was born with, as if it had always been so: the score, the Luck left (by the same
    difference), the birth augur's modifier, a 1st-level lucky weapon or spell that still carried the old modifier,
    and the hit points where the augur touches them."""
    luck = int(luck)
    if not 3 <= luck <= 18:
        raise DCCError("Luck at birth is a 3d6 score (3 to 18).")
    old = int(character["abilities"]["luck"])
    old_mod, new_mod = ability_mod(content, old), ability_mod(content, luck)
    character["abilities"]["luck"] = luck
    character["luck_current"] = max(0, int(character.get("luck_current", old)) + luck - old)
    if int(character["birth_augur"].get("roll") or 0) and not character["birth_augur"].get("origin"):  # a sold or bought augur no longer follows the Luck of birth
        character["birth_augur"]["modifier"] = new_mod
    if character.get("first_level_luck_mod") == old_mod:
        character["first_level_luck_mod"] = new_mod
    if "hp_per_level" in augur_targets(character["birth_augur"]["applies_to"]):
        sta_mod = ability_mod(content, character["abilities"]["stamina"])
        total = 0
        for entry in character.get("history", []):
            if entry.get("event") in ("0-level", "level"):
                gained = max(1, int(entry["hp_roll"]) + sta_mod + new_mod)
                total += gained
                entry.pop("augur_hp", None)
                if new_mod:
                    entry["augur_hp"] = new_mod
                if entry["event"] == "level":
                    entry["hp_gained"] = gained
        if total:
            character["hp_current"] = max(1, int(character["hp_current"]) + total - int(character["hp_max"]))
            character["hp_max"] = total


NO_AUGUR = {"roll": 0, "augur": "Born under nothing", "applies_to": "nothing", "modifier": 0}


def set_augur(character: dict, content: dict, augur: dict | None, modifier: int = 0, origin: str | None = None) -> None:
    """Take a character's birth augur away (``augur`` None) or give them another one with a modifier of its own, as
    this campaign's augur trade does. Hit points follow for every level so far when the old or the new augur is the
    one that touches them: each level's roll is kept in the history, so the sum is exact. ``origin`` says where a
    bought augur came from."""
    old = character["birth_augur"]
    new = {**{k: augur[k] for k in ("roll", "augur", "applies_to")}, "modifier": int(modifier)} if augur else dict(NO_AUGUR)
    if origin:
        new["origin"] = origin
    character["birth_augur"] = new
    touches = lambda a: "hp_per_level" in augur_targets(a["applies_to"])
    if not (touches(old) or touches(new)):
        return
    hp_mod = int(new["modifier"]) if touches(new) else 0
    sta_mod = ability_mod(content, character["abilities"]["stamina"])
    total = 0
    for entry in character.get("history", []):
        if entry.get("event") in ("0-level", "level"):
            gained = max(1, int(entry["hp_roll"]) + sta_mod + hp_mod)
            total += gained
            entry.pop("augur_hp", None)
            if hp_mod:
                entry["augur_hp"] = hp_mod
            if entry["event"] == "level":
                entry["hp_gained"] = gained
    if total:
        character["hp_current"] = max(1, int(character["hp_current"]) + total - int(character["hp_max"]))
        character["hp_max"] = total


def reroll_augur(character: dict, content: dict, roll: int) -> None:
    """Replace the birth augur of a 0-level character with another row of table 1-2. The Luck modifier at birth stays
    the one of the natural Luck score; hit points follow if the old or the new augur is the one that touches them."""
    if int(character["level"]) != 0:
        raise DCCError("The birth augur is fixed once a class is chosen.")
    augur = next((a for a in content["luck_augurs"] if a["roll"] == int(roll)), None)
    if not augur:
        raise DCCError("The birth augur is a d30 roll (1 to 30).")
    luck_mod = ability_mod(content, character["abilities"]["luck"])
    character["birth_augur"] = {**augur, "modifier": luck_mod}
    start = next(h for h in character.get("history", []) if h.get("event") == "0-level")
    aug_hp = luck_mod if "hp_per_level" in augur_targets(augur["applies_to"]) else 0
    hp = max(1, int(start["hp_roll"]) + ability_mod(content, character["abilities"]["stamina"]) + aug_hp)
    character["hp_current"] = max(1, int(character["hp_current"]) + hp - int(character["hp_max"]))
    character["hp_max"] = hp
    start.pop("augur_hp", None)
    if aug_hp:
        start["augur_hp"] = aug_hp


def level_up(character: dict, klass: str | None, hp_roll: int, content: dict | None = None) -> None:
    """Advance one level. At level 0 the class is chosen; demi-human occupations
    must take their racial class and humans cannot. Hit points use the natural
    Stamina score, so a temporary loss never costs permanent hit points."""
    content = content or load_content()
    level = int(character["level"])
    if level >= MAX_LEVEL:
        raise DCCError("Already at level 10.")
    if level == 0:
        if klass not in CLASSES:
            raise DCCError("Choose a class.")
        race = race_of(character)
        if race and klass != race:
            raise DCCError(f"A {race} occupation must take the {race} class.")
        if not race and klass in RACE_CLASS.values():
            raise DCCError(f"Only characters with a {klass} occupation can take the {klass} class.")
    elif klass and klass != character["class"]:
        raise DCCError(f"Class is fixed at {character['class']} after level 1.")
    klass = klass if level == 0 else character["class"]
    if not 1 <= int(hp_roll) <= HIT_DIE[klass]:
        raise DCCError(f"A {klass} rolls 1d{HIT_DIE[klass]} for hit points (1 to {HIT_DIE[klass]}).")
    if level == 0:
        character["class"] = klass
        character["first_level_luck_mod"] = ability_mod(content, character.get("luck_current", character["abilities"]["luck"]))
        if klass == "thief" and "Thieves' cant" not in character.setdefault("languages", ["Common"]):
            character["languages"].append("Thieves' cant")
        if klass == "elf":  # patron bond and invoke patron come with the class (table 1-16)
            character["spells"] = list(ELF_FREE_SPELLS) + [n for n in character.get("spells", []) if n not in ELF_FREE_SPELLS]
    sta_mod = ability_mod(content, character["abilities"]["stamina"])
    aug = character["birth_augur"]
    aug_hp = int(aug["modifier"]) if "hp_per_level" in augur_targets(aug["applies_to"]) else 0
    gained = max(1, int(hp_roll) + sta_mod + aug_hp)
    character["level"] = level + 1
    character["hp_max"] = int(character["hp_max"]) + gained
    character["hp_current"] = int(character["hp_current"]) + gained
    character.setdefault("history", []).append(
        {"event": "level", "level": level + 1, "class": klass, "hp_roll": int(hp_roll), "hp_gained": gained,
         **({"augur_hp": aug_hp} if aug_hp else {})})


def set_class_choices(character: dict, content: dict, lucky_weapon: str | None = None, lucky_spell: str | None = None,
                      deity: str | None = None, patron: str | None = None) -> None:
    """The one-time choices a class asks for at 1st level. The lucky weapon and
    lucky spell are fixed for life (pp. 44, 54, 58) and a cleric's god is chosen at 1st level (p. 28),
    so a second, different choice is refused."""
    klass = character.get("class")
    if lucky_weapon:
        if klass not in ("warrior", "dwarf"):
            raise DCCError("Only warriors and dwarves have a lucky weapon.")
        row = weapon_row(content, lucky_weapon)
        if not row:
            raise DCCError("The lucky weapon must be one specific weapon from the weapon table, such as longsword.")
        if character.get("lucky_weapon") and character["lucky_weapon"] != row["name"]:
            raise DCCError(f"The lucky weapon is fixed for life: {character['lucky_weapon']}.")
        character["lucky_weapon"] = row["name"]
    if lucky_spell:
        if klass != "elf":
            raise DCCError("Only elves apply Luck to one chosen spell.")
        if lucky_spell not in character.get("spells", []) and lucky_spell not in ELF_FREE_SPELLS:
            raise DCCError(f"{lucky_spell} is not a known spell.")
        if character.get("lucky_spell") and character["lucky_spell"] != lucky_spell:
            raise DCCError(f"The lucky spell is fixed for life: {character['lucky_spell']}.")
        character["lucky_spell"] = lucky_spell
    if deity is not None:
        if klass != "cleric":
            raise DCCError("Only clerics choose a god.")
        chosen = deity.strip() or None
        if character.get("deity") and chosen and chosen != character["deity"]:  # "At 1st level, a cleric selects a god to worship" (p. 28)
            raise DCCError(f"A cleric chooses a god once, at 1st level: {character['deity']}. A change of faith is the judge's to rule.")
        character["deity"] = character.get("deity") or chosen
    if patron is not None:
        if klass not in ("wizard", "elf"):
            raise DCCError("Only wizards and elves bond with a patron.")
        character["patron"] = patron.strip() or None


def spell_allowance(character: dict, content: dict) -> dict:
    """How many spells the character may know per spell level, and the max
    spell level, from the class table and the natural casting ability (a
    temporary loss does not make a caster forget spells)."""
    klass, level = character.get("class"), int(character["level"])
    row = class_row(content, klass, level)
    if not row or klass not in CASTER_ABILITY:
        return {"caster": False}
    ability = CASTER_ABILITY[klass]
    score = int(character["abilities"][ability])
    check_bonus = level + ability_mod(content, effective_abilities(character)[ability])
    max_by_ability = max_spell_level_by_ability(content, score)
    blocked = None if max_by_ability else f"{ability.capitalize()} {score}: no spellcasting possible (table 1-1)."
    if klass == "cleric":
        per_level = {lvl: _int(row.get(f"spells_l{lvl}", "0")) if row.get(f"spells_l{lvl}", "-") != "-" else 0
                     for lvl in range(1, 6)}
        max_level = min(max((lvl for lvl, n in per_level.items() if n), default=0), max_by_ability)
        return {"caster": True, "kind": "cleric", "per_level": per_level, "max_level": max_level,
                "total": None, "check_bonus": check_bonus, "blocked": blocked}
    known = _int(row["spells_known"]) + spells_known_adjustment(content, score)
    max_level = min(_int(row["max_spell_level"]), max_by_ability)
    return {"caster": True, "kind": "wizard", "total": 0 if blocked else max(1, known), "max_level": max_level,
            "per_level": None, "check_bonus": check_bonus, "blocked": blocked}


ELF_FREE_SPELLS = ("Patron Bond", "Invoke Patron")


def free_spells(character: dict) -> list[str]:
    """Spells known without counting against the allowance (elves: patron bond and invoke patron)."""
    return list(ELF_FREE_SPELLS) if character.get("class") == "elf" else []


def spell_slots_used(character: dict, names: list[str]) -> int:
    """Slots a list of spells takes. For a wizard, patron bond and invoke
    patron come together and count as one slot (table 5-8)."""
    free = {n.lower() for n in free_spells(character)}
    counted = [n for n in names if n.lower() not in free]
    pair = sum(1 for n in counted if n in PATRON_PAIR)
    return len(counted) - (1 if pair == 2 else 0)


def set_spells(character: dict, names: list[str], content: dict | None = None) -> None:
    content = content or load_content()
    allowance = spell_allowance(character, content)
    if not allowance["caster"]:
        raise DCCError("This character cannot cast spells.")
    if allowance.get("blocked"):
        raise DCCError(allowance["blocked"])
    klass = character["class"]
    free = {n.lower() for n in free_spells(character)}
    names = [n.strip() for n in names if n.strip().lower() not in free]
    if klass == "wizard" and any(n.lower() in ("patron bond", "invoke patron") for n in names):
        names += [n for n in PATRON_PAIR if n.lower() not in {x.lower() for x in names}]
    bonded = klass == "elf" or any(n.lower() == "patron bond" for n in names)
    allowed = {s["name"].lower(): s for s in spell_list(content, klass, {**character, "spells": list(PATRON_PAIR) if bonded else []})}
    chosen = []
    for n in names:
        s = allowed.get(n.lower())
        if not s:
            other = find_spell(content, n)
            if other and other["class"] == "patron":
                raise DCCError(f"{other['name']} is a patron spell of {other.get('patron')}: it needs Patron Bond and that patron.")
            raise DCCError(f"Unknown spell for this class: {n}")
        if s["level"] > allowance["max_level"]:
            raise DCCError(f"{s['name']} is level {s['level']}, above the maximum of {allowance['max_level']}.")
        chosen.append(s)
    if len({s["name"] for s in chosen}) != len(chosen):
        raise DCCError("A spell was submitted twice; reload the page and try again.")
    used = spell_slots_used(character, [s["name"] for s in chosen])
    if allowance["kind"] == "wizard" and used > allowance["total"]:
        raise DCCError(f"Too many spells: {used} chosen, {allowance['total']} allowed at level {character['level']}. Untick {used - allowance['total']}.")
    if allowance["kind"] == "cleric":
        for lvl, n in allowance["per_level"].items():
            got = sum(1 for s in chosen if s["level"] == lvl)
            if got > n:
                raise DCCError(f"Too many level {lvl} spells: {got} chosen, {n} allowed.")
    character["spells"] = free_spells(character) + [s["name"] for s in chosen]
    details = character.setdefault("spell_details", {})
    for gone in [k for k in details if k not in character["spells"]]:
        details.pop(gone)
    if character.get("lucky_spell") and character["lucky_spell"] not in character["spells"]:
        character["lucky_spell"] = None


ROLL_AGAIN_TWICE = (99, 100)   # mercurial magic 99: roll again twice. 00: the same, on 4d20 instead of d% (both with Luck x 10)


def set_spell_detail(character: dict, spell: str, mercurial: int | None, more: list | None = None) -> None:
    """Record the player's own mercurial magic roll (d% + Luck mod x 10) for a known spell. A result of 99 or 00 says
    "roll again twice": ``more`` holds those two further results, each a plain entry of the table (1 to 98; a
    further 99 or 00 is rolled again, so the answer is always two effects)."""
    if spell not in character.get("spells", []):
        raise DCCError(f"{spell} is not a known spell.")
    if mercurial is not None and not 1 <= int(mercurial) <= 100:
        raise DCCError("Mercurial magic is a d% result from 1 to 100.")
    detail = character.setdefault("spell_details", {}).setdefault(spell, {})
    detail["mercurial"] = int(mercurial) if mercurial else None
    detail.pop("mercurial_more", None)
    if detail["mercurial"] in ROLL_AGAIN_TWICE and more:
        rolls = [int(r) for r in more if r]
        if len(rolls) != 2 or not all(1 <= r <= 98 for r in rolls):
            raise DCCError(f"{spell}: 'roll again twice' needs two further results from 1 to 98. A further 99 or 00 is rolled again.")
        detail["mercurial_more"] = rolls


def mercurial_entry(content: dict, roll: int | None) -> dict | None:
    if not roll:
        return None
    for r in content["mercurial_magic"]:
        m = re.match(r"^(\d+)(?:-(\d+))?", r["roll"]); lo = int(m.group(1)); hi = int(m.group(2) or lo)
        lo, hi = (100 if lo == 0 else lo), (100 if hi == 0 else hi)
        if lo <= int(roll) <= hi:
            return r
    return None


DICE_CHAIN = ["d3", "d4", "d5", "d6", "d7", "d8", "d10", "d12", "d14", "d16", "d20", "d24", "d30"]
ACTION_DIE_USE = {
    None: "an attack or a skill check",
    "warrior": "an attack (warriors always use action dice to attack)",
    "dwarf": "an attack, plus a separate d14 shield bash each round",
    "cleric": "an attack or a spell check",
    "thief": "an attack or a skill check",
    "wizard": "a spell check or an attack (the second die at level 5+ is best spent on a spell)",
    "elf": "a spell check or an attack",
    "halfling": "an attack, or two attacks when fighting with two small weapons",
}


def action_dice_info(character: dict, v: dict) -> dict:
    """Plain-words explanation of the action dice for the table."""
    dice = [d.strip() for d in v["action_dice"].split("+")]
    klass = character.get("class")
    ordinal = ["first", "second", "third"]
    lines = [f"{len(dice)} action{'s' if len(dice) > 1 else ''} per round."]
    for n, d in enumerate(dice):
        lines.append(f"The {ordinal[n]} action rolls {d} for {ACTION_DIE_USE.get(klass, ACTION_DIE_USE[None])}.")
    if len(dice) > 1:
        lines.append("Each die is one action: a smaller second die means a weaker second action, not a bonus to the first.")
    lines.append("A spell check or attack made with a die smaller than d20 uses that die instead of a d20; all modifiers still apply.")
    lines.append("Penalties written as -1d step the die down the chain (d20 becomes d16); bonuses of +1d step it up.")
    if v.get("threat_range"):
        lines.append(f"Natural {v['threat_range']} on an attack is a critical hit, on any action die.")
    if klass == "thief":
        lines.append("Burning Luck adds the luck die per point to any action.")
    return {"dice": dice, "count": len(dice), "lines": lines, "chain": DICE_CHAIN}


# ------------------------------------------------------------------ weapon training and ammunition
AMMO_FOR = {"Longbow": "Arrows", "Shortbow": "Arrows", "Crossbow": "Quarrels", "Sling": "Sling stones"}


def trained_weapons(character: dict, content: dict) -> set[str] | None:
    """Weapon names the character is trained in; None means no penalty with
    any weapon. 0-level characters never take the untrained penalty (p. 24).
    Clerics train in their alignment's weapons (p. 32), every other class in the
    list of its 'Weapon training' paragraph, plus the occupation weapon."""
    klass = character.get("class")
    if not klass:
        return None
    occ_weapon = weapon_row(content, (character.get("occupation") or {}).get("weapon", ""))
    trained = {occ_weapon["name"]} if occ_weapon else set()
    if klass == "cleric":
        deity = content.get("deities", {}).get(character.get("alignment", "neutral"))
        return trained | set(deity["weapons"]) if deity else None
    text = content["class_prose"].get(klass, {}).get("Weapon training", "").lower().replace("-", "").replace(" ", "")
    for w in content["weapons"]:
        if w["name"].lower().replace("-", "").replace(" ", "") in text:
            trained.add(w["name"])
    return trained


def ammo_count(character: dict, weapon_name: str) -> int | None:
    base = weapon_row_name(character, weapon_name)
    need = AMMO_FOR.get(base)
    if not need:
        return None
    return sum(int(i.get("qty", 0)) for i in character.get("inventory", []) if i["kind"] == "ammo" and i["name"].lower().startswith(need.lower().split()[0]))


def weapon_row_name(character: dict, weapon_name: str) -> str:
    m = re.search(r"\(as (\w[\w ]*)\)", weapon_name)
    base = (m.group(1) if m else weapon_name).strip().lower()
    return {"axe": "Handaxe", "hand axe": "Handaxe", "bow": "Shortbow", "hammer": "Warhammer", "shovel": "Staff"}.get(base, base.title() if base.islower() else base)


# ------------------------------------------------------------------ inventory
ITEM_KINDS = ["weapon", "armor", "shield", "ammo", "gear", "mount", "trade", "other"]


def cost_in_cp(cost) -> int | None:
    """'7' (gp), '5 sp', '15 cp', '10,02 gp' (10 gp and 2 cp, written like cents), '1,200 gp' and '1.200,50 gp'
    -> copper pieces; None when unpriced. A comma or dot followed by exactly three digits separates thousands;
    otherwise the last comma or dot is the decimal mark."""
    if cost is None:
        return None
    text = str(cost).strip().lower()
    m = re.match(r"^([\d.,]*\d)\s*(gp|sp|cp|pp|ep)?$", text)
    if m:
        number = m.group(1)
        mark = max(number.rfind(","), number.rfind("."))
        if mark >= 0 and len(number) - mark - 1 != 3:   # a decimal mark: everything before it is the whole part
            number = re.sub(r"[.,]", "", number[:mark]) + "." + number[mark + 1:]
        else:
            number = re.sub(r"[.,]", "", number)
        text = number + (m.group(2) or "")
    m = re.match(r"^(\d+(?:\.\d+)?)\s*(gp|sp|cp|pp|ep)?$", text)
    if not m:
        return None
    n, unit = float(m.group(1)), m.group(2) or "gp"
    return int(round(n * {"cp": 1, "sp": 10, "gp": 100, "ep": 1000, "pp": 10000}[unit]))


def coins_total_cp(coins: dict) -> int:
    return int(coins.get("gp", 0)) * 100 + int(coins.get("sp", 0)) * 10 + int(coins.get("cp", 0))


def spend(coins: dict, cp: int) -> dict:
    """Pay from cp, then sp, then gp, making change downward when needed."""
    total = coins_total_cp(coins) - cp
    if total < 0:
        raise DCCError(f"Not enough coin: costs {cp} cp, you have {coins_total_cp(coins)} cp in total.")
    gp, sp, c = int(coins.get("gp", 0)), int(coins.get("sp", 0)), int(coins.get("cp", 0))
    need = cp
    take = min(c, need); c -= take; need -= take
    take = min(sp, need // 10); sp -= take; need -= take * 10
    take = min(gp, -(-need // 100)) if need else 0
    if need:
        gp -= take; change = take * 100 - need; need = 0
        sp += change // 10; c += change % 10
    return {"gp": gp, "sp": sp, "cp": c}


def catalog(content: dict) -> list[dict]:
    """Every purchasable thing from the extracted tables, as inventory templates."""
    out = []
    for w in content["weapons"]:
        out.append({"key": f"weapon:{w['name']}", "name": w["name"], "kind": "weapon", "cost": w["cost"] if re.search(r"[a-z]", str(w["cost"])) else f"{w['cost']} gp",
                    "detail": w["damage"] + (f", {w['range']}" if w["range"] else "")})
    for a in content["armor"]:
        if a["name"] == "Unarmored":
            continue
        out.append({"key": f"{'shield' if a['name'] == 'Shield' else 'armor'}:{a['name']}", "name": a["name"], "kind": "shield" if a["name"] == "Shield" else "armor",
                    "cost": a["cost"], "detail": f"AC +{a['ac']}, check {a['check_penalty']}, fumble {a['fumble_die'] or '-'}"})
    for e in content.get("ammunition", []):
        out.append({"key": f"ammo:{e['name']}", "name": e["name"], "kind": "ammo", "cost": e["cost"], "detail": f"x{e['quantity']}", "qty": e["quantity"]})
    for e in content["equipment"]:
        out.append({"key": f"gear:{e['item']}", "name": e["item"], "kind": "gear", "cost": e["cost"], "detail": ""})
    for e in content.get("mounts", []):
        out.append({"key": f"mount:{e['name']}", "name": e["name"], "kind": "mount", "cost": e["cost"], "detail": ""})
    return out


def ensure_inventory(character: dict) -> list[dict]:
    """Build the structured inventory from the legacy weapon/armor/equipment
    fields the first time, then keep those fields in sync for the printable
    sheet and older code paths."""
    if "inventory" not in character:
        inv = []
        for w in character.get("weapons", []):
            inv.append({"name": w, "kind": "weapon", "qty": 1, "cost": None, "equipped": True, "notes": ""})
        if character.get("armor"):
            inv.append({"name": character["armor"], "kind": "armor", "qty": 1, "cost": None, "equipped": True, "notes": ""})
        if character.get("shield"):
            inv.append({"name": "Shield", "kind": "shield", "qty": 1, "cost": None, "equipped": True, "notes": ""})
        trade = (character.get("occupation") or {}).get("trade_goods", "")
        for e in character.get("equipment", []):
            inv.append({"name": e, "kind": "trade" if e and e == trade else "gear", "qty": 1, "cost": None, "equipped": False, "notes": ""})
        character["inventory"] = inv
    sync_legacy_fields(character)
    return character["inventory"]


def sync_legacy_fields(character: dict) -> None:
    inv = character.get("inventory", [])
    character["weapons"] = [i["name"] for i in inv if i["kind"] == "weapon" and i.get("equipped")]
    armor = next((i["name"] for i in inv if i["kind"] == "armor" and i.get("equipped")), None)
    character["armor"] = armor
    character["shield"] = any(i["kind"] == "shield" and i.get("equipped") for i in inv)
    character["equipment"] = [f"{i['name']}" + (f" x{i['qty']}" if int(i.get("qty", 1)) != 1 else "")
                              for i in inv if i["kind"] not in ("weapon", "armor", "shield") or not i.get("equipped")]


def add_item(character: dict, name: str, kind: str, qty: int = 1, cost: str | None = None, buy: bool = False,
             notes: str = "", priced_units: int | None = None, mithril: bool = False) -> None:
    """Add ``qty`` of an item. ``cost`` is the price of one priced unit; ammunition
    is priced per bundle, so the caller passes the number of bundles as ``priced_units``."""
    if kind not in ITEM_KINDS:
        raise DCCError(f"Unknown item kind {kind}.")
    if not name.strip():
        raise DCCError("Item needs a name.")
    qty = max(1, int(qty))
    inv = ensure_inventory(character)
    if buy:
        cp = cost_in_cp(cost)
        if cp is None:
            raise DCCError(f"{name} has no price to pay.")
        character["coins"] = spend(character["coins"], cp * (qty if priced_units is None else int(priced_units)))
    for item in inv:  # stack identical unequipped countables
        if item["name"] == name and item["kind"] == kind and kind in ("ammo", "gear", "trade", "other") and not item.get("equipped") and not item.get("mark"):
            item["qty"] = int(item.get("qty", 1)) + qty
            sync_legacy_fields(character); return
    equipped = kind == "weapon" or (kind in ("armor", "shield") and not any(i["kind"] == kind and i.get("equipped") for i in inv))
    entry = {"name": name.strip(), "kind": kind, "qty": qty, "cost": cost, "equipped": bool(equipped), "notes": notes}
    if mithril:
        entry["mithril"] = True
    inv.append(entry)
    sync_legacy_fields(character)


def buy_catalog(character: dict, content: dict, key: str, count: int = 1, pay: bool = True, mithril: bool = False) -> None:
    """Take ``count`` purchases of a catalog entry; one purchase of ammunition is one bundle (20 arrows).
    An elf may take one weapon and one armor in mithril at the normal price at 1st level (p. 56)."""
    entry = next((e for e in catalog(content) if e["key"] == key), None)
    if not entry:
        raise DCCError("Pick something from the list.")
    count = max(1, int(count))
    if mithril:
        if character.get("class") != "elf" or entry["kind"] not in ("weapon", "armor"):
            raise DCCError("Only an elf's one weapon and one armor come in mithril at the normal price.")
        if any(i.get("mithril") and i["kind"] == entry["kind"] for i in ensure_inventory(character)):
            raise DCCError(f"The elf already has a mithril {entry['kind']}; further mithril is the judge's call.")
        count = 1
    add_item(character, entry["name"], entry["kind"], count * int(entry.get("qty", 1)), entry["cost"], buy=pay,
             priced_units=count, mithril=mithril, notes="mithril" if mithril else "")


def remove_item(character: dict, index: int) -> None:
    inv = ensure_inventory(character)
    if not 0 <= index < len(inv):
        raise DCCError("No such item.")
    inv.pop(index); sync_legacy_fields(character)


def set_equipped(character: dict, index: int, equipped: bool) -> None:
    inv = ensure_inventory(character)
    if not 0 <= index < len(inv):
        raise DCCError("No such item.")
    item = inv[index]
    if item["kind"] in ("armor", "shield") and equipped:
        for other in inv:
            if other is not item and other["kind"] == item["kind"]:
                other["equipped"] = False
    if item["kind"] not in ("weapon", "armor", "shield"):
        raise DCCError("Only weapons, armor and shields are equipped.")
    item["equipped"] = bool(equipped); sync_legacy_fields(character)


def change_qty(character: dict, index: int, delta: int) -> None:
    inv = ensure_inventory(character)
    if not 0 <= index < len(inv):
        raise DCCError("No such item.")
    inv[index]["qty"] = max(0, int(inv[index].get("qty", 1)) + int(delta))
    if inv[index]["qty"] == 0:
        inv.pop(index)
    sync_legacy_fields(character)


# ------------------------------------------------------------------ birth augur targets and roll breakdowns
#: Table 1-2 "lucky roll" text -> which sheet rolls the augur modifier touches.
AUGUR_RULES = [
    (r"all attack rolls", {"melee_attack", "missile_attack"}),
    (r"melee attack", {"melee_attack"}), (r"missile fire attack", {"missile_attack"}),
    (r"unarmed attack", {"unarmed_attack"}), (r"mounted attack", {"mounted_attack"}),
    (r"attack and damage rolls for 0-level", {"starting_weapon"}),
    (r"^damage rolls", {"melee_damage", "missile_damage"}),
    (r"melee damage", {"melee_damage"}), (r"missile fire damage", {"missile_damage"}),
    (r"skill checks", {"skill_checks", "thief_skills"}), (r"find/disable traps", {"traps"}),
    (r"secret doors", {"secret_doors"}), (r"spell checks", {"spell_check"}), (r"spell damage", {"spell_damage"}),
    (r"turn unholy", {"turn_unholy"}), (r"magical healing", {"healing"}),
    (r"^saving throws$", {"reflex", "fortitude", "willpower"}), (r"escape traps", {"save_traps"}),
    (r"(against|vs\.?) poison", {"save_poison"}), (r"reflex", {"reflex"}), (r"fortitude", {"fortitude"}),
    (r"willpower", {"willpower"}), (r"armor class", {"ac"}), (r"initiative", {"initiative"}),
    (r"hit points", {"hp_per_level"}), (r"critical hit", {"crit"}), (r"corruption", {"corruption"}),
    (r"fumbles", {"fumble"}), (r"languages", {"languages"}), (r"speed", {"speed"}),
]


def augur_targets(applies_to: str) -> set[str]:
    text = applies_to.lower().strip()
    out: set[str] = set()
    for pat, targets in AUGUR_RULES:
        if re.search(pat, text):
            out |= targets
    return out


def augur_effect(character: dict) -> str:
    """One sentence a player can act on: 'Charmed House: +1 to Armor Class'."""
    aug = character["birth_augur"]; mod = int(aug["modifier"]); targets = augur_targets(aug["applies_to"])
    what = aug["applies_to"].replace("*", "").strip()
    if not int(aug.get("roll") or 0):
        return "Born under nothing: no birth augur"
    if mod == 0 and aug.get("origin"):
        return f"{aug['augur']}: no effect, worn down to nothing (it would apply to {what.lower()})"
    if mod == 0:
        return f"{aug['augur']}: no effect, the Luck modifier was 0 at birth (it would apply to {what.lower()})"
    doubled = ""
    if "crit" in targets:
        doubled = " on top of the normal Luck modifier, so Luck counts double there"
    elif "fumble" in targets:
        return (f"{aug['augur']}: Luck counts double on fumbles; the fixed {_plus(mod)} is subtracted from every fumble roll "
                "on top of the normal Luck modifier, for life")
    special = ""
    if "speed" in targets:
        special = f", that is {_plus(mod * 5)}' speed"
    elif "languages" in targets:
        special = f", that is {abs(mod)} {'more' if mod > 0 else 'fewer'} language{'s' if abs(mod) != 1 else ''}"
    elif "hp_per_level" in targets:
        special = ", added every time hit points are rolled"
    return f"{aug['augur']}: {_plus(mod)} to {what.lower()}{doubled}{special}, fixed for life"


def two_weapon_row(content: dict, agility: int) -> dict | None:
    for r in content.get("two_weapon", []):
        if r["agility"][0] <= agility <= r["agility"][1]:
            return r
    return None


def burn_luck(character: dict, points: int, content: dict | None = None) -> str:
    """Burn Luck for a one-time bonus; returns the bonus the burn gives this class."""
    points = int(points)
    if points < 1 or points > int(character["luck_current"]):
        raise DCCError("Burn between 1 and your current Luck.")
    character["luck_current"] = int(character["luck_current"]) - points
    klass = character.get("class")
    if klass == "thief":
        die = (class_row(content or load_content(), klass, int(character["level"])) or {}).get("luck_die", "d3")
        return f"+{points}{die}"
    return f"+{points * 2}" if klass == "halfling" else f"+{points}"


def recover_luck(character: dict, points: int | None = None) -> int:
    """Thieves and halflings regain their level in Luck each night, others only by
    the judge's grace; returns the points actually restored."""
    klass = character.get("class")
    natural = int(character["abilities"]["luck"])
    if points is None:
        points = int(character["level"]) if klass in ("thief", "halfling") else 0
    restored = max(0, min(int(points), natural - int(character["luck_current"])))
    character["luck_current"] = int(character["luck_current"]) + restored
    return restored


def spellburn(character: dict, strength: int = 0, agility: int = 0, stamina: int = 0) -> dict:
    """Burn ability points for +1 per point on one spell check (p. 107). A full
    20 points in one burn makes the check a natural 20. The loss is temporary
    and returns with rest like any other ability loss."""
    if character.get("class") not in ("wizard", "elf"):
        raise DCCError("Only wizards and elves can spellburn.")
    burn = {"strength": int(strength), "agility": int(agility), "stamina": int(stamina)}
    if any(v < 0 for v in burn.values()) or sum(burn.values()) == 0:
        raise DCCError("Spellburn at least one point of Strength, Agility or Stamina.")
    eff = effective_abilities(character)
    for a, n in burn.items():
        if n > eff[a]:
            raise DCCError(f"Not enough {a} left to burn {n}.")
    dmg = character.setdefault("ability_damage", {})
    for a, n in burn.items():
        if n:
            dmg[a] = int(dmg.get(a, 0)) + n
    total = sum(burn.values())
    return {"bonus": total, "natural_20": total >= 20}


def heal_ability_damage(character: dict, points: int = 1, prefer: str | None = None) -> list[str]:
    """Return ``points`` of lost ability score in total (p. 94: 1 point per
    night, 2 with bed rest), the preferred ability first, then the most
    damaged one. Returns the abilities that healed."""
    dmg = character.get("ability_damage") or {}
    healed = []
    for _ in range(int(points)):
        open_ = [a for a in dmg if int(dmg[a]) > 0]
        if not open_:
            break
        a = prefer if prefer in open_ else max(open_, key=lambda k: int(dmg[k]))
        dmg[a] = int(dmg[a]) - 1
        healed.append(a)
        if dmg[a] == 0:
            dmg.pop(a)
    return healed


def rest(character: dict, bed_rest: bool = False, prefer: str | None = None, hp: int | None = None,
         ability: int | None = None) -> dict:
    """A night's rest (p. 94): 1 hit point and 1 point of lost ability score, 2
    each with a day of bed rest; thieves and halflings regain Luck; a cleric's
    disapproval range resets. ``hp`` and ``ability`` override the two amounts
    (the campaign's inns set their own). Dodo's ruling 2026-10-04: a day with
    spellburn heals like any other."""
    points = 2 if bed_rest else 1
    before = int(character["hp_current"])
    character["hp_current"] = max(before, min(int(character["hp_max"]), before + (points if hp is None else int(hp))))
    healed = heal_ability_damage(character, points if ability is None else int(ability), prefer)
    luck = recover_luck(character)
    if character.get("class") == "cleric":
        character["disapproval"] = 1
    return {"hp": int(character["hp_current"]) - before, "abilities": healed, "luck": luck}


def saved_from_bleeding_out(character: dict, healed: int) -> None:
    """Healed in time while bleeding out (p. 93): hit points count up from 0, and 1 point of Stamina is gone for good."""
    if int(character["level"]) < 1 or int(character["hp_current"]) > 0:
        raise DCCError("Only a classed character at 0 hit points bleeds out.")
    if int(healed) < 1:
        raise DCCError("The healing must restore at least 1 hit point.")
    character["hp_current"] = min(int(character["hp_max"]), int(healed))
    character["abilities"]["stamina"] = max(1, int(character["abilities"]["stamina"]) - 1)
    character.setdefault("history", []).append({"event": "saved from bleeding out", "stamina_lost": 1})


def recovered_body(character: dict, ability: str) -> None:
    """The Luck check when the body was rolled over succeeded (p. 93): 1 hit point, and 1 point of Strength, Agility
    or Stamina lost for good (the table decides which)."""
    if ability not in ("strength", "agility", "stamina"):
        raise DCCError("The permanent injury takes 1 point of Strength, Agility or Stamina.")
    if int(character["hp_current"]) > 0:
        raise DCCError("Only a character at 0 hit points is recovered this way.")
    character["hp_current"] = 1
    character["abilities"][ability] = max(1, int(character["abilities"][ability]) - 1)
    character.setdefault("history", []).append({"event": "body recovered", "lost": ability})


def adjust_disapproval(character: dict, delta: int) -> int:
    """Failed check +1, divine aid +10, sin +1 to +10, sacrifice -1 per 50 gp; never below a natural 1."""
    if character.get("class") != "cleric":
        raise DCCError("Only clerics have a disapproval range.")
    character["disapproval"] = max(1, min(20, int(character.get("disapproval", 1)) + int(delta)))
    return character["disapproval"]


def set_ability_damage(character: dict, ability: str, amount: int) -> None:
    if ability not in ABILITIES or int(amount) < 0 or int(amount) > int(character["abilities"][ability]):
        raise DCCError("Ability loss runs from 0 to the full score.")
    dmg = character.setdefault("ability_damage", {})
    if int(amount):
        dmg[ability] = int(amount)
    else:
        dmg.pop(ability, None)


def roll_breakdowns(character: dict, content: dict, v: dict) -> list[dict]:
    """Every roll the sheet cares about, as total plus named components, so the
    player sees exactly which modifiers apply (class, ability, birth augur,
    lucky weapon, luck die)."""
    c, m = character, v["mods"]
    aug = c["birth_augur"]; targets = augur_targets(aug["applies_to"]); amod = int(aug["modifier"])
    klass, level = c.get("class"), int(c["level"])

    def parts_total(parts):
        return sum(p[1] for p in parts if isinstance(p[1], int))

    def augur_part(key):
        if key in targets and amod:
            return [(f"birth augur ({aug['augur']})", -amod if key == "fumble" else amod)]
        return []

    rolls = []

    def add(key, label, die, parts, note=""):
        total = parts_total(parts)
        dice_parts = [p for p in parts if not isinstance(p[1], int)]
        text = " ".join([die] + [f"{p[1]}" for p in dice_parts] + [_plus(total)]) if not dice_parts else f"{die} + {' + '.join(str(p[1]) for p in dice_parts)} {_plus(total)}"
        rolls.append({"key": key, "label": label, "total": text, "parts": [(p[0], p[1] if not isinstance(p[1], int) else _plus(p[1])) for p in parts], "note": note})

    deed = [("deed die", v["attack"][1:])] if v["deed_die"] else [("class attack", _int(v["attack"]))]
    lucky_w = c.get("lucky_weapon")
    lucky_parts = [(f"lucky weapon ({lucky_w})", int(c.get("first_level_luck_mod", 0)))] if lucky_w and klass in ("warrior", "dwarf") else []
    add("melee_attack", "Melee attack", "1d20", deed + [("Str", m["strength"])] + augur_part("melee_attack"),
        note=(f"{int(c.get('first_level_luck_mod', 0)):+d} more with {lucky_w}" if lucky_parts else ""))
    add("missile_attack", "Missile attack", "1d20", deed + [("Agi", m["agility"])] + augur_part("missile_attack"),
        note=(f"{int(c.get('first_level_luck_mod', 0)):+d} more with {lucky_w}" if lucky_parts else ""))
    untrained = [w["name"] for w in v["weapons"] if not w["trained"]]
    if untrained:
        rolls[-2]["note"] = (rolls[-2]["note"] + " | " if rolls[-2]["note"] else "") + f"untrained: -1d with {', '.join(untrained)}"
        rolls[-1]["note"] = (rolls[-1]["note"] + " | " if rolls[-1]["note"] else "") + f"untrained: -1d with {', '.join(untrained)}"
    if klass == "elf":
        rolls.append({"key": "secret_doors", "label": "Detect secret doors", "total": _plus(4 + (amod if "secret_doors" in targets else 0)),
                      "parts": [("heightened senses", "+4")] + augur_part("secret_doors"), "note": "free check within 10 feet of a secret door"})
    add("melee_damage", "Melee damage", "weapon", ([("deed die", v["attack"][1:])] if v["deed_die"] else []) + [("Str", m["strength"])] + augur_part("melee_damage"))
    add("missile_damage", "Missile damage", "weapon", ([("deed die", v["attack"][1:])] if v["deed_die"] else []) + augur_part("missile_damage"),
        note="Str applies only to thrown weapons and slings at short range")
    add("initiative", "Initiative", "1d20", [("Agi", m["agility"])] + ([("warrior level", level)] if klass == "warrior" else []) + augur_part("initiative"),
        note="rolled on d16 while wielding a two-handed weapon" + (": that is the case now" if v["init_die"] == "d16" else ""))
    row = v["class_row"]
    for key, label, ab in (("reflex", "Reflex save", "agility"), ("fortitude", "Fortitude save", "stamina"), ("willpower", "Willpower save", "personality")):
        add(key, label, "1d20", [("class", _int(row.get({"reflex": "ref", "fortitude": "fort", "willpower": "will"}[key], "+0"))), (ABILITY_LABELS[ab], m[ab])] + augur_part(key))
    add("ac", "Armor Class", "10", [("Agi", m["agility"])] + ([(f"armor ({v['armor']['name']})", v["armor"]["ac"])] if v["armor"] else []) + ([("shield", 1)] if c.get("shield") else []) + augur_part("ac"))
    if v["spellcasting"].get("caster"):
        ab = CASTER_ABILITY[klass]
        armour_pen = [("armor check penalty", v["check_penalty"])] if klass in ("wizard", "elf") and v["check_penalty"] else []
        add("spell_check", "Spell check", v["action_dice"].split("+")[0], [("caster level", level), (ABILITY_LABELS[ab], m[ab])] + armour_pen + augur_part("spell_check"),
            note=("Luck (fixed) applies to " + c["lucky_spell"] if klass == "elf" and c.get("lucky_spell") else "") + (" | mercurial magic may change the die per spell" if klass in ("wizard", "elf") else ""))
        if klass in ("wizard", "elf"):
            add("mercurial", "Mercurial magic (when learning a spell)", "d%", [("Luck x10", m["luck"] * 10)])
            add("corruption", "Corruption roll", "as spell", [("Luck", m["luck"])] + augur_part("corruption"))
        if klass == "cleric":
            add("turn_unholy", "Turn unholy", "1d20", [("caster level", level), ("Per", m["personality"]), ("Luck", m["luck"])] + augur_part("turn_unholy"))
            add("lay_on_hands", "Lay on hands", "1d20", [("caster level", level), ("Per", m["personality"])] + augur_part("healing"))
    agi = v["effective"]["agility"]
    tw_agi = max(agi, 16) if klass == "halfling" and agi <= 17 else agi
    tw = two_weapon_row(content, tw_agi)
    if tw:
        note = tw["crits"]
        if klass == "halfling" and agi <= 17:
            note = "halfling: counts as Agility 16, crits and auto-hits on a natural 16 on either die, fumbles only when both dice show 1"
        rolls.append({"key": "two_weapon", "label": "Two-weapon fighting", "total": f"primary {tw['primary']}, off hand {tw['off_hand']}",
                      "parts": [("Agility", tw_agi)] + ([("halfling minimum", "16")] if tw_agi != agi else []), "note": note})
    if klass == "dwarf" and c.get("shield"):
        rolls.append({"key": "shield_bash", "label": "Shield bash (extra attack)", "total": f"1d14 {v['attack']} {_plus(m['strength'])}, 1d3 damage",
                      "parts": [("deed die", v["attack"][1:]), ("Str", _plus(m["strength"]))], "note": "one per round on top of the action dice; Mighty Deeds allowed"})
    if klass == "dwarf":
        rolls.append({"key": "underground", "label": "Detect underground construction", "total": _plus(level),
                      "parts": [("dwarf level", _plus(level))], "note": "traps, slanting passages, shifting walls; can smell gold and gems within 100'"})
    if klass == "thief" and v["thief_skills"]:
        bs = next((sk for sk in v["thief_skills"] if sk["skill"] == "Backstab"), None)
        if bs:
            rolls.append({"key": "backstab", "label": "Backstab attack", "total": f"melee attack {bs['value']}",
                          "parts": [("backstab bonus", bs["value"])], "note": f"target unaware or from behind; a hit is an automatic crit on table {v['crit_table']}; backstab weapons use their second damage"})
    add("crit", "Crit roll", v["crit_die"], [("Luck", m["luck"])] + augur_part("crit"),
        note=f"table {v['crit_table']}" + ("; the augur makes Luck count double" if "crit" in targets and amod else ""))
    add("fumble", "Fumble roll", v["fumble_die"], [("Luck (subtract)", -m["luck"])] + augur_part("fumble"),
        note="lower is better" + ("; the augur makes Luck count double" if "fumble" in targets and amod else ""))
    add("skill_checks", "Skill checks", "1d20", [("ability", "varies")] + augur_part("skill_checks"), note="trained skills use d20, untrained d10")
    if klass == "thief":
        add("thief_skills", "Thief skills", "1d20", [("skill bonus", "see table"), ("ability", "varies")] + augur_part("thief_skills"),
            note=f"burning Luck adds {v['luck_die']} per point")
    if "hp_per_level" in targets and amod:
        rolls.append({"key": "hp_per_level", "label": "Hit points per level", "total": f"{_plus(amod)} per level", "parts": [(f"birth augur ({aug['augur']})", _plus(amod))], "note": "add when rolling hit points"})
    if "speed" in targets and amod:
        rolls.append({"key": "speed", "label": "Speed", "total": f"{_plus(amod * 5)}'", "parts": [(f"birth augur ({aug['augur']})", f"{_plus(amod)} x 5'")], "note": "already included in the speed shown"})
    if "languages" in targets and amod:
        rolls.append({"key": "languages", "label": "Languages", "total": _plus(amod), "parts": [(f"birth augur ({aug['augur']})", _plus(amod))], "note": "already included in the languages allowed"})
    for key in ("unarmed_attack", "mounted_attack", "starting_weapon", "traps", "secret_doors", "spell_damage", "save_traps", "save_poison", "healing"):
        if key in targets and amod:
            rolls.append({"key": key, "label": aug["applies_to"], "total": _plus(amod), "parts": [(f"birth augur ({aug['augur']})", _plus(amod))], "note": "situational"})
    return rolls


def language_slots(character: dict, content: dict) -> dict:
    """How many languages the character knows and which come automatically
    (p. 20 and Appendix L). Common for all; one per point of Intelligence
    modifier, set at 0 level; the racial tongue for demi-humans with Int 8+. At
    1st level thieves add the cant, demi-humans one more language, and wizards
    a second language per point of Intelligence modifier. Int 7 or less speaks
    only Common."""
    klass, race = character.get("class"), race_of(character)
    score = int(character["abilities"]["intelligence"])
    bonus = max(0, ability_mod(content, score))
    aug = character["birth_augur"]
    aug_mod = int(aug["modifier"]) if "languages" in augur_targets(aug["applies_to"]) else 0
    column = klass or race or "zero"
    if score <= 7:
        return {"total": 1, "automatic": ["Common"], "to_roll": 0, "column": column, "literate": score > 5,
                "note": "Intelligence 7 or less: speaks only Common" + ("" if score > 5 else ", and cannot read or write") + "."}
    automatic = ["Common"] + ([RACE_LANGUAGE[race]] if race else []) + (["Thieves' cant"] if klass == "thief" else [])
    rolled = bonus + (1 if klass in RACE_CLASS.values() else 0) + (bonus if klass == "wizard" else 0)
    total = max(1, len(automatic) + rolled + aug_mod)
    return {"total": total, "automatic": automatic, "to_roll": max(0, total - len(automatic)), "column": column,
            "literate": True, "note": ""}


def language_for_roll(content: dict, column: str, roll: int, alignment: str) -> str | None:
    """Appendix L result for a d% roll in a class column; None means roll again."""
    tongue = {"lawful": "Law", "neutral": "Neutrality", "chaotic": "Chaos"}[alignment]
    for row in content.get("languages", []):
        span = row["ranges"].get(column)
        if span and span[0] <= int(roll) <= span[1]:
            if row["language"] == "Alignment tongue":
                return tongue
            return None if row["language"] == tongue else row["language"]
    return None


ZERO_SCORE = {"strength": "cannot move", "agility": "cannot move", "stamina": "faints and stays unconscious",
              "personality": "is a babbling idiot", "intelligence": "is a babbling idiot",
              "luck": "suffers constant, bizarre mishaps and can accomplish nothing"}


def sheet_warnings(character: dict, content: dict, v: dict) -> tuple[list[str], list[str]]:
    """Rule consequences the numbers alone do not show, and choices still open."""
    c, klass, level = character, character.get("class"), int(character["level"])
    warn, todo = [], []
    eff, natural = v["effective"], c["abilities"]
    held = [w for w in v["weapons"]]
    two_handed = [w["name"] for w in held if w["two_handed"]]
    for a in ABILITIES:
        if eff[a] <= 0:
            warn.append(f"{a.capitalize()} is at 0: the character {ZERO_SCORE[a]} (p. 96).")
    if eff["strength"] <= 5 and held and c.get("shield"):
        warn.append("Strength 5 or less: can carry a weapon or a shield, not both (p. 18).")
    if eff["stamina"] <= 5:
        warn.append("Stamina 5 or less: double damage from all poisons and diseases (p. 18).")
    if not v["languages"]["literate"]:
        warn.append("Intelligence 5 or less: cannot read or write (p. 18).")
    if c.get("shield") and two_handed:
        warn.append(f"A shield cannot be used with a two-handed weapon ({', '.join(two_handed)}).")
    if c.get("shield") and len(held) > 1:
        warn.append("Fighting with two weapons rules out a shield (p. 95).")
    if level == 0 and int(c["hp_current"]) <= 0:
        warn.append("A 0-level character at 0 hit points is irrevocably dead. If allies reach the body within the hour: "
                    f"a Luck check (d20, {eff['luck']} or less) when it is rolled over may show the character only stunned (p. 93).")
    elif int(c["hp_current"]) <= 0:
        warn.append(f"At 0 hit points and bleeding out: healing within {level} round{'s' if level != 1 else ''} saves the character, "
                    "at the price of 1 point of Stamina for good and a terrible scar. After that the character is dead, unless "
                    f"allies reach the body within the hour and a Luck check (d20, {eff['luck']} or less) succeeds: then 1 hit point, "
                    "-4 to all rolls for an hour, and 1 point of Strength, Agility or Stamina lost for good (p. 93).")
    extra = v["class_extras"]
    if extra.get("iron_items"):
        warn.append(f"Iron burns an elf for 1 hp per day of contact: {', '.join(extra['iron_items'])}.")
    if extra.get("untrained_wielded"):
        warn.append(f"Untrained with {', '.join(extra['untrained_wielded'])}: attack one die lower (d16 instead of d20).")
    if klass in ("wizard", "elf") and v["check_penalty"]:
        warn.append(f"Armor check penalty {v['check_penalty']} applies to every spell check.")
    if v["spellcasting"].get("blocked"):
        warn.append(v["spellcasting"]["blocked"])
    if len(c.get("languages", [])) > v["languages"]["total"]:
        warn.append(f"{len(c['languages'])} languages listed, {v['languages']['total']} allowed. {v['languages']['note']}".strip())
    if klass == "thief" and not any("thieves" in i["name"].lower() and "tools" in i["name"].lower() for i in v["inventory"]):
        todo.append("Buy thieves' tools (25 gp): needed to pick locks, find and disable traps, climb, forge and handle poison.")
    if klass in ("warrior", "dwarf") and not c.get("lucky_weapon"):
        todo.append("Choose the lucky weapon: one specific weapon type, fixed for life.")
    if klass == "elf" and not c.get("lucky_spell") and int(c.get("first_level_luck_mod", 0)) > 0:  # "may choose" (p. 58): no duty to take a penalty
        todo.append("Choose the one spell that gets the 1st-level Luck modifier, fixed for life.")
    if klass == "cleric" and not c.get("deity"):
        todo.append(f"Choose a god of {c.get('alignment', 'neutral')} alignment.")
    spell = v["spellcasting"]
    if spell.get("caster") and not spell.get("blocked"):
        if spell["kind"] == "wizard" and spell["used"] < spell["total"]:
            todo.append(f"Learn {spell['total'] - spell['used']} more spell(s): {spell['used']} of {spell['total']} known.")
        if spell["kind"] == "cleric":
            for lvl, n in spell["per_level"].items():
                got = sum(1 for sp in v["spells"] if sp.get("level") == lvl)
                if lvl <= spell["max_level"] and got < n:
                    todo.append(f"Choose {n - got} more level {lvl} spell(s).")
        if klass in ("wizard", "elf"):
            unrolled = [sp["name"] for sp in v["spells"] if not sp.get("mercurial_roll")]
            if unrolled:
                todo.append(f"Roll mercurial magic for: {', '.join(unrolled)}.")
            twice = [sp["name"] for sp in v["spells"] if sp.get("mercurial_roll") in ROLL_AGAIN_TWICE and len(sp.get("mercurial_more") or []) != 2]
            if twice:
                todo.append(f"Mercurial magic said 'roll again twice'; the two further rolls are missing for: {', '.join(twice)}.")
    missing = v["languages"]["total"] - len(c.get("languages", []))
    if missing > 0:
        todo.append(f"Add {missing} more language(s): roll d% in the {v['languages']['column']} column of Appendix L.")
    if v["can_level"]:
        todo.append("Enough XP for the next level." if level else "10 XP reached: choose a class.")
    return warn, todo


def derive(character: dict, content: dict | None = None) -> dict:
    """Everything the sheet shows that is computed rather than stored."""
    content = content or load_content()
    inventory = ensure_inventory(character)
    ab = effective_abilities(character)
    damage = {a: int((character.get("ability_damage") or {}).get(a, 0)) for a in ABILITIES}
    mods = {a: ability_mod(content, ab[a]) for a in ABILITIES}
    klass, level = character.get("class"), int(character["level"])
    row = class_row(content, klass, level) or {}
    armor = armor_row(content, character.get("armor"))
    shield = bool(character.get("shield"))
    aug_targets = augur_targets(character["birth_augur"]["applies_to"]); aug_mod = int(character["birth_augur"]["modifier"])
    aug = lambda key: aug_mod if key in aug_targets else 0
    ac = 10 + mods["agility"] + (armor["ac"] if armor else 0) + (1 if shield else 0) + aug("ac")
    check_penalty = (armor["check_penalty"] if armor else 0) + (-1 if shield else 0)
    speed = BASE_SPEED.get(klass or race_of(character) or "", 30) + (armor["speed_penalty"] if armor else 0) + aug("speed") * 5
    # Table 3-3: the worn armor and the shield each name a fumble die; the larger one counts.
    fumble_dice = [armor["fumble_die"] if armor and armor["fumble_die"] else "d4"] + (["d8"] if shield else [])
    fumble_die = max(fumble_dice, key=DICE_CHAIN.index)
    attack = row.get("attack", "+0")
    deed = attack.startswith("+d")
    saves = {"reflex": _int(row.get("ref", "+0")) + mods["agility"] + aug("reflex"),
             "fortitude": _int(row.get("fort", "+0")) + mods["stamina"] + aug("fortitude"),
             "willpower": _int(row.get("will", "+0")) + mods["personality"] + aug("willpower")}
    initiative = mods["agility"] + (level if klass == "warrior" else 0) + aug("initiative")
    title = None
    if klass and level >= 1:
        t = content["class_titles"].get(klass, {}).get(str(min(level, 5)), {})
        title = t.get(character.get("alignment", "neutral")) or t.get("all")
    weapons = []
    trained = trained_weapons(character, content)
    for held in [i for i in inventory if i["kind"] == "weapon" and i.get("equipped")]:
        name = held["name"]
        w = weapon_row(content, name)
        is_trained = trained is None or (w is not None and w["name"] in trained) or (w is None)
        ammo = ammo_count(character, w["name"]) if w else None
        dmg = w["damage"] if w else "?"
        backstab = None
        if w and "/" in dmg:
            dmg, second = dmg.split("/", 1)
            if w.get("backstab_weapon") and klass == "thief":
                backstab = second.rstrip("*")
        weapons.append({"name": name, "damage": dmg, "backstab_damage": backstab, "range": w["range"] if w else None,
                        "trained": is_trained, "ammo": ammo, "ammo_kind": AMMO_FOR.get(w["name"]) if w else None,
                        "qty": int(held.get("qty", 1)), "mithril": bool(held.get("mithril")),
                        "iron": (klass == "elf" or race_of(character) == "elf") and not held.get("mithril") and w is not None
                                and w["name"] not in ("Club", "Staff", "Sling", "Blackjack", "Garrote", "Blowgun", "Dart", "Shortbow", "Longbow"),
                        "two_handed": bool(w and w["two_handed"]),
                        "melee_bonus": (attack if deed else _plus(_int(attack) + mods["strength"])) + (
                            f"{_plus(mods['strength'])} Str" if deed else ""),
                        "missile_bonus": (attack if deed else _plus(_int(attack) + mods["agility"])) + (
                            f"{_plus(mods['agility'])} Agi" if deed else "")})
    thief_skills = None
    if klass == "thief":
        table = content["thief_skills"][character.get("alignment", "neutral")]
        thief_skills = []
        for skill, values in table.items():
            v = values[min(level, MAX_LEVEL) - 1]
            gov = THIEF_SKILL_ABILITY.get(skill)
            aug_here = aug_mod if ("thief_skills" in aug_targets or ("traps" in aug_targets and "Trap" in skill)) else 0
            armor_here = check_penalty if skill in ARMOR_PENALTY_SKILLS else 0
            parts = ([("table", v)] + ([(ABILITY_LABELS[gov], _plus(mods[gov]))] if gov else [])
                     + ([("birth augur", _plus(aug_here))] if aug_here else []) + ([("armor check penalty", _plus(armor_here))] if armor_here else []))
            if v.startswith("d"):
                thief_skills.append({"skill": skill, "value": v, "ability": gov,
                                     "parts": [("die", v), (ABILITY_LABELS[gov], _plus(mods[gov]))], "bonus": _plus(mods[gov])})
            else:
                thief_skills.append({"skill": skill, "value": _plus(_int(v) + (mods[gov] if gov else 0) + aug_here + armor_here),
                                     "ability": gov, "parts": parts})
    if klass == "halfling" and row.get("sneak_hide"):
        aug_here = aug_mod if "thief_skills" in aug_targets else 0
        thief_skills = []
        for sk in ("Sneak Silently", "Hide in Shadows"):
            armor_here = check_penalty if sk in ARMOR_PENALTY_SKILLS else 0
            thief_skills.append({"skill": sk, "value": _plus(_int(row["sneak_hide"]) + mods["agility"] + aug_here + armor_here), "ability": "agility",
                                 "parts": [("table", row["sneak_hide"]), ("Agi", _plus(mods["agility"]))] + ([("birth augur", _plus(aug_here))] if aug_here else [])
                                          + ([("armor check penalty", _plus(armor_here))] if armor_here else [])})
    allowance = spell_allowance(character, content) if klass else {"caster": False}
    if allowance.get("caster"):
        allowance["check_bonus"] += aug("spell_check") + (check_penalty if klass in ("wizard", "elf") else 0)
        allowance["used"] = spell_slots_used(character, character.get("spells", []))
    known = list(character.get("spells", []))
    for free in free_spells(character):
        if free not in known:
            known.insert(0, free)
    details = character.get("spell_details", {})
    spells = []
    for n in known:
        sp = dict(find_spell(content, n, klass) or {"name": n})
        sp["free"] = n in free_spells(character)
        sp["mercurial_roll"] = (details.get(n) or {}).get("mercurial")
        sp["mercurial"] = mercurial_entry(content, sp["mercurial_roll"]) if klass in ("wizard", "elf") else None
        more = (details.get(n) or {}).get("mercurial_more") or []
        if sp["mercurial"] and sp["mercurial_roll"] in ROLL_AGAIN_TWICE:  # "roll again twice": the spell has both further effects
            sp["mercurial_more"] = more
            rows = [mercurial_entry(content, r) for r in more]
            if len(rows) == 2 and all(rows):
                sp["mercurial"] = {**sp["mercurial"], "text": f"Both of these. ({more[0]}) {rows[0]['text']} ({more[1]}) {rows[1]['text']}"}
        sp["lucky"] = klass == "elf" and character.get("lucky_spell") == n
        spells.append(sp)
    xp = content["xp_thresholds"]
    next_level_xp = xp.get(str(level + 1)) if level < MAX_LEVEL else None
    out = {
        "mods": mods, "mods_text": {a: _plus(m) for a, m in mods.items()}, "effective": ab, "ability_damage": damage,
        "class_row": row, "hit_die": HIT_DIE.get(klass) if klass else 4, "race": race_of(character),
        "ac": ac, "check_penalty": check_penalty, "speed": speed, "fumble_die": fumble_die,
        "attack": attack, "deed_die": deed, "saves": saves, "saves_text": {k: _plus(v) for k, v in saves.items()},
        "initiative": _plus(initiative), "crit_die": row.get("crit_die", "1d4"), "crit_table": row.get("crit_table", "I"),
        "init_die": "d16" if any(w["two_handed"] for w in weapons) else "d20",
        "action_dice": row.get("action_dice", "1d20"), "threat_range": row.get("threat_range"),
        "luck_die": row.get("luck_die"), "sneak_hide": row.get("sneak_hide"), "title": title,
        "lucky_roll": f"{character['birth_augur']['applies_to']} ({_plus(character['birth_augur']['modifier'])})",
        "weapons": weapons, "armor": armor, "thief_skills": thief_skills, "spellcasting": allowance,
        "spells": spells, "languages": language_slots(character, content),
        "augur_targets": sorted(aug_targets), "augur_effect": augur_effect(character),
        "inventory": [{**i, "cost_cp": cost_in_cp(i.get("cost")), "row": weapon_row(content, i["name"]) if i["kind"] == "weapon" else armor_row(content, i["name"]) if i["kind"] in ("armor", "shield") else None} for i in inventory],
        "coins_cp": coins_total_cp(character["coins"]),
        "next_level_xp": next_level_xp, "can_level": level < MAX_LEVEL and (next_level_xp is None or int(character["xp"]) >= next_level_xp),
        "prose": content["class_prose"].get(klass, {}) if klass else {},
        "class_choices": [c for c in CLASSES if (race_of(character) == c if c in RACE_CLASS.values() else not race_of(character))] if level == 0 else [],
    }
    out["rolls"] = roll_breakdowns(character, content, out)
    out["action"] = action_dice_info(character, out)
    out["languages_allowed"] = out["languages"]["total"]
    out["class_extras"] = class_extras(character, content, out)
    out["warnings"], out["todo"] = sheet_warnings(character, content, out)
    return out


def class_extras(character: dict, content: dict, v: dict) -> dict:
    """Second-order class rules the sheet surfaces as features, choices and tables."""
    c, klass = character, character.get("class")
    x: dict = {"tables": {}}
    if klass in ("warrior", "dwarf"):
        x["lucky_weapon"] = {"chosen": c.get("lucky_weapon"), "modifier": int(c.get("first_level_luck_mod", 0)),
                             "rule": "Luck modifier at 1st level applies to attack rolls with one specific weapon type, fixed forever."}
        x["tables"]["Mighty Deeds"] = None  # rendered from content["mighty_deeds"] separately
        if klass == "dwarf":
            x["shield_bash"] = "Extra d14 action die for a shield bash each round, on top of the normal action dice."
    prose = content["class_prose"].get(klass or "", {})
    if klass == "elf":
        x["lucky_spell"] = {"chosen": c.get("lucky_spell"), "modifier": int(c.get("first_level_luck_mod", 0)),
                            "rule": "Luck modifier at 1st level applies to spell checks for one chosen spell, fixed forever."}
        x["free_spells"] = list(ELF_FREE_SPELLS)
        x["heightened_senses"] = "+4 to detect secret doors, and a free check when passing within 10 feet of one."
        x["immunities"] = prose.get("Immunities", "Immune to magical sleep and paralysis.")
        x["iron"] = "Cannot wear iron armor; prolonged contact with iron weapons or armor burns 1 hp per day. Iron items in the inventory are flagged."
    if klass == "elf" or race_of(c) == "elf":
        worn = next((i for i in c.get("inventory", []) if i["kind"] == "armor" and i.get("equipped")), None)
        iron_armor = worn and not worn.get("mithril") and worn["name"].lower() not in ("padded", "leather", "studded leather", "hide")
        x["iron_items"] = [w["name"] for w in v["weapons"] if w.get("iron")] + ([worn["name"]] if iron_armor else [])
    if klass == "halfling":
        x["two_weapon_rule"] = prose.get("Two-weapon Fighting", "")
        x["stealth"] = f"Sneak silently and hide in shadows at {v['sneak_hide']} plus Agility, like a thief."
        x["small"] = prose.get("Small size", "")
    if klass == "dwarf":
        x["sword_and_board"] = prose.get("Sword and board", "")
        x["underground"] = prose.get("Underground Skills", "")
    if klass == "thief":
        x["backstab"] = prose.get("Backstab", "")
        x["thieves_cant"] = prose.get("Thieves\u2019 Cant", "")
    if klass == "cleric" and content.get("deities"):
        x["deity_options"] = content["deities"].get(c.get("alignment", "neutral"), {})
    x["trained_weapons"] = trained_weapons(c, content)
    x["untrained_wielded"] = [w["name"] for w in v["weapons"] if not w["trained"]]
    corruption = content.get("corruption", {})
    if klass in ("wizard", "elf"):
        x["tables"]["Spellburn"] = content.get("spellburn")
        x["tables"]["Minor corruption"] = corruption.get("minor")
        x["tables"]["Major corruption"] = corruption.get("major")
        x["tables"]["Greater corruption"] = corruption.get("greater")
        x["tables"]["Generic spell misfire"] = content.get("generic_misfire")
    if klass == "cleric":
        rng = int(c.get("disapproval", 1))
        x["deity"] = c.get("deity") or ""
        x["disapproval"] = {"range": rng, "luck": v["mods"]["luck"],
                            "rule": f"A natural spell check roll of 1 to {rng} means disapproval, and every failed check today raises the range by 1 until spells are regained. "
                                    f"Then roll 1d4 per point of the natural roll (natural 3 = 3d4) reduced by Luck ({_plus(v['mods']['luck'])}) on the Disapproval table."}
        x["lay_on_hands"] = content.get("lay_on_hands", [])
        x["turn_unholy"] = content.get("turn_unholy", [])
        x["tables"]["Disapproval"] = content.get("disapproval")
    if klass == "thief":
        x["backstab"] = x.get("backstab", "")
        x["luck_die"] = {"die": v["luck_die"], "rule": f"Each point of Luck burned adds {v['luck_die']} instead of +1, and {int(c['level'])} point(s) of Luck come back each night."}
    if klass in ("wizard", "elf"):
        x["spellburn"] = "Before a spell check, burn points of Strength, Agility or Stamina for +1 each; the loss is temporary and heals 1 point per day (roll on the Spellburn table for how it manifests)."
        x["corruptions"] = list(c.get("corruptions") or [])
    x["luck_recovery"] = (f"{int(c['level'])} point(s) per night" if klass in ("thief", "halfling") else "only by the judge's grace or quest rewards")
    if klass == "halfling":
        x["good_luck_charm"] = "Burning Luck gives +2 per point, Luck recovers by level each night, and Luck can be spent on nearby allies."
        x["two_weapons"] = "Fights with two weapons as if Agility were 16 or higher; both attacks use the same die, chosen weapons must be small."
    x["tables"]["Fumbles"] = content.get("fumbles")
    return x



# ------------------------------------------------------------------ storage
def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "character"


def character_path(character_id: str) -> Path:
    if not re.fullmatch(r"[a-z0-9-]+", character_id):
        raise DCCError("Bad character id.")
    return CHARACTERS_DIR / f"{character_id}.json"


def new_character_id(name: str) -> str:
    CHARACTERS_DIR.mkdir(parents=True, exist_ok=True)
    base = _slug(name)
    candidate, n = base, 2
    while (CHARACTERS_DIR / f"{candidate}.json").exists():
        candidate = f"{base}-{n}"; n += 1
    return candidate


#: Set by a campaign that keeps packs elsewhere (westmarch: one items table). Needs read, write and forget.
INVENTORY_STORE = None


def save_character(character: dict, character_id: str) -> None:
    CHARACTERS_DIR.mkdir(parents=True, exist_ok=True)
    stored = INVENTORY_STORE.write(character_id, character) if INVENTORY_STORE else character
    character_path(character_id).write_text(json.dumps(stored, indent=1, ensure_ascii=False), encoding="utf-8")


def load_character(character_id: str) -> dict:
    character = json.loads(character_path(character_id).read_text(encoding="utf-8"))
    if INVENTORY_STORE:
        INVENTORY_STORE.read(character_id, character)
    return character


def list_characters() -> list[dict[str, Any]]:
    CHARACTERS_DIR.mkdir(parents=True, exist_ok=True)
    out = []
    for p in sorted(CHARACTERS_DIR.glob("*.json")):
        c = json.loads(p.read_text(encoding="utf-8"))
        out.append({"id": p.stem, "name": c.get("name"), "level": c.get("level", 0), "class": c.get("class"),
                    "occupation": (c.get("occupation") or {}).get("occupation"), "owner": c.get("owner"),
                    "hp": f"{c.get('hp_current')}/{c.get('hp_max')}", "alignment": c.get("alignment")})
    return out


# ------------------------------------------------------------------ printable sheets
SHEETS_DIR = CONTENT_PATH.parent / "sheets"


def _skill_key(skill: str) -> str:
    return re.sub(r"[^a-z]+", "_", skill.lower()).strip("_")


def sheet_values(character: dict, content: dict | None = None) -> dict:
    """Flat name -> text mapping for ``ttrpgtools.sheetfill`` layouts."""
    content = content or load_content()
    c, v = character, derive(character, content)
    ab, m = c["abilities"], v["mods"]
    plus = _plus
    vals = {
        "player": c.get("owner") or "", "created": c.get("created") or "", "name": c["name"],
        "birth_augur_short": v["augur_effect"].replace(", fixed for life", ""),
        "birth_augur": c["birth_augur"]["augur"], "lucky_roll": v["lucky_roll"],
        "str": ab["strength"], "agi": ab["agility"], "sta": ab["stamina"], "per": ab["personality"],
        "int": ab["intelligence"], "luck": c.get("luck_current", ab["luck"]), "luck_start": ab["luck"],
        "str_mod": plus(m["strength"]), "agi_mod": plus(m["agility"]), "sta_mod": plus(m["stamina"]),
        "per_mod": plus(m["personality"]), "int_mod": plus(m["intelligence"]), "luck_mod": plus(m["luck"]),
        "deed_die": v["attack"][1:] if v["deed_die"] else "", "attack": v["attack"],
        "ref": v["saves_text"]["reflex"], "fort": v["saves_text"]["fortitude"], "will": v["saves_text"]["willpower"],
        "luck_die": v["luck_die"] or "", "level": c["level"], "xp": c["xp"],
        "class": (c["class"] or "0-level").capitalize(), "title": v["title"] or "",
        "occupation": c["occupation"]["occupation"], "race": (v["race"] or "human").capitalize(),
        "alignment": c["alignment"].capitalize(), "patron": c.get("patron") or "",
        "languages": ", ".join(c.get("languages", [])),
        "ac": v["ac"], "armor": (c.get("armor") or "none") + (" + shield" if c.get("shield") else ""),
        "ac_bonus": plus((v["armor"]["ac"] if v["armor"] else 0) + (1 if c.get("shield") else 0)),
        "fumble_die": v["fumble_die"], "check_penalty": v["check_penalty"] or "0",
        "initiative": v["initiative"], "speed": f"{v['speed']}'", "crit": f"{v['crit_die']} / {v['crit_table']}",
        "action_dice": v["action_dice"], "hp": f"{c['hp_current']} / {c['hp_max']}", "hp_max": c["hp_max"],
        "coins": f"{c['coins']['gp']} gp, {c['coins']['sp']} sp, {c['coins']['cp']} cp",
        "equipment": "\n".join(c.get("equipment", [])), "notes": c.get("notes", ""),
        "spells": "\n".join(f"L{s.get('level', '?')} {s['name']}" for s in v["spells"]),
        "other_skill1": f"{c['occupation']['occupation']} (occupation)", "other_skill1_die": "1d20", "other_skill1_bonus": "",
        "cp": c["coins"]["cp"], "sp": c["coins"]["sp"], "gp": c["coins"]["gp"], "ep": "", "pp": "",
        "equipment_all": "\n".join([w for w in c.get("weapons", [])] + ([c["armor"]] if c.get("armor") else []) +
                                   (["Shield"] if c.get("shield") else []) + list(c.get("equipment", []))),
        "history_text": "; ".join(
            f"L{h['level']} {h['class']} (hp +{h['hp_gained']})" if h.get("event") == "level" else f"0-level {c['occupation']['occupation']}, hp roll {h.get('hp_roll')}"
            for h in c.get("history", [])),
    }
    for n, w in enumerate(v["weapons"][:4], start=1):
        vals[f"weapon{n}_name"] = w["name"]
        vals[f"weapon{n}_hit"] = w["melee_bonus"] if not w["range"] else w["missile_bonus"]
        vals[f"weapon{n}_dmg"] = w["damage"]
        vals[f"weapon{n}_notes"] = w["range"] or ("2h" if w["two_handed"] else "")
    common = {"balancing": m["agility"], "breaking_doors": m["strength"], "climbing": max(m["strength"], m["agility"]),
              "listening": m["luck"], "searching": m["intelligence"], "sneaking": m["agility"]}
    for k, mod in common.items():
        vals[k], vals[f"{k}_die"] = plus(mod), v["action_dice"].split("+")[0]
    for sk in v["thief_skills"] or []:
        key = _skill_key(sk["skill"])
        if sk["value"].startswith("d"):
            vals[f"thief_{key}_die"], vals[f"thief_{key}"] = sk["value"], ""
        else:
            vals[f"thief_{key}_die"], vals[f"thief_{key}"] = "1d20", sk["value"]
    features = []
    prose = v["prose"]
    for k in ("Attack modifier", "Critical hits", "Magic", "Turn unholy", "Lay on hands", "Infravision", "Stealth",
              "Good luck charm", "Heightened Senses", "Two weapons", "Backstab", "Sneak silently", "Thieves\u2019 Cant",
              "Slow", "Small size", "Luck", "Initiative", "Familiars", "Divine aid"):
        if k in prose:
            features.append(k)
    vals["class_features"] = ", ".join(features)
    racial = [k for k in ("Infravision", "Slow", "Small size", "Stealth", "Good luck charm", "Heightened Senses") if k in prose]
    vals["racial_features"] = "; ".join(f"{k}: {prose[k][:90]}" for k in racial)
    return vals
