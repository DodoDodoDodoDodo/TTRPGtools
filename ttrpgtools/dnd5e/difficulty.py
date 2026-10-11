"""Encounter difficulty, 2014 rules.

Two ratings side by side:

1. The official ones: DMG 2014 XP thresholds with the count multiplier, and the
   Lazy Encounter Benchmark (Sly Flourish). Both look at CR only.
2. A duel estimate from the stat blocks: an expected-value round-by-round fight.
   The party focuses monsters down in threat order, every living monster deals
   its expected damage, hit chances come from the real AC, attack bonuses and
   save DCs. No dice and no multiplier table: six goblins are dangerous because
   six goblins attack, until they stop.

Every number the estimate uses is returned so the page can show the reasoning.
PC damage is the weak input: it is a per-level baseline unless the PC carries
its own ``dpr``.
"""

from __future__ import annotations

import math
import re
from typing import Any

from .statblock import dice_average

# ------------------------------------------------------------------ DMG 2014 tables
#: level -> (easy, medium, hard, deadly, adventuring day)
XP_THRESHOLDS = {
    1: (25, 50, 75, 100, 300), 2: (50, 100, 150, 200, 600), 3: (75, 150, 225, 400, 1200),
    4: (125, 250, 375, 500, 1700), 5: (250, 500, 750, 1100, 3500), 6: (300, 600, 900, 1400, 4000),
    7: (350, 750, 1100, 1700, 5000), 8: (450, 900, 1400, 2100, 6000), 9: (550, 1100, 1600, 2400, 7500),
    10: (600, 1200, 1900, 2800, 9000), 11: (800, 1600, 2400, 3600, 10500), 12: (1000, 2000, 3000, 4500, 11500),
    13: (1100, 2200, 3400, 5100, 13500), 14: (1250, 2500, 3800, 5700, 15000),
    15: (1400, 2800, 4300, 6400, 18000), 16: (1600, 3200, 4800, 7200, 20000),
    17: (2000, 3900, 5900, 8800, 25000), 18: (2100, 4200, 6300, 9500, 27000),
    19: (2400, 4900, 7300, 10900, 30000), 20: (2800, 5700, 8500, 12700, 40000),
}
MULTIPLIER_STEPS = [0.5, 1, 1.5, 2, 2.5, 3, 4, 5]

#: DMG "Monster Statistics by Challenge Rating": cr -> (ac, hp max, attack bonus, dpr max, save dc)
CR_STATS: dict[float, tuple[int, int, int, int, int]] = {
    0: (13, 6, 3, 1, 13), 0.125: (13, 35, 3, 3, 13), 0.25: (13, 49, 3, 5, 13), 0.5: (13, 70, 3, 8, 13),
    1: (13, 85, 3, 14, 13), 2: (13, 100, 3, 20, 13), 3: (13, 115, 4, 26, 13), 4: (14, 130, 5, 32, 14),
    5: (15, 145, 6, 38, 15), 6: (15, 160, 6, 44, 15), 7: (15, 175, 6, 50, 15), 8: (16, 190, 7, 56, 16),
    9: (16, 205, 7, 62, 16), 10: (17, 220, 7, 68, 16), 11: (17, 235, 8, 74, 17), 12: (17, 250, 8, 80, 17),
    13: (18, 265, 8, 86, 18), 14: (18, 280, 8, 92, 18), 15: (18, 295, 8, 98, 18), 16: (18, 310, 9, 104, 18),
    17: (19, 325, 10, 110, 19), 18: (19, 340, 10, 116, 19), 19: (19, 355, 10, 122, 19),
    20: (19, 400, 10, 140, 19), 21: (19, 445, 11, 158, 20), 22: (19, 490, 11, 176, 20),
    23: (19, 535, 11, 194, 20), 24: (19, 580, 12, 212, 21), 25: (19, 625, 12, 230, 21),
    26: (19, 670, 12, 248, 21), 27: (19, 715, 13, 266, 22), 28: (19, 760, 13, 284, 22),
    29: (19, 805, 13, 302, 22), 30: (19, 850, 14, 320, 23),
}
CR_ORDER = sorted(CR_STATS)

#: DMG spell damage by slot level, one target (used when a caster's spells are only names).
SPELL_DAMAGE = {1: 11, 2: 16, 3: 27, 4: 33, 5: 44, 6: 55, 7: 60, 8: 66, 9: 82}

