"""Helpers for serialising and deserialising characters to JSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from .models import Career, Character, PrerequisiteError, get_career


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
        try:
            character.purchase_advance(advance_name, page_override=page)
        except (PrerequisiteError, KeyError) as exc:
            raise ValueError(f"Invalid advance '{advance_name}': {exc}") from exc
    return character


def save_character(character: Character, path: str | Path) -> None:
    Path(path).write_text(json.dumps(character_to_dict(character), indent=2))


def load_character(path: str | Path) -> Character:
    data = json.loads(Path(path).read_text())
    return character_from_dict(data)
