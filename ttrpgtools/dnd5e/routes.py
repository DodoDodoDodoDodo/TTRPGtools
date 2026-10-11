"""Flask blueprint for the D&D 5e encounter tools, mounted under /TTRPG/dnd5e.

Pages are thin shells; they talk to the JSON API below. Errors come back as
{"error": "..."} with a 4xx status, which the pages show as they are.
"""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone

from flask import Blueprint, abort, g, jsonify, render_template, request

from ttrpgtools.dnd5e import bestiary, combat, db, ddb_character, difficulty, paste_import
from ttrpgtools.dnd5e.statblock import derive, slugify

bp = Blueprint("dnd5e", __name__, url_prefix="/TTRPG/dnd5e")

MAX_PASTE = 60_000
PC_FIELDS = ("name", "level", "cls", "classes", "race", "hp", "hp_current", "temp_hp", "ac", "ac_how",
             "ac_estimated", "abilities", "init_mod", "resources", "dpr", "attack_bonus", "notes",
             "ddb_id", "ddb_url", "source", "player")


class ApiError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


@bp.errorhandler(ApiError)
def _api_error(exc: ApiError):
    return jsonify(error=str(exc)), exc.status


@bp.errorhandler(combat.VersionConflict)
def _conflict(exc):
    return jsonify(error=str(exc), conflict=True), 409


@bp.errorhandler(combat.CombatError)
@bp.errorhandler(paste_import.PasteError)
@bp.errorhandler(ddb_character.DDBError)
def _domain_error(exc):
    return jsonify(error=str(exc)), 400


def conn():
    if "dnd5e_db" not in g:
        g.dnd5e_db = db.connect()
    return g.dnd5e_db


@bp.teardown_app_request
def _close(_exc):
    connection = g.pop("dnd5e_db", None)
    if connection is not None:
        connection.close()


def _owner() -> str | None:
    return request.headers.get("Remote-User") or None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _body() -> dict:
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ApiError("Expected a JSON object.")
    return body


def _number(name: str) -> float | None:
    raw = request.args.get(name, "").strip()
    if not raw:
        return None
    try:
        return float(raw) if "/" not in raw else int(raw.split("/")[0]) / int(raw.split("/")[1])
    except (ValueError, ZeroDivisionError) as exc:
        raise ApiError(f"{name} is not a number.") from exc


# ------------------------------------------------------------------ pages
@bp.get("/")
def index():
    return render_template("dnd5e/dnd5e_index.html")


@bp.get("/monsters")
def monsters_page():
    return render_template("dnd5e/dnd5e_monsters.html")


@bp.get("/encounter/<encounter_id>")
def encounter_page(encounter_id):
    if not conn().execute("SELECT 1 FROM encounters WHERE id = ?", (encounter_id,)).fetchone():
        abort(404)
    return render_template("dnd5e/dnd5e_encounter.html", encounter_id=encounter_id)


@bp.get("/combat/<combat_id>")
def combat_page(combat_id):
    if combat.load(conn(), combat_id) is None:
        abort(404)
    return render_template("dnd5e/dnd5e_combat.html", combat_id=combat_id, conditions=combat.CONDITIONS)


# ------------------------------------------------------------------ monsters
@bp.get("/api/monsters")
def api_monsters():
    rows = bestiary.search(
        conn(), request.args.get("q", ""), _number("cr_min"), _number("cr_max"), request.args.get("type", ""),
        official_only=request.args.get("official") == "1", origin=request.args.get("origin", ""),
        limit=min(200, int(request.args.get("limit") or 60)))
    total = conn().execute("SELECT COUNT(*) FROM monsters").fetchone()[0]
    return jsonify(monsters=rows, bestiary_size=total)


@bp.get("/api/monsters/<monster_id>")
def api_monster(monster_id):
    monster = bestiary.get_monster(conn(), monster_id)
    if monster is None:
        raise ApiError("No such monster.", 404)
    monster["profile"] = {k: v for k, v in difficulty.monster_profile(monster).items() if k != "plans"}
    return jsonify(monster)


@bp.post("/api/monsters/parse")
def api_monster_parse():
    text = str(_body().get("text") or "")
    if len(text) > MAX_PASTE:
        raise ApiError("That is too much text for one stat block.")
    monster = paste_import.parse(text)
    monster["profile"] = {k: v for k, v in difficulty.monster_profile(monster).items() if k != "plans"}
    return jsonify(monster)


