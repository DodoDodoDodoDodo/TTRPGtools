"""The barley fields and the eel ponds: where the village's staple and its eels come from once ``places.FIELDS`` is set.

Fields. A hundred small plots, one per person of the village at the start; they are owned, inherited (widow or widower, else the village's common
pool) and sold. A plot is sown, ripens in ``grow`` nights, is harvested, and rests ``rest`` nights before it can be sown again. Sowing takes seed: one
sack of barley for every ``per_seed`` plots, and the seed is barley the farmer owns (Dodo 10-10): kept back from a harvest, or bought off a shelf. One
person keeps at most ``work`` plots under barley at once. The yield of a plot is ``yield`` sacks times the light of the last ``light_nights`` nights before the
harvest, and the light is the moons': ``light()`` is written down here and nowhere the villagers or the herb woman can read. Who tills: the trader
bots with ``tills`` (the barley farmer, the farmhand) till the plots of theirs that are ready, keep seed back from each harvest, buy a plot when
their hands are idle and no common plot is free, and sell one when they are broke; the villagers whose trade is farming till their own plots, keep
their seed, buy more seed off the shelf with their own coin when short, and bring the rest of the harvest to the shelves for nothing, like PRODUCE.
A farmer whose own plots do not fill their hands works plots of the village's common pool for nothing (Dodo 10-10); the harvest is the worker's.
Everyone else lets their plot lie fallow. Every owner names their own price, "I'd sell it if you gave me so much right now", and that price includes
whatever grows on the plot (Dodo 10-10): ``ask_cp``.

Ponds. The eel farmer has ``ponds``; each gives ``per`` eels every ``days`` nights, smoked the same night for one sack of coal whatever the catch.
On a night the Drowned Moon is bright and the other two are not (``fat_night``), a pond's catch is ``fat`` times as large.
Nobody is told.
"""

from __future__ import annotations

import math
import random
from datetime import date

from ttrpgtools import dcc
from . import places, town, villagers

LIT = {"new": 0.0, "waxing crescent": 0.25, "first quarter": 0.5, "waxing gibbous": 0.75, "full": 1.0, "waning gibbous": 0.75, "last quarter": 0.5, "waning crescent": 0.25}
BARLEY = "Barley, a sack"
EEL = "Smoked eel"
FARMING = {"farmer", "farmhand", "barley farmer"}   # the whole trade, not a word in it: an eel farmer and a mushroom farmer grow no barley


def config() -> dict | None:
    return places.FIELDS


def on_day(day: int) -> date:
    return date.fromordinal(places.EPOCH.toordinal() + day - 1)


def lit(day: int) -> dict[str, float]:
    """How bright each moon stands on a night, 0 (new) to 1 (full)."""
    return {m["id"]: LIT[town.moon(on_day(day), m["id"])["phase"]] for m in places.MOONS}


def light(day: int) -> float:
    """The light barley grows by on one night. The Pale Moon gives most of it, less when the Drowned Moon stands high beside it; the Red Lantern adds a little.
    Averages 1.0 over the years and runs from about 0.4 to 1.6."""
    m = lit(day)
    return 0.4 + 0.9 * m["pale"] * (1 - 0.5 * m["drowned"]) + 0.3 * m["red"]


def harvest_factor(day: int, cfg: dict) -> float:
    nights = int(cfg["light_nights"])
    return max(0.4, min(1.6, sum(light(d) for d in range(day - nights + 1, day + 1)) / nights))


def fat_night(day: int) -> bool:
    """The eels run fat: the Drowned Moon gibbous or full while neither of the other two is. About five nights in six months."""
    m = lit(day)
    return m["drowned"] >= 0.75 and m["pale"] < 0.75 and m["red"] < 0.75


# ---------------------------------------------------------------- the plots
def book(state: dict) -> dict:
    return state.setdefault("fields", {"plots": [], "harvests": [], "sales": [], "common_cp": 0})


def crop_cp(state: dict, plot: dict) -> int:
    """What grows on a plot is worth to its owner: the sacks a plot gives, at today's price of barley. Nothing on a fallow or resting plot."""
    if plot["sown"] is None:
        return 0
    rel = (state.get("market") or {}).get("rel", {}).get(BARLEY, 1.0)
    return int(config()["yield"] * 40 * rel)


