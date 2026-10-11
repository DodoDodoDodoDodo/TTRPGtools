"""Import an existing (paper-sheet) Imperial Psyker character, reconstructed
from the player's memory of their sheet rather than a clean purchase log.

Some skill-to-rank attributions in ttrpgtools/dh1e/database/career_advances.json are known to
be unreliable in this exact area (three confirmed mis-attributions found while
building this: Tech-Priest's Mech-Wright, Imperial Psyker's Lieutenant-Savant,
and Savant Adjunct headings were all lost/misread during text extraction) --
where the real rank for a skill can't be pinned down in reasonable time, it's
recorded via ``add_advance_unchecked`` rather than blocked or guessed at.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from ttrpgtools.dh1e.models import Character, PrerequisiteError, Wounds, get_career
from ttrpgtools.dh1e.storage import character_path, new_character_id, save_character


def main() -> None:
    character = Character(
        name="Sample Psyker",
        career=get_career("Imperial Psyker"),
        # Base (unadvanced) values -- WS/S/Ag/Int/Per/Fel as given are within a
        # Void Born's 2d10+homeworld roll range and recorded as-is. BS 51, T 41,
        # and WP 61 as GIVEN exceed what's rollable (Void Born max is ~40 for
        # BS/T, ~45 for WP) -- those are base+purchased-Characteristic-Advances,
        # see below. Base values chosen here land exactly on the stated totals
        # after the advances purchased further down.
        characteristics={
            "Weapon Skill": 21, "Ballistic Skill": 36, "Strength": 22, "Toughness": 36,
            "Agility": 36, "Intelligence": 26, "Perception": 22, "Willpower": 41, "Fellowship": 22,
        },
        xp_total=7350 + 400,  # 400 = standard DH1e starting XP (core rulebook, "All characters begin play with 400 xp")
        homeworld="Void Born",
        wounds=Wounds(current=7, max=7),  # Void Born d5+6, roll of 1 -- matches stated total of 7
    )

    # Career path: Scholar Materium branch. Evidence: Psy Rating 3+4 both sit at
    # Scholar Medicae (3000-5999 XP tier), fitting the 7350 XP budget; the
    # Militant branch's equivalent (Lieutenant-Savant/Savant Adjunct) does not.
    for rank in ("Neonate", "Aspirant", "Scholar Materium", "Scholar Medicae"):
        character.advance_to_rank(rank)

    # Characteristic Advances -- bought BEFORE the Psy Rating chain below,
    # deliberately: each Psy Rating tier's free power-grant size is locked in at
    # ceil(current Willpower Bonus / 2) at the moment it's purchased ("if your
    # WP bonus later increases, you do not retroactively gain additional
    # powers" -- core rulebook, verbatim). Buying WP up to its final value first
    # means every tier's grant uses the same WP Bonus of 6 this script was
    # designed around; buying it later would under-grant powers at the earlier
    # tiers and require more separately-purchased "Psychic Power" advances.
    for _ in range(3):
        character.purchase_characteristic_advance("Ballistic Skill")  # 36 -> 51 (250+500+750)
    character.purchase_characteristic_advance("Toughness")  # 36 -> 41 (250)
    for _ in range(4):
        character.purchase_characteristic_advance("Willpower")  # 41 -> 61 (100+250+500+750)

    # Psy Rating chain + free power grants (WP Bonus 6, so ceil(6/2)=3 minor or
    # discipline powers per eligible tier -- see models._PSY_RATING_GRANTS).
    character.purchase_psy_rating(1, minor_powers=["Healer", "Precognition"])
    character.purchase_psy_rating(2)
    character.purchase_psy_rating(3, new_discipline="Telepathy", discipline_powers=["Terrify"])
    character.purchase_psy_rating(4, discipline_powers=["See Me Not", "Inspire", "Dominate"])

    # Remaining 2 Telepathy powers not covered by free grants -- bought outright.
    character.purchase_advance("Psychic Power", choice="Psychic Shriek")
    character.purchase_advance("Psychic Power", choice="Telepathy")

    # Skills confirmed on this path against the auto-parsed data.
    for name in ("Deceive", "Forbidden Lore (Psykers)", "Wrangling"):
        character.purchase_advance(name)

    # Skills confirmed against the user's own book-transcribed correction
    # (ttrpgtools/dh1e/database/imperial_psyker_verified_advances.json) once the parser's
    # Scholar Arcanum/Savant Adjunct mix-up was fixed.
    character.purchase_advance("Literacy +10")  # Aspirant
    # Invocation/Psyniscience (base) are free starting skills for every Imperial
    # Psyker (not purchasable catalog entries -- same category as Psy Rating 1),
    # required as prerequisites for their own "+10" tiers.
    character.add_advance_unchecked("Invocation", xp_cost=0, type="advance")
    character.add_advance_unchecked("Psyniscience", xp_cost=0, type="advance")
    for name in ("Invocation +10", "Psyniscience +10", "Logic"):  # Scholar Materium
        character.purchase_advance(name)

    # Skills the player remembers but whose exact rank/variant still couldn't
    # be confirmed even after the correction above -- recorded as-is via the
    # unchecked escape hatch, not blocked. Dodge and Ciphers/Common Lore DO
    # exist on this path now (Dodge at Aspirant; Ciphers (Acolyte) at Aspirant
    # or (Occult) at Scholar Materium; Common Lore (Imperial Creed)/(Imperium)
    # at Sanctionite or (Tech)/(Machine Cult) at Scholar Materium) but the
    # player specifically remembers "Dodge +10%" (only base Dodge is on this
    # path) and didn't specify a Ciphers/Common Lore variant, so those stay
    # unverified rather than guessing a specific tier/topic.
    unverified = [
        ("Dodge +10%", 100), ("Search", 100), ("Ciphers (unspecified variant)", 100),
        ("Common Lore (unspecified topic)", 100), ("Demolition", 200), ("Command", 100),
    ]
    for name, cost in unverified:
        character.add_advance_unchecked(name, xp_cost=cost, type="advance")

    character.equipment = ["Plasma Pistol", "Plasma Pistol", "Bolter"]

    character_id = new_character_id(character.name)
    save_character(character, character_path(character_id))
    print(f"Saved {character.name} -> {character_id}.json")
    print(f"XP: {character.xp_spent}/{character.xp_total} spent ({character.xp_available} remaining)")
    print(f"Career path: {' -> '.join(character.career_path)}")
    print(f"Fatigue Threshold: {character.fatigue_threshold} (should be 4)")
    print(f"Wounds: {character.wounds.current}/{character.effective_wounds_max} (should be 7/7)")


if __name__ == "__main__":
    main()