@bp.post("/api/monsters")
def api_monster_save():
    body = _body()
    if body.get("text"):
        monster = paste_import.parse(str(body["text"])[:MAX_PASTE])
        origin = "paste"
    elif isinstance(body.get("monster"), dict) and body["monster"].get("name"):
        monster = derive(dict(body["monster"], resources=[]))
        origin = "manual"
    else:
        raise ApiError("Send either text or a monster.")
    for field in ("name", "cr", "ac", "hp", "source"):
        if body.get(field) not in (None, ""):
            monster[field] = int(body[field]) if field in ("ac", "hp") else str(body[field]).strip()
    monster = derive(monster)
    monster["imported_by"], monster["imported_at"] = _owner(), _now()
    with conn():
        monster_id = bestiary.save_monster(conn(), monster, origin, body.get("replace_id") or None)
    return jsonify(id=monster_id, name=monster["name"])


@bp.delete("/api/monsters/<monster_id>")
def api_monster_delete(monster_id):
    row = conn().execute("SELECT origin FROM monsters WHERE id = ?", (monster_id,)).fetchone()
    if row is None:
        raise ApiError("No such monster.", 404)
    if row["origin"] == "compendium":
        raise ApiError("Compendium monsters are rebuilt from the book data and cannot be deleted here.")
    with conn():
        conn().execute("DELETE FROM monsters WHERE id = ?", (monster_id,))
    return jsonify(ok=True)


# ------------------------------------------------------------------ player characters
def _pc_from(body: dict, existing: dict | None = None) -> dict:
    pc = dict(existing or {})
    pc.update({k: body[k] for k in PC_FIELDS if k in body})
    pc["name"] = str(pc.get("name") or "").strip()[:60]
    if not pc["name"]:
        raise ApiError("A character needs a name.")
    try:
        pc["level"] = min(20, max(1, int(pc.get("level") or 1)))
        for field in ("hp", "ac", "init_mod", "hp_current", "temp_hp", "attack_bonus"):
            if pc.get(field) in ("", None):
                pc.pop(field, None)
            else:
                pc[field] = int(pc[field])
        if pc.get("dpr") in ("", None):
            pc.pop("dpr", None)
        else:
            pc["dpr"] = float(pc["dpr"])
    except (TypeError, ValueError) as exc:
        raise ApiError("Level, HP, AC and the other numbers must be numbers.") from exc
    pc["cls"] = str(pc.get("cls") or "").strip().lower()
    pc.setdefault("resources", [])
    return pc


def _save_pc(pc: dict, pc_id: str | None = None) -> str:
    pc_id = pc_id or f"{slugify(pc['name'])}-{secrets.token_hex(2)}"
    data = {k: v for k, v in pc.items() if k != "id"}
    with conn():
        conn().execute("INSERT OR REPLACE INTO pcs (id, name, owner, data) VALUES (?,?,?,?)",
                       (pc_id, pc["name"], pc.get("owner") or _owner(), db.dumps(data)))
    return pc_id


def _get_pc(pc_id: str) -> dict:
    pc = db.row_data(conn().execute("SELECT id, data FROM pcs WHERE id = ?", (pc_id,)).fetchone())
    if pc is None:
        raise ApiError("No such character.", 404)
    return pc


@bp.get("/api/pcs")
def api_pcs():
    rows = conn().execute("SELECT id, data FROM pcs ORDER BY name COLLATE NOCASE").fetchall()
    return jsonify(pcs=[db.row_data(r) for r in rows], classes=sorted(difficulty.CLASSES))


@bp.post("/api/pcs")
def api_pc_create():
    pc = _pc_from(_body())
    pc.setdefault("source", "manual")
    return jsonify(id=_save_pc(pc))


@bp.put("/api/pcs/<pc_id>")
def api_pc_update(pc_id):
    body = _body()
    pc = _pc_from(body, _get_pc(pc_id))
    if "ac" in body:
        pc["ac_estimated"] = False
    _save_pc(pc, pc_id)
    return jsonify(id=pc_id)


@bp.delete("/api/pcs/<pc_id>")
def api_pc_delete(pc_id):
    with conn():
        conn().execute("DELETE FROM pcs WHERE id = ?", (pc_id,))
    return jsonify(ok=True)


