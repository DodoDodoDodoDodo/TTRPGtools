"""Prices and production that come out of the economy itself, switched on by ``places.MARKET`` (None: off, the old fixed prices).

Nothing in here says "this price follows that price". A price is made from what is on the shelf (``reprice``); a producer
decides what to make from the price of the day and the goods arrive after the time the work takes (``daily.arrive`` with a
``lag``); eggs come from hens that were fed. A chain such as barley, hens, eggs then swings by itself.

The stuck-episode mechanisms are separate switches (own use, ratchet, momentum), each an ordinary piece of behaviour:
none of them names a price or a duration it should produce. Tuning numbers are PLACEHOLDERS, found in scripts/westmarch_lab.py.
"""

from __future__ import annotations

import math
import random

from . import lives, materials, places

WANT_USUAL = 10    # the usual stock of a raw material a workshop wants (half of town.WANT_CAP, which it stops buying at)

DEFAULT = {
    "floor": 0.05,                                   # the village is never read as emptier than this share of its usual stock
    # ``village`` is how much the stock of the whole village (traders' packs and unlisted shelves included) counts, against the shelf alone.
    # A shelf is never read as emptier than ``floor`` (its share of usual stock) nor priced outside ``range`` (times the usual price).
    # Prices move in logarithms: ``speed`` is the share of the log-distance to the scarcity price covered per night. Free is the 1 cp minimum.
    "staple": {"exp": 0.9, "village": 1.0, "floor": 0.02, "range": (0.01, 90.0), "speed": 0.4, "calm": 0.15},   # food, small goods: calm is the share of the old wave that is left
    "gear": {"exp": 1.5, "village": 0.25, "floor": 0.2, "range": (0.01, 90.0), "speed": 0.7, "calm": 1.8},        # weapons, armor, gear: their shelves are a few pieces, so one sale is a big step
        # What the players (not the traders) buy pushes prices up, for weeks. ``heat`` is the units of a good bought, against its usual stock, and
    # fades ``heat_decay`` a night; ``spent`` is the coin the players paid out and fades ``spent_decay`` a night. A good's price asks
    # for 1 + heat_gain * heat times, and every price for 1 + infl_gain * spent / infl_ref times: the players' own inflation.
    "heat_gain": 1.5, "heat_decay": 0.07,
    "infl_gain": 1.0, "infl_ref": 10000, "spent_decay": 0.05, "infl_cap": 30.0,
    "bounty_step": 0.05, "bounty_max": 0.5,           # in a glut so great that the scarcity price falls below the range, the shop pays this share of the usual price per tenfold of it
    # Weather: the farm trades' yield swings with a slow random walk shared by all of them (a bumper year, a drought): exp(sigma * z), z drifting
    # with ``memory`` per night. Nobody scripts a good year; it floods the market and the price falls to nothing until the glut is eaten.
    "weather": {"sigma": 1.0, "memory": 0.985},
    "junk_cap": 40,                                  # an unlisted shelf (the junk shop) takes at most this many of a kind: a shop that already has 28.000 candles says enough (None: no limit)
    "cheap_reserve": True,                           # a producer with ``stock_up_cheap`` fills its cellar further while the input is cheap, against a drought
    "wholesale": 0.85,                               # share of its price a shop pays for fresh staples (it resells them at once); other goods stay at SELL_BACK
    "margin": 0.85,                                  # a producer with a recipe works only while its good holds this share of its input's price
    "plant_exp": 1.2,                                # how strongly the price of the day decides how much is made
    "plant_range": (0.0, 10.0),                     # ... between this many times the usual amount: a 40-fold price brings a flood, a free good stops the work
    "lay": 1.0,                                      # eggs per fed hen and night
    "ratchet": None,                                 # {"down": 0.06, "above": 1.5}: a dear staple's log-price falls only this fast
    "own_use": None,                                 # {"goods": [...], "above": 1.6, "fill": 0.4, "cap_days": 3.5, "eat": 0.03, "rest": 10}
    "momentum": None,                                # {"rise": 0.25, "days": 5, "buy": 3}: traders chase a rising price
    "till_float": 3000,                              # coppers a till keeps; of what it holds above that, ``wage_share`` goes to the households each night
    "wage_share": 0.03, "refill_share": 0.05,
    # The caravan's crew drinks and eats in the village while the wagons stand there (paid from the coin in the wagons), per night:
    "crew_diet": {"Ale, a jug": 10, "Rations, per day": 8, "Eggs, a dozen": 2, "Stinky cheese": 2, "Smoked eel": 2},
    # One delver goes into the dungeon and comes back about every ``every`` days with ``gp`` gold pieces of treasure: new coin, the bank's, spent
    # at once: ``inn`` of it at the inn, the rest by the households. Dungeon treasure is how coin enters the village; the caravan is how it leaves.
    # He also replaces what the dungeon took: with ``gear`` of his treasure he buys the dearest weapon, armor or shield the smith has that he can pay for.
    # It goes into the dungeon with him and does not come back (that is how a smith gets work, and how metal leaves the village).
    "delver": {"name": "Garrick Dunmoor", "every": (26, 34), "gp": (4, 6), "inn": 0.4, "till": "good-inn", "gear": 0.6},
    # The herb woman lives by selling herbs and forecasts to the households: while her purse is below the steward's working capital they pay her
    # up to ``herb_cap`` coppers a night (never the Finanzamt: it does not help people).
    "herb_cap": 20,
    "relief_floor": 500, "relief_gift": 300,         # a tradesman whose purse is below ``relief_floor`` coppers gets up to ``relief_gift`` a night from the households: neighbours look after their own
    "reserve": 3000, "family_share": 0.02,           # a trader's purse above ``reserve`` coppers feeds the family: this share of the excess goes to the households each night
    "diet": {"Rations, per day": 3, "Ale, a jug": 5, "Eggs, a dozen": 1, "Stinky cheese": 1, "Smoked eel": 1, "Barley, a sack": 1, "Coal, a sack": 1, "Hen": 0.1},
    "diet_scale": 0.3,                               # the whole diet at once, to tune the village's appetite against what the producers can make
    "hh_ref": 40000,                                 # coppers the households hold when they eat their usual diet; they eat more with more coin, less with less
    "diet_elasticity": 0.6,                          # the village eats less of what is dear: units * price ** -elasticity
}


