"""The village's history: every night one line per good (its price, how much is on the shelves, how much is usual) and the caravan's ranking of what
the village needs, kept in the campaign database so the admin's chart (``/TTRPG/dcc/history``) can draw prices and amounts from the first night to now.

``record`` is called by the nightly update (``daily.run_day``, live nights only). ``series`` is what the chart asks for.
"""

from __future__ import annotations

import json

from . import registry

SCHEMA = """
CREATE TABLE IF NOT EXISTS market_history (
  day INTEGER NOT NULL, name TEXT NOT NULL, kind TEXT, price REAL, rel REAL, stock INTEGER, usual INTEGER,
  PRIMARY KEY (day, name)
);
CREATE INDEX IF NOT EXISTS market_history_name ON market_history (name, day);
CREATE TABLE IF NOT EXISTS caravan_history (
  day INTEGER NOT NULL, event TEXT NOT NULL, detail TEXT, PRIMARY KEY (day, event)
);
CREATE TABLE IF NOT EXISTS need_history (
  day INTEGER PRIMARY KEY, top TEXT, value_cp INTEGER, ranking TEXT, asked TEXT
);
"""


def _db():
    db = registry.connect()
    db.executescript(SCHEMA)
    return db


def snapshot(state: dict, day: int) -> tuple[list[tuple], tuple]:
    """(the rows of tonight's market, tonight's need row). One row per kind of thing on a shelf: the mean price of one piece over the shelves that
    list it (what a customer pays, free being 0 and a shop that pays you being negative), the pieces on all shelves, the usual pieces."""
    from . import daily, town
    rows = []
    names: dict[str, list] = {}
    for shop in state["shops"].values():
        if "caravan" in shop.get("kinds", []) or shop.get("away"):
            continue
        for line in shop["stock"]:
            if line["kind"] != "service" and not line.get("gone"):
                names.setdefault(line["name"], []).append((shop, line))
    for name, lines in names.items():
        prices = [town.price_cp(shop, line, day) / max(1, int(line.get("units", 1))) for shop, line in lines]
        bases = [line["base_cp"] / max(1, int(line.get("units", 1))) for _, line in lines]
        stock = [int(line["qty"]) * int(line.get("units", 1)) for _, line in lines if line["qty"] is not None]
        usual = [int(line.get("target") or 0) * int(line.get("units", 1)) for _, line in lines]
        mean_price = sum(prices) / len(prices)
        mean_base = sum(bases) / len(bases)
        rows.append((day, name, lines[0][1]["kind"], round(mean_price, 2), round(mean_price / mean_base, 4) if mean_base else None,
                     sum(stock) if stock else None, sum(usual)))
    needs = daily.village_needs(state)[:5]
    asked = (state.get("caravan") or {})
    asked_now = [w["label"] for w in asked.get("wants", [])] if asked.get("asked_day") == day else []
    need = (day, needs[0]["label"] if needs else "", int(needs[0]["value_cp"]) if needs else 0,
            json.dumps([[n["label"], int(n["value_cp"]), n["kind"]] for n in needs]), json.dumps(asked_now))
    return rows, need


def caravan_events(state: dict, day: int) -> list[tuple]:
    """The caravan's doings of tonight: sent for (asked), came (arrived: what it brought and what it was paid), left (what it took away)."""
    c, out = state.get("caravan") or {}, []
    if c.get("asked_day") == day:
        out.append((day, "asked", json.dumps([w["label"] for w in c.get("wants", [])])))
    if c.get("last_day") == day:
        out.append((day, "arrived", json.dumps({"brought": c.get("brought", []), "paid_cp": int(c.get("paid_cp", 0))})))
    if c.get("left_day") == day:
        out.append((day, "left", json.dumps({"took": c.get("took", [])})))
    return out


