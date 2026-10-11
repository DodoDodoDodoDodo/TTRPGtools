"""Start a new book of the village: year 0 (the owner 10-11).

    docker exec -w /app -e PYTHONPATH=/app sheet python scripts/dcc/new_year_zero.py <tag>

Stop the run first and take a backup. The old town file is moved to data/westmarch/town-<tag>.json; the history (economy, markets, lives, events) and every
villager nobody plays are wiped; the players' villagers, their characters and their packs stay. Then the cast of ``villagers.py`` is added, genesis gives it ages,
couples and children, every household gets a purse (``households.migrate``), the first night runs, and Hedwig and the town note are seeded by hand below.
"""

from __future__ import annotations

import shutil
import sqlite3
import sys

from ttrpgtools.dcc.westmarch import daily, households, items, lives, registry, steward, town

WIPED = ["economy", "market_history", "need_history", "caravan_history", "life_events", "lives_monthly"]

# The REQUESTS part of the town note at day 0: what the traders would plainly want. (TALK starts from places.FLAVOUR_SEED.)
REQUESTS = [
    ("Detlef of the Ford", "The hens need barley before the frost. Who has a spare sack?"),
    ("Hartmut Bachmeier", "Old iron to sell, and nobody asks. I dig, I wait."),
    ("Xaver Haberkorn", "Barley at a fair price, and there will be ale at a fair price."),
    ("Marta Vogt", "Eggs and rations for the shelf, any day. The shelf pays what the shelf allows."),
    ("Ivo Zwiebel", "Oak bark, if anyone passes a grove."),
]

# Hedwig's notebook at day 0: what she wrote herself in the old book (her habits, the barley rule she found, the crossbow trial) and what the people who keep
# the world know and she has not seen. The long teachings are in data/steward/teachings.md. Eight pins at most.
NOTES = [
    (True, "This notebook is my only memory and it is small. At every look: delete what is settled, merge what repeats, keep only what I will need in years. An alarm that rang is not worth a note unless it taught me a rule, and then the rule is the note, not the alarm."),
    (True, "The alarms are mine to define (flags). A tenfold price swing is the village breathing, not a disaster. A flag that rings falsely twice gets a higher limit or a longer duration, and that is all I write about it. The real dangers are few: the flock, a producer without capital, a staple gone, no coin left to buy with."),
    (True, "Quiet is the goal. After a quiet look I say a year or two. I look often only to watch something I started, and then I write down what I am testing, what I expect, and the night it ends, so that I can go quiet again."),
    (True, "One slow experiment at a time: change one order, write what I expect, judge it a year later in one line. Several changes at once teach me nothing. My actions stay hidden from any dragons, adventurers or spies."),
    (True, "Ensuring the DELVER is someone competent matters. I steward the town by matchmaking to keep several families with good stats that can have children who become the DELVER. Do not mentor the best of those children away."),
    (True, "Swings may have causes I cannot see. When a good swings the same way twice, I write what else was going on beside it. Unconfirmed coincidences are deleted after some years; confirmed ones become theory."),
    (True, "Barley rule (confirmed over many harvests): Pale Moon waxing, first quarter or full at sowing gives 4.1-5.2 sacks; waning or last quarter gives 2.8-3.7. Theory."),
    (True, "Crossbow trial (confirmed): when the smith has an empty till and metal, I buy his crossbows (below 0.45, keep 120 gp, up to 3) and sell them back when his metal is under 3 kg; his till rose from 22 to 33 gp. Work adds the value; I only move it."),
    (False, "A NEW BOOK. The village is new to me again, though the old rules held. Read it fresh before I trust an old figure. The standing orders below are from the old book; judge them in a year. The Old Order's teachings are in my report: weigh them, do not repeat them."),
    (False, "Small kinds can end: fewer than a dozen dwarves, halflings or elves is a line at risk. Match their singles early. A seat (inn, outfitter, smith first) should never stand empty for long: teach a child the trade before the holder dies."),
]
ORDERS = [   # from the old book, goods only (no person is named): she may change any of them at her first look
    {"buy": "Barley, a sack", "below": 2.0, "for_days": 0, "up_to": 8, "per_night": 2, "keep_gp": 3},
    {"buy": "Hen", "below": 2.0, "for_days": 0, "up_to": 5, "per_night": 2, "keep_gp": 30},
    {"buy": "Crossbow", "below": 0.45, "for_days": 0, "up_to": 3, "per_night": 1, "keep_gp": 120},
    {"buy": "Scrap metal", "below": 0.2, "for_days": 0, "up_to": 10, "per_night": 2, "keep_gp": 100},
    {"sell": "Crossbow", "for_days": 365, "keep": 0, "per_night": 1, "when_metal_below_kg": 3},
    {"sell": "Scrap metal", "for_days": 30, "keep": 0, "per_night": 3, "when_metal_below_kg": 1},
    {"aid": "detlef", "gp": 10, "when_purse_below_gp": 4, "for_days": 7, "every_days": 14},
    {"aid": "hartmut", "gp": 10, "when_purse_below_gp": 3, "for_days": 7, "every_days": 90},
    {"aid": "xaver", "gp": 10, "when_purse_below_gp": 3, "for_days": 30, "every_days": 90},
    {"aid": "ivo", "gp": 5, "when_purse_below_gp": 4, "for_days": 14, "every_days": 180},
    {"give_hens": 2, "when_flock_below": 7},
]
FLAGS = [
    {"when": "flock_below", "for_days": 10, "n": 5},
    {"when": "purse_below_gp", "for_days": 120, "gp": 1, "of": "each producer"},
    {"when": "stock_below", "for_days": 90, "n": 1, "of": "each good", "except": ["Ale, a jug", "Eggs, a dozen", "Smoked eel"]},
    {"when": "stock_below", "for_days": 365, "n": 1, "of": "Smoked eel"},
]
NEXT = {"in_days": 60, "or_when": [{"flock_below": 5}, {"disaster": True}, {"purse_below_gp": "xaver", "gp": 1}, {"purse_below_gp": "jutta", "gp": 1}]}