def config() -> dict | None:
    return {**DEFAULT, **places.MARKET} if places.MARKET is not None else None


def _local(shop: dict) -> bool:
    """Does this place belong to the village's own household flows? Not the caravan, whose wagons carry their own coin away, and not the library."""
    return "till" in shop and "caravan" not in shop.get("kinds", []) and "library" not in shop.get("kinds", [])


def stock_levels(state: dict) -> tuple[dict, dict]:
    """(pieces of each good in the village, usual pieces): shelves plus what traders carry, against the shelves' targets."""
    have: dict[str, int] = {}
    usual: dict[str, int] = {}
    for shop in state["shops"].values():
        for line in shop["stock"]:
            if line["kind"] == "service" or line.get("gone") or line["qty"] is None:
                continue
            have[line["name"]] = have.get(line["name"], 0) + int(line["qty"])
            usual[line["name"]] = usual.get(line["name"], 0) + int(line.get("target") or 0)
    for bot in state.get("bots", {}).values():
        for thing in bot.get("inventory", []):
            if thing["name"] in have:
                have[thing["name"]] += int(thing.get("qty", 1))
    return have, usual


def reprice(state: dict, day: int) -> None:
    """One night of scarcity pricing. Each stocked line moves toward the price its scarcity asks for: dear when its shelf and
    the village are low, cheap when they are full; it moves a fraction of the way each night, so the price remembers."""
    cfg = config()
    if not cfg:
        return
    have, usual = stock_levels(state)
    book = state.setdefault("market", {})
    heat = book.setdefault("heat", {})
    for name in list(heat):
        heat[name] = round(heat[name] * (1 - cfg["heat_decay"]), 4)
        if heat[name] < 0.01:
            del heat[name]
    book["spent"] = round(float(book.get("spent", 0)) * (1 - cfg["spent_decay"]), 2)
    inflation = min(cfg["infl_cap"], 1 + cfg["infl_gain"] * book["spent"] / cfg["infl_ref"])   # the players' own inflation, on everything
    book["inflation"] = round(inflation, 3)
    seen: dict[str, list[float]] = {}
    for shop in state["shops"].values():
        for line in shop["stock"]:
            if line["kind"] == "service" or line.get("gone"):
                continue
            name = line["name"]
            staple = materials.is_produce(name) or materials.is_raw(name)   # raw materials a workshop collects are priced like food: a pile of scrap is worth little
            kind = cfg["staple" if staple else "gear"]
            line["calm"] = kind["calm"]    # a shelf that never runs out has no scarcity: only its wave moves its price
            if line.get("target") is None and line["qty"] is not None and name.lower() in [w.lower() for w in shop.get("wants") or []]:
                line["target"] = WANT_USUAL    # what a workshop collects (scrap, hides) has a usual stock like any shelf, so the diggers can see when it is full
            if line["qty"] is None:
                continue
            listed = bool(line.get("target"))   # a shelf with no usual stock is priced by the village's scarcity alone
            local = max(kind["floor"], int(line["qty"]) / int(line["target"])) if listed else 1.0
            village = max(cfg["floor"], have.get(name, 0) / usual[name]) if usual.get(name) else 1.0
            goal = local ** -kind["exp"] * village ** -kind["village"] * inflation
            if usual.get(name) and heat.get(name):
                goal *= 1 + cfg["heat_gain"] * heat[name] / usual[name]
            if goal < kind["range"][0]:   # below the cheapest the market goes: the shop would rather pay to be rid of it
                line["bounty"] = round(min(cfg["bounty_max"], cfg["bounty_step"] * math.log10(kind["range"][0] / goal)), 3)
            else:
                line.pop("bounty", None)
            goal = max(kind["range"][0], min(kind["range"][1], goal))
            old = max(kind["range"][0], float(line.get("drift", 1.0)))
            speed = kind["speed"]
            if staple and cfg.get("ratchet") and goal < old and old > cfg["ratchet"]["above"]:
                speed = cfg["ratchet"]["down"]
            line["drift"] = round(math.exp(math.log(old) + speed * (math.log(goal) - math.log(old))), 4)
            seen.setdefault(name, []).append(line["drift"])
    book["rel"] = {name: sum(values) / len(values) for name, values in seen.items()}
    book["fill"] = {name: have.get(name, 0) / usual[name] for name in seen if usual.get(name)}
    hist = book.setdefault("hist", {})
    for name, value in book["rel"].items():
        hist[name] = (hist.get(name, []) + [round(value, 4)])[-14:]


