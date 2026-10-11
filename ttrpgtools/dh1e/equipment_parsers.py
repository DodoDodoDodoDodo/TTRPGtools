"""Parsers for equipment, weapons, and armor."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List


class ParseError(ValueError):
    """Raised when equipment text cannot be parsed."""


@dataclass
class RangedWeaponEntry:
    """Represents a ranged weapon."""

    name: str
    weapon_class: str  # Pistol, Basic, Heavy, Thrown
    range: str
    rof: str  # Rate of Fire
    damage: str
    penetration: str
    clip: str
    reload: str
    special: str
    weight: str
    cost: str
    availability: str
    page: int | None = None
    source: str | None = None
    full_description: str | None = None

    def to_dict(self) -> dict:
        payload = {
            "type": "ranged_weapon",
            "name": self.name,
            "class": self.weapon_class,
            "range": self.range,
            "rof": self.rof,
            "damage": self.damage,
            "penetration": self.penetration,
            "clip": self.clip,
            "reload": self.reload,
            "special": self.special,
            "weight": self.weight,
            "cost": self.cost,
            "availability": self.availability,
            "page": self.page,
            "source": self.source,
            "full_description": self.full_description,
        }
        return {k: v for k, v in payload.items() if v is not None}


@dataclass
class MeleeWeaponEntry:
    """Represents a melee weapon."""

    name: str
    weapon_class: str  # Melee, Melee/Thrown
    range: str  # For thrown weapons
    damage: str
    penetration: str
    special: str
    weight: str
    cost: str
    availability: str
    page: int | None = None
    source: str | None = None
    full_description: str | None = None

    def to_dict(self) -> dict:
        payload = {
            "type": "melee_weapon",
            "name": self.name,
            "class": self.weapon_class,
            "range": self.range,
            "damage": self.damage,
            "penetration": self.penetration,
            "special": self.special,
            "weight": self.weight,
            "cost": self.cost,
            "availability": self.availability,
            "page": self.page,
            "source": self.source,
            "full_description": self.full_description,
        }
        return {k: v for k, v in payload.items() if v is not None}


@dataclass
class ArmourEntry:
    """Represents armor."""

    name: str
    armour_type: str  # Type/category
    locations: str  # Body parts covered
    ap: str  # Armor points
    weight: str
    cost: str
    availability: str
    page: int | None = None
    source: str | None = None
    full_description: str | None = None

    def to_dict(self) -> dict:
        payload = {
            "type": "armour",
            "name": self.name,
            "armour_type": self.armour_type,
            "locations": self.locations,
            "ap": self.ap,
            "weight": self.weight,
            "cost": self.cost,
            "availability": self.availability,
            "page": self.page,
            "source": self.source,
            "full_description": self.full_description,
        }
        return {k: v for k, v in payload.items() if v is not None}


def parse_ranged_weapons_table(
    text: str,
    *,
    page: int | None = None,
    source: str | None = None,
) -> List[RangedWeaponEntry]:
    """Parse a ranged weapons table."""

    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    entries: list[RangedWeaponEntry] = []
    header_found = False

    for line in lines:
        lowered = line.lower()

        # Skip table headers and category headers
        if 'table' in lowered or lowered.startswith('name') or 'weapons' in lowered:
            header_found = True
            continue

        if not header_found:
            continue

        # Try to parse weapon row
        # Format: Name Class Range RoF Dam Pen Clip Rld Special Wt Cost Availability
        tokens = line.split()
        if len(tokens) < 11:
            continue

        # Name might be multiple words - find where class starts
        # Class is usually: Pistol, Basic, Heavy, Thrown
        class_idx = None
        for i, tok in enumerate(tokens):
            if tok in ['Pistol', 'Basic', 'Heavy', 'Thrown']:
                class_idx = i
                break

        if class_idx is None or class_idx == 0:
            continue

        name = ' '.join(tokens[:class_idx])
        weapon_class = tokens[class_idx]

        # Parse rest of fields
        remaining = tokens[class_idx + 1:]
        if len(remaining) < 10:
            continue

        range_val = remaining[0]
        rof = remaining[1]
        damage = remaining[2]
        pen = remaining[3]
        clip = remaining[4]
        reload = remaining[5]

        # Special qualities might be multiple words or "—"
        # Find where weight starts (ends with 'kg')
        wt_idx = None
        for i in range(6, len(remaining)):
            if 'kg' in remaining[i]:
                wt_idx = i
                break

        if wt_idx is None:
            continue

        special = ' '.join(remaining[6:wt_idx]) if wt_idx > 6 else '—'
        weight = remaining[wt_idx]

        # Cost and availability are last two
        if len(remaining) < wt_idx + 3:
            continue

        cost = remaining[wt_idx + 1]
        availability = ' '.join(remaining[wt_idx + 2:])

        entries.append(
            RangedWeaponEntry(
                name=name,
                weapon_class=weapon_class,
                range=range_val,
                rof=rof,
                damage=damage,
                penetration=pen,
                clip=clip,
                reload=reload,
                special=special,
                weight=weight,
                cost=cost,
                availability=availability,
                page=page,
                source=source,
            )
        )

    if not entries:
        raise ParseError("No ranged weapons found in table.")
    return entries


def parse_melee_weapons_table(
    text: str,
    *,
    page: int | None = None,
    source: str | None = None,
) -> List[MeleeWeaponEntry]:
    """Parse a melee weapons table."""

    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    entries: list[MeleeWeaponEntry] = []
    header_found = False

    for line in lines:
        lowered = line.lower()

        # Skip headers
        if 'table' in lowered or lowered.startswith('name') or 'weapons' in lowered:
            header_found = True
            continue

        if not header_found:
            continue

        # Format: Name Class Range Dam Pen Special Wt Cost Availability
        tokens = line.split()
        if len(tokens) < 8:
            continue

        # Find class (Melee, Melee/Thrown, Thrown)
        class_idx = None
        for i, tok in enumerate(tokens):
            if 'melee' in tok.lower() or tok == 'Thrown':
                class_idx = i
                break

        if class_idx is None or class_idx == 0:
            continue

        name = ' '.join(tokens[:class_idx])
        weapon_class = tokens[class_idx]

        remaining = tokens[class_idx + 1:]
        if len(remaining) < 7:
            continue

        range_val = remaining[0]
        damage = remaining[1]
        pen = remaining[2]

        # Find weight (ends with 'kg')
        wt_idx = None
        for i in range(3, len(remaining)):
            if 'kg' in remaining[i]:
                wt_idx = i
                break

        if wt_idx is None:
            continue

        special = ' '.join(remaining[3:wt_idx]) if wt_idx > 3 else '—'
        weight = remaining[wt_idx]

        if len(remaining) < wt_idx + 3:
            continue

        cost = remaining[wt_idx + 1]
        availability = ' '.join(remaining[wt_idx + 2:])

        entries.append(
            MeleeWeaponEntry(
                name=name,
                weapon_class=weapon_class,
                range=range_val,
                damage=damage,
                penetration=pen,
                special=special,
                weight=weight,
                cost=cost,
                availability=availability,
                page=page,
                source=source,
            )
        )

    if not entries:
        raise ParseError("No melee weapons found in table.")
    return entries


def parse_armour_table(
    text: str,
    *,
    page: int | None = None,
    source: str | None = None,
) -> List[ArmourEntry]:
    """Parse an armour table."""

    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    entries: list[ArmourEntry] = []
    header_found = False
    current_type = None

    for line in lines:
        lowered = line.lower()

        # Skip table header
        if 'table' in lowered or lowered.startswith('armour type'):
            header_found = True
            continue

        if not header_found:
            continue

        # Track armor category headers
        if 'armour' in lowered and len(line.split()) <= 3:
            current_type = line.strip()
            continue

        # Format: Name Locations AP Wt Cost Availability
        tokens = line.split()
        if len(tokens) < 5:
            continue

        # Find AP (should be a number)
        ap_idx = None
        for i, tok in enumerate(tokens):
            if tok.replace(',', '').isdigit() and i > 0:
                ap_idx = i
                break

        if ap_idx is None or ap_idx == 0:
            continue

        name = ' '.join(tokens[:ap_idx - 1])
        locations = tokens[ap_idx - 1]
        ap = tokens[ap_idx]

        remaining = tokens[ap_idx + 1:]
        if len(remaining) < 3:
            continue

        weight = remaining[0]
        cost = remaining[1]
        availability = ' '.join(remaining[2:])

        entries.append(
            ArmourEntry(
                name=name,
                armour_type=current_type or "Unknown",
                locations=locations,
                ap=ap,
                weight=weight,
                cost=cost,
                availability=availability,
                page=page,
                source=source,
            )
        )

    if not entries:
        raise ParseError("No armour found in table.")
    return entries