def wipe() -> None:
    registry.connect().close()                      # the tables exist, even in a new database
    db = sqlite3.connect(items.DB_PATH, isolation_level=None, timeout=60)
    for table in WIPED:
        try:
            db.execute(f"DELETE FROM {table}")
        except sqlite3.OperationalError:
            pass
    db.execute("DELETE FROM items WHERE holder_type != 'pc'")
    db.execute("DELETE FROM people WHERE claimed_by IS NULL")
    db.execute("UPDATE people SET born_day = NULL, spouse_id = NULL, mother_id = NULL, father_id = NULL, household_id = NULL, seat = NULL, "
               "genes = NULL, died_day = NULL, cause = NULL WHERE claimed_by IS NOT NULL")   # a player's villager belongs to no household: the character's coins are theirs
    db.execute("VACUUM")
    db.close()


def main(tag: str) -> None:
    path = town.TOWN_PATH
    if path.exists():
        shutil.move(str(path), str(path.with_name(f"town-{tag}.json")))
    wipe()
    day = town.campaign_day()
    registry.connect().close()                      # the cast of villagers.py
    with town.town(write=True) as s:
        s["last_daily"] = day - 1
        lives.monthly(s, day)                       # genesis: ages, couples, children
        db = registry.connect()
        with db:
            report = households.migrate(db, s)      # one purse per household from the first night
        db.close()
        s["town_note"] = "\n".join(f"{who}: {line}" for who, line in REQUESTS)
    daily._work(use_model=False)                    # the first night: shops, traders, fields
    with town.town(write=True) as s:
        b = steward.book(s)
        b["notes"] = [{"id": i, "day": day, "text": text, "pin": pin, "until": None} for i, (pin, text) in enumerate(NOTES, 1)]
        b["next_note"] = len(NOTES) + 1
        b["notebook"] = "\n".join(n["text"] for n in b["notes"])
        b["lost_for_room"], b["changed_by_rules"], b["log"], b["history"], b["done"], b["streak"] = [], [], [], [], [], {}
        b["matches"], b["mentoring"], b["blocks"] = [], [], []
        b["orders"], b["flags"] = ORDERS, FLAGS
        b["attention"] = steward.ATTENTION_CAP
        b["next"] = {**NEXT, "day": day + NEXT["in_days"]}
        print("year 0 = day", day, report)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "old")
