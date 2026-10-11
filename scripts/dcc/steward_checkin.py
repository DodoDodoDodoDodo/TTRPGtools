#!/usr/bin/env python3
"""One check-in of the steward (Hedwig Dornbusch), run on the host with the standard library only: the town container builds her report and the
prompt, a headless Claude instance (it holds only her notebook as memory) answers, the container applies the answer. The container has no Claude.

    python3 scripts/dcc/steward_checkin.py                 # the live town, container "sheet", model sonnet
    python3 scripts/dcc/steward_checkin.py --dry           # show the answer, change nothing

Run it from a nightly timer: it only does anything on the nights she is due (her own date or the conditions she set), her standing orders do the rest; see ~/.config/systemd/user/westmarch-steward.timer.
"""

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

ASK = ("import json\nfrom ttrpgtools.dcc.westmarch import steward, town\nwith town.town() as s:\n"
       "    why = steward.due(s, town.campaign_day()) or {force!r}\n    print(json.dumps({{'why': why, 'request': steward.brain_request(steward.report(s, town.campaign_day(), why or ''))}} if why else {{}}))\n")
APPLY = ("import json\nfrom ttrpgtools.dcc.westmarch import steward, town\nanswer = json.loads({answer!r})\n"
         "with town.town(write=True) as s:\n    steward.apply(s, town.campaign_day(), answer, {why!r}, {cost!r})\n    print('applied;', len(s['steward']['orders']), 'orders')\n")


SEED = ("from pathlib import Path\nfrom ttrpgtools.dcc.westmarch import steward, town\nwith town.town(write=True) as s:\n"
        "    print('seed notes added:', steward.load_seed(s, {day}, Path('/app/data/steward/notebook-seed.txt').read_text()))\n")


def in_container(name: str, code: str) -> str:
    return subprocess.run(["docker", "exec", "-i", "-w", "/app", name, "python", "-"], input=code, capture_output=True, text=True, check=True).stdout.strip()


def ask_claude(request: dict, model: str) -> tuple[dict, dict]:
    """One call: her answer, and what it used ({"tokens": all tokens read and written, "usd": the bill})."""
    # Run from an empty directory outside your home directory: claude reads CLAUDE.md and project memory from the working directory upwards, and she must see neither.
    here = Path(tempfile.gettempdir()) / "hedwig-cwd"
    here.mkdir(exist_ok=True)
    out = subprocess.run(["claude", "-p", "--output-format", "json", "--tools", "", "--no-session-persistence", "--model", model, "--system-prompt", request["system"], request["prompt"]],
                         capture_output=True, text=True, timeout=300, cwd=here)
    meta = json.loads(out.stdout or "{}")
    u = meta.get("usage") or {}
    used = {"tokens": sum(int(u.get(k) or 0) for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")),
            "usd": float(meta.get("total_cost_usd") or 0)}
    text = str(meta.get("result") or "")
    start, end = text.find("{"), text.rfind("}")
    try:
        return (json.loads(text[start:end + 1]) if start >= 0 < end else {}), used
    except json.JSONDecodeError:
        return {}, used


REF_TOKENS = 31000   # one point of her attention: one plain check-in call measured 30,867 tokens (USD 0.13) on 2026-10-10 at day 24023
LOOK = ("import json\nfrom ttrpgtools.dcc.westmarch import steward, town\nqueries = json.loads({queries!r})\n"
        "with town.town() as s:\n    print(json.dumps(steward.look(s, {day}, queries)))\n")


def ask_with_lookups(container: str, request: dict, model: str, day: str = "town.campaign_day()", rounds: int = 2) -> tuple[dict, int, dict]:
    """Ask her; when she answers with nothing but ``look_up`` questions about the people, answer them from the register and ask again (at most ``rounds`` times).
    Returns her answer, how many times she looked things up, and what all the calls used together."""
    prompt, looked, spent = request["prompt"], 0, {"tokens": 0, "usd": 0.0}
    while True:
        answer, used = ask_claude({"system": request["system"], "prompt": prompt}, model)
        spent = {"tokens": spent["tokens"] + used["tokens"], "usd": spent["usd"] + used["usd"]}
        queries = answer.get("look_up") if isinstance(answer, dict) else None
        if not queries or set(answer) - {"look_up"} or looked >= rounds:
            answer.pop("look_up", None)
            return answer, looked, spent
        found = in_container(container, LOOK.format(queries=json.dumps(queries), day=day))
        prompt += "\n\nWhat you asked to look up:\n" + found + "\n\nNow answer with the JSON for your decisions" + (" (you may look something up once more if you must)." if looked + 1 < rounds else ".")
        looked += 1


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--container", default="sheet")
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--force", action="store_true", help="check in even when she is not due")
    ap.add_argument("--seed", action="store_true", help="only add the lines of data/steward/notebook-seed.txt to her notebook (pinned), then stop")
    args = ap.parse_args()
    if args.seed:
        print(in_container(args.container, SEED.format(day="town.campaign_day()")))
        return
    asked = json.loads(in_container(args.container, ASK.format(force="forced from the host" if args.force else "")))
    if not asked:
        print("not due")   # the timer runs every night; she is woken by the date or the conditions she set herself
        return
    answer, looked, spent = ask_with_lookups(args.container, asked["request"], args.model)
    print(asked["why"], f"(looked things up {looked} times; {spent['tokens']} tokens, {spent['usd']:.3f} USD)", json.dumps(answer, indent=1, ensure_ascii=False), sep="\n")
    if not args.dry and answer:
        print(in_container(args.container, APPLY.format(answer=json.dumps(answer), why=asked["why"], cost=spent["tokens"] / REF_TOKENS)))


if __name__ == "__main__":
    main()