# ------------------------------------------------------------------ PC baselines
#: Damage per round if every attack hits, by level. Reference: a weapon user with
#: Extra Attack and modest resource use. Calibration constant, not a rule.
PC_DAMAGE = {1: 9, 2: 10, 3: 12, 4: 13, 5: 20, 6: 21, 7: 22, 8: 24, 9: 25, 10: 26, 11: 32, 12: 33,
             13: 34, 14: 35, 15: 36, 16: 37, 17: 42, 18: 43, 19: 44, 20: 48}
#: class -> (hit die, damage factor, share of damage that is area damage from level 5)
CLASSES = {
    "artificer": (8, 0.85, 0.1), "barbarian": (12, 1.1, 0.0), "bard": (8, 0.75, 0.2),
    "cleric": (8, 0.85, 0.3), "druid": (8, 0.85, 0.3), "fighter": (10, 1.1, 0.0),
    "monk": (8, 1.0, 0.0), "paladin": (10, 1.1, 0.0), "ranger": (10, 1.0, 0.1),
    "rogue": (8, 1.0, 0.0), "sorcerer": (6, 1.0, 0.5), "warlock": (8, 1.0, 0.3),
    "wizard": (6, 1.0, 0.5),
}
#: Staying power and output of a PC beyond the bare sheet: healing, control, magic
#: items, tactics. Multiplies PC damage and effective HP. Fitted by
#: scripts/calibrate_difficulty.py so that one official monster of CR = party level
#: costs four baseline PCs CALIBRATION_TARGET of their hit points (median).
PC_POWER = {1: 0.88, 2: 0.91, 3: 0.97, 4: 0.97, 5: 0.9, 6: 0.88, 7: 0.88, 8: 0.95, 9: 1.01, 10: 1.03,
            11: 1.0, 12: 0.99, 13: 1.04, 14: 1.09, 15: 1.17, 16: 1.18, 17: 1.2, 18: 1.14, 19: 1.2, 20: 1.25}
CALIBRATION_TARGET = 0.30
RESOURCE_FACTOR = {"fresh": 1.2, "normal": 1.0, "depleted": 0.8}
AOE_MAX_TARGETS = 4
AOE_EFFICIENCY = 0.75
MAX_ROUNDS = 30

BANDS = [(0.10, "Trivial"), (0.25, "Light"), (0.45, "Moderate"), (0.70, "Dangerous"), (math.inf, "Lethal")]

NUMBER_WORDS = {"one": 1, "once": 1, "a": 1, "an": 1, "two": 2, "twice": 2, "three": 3, "four": 4,
                "five": 5, "six": 6, "seven": 7, "eight": 8}


def proficiency(level_or_cr: float) -> int:
    return 2 + max(0, (math.ceil(level_or_cr) - 1)) // 4


def hit_chance(bonus: float, ac: float) -> float:
    return min(0.95, max(0.05, (21 + bonus - ac) / 20))


# ------------------------------------------------------------------ official ratings
def dmg_multiplier(monster_count: int, party_size: int) -> float:
    if monster_count <= 0:
        return 0.0
    index = 1 + sum(monster_count >= n for n in (2, 3, 7, 11, 15))
    if party_size < 3:
        index += 1
    elif party_size >= 6:
        index -= 1
    return MULTIPLIER_STEPS[index]


