"""Ageing in the village: the playable villagers grow old, marry, have children and die; each month a few things happen.

Everyone nobody plays takes part, the locked townsfolk (keepers, producers, the herb woman) too. A townsperson holds a seat, a trade that others depend on
(a shop, a trader). When the holder dies the seat passes to an adult who already has that trade and was not seated (a child who chose the parent's job at eighteen);
without one it stands empty, the shop shut and the trader idle, until a child picks that trade at eighteen. The townsfolk's trades are on the list of jobs a child draws from.
Everything is a monthly chance, drawn from a generator seeded by the month, so the same history repeats
on the same village.

* Death: a Weibull curve around the expected lifespan of the kind (human 60, dwarf 250, halfling 110; an elf never dies of age), plus a small accident chance.
  What the dead owed is split among the living (``debts.spread``), their coin goes to the widow or widower, else to the households.
* Romance: a single adult may find a single adult of the same kind, the other sex, near their age, and not kin. They wed at once and stay wed until one dies;
  only widows and widowers wed again. The herb woman's hand (``steward`` matches) makes a chosen pair far likelier.
* Children: a wed couple may have a child while the mother is of an age to; fewer where the village is full (``cap``) and for the long-lived kinds. Each ability is
  the father's, the mother's, their mean or a fresh 2d10, one time in four each, with a small chance of a point more or less. The child is of the parents' kind.
* At eighteen the child comes of age: a 0-level character is rolled with the inherited abilities, the trade is a parent's four times in five, else any
  occupation of the rulebook's table, and the purse is what the households can spare.
* The delver is the best of the adults in their prime; his gold follows his strength, and a trip can kill him.

Everything is off while ``places.LIVES`` is None.
"""

from __future__ import annotations

import json
import math
import random
import re
from datetime import datetime

from ttrpgtools import dcc
from . import households, places, registry, villagers

SCHEMA = """
CREATE TABLE IF NOT EXISTS life_events (day INTEGER NOT NULL, kind TEXT NOT NULL, who TEXT NOT NULL, other TEXT, detail TEXT);
CREATE INDEX IF NOT EXISTS life_events_day ON life_events (day);
CREATE TABLE IF NOT EXISTS lives_monthly (
  month INTEGER PRIMARY KEY, day INTEGER, population INTEGER, children INTEGER, couples INTEGER, births INTEGER, deaths INTEGER, weddings INTEGER, delver TEXT
);
"""
ELF_YEARS = 400   # what an elf's years count as where a lifespan is needed (the fertile years and the gap between a couple)
FEMALE = {"Brunhilde", "Edda", "Dagmar", "Lotte", "Marta", "Lady", "Sigrun", "Vessa", "Hedwig", "Gudrun", "Rosamund", "Brunhild", "Berta", "Irmgard", "Ursel", "Kunigunde", "Mechthild", "Stine", "Walpurga", "Wiebke", "Dietlind", "Cordula", "Senta", "Ysolde",
          "Jutta", "Verena", "Reinhild", "Ottilie", "Gundula", "Notburga", "Josefa", "Fenja", "Agnes", "Dorothea"}
GIVEN = {"f": ["Adelheid", "Amalia", "Anneke", "Balbina", "Christel", "Elsbeth", "Frieda", "Gerlinde", "Greta", "Hanne", "Hedda", "Hilde", "Imke", "Kathrein", "Lene",
               "Linde", "Margit", "Marthe", "Oda", "Rike", "Sieglinde", "Trude", "Uta", "Wilhelmine", "Zilla"],
         "m": ["Albrecht", "Arnulf", "Bastian", "Berthold", "Clas", "Dankwart", "Dietmar", "Elmar", "Friedel", "Gottfried", "Hagen", "Heinz", "Ingo", "Joost", "Karlmann",
               "Lambert", "Leopold", "Merten", "Otto", "Randolf", "Siegmund", "Tobias", "Udo", "Volker", "Wendel"]}
ABILITIES = dcc.ABILITIES


def config() -> dict | None:
    return places.LIVES


def _db():
    db = registry.connect()
    db.executescript(SCHEMA)
    return db


# ---------------------------------------------------------------- seats: the townsfolk's trades
def role_entries(content: dict) -> list[dict]:
    """The townsfolk's trades as entries of the table of jobs (weapon and goods from the table's entry of the same plain name, if there is one)."""
    table = {o["occupation"]: o for o in content["occupations"]}
    out = []
    for _, occupation in villagers.TOWNSFOLK:
        if occupation == "Herb woman":   # the elf who has watched the village for centuries is not a trade anyone is born into
            continue
        base = table.get(re.sub(r"\s*\(.*\)$", "", occupation), {})
        out.append({"roll": [0, 0], "occupation": occupation, "weapon": base.get("weapon", "Dagger"), "trade_goods": base.get("trade_goods", "Tools of the trade"),
                    "notes": "a trade of the village's own"})
    return out


def holder_name(state: dict, spec: dict) -> str:
    """Who is behind a trader tonight: the person who took the seat over, else the name in places.py."""
    return (state.get("seats") or {}).get(spec["id"], spec["name"])


def vacant_bot(state: dict, spec: dict) -> bool:
    """A trader whose seat stands empty does nothing until someone takes it."""
    who = holder_name(state, spec)
    return any(v["was"] == who for v in (state.get("vacant") or {}).values())


def abilities_of(row) -> dict | None:
    """A person's six scores: their character's, or for the townsfolk (who have none) the stand-in rolled for them."""
    sheet = _sheet(row)
    if sheet:
        return sheet["abilities"]
    return json.loads(row["genes"])["abilities"] if row["genes"] else None


def _race_for(row) -> str:
    spec = next((b for b in places.BOTS if b["name"] == row["name"] or b["name"].startswith(row["name"] + " ")), None)
    return spec.get("race", "human") if spec else race_of(row["occupation"])


# ---------------------------------------------------------------- kinds and ages
def race_of(occupation: str) -> str:
    first = (occupation or "").split(" ")[0]
    return {"Elven": "elf", "Dwarven": "dwarf", "Halfling": "halfling"}.get(first, "human")


