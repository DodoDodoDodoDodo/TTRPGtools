"""Flask blueprint for the DCC builder and sheet, mounted under /TTRPG/dcc."""

from __future__ import annotations

import copy
import json
import random
from pathlib import Path

from flask import Blueprint, Response, abort, redirect, render_template, request, send_from_directory, url_for

from ttrpgtools import dcc, helper
from ttrpgtools.dcc import explain as dcc_explain, folio as dcc_folio, sheetfill
from ttrpgtools.permissions import require_delete
from ttrpgtools.dcc.westmarch import (clauses as town_clauses, daily as town_daily, debts as town_debts, history as town_history, items as town_items, materials as town_materials, money as town_money, places as town_places,
                         registry as town_registry, town as dcc_town, voices as town_voices)

dcc.INVENTORY_STORE = town_items.CharacterPacks  # every DCC character here belongs to the one campaign: packs go to its items table

bp = Blueprint("dcc", __name__, url_prefix="/TTRPG/dcc")

#: Page color by class: one of the six pastel "lands" of static/dcc.css. 0-level characters get the plains.
LAND = {None: "plains", "cleric": "island", "thief": "wastes", "warrior": "mountain", "wizard": "swamp",
        "dwarf": "mountain", "elf": "forest", "halfling": "plains"}


def _owner() -> str | None:
    return request.headers.get("Remote-User") or None


def _title(ch: dict) -> str:
    """What a character under the "nameless" clause is called instead of their name: their occupation."""
    return "The " + str((ch.get("occupation") or {}).get("occupation") or "Stranger")


def _nameless(ch: dict) -> bool:
    return town_clauses.clause_of(ch) == "nameless" and not dcc_town.is_judge({}, _owner())


def _shown(ch: dict) -> dict:
    """The character as this viewer may know them: under the "nameless" clause the name is the occupation."""
    return {**ch, "name": _title(ch)} if _nameless(ch) else ch


@bp.after_request
def _address_by_occupation(response):
    """The "nameless" clause: in every page and answer sent to a player, the names of their own nameless characters
    are replaced by the occupation. The admin sees real names. Files and streams pass untouched."""
    try:
        if response.direct_passthrough or response.mimetype not in ("text/html", "application/json") or dcc_town.is_judge({}, _owner()):
            return response
        names = {}
        for row in dcc.list_characters():
            if row["owner"] == _owner():
                ch = dcc.load_character(row["id"])
                if town_clauses.clause_of(ch) == "nameless":
                    names[ch["name"]] = _title(ch)
        if names:
            body = response.get_data(as_text=True)
            for name, title in names.items():
                body = body.replace(name, title).replace(json.dumps(name)[1:-1], json.dumps(title)[1:-1])
            response.set_data(body)
    except Exception:   # a page is better with a name in it than not delivered at all
        pass
    return response


def _town_gate(what: str, shops_only: bool = False) -> None:
    """Money comes from the judge, and once the town has shops, gear is bought there. Raises for anyone else."""
    with dcc_town.town() as state:
        if dcc_town.is_judge(state, _owner()) or (shops_only and not state["shops"]):
            return
    raise dcc.DCCError(f"{what} is the judge's to do." if not shops_only else f"{what}: buy in town, the shops there hold the real stock.")


def _content():
    try:
        return dcc.load_content()
    except FileNotFoundError as exc:
        abort(503, str(exc))


def _load(character_id: str) -> dict:
    try:
        path = dcc.character_path(character_id)
    except dcc.DCCError:
        abort(404)
    if not path.exists():
        abort(404)
    ch = dcc.load_character(character_id)
    owed = "tax_debt_cp" not in ch
    dcc_town.tax_debt(ch)
    if dcc_town.settle(ch) or owed:  # nights of a paid inn stay that have passed; the tax office's opening claim
        dcc.save_character(ch, character_id)
    return ch


def _back(character_id: str, error: str | None = None):
    return redirect(url_for("dcc.sheet", character_id=character_id, error=error))


@bp.get("/")
def index():
    living, dead, debt = [], [], 0
    xp_table = dcc.load_content()["xp_thresholds"] if dcc.content_available() else {}
    for row in dcc.list_characters():
        ch = dcc.load_character(row["id"])
        if ch.get("dead"):
            dead.append({**row, **ch["dead"]})
            continue
        owed = dcc_town.tax_debt(ch)
        debt += owed
        need = xp_table.get(str(int(ch["level"]) + 1))
        living.append({**row, "moon": next((m["name"] for m in town_places.MOONS if m["id"] == ch.get("moon")), ""), "purse": dcc_town.coins_text(dcc.coins_total_cp(ch["coins"])), "debt": dcc_town.coins_text(owed),
                       "xp": ch.get("xp", 0), "can_level": need is not None and int(ch.get("xp", 0)) >= need,
                       "lodging": (ch.get("lodging") or {}).get("name", "")})
    with dcc_town.town() as state:
        judge = dcc_town.is_judge(state, _owner())
    town = town_debts.town_total()
    return render_template("dcc/dcc_list.html", characters=living, graveyard=dead, fallen=town_registry.graveyard(), content_ok=dcc.content_available(),
                           total_debt=dcc_town.coins_text(town["total_cp"]), party_debt=dcc_town.coins_text(debt), town=town,
                           judge=judge, user=_owner())


@bp.route("/funnel", methods=["GET", "POST"])
def funnel():
    content = _content()
    party = None
    if request.method == "POST":
        count = max(1, min(20, int(request.form.get("count") or 4)))
        prefix = (request.form.get("prefix") or "").strip()
        alignment = request.form.get("alignment") or "neutral"
        seed = request.form.get("seed") or None
        rng = random.Random(seed) if seed else random.Random()
        party = []
        for n in range(1, count + 1):
            name = f"{prefix} {n}".strip() if prefix else f"Peasant {n}"
            ch = dcc.roll_funnel_character(rng, content, name, alignment, _owner(), [p["character"] for p in party])
            party.append({"character": ch, "view": dcc.derive(ch, content), "json": json.dumps(ch)})
    return render_template("dcc/dcc_funnel.html", party=party, alignments=dcc.ALIGNMENTS, land="plains")


@bp.post("/funnel/keep")
def funnel_keep():
    kept = 0
    last_id = None
    for raw in request.form.getlist("keep"):
        ch = json.loads(raw)
        name = (request.form.get(f"name_{ch['name']}") or ch["name"]).strip() or ch["name"]
        ch["name"] = name
        last_id = dcc.new_character_id(name)
        dcc.save_character(ch, last_id)
        kept += 1
    if kept == 1 and last_id:
        return redirect(url_for("dcc.build", character_id=last_id))
    return redirect(url_for("dcc.index"))


