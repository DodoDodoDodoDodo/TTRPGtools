"""Helpers for serialising and deserialising characters to JSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from .models import AdvancePurchase, Career, Character, get_career


def character_to_dict(character: Character) -> Dict[str, Any]:
    return {
        "name": character.name,
        "career": character.career.name,
        "xp_total": character.xp_total,
        "purchases": [
            {"name": purchase.name, "xp_cost": purchase.xp_cost, "page": purchase.page}
            for purchase in character.purchases
        ],
    }


def character_from_dict(payload: Dict[str, Any]) -> Character:
    career_name = payload["career"]
    career: Career = get_career(career_name)
    character = Character(
        name=payload["name"],
        career=career,
        xp_total=int(payload.get("xp_total", 0)),
    )
    for purchase_data in payload.get("purchases", []):
        advance_name = purchase_data["name"]
        page = int(purchase_data.get("page"))
        # Validate against career definition and prerequisites.
        advance = career.get_advance(advance_name)
        missing = advance.missing_prerequisites(p.name for p in character.purchases)
        if missing:
            raise ValueError(
                f"Advance '{advance.name}' is missing prerequisites: {', '.join(missing)}"
            )
        character.purchases.append(
            AdvancePurchase(name=advance.name, xp_cost=advance.xp_cost, page=page)
        )
    if character.xp_spent > character.xp_total:
        raise ValueError(
            f"Character spends {character.xp_spent} XP but only has {character.xp_total}."
        )
    return character


def save_character(character: Character, path: str | Path) -> None:
    Path(path).write_text(json.dumps(character_to_dict(character), indent=2))


def load_character(path: str | Path) -> Character:
    data = json.loads(Path(path).read_text())
    return character_from_dict(data)
