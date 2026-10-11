"""Live combat state and the operations on it.

State is one JSON document. Every change is an operation dict passed to
``apply``; the store keeps the previous documents for undo and a version number
so two open tabs cannot overwrite each other silently.

A combatant carries a snapshot of its stat block, so editing or re-importing a
monster never changes a fight in progress. Counters store ``max`` and ``spent``.
The tracker never rolls dice; it prompts, the table rolls.
"""

from __future__ import annotations

import copy
import json
import secrets
import sqlite3
from datetime import datetime, timezone
from typing import Any

from . import db
from .statblock import ability_mod

UNDO_DEPTH = 50
CONDITIONS = ["Blinded", "Charmed", "Deafened", "Frightened", "Grappled", "Incapacitated", "Invisible",
              "Paralyzed", "Petrified", "Poisoned", "Prone", "Restrained", "Stunned", "Unconscious",
              "Exhaustion", "Hidden", "Surprised", "Dodging", "Hasted", "Slowed", "Blessed", "Baned",
              "Hexed", "Marked"]


class CombatError(ValueError):
    """The operation makes no sense in the current state."""


class VersionConflict(CombatError):
    """The state changed since the client last loaded it."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_id() -> str:
    return secrets.token_hex(4)


# ------------------------------------------------------------------ building
def _counters(resources: list[dict]) -> list[dict]:
    return [dict(r, spent=int(r.get("spent") or 0)) for r in resources or []]


def _next_number(state: dict, name: str) -> int:
    used = [c.get("number") or 1 for c in state["combatants"] if c.get("base_name") == name]
    return max(used, default=0) + 1


def _monster_combatant(state: dict, statblock: dict, initiative: int | None = None) -> dict:
    name = statblock["name"]
    return {
        "id": _new_id(), "kind": "monster", "base_name": name, "number": _next_number(state, name),
        "label": name, "monster_id": statblock.get("id"),
        "hp": statblock["hp"], "hp_max": statblock["hp"], "temp_hp": 0, "ac": statblock["ac"],
        "init_mod": statblock.get("init_mod", 0), "initiative": initiative,
        "conditions": [], "concentration": None, "reaction_used": False, "defeated": False, "notes": "",
        "resources": _counters(statblock.get("resources")),
        "statblock": {k: v for k, v in statblock.items() if k not in ("description", "import_problems")},
    }


def _relabel(state: dict, name: str) -> None:
    """Identical monsters get numbers; a lone one keeps its plain name. Renamed ones are left alone."""
    group = [c for c in state["combatants"] if c.get("base_name") == name and not c.get("renamed")]
    total = len([c for c in state["combatants"] if c.get("base_name") == name])
    for c in group:
        c["label"] = f"{name} {c['number']}" if total > 1 or c["number"] > 1 else name


def _pc_combatant(pc: dict) -> dict:
    hp_max = int(pc.get("hp") or 1)
    dex = (pc.get("abilities") or {}).get("dex")
    return {
        "id": _new_id(), "kind": "pc", "pc_id": pc.get("id"), "label": pc["name"],
        "level": pc.get("level"), "cls": pc.get("cls"),
        "hp": int(pc["hp_current"]) if pc.get("hp_current") is not None else hp_max, "hp_max": hp_max,
        "temp_hp": int(pc.get("temp_hp") or 0), "ac": int(pc.get("ac") or 10),
        "init_mod": int(pc["init_mod"]) if pc.get("init_mod") is not None else ability_mod(dex or 10),
        "initiative": None, "conditions": [], "concentration": None, "reaction_used": False,
        "defeated": False, "notes": pc.get("notes") or "", "death_saves": {"success": 0, "fail": 0},
        "resources": _counters(pc.get("resources")),
    }


def new_combat(name: str, pcs: list[dict], monsters: list[tuple[dict, int]], encounter_id: str | None = None) -> dict:
    state: dict[str, Any] = {"name": name, "encounter_id": encounter_id, "round": 0, "turn": None,
                             "started": False, "combatants": [], "log": [], "version": 0}
    state["combatants"].extend(_pc_combatant(pc) for pc in pcs)
    for statblock, count in monsters:
        for _ in range(max(1, int(count))):
            state["combatants"].append(_monster_combatant(state, statblock))
        _relabel(state, statblock["name"])
    return state


# ------------------------------------------------------------------ reading
def find(state: dict, combatant_id: str) -> dict:
    for c in state["combatants"]:
        if c["id"] == combatant_id:
            return c
    raise CombatError(f"No combatant {combatant_id}.")


def resource(combatant: dict, key: str) -> dict:
    for r in combatant["resources"]:
        if r["key"] == key:
            return r
    raise CombatError(f"{combatant['label']} has no counter {key}.")


def ordered(state: dict) -> list[dict]:
    """Initiative order: total, then modifier, then the order of joining. Unset goes last."""
    position = {c["id"]: i for i, c in enumerate(state["combatants"])}
    return sorted(state["combatants"], key=lambda c: (
        c["initiative"] is None, -(c["initiative"] or 0), -(c.get("init_mod") or 0),
        c.get("tiebreak", position[c["id"]])))


def current(state: dict) -> dict | None:
    return next((c for c in state["combatants"] if c["id"] == state.get("turn")), None)


# ------------------------------------------------------------------ operations
def _log(state: dict, text: str) -> None:
    state["log"].append({"round": state["round"], "text": text})
    del state["log"][:-200]


def _targets(state: dict, op: dict) -> list[dict]:
    ids = op.get("ids") or ([op["id"]] if op.get("id") else [])
    if not ids:
        raise CombatError("No target given.")
    return [find(state, i) for i in ids]


def _amount(op: dict) -> int:
    try:
        amount = int(op.get("amount", 1))
    except (TypeError, ValueError) as exc:
        raise CombatError("Amount must be a whole number.") from exc
    if amount < 0:
        raise CombatError("Amount must not be negative.")
    return amount


def _damage(state: dict, op: dict, prompts: list[str]) -> None:
    amount = _amount(op)
    halved = set(op.get("half") or [])
    for c in _targets(state, op):
        dealt = amount // 2 if c["id"] in halved else amount
        absorbed = min(c["temp_hp"], dealt)
        c["temp_hp"] -= absorbed
        before = c["hp"]
        c["hp"] = max(0, c["hp"] - (dealt - absorbed))
        _log(state, f"{c['label']} takes {dealt} damage ({before} -> {c['hp']}).")
        if c["concentration"] and dealt > 0:
            if c["hp"] == 0:
                _log(state, f"{c['label']} loses concentration on {c['concentration']}.")
                c["concentration"] = None
            else:
                prompts.append(f"{c['label']}: Constitution save DC {max(10, dealt // 2)} "
                               f"to keep concentrating on {c['concentration']}.")
        if c["hp"] == 0 and before > 0:
            if c["kind"] == "pc":
                massive = dealt - absorbed - before >= c["hp_max"]
                prompts.append(f"{c['label']} is dead (massive damage)." if massive
                               else f"{c['label']} is down: death saves start.")
                c["death_saves"] = {"success": 0, "fail": 0}
                _set_condition(c, "Unconscious", None, None)
            else:
                c["defeated"] = True
                _log(state, f"{c['label']} is defeated.")
        elif c["hp"] == 0 and c["kind"] == "pc" and dealt > 0:
            c["death_saves"]["fail"] = min(3, c["death_saves"]["fail"] + 1)
            prompts.append(f"{c['label']} takes damage at 0 HP: one death save failure.")


def _heal(state: dict, op: dict) -> None:
    amount = _amount(op)
    for c in _targets(state, op):
        before = c["hp"]
        c["hp"] = min(c["hp_max"], c["hp"] + amount)
        if before == 0 and c["hp"] > 0:
            c["defeated"] = False
            c["conditions"] = [x for x in c["conditions"] if x["name"] != "Unconscious"]
            if c["kind"] == "pc":
                c["death_saves"] = {"success": 0, "fail": 0}
        _log(state, f"{c['label']} regains {c['hp'] - before} HP ({before} -> {c['hp']}).")


def _set_condition(c: dict, name: str, rounds: int | None, source: str | None) -> None:
    c["conditions"] = [x for x in c["conditions"] if x["name"] != name]
    c["conditions"].append({"name": name, "rounds": rounds, "source": source})


def _turn_start(state: dict, c: dict, prompts: list[str]) -> None:
    c["reaction_used"] = False
    for r in c["resources"]:
        if r["kind"] == "legendary":
            r["spent"] = 0
        elif r["kind"] == "recharge" and r["spent"]:
            low = r.get("recharge_min", 6)
            prompts.append(f"{c['label']}: roll a d6 for {r['name']}, recharges on "
                           f"{low if low == 6 else f'{low}-6'}.")
    remaining = []
    for condition in c["conditions"]:
        if condition["rounds"] is None:
            remaining.append(condition)
            continue
        condition["rounds"] -= 1
        if condition["rounds"] > 0:
            remaining.append(condition)
        else:
            _log(state, f"{condition['name']} ends on {c['label']}.")
    c["conditions"] = remaining
    if c["kind"] == "pc" and c["hp"] == 0 and not c["defeated"]:
        prompts.append(f"{c['label']}: death saving throw.")
    regeneration = next((t for t in (c.get("statblock") or {}).get("traits", [])
                         if t["name"].lower().startswith("regeneration")), None)
    if regeneration and not c["defeated"]:
        prompts.append(f"{c['label']}: Regeneration. {regeneration['text'][:160]}")


def _step(state: dict, direction: int, prompts: list[str]) -> None:
    if not state["started"]:
        raise CombatError("Combat has not started.")
    order = ordered(state)
    active = [c for c in order if not c["defeated"] or c["id"] == state["turn"]]
    if not active:
        raise CombatError("Nobody is left to act.")
    index = next((i for i, c in enumerate(active) if c["id"] == state["turn"]), -1)
    for _ in range(len(active)):
        index += direction
        if index >= len(active):
            index = 0
            state["round"] += 1
        elif index < 0:
            if state["round"] <= 1:
                raise CombatError("Already at the first turn.")
            index = len(active) - 1
            state["round"] -= 1
        if not active[index]["defeated"]:
            break
    state["turn"] = active[index]["id"]
    if direction > 0:
        _turn_start(state, active[index], prompts)
        if any(c.get("statblock", {}).get("lair") for c in state["combatants"] if not c["defeated"]) \
                and index == 0:
            prompts.append("Lair actions act on initiative count 20.")


def apply(state: dict, op: dict) -> dict:
    """Apply one operation in place. Returns {"prompts": [...]}: reminders for the table."""
    prompts: list[str] = []
    kind = op.get("op")

    if kind == "damage":
        _damage(state, op, prompts)
    elif kind == "heal":
        _heal(state, op)
    elif kind == "temp_hp":
        for c in _targets(state, op):
            c["temp_hp"] = max(c["temp_hp"], _amount(op))
    elif kind == "set":
        c = find(state, op["id"])
        for field in ("hp", "hp_max", "temp_hp", "ac", "init_mod"):
            if op.get(field) is not None:
                c[field] = int(op[field])
        if "notes" in op:
            c["notes"] = str(op["notes"])[:2000]
        c["hp"] = max(0, min(c["hp"], c["hp_max"]))
        if c["kind"] != "pc":
            c["defeated"] = c["hp"] == 0 and c["hp_max"] > 0
    elif kind == "set_initiative":
        c = find(state, op["id"])
        c["initiative"] = None if op.get("value") in (None, "") else int(op["value"])
    elif kind == "set_group_initiative":
        for c in state["combatants"]:
            if c.get("base_name") == op["base_name"]:
                c["initiative"] = int(op["value"])
    elif kind == "reorder":
        # Manual tie-break: the client sends the ids in the order it wants.
        for position, combatant_id in enumerate(op["ids"]):
            find(state, combatant_id)["tiebreak"] = position
    elif kind == "condition":
        c = find(state, op["id"])
        name = str(op["name"]).strip()[:40]
        if not name:
            raise CombatError("Condition needs a name.")
        rounds = int(op["rounds"]) if op.get("rounds") else None
        _set_condition(c, name, rounds, op.get("source"))
    elif kind == "remove_condition":
        c = find(state, op["id"])
        c["conditions"] = [x for x in c["conditions"] if x["name"] != op["name"]]
    elif kind == "concentration":
        c = find(state, op["id"])
        c["concentration"] = (str(op.get("spell") or "").strip()[:60] or None)
    elif kind == "reaction":
        c = find(state, op["id"])
        c["reaction_used"] = bool(op.get("used", not c["reaction_used"]))
    elif kind == "death_save":
        c = find(state, op["id"])
        saves = c.setdefault("death_saves", {"success": 0, "fail": 0})
        key = "success" if op.get("success") else "fail"
        saves[key] = max(0, min(3, saves[key] + int(op.get("amount", 1))))
        if saves["fail"] >= 3:
            c["defeated"] = True
            prompts.append(f"{c['label']} has died.")
        elif saves["success"] >= 3:
            prompts.append(f"{c['label']} is stable.")
    elif kind in ("spend", "restore"):
        c = find(state, op["id"])
        r = resource(c, op["key"])
        amount = _amount(op)
        if kind == "spend":
            if r["spent"] + amount > r["max"]:
                raise CombatError(f"{c['label']}: {r['name']} has {r['max'] - r['spent']} left.")
            r["spent"] += amount
            _log(state, f"{c['label']} uses {r['name']} ({r['max'] - r['spent']}/{r['max']} left).")
        else:
            r["spent"] = max(0, r["spent"] - amount)
    elif kind == "add_resource":
        c = find(state, op["id"])
        name = str(op["name"]).strip()[:60]
        if not name:
            raise CombatError("Counter needs a name.")
        c["resources"].append({"key": f"custom-{_new_id()}", "name": name, "kind": op.get("kind") or "day",
                               "max": max(1, int(op.get("max") or 1)), "spent": 0})
    elif kind == "remove_resource":
        c = find(state, op["id"])
        c["resources"] = [r for r in c["resources"] if r["key"] != op["key"]]
    elif kind == "rest":
        kinds = {"short": {"short", "recharge", "encounter"},
                 "long": {"short", "long", "day", "slot", "recharge", "legendary_resistance",
                          "encounter"}}[op.get("kind", "long")]
        for c in _targets(state, op) if op.get("id") or op.get("ids") else state["combatants"]:
            for r in c["resources"]:
                if r["kind"] in kinds:
                    r["spent"] = 0
            if op.get("kind", "long") == "long":
                c["hp"], c["temp_hp"] = c["hp_max"], 0
    elif kind == "rename":
        c = find(state, op["id"])
        label = str(op["label"]).strip()[:60]
        if not label:
            raise CombatError("Name must not be empty.")
        c["label"], c["renamed"] = label, True
    elif kind == "add_monster":
        for _ in range(max(1, min(50, int(op.get("count") or 1)))):
            c = _monster_combatant(state, op["statblock"], op.get("initiative"))
            state["combatants"].append(c)
        _relabel(state, op["statblock"]["name"])
    elif kind == "add_pc":
        state["combatants"].append(dict(_pc_combatant(op["pc"]), initiative=op.get("initiative")))
    elif kind == "add_custom":
        label = str(op.get("label") or "").strip()[:60]
        if not label:
            raise CombatError("Name must not be empty.")
        hp = max(0, int(op.get("hp") or 0))
        state["combatants"].append({
            "id": _new_id(), "kind": "custom", "label": label, "renamed": True, "hp": hp, "hp_max": hp,
            "temp_hp": 0, "ac": int(op.get("ac") or 10), "init_mod": int(op.get("init_mod") or 0),
            "initiative": op.get("initiative"), "conditions": [], "concentration": None,
            "reaction_used": False, "defeated": False, "notes": "", "resources": []})
    elif kind == "remove":
        c = find(state, op["id"])
        if state.get("turn") == c["id"] and state["started"]:
            try:
                _step(state, 1, prompts)
            except CombatError:
                state["turn"] = None
        state["combatants"].remove(c)
        if state.get("turn") == c["id"]:
            state["turn"] = None
    elif kind == "defeated":
        c = find(state, op["id"])
        c["defeated"] = bool(op.get("value", not c["defeated"]))
    elif kind == "start":
        if not state["combatants"]:
            raise CombatError("Add combatants first.")
        state["started"], state["round"] = True, 1
        first = next((c for c in ordered(state) if not c["defeated"]), None)
        state["turn"] = first["id"] if first else None
        unset = [c["label"] for c in state["combatants"] if c["initiative"] is None]
        if unset:
            prompts.append("No initiative yet: " + ", ".join(unset) + ".")
        if first:
            _turn_start(state, first, prompts)
    elif kind == "next":
        _step(state, 1, prompts)
    elif kind == "prev":
        _step(state, -1, prompts)
    elif kind == "end":
        state["started"], state["turn"] = False, None
        _log(state, f"Combat ends after {state['round']} rounds.")
    else:
        raise CombatError(f"Unknown operation {kind!r}.")
    return {"prompts": prompts}


# ------------------------------------------------------------------ store
def create(conn: sqlite3.Connection, state: dict) -> str:
    combat_id = _new_id()
    state["version"] = 0
    conn.execute("INSERT INTO combats (id, encounter_id, name, updated, version, data) VALUES (?,?,?,?,?,?)",
                 (combat_id, state.get("encounter_id"), state["name"], _now(), 0, db.dumps(state)))
    conn.commit()
    return combat_id


def load(conn: sqlite3.Connection, combat_id: str) -> dict | None:
    row = conn.execute("SELECT id, data, version FROM combats WHERE id = ?", (combat_id,)).fetchone()
    if row is None:
        return None
    state = json.loads(row["data"])
    state["id"], state["version"] = row["id"], row["version"]
    return state


def list_combats(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT id, name, updated, json_extract(data,'$.round') AS round, "
                        "json_extract(data,'$.started') AS started FROM combats ORDER BY updated DESC")
    return [dict(r) for r in rows]


def delete(conn: sqlite3.Connection, combat_id: str) -> None:
    conn.execute("DELETE FROM combats WHERE id = ?", (combat_id,))
    conn.commit()


def act(conn: sqlite3.Connection, combat_id: str, op: dict, version: int | None = None) -> tuple[dict, dict]:
    """Load, apply, save in one write transaction. ``version`` is what the client last saw."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute("SELECT data, version, undo FROM combats WHERE id = ?", (combat_id,)).fetchone()
        if row is None:
            raise CombatError("No such combat.")
        if version is not None and int(version) != row["version"]:
            raise VersionConflict("The fight changed in another window; reloaded.")
        state = json.loads(row["data"])
        previous = copy.deepcopy(state)
        result = apply(state, op)
        state["version"] = row["version"] + 1
        undo_stack = (json.loads(row["undo"]) + [previous])[-UNDO_DEPTH:]
        conn.execute("UPDATE combats SET data = ?, version = ?, undo = ?, updated = ?, name = ? WHERE id = ?",
                     (db.dumps(state), state["version"], db.dumps(undo_stack), _now(), state["name"], combat_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    state["id"] = combat_id
    return state, result


def undo(conn: sqlite3.Connection, combat_id: str) -> dict:
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute("SELECT version, undo FROM combats WHERE id = ?", (combat_id,)).fetchone()
        if row is None:
            raise CombatError("No such combat.")
        stack = json.loads(row["undo"])
        if not stack:
            raise CombatError("Nothing to undo.")
        state = stack.pop()
        state["version"] = row["version"] + 1
        conn.execute("UPDATE combats SET data = ?, version = ?, undo = ?, updated = ? WHERE id = ?",
                     (db.dumps(state), state["version"], db.dumps(stack), _now(), combat_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    state["id"] = combat_id
    return state