@bp.get("/new")
def new():
    """A character is created by taking over one of the villagers. The roll-your-own wizard stays at ?roll=1."""
    _content()
    if not request.args.get("roll"):
        return redirect(url_for("dcc.people_page"))
    return render_template("dcc/dcc_builder.html", character_id=None, start="", title="New character", land="plains")


@bp.get("/<character_id>/build")
@bp.get("/<character_id>/level-up", endpoint="level_up", defaults={"start": "level"})
def build(character_id, start=""):
    """Equipment, languages and level-up for a saved character; /level-up opens on the class or hit point step."""
    ch = _load(character_id)
    return render_template("dcc/dcc_builder.html", character_id=character_id, start=start, title=ch["name"], land=LAND[ch.get("class")])


@bp.get("/palette")
def palette():
    """Swatches of the Moebius palette and the six lands, for building pages by hand."""
    return render_template("dcc/dcc_palette.html", lands=sorted(set(LAND.values())) + ["island"], land="wastes")


@bp.get("/<character_id>")
def sheet(character_id):
    content = _content()
    ch = _load(character_id)
    if _sealed(ch):  # the sheet would tell Luck and augur: first the character is finished
        return redirect(url_for("dcc.build", character_id=character_id))
    view = dcc.derive(ch, content)
    spells = dcc.spell_list(content, ch.get("class")) if view["spellcasting"].get("caster") else []
    return render_template("dcc/dcc_sheet.html", c=ch, v=view, character_id=character_id, error=request.args.get("error"), land=LAND[ch.get("class")],
                           moon_rule=dcc_town.moon_rule(ch),
                           armor_options=content["armor"], weapon_options=content["weapons"],
                           gear_options=content["equipment"], spell_options=spells, alignments=dcc.ALIGNMENTS,
                           hit_die=dcc.HIT_DIE, labels=dcc.ABILITY_LABELS, abilities=dcc.ABILITIES,
                           crit_table=content["crit_tables"].get(view["crit_table"], []),
                           layouts=[p.stem for p in sheetfill.list_layouts(dcc.SHEETS_DIR)],
                           mercurial_table=content["mercurial_magic"], catalog=dcc.catalog(content), item_kinds=dcc.ITEM_KINDS,
                           deeds=content["mighty_deeds"] if ch.get("class") in ("warrior", "dwarf") else None)


@bp.post("/<character_id>/update")
def update(character_id):
    ch = _load(character_id)
    f = request.form
    ch["name"] = (f.get("name") or ch["name"]).strip() or ch["name"]
    ch["alignment"] = f.get("alignment") if f.get("alignment") in dcc.ALIGNMENTS else ch["alignment"]
    for key in ("hp_current", "hp_max", "luck_current", "xp", "disapproval"):
        if f.get(key, "") != "":
            ch[key] = int(f.get(key))
    for a in dcc.ABILITIES:
        if f.get(f"ability_{a}", "") != "":
            ch["abilities"][a] = max(1, min(24, int(f.get(f"ability_{a}"))))
    ch["luck_current"] = min(int(ch["luck_current"]), int(ch["abilities"]["luck"]))
    if "coin_gp" in f:
        try:
            _town_gate("Setting coins")
            with dcc_town.town(write=True) as state:
                dcc_town.fund_purse(state, ch, dcc.coins_total_cp({k: int(f.get(f"coin_{k}") or 0) for k in ("cp", "sp", "gp")}), _owner())
        except dcc.DCCError as exc:
            return _back(character_id, str(exc))
    if "armor" in f:
        ch["armor"] = f.get("armor") or None
    if "shield_field" in f:
        ch["shield"] = bool(f.get("shield"))
    for key in ("patron", "deity"):  # absent fields stay untouched, so a partial form cannot erase them
        if key in f:
            ch[key] = (f.get(key) or "").strip() or None
    if ch.get("class") in ("warrior", "dwarf") and "lucky_weapon" in f:
        ch["lucky_weapon"] = (f.get("lucky_weapon") or "").strip() or None
    if ch.get("class") == "elf" and "lucky_spell" in f:
        ch["lucky_spell"] = (f.get("lucky_spell") or "").strip() or None
    ch["notes"] = f.get("notes", ch.get("notes", ""))
    if "campaign_home" in f:
        goals = []
        for line in (f.get("campaign_goals") or "").splitlines():
            line = line.strip()
            if line:
                done = line.lower().startswith(("[x]", "x "))
                goals.append({"text": line[3:].strip() if line.lower().startswith("[x]") else line[2:].strip() if line.lower().startswith("x ") else line.lstrip("[ ]").strip(), "done": done})
        ch["campaign"] = {"name": (f.get("campaign_name") or "").strip(), "home": (f.get("campaign_home") or "").strip(),
                          "religion": (f.get("campaign_religion") or "").strip(),
                          "relations": [l.strip() for l in (f.get("campaign_relations") or "").splitlines() if l.strip()], "goals": goals}
    if "corruptions" in f:
        ch["corruptions"] = [l.strip() for l in f.get("corruptions", "").splitlines() if l.strip()]
    try:
        for a in dcc.ABILITIES:
            if f.get(f"damage_{a}", "") != "":
                dcc.set_ability_damage(ch, a, int(f.get(f"damage_{a}")))
    except dcc.DCCError as exc:
        return _back(character_id, str(exc))
    if "languages" in f:
        ch["languages"] = [l.strip() for l in f.get("languages").split(",") if l.strip()]
    if "equipment" in f:
        ch["equipment"] = [l.strip() for l in (f.get("equipment") or "").splitlines() if l.strip()]
    if "weapons" in f:
        ch["weapons"] = [l.strip() for l in (f.get("weapons") or "").splitlines() if l.strip()]
    dcc.save_character(ch, character_id)
    return _back(character_id)


@bp.post("/<character_id>/level")
def level(character_id):
    ch = _load(character_id)
    content = _content()
    klass = request.form.get("class") or ch.get("class")
    hp_roll = request.form.get("hp_roll")
    try:
        if not hp_roll:
            die = dcc.HIT_DIE[klass] if klass in dcc.HIT_DIE else 4
            hp_roll = random.randint(1, die)
        dcc.level_up(ch, klass, int(hp_roll), content)
    except (dcc.DCCError, KeyError, ValueError) as exc:
        return _back(character_id, str(exc))
    dcc.save_character(ch, character_id)
    return _back(character_id)


