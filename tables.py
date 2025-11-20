import re
from pathlib import Path

# -------- CONFIG --------
INPUT_FILE = "core_all.txt"   # your big .txt
OUTPUT_FILE = "core_tables.txt"    # where tables go





def is_table_start(line: str) -> bool:
    """
    Detects lines like:
    'Table 1-3: Grenades and Torpedoes'
    'Table 7–23: Rending Critical Effects – Head'
    """
    stripped = line.strip()
    return bool(re.match(r'^Table\s+\d', stripped))


def is_row_start(line: str) -> bool:
    """
    A line that looks like the *start* of a row in a table.
    Examples:
      '01–20 Feral World: ...'
      '3 metres 1d10+3'
      '25+ metres 1d10+20'
      '1 The attack tears ...'
    """
    stripped = line.lstrip()

    # Starts with a number (possibly with + or range markers)
    # 01–20, 41-70, 25+, 3, 10+, etc.
    if re.match(r'^\d', stripped):
        return True

    return False


def contains_any_digit(line: str) -> bool:
    return any(ch.isdigit() for ch in line)


def extract_tables_from_lines(lines):
    tables = []
    n = len(lines)
    i = 0

    while i < n:
        line = lines[i]

        if not is_table_start(line):
            i += 1
            continue

        # We found a table header
        current_table_lines = [line.rstrip("\n")]
        i += 1

        # Collect a coarse candidate block until:
        # - next table header, OR
        # - blank line, OR
        # - EOF
        block = []
        while i < n:
            next_line = lines[i]
            # Stop if the next line starts a new table
            if is_table_start(next_line):
                break

            # Stop if blank line (hard break in layout)
            if not next_line.strip():
                block.append(next_line.rstrip("\n"))
                i += 1
                break

            block.append(next_line.rstrip("\n"))
            i += 1

        # Now refine this block using numeric / row heuristics
        trimmed = trim_block_to_table(block)

        current_table_lines.extend(trimmed)
        tables.append("\n".join(current_table_lines))

    return tables


def trim_block_to_table(block_lines):
    """
    Given a block of lines after a 'Table X-Y' header,
    keep the part that is most likely to be the table:

    - Require at least 3 'row start' lines.
    - Allow some non-row continuation lines after the last row.
    - If we see MANY non-row lines after the last row, assume
      we've drifted into prose and cut there.
    """

    if not block_lines:
        return []

    # First, just keep everything up to the first obvious prose break,
    # then we'll trim from the end if needed.
    # (In practice, this is mostly for 'Random Home World' where there
    #  is no blank line before prose.)

    result = []
    row_indices = []

    # Parameters: tweak to taste
    MIN_ROWS = 3
    MAX_NONROW_AFTER_LAST_ROW = 6  # how many non-row lines we tolerate after last real row

    nonrow_since_last_row = 0
    last_row_idx = -1

    for idx, line in enumerate(block_lines):
        stripped = line.strip()
        result.append(line)

        if is_row_start(stripped):
            row_indices.append(idx)
            last_row_idx = idx
            nonrow_since_last_row = 0
        else:
            if last_row_idx != -1:
                # We are after at least one row
                # Count how many non-row lines we've seen since last row
                nonrow_since_last_row += 1

                # If we've seen enough rows AND too many non-row lines after the last row,
                # we assume we've wandered into prose. Cut here.
                if len(row_indices) >= MIN_ROWS and nonrow_since_last_row > MAX_NONROW_AFTER_LAST_ROW:
                    # Drop everything from this line onward
                    result = result[:idx]  # do not include current line
                    break

    # If we never saw enough rows, it's probably either:
    # - a non-data "table" (like a one-line reference), or
    # - a text-only table (e.g. Signs of the Dark Gods).
    # In both cases, just return the whole block as-is.
    #
    # If we did see enough rows but never hit the non-row cutoff,
    # we also just return `result` as collected.

    return result


def main():
    text_path = Path(INPUT_FILE)
    if not text_path.exists():
        raise FileNotFoundError(f"Input file not found: {INPUT_FILE}")

    with text_path.open("r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    tables = extract_tables_from_lines(lines)

    out_path = Path(OUTPUT_FILE)
    separator = "\n\n" + ("-" * 80) + "\n\n"

    with out_path.open("w", encoding="utf-8") as f:
        f.write(separator.join(tables))

    print(f"Extracted {len(tables)} table(s) to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()