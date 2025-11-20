"""Parse equipment blocks from a text file into JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ttrpgtools.block_parsers import parse_equipment_blocks


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="Path to raw equipment text")
    parser.add_argument("output", help="Destination JSON file")
    args = parser.parse_args()

    text = Path(args.source).read_text()
    entries = parse_equipment_blocks(text)
    Path(args.output).write_text(json.dumps([entry.to_dict() for entry in entries], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
