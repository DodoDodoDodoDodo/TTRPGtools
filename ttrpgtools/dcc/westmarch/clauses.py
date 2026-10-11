"""Clauses: one quirk of the town per character, fixed by birth augur and moon together, and never explained.

Nobody is told their clause. It simply happens: a price is different, a keeper shakes his head, the office wants its
coin in sevens. The pages show the result (a doubled price, a thing that is "not for you") and never the reason.
Only the admin sees which clause a character has. A character who sells their augur has no clause until they carry
another one; then it is the clause of that augur and their moon.

The list is the owner's choice from two rounds of ideas (2026-10-05/06). Each clause is one word here; what it does is
decided by the small functions below, which ``town.py`` asks at the few places where it matters.
"""

from __future__ import annotations

import hashlib
import re

from ttrpgtools import dcc
from . import materials, places

CLAUSES = {
    "no_rope": "Nobody in town sells you rope.",
    "pairs": "You can only buy things in pairs: two pieces, twice the price, and never the last single one.",
    "round_gold": "Prices above 1 gp are rounded up to the next gold piece for you; Groderick rounds them down.",
    "nameless": "Everything addresses you by your occupation. Your name is shown to you nowhere.",
    "hens_and_leather": "A hen costs you a tenth, at least 1 cp. Everything made of leather and stuff costs you double.",
    "pet_fee": "Inns charge you a pet fee on every night, pet or no pet.",
    "trade_in": "The blacksmith sells you a weapon only if you hand one in.",
    "sevens": "The tax office takes your payments only in multiples of seven copper.",
    "tax_first": "No shop serves you on a day on which you have not yet paid some tax.",
    "sixty": "Shops that pay half pay you six tenths.",
    "hens_for_groderick": "Groderick pays you double for hens and nothing for anything else.",
    "oldest": "Whatever you buy, you pay for it and get the oldest thing in the shop instead.",
    "no_edges": "The blacksmith sells you nothing with an edge.",
    "rope_and_light": "The outfitter gives you rope at half price and charges you double for light.",
    "no_helmets": "You may not buy helmets, by decree.",
    "worst_bed": "Inns give you the worst bed: it heals one point less of each kind and costs the same.",
    "herb_week": "The herb woman answers your first question of a week for nothing and lies on the second.",
    "keeper_moon": "You may sell to, but never buy from, a shop whose keeper shares your moon.",
    "no_interest": "The library charges you no interest on borrowed coin.",
    "two_weeks": "The blacksmith sells you only things that are two weeks old or older.",
}
OLD_ENOUGH = 14      # days, for "two_weeks"
SEVEN = 7            # coppers, for "sevens"


def clause_of(character: dict | None) -> str | None:
    """The clause a character lives under, or None: traders have none, nor has anyone without an augur or a moon."""
    augur = (character or {}).get("birth_augur") or {}
    roll, moon = int(augur.get("roll") or 0), (character or {}).get("moon")
    if not roll or not moon:
        return None
    return _deal().get((roll, moon))


def _deal() -> dict:
    """Every pairing of augur and moon with its clause: the pairings are shuffled once, always the same way, and the
    clauses dealt round like cards, so each clause belongs to as many pairings as any other, give or take one."""
    pairs = sorted(((roll, moon["id"]) for roll in range(1, 31) for moon in places.MOONS),
                   key=lambda pair: hashlib.sha1(f"clause/{pair[0]}/{pair[1]}".encode()).hexdigest())
    names = list(CLAUSES)
    return {pair: names[n % len(names)] for n, pair in enumerate(pairs)}


def _is(words: str, name: str) -> bool:
    return bool(re.search(rf"\b(?:{words})", name.lower()))


is_hen = lambda name: _is(r"hen\b|chicken|rooster", name)
is_rope = lambda name: _is("rope", name)
is_light = lambda name: _is("candle|torch|lantern|oil", name)
is_edged = lambda name: _is("sword|longsword|axe|battleaxe|handaxe|dagger|polearm|knife|cleaver|razor|scissors", name) or "sword" in name.lower() or "axe" in name.lower()
is_helmet = lambda name: _is("helmet|helm", name)


def keeper_moon(shop: dict) -> str:
    """A keeper's moon, the same every time: drawn from the name."""
    name = shop.get("keeper") or shop.get("name", "")
    return places.MOONS[int(hashlib.sha1(f"keeper-moon/{name}".encode()).hexdigest(), 16) % len(places.MOONS)]["id"]