@bp.post("/<character_id>/spells")
def spells(character_id):
    ch = _load(character_id)
    try:
        dcc.set_spells(ch, request.form.getlist("spell"), _content())
    except dcc.DCCError as exc:
        return _back(character_id, str(exc))
    dcc.save_character(ch, character_id)
    return _back(character_id)


@bp.post("/<character_id>/inventory")
def inventory(character_id):
    ch = _load(character_id)
    content = _content()
    f = request.form
    action = f.get("action")
    try:
        if action == "add_catalog":
            _town_gate("Gear from the book", shops_only=True)
            dcc.buy_catalog(ch, content, f.get("key", ""), int(f.get("qty") or 1), pay=bool(f.get("buy")),
                            mithril=bool(f.get("mithril")))
        elif action == "add_custom":
            dcc.add_item(ch, f.get("name", ""), f.get("kind", "other"), int(f.get("qty") or 1), (f.get("cost") or "").strip() or None,
                         buy=bool(f.get("buy")), notes=(f.get("notes") or "").strip())
        elif action == "remove":
            dcc.remove_item(ch, int(f["index"]))
        elif action == "equip":
            dcc.set_equipped(ch, int(f["index"]), f.get("state") == "on")
        elif action == "qty":
            dcc.change_qty(ch, int(f["index"]), int(f.get("delta") or 0))
        elif action == "coins":
            _town_gate("Setting coins")
            with dcc_town.town(write=True) as state:
                dcc_town.fund_purse(state, ch, dcc.coins_total_cp({k: max(0, int(f.get(f"coin_{k}") or 0)) for k in ("cp", "sp", "gp")}), _owner())
        else:
            abort(400)
    except (dcc.DCCError, ValueError, KeyError) as exc:
        return _back(character_id, str(exc))
    dcc.save_character(ch, character_id)
    return _back(character_id)


@bp.post("/<character_id>/play")
def play(character_id):
    """Quick in-play actions: burn or recover Luck, spellburn, heal a day, disapproval."""
    ch = _load(character_id)
    f = request.form
    action = f.get("action")
    try:
        if action == "burn_luck":
            dcc.burn_luck(ch, int(f.get("points") or 1), _content())
        elif action == "recover_luck":
            dcc.recover_luck(ch, int(f["points"]) if f.get("points") else None)
        elif action == "spellburn":
            dcc.spellburn(ch, int(f.get("strength") or 0), int(f.get("agility") or 0), int(f.get("stamina") or 0))
        elif action == "new_day":
            dcc.rest(ch, bed_rest=bool(f.get("bed_rest")), prefer=f.get("prefer") or None)
        elif action == "failed_check":
            dcc.adjust_disapproval(ch, 1)
        elif action == "disapproval":
            dcc.adjust_disapproval(ch, int(f.get("delta") or 0))
        elif action == "hp":
            ch["hp_current"] = max(-99, min(int(ch["hp_max"]) + 50, int(ch["hp_current"]) + int(f.get("delta") or 0)))
        else:
            abort(400)
    except (dcc.DCCError, ValueError) as exc:
        return _back(character_id, str(exc))
    dcc.save_character(ch, character_id)
    return _back(character_id)


@bp.post("/<character_id>/spell-detail")
def spell_detail(character_id):
    ch = _load(character_id)
    try:
        for spell in ch.get("spells", []):
            raw = request.form.get(f"mercurial_{spell}")
            if raw is not None:
                dcc.set_spell_detail(ch, spell, int(raw) if raw.strip() else None)
    except (dcc.DCCError, ValueError) as exc:
        return _back(character_id, str(exc))
    dcc.save_character(ch, character_id)
    return _back(character_id)


@bp.get("/<character_id>/folio")
def folio(character_id):
    ch = _load(character_id)
    if _sealed(ch):
        return redirect(url_for("dcc.build", character_id=character_id))
    imposed = request.args.get("print") == "1"
    data = dcc_folio.render(_shown(ch), _content(), imposed=imposed)
    return Response(data, mimetype="application/pdf",
                    headers={"Content-Disposition": f"inline; filename={character_id}-folio{'-print' if imposed else ''}.pdf"})


@bp.get("/<character_id>/json")
def download(character_id):
    ch = _load(character_id)
    if _sealed(ch):
        return redirect(url_for("dcc.build", character_id=character_id))
    return Response(json.dumps(_shown(ch), indent=1, ensure_ascii=False), mimetype="application/json",
                    headers={"Content-Disposition": f"attachment; filename={character_id}.json"})


@bp.post("/<character_id>/delete")
def delete(character_id):
    path = dcc.character_path(character_id)
    if path.exists():
        require_delete(json.loads(path.read_text()).get("owner"))
        path.unlink()
        town_items.CharacterPacks.forget(character_id)
    return redirect(url_for("dcc.index"))


@bp.get("/<character_id>/pdf")
def pdf(character_id):
    ch = _load(character_id)
    if _sealed(ch):
        return redirect(url_for("dcc.build", character_id=character_id))
    layouts = sheetfill.list_layouts(dcc.SHEETS_DIR)
    if not layouts:
        abort(503, "No sheet layouts in content/dcc/private/sheets/.")
    wanted = request.args.get("layout")
    path = next((p for p in layouts if p.stem == wanted), layouts[0])
    layout = sheetfill.load_layout(path)
    data, mime = sheetfill.render(layout, dcc.sheet_values(ch, _content()))
    ext = "pdf" if mime == "application/pdf" else "png"
    return Response(data, mimetype=mime,
                    headers={"Content-Disposition": f"inline; filename={character_id}-{path.stem}.{ext}"})


# ------------------------------------------------------------------ JSON interface (builder, sheet overlays)
MUSIC_DIR = dcc.REPO_DIR / "content" / "dcc" / "music"
SPELL_FIELDS = ("name", "level", "class", "patron", "range", "duration", "casting_time", "save", "general", "manifestation",
                "check_penalty", "note")


#: Changes whenever a script or stylesheet of the DCC pages changes. An open page compares it with the one it started
#: with and tells the player to reload, instead of running old code against a newer server.
STATIC = Path(__file__).resolve().parents[1] / "web" / "static" / "dcc"
BUILD = str(int(max(p.stat().st_mtime for p in STATIC.glob("dcc*"))))


