"""What things are made of. Goods are a closed system like the coin: nothing appears or vanishes by itself.

Every piece of equipment is made of one material and has a weight. A shop can only make a piece when its workshop
holds that weight of the material (``town.restock``), and gets material back by breaking pieces up, at the
material's recycling rate. Small goods (food, candles, the trade goods) have no entry here: the villagers bring
them, a piece at a time (``places.PRODUCE``, ``daily.produce``).

The rulebook gives no weights. Every number below is a PLACEHOLDER written for this campaign, in kilograms for one
piece (one arrow, not one bundle).
"""

from __future__ import annotations

import re

from ttrpgtools import dcc
from . import items, places

# recycle: the share that comes back when a piece is broken up. None: never broken up.
MATERIALS = {
    "metal": {"name": "Metal", "recycle": 1.0},
    "leather": {"name": "Leather and stuff", "recycle": 1.0},   # the catch-all: leather, paper, cloth, rope, flint, anything organic
    "tech": {"name": "Oldwork", "recycle": 0.5},  # half is lost each time
    "wood": {"name": "Wood", "recycle": None},                 # harvested by villagers instead
}

_TABLE = {
    # weapons
    "Battleaxe": ("metal", 3.0), "Blackjack": ("leather", 1.0), "Blowgun": ("wood", 0.5), "Club": ("wood", 1.5),
    "Crossbow": ("wood", 3.0), "Dagger": ("metal", 0.5), "Dart": ("metal", 0.25), "Flail": ("metal", 2.5),
    "Garrote": ("leather", 0.1), "Handaxe": ("metal", 1.5), "Javelin": ("wood", 1.0), "Lance": ("wood", 4.5),
    "Longbow": ("wood", 1.5), "Longsword": ("metal", 2.0), "Mace": ("metal", 3.0), "Polearm": ("metal", 5.0),
    "Shortbow": ("wood", 1.0), "Short sword": ("metal", 1.0), "Sling": ("leather", 0.1), "Spear": ("wood", 2.5),
    "Staff": ("wood", 2.0), "Two-handed sword": ("metal", 4.0), "Warhammer": ("metal", 3.5),
    # armor
    "Padded": ("leather", 4.5), "Leather": ("leather", 7.0), "Studded Leather": ("leather", 9.0), "Hide": ("leather", 11.0),
    "Scale Mail": ("metal", 14.0), "Chainmail": ("metal", 18.0), "Banded Mail": ("metal", 16.0), "Half-Plate": ("metal", 22.0),
    "Full Plate": ("metal", 25.0), "Shield": ("wood", 4.0),
    # ammunition, one piece
    "Arrows": ("wood", 0.05), "Arrows, silver-tipped": ("wood", 0.05), "Quarrels": ("wood", 0.05),
    # gear
    "Backpack": ("leather", 1.0), "Chain, 10’": ("metal", 1.0), "Chest, empty": ("wood", 11.0), "Crowbar": ("metal", 2.5),
    "Flask, empty": ("leather", 0.7), "Flint & steel": ("leather", 0.1), "Grappling hook": ("metal", 2.0),
    "Hammer, small": ("metal", 1.0), "Holy symbol": ("metal", 0.5), "Iron spikes, each": ("metal", 0.5),
    "Lantern": ("tech", 1.0), "Mirror, hand-sized": ("tech", 0.25), "Pole, 10-foot": ("wood", 3.5), "Rope, 50’": ("leather", 4.5),
    "Sack, large": ("leather", 0.5), "Sack, small": ("leather", 0.25), "Thieves’ tools": ("tech", 0.5), "Waterskin": ("leather", 0.5),
    # dug out of the hill and sold to the smith, who melts it: one lump
    "Scrap metal": ("metal", 1.0),
    # tanned by the leatherworker from the hides of the village's beasts and sold to the shops that work leather
    "Tanned hide": ("leather", 1.5),
    # forged far away and brought by the caravan, never made here: the smith may melt it into his work
    "Eastern steel, an ingot": ("metal", 2.0),
    # mount gear
    "Bridle and Bit": ("leather", 0.5), "Saddle, pack": ("leather", 7.0), "Saddle, riding": ("leather", 11.0), "Saddlebags": ("leather", 3.5),
}
WEIGHTS = {dcc._slug(name): entry for name, entry in _TABLE.items()}

