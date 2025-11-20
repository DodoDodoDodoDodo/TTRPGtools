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