@bp.post("/api/pcs/import-ddb")
def api_pc_import():
    reference = str(_body().get("reference") or "")
    pc = ddb_character.import_character(reference)
    existing = conn().execute("SELECT id, data FROM pcs WHERE json_extract(data,'$.ddb_id') = ?",
                              (pc["ddb_id"],)).fetchone()
    if existing:
        old = db.row_data(existing)
        # Hand-entered values survive a refresh.
        for field in ("dpr", "attack_bonus", "notes", "player"):
            if old.get(field) not in (None, ""):
                pc[field] = old[field]
        if old.get("ac_estimated") is False:
            pc["ac"], pc["ac_estimated"] = old["ac"], False
    pc_id = _save_pc(pc, existing["id"] if existing else None)
    return jsonify(id=pc_id, pc=dict(pc, id=pc_id), refreshed=bool(existing))


# ------------------------------------------------------------------ encounters
def _get_encounter(encounter_id: str) -> dict:
    row = conn().execute("SELECT id, data FROM encounters WHERE id = ?", (encounter_id,)).fetchone()
    encounter = db.row_data(row)
    if encounter is None:
        raise ApiError("No such encounter.", 404)
    return encounter


def _resolve(plan: dict) -> tuple[list[dict], list[tuple[dict, int]], list[str]]:
    """Plan ids -> PCs and (monster, count). Missing entries are reported, not fatal."""
    missing, pcs, monsters = [], [], []
    for pc_id in plan.get("pcs") or []:
        row = conn().execute("SELECT id, data FROM pcs WHERE id = ?", (pc_id,)).fetchone()
        (pcs.append(db.row_data(row)) if row else missing.append(f"character {pc_id}"))
    for entry in plan.get("monsters") or []:
        monster = bestiary.get_monster(conn(), entry.get("id"))
        count = max(1, min(50, int(entry.get("count") or 1)))
        (monsters.append((monster, count)) if monster else missing.append(f"monster {entry.get('id')}"))
    return pcs, monsters, missing


def _rating(plan: dict) -> dict:
    pcs, monsters, missing = _resolve(plan)
    flat = [m for m, count in monsters for _ in range(count)]
    rating = difficulty.rate(pcs, flat, plan.get("resources") or "normal")
    rating["missing"] = missing
    return rating


@bp.get("/api/encounters")
def api_encounters():
    rows = conn().execute("SELECT id, name, updated, data FROM encounters ORDER BY updated DESC").fetchall()
    combats = combat.list_combats(conn())
    out = []
    for r in rows:
        plan = json.loads(r["data"])
        out.append({"id": r["id"], "name": r["name"], "updated": r["updated"],
                    "monsters": sum(int(m.get("count") or 1) for m in plan.get("monsters") or []),
                    "pcs": len(plan.get("pcs") or [])})
    return jsonify(encounters=out, combats=combats)


@bp.post("/api/encounters")
def api_encounter_create():
    body = _body()
    name = str(body.get("name") or "").strip()[:80] or "New encounter"
    encounter_id = secrets.token_hex(4)
    all_pcs = [r["id"] for r in conn().execute("SELECT id FROM pcs ORDER BY name COLLATE NOCASE")]
    plan = {"name": name, "pcs": body.get("pcs") if body.get("pcs") is not None else all_pcs,
            "monsters": body.get("monsters") or [], "notes": "", "resources": "normal"}
    with conn():
        conn().execute("INSERT INTO encounters (id, name, owner, updated, data) VALUES (?,?,?,?,?)",
                       (encounter_id, name, _owner(), _now(), db.dumps(plan)))
    return jsonify(id=encounter_id)


@bp.get("/api/encounters/<encounter_id>")
def api_encounter(encounter_id):
    plan = _get_encounter(encounter_id)
    pcs, monsters, _missing = _resolve(plan)
    names = {m["id"]: {k: m.get(k) for k in ("id", "name", "cr", "xp", "hp", "ac", "source", "type", "size")}
             for m, _count in monsters}
    return jsonify(encounter=plan, monsters=names, rating=_rating(plan))