def lot(clause: str | None, item: dict) -> int:
    """How many pieces one purchase is: two under "pairs"."""
    return 2 if clause == "pairs" and item["kind"] != "service" else 1


def old_pieces(item: dict, day: int) -> int:
    """How many pieces of a shelf line are two weeks old or older. A piece without a mark predates the marks: old."""
    made = item.get("made") or []
    plain = max(0, int(item["qty"] or 0) - len(made))
    return plain + sum(1 for m in made if int(m.get("day", 0)) <= day - OLD_ENOUGH)


def refusal(clause: str | None, shop_id: str, shop: dict, item: dict, character: dict, day: int) -> str | None:
    """Why this keeper will not sell this thing to this character, as the keeper would put it, or None."""
    name, keeper = item["name"], shop.get("keeper") or shop.get("name", "The keeper")
    smith = shop_id == places.ROLES["smith"]
    no = f"{keeper} will not sell that. Not to you."
    if item["kind"] == "service" or not clause:
        return None
    if clause == "tax_first" and int(character.get("taxed_day") or 0) != day:
        return f"{keeper} asks whether you have been to the tax office today."
    if clause == "no_rope" and is_rope(name):
        return no
    if clause == "no_helmets" and is_helmet(name):
        return f"{keeper} points at a decree on the wall. No helmets. Not for you."
    if clause == "no_edges" and smith and is_edged(name):
        return no
    if clause == "keeper_moon" and keeper_moon(shop) == character.get("moon"):
        return f"{keeper} buys from you gladly and sells you nothing."
    if clause == "pairs" and item["qty"] is not None and int(item["qty"]) < 2:
        return f"{keeper} has only the one. One is no use to you."
    if clause == "two_weeks" and smith and item["qty"] is not None and old_pieces(item, day) < 1:
        return f"{keeper} says these are too fresh for you. Come back in a fortnight."
    if clause == "trade_in" and smith and item["kind"] == "weapon" and trade_in_index(character) is None:
        return f"{keeper} wants a weapon handed in before he sells you one."
    return None


def trade_in_index(character: dict) -> int | None:
    """The weapon a character hands in under "trade_in": the first one of their own in the pack."""
    for index, thing in enumerate(dcc.ensure_inventory(character)):
        if thing["kind"] == "weapon" and not thing.get("on_loan"):
            return index
    return None


def price(clause: str | None, shop_id: str, shop: dict, item: dict, cp: int) -> int:
    """The price of one piece for this character."""
    name = item["name"]
    if item["kind"] == "service" or not clause or cp <= 0:   # nothing to change about a free thing or one the shop pays you to take
        return cp
    if clause == "hens_and_leather":
        if is_hen(name):
            return max(1, round(cp / 10))
        made = materials.made_of(name, item["kind"])
        if made and made[0] == "leather":
            return cp * 2
    if clause == "rope_and_light" and shop_id == places.ROLES["outfitter"]:
        if is_rope(name):
            return max(1, round(cp / 2))
        if is_light(name):
            return cp * 2
    if clause == "round_gold" and cp > 100:
        return cp // 100 * 100 if shop_id == places.ROLES["junk"] else -(-cp // 100) * 100
    return cp


def sell_rate(clause: str | None, shop_id: str, shop: dict, thing: dict, rate: float) -> float:
    """The share of its own price a shop pays this character; 0 means it buys nothing."""
    if clause == "sixty" and abs(rate - places.SELL_BACK) < 1e-9:
        return 0.6
    if clause == "hens_for_groderick" and shop_id == places.ROLES["junk"]:
        return rate * 2 if is_hen(thing["name"]) else 0.0
    return rate


def stay_terms(clause: str | None, deal: dict) -> dict:
    """A bed for this character: the pet fee on top, or the worst bed."""
    if clause == "pet_fee":
        fee = dcc.cost_in_cp(places.PET_FEE) or 0
        return {**deal, "price_cp": deal["price_cp"] + fee, "pet_fee_cp": fee}
    if clause == "worst_bed":
        return {**deal, "hp": max(0, deal["hp"] - 1), "ability": max(0, deal["ability"] - 1), "worst": True}
    return deal


def tax_payment(clause: str | None, cp: int) -> int:
    """What the office actually takes of an offered sum: under "sevens" the largest multiple of seven in it."""
    return cp - cp % SEVEN if clause == "sevens" else cp