@bp.app_context_processor
def _assets():
    """``asset('dcc.css')`` in a template: the file's address with its change time attached. Something between this
    server and the browser keeps scripts for hours whatever the headers say; a changed file under a new address
    cannot be served from that store."""
    folder = STATIC
    return {"asset": lambda name: url_for("static", filename="dcc/" + name, v=int((folder / name).stat().st_mtime))}


def _json(payload, status=200):
    body = json.dumps(payload, ensure_ascii=False, default=lambda o: sorted(o) if isinstance(o, (set, frozenset)) else str(o))
    return Response(body, status=status, mimetype="application/json", headers={"X-DCC-Build": BUILD})


def _fail(message, status=400):
    return _json({"error": str(message)}, status)


def _sealed(ch) -> bool:
    """Luck and the birth augur of a taken villager are told only when the character is finished, that is, has
    reached 1st level. Until then no player is shown them, the owner included; the admin always is."""
    return bool(ch.get("villager")) and int(ch.get("level") or 0) == 0 and not ch.get("dead") and not dcc_town.is_judge({}, _owner())


def _seal_view(view: dict) -> dict:
    view = copy.deepcopy(view)
    for key in ("mods", "mods_text", "effective"):
        if "luck" in view.get(key, {}):
            view[key]["luck"] = None
    view.update(lucky_roll=None, augur_effect=None, augur_targets=[])
    return view


def _state(character_id, ch, content, **extra):
    """A character with everything computed; the campaign adds the character's moon and reminds of a missing choice.
    For a sealed character the Luck score and the birth augur are left out of what the browser gets."""
    view = dcc.derive(ch, content)
    bound = ch.get("moon")
    if not bound and not ch.get("dead"):
        view["todo"].append("Choose the moon this character is bound to.")
    mine = next((m for m in dcc_town.moons() if m["id"] == bound), None)
    sealed = _sealed(ch)
    if sealed:
        ch, view = copy.deepcopy(ch), _seal_view(view)
        ch["abilities"]["luck"] = ch["luck_current"] = ch["birth_augur"] = None
    return _json({"id": character_id, "character": ch, "view": view, "moon": mine, "sealed": sealed, "moon_rule": dcc_town.moon_rule(ch), **extra})


def _bind_moon(ch, moon_id, force=False):
    """The moon is chosen once, at creation; only the admin changes it afterwards."""
    if moon_id not in [m["id"] for m in town_places.MOONS]:
        raise dcc.DCCError("Choose one of the three moons.")
    if ch.get("moon") and ch["moon"] != moon_id and not force:
        _town_gate("Changing a character's moon")
    ch["moon"] = moon_id


def _spell_options(content, klass):
    return [{k: sp.get(k) for k in SPELL_FIELDS if sp.get(k) is not None} for sp in dcc.spell_list(content, klass)]


@bp.get("/api/content")
def api_content():
    """Everything the creation steps show: tables to roll on, the shop, class summaries."""
    content = _content()
    classes = {k: {"hit_die": dcc.HIT_DIE[k], "prose": content["class_prose"].get(k, {}), "row": content["classes"][k]["1"],
                   "titles": content["class_titles"].get(k, {}), "race": k if k in dcc.RACE_CLASS.values() else None,
                   "caster": dcc.CASTER_ABILITY.get(k), "starting_gold": content.get("starting_gold", {}).get(k)}
               for k in dcc.CLASSES}
    occupations = [{**o, "extras": dcc.occupation_extras(content, o)} for o in content["occupations"]]
    return _json({"abilities": dcc.ABILITIES, "labels": dcc.ABILITY_LABELS, "alignments": dcc.ALIGNMENTS,
                  "ability_mods": content["ability_mods"], "occupations": occupations, "augurs": content["luck_augurs"],
                  "equipment": content["equipment"], "catalog": dcc.catalog(content), "classes": classes,
                  "farm_animals": dcc.FARM_ANIMALS, "deities": content.get("deities", {}),
                  "weapons": [w["name"] for w in content["weapons"]], "xp": content["xp_thresholds"],
                  "lands": {k or "": v for k, v in LAND.items()}, "town": _town_summary(),
                  "moons": [{"id": m["id"], "name": m["name"], "blurb": m["blurb"]} for m in town_places.MOONS]})


@bp.get("/api/character/<character_id>")
def api_character(character_id):
    return _state(character_id, _load(character_id), _content())


@bp.post("/api/character")
def api_create():
    """Create a 0-level character from the wizard's rolls and purchases."""
    content, d = _content(), request.get_json(silent=True) or {}
    try:
        name = str(d.get("name") or "").strip()
        if not name:
            raise dcc.DCCError("The character needs a name.")
        if d.get("occupation"):
            occupation = next((o for o in content["occupations"] if o["occupation"] == d["occupation"]), None)
        else:
            roll = int(d.get("occupation_roll") or 0)
            occupation = next((o for o in content["occupations"] if o["roll"][0] <= roll <= o["roll"][1]), None)
        augur = next((a for a in content["luck_augurs"] if a["roll"] == int(d.get("augur_roll") or 0)), None)
        item = next((e for e in content["equipment"] if e["roll"] == int(d.get("equipment_roll") or 0)), None)
        if not occupation or not augur or not item:
            raise dcc.DCCError("Occupation (d100), birth augur (d30) and equipment (d24) each need a roll inside the table.")
        if not 5 <= int(d.get("copper") or 0) <= 60:
            raise dcc.DCCError("Starting copper is a 5d12 roll (5 to 60).")
        ch = dcc.new_character(name, {a: int((d.get("abilities") or {}).get(a) or 0) for a in dcc.ABILITIES},
                               {**occupation, **({"rolled": int(d["occupation_roll"])} if d.get("occupation_roll") else {})},
                               augur, int(d.get("hp_roll") or 0), int(d["copper"]), item["item"],
                               d.get("alignment") or "neutral", _owner(), content, d.get("extras") or {})
        if d.get("moon"):
            _bind_moon(ch, str(d["moon"]))
        for purchase in d.get("purchases") or []:
            _town_gate("Gear from the book", shops_only=True)
            dcc.buy_catalog(ch, content, purchase["key"], int(purchase.get("count") or 1))
        _apply_languages(ch, content, d.get("languages"))
    except (dcc.DCCError, ValueError, TypeError, KeyError) as exc:
        return _fail(exc)
    cid = dcc.new_character_id(name)
    dcc.save_character(ch, cid)
    return _state(cid, ch, content)