def view(state: dict) -> dict:
    """What a producer can see of the market tonight: ``rel`` (a good's price against its usual) and ``fill`` (its stock against usual)."""
    return state.get("market") or {}


def eagerness(cfg: dict, spec: dict, name: str, rel: dict) -> float:
    """How much more or less of a good a producer makes at today's price: the price of the good itself, or of the good the trade
    watches instead (a hen keeper's hens follow the price of eggs as well), whichever asks for more."""
    low, high = cfg["plant_range"]
    seen = [name, (spec.get("watch") or {}).get(name, name)]
    return max(low, min(high, max(rel.get(g, 1.0) ** cfg["plant_exp"] for g in seen)))


def recipes(spec: dict, name: str) -> list[tuple[str, int]]:
    """What a good is made from: [(input, pieces made per input)]. One pair, or a list of pairs when the good can be made several ways."""
    r = (spec.get("makes_from") or {}).get(name)
    if not r:
        return []
    return [tuple(r)] if isinstance(r[0], str) else [tuple(x) for x in r]


_BASE: dict[str, int] = {}


def base_cp(name: str) -> int:
    """The usual price of a good in copper, as the small goods and the producers list it."""
    if not _BASE:
        from ttrpgtools import dcc
        for good, price in places.SMALL_GOODS:
            _BASE[good] = dcc.cost_in_cp(price) or 1
        for spec in places.BOTS:
            for good, _kind, cost, *_ in spec.get("brings", []):
                _BASE.setdefault(good, dcc.cost_in_cp(cost) or 1)
    return _BASE.get(name, 1)


