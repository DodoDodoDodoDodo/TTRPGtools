from __future__ import annotations

from ttrpgtools.dh1e.career_scheme_parser import parse_career_schemes

_SAMPLE_TEXT = """\
Table 2-4: Assassin Characteristic Advances
Characteristic Simple Intermediate Trained Expert
Weapon Skill 100 250 500 750
Fellowship N/A N/A N/A N/A
SELL-STEEL
ADVANCES
"Two in the head makes sure they're dead."
Some flavour text about killers for hire.
Advance Cost Type Prerequisites
Climb 100 S —
Sound Constitution† 100 T —
SHADESMAN
ADVANCES
"Killed 'em all with a single round."
More flavour text about shadows.
Advance Cost Type Prerequisites
Silent Move 100 S —
Catfall 100 T Ag 30
Table 2-5: Cleric Characteristic Advances
Characteristic Simple Intermediate Trained Expert
Weapon Skill 100 250 500 750
NOVICE
ADVANCES
"Prayer flavour text."
Advance Cost Type Prerequisites
Common Lore (Ecclesiarchy) 100 S —
Table 3-1: Skills
"""


def test_parse_career_schemes_splits_ranks_and_careers() -> None:
    characteristic_advances, rank_advances, skipped = parse_career_schemes(_SAMPLE_TEXT)

    assert skipped == []
    assert {entry.career for entry in characteristic_advances} == {"Assassin", "Cleric"}

    assassin_ranks = sorted({entry.rank for entry in rank_advances if entry.career == "Assassin"})
    assert assassin_ranks == ["Sell-Steel", "Shadesman"]

    assassin_advances = [entry for entry in rank_advances if entry.career == "Assassin"]

    sound_constitution = next(entry for entry in assassin_advances if entry.name == "Sound Constitution")
    assert sound_constitution.repeatable is True
    assert sound_constitution.type == "talent"

    catfall = next(entry for entry in assassin_advances if entry.name == "Catfall")
    assert catfall.prerequisites == ["Ag 30"]
    assert catfall.rank == "Shadesman"


def test_parse_career_schemes_handles_na_characteristic_cost() -> None:
    characteristic_advances, _rank_advances, _skipped = parse_career_schemes(_SAMPLE_TEXT)

    fellowship = next(
        entry
        for entry in characteristic_advances
        if entry.career == "Assassin" and entry.characteristic == "Fellowship"
    )
    assert fellowship.simple == "N/A"