def _apply_languages(ch, content, languages):
    if languages is None:
        return
    slots = dcc.language_slots(ch, content)
    wanted = list(dict.fromkeys(slots["automatic"] + [str(l).strip() for l in languages if str(l).strip()]))
    if len(wanted) > slots["total"]:
        raise dcc.DCCError(f"{len(wanted)} languages chosen, {slots['total']} allowed. {slots['note']}".strip())
    ch["languages"] = wanted


def _leveled(ch, content, d):
    """Apply one level and its choices to a copy; raises DCCError and leaves the original untouched."""
    ch = copy.deepcopy(ch)
    level = int(ch["level"])
    need = content["xp_thresholds"].get(str(level + 1))
    if need is not None and int(ch["xp"]) < need:
        if not d.get("raise_xp"):
            raise dcc.DCCError(f"Level {level + 1} needs {need} XP; the character has {ch['xp']}.")
        ch["xp"] = need
    dcc.level_up(ch, d.get("class") or ch.get("class"), int(d.get("hp_roll") or 0), content)
    if d.get("gold") is not None and level == 0 and _town_summary()["judge"] and not d.get("preview"):  # ignored from anyone else
        with dcc_town.town(write=True) as state:  # starting gold is paid out of the bank's vault like any other coin
            dcc_town.move(state, "bank", "character", max(0, int(d["gold"])) * 100, ch, _owner())
    dcc.set_class_choices(ch, content, deity=d.get("deity"), patron=d.get("patron"))
    if d.get("spells") is not None:
        dcc.set_spells(ch, d["spells"], content)
    dcc.set_class_choices(ch, content, lucky_weapon=d.get("lucky_weapon"), lucky_spell=d.get("lucky_spell"))
    for spell, roll in (d.get("mercurial") or {}).items():
        dcc.set_spell_detail(ch, spell, int(roll) if roll else None, (d.get("mercurial_more") or {}).get(spell))
    _apply_languages(ch, content, d.get("languages"))
    return ch


@bp.post("/api/character/<character_id>/level")
def api_level(character_id):
    """Level up. With ``preview`` the result is computed and returned without saving."""
    content, ch, d = _content(), _load(character_id), request.get_json(silent=True) or {}
    try:
        if d.get("preview"):
            d = {**d, "raise_xp": True, "hp_roll": d.get("hp_roll") or 1}
        new = _leveled(ch, content, d)
    except (dcc.DCCError, ValueError, TypeError, KeyError) as exc:
        return _fail(exc)
    if d.get("preview"):
        klass = new["class"]
        return _state(character_id, new, content, before=_seal_view(dcc.derive(ch, content)) if _sealed(ch) else dcc.derive(ch, content),
                      spell_options=_spell_options(content, klass), hit_die=dcc.HIT_DIE[klass],
                      xp_needed=content["xp_thresholds"].get(str(new["level"])), xp=ch["xp"],
                      mercurial_table=content["mercurial_magic"] if klass in ("wizard", "elf") else None)
    dcc.save_character(new, character_id)
    return _state(character_id, new, content)


@bp.post("/api/character/<character_id>/op")
def api_op(character_id):
    """One change to a stored character: play actions, inventory, choices. Returns the new state."""
    content, ch, d = _content(), _load(character_id), request.get_json(silent=True) or {}
    op, result = d.get("op"), None
    n = lambda key, default=0: int(d.get(key) if d.get(key) not in (None, "") else default)
    try:
        if op == "hp":
            ch["hp_current"] = max(-99, min(int(ch["hp_max"]), int(ch["hp_current"]) + n("delta")))
        elif op == "xp":
            ch["xp"] = max(0, n("value"))
        elif op == "burn_luck":
            result = dcc.burn_luck(ch, n("points", 1), content)
        elif op == "recover_luck":
            result = dcc.recover_luck(ch, n("points") if d.get("points") else None)
        elif op == "spellburn":
            result = dcc.spellburn(ch, n("strength"), n("agility"), n("stamina"))
        elif op == "rest":
            result = dcc.rest(ch, bool(d.get("bed_rest")), d.get("prefer"))
        elif op == "disapproval":
            result = dcc.adjust_disapproval(ch, n("delta"))
        elif op == "reroll_augur":  # a second chance at fate, during creation only; the tax office doubles its claim each time
            before = dcc_town.tax_debt(ch)
            old = ch["birth_augur"]["roll"]
            dcc.reroll_augur(ch, content, random.choice([n for n in range(1, 31) if n != old]))
            ch["tax_debt_cp"] = before * 2
            ch["augur_rerolls"] = int(ch.get("augur_rerolls", 0)) + 1
            result = {"debt_before": before, "debt_after": before * 2}
        elif op == "reroll":  # any die rolled a second time in the builder: the tax office doubles its claim
            before = dcc_town.tax_debt(ch)
            ch["tax_debt_cp"] = before * 2
            ch["rerolls"] = int(ch.get("rerolls", 0)) + 1
            result = {"debt_before": before, "debt_after": before * 2}
        elif op == "taxes_for_no_reason":  # a rolled value was nudged by hand: up costs a fortune, down refunds one copper
            up = d.get("direction") == "up"
            ch["tax_debt_cp"] = max(0, dcc_town.tax_debt(ch) + (dcc.cost_in_cp(town_places.TAX_SURCHARGE) if up else -1))
            result = {"debt": dcc_town.coins_text(ch["tax_debt_cp"]), "direction": "up" if up else "down"}
        elif op == "die":
            if ch.get("owner") != _owner():
                _town_gate("Recording another player's death")
            if ch.get("dead"):
                raise dcc.DCCError(f"{ch['name']} is already dead.")
            with dcc_town.town(write=True) as state:  # the coins go into the library's pot, the things onto its shelves
                seized = dcc_town.pot_the_purse(state, ch)
                owed = dcc_town.tax_debt(ch)
                try:
                    pieces = dcc_town.bequeath(state, ch)
                except dcc_town.TownError:  # a town without a library: the things stay with the body
                    pieces = 0
            ch["tax_debt_cp"] = 0
            ch["dead"] = {"date": dcc_town.today().isoformat(), "cause": str(d.get("cause") or "unknown")[:200], "epitaph": str(d.get("epitaph") or "")[:200],
                          "debt_passed_on_cp": owed, "pieces_to_library": pieces, "coins_to_library_cp": seized}
            dcc.save_character(ch, character_id)   # before the debt is spread: the dead must not get a share of their own debt
            town_registry.follow_character(character_id, "dead")
            heirs = town_debts.spread(owed, skip_character=character_id)
            result = {"debt_passed_on": dcc_town.coins_text(owed), "heirs": heirs, "pieces_to_library": pieces,
                      "coins_to_library": dcc_town.coins_text(seized)}
        elif op == "revive":
            _town_gate("Bringing back the dead")
            was = ch.pop("dead", None) or {}
            dcc.save_character(ch, character_id)
            town_registry.follow_character(character_id, "alive")
            ch["tax_debt_cp"] = town_debts.gather(int(was.get("debt_passed_on_cp") or 0), for_character=character_id)  # the debt comes home; the things and the coins stay at the library
        elif op == "bleed_saved":
            dcc.saved_from_bleeding_out(ch, n("healed", 1))
        elif op == "body_recovered":
            dcc.recovered_body(ch, str(d.get("ability")))
        elif op == "ability_damage":
            dcc.set_ability_damage(ch, d.get("ability"), n("amount"))
        elif op == "buy":
            _town_gate("Gear from the book", shops_only=True)
            dcc.buy_catalog(ch, content, d.get("key", ""), n("count", 1), pay=d.get("pay", True), mithril=bool(d.get("mithril")))
        elif op == "add_item":
            dcc.add_item(ch, str(d.get("name", "")), d.get("kind", "other"), n("qty", 1), d.get("cost") or None,
                         buy=bool(d.get("pay")), notes=str(d.get("notes", "")))
        elif op == "remove_item":
            dcc.remove_item(ch, n("index"))
        elif op == "equip":
            dcc.set_equipped(ch, n("index"), bool(d.get("equipped")))
        elif op == "qty":
            dcc.change_qty(ch, n("index"), n("delta"))
        elif op == "coins":
            _town_gate("Setting coins")
            with dcc_town.town(write=True) as state:
                dcc_town.fund_purse(state, ch, dcc.coins_total_cp({k: max(0, int((d.get("coins") or {}).get(k) or 0)) for k in ("cp", "sp", "gp")}), _owner())
        elif op == "spells":
            dcc.set_spells(ch, d.get("spells") or [], content)
        elif op == "mercurial":
            dcc.set_spell_detail(ch, d.get("spell", ""), n("roll") or None, d.get("more"))
        elif op == "choices":
            dcc.set_class_choices(ch, content, d.get("lucky_weapon"), d.get("lucky_spell"), d.get("deity"), d.get("patron"))
        elif op == "languages":
            _apply_languages(ch, content, d.get("languages") or [])
        elif op == "set":
            if str(d.get("name") or "").strip():
                ch["name"] = str(d["name"]).strip()
            if d.get("alignment") in dcc.ALIGNMENTS:
                ch["alignment"] = d["alignment"]
            if d.get("moon"):
                _bind_moon(ch, str(d["moon"]))
            if "notes" in d:
                ch["notes"] = str(d["notes"])
        else:
            return _fail(f"Unknown operation {op!r}.")
    except (dcc.DCCError, ValueError, TypeError, KeyError, IndexError) as exc:
        return _fail(exc)
    dcc.save_character(ch, character_id)
    return _state(character_id, ch, content, result=result)