def sex_of(name: str) -> str:
    return "f" if name.split(" ")[0] in FEMALE else "m"


def lifespan(race: str, cfg: dict | None = None) -> float | None:
    return (cfg or config())["lifespan"].get(race, 60)


def years(race: str, cfg: dict | None = None) -> float:
    """The span a kind's years are counted against: its lifespan, or an elf's long count."""
    return lifespan(race, cfg) or ELF_YEARS


def age_of(row, day: int) -> float:
    return (day - int(row["born_day"])) / 365


def death_chance(age: float, race: str, cfg: dict | None = None, mishap: bool = True) -> float:
    """The chance of dying in the month that starts at this age (years): the Weibull curve around the expected lifespan, then a small accident chance.
    An elf's expected life is so long that neither matters in the years of a campaign."""
    cfg = cfg or config()
    span = years(race, cfg)
    k = float(cfg["weibull"])
    scale = span / math.gamma(1 + 1 / k)
    aged = 1 - math.exp(-(((age + 1 / 12) / scale) ** k - (age / scale) ** k))
    child = 0.0 if age >= cfg["adult"] else cfg["child_death"][0] if age < 5 else cfg["child_death"][1]
    accident = cfg["accident"] * min(1.0, 60 / span) * (cfg.get("accident_kind") or {}).get(race, 1.0) if mishap else 0.0
    return 1 - (1 - aged) * (1 - accident) * (1 - child)


def fertile_until(race: str, cfg: dict | None = None) -> float:
    cfg = cfg or config()
    return cfg["adult"] + min(0.4 * years(race, cfg), 150)


def prime_until(race: str, cfg: dict | None = None) -> float:
    cfg = cfg or config()
    return cfg["adult"] + cfg["delver"]["prime"] * min(years(race, cfg), 120)


def score(sheet: dict) -> float:
    """What makes a delver: the mean of strength, agility, stamina and luck."""
    a = sheet["abilities"]
    return sum(int(a[x]) for x in ("strength", "agility", "stamina", "luck")) / 4


def _sheet(row) -> dict | None:
    return json.loads(row["sheet"]) if row["sheet"] else None


def _event(db, day: int, kind: str, who: str, other: str = "", detail: str = "") -> None:
    db.execute("INSERT INTO life_events (day, kind, who, other, detail) VALUES (?, ?, ?, ?, ?)", (day, kind, who, other, detail))


# ---------------------------------------------------------------- who can wed
def related(a, b) -> bool:
    """Parent and child, or siblings (a shared parent)."""
    return (a["id"] in (b["father_id"], b["mother_id"]) or b["id"] in (a["father_id"], a["mother_id"])
            or any(p is not None and p in (b["father_id"], b["mother_id"]) for p in (a["father_id"], a["mother_id"])))


def compatible(a, b, day: int, cfg: dict) -> bool:
    if a["id"] == b["id"] or a["sex"] == b["sex"] or a["race"] != b["race"] or related(a, b):
        return False
    gap = cfg["age_gap"] * years(a["race"], cfg) / 60
    return abs(age_of(a, day) - age_of(b, day)) <= gap


def _adults(db, day: int, cfg: dict) -> list:
    return [r for r in db.execute("SELECT * FROM people WHERE status = 'alive' AND claimed_by IS NULL AND born_day IS NOT NULL AND sex IS NOT NULL ORDER BY id")
            if age_of(r, day) >= cfg["adult"]]


def _single(r) -> bool:
    return r["spouse_id"] is None


def _wed(db, a, b, day: int, state: dict | None = None) -> None:
    db.execute("UPDATE people SET spouse_id = ? WHERE id = ?", (b["id"], a["id"]))
    db.execute("UPDATE people SET spouse_id = ? WHERE id = ?", (a["id"], b["id"]))
    if state is not None and state.get("household_mode"):   # one purse for the couple: hers joins his
        man, woman = (a, b) if a["sex"] == "m" else (b, a)
        households.merge(db, state, households.of(db, man["name"]), households.of(db, woman["name"]))
    _event(db, day, "wed", a["name"], b["name"])


# ---------------------------------------------------------------- the first month: who everybody is
def genesis(db, day: int, cfg: dict) -> int:
    """Give the villagers of the file a sex (by their name), a kind (by their trade), an age and, for half of them, a husband or wife.
    Done once; returns how many people were set up."""
    rows = db.execute("SELECT * FROM people WHERE claimed_by IS NULL AND status = 'alive' AND born_day IS NULL").fetchall()
    for r in rows:
        rng = random.Random(f"lives/genesis/{r['name']}")
        race = _race_for(r)
        age = rng.uniform(cfg["adult"], min(0.8 * years(race, cfg), 600))   # an elf may be six hundred; nobody is made older
        db.execute("UPDATE people SET sex = ?, race = ?, born_day = ? WHERE id = ?", (sex_of(r["name"]), race, day - round(age * 365), r["id"]))
        if r["locked"]:   # a townsperson holds the seat of their trade, and has no character: scores are rolled for the children to inherit
            stand_in = {a: sum(rng.randint(1, 6) for _ in range(3)) for a in ABILITIES}
            db.execute("UPDATE people SET seat = ?, genes = ? WHERE id = ?", (r["occupation"], json.dumps({"abilities": stand_in, "stand_in": True}), r["id"]))
    rng = random.Random("lives/genesis/weddings")
    adults = _adults(db, day, cfg)
    rng.shuffle(adults)
    wed = {r["id"] for r in adults if _single(r)}
    for a in adults:
        if a["id"] not in wed or rng.random() >= 0.55:
            continue
        for b in adults:
            if b["id"] in wed and compatible(a, b, day, cfg):
                _wed(db, a, b, day)
                wed -= {a["id"], b["id"]}
                break
    for mother in db.execute("SELECT * FROM people WHERE sex = 'f' AND spouse_id IS NOT NULL AND status = 'alive' AND claimed_by IS NULL").fetchall():
        father = db.execute("SELECT * FROM people WHERE id = ?", (mother["spouse_id"],)).fetchone()
        if not abilities_of(mother) or not abilities_of(father):
            continue
        room = min(age_of(mother, day) - cfg["adult"], fertile_until(mother["race"], cfg) - cfg["adult"], cfg["adult"] - 0.5)   # children she could have by now who are still children
        if room <= 0:
            continue
        for _ in range(rng.randint(0, 2 if years(mother["race"], cfg) <= 120 else 1)):
            name = _birth(db, father, mother, day - round(rng.uniform(0.1, room) * 365), cfg, rng)
            db.execute("DELETE FROM life_events WHERE who = ? AND kind = 'born'", (name,))   # they were here before the book began
    return len(rows)


