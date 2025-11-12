"""Generate a sample Dark Heresy character profile in JSON format."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


def _build_sample_character() -> Dict[str, Any]:
    """Return a ready-to-use sample character payload.

    The payload is intentionally verbose so that downstream tooling has
    everything it needs to present the character sheet without extra
    bookkeeping.  When updating XP totals we keep both the spent value and
    an "available" field to make it immediately obvious how much room the
    character has left for growth.
    """

    stats: Dict[str, int] = {
        "Weapon Skill": 45,
        "Ballistic Skill": 52,
        "Strength": 38,
        "Toughness": 41,
        "Agility": 42,
        "Intelligence": 37,
        "Perception": 43,
        "Willpower": 46,
        "Fellowship": 35,
    }

    xp_total = 1150
    xp_spent = 850

    skills: List[Dict[str, Any]] = [
        {"name": "Awareness", "status": "Trained"},
        {"name": "Command", "status": "+10"},
        {"name": "Intimidate", "status": "+5"},
        {"name": "Medicae", "status": "Trained"},
        {"name": "Parry", "status": "+10"},
        {"name": "Scrutiny", "status": "Untrained"},
    ]

    talents = [
        "Air of Authority",
        "Bolter Drill",
        "Combat Sense",
        "Iron Jaw",
        "Nerves of Steel",
        "Rapid Reload",
    ]

    equipment = [
        "Mk IX Pattern Carapace Armour",
        "Accatran Pattern Assault Bolter",
        "Melta Bomb",
        "Micro-bead",
        "Rebreather",
        "Regimental Medkit",
    ]

    armour = {
        "head": {"item": "Carapace Helmet", "ap": 6},
        "body": {"item": "Carapace Breastplate", "ap": 6},
        "arms": {"item": "Carapace Pauldrons", "ap": 5},
        "legs": {"item": "Carapace Greaves", "ap": 5},
    }

    actions: List[Dict[str, Any]] = [
        {
            "name": "Suppressing Fire",
            "type": "Full Action",
            "description": "Lay down a hail of shots with the Accatran assault bolter. Targets in the area must test Pinning.",
            "keywords": ["Ranged", "Bolter"],
        },
        {
            "name": "Coordinated Strike",
            "type": "Half Action",
            "description": "Issue battlefield orders granting +10 to allies' next Weapon Skill test against a designated enemy.",
            "keywords": ["Command", "Support"],
        },
        {
            "name": "Brace for Impact",
            "type": "Reaction",
            "description": "Spend a reaction to gain +10 to Agility tests to avoid blasts and reduce incoming damage by 2 until the start of the next turn.",
            "keywords": ["Defensive"],
        },
        {
            "name": "Vicious Riposte",
            "type": "Reaction",
            "description": "After a successful Parry, immediately make a counterattack with the combat knife at +10 Weapon Skill.",
            "keywords": ["Melee", "Counter"],
        },
    ]

    return {
        "name": "Sergeant Elara Voss",
        "career": "Soldier",
        "stats": stats,
        "xp": {
            "total": xp_total,
            "spent": xp_spent,
            "available": xp_total - xp_spent,
        },
        "skills": skills,
        "talents": talents,
        "equipment": equipment,
        "armour": armour,
        "actions": actions,
    }


def _save_character(payload: Dict[str, Any], destination: Path) -> None:
    destination.write_text(json.dumps(payload, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a sample character sheet.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("sample_character.json"),
        help="Where to write the sample JSON file (default: sample_character.json).",
    )
    args = parser.parse_args()

    character = _build_sample_character()
    _save_character(character, args.output)

    print(f"Sample character written to {args.output}.")
    print("Actions available:")
    for action in character["actions"]:
        print(f" - {action['name']} ({action['type']}): {action['description']}")


if __name__ == "__main__":
    main()
