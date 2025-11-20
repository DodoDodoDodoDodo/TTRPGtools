from __future__ import annotations

from pathlib import Path

import pytest

from ttrpgtools.parsers import (
    AdvanceEntry,
    CharacteristicAdvanceEntry,
    DivinationResultEntry,
    ParseError,
    PsychicPowerEntry,
    TalentEntry,
    parse_advances_table,
    parse_characteristic_advances_table,
    parse_divination_table,
    parse_psychic_powers,
    parse_talent_prose,
    parse_talent_table,
)

ROOT = Path(__file__).resolve().parents[1]
STUFF = (ROOT / "stuff.md").read_text()


def section(start_marker: str, *, include_marker: bool = False) -> str:
    start = STUFF.index(start_marker)
    if not include_marker:
        start += len(start_marker)
    try:
        end = STUFF.index("\n---", start)
    except ValueError:
        end = len(STUFF)
    return STUFF[start:end].strip()


def test_parse_talent_table_extracts_rows() -> None:
    table_text = section("Table 4–1: Talents\n", include_marker=True)
    entries = parse_talent_table(table_text)
    assert isinstance(entries[0], TalentEntry)
    assert entries[0].name == "Air Of Authority"
    assert entries[0].prerequisites == ["Fel 30"]
    assert "Affect more targets" in entries[0].description
    assert "Air of Authority" in entries[0].raw_text
    assert entries[-1].name == "Cleanse And Purify"


def test_parse_talent_prose_supports_multiline_names() -> None:
    prose_text = section("talents text: \n\n")
    entries = parse_talent_prose(prose_text)
    names = [entry.name for entry in entries]
    assert "Ambidextrous" in names
    basic_training = next(entry for entry in entries if entry.name.startswith("Basic Weapon Training"))
    assert "Talent Groups" in basic_training.description
    catfall = next(entry for entry in entries if entry.name == "Catfall")
    assert catfall.prerequisites == ["Agility 30"]
    assert "Prerequisites:" in catfall.raw_text


def test_parse_divination_table_handles_ranges() -> None:
    divination_text = section("Table 1–18: Imperial Divination\n", include_marker=True)
    entries = parse_divination_table(divination_text)
    assert isinstance(entries[0], DivinationResultEntry)
    assert entries[0].roll_min == 1
    assert entries[0].roll_max == 1
    assert "Minor Mutation" in entries[0].effect
    last = entries[-1]
    assert last.roll_min == 98
    assert last.roll_max == 99
    assert "Weapon Skill" in last.effect


def test_parse_characteristic_advances_table_produces_entries() -> None:
    table_text = section("Table 2-6: Guardsman Characteristic Advances\n", include_marker=True)
    entries = parse_characteristic_advances_table(table_text)
    costs = {(entry.characteristic, entry.tier): entry.cost for entry in entries}
    assert costs["Weapon Skill", "Simple"] == 100
    assert costs["Strength", "Expert"] == 500
    assert costs["Intelligence", "Intermediate"] == 750


def test_parse_advances_table_converts_prerequisites() -> None:
    table_text = section("Advance Cost Type Prerequisites\n", include_marker=True)
    entries = parse_advances_table(table_text, page=123, source="Core")
    sound = next(entry for entry in entries if entry.name.startswith("Sound Constitution"))
    assert sound.prerequisites == []
    assert sound.page == 123
    pistol = next(entry for entry in entries if entry.name == "Pistol Training (Las)")
    assert pistol.cost == 100
    assert pistol.advance_type == "T"


def test_parse_psychic_powers_extracts_metadata() -> None:
    powers_text = section("psychic powers: \n\n")
    entries = parse_psychic_powers(powers_text)
    telepathy = next(entry for entry in entries if entry.name == "Telepathy")
    assert telepathy.threshold == 11
    assert "send your thoughts" in telepathy.description.lower()
    assert "THRESHOLD" in telepathy.raw_text.upper()
    terrify = next(entry for entry in entries if entry.name == "Terrify")
    assert terrify.sustain == "No"


def test_parse_invalid_block_raises() -> None:
    with pytest.raises(ParseError):
        parse_talent_table("Invalid content")
