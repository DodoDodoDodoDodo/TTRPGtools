"""Automatic discovery of parseable sections in full rulebook text."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Iterable, List, Sequence

from .parsers import (
    ParseError,
    parse_advances_table,
    parse_characteristic_advances_table,
    parse_divination_table,
    parse_psychic_powers,
    parse_talent_prose,
    parse_talent_table,
)


ParseFunc = Callable[..., List]


@dataclass
class _Detector:
    """Defines how to locate and parse a section within a book."""

    parser: ParseFunc
    start_finder: Callable[[Sequence[str], int], int | None]
    max_lines: int = 400


def _find_previous_table_header(lines: Sequence[str], idx: int) -> int:
    if idx > 0 and lines[idx - 1].strip().lower().startswith("table"):
        return idx - 1
    return idx


def _starts_with_header(line: str, header: str) -> bool:
    return line.strip().lower().startswith(header)


def _talent_table_start(lines: Sequence[str], idx: int) -> int | None:
    if _starts_with_header(lines[idx], "talent name"):
        return _find_previous_table_header(lines, idx)
    return None


def _advances_table_start(lines: Sequence[str], idx: int) -> int | None:
    if _starts_with_header(lines[idx], "advance cost type"):
        return _find_previous_table_header(lines, idx)
    return None


def _characteristic_table_start(lines: Sequence[str], idx: int) -> int | None:
    if re.match(r"^characteristic\s+simple\b", lines[idx].strip(), re.IGNORECASE):
        return _find_previous_table_header(lines, idx)
    return None


def _divination_table_start(lines: Sequence[str], idx: int) -> int | None:
    lowered = lines[idx].strip().lower()
    if lowered.startswith("table") and "divination" in lowered:
        return idx
    return None


def _talent_prose_start(lines: Sequence[str], idx: int) -> int | None:
    current = lines[idx].strip()
    if not current or not current.isupper():
        return None
    # Look ahead for a prerequisites stanza to avoid catching ordinary headings.
    for look_ahead in range(idx + 1, min(idx + 6, len(lines))):
        candidate = lines[look_ahead].strip()
        if not candidate:
            continue
        lowered = candidate.lower()
        if lowered.startswith("prerequisites:"):
            return idx
        if any(lowered.startswith(prefix) for prefix in ["threshold:", "focus time:", "sustain:", "range:"]):
            return None
        if candidate.isupper():
            return None
        break
    return None


def _psychic_power_start(lines: Sequence[str], idx: int) -> int | None:
    current = lines[idx].strip()
    if not current or not current.isupper():
        return None
    for look_ahead in range(idx + 1, min(idx + 8, len(lines))):
        candidate = lines[look_ahead].strip().lower()
        if not candidate:
            continue
        if any(candidate.startswith(prefix) for prefix in ["threshold:", "focus time:", "sustain:", "range:"]):
            return idx
        if ":" in candidate:
            break
    return None


_DETECTORS: list[_Detector] = [
    _Detector(parser=parse_talent_table, start_finder=_talent_table_start, max_lines=200),
    _Detector(parser=parse_talent_prose, start_finder=_talent_prose_start, max_lines=200),
    _Detector(parser=parse_advances_table, start_finder=_advances_table_start, max_lines=120),
    _Detector(
        parser=parse_characteristic_advances_table,
        start_finder=_characteristic_table_start,
        max_lines=120,
    ),
    _Detector(parser=parse_divination_table, start_finder=_divination_table_start, max_lines=120),
    _Detector(parser=parse_psychic_powers, start_finder=_psychic_power_start, max_lines=200),
]


def _next_detector_index(lines: Sequence[str], start: int, *, ignore: _Detector | None = None) -> int | None:
    for idx in range(start + 1, len(lines)):
        for detector in _DETECTORS:
            if detector is ignore:
                continue
            result = detector.start_finder(lines, idx)
            if result is not None and result != start:
                return idx
    return None


def _extract_career_from_table_header(lines: Sequence[str], start: int) -> str | None:
    """Extract career name from table headers like 'Table 2-2: Adept Characteristic Advances'."""
    for i in range(max(0, start - 5), start + 3):
        if i >= len(lines):
            break
        line = lines[i].strip()
        # Match pattern: "Table X-Y: [Career Name] Characteristic Advance"
        match = re.match(r"table\s+[\d-]+:\s+([a-z\s-]+?)\s+characteristic\s+advance", line, re.IGNORECASE)
        if match:
            return match.group(1).strip().title()
    return None


_RANK_HEADING_WORD = re.compile(r"^[A-Z][A-Z '\-]*$")
_RANK_FOLLOWUP_MARKERS = {"ADVANCES", "ADVANCE SCHEME"}
_NOT_A_RANK_NAME = {"ADVANCES", "ADVANCE", "SCHEME", "ADVANCE SCHEME"}


def _next_line_completes_scheme(lines: Sequence[str], idx: int) -> bool:
    """True if the line at ``idx`` is 'SCHEME', completing a 'ADVANCE' / 'SCHEME' wrap."""
    return idx < len(lines) and lines[idx].strip().upper().startswith("SCHEME")


def _extract_rank_from_context(lines: Sequence[str], start: int) -> str | None:
    """Extract rank name from section headers like 'ARCHIVIST\\nADVANCES' or
    'TECHNOGRAPHER\\nADVANCE SCHEME' (hyphenated ranks like 'SELL-STEEL' included).
    Also tolerates PDF line-wrap artifacts where 'ADVANCE SCHEME' itself splits
    across two lines, sometimes with 'ADVANCE' trailing onto the rank-name line."""
    for i in range(start - 1, max(0, start - 40), -1):
        line = lines[i].strip()
        if not line:
            continue
        if len(line) <= 2 or not _RANK_HEADING_WORD.match(line):
            continue
        if line.upper() in _NOT_A_RANK_NAME:
            continue

        for j in range(i + 1, min(len(lines), i + 5)):
            next_line = lines[j].strip()
            if not next_line:
                continue
            upper = next_line.upper()
            if upper in _RANK_FOLLOWUP_MARKERS:
                return line.title()
            if upper == "ADVANCE" and _next_line_completes_scheme(lines, j + 1):
                return line.title()
            # Some ranks skip the "ADVANCES" marker entirely and go straight into
            # their flavour quote (e.g. Tech-Priest's higher ranks).
            if next_line[0] in "\"'“‘":
                return line.title()
            break

        # Name itself trails " ADVANCE" (wrapped mid-name), completed by "SCHEME" next.
        if line.upper().endswith(" ADVANCE") and _next_line_completes_scheme(lines, i + 1):
            name = line[: -len(" ADVANCE")].strip()
            # The name may itself continue from a hyphen-wrapped line above (e.g.
            # "ELECTRO-" / "PRIEST ADVANCE" -> "Electro-Priest").
            if i > 0 and lines[i - 1].strip().endswith("-"):
                name = lines[i - 1].strip() + name
            return name.title()
    return None


def _try_parse_window(
    parser: ParseFunc,
    lines: Sequence[str],
    start: int,
    *,
    stop: int,
    max_lines: int,
    page: int | None,
    source: str | None,
) -> tuple[int, List] | None:
    """Return ``(end_index, entries)`` for the largest successful window before ``stop``."""

    kwargs: dict[str, int | str] = {}
    if page is not None:
        kwargs["page"] = page
    if source is not None:
        kwargs["source"] = source

    # Extract career and rank context for advance tables
    if parser == parse_characteristic_advances_table:
        career = _extract_career_from_table_header(lines, start)
        if career:
            kwargs["career"] = career
    elif parser == parse_advances_table:
        rank = _extract_rank_from_context(lines, start)
        if rank:
            kwargs["rank"] = rank
        # For advances, also try to find career from a characteristic table earlier
        career = None
        for i in range(start - 1, max(0, start - 100), -1):
            candidate_career = _extract_career_from_table_header(lines, i)
            if candidate_career:
                career = candidate_career
                break
        if career:
            kwargs["career"] = career

    last_success: tuple[int, List] | None = None
    upper_bound = min(len(lines), stop, start + max_lines)
    for end in range(start + 3, upper_bound + 1):
        window = "\n".join(lines[start:end])
        try:
            entries = parser(window, **kwargs)
        except ParseError:
            continue
        last_success = (end, entries)

    return last_success


def auto_parse_book(text: str, *, page: int | None = None, source: str | None = None) -> List:
    """Scan a whole-book text for known sections and parse them automatically."""

    lines = [line.rstrip("\n") for line in text.splitlines()]
    collected: list = []

    idx = 0
    while idx < len(lines):
        line = lines[idx]
        matched = False
        for detector in _DETECTORS:
            start = detector.start_finder(lines, idx)
            if start is None:
                continue
            stop = _next_detector_index(lines, start, ignore=detector) or len(lines)
            result = _try_parse_window(
                detector.parser,
                lines,
                start,
                stop=stop,
                max_lines=detector.max_lines,
                page=page,
                source=source,
            )
            if result is None:
                continue
            end, entries = result
            collected.extend(entries)
            idx = end
            matched = True
            break
        if not matched:
            idx += 1

    if not collected:
        raise ParseError("No recognizable sections were found in the supplied text.")

    return collected

