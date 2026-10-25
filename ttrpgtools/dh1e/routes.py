"""DH1e character pages: list, create, sheet, advances."""

from __future__ import annotations

import json

from flask import Blueprint, abort, redirect, render_template, request, url_for

from .models import (
    CAREERS,
    CHARACTERISTIC_SHORT_CODES,
    Character,
    FatePoints,
    PrerequisiteError,
    RankAdvance,
    Wounds,
    get_career,
    psy_rating_grant_info,
    psy_rating_tier,
)
from .storage import (
    character_path,
    list_characters,
    load_character,
    new_character_id,
    save_character,
)
from ttrpgtools.permissions import require_delete

bp = Blueprint("dh1e", __name__)

CHARACTERISTIC_NAMES = sorted(set(CHARACTERISTIC_SHORT_CODES.values()))

#: DH1e's 6 hit locations (Table 7-7: Hit Locations) -- (storage key, display label).
ARMOUR_LOCATIONS = [
    ("head", "Head"),
    ("body", "Body"),
    ("left_arm", "Left Arm"),
    ("right_arm", "Right Arm"),
    ("left_leg", "Left Leg"),
    ("right_leg", "Right Leg"),
]


def _sorted_careers():
    return sorted(CAREERS.values(), key=lambda career: career.name)


