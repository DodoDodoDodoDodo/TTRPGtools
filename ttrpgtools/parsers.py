"""Utilities for parsing structured RPG reference text into normalized data."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Sequence

__all__ = [
    "ParseError",
    "TalentEntry",
    "AdvanceEntry",
    "CharacteristicAdvanceEntry",
    "DivinationResultEntry",
    "PsychicPowerEntry",
    "parse_talent_table",
    "parse_talent_prose",
    "parse_advances_table",
    "parse_characteristic_advances_table",
    "parse_divination_table",
    "parse_psychic_powers",
]


class ParseError(ValueError):
    """Raised when a text snippet cannot be parsed into structured data."""


@dataclass
class TalentEntry:
    """Represents a talent definition."""

    name: str
    prerequisites: List[str]
    description: str
    page: int | None = None
    source: str | None = None

    def to_dict(self) -> dict:
        payload = {
            "type": "talent",
            "name": self.name,
            "prerequisites": self.prerequisites,
            "description": self.description,
            "page": self.page,
            "source": self.source,
        }
        return {key: value for key, value in payload.items() if value is not None and value != []}


@dataclass
class AdvanceEntry:
    """Represents an advance (skill/talent purchase option)."""

    name: str
    cost: int
    advance_type: str
    prerequisites: List[str]
    page: int | None = None
    source: str | None = None

    def to_dict(self) -> dict:
        payload = {
            "type": "advance",
            "name": self.name,
            "cost": self.cost,
            "advance_type": self.advance_type,
            "prerequisites": self.prerequisites,
            "page": self.page,
            "source": self.source,
        }
        return {key: value for key, value in payload.items() if value is not None and value != []}


@dataclass
class CharacteristicAdvanceEntry:
    """Represents XP costs for characteristic advances."""

    characteristic: str
    tier: str
    cost: int
    page: int | None = None
    source: str | None = None

    def to_dict(self) -> dict:
        payload = {
            "type": "characteristic_advance",
            "characteristic": self.characteristic,
            "tier": self.tier,
            "cost": self.cost,
            "page": self.page,
            "source": self.source,
        }
        return {key: value for key, value in payload.items() if value is not None}


@dataclass
class DivinationResultEntry:
    """Represents a single divination table result."""

    roll_min: int
    roll_max: int
    quote: str
    effect: str
    page: int | None = None
    source: str | None = None

    def to_dict(self) -> dict:
        payload = {
            "type": "divination",
            "roll_min": self.roll_min,
            "roll_max": self.roll_max,
            "quote": self.quote,
            "effect": self.effect,
            "page": self.page,
            "source": self.source,
        }
        return {key: value for key, value in payload.items() if value is not None}


@dataclass
class CharacterModfierEntry:
    """Represents something that modifies a characters stats or another overriding attribute. 
    Examples are missing limbs, bionic augments, permanent effects of dark pacts."""

    modified_stat: str
    quote: str
    effect: str
    value: int
    page: int | None = None
    source: str | None = None

    def to_dict(self) -> dict:
        payload = {
            "type": "modifier_char",
            "value": self.value,
            "quote": self.quote,
            "effect": self.effect,
            "page": self.page,
            "source": self.source,
        }
        return {key: value for key, value in payload.items() if value is not None}


@dataclass
class PsychicPowerEntry:
    """Represents a psychic power definition."""

    name: str
    threshold: int
    focus_time: str
    sustain: str
    range: str
    description: str
    page: int | None = None
    source: str | None = None

    def to_dict(self) -> dict:
        payload = {
            "type": "psychic_power",
            "name": self.name,
            "threshold": self.threshold,
            "focus_time": self.focus_time,
            "sustain": self.sustain,
            "range": self.range,
            "description": self.description,
            "page": self.page,
            "source": self.source,
        }
        return {key: value for key, value in payload.items() if value is not None}


def _normalise_name(name_lines: Sequence[str]) -> str:
    raw = " ".join(line.strip() for line in name_lines if line.strip())
    tokens = raw.split()
    normalised: list[str] = []
    for token in tokens:
        cleaned = token.strip()
        if not cleaned:
            continue
        if cleaned.isupper() and len(cleaned) <= 3:
            normalised.append(cleaned)
        else:
            # Preserve characters like † or punctuation by title-casing the alpha portion.
            prefix = re.match(r"^([^A-Za-z]*)([A-Za-z\']+)(.*)$", cleaned)
            if prefix:
                lead, letters, trail = prefix.groups()
                normalised.append(f"{lead}{letters.capitalize()}{trail}")
            else:
                normalised.append(cleaned.capitalize())
    return " ".join(normalised)


def _tokenize_table_row(row: str) -> list[str]:
    tokens = row.strip().split()
    if not tokens:
        raise ParseError("Encountered an empty table row.")
    return tokens


def _score_talent_split(name_tokens: Sequence[str], prereq_tokens: Sequence[str], benefit_tokens: Sequence[str]) -> float:
    if not name_tokens or not prereq_tokens or not benefit_tokens:
        return float("-inf")

    score = 0.0

    if any(token.isdigit() for token in name_tokens):
        score -= 3
    if len(name_tokens) > 5:
        score -= 1
    if name_tokens[0][0].isupper():
        score += 1
    score += min(len(name_tokens), 4) * 0.3
    if name_tokens[-1].lower() in {"basic", "weapon", "pistol", "sound", "thrown", "drive", "training"}:
        score -= 1.5

    prereq_text = " ".join(prereq_tokens)
    if any(char.isdigit() for char in prereq_text):
        score += 2
    if "—" in prereq_text or "-" in prereq_text:
        score += 1
    if prereq_text.strip() == "—":
        score += 3
    lowered_prereq = prereq_text.lower()
    if any(
        keyword in lowered_prereq
        for keyword in [
            "training",
            "talent",
            "weapon",
            "skill",
            "bonus",
            "frenzy",
            "prerequisite",
            "acrobatic",
            "willpower",
            "agility",
            "perception",
            "strength",
            "fellowship",
            "initiative",
            "basic",
            "pistol",
            "thrown",
            "drive",
            "sound",
            "constitution",
            "fel",
            "wp",
            "bs",
            "ws",
            "per",
            "int",
            "toughness",
        ]
    ):
        score += 1.5
    if "(" in prereq_text and ")" in prereq_text:
        score += 0.5
    if len(prereq_tokens) > 8:
        score -= 1
    if len(prereq_tokens) == 1 and prereq_tokens[0].isdigit():
        score -= 2
    if len(prereq_tokens) == 1 and prereq_tokens[0] != "—":
        score -= 1

    benefit_text = " ".join(benefit_tokens)
    if benefit_text.endswith("."):
        score += 1.5
    start_word = benefit_tokens[0].strip('"“”').lower()
    if start_word in {"affect", "use", "on", "you", "heal", "gain", "re-roll", "reroll", "suffer", "remove", "reduce", "parry", "such", "whenever", "despite", "whenever", "burn!", "targets", "through", "whereas", "when"}:
        score += 1
    if any(char.isdigit() for char in benefit_text):
        score += 0.5
    if benefit_tokens[0].startswith("("):
        score -= 2

    return score


def _split_talent_row(row: str) -> tuple[str, str, str]:
    tokens = _tokenize_table_row(row)
    best: tuple[str, str, str] | None = None
    best_score = float("-inf")

    for i in range(1, len(tokens) - 1):
        for j in range(i + 1, len(tokens)):
            name_tokens = tokens[:i]
            prereq_tokens = tokens[i:j]
            benefit_tokens = tokens[j:]
            score = _score_talent_split(name_tokens, prereq_tokens, benefit_tokens)
            if score > best_score:
                best_score = score
                best = (
                    " ".join(name_tokens),
                    " ".join(prereq_tokens),
                    " ".join(benefit_tokens),
                )
    if best is None or best_score < 0:
        raise ParseError(f"Could not parse talent table row: {row!r}")
    name, prereq_text, benefit = best
    lowered_prereq = prereq_text.lower()
    if not (
        re.search(r"\d", prereq_text)
        or "—" in prereq_text
        or "talent" in lowered_prereq
        or "training" in lowered_prereq
        or "skill" in lowered_prereq
    ):
        raise ParseError(f"Unable to identify prerequisites in row: {row!r}")
    return name, prereq_text, benefit


def _split_advances_row(row: str) -> tuple[str, str, str, str]:
    tokens = _tokenize_table_row(row)
    cost_index = None
    for idx, token in enumerate(tokens):
        if re.fullmatch(r"[0-9][0-9,]*", token):
            cost_index = idx
            break
    if cost_index is None or cost_index == 0 or cost_index >= len(tokens) - 2:
        raise ParseError(f"Advance row does not contain a valid cost: {row!r}")

    name = " ".join(tokens[:cost_index])
    cost = tokens[cost_index]
    advance_type = tokens[cost_index + 1]
    prereq_tokens = tokens[cost_index + 2 :]
    prerequisites = " ".join(prereq_tokens) if prereq_tokens else "—"
    return name, cost, advance_type, prerequisites


def parse_talent_table(text: str, *, page: int | None = None, source: str | None = None) -> List[TalentEntry]:
    """Parse a compact talent table into :class:`TalentEntry` objects."""

    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    entries: list[TalentEntry] = []

    header_found = False
    row_buffer: list[str] = []
    for line in lines:
        lowered = line.lower()
        if lowered.startswith("table"):
            continue
        if not header_found:
            if re.match(r"talent\s+name", lowered):
                header_found = True
                continue
            header_found = True
        if line.startswith("---"):
            break
        row_buffer.append(line)
        candidate_row = " ".join(row_buffer)
        try:
            name, prereq_text, benefit = _split_talent_row(candidate_row)
        except ParseError:
            continue
        row_buffer.clear()
        prereqs = [item.strip().rstrip(".") for item in re.split(r",|;", prereq_text) if item.strip() and item.strip() != "—"]
        entry = TalentEntry(
            name=_normalise_name([name]),
            prerequisites=prereqs,
            description=benefit.strip(),
            page=page,
            source=source,
        )
        entries.append(entry)

    if row_buffer:
        raise ParseError(f"Unparsed content remaining in talent table: {' '.join(row_buffer)!r}")
    if not header_found or not entries:
        raise ParseError("No talent entries were parsed from the provided text.")
    return entries


def parse_talent_prose(text: str, *, page: int | None = None, source: str | None = None) -> List[TalentEntry]:
    """Parse an extended prose talent description section."""

    lines = [line.rstrip() for line in text.splitlines()]
    entries: list[TalentEntry] = []
    idx = 0

    while idx < len(lines):
        if not lines[idx].strip():
            idx += 1
            continue
        if not lines[idx].strip().isupper():
            raise ParseError(f"Expected talent name in uppercase, found: {lines[idx]!r}")

        name_lines = [lines[idx].strip()]
        idx += 1
        while idx < len(lines):
            candidate = lines[idx].strip()
            if not candidate:
                idx += 1
                continue
            if candidate.startswith("Prerequisites:"):
                break
            if candidate.isupper():
                name_lines.append(candidate)
                idx += 1
                continue
            break

        name = _normalise_name(name_lines)
        prerequisites: list[str] = []
        if idx < len(lines) and lines[idx].strip().startswith("Prerequisites:"):
            prereq_buffer = lines[idx].strip()[len("Prerequisites:") :].strip()
            idx += 1
            if not prereq_buffer.endswith('.'):
                while idx < len(lines):
                    candidate = lines[idx].strip()
                    if not candidate:
                        idx += 1
                        break
                    if candidate.isupper() and not candidate.startswith("Prerequisites:"):
                        break
                    lowered = candidate.lower()
                    if lowered.startswith(("talent groups:", "special:")):
                        break
                    if ":" in candidate:
                        break
                    prereq_buffer += " " + candidate
                    idx += 1
                    if candidate.endswith('.'):
                        break
            prerequisites = [item.strip().rstrip(".") for item in prereq_buffer.split(",") if item.strip() and item.strip() != "—"]

        description_lines: list[str] = []
        while idx < len(lines):
            candidate = lines[idx].strip()
            if not candidate:
                idx += 1
                continue
            if candidate.isupper():
                break
            description_lines.append(candidate)
            idx += 1

        description = " ".join(description_lines).replace("  ", " ").strip()
        entries.append(
            TalentEntry(
                name=name,
                prerequisites=prerequisites,
                description=description,
                page=page,
                source=source,
            )
        )

    if not entries:
        raise ParseError("No talents were discovered in the prose block.")
    return entries


def parse_advances_table(text: str, *, page: int | None = None, source: str | None = None) -> List[AdvanceEntry]:
    """Parse a table of career advances."""

    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    entries: list[AdvanceEntry] = []
    header_found = False
    for line in lines:
        lowered = line.lower()
        if lowered.startswith("table"):
            continue
        if not header_found:
            if re.match(r"advance\s+cost\s+type", lowered):
                header_found = True
                continue
            header_found = True
        if line.startswith("---"):
            break
        name, cost_text, advance_type, prereq_text = _split_advances_row(line)
        prerequisites = [item.strip().rstrip(".") for item in re.split(r",|;", prereq_text) if item.strip() and item.strip() != "—"]
        entries.append(
            AdvanceEntry(
                name=_normalise_name([name]),
                cost=int(cost_text.replace(",", "")),
                advance_type=advance_type,
                prerequisites=prerequisites,
                page=page,
                source=source,
            )
        )

    if not header_found or not entries:
        raise ParseError("No advance entries were parsed from the provided text.")
    return entries


def parse_characteristic_advances_table(
    text: str, *, page: int | None = None, source: str | None = None
) -> List[CharacteristicAdvanceEntry]:
    """Parse a table of characteristic advance costs."""

    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    entries: list[CharacteristicAdvanceEntry] = []
    tiers: Sequence[str] | None = None
    for line in lines:
        lowered = line.lower()
        if lowered.startswith("table") or lowered.startswith("characteristic"):
            tokens = line.split()
            if "Characteristic" in tokens:
                tiers = tokens[1:]
            continue
        if tiers is None:
            raise ParseError("Characteristic tiers header not found before data rows.")
        tokens = line.split()
        if len(tokens) < len(tiers) + 1:
            raise ParseError(f"Characteristic row is too short: {line!r}")
        costs_tokens = tokens[-len(tiers) :]
        name_tokens = tokens[: -len(tiers)]
        name = _normalise_name([" ".join(name_tokens)])
        for tier, cost_text in zip(tiers, costs_tokens):
            cost = int(cost_text.replace(",", ""))
            entries.append(
                CharacteristicAdvanceEntry(
                    characteristic=name,
                    tier=_normalise_name([tier]),
                    cost=cost,
                    page=page,
                    source=source,
                )
            )

    if not entries:
        raise ParseError("No characteristic advances found in the table.")
    return entries


_RANGE_PATTERN = re.compile(r"^(?P<start>\d{1,2})(?:[–-](?P<end>\d{1,2}))?$")


def _parse_roll_range(token: str) -> tuple[int, int]:
    match = _RANGE_PATTERN.match(token)
    if not match:
        raise ParseError(f"Invalid roll range token: {token!r}")
    start = int(match.group("start"))
    end = match.group("end")
    return start, int(end) if end is not None else start


def parse_divination_table(
    text: str, *, page: int | None = None, source: str | None = None
) -> List[DivinationResultEntry]:
    """Parse an Imperial Divination table."""

    lines = [line.rstrip() for line in text.splitlines()]
    entries: list[DivinationResultEntry] = []
    current_roll: tuple[int, int] | None = None
    current_text_parts: list[str] = []
    header_seen = False

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        lowered = line.lower()
        if lowered.startswith("table"):
            header_seen = True
            continue
        if not header_seen:
            continue
        if lowered.startswith("roll"):
            continue
        match = re.match(r"^(?P<range>\d{1,2}(?:[–-]\d{1,2})?)\s+(?P<text>.+)$", line)
        if match:
            if current_roll is not None:
                entries.append(_build_divination_entry(current_roll, " ".join(current_text_parts), page, source))
            current_roll = _parse_roll_range(match.group("range"))
            current_text_parts = [match.group("text").strip()]
            continue
        if current_roll is None:
            raise ParseError(f"Unexpected line in divination table: {line!r}")
        current_text_parts.append(line)

    if current_roll is not None:
        entries.append(_build_divination_entry(current_roll, " ".join(current_text_parts), page, source))

    if not entries:
        raise ParseError("No divination entries were parsed from the provided text.")
    return entries


def _build_divination_entry(
    roll: tuple[int, int],
    text: str,
    page: int | None,
    source: str | None,
) -> DivinationResultEntry:
    quote = text
    effect = ""
    quote_match = re.search(r"[\"“](.+?)[\"”]", text)
    if quote_match:
        quote = quote_match.group(1)
        effect = text[: quote_match.start()].strip() + text[quote_match.end() :].strip()
        effect = effect.strip()
    if not effect:
        # Attempt to split by first period if quotes were not found.
        parts = text.split(".", 1)
        if len(parts) == 2:
            quote = parts[0].strip("\"“” ")
            effect = parts[1].strip()
        else:
            effect = text.strip()
    return DivinationResultEntry(
        roll_min=roll[0],
        roll_max=roll[1],
        quote=quote.strip(),
        effect=effect.strip(),
        page=page,
        source=source,
    )


def parse_psychic_powers(
    text: str, *, page: int | None = None, source: str | None = None
) -> List[PsychicPowerEntry]:
    """Parse a sequence of psychic power descriptions."""

    lines = [line.rstrip() for line in text.splitlines()]
    entries: list[PsychicPowerEntry] = []
    idx = 0

    while idx < len(lines):
        if not lines[idx].strip():
            idx += 1
            continue
        if not lines[idx].strip().isupper():
            raise ParseError(f"Expected psychic power name in uppercase, found: {lines[idx]!r}")
        name_lines = [lines[idx].strip()]
        idx += 1
        while idx < len(lines):
            candidate = lines[idx].strip()
            if not candidate:
                idx += 1
                continue
            if candidate.isupper():
                name_lines.append(candidate)
                idx += 1
                continue
            break
        name = _normalise_name(name_lines)

        fields: dict[str, str] = {}
        description_lines: list[str] = []
        while idx < len(lines):
            candidate = lines[idx].strip()
            if not candidate:
                idx += 1
                continue
            lowered = candidate.lower()
            if candidate.isupper():
                break
            if ":" in candidate:
                key, value = candidate.split(":", 1)
                key_lower = key.strip().lower()
                if key_lower in {"threshold", "focus time", "sustain", "range"}:
                    fields[key_lower] = value.strip()
                    idx += 1
                    continue
            description_lines.append(candidate)
            idx += 1

        try:
            threshold_value = int(fields["threshold"].split()[0])
        except (KeyError, ValueError, IndexError) as exc:
            raise ParseError(f"Missing or invalid threshold for psychic power '{name}'.") from exc

        focus_time = fields.get("focus time", "")
        sustain = fields.get("sustain", "")
        range_ = fields.get("range", "")
        description = " ".join(description_lines).replace("  ", " ").strip()
        entries.append(
            PsychicPowerEntry(
                name=name,
                threshold=threshold_value,
                focus_time=focus_time,
                sustain=sustain,
                range=range_,
                description=description,
                page=page,
                source=source,
            )
        )

    if not entries:
        raise ParseError("No psychic powers were parsed from the provided text.")
    return entries


