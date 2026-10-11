from __future__ import annotations

import pytest

from ttrpgtools.dh1e import models
from ttrpgtools.dh1e.storage import character_from_dict


def make_career(name: str, advance: models.RankAdvance) -> models.Career:
    return models.Career.from_data(
        name,
        [
            {
                "name": advance.name,
                "cost": advance.cost,
                "type": advance.type,
                "prerequisites": list(advance.prerequisites),
                "repeatable": advance.repeatable,
                "rank": advance.rank,
            }
        ],
        [
            {
                "characteristic": characteristic,
                "simple": 100,
                "intermediate": 200,
                "trained": 300,
                "expert": 400,
            }
            for characteristic in models.CHARACTERISTIC_SHORT_CODES.values()
        ],
        {"root": {"name": advance.rank, "previous": [], "next": [], "xp_range": [0, 10**9]}},
    )


def test_repeatable_advance_respects_purchase_limit() -> None:
    advance = models.RankAdvance(
        "Sound Constitution", cost=100, type="talent", repeatable=True, rank="Trooper"
    )
    career = make_career("Guardsman", advance)
    character = models.Character(name="Cassia", career=career, xp_total=400)

    character.purchase_advance("Sound Constitution")
    character.purchase_advance("Sound Constitution")

    assert character.xp_spent == 200

    character.purchase_advance("Sound Constitution")
    assert character.xp_spent == 300


def test_non_repeatable_advance_can_only_be_bought_once() -> None:
    advance = models.RankAdvance("Iron Jaw", cost=100, type="talent", rank="Trooper")
    career = make_career("Guardsman", advance)
    character = models.Character(name="Cassia", career=career, xp_total=400)

    character.purchase_advance("Iron Jaw")

    with pytest.raises(models.PrerequisiteError):
        character.purchase_advance("Iron Jaw")


def test_purchase_advance_rejects_advances_outside_own_career() -> None:
    advance = models.RankAdvance("Iron Jaw", cost=100, type="talent", rank="Trooper")
    career = make_career("Guardsman", advance)
    character = models.Character(name="Cassia", career=career, xp_total=400)

    with pytest.raises(models.PrerequisiteError):
        character.purchase_advance("Something Not On This Table")


def test_characteristic_prerequisite_must_be_met() -> None:
    advance = models.RankAdvance(
        "Sharpshooter", cost=100, type="talent", prerequisites=["BS 40"], rank="Trooper"
    )
    career = make_career("Guardsman", advance)
    character = models.Character(
        name="Cassia", career=career, xp_total=400, characteristics={"Ballistic Skill": 35}
    )

    with pytest.raises(models.PrerequisiteError):
        character.purchase_advance("Sharpshooter")

    character.characteristics["Ballistic Skill"] = 40
    character.purchase_advance("Sharpshooter")
    assert character.has_advance("Sharpshooter")


def test_purchase_characteristic_advance_progresses_tiers_in_order() -> None:
    advance = models.RankAdvance("Iron Jaw", cost=100, type="talent", rank="Trooper")
    career = make_career("Guardsman", advance)
    character = models.Character(
        name="Cassia", career=career, xp_total=1000, characteristics={"Weapon Skill": 30}
    )

    character.purchase_characteristic_advance("Weapon Skill")
    assert character.effective_characteristic("Weapon Skill") == 35
    assert character.characteristics["Weapon Skill"] == 30  # base is untouched; the +5 is derived
    assert character.xp_spent == 100

    character.purchase_characteristic_advance("Weapon Skill")
    assert character.effective_characteristic("Weapon Skill") == 40
    assert character.xp_spent == 300  # 100 (simple) + 200 (intermediate)


def test_characteristic_advance_survives_reload_without_double_counting() -> None:
    """Regression test: characteristics must be stored as a base value, not the
    already-bumped current value, or replaying advance_history on load re-applies
    the +5 on top of a value that already includes it."""
    from ttrpgtools.dh1e.storage import character_from_dict, character_to_dict

    advance = models.RankAdvance("Iron Jaw", cost=100, type="talent", rank="Trooper")
    models.register_career(make_career("Test Reload Career", advance))
    character = models.Character(
        name="Cassia",
        career=models.get_career("Test Reload Career"),
        xp_total=1000,
        characteristics={"Weapon Skill": 30},
    )
    character.purchase_characteristic_advance("Weapon Skill")

    reloaded = character_from_dict(character_to_dict(character))
    assert reloaded.effective_characteristic("Weapon Skill") == 35

    reloaded_again = character_from_dict(character_to_dict(reloaded))
    assert reloaded_again.effective_characteristic("Weapon Skill") == 35


def test_undo_characteristic_advance_reverses_effective_value() -> None:
    advance = models.RankAdvance("Iron Jaw", cost=100, type="talent", rank="Trooper")
    career = make_career("Guardsman", advance)
    character = models.Character(
        name="Cassia", career=career, xp_total=1000, characteristics={"Weapon Skill": 30}
    )

    character.purchase_characteristic_advance("Weapon Skill")
    assert character.effective_characteristic("Weapon Skill") == 35

    character.undo_last_purchase()
    assert character.effective_characteristic("Weapon Skill") == 30
    assert character.xp_spent == 0


def test_character_from_dict_rejects_excess_repeat_purchases() -> None:
    advance = models.RankAdvance("Iron Jaw", cost=100, type="talent", rank="Trooper")
    career = make_career("Temp Career", advance)
    key = career.name.lower()
    models.CAREERS[key] = career
    try:
        payload = {
            "name": "Rook",
            "career": career.name,
            "xp_total": 200,
            "advance_history": [
                {"name": "Iron Jaw", "xp_cost": 100, "type": "talent", "order": 1},
                {"name": "Iron Jaw", "xp_cost": 100, "type": "talent", "order": 2},
            ],
        }

        with pytest.raises(ValueError) as excinfo:
            character_from_dict(payload)
        assert "Iron Jaw" in str(excinfo.value)
    finally:
        models.CAREERS.pop(key, None)