# ---------------------------------------------------------------- the month
def _rare_boost(n: int, cfg: dict) -> float:
    """The factor on the chance of a child for a kind with few living: 1 at ``below`` and more, ``boost`` when none are left but the couple."""
    rare = cfg.get("rare_kind") or {}
    below = rare.get("below", 0)
    return 1.0 if n >= below or below <= 0 else 1.0 + (rare["boost"] - 1.0) * (below - n) / below


def _steer(db, cfg: dict) -> tuple[float, float]:
    """(the factor on everyone's chance of dying, the factor on the chance of a child) that nudge the village towards ``target`` living people: at 110 living,
    fifteen percent more deaths (``steer_deaths`` 1.5) and ten percent fewer births (``steer`` 1). Deaths alone were not enough: more people means more weddings, so a village a little
    above its balance kept growing and one a little below kept shrinking."""
    pop = db.execute("SELECT COUNT(*) FROM people WHERE status = 'alive'").fetchone()[0]
    x = pop / cfg["target"] - 1
    return max(0.3, min(3.0, 1 + cfg.get("steer_deaths", cfg["steer"]) * x)), max(0.0, min(2.0, 1 - cfg["steer"] * x))


def _child_name(db, father, sex: str, rng: random.Random) -> str:
    stem = father["name"].split(" ")[0]
    patronym = stem + ("sson" if sex == "m" else "sdotter")
    taken = {r[0] for r in db.execute("SELECT name FROM people")}
    for _ in range(100):
        name = f"{rng.choice(GIVEN[sex])} {patronym}"
        if name not in taken:
            return name
    for n in range(2, 1000):   # every given name taken: the second of the name is the Younger, then the Third, the Fourth (the owner 10-11; was "the Younger" and a random number)
        numbered = f"{name} the {ORDINALS[n - 2] if n - 2 < len(ORDINALS) else f'{n}th'}"
        if numbered not in taken:
            return numbered
    return name


ORDINALS = ["Younger", "Third", "Fourth", "Fifth", "Sixth", "Seventh", "Eighth", "Ninth", "Tenth", "Eleventh", "Twelfth", "Thirteenth", "Fourteenth",
            "Fifteenth", "Sixteenth", "Seventeenth", "Eighteenth", "Nineteenth", "Twentieth"]


def _genes(father, mother, cfg: dict, rng: random.Random) -> dict:
    """Each ability: the father's, the mother's, their mean or 2d10 (one in four each); then, rarely, a point either way."""
    fa, ma = abilities_of(father), abilities_of(mother)
    out = {}
    for a in ABILITIES:
        pick = rng.random()
        value = int(fa[a]) if pick < 0.25 else int(ma[a]) if pick < 0.5 else round((int(fa[a]) + int(ma[a])) / 2) if pick < 0.75 else rng.randint(1, 10) + rng.randint(1, 10)
        if rng.random() < cfg["mutation"]:
            value += rng.choice((-1, 1))
        out[a] = max(3, min(18, value))
    return out


def _birth(db, father, mother, day: int, cfg: dict, rng: random.Random) -> str:
    sex = rng.choice("mf")
    name = _child_name(db, father, sex, rng)
    genes = {"abilities": _genes(father, mother, cfg, rng), "jobs": [father["occupation"], mother["occupation"]]}
    db.execute("INSERT INTO people (name, occupation, status, notes, updated, locked, debt_cp, born_day, sex, race, mother_id, father_id, genes, household_id) "
               "VALUES (?, 'Child', 'alive', '', ?, 0, 0, ?, ?, ?, ?, ?, ?, ?)",   # a child belongs to the mother's household until eighteen
               (name, datetime.now().isoformat(timespec="seconds"), day, sex, father["race"], mother["id"], father["id"], json.dumps(genes), mother["household_id"]))
    _event(db, day, "born", name, f"{father['name']} and {mother['name']}")
    return name


def _holder(db, role: str):
    return db.execute("SELECT * FROM people WHERE seat = ? AND status = 'alive' AND claimed_by IS NULL", (role,)).fetchone()


def _install(db, state: dict, person, role: str, day: int, was: str) -> None:
    """A person takes a seat over: they are townsfolk now, the shops of the trade name them keeper, the trader's name is theirs."""
    db.execute("UPDATE people SET locked = 1, seat = ? WHERE id = ?", (role, person["id"]))
    alive = {r[0] for r in db.execute("SELECT name FROM people WHERE status = 'alive'")}
    same = lambda label: bool(was) and (label == was or (label.startswith(was + " ") and label not in alive))   # "X the Younger 21", alive, is not the dead "X"
    for shop_id, shop in state.get("shops", {}).items():
        keeper = shop.get("keeper") or ""
        if same(keeper):
            shop["keeper"] = person["name"]
            state.setdefault("keepers", {})[shop_id] = person["name"]   # remembered apart from the shop, which town._seed rewrites from places.py every load
    seats = state.setdefault("seats", {})
    for spec in places.BOTS:
        if same(holder_name(state, spec)):
            seats[spec["id"]] = person["name"]
    (state.get("vacant") or {}).pop(role, None)
    _event(db, day, "seat", person["name"], was, role)


