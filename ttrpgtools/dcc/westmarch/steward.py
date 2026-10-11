"""The steward: Hedwig Dornbusch, the herb woman, an elf who has watched the village for centuries and steers it only by what she herself does.

She does not trade for profit and does not hoard. She sees the whole village (``report``: prices over months and years, stocks, every producer's
purse, the flock, the coin, her own past deeds) and steps in only to prevent a **disaster**: the chickens dying out, a producer broke for weeks,
a staple gone for weeks, a price stuck at an extreme until the producers give up. Her tools are her own: a small reserve she buys while a good is
nearly free and releases while it is dear, hens she gives to the hen keeper when his flock is nearly gone, a little coin she gives to a producer
who has none. She cannot set anyone's price or take anyone's coin.

She acts every night on **standing orders** she wrote ahead (each with ``for_days``: the crisis must have lasted that long, so ordinary swings are
left alone) and **checks in** now and then (monthly in play, every half year when the years are run fast): a brain reads the report, may rewrite her
orders and her notebook (her only memory), may leave a line on the town note. The brain is a plain rule (``rules``: orders stay as they are) or a
headless Claude instance (``claude``, run on the host: ``scripts/steward_checkin.py``). Her purse above her working capital goes back to the
households every night (``economy.families``), her cellar holds at most ``LIMITS["cellar"]`` things.

Off unless ``places.STEWARD`` is set (None: the herb woman is just the herb woman). State: ``state["steward"]``.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from ttrpgtools import dcc
from . import economy, fields, lives, places, town

ID = "hedwig-d"
GOODS = ["Barley, a sack", "Ale, a jug", "Eggs, a dozen", "Smoked eel", "Stinky cheese", "Coal, a sack", "Rations, per day", "Scrap metal", "Tanned hide"]
PRODUCERS = {"detlef": "hens and eggs", "xaver": "ale", "jutta": "smoked eel", "reinhild": "barley", "hartmut": "scrap", "ivo": "hides"}
BASELINE = ([{"sell": g, "above": 10.0, "for_days": 21, "keep": 0, "per_night": 3} for g in GOODS]
            + [{"buy": g, "below": 0.05, "for_days": 28, "up_to": 10, "per_night": 2, "keep_gp": 100} for g in GOODS]
            + [{"buy": "Hen", "below": 1.0, "for_days": 0, "up_to": 6, "per_night": 1, "keep_gp": 50}, {"give_hens": 6, "when_flock_below": 3}]
            + [{"aid": pid, "gp": 5, "when_purse_below_gp": 3, "for_days": 14, "every_days": 30} for pid in PRODUCERS])
LIMITS = {"cellar": 40, "orders": 40, "per_night": 10, "up_to": 60, "notebook": 2000, "note": 140, "history": 156, "done": 40}
NOTE_EVERY = 90   # she writes to the village notebook (the town note) at most this often
# Her attention is a token budget (the owner 10-10: about the tokens per in-game week of the runs before): one point is the tokens of one average call (the host
# measures each call and charges it in points), and points come back at 3.14 a year, the calls a year of the three runs of 10-09 and 10-10 (181 calls,
# lookups included, in 57.7 years). Up to ATTENTION_CAP can be saved for a crisis; with less than one point nothing wakes her, not even her own date.
ATTENTION_CAP, ATTENTION_PER_YEAR = 12.0, 3.14
ATTENTION_DAYS = 365 / ATTENTION_PER_YEAR
DEFAULT_GAP, MAX_GAP, MAX_WAKE_CONDITIONS = 90, 730, 5   # when she does not say when to look again, and the longest she may wait
NOTE_LIMITS = {"text": 400, "chars": 2400, "entries": 30, "pins": 8}   # her notebook: entries with ids she can add, edit and delete; the oldest unpinned ones go when it is full
MAX_FLAGS = 12
# The alarms ("flags") she keeps: each says what counts as a disaster for as long as it holds. She rewrites the list herself; these are where she starts.
DEFAULT_FLAGS = [{"when": "price_above", "of": "each good", "x": 10.0, "for_days": 21},
                 {"when": "price_below", "of": "each good", "x": 0.05, "for_days": 28},
                 {"when": "stock_below", "of": "each good", "n": 1, "for_days": 21},
                 {"when": "purse_below_gp", "of": "each producer", "gp": 3, "for_days": 14},
                 {"when": "flock_below", "n": 3, "for_days": 1},
                 {"when": "village_coin_below_gp", "gp": 40, "for_days": 30}]
FLAG_KINDS = {"price_above": "x", "price_below": "x", "stock_below": "n", "stock_above": "n", "purse_below_gp": "gp", "flock_below": "n", "village_coin_below_gp": "gp"}


def known_items(state: dict) -> set:
    """Every kind of thing on a shelf in the village: what her buy and sell orders may name besides the staples."""
    return {line["name"] for shop in state["shops"].values() for line in shop["stock"] if line["kind"] != "service" and "caravan" not in shop.get("kinds", [])}


def book(state: dict) -> dict:
    b = state.setdefault("steward", {"orders": [dict(o) for o in BASELINE], "notebook": "", "checked": 0, "log": [], "history": [], "streak": {}, "done": [], "aided": {}})
    if "flags" not in b:   # a book from before she kept her own alarms
        b["flags"] = [dict(f) for f in DEFAULT_FLAGS]
        b["streak"] = {k: v for k, v in b["streak"].items() if k.partition(":")[0] not in ("dear", "free", "gone", "broke", "dry", "flock")}
    if "notes" not in b:   # a book from before the notebook had entries: the old text becomes one note
        b["notes"], b["next_note"] = ([{"id": 1, "day": int(b.get("checked", 0)), "text": b["notebook"][:NOTE_LIMITS["text"] * 4], "pin": False, "until": None}] if b.get("notebook") else []), 2
    return b


def held(bot: dict, good: str) -> int:
    return sum(int(i.get("qty", 1)) for i in bot["inventory"] if i["name"] == good)


def flock(state: dict) -> int:
    return held(state["bots"].get("detlef", {"inventory": []}), "Hen")


def _purse_gp(bot: dict) -> int:
    return dcc.coins_total_cp(bot["coins"]) // 100


def _streak(b: dict, key: str, holds: bool) -> int:
    b["streak"][key] = b["streak"].get(key, 0) + 1 if holds else 0
    return b["streak"][key]


def observe(state: dict, day: int) -> None:
    """Each night she looks: how many nights in a row each trouble has lasted, and once a week a line of history she can read years later."""
    b = book(state)
    b["attention"] = min(ATTENTION_CAP, float(b.get("attention", ATTENTION_CAP)) + 1 / ATTENTION_DAYS)
    rel = economy.view(state).get("rel", {})
    have, usual = economy.stock_levels(state)
    from . import money
    sup = money.supply(state)
    for index, flag in enumerate(b["flags"]):
        for target in _flag_targets(flag):
            _streak(b, f"flag:{index}:{target}", _flag_holds(state, flag, target, rel, have, usual, sup))
    b["acked"] = [k for k in b.get("acked", []) if b["streak"].get(k, 0) >= _flag_days(b, k)]   # an alarm she has seen stays quiet until it has stopped and come back
    for sid, shop in state["shops"].items():   # a workshop's shelf that has sat full and cheap: no work for him
        for line in shop["stock"]:
            if line["kind"] in ("armor", "weapon", "shield") and line.get("target") and line["qty"] is not None:
                _streak(b, f"idle:{sid}:{line['name']}", int(line["qty"]) >= int(line["target"]) and rel.get(line["name"], 1.0) < 0.8)
    if day % 7 == 0:
        b["history"] = (b["history"] + [{"d": day, "p": {g: round(rel.get(g, 1.0), 2) for g in GOODS}, "s": {g: have.get(g, 0) for g in GOODS}, "hens": flock(state),
                                         "purse": {pid: _purse_gp(state["bots"][pid]) for pid in PRODUCERS if pid in state["bots"]},
                                         "coin": [sup["tills_cp"] // 100, sup["households_cp"] // 100, sup["caravan_cp"] // 100]}])[-LIMITS["history"]:]


def _flag_targets(flag: dict) -> list[str]:
    of = flag.get("of")
    if of == "each good":
        names = list(GOODS)
    elif of == "each producer":
        names = list(PRODUCERS)
    else:
        names = [of or ""]
    return [n for n in names if n not in flag.get("except", [])]


def _flag_days(b: dict, key: str) -> int:
    index = int(key.split(":")[1])
    return int(b["flags"][index]["for_days"]) if index < len(b["flags"]) else 10 ** 9


def _flag_holds(state: dict, flag: dict, target: str, rel: dict, have: dict, usual: dict, sup: dict) -> bool:
    kind = flag["when"]
    if kind == "price_above":
        return rel.get(target, 1.0) >= flag["x"]
    if kind == "price_below":
        return rel.get(target, 1.0) <= flag["x"]
    if kind == "stock_below":   # a good no shelf is meant to hold cannot run out
        return usual.get(target, 0) > 0 and have.get(target, 0) < flag["n"]
    if kind == "stock_above":
        return have.get(target, 0) > flag["n"]
    if kind == "purse_below_gp":
        bot = state["bots"].get(target)
        return bot is not None and _purse_gp(bot) < flag["gp"]
    if kind == "flock_below":
        return flock(state) < flag["n"]
    return (sup["households_cp"] + sup["tills_cp"]) // 100 < flag["gp"]   # village_coin_below_gp


def _flag_text(flag: dict, target: str, days: int) -> str:
    kind, value = flag["when"], flag.get(FLAG_KINDS[flag["when"]])
    return {"price_above": f"{target} has been at {value} times its usual price or more for {days} nights",
            "price_below": f"{target} has been at {value} times its usual price or less for {days} nights",
            "stock_below": f"there have been fewer than {value} {target} in the village for {days} nights",
            "stock_above": f"there have been more than {value} {target} in the village for {days} nights",
            "purse_below_gp": f"{target} ({PRODUCERS.get(target, '')}) has had under {value} gp for {days} nights",
            "flock_below": f"the hen keeper's flock has been below {value} hens for {days} nights",
            "village_coin_below_gp": f"the households and the tills together have held under {value} gp for {days} nights"}[kind]


def active_flags(state: dict) -> list[tuple[str, str]]:
    """(key, what) for each alarm of hers that has held for as long as she asked."""
    b, out = book(state), []
    for key, days in b["streak"].items():
        if key.startswith("flag:"):
            _, index, target = key.split(":", 2)
            if int(index) < len(b["flags"]) and days >= int(b["flags"][int(index)]["for_days"]):
                out.append((key, _flag_text(b["flags"][int(index)], target, days)))
    return out


def alerts(state: dict) -> list[str]:
    """The disasters she can see right now (her own alarms that are on), each with how long it has lasted."""
    return [text for _, text in active_flags(state)]


def validate_flags(raw, known=frozenset()) -> list[dict] | None:
    """Her alarms as she writes them: {"when": price_above|price_below|stock_below|stock_above|purse_below_gp|flock_below|village_coin_below_gp, "of": good or producer or
    "each good" / "each producer", the limit (x, n or gp), "for_days", optional "except": [names]}. None when she wrote no list at all."""
    if not isinstance(raw, list):
        return None
    out = []
    for f in raw[:MAX_FLAGS * 2]:
        if not isinstance(f, dict) or f.get("when") not in FLAG_KINDS or len(out) >= MAX_FLAGS:
            continue
        kind, field = f["when"], FLAG_KINDS[f["when"]]
        try:
            flag = {"when": kind, "for_days": max(1, min(730, int(f.get("for_days", 1))))}
            if kind in ("price_above", "price_below"):
                flag["x"] = max(0.01, min(1000.0, float(f["x"])))
            else:
                flag[field] = max(0, min(100000, int(f[field])))
            if kind in ("price_above", "price_below", "stock_below", "stock_above"):
                of = f.get("of")
                if not (of == "each good" or of in GOODS or of == "Hen" or of in known):
                    continue
                flag["of"] = of
            elif kind == "purse_below_gp":
                if not (f.get("of") == "each producer" or f.get("of") in PRODUCERS):
                    continue
                flag["of"] = f["of"]
            if isinstance(f.get("except"), list) and flag.get("of", "").startswith("each"):
                flag["except"] = [str(e) for e in f["except"][:12]]
            out.append(flag)
        except (KeyError, TypeError, ValueError):
            continue
    return out


def _did(state: dict, day: int, what: str) -> None:
    b = book(state)
    b["done"] = (b["done"] + [{"day": day, "what": what}])[-LIMITS["done"]:]


def plan(state: dict, bot: dict, spec: dict, day: int) -> list[dict]:
    """Tonight: observe, then follow the standing orders that have held for long enough. Trades are returned for ``daily.act`` (buys at the cheapest
    shelf, sells at the shop that pays most); gifts of hens and coin are made here."""
    b = book(state)
    observe(state, day)
    rel = economy.view(state).get("rel", {})
    purse = dcc.coins_total_cp(bot["coins"])
    stored = sum(int(i.get("qty", 1)) for i in bot["inventory"])
    actions: list[dict] = []
    for index, order in enumerate(b["orders"]):
        key = f"o{index}"
        if "buy" in order:
            good, price = order["buy"], rel.get(order["buy"])
            ok = price is not None and price <= order["below"]
            if _streak(b, key, ok) >= order.get("for_days", 0) and ok and held(bot, good) < order["up_to"] and purse >= 100 * order.get("keep_gp", 0) and stored < LIMITS["cellar"]:
                actions += [{"do": "buy", "shop": "", "item": good, "count": 1}] * int(order.get("per_night", 1))
        elif "sell" in order:
            good, price = order["sell"], rel.get(order["sell"])
            if "when_metal_below_kg" in order:
                metals = [int((sh.get("materials") or {}).get("metal", 0)) / 1000 for sh in state["shops"].values() if (sh.get("materials") or {}).get("metal") is not None]
                ok = bool(metals) and min(metals) < order["when_metal_below_kg"]
            else:
                ok = price is not None and price >= order["above"]
            spare = held(bot, good) - int(order.get("keep", 0))
            at = next((n for n, i in enumerate(bot["inventory"]) if i["name"] == good and int(i.get("qty", 1)) > 0), None)
            if _streak(b, key, ok) >= order.get("for_days", 0) and ok and spare > 0 and at is not None:
                actions.append({"do": "sell", "shop": "", "index": at, "count": min(spare, int(order.get("per_night", 3)))})
        elif "give_hens" in order:
            detlef = state["bots"].get("detlef")
            if detlef and _streak(b, key, flock(state) < int(order["when_flock_below"])) >= 1:
                need, gave = int(order["give_hens"]), 0
                for stack in [i for i in bot["inventory"] if i["name"] == "Hen"]:
                    take = min(need - gave, int(stack.get("qty", 1)))
                    if take <= 0:
                        break
                    if take == int(stack.get("qty", 1)):
                        bot["inventory"].remove(stack)
                        detlef["inventory"].append(stack)
                    else:   # a stack of several: split it
                        stack["qty"] = int(stack["qty"]) - take
                        detlef["inventory"].append({**stack, "qty": take})
                    gave += take
                if gave:
                    _did(state, day, f"gave {gave} hens to Detlef, whose flock was down to {flock(state) - gave}")
        elif "aid" in order:
            pid, target = order["aid"], state["bots"].get(order["aid"])
            low = target is not None and _purse_gp(target) < int(order["when_purse_below_gp"])
            if _streak(b, key, low) >= order.get("for_days", 0) and low and day - b["aided"].get(pid, -999) >= int(order.get("every_days", 30)) and purse >= 2000 + 100 * int(order["gp"]):
                cp = 100 * int(order["gp"])
                total = dcc.coins_total_cp(bot["coins"]) - cp
                bot["coins"] = {"gp": total // 100, "sp": total % 100 // 10, "cp": total % 10}
                after = dcc.coins_total_cp(target["coins"]) + cp
                target["coins"] = {"gp": after // 100, "sp": after % 100 // 10, "cp": after % 10}
                b["aided"][pid] = day
                _did(state, day, f"gave {order['gp']} gp to {pid} ({PRODUCERS.get(pid, '')}), out of working capital")
    eggs = next((n for n, i in enumerate(bot["inventory"]) if i["name"] == "Eggs, a dozen" and int(i.get("qty", 1)) > 0), None)
    if eggs is not None:   # what her own hens lay goes to the shelves every night: her coin from the flock
        actions.append({"do": "sell", "shop": "", "index": eggs, "count": int(bot["inventory"][eggs].get("qty", 1))})
    if actions:
        _did(state, day, "traded " + ", ".join(sorted({a["item"] if a["do"] == "buy" else bot["inventory"][a["index"]]["name"] for a in actions})))
    return actions


def _span(values: list, last: int) -> list:
    window = [v for v in values[-last:] if v is not None]
    return [round(min(window), 2), round(sum(window) / len(window), 2), round(max(window), 2)] if window else []


def _squeeze(b: dict, day: int) -> None:
    """Keep the notebook inside its limits: expired notes go, then the oldest unpinned ones until it fits (she is told which in the next report)."""
    notes = [n for n in b["notes"] if n.get("until") is None or day <= n["until"]]
    lost = []
    def over() -> bool:
        return len(notes) > NOTE_LIMITS["entries"] or sum(len(n["text"]) for n in notes) > NOTE_LIMITS["chars"]
    while over():
        old = next((n for n in notes if not n["pin"]), None)
        if old is None:
            break
        notes.remove(old)
        lost.append(old["text"][:70])
    b["notes"] = notes
    b["lost_for_room"] = lost
    b["notebook"] = "\n".join(n["text"] for n in notes)


def _cut(b: dict, note_id, text: str) -> str:
    """A note at most NOTE_LIMITS["text"] long; what is cut off is told back to her (until 10-11 she lost the ends of notes without knowing)."""
    text, limit = text.strip(), NOTE_LIMITS["text"]
    if len(text) > limit:
        b["changed_by_rules"] = b.get("changed_by_rules", []) + [f"note {note_id} was cut at {limit} characters; this end was lost: {text[limit:][:200]!r}"]
    return text[:limit]


def edit_notes(b: dict, answer: dict, day: int) -> None:
    """Her notebook edits: ``notes_delete`` (ids), ``notes_edit`` ({id: new text}; empty text deletes), ``notes_add`` ([text or {text, pin, forget_after_days}]).
    An answer with the old whole-text ``notebook`` replaces everything with that one note."""
    notes = b["notes"]
    if isinstance(answer.get("notebook"), str):
        notes[:] = [{"id": b["next_note"], "day": day, "text": answer["notebook"][:NOTE_LIMITS["chars"]], "pin": False, "until": None}] if answer["notebook"].strip() else []
        b["next_note"] += 1
    gone = {int(i) for i in (answer.get("notes_delete") if isinstance(answer.get("notes_delete"), list) else []) if str(i).lstrip("-").isdigit()}
    notes[:] = [n for n in notes if n["id"] not in gone]
    for key, text in (answer.get("notes_edit") if isinstance(answer.get("notes_edit"), dict) else {}).items():
        note = next((n for n in notes if str(n["id"]) == str(key)), None)
        if note is not None and isinstance(text, str):
            if text.strip():
                note["text"], note["day"] = _cut(b, note["id"], text), day
            else:
                notes.remove(note)
    for new in (answer.get("notes_add") if isinstance(answer.get("notes_add"), list) else [])[:10]:
        entry = {"text": new} if isinstance(new, str) else new if isinstance(new, dict) else {}
        text = entry.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        pin = bool(entry.get("pin")) and sum(n["pin"] for n in notes) < NOTE_LIMITS["pins"]
        try:
            until = day + max(1, min(36500, int(entry["forget_after_days"]))) if entry.get("forget_after_days") else None
        except (TypeError, ValueError):
            until = None
        notes.append({"id": b["next_note"], "day": day, "text": _cut(b, b["next_note"], text), "pin": pin, "until": until})
        b["next_note"] += 1
    _squeeze(b, day)


def load_seed(state: dict, day: int, text: str) -> int:
    """Add the lines of a seed file to her notebook as pinned notes, each line once ever (``#`` lines and blank lines are skipped). A note she has since
    rewritten or deleted is hers: it is not put back."""
    b = book(state)
    given = set(b.setdefault("seed_given", [n["text"] for n in b["notes"] if n["pin"]]))   # a book from before: what is pinned now was given
    lines = [ln.strip()[:NOTE_LIMITS["text"]] for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    new = [ln for ln in lines if ln not in given]
    edit_notes(b, {"notes_add": [{"text": ln, "pin": True} for ln in new]}, day)
    b["seed_given"] = sorted(given | set(new))
    return len(new)


def validate_wake(raw, known=frozenset()) -> dict | None:
    """Her next check-in as she asks for it: ``in_days`` (the latest) and ``or_when``, up to a few conditions any one of which wakes her sooner.
    A condition is one of {"flock_below": n}, {"price_above"|"price_below": good, "x": ratio_to_usual}, {"stock_below"|"stock_above": good, "n": pieces},
    {"purse_below_gp": producer_id, "gp": n}, {"disaster": true}. Anything else is dropped."""
    if not isinstance(raw, dict):
        return None
    try:
        days = max(1, min(MAX_GAP, int(raw.get("in_days", DEFAULT_GAP))))
    except (TypeError, ValueError):
        days = DEFAULT_GAP
    wake = []
    for c in (raw.get("or_when") if isinstance(raw.get("or_when"), list) else [])[:20]:
        if not isinstance(c, dict) or len(wake) >= MAX_WAKE_CONDITIONS:
            continue
        try:
            if "flock_below" in c:
                wake.append({"flock_below": max(1, min(500, int(c["flock_below"])))})
            elif any(k in c for k in ("price_above", "price_below")):
                kind = "price_above" if "price_above" in c else "price_below"
                if c[kind] in GOODS or c[kind] == "Hen" or c[kind] in known:
                    wake.append({kind: c[kind], "x": max(0.01, min(100.0, float(c["x"])))})
            elif any(k in c for k in ("stock_below", "stock_above")):
                kind = "stock_below" if "stock_below" in c else "stock_above"
                if c[kind] in GOODS or c[kind] == "Hen" or c[kind] in known:
                    wake.append({kind: c[kind], "n": max(0, min(100000, int(c["n"])))})
            elif "purse_below_gp" in c and c["purse_below_gp"] in PRODUCERS:
                wake.append({"purse_below_gp": c["purse_below_gp"], "gp": max(1, min(1000, int(c["gp"])))})
            elif c.get("disaster"):
                wake.append({"disaster": True})
        except (KeyError, TypeError, ValueError):
            continue
    return {"in_days": days, "or_when": wake}


def _wake_hit(state: dict, c: dict) -> str | None:
    rel = economy.view(state).get("rel", {})
    have, _ = economy.stock_levels(state)
    if "flock_below" in c and flock(state) < c["flock_below"]:
        return f"only {flock(state)} hens are left (you asked to be woken below {c['flock_below']})"
    if "price_above" in c and rel.get(c["price_above"], 1.0) > c["x"]:
        return f"{c['price_above']} is above {c['x']} times its usual price"
    if "price_below" in c and rel.get(c["price_below"], 1.0) < c["x"]:
        return f"{c['price_below']} is below {c['x']} times its usual price"
    for key, above in (("stock_below", False), ("stock_above", True)):
        if key in c:
            n = have.get(c[key], 0)
            if (n > c["n"]) if above else (n < c["n"]):
                return f"{n} {c[key]} are in the village (you asked to be woken {'above' if above else 'below'} {c['n']})"
    if "purse_below_gp" in c:
        bot = state["bots"].get(c["purse_below_gp"])
        if bot and _purse_gp(bot) < c["gp"]:
            return f"{c['purse_below_gp']}'s purse is below {c['gp']} gp"
    if c.get("disaster"):
        fresh = [text for key, text in active_flags(state) if key not in book(state).get("acked", [])]
        if fresh:
            return "a new alarm of yours is on: " + fresh[0]
    return None


def due(state: dict, day: int) -> str | None:
    """Why she should look over the village tonight, or None. The date she set always wakes her; her conditions wake her sooner only while she has
    attention left (every check-in costs a point), and never twice in a night."""
    cfg = places.STEWARD
    if not cfg or ID not in state["bots"]:
        return None
    spec = next((s for s in places.BOTS if s["id"] == ID), None)
    if places.LIVES and spec and lives.vacant_bot(state, spec):
        return None   # she is dead: nobody looks (until 10-11 she went on looking for seven years after her death)
    b = book(state)
    since, nxt = day - int(b["checked"]), b.get("next")
    if not nxt:
        return "the usual interval has passed" if since >= int(cfg.get("every", 30)) else None
    if float(b.get("attention", ATTENTION_CAP)) < 1:
        return None   # spent: she sleeps until enough has come back, her own date included
    if day >= int(nxt["day"]):
        return f"the {nxt['in_days']} days you set have passed"
    if since >= 1:
        for c in nxt["or_when"]:
            why = _wake_hit(state, c)
            if why:
                return why
    return None


def buyers_of(state: dict, good: str) -> list[str]:
    """The places a producer can sell a good to: those that keep a shelf of it, and the shop that buys anything (for a pittance); shut or open. When the one
    place that buys barley and eggs shut, the whole chain stopped for years, and she could not see why (the owner 10-10: she must know)."""
    out = []
    for shop in state["shops"].values():
        if "caravan" in shop.get("kinds", []):
            continue
        shelf = any(town._listed(l) and l["name"] == good for l in shop.get("stock", []))
        if shelf or shop.get("buys_anything"):
            shut = town.closed_reason(shop)
            out.append(f"{shop['name']}" + ("" if shelf else " (buys anything, pays a pittance)") + (f": SHUT, {shut}" if shut else ""))
    return out


TEACHINGS_FILE = dcc.REPO_DIR / "data" / "steward" / "teachings.md"   # live copy: the owner and Claude edit it, no deploy needed


def teachings() -> str:
    """The Old Order's words: her other memory, written by the people who keep the world and read by her at every look. The live file wins; the bundled one is the seed."""
    for path in (Path(os.environ.get("WESTMARCH_TEACHINGS") or TEACHINGS_FILE), Path(__file__).parent / "teachings.md"):
        try:
            return path.read_text(encoding="utf-8")[:4000]
        except OSError:
            continue
    return ""


def report(state: dict, day: int, why: str = "") -> dict:
    """What she sees when she looks over the village: months and years of prices and stocks, every producer, the flock, the coin, her deeds."""
    b, market = book(state), state.get("market") or {}
    rel = economy.view(state).get("rel", {})
    have, usual = economy.stock_levels(state)
    me = state["bots"].get(ID, {"coins": {}, "inventory": []})
    history = b["history"]
    goods = {}
    for g in GOODS:
        series = [h["p"].get(g) for h in history]
        goods[g] = {"price_now": round(rel.get(g, 1.0), 2), "stock_in_village": have.get(g, 0), "usual_stock": usual.get(g, 0), "i_hold": held(me, g),
                    "producers_can_sell_it_only_to": buyers_of(state, g),
                    "price_min_mean_max_last_3_months": _span(series, 13), "price_min_mean_max_last_year": _span(series, 52), "price_min_mean_max_last_5_years": _span(series, 156)}
    from . import money
    sup = money.supply(state)
    workshops = {}
    for sid, shop in state["shops"].items():
        if shop.get("materials") is not None:
            idle = sorted(((days, key.split(":", 2)[2]) for key, days in b["streak"].items() if key.startswith(f"idle:{sid}:") and days >= 30), reverse=True)[:8]
            workshops[shop["name"]] = {"raw_material_kg": {m: round(int(g) / 1000, 1) for m, g in shop["materials"].items()}, "till_gp": int(shop.get("till", 0)) // 100,
                                       "shelf_pieces_that_have_sat_full_and_cheap_for_30_nights_or_more": [{"item": n, "nights": d, "price_now": round(rel.get(n, 1.0), 2)} for d, n in idle]}
    return {"day": day, "year": round(day / 365, 1), "workshops": workshops,
            "disasters_now": alerts(state) or ["none"],
            "flock_of_the_hen_keeper": flock(state), "my_own_hens": held(me, "Hen"), "my_barley_for_them": held(me, "Barley, a sack"), "flock_each_quarter_last_2_years": [h["hens"] for h in history[-104::13]],
            "producers": {pid: {"trade": what, "purse_gp": _purse_gp(state["bots"][pid]) if pid in state["bots"] else None,
                                "purse_each_quarter_last_2_years": [h["purse"].get(pid) for h in history[-104::13]]} for pid, what in PRODUCERS.items()},
            "coin_gp": {"tills": sup["tills_cp"] // 100, "households": sup["households_cp"] // 100, "in_the_wagons": sup["caravan_cp"] // 100,
                        "finanzamt": sup["finanzamt_cp"] // 100, "my_purse": _purse_gp(me), "my_working_capital": places.STEWARD_CAPITAL_CP // 100},
            "what_the_players_spent_lately_made_prices_x": market.get("inflation", 1.0), "weather_yield_factor": market.get("weather", 1.0),
            "goods": goods, "my_cellar_things": sum(int(i.get("qty", 1)) for i in me["inventory"]), "my_cellar_limit": LIMITS["cellar"],
            **({"village_people": lives.summary(state, day)} if places.LIVES else {}),
            **({"the_land": fields.summary(state, day)} if places.FIELDS else {}),
            "the_old_order_teachings": teachings(), "my_deeds_lately": b["done"][-15:], "my_orders": b["orders"], "my_last_answer_changed_by_the_rules": b.get("changed_by_rules", []),
            "my_flags": b["flags"], "my_notebook": [{"id": n["id"], "day": n["day"], "pin": n["pin"], **({"forgotten_on_day": n["until"]} if n.get("until") else {}), "text": n["text"]} for n in b["notes"]],
            "notebook_room": {"characters_left": NOTE_LIMITS["chars"] - sum(len(n["text"]) for n in b["notes"]), "entries_left": NOTE_LIMITS["entries"] - len(b["notes"]),
                              "pins_left": NOTE_LIMITS["pins"] - sum(n["pin"] for n in b["notes"]), "dropped_for_lack_of_room_last_time": b.get("lost_for_room", [])},
            "check_ins": {"woken_because": why or "(not said)", "attention_left": round(float(b.get("attention", ATTENTION_CAP)), 1),
                          "attention_rules": f"a look costs attention in proportion to what you read and write: a plain look about 1 point, each look_up round about as much again. "
                                             f"Attention comes back at about {ATTENTION_PER_YEAR} points a year and you can save up to {int(ATTENTION_CAP)}. With less than 1 point nothing wakes you, "
                                             "not even your own date, until enough has come back; save some for a crisis",
                          "you_asked_to_be_woken": b.get("next") or "(nothing asked: the usual interval)"}}


def look(state: dict, day: int, queries) -> list[dict]:
    """What she asked to see of the people (``lives.look_up``): the report only outlines them."""
    return lives.look_up(state, day, queries) if places.LIVES else []


BUY_CAP = 2.0   # a buy order pays at most twice the usual price, the floor of a sell order (1.0 until 10-10: her hens' barley was never cheap enough)


def changed_by_rules(asked, kept: list[dict]) -> list[str]:
    """What the rules altered or dropped in the orders she wrote, told back to her at her next look (she once "raised" a buy limit twice that had been cut to the cap)."""
    out = []
    asked = asked if isinstance(asked, list) else []
    for o in asked:
        if not isinstance(o, dict):
            continue
        twin = next((k for k in kept if all(k.get(f) == o.get(f) for f in ("buy", "sell", "aid", "give_hens") if f in o)), None)
        if twin is None:
            out.append(f"dropped: {json.dumps(o, ensure_ascii=False)[:160]}")
            continue
        for key, value in o.items():
            if key in twin and isinstance(value, (int, float)) and not isinstance(value, bool) and float(value) != float(twin[key]):
                out.append(f"{o.get('buy') or o.get('sell') or o.get('aid') or 'give_hens'}: {key} {value} became {twin[key]} (the rules' bound)")
    return out[:10]


def validate(orders, known=frozenset()) -> list[dict]:
    """Only orders she can really carry out, with their numbers kept inside sane bounds. Anything else a brain writes is dropped."""
    out = []
    for o in (orders if isinstance(orders, list) else [])[:LIMITS["orders"]]:
        if not isinstance(o, dict):
            continue
        try:
            days = max(0, min(365, int(o.get("for_days", 0))))
            if "buy" in o and (o["buy"] in GOODS or o["buy"] == "Hen" or o["buy"] in known):
                out.append({"buy": o["buy"], "below": max(0.01, min(BUY_CAP, float(o["below"]))), "for_days": days, "up_to": max(1, min(LIMITS["up_to"], int(o.get("up_to", 10)))),
                            "per_night": max(1, min(LIMITS["per_night"], int(o.get("per_night", 1)))), "keep_gp": max(0, min(10000, int(o.get("keep_gp", 50))))})
            elif "sell" in o and (o["sell"] in GOODS or o["sell"] in known):
                order = {"sell": o["sell"], "for_days": days, "keep": max(0, int(o.get("keep", 0))), "per_night": max(1, min(LIMITS["per_night"], int(o.get("per_night", 3))))}
                if "when_metal_below_kg" in o:   # sell it back to the workshop that needs the metal, not at a price
                    order["when_metal_below_kg"] = max(1, min(1000, int(o["when_metal_below_kg"])))
                else:
                    order["above"] = max(2.0, min(100.0, float(o["above"])))
                out.append(order)
            elif "give_hens" in o:
                out.append({"give_hens": max(1, min(12, int(o["give_hens"]))), "when_flock_below": max(1, min(12, int(o["when_flock_below"])))})
            elif "aid" in o and o["aid"] in PRODUCERS:
                out.append({"aid": o["aid"], "gp": max(1, min(20, int(o["gp"]))), "when_purse_below_gp": max(1, min(20, int(o["when_purse_below_gp"]))),
                            "for_days": days, "every_days": max(7, min(365, int(o.get("every_days", 30))))})
        except (KeyError, TypeError, ValueError):
            continue
    return out


def apply(state: dict, day: int, answer: dict, why: str = "", cost: float = 1.0) -> None:
    """Take a brain's answer: new orders (if valid; the old streaks start over), a new notebook, and perhaps one line for the town note."""
    b = book(state)
    orders = validate(answer.get("orders"), known_items(state))
    b["changed_by_rules"] = changed_by_rules(answer.get("orders"), orders) if "orders" in answer else []
    if orders:
        b["orders"] = orders
        b["streak"] = {k: v for k, v in b["streak"].items() if not k.startswith("o")}
    flags = validate_flags(answer.get("flags"), known_items(state))
    if flags is not None and (flags or answer.get("flags") == []):
        b["flags"] = flags
        b["streak"] = {k: v for k, v in b["streak"].items() if not k.startswith("flag:")}
    edit_notes(b, answer, day)
    if places.LIVES and "mentor" in answer:
        taught = {m["child"] for m in lives.set_mentoring(state, day, answer["mentor"])}
        b["changed_by_rules"] = b.get("changed_by_rules", []) + [f"mentor dropped (not a living child under age, or no such trade): {json.dumps(m, ensure_ascii=False)[:120]}"
                                                                 for m in (answer["mentor"] if isinstance(answer["mentor"], list) else [])
                                                                 if not isinstance(m, dict) or m.get("child") not in taught][:5]
    if places.LIVES and "blocks" in answer:
        lives.set_blocks(state, day, answer["blocks"])
    if places.LIVES and "matches" in answer:
        lives.set_matches(state, day, answer["matches"])
    note = answer.get("town_note")
    if isinstance(note, str) and note.strip() and day - int(b.get("note_day", -999)) >= NOTE_EVERY:
        town.town_note_write(state, "Hedwig Dornbusch", note.strip()[:LIMITS["note"]])
        b["note_day"] = day
    b["checked"] = day
    b["acked"] = [k for k, _ in active_flags(state)]   # she has seen what is on now: only a new alarm wakes her for "disaster"
    b["attention"] = max(0.0, float(b.get("attention", ATTENTION_CAP)) - max(0.0, float(cost)))   # what the look cost, in points of an average call
    wake = validate_wake(answer.get("next_checkin"), known_items(state)) or ({"in_days": DEFAULT_GAP, "or_when": []} if answer else None)
    b["next"] = {"day": day + wake["in_days"], "in_days": wake["in_days"], "or_when": wake["or_when"]} if wake else None
    b["log"] = (b["log"] + [{"day": day, "orders": len(b["orders"]), "why": why[:120], "next": wake}])[-20:]


PERSONA = ("You are Hedwig Dornbusch, the herb woman of a small frontier village in a world of swords, sorcery and ruins left by a vanished age of metal. "
           "You are an elf and have watched this village for three hundred years. You steer it only by what you yourself do, and you do very little: "
           "the village is meant to swing wildly, a good nearly free for weeks and then forty times the usual price, and you do not want to stop that. "
           "You are like the Bene Gesserit: your plans span centuries, not quarters. "
           "You step in only to prevent a disaster: the chickens dying out, a producer out of working capital for weeks, a staple gone from the village "
           "for weeks, a price stuck at an extreme until its producer gives up. A slower disaster: a seat of the village (a trade or a house that passes from parent "
           "to child) standing empty for years. Short gaps are nothing, but in the long run every seat must have someone in it, and teaching a child the trade is how you see to it. You do not trade for profit and you do not hoard: your cellar is small and "
           "what you earn above your working capital goes back to the village. Your tools are standing orders you write ahead (a buy or sell order only "
           "acts after the trouble has lasted for_days nights, so that ordinary swings are left alone), hens you give to the hen keeper, and a little coin "
           "you give to a producer with none. Think in years, decades, centuries. Change your orders, and what you write to the village notebook (the town note), "
           "only slowly and for a reason you write into your own notebook. Find solutions to problems: if a smith has inventory sitting on his shelf but no work, "
           "consider buying the armor not for yourself but to sell it back as scrap in five years, when he needs the metal. Your tools are limited, but you "
           "can be free in your notes; steer the village benevolently and consistently. "
           "Every time you look over the village it costs the person who keeps this world real money, and you have a limited store of attention, so look rarely: "
           "a year with a handful of check-ins is better than a year with many. You decide when you look next. After a quiet check-in say that you will look again "
           "in a year or two; when you want to watch something change, look often for a while (every few days, even every night for two weeks) and then go quiet again. "
           "The hens are the village's most fragile thing: keep a few laying hens of your own at all times (they eat your barley, and their eggs are sold for you "
           "every night), and when the hen keeper's flock runs low give or sell him hens from yours before it is gone. "
           "You may also name the things that should wake you earlier, such as the flock falling below a number or a price passing a limit. "
           "The villagers are mortal, they marry and have children, and over the centuries the village is its families. Your hand in it stays hidden: you may bring two single people "
           "of the same kind together (they wed far likelier, and nobody learns you had a hand in it), and you use this to keep good families alive, above all families whose "
           "children could become the delver, the one who goes into the dungeon and whose strength sets how much treasure comes back. Never act in a way that dragons, adventurers or spies could trace. "
           "The report holds \"the_old_order_teachings\": the words of the Old Order, your teachers across the centuries, kept in your other memory. They are not yours to change; weigh them like a teacher's advice, act on them quietly and in your own time, and never write them into the village.")


def brain_request(rep: dict) -> dict:
    """What a Claude brain is asked: the system prompt (her persona) and the user prompt (how to answer, then the report). The host script that runs
    Claude needs nothing else from this module."""
    ask = ("This is your report of the village. Decide whether your standing orders should change, and tend your notebook (your only memory, a few short notes with ids: "
           f"at most {NOTE_LIMITS['chars']} characters and {NOTE_LIMITS['entries']} notes in all, {NOTE_LIMITS['text']} characters each). Keep it lean: delete what is settled or no longer true, "
           "merge what repeats, keep what you will need in years. What you were woken for is not automatically worth a note. When it is full the oldest unpinned notes are dropped, "
           "and the report tells you which. Notebook edits: \"notes_delete\": [ids], \"notes_edit\": {\"id\": \"new text, or empty to delete\"}, "
           "\"notes_add\": [\"text\" or {\"text\": ..., \"pin\": true (kept when room is short, a few only), \"forget_after_days\": n}]. "
           "Your alarms (\"my_flags\") are yours to define: they say what counts as a disaster, and a new one wakes you if you asked to be woken on {\"disaster\": true}. "
           "To change them send the whole list as \"flags\": [up to 12 of {\"when\": price_above|price_below (\"x\" times the usual price) | stock_below|stock_above (\"n\" pieces) | "
           "purse_below_gp (\"gp\", \"of\" a producer id or \"each producer\") | flock_below (\"n\") | village_coin_below_gp (\"gp\"), \"of\": a good or \"each good\", \"for_days\", optional \"except\": [names]}]. "
           "The report only outlines the people (\"village_people\"). To see individuals, answer first with nothing but {\"look_up\": [up to 3 queries]} and you are given the results and asked again, "
           "at most twice, and each question costs real money. Queries: {\"person\": name} (with family), {\"singles\": {\"race\": ..., \"sex\": \"f\" or \"m\"}}, {\"children\": true} "
           "(their scores are fixed at birth and known to you eighteen years before they work), {\"couples\": true}, {\"best_for_delver\": n}, {\"trade\": text}. "
           "Matchmaking: \"matches\": [up to 3 of {\"a\": name, \"b\": name}] replaces your list (both single adults of the same kind, other sexes, near in age, not kin); "
           "each pair then weds in a given month with a high chance, for up to two years. "
           "Blocking: \"blocks\": [up to 6 of {\"a\": name, \"b\": name}] replaces your list; any two living people, and a blocked pair weds a hundred times less often for as long as the block stands. "
           "Teaching: \"mentor\": [up to 4 of {\"child\": name, \"trade\": a job from the table or one of the village's trades as named under townsfolk_seats}] replaces your list; "
           "at eighteen the child most likely takes that trade (an empty seat is filled by whoever has its trade). Nobody learns it was you. "
           "If nothing is a disaster or about to become one, return the same orders. Orders are objects of these kinds, goods exactly as named in the report (the staples, \"Hen\", or any piece named under \"workshops\"): "
           '{"buy": good_or_"Hen", "below": price_ratio_0.01_to_2, "for_days": 0_to_365, "up_to": units_held_1_to_60, "per_night": 1_to_10, "keep_gp": gold_to_keep_in_purse}, '
           '{"sell": good, "above": price_ratio_2_to_100 OR "when_metal_below_kg": kg_of_metal_a_workshop_has_left, "for_days": 0_to_365, "keep": units_kept, "per_night": 1_to_10}, '
           '{"give_hens": count_1_to_12, "when_flock_below": 1_to_12}, '
           '{"aid": producer_id (detlef, xaver, jutta, reinhild, hartmut, ivo), "gp": 1_to_20, "when_purse_below_gp": 1_to_20, "for_days": 0_to_60, "every_days": 7_to_365}. '
           'Also say when you will look again: "next_checkin": {"in_days": 1_to_730, "or_when": [up to 5 of {"flock_below": hens}, {"price_above": good, "x": ratio_to_usual}, '
           '{"price_below": good, "x": ratio_to_usual}, {"stock_below": good, "n": pieces}, {"stock_above": good, "n": pieces}, {"purse_below_gp": producer_id, "gp": gold}, {"disaster": true}]}. '
           'The date wakes you and a condition may wake you earlier, both only while you have at least one point of attention (see "check_ins" in the report). Without next_checkin you are woken in 90 nights. '
           'Answer with JSON only: {"orders": [...], "notes_add": [...], "notes_delete": [...], "notes_edit": {...}, "flags": [...], "matches": [...], "blocks": [...], "mentor": [...], "town_note": "optional, one short line", "next_checkin": {...}}; leave out what you do not change.\n\n' + json.dumps(rep))
    return {"system": PERSONA, "prompt": ask}


def run_claude(request: dict, model: str = "sonnet") -> dict:
    """Run a headless Claude with no tools on a request from ``brain_request``; its JSON answer, or {} when there is none. Needs the claude CLI
    (on the host, not in the town container)."""
    import tempfile
    from pathlib import Path
    here = Path(tempfile.gettempdir()) / "hedwig-cwd"   # an empty directory outside your home directory: no CLAUDE.md or project memory reaches her
    here.mkdir(exist_ok=True)
    out = subprocess.run(["claude", "-p", "--tools", "", "--no-session-persistence", "--model", model, "--system-prompt", request["system"], request["prompt"]],
                         capture_output=True, text=True, timeout=300, cwd=here)
    text = out.stdout.strip()
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start:end + 1]) if start >= 0 < end else {}


def claude_brain(rep: dict, model: str = "sonnet") -> dict:
    return run_claude(brain_request(rep), model)


def maybe_checkin(state: dict, day: int) -> bool:
    """On the nights she is due, ask her brain in process (``brain`` "rules": no answer, the standing orders stay). With ``brain`` "host" nothing happens
    here: a host script (``scripts/steward_checkin.py``) asks ``due`` and runs the headless Claude, which the town container does not have."""
    cfg = places.STEWARD
    if not cfg or cfg.get("brain", "rules") == "host":
        return False
    why = due(state, day)
    if not why:
        return False
    apply(state, day, {}, why)
    return True