def _advances_by_rank(character: Character):
    """Career advances grouped by rank, annotated with purchase eligibility.

    Owned, non-repeatable advances are left out entirely -- there's nothing left
    to do with them on the picker. Only ranks the character has actually reached
    (``career_path``) are shown -- matches the gating in ``purchase_advance``.
    """
    reached = set(character.career_path)
    groups: dict[str, list[dict]] = {}
    for advance in character.career.advances.values():
        reachable = set(advance.available_ranks) or {advance.rank}
        matching = reachable & reached
        if character.career.rank_previous and not matching:
            continue
        if character.has_advance(advance.name) and not advance.repeatable:
            continue
        # Group under whichever of the character's OWN reached ranks actually
        # offers this advance -- not advance.rank, which is a career-wide
        # canonical value (e.g. always "Savant Militant" for "Minor Psychic
        # Power", its cheapest occurrence across the whole career) and would
        # otherwise show a rank heading the character never went through, for
        # any advance that recurs across multiple branches (see Career.from_data).
        display_rank = min(matching, key=character.career.rank_sort_key) if matching else advance.rank
        tier = psy_rating_tier(advance.name)
        psy_rating = None
        if tier is not None:
            grants_minor, grants_discipline, forced_choice = psy_rating_grant_info(tier)
            max_count = -(-character.characteristic_bonus("Willpower") // 2)  # ceil
            psy_rating = {
                "tier": tier,
                "grants_minor": grants_minor,
                "max_minor": max_count if grants_minor else 0,
                "grants_discipline": grants_discipline,
                "max_discipline": max_count if grants_discipline else 0,
                "forces_new_discipline": forced_choice == "new",
            }
        groups.setdefault(display_rank, []).append(
            {
                "advance": advance,
                "affordable": advance.cost <= character.xp_available,
                "missing_prerequisites": character.missing_prerequisites(advance.prerequisites),
                "psy_rating": psy_rating,
            }
        )
    _add_psy_rating_1_if_needed(character, groups)

    ordered_ranks = sorted(groups, key=lambda rank: character.career.rank_sort_key(rank))
    return [(rank, sorted(groups[rank], key=lambda a: a["advance"].name)) for rank in ordered_ranks]


def _add_psy_rating_1_if_needed(character: Character, groups: dict[str, list[dict]]) -> None:
    """Psy Rating 1 is a free starting grant with no catalog entry (see
    ``Character.purchase_psy_rating``), so it never appears in
    ``character.career.advances`` and would otherwise be unreachable through
    the GUI entirely. Inject a synthetic picker row for it, at the career's
    root rank, for any Psy-Rating-using career that hasn't taken it yet."""
    roots = character.career.root_ranks()
    if len(roots) != 1 or roots[0] not in character.career_path:
        return
    if character.has_advance("Psy Rating 1") or "Psy Rating 2" not in {a.name for a in character.career.advances.values()}:
        return
    grants_minor, grants_discipline, forced_choice = psy_rating_grant_info(1)
    max_count = -(-character.characteristic_bonus("Willpower") // 2)  # ceil
    groups.setdefault(roots[0], []).append(
        {
            "advance": RankAdvance(name="Psy Rating 1", cost=0, type="talent", rank=roots[0]),
            "affordable": True,
            "missing_prerequisites": [],
            "psy_rating": {
                "tier": 1,
                "grants_minor": grants_minor,
                "max_minor": max_count if grants_minor else 0,
                "grants_discipline": grants_discipline,
                "max_discipline": max_count if grants_discipline else 0,
                "forces_new_discipline": forced_choice == "new",
            },
        }
    )


def _characteristic_rows(character: Character):
    rows = []
    for name in CHARACTERISTIC_NAMES:
        try:
            cost = character.career.get_characteristic_cost(name)
        except KeyError:
            cost = None
        owned_tiers = sum(
            1
            for purchase in character.advance_history
            if purchase.type == "characteristic" and purchase.name.rsplit(" ", 1)[0] == name
        )
        next_tier = None
        next_cost = None
        if cost is not None and owned_tiers < 4:
            from .models import CHARACTERISTIC_TIERS

            next_tier = CHARACTERISTIC_TIERS[owned_tiers]
            next_cost = cost.cost_for(next_tier)
        base = character.characteristics.get(name, 0)
        effective = character.effective_characteristic(name)
        rows.append(
            {
                "name": name,
                "value": base,
                "effective": effective if effective != base else None,
                "next_tier": next_tier,
                "next_cost": next_cost,
                "affordable": next_cost is not None and next_cost <= character.xp_available,
            }
        )
    return rows


def _armour_rows(character: Character):
    return [
        {
            "key": key,
            "label": label,
            "item": character.armour.get(key, {}).get("item", ""),
            "ap": character.armour.get(key, {}).get("ap", 0),
        }
        for key, label in ARMOUR_LOCATIONS
    ]


def _load_or_404(character_id: str) -> Character:
    path = character_path(character_id)
    if not path.exists():
        abort(404)
    return load_character(path)


@bp.get("/TTRPG/dh1e")
def character_list():
    return render_template("dh1e/list.html", characters=list_characters())

@bp.route("/TTRPG/dh1e/new", methods=["GET", "POST"])
def new_character():
    if request.method == "POST":
        name = request.form["name"].strip()
        if not name:
            abort(400, "Name is required.")
        career = get_career(request.form["career"])
        characteristics = {
            c: int(request.form.get(f"char_{c}") or 0) for c in CHARACTERISTIC_NAMES
        }
        character = Character(
            name=name,
            career=career,
            characteristics=characteristics,
            xp_total=int(request.form.get("xp_total") or 0),
            homeworld=request.form.get("homeworld") or None,
        )
        character_id = new_character_id(name)
        save_character(character, character_path(character_id))
        return redirect(url_for("dh1e.character_sheet", character_id=character_id))
    return render_template(
        "dh1e/new.html", careers=_sorted_careers(), characteristic_names=CHARACTERISTIC_NAMES
    )

@bp.get("/TTRPG/dh1e/<character_id>")
def character_sheet(character_id):
    character = _load_or_404(character_id)
    return render_template(
        "dh1e/sheet.html",
        character=character,
        character_id=character_id,
        characteristic_rows=_characteristic_rows(character),
        armour_rows=_armour_rows(character),
        advances_by_rank=_advances_by_rank(character),
        available_next_ranks=character.available_next_ranks(),
        error=request.args.get("error"),
    )

@bp.post("/TTRPG/dh1e/<character_id>/update")
def update_character(character_id):
    character = _load_or_404(character_id)
    character.xp_total = int(request.form.get("xp_total") or character.xp_total)
    character.insanity_points = int(request.form.get("insanity_points") or 0)
    character.corruption_points = int(request.form.get("corruption_points") or 0)
    character.homeworld = request.form.get("homeworld") or None
    character.divination = request.form.get("divination") or None
    if request.form.get("wounds_max"):
        character.wounds = Wounds(
            current=int(request.form.get("wounds_current") or 0),
            max=int(request.form["wounds_max"]),
        )
    if request.form.get("fate_max"):
        character.fate_points = FatePoints(
            current=int(request.form.get("fate_current") or 0),
            max=int(request.form["fate_max"]),
        )
    for name in CHARACTERISTIC_NAMES:
        field = f"char_{name}"
        if request.form.get(field):
            character.characteristics[name] = int(request.form[field])
    character.equipment = [
        line.strip() for line in request.form.get("equipment", "").splitlines() if line.strip()
    ]
    armour = {}
    for key, _label in ARMOUR_LOCATIONS:
        item = request.form.get(f"armour_{key}_item", "").strip()
        ap = request.form.get(f"armour_{key}_ap") or 0
        if item or int(ap or 0):
            armour[key] = {"item": item, "ap": int(ap or 0)}
    character.armour = armour
    save_character(character, character_path(character_id))
    return redirect(url_for("dh1e.character_sheet", character_id=character_id))

@bp.post("/TTRPG/dh1e/<character_id>/advance-rank")
def advance_rank(character_id):
    character = _load_or_404(character_id)
    error = None
    try:
        character.advance_to_rank(request.form["rank_name"])
        save_character(character, character_path(character_id))
    except PrerequisiteError as exc:
        error = str(exc)
    return redirect(url_for("dh1e.character_sheet", character_id=character_id, error=error))

@bp.post("/TTRPG/dh1e/<character_id>/buy-advance")
def buy_advance(character_id):
    character = _load_or_404(character_id)
    error = None
    try:
        character.purchase_advance(request.form["advance_name"], choice=request.form.get("choice") or None)
        save_character(character, character_path(character_id))
    except PrerequisiteError as exc:
        error = str(exc)
    return redirect(url_for("dh1e.character_sheet", character_id=character_id, error=error))

@bp.post("/TTRPG/dh1e/<character_id>/buy-psy-rating")
def buy_psy_rating(character_id):
    character = _load_or_404(character_id)
    error = None

    def _split(field: str) -> list[str]:
        return [p.strip() for p in request.form.get(field, "").split(",") if p.strip()]

    try:
        character.purchase_psy_rating(
            int(request.form["tier"]),
            new_discipline=request.form.get("new_discipline") or None,
            discipline_powers=_split("discipline_powers"),
            minor_powers=_split("minor_powers"),
        )
        save_character(character, character_path(character_id))
    except PrerequisiteError as exc:
        error = str(exc)
    return redirect(url_for("dh1e.character_sheet", character_id=character_id, error=error))

@bp.post("/TTRPG/dh1e/<character_id>/buy-characteristic")
def buy_characteristic(character_id):
    character = _load_or_404(character_id)
    error = None
    try:
        character.purchase_characteristic_advance(request.form["characteristic"])
        save_character(character, character_path(character_id))
    except PrerequisiteError as exc:
        error = str(exc)
    return redirect(url_for("dh1e.character_sheet", character_id=character_id, error=error))

@bp.post("/TTRPG/dh1e/<character_id>/undo")
def undo_purchase(character_id):
    character = _load_or_404(character_id)
    error = None
    try:
        character.undo_last_purchase()
        save_character(character, character_path(character_id))
    except PrerequisiteError as exc:
        error = str(exc)
    return redirect(url_for("dh1e.character_sheet", character_id=character_id, error=error))

@bp.post("/TTRPG/dh1e/<character_id>/delete")
def delete_character(character_id):
    _load_or_404(character_id)
    require_delete(json.loads(character_path(character_id).read_text()).get("owner"))
    character_path(character_id).unlink()
    return redirect(url_for("dh1e.character_list"))