def _purses() -> dict[str, int]:
    import json
    from . import registry
    db = registry.connect()
    try:
        return {r["name"]: int(json.loads(r["sheet"])["copper"]) for r in db.execute("SELECT name, sheet FROM people WHERE status = 'alive' AND claimed_by IS NULL AND sheet IS NOT NULL")}
    finally:
        db.close()


def ask_cp(state: dict, plot: dict, purses: dict | None = None, people: dict | None = None) -> int | None:
    """The owner's price for a plot right now, the crop on it included. A villager names it by their attachment to the land (their own, the same every
    time), how short of coin they are (the poor sell cheaper) and whether it is their living (a farmer asks three times as much). A farming trader asks
    what their model set, else three times the usual. The common pool asks the usual price. None: not for sale (a common plot somebody is working)."""
    cfg = config()
    usual = cfg["usual_plot_cp"]
    owner = plot["owner"]
    if owner is None:
        return None if plot.get("worker") else usual
    crop = crop_cp(state, plot)
    trader = next((b for b in places.BOTS if b.get("tills") and person_of(state, b) == owner), None)
    if trader is not None:
        set_by_model = ((state.get("bots") or {}).get(trader["id"], {}).get("asks") or {}).get(str(plot["id"]))
        return int(set_by_model) if set_by_model is not None else cfg["farmer_ask"] * usual + crop
    purses = _purses() if purses is None else purses
    attachment = random.Random(f"plot-ask/{owner}").uniform(*cfg["attachment"])
    need = max(0.4, min(1.5, (purses.get(owner, 0) + 200) / 1200))   # a villager with little coin takes less
    farming = (people or {}).get(owner, "").lower() in FARMING
    return int(usual * attachment * need * (cfg["farmer_ask"] if farming else 1)) + crop


def for_sale(state: dict, day: int, buyer: str | None = None, limit: int = 8) -> list[dict]:
    """The cheapest plots tonight, each with its owner, what is on it, and the owner's price."""
    cfg = config()
    from . import registry
    db = registry.connect()
    try:
        people = {r["name"]: r["occupation"] for r in db.execute("SELECT name, occupation FROM people WHERE status = 'alive'")}
    finally:
        db.close()
    purses = _purses()
    rows = []
    for p in book(state)["plots"]:
        if p["owner"] == buyer:
            continue
        price = ask_cp(state, p, purses, people)
        if price is None:
            continue
        on_it = (f"barley sown {day - p['sown']} nights ago, ripe in {max(0, p['sown'] + cfg['grow'] - day)}" if p["sown"] is not None
                 else "fallow, ready to sow" if ready(p, day) else f"resting {p['rest_until'] - day} more nights")
        rows.append({"plot": p["id"], "owner": p["owner"] or "the village", "on_it": on_it, "ask_cp": price})
    return sorted(rows, key=lambda r: (r["ask_cp"], r["plot"]))[:limit]


def lay_out(state: dict, day: int, owners: list[str]) -> int:
    """The first night: one plot to each person of the village, fallow. Returns how many were laid out."""
    b = book(state)
    if b["plots"]:
        return 0
    cfg = config()
    for n, name in enumerate(owners[:cfg["plots"]]):
        b["plots"].append({"id": n + 1, "owner": name, "sown": None, "rest_until": None})
    while len(b["plots"]) < cfg["plots"]:
        b["plots"].append({"id": len(b["plots"]) + 1, "owner": None, "sown": None, "rest_until": None})
    return len(b["plots"])


def person_of(state: dict, spec: dict) -> str:
    """The person behind a trader, who owns the land: the heir who took the seat over, else the townsperson whose name the trader's starts with
    ("Pip" for "Pip the farmhand")."""
    held = (state.get("seats") or {}).get(spec["id"])
    if held:
        return held
    return next((name for name, _ in villagers.TOWNSFOLK if spec["name"] == name or spec["name"].startswith(name + " ")), spec["name"])


def _tillers(state: dict) -> set[str]:
    return {person_of(state, b) for b in places.BOTS if b.get("tills")}


def owned_by(state: dict, name: str) -> list[dict]:
    return [p for p in book(state)["plots"] if p["owner"] == name]