def record(state: dict, day: int) -> int:
    """Write tonight's lines (replacing any already written for this day). Returns how many goods were written."""
    rows, need = snapshot(state, day)
    db = _db()
    try:
        with db:
            db.execute("DELETE FROM market_history WHERE day = ?", (day,))
            db.executemany("INSERT INTO market_history (day, name, kind, price, rel, stock, usual) VALUES (?, ?, ?, ?, ?, ?, ?)", rows)
            db.execute("INSERT OR REPLACE INTO need_history (day, top, value_cp, ranking, asked) VALUES (?, ?, ?, ?, ?)", need)
            db.executemany("INSERT OR REPLACE INTO caravan_history (day, event, detail) VALUES (?, ?, ?)", caravan_events(state, day))
    finally:
        db.close()
    return len(rows)


def span() -> tuple[int, int]:
    db = _db()
    try:
        row = db.execute("SELECT MIN(day), MAX(day) FROM need_history").fetchone()   # written every night, shelves or none
        return (row[0] or 0, row[1] or 0)
    finally:
        db.close()


def series(since: int | None = None, until: int | None = None, points: int = 700) -> dict:
    """What the chart draws: ``days`` (the first day of each stretch), per good ``price`` / ``stock`` / ``usual`` lists with the stretch's mean,
    the caravan's top need for each stretch, and the price index from the books."""
    first, last = span()
    since = first if since is None else max(first, int(since))
    until = last if until is None else min(last, int(until))
    if until < since or not last:
        return {"days": [], "series": {}, "needs": [], "caravan": [], "caravan_from": None, "span": [first, last], "step": 1}
    step = max(1, -(-(until - since + 1) // max(50, int(points))))
    db = _db()
    try:
        days = list(range(since, until + 1, step))
        slot = {d: n for n, d in enumerate(days)}
        out: dict[str, dict] = {}
        for name, kind, bucket, price, rel, stock, usual in db.execute(
                "SELECT name, MIN(kind), ((day - ?) / ?) AS b, AVG(price), AVG(rel), AVG(stock), AVG(usual) FROM market_history WHERE day BETWEEN ? AND ? "
                "GROUP BY name, b ORDER BY name, b", (since, step, since, until)):
            entry = out.setdefault(name, {"kind": kind, "price": [None] * len(days), "rel": [None] * len(days), "stock": [None] * len(days), "usual": [None] * len(days)})
            entry["price"][bucket] = round(price, 2)
            entry["rel"][bucket] = None if rel is None else round(rel, 3)
            entry["stock"][bucket] = None if stock is None else round(stock, 1)
            entry["usual"][bucket] = None if usual is None else round(usual, 1)
        needs = []
        for day, top, value, ranking, asked in db.execute("SELECT day, top, value_cp, ranking, asked FROM need_history WHERE day BETWEEN ? AND ? ORDER BY day", (since, until)):
            if needs and needs[-1]["label"] == top:
                needs[-1]["to"] = day
                needs[-1]["peak"] = max(needs[-1]["peak"], value)
            else:
                needs.append({"from": day, "to": day, "label": top, "peak": value, "ranking": json.loads(ranking or "[]")[:5], "asked": json.loads(asked or "[]")})
            if json.loads(asked or "[]"):
                needs[-1]["asked"] = json.loads(asked)
        visits: list[dict] = []
        pending: list = []
        for day, event, detail in db.execute("SELECT day, event, detail FROM caravan_history WHERE day BETWEEN ? AND ? ORDER BY day", (since - 10, until)):
            d = json.loads(detail or "null")
            if event == "asked":
                pending = d
            elif event == "arrived":
                visits.append({"day": day, "asked": pending, "brought": d["brought"], "paid_cp": d["paid_cp"], "took": []})
                pending = []
            elif event == "left" and visits:
                visits[-1]["took"] = d["took"]
        visits = [v for v in visits if since <= v["day"] <= until]
        first_event = db.execute("SELECT MIN(day) FROM caravan_history").fetchone()[0]
        try:
            index = [[r[0], r[1]] for r in db.execute("SELECT day, price_index FROM economy WHERE day BETWEEN ? AND ? ORDER BY day", (since, until)) if r[1] is not None]
        except Exception:
            index = []
    finally:
        db.close()
    return {"days": days, "series": out, "needs": needs, "caravan": visits, "caravan_from": first_event, "index": index, "span": [first, last], "step": step}
