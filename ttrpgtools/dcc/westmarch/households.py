"""One purse per household, and none per villager (Dodo 10-11).

A household is a couple and their minor children, or one adult. Its purse lives in ``state["households"]`` ({"<id>": coin}); ``people.household_id`` says who belongs
to which. A played villager has no household: the character's own coins are the purse. ``state["money"]["households"]`` stays the sum of all purses: the economy's
flows (diet, wages, refills, relief) still change that one number, and ``reconcile`` then spreads the difference over the purses (a gain by headcount, a loss in
proportion to what each holds), so coin is never made or lost. Flows that belong to one household (a shop's wages to its keeper's house, a trader's surplus
to the trader's family, a plot sold by a villager) name it with ``credit``.
"""

from __future__ import annotations

KEY, SEQ = "households", "household_seq"


def purses(state: dict) -> dict:
    return state.setdefault(KEY, {})


def _aggregate(state: dict) -> int:
    return int(state["money"].get("households", 0))


def total(state: dict) -> int:
    return sum(purses(state).values())


def headcounts(db) -> dict:
    """{household id: living members}."""
    return {r[0]: r[1] for r in db.execute("SELECT household_id, COUNT(*) FROM people WHERE status = 'alive' AND household_id IS NOT NULL GROUP BY household_id")}


def new(state: dict, coin: int = 0) -> int:
    hid = int(state.get(SEQ, 0)) + 1
    state[SEQ] = hid
    purses(state)[str(hid)] = int(coin)
    return hid


def _spread_gain(box: dict, weights: dict, amount: int) -> None:
    if not box:
        box["0"] = 0
    keys = [str(h) for h in weights if str(h) in box] or list(box)
    w = {k: max(1, int(weights.get(int(k) if k.lstrip("-").isdigit() else k, 1))) for k in keys}
    whole = sum(w.values())
    given = 0
    for k in keys:
        part = amount * w[k] // whole
        box[k] += part
        given += part
    box[max(keys, key=lambda k: w[k])] += amount - given


def _spread_loss(box: dict, amount: int) -> None:
    held = sum(box.values())
    amount = min(amount, held)
    if amount <= 0:
        return
    taken = 0
    for k in box:
        part = amount * box[k] // held
        box[k] -= part
        taken += part
    for k in sorted(box, key=lambda k: -box[k]):   # the rest from the richest, one coin at a time at most what each has
        if taken >= amount:
            break
        part = min(box[k], amount - taken)
        box[k] -= part
        taken += part


def reconcile(state: dict, db) -> None:
    """Make the purses add up to ``state["money"]["households"]``. Households the database knows but the purses do not get an empty purse."""
    box = purses(state)
    counts = headcounts(db)
    for hid in counts:
        box.setdefault(str(hid), 0)
    delta = _aggregate(state) - sum(box.values())
    if delta > 0:
        _spread_gain(box, counts, delta)
    elif delta < 0:
        _spread_loss(box, -delta)
    state["money"]["households"] = sum(box.values())


def credit(state: dict, db, household_id, cp: int) -> None:
    """Coin into one household (a flow that belongs to it); without a household, to all by headcount."""
    reconcile(state, db)
    box = purses(state)
    if household_id is not None and str(household_id) in box:
        box[str(household_id)] += int(cp)
    else:
        _spread_gain(box, headcounts(db), int(cp))
    state["money"]["households"] = sum(box.values())


def debit(state: dict, db, household_id, cp: int) -> int:
    """Coin out of one household, at most what it holds. Returns what came out."""
    reconcile(state, db)
    box = purses(state)
    took = min(int(cp), box.get(str(household_id), 0))
    if took > 0:
        box[str(household_id)] -= took
    state["money"]["households"] = sum(box.values())
    return max(0, took)


def endow(state: dict, db, cp: int) -> int:
    """A new household of one, with ``cp`` taken from the others (as far as they hold it). Returns its id."""
    reconcile(state, db)
    box = purses(state)
    cp = min(int(cp), sum(box.values()))
    _spread_loss(box, cp)
    hid = new(state, cp)
    state["money"]["households"] = sum(box.values())
    return hid


def of(db, name: str):
    row = db.execute("SELECT household_id FROM people WHERE name = ? AND status = 'alive'", (name,)).fetchone()
    return row[0] if row else None


def merge(db, state: dict, keep, gone) -> None:
    """Two households become one (a wedding): the purses add up and the members move over."""
    if keep is None or gone is None or keep == gone:
        return
    box = purses(state)
    reconcile(state, db)
    box[str(keep)] = box.get(str(keep), 0) + box.pop(str(gone), 0)
    db.execute("UPDATE people SET household_id = ? WHERE household_id = ?", (keep, gone))


def dissolve_if_empty(db, state: dict, household_id) -> None:
    """A household with nobody left alive returns its coin to the others, by headcount."""
    if household_id is None or db.execute("SELECT 1 FROM people WHERE household_id = ? AND status = 'alive' LIMIT 1", (household_id,)).fetchone():
        return
    box = purses(state)
    reconcile(state, db)
    left = box.pop(str(household_id), 0)
    if left:
        _spread_gain(box, headcounts(db), left)
    state["money"]["households"] = sum(box.values())


