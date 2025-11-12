from __future__ import annotations

import pytest

from ttrpgtools import models
from ttrpgtools.storage import character_from_dict


def make_career(name: str, advance: models.Advance) -> models.Career:
    return models.Career.from_advances(name, [advance])


def test_repeatable_advance_respects_purchase_limit() -> None:
    advance = models.Advance(
        "Sound Constitution",
        xp_cost=100,
        page=120,
        max_purchases=2,
    )
    career = make_career("Guardsman", advance)
    character = models.Character(name="Cassia", career=career, xp_total=400)

    character.purchase_advance("Sound Constitution")
    character.purchase_advance("Sound Constitution")

    assert character.xp_spent == 200

    with pytest.raises(models.PrerequisiteError):
        character.purchase_advance("Sound Constitution")


def test_character_from_dict_rejects_excess_repeat_purchases() -> None:
    advance = models.Advance(
        "Sound Constitution",
        xp_cost=100,
        page=120,
        max_purchases=1,
    )
    career = make_career("Temp Career", advance)
    key = career.name.lower()
    models.CAREERS[key] = career
    try:
        payload = {
            "name": "Rook",
            "career": career.name,
            "xp_total": 200,
            "purchases": [
                {"name": "Sound Constitution", "xp_cost": 100, "page": 120},
                {"name": "Sound Constitution", "xp_cost": 100, "page": 120},
            ],
        }

        with pytest.raises(ValueError) as excinfo:
            character_from_dict(payload)
        assert "Sound Constitution" in str(excinfo.value)
    finally:
        models.CAREERS.pop(key, None)
