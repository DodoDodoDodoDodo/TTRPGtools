"""Helpers for serialising and deserialising characters to JSON."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List

from .models import AdvancePurchase, Career, Character, FatePoints, PrerequisiteError, Wounds, get_career

CHARACTERS_DIR = Path(__file__).resolve().parents[2] / "characters" / "dh1e"


def character_to_dict(character: Character) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "name": character.name,
        "career": character.career.name,
        "characteristics": character.characteristics,
        "xp_total": character.xp_total,
        "insanity_points": character.insanity_points,
        "corruption_points": character.corruption_points,
        "equipment": character.equipment,
        "armour": character.armour,
        "career_path": character.career_path,
        "known_disciplines": character.known_disciplines,
        "advance_history": [
            {"name": p.name, "xp_cost": p.xp_cost, "type": p.type, "order": p.order, "direct": p.direct}
            for p in character.advance_history
        ],
    }
    if character.wounds is not None:
        payload["wounds"] = {"current": character.wounds.current, "max": character.wounds.max}
    if character.fate_points is not None:
        payload["fate_points"] = {"current": character.fate_points.current, "max": character.fate_points.max}
    if character.homeworld is not None:
        payload["homeworld"] = character.homeworld
    if character.divination is not None:
        payload["divination"] = character.divination
    return payload


def character_from_dict(payload: Dict[str, Any]) -> Character:
    career_name = payload["career"]
    career: Career = get_career(career_name)

    wounds_data = payload.get("wounds")
    fate_points_data = payload.get("fate_points")

    character = Character(
        name=payload["name"],
        career=career,
        characteristics=dict(payload.get("characteristics", {})),
        xp_total=int(payload.get("xp_total", 0)),
        wounds=Wounds(**wounds_data) if wounds_data else None,
        fate_points=FatePoints(**fate_points_data) if fate_points_data else None,
        insanity_points=int(payload.get("insanity_points", 0)),
        corruption_points=int(payload.get("corruption_points", 0)),
        homeworld=payload.get("homeworld"),
        divination=payload.get("divination"),
        equipment=list(payload.get("equipment", [])),
        armour=dict(payload.get("armour", {})),
        career_path=list(payload.get("career_path", [])),
        known_disciplines=list(payload.get("known_disciplines", [])),
    )

    for entry in payload.get("advance_history", []):
        name = entry["name"]
        try:
            if entry.get("direct"):
                # A free Psy Rating power grant or an unchecked import (see
                # Character.purchase_psy_rating / add_advance_unchecked) -- it
                # bypassed normal validation/pricing when created, so replaying
                # it through purchase_advance would wrongly re-validate rank
                # reachability or re-charge XP that was actually free. Trust and
                # replay directly instead.
                character.advance_history.append(
                    AdvancePurchase(
                        name=name,
                        xp_cost=int(entry.get("xp_cost", 0)),
                        type=entry.get("type", "talent"),
                        order=entry["order"],
                        direct=True,
                    )
                )
            elif entry.get("type") == "characteristic":
                characteristic = name.rsplit(" ", 1)[0]
                character.purchase_characteristic_advance(characteristic)
            else:
                catalog_name, choice = _split_choice(character, name)
                character.purchase_advance(catalog_name, choice=choice)
        except (PrerequisiteError, KeyError) as exc:
            raise ValueError(f"Invalid advance history entry '{name}': {exc}") from exc

    return character


def _split_choice(character: Character, display_name: str) -> tuple[str, str | None]:
    """Recover (catalog_name, choice) from a saved display name like "Minor
    Psychic Power (Healer)". Some real catalog names also end in "(...)" (e.g.
    "Common Lore (Imperium)"), so this only treats the parenthetical as a choice
    when the full string ISN'T itself a real catalog entry."""
    try:
        character.career.get_advance(display_name)
        return display_name, None
    except KeyError:
        pass
    match = re.match(r"^(.*) \(([^()]+)\)$", display_name)
    if match:
        return match.group(1), match.group(2)
    return display_name, None


def save_character(character: Character, path: str | Path) -> None:
    Path(path).write_text(json.dumps(character_to_dict(character), indent=2))


def load_character(path: str | Path) -> Character:
    data = json.loads(Path(path).read_text())
    return character_from_dict(data)


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "character"


def character_path(character_id: str, directory: str | Path = CHARACTERS_DIR) -> Path:
    return Path(directory) / f"{character_id}.json"


def new_character_id(name: str, directory: str | Path = CHARACTERS_DIR) -> str:
    """Slugify ``name`` into an id, disambiguating against existing files in ``directory``."""
    directory = Path(directory)
    base = _slugify(name)
    candidate = base
    suffix = 2
    while (directory / f"{candidate}.json").exists():
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def list_characters(directory: str | Path = CHARACTERS_DIR) -> List[Dict[str, Any]]:
    """Summaries of every character file in ``directory``, for a character list view.

    Files that fail to load (corrupt JSON, unknown career) are skipped rather than
    raised -- one bad file shouldn't take down the whole list.
    """
    directory = Path(directory)
    if not directory.exists():
        return []
    summaries = []
    for path in sorted(directory.glob("*.json")):
        try:
            character = load_character(path)
        except Exception:
            continue
        summaries.append(
            {
                "id": path.stem,
                "name": character.name,
                "career": character.career.name,
                "rank": character.current_rank,
                "xp_total": character.xp_total,
                "xp_available": character.xp_available,
            }
        )
    return summaries