def worked_by(state: dict, name: str) -> list[dict]:
    """A farmer's land tonight: the plots they own and the common plots they have sown."""
    return [p for p in book(state)["plots"] if p["owner"] == name or (p["owner"] is None and p.get("worker") == name)]


def ready(plot: dict, day: int) -> bool:
    return plot["sown"] is None and (plot["rest_until"] is None or day >= plot["rest_until"])


def ripe(plot: dict, day: int, cfg: dict) -> bool:
    return plot["sown"] is not None and day >= plot["sown"] + cfg["grow"]


def seed_for(count: int, cfg: dict) -> int:
    return math.ceil(count / cfg["per_seed"]) if count else 0


def sow(state: dict, plots: list[dict], day: int, seed_sacks: int, cfg: dict, who: str | None = None) -> int:
    """Sow as many of these plots as the seed allows (a common plot is the sower's to reap). Returns how many were sown."""
    can = min(len(plots), seed_sacks * cfg["per_seed"])
    for p in plots[:can]:
        p["sown"] = day
        if p["owner"] is None and who:
            p["worker"] = who
    return can


def reap(state: dict, plots: list[dict], day: int, cfg: dict, who: str) -> int:
    """Harvest the ripe plots among these: sacks by the light of the last nights, a fraction left to chance. The plots rest. Returns the sacks."""
    sacks = 0
    for p in plots:
        if ripe(p, day, cfg):
            x = cfg["yield"] * harvest_factor(day, cfg)
            sacks += int(x) + (1 if random.Random(f"{day}/field/{p['id']}").random() < x - int(x) else 0)
            book(state)["harvests"] = (book(state)["harvests"] + [{"day": day, "who": who, "plot": p["id"], "sown": p["sown"], "sacks": round(x, 2),
                                                                   "moons_sown": town.moons(on_day(p["sown"])), "moons_reaped": town.moons(on_day(day))}])[-cfg["harvest_log"]:]
            p["sown"], p["rest_until"] = None, day + cfg["rest"]
            p.pop("worker", None)   # a common plot is free again once reaped
    return sacks


# ---------------------------------------------------------------- the night: inheritance, the villagers' own plots, the common pool
def _villager_coin(name: str, cp: int) -> bool:
    """Coin to a villager nobody plays (their rolled purse), or False when there is no such purse (the townsfolk, the dead)."""
    import json
    from . import registry
    db = registry.connect()
    try:
        row = db.execute("SELECT id, sheet FROM people WHERE name = ? AND status = 'alive' AND claimed_by IS NULL AND sheet IS NOT NULL", (name,)).fetchone()
        if row is None:
            return False
        sheet = json.loads(row["sheet"])
        sheet["copper"] = int(sheet["copper"]) + cp
        with db:
            db.execute("UPDATE people SET sheet = ? WHERE id = ?", (json.dumps(sheet), row["id"]))
        return True
    finally:
        db.close()


def transfer(state: dict, plot: dict, buyer: str | None, price_cp: int, day: int, pay_from: dict | None = None) -> None:
    """A plot changes hands. The buyer's coin (``pay_from``: a trader's purse, or None for the village's common pool paying from the households) goes to the
    seller: a villager's purse, else the households (the townsfolk have none of their own; a common plot's price is the households' already)."""
    seller = plot["owner"]
    if pay_from is not None:
        pay_from["coins"] = dcc.spend(pay_from["coins"], price_cp)
    else:
        state["money"]["households"] = int(state["money"].get("households", 0)) - price_cp
    if state.get("household_mode"):   # a villager's sale goes to their household
        from . import households, registry
        db = registry.connect()
        try:
            households.credit(state, db, households.of(db, seller) if seller else None, price_cp)
        finally:
            db.close()
    elif seller is None or not _villager_coin(seller, price_cp):
        state["money"]["households"] = int(state["money"].get("households", 0)) + price_cp
    plot["owner"] = buyer
    b = book(state)
    b["sales"] = (b["sales"] + [{"day": day, "plot": plot["id"], "from": seller or "the village", "to": buyer or "the village", "cp": price_cp}])[-40:]