def worth_making(cfg: dict, spec: dict, name: str, rel: dict) -> bool:
    """A producer with a recipe works only while the product still fetches its share of what an input costs: any way of making it that pays."""
    options = recipes(spec, name)
    return not options or any(rel.get(name, 1.0) >= cfg["margin"] * rel.get(source, 1.0) for source, _ in options)


def queued(bot: dict, name: str) -> int:
    return sum(int(e["count"]) for e in bot.get("pipeline", []) if e["name"] == name)


def queue(bot: dict, name: str, kind: str, cost: str, count: int, due: int) -> None:
    bot.setdefault("pipeline", []).append({"name": name, "kind": kind, "cost": cost, "count": int(count), "due": int(due)})


def arrived(bot: dict, day: int) -> list[dict]:
    """The queued goods whose time has come; they leave the queue."""
    pipeline = bot.get("pipeline", [])
    ready = [e for e in pipeline if e["due"] <= day]
    bot["pipeline"] = [e for e in pipeline if e["due"] > day]
    return ready


def eggs_laid(bot: dict, spec: dict, cfg: dict, run: float) -> int:
    """Dozens of eggs laid tonight: every hen that was fed lays, the moon sways the flock. Eggs below a dozen wait for tomorrow."""
    if not spec.get("lays"):
        return 0
    bot["laid"] = float(bot.get("laid", 0)) + float(bot.get("hens_fed", 0)) * cfg["lay"] * run
    dozens = int(bot["laid"] // 12)
    bot["laid"] -= dozens * 12
    return dozens


def own_use(bot: dict, spec: dict, cfg: dict, view_: dict, day: int = 0) -> None:
    """The producer keeps back what they make of a scarce, dear good, as the tailor wears the only shirt, until what is kept is
    enough for a good while or the price has come down; then it all goes to the shelf and, their own need met, they keep nothing
    back for a rest period. Some of what is kept is used up each night."""
    rule = cfg.get("own_use")
    if not rule:
        return
    kept = bot.setdefault("kept", {})
    for name, kind, cost, *most in spec.get("brings", []):
        if name not in rule["goods"]:
            continue
        rel, fill = view_.get("rel", {}).get(name, 1.0), view_.get("fill", {}).get(name, 1.0)
        stack = next((i for i in bot["inventory"] if i["name"] == name), None)
        if stack and rel > rule["above"] and fill < rule["fill"] and day >= bot.get("rested_until", 0):
            kept[name] = float(kept.get(name, 0)) + int(stack.get("qty", 1))
            stack["qty"] = 0
            bot["inventory"] = [i for i in bot["inventory"] if int(i.get("qty", 1)) > 0]
        kept[name] = float(kept.get(name, 0)) * (1 - rule["eat"])
        if kept[name] >= rule["cap_days"] * (int(most[0]) if most else 2) or (kept[name] >= 1 and rel < 0.7 * rule["above"]):
            bot.setdefault("release", {})[name] = int(kept[name])
            kept[name] = 0.0
            bot["rested_until"] = day + int(rule.get("rest", 10))


def rising(state: dict, name: str, cfg: dict) -> bool:
    """Has the good's price gone up by the momentum rule's share over its days?"""
    rule = cfg.get("momentum")
    hist = (state.get("market") or {}).get("hist", {}).get(name, [])
    return bool(rule and len(hist) > rule["days"] and hist[-1] >= (1 + rule["rise"]) * hist[-1 - rule["days"]])


def wages(state: dict, cfg: dict) -> int:
    """The tills' surplus goes to the households (owners, staff and families of the shops), a share each night: coin that would
    pool in a till comes back into the village. Coin only moves. Returns the coppers paid."""
    paid = 0
    room = max(0.0, 1 - int(state["money"].get("households", 0)) / (2 * cfg["hh_ref"]))   # households that already hold plenty are paid less: coin stays in the tills
    wages_to: dict = {}
    for shop in state["shops"].values():
        surplus = int(shop.get("till", 0)) - cfg["till_float"]
        if surplus > 0 and room > 0 and _local(shop):
            cut = max(1, int(surplus * cfg["wage_share"] * room))
            shop["till"] = int(shop["till"]) - cut
            paid += cut
            wages_to[shop.get("keeper") or ""] = wages_to.get(shop.get("keeper") or "", 0) + cut
    if state.get("household_mode"):   # a shop's wages go home with its keeper (households.py); the rest of the pool is unchanged
        from . import households, registry
        db = registry.connect()
        try:
            for keeper, cut in wages_to.items():
                households.credit(state, db, households.of(db, keeper), cut)
        finally:
            db.close()
    else:
        state["money"]["households"] = int(state["money"].get("households", 0)) + paid
    return paid


def refill(state: dict, cfg: dict) -> int:
    """Everyday spending the diet leaves out (labour, repairs, a drink): the households top up the tills that have fallen below their
    float, a share of what the households hold each night, so a shop that has paid out its coin can pay the next seller. Coin only moves."""
    held = int(state["money"].get("households", 0))
    moved = 0
    for shop in state["shops"].values():
        deficit = cfg["till_float"] - int(shop.get("till", 0))
        if _local(shop) and deficit > 0 and held - moved > 0:
            give = min(deficit, max(1, int((held - moved) * cfg["refill_share"])))
            shop["till"] = int(shop["till"]) + give
            moved += give
    state["money"]["households"] = held - moved
    return moved


def eat(state: dict, day: int, cfg: dict) -> dict:
    """The households eat: each staple of the diet, a few units a night, fewer when it is dear, bought from the cheapest shelf
    that has it with the coin the households hold (never more). What is eaten is gone; the coin lands in the till. Returns what was eaten."""
    from . import town
    rng = random.Random(f"{day}/households")
    book = state.get("market") or {}
    eaten: dict[str, int] = {}
    means = max(0.2, min(1.5, int(state["money"].get("households", 0)) / cfg["hh_ref"]))
    for good, per_night in cfg["diet"].items():
        want = means * cfg["diet_scale"] * per_night * min(6.0, book.get("rel", {}).get(good, 1.0) ** -cfg["diet_elasticity"])   # at most six times the diet, however cheap
        units = int(want) + (1 if rng.random() < want - int(want) else 0)
        for _ in range(units):
            offers = [(town.price_cp(shop, line, day), shop_id, line) for shop_id, shop in state["shops"].items() if _local(shop)
                      for line in shop["stock"] if line["name"] == good and line["qty"] and not line.get("gone") and line["kind"] != "service"]
            if not offers:
                break
            price, shop_id, line = min(offers, key=lambda o: o[0])
            price = max(0, price)   # a household eats a free meal; it is not paid for eating a glut
            if price > int(state["money"].get("households", 0)):
                break
            line["qty"] = int(line["qty"]) - 1
            state["shops"][shop_id]["till"] = int(state["shops"][shop_id]["till"]) + price
            state["money"]["households"] = int(state["money"]["households"]) - price
            eaten[good] = eaten.get(good, 0) + 1
    return eaten


def fresh_start(state: dict, capital_cp: int = 1500, flock: int = 12, pile: int = 3, purse_cap_cp: int = 20000) -> dict:
    """Settle the village before the market switches on: every staple shelf at its usual stock (unlisted ones at most 6), no
    piles of staples in the traders' packs (at most ``pile`` of a kind), a flock for the hen keeper, and working capital for
    every producer, moved from the Finanzamt (coin only moves; a producer who cannot buy inputs cannot make anything). A trader's
    purse above ``purse_cap_cp`` (the 20.000 gp test windfall of 2026-10-07) goes back to the Finanzamt. Returns what was done."""
    from ttrpgtools import dcc
    from . import daily
    done = {"shelves": 0, "capital_cp": 0, "hens": 0, "returned_cp": 0}
    for key, bot in state.get("bots", {}).items():
        excess = dcc.coins_total_cp(bot["coins"]) - (max(purse_cap_cp, places.STEWARD_CAPITAL_CP) if key == "hedwig-d" else purse_cap_cp)
        if excess > 0:
            state["money"]["finanzamt"] += excess
            bot["coins"] = {"gp": purse_cap_cp // 100, "sp": 0, "cp": 0}
            done["returned_cp"] += excess
    for shop in state["shops"].values():
        for line in shop["stock"]:
            if line["kind"] == "service" or line["qty"] is None or not materials.is_produce(line["name"]):
                continue
            line["qty"] = int(line["target"]) if line.get("target") else min(int(line["qty"]), 6)
            done["shelves"] += 1
    for bot in state.get("bots", {}).values():
        for thing in bot["inventory"]:
            if materials.is_produce(thing["name"]) and thing["name"] != "Hen":
                thing["qty"] = min(int(thing.get("qty", 1)), pile)
        bot["inventory"] = [i for i in bot["inventory"] if int(i.get("qty", 1)) > 0 and i["name"] != "Hen"]
    for spec in places.BOTS:
        bot = state["bots"].get(spec["id"]) or (daily._record(state, spec) if spec.get("steward") else None)   # the steward arrives with her purse
        if bot is not None and spec.get("steward"):
            top = max(0, places.STEWARD_CAPITAL_CP - dcc.coins_total_cp(bot["coins"]))
            if top and state["money"]["finanzamt"] >= top:
                state["money"]["finanzamt"] -= top
                total = dcc.coins_total_cp(bot["coins"]) + top
                bot["coins"] = {"gp": total // 100, "sp": total % 100 // 10, "cp": total % 10}
                done["capital_cp"] += top
            continue
        if bot is None or not (spec.get("brings") and (spec.get("stock_up") or spec.get("makes_from") or spec.get("lays") or spec.get("lag"))):
            continue
        top = max(0, capital_cp - dcc.coins_total_cp(bot["coins"]))
        if top and state["money"]["finanzamt"] >= top:
            state["money"]["finanzamt"] -= top
            bot["coins"] = {"gp": (dcc.coins_total_cp(bot["coins"]) + top) // 100, "sp": (dcc.coins_total_cp(bot["coins"]) + top) % 100 // 10, "cp": (dcc.coins_total_cp(bot["coins"]) + top) % 10}
            done["capital_cp"] += top
        if spec.get("lays"):
            egg_cost = next(b for b in spec["brings"] if b[0] == "Hen")
            missing = flock - sum(int(i.get("qty", 1)) for i in bot["inventory"] if i["name"] == "Hen")
            if missing > 0:
                daily._bring(bot, spec, "Hen", egg_cost[1], egg_cost[2], missing, state.get("last_daily") or 0)
                done["hens"] += missing
    return done


def note_purchase(state: dict, name: str, kind: str, count: int, paid_cp: int, by_bot: bool) -> None:
    """A sale to a buyer is noted for the next night's prices. Traders' buying works through the emptied shelves alone; what the
    players buy also heats the good it was (services only count as coin spent) and raises every price a little."""
    if by_bot or not config():
        return
    book = state.setdefault("market", {})
    book["spent"] = float(book.get("spent", 0)) + paid_cp
    if kind != "service":
        heat = book.setdefault("heat", {})
        heat[name] = float(heat.get(name, 0)) + count


def families(state: dict, cfg: dict) -> int:
    """Coin a trader holds above the reserve is spent on the family, a share each night: it goes to the households. Without this the
    producers' purses collect all the coin and the village runs dry. Coin only moves. Returns the coppers moved."""
    from ttrpgtools import dcc
    moved = 0
    homes: dict = {}
    for key, bot in state.get("bots", {}).items():
        excess = dcc.coins_total_cp(bot["coins"]) - (places.STEWARD_CAPITAL_CP if key == "hedwig-d" else cfg["reserve"])   # the steward keeps her capital; what she earns above it goes home
        if excess > 0:
            cut = max(1, int(excess * cfg["family_share"]))
            total = dcc.coins_total_cp(bot["coins"]) - cut
            bot["coins"] = {"gp": total // 100, "sp": total % 100 // 10, "cp": total % 10}
            moved += cut
            homes[bot.get("name") or key] = homes.get(bot.get("name") or key, 0) + cut
    if state.get("household_mode"):   # the trader's surplus feeds the trader's own household
        from . import households, registry
        db = registry.connect()
        try:
            for name, cut in homes.items():
                households.credit(state, db, households.of(db, name), cut)
        finally:
            db.close()
    else:
        state["money"]["households"] = int(state["money"].get("households", 0)) + moved
    return moved


def step_weather(state: dict, day: int) -> float:
    """One night of weather: z is an AR(1) walk (seeded by the day, so a rerun of the same night gives the same sky); the yield factor is exp(sigma * z)."""
    import random
    cfg = config()
    rule = cfg and cfg.get("weather")
    book = state.setdefault("market", {})
    if not rule:
        book["weather"] = 1.0
        return 1.0
    z = float(book.get("z", 0.0))
    z = rule["memory"] * z + math.sqrt(1 - rule["memory"] ** 2) * random.Random(f"{day}/weather").gauss(0, 1)
    book["z"] = round(z, 4)
    book["weather"] = round(math.exp(rule["sigma"] * z), 3)
    return book["weather"]


def crew_eats(state: dict, day: int, cfg: dict) -> dict:
    """While the wagons stand in the village the crew buys ale and food from the cheapest shelf that has it, paying from the caravan's coin
    (the camp's till): what they eat is gone, their coin lands in the village's tills. Returns what was eaten."""
    from . import town
    camp = state["shops"].get("caravan")
    eaten: dict[str, int] = {}
    if not camp or camp.get("away"):
        return eaten
    for good, units in cfg["crew_diet"].items():
        for _ in range(units):
            offers = [(max(0, town.price_cp(shop, line, day)), shop_id, line) for shop_id, shop in state["shops"].items() if _local(shop)
                      for line in shop["stock"] if line["name"] == good and line["qty"] and not line.get("gone") and line["kind"] != "service"]
            if not offers:
                break
            price, shop_id, line = min(offers, key=lambda o: o[0])
            if price > int(camp.get("till", 0)):
                break
            line["qty"] = int(line["qty"]) - 1
            state["shops"][shop_id]["till"] = int(state["shops"][shop_id]["till"]) + price
            camp["till"] = int(camp["till"]) - price
            eaten[good] = eaten.get(good, 0) + 1
    return eaten


def delver(state: dict, day: int, cfg: dict) -> int:
    """The village's one delver comes back from the dungeon now and then with a few gold pieces of treasure. The bank mints it (the only way coin
    is made), and it is spent in the village the same night. Returns the coppers brought, 0 on the other nights."""
    import random
    from . import town
    rule = cfg.get("delver")
    if not rule:
        return 0
    book = state.setdefault("delver", {})
    if "next" not in book:
        book["next"] = day + random.Random(f"{day}/delver/first").randint(*rule["every"])
    if day < book["next"]:
        return 0
    rng = random.Random(f"{day}/delver")
    who = lives.delver(state, day, rng) if places.LIVES else None   # with ageing he is one of the villagers, and the gold follows his strength
    name = who["name"] if who else rule["name"]
    if who and who["died"]:
        book["next"] = day + rng.randint(*rule["every"])
        town.tell(state, day, f"{name} went into the dungeon and did not come back.")
        return 0
    brought = max(1, round(rng.randint(*rule["gp"]) * (who["factor"] if who else 1.0))) * 100
    town.issue(state, brought, "the dungeon")
    gear_line = ""
    smith_id = places.ROLES.get("smith")
    if rule.get("gear") and smith_id in state["shops"]:
        smith = state["shops"][smith_id]
        budget = int(brought * rule["gear"])
        pieces = [(town.price_cp(smith, line, day), line) for line in smith["stock"]
                  if line["kind"] in ("weapon", "armor", "shield") and line["qty"] and not line.get("gone")]
        pieces = [(price, line) for price, line in pieces if 0 < price <= budget]
        if pieces:
            price, line = max(pieces, key=lambda t: (t[0], t[1]["name"]))
            town.move(state, "bank", f"till:{smith_id}", price, who="the dungeon")
            line["qty"] = int(line["qty"]) - 1
            town._marks_fit(line)
            gear_line = f" He bought a {line['name']} from the smith for {town.coins_text(price)} and took it into the dungeon."
        else:
            price = 0
    else:
        price = 0
    inn = int((brought - price) * rule["inn"])
    till = rule["till"]
    if inn and till in state["shops"]:
        town.move(state, "bank", f"till:{till}", inn, who="the dungeon")
    rest = brought - price - (inn if till in state["shops"] else 0)
    if rest > 0:
        town.move(state, "bank", "households", rest, who="the dungeon")
    book["next"] = day + rng.randint(*rule["every"])
    town.tell(state, day, f"{name} came back from the dungeon with {town.coins_text(brought)} and spent it in the village's inn and kitchens." + gear_line)
    return brought


def relief(state: dict, cfg: dict) -> int:
    """Neighbours look after their own: a trader with a trade whose purse has fallen below the floor gets a gift from the households, as far as
    they have the coin. Without it, a producer who has once run out of working capital can never buy inputs again. Returns the coppers moved."""
    from ttrpgtools import dcc
    moved = 0
    for spec in places.BOTS:
        bot = state.get("bots", {}).get(spec["id"])
        if bot is None or spec.get("steward") or not (spec.get("brings") or spec.get("makes_from")):
            continue
        purse = dcc.coins_total_cp(bot["coins"])
        give = min(cfg["relief_gift"], cfg["relief_floor"] - purse, int(state["money"].get("households", 0)))
        if purse < cfg["relief_floor"] and give > 0:
            total = purse + give
            bot["coins"] = {"gp": total // 100, "sp": total % 100 // 10, "cp": total % 10}
            state["money"]["households"] = int(state["money"]["households"]) - give
            moved += give
    return moved


def herbs(state: dict, cfg: dict) -> int:
    """The herb woman's living: the households buy herbs and forecasts from her, a few coppers a night, while her purse is below the steward's working
    capital. Not the Finanzamt: the village pays its own elf. Coin only moves. Returns the coppers moved."""
    from ttrpgtools import dcc
    me = state.get("bots", {}).get("hedwig-d")
    if not me or places.STEWARD is None:
        return 0
    give = min(int(cfg["herb_cap"]), places.STEWARD_CAPITAL_CP - dcc.coins_total_cp(me["coins"]), int(state["money"].get("households", 0)))
    if give <= 0:
        return 0
    total = dcc.coins_total_cp(me["coins"]) + give
    me["coins"] = {"gp": total // 100, "sp": total % 100 // 10, "cp": total % 10}
    state["money"]["households"] = int(state["money"]["households"]) - give
    return give
