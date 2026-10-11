"""Once per real day: the villagers bring their small goods, the keepers make new stock, and the traders of
``places.BOTS`` do their rounds.

A trader has a purse and a pack in the town file,
brings the small goods they produce themselves, sells to the shops at the same half price as
any character, and buys from the same shelves. The local model plays each
trader when a llama.cpp server answers; otherwise a plain rule does (sell
what pays, buy the best bargain). Either way every action goes through
``town.buy`` and ``town.sell``, so a trader can never do what a player could not.

The update belongs to ``places.UPDATE_HOUR`` (2 o'clock at night). A systemd user timer on the host runs
``docker exec sheet python -m ttrpgtools.dcc.westmarch.daily`` at that hour every night. Should that ever fail, the
first visit to the town after that hour starts the update in a background thread instead, and days that were
missed altogether are caught up with the plain rule.
"""

from __future__ import annotations

import copy
import json
import random
import re
import sys
import threading
import urllib.request
from datetime import timedelta
from pathlib import Path

from ttrpgtools import dcc
from ttrpgtools.dcc import explain as dcc_explain
from . import clauses, economy, fields, lives, materials, places, registry, steward, town

MAX_ACTIONS = 3
CATCH_UP_DAYS = 14
HOLD_DAYS = 14          # after this long an unscripted trader sells an unsold purchase for whatever it fetches
_running = threading.Lock()