def nightly(state: dict, day: int) -> dict:
    """Every night: plots of the dead go to the widow or widower, else to the common pool; the villagers of a farming trade till their own plot and bring the
    harvest to the shelves. Returns {"inherited", "to_common", "sown", "sacks"}."""
    cfg = config()
    out = {"inherited": 0, "to_common": 0, "sown": 0, "sacks": 0}
    if not cfg:
        return out
    from . import registry
    db = registry.connect()
    try:
        people = {r["name"]: r for r in db.execute("SELECT name, occupation, status, claimed_by, spouse_id, id FROM people")}
        by_id = {r["id"]: r for r in people.values()}
    finally:
        db.close()
    if not book(state)["plots"]:
        lay_out(state, day, [n for n, r in people.items() if r["status"] == "alive"])
    for p in book(state)["plots"]:
        r = people.get(p["owner"]) if p["owner"] else None
        if p["owner"] is not None and (r is None or r["status"] == "dead"):
            heir = by_id.get(r["spouse_id"]) if r is not None and r["spouse_id"] else None
            if heir is not None and heir["status"] == "alive":
                p["owner"] = heir["name"]
                out["inherited"] += 1
            else:
                p["owner"] = None
                out["to_common"] += 1
    farmers = {n for n, r in people.items() if r["status"] == "alive" and not r["claimed_by"] and r["occupation"].lower() in FARMING
               and n not in _tillers(state)}   # the farming traders till theirs in their own turn
    reapers = (farmers | _tillers(state)) & {n for n, r in people.items() if r["status"] == "alive"}   # a seat left empty keeps its dead holder's name: no reaper (plots 15-21 stood sown 6 years)
    for p in book(state)["plots"]:   # a crop nobody is left to reap (its worker dead, its owner dead without heir or an heir who does not farm) rots; the plot is free again
        if p["sown"] is not None and (p.get("worker") if p["owner"] is None else p["owner"]) not in reapers:
            p.pop("worker", None)
            p["sown"], p["rest_until"] = None, day
    stores = book(state).setdefault("stores", {})
    for name in sorted(farmers):
        mine = worked_by(state, name)
        sacks = reap(state, mine, day, cfg, name)
        store = int(stores.get(name, 0))
        keep = min(sacks, max(0, seed_for(min(len(mine), cfg["work"]), cfg) - store))   # seed for the next sowing first
        store += keep
        for _ in range(sacks - keep):
            if town.deliver(state, BARLEY):   # a shelf short of barley takes it; the rest the household eats
                out["sacks"] += 1
        to_sow = _workable(state, mine, day, cfg)
        if to_sow:
            while store < seed_for(len(to_sow), cfg) and _buy_seed(state, name, day):
                store += 1
            sown = sow(state, to_sow, day, store, cfg, name)
            store -= seed_for(sown, cfg)
            out["sown"] += sown
        stores[name] = store
    return out


def _workable(state: dict, mine: list[dict], day: int, cfg: dict) -> list[dict]:
    """The ready plots one pair of hands can still take on, up to ``work`` under barley at once: their own first, then free common plots."""
    room = max(0, cfg["work"] - sum(1 for p in mine if p["sown"] is not None))
    own = [p for p in mine if ready(p, day)][:room]
    common = [p for p in book(state)["plots"] if p["owner"] is None and not p.get("worker") and ready(p, day)]
    return own + common[:room - len(own)]