def official_rating(pc_levels: list[int], monsters: list[dict]) -> dict:
    """DMG 2014 rating and Lazy Encounter Benchmark. ``monsters`` need xp and cr_value."""
    levels = [min(20, max(1, int(lv))) for lv in pc_levels]
    thresholds = [sum(XP_THRESHOLDS[lv][i] for lv in levels) for i in range(4)]
    raw_xp = sum(m.get("xp") or 0 for m in monsters)
    # Every monster counts towards the multiplier, as on D&D Beyond. The DMG leaves
    # discounting weak stragglers to the DM's judgement.
    top_cr = max((m.get("cr_value") or 0 for m in monsters), default=0)
    multiplier = dmg_multiplier(len(monsters), len(levels))
    adjusted = round(raw_xp * multiplier)
    names = ["Trivial", "Easy", "Medium", "Hard", "Deadly"]
    tier = names[sum(adjusted >= t for t in thresholds)] if levels and monsters else "None"

    total_levels = sum(levels)
    average = total_levels / len(levels) if levels else 0
    fraction = 0.25 if average < 5 else 0.5 if average < 11 else 0.75 if average < 17 else 1.0
    cr_sum = sum(m.get("cr_value") or 0 for m in monsters)
    solo_cap = average if average < 5 else 1.5 * average
    return {
        "dmg": {
            "tier": tier, "raw_xp": raw_xp, "multiplier": multiplier, "adjusted_xp": adjusted,
            "thresholds": dict(zip(["easy", "medium", "hard", "deadly"], thresholds)),
            "day_budget": sum(XP_THRESHOLDS[lv][4] for lv in levels),
            "day_share": round(adjusted / max(1, sum(XP_THRESHOLDS[lv][4] for lv in levels)), 2),
        },
        "lazy": {
            "cr_sum": cr_sum, "limit": round(total_levels * fraction, 1),
            "over_limit": cr_sum > total_levels * fraction,
            "solo_cap": round(solo_cap, 1), "over_solo_cap": top_cr > solo_cap,
            "maybe_deadly": cr_sum > total_levels * fraction or top_cr > solo_cap,
        },
    }


# ------------------------------------------------------------------ monster profile
_HIT_SENTENCE = re.compile(r"Hit:\s*(.*?)(?:\.(?:\s|$)|$)", re.S)
_DAMAGE = re.compile(r"(\d+)\s*(?:\(([^)]*d[^)]*)\)\s*)?(?:[a-z]+\s+)?damage", re.I)
_TO_HIT = re.compile(r"([+-]\s*\d+)\s+to\s+hit", re.I)
_SAVE_DC = re.compile(r"DC\s*(\d+)", re.I)
_RIDER = re.compile(r"taking\s+(\d+)\s*(?:\([^)]*\)\s*)?(?:[a-z]+\s+)?damage\s+on\s+a\s+failed\s+save", re.I)
_AREA = re.compile(r"each creature|cone|-foot line|-foot-radius|-foot radius|-foot cube|within \d+ feet of", re.I)
_COST = re.compile(r"Costs\s+(\d+)\s+Actions", re.I)
_SPELL_DC = re.compile(r"spell save DC\s*(\d+)", re.I)
_WEAPON_RESIST = re.compile(r"bludgeoning|piercing|slashing|nonmagical", re.I)


def _best_alternative(sentence: str) -> float:
    """Damage of a Hit sentence: "plus" parts add up, "or" parts are alternatives."""
    best = 0.0
    for alternative in re.split(r",?\s+or\s+", sentence):
        total = sum(float(n) for n, _dice in _DAMAGE.findall(alternative))
        best = max(best, total)
    return best


def action_profile(entry: dict) -> dict | None:
    """What one use of an action deals: damage if it lands, and what it rolls against."""
    text = entry.get("text") or ""
    attacks = entry.get("attacks") or []
    to_hit_match = _TO_HIT.search(text)
    to_hit = int(to_hit_match.group(1).replace(" ", "")) if to_hit_match else next(
        (a["to_hit"] for a in attacks if a.get("to_hit") is not None), None)
    hit_sentence = _HIT_SENTENCE.search(text)

    if to_hit is not None:
        damage = _best_alternative(hit_sentence.group(1)) if hit_sentence else 0.0
        if not damage and attacks:
            damage = dice_average(attacks[0].get("dice"))
        # A failed-save rider lands about three times in four (fail, or half on success).
        rider = sum(float(n) for n in _RIDER.findall(text)) * 0.75
        if damage + rider <= 0:
            return None
        return {"name": entry["name"], "mode": "attack", "bonus": to_hit, "damage": damage + rider, "targets": 1}

    dc = _SAVE_DC.search(text)
    amounts = [float(n) for n, _dice in _DAMAGE.findall(text)]
    if dc and amounts:
        # DMG monster building: an area effect is assumed to catch two targets.
        return {"name": entry["name"], "mode": "save", "bonus": int(dc.group(1)), "damage": max(amounts[:2]),
                "targets": 2 if _AREA.search(text) else 1}
    if amounts:
        # Damage with neither attack roll nor save simply happens.
        return {"name": entry["name"], "mode": "auto", "bonus": 0, "damage": amounts[0],
                "targets": 2 if _AREA.search(text) else 1}
    if attacks and dice_average(attacks[0].get("dice")) > 0:
        return {"name": entry["name"], "mode": "auto", "bonus": 0,
                "damage": dice_average(attacks[0].get("dice")), "targets": 1}
    return None