def _heir(db, role: str, day: int):
    """The eldest unseated adult born in the village or come to it (genes; the written cast stays playable) who has the seat's trade, by its full name or its
    plain one ("Blacksmith" for "Blacksmith (The Blacksmith)")."""
    names = {role, re.sub(r"\s*\(.*\)$", "", role)}
    marks = ", ".join("?" * len(names))
    return next((r for r in db.execute(f"SELECT * FROM people WHERE occupation IN ({marks}) AND seat IS NULL AND status = 'alive' AND claimed_by IS NULL AND locked = 0 "
                                       "AND born_day IS NOT NULL AND genes IS NOT NULL ORDER BY born_day", tuple(names)) if age_of(r, day) >= config()["adult"]), None)


def _fill_vacant(db, state: dict, day: int) -> None:
    """An empty seat goes to the first adult who has its trade (a child who came of age into it, or one of the plain trade of the table of jobs)."""
    for role, was in list((state.get("vacant") or {}).items()):
        heir = _heir(db, role, day)
        if heir is not None:
            _install(db, state, heir, role, day, was.get("was", ""))


def _vacate(db, state: dict, row, day: int) -> None:
    """The holder of a seat has died: the eldest adult who has the trade and no seat takes over, else the seat stands empty."""
    role = row["seat"]
    db.execute("UPDATE people SET seat = NULL WHERE id = ?", (row["id"],))
    heir = _heir(db, role, day)
    if heir is not None:
        _install(db, state, heir, role, day, row["name"])
    else:
        state.setdefault("vacant", {})[role] = {"was": row["name"], "since": day}
        _event(db, day, "vacant", row["name"], "", role)


def _come_of_age(db, state: dict, day: int, cfg: dict, content: dict, rng: random.Random) -> int:
    done = 0
    roles = role_entries(content)
    table = content["occupations"] + roles
    full = {**content, "occupations": table}
    for r in db.execute("SELECT * FROM people WHERE status = 'alive' AND claimed_by IS NULL AND mother_id IS NOT NULL AND sheet IS NULL AND born_day IS NOT NULL").fetchall():
        if age_of(r, day) < cfg["adult"]:
            continue
        genes = json.loads(r["genes"])
        names = [o["occupation"] for o in table]
        taught = next((m for m in _mentoring(state) if m["child"] == r["name"]), None)
        if taught is not None:
            state["steward"]["mentoring"] = [m for m in _mentoring(state) if m["child"] != r["name"]]
        if taught is not None and taught["trade"] in names and rng.random() < cfg["mentor_chance"]:   # the herb woman's teaching took
            job = taught["trade"]
            _event(db, day, "taught", r["name"], "", job)
        elif rng.random() < cfg["parent_job"] and any(j in names for j in genes["jobs"]):
            job = rng.choice([j for j in genes["jobs"] if j in names])
        else:   # any job on the table; the trades of the village count as one slot each, eight for one whose seat stands empty
            weights = [o["roll"][1] - o["roll"][0] + 1 for o in content["occupations"]] + [cfg["vacant_weight"] if _holder(db, o["occupation"]) is None else 1 for o in roles]
            job = rng.choices(names, weights=weights)[0]
        sheet = registry.roll_villager(full, r["name"], job, genes["abilities"])
        if sheet is None:
            continue
        if state.get("household_mode"):   # at eighteen a household of their own, with nothing in the purse (the sheet's copper is only a player's starting purse)
            db.execute("UPDATE people SET household_id = ? WHERE id = ?", (households.new(state), r["id"]))
        else:
            spare = min(int(sheet["copper"]), int(state["money"].get("households", 0)))   # only what the households can afford
            state["money"]["households"] = int(state["money"].get("households", 0)) - spare
            sheet["copper"] = spare
        db.execute("UPDATE people SET occupation = ?, sheet = ?, updated = ? WHERE id = ?", (job, json.dumps(sheet), datetime.now().isoformat(timespec="seconds"), r["id"]))
        _event(db, day, "adult", r["name"], job)
        if job in [o["occupation"] for o in roles] and _holder(db, job) is None:   # the seat stood empty: here is the one who takes it
            row = db.execute("SELECT * FROM people WHERE id = ?", (r["id"],)).fetchone()
            _install(db, state, row, job, day, (state.get("vacant") or {}).get(job, {}).get("was", ""))
        done += 1
    return done


def _die(db, state: dict, row, day: int, cause: str) -> int:
    """Record a death: coin to the widow or widower, else to the households; the survivor is single again. Returns the debt to hand to the living."""
    row = db.execute("SELECT * FROM people WHERE id = ?", (row["id"],)).fetchone()   # as it stands now: a spouse who died earlier tonight left their coin here
    sheet = _sheet(row)
    coin = 0 if state.get("household_mode") else int(sheet["copper"]) if sheet else 0   # in household mode the purse is the household's and stays with it
    heir = db.execute("SELECT * FROM people WHERE id = ? AND status = 'alive'", (row["spouse_id"],)).fetchone() if row["spouse_id"] else None
    if coin and heir is not None and _sheet(heir):
        s = _sheet(heir)
        s["copper"] = int(s["copper"]) + coin
        db.execute("UPDATE people SET sheet = ? WHERE id = ?", (json.dumps(s), heir["id"]))
    elif coin:
        state["money"]["households"] = int(state["money"].get("households", 0)) + coin
    if sheet:
        sheet["copper"] = 0
    debt = int(row["debt_cp"] or 0)
    db.execute("UPDATE people SET status = 'dead', debt_cp = 0, sheet = ?, died_day = ?, cause = ?, spouse_id = NULL, updated = ? WHERE id = ?",
               (json.dumps(sheet) if sheet else None, day, cause, datetime.now().isoformat(timespec="seconds"), row["id"]))
    if row["spouse_id"]:
        db.execute("UPDATE people SET spouse_id = NULL WHERE id = ?", (row["spouse_id"],))
    if state.get("household_mode"):
        households.dissolve_if_empty(db, state, row["household_id"])
    if row["seat"]:
        _vacate(db, state, row, day)
    _event(db, day, "died", row["name"], "", f"{cause} at {age_of(row, day):.0f}" if row["born_day"] is not None else cause)
    return debt