def _record(state: dict, spec: dict) -> dict:
    """The trader's purse and pack, shaped like a character so the shop functions accept it."""
    bots = state.setdefault("bots", {})
    if spec["id"] not in bots:
        start = dcc.cost_in_cp(spec.get("start")) or 0
        bots[spec["id"]] = {"coins": {"gp": start // 100, "sp": start % 100 // 10, "cp": start % 10}, "inventory": []}
    bot = bots[spec["id"]]
    bot["name"] = spec["name"]
    if spec.get("seed") and not bot.get("seeded"):   # every trader starts with the note written for them; the model takes it from there
        bot["note"], bot["seeded"] = spec["seed"], True
        bot.pop("notes", None)
    return bot


def identity(spec: dict) -> str:
    """A trader's fixed identity note, in labelled fields, at most fifty words: who they are, what they make, need,
    keep and like, and one quirk. Built from the trader's data in places.BOTS; the older prose ``persona`` otherwise."""
    if not spec.get("trade"):
        return spec.get("persona", "")
    short = lambda name: name.split(",")[0].split("(")[0].strip().lower()
    listing = lambda names: ", ".join(dict.fromkeys(short(n) for n in names))
    parts = [f"NAME {spec['name']}.", f"RACE {spec.get('race', 'human')}" + (f" who {spec['who']}" if spec.get("who") else "") + ".", f"TRADE {spec['trade']}."]
    if spec.get("brings"):
        parts.append(f"MAKES {listing(b[0] for b in spec['brings'])}.")
    if spec.get("needs"):
        parts.append(f"NEEDS {listing(spec['needs'])}.")
    for label, key in (("KEEPS", "keeps"), ("LIKES", "fond"), ("QUIRK", "quirk"), ("RHYTHM", "rhythm"), ("WRITES", "tidbit")):
        if spec.get(key):
            parts.append(f"{label} {spec[key]}.")
    return " ".join(parts)


def rhythm(spec: dict, day: int) -> float:
    """How well the trader's trade runs today: it follows a moon, as eels run with the Red Lantern. ``moon`` in the
    trader's entry names the moon (``id``), the phase of the peak (``peak``: "full" or "new") and how far the trade swings
    from its usual rate (``swing``, 0 to 1). 1,0 for a trade with no moon; otherwise between 1 minus and 1 plus the swing,
    a smooth wave with the moon's own period."""
    r = spec.get("moon")
    if not r:
        return 1.0
    lit = town.moon_light(r["id"], day)
    phase = lit if r.get("peak", "full") == "full" else 1 - lit
    return 1 - r["swing"] + 2 * r["swing"] * phase


def _bring(bot: dict, spec: dict, name: str, kind: str, cost: str, count: int, day: int) -> None:
    """Put goods into the pack. A hen has a moon: that of the day she is brought, by her keeper's Luck."""
    if clauses.is_hen(name):
        for _ in range(count):
            mark = town.roll_mark(day, spec["name"], town.maker_luck(spec["name"]), f"hen/{spec['id']}/{day}")
            bot["inventory"].append({"name": name, "kind": kind, "qty": 1, "cost": cost,
                                     "equipped": False, "notes": town.mark_text(mark, kind) if mark else "", **({"mark": mark} if mark else {})})
    else:
        dcc.add_item(bot, name, kind, count, cost)


def arrive(bot: dict, spec: dict, day: int, view: dict | None = None) -> None:
    """Morning: the trader brings what they produced themselves, small goods only: anything made of a material has
    to come out of a workshop. No coin arrives, and nothing leaves the pack by itself. Same result for the same day.
    Under places.MARKET the producer reads the market (``view``): a dear good is made more, a recipe only while it pays, a trade
    with a ``lag`` delivers that many days after the decision, and eggs come from the hens that were fed."""
    rng = random.Random(f"{day}/{spec['id']}/arrive")
    moon_run = rhythm(spec, day)   # the moon's part: the trade runs at this multiple of its usual rate
    cfg = economy.config()
    rel = (view or {}).get("rel", {})
    sky = float((view or {}).get("weather", 1.0)) if spec.get("farm") else 1.0   # a farm trade's yield follows the weather
    if cfg:
        for done in economy.arrived(bot, day):
            count = int(done["count"])
            if sky != 1.0 and not clauses.is_hen(done["name"]):   # the weather moves a harvest, not a hatching; and a fraction of a sack is left to chance
                x = count * sky
                count = int(x) + (1 if random.Random(f"{day}/{spec['id']}/{done['name']}/sky").random() < x - int(x) else 0)
            _bring(bot, spec, done["name"], done["kind"], done["cost"], count, day)
        for name, count in (bot.pop("release", None) or {}).items():
            brought = next((b for b in spec.get("brings", []) if b[0] == name), None)
            if brought and count > 0:
                dcc.add_item(bot, name, brought[1], count, brought[2])
        dozens = economy.eggs_laid(bot, spec, cfg, moon_run * sky)
        if dozens:
            egg = next(b for b in spec["brings"] if b[0] == spec["lays"])
            dcc.add_item(bot, egg[0], egg[1], dozens, egg[2])
    fields.ponds_tonight(bot, spec, day)
    for name, kind, cost, *most in spec.get("brings", []):
        if name == fields.BARLEY and spec.get("tills") and fields.config():
            continue   # barley is reaped from the plots (fields.farm), not brought
        run = moon_run
        if cfg:
            if name == spec.get("lays") or not economy.worth_making(cfg, spec, name, rel):
                continue   # eggs are laid, not made; a recipe that no longer pays is left alone
            run *= economy.eagerness(cfg, spec, name, rel)
            lag_days = int((spec.get("lag") or {}).get(name, 0))
            if lag_days:   # a farmer counts what is already in the ground before sowing more
                run *= max(0.0, 1 - economy.queued(bot, name) / ((lag_days + 2) * int(most[0] if most else 2)))
        if rng.random() >= min(0.95, 0.5 * run) or (materials.made_of(name, kind) and not materials.is_raw(name)):
            continue   # nothing today; and nothing ever that would have to come out of a workshop (scrap metal is dug up, not made)
        held = sum(int(i.get("qty", 1)) for i in bot["inventory"] if i["name"] == name)
        if held >= 3 * int(most[0] if most else 2) + int((spec.get("hold") or {}).get(name, 0)):
            continue   # the cellar is full of it (above what the trade keeps back): no use making more before some is sold
        lag = int((spec.get("lag") or {}).get(name, 0)) if cfg else 0
        if lag and economy.queued(bot, name) >= (lag + 2) * int(most[0] if most else 2):
            continue   # the fields, the yard or the kettle are as full as they get
        if clauses.is_hen(name):
            if lag:
                economy.queue(bot, name, kind, cost, 1, day + lag)
            else:
                _bring(bot, spec, name, kind, cost, 1, day)
            continue
        count = rng.randint(1, max(1, round((int(most[0]) if most else 2) * run)))
        options = economy.recipes(spec, name)
        if options:   # a brewer needs barley, a smoker coal, a cook barley or eggs or hens: what is made is limited by the raw stuff in the pack, the cheapest way first
            batch = bot.setdefault("batch", {})
            while batch.get(name, 0) < count:
                stocked = [(src, per) for src, per in options if any(i["name"] == src and int(i.get("qty", 1)) > 0 for i in bot["inventory"])]
                if not stocked:
                    break
                source, per = min(stocked, key=lambda o: rel.get(o[0], 1.0) * economy.base_cp(o[0]) / o[1])
                sack = next(i for i in bot["inventory"] if i["name"] == source and int(i.get("qty", 1)) > 0)
                sack["qty"] = int(sack.get("qty", 1)) - 1
                batch[name] = batch.get(name, 0) + int(per)
            bot["inventory"] = [i for i in bot["inventory"] if int(i.get("qty", 1)) > 0]
            count = min(count, batch.get(name, 0))
            batch[name] = batch.get(name, 0) - count
            if count <= 0:
                continue
        if name == fields.EEL:
            count = fields.take_eels(bot, spec, count)
            if count <= 0:
                continue
        if lag:
            economy.queue(bot, name, kind, cost, count, day + lag)
        else:
            dcc.add_item(bot, name, kind, max(1, round(count * sky)), cost)
    if cfg:
        economy.own_use(bot, spec, cfg, view or {}, day)
    for item in bot["inventory"]:
        item["equipped"] = False


def pay_tax(state: dict, bot: dict, spec: dict) -> int:
    """A trader who owes the tax office sets a little aside for it: a share of the coin above a reserve, never more than the
    debt. The coin goes to the Finanzamt like any tax. Returns the coppers paid."""
    from . import debts
    spare = dcc.coins_total_cp(bot["coins"]) - (dcc.cost_in_cp(places.TAX_PAY_RESERVE) or 0)
    if spare <= 0:
        return 0
    paid = debts.villager_pays(spec["name"], max(1, int(spare * places.TAX_PAY_SHARE)))
    if paid:
        bot["coins"] = dcc.spend(bot["coins"], paid)
        bot["taxed_cp"] = int(bot.get("taxed_cp", 0)) + paid
        state["money"]["finanzamt"] += paid
    return paid


def is_rich(purse_cp: int) -> bool:
    """Does a purse make its holder rich by the village's standards (places.RICH_PURSE)?"""
    return int(purse_cp) >= (dcc.cost_in_cp(places.RICH_PURSE) or 10 ** 12)


def wealth_note(state: dict, bot: dict) -> str | None:
    """A rich trader is told what the money means, in words and with numbers a small model can use: how much is in the
    purse, what the other traders hold, and what everything on every shelf in the village would cost together. None
    for anyone who is not rich."""
    purse = dcc.coins_total_cp(bot["coins"])
    if not is_rich(purse):
        return None
    day = town.campaign_day()
    shelves = sum(town.price_cp(shop, line, day) * int(line["qty"] or 0) for shop in state["shops"].values() if "shop" in shop.get("kinds", [])
                  for line in shop["stock"] if line["kind"] != "service" and line["qty"] is not None and not line.get("gone"))
    others = max([dcc.coins_total_cp(b["coins"]) for b in state.get("bots", {}).values() if b is not bot] or [0])
    return (f"YOU ARE RICH. Your purse holds {town.coins_text(purse)}. The richest other trader holds {town.coins_text(others)}. Everything on every shelf in the village "
            f"together costs about {town.coins_text(shelves)}, so you could buy all of it {max(1, purse // max(shelves, 1))} times over. "
            "You can afford whatever you like, and nothing stops you buying what your trade does not need: weapons, armor, tools, luxuries, a whole shelf of anything, up to ten pieces of a thing. "
            "Money that is never spent is worth nothing. Decide what you would really do with such a fortune, as the person described in who_you_are, and buy it today: "
            "several different things, and at least one that your trade has no need of. "
            "Your_note was written when you were poor, and its GOAL and RULE no longer fit: in the note you write today, change them for a rich person.")


def windfall_seed(spec: dict, bot: dict) -> str:
    """The trader's own note once they come into money, in the same shape as every seed: a GOAL, something to TRACK and a
    RULE that depends on it, so that the note that used to say "feed hens only" no longer holds a rich person back."""
    keeps = spec.get("keeps") or "my tools"
    text = (f"WINDFALL I came into {town.coins_text(dcc.coins_total_cp(bot['coins']))}. GOAL spend it on things I never could: better tools, a better house, pleasure. "
            f"TRACK what I bought and the price: (none yet). RULE each day buy several different things, one not for my trade. KEEP {keeps}.")
    return " ".join(text.split()[:NOTE_WORDS])


def market(state: dict, spec: dict, purse_cp: int) -> list[dict]:
    """What the trader could buy today, best bargains first. A rich trader is shown everything, not only their trade's needs."""
    rich = is_rich(purse_cp)
    rows = []
    held: dict[str, int] = {}
    for thing in (state.get("bots", {}).get(spec["id"]) or {}).get("inventory", []):
        held[thing["name"]] = held.get(thing["name"], 0) + int(thing.get("qty", 1))
    for shop in town.view(state, "", full=True)["shops"]:
        if "library" in shop["kinds"]:
            continue  # the library lends to characters; traders have no business there
        for item in shop["stock"]:
            if not rich and spec.get("needs") is not None and (item["name"] not in spec["needs"] or held.get(item["name"], 0) >= 3):
                continue   # a producer buys what the trade needs, and no more than three of it; a rich one buys what they like
            if (rich or item["kind"] in spec.get("likes", [])) and item["kind"] != "service" and item["qty"] != 0 and item["price_cp"] <= purse_cp:
                rows.append({"shop": shop["id"], "item": item["id"], "name": item["name"], "price_cp": item["price_cp"],
                             "against_usual": item["against_usual"], "left": item["qty"]})
    return sorted(rows, key=lambda r: r["against_usual"])


def shelves_shown(rows: list[dict], purse_cp: int) -> list[dict]:
    """The shelf rows a model is shown: twelve of the best bargains; for a rich trader the ten dearest things as well,
    since for them price is no obstacle and bargains are the least of it."""
    if not is_rich(purse_cp):
        return rows[:12]
    dear = sorted(rows, key=lambda r: -r["price_cp"])[:10]
    return dear + [r for r in rows if r not in dear][:8]


def best_offers(state: dict, bot: dict) -> list[dict]:
    """For each line of the pack, the shop that pays most today."""
    out = []
    for shop_id, rows in town.offers(state, bot).items():
        till = int(state["shops"][shop_id].get("till", 0))
        for row in rows:
            takes = min(row["qty"], till // row["each_cp"], row["qty"] if row.get("room") is None else row["room"])
            if takes > 0:   # a shop that cannot pay, or has enough, is no offer at all
                out.append({**row, "shop": shop_id, "takes": takes})
    best: dict[int, dict] = {}
    for row in out:
        if row["index"] not in best or row["each_cp"] > best[row["index"]]["each_cp"]:
            best[row["index"]] = row
    return [best[i] for i in sorted(best)]


# ------------------------------------------------------------------ scripted traders
def candidates(state: dict, bot: dict, spec: dict) -> dict:
    """The only moves a scripted trader may make today, each already inside its limits: pack lines a shop pays enough
    for, and shelf lines cheap enough, one piece per line. Best first."""
    limits = spec["limits"]
    sells = []
    for row in best_offers(state, bot):
        paid = bot["inventory"][row["index"]].get("paid_cp")
        if paid is not None and row["each_cp"] >= paid * limits.get("min_profit", 1.0) and row["each_cp"] > paid:
            sells.append({"index": row["index"], "shop": row["shop"], "name": row["name"], "pays_cp": row["each_cp"],
                          "paid_cp": paid, "profit_cp": row["each_cp"] - paid})
    sells.sort(key=lambda r: -r["profit_cp"])
    held = sum(int(i.get("qty", 1)) for i in bot["inventory"])
    buys = []
    if held < limits.get("pack_limit", 99):
        units = {(shop_id, item["id"]): int(item.get("units", 1)) for shop_id, shop in state["shops"].items() for item in shop["stock"]}
        for row in market(state, spec, dcc.coins_total_cp(bot["coins"])):
            discount = -row["against_usual"]
            if discount >= 1 - limits.get("buy_below", 1.0) and units.get((row["shop"], row["item"]), 1) == 1:
                buys.append({"shop": row["shop"], "item": row["item"], "name": row["name"], "price_cp": row["price_cp"], "discount": round(discount, 2)})
        buys.sort(key=lambda r: (-r["discount"], -r["price_cp"]))
    return {"sell": [{"n": n, **r} for n, r in enumerate(sells)], "buy": [{"n": n, **r} for n, r in enumerate(buys[:12])],
            "room": limits.get("pack_limit", 99) - held}


def scripted_plan(options: dict, spec: dict, pick: dict | None = None) -> list[dict]:
    """Turn a choice of line numbers into actions, cut to the daily limits and the room in the pack. Without a choice
    (no model, or a useless answer) the first lines are taken: the lists are sorted best first."""
    limits = spec["limits"]
    def chosen(key, cap):
        numbers = (pick or {}).get(key)
        if not isinstance(numbers, list):
            numbers = range(len(options[key]))
        rows = [options[key][n] for n in dict.fromkeys(numbers) if isinstance(n, int) and 0 <= n < len(options[key])]
        return rows[:cap]
    sells = chosen("sell", limits.get("sells_per_day", 2))
    buys = chosen("buy", min(limits.get("buys_per_day", 2), max(0, options["room"] + len(sells))))
    return ([{"do": "sell", "shop": r["shop"], "index": r["index"], "count": 1} for r in sells]
            + [{"do": "buy", "shop": r["shop"], "item": r["item"], "count": 1} for r in buys])


MODEL_TIMEOUT = 150   # seconds for one answer: the small model on the CPU is slow, and at two in the night nobody is waiting


def ask_model(messages: list[dict], max_tokens: int = 300, temperature: float = 0.7) -> dict | None:
    """One JSON answer from the first local model that gives one; None otherwise."""
    body = json.dumps({"model": dcc_explain.MODEL, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}).encode()
    for host in dcc_explain.HOSTS:
        try:
            req = urllib.request.Request(f"http://{host}/v1/chat/completions", data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=MODEL_TIMEOUT) as resp:
                text = json.load(resp)["choices"][0]["message"]["content"]
            return json.loads(text[text.index("{"):text.rindex("}") + 1])
        except (OSError, ValueError, KeyError, IndexError, TypeError):
            continue
    return None


def scripted_model_plan(state: dict, bot: dict, spec: dict) -> tuple[list[dict], str] | None:
    """The script file is the model's instruction; today's permitted lines are its input."""
    options = candidates(state, bot, spec)
    if not options["sell"] and not options["buy"]:
        return [], ""
    script = (Path(__file__).parent / "bots" / spec["script"]).read_text(encoding="utf-8")
    slim = lambda rows, keys: [{k: r[k] for k in keys} for r in rows]
    today = {"purse_cp": dcc.coins_total_cp(bot["coins"]), "room_in_pack": options["room"],
             "who_you_are": identity(spec), "your_note": note_of(bot), "village_needs_board": board_text(state), "town_note": town.note_text(state),
             "day": town.campaign_day(), "sky_tonight": [m["text"] for m in town.moons()],
             "limits": {"sell_at_most": spec["limits"].get("sells_per_day", 2), "buy_at_most": spec["limits"].get("buys_per_day", 2)},
             "SELL": slim(options["sell"], ("n", "name", "paid_cp", "pays_cp", "profit_cp")),
             "BUY": slim(options["buy"], ("n", "name", "price_cp", "discount"))}
    answer = ask_model([{"role": "system", "content": script}, {"role": "user", "content": json.dumps(today, ensure_ascii=False)}],
                       max_tokens=220, temperature=0.2)
    if answer is None:
        return None
    return scripted_plan(options, spec, answer), "", _note_of(answer), _board_of(answer)


NOTE_WORDS = 50                    # a trader's own note: one small note, rewritten whole, never longer than this
BOARD_LINES, BOARD_WORDS = 12, 60  # "village needs", the notepad all traders share: a small page, short lines


def _note_of(answer: dict) -> str:
    return " ".join(str(answer.get("note") or "").split()[:NOTE_WORDS])


def _board_of(answer: dict) -> dict:
    return {k: answer[k] for k in ("me_too", "need", "town_note", "flavour") if answer.get(k)}


def note_of(bot: dict) -> str:
    """A trader's note as it stands (an older list of notebook lines counts by its last line)."""
    return bot.get("note") or (bot.get("notes") or [{}])[-1].get("text", "")


def board_text(state: dict) -> list[str]:
    """The village's notepad as numbered lines: what somebody needs, and everyone who put their name under it."""
    return [f"{n}. {line['what']}: {', '.join(line['by'])}" for n, line in enumerate(state.get("needs_board", []), 1)]


def board_write(state: dict, name: str, day: int, entry: dict | None) -> str | None:
    """A trader writes on the village's notepad: a new line with the thing they need most, or their name under a line
    that is true for them too. ``entry`` is what a model answered: {"me_too": <line number>} or {"need": "<a few words>"};
    a need that says the same as an existing line counts as "me too". One page: when it is full, the line nobody has
    supported for longest makes room. Returns the line written on, or None."""
    board = state.setdefault("needs_board", [])
    entry = entry if isinstance(entry, dict) else {}
    line = None
    number = entry.get("me_too")
    if isinstance(number, int) and 1 <= number <= len(board):
        line = board[number - 1]
    need = " ".join(str(entry.get("need") or "").replace(":", " ").split())[:BOARD_WORDS].strip(" .").lower()
    if line is None and need:
        words = lambda text: {w.rstrip("s") for w in re.findall(r"[a-z]{4,}", text.lower())} - {"more", "need", "some", "want", "good", "cheap", "much", "many"}
        line = next((l for l in board if words(l["what"]) & words(need)), None)   # the same thing in other words is the same line
        if line is None:
            line = {"what": need, "by": [], "day": day, "last": day}
            board.append(line)
    if line is None:
        return None
    if name not in line["by"]:
        line["by"].append(name)
    line["last"] = day
    while len(board) > BOARD_LINES:
        board.remove(min(board, key=lambda l: (l["last"], len(l["by"]))))
    return line["what"]


def write_note(bot: dict, day: int, text: str) -> None:
    """A trader's one small note. The model reads it every time it plays the trader and may rewrite it whole; an
    answer without a note leaves it as it is."""
    text = " ".join(str(text or "").split()[:NOTE_WORDS])
    if text:
        bot["note"], bot["note_day"] = text, day
        bot.pop("notes", None)


# ------------------------------------------------------------------ what the village needs, and the caravan
def village_needs(state: dict) -> list[dict]:
    """What the village is short of, the worst first, each with its worth in copper so unlike things can be compared.
    Raw material: what the workshops lack to bring every listed line up to its quantity. Small goods: listed shelves
    below their quantity that no workshop can fill."""
    out = []
    prices = {m: dcc.cost_in_cp(p) or 0 for m, p in places.CARAVAN["material_price"].items()}
    lacking = {m: 0 for m in materials.MATERIALS}
    goods: dict[str, dict] = {}
    for shop in state["shops"].values():
        need = {m: 0 for m in materials.MATERIALS}
        for line in shop["stock"]:
            if not town._listed(line) or line["qty"] >= line["target"]:
                continue
            made = materials.made_of(line["name"], line["kind"])
            if made and not materials.is_raw(line["name"]):
                need[made[0]] += (line["target"] - line["qty"]) * made[1] * int(line.get("units", 1))
            else:
                entry = goods.setdefault(line["name"], {"what": line["name"], "kind": "goods", "pieces": 0, "value_cp": 0})
                entry["pieces"] += line["target"] - line["qty"]
                entry["value_cp"] += (line["target"] - line["qty"]) * int(line["base_cp"])
        for m, grams in need.items():
            lacking[m] += max(0, grams - int(shop.get("materials", {}).get(m, 0)))
    for m, grams in lacking.items():
        if grams > 0:
            out.append({"what": m, "kind": "material", "label": materials.MATERIALS[m]["name"], "kg": round(grams / 1000, 1),
                        "value_cp": round(grams / 1000 * prices.get(m, 0))})
    out += [{**g, "label": g["what"]} for g in goods.values()]
    # what the villagers wrote on their notepad: a line that names something a shop keeps is a need of its own,
    # worth more the more names stand under it, even while the shelf is full
    listed = {line["name"]: line for shop in state["shops"].values() for line in shop["stock"] if town._listed(line) and not materials.made_of(line["name"], line["kind"])}
    stem = lambda text: {w.rstrip("s") for w in re.findall(r"[a-z]{3,}", text.lower())}
    for wish in state.get("needs_board", []):
        name = next((n for n in listed if stem(n) & (stem(wish["what"]) | ({"hen"} if "chicken" in wish["what"] else set()))), None)
        if name and not any(o["what"] == name for o in out):
            line = listed[name]
            out.append({"what": name, "kind": "goods", "label": name, "pieces": int(line["target"]), "wished_by": len(wish["by"]),
                        "value_cp": int(line["target"]) * int(line["base_cp"]) * len(wish["by"]), "wish": True})
    return sorted(out, key=lambda need: -need["value_cp"])


def request_caravan(state: dict, day: int, pick: list | None = None) -> list[dict]:
    """The factor sends for the caravan: the most needed kinds, or the ones the model picked from the top of the list."""
    spec = places.CARAVAN
    needs = village_needs(state)
    top = needs[:5]
    chosen = [top[n] for n in dict.fromkeys(pick or []) if isinstance(n, int) and 0 <= n < len(top)][:spec["kinds"]] or needs[:spec["kinds"]]
    state["caravan"] = {"asked_day": day, "wants": chosen}
    who = next((b["name"] for b in places.BOTS if b["id"] == spec["by"]), "The factor")
    if chosen:
        town.tell(state, day, f"{who} has sent for the caravan: {' and '.join(need['label'].lower() for need in chosen)}. It is expected in {spec['ask_ahead']} days.")
    else:
        town.tell(state, day, f"{who} finds the village wants for nothing. No caravan was sent for.")
    return chosen


def caravan_arrives(state: dict, day: int, master: dict | None = None) -> dict:
    """The caravan brings what was sent for: raw material into the workshops that lack it, small goods onto the shelves
    that are short. It is dear. Every shop pays from its own till, and takes only what that till can pay. Then the
    wagons stay for a few days as a place that buys from anyone, low (``master``: the terms a model chose, if any)."""
    spec, wants = places.CARAVAN, (state.get("caravan") or {}).get("wants") or []
    prices = {m: dcc.cost_in_cp(p) or 0 for m, p in spec["material_price"].items()}
    brought, paid = [], 0
    for want in wants:
        if want["kind"] == "material":
            m, left, total = want["what"], round(spec["most_kg"] * 1000), 0
            for shop in state["shops"].values():
                short = sum((line["target"] - line["qty"]) * made[1] * int(line.get("units", 1)) for line in shop["stock"]
                            if town._listed(line) and line["qty"] < line["target"] and (made := materials.made_of(line["name"], line["kind"])) and made[0] == m
                            and not materials.is_raw(line["name"])) - int(shop.get("materials", {}).get(m, 0))
                grams = max(0, min(short, left))
                if prices.get(m):
                    grams = min(grams, int(shop.get("till", 0)) * 1000 // prices[m])   # only what the till can pay for
                if grams <= 0:
                    continue
                cost = -(-grams * prices.get(m, 0) // 1000)
                shop["till"] = int(shop.get("till", 0)) - cost
                shop.setdefault("materials", {})[m] = int(shop["materials"].get(m, 0)) + grams
                left -= grams; total += grams; paid += cost
            if total:
                brought.append(f"{materials.kg_text(total)} of {materials.MATERIALS[m]['name'].lower()}")
        else:
            pieces = 0
            hens_left = None
            if clauses.is_hen(want["what"]):
                shelved = [(int(l["qty"] or 0), int(l["target"] or 0)) for sh in state["shops"].values() for l in sh["stock"] if l["name"] == want["what"] and town._listed(l)]
                hens_left = spec.get("hens_max", 2) if 2 * sum(q for q, _ in shelved) < sum(t for _, t in shelved) else 0   # only a short flock, and a couple at most
            for shop in state["shops"].values():
                for line in shop["stock"]:
                    room = 2 * line["target"] - line["qty"] if want.get("wish") and town._listed(line) else (line.get("target") or 0) - (line["qty"] or 0)
                    if hens_left is not None:
                        room = min(room, hens_left)
                    if line["name"] == want["what"] and town._listed(line) and room > 0:   # a wish may fill a shelf up to twice its usual quantity
                        each = max(1, round(int(line["base_cp"]) * spec["goods_price"]))   # the caravan is dear
                        count = min(room, line["target"], int(shop.get("till", 0)) // each)
                        if count > 0:
                            shop["till"] = int(shop["till"]) - each * count
                            line["qty"] += count; pieces += count; paid += each * count
                            if hens_left is not None:
                                hens_left -= count
            if pieces:
                brought.append(f"{pieces} x {want['what']}")
    state["money"]["caravan"] = int(state["money"].get("caravan", 0)) + paid
    state["caravan"] = {"last_day": day, "brought": brought, "paid_cp": paid}
    # it stays and buys: a place of its own for a few days, paying out of the coin caravans have taken so far
    master = master or {}
    low, high = spec["share_range"]
    share = master.get("pays_share") if isinstance(master.get("pays_share"), (int, float)) else spec["pays_share"]
    refuses = [str(w).lower().strip() for w in master.get("refuses", spec["refuses"]) if str(w).strip()][:8] if isinstance(master.get("refuses", spec["refuses"]), list) else spec["refuses"]
    camp = state["shops"].setdefault("caravan", {"stock": []})
    camp.update(name="The Caravan", kinds=["caravan"], keeper="the caravan master", blurb="Wagons on the green. They sell dear and buy low, and they leave soon.",
                buys_anything=True, sell_back=min(high, max(low, float(share))), junk_cp=1, deals=[], refuses=refuses, away=False, arrived=day,
                curve={"period": 10, "amplitude": 0, "phase": 0}, till=int(state["money"]["caravan"]))
    state["money"]["caravan"] = 0   # the coin is in the wagons while they stand in town
    write_note(state.setdefault("caravan_master", {}), day, master.get("note") or (state.get("caravan_master") or {}).get("note") or spec["seed"])
    line = f"The caravan came{': ' + ', '.join(brought) + f', for {town.coins_text(paid)}' if brought else ' and sold nothing: nobody could pay'}."
    town.tell(state, day, line + f" It stays {spec['stays']} days and buys at {round(camp['sell_back'] * 100)} percent of the usual price"
                                 + (f", but no {', no '.join(refuses)}" if refuses else "") + ".")
    return state["caravan"]


def caravan_leaves(state: dict, day: int) -> None:
    """The wagons roll: what the caravan bought leaves the village with it, and so does the coin it still holds."""
    camp = state["shops"].get("caravan")
    if not camp or camp.get("away") or day < int(camp.get("arrived", day)) + places.CARAVAN["stays"]:
        return
    took = [f"{line['qty']} x {line['name']}" for line in camp["stock"] if int(line.get("qty") or 0) > 0]
    state["money"]["caravan"] = int(state["money"].get("caravan", 0)) + int(camp.get("till", 0))
    state.setdefault("caravan", {}).update(left_day=day, took=took)   # for the history: what the wagons took away
    camp.update(stock=[], till=0, away=True)
    town.tell(state, day, "The caravan left" + (f", taking {', '.join(took)}" if took else ", having bought nothing") + f". {town.coins_text(state['money']['caravan'])} of the village's coin is with it.")


def hens_eat(state: dict, day: int, characters: bool = True) -> list[str]:
    """Hens eat. Every holder of hens (a shop, a trader, a character) uses up a little barley per hen and day; a
    holder without barley loses each hen with a small chance. Returns what happened, for the town's log."""
    eats, dies = places.HENS["eats"], places.HENS["dies"]
    told = []

    def feed(holder: dict, lines: list, name: str, shelf: bool, key: str) -> bool:
        count = lambda line: int(line.get("qty") or 0) if shelf else int(line.get("qty", 1))
        hens = [l for l in lines if clauses.is_hen(l["name"]) and count(l) > 0 and not l.get("gone")]
        holder["hens_fed"] = 0   # tonight's laying hens: those that found barley
        if not hens:
            return False
        barley = next((l for l in lines if l["name"].lower().startswith("barley") and count(l) > 0 and not l.get("gone")), None)
        if barley:
            holder["hens_fed"] = sum(count(l) for l in hens)
            holder["hen_feed"] = float(holder.get("hen_feed", 0)) + eats * sum(count(l) for l in hens)
            while holder["hen_feed"] >= 1 and barley["qty"] > 0:
                barley["qty"] -= 1
                holder["hen_feed"] -= 1
                told.append(f"{name}'s hens ate a sack of barley.")
            return True
        dead = 0
        for at, line in enumerate(hens):   # each hen has her own luck: a keeper's hens are separate lines of one piece each
            for n in range(count(line)):
                if random.Random(f"{day}/{key}/{at}/{line['name']}/{n}/hen").random() < dies:
                    line["qty"] = count(line) - 1
                    if line.get("made"):
                        line["made"].pop()
                    dead += 1
        if dead:
            told.append(f"{dead} of {name}'s hens died for want of barley.")
        return True

    for shop_id, shop in state["shops"].items():
        feed(shop, shop["stock"], shop["name"], True, shop_id)
    for bot_id, bot in state.get("bots", {}).items():
        if feed(bot, bot["inventory"], bot.get("name", bot_id), False, bot_id):
            bot["inventory"][:] = [i for i in bot["inventory"] if int(i.get("qty", 1)) > 0]
    if characters:
        for row in dcc.list_characters():
            ch = dcc.load_character(row["id"])
            if ch.get("dead"):
                continue
            pack = dcc.ensure_inventory(ch)
            before = json.dumps([(i["name"], i.get("qty", 1)) for i in pack]) + str(ch.get("hen_feed"))
            if feed(ch, pack, ch["name"], False, row["id"]):
                ch["inventory"] = [i for i in pack if int(i.get("qty", 1)) > 0]
                if json.dumps([(i["name"], i.get("qty", 1)) for i in ch["inventory"]]) + str(ch.get("hen_feed")) != before:
                    dcc.sync_legacy_fields(ch)
                    dcc.save_character(ch, row["id"])
    for line in told:
        town.tell(state, day, line)
    return told


def model_caravan_master(state: dict) -> dict | None:
    """The caravan master, played by the local model as the wagons arrive: what share of the usual price to offer,
    what to refuse, and the note for the next visit. None when no model answers; the terms of places.CARAVAN hold then."""
    spec = places.CARAVAN
    low, high = spec["share_range"]
    task = {"who_you_are": spec["identity"], "your_note": note_of(state.get("caravan_master") or {}) or spec["seed"],
            "village_needs_board": board_text(state), "town_note": town.note_text(state),
            "you_were_sent_for": [w["label"] for w in (state.get("caravan") or {}).get("wants") or []],
            "coin_in_your_wagons_cp": int(state["money"].get("caravan", 0))}
    answer = ask_model([{"role": "system", "content": "You are the master of a trade caravan stopping in a poor village for two days. You sell dear. You also buy, "
                                                      "but only cheap, and only what will sell elsewhere. Reply with JSON only."},
                        {"role": "user", "content": json.dumps(task, ensure_ascii=False) + f"""

Decide your terms for this visit. Reply exactly in this shape:
{{"pays_share": <the share of a thing's usual price you offer the villagers, a number from {low} to {high}>,
 "refuses": ["<a word>", ...],
 "note": "<your own note, rewritten whole, at most 50 words: keep its labels, add what you learned here>"}}
"refuses" lists up to 6 single words; you buy nothing whose name contains one of them. Follow the RULE in your_note."""}],
                       max_tokens=220, temperature=0.4)
    return answer if isinstance(answer, dict) else None


def caravan_today(day: int) -> str | None:
    """'ask' on the day the factor sends for the caravan, 'arrive' on the day it comes, else None."""
    every, ahead = places.CARAVAN["every"], places.CARAVAN["ask_ahead"]
    return "arrive" if day % every == 0 else "ask" if day % every == every - ahead else None


def model_caravan(needs: list[dict], board: list[str] | None = None) -> list[int] | None:
    """Let the local model choose which of the top needs the caravan should bring, with the village's notepad before
    it; None when no model answers."""
    top = [{"n": n, "what": need["label"], "kind": need["kind"], "worth_cp": need["value_cp"],
            **({"kg": need["kg"]} if "kg" in need else {"pieces": need["pieces"]})} for n, need in enumerate(needs[:5])]
    if not top:
        return None
    answer = ask_model([{"role": "system", "content": "You are the factor of a small market town. Once a month you send for a trade caravan. "
                                                      "It can bring only a few kinds of goods. Choose what keeps the town's workshops and shelves "
                                                      "running: raw material that workshops lack matters most, because without it nothing is made. "
                                                      "Reply with JSON only."},
                        {"role": "user", "content": json.dumps({"shortages": top, "what_the_villagers_wrote_they_need": board or [],
                                                                "kinds_the_caravan_can_bring": places.CARAVAN["kinds"]}) +
                                                    '\nReply exactly like this, with the "n" numbers of your choice: {"bring": [<n>, ...]}'}],
                       max_tokens=60, temperature=0.2)
    picks = (answer or {}).get("bring")
    return [n for n in picks if isinstance(n, int)] if isinstance(picks, list) else None


def rule_plan(state: dict, bot: dict, spec: dict, day: int) -> list[dict]:
    """Sell own wares where they pay best, sell earlier purchases at a profit (or, after HOLD_DAYS, at whatever
    they fetch), buy one clear bargain."""
    if spec.get("steward"):   # the herb woman acts on her standing orders, or not at all while the steward is off
        return steward.plan(state, bot, spec, day) if places.STEWARD is not None else []
    if spec.get("limits"):
        return scripted_plan(candidates(state, bot, spec), spec)
    rng = random.Random(f"{day}/{spec['id']}/plan")
    plan = []
    spare = {name: sum(int(i.get("qty", 1)) for i in bot["inventory"] if i["name"] == name) - int(keep)
             for name, keep in (spec.get("hold") or {}).items()}   # what a trade must keep (a hen keeper's laying hens) is not for sale
    for row in best_offers(state, bot):
        thing = bot["inventory"][row["index"]]
        paid = thing.get("paid_cp")
        takes = row["takes"] if row["name"] not in spare else min(row["takes"], max(0, spare[row["name"]]))
        if takes > 0 and (paid is None or row["each_cp"] > paid or day - thing.get("bought_day", day) >= HOLD_DAYS):
            plan.append({"do": "sell", "shop": row["shop"], "index": row["index"], "count": takes})
            if row["name"] in spare:
                spare[row["name"]] -= takes
    purse = dcc.coins_total_cp(bot["coins"])
    bargains = [r for r in market(state, spec, purse) if r["against_usual"] < -0.1]
    if bargains and rng.random() < 0.7:
        pick = bargains[0]
        plan.append({"do": "buy", "shop": pick["shop"], "item": pick["item"], "count": 1})
    cfg = economy.config()
    for good, want in ((spec.get("stock_up") or {}) if cfg else {}).items():   # a producer keeps its inputs in the cellar, at whatever they cost
        held = sum(int(i.get("qty", 1)) for i in bot["inventory"] if i["name"] == good)
        offers = [(item["price_cp"], shop["id"], item["id"]) for shop in town.view(state, "", full=True)["shops"] if "library" not in shop["kinds"]
                  for item in shop["stock"] if item["name"] == good and item["qty"] and item["price_cp"] <= purse]
        if held < want and offers:
            price, shop_id, item_id = min(offers)
            plan.append({"do": "buy", "shop": shop_id, "item": item_id, "count": max(1, min(want - held, 2, purse // max(1, price)))})
    for good, (want, below) in ((spec.get("stock_up_cheap") or {}) if cfg and cfg.get("cheap_reserve") else {}).items():   # and more of it while it is cheap, against a drought
        held = sum(int(i.get("qty", 1)) for i in bot["inventory"] if i["name"] == good)
        offers = [(item["price_cp"], shop["id"], item["id"]) for shop in town.view(state, "", full=True)["shops"] if "library" not in shop["kinds"]
                  for item in shop["stock"] if item["name"] == good and item["qty"] and item["price_cp"] <= purse]
        if held < want and offers and economy.view(state).get("rel", {}).get(good, 1.0) <= cfg.get("reserve_below", below):
            price, shop_id, item_id = min(offers)
            plan.append({"do": "buy", "shop": shop_id, "item": item_id, "count": max(1, min(want - held, 3, purse // max(1, price)))})
    if cfg and cfg.get("momentum") and not spec.get("brings"):   # a trader who makes nothing chases a price that is going up
        chase = [r for r in market(state, spec, purse) if economy.rising(state, r["name"], cfg) and r["name"] != "Hen"]
        if chase:
            pick = chase[0]
            plan.append({"do": "buy", "shop": pick["shop"], "item": pick["item"], "count": max(1, min(cfg["momentum"]["buy"], purse // max(1, pick["price_cp"]), pick["left"] or 1))})
    return plan


def model_plan(state: dict, bot: dict, spec: dict) -> tuple[list[dict], str] | None:
    """Ask the local model what the trader does today. None when no model answers or the answer is unusable."""
    if spec.get("steward"):
        return None
    if spec.get("script"):
        return scripted_model_plan(state, bot, spec)
    purse = dcc.coins_total_cp(bot["coins"])
    task = {"you": spec["name"], "character": identity(spec), "purse_cp": purse,
            "your_note": note_of(bot), "village_needs_board": board_text(state), "town_note": town.note_text(state),
            "day": town.campaign_day(), "sky_tonight": [m["text"] for m in town.moons()],
            "pack_you_can_sell": [{"index": r["index"], "name": r["name"], "have": r["qty"], "shop": r["shop"], "pays_cp_each": r["each_cp"], "shop_takes_at_most": r["takes"],
                                   "you_paid_cp": bot["inventory"][r["index"]].get("paid_cp")} for r in best_offers(state, bot)],
            "shelves_you_can_afford": shelves_shown(market(state, spec, purse), purse)}
    land = fields.mine_for_prompt(state, bot, spec, town.campaign_day())
    if land:
        task["your_land"] = land
        task["land_actions"] = ('besides sell and buy you may add {"do": "buy_field", "plot": <plot>} (at the owner\'s ask_cp, crop included), {"do": "ask_field", "plot": <your plot>, "ask_cp": <n>} '
                                '(the price you would sell it for right now) or {"do": "sell_field"} (one fallow plot to the village at four fifths of the usual price). Your plots and free common '
                                'plots, as many as your hands work, are sown and reaped for you; the harvest of a common plot you work is yours.')
    wealth = wealth_note(state, bot)
    if wealth:
        task["you_have_come_into_money"] = wealth
        if not bot.get("windfall_told"):
            task["your_note"] = windfall_seed(spec, bot)   # the new situation, written into the note the model will see and rewrite
    messages = [
        {"role": "system", "content": "You play one trader in a fantasy market town for one day. Stay in character and be thrifty. "
                                      "Reply with JSON only, no other text."},
        {"role": "user", "content": json.dumps(task, ensure_ascii=False) + f"""

Choose at most {MAX_ACTIONS} actions for today. against_usual is today's price against the usual price (-0.2 = 20% cheaper).
Selling something for less than you_paid_cp is a loss. Reply exactly in this shape:
{{"actions": [{{"do": "sell", "shop": "<shop>", "index": <index>, "count": <n>}}, {{"do": "buy", "shop": "<shop>", "item": "<item>", "count": <n>}}],
 "note": "<optional: your own small note, rewritten whole, at most 50 words: what you want to remember. It replaces your_note. Leave it out to keep your_note>"}}
"character" says who you are: what you MAKE, NEED and KEEP for yourself, what you LIKE, and your QUIRK. Act like that person; what you KEEP you do not sell.
your_note is your own note from earlier days. It has a GOAL, things you TRACK and a RULE: follow the RULE today, and when you rewrite the note, keep its labels and add today's numbers to what you TRACK.
village_needs_board is a notepad the whole village shares: each line is something people need, with the names of those who need it.
You may add ONE of these to your reply: "me_too": <number of a line that is true for you as well>, or
"need": "<the one thing you need most and cannot get, 2 to 5 words>". If a line fits you, prefer "me_too".
If the input has "you_have_come_into_money", you are rich: believe it, and spend, as the person you are.
town_note is a scrap of paper the whole town shares and reads, in two parts. REQUESTS are what the village asks for. Add a request line ONLY if it is NEW: something the note
does not say yet, not even in other words. Most days you have nothing new: then leave it out. Write something others can use (a price, a shortage, a warning), never a slogan
and never a line you read there. To add one, put "town_note": "<one short line, at most 20 words>" in your reply.
TALK is what villagers scribble for each other: gossip, a grumble, a joke, a bad rhyme, something you saw or overheard, in YOUR voice (see WRITES in "character").
On most days write one line of talk: "flavour": "<one line, at most 25 words>". Make it about something that happened to you or near you today, never a price, never a line
you read there, and not in the shape of the lines already there."""}]
    answer = ask_model(messages, max_tokens=260, temperature=0.7)
    if answer is None or not isinstance(answer.get("actions", []), list):
        return None
    return [a for a in answer.get("actions", []) if isinstance(a, dict)][:MAX_ACTIONS], "", _note_of(answer), _board_of(answer)


def talk(state: dict, day: int) -> str | None:
    """Town talk. Every week has one or two nights, fixed in advance, on which one short line about one sale of the
    last day appears: who sold what to whom. Nothing else is told, and most sales never are. A player who looks in
    once a week finds one or two new lines."""
    week = random.Random(f"{(day - 1) // 7}/talk-week")
    nights = week.sample(range(7), week.randint(*places.TALK_PER_WEEK))
    if (day - 1) % 7 not in nights:
        return None
    rng = random.Random(f"{day}/talk")
    sales = [s for s in state["log"] if s.get("day") in (day, day - 1) and int(s.get("count") or 0) < 0 and not str(s.get("item", "")).startswith("Augur")]
    if not sales:
        return None
    sale = rng.choice(sales)
    line = f"{sale['character']} sold {sale['item']} to {sale['shop']}."
    town.gossip(state, day, line)
    return line


def _shelf(state: dict, shop_id: str, wanted: str, purse_cp: int) -> tuple[str, str] | None:
    """Find what a model meant to buy. Models name a thing by its shelf id, by its name, or at the wrong shop: look
    in the named shop first, by id and then by name, then in every shop for the cheapest of that name the purse can pay."""
    key = wanted.strip().lower()
    match = lambda item: item["kind"] != "service" and not item.get("gone") and (item["id"] == wanted or item["name"].lower() == key)
    here = state["shops"].get(shop_id)
    if here and "shop" in here.get("kinds", []):
        for item in here["stock"]:
            if match(item) and item["qty"] != 0:
                return shop_id, item["id"]
    day, found = town.campaign_day(), []
    for other_id, shop in state["shops"].items():
        if "shop" not in shop.get("kinds", []) and not shop.get("stay"):
            continue
        for item in shop["stock"]:
            if match(item) and item["qty"] != 0 and town.price_cp(shop, item, day) <= purse_cp:
                found.append((town.price_cp(shop, item, day), other_id, item["id"]))
    return min(found)[1:] if found else None


def act(state: dict, bot: dict, spec: dict, actions: list[dict], day: int) -> list[str]:
    """Carry out a plan through the same doors a player uses. Returns what happened.

    A model decides WHAT to sell and buy; the town decides whether it can be done. So that a plan is not lost to a
    slip of the model's, an unscripted trader's action is put right where the intent is clear: a sale goes to the
    shop that pays best and can pay, for as many pieces as that shop takes; a purchase is looked up by id or by name,
    at the named shop or the cheapest one. What the town still refuses is skipped."""
    done = []
    limits = spec.get("limits") or {}
    def line_of(a: dict) -> int:
        try:
            return int(a.get("index", 0))
        except (TypeError, ValueError):
            return -1   # not a number: sorted last, and refused when its turn comes
    sells = sorted((a for a in actions if isinstance(a, dict) and a.get("do") == "sell"), key=lambda a: -line_of(a))  # high index first: indexes stay valid
    buys = [a for a in actions if isinstance(a, dict) and a.get("do") == "buy"]
    if limits:  # the hard limits hold whatever the plan says
        sells, buys = sells[:limits.get("sells_per_day", 2)], buys[:limits.get("buys_per_day", 2)]
    for a in sells + buys:
        try:
            count = 1 if limits else max(1, int(a.get("count", 1)))
            shop_id = str(a.get("shop", ""))
            if a["do"] == "sell":
                paid = bot["inventory"][int(a["index"])].get("paid_cp")
                if limits and (paid is None or town.offer(state, shop_id, bot["inventory"][int(a["index"])])["each_cp"] <= paid):
                    continue  # never at a loss
                if not limits:
                    row = next((r for r in best_offers(state, bot) if r["index"] == int(a["index"])), None)
                    if row is None:
                        continue  # no shop can take it today
                    here = next((r for r in town.offers(state, bot).get(shop_id, []) if r["index"] == int(a["index"])), None)
                    till = int(state["shops"][shop_id].get("till", 0)) if shop_id in state["shops"] else 0
                    takes = 0 if not here else min(here["qty"], till // here["each_cp"], here["qty"] if here.get("room") is None else here["room"])
                    if takes < 1:
                        shop_id, takes = row["shop"], row["takes"]   # the named shop cannot: the one that pays best and can
                    count = min(count, takes)
            elif limits and sum(int(i.get("qty", 1)) for i in bot["inventory"]) >= limits.get("pack_limit", 99):
                continue
            if a["do"] == "sell":
                sale = town.sell(state, shop_id, bot, int(a["index"]), count, who="bot")
                done.append(f"sold {count} x {sale['item']} to {sale['shop']} ({town.coins_text(sale['each_cp'] * count)})")
            else:
                item_id = str(a["item"])
                if not limits:
                    found = _shelf(state, shop_id, item_id, dcc.coins_total_cp(bot["coins"]))
                    if found is None:
                        continue
                    shop_id, item_id = found
                    rich = is_rich(dcc.coins_total_cp(bot["coins"]))
                    if spec.get("needs") is not None and not rich:   # a producer buys only what the trade needs, whatever the model fancies; a rich one is not held to it
                        name = next(i["name"] for i in state["shops"][shop_id]["stock"] if i["id"] == item_id)
                        if name not in spec["needs"]:
                            continue
                    count = min(count, 10 if rich else 3)
                    held = next((i["qty"] for i in state["shops"][shop_id]["stock"] if i["id"] == item_id), None)
                    if held is not None:
                        count = min(count, int(held))   # no more than the shelf holds: asking for more is a slip, not a wish to buy nothing
                    if count < 1:
                        continue
                sale = town.buy(state, shop_id, item_id, bot, count, who="bot")
                mine = next(i for i in reversed(bot["inventory"]) if i["name"] == sale["item"])
                mine.update(paid_cp=sale["each_cp"], bought_day=day, equipped=False)
                done.append(f"bought {count} x {sale['item']} at {sale['shop']} ({town.coins_text(sale['each_cp'] * count)})")
        except (dcc.DCCError, KeyError, ValueError, TypeError, StopIteration, IndexError):   # IndexError: a model named a pack line that is not there
            continue
    return done


def produce(state: dict, day: int) -> dict:
    """Night: every living villager nobody plays may bring one piece of each small good their trade yields
    (``places.PRODUCE``), and wood for the workshops. A shelf at its listed quantity takes nothing, and then nothing
    is produced. Same result for the same day. Returns {"pieces": n, "wood_g": grams}."""
    out = {"pieces": 0, "wood_g": 0}
    cfg, rel = economy.config(), economy.view(state).get("rel", {})
    for person in registry.producers():
        occupation = person["occupation"].lower()
        for n, entry in enumerate(places.PRODUCE):
            if not any(word in occupation for word in entry["by"]):
                continue
            chance = places.PRODUCE_CHANCE
            if cfg and "good" in entry:   # under the market the villagers make what is dear and let go of what is free
                chance = min(0.95, chance * economy.eagerness(cfg, {}, entry["good"], rel) * (economy.view(state).get("weather", 1.0) if entry["good"] == "Rations, per day" else 1.0))
            if random.Random(f"{day}/{person['name']}/produce/{n}").random() >= chance:
                continue
            if "wood_kg" in entry:
                out["wood_g"] += town.deliver_wood(state, entry["wood_kg"])
            elif town.deliver(state, entry["good"]):
                out["pieces"] += 1
    return out


def run_day(state: dict, day: int, plans: dict | None = None, live: bool = True) -> None:
    """One day's update on the given state: interest, the villagers' produce, making days, then each trader.
    ``plans`` maps trader id to a model plan. ``live`` is off for simulations, which must not touch anybody's real debt."""
    if live:
        from . import debts
        debts.accrue(day)
    caravan_leaves(state, day)
    lives.monthly(state, day)   # births, weddings and deaths once a month (nothing while places.LIVES is None)
    if economy.config():   # fixed prices and no households unless places.MARKET is set
        economy.step_weather(state, day)
        economy.reprice(state, day)
        economy.wages(state, economy.config())
        economy.families(state, economy.config())
        economy.delver(state, day, economy.config())
        economy.herbs(state, economy.config())
        economy.relief(state, economy.config())
        economy.refill(state, economy.config())
        economy.eat(state, day, economy.config())
    fields.nightly(state, day)
    produce(state, day)
    hens_eat(state, day, characters=live)
    for shop_id, shop in state["shops"].items():
        if town.next_delivery(shop_id, shop, day) == 0:
            work = town.restock(state, shop_id, day)
            if work["made"] or work["short"]:
                line = f"Making day at {shop['name']}: {work['made']} piece{'s' if work['made'] != 1 else ''} made"
                if work["broken"]:
                    line += f", {work['broken']} old piece{'s' if work['broken'] != 1 else ''} broken up for material"
                if work["short"]:
                    line += ". No material left for: " + ", ".join(work["short"][:5]) + (" and more" if len(work["short"]) > 5 else "")
                town.tell(state, day, line + ".")
    if places.BOTS and caravan_today(day) == "arrive":
        caravan_arrives(state, day, (plans or {}).get("caravan_master"))
    elif places.BOTS and caravan_today(day) == "ask":
        request_caravan(state, day, (plans or {}).get("caravan"))
    if economy.config():
        economy.crew_eats(state, day, economy.config())   # the crew's evening, while the wagons stand
    steward.maybe_checkin(state, day)
    for spec in places.BOTS:
        if places.LIVES:   # the trader is whoever holds the seat now; with the seat empty the trade stands still
            if lives.vacant_bot(state, spec):
                continue
            spec = dict(spec, name=lives.holder_name(state, spec))
        try:   # one trader's trouble must never stop the town's night: it is written in the log and the day goes on
            bot = _record(state, spec)
            arrive(bot, spec, day, economy.view(state))
            farmed = fields.farm(state, bot, spec, day)
            planned = (plans or {}).get(spec["id"])
            actions, remark, *note = planned or (rule_plan(state, bot, spec, day) + fields.rule_actions(state, bot, spec, day), "")
            farmed += fields.act(state, bot, spec, actions, day)
            write_note(bot, day, note[0] if note else "")
            if is_rich(dcc.coins_total_cp(bot["coins"])) and not bot.get("windfall_told"):
                bot["windfall_told"] = True   # once: the note of a trader who has just come into money starts from the windfall
                if "WINDFALL" not in note_of(bot).upper():
                    write_note(bot, day, windfall_seed(spec, bot))
            board_write(state, spec["name"], day, note[1] if len(note) > 1 else None)
            if len(note) > 1 and isinstance(note[1], dict) and note[1].get("town_note"):
                town.town_note_write(state, spec["name"], note[1]["town_note"])
            if len(note) > 1 and isinstance(note[1], dict) and note[1].get("flavour"):
                town.flavour_write(state, spec["name"], note[1]["flavour"])
            done = act(state, bot, spec, actions, day)
            if planned and not done:   # the model talked and nothing came of it: the plain rule does the day's trading instead
                done, remark = act(state, bot, spec, rule_plan(state, bot, spec, day), day), ""
            done = farmed + done
            if done:
                town.tell(state, day, f"{spec['name']} {' and '.join(done)}." + (f' "{remark}"' if remark else ""))
            if live:   # simulations must not touch anybody's real debt
                pay_tax(state, bot, spec)
        except Exception as exc:
            town.tell(state, day, f"{spec['name']} could not be played today: {type(exc).__name__}: {str(exc)[:80]}.")
    talk(state, day)
    state["last_daily"] = day
    if state.get("household_mode"):   # tonight's flows moved the one total: the purses follow it (households.py)
        from . import households, registry
        db = registry.connect()
        try:
            households.reconcile(state, db)
        finally:
            db.close()
    if live:
        from . import money
        money.record(state, day)  # tonight's line in the books: where the coin is, what the town owes, how dear things are
        from . import history
        history.record(state, day)   # and tonight's price and stock of every good, and what the caravan would be asked for


def due(state: dict) -> list[int]:
    """The campaign days whose nightly update has not run yet. Before the update hour, today's is not due."""
    today, last = town.campaign_day() - (1 if town.hour() < places.UPDATE_HOUR else 0), state.get("last_daily")
    return [today] if last is None else list(range(max(last + 1, today - CATCH_UP_DAYS + 1), today + 1))


def _work(use_model: bool = True) -> list[int]:
    """Bring the town up to today. The model is asked outside the file lock, on a copy, so nobody waits for it."""
    if not _running.acquire(blocking=False):
        return []
    try:
        with town.town() as state:
            days = due(state)
            draft = copy.deepcopy(state) if days else None
        if not days:
            return []
        plans = {}
        if use_model:
            for day in days[:-1]:
                run_day(draft, day, live=False)
            for shop_id, shop in draft["shops"].items():
                if town.next_delivery(shop_id, shop, days[-1]) == 0:
                    town.restock(draft, shop_id)
            for spec in places.BOTS:  # today's morning on a copy, so the model sees the market the real run starts from
                morning = copy.deepcopy(draft)
                arrive(_record(morning, spec), spec, days[-1])
                plan = model_plan(morning, _record(morning, spec), spec)
                if plan:
                    plans[spec["id"]] = plan
            if places.BOTS and caravan_today(days[-1]) == "arrive":
                terms = model_caravan_master(draft)
                if terms:
                    plans["caravan_master"] = terms
            if places.BOTS and caravan_today(days[-1]) == "ask":
                picks = model_caravan(village_needs(draft), board_text(draft))
                if picks:
                    plans["caravan"] = picks
        with town.town(write=True) as state:
            days = due(state)  # another worker may have finished meanwhile
            for day in days:
                run_day(state, day, plans if day == days[-1] else None)
        return days
    finally:
        _running.release()


AUTO = True  # page visits start the update by themselves; tests switch this off


def ensure_on_visit() -> None:
    if AUTO:
        ensure()


def ensure(background: bool = True, use_model: bool = True) -> bool:
    """Start the daily update when one is due. Returns whether one was due."""
    with town.town() as state:
        if not due(state):
            return False
    if background:
        threading.Thread(target=_work, args=(use_model,), daemon=True).start()
    else:
        _work(use_model)
    return True


def simulate(days: int, only: str | None = None, use_model: bool = False) -> list[dict]:
    """Play ``days`` future days on a copy of the town and report each trader's purse: the way to try a script before
    it meets the real shelves. Nothing is saved. Swaps the clock, so it is for the command line, never the server."""
    with town.town() as state:
        draft = copy.deepcopy(state)
    real_today, all_bots, start = town.today, places.BOTS, town.campaign_day()
    places.BOTS = [b for b in all_bots if only in (None, b["id"])]
    if only:
        draft["bots"] = {}
    report = []
    try:
        for step in range(1, days + 1):
            town.today = lambda step=step: real_today() + timedelta(days=step)
            plans = {}
            if use_model:
                for spec in places.BOTS:
                    morning = copy.deepcopy(draft)
                    arrive(_record(morning, spec), spec, start + step)
                    plan = model_plan(morning, _record(morning, spec), spec)
                    if plan:
                        plans[spec["id"]] = plan
            run_day(draft, start + step, plans, live=False)
            report.append({"day": start + step, **{b["id"]: dcc.coins_total_cp(draft["bots"][b["id"]]["coins"]) for b in places.BOTS}})
    finally:
        town.today, places.BOTS = real_today, all_bots
    report.append({"packs": {b["id"]: [(i["name"], i.get("paid_cp")) for i in draft["bots"][b["id"]]["inventory"]] for b in all_bots if b["id"] in draft["bots"]},
                   "news": [n["text"] for n in draft.get("chronicle", []) if only is None or any(b["name"] in n["text"] for b in all_bots if b["id"] == only)][-6:]})
    return report


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "simulate":  # python -m ttrpgtools.dcc.westmarch.daily simulate 90 [bot id] [model]
        result = simulate(int(sys.argv[2]), sys.argv[3] if len(sys.argv) > 3 else None, "model" in sys.argv[4:])
        for row in result[:-1]:
            if row["day"] % 10 == 0 or row is result[-2]:
                print(row)
        print(result[-1])
    else:
        print("days updated:", _work())
