"""Lightweight parsers for loosely structured reference blocks.

These helpers are intentionally permissive so that we can iterate on
parsing for new rulebook sections (items, equipment, skills, careers,
monsters) without needing to change the main parser implementations.
Every entry retains the original ``raw_text`` to make post-processing
and manual clean-up straightforward.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List

__all__ = [
    "BlockEntry",
    "parse_named_blocks",
    "parse_equipment_blocks",
    "parse_item_blocks",
    "parse_skill_blocks",
    "parse_career_blocks",
    "parse_monster_blocks",
    "write_entries",
]


@dataclass
class BlockEntry:
    """Generic parsed block with optional structured attributes."""

    kind: str
    name: str
    description: str
    attributes: Dict[str, str]
    raw_text: str

    def to_dict(self) -> dict:
        payload = {
            "type": self.kind,
            "name": self.name,
            "description": self.description,
            "attributes": self.attributes,
            "raw_text": self.raw_text,
        }
        return payload


def _split_blocks(text: str) -> Iterable[list[str]]:
    buffer: list[str] = []
    for line in text.splitlines():
        if line.strip():
            buffer.append(line.rstrip())
            continue
        if buffer:
            yield buffer
            buffer = []
    if buffer:
        yield buffer


def parse_named_blocks(text: str, *, kind: str, default_attributes: Iterable[str] | None = None) -> List[BlockEntry]:
    """Parse simple name-first blocks separated by blank lines.

    The first non-empty line becomes the name. Lines containing a ``:``
    are treated as key/value metadata. Remaining lines join into the
    description. Unknown metadata keys are kept verbatim so later passes
    can refine them.
    """

    default_keys = {key.lower(): key for key in default_attributes or []}
    entries: list[BlockEntry] = []
    for block in _split_blocks(text):
        if not block:
            continue
        name = block[0].strip()
        attributes: Dict[str, str] = {}
        description_lines: list[str] = []
        for line in block[1:]:
            if ":" in line:
                key, value = line.split(":", 1)
                normalised_key = default_keys.get(key.strip().lower(), key.strip())
                attributes[normalised_key] = value.strip()
                continue
            # Attempt to capture inline cost/weight style metadata.
            match = re.match(r"^(?P<label>[A-Za-z][\w ]+)\s+[-–]\s+(?P<value>.+)$", line)
            if match:
                label = match.group("label").strip()
                normalised_key = default_keys.get(label.lower(), label)
                attributes[normalised_key] = match.group("value").strip()
                continue
            description_lines.append(line.strip())
        raw_text = "\n".join(block).strip()
        description = " ".join(description_lines).strip()
        entries.append(
            BlockEntry(
                kind=kind,
                name=name,
                description=description,
                attributes=attributes,
                raw_text=raw_text,
            )
        )
    return entries


def parse_equipment_blocks(text: str) -> List[BlockEntry]:
    return parse_named_blocks(text, kind="equipment", default_attributes=["Availability", "Weight", "Cost", "Range"])


def parse_item_blocks(text: str) -> List[BlockEntry]:
    return parse_named_blocks(text, kind="item", default_attributes=["Availability", "Weight", "Cost"])


def parse_skill_blocks(text: str) -> List[BlockEntry]:
    return parse_named_blocks(text, kind="skill", default_attributes=["Characteristic", "Use"])


def parse_career_blocks(text: str) -> List[BlockEntry]:
    return parse_named_blocks(text, kind="career-path", default_attributes=["Entry", "Exit", "Aptitudes"])


def parse_monster_blocks(text: str) -> List[BlockEntry]:
    return parse_named_blocks(text, kind="monster-statblock", default_attributes=["Traits", "Skills", "Weapons", "Armour", "Wounds"])


def write_entries(entries: Iterable[BlockEntry], output: str | Path) -> None:
    Path(output).write_text(json.dumps([entry.to_dict() for entry in entries], indent=2, sort_keys=True))