def _matches(state: dict) -> list:
    return state.get("steward", {}).get("matches", [])


def _blocks(state: dict) -> list:
    return state.get("steward", {}).get("blocks", [])


def _mentoring(state: dict) -> list:
    return state.get("steward", {}).get("mentoring", [])


def _blocked(state: dict, a, b) -> bool:
    return any({m["a"], m["b"]} == {a["name"], b["name"]} for m in _blocks(state))


def _month(db, state: dict, day: int, month: int, cfg: dict, content: dict | None) -> dict:
    rng = random.Random(f"lives/{month}")
    out = {"births": 0, "deaths": 0, "weddings": 0}
    owed = []
    # children who turn eighteen
    if content:
        _come_of_age(db, state, day, cfg, content, rng)
    _fill_vacant(db, state, day)
    # deaths
    deaths_by, births_by = _steer(db, cfg)
    for r in db.execute("SELECT * FROM people WHERE status = 'alive' AND claimed_by IS NULL AND born_day IS NOT NULL ORDER BY id").fetchall():
        if rng.random() < death_chance(age_of(r, day), r["race"], cfg, r["name"] not in cfg.get("no_mishap", [])) * deaths_by:
            old = age_of(r, day) >= 0.7 * years(r["race"], cfg)
            cause = "old age" if old else "a childhood illness" if age_of(r, day) < cfg["adult"] else "a mishap"
            owed.append((r["id"], _die(db, state, r, day, cause)))
            out["deaths"] += 1
    # the herb woman's matches, then chance meetings
    adults = {r["id"]: r for r in _adults(db, day, cfg)}
    keep = []
    for m in _matches(state):
        a = next((r for r in adults.values() if r["name"] == m["a"]), None)
        b = next((r for r in adults.values() if r["name"] == m["b"]), None)
        if not a or not b or not _single(a) or not _single(b) or not compatible(a, b, day, cfg):
            continue
        if rng.random() < cfg["match_boost"]:
            _wed(db, a, b, day, state)
            adults[a["id"]], adults[b["id"]] = dict(a, spouse_id=b["id"]), dict(b, spouse_id=a["id"])
            out["weddings"] += 1
            continue
        m["left"] = int(m.get("left", cfg["match_months"])) - 1
        if m["left"] > 0:
            keep.append(m)
    if _matches(state) or "steward" in state:
        state.setdefault("steward", {})["matches"] = keep
    if _blocks(state):   # a block lapses when either of the two is dead
        state["steward"]["blocks"] = [m for m in _blocks(state) if db.execute("SELECT COUNT(*) FROM people WHERE name IN (?, ?) AND status = 'alive'", (m["a"], m["b"])).fetchone()[0] == 2]
    singles = [r for r in adults.values() if _single(r)]
    rng.shuffle(singles)
    for a in singles:
        a = db.execute("SELECT * FROM people WHERE id = ?", (a["id"],)).fetchone()
        if not _single(a) or rng.random() >= cfg["romance"]:
            continue
        pool = [b for b in singles if b["id"] != a["id"] and compatible(a, b, day, cfg) and db.execute("SELECT spouse_id FROM people WHERE id = ?", (b["id"],)).fetchone()[0] is None]
        if pool:
            b = rng.choice(pool)
            if _blocked(state, a, b) and rng.random() >= cfg["block_factor"]:   # the herb woman's hand against it: a hundredth of the chance
                continue
            _wed(db, a, b, day, state)
            out["weddings"] += 1
    # children
    kinds = dict(db.execute("SELECT race, COUNT(*) FROM people WHERE status = 'alive' AND claimed_by IS NULL GROUP BY race").fetchall())
    for mother in [r for r in db.execute("SELECT * FROM people WHERE status = 'alive' AND sex = 'f' AND spouse_id IS NOT NULL AND claimed_by IS NULL")]:
        father = db.execute("SELECT * FROM people WHERE id = ? AND status = 'alive'", (mother["spouse_id"],)).fetchone()
        if father is None or not abilities_of(father) or not abilities_of(mother) or age_of(mother, day) > fertile_until(mother["race"], cfg):
            continue
        if db.execute("SELECT COUNT(*) FROM people WHERE mother_id = ?", (mother["id"],)).fetchone()[0] >= cfg["children_max"]:
            continue
        chance = cfg["birth"] * min(1.0, 60 / years(mother["race"], cfg)) * births_by * _rare_boost(kinds.get(mother["race"], 0), cfg)   # a long life means as few children, in proportion: an elf's chance is a thirtieth of a human's
        if rng.random() < chance:
            _birth(db, father, mother, day, cfg, rng)
            out["births"] += 1
    return out, owed


def _forget_the_old_dead(db, keep: int = registry.GRAVEYARD_SHOWN) -> int:
    """Only the ``keep`` villagers who died last are remembered (the graveyard shows no more); the rows of the older dead go. A played villager's row stays
    (its character file is the record), and so does the written cast's: ``registry.connect`` re-adds a name of the files that is missing, as a new living
    person (10-11: 70 of them rose again, with seats and coin). Children keep the ids of parents who are gone: a sibling is still known by the shared parent."""
    cast = sorted({n for n, _ in villagers.TOWNSFOLK + villagers.VILLAGERS})
    marks = ",".join("?" * len(cast))
    return db.execute(f"DELETE FROM people WHERE status = 'dead' AND claimed_by IS NULL AND name NOT IN ({marks}) AND id NOT IN "
                      "(SELECT id FROM people WHERE status = 'dead' AND claimed_by IS NULL ORDER BY died_day IS NULL, died_day DESC, id DESC LIMIT ?)",
                      (*cast, keep)).rowcount