def _town_summary() -> dict:
    with dcc_town.town() as state:
        return {"shops": len(state["shops"]), "judge": dcc_town.is_judge(state, _owner()), "day": dcc_town.campaign_day()}


def _shoppers(state) -> list[dict]:
    """Characters this visitor may spend for: their own, or every one for the judge."""
    judge, user, out = dcc_town.is_judge(state, _owner()), _owner(), []
    for row in dcc.list_characters():
        if judge or row["owner"] == user:
            ch = _load(row["id"])
            if ch.get("dead"):
                continue
            out.append({"id": row["id"], "name": row["name"], "level": row["level"], "class": row["class"], "owner": row["owner"],
                        "coins": ch["coins"], "coins_cp": dcc.coins_total_cp(ch["coins"]), "hp": f"{ch['hp_current']}/{ch['hp_max']}",
                        "lodging": ch.get("lodging"), "moon": ch.get("moon"), "tax_debt_cp": ch["tax_debt_cp"],
                        "loans": [{"index": n, "name": i["name"]} for n, i in enumerate(dcc.ensure_inventory(ch)) if i.get("on_loan")],
                        "library_loan_cp": int(ch.get("library_loan_cp", 0)), "tax_debt": dcc_town.coins_text(ch["tax_debt_cp"]),
                        "tax_line": town_voices.tax_office(_shown(ch), dcc_town.campaign_day(), _sealed(ch))["owes"],  # the office's manner follows Luck
                        "tax_step_cp": town_clauses.SEVEN if town_clauses.clause_of(ch) == "sevens" else None,
                        "clause": town_clauses.clause_of(ch) if judge else None,   # only the admin is told
                        "roman": any(m["id"] == ch.get("moon") and m.get("numerals") == "roman" for m in town_places.MOONS),
                        "moon_rule": dcc_town.moon_rule(ch),
                        "augur": None if int(ch.get("level") or 0) < 1 else {  # what the herb woman would do about it; a level 0 augur is nobody's business yet
                            "name": ch["birth_augur"]["augur"], "modifier": int(ch["birth_augur"]["modifier"]), "has": bool(int(ch["birth_augur"].get("roll") or 0)),
                            "effect": dcc.augur_effect(ch)}})
    return out


def _town_state(state, character_id=None, **extra):
    """The town as this visitor sees it; with a shopper chosen, also what each shop would pay for their things."""
    shoppers = _shoppers(state)
    if dcc_town.is_judge(state, _owner()):  # the admin's books: where the coin is tonight, and the nightly record
        extra = {**extra, "money": {**town_money.supply(state), "tills": {s["name"]: int(s.get("till", 0)) for s in state["shops"].values() if s.get("till")},
                                    "log": state.get("money_log", [])[-15:][::-1], "price_index": dcc_town.price_index(state),
                                    "history": town_money.history(30)},
                 "goods": {"census": town_materials.census(state), "log": state.get("goods_log", [])[-15:][::-1]}}
    offers, ch = {}, None
    if character_id and any(s["id"] == character_id for s in shoppers):
        ch = _load(character_id)
        offers = dcc_town.offers(state, ch)
    return _json({**dcc_town.view(state, _owner(), ch), "characters": shoppers, "offers": offers,
                  "library_pot_cp": int(state["money"].get("library", 0)), **extra})


