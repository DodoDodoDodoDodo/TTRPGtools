"""Parses per-career DH1e advance schemes (characteristic costs and rank advance
tables) directly out of the raw core rulebook text.

Unlike ``book_import.auto_parse_book`` (which scans the whole book without chapter
context and only recovers career attribution via a short backward search), this
module locates each career's chapter explicitly using its "Table 2-N: <Career>
Characteristic Advances" header, then walks the chapter with its own rank-heading
detector (deliberately not shared with ``book_import``'s -- that one only needs the
single nearest heading for a given table, this one needs every heading in the
chapter, including ones that never get a table of their own).

Rank structure (the chart of which ranks exist, their XP thresholds, and how they
branch) is NOT parsed here anymore -- an earlier version tried to reconstruct it
from this text (first as inferred parent-rank adjacency, then as a scraped
"XP Level:" chart) and got it wrong both times: e.g. it read Tech-Priest's
"Mech-Wright" and "Electro-Priest" as sibling branches of one tier, when they're
actually two solo, consecutive tiers. ``database/career_ranks.json`` is now a
hand-verified external file (a real branching tree with previous/next/xp_range
per rank) and is the sole source of truth for rank structure -- see
``models.Career.from_data``, which matches each advance row's heading-walked
``rank`` name onto its canonical tree equivalent (e.g. "Cyber Seer" -> "Cyber-Seer").

Some ranks still have zero recoverable advances (their table apparently never
survived extraction at all, e.g. Tech-Priest's "Mech-Wright") -- that's fine,
they still exist in the external rank tree, just with nothing purchasable.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List

from .parsers import ParseError, _normalise_name, _split_advances_row

__all__ = [
    "CareerCharacteristicAdvance",
    "CareerAdvance",
    "parse_career_schemes",
    "regenerate_database_files",
]

_CHAPTER_HEADER = re.compile(r"^Table\s+2-\d+:\s+(.+?)\s+Characteristic Advances\s*$")
_NEXT_CHAPTER_HEADER = re.compile(r"^Table\s+3-\d+:")
_ADVANCE_ROW_HEADER = re.compile(r"^advance\s+cost\s+type\s+prerequisites", re.IGNORECASE)
_BARE_PAGE_NUMBER = re.compile(r"^\d{1,3}$")

# -- Rank heading detection ---------------------------------------------------
# Forked from (not shared with) book_import._extract_rank_from_context: that
# function returns only the single nearest heading before a given position; this
# module needs every heading in a chapter, including ones that never get a table.
_RANK_HEADING_WORD = re.compile(r"^[A-Z][A-Z '\-]*$")
_RANK_FOLLOWUP_MARKERS = {"ADVANCES", "ADVANCE SCHEME"}
_NOT_A_RANK_NAME = {"ADVANCES", "ADVANCE", "SCHEME", "ADVANCE SCHEME"}


def _heading_at(lines: List[str], i: int) -> tuple[str, int] | None:
    """Return (rank name, lines consumed) if a heading block starts at line
    ``i``, else None. ``consumed`` matters to the caller (``_find_rank_headings``)
    so it can skip past the lines a multi-line heading swallowed -- otherwise
    the second line of a wrapped name (e.g. "ARCANUM" in "SCHOLAR"/"ARCANUM")
    gets independently re-detected as its own spurious one-word heading right
    after the real one, and immediately overwrites it as the "current rank"
    before any of its table rows are consumed.

    Several physical layouts show up in the extracted text for the same logical
    heading ("<NAME>\\nADVANCE SCHEME" or "<NAME>\\nADVANCES"), plus line-wrap
    variants: "ADVANCE SCHEME" itself splitting across two lines, sometimes with
    "ADVANCE" trailing onto the name's own line (e.g. "ELECTRO-" / "PRIEST
    ADVANCE" / "SCHEME" -> "Electro-Priest"); and a two-word rank name splitting
    one-word-per-line before the marker (e.g. "SCHOLAR" / "ARCANUM" /
    "ADVANCES" -> "Scholar Arcanum", or hyphenated "LIEUTENANT-" / "SAVANT" /
    "ADVANCES" -> "Lieutenant-Savant") -- this was found and fixed after it
    silently dropped "Scholar Arcanum"'s and "Lieutenant-Savant"'s entire
    advance tables (their content got mis-attributed to whatever heading
    preceded them instead).
    """
    line = lines[i].strip()
    if len(line) > 2 and _RANK_HEADING_WORD.match(line) and line.upper() not in _NOT_A_RANK_NAME:
        for j in range(i + 1, min(len(lines), i + 5)):
            next_line = lines[j].strip()
            if not next_line:
                continue
            upper = next_line.upper()
            if upper in _RANK_FOLLOWUP_MARKERS:
                return line.title(), 1
            if upper == "ADVANCE" and j + 1 < len(lines) and lines[j + 1].strip().upper().startswith("SCHEME"):
                return line.title(), 1
            if next_line[0] in "\"'“‘":
                return line.title(), 1
            # A second heading-shaped word/line before the marker: the rank
            # name itself wrapped one word per line (not this word starting an
            # unrelated new heading -- confirmed by requiring the line AFTER
            # it to be a real marker or a flavour-quote opener).
            if (
                j == i + 1
                and len(next_line) > 1
                and _RANK_HEADING_WORD.match(next_line)
                and next_line.upper() not in _NOT_A_RANK_NAME
            ):
                for k in range(j + 1, min(len(lines), j + 4)):
                    after = lines[k].strip()
                    if not after:
                        continue
                    if after.upper() in _RANK_FOLLOWUP_MARKERS or after[0] in "\"'“‘":
                        joiner = "" if line.endswith("-") else " "
                        return (line + joiner + next_line).title(), 2
                    break
            break

    if line.upper().endswith(" ADVANCE") and i + 1 < len(lines) and lines[i + 1].strip().upper().startswith("SCHEME"):
        name = line[: -len(" ADVANCE")].strip()
        if i > 0 and lines[i - 1].strip().endswith("-"):
            name = lines[i - 1].strip() + name
        return name.title(), 1

    return None


def _find_rank_headings(lines: List[str], start: int, end: int) -> list[tuple[int, str]]:
    """Every rank-heading occurrence in ``lines[start:end]``, in text order."""
    headings = []
    i = start
    while i < end:
        result = _heading_at(lines, i)
        if result:
            name, consumed = result
            headings.append((i, name))
            i += consumed
        else:
            i += 1
    return headings


@dataclass
class CareerCharacteristicAdvance:
    """XP cost to raise one characteristic through one tier, for one career."""

    career: str
    characteristic: str
    simple: int | str
    intermediate: int | str
    trained: int | str
    expert: int | str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CareerAdvance:
    """A single skill/talent advance available to a career at a given rank."""

    career: str
    rank: str
    name: str
    cost: int
    type: str
    prerequisites: List[str] = field(default_factory=list)
    repeatable: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def _find_chapter_bounds(lines: List[str]) -> list[tuple[str, int, int]]:
    starts = [
        (match.group(1).strip(), idx)
        for idx, line in enumerate(lines)
        if (match := _CHAPTER_HEADER.match(line.strip()))
    ]
    if not starts:
        raise ParseError("No career characteristic-advance chapter headers found.")

    bounds = []
    for i, (career, start) in enumerate(starts):
        if i + 1 < len(starts):
            end = starts[i + 1][1]
        else:
            end = next(
                (j for j in range(start, len(lines)) if _NEXT_CHAPTER_HEADER.match(lines[j].strip())),
                len(lines),
            )
        bounds.append((career, start, end))
    return bounds


def _parse_characteristic_table(lines: List[str], start: int, end: int, career: str) -> List[CareerCharacteristicAdvance]:
    entries = []
    for idx in range(start + 1, end):
        stripped = lines[idx].strip()
        if not stripped:
            continue
        if stripped.lower().startswith("characteristic"):
            continue
        tokens = stripped.split()
        if len(tokens) < 5:
            break  # end of the small fixed-size table
        costs = tokens[-4:]
        if not all(re.fullmatch(r"[0-9,]+|N/A", cost) for cost in costs):
            break
        name = _normalise_name([" ".join(tokens[:-4])])
        simple, intermediate, trained, expert = (
            (int(c.replace(",", "")) if c != "N/A" else "N/A") for c in costs
        )
        entries.append(
            CareerCharacteristicAdvance(
                career=career,
                characteristic=name,
                simple=simple,
                intermediate=intermediate,
                trained=trained,
                expert=expert,
            )
        )
    if not entries:
        raise ParseError(f"No characteristic advances parsed for career '{career}'.")
    return entries


def _parse_rank_advances(
    lines: List[str], start: int, end: int, career: str
) -> tuple[List[str], List[CareerAdvance]]:
    """Walk the chapter attaching advance tables to the nearest preceding rank
    heading. Returns every rank NAME found (including ones that never got a
    table of their own, like Tech-Priest's "Mech-Wright") and the advance rows.
    XP thresholds/tier grouping come from ``_parse_rank_chart``, not from here --
    this function only knows where each rank's table lives in the chapter."""
    headings = _find_rank_headings(lines, start, end)
    if not headings:
        return [], []

    # Attach each table to the most recently seen heading. Consecutive tables
    # with no heading in between (a page-break split) attach to the same rank as
    # the previous table, exactly like the previous single-heading parser did.
    rank_order: list[str] = []
    advances: list[CareerAdvance] = []

    heading_iter = iter(headings)
    next_heading = next(heading_iter, None)
    current_rank: str | None = None
    idx = start
    while idx < end:
        while next_heading is not None and next_heading[0] <= idx:
            current_rank = next_heading[1]
            if current_rank not in rank_order:
                rank_order.append(current_rank)
            next_heading = next(heading_iter, None)

        line = lines[idx].strip()
        if not _ADVANCE_ROW_HEADER.match(line):
            idx += 1
            continue

        if current_rank is None:
            idx += 1
            continue
        rank = current_rank

        idx += 1
        while idx < end:
            row = lines[idx].strip()
            if not row:
                idx += 1
                continue
            if _ADVANCE_ROW_HEADER.match(row) or _BARE_PAGE_NUMBER.match(row) or row.startswith("†"):
                idx += 1
                continue
            # A new heading appearing here ends this table implicitly (the outer
            # loop will pick it up on the next iteration); stop consuming rows.
            if next_heading is not None and next_heading[0] == idx:
                break
            try:
                name, cost_text, advance_type, prereq_text = _split_advances_row(row)
            except ParseError:
                break  # table has ended; fall back to outer loop to find the next header

            # †/‡/¥ are all footnote markers on repeatable-slot advances (e.g.
            # "Minor Psychic Power‡") -- distinct symbols per distinct footnote
            # text, but all meaning "this slot can be taken more than once";
            # stripped so e.g. "Minor Psychic Power" and "Minor Psychic Power‡"
            # are recognised as the same slot rather than fragmenting into two.
            repeatable = bool(re.search(r"[†‡¥]\s*$", name.rstrip()))
            clean_name = re.sub(r"[†‡¥]+\s*$", "", name).strip()
            prerequisites = [
                item.strip().rstrip(".")
                for item in re.split(r",|;", prereq_text)
                if item.strip() and item.strip() != "—"
            ]
            advances.append(
                CareerAdvance(
                    career=career,
                    rank=rank,
                    name=_normalise_name([clean_name]),
                    cost=int(cost_text.replace(",", "")),
                    type="talent" if advance_type.upper().startswith("T") else "advance",
                    prerequisites=prerequisites,
                    repeatable=repeatable,
                )
            )
            idx += 1

    return rank_order, advances


# The advance-table heading walk (_find_rank_headings/_heading_at) and the rank
# chart (_parse_rank_chart) are two independent detectors reading two differently
def parse_career_schemes(
    text: str,
) -> tuple[list[CareerCharacteristicAdvance], list[CareerAdvance], list[str]]:
    """Parse every recoverable career chapter out of ``text``.

    Returns ``(characteristic_advances, rank_advances, skipped_careers)``. A
    career is skipped (rather than emitting guessed data) when its
    characteristic-advance table can't be parsed cleanly. Rank structure itself
    isn't parsed here -- see the module docstring; ``models.Career.from_data``
    reconciles each advance row's heading-walked ``rank`` against the
    authoritative ``database/career_ranks.json`` tree.
    """

    lines = text.splitlines()
    characteristic_advances: list[CareerCharacteristicAdvance] = []
    rank_advances: list[CareerAdvance] = []
    skipped: list[str] = []

    for career, start, end in _find_chapter_bounds(lines):
        try:
            characteristic_advances.extend(_parse_characteristic_table(lines, start, end, career))
        except ParseError:
            skipped.append(career)
            continue
        _rank_order, career_advances = _parse_rank_advances(lines, start, end, career)
        rank_advances.extend(career_advances)

    return characteristic_advances, rank_advances, skipped


#: Path to hand-transcribed, book-verified advance tables that override the
#: auto-parser's output for specific (career, rank) pairs -- see
#: ``_apply_verified_overrides``.
_VERIFIED_OVERRIDES_PATH = Path("database/imperial_psyker_verified_advances.json")


def _apply_verified_overrides(
    rank_advances: list[CareerAdvance], overrides_path: Path = _VERIFIED_OVERRIDES_PATH
) -> list[CareerAdvance]:
    """Replace auto-parsed rows with hand-verified ones for any (career, rank)
    pair present in ``overrides_path``.

    The auto-parser's "attach table to nearest preceding heading" strategy
    fails whenever the source PDF's 2-column layout interleaves two ranks'
    content out of logical order -- confirmed for Imperial Psyker's
    Scholar Arcanum/Savant Adjunct pair (Scholar Arcanum's real table was
    printed further down the page than Savant Adjunct's heading, so it got
    attributed to the wrong rank entirely) and impossible to fix generally
    without risking the same kind of wrong guess again. Where a human has
    directly transcribed a rank's table from the book, that data wins outright
    -- this isn't a merge/reconciliation, the auto-parsed rows for that exact
    (career, rank) are dropped and replaced wholesale.
    """
    if not overrides_path.exists():
        return rank_advances

    overrides = json.loads(overrides_path.read_text())
    override_keys = {(o["career"], o["rank"]) for o in overrides}
    kept = [a for a in rank_advances if (a.career, a.rank) not in override_keys]
    verified = [
        CareerAdvance(
            career=o["career"],
            rank=o["rank"],
            name=o["name"],
            cost=o["cost"],
            type=o["type"],
            prerequisites=list(o.get("prerequisites", [])),
            repeatable=o.get("repeatable", False),
        )
        for o in overrides
    ]
    return kept + verified


def regenerate_database_files(
    source: Path | str = "rulebooks/dh1e/core_all.txt",
    *,
    characteristic_output: Path | str = "database/career_characteristic_advances.json",
    advances_output: Path | str = "database/career_advances.json",
) -> tuple[int, int, list[str]]:
    """Re-run the parser against ``source`` and overwrite the characteristic and
    advance-table database files. Does NOT touch ``database/career_ranks.json``
    -- that's a hand-authored external file, not parser output (see the module
    docstring). Applies ``_apply_verified_overrides`` after parsing."""

    text = Path(source).read_text(encoding="utf-8", errors="replace")
    characteristic_advances, rank_advances, skipped = parse_career_schemes(text)
    rank_advances = _apply_verified_overrides(rank_advances)

    Path(characteristic_output).write_text(
        json.dumps([entry.to_dict() for entry in characteristic_advances], indent=2) + "\n"
    )
    Path(advances_output).write_text(
        json.dumps([entry.to_dict() for entry in rank_advances], indent=2) + "\n"
    )
    return len(characteristic_advances), len(rank_advances), skipped


if __name__ == "__main__":
    char_count, advance_count, skipped_careers = regenerate_database_files()
    print(f"Wrote {char_count} characteristic advances, {advance_count} rank advances.")
    if skipped_careers:
        print(f"Skipped (could not parse cleanly): {', '.join(skipped_careers)}")