# Things without a line above (an occupation's tools, loot, second-hand oddities) are placed by a word in their name.
_GUESSES = [
    (r"quill|pelt|leather|hide|parchment|book|cloth|rope|sack|bag|flint|paper|fabric|rag|boot|glove|net|rug|linen|wax|ink|fur|hat|cloak|robe", "leather", 0.5),
    (r"spyglass|lens|clock|lantern|mirror|tools", "tech", 0.5),
    (r"stick|club|cudgel|pole|pitchfork|bow|staff|oar|barrel|crate|ladder|wood|wooden", "wood", 1.5),
    (r"sword|longsword|axe|cleaver|knife|dagger|helmet|hammer|scissors|razor|shears|awl|chisel|pick|trowel|crowbar|shovel|iron|steel|tongs|ring|key|lock|chain|nail|needle|bell|mace|spike", "metal", 1.0),
]
_GUESSES = [(re.compile(rf"\b(?:{words})s?\b"), material, kg) for words, material, kg in _GUESSES]


RAW = {dcc._slug("Scrap metal"), dcc._slug("Eastern steel, an ingot"), dcc._slug("Tanned hide")}   # made of a material, yet not made in a workshop: dug up here, or forged far away


def is_raw(name: str) -> bool:
    return dcc._slug(name) in RAW


def kg_text(grams: int) -> str:
    """'4,0 kg', '0,25 kg': German decimal comma like the coin, two places only where they are needed."""
    text = f"{grams / 1000:.2f}"
    return (text[:-1] if text.endswith("0") else text).replace(".", ",") + " kg"


def is_produce(name: str) -> bool:
    """Is this a small good that is grown, brewed, dug or kept rather than made in a workshop: whatever the villagers
    produce, the small goods and the trade goods of places.py. A word in a name ("a sack of barley") never makes it a
    leather good."""
    slug = dcc._slug(name)
    return (any(dcc._slug(entry.get("good", "")) == slug for entry in places.PRODUCE)
            or any(dcc._slug(good_name) == slug for good_name, _ in places.SMALL_GOODS)
            or any(dcc._slug(good["name"]) == slug for good in places.TRADE_GOODS))


def made_of(name: str, kind: str | None = None) -> tuple[str, int] | None:
    """(material, grams of one piece), or None for what is not made in a workshop: small goods, services, livestock."""
    hit = WEIGHTS.get(dcc._slug(name))
    if hit:
        return hit[0], round(hit[1] * 1000)
    if kind == "service" or is_produce(name):
        return None
    low = name.lower()
    for pattern, material, kg in _GUESSES:
        if pattern.search(low):
            return material, round(kg * 1000)
    if kind == "weapon":
        return "metal", 1000
    if kind in ("armor", "shield"):
        return "leather", 5000
    return None


def census(state: dict) -> dict:
    """Grams of every material in the village: raw in the workshops, and bound in things on shelves, at the library,
    in the traders' packs and in the characters' packs. A piece made or broken up moves weight between the two;
    only Oldwork loses any, and only the admin and the wood harvest add any."""
    out = {m: {"name": spec["name"], "raw_g": 0, "things_g": 0} for m, spec in MATERIALS.items()}

    def count(thing: dict, pieces: int) -> None:
        hit = made_of(thing["name"], thing.get("kind"))
        if hit and pieces > 0:
            out[hit[0]]["things_g"] += hit[1] * pieces

    for shop in state["shops"].values():
        for material, grams in (shop.get("materials") or {}).items():
            if material in out:
                out[material]["raw_g"] += int(grams)
        for line in shop["stock"]:
            if line["kind"] != "service" and line.get("qty") and not line.get("gone"):
                count(line, int(line["qty"]) * int(line.get("units") or 1))
    for bot in state.get("bots", {}).values():
        for thing in bot.get("inventory", []):
            count(thing, int(thing.get("qty", 1)))
    for row in items.everything():
        if row["holder_type"] == "pc":
            count(row, int(row["qty"] or 0))
    for entry in out.values():
        entry["total_g"] = entry["raw_g"] + entry["things_g"]
    return out
