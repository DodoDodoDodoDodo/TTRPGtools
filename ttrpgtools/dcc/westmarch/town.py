"""The town: shops and inns with finite shelves and prices that move with the real calendar.

``data/westmarch/town.json`` holds what play has changed: quantities left,
judge edits, the sales log. The places themselves come from ``places.py`` and
are merged in on every load, so adding a place or an item there is enough.
Every read-modify-write runs under a file lock, so two players cannot buy the
same last item.

Price of an item on a day = usual price x place wave x item wave. Both waves
are sine curves ``1 + amplitude * sin(2 pi (day + phase) / period)``: the
place's is slow and shared by everything it sells, the item's is its own. A
curve nobody set is derived from the place or item name, so it is stable
without being stored.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import math
import os
import re
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from ttrpgtools import dcc
from . import clauses, economy, items, materials, places

TOWN_PATH = Path(os.environ.get("WESTMARCH_TOWN_FILE") or dcc.REPO_DIR / "data" / "westmarch" / "town.json")
LOG_LIMIT = 1000
KINDS = dcc.ITEM_KINDS + ["service"]
#: (period range in days, amplitude range) for curves derived from a name.
CURVE_RANGES = {"shop": ((18, 40), (0.10, 0.30)), "item": ((5, 17), (0.20, 0.60))}
NEWS_LIMIT = 12          # town talk kept; the page shows the newest NEWS_SHOWN
NEWS_SHOWN = 4
CHRONICLE_LIMIT = 300    # the admin's log of everything the nightly update did


class TownError(dcc.DCCError):
    """A town rule was violated (sold out, not enough coin, not the judge)."""


# ------------------------------------------------------------------ calendar
def today() -> date:
    return datetime.now(ZoneInfo(places.TIMEZONE)).date()


def hour() -> int:
    return datetime.now(ZoneInfo(places.TIMEZONE)).hour


def campaign_day(on: date | None = None) -> int:
    """Days run 1:1 with the real calendar; day 1 is the campaign's first date."""
    return ((on or today()) - places.EPOCH).days + 1


SYNODIC_MONTH = 29.530588853
MOON_NAMES = ["new", "waxing crescent", "first quarter", "waxing gibbous", "full", "waning gibbous", "last quarter", "waning crescent"]


def _moon_text(name: str, phase: str, to_full: int) -> str:
    when = "full tonight" if phase == "full" else f"full in {to_full} night{'s' if to_full != 1 else ''}"
    return f"{name}: {phase}, {when}"


def moon(on: date | None = None, which: str = "pale") -> dict:
    """One moon on a date: phase, nights until it is next full, and a sentence. The pale moon is the real one;
    the others run through the uneven cycles of places.MOONS."""
    spec = next(m for m in places.MOONS if m["id"] == which)
    on = on or today()
    if spec.get("real"):
        age = (((on - date(2000, 1, 6)).days - 0.76) % SYNODIC_MONTH)  # new moon of 2000-01-06, 18:14 UTC
        phase = MOON_NAMES[int((age / SYNODIC_MONTH) * 8 + 0.5) % 8]
        to_full = 0 if phase == "full" else round((SYNODIC_MONTH / 2 - age) % SYNODIC_MONTH)
        length = SYNODIC_MONTH
    else:
        length = sum(nights for _, nights in spec["cycle"])
        position = ((on - places.EPOCH).days + spec.get("offset", 0)) % length
        start, phase, full_start = 0, "", 0
        for name, nights in spec["cycle"]:
            if start <= position < start + nights:
                phase = name
            if name == "full":
                full_start = start
            start += nights
        to_full = 0 if phase == "full" else (full_start - position) % length
    return {"id": spec["id"], "name": spec["name"], "phase": phase, "days_to_full": to_full, "cycle_nights": round(length, 1),
            "blurb": spec["blurb"], "text": _moon_text(spec["name"], phase, to_full)}


def moons(on: date | None = None, full: bool = False) -> list[dict]:
    """All moons. Players get name, vibe and tonight's phase; the cycle and the countdown are for the admin (``full``)."""
    out = [moon(on, spec["id"]) for spec in places.MOONS]
    return out if full else [{"id": m["id"], "name": m["name"], "blurb": m["blurb"], "phase": m["phase"], "text": f"{m['name']}: {m['phase']}"} for m in out]


def moon_rule(character: dict) -> dict | None:
    """The moon's part in a fight, always the same for a character: one die better against the moon's enemies, one die
    worse against the kind it is weak against. None for a character without a moon."""
    spec = next((m for m in places.MOONS if m["id"] == character.get("moon")), None)
    if not spec or not spec.get("enemies"):
        return None
    text = f"Your moon is {spec['name']}. One die better (+1d) against {spec['enemies']}."
    if spec.get("weak"):
        text += f" One die worse (-1d) against {spec['weak']}."
    if spec.get("safe"):
        text += f" Saving throws are one die better (+1d) {spec['safe']}."
    return {"moon": spec["name"], "plus": spec["enemies"], "minus": spec.get("weak", ""), "text": text}


def full_forecast(which: str, on: date | None = None) -> dict:
    """When a moon is next full and for how many nights: {"in": nights from tonight (0 = tonight), "for": nights it lasts from then}."""
    on = on or today()
    first = next(n for n in range(0, 800) if moon(date.fromordinal(on.toordinal() + n), which)["phase"] == "full")
    lasts = next(n for n in range(1, 800) if moon(date.fromordinal(on.toordinal() + first + n), which)["phase"] != "full")
    return {"in": first, "for": lasts}