@bp.get("/town")
def town_page():
    _content()
    return render_template("dcc/dcc_town.html", land="island")


@bp.get("/history")
def history_page():
    _content()
    return render_template("dcc/dcc_history.html", land="wastes")


@bp.get("/api/history")
def api_history():
    """The admin's chart: every good's price and amount on the shelves, night by night, and what the caravan would be asked for."""
    with dcc_town.town() as state:
        if not dcc_town.is_judge(state, _owner()):
            return _fail("The history of the village is for the admin.", 403)
        real = dcc_town.campaign_day()
    data = town_history.series(request.args.get("since", type=int), request.args.get("until", type=int), request.args.get("points", default=700, type=int))
    return _json({**data, "real_day": real, "epoch": town_places.EPOCH.isoformat()})


@bp.get("/api/town")
def api_town():
    town_daily.ensure_on_visit()  # the first visit after the update hour starts the day's update in the background, should the timer have failed
    with dcc_town.town() as state:
        return _town_state(state, request.args.get("character"),
                           catalog=dcc.catalog(_content()) if dcc_town.is_judge(state, _owner()) else None)


@bp.post("/api/town/buy")
def api_town_buy():
    """A character buys from a shelf at today's price, or with ``index`` sells that inventory line to the shop
    at half of it. Stock, purse and pack change together."""
    d = request.get_json(silent=True) or {}
    try:
        with dcc_town.town(write=True) as state:
            character_id = str(d.get("character") or "")
            ch = _load(character_id)
            if not dcc_town.is_judge(state, _owner()) and ch.get("owner") != _owner():
                raise dcc.DCCError("That character belongs to another player.")
            receipt = None
            if d.get("borrow_coin"):
                sale = dcc_town.borrow_coin(state, ch, str(d["borrow_coin"]), _owner())
            elif d.get("repay_coin"):
                sale = dcc_town.repay_coin(state, ch, str(d["repay_coin"]), _owner())
            elif d.get("borrow"):
                sale = dcc_town.borrow(state, ch, str(d["borrow"]), _owner())
            elif d.get("give_back") is not None:
                sale = dcc_town.give_back(state, ch, int(d["give_back"]), _owner())
            elif d.get("sell_augur"):
                sale = dcc_town.sell_augur(state, str(d.get("shop")), ch, _owner())
                receipt = sale["answer"]
            elif d.get("take_augur") is not None:
                sale = dcc_town.take_augur(state, str(d.get("shop")), ch, int(d["take_augur"]), _owner())
                receipt = sale["answer"]
            elif d.get("town_note"):   # a line on the scrap of paper the whole town shares
                dcc_town.town_note_write(state, ch["name"], str(d["town_note"]))
                sale = {"item": "A line on the town note", "count": 0, "each_cp": 0}
                receipt = "Written on the town note."
            elif d.get("flavour"):   # a line of talk on the same scrap
                dcc_town.flavour_write(state, ch["name"], str(d["flavour"]))
                sale = {"item": "A line of talk on the town note", "count": 0, "each_cp": 0}
                receipt = "Written on the town note."
            elif d.get("ask_moon"):
                sale = dcc_town.ask_moon(state, str(d.get("shop")), ch, str(d["ask_moon"]), _owner())
                receipt = sale["answer"]
            elif d.get("taxes"):
                sale = dcc_town.pay_taxes(state, ch, str(d["taxes"]), _owner())
                receipt = town_voices.tax_receipt(_shown(ch), sale["each_cp"], dcc_town.campaign_day(), _sealed(ch))
            elif d.get("nights"):
                sale = dcc_town.stay(state, str(d.get("shop")), ch, int(d["nights"]), _owner())
            elif d.get("index") is not None:
                sale = dcc_town.sell(state, str(d.get("shop")), ch, int(d["index"]), int(d.get("count") or 1), _owner())
            else:
                sale = dcc_town.buy(state, str(d.get("shop")), str(d.get("item")), ch, int(d.get("count") or 1), _owner())
            dcc.save_character(ch, character_id)
            return _town_state(state, character_id, sale=sale, receipt=receipt)
    except (dcc.DCCError, ValueError, TypeError) as exc:
        return _fail(exc)