def _clean(name: str) -> str:
    return re.sub(r"\s*\([^()]*\)", "", name).strip().lower()


def _find_action(word: str, profiles: dict[str, dict]) -> dict | None:
    word = word.strip().lower().rstrip("s")
    for name, profile in profiles.items():
        if name == word or name.rstrip("s") == word or word in name.split():
            return profile
    for name, profile in profiles.items():
        if word and (word in name or name in word):
            return profile
    return None


def multiattack_routine(text: str, profiles: dict[str, dict]) -> list[tuple[int, dict]]:
    """[(count, action profile)] from a Multiattack sentence. Unknown phrasing falls
    back to the stated number of attacks with the strongest attack."""
    if not profiles:
        return []
    attack_profiles = {n: p for n, p in profiles.items() if p["mode"] == "attack"} or profiles
    strongest = max(attack_profiles.values(), key=lambda p: p["damage"])
    low = text.lower()
    words = "|".join(NUMBER_WORDS)
    routine: list[tuple[int, dict]] = []
    for count, name in re.findall(
            rf"\b({words})\s+(?:attacks?\s+)?(?:with|using)\s+(?:its|his|her|their|the|a|an)?\s*([a-z' -]+?)"
            rf"(?=\s+attacks?\b|\s+and\b|\s+or\b|,|\.|$)", low):
        profile = _find_action(name, profiles)
        if profile:
            routine.append((NUMBER_WORDS[count], profile))
    if not routine:
        for count, name in re.findall(rf"\b({words})\s+([a-z' -]+?)\s+attacks?\b", low):
            profile = _find_action(name, profiles)
            if profile:
                routine.append((NUMBER_WORDS[count], profile))
    if routine:
        # "two with its spear or one with its bite": alternatives, keep the stronger half.
        if re.search(r"\bor\b", low) and len(routine) > 1:
            stated = re.search(rf"makes\s+({words})\b", low)
            limit = NUMBER_WORDS[stated.group(1)] if stated else None
            if limit and sum(c for c, _ in routine) > limit:
                routine.sort(key=lambda r: r[0] * r[1]["damage"], reverse=True)
                kept, used = [], 0
                for count, profile in routine:
                    if used + count <= limit:
                        kept.append((count, profile))
                        used += count
                routine = kept or routine[:1]
        extras = [p for n, p in profiles.items()
                  if p["mode"] == "save" and re.search(rf"can use (?:its |his |her )?{re.escape(n)}", low)]
        return routine + [(1, p) for p in extras if not p.get("limited")]
    stated = re.search(rf"(?:makes|attacks)\s+({words})\b", low)
    return [(NUMBER_WORDS[stated.group(1)] if stated else 2, strongest)]


def _expected(profile: dict, pc_ac: float, pc_save: float) -> float:
    if profile["mode"] == "attack":
        return profile["damage"] * hit_chance(profile["bonus"], pc_ac) * profile["targets"]
    if profile["mode"] == "save":
        fail = min(0.95, max(0.05, (profile["bonus"] - pc_save - 1) / 20))
        return profile["damage"] * (fail + (1 - fail) / 2) * profile["targets"]
    return profile["damage"] * profile["targets"]


def _nominal(profile: dict) -> float:
    return profile["damage"] * profile["targets"]