@bp.put("/api/encounters/<encounter_id>")
def api_encounter_update(encounter_id):
    plan = _get_encounter(encounter_id)
    body = _body()
    for field in ("name", "pcs", "monsters", "notes", "resources"):
        if field in body:
            plan[field] = body[field]
    plan["name"] = str(plan.get("name") or "").strip()[:80] or "Encounter"
    plan["monsters"] = [{"id": str(m["id"]), "count": max(1, min(50, int(m.get("count") or 1)))}
                        for m in plan.get("monsters") or [] if m.get("id")]
    data = {k: v for k, v in plan.items() if k != "id"}
    with conn():
        conn().execute("UPDATE encounters SET name = ?, updated = ?, data = ? WHERE id = ?",
                       (plan["name"], _now(), db.dumps(data), encounter_id))
    return jsonify(encounter=plan, rating=_rating(plan))


@bp.delete("/api/encounters/<encounter_id>")
def api_encounter_delete(encounter_id):
    with conn():
        conn().execute("DELETE FROM encounters WHERE id = ?", (encounter_id,))
    return jsonify(ok=True)


@bp.post("/api/rate")
def api_rate():
    return jsonify(_rating(_body()))


# ------------------------------------------------------------------ combat
@bp.post("/api/encounters/<encounter_id>/run")
def api_encounter_run(encounter_id):
    plan = _get_encounter(encounter_id)
    pcs, monsters, _missing = _resolve(plan)
    state = combat.new_combat(plan["name"], pcs, monsters, encounter_id)
    return jsonify(id=combat.create(conn(), state))


@bp.post("/api/combats")
def api_combat_create():
    """A fight without a plan: start empty, or with the whole party, and add as you go."""
    body = _body()
    pcs = [db.row_data(r) for r in conn().execute("SELECT id, data FROM pcs ORDER BY name")] \
        if body.get("with_party") else []
    state = combat.new_combat(str(body.get("name") or "").strip()[:80] or "Quick fight", pcs, [])
    return jsonify(id=combat.create(conn(), state))


@bp.get("/api/combats/<combat_id>")
def api_combat(combat_id):
    state = combat.load(conn(), combat_id)
    if state is None:
        raise ApiError("No such combat.", 404)
    return jsonify(state=state, order=[c["id"] for c in combat.ordered(state)])


@bp.post("/api/combats/<combat_id>/op")
def api_combat_op(combat_id):
    body = _body()
    op = body.get("op")
    if not isinstance(op, dict):
        raise ApiError("Send the operation as op.")
    if op.get("op") == "add_monster":
        monster = bestiary.get_monster(conn(), str(op.get("monster_id")))
        if monster is None:
            raise ApiError("No such monster.", 404)
        op = dict(op, statblock=monster)
    elif op.get("op") == "add_pc":
        op = dict(op, pc=_get_pc(str(op.get("pc_id"))))
    state, result = combat.act(conn(), combat_id, op, body.get("version"))
    return jsonify(state=state, order=[c["id"] for c in combat.ordered(state)], prompts=result["prompts"])


@bp.post("/api/combats/<combat_id>/undo")
def api_combat_undo(combat_id):
    state = combat.undo(conn(), combat_id)
    return jsonify(state=state, order=[c["id"] for c in combat.ordered(state)], prompts=[])


@bp.post("/api/combats/<combat_id>/sync-pcs")
def api_combat_sync(combat_id):
    """Write HP and spent counters of the PCs back to the party after the fight."""
    state = combat.load(conn(), combat_id)
    if state is None:
        raise ApiError("No such combat.", 404)
    updated = []
    for c in state["combatants"]:
        if c["kind"] != "pc" or not c.get("pc_id"):
            continue
        row = conn().execute("SELECT id, data FROM pcs WHERE id = ?", (c["pc_id"],)).fetchone()
        if row is None:
            continue
        pc = db.row_data(row)
        pc["hp_current"], pc["temp_hp"] = c["hp"], c["temp_hp"]
        spent = {r["key"]: r["spent"] for r in c["resources"]}
        for r in pc.get("resources") or []:
            if r["key"] in spent:
                r["spent"] = spent[r["key"]]
        _save_pc(pc, pc["id"])
        updated.append(pc["name"])
    return jsonify(updated=updated)


@bp.delete("/api/combats/<combat_id>")
def api_combat_delete(combat_id):
    combat.delete(conn(), combat_id)
    return jsonify(ok=True)