@bp.post("/api/town/judge")
def api_town_judge():
    """The judge's tools: shelves, price curves, and every character's purse."""
    d = request.get_json(silent=True) or {}
    action = d.get("action")
    qty = lambda: None if d.get("qty") in (None, "", "unlimited") else int(d["qty"])
    try:
        if action == "run_daily":  # play today's produce, making days and traders again, waiting for the model
            with dcc_town.town(write=True) as state:
                if not dcc_town.is_judge(state, _owner()):
                    return _fail("Only the judge runs the town.", 403)
                state["last_daily"] = dcc_town.campaign_day() - 1
            town_daily.ensure(background=False)
            with dcc_town.town() as state:
                return _town_state(state, d.get("character"), catalog=dcc.catalog(_content()))
        with dcc_town.town(write=True) as state:
            if not dcc_town.is_judge(state, _owner()):
                return _fail("Only the judge runs the town.", 403)
            if action == "curve":  # places themselves are fixed in westmarch/places.py; only their price curve is tuned here
                shop = dcc_town._shop(state, str(d.get("shop")))
                shop["curve"] = dcc_town.clean_curve(d.get("curve"), "shop", str(d.get("shop")))
            elif action == "stock":  # the admin's hand reaches in from outside the village: noted in the goods record
                dcc_town.stock_item(state, str(d.get("shop")), str(d.get("name") or ""), d.get("kind") or "gear",
                                    str(d.get("cost") or ""), qty(), int(d.get("units") or 1), str(d.get("detail") or ""), d.get("curve"))
                dcc_town.goods_note(state, f"{d.get('qty') or 'endless'} x {d.get('name')} put on the shelf at {dcc_town._shop(state, str(d.get('shop')))['name']}", _owner())
            elif action == "stock_book":
                dcc_town.stock_from_book(state, str(d.get("shop")), _content(), list(d.get("keys") or []), qty())
                dcc_town.goods_note(state, f"{len(d.get('keys') or [])} kind(s) from the rulebook put on the shelf at {dcc_town._shop(state, str(d.get('shop')))['name']}", _owner())
            elif action == "material":  # raw material from outside the village, or out of it
                kg = str(d.get("kg") or "").replace(",", ".")
                try:
                    kg = float(kg)
                except ValueError:
                    raise dcc.DCCError("Write the kilograms as a number, such as 12,5.")
                dcc_town.add_material(state, str(d.get("shop")), str(d.get("material")), kg, _owner())
            elif action == "item":
                dcc_town.edit_item(state, str(d.get("shop")), str(d.get("item")), qty() if "qty" in d else "keep",
                                   d.get("cost") or None, d.get("curve"))
            elif action == "remove_item":
                dcc_town.remove_item(state, str(d.get("shop")), str(d.get("item")))
            elif action == "restock":
                dcc_town.restock(state, str(d.get("shop")))
            elif action in ("issue", "retire"):  # the bank makes coin or melts it down: the one tap on the amount of money
                amount = dcc.cost_in_cp(str(d.get("amount") or ""))
                if not amount:
                    raise dcc.DCCError("Write the amount, such as 500,00 gp.")
                dcc_town.issue(state, amount if action == "issue" else -amount, _owner())
            elif action == "move":  # coin between bank, Finanzamt, a till and a character
                amount = dcc.cost_in_cp(str(d.get("amount") or ""))
                if not amount:
                    raise dcc.DCCError("Write the amount, such as 500,00 gp.")
                ch = _load(str(d.get("target"))) if "character" in (d.get("source"), d.get("to")) else None
                dcc_town.move(state, str(d.get("source")), str(d.get("to")), amount, ch, _owner())
                if ch:
                    dcc.save_character(ch, str(d.get("target")))
            elif action == "town_note":   # the admin may set the whole town note, or clear it
                state["town_note"] = "\n".join(l.strip() for l in str(d.get("text") or "").split("\n") if l.strip())
                dcc_town.town_note_write(state, "", "")
            elif action == "notice":
                text = str(d.get("text") or "").strip()
                if text:
                    state["notices"] = (state.get("notices", []) + [{"text": text[:400], "date": dcc_town.today().isoformat()}])[-20:]
            elif action == "remove_notice":
                state.get("notices", []).pop(int(d.get("index") or 0))
            elif action == "remove_news":
                state["news"] = [n for n in state.get("news", []) if n["text"] != d.get("text")]
            elif action == "debt":
                ch = _load(str(d.get("target")))
                ch["tax_debt_cp"] = max(0, dcc.cost_in_cp(str(d.get("amount") or "0 cp")) or 0)
                dcc.save_character(ch, str(d.get("target")))
            elif action == "coins":
                ch = _load(str(d.get("target")))
                total = dcc.cost_in_cp(str(d["amount"])) if d.get("amount") is not None else dcc.coins_total_cp(
                    {k: max(0, int((d.get("coins") or {}).get(k) or 0)) for k in ("cp", "sp", "gp")})
                if total is None:
                    raise dcc.DCCError("Write the purse as a sum, such as 12,50 gp.")
                dcc_town.fund_purse(state, ch, total, _owner())  # the difference comes from the bank's vault or returns to it
                dcc.save_character(ch, str(d.get("target")))
            else:
                return _fail(f"Unknown action {action!r}.")
            return _town_state(state, d.get("character"), catalog=dcc.catalog(_content()))
    except (dcc.DCCError, ValueError, TypeError, KeyError) as exc:
        return _fail(exc)


@bp.get("/api/town/items")
def api_town_items():
    """The whole items table for the admin: every stack and who holds it."""
    with dcc_town.town() as state:
        if not dcc_town.is_judge(state, _owner()):
            return _fail("Only the judge reads the ledger.", 403)
    return _json({"items": town_items.everything()})


@bp.get("/people")
def people_page():
    return render_template("dcc/dcc_registry.html", land="wastes")


@bp.route("/api/registry/<table>", methods=["GET", "POST"])
def api_registry(table):
    """Villagers ('people') or monsters. Everyone reads; the admin sets status and notes."""
    try:
        with dcc_town.town() as state:
            judge = dcc_town.is_judge(state, _owner())
            shown = {k: state.get(k) for k in ("household_mode", "households")}
        if request.method == "POST":
            d = request.get_json(silent=True) or {}
            if table == "people" and d.get("action") == "claim":  # a player creates a character by taking a villager over
                if d.get("alignment") not in dcc.ALIGNMENTS:
                    raise dcc.DCCError("Choose an alignment.")
                with dcc_town.town(write=True) as claim_state:
                    return _json({"character": town_registry.claim(int(d.get("id") or 0), _owner(), d["alignment"], str(d.get("moon")), claim_state)})
            if not judge:
                return _fail("Only the judge changes the registers.", 403)
            town_registry.update(table, int(d.get("id") or 0), d.get("status"), d.get("notes"))
        return _json({"rows": town_registry.rows(table, judge, shown), "statuses": town_registry.TABLES[table], "judge": judge,
                      "moons": [{"id": m["id"], "name": m["name"], "blurb": m["blurb"]} for m in town_places.MOONS], "alignments": dcc.ALIGNMENTS})
    except (dcc.DCCError, ValueError, TypeError, KeyError) as exc:
        return _fail(exc)


@bp.post("/api/language")
def api_language():
    """Appendix L: the language for a d% roll in a class column (null means roll again)."""
    d = request.get_json(silent=True) or {}
    try:
        return _json({"language": dcc.language_for_roll(_content(), d.get("column", "zero"), int(d.get("roll") or 0),
                                                         d.get("alignment", "neutral"))})
    except (KeyError, ValueError) as exc:
        return _fail(exc)


@bp.post("/api/explain")
def api_explain():
    """Explain a clicked page element with the local model and the rulebook passages that match it."""
    user = _owner() or ""
    out = helper.serve(dcc_explain.SITE, user, helper.premium_of(user), request.get_json(silent=True) or {})
    if isinstance(out, tuple):
        return Response(json.dumps({"error": out[0]}), status=out[1], mimetype="application/json")
    return Response(out, mimetype="text/event-stream", headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@bp.get("/music")
def music_list():
    tracks = sorted(p.name for p in MUSIC_DIR.glob("*") if p.suffix.lower() in (".mp3", ".ogg", ".m4a")) if MUSIC_DIR.is_dir() else []
    credit = MUSIC_DIR / "CREDITS.txt"
    return _json({"tracks": tracks, "credit": credit.read_text(encoding="utf-8").strip() if credit.exists() else ""})


@bp.get("/music/<path:name>")
def music_file(name):
    return send_from_directory(MUSIC_DIR, name, conditional=True)