def ask_moon(state: dict, shop_id: str, character: dict, which: str, who: str | None = None) -> dict:
    """Pay the herb woman her copper and hear when one moon is next full. The coin goes into her till."""
    shop = _open(state, shop_id)
    price = dcc.cost_in_cp(shop.get("ask"))
    spec = next((m for m in places.MOONS if m["id"] == which), None)
    if not price or not spec:
        raise TownError("Ask about one of the three moons.")
    asked, lied = 0, False
    if clauses.clause_of(character) == "herb_week":   # the first question of a week is free; the second is paid for and answered wrongly
        week = campaign_day() // 7
        memory = character.get("herb") if (character.get("herb") or {}).get("week") == week else {"week": week, "asked": 0}
        asked = int(memory["asked"])
        character["herb"] = {"week": week, "asked": asked + 1}
        price, lied = (0, False) if asked == 0 else (price, asked == 1)
    character["coins"] = dcc.spend(character["coins"], price)
    shop["till"] = int(shop.get("till", 0)) + price
    seen = full_forecast(which)
    if lied:
        twist = int(hashlib.sha1(f"{character['name']}/{campaign_day()}/{which}".encode()).hexdigest(), 16)
        seen = {"in": seen["in"] + 2 + twist % 9, "for": 1 + (seen["for"] + 1 + twist // 9 % 3) % 6}
    nights = lambda n: f"{n} night{'s' if n != 1 else ''}"
    keeper = shop.get("keeper") or shop["name"]
    answer = (f"{keeper} does not look up. \"{spec['name']} is full tonight. It stays so for {nights(seen['for'])}, tonight counted.\"" if seen["in"] == 0
              else f"{keeper} counts on her fingers. \"{spec['name']} is full in {nights(seen['in'])}. It stays so for {nights(seen['for'])}.\"")
    sale = {"day": campaign_day(), "date": today().isoformat(), "at": datetime.now(ZoneInfo(places.TIMEZONE)).strftime("%H:%M"), "shop": shop["name"],
            "item": f"A word about {spec['name']}", "count": 1, "each_cp": price, "character": character["name"], "by": who, "answer": answer}
    state["log"] = (state["log"] + [sale])[-LOG_LIMIT:]
    return sale


# ------------------------------------------------------------------ things with a moon
MOON_KINDS = ("weapon", "armor", "shield", "gear", "mount")   # whatever could bear a name; not ammunition, not what villagers bring
GIFT_CHANCE = 0.5      # a maker of plain Luck: a gift on every second piece, a flaw on every second piece, each by itself
LUCK_SWAYS = 0.1       # per point of the maker's Luck modifier: more gifts and fewer flaws, or the other way round


def _lit(spec: dict, on: date) -> float:
    """How much of a moon's face is lit on a date, 0 (new) to 1 (full)."""
    if spec.get("real"):
        age = (((on - date(2000, 1, 6)).days - 0.76) % SYNODIC_MONTH)
        return (1 - math.cos(2 * math.pi * age / SYNODIC_MONTH)) / 2
    length = sum(nights for _, nights in spec["cycle"])
    position = ((on - places.EPOCH).days + spec.get("offset", 0)) % length
    start = 0
    for name, nights in spec["cycle"]:
        if name == "full":
            middle = start + nights / 2
        start += nights
    return (1 + math.cos(2 * math.pi * (position + 0.5 - middle) / length)) / 2


def moon_light(which: str, day: int) -> float:
    """How much of a moon's face is lit on a campaign day, 0 at the new moon, 1 at the middle of the full: a smooth wave."""
    spec = next(m for m in places.MOONS if m["id"] == which)
    return _lit(spec, date.fromordinal(places.EPOCH.toordinal() + day - 1))


def fullest_moon(on: date | None = None) -> str:
    """The moon that stands fullest on a date: the one things made that day belong to."""
    on = on or today()
    return max(places.MOONS, key=lambda spec: (moon(on, spec["id"])["phase"] == "full", _lit(spec, on)))["id"]   # a moon that is full beats one that is merely bright


def maker_luck(name: str) -> int:
    """A keeper's Luck: 3d6 of their own, the same every time, nudged out of the +0 band like everybody's."""
    import random
    from . import registry
    score = sum(random.Random(f"villager/{name}/maker").randint(1, 6) for _ in range(3)) if name else 10
    return (registry.nudged_luck(name) or score) if 9 <= score <= 12 and name else score


def _luck_mod(score: int) -> int:
    return -3 if score <= 3 else -2 if score <= 5 else -1 if score <= 8 else 0 if score <= 12 else 1 if score <= 15 else 2 if score <= 17 else 3


def roll_mark(day: int, maker: str, luck: int, seed: str) -> dict | None:
    """The mark of a thing that came into being on a day: the fullest moon's. It may carry one gift and one flaw from
    that moon's lists, each only a chance: even odds for a maker of plain Luck, shifted by a tenth per point of the
    maker's Luck modifier. Many things have a moon and nothing else. The same for the same seed."""
    import random
    on = date.fromordinal(places.EPOCH.toordinal() + day - 1)
    spec = next(m for m in places.MOONS if m["id"] == fullest_moon(on))
    if not spec.get("gifts") or not spec.get("flaws"):
        return None
    rng = random.Random(f"{seed}/mark")
    sway = LUCK_SWAYS * _luck_mod(luck)
    chance = lambda p: rng.random() < min(0.9, max(0.1, p))
    return {"moon": spec["id"], "luck": luck, "maker": maker, "day": day,
            "gifts": [rng.choice(spec["gifts"])] if chance(GIFT_CHANCE + sway) else [],
            "flaws": [rng.choice(spec["flaws"])] if chance(GIFT_CHANCE - sway) else []}


def make_mark(shop_id: str, shop: dict, line: dict, day: int, piece: int = 0) -> dict | None:
    """The mark of a piece a keeper made today, or None for what bears no name: ammunition, bundles, small goods."""
    if line["kind"] not in MOON_KINDS or int(line.get("units") or 1) != 1:
        return None
    maker = shop.get("keeper") or shop.get("name", "")
    return roll_mark(day, maker, maker_luck(maker), f"{shop_id}/{line['id']}/{day}/{piece}")


def mark_text(mark: dict, kind: str = "weapon") -> str:
    """What a mark does, as one line for the sheet."""
    name = next((m["name"] for m in places.MOONS if m["id"] == mark["moon"]), mark["moon"]).replace("The ", "")
    rolls = "Attacks with it" if kind == "weapon" else "Saving throws while it is worn" if kind in ("armor", "shield") else "Rolls made with it"
    parts = [f"{rolls} are one die better {gift}." for gift in mark.get("gifts", [])] + [f"{rolls} are one die worse {flaw}." for flaw in mark.get("flaws", [])]
    return " ".join([f"{name} make."] + parts)


def oldest_line(shop: dict) -> dict | None:
    """The shelf line that holds the oldest thing in a shop. A piece without a mark predates the marks, so the first
    line on the shelf that still has such a piece wins; once none is left, the line with the oldest mark."""
    lines = [line for line in shop["stock"] if line["kind"] != "service" and not line.get("gone") and int(line["qty"] or 0) > 0]
    plain = next((line for line in lines if int(line["qty"]) > len(line.get("made") or [])), None)
    if plain or not lines:
        return plain
    return min(lines, key=lambda line: min(int(m.get("day", 0)) for m in line["made"]))


def _take_pieces(line: dict, count: int, oldest: bool = False, before_day: int | None = None) -> list[dict]:
    """Choose which pieces of a shelf line a buyer gets and return their marks (the unmarked ones are not listed).
    Normally the keeper shows the fresh, marked pieces first. ``oldest``: the unmarked ones go first, they predate
    the marks, then the marked ones by age, and with ``before_day`` only those made on or before that day."""
    made = line.get("made") or []
    if not oldest:
        return [made.pop(0) for _ in range(min(count, len(made)))]
    plain = max(0, int(line["qty"] if line["qty"] is not None else count) - len(made))
    out, wanted = [], count - min(plain, count)
    made.sort(key=lambda m: int(m.get("day", 0)))
    while wanted > 0 and made and (before_day is None or int(made[0].get("day", 0)) <= before_day):
        out.append(made.pop(0)); wanted -= 1
    return out


def _marks_fit(line: dict) -> None:
    """A shelf line never holds more marks than pieces: the unmarked piece is the one that goes first."""
    made = line.get("made")
    if made is not None:
        del made[max(0, int(line["qty"] or 0)):]
        if not made:
            line.pop("made")


# ------------------------------------------------------------------ the augur trade
def _augur_point(shop: dict) -> int:
    point = dcc.cost_in_cp(shop.get("augur_point"))
    if not point:
        raise TownError(f"{shop['name']} does not deal in augurs.")
    return point


def augur_shelf(shop: dict) -> list[dict]:
    """The augurs she holds, each with what taking it costs: positive is what you pay, negative what she pays you."""
    point = dcc.cost_in_cp(shop.get("augur_point")) or 0
    out = []
    for index, a in enumerate(shop.get("augurs", [])):
        value = int(a["modifier"]) * point
        out.append({"index": index, "augur": a["augur"], "modifier": int(a["modifier"]), "effect": dcc.augur_effect({"birth_augur": {**a, "origin": "x"}}),
                    "from": a.get("from", ""), "price_cp": value, "price": coins_text(abs(value))})
    return out


def augur_offer(shop: dict, character: dict) -> dict | None:
    """What she does about this character's augur: {"value_cp": positive = she pays, negative = you pay, "text"}; None when there is none to sell."""
    augur = character.get("birth_augur") or {}
    if not int(augur.get("roll") or 0) or not shop.get("augur_point"):
        return None
    value = int(augur["modifier"]) * (dcc.cost_in_cp(shop["augur_point"]) or 0)
    return {"augur": augur["augur"], "modifier": int(augur["modifier"]), "value_cp": value, "value": coins_text(abs(value))}


def _finished(character: dict) -> None:
    if int(character.get("level") or 0) < 1:
        raise TownError(f"{character['name']} does not know their own augur yet. Finish the character first.")


def sell_augur(state: dict, shop_id: str, character: dict, who: str | None = None) -> dict:
    """Hand the birth augur over, modifier and all. She pays for a good one (if her till can), is paid to take a bad
    one, and takes a worthless one for nothing. Hit points go with it where the augur touched them. It goes on her
    shelf worn by one point."""
    shop = _open(state, shop_id)
    point = _augur_point(shop)
    _finished(character)
    augur = dict(character["birth_augur"])
    if not int(augur.get("roll") or 0):
        raise TownError(f"{character['name']} has no augur left to sell.")
    value = int(augur["modifier"]) * point
    if value > 0:
        if int(shop.get("till", 0)) < value:
            raise TownError(f"{shop['name']} has only {coins_text(int(shop.get('till', 0)))} and cannot pay {coins_text(value)} for it.")
        shop["till"] = int(shop["till"]) - value
        set_purse(character, dcc.coins_total_cp(character["coins"]) + value)
    elif value < 0:
        character["coins"] = dcc.spend(character["coins"], -value)   # raises before anything changes when the purse is too light
        shop["till"] = int(shop.get("till", 0)) + -value
    dcc.set_augur(character, dcc.load_content(), None)
    shop.setdefault("augurs", []).append({"roll": augur["roll"], "augur": augur["augur"], "applies_to": augur["applies_to"],
                                          "modifier": int(augur["modifier"]) - 1, "from": character["name"], "day": campaign_day()})
    told = (f"{coins_text(value)} for {augur['augur']}. It is hers now." if value > 0 else
            f"{coins_text(-value)} paid to be rid of {augur['augur']}. She wraps it in a cloth, carefully." if value < 0 else
            f"She takes {augur['augur']} for nothing. It was worth nothing.")
    sale = {"day": campaign_day(), "date": today().isoformat(), "at": datetime.now(ZoneInfo(places.TIMEZONE)).strftime("%H:%M"), "shop": shop["name"],
            "item": f"Augur sold: {augur['augur']} ({augur['modifier']:+d})", "count": -1, "each_cp": abs(value), "character": character["name"], "by": who,
            "answer": told}
    state["log"] = (state["log"] + [sale])[-LOG_LIMIT:]
    return sale


def take_augur(state: dict, shop_id: str, character: dict, index: int, who: str | None = None) -> dict:
    """Take one of her augurs. Only somebody without an augur can: one at a time. A good one costs, a bad one pays
    (if her till can). Hit points come with it where the augur touches them, for every level so far."""
    shop = _open(state, shop_id)
    point = _augur_point(shop)
    _finished(character)
    if int((character.get("birth_augur") or {}).get("roll") or 0):
        raise TownError(f"{character['name']} still has an augur. One at a time: sell the old one first.")
    shelf = shop.get("augurs", [])
    if not 0 <= int(index) < len(shelf):
        raise TownError("She has no such augur.")
    augur = shelf[int(index)]
    value = int(augur["modifier"]) * point
    if value > 0:
        character["coins"] = dcc.spend(character["coins"], value)
        shop["till"] = int(shop.get("till", 0)) + value
    elif value < 0:
        if int(shop.get("till", 0)) < -value:
            raise TownError(f"{shop['name']} has only {coins_text(int(shop.get('till', 0)))} and cannot pay {coins_text(-value)} to whoever takes it.")
        shop["till"] = int(shop["till"]) + value
        set_purse(character, dcc.coins_total_cp(character["coins"]) - value)
    shelf.pop(int(index))
    origin = f"bought from {shop.get('keeper') or shop['name']}" + (f", once {augur['from']}'s" if augur.get("from") else "")
    dcc.set_augur(character, dcc.load_content(), augur, int(augur["modifier"]), origin=origin)
    told = (f"{coins_text(value)} for {augur['augur']}. It itches at first." if value > 0 else
            f"She pays {coins_text(-value)} to whoever carries {augur['augur']} out of her house. That is {character['name']} now." if value < 0 else
            f"{augur['augur']}, for nothing. It does nothing.")
    sale = {"day": campaign_day(), "date": today().isoformat(), "at": datetime.now(ZoneInfo(places.TIMEZONE)).strftime("%H:%M"), "shop": shop["name"],
            "item": f"Augur taken: {augur['augur']} ({int(augur['modifier']):+d})", "count": 1, "each_cp": abs(value), "character": character["name"], "by": who,
            "answer": told}
    state["log"] = (state["log"] + [sale])[-LOG_LIMIT:]
    return sale


_NOTE_FILLER = {"the", "and", "but", "for", "with", "this", "that", "today", "again", "keep", "your", "you", "are", "was", "has", "have", "not", "all",
                "now", "from", "our", "out", "its", "their", "there", "very", "more", "some", "will", "can", "should", "must", "red", "full"}


def _note_words(text: str) -> tuple[set, set]:
    """What a line of the town note says, for telling whether two lines say the same: its content words (without
    endings or filler) and the numbers and names with digits in them, which must match for two lines to be the same."""
    tokens = re.findall(r"[a-z0-9]+", str(text).lower())
    words = {t.rstrip("s") if len(t) > 3 else t for t in tokens if t not in _NOTE_FILLER and (len(t) >= 3 or any(c.isdigit() for c in t))}
    return words, {t for t in words if any(c.isdigit() for c in t)}


def note_repeats(note: str, line: str) -> bool:
    """Does the town note already say this, in these words or in others? Two lines are the same when three quarters
    of the shorter one's content words are in the other and they agree on every number and every name with a digit in
    it ("shop1" is not "shop3"). A line with next to nothing in it (fewer than two content words) is not worth a place
    on the note and counts as a repeat."""
    new, new_digits = _note_words(line)
    if len(new) < 2:
        return True
    for old_line in str(note or "").split("\n"):
        old, old_digits = _note_words(old_line.split(":", 1)[-1])
        if old and new_digits == old_digits and min(len(new), len(old)) >= 2 and len(new & old) / min(len(new), len(old)) >= 0.75:
            return True
    return False


def _write_note(state: dict, key: str, words: int, who: str, line: str) -> str:
    line = " ".join(str(line or "").split()[:25])
    lines = [l for l in str(state.get(key) or "").split("\n") if l.strip()]
    if line and note_repeats("\n".join(lines), line):
        line = ""
    if line:
        lines.append(f"{who}: {line}")
        while len(lines) > 1 and sum(len(l.split()) for l in lines) > words:
            lines.pop(0)
    state[key] = "\n".join(lines)
    return state[key]


def town_note_write(state: dict, who: str, line: str) -> str:
    """Add one line to the REQUESTS part of the town note, the scrap of paper everyone shares: "Name: what they wrote". It holds about
    ``TOWN_NOTE_WORDS`` words; the oldest lines fall off the top. A line the note already says, in any words, is not written again. Returns the part."""
    return _write_note(state, "town_note", places.TOWN_NOTE_WORDS, who, line)


def flavour_lines(state: dict) -> str:
    """The TALK part: what villagers scribbled lately. A village that has none yet starts from ``places.FLAVOUR_SEED``."""
    if state.get("town_flavour") is None:
        return "\n".join(f"{who}: {line}" for who, line in places.FLAVOUR_SEED)
    return str(state["town_flavour"])


def flavour_write(state: dict, who: str, line: str) -> str:
    """One line of TALK (gossip, grumbles, jokes). The same rules as for requests, its own page of ``TOWN_FLAVOUR_WORDS`` words."""
    state["town_flavour"] = flavour_lines(state)
    return _write_note(state, "town_flavour", places.TOWN_FLAVOUR_WORDS, who, line)


def note_text(state: dict) -> str:
    """The whole town note as a model reads it: TALK, then REQUESTS."""
    return f"TALK (what villagers wrote lately):\n{flavour_lines(state)}\n\nREQUESTS (what the village asks for):\n{state.get('town_note') or ''}"


def closed_reason(shop: dict) -> str | None:
    """A place is closed while its keeper is not alive and present in the villagers register."""
    from . import registry
    if shop.get("away"):
        return "The caravan is not in town."
    keeper = shop.get("keeper") or ""
    if any(person["name"] == keeper for person in registry.living()):   # alive by this very name: open, though a dead "X" is a prefix of "X the Younger 21"
        return None
    for person in registry.absent():
        if keeper == person["name"] or keeper.startswith(person["name"] + " "):
            return f"Closed: {person['name']} is {person['status']}."
    return None


# ------------------------------------------------------------------ prices
def _fraction(seed: str) -> float:
    return int(hashlib.sha1(seed.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF


def derived_curve(kind: str, seed: str) -> dict:
    (p_lo, p_hi), (a_lo, a_hi) = CURVE_RANGES[kind]
    period = p_lo + round(_fraction(seed + "/period") * (p_hi - p_lo))
    return {"period": period, "amplitude": round(a_lo + _fraction(seed + "/amplitude") * (a_hi - a_lo), 3),
            "phase": round(_fraction(seed + "/phase") * period)}


def clean_curve(raw: dict | None, kind: str, seed: str) -> dict:
    """A judge's curve, bounded so a price never reaches zero or runs away; missing parts fall back to the derived curve."""
    base = derived_curve(kind, seed)
    raw = raw or {}
    try:
        return {"period": max(2, min(365, int(raw.get("period") or base["period"]))),
                "amplitude": max(0.0, min(0.9, float(raw["amplitude"] if raw.get("amplitude") not in (None, "") else base["amplitude"]))),
                "phase": int(raw["phase"] if raw.get("phase") not in (None, "") else base["phase"])}
    except (TypeError, ValueError) as exc:
        raise TownError("A price curve needs numbers: period in days, amplitude from 0 to 0.9, phase in days.") from exc


def wave(curve: dict, day: int, calm: float = 1.0) -> float:
    """The sine rhythm of a place or an item; ``calm`` scales its amplitude (a staple's wave is only a small nudge under places.MARKET)."""
    return 1 + calm * curve["amplitude"] * math.sin(2 * math.pi * (day + curve["phase"]) / curve["period"])


def price_cp(shop: dict, item: dict, day: int) -> int:
    """Today's price: the usual price times the place's wave, the item's wave and the item's scarcity price (``drift``, written
    nightly by economy.reprice; 1 when places.MARKET is off). Waves on staples are scaled down by ``calm`` then. A price the market
    sets may be nothing (free), and in a great glut ``bounty`` makes it negative: the shop pays whoever carries the goods away."""
    calm = float(item.get("calm", 1.0))
    if float(item.get("bounty", 0)) > 0:
        return -max(1, round(item["base_cp"] * float(item["bounty"])))
    floor = 0 if "drift" in item else 1
    return max(floor, round(item["base_cp"] * wave(shop["curve"], day, calm) * wave(item["curve"], day, calm) * float(item.get("drift", 1.0))))


def coins_text(cp: int) -> str:
    """Money as gold with two decimals, like cents: 1002 cp is '10,02 gp' (1 gp = 100 cp). Thousands get a dot."""
    cp = int(cp)
    if cp < 0:
        return "-" + coins_text(-cp)
    return f"{cp // 100:,}".replace(",", ".") + f",{cp % 100:02d} gp"


def price_text(cp: int) -> str:
    """A shelf price in words: free at nothing, and a price below nothing is the shop paying whoever takes the goods away."""
    return "free" if int(cp) == 0 else f"they pay you {coins_text(-int(cp))}" if int(cp) < 0 else coins_text(cp)


# ------------------------------------------------------------------ storage
def _seed(state: dict) -> None:
    """Merge the places of ``places.py`` into the state: new places and new items appear, existing quantities stay."""
    if not places.PLACES:
        return
    entries = {e["key"]: e for e in dcc.catalog(dcc.load_content())} if dcc.content_available() else {}
    for place in places.PLACES:
        shop = state["shops"].setdefault(place["id"], {"stock": []})
        keeper = (state.get("keepers") or {}).get(place["id"]) or place.get("keeper", "")   # an heir who took the seat over keeps the shop (lives._install)
        shop.update(name=place["name"], kinds=place["kinds"], keeper=keeper, blurb=place.get("blurb", ""),
                    deals=place.get("deals", []), restock_every=place.get("restock_every"), stay=place.get("stay"),
                    buys_anything=place.get("buys_anything", False), sell_back=place.get("sell_back"), junk_cp=place.get("junk_cp"),
                    ask=place.get("ask"), augur_point=place.get("augur_point"), wants=place.get("wants", []))
        shop.setdefault("curve", clean_curve(place.get("curve"), "shop", place["id"]))
        shop.setdefault("till", dcc.cost_in_cp(place.get("till")) or 0)  # the coin the place opens with
        shop.setdefault("materials", {m: round(kg * 1000) for m, kg in place.get("materials", {}).items()})  # grams in the workshop at the start
        have = {item["id"]: item for item in shop["stock"]}
        for good in place.get("goods", []):
            if len(good) == 2 and good[0] in entries:
                e = entries[good[0]]
                spec = (e["name"], e["kind"], e["cost"], good[1], int(e.get("qty", 1)), e.get("detail", "").replace("*", ""))
            elif len(good) == 4:
                spec = (*good, 1, "")
            else:
                continue  # a rulebook key while the rules file is missing, or a typo: skip rather than break the town
            line = have.get(dcc._slug(spec[0]))
            if line is None and dcc.cost_in_cp(spec[2]):
                stock_item(state, place["id"], *spec)["target"] = spec[3]  # the shelf is made up or brought up to this
            elif line is not None and line.get("target") is None and spec[3] is not None:
                line["target"] = spec[3]  # a line that was endless, or second-hand before the place listed it
                if line["qty"] is None:
                    line["qty"] = spec[3]
        for name, cost in place.get("services", []):
            if dcc._slug(name) not in have:
                stock_item(state, place["id"], name, "service", cost, None)


@contextmanager
def town(write: bool = False, path: Path | None = None):
    """The town state under a lock; with ``write`` the state is saved when the block ends without an error."""
    path = path or TOWN_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path.with_suffix(".lock"), "a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX if write else fcntl.LOCK_SH)
        state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"shops": {}, "log": [], "news": [], "bots": {}}
        state.setdefault("money", {"bank": dcc.cost_in_cp(places.BANK_START) or 0, "finanzamt": 0})
        state["money"].setdefault("library", 0)  # the library's cash pot: what the dead had in their purses, lent out to the living
        state["money"].setdefault("caravan", 0)  # coin that left the village with the caravans, for goods brought in
        state.setdefault("money_log", [])
        if "chronicle" not in state:   # before 2026-10-06 everything was town talk: it becomes the admin's log, and town talk starts empty
            state["chronicle"], state["news"] = state.get("news", [])[-CHRONICLE_LIMIT:], []
        db = items.connect()
        try:  # shelves and trader packs live in the items table; the file keeps everything else
            for shop_id, shop in state["shops"].items():
                shop["stock"] = items.load("shop", shop_id, db)
            for bot_id, bot in state.get("bots", {}).items():
                bot["inventory"] = items.load("bot", bot_id, db)
            _seed(state)
            yield state
            if write:
                for shop_id, shop in state["shops"].items():
                    items.replace("shop", shop_id, shop["stock"], db)
                for bot_id, bot in state.get("bots", {}).items():
                    items.replace("bot", bot_id, bot.get("inventory", []), db)
                lean = {**state, "shops": {k: {a: b for a, b in v.items() if a != "stock"} for k, v in state["shops"].items()},
                        "bots": {k: {a: b for a, b in v.items() if a != "inventory"} for k, v in state.get("bots", {}).items()}}
                tmp = path.with_suffix(".tmp")
                tmp.write_text(json.dumps(lean, indent=1, ensure_ascii=False), encoding="utf-8")
                os.replace(tmp, path)
                board = [f"{n}. {line['what']}: {', '.join(line['by'])}" for n, line in enumerate(state.get("needs_board", []), 1)]
                path.with_name("village_needs.txt").write_text("VILLAGE NEEDS\n" + "\n".join(board) + "\n", encoding="utf-8")   # the traders' shared notepad, to read
        finally:
            db.close()


def is_judge(state: dict, user: str | None) -> bool:
    """The admins of places.py. No login name means a local run without the auth proxy: treated as the judge."""
    return user is None or user in places.JUDGES


def _shop(state: dict, shop_id: str) -> dict:
    if shop_id not in state["shops"]:
        raise TownError("No such place in town.")
    return state["shops"][shop_id]


def _open(state: dict, shop_id: str) -> dict:
    shop = _shop(state, shop_id)
    reason = closed_reason(shop)
    if reason:
        raise TownError(f"{shop['name']} is shut. {reason}")
    return shop


def _item(shop: dict, item_id: str) -> dict:
    for item in shop["stock"]:
        if item["id"] == item_id and not item.get("gone"):
            return item
    raise TownError("That is not on offer here.")


# ------------------------------------------------------------------ what a visitor sees
def insight(character: dict | None) -> list[str]:
    """Trade goods whose price curve this character can read, from their occupation (places.TRADE_GOODS)."""
    occupation = ((character or {}).get("occupation") or {}).get("occupation", "").lower()
    known = [good["name"] for good in places.TRADE_GOODS if occupation and any(word in occupation for word in good["knows"])]
    return known[:places.INSIGHT_MAX]


def view(state: dict, user: str | None, character: dict | None = None, full: bool | None = None) -> dict:
    """The town for one visitor. Players see today's prices only and must guess the trend; the admin (or ``full``)
    also sees the usual price, yesterday's direction and the curves. ``character`` adds the curves their trade knows."""
    day, judge = campaign_day(), is_judge(state, user)
    full = judge if full is None else full
    known = insight(character)
    clause = clauses.clause_of(character)
    shops = []
    for shop_id, shop in state["shops"].items():
        if shop.get("away"):
            continue   # the caravan between its visits
        stock = []
        for item in shop["stock"]:
            if item.get("gone"):
                continue
            now, before = price_cp(shop, item, day), price_cp(shop, item, day - 1)
            row = {"id": item["id"], "name": item["name"], "kind": item["kind"], "detail": item.get("detail", ""),
                   "qty": item["qty"], "units": item.get("units", 1), "price_cp": now, "price": price_text(now)}
            if clause and "shop" in shop.get("kinds", []):   # what this shopper's clause does to the line: shown, never explained
                pieces = clauses.lot(clause, item)
                mine = clauses.price(clause, shop_id, shop, item, now) * pieces
                row.update(price_cp=mine, price=price_text(mine))
                if pieces > 1:
                    row["lot"] = pieces
                if clauses.refusal(clause, shop_id, shop, item, character, day):
                    row["refused"] = True
                if clause == "two_weeks" and shop_id == places.ROLES["smith"] and item["qty"] is not None:
                    row["qty"] = clauses.old_pieces(item, day)
            if item.get("made") and full:   # which moon the next piece carries: for the admin only; players find out by buying
                first = item["made"][0]
                row["mark"] = {"moon": next((m["name"] for m in places.MOONS if m["id"] == first["moon"]), first["moon"]),
                               "text": mark_text(first, item["kind"]), "pieces": len(item["made"])}
            made = materials.made_of(item["name"], item["kind"])
            if made:
                row.update(material=materials.MATERIALS[made[0]]["name"], weight=materials.kg_text(made[1] * int(item.get("units", 1))))
            if full:
                row.update(usual=coins_text(item["base_cp"]), trend=(now > before) - (now < before),
                           against_usual=round(now / item["base_cp"] - 1, 3), base_cp=item["base_cp"], curve=item["curve"])
            if full or item["name"] in known:
                row["series"] = [round(wave(shop["curve"], d) * wave(item["curve"], d), 3) for d in range(day - 7, day + 22)]
            stock.append(row)
        entry = {"id": shop_id, "name": shop["name"], "kinds": shop.get("kinds", ["shop"]), "keeper": shop.get("keeper", ""),
                 "blurb": shop.get("blurb", ""), "mood": round(wave(shop["curve"], day) - 1, 3) if full else None, "stock": stock,
                 "deals": shop.get("deals", []), "next_delivery": next_delivery(shop_id, shop, day),
                 "buys_anything": bool(shop.get("buys_anything")), "stay": stay_offer(shop_id, shop, day, character),
                 "closed": closed_reason(shop),
                 "ask": {"price_cp": dcc.cost_in_cp(shop["ask"]), "price": coins_text(dcc.cost_in_cp(shop["ask"]))} if shop.get("ask") else None,
                 "augurs": augur_shelf(shop) if shop.get("augur_point") else None, "augur_point_cp": dcc.cost_in_cp(shop.get("augur_point")),
                 "materials": [{"id": m, "name": spec["name"], "amount": materials.kg_text(int(shop.get("materials", {}).get(m, 0)))}
                               for m, spec in materials.MATERIALS.items() if shop.get("materials", {}).get(m)]}
        if full:
            entry.update(curve=shop["curve"], series=[round(wave(shop["curve"], d), 3) for d in range(day - 7, day + 22)])
        shops.append(entry)
    return {"day": day, "date": today().strftime("%A, %-d %B %Y"), "judge": judge, "shops": shops,
            "news": state.get("news", [])[-NEWS_SHOWN:][::-1], "town_note": state.get("town_note", ""), "town_flavour": flavour_lines(state), "insight": known, "moons": moons(full=full), "notices": state.get("notices", []),
            "record": [s for s in state["log"] if character and s["character"] == character["name"]][-15:][::-1],
            **({"log": state["log"][-80:][::-1], "bots": state.get("bots", {}), "last_daily": state.get("last_daily"),
               "chronicle": state.get("chronicle", [])[-60:][::-1], "needs_board": state.get("needs_board", [])} if judge else {})}


# ------------------------------------------------------------------ buying
def buy(state: dict, shop_id: str, item_id: str, character: dict, count: int = 1, who: str | None = None) -> dict:
    """Move ``count`` purchases from the shelf to the character at today's price. Changes both, or raises and changes neither.
    A service (lodging, a meal) is paid for and noted in the character's downtime record instead of the pack."""
    shop = _open(state, shop_id)
    if "library" in shop.get("kinds", []):
        raise TownError(f"{shop['name']} lends; it does not sell.")
    item = _item(shop, item_id)
    day = campaign_day()
    clause = clauses.clause_of(character)      # the character's hidden quirk of the town, if any (westmarch/clauses.py)
    if int(count) < 1:
        raise TownError("Buy at least one.")
    count = int(count) * clauses.lot(clause, item)   # "pairs": one purchase is two pieces
    refused = clauses.refusal(clause, shop_id, shop, item, character, day)
    if refused:
        raise TownError(refused)
    old_only = clause == "two_weeks" and shop_id == places.ROLES["smith"]
    on_offer = item["qty"] if not old_only or item["qty"] is None else clauses.old_pieces(item, day)
    if on_offer is not None and on_offer < count:
        raise TownError(f"Sold out: {item['name']}." if on_offer == 0 else f"Only {on_offer} of {item['name']} left.")
    each = clauses.price(clause, shop_id, shop, item, price_cp(shop, item, day))
    if each < 0:   # a glut: the shop pays whoever takes it away, as far as its till reaches
        if int(shop.get("till", 0)) < -each * count:
            raise TownError(f"{shop['name']} would pay you to take {item['name']} away, but its till is too light for {count}.")
        total = dcc.coins_total_cp(character["coins"]) - each * count
        coins = {"gp": total // 100, "sp": total % 100 // 10, "cp": total % 10}
    else:
        coins = dcc.spend(character["coins"], each * count)  # raises when the purse is too light, before anything changes
    stamp = today().isoformat()
    if clause == "trade_in" and shop_id == places.ROLES["smith"] and item["kind"] == "weapon":   # one of theirs goes on his shelf first
        handed = dcc.ensure_inventory(character)[clauses.trade_in_index(character)]
        back = next((i for i in shop["stock"] if i["name"].lower() == handed["name"].lower() and i["kind"] == "weapon"), None)
        back = back or stock_item(state, shop_id, handed["name"], "weapon", f"{_book_price(handed['name'], 'weapon') or dcc.cost_in_cp(handed.get('cost')) or 100} cp", 0)
        back.pop("gone", None)
        back["qty"] = int(back["qty"] or 0) + 1
        if handed.get("mark"):
            back.setdefault("made", []).append(handed["mark"])
        dcc.change_qty(character, clauses.trade_in_index(character), -1)
    given = item   # what leaves the shelf. Under "oldest" that is not what was asked for: the oldest thing in the shop, at the price of the thing asked for
    if clause == "oldest" and item["kind"] != "service":
        given = oldest_line(shop) or item
    if item["kind"] == "service":
        character.setdefault("downtime", []).append({"date": stamp, "day": day, "place": shop["name"], "what": item["name"],
                                                     "count": count, "paid_cp": each * count})
    else:
        marks = _take_pieces(given, count, oldest=clause == "oldest" or old_only, before_day=day - clauses.OLD_ENOUGH if old_only else None)
        for mark in marks:   # a piece with a moon is a pack line of its own, never stacked, and says what it does
            pack = dcc.ensure_inventory(character)
            worn = given["kind"] == "weapon" or (given["kind"] in ("armor", "shield") and not any(i["kind"] == given["kind"] and i.get("equipped") for i in pack))
            pack.append({"name": given["name"], "kind": given["kind"], "qty": 1, "cost": coins_text(max(0, each)), "equipped": worn, "mark": mark,
                         "notes": f"{mark_text(mark, given['kind'])} ({shop['name']}, {stamp})"})
            dcc.sync_legacy_fields(character)
        if count - len(marks) > 0:
            dcc.add_item(character, given["name"], given["kind"], (count - len(marks)) * int(given.get("units", 1)), coins_text(max(0, each)),
                         notes=f"{shop['name']}, {stamp}")
    character["coins"] = coins
    shop["till"] = int(shop.get("till", 0)) + each * count
    if given["qty"] is not None:
        given["qty"] -= count
        _marks_fit(given)
    sale = {"day": day, "date": stamp, "at": datetime.now(ZoneInfo(places.TIMEZONE)).strftime("%H:%M"), "shop": shop["name"],
            "item": given["name"], "count": count, "each_cp": each, "character": character["name"], "by": who}
    state["log"] = (state["log"] + [sale])[-LOG_LIMIT:]
    economy.note_purchase(state, given["name"], given["kind"], count, max(0, each * count), who == "bot")
    return sale


# ------------------------------------------------------------------ selling to a shop
def _book_price(name: str, kind: str) -> int | None:
    if not dcc.content_available():
        return None
    for e in dcc.catalog(dcc.load_content()):
        if e["name"].lower() == name.lower() and e["kind"] == kind:
            return (dcc.cost_in_cp(e["cost"]) or 0) // int(e.get("qty", 1)) or None
    return None


def offer(state: dict, shop_id: str, thing: dict, character: dict | None = None) -> dict:
    """What a shop pays today for one unit of something from a pack: half of its own price for it. The value comes from
    the shop's shelf when it sells the same thing, else the rulebook tables, else what the owner paid."""
    shop = _shop(state, shop_id)
    anything, rate = bool(shop.get("buys_anything")), shop.get("sell_back") or places.SELL_BACK
    clause = clauses.clause_of(character)
    usual_rate = rate
    cfg = economy.config()
    if cfg and materials.is_produce(thing["name"]):
        rate = max(rate, cfg["wholesale"])   # fresh food is bought at a better rate than anything else: the shop sells it on at once
    rate = clauses.sell_rate(clause, shop_id, shop, thing, rate)
    if not rate:
        raise TownError(f"{shop['name']} does not want that from you.")
    wanted = thing["name"].lower() in [w.lower() for w in shop.get("wants") or []]   # the smith and scrap metal
    caravan = "caravan" in shop.get("kinds", [])
    if caravan and (shop.get("away") or any(word in thing["name"].lower() for word in shop.get("refuses") or [])):
        raise TownError(f"{shop['name']} does not want that.")
    sells_it = any(_listed(i) and i["name"].lower() == thing["name"].lower() for i in shop["stock"])   # an inn buys the ale it pours (refused until 10-10: its shelf never filled)
    if not sells_it and (not caravan and "shop" not in shop.get("kinds", ["shop"]) or (not anything and not wanted and thing["kind"] not in (shop.get("deals") or dcc.ITEM_KINDS))):
        raise TownError(f"{shop['name']} does not deal in that.")
    if materials.is_raw(thing["name"]) and not wanted and not anything:
        raise TownError(f"{shop['name']} has no use for that.")   # raw material goes to the workshop that works it
    if thing.get("on_loan"):
        raise TownError(f"{thing['name']} belongs to the library.")
    day = campaign_day()
    shelf = next((i for i in shop["stock"] if i["name"].lower() == thing["name"].lower() and i["kind"] != "service"), None)
    if shelf:
        full = price_cp(shop, shelf, day) / int(shelf.get("units", 1))
    else:
        base = _book_price(thing["name"], thing["kind"]) or thing.get("base_cp") or dcc.cost_in_cp(thing.get("cost"))
        if not base:
            if not anything:
                raise TownError(f"Nobody at {shop['name']} knows what {thing['name']} is worth.")
            junk = int(shop.get("junk_cp") or 1)  # a hen, a rag doll: a flat pittance, and a shelf price to match
            return {"each_cp": max(1, round(junk * rate / usual_rate)), "base_cp": max(1, round(junk / usual_rate)), "shelf": None, "room": None}
        curve = clean_curve(None, "item", f"{shop_id}/{dcc._slug(thing['name'])}")
        full = base if caravan else base * wave(shop["curve"], day) * wave(curve, day)   # the caravan offers its share of the usual price, whatever the day
    return {"each_cp": max(1 if anything else 0, int(full * rate)), "base_cp": shelf["base_cp"] if shelf else int(base), "shelf": shelf,
            "room": room_for(shop, shelf, thing)}


WANT_CAP = 20   # lumps of a wanted raw material a shop keeps lying about before it says "enough"


def room_for(shop: dict, shelf: dict | None, thing: dict) -> int | None:
    """How many more purchases of this a shop takes: a listed shelf is bought up to twice its listed quantity, a
    wanted raw material up to WANT_CAP; anything else (second-hand things, loot) as long as the till pays. None = no limit."""
    units = int(shelf.get("units", 1)) if shelf else 1
    have = int(shelf["qty"] or 0) if shelf else 0
    if shelf and shelf.get("target") is not None and shelf["kind"] != "service":
        return max(0, 2 * int(shelf["target"]) - have) * units
    if thing["name"].lower() in [w.lower() for w in shop.get("wants") or []]:
        return max(0, WANT_CAP - have)
    cfg = economy.config()
    if cfg and cfg.get("junk_cap") and "caravan" not in shop.get("kinds", []):
        return max(0, int(cfg["junk_cap"]) - have)   # even a shop that buys anything has only so much room
    return None


def offers(state: dict, character: dict) -> dict:
    """Per shop, what it would pay for each thing the character carries (index into the inventory)."""
    out = {}
    for shop_id, shop in state["shops"].items():
        rows = []
        for index, thing in enumerate(dcc.ensure_inventory(character)):
            try:
                deal = offer(state, shop_id, thing, character)
                each = deal["each_cp"]
            except TownError:
                continue
            if each > 0 and deal["room"] != 0:
                rows.append({"index": index, "name": thing["name"], "qty": int(thing.get("qty", 1)), "each_cp": each, "each": coins_text(each),
                             "room": deal["room"]})
        if rows:
            out[shop_id] = rows
    return out


def sell(state: dict, shop_id: str, character: dict, index: int, count: int = 1, who: str | None = None) -> dict:
    """A character sells ``count`` of one inventory line to a shop at half of today's price; the goods go on the shelf."""
    inventory = dcc.ensure_inventory(character)
    if not 0 <= int(index) < len(inventory):
        raise TownError("No such item in the pack.")
    thing, count = inventory[int(index)], int(count)
    if count < 1 or count > int(thing.get("qty", 1)):
        raise TownError(f"{character['name']} carries {thing.get('qty', 1)} of {thing['name']}.")
    deal = offer(state, shop_id, thing, character)
    shop, shelf = _open(state, shop_id), deal["shelf"]
    if not deal["each_cp"]:
        raise TownError(f"{shop['name']} will not pay a single copper for that.")
    units = int(shelf.get("units", 1)) if shelf else 1
    if count % units:
        raise TownError(f"{thing['name']} is traded in lots of {units}.")
    if deal["room"] is not None and count > deal["room"]:
        raise TownError(f"{shop['name']} has enough of that for now." if deal["room"] == 0 else f"{shop['name']} takes only {deal['room']} more of that for now.")
    paid = deal["each_cp"] * count
    if int(shop.get("till", 0)) < paid:  # every refusal comes before anything changes: a refused sale must leave no trace
        raise TownError(f"{shop['name']} has only {coins_text(int(shop.get('till', 0)))} in the till and cannot pay {coins_text(paid)}.")
    if shelf is None:
        shelf = stock_item(state, shop_id, thing["name"], thing["kind"], f"{deal['base_cp']} cp", 0)
    shelf.pop("gone", None)
    if shelf["qty"] is not None:
        shelf["qty"] += count // units
        if thing.get("mark"):
            shelf.setdefault("made", []).append(thing["mark"])   # the piece keeps its moon on the shelf
    shop["till"] = int(shop["till"]) - paid
    total = dcc.coins_total_cp(character["coins"]) + paid
    name = thing["name"]
    dcc.change_qty(character, int(index), -count)
    character["coins"] = {"gp": total // 100, "sp": total % 100 // 10, "cp": total % 10}
    sale = {"day": campaign_day(), "date": today().isoformat(), "at": datetime.now(ZoneInfo(places.TIMEZONE)).strftime("%H:%M"),
            "shop": shop["name"], "item": name, "count": -count, "each_cp": deal["each_cp"], "character": character["name"], "by": who}
    state["log"] = (state["log"] + [sale])[-LOG_LIMIT:]
    return sale


# ------------------------------------------------------------------ the library
def _library(state: dict) -> tuple[str, dict]:
    for shop_id, shop in state["shops"].items():
        if "library" in shop.get("kinds", []):
            return shop_id, shop
    raise TownError("This town has no library.")


def _shelve(state: dict, library_id: str, thing: dict, count: int) -> None:
    """Put pieces on the library's shelf, next to the same thing if it is already there."""
    shop = state["shops"][library_id]
    shelf = next((i for i in shop["stock"] if i["name"].lower() == thing["name"].lower() and i["kind"] == thing["kind"]), None)
    if shelf:
        shelf["qty"] = int(shelf["qty"] or 0) + count
        shelf.pop("gone", None)
    else:
        worth = _book_price(thing["name"], thing["kind"]) or dcc.cost_in_cp(thing.get("cost")) or 1
        shelf = stock_item(state, library_id, thing["name"], thing["kind"], f"{worth} cp", count)
    if thing.get("mark"):
        shelf.setdefault("made", []).append(thing["mark"])


def bequeath(state: dict, character: dict) -> int:
    """A dead character's things, every one of them, go to the library. Returns how many pieces."""
    library_id, _ = _library(state)
    pieces = 0
    for thing in dcc.ensure_inventory(character):
        count = int(thing.get("qty", 1))
        _shelve(state, library_id, thing, count)
        pieces += count
    character["inventory"] = []
    dcc.sync_legacy_fields(character)
    return pieces


def borrow(state: dict, character: dict, item_id: str, who: str | None = None) -> dict:
    """Take one piece from the library, free of charge. It stays the library's: it cannot be sold, only brought back."""
    library_id, shop = _library(state)
    item = _item(shop, item_id)
    if not item["qty"]:
        raise TownError(f"Somebody else has {item['name']} out.")
    item["qty"] -= 1
    mark = item["made"].pop(0) if item.get("made") else None
    _marks_fit(item)
    lent = {"name": item["name"], "kind": item["kind"], "qty": 1, "cost": None, "equipped": False, "on_loan": True,
            "notes": f"on loan from {shop['name']}" + (". " + mark_text(mark, item["kind"]) if mark else "")}
    if mark:
        lent["mark"] = mark
    character.setdefault("inventory", dcc.ensure_inventory(character)).append(lent)
    dcc.sync_legacy_fields(character)
    return _note(state, shop["name"], f"Borrowed: {item['name']}", 1, 0, character, who)


def give_back(state: dict, character: dict, index: int, who: str | None = None) -> dict:
    inventory = dcc.ensure_inventory(character)
    if not 0 <= int(index) < len(inventory) or not inventory[int(index)].get("on_loan"):
        raise TownError("That is not a library loan.")
    library_id, shop = _library(state)
    thing = inventory.pop(int(index))
    _shelve(state, library_id, thing, int(thing.get("qty", 1)))
    dcc.sync_legacy_fields(character)
    return _note(state, shop["name"], f"Returned: {thing['name']}", 1, 0, character, who)


def _note(state: dict, place: str, what: str, count: int, each_cp: int, character: dict, who: str | None) -> dict:
    entry = {"day": campaign_day(), "date": today().isoformat(), "at": datetime.now(ZoneInfo(places.TIMEZONE)).strftime("%H:%M"),
             "shop": place, "item": what, "count": count, "each_cp": each_cp, "character": character["name"], "by": who}
    state["log"] = (state["log"] + [entry])[-LOG_LIMIT:]
    return entry


# ------------------------------------------------------------------ inns
def stay_offer(shop_id: str, shop: dict, day: int, character: dict | None = None) -> dict | None:
    """Tonight's price for a bed and what a night restores; None for a place without beds."""
    stay = shop.get("stay")
    if not stay:
        return None
    night = {"base_cp": dcc.cost_in_cp(stay["price"]), "curve": clean_curve(None, "item", f"{shop_id}/stay")}
    each = price_cp(shop, night, day)
    deal = clauses.stay_terms(clauses.clause_of(character), {"price_cp": each, "usual": coins_text(night["base_cp"]), "hp": stay["hp"], "ability": stay["ability"]})
    deal["price"] = coins_text(deal["price_cp"])
    if deal.get("pet_fee_cp"):
        deal["note"] = f"pet fee of {coins_text(deal['pet_fee_cp'])} a night included"
    return deal


def settle(character: dict, day: int | None = None) -> bool:
    """Apply the nights of a paid stay that have passed since the last look. Returns whether the character changed."""
    lodging = character.get("lodging")
    if not lodging:
        return False
    day = campaign_day() if day is None else day
    passed = max(0, min(int(lodging["nights"]), day - int(lodging["from_day"])))
    owed = passed - int(lodging.get("applied", 0))
    for _ in range(owed):
        dcc.rest(character, hp=lodging["hp"], ability=lodging["ability"])
    lodging["applied"] = passed
    if passed >= int(lodging["nights"]):
        character.pop("lodging")
        return True
    return owed > 0


def stay(state: dict, shop_id: str, character: dict, nights: int = 1, who: str | None = None) -> dict:
    """Pay for ``nights`` at an inn at tonight's price. Each real night that then passes heals at the inn's rate."""
    shop, day, nights = _open(state, shop_id), campaign_day(), int(nights)
    deal = stay_offer(shop_id, shop, day, character)
    if not deal:
        raise TownError(f"{shop['name']} has no beds.")
    if not 1 <= nights <= 30:
        raise TownError("Book between 1 and 30 nights.")
    settle(character, day)
    if character.get("lodging"):
        current = character["lodging"]
        left = int(current["nights"]) - int(current.get("applied", 0))
        raise TownError(f"{character['name']} already has a bed at {current['name']} for {left} more night{'s' if left != 1 else ''}.")
    character["coins"] = dcc.spend(character["coins"], deal["price_cp"] * nights)
    shop["till"] = int(shop.get("till", 0)) + deal["price_cp"] * nights
    character["lodging"] = {"place": shop_id, "name": shop["name"], "from_day": day, "nights": nights, "applied": 0,
                            "hp": deal["hp"], "ability": deal["ability"]}
    stamp = today().isoformat()
    character.setdefault("downtime", []).append({"date": stamp, "day": day, "place": shop["name"], "what": f"{nights} night(s) lodging",
                                                 "count": nights, "paid_cp": deal["price_cp"] * nights})
    sale = {"day": day, "date": stamp, "at": datetime.now(ZoneInfo(places.TIMEZONE)).strftime("%H:%M"), "shop": shop["name"],
            "item": "Lodging, per night", "count": nights, "each_cp": deal["price_cp"], "character": character["name"], "by": who}
    state["log"] = (state["log"] + [sale])[-LOG_LIMIT:]
    return sale


# ------------------------------------------------------------------ the tax office
def tax_debt(character: dict) -> int:
    """What the character still owes, in copper. Everyone starts with ``places.TAX_DEBT``."""
    if "tax_debt_cp" not in character:
        character["tax_debt_cp"] = dcc.cost_in_cp(places.TAX_DEBT)
    return int(character["tax_debt_cp"])


def pay_taxes(state: dict, character: dict, amount: str, who: str | None = None) -> dict:
    """Hand over an amount such as '5 gp' or '30 cp'. The coin is gone at once and the debt shrinks by it, never below zero."""
    cp = dcc.cost_in_cp(amount)
    if not cp or not any(unit in str(amount).lower() for unit in ("cp", "sp", "gp")):
        raise TownError("Write the amount with its coin, such as 5 gp, 12 sp or 30 cp.")
    debt = tax_debt(character)
    if debt <= 0:
        raise TownError(f"{character['name']} owes the tax office nothing.")
    cp = clauses.tax_payment(clauses.clause_of(character), min(cp, debt))
    if cp <= 0:
        raise TownError("The office hands the coin back. From this debtor it takes sevens: 7 cp, 14 cp, 21 cp.")
    character["coins"] = dcc.spend(character["coins"], cp)
    character["taxed_day"] = campaign_day()   # some clauses care whether tax was paid today
    state["money"]["finanzamt"] += cp  # taxes take coin out of circulation; it sits at the Finanzamt until the admin moves it
    character["tax_debt_cp"] = debt - cp
    sale = {"day": campaign_day(), "date": today().isoformat(), "at": datetime.now(ZoneInfo(places.TIMEZONE)).strftime("%H:%M"),
            "shop": "Tax office", "item": "Taxes paid", "count": 1, "each_cp": cp, "character": character["name"], "by": who}
    state["log"] = (state["log"] + [sale])[-LOG_LIMIT:]
    return sale


# ------------------------------------------------------------------ money: the bank, the Finanzamt, the tills
def set_purse(character: dict, cp: int) -> None:
    character["coins"] = {"gp": cp // 100, "sp": cp % 100 // 10, "cp": cp % 10}


def _account(state: dict, name: str) -> tuple[dict, str]:
    """Where an account's coin is kept: 'bank', 'finanzamt', 'library' (its cash pot) or 'till:<place id>'."""
    if name in ("bank", "finanzamt", "library", "caravan", "households"):
        return state["money"], name
    if name.startswith("till:") and name[5:] in state["shops"]:
        return state["shops"][name[5:]], "till"
    raise TownError("Money sits at the bank, the Finanzamt or in a place's till.")


def _money_note(state: dict, what: str, cp: int, who: str | None) -> None:
    state["money_log"] = (state["money_log"] + [{"date": today().isoformat(), "what": what, "cp": int(cp), "by": who}])[-200:]


def issue(state: dict, amount_cp: int, who: str | None = None) -> None:
    """The bank makes new coin (positive) or melts coin from its vault down (negative). The only way the amount of money changes."""
    amount_cp = int(amount_cp)
    if state["money"]["bank"] + amount_cp < 0:
        raise TownError(f"The bank's vault holds only {coins_text(state['money']['bank'])}.")
    state["money"]["bank"] += amount_cp
    _money_note(state, "bank issued new coin" if amount_cp >= 0 else "bank retired coin", amount_cp, who)


def move(state: dict, source: str, target: str, amount_cp: int, character: dict | None = None, who: str | None = None) -> None:
    """Move coin between accounts, or between an account and a character ('character' as source or target)."""
    amount_cp = int(amount_cp)
    if amount_cp <= 0:
        raise TownError("Move an amount above zero.")
    if "character" in (source, target) and character is None:
        raise TownError("Name the character.")
    if source == "character":
        character["coins"] = dcc.spend(character["coins"], amount_cp)
    else:
        box, key = _account(state, source)
        if int(box.get(key, 0)) < amount_cp:
            raise TownError(f"Only {coins_text(int(box.get(key, 0)))} is there to take.")
        box[key] = int(box[key]) - amount_cp
    if target == "character":
        set_purse(character, dcc.coins_total_cp(character["coins"]) + amount_cp)
    else:
        box, key = _account(state, target)
        box[key] = int(box.get(key, 0)) + amount_cp
    name = lambda a: character["name"] if a == "character" else a
    _money_note(state, f"{name(source)} -> {name(target)}", amount_cp, who)


def fund_purse(state: dict, character: dict, wanted_cp: int, who: str | None = None) -> None:
    """Set a purse to an amount the honest way: the difference comes out of the bank's vault or goes back into it."""
    change = int(wanted_cp) - dcc.coins_total_cp(character["coins"])
    if change > 0:
        if state["money"]["bank"] < change:
            raise TownError(f"The bank's vault holds only {coins_text(state['money']['bank'])}. Issue coin first; money does not come from nowhere.")
        move(state, "bank", "character", change, character, who)
    elif change < 0:
        move(state, "character", "bank", -change, character, who)


def pot_the_purse(state: dict, character: dict) -> int:
    """A dead character's coins go into the library's cash pot, like their things go onto its shelves. Returns the sum.
    A loan from the pot that they still owed dies with them."""
    coin = dcc.coins_total_cp(character["coins"])
    if coin:
        state["money"]["library"] += coin
        set_purse(character, 0)
        _money_note(state, f"{character['name']} (dead) -> library", coin, None)
    if character.get("library_loan_cp"):
        _money_note(state, f"loan of {character['name']} (dead) written off", int(character["library_loan_cp"]), None)
        character["library_loan_cp"] = 0
    return coin


def borrow_coin(state: dict, character: dict, amount: str, who: str | None = None) -> dict:
    """Take coin from the library's pot as a loan. It grows nightly, by the borrower's moon, until it is paid back."""
    cp = dcc.cost_in_cp(amount)
    if not cp:
        raise TownError("Write the amount, such as 5,00 gp.")
    if cp > state["money"]["library"]:
        raise TownError(f"The library's pot holds only {coins_text(state['money']['library'])}.")
    state["money"]["library"] -= cp
    set_purse(character, dcc.coins_total_cp(character["coins"]) + cp)
    character["library_loan_cp"] = int(character.get("library_loan_cp", 0)) + cp
    _, shop = _library(state)
    return _note(state, shop["name"], "Coin borrowed from the pot", 1, cp, character, who)


def repay_coin(state: dict, character: dict, amount: str, who: str | None = None) -> dict:
    """Pay coin back into the pot, interest included; never more than is owed."""
    cp = dcc.cost_in_cp(amount)
    owed = int(character.get("library_loan_cp", 0))
    if not cp:
        raise TownError("Write the amount, such as 5,00 gp.")
    if owed <= 0:
        raise TownError(f"{character['name']} owes the library no coin.")
    cp = min(cp, owed)
    character["coins"] = dcc.spend(character["coins"], cp)
    state["money"]["library"] += cp
    character["library_loan_cp"] = owed - cp
    _, shop = _library(state)
    return _note(state, shop["name"], "Coin paid back into the pot", 1, cp, character, who)


def price_index(state: dict, day: int | None = None) -> float:
    """Today's prices against the usual ones, averaged over everything on a shop shelf: 1.0 is normal."""
    day = campaign_day() if day is None else day
    ratios = [price_cp(shop, item, day) / item["base_cp"] for shop in state["shops"].values() if "shop" in shop.get("kinds", [])
              for item in shop["stock"] if item["kind"] != "service" and item["qty"] != 0 and not item.get("gone")]
    return round(sum(ratios) / len(ratios), 4) if ratios else 1.0


# ------------------------------------------------------------------ deliveries and town talk
def next_delivery(shop_id: str, shop: dict, day: int) -> int | None:
    """Days until this place's next making day (0 = today); the weekday of a place is fixed by its name."""
    every = shop.get("restock_every")
    if not every:
        return None
    return (-(day + round(_fraction(shop_id + "/delivery") * every))) % every


def _listed(line: dict) -> bool:
    """A shelf line the place keeps at a quantity written in places.py."""
    return line.get("target") is not None and line["qty"] is not None and not line.get("gone") and line["kind"] != "service"


def _spare(shop: dict, material: str) -> list[tuple[dict, int]]:
    """Pieces this shop may break up for a material: what the shelf holds beyond its listed quantity, second-hand
    lines foremost, cheapest first. Each with the grams one piece gives back."""
    rate = materials.MATERIALS[material]["recycle"]
    out = []
    for line in shop["stock"]:
        made = materials.made_of(line["name"], line["kind"])
        if not rate or not made or made[0] != material or line["qty"] is None or line.get("gone"):
            continue
        if line["qty"] - (line.get("target") or 0) > 0:
            out.append((line, int(made[1] * int(line.get("units", 1)) * rate)))
    return sorted(out, key=lambda pair: (pair[0].get("target") is not None, pair[0]["base_cp"]))


def restock(state: dict, shop_id: str, day: int | None = None) -> dict:
    """Making day. The keeper makes what is short of the quantity written in places.py, one piece at a time, out of
    the material in the workshop: a piece takes its own weight of what it is made of. When the material runs out,
    spare pieces on the shelf are broken up for it at the material's recycling rate, and only when that yields
    enough for the piece. Small goods are not made here: the villagers bring them (``deliver``).
    Returns {"made": pieces, "broken": pieces, "short": names still missing for want of material}."""
    shop = _shop(state, shop_id)
    store = shop.setdefault("materials", {})
    wanted = [(line, made) for line in shop["stock"] if _listed(line) and not materials.is_raw(line["name"]) and (made := materials.made_of(line["name"], line["kind"]))]
    made_count = broken = 0
    progress = True
    while progress:  # round after round, so one hungry line does not eat the whole store
        progress = False
        for line, (material, grams) in wanted:
            if line["qty"] >= line["target"]:
                continue
            need = grams * int(line.get("units", 1))
            if store.get(material, 0) < need:
                spare = [(other, back) for other, back in _spare(shop, material) if other is not line]
                if store.get(material, 0) + sum(back * (other["qty"] - (other.get("target") or 0)) for other, back in spare) < need:
                    continue
                for other, back in spare:
                    while store.get(material, 0) < need and other["qty"] - (other.get("target") or 0) > 0:
                        other["qty"] -= 1
                        _marks_fit(other)
                        store[material] = store.get(material, 0) + back
                        broken += 1
            store[material] -= need
            line["qty"] += 1
            mark = make_mark(shop_id, shop, line, campaign_day() if day is None else day, made_count)
            if mark:
                line.setdefault("made", []).append(mark)   # this piece belongs to the moon that stands fullest today
            made_count += 1
            progress = True
    return {"made": made_count, "broken": broken, "short": [line["name"] for line, _ in wanted if line["qty"] < line["target"]]}


def deliver(state: dict, good: str) -> str | None:
    """A villager brings one piece of a small good to the listed shelf that is shortest of it. Returns the place's
    name, or None when no shelf wants any: then the piece is not produced at all."""
    best = None
    for shop in state["shops"].values():
        for line in shop["stock"]:
            if line["name"].lower() == good.lower() and _listed(line) and line["qty"] < line["target"]:
                if best is None or line["target"] - line["qty"] > best[1]["target"] - best[1]["qty"]:
                    best = (shop, line)
    if best is None:
        return None
    best[1]["qty"] += 1
    return best[0]["name"]


def deliver_wood(state: dict, kg: float) -> int:
    """A villager brings raw wood to the workshop that works wood and holds least of it. Returns the grams taken."""
    cap = round(places.WOOD_STORE_KG * 1000)
    takers = [shop for shop in state["shops"].values() if shop.get("materials", {}).get("wood", 0) < cap
              and any(_listed(line) and (materials.made_of(line["name"], line["kind"]) or ("",))[0] == "wood" for line in shop["stock"])]
    if not takers:
        return 0
    shop = min(takers, key=lambda s: s.get("materials", {}).get("wood", 0))
    store = shop.setdefault("materials", {})
    grams = min(round(kg * 1000), cap - store.get("wood", 0))
    store["wood"] = store.get("wood", 0) + grams
    return grams


def goods_note(state: dict, what: str, who: str | None) -> None:
    """The admin's hand in the goods, for the record: the only way besides the villagers' produce that goods come from outside."""
    state["goods_log"] = (state.get("goods_log", []) + [{"date": today().isoformat(), "what": what, "by": who}])[-200:]


def add_material(state: dict, shop_id: str, material: str, kg: float, who: str | None = None) -> None:
    """The admin brings raw material into a workshop from outside the village (loot, a caravan), or takes it away."""
    shop = _shop(state, shop_id)
    if material not in materials.MATERIALS or not kg:
        raise TownError("Choose a material and write an amount in kilograms, such as 12,5.")
    store = shop.setdefault("materials", {})
    grams = round(float(kg) * 1000)
    if store.get(material, 0) + grams < 0:
        raise TownError(f"{shop['name']} holds only {materials.kg_text(store.get(material, 0))} of that.")
    store[material] = store.get(material, 0) + grams
    name = materials.MATERIALS[material]["name"]
    goods_note(state, f"{materials.kg_text(abs(grams))} of {name} {'brought to' if grams > 0 else 'taken from'} {shop['name']}", who)


def _dated(day: int, text: str) -> dict:
    return {"day": day, "date": date.fromordinal(places.EPOCH.toordinal() + day - 1).isoformat(), "text": text}


def tell(state: dict, day: int, text: str) -> None:
    """A line in the town's log, which only the admin reads: making days, what each trader did, the caravan."""
    state["chronicle"] = (state.get("chronicle", []) + [_dated(day, text)])[-CHRONICLE_LIMIT:]


def gossip(state: dict, day: int, text: str) -> None:
    """A line of town talk, which every player sees. Kept rare and short (daily.talk)."""
    state["news"] = (state.get("news", []) + [_dated(day, text)])[-NEWS_LIMIT:]


# ------------------------------------------------------------------ the judge's tools
def _new_id(taken, text: str) -> str:
    base = dcc._slug(text)
    candidate, n = base, 2
    while candidate in taken:
        candidate = f"{base}-{n}"; n += 1
    return candidate


def save_shop(state: dict, shop_id: str | None, name: str, keeper: str = "", blurb: str = "", curve: dict | None = None) -> str:
    """Edit a place's curve (name, keeper and blurb of a place from places.py are restored from there on the next load)."""
    name = name.strip()
    if not name:
        raise TownError("A place needs a name.")
    if shop_id:
        shop = _shop(state, shop_id)
    else:
        shop_id = _new_id(state["shops"], name)
        shop = state["shops"][shop_id] = {"stock": [], "kinds": ["shop"]}
    shop.update(name=name, keeper=keeper.strip(), blurb=blurb.strip(), curve=clean_curve(curve, "shop", shop_id))
    return shop_id


def stock_item(state: dict, shop_id: str, name: str, kind: str, base_cost: str, qty: int | None, units: int = 1,
               detail: str = "", curve: dict | None = None) -> dict:
    """Put an item on the shelf, or add to the pile when the place already sells it. ``qty`` None means it never runs out."""
    shop = _shop(state, shop_id)
    base_cp = dcc.cost_in_cp(base_cost)
    if not name.strip() or kind not in KINDS or not base_cp:
        raise TownError("Stock needs a name, a kind and a usual price such as '10 gp' or '5 sp'.")
    if qty is not None and int(qty) < 0:
        raise TownError("The quantity cannot be negative.")
    for item in shop["stock"]:
        if item["name"].lower() == name.strip().lower():
            item["qty"] = None if qty is None or item["qty"] is None else item["qty"] + int(qty)
            item.pop("gone", None)
            return item
    item = {"id": _new_id({i["id"] for i in shop["stock"]}, name), "name": name.strip(), "kind": kind, "base_cp": base_cp,
            "qty": None if qty is None else int(qty), "units": max(1, int(units)), "detail": detail}
    item["curve"] = clean_curve(curve, "item", f"{shop_id}/{item['id']}")
    shop["stock"].append(item)
    return item


def stock_from_book(state: dict, shop_id: str, content: dict, keys: list[str], qty: int | None) -> int:
    """Shelve entries of the rulebook's equipment tables by their catalog key ('weapon:Longsword'); returns how many."""
    entries = {e["key"]: e for e in dcc.catalog(content)}
    for key in keys:
        if key not in entries:
            raise TownError(f"Not in the rulebook tables: {key}")
        e = entries[key]
        if not dcc.cost_in_cp(e["cost"]):
            continue  # barding is priced "x4" of the mount: no usual price to hang a curve on
        stock_item(state, shop_id, e["name"], e["kind"], e["cost"], qty, int(e.get("qty", 1)), e.get("detail", "").replace("*", ""))
    return len(keys)


def edit_item(state: dict, shop_id: str, item_id: str, qty="keep", base_cost: str | None = None, curve: dict | None = None) -> None:
    shop = _shop(state, shop_id)
    item = _item(shop, item_id)
    if qty != "keep":
        if qty is not None and int(qty) < 0:
            raise TownError("The quantity cannot be negative.")
        item["qty"] = None if qty is None else int(qty)
    if base_cost:
        cp = dcc.cost_in_cp(base_cost)
        if not cp:
            raise TownError("The usual price reads like '10 gp' or '5 sp'.")
        item["base_cp"] = cp
    if curve is not None:
        item["curve"] = clean_curve(curve, "item", f"{shop_id}/{item_id}")


def remove_item(state: dict, shop_id: str, item_id: str) -> None:
    """Take an item off offer. It is marked rather than deleted, so places.py does not put it back."""
    _item(_shop(state, shop_id), item_id)["gone"] = True
