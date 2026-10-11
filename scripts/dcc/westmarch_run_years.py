#!/usr/bin/env python3
"""Run the live village forward by simulated years, stopping whenever the steward is due so a headless Claude can look over it (stdlib only, on the host).

    python3 scripts/dcc/westmarch_run_years.py 5                 # five years, model sonnet, at most 150 check-ins
    python3 scripts/dcc/westmarch_run_years.py 5 --model haiku --budget 60

The village is the real one (container "sheet"; take a backup first, scripts/dcc/westmarch_reset.sh restores it). Each stretch runs nights in the container
until ``steward.due`` gives a reason, then the check-in is made as scripts/dcc/steward_checkin.py does, with the reason in her report. A file ``STOP`` next to
this script's log ends the run after the current stretch. The log is data/steward/run-years.log.
"""

import argparse
import datetime
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import steward_checkin as checkin  # noqa: E402

RUN = """
import os
from datetime import timedelta
from ttrpgtools.dcc.westmarch import daily, places, steward, town
places.INTEREST_MONTHLY = 0          # years of 2 percent a month would only make the debts silly
places.LIBRARY_INTEREST_MONTHLY = 0
real, start = town.today, town.campaign_day()
with town.town() as s:
    first = int(s["last_daily"]) + 1
last = {last}
for day in range(first, last + 1):
    town.today = lambda on=real() + timedelta(days=day - start): on
    daily._work(use_model=False)
    with town.town() as s:
        why = steward.due(s, day)
    if why:
        print("DUE", day, why, flush=True)
        break
else:
    print("DONE", last, flush=True)
"""
CHUNK_NIGHTS = 60   # the village runs in stretches this long, so a PAUSE or STOP takes hold within a minute or two
DAY = "from ttrpgtools.dcc.westmarch import town\nwith town.town() as s:\n    print(s['last_daily'])\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("years", type=float, nargs="?", default=None, help="how long; leave out to run until the STOP file appears")
    ap.add_argument("--container", default="sheet")
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--budget", type=int, default=100000, help="most check-ins in this run (a safety catch; her attention is the real limit)")
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[2]
    here = root / "data" / "steward"
    log, stop, pause = here / "run-years.log", here / "STOP", here / "PAUSE"
    here.mkdir(parents=True, exist_ok=True)

    def say(text: str) -> None:
        with open(log, "a") as f:
            print(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {text}", file=f)

    day0 = int(checkin.in_container(args.container, DAY))
    end = None if args.years is None else day0 + round(args.years * 365)
    say(f"start: day {day0} to {end or 'STOP'}, model {args.model}; one point of attention = {checkin.REF_TOKENS} tokens; "
        + checkin.in_container(args.container, checkin.SEED.format(day=day0)))
    calls, spent_all, now, paused, next_year = 0, {"tokens": 0, "usd": 0.0}, day0, False, day0 + 365
    while not stop.exists():
        if pause.exists():   # touch data/steward/PAUSE to hold the village where it is; remove it to go on
            if not paused:
                say(f"paused at day {now}")
                paused = True
            time.sleep(10)
            continue
        if paused:
            say(f"resumed at day {now}")
            paused = False
        target = now + CHUNK_NIGHTS if end is None else min(end, now + CHUNK_NIGHTS)
        out = checkin.in_container(args.container, RUN.format(last=target)).splitlines()[-1]
        if out.startswith("DONE"):
            now = target
            if now >= next_year:
                weeks = (now - day0) / 7
                say(f"year {now / 365:.1f}: {calls} check-ins so far; {spent_all['tokens'] / max(weeks, 1):.0f} tokens per in-game week, {spent_all['usd'] / max(weeks, 1) * 52.1:.2f} USD per in-game year")
                next_year += 365
            if end is not None and now >= end:
                break
            continue
        _, day, why = out.split(" ", 2)
        now = int(day)
        if calls >= args.budget:
            say(f"stopping: check-in budget spent, due on day {day}: {why}")
            break
        # the container's own calendar says today, the simulated night is `day`
        asked = json.loads(checkin.in_container(args.container, checkin.ASK.format(force=why).replace("town.campaign_day()", day)))
        answer, looked, spent = {}, 0, {"tokens": 0, "usd": 0.0}
        for attempt in (1, 2):   # an exception or an answer without a word of JSON is a failed call, not a decision: ask once more
            try:
                answer, looked, used = checkin.ask_with_lookups(args.container, asked["request"], args.model, day)
                spent = {"tokens": spent["tokens"] + used["tokens"], "usd": spent["usd"] + used["usd"]}
            except Exception as exc:
                say(f"day {day}: claude failed ({exc!r})")
            if answer:
                break
            say(f"day {day}: no answer (attempt {attempt})")
        calls += 1
        spent_all = {"tokens": spent_all["tokens"] + spent["tokens"], "usd": spent_all["usd"] + spent["usd"]}
        cost = spent["tokens"] / checkin.REF_TOKENS
        checkin.in_container(args.container, checkin.APPLY.format(answer=json.dumps(answer), why=why, cost=cost).replace("town.campaign_day()", day))
        wake = answer.get("next_checkin")
        say(f"day {day} (year {int(day) / 365:.1f}): {why} | lookups {looked} | {spent['tokens']} tokens = {cost:.2f} points, {spent['usd']:.3f} USD | orders {len(answer.get('orders') or [])} | next {json.dumps(wake)} | note {str(answer.get('town_note'))[:80]!r}")
        say(f"   notes added: {json.dumps(answer.get('notes_add'), ensure_ascii=False)[:400]} | deleted: {answer.get('notes_delete')} | flags changed: {'flags' in answer} | matches: {json.dumps(answer.get('matches'))} | mentor: {json.dumps(answer.get('mentor'))}")
        if calls >= args.budget:
            say(f"stopping: {calls} check-ins made, as asked")
            break
    weeks = (now - day0) / 7
    say(f"finished at day {now} after {calls} check-ins: {spent_all['tokens']} tokens, {spent_all['usd']:.2f} USD, {spent_all['tokens'] / max(weeks, 1):.0f} tokens per in-game week")


if __name__ == "__main__":
    main()