def _buy_seed(state: dict, name: str, day: int, bot: dict | None = None) -> bool:
    """A villager (or, with ``bot``, a farming trader from the purse) buys one sack of barley off the cheapest shelf with their own coin, if they can afford
    it. The coin goes to the shop's till."""
    import json
    from . import registry
    shelves = [(max(0, town.price_cp(shop, line, day)), shop, line) for shop in state["shops"].values() if "caravan" not in shop.get("kinds", []) and not shop.get("away")
               for line in shop["stock"] if line["name"] == BARLEY and line["qty"] and not line.get("gone")]
    if not shelves:
        return False
    price, shop, line = min(shelves, key=lambda t: t[0])
    if bot is not None:
        if dcc.coins_total_cp(bot["coins"]) < price:
            return False
        bot["coins"] = dcc.spend(bot["coins"], price)
        line["qty"] = int(line["qty"]) - 1
        shop["till"] = int(shop.get("till", 0)) + price
        return True
    db = registry.connect()
    try:
        if state.get("household_mode"):   # the coin is the household's: the copper on a villager's sheet is no money (10-11: seed bought with it made coin from nothing)
            from . import households
            hid = households.of(db, name)
            households.reconcile(state, db)
            if hid is None or households.purses(state).get(str(hid), 0) < price:
                return False   # only what they can afford
            with db:
                households.debit(state, db, hid, price)
            line["qty"] = int(line["qty"]) - 1
            shop["till"] = int(shop.get("till", 0)) + price
            return True
        row = db.execute("SELECT id, sheet FROM people WHERE name = ? AND status = 'alive' AND claimed_by IS NULL AND sheet IS NOT NULL", (name,)).fetchone()
        if row is None:
            return False
        sheet = json.loads(row["sheet"])
        if int(sheet["copper"]) < price:
            return False   # only what they can afford
        sheet["copper"] = int(sheet["copper"]) - price
        with db:
            db.execute("UPDATE people SET sheet = ? WHERE id = ?", (json.dumps(sheet), row["id"]))
    finally:
        db.close()
    line["qty"] = int(line["qty"]) - 1
    shop["till"] = int(shop.get("till", 0)) + price
    return True


# ---------------------------------------------------------------- the trader bots who farm
def farm(state: dict, bot: dict, spec: dict, day: int) -> list[str]:
    """A farming trader's night on the land: reap what is ripe (the sacks go into the pack, seed for the next sowing kept back), then sow every ready plot the
    seed allows. The plain rule; a model may add buying and selling of plots through ``act``. Returns what happened, for the town's log."""
    cfg = config()
    if not cfg or not spec.get("tills"):
        return []
    done, who = [], person_of(state, spec)
    mine = worked_by(state, who)
    sacks = reap(state, mine, day, cfg, who)
    if sacks:
        keep = min(sacks, max(0, seed_for(cfg["work"], cfg) - int(bot.get("seed", 0))))
        bot["seed"] = int(bot.get("seed", 0)) + keep
        if sacks - keep > 0:
            brought = next((b for b in spec.get("brings", []) if b[0] == BARLEY), (BARLEY, "trade", "4 sp"))
            dcc.add_item(bot, BARLEY, brought[1], sacks - keep, brought[2])
        done.append(f"reaped {sacks} sacks of barley from {sum(1 for h in book(state)['harvests'] if h['day'] == day and h['who'] == who)} plots")
    mine = worked_by(state, who)
    to_sow = _workable(state, mine, day, cfg)
    if to_sow:
        seed = int(bot.get("seed", 0))
        if seed < seed_for(len(to_sow), cfg):   # short of seed: sacks from the pack
            from_pack = next((i for i in bot["inventory"] if i["name"] == BARLEY and int(i.get("qty", 1)) > 0), None)
            while from_pack is not None and seed < seed_for(len(to_sow), cfg) and int(from_pack.get("qty", 1)) > 0:
                from_pack["qty"] = int(from_pack.get("qty", 1)) - 1
                seed += 1
            bot["inventory"] = [i for i in bot["inventory"] if int(i.get("qty", 1)) > 0]
        while seed < seed_for(len(to_sow), cfg) and _buy_seed(state, who, day, bot):   # none left: a sack off the shelf (until 10-10 a seat out of seed never sowed again)
            seed += 1
        sown = sow(state, to_sow, day, seed, cfg, who)
        used = seed_for(sown, cfg)
        bot["seed"] = seed - used
        if sown:
            done.append(f"sowed {sown} plot{'s' if sown != 1 else ''} with {used} sack{'s' if used != 1 else ''} of seed")
    return done