def monthly(state: dict, day: int) -> int:
    """Run the months that have begun since the last call (usually none or one). Returns how many months were run."""
    cfg = config()
    if not cfg:
        return 0
    month = (day * 12) // 365
    book = state.setdefault("lives", {"month": month - 1})
    content = dcc.load_content() if dcc.content_available() else None
    ran = 0
    while book["month"] < month and ran < 3:
        book["month"] += 1
        db = _db()
        try:
            with db:
                if db.execute("SELECT COUNT(*) FROM people WHERE claimed_by IS NULL AND born_day IS NULL AND status = 'alive'").fetchone()[0]:
                    genesis(db, day, cfg)
                out, owed = _month(db, state, day, book["month"], cfg, content)
                alive = db.execute("SELECT COUNT(*) FROM people WHERE status = 'alive'").fetchone()[0]
                kids = db.execute("SELECT COUNT(*) FROM people WHERE status = 'alive' AND mother_id IS NOT NULL AND sheet IS NULL").fetchone()[0]
                couples = db.execute("SELECT COUNT(*) FROM people WHERE status = 'alive' AND sex = 'f' AND spouse_id IS NOT NULL").fetchone()[0]
                db.execute("INSERT OR REPLACE INTO lives_monthly (month, day, population, children, couples, births, deaths, weddings, delver) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                           (book["month"], day, alive, kids, couples, out["births"], out["deaths"], out["weddings"], state.get("delver", {}).get("who", "")))
                _forget_the_old_dead(db)
        finally:
            db.close()
        from . import debts
        for person_id, debt in owed:
            if debt:
                debts.spread(debt, skip_villager=person_id)
        ran += 1
    return ran


# ---------------------------------------------------------------- the delver
def delver(state: dict, day: int, rng: random.Random) -> dict | None:
    """The delver of tonight's trip: ``{"name", "factor"}`` (gold follows strength: the mean of his best four scores against the average 10.5, from half to
    one and a half), after he is chosen if there is none, or when the last grew too old. A trip can kill him; then ``died`` is set. None when ageing is off
    or nobody is left to go."""
    cfg = config()
    if not cfg:
        return None
    book = state.setdefault("delver", {})
    db = _db()
    try:
        with db:
            current = db.execute("SELECT * FROM people WHERE name = ? AND status = 'alive' AND claimed_by IS NULL", (book.get("who", ""),)).fetchone() if book.get("who") else None
            if current is not None and age_of(current, day) > prime_until(current["race"], cfg):
                _event(db, day, "retired", current["name"], "", "from the dungeon")
                current = None
            if current is None:
                candidates = [r for r in _adults(db, day, cfg) if _sheet(r) and not r["locked"] and age_of(r, day) <= prime_until(r["race"], cfg)]
                if not candidates:
                    book.pop("who", None)
                    return None
                current = max(candidates, key=lambda r: (score(_sheet(r)), -r["id"]))
                book["who"] = current["name"]
                _event(db, day, "delver", current["name"], "", f"score {score(_sheet(current)):.1f}")
            strength = score(_sheet(current))
            out = {"name": current["name"], "factor": max(0.5, min(1.6, strength / 10.5)), "died": False}
            if rng.random() < cfg["delver"]["trip_death"] * (10.5 / max(3.0, strength)) ** 2:
                owed = _die(db, state, current, day, "the dungeon")
                out["died"] = True
                book.pop("who", None)
            else:
                owed = 0
    finally:
        db.close()
    if owed:
        from . import debts
        debts.spread(owed, skip_villager=current["id"])
    return out


# ---------------------------------------------------------------- what the herb woman sees
def _line(r, day: int) -> str:
    s = _sheet(r)
    a = abilities_of(r) or {}
    stats = " ".join(f"{k[:3].upper()}{a[k]}" for k in ABILITIES) if a else "stats unknown"
    score_text = f"; delver score {score({'abilities': a}):.1f}" if a else ""
    job = r["occupation"] if r["occupation"] != "Child" else "child"
    return f"{r['name']} ({r['race']}, {'woman' if r['sex'] == 'f' else 'man'}, {age_of(r, day):.0f}, {job}; {stats}{score_text})" if a else r["name"]


def _name(by_id: dict, person_id) -> str:
    return by_id[person_id]["name"] if person_id in by_id else "a parent who has died"


def _alive(db, cfg: dict, day: int):
    alive = db.execute("SELECT * FROM people WHERE status = 'alive' AND claimed_by IS NULL AND born_day IS NOT NULL ORDER BY id").fetchall()
    return alive, [r for r in alive if age_of(r, day) >= cfg["adult"]], {r["id"]: r for r in alive}


def _empty_since(since, day: int) -> str:
    return f"EMPTY since day {since} ({(day - int(since)) / 365:.1f} years)" if since is not None else "EMPTY"


def summary(state: dict, day: int) -> dict:
    """The village's people in outline, for the herb woman's report: counts, the trades and who holds them, the delver, the latest births, weddings and deaths, her
    open matches. Names and scores she asks for with ``look_up``; a hundred and more people would only bury the rest of her report."""
    cfg = config()
    if not cfg:
        return {}
    db = _db()
    try:
        alive, adults, by_id = _alive(db, cfg, day)
        singles = [r for r in adults if _single(r)]
        children = [r for r in alive if age_of(r, day) < cfg["adult"]]
        events = [f"day {e['day']}: {e['kind']} {e['who']}{(' / ' + e['other']) if e['other'] else ''}{(' (' + e['detail'] + ')') if e['detail'] else ''}"
                  for e in db.execute("SELECT * FROM life_events ORDER BY rowid DESC LIMIT 12")][::-1]
        deaths = db.execute("SELECT COUNT(*) FROM life_events WHERE kind = 'died' AND day > ?", (day - 3 * 365,)).fetchone()[0]
        births = db.execute("SELECT COUNT(*) FROM life_events WHERE kind = 'born' AND day > ?", (day - 3 * 365,)).fetchone()[0]
        seats = []
        for _, role in villagers.TOWNSFOLK:
            if role == "Herb woman":
                continue
            holder = next((r for r in alive if r["seat"] == role), None)
            heirs = [r for r in adults if r["occupation"] == role and not r["seat"]]
            seats.append(f"{role}: " + (f"{holder['name']} ({holder['race']}, {age_of(holder, day):.0f})" if holder else _empty_since((state.get('vacant') or {}).get(role, {}).get('since'), day))
                         + (f"; has the trade, no seat: {', '.join(h['name'] for h in heirs)}" if heirs else "")
                         + (f"; children who may take it: {sum(1 for c in children if holder and holder['id'] in (c['father_id'], c['mother_id']))}" if holder else ""))
        counts = {}
        for r in singles:
            counts[f"{r['race']} {'women' if r['sex'] == 'f' else 'men'}"] = counts.get(f"{r['race']} {'women' if r['sex'] == 'f' else 'men'}", 0) + 1
        bands = {"under 6": 0, "6 to 11": 0, "12 to 17": 0}
        for c in children:
            bands["under 6" if age_of(c, day) < 6 else "6 to 11" if age_of(c, day) < 12 else "12 to 17"] += 1
        who = state.get("delver", {}).get("who")
        delver = next((r for r in alive if r["name"] == who), None)
    finally:
        db.close()
    return {"population": {"living": len(alive), "adults": len(adults), "children_by_age": bands, "wed_couples": sum(1 for r in adults if r["sex"] == "f" and r["spouse_id"] in by_id),
                           "single_adults_by_kind": counts, "target": cfg["target"], "births_last_3_years": births, "deaths_last_3_years": deaths},
            "delver_now": (_line(delver, day) if delver else "(none)"), "townsfolk_seats": seats, "latest_events": events,
            "my_matches": [[m["a"], m["b"], f"{int(m.get('left', cfg['match_months']))} months left"] for m in _matches(state)],
            "my_blocks": [[m["a"], m["b"]] for m in _blocks(state)],
            "my_mentoring": [[m["child"], m["trade"]] for m in _mentoring(state)],
            "look_up": "for names, ages and scores ask with \"look_up\" (see the instructions); nothing about individual villagers is in this report"}


def look_up(state: dict, day: int, queries) -> list[dict]:
    """The herb woman's questions about the people, answered from the register. Each query is one of {"person": name}, {"singles": {"race": .., "sex": "f"|"m"}},
    {"children": true}, {"couples": true}, {"best_for_delver": n}, {"trade": text}; at most three queries and thirty lines each."""
    cfg = config()
    if not cfg or not isinstance(queries, list):
        return []
    db = _db()
    out = []
    try:
        alive, adults, by_id = _alive(db, cfg, day)
        for q in queries[:3]:
            if not isinstance(q, dict):
                continue
            lines: list[str] = []
            if "person" in q:
                r = next((x for x in alive if x["name"].lower() == str(q["person"]).lower()), None)
                if r:
                    kids = [c for c in alive if r["id"] in (c["father_id"], c["mother_id"])]
                    lines = [_line(r, day), f"spouse: {by_id[r['spouse_id']]['name'] if r['spouse_id'] in by_id else 'none'}; parents: {_name(by_id, r['father_id'])}, {_name(by_id, r['mother_id'])}"
                             + (f"; holds the seat of {r['seat']}" if r["seat"] else ""), "children: " + (", ".join(f"{c['name']} ({age_of(c, day):.0f})" for c in kids) or "none")]
                else:
                    lines = ["no such living villager"]
            elif "singles" in q:
                f = q["singles"] if isinstance(q["singles"], dict) else {}
                pool = [r for r in adults if _single(r) and (not f.get("race") or r["race"] == f["race"]) and (not f.get("sex") or r["sex"] == f["sex"])]
                lines = [_line(r, day) for r in sorted(pool, key=lambda r: -score({"abilities": abilities_of(r)}) if abilities_of(r) else 0)[:30]]
            elif "children" in q:
                lines = [f"{_line(r, day)}; comes of age in {cfg['adult'] - age_of(r, day):.0f} years; child of {_name(by_id, r['father_id'])} and {_name(by_id, r['mother_id'])}"
                         for r in sorted((r for r in alive if age_of(r, day) < cfg["adult"]), key=lambda r: r["born_day"])[:30]]
            elif "couples" in q:
                for r in adults:
                    if r["sex"] == "f" and r["spouse_id"] in by_id:
                        lines.append(f"{r['name']} and {by_id[r['spouse_id']]['name']} ({r['race']}, she {age_of(r, day):.0f}), {sum(1 for c in alive if c['mother_id'] == r['id'])} children living")
                lines = lines[:30]
            elif "best_for_delver" in q:
                try:
                    n = max(1, min(30, int(q["best_for_delver"])))
                except (TypeError, ValueError):
                    n = 8
                fit = (r for r in alive if age_of(r, day) >= cfg["adult"] - 6 and age_of(r, day) <= prime_until(r["race"], cfg) and abilities_of(r) and not r["locked"])   # children close to eighteen count
                lines = [_line(r, day) for r in sorted(fit, key=lambda r: -score({"abilities": abilities_of(r)}))[:n]]
            elif "trade" in q:
                text = str(q["trade"]).lower()
                lines = [_line(r, day) + (f"; seat of {r['seat']}" if r["seat"] else "") for r in alive if text in r["occupation"].lower()][:30]
            out.append({"asked": q, "answer": lines or ["nothing"]})
    finally:
        db.close()
    return out


NEWCOMER_NAMES = ["Brandt", "Falkner", "Weber", "Kessler", "Imhof", "Lindner", "Ostwald", "Rainer", "Sattler", "Tanner", "Vogler", "Wendt", "Zimmer", "Amsel",
                  "Bauer", "Dreher", "Eckart", "Fink", "Gerber", "Holler", "Jaeger", "Kranz", "Moser", "Pfister", "Ritter", "Seidel", "Thal", "Unger"]


def spawn(state: dict, day: int, occupation: str, content: dict, rng: random.Random, sex: str | None = None) -> str | None:
    """A newcomer walks into the village: an adult (18 to 35) of the trade, of the kind its name says, single, with a 0-level character rolled for them and
    the purse the households can spare. For a hand-made repopulation between runs (the owner 10-10: the trades that had died out). Returns the name, or None."""
    cfg = config()
    full = {**content, "occupations": content["occupations"] + role_entries(content)}
    race = race_of(occupation)
    sex = sex or rng.choice("mf")
    db = _db()
    try:
        taken = {r[0] for r in db.execute("SELECT name FROM people")}
        name = next((n for n in (f"{rng.choice(GIVEN[sex])} {rng.choice(NEWCOMER_NAMES)}" for _ in range(200)) if n not in taken), None)
        sheet = registry.roll_villager(full, name, occupation) if name else None
        if sheet is None:
            return None
        hid = None
        if state.get("household_mode"):   # a household of one, endowed from the others: nobody brings coin from outside
            hid = households.endow(state, db, int(sheet["copper"]))
        else:
            spare = min(int(sheet["copper"]), int(state["money"].get("households", 0)))   # nobody brings coin from outside: what the households can spare
            state["money"]["households"] = int(state["money"].get("households", 0)) - spare
            sheet["copper"] = spare
        age = rng.uniform(cfg["adult"], 35)
        with db:
            db.execute("INSERT INTO people (name, occupation, status, notes, updated, locked, sheet, debt_cp, born_day, sex, race, genes, household_id) "
                       "VALUES (?, ?, 'alive', 'came to the village', ?, 0, ?, 0, ?, ?, ?, ?, ?)",
                       (name, occupation, datetime.now().isoformat(timespec="seconds"), json.dumps(sheet), day - round(age * 365), sex, race,
                        json.dumps({"abilities": sheet["abilities"], "jobs": [occupation, occupation], "newcomer": True}), hid))
            _event(db, day, "arrived", name, "", occupation)
        return name
    finally:
        db.close()


def set_mentoring(state: dict, day: int, pairs, content: dict | None = None) -> list[dict]:
    """The children the herb woman teaches a trade, replacing her old list (at most ``mentor_max``): {"child": name, "trade": job}. The child must be living and
    under age, the trade on the table of jobs or one of the village's own. At eighteen the child takes that trade with ``mentor_chance``; nobody is told."""
    cfg = config()
    if not cfg or not isinstance(pairs, list):
        return _mentoring(state)
    content = content or (dcc.load_content() if dcc.content_available() else None)
    jobs = {o["occupation"] for o in (content["occupations"] + role_entries(content))} if content else set()
    db = _db()
    try:
        children = {r["name"] for r in db.execute("SELECT * FROM people WHERE status = 'alive' AND claimed_by IS NULL AND mother_id IS NOT NULL AND sheet IS NULL AND born_day IS NOT NULL")
                    if age_of(r, day) < cfg["adult"]}
    finally:
        db.close()
    out = []
    for p in pairs[:cfg["mentor_max"] * 2]:
        try:
            child, trade = p["child"], p["trade"]
        except (KeyError, TypeError):
            continue
        plain = [j for j in jobs if re.sub(r"\s*\(.*\)$", "", j) == trade]
        if trade not in jobs and len(plain) == 1:   # a seat by its plain name ("Outfitter and innkeeper"): she was dropped for writing it so until 10-10
            trade = plain[0]
        if child in children and trade in jobs and len(out) < cfg["mentor_max"] and child not in [m["child"] for m in out]:
            out.append({"child": child, "trade": trade})
    state.setdefault("steward", {})["mentoring"] = out
    return out


def set_blocks(state: dict, day: int, pairs) -> list[dict]:
    """The pairs the herb woman stands in the way of, replacing her old list (at most ``block_max``; any two living people, wed or not). A blocked pair meets
    with a hundredth of the usual chance of wedding, for as long as the block stands (it lapses when one of them dies). A match on the same pair is dropped."""
    cfg = config()
    if not cfg or not isinstance(pairs, list):
        return _blocks(state)
    db = _db()
    try:
        alive = {r["name"] for r in db.execute("SELECT name FROM people WHERE status = 'alive' AND claimed_by IS NULL AND born_day IS NOT NULL")}
    finally:
        db.close()
    out = []
    for p in pairs[:cfg["block_max"] * 2]:
        try:
            a, b = p["a"], p["b"]
        except (KeyError, TypeError):
            continue
        if a in alive and b in alive and a != b and len(out) < cfg["block_max"] and {a, b} not in [{m["a"], m["b"]} for m in out]:
            out.append({"a": a, "b": b})
    state.setdefault("steward", {})["blocks"] = out
    if out:
        state["steward"]["matches"] = [m for m in _matches(state) if not any({m["a"], m["b"]} == {x["a"], x["b"]} for x in out)]
    return out


def set_matches(state: dict, day: int, pairs) -> list[dict]:
    """The pairs the herb woman wants to bring together, replacing her old list (at most ``match_max``; a pair already on it keeps its months). Only pairs who could wed
    tonight (two single adults of the same kind, the other sex, near in age, not kin) are taken."""
    cfg = config()
    if not cfg or not isinstance(pairs, list):
        return _matches(state)
    db = _db()
    try:
        adults = {r["name"]: r for r in _adults(db, day, cfg)}
    finally:
        db.close()
    old = {(m["a"], m["b"]): m for m in _matches(state)}
    out = []
    for p in pairs[:cfg["match_max"] * 2]:
        try:
            a, b = adults.get(p["a"]), adults.get(p["b"])
        except (KeyError, TypeError, AttributeError):
            continue
        if a and b and _single(a) and _single(b) and compatible(a, b, day, cfg) and len(out) < cfg["match_max"] and (p["a"], p["b"]) not in [(m["a"], m["b"]) for m in out]:
            out.append(old.get((p["a"], p["b"])) or {"a": p["a"], "b": p["b"], "left": cfg["match_months"]})
    state.setdefault("steward", {})["matches"] = out
    return out