def monster_profile(monster: dict) -> dict:
    """Offence and defence of one monster, with the factors that produced them."""
    cr = monster.get("cr_value") or 0
    notes: list[str] = []

    profiles: dict[str, dict] = {}
    limited: list[dict] = []
    multiattack_text = ""
    for entry in monster.get("actions", []):
        if _clean(entry["name"]).startswith("multiattack"):
            multiattack_text = entry.get("text") or ""
            continue
        profile = action_profile(entry)
        if not profile:
            continue
        usage = entry.get("usage")
        if usage:
            if usage["kind"] == "recharge":
                profile["repeat"] = (7 - usage["recharge_min"]) / 6
            else:
                profile["repeat"] = 1.0 if usage["max"] >= 3 else 0.5 if usage["max"] == 2 else 0.0
            profile["limited"] = True
            limited.append(profile)
        else:
            profiles[_clean(entry["name"])] = profile

    if multiattack_text:
        routine = multiattack_routine(multiattack_text, profiles)
    elif profiles:
        routine = [(1, max(profiles.values(), key=_nominal))]
    else:
        routine = []

    slots = monster.get("spell_slots") or []
    spell_rounds: list[dict] = []
    if slots:
        text = " ".join(e.get("text") or "" for e in monster.get("traits", []) + monster.get("actions", []))
        dc = _SPELL_DC.search(text)
        levels = [lv for lv in range(len(slots), 0, -1) for _ in range(slots[lv - 1])][:3]
        spell_rounds = [{"name": f"level {lv} spell", "mode": "save", "bonus": int(dc.group(1)) if dc else 8 + proficiency(cr) + 3,
                         "damage": SPELL_DAMAGE[lv], "targets": 1} for lv in levels]
        if spell_rounds:
            notes.append("Spell damage is estimated from slot levels; the stat block lists spell names only.")

    legendary_uses = monster.get("legendary_uses") or 0
    legendary_best = None
    if legendary_uses:
        for entry in monster.get("legendary", []):
            if entry.get("intro"):
                continue
            profile = action_profile(entry)
            if not profile:
                referenced = re.search(r"makes (?:a|an|one) ([a-z' ]+?) attack", (entry.get("text") or "").lower())
                profile = _find_action(referenced.group(1), profiles) if referenced else None
            if not profile:
                continue
            cost = int(_COST.search(entry["name"]).group(1)) if _COST.search(entry["name"]) else 1
            candidate = dict(profile, cost=cost, source=entry["name"])
            if cost <= legendary_uses and (
                    legendary_best is None
                    or _nominal(candidate) / cost > _nominal(legendary_best) / legendary_best["cost"]):
                legendary_best = candidate

    # Villain actions come one per round, in their printed order.
    villain = [action_profile(entry) for entry in monster.get("villain", [])]

    def round_plan(round_number: int) -> list[tuple[float, dict]]:
        """[(weight, profile)] for one round: limited abilities first, then the routine."""
        base = [(float(count), profile) for count, profile in routine]
        base_value = sum(w * _nominal(p) for w, p in base)
        options = sorted(limited, key=_nominal, reverse=True)
        plan = base
        if options and _nominal(options[0]) > base_value:
            best = options[0]
            chance = 1.0 if round_number == 1 else best["repeat"]
            plan = [(chance, best)] + [(w * (1 - chance), p) for w, p in base]
        if spell_rounds and round_number <= len(spell_rounds):
            spell = spell_rounds[round_number - 1]
            if _nominal(spell) > sum(w * _nominal(p) for w, p in plan):
                plan = [(1.0, spell)]
        if legendary_best:
            plan = plan + [(legendary_uses // legendary_best["cost"], legendary_best)]
        if round_number <= len(villain) and villain[round_number - 1]:
            plan = plan + [(1.0, villain[round_number - 1])]
        return [(w, p) for w, p in plan if w > 0]

    plans = [round_plan(r) for r in (1, 2, 3)]
    nominal_rounds = [sum(w * _nominal(p) for w, p in plan) for plan in plans]
    dpr = sum(nominal_rounds) / 3
    bonuses = [(w * _nominal(p), p["bonus"] if p["mode"] == "attack" else p["bonus"] - 8)
               for plan in plans for w, p in plan if p["mode"] != "auto"]
    weight = sum(w for w, _ in bonuses)
    attack_bonus = sum(w * b for w, b in bonuses) / weight if weight else proficiency(cr) + 2
    if not routine and not limited and not spell_rounds:
        notes.append("No damaging action could be read from the stat block.")

    hp = monster.get("hp") or 1
    ehp = float(hp)
    factors: list[str] = []
    resist, immune = monster.get("resist") or "", monster.get("immune") or ""
    tier = 0 if cr < 5 else 1 if cr < 11 else 2 if cr < 17 else 3
    if _WEAPON_RESIST.search(immune):
        factor = (2, 2, 1.5, 1.25)[tier]
        ehp *= factor
        factors.append(f"weapon damage immunity x{factor}")
    elif _WEAPON_RESIST.search(resist):
        factor = (2, 1.5, 1.25, 1)[tier]
        if factor > 1:
            ehp *= factor
            factors.append(f"weapon damage resistance x{factor}")
    if _WEAPON_RESIST.search(monster.get("vulnerable") or ""):
        ehp *= 0.5
        factors.append("weapon damage vulnerability x0.5")
    for resource in monster.get("resources", []):
        if resource["kind"] == "legendary_resistance":
            bonus = resource["max"] * (10 if cr < 5 else 20 if cr < 11 else 30)
            ehp += bonus
            factors.append(f"legendary resistance +{bonus} HP")
    regeneration = next((e for e in monster.get("traits", []) if _clean(e["name"]) == "regeneration"), None)
    if regeneration:
        amount = re.search(r"regains (\d+) hit points", regeneration.get("text") or "")
        if amount:
            ehp += 3 * int(amount.group(1))
            factors.append(f"regeneration +{3 * int(amount.group(1))} HP")

    computed = computed_cr(ehp, monster.get("ac") or 10, dpr, attack_bonus)
    # Caster damage is a slot-level guess, too coarse to call a monster mis-rated.
    if monster.get("cr_value") is not None and dpr > 0 and not spell_rounds and abs(_cr_index(computed) - _cr_index(cr)) >= 3:
        direction = "stronger" if computed > cr else "weaker"
        notes.append(f"Stats read like CR {format_cr(computed)}, listed CR {format_cr(cr)}: {direction} than rated.")

    return {
        "name": monster.get("name"), "cr": cr, "hp": hp, "ehp": round(ehp, 1), "ac": monster.get("ac") or 10,
        "dpr": round(dpr, 1), "attack_bonus": round(attack_bonus, 1),
        "round_damage": [round(x, 1) for x in nominal_rounds], "max_round": round(max(nominal_rounds, default=0), 1),
        "plans": plans, "computed_cr": computed, "ehp_factors": factors, "notes": notes,
        "routine": [f"{int(c)}x {p['name']}" for c, p in routine],
        "legendary": legendary_best["source"] if legendary_best else None,
    }


def _cr_index(cr: float) -> int:
    return min(range(len(CR_ORDER)), key=lambda i: abs(CR_ORDER[i] - cr))


def format_cr(cr: float) -> str:
    return {0.125: "1/8", 0.25: "1/4", 0.5: "1/2"}.get(cr, str(int(cr)))


def computed_cr(ehp: float, ac: float, dpr: float, attack_bonus: float) -> float:
    """DMG monster-building method: defensive and offensive CR, averaged."""
    def lookup(value: float, column: int) -> int:
        return next((i for i, cr in enumerate(CR_ORDER) if value <= CR_STATS[cr][column]), len(CR_ORDER) - 1)

    def shifted(index: int, actual: float, expected_column: int) -> int:
        expected = CR_STATS[CR_ORDER[index]][expected_column]
        return min(len(CR_ORDER) - 1, max(0, index + int((actual - expected) / 2)))

    defensive = shifted(lookup(ehp, 1), ac, 0)
    offensive = shifted(lookup(dpr, 3), attack_bonus, 2)
    return CR_ORDER[round((defensive + offensive) / 2)]


# ------------------------------------------------------------------ party
def pc_profile(pc: dict, resources: str = "normal") -> dict:
    level = min(20, max(1, int(pc.get("level") or 1)))
    cls = (pc.get("cls") or "").strip().lower()
    hit_die, damage_factor, area_share = CLASSES.get(cls, (8, 1.0, 0.1))
    pb = proficiency(level)
    ability = 3 if level < 4 else 4 if level < 8 else 5
    default_hp = hit_die + 2 + (level - 1) * (hit_die // 2 + 1 + 2)
    power = PC_POWER[level] * RESOURCE_FACTOR.get(resources, 1.0)
    damage = (pc.get("dpr") or PC_DAMAGE[level] * damage_factor) * power
    hp = int(pc.get("hp") or default_hp)
    return {
        "name": pc.get("name") or "PC", "level": level, "cls": cls,
        "hp": hp, "ehp": hp * power, "power": round(power, 2), "ac": int(pc.get("ac") or 15),
        "attack_bonus": int(pc.get("attack_bonus") or pb + ability),
        # Halfway between a proficient and a non-proficient save.
        "save_bonus": float(pc.get("save_bonus") or 1 + pb / 2),
        "damage": float(damage),
        "area_share": area_share if level >= 5 else area_share / 2,
        "assumed": [k for k in ("hp", "ac", "dpr") if not pc.get(k)],
    }


# ------------------------------------------------------------------ the duel
def _simulate(party: list[dict], monsters: list[dict], focus: bool) -> dict:
    """Expected-value fight. ``focus``: monsters drop PCs one by one (weakest first);
    otherwise damage spreads evenly and nobody drops until the pool is empty."""
    pcs = [dict(p, left=float(p["ehp"])) for p in sorted(party, key=lambda p: p["ehp"])]
    foes = [dict(m, left=float(m["ehp"])) for m in monsters]
    # Kill order: most damage removed per point of effective HP.
    foes.sort(key=lambda m: m["dpr"] / max(1.0, m["ehp"]), reverse=True)
    party_hp = sum(p["ehp"] for p in pcs)
    rounds, dropped_at = 0, []

    while rounds < MAX_ROUNDS and any(m["left"] > 0 for m in foes) and any(p["left"] > 0 for p in pcs):
        rounds += 1
        standing = [p for p in pcs if p["left"] > 0]
        alive_before = [m for m in foes if m["left"] > 0]

        for pc in standing:
            # A PC that goes down this round still acted for about half of it.
            share = 1.0
            targets = [m for m in foes if m["left"] > 0]
            if not targets:
                break
            single = pc["damage"] * (1 - pc["area_share"]) * share
            area = pc["damage"] * pc["area_share"] * share
            if len(targets) == 1:
                single, area = single + area, 0.0
            for target in targets[:AOE_MAX_TARGETS]:
                target["left"] -= area * AOE_EFFICIENCY * hit_chance(pc["attack_bonus"], target["ac"])
            remaining = single
            for target in targets:
                if remaining <= 0:
                    break
                if target["left"] <= 0:
                    continue
                dealt = remaining * hit_chance(pc["attack_bonus"], target["ac"])
                used = min(dealt, target["left"])
                target["left"] -= used
                remaining -= used / hit_chance(pc["attack_bonus"], target["ac"])

        mean_ac = sum(p["ac"] for p in standing) / len(standing)
        mean_save = sum(p["save_bonus"] for p in standing) / len(standing)
        incoming = 0.0
        for monster in alive_before:
            plan = monster["plans"][min(rounds, 3) - 1]
            damage = sum(w * _expected(p, mean_ac, mean_save) for w, p in plan)
            # Initiative is a coin flip: a monster killed this round acted in half of it.
            incoming += damage * (1.0 if monster["left"] > 0 else 0.5)

        if focus:
            for pc in pcs:
                if incoming <= 0:
                    break
                if pc["left"] <= 0:
                    continue
                used = min(incoming, pc["left"])
                pc["left"] -= used
                incoming -= used
                if pc["left"] <= 0:
                    dropped_at.append({"name": pc["name"], "round": rounds})
        else:
            pool = sum(p["left"] for p in standing)
            fraction = min(1.0, incoming / pool) if pool else 1.0
            for pc in standing:
                pc["left"] -= pc["left"] * fraction

    left = sum(max(0.0, p["left"]) for p in pcs)
    return {
        "rounds": rounds,
        "party_wins": not any(m["left"] > 0 for m in foes),
        "hp_lost": round(1 - left / party_hp, 3) if party_hp else 1.0,
        "dropped": dropped_at,
        "monsters_left": sum(1 for m in foes if m["left"] > 0),
    }


def duel_rating(pcs: list[dict], monsters: list[dict], resources: str = "normal") -> dict:
    party = [pc_profile(pc, resources) for pc in pcs]
    profiles = [monster_profile(m) for m in monsters]
    if not party or not profiles:
        return {"band": "None", "party": party, "monsters": profiles, "warnings": [], "hp_lost": 0.0}

    spread = _simulate(party, profiles, focus=False)
    focus = _simulate(party, profiles, focus=True)
    hp_lost = (spread["hp_lost"] + focus["hp_lost"]) / 2
    party_wins = spread["party_wins"] and focus["party_wins"]
    band = next(name for limit, name in BANDS if hp_lost < limit) if party_wins else "Lethal"

    warnings: list[str] = []
    weakest = min(party, key=lambda p: p["hp"])
    for profile in {p["name"]: p for p in profiles}.values():
        if profile["max_round"] >= weakest["hp"]:
            warnings.append(f"{profile['name']} can deal {profile['max_round']:.0f} in one round; "
                            f"{weakest['name']} has {weakest['hp']} HP.")
        warnings.extend(f"{profile['name']}: {note}" for note in profile["notes"])
    if not party_wins:
        warnings.append("The party does not win this fight on expected values.")
    if focus["dropped"] and party_wins:
        first = focus["dropped"][0]
        warnings.append(f"Under focused attacks {first['name']} drops in round {first['round']} "
                        f"({len(focus['dropped'])} PC down by the end).")
    assumed = sorted({f"{p['name']}: {', '.join(p['assumed'])}" for p in party if p["assumed"]})
    monster_actions = sum(1 + (1 if p["legendary"] else 0) for p in profiles)

    return {
        "band": band, "hp_lost": round(hp_lost, 3),
        "hp_lost_range": [min(spread["hp_lost"], focus["hp_lost"]), max(spread["hp_lost"], focus["hp_lost"])],
        "rounds": round((spread["rounds"] + focus["rounds"]) / 2, 1),
        "party_wins": party_wins, "dropped": focus["dropped"],
        "action_ratio": f"{monster_actions} monster turns : {len(party)} PC turns",
        "party": party, "monsters": [{k: v for k, v in p.items() if k != "plans"} for p in profiles],
        "warnings": warnings, "assumed": assumed,
    }


def explain_disagreement(official: dict, duel: dict, monster_count: int) -> list[str]:
    """Why the DMG tier and the duel band differ, when they do."""
    order = {"None": 0, "Trivial": 0, "Easy": 1, "Light": 1, "Medium": 2, "Moderate": 2,
             "Hard": 3, "Dangerous": 3, "Deadly": 4, "Lethal": 4}
    gap = order[duel["band"]] - order[official["dmg"]["tier"]]
    if abs(gap) < 1:
        return []
    reasons = []
    harder = gap > 0
    for m in {p["name"]: p for p in duel["monsters"]}.values():
        expected = CR_STATS[CR_ORDER[_cr_index(m["cr"])]]
        if harder:
            if m["ac"] - expected[0] >= 2:
                reasons.append(f"{m['name']}: AC {m['ac']} is {m['ac'] - expected[0]} over the CR norm.")
            if m["dpr"] > expected[3] * 1.25:
                reasons.append(f"{m['name']}: {m['dpr']:.0f} damage per round, CR norm tops at {expected[3]}.")
            if m["ehp_factors"]:
                reasons.append(f"{m['name']}: {', '.join(m['ehp_factors'])}.")
        else:
            if expected[0] - m["ac"] >= 2:
                reasons.append(f"{m['name']}: AC {m['ac']} is {expected[0] - m['ac']} under the CR norm.")
            if m["dpr"] and m["dpr"] < expected[3] * 0.6:
                reasons.append(f"{m['name']}: {m['dpr']:.0f} damage per round is low for its CR.")
            if m["ehp"] < expected[1] * 0.6:
                reasons.append(f"{m['name']}: {m['ehp']:.0f} effective HP is low for its CR.")
    if monster_count > 1 and official["dmg"]["multiplier"] != 1:
        verb = "the duel finds the numbers matter more" if harder else "the duel counts their actual attacks, which weigh less"
        reasons.append(f"The DMG multiplies XP by {official['dmg']['multiplier']} for {monster_count} monsters; {verb}.")
    if duel.get("assumed"):
        reasons.append("PC values are baselines where not entered; real HP, AC and damage sharpen the estimate.")
    return reasons


def rate(pcs: list[dict], monsters: list[dict], resources: str = "normal") -> dict[str, Any]:
    official = official_rating([int(pc.get("level") or 1) for pc in pcs], monsters)
    duel = duel_rating(pcs, monsters, resources)
    return {"official": official, "duel": duel,
            "disagreement": explain_disagreement(official, duel, len(monsters)) if pcs and monsters else []}