def rule_actions(state: dict, bot: dict, spec: dict, day: int) -> list[dict]:
    """The plain rule's land dealings: buy the cheapest plot when the hands have room, no common plot is free, the ask is below a year of what the plot
    gives at today's price, and the purse allows; sell one to the village when broke."""
    cfg = config()
    if not cfg or not spec.get("tills"):
        return []
    who = person_of(state, spec)
    purse = dcc.coins_total_cp(bot["coins"])
    mine = owned_by(state, who)
    if purse < cfg["sell_below_cp"] and len(mine) > 1:
        return [{"do": "sell_field"}]
    busy = sum(1 for p in worked_by(state, who) if p["sown"] is not None)
    free_common = any(p["owner"] is None and not p.get("worker") and ready(p, day) for p in book(state)["plots"])
    if busy + sum(1 for p in mine if p["sown"] is None) >= cfg["work"] or free_common:
        return []
    rel = (state.get("market") or {}).get("rel", {}).get(BARLEY, 1.0)
    worth = int(365 / (cfg["grow"] + cfg["rest"]) * cfg["yield"] * 40 * rel)
    best = next(iter(for_sale(state, day, who, 1)), None)
    if best and best["ask_cp"] <= min(worth, purse - cfg["keep_cp"]):
        return [{"do": "buy_field", "plot": best["plot"]}]
    return []


def act(state: dict, bot: dict, spec: dict, actions: list[dict], day: int) -> list[str]:
    """Carry out a trader's land actions: ``buy_field`` (the named plot, else the cheapest, at its owner's price; the coin goes to the owner), ``sell_field``
    (one fallow plot to the village's common pool at four fifths of the usual price, as far as the households can pay) and ``ask_field`` (name your own price
    for one of your plots)."""
    cfg = config()
    if not cfg or not spec.get("tills"):
        return []
    done, who = [], person_of(state, spec)
    for a in actions:
        if not isinstance(a, dict):
            continue
        if a.get("do") == "buy_field" and len(owned_by(state, who)) < cfg["work"]:
            offers = for_sale(state, day, who, len(book(state)["plots"]))
            pick = next((o for o in offers if str(o["plot"]) == str(a.get("plot"))), None) or (offers[0] if offers else None)
            if pick and dcc.coins_total_cp(bot["coins"]) >= pick["ask_cp"]:
                plot = next(p for p in book(state)["plots"] if p["id"] == pick["plot"])
                transfer(state, plot, who, pick["ask_cp"], day, pay_from=bot)
                done.append(f"bought plot {plot['id']} from {pick['owner']} for {town.coins_text(pick['ask_cp'])}")
        elif a.get("do") == "sell_field":
            mine = [p for p in owned_by(state, who) if p["sown"] is None]
            paid = int(cfg["usual_plot_cp"] * cfg["sell_share"])
            if len(owned_by(state, who)) > 1 and mine and int(state["money"].get("households", 0)) >= paid:
                plot = mine[-1]
                state["money"]["households"] = int(state["money"].get("households", 0)) - paid
                bot["coins"] = _add(bot, paid)
                plot["owner"] = None
                (bot.get("asks") or {}).pop(str(plot["id"]), None)
                book(state)["sales"] = (book(state)["sales"] + [{"day": day, "plot": plot["id"], "from": who, "to": "the village", "cp": paid}])[-40:]
                done.append(f"sold plot {plot['id']} to the village for {town.coins_text(paid)}")
        elif a.get("do") == "ask_field":
            try:
                plot_id, price = int(a["plot"]), max(1, int(a["ask_cp"]))
            except (KeyError, TypeError, ValueError):
                continue
            if any(p["id"] == plot_id for p in owned_by(state, who)):
                bot.setdefault("asks", {})[str(plot_id)] = price
                done.append(f"would sell plot {plot_id} for {town.coins_text(price)}")
    return done