def migrate(db, state: dict) -> dict:
    """Once: give every living villager a household and share the old pool (and the coin in the villagers' own purses, which stop counting) by headcount.
    A household is a couple and their children under eighteen, or one adult. Played villagers belong to none."""
    from . import lives
    cfg = lives.config()
    day = int(state["last_daily"])
    people = [dict(r) for r in db.execute("SELECT * FROM people WHERE status = 'alive' AND claimed_by IS NULL")]
    by_id = {p["id"]: p for p in people}
    parent = {p["id"]: p["id"] for p in people}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        if a in parent and b in parent:
            parent[find(a)] = find(b)

    for p in people:
        if p["spouse_id"] in by_id:
            union(p["id"], p["spouse_id"])
        young = p["born_day"] is not None and lives.age_of(p, day) < cfg["adult"]
        if young:
            union(p["id"], p["mother_id"] if p["mother_id"] in by_id else p["father_id"])
    groups: dict = {}
    for p in people:
        groups.setdefault(find(p["id"]), []).append(p["id"])
    import json
    sheets = [json.loads(r[0]) for r in db.execute("SELECT sheet FROM people WHERE status != 'dead' AND claimed_by IS NULL AND sheet IS NOT NULL")]
    pool = _aggregate(state) + sum(int(s.get("copper", 0)) for s in sheets)
    state[KEY], state[SEQ] = {}, 0
    members = len(people) or 1
    given = 0
    ids = []
    for ids_in in groups.values():
        hid = new(state)
        ids.append(hid)
        share = pool * len(ids_in) // members
        state[KEY][str(hid)] = share
        given += share
        db.execute(f"UPDATE people SET household_id = ? WHERE id IN ({','.join('?' * len(ids_in))})", (hid, *ids_in))
    if ids:
        state[KEY][str(ids[0])] += pool - given
    db.execute("UPDATE people SET household_id = NULL WHERE claimed_by IS NOT NULL OR status != 'alive'")
    state["money"]["households"] = sum(state[KEY].values())
    state["household_mode"] = True
    return {"households": len(groups), "people": len(people), "pool_cp": pool}


# ---------------------------------------------------------------- what villagers own (Dodo 10-12: every villager is modelled with an inventory)
PERSON, PANTRY = "person", "household"   # item holders: a villager's own pack (their kit), and a household's pantry (barley, hens, food)
OUTFIT_CP, OUTFIT_BARLEY = 500, 1        # what each villager brings to the household when inventories begin: five gold (from the Finanzamt) and a sack


def kit(content: dict, row) -> list[dict]:
    """A villager's 0-level things, as a player taking them over would get them: weapon, trade good, item."""
    import json
    from . import registry
    from ttrpgtools import dcc
    if not row["sheet"]:
        return []
    ch = registry.build_character(content, row["name"], json.loads(row["sheet"]))
    return [dict(i) for i in dcc.ensure_inventory(ch)]


def settle(db, state: dict, row, content: dict) -> None:
    """Give one villager their kit: their own things into their pack, a hen of it into the household's pantry (hens belong to the house)."""
    from . import clauses, items
    things = kit(content, row)
    mine = [t for t in things if not clauses.is_hen(t["name"])]
    hens = [t for t in things if clauses.is_hen(t["name"])]
    items.replace(PERSON, str(row["id"]), items.load(PERSON, str(row["id"]), db) + mine, db)
    if hens and row["household_id"] is not None:
        items.replace(PANTRY, str(row["household_id"]), items.load(PANTRY, str(row["household_id"]), db) + hens, db)


def outfit(db, state: dict, content: dict) -> dict:
    """Once: every living villager nobody plays gets their kit, every household a sack of barley per member, and five gold per member moves from the
    Finanzamt into the household purses (coin only moves)."""
    from . import items
    if state.get("outfitted"):
        return {}
    people = db.execute("SELECT * FROM people WHERE status = 'alive' AND claimed_by IS NULL AND household_id IS NOT NULL").fetchall()
    for row in people:
        settle(db, state, row, content)
    members: dict = {}
    for row in people:
        members[row["household_id"]] = members.get(row["household_id"], 0) + 1
    for hid, n in members.items():
        pantry = items.load(PANTRY, str(hid), db)
        pantry.append({"name": "Barley, a sack", "kind": "trade", "qty": OUTFIT_BARLEY * n, "cost": "4 sp"})
        items.replace(PANTRY, str(hid), pantry, db)
    each, short = OUTFIT_CP, OUTFIT_CP * len(people) - int(state["money"].get("finanzamt", 0))
    if short > 0:   # the Finanzamt cannot pay it all: the bank mints the rest into the Finanzamt first (logged, like the delver's treasure)
        from . import town
        town.issue(state, short, "the households' start")
        town.move(state, "bank", "finanzamt", short, who="the households' start")
    reconcile(state, db)
    box = purses(state)
    for hid, n in members.items():
        box[str(hid)] = box.get(str(hid), 0) + each * n
    state["money"]["finanzamt"] = int(state["money"]["finanzamt"]) - each * len(people)
    state["money"]["households"] = sum(box.values())
    coin = each * len(people)
    state["outfitted"] = True
    return {"villagers": len(people), "households": len(members), "coin_cp": coin}


def pantry_hens(db) -> dict:
    """{household id: hens in its pantry}."""
    from . import clauses
    out: dict = {}
    for r in db.execute("SELECT holder_id, name, qty FROM items WHERE holder_type = ?", (PANTRY,)):
        if clauses.is_hen(r[1]):
            out[r[0]] = out.get(r[0], 0) + int(r[2] or 1)
    return out


def house_name(db, hid) -> str:
    """A household as the town speaks of it: by its eldest living member."""
    row = db.execute("SELECT name FROM people WHERE household_id = ? AND status = 'alive' ORDER BY born_day LIMIT 1", (int(hid),)).fetchone()
    return f"{row[0]}'s household" if row else f"household {hid}"