def _add(bot: dict, cp: int) -> dict:
    total = dcc.coins_total_cp(bot["coins"]) + cp
    return {"gp": total // 100, "sp": total % 100 // 10, "cp": total % 10}


def mine_for_prompt(state: dict, bot: dict, spec: dict, day: int) -> dict | None:
    """What a model-played farmer is told about the land: their plots with what is on them and their own price for each, the free common plots, and the
    cheapest plots for sale with their owners' prices."""
    cfg = config()
    if not cfg or not spec.get("tills"):
        return None
    who = person_of(state, spec)
    asks = bot.get("asks") or {}
    return {"your_plots": [{"plot": p["id"], "yours": p["owner"] == who, "on_it": (f"barley, ripe in {max(0, p['sown'] + cfg['grow'] - day)} nights" if p["sown"] is not None
                                                                                   else "fallow, ready to sow" if ready(p, day) else f"resting {p['rest_until'] - day} more nights"),
                            **({"your_price_cp": ask_cp(state, p)} if p["owner"] == who else {"common_plot_you_work": True})} for p in worked_by(state, who)],
            "your_hands_work_at_most": cfg["work"], "free_common_plots_ready": sum(1 for p in book(state)["plots"] if p["owner"] is None and not p.get("worker") and ready(p, day)),
            "seed_sacks_kept": int(bot.get("seed", 0)), "plots_for_sale_cheapest_first": for_sale(state, day, who, 5),
            "sacks_a_plot_gave_lately": [h["sacks"] for h in book(state)["harvests"] if h["who"] == who][-6:],
            "your_prices_set": asks}


# ---------------------------------------------------------------- the eel ponds
def pond_catch(mean: float, start: int, rng: random.Random) -> int:
    """One pond's catch (Dodo 10-12): ``start`` plus a decaying count, ``start`` likeliest, then one more, then two, each step less likely; the
    count's mean is ``mean``. An ordinary night starts at nothing, a fat night at ``FIELDS["fat"]``."""
    q = max(0.0, mean) / (1 + max(0.0, mean))
    k = 0
    while rng.random() < q:
        k += 1
    return start + k


def ponds_tonight(bot: dict, spec: dict, day: int) -> int:
    """The eel farmer's ponds. Each due pond gives a catch (``pond_catch``: ``per`` eels on average times the moon's run of her trade, from 0 up;
    on a fat night from ``fat`` up), and the night's whole
    catch is smoked at once, fresh, for one sack of coal however many eels it is (Dodo 10-12: smoke many at once). Without a sack of coal the catch
    spoils. Returns the smoked eels."""
    from . import daily
    cfg = config()
    rule = spec.get("ponds")
    if not cfg or not rule:
        return 0
    due = bot.setdefault("ponds", [day + (n * rule["days"]) // rule["count"] for n in range(rule["count"])])   # staggered, so the catch comes in all month
    caught = 0
    for n, when in enumerate(due):
        if day >= when:
            caught += pond_catch(rule["per"] * daily.rhythm(spec, day), cfg["fat"] if fat_night(day) else 0, random.Random(f"{day}/pond/{n}"))
            due[n] = day + rule["days"]
    caught += int(bot.pop("eels", 0))   # fresh eels the old store still held (before 10-12) go into tonight's smoking
    if caught <= 0:
        return 0
    coal = next((i for i in bot["inventory"] if i["name"].startswith("Coal") and int(i.get("qty", 1)) > 0), None)
    if coal is None:
        bot["eels_spoiled"] = int(bot.get("eels_spoiled", 0)) + caught
        return 0
    coal["qty"] = int(coal.get("qty", 1)) - 1
    bot["inventory"] = [i for i in bot["inventory"] if int(i.get("qty", 1)) > 0]
    dcc.add_item(bot, EEL, "trade", caught, "2 sp")
    return caught


# ---------------------------------------------------------------- what the herb woman and the admin see
def summary(state: dict, day: int) -> dict:
    cfg = config()
    if not cfg:
        return {}
    b = book(state)
    plots = b["plots"]
    tillers = _tillers(state)
    owners: dict[str, int] = {}
    for p in plots:
        key = p["owner"] if p["owner"] in tillers else "the village (common)" if p["owner"] is None else "other villagers"
        owners[key] = owners.get(key, 0) + 1
    recent = b["harvests"][-12:]
    return {"plots": len(plots), "sown": sum(1 for p in plots if p["sown"] is not None), "ready_to_sow": sum(1 for p in plots if ready(p, day)),
            "resting": sum(1 for p in plots if p["sown"] is None and not ready(p, day)), "owned_by": owners, "common_plots_worked": sum(1 for p in plots if p["owner"] is None and p.get("worker")),
            "cheapest_plots_for_sale": for_sale(state, day, None, 3),
            "sales_lately": b["sales"][-5:],
            "harvests_lately": [{"day": h["day"], "who": h["who"], "sacks": h["sacks"], "sown_day": h["sown"], "sky_when_sown": [m["text"] for m in h["moons_sown"]],
                                 "sky_when_reaped": [m["text"] for m in h["moons_reaped"]]} for h in recent]}
