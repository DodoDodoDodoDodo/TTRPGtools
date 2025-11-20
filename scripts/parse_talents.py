"""Parse talents from a text file into JSON (table or prose formats)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ttrpgtools.parsers import parse_talent_prose, parse_talent_table


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="Path to raw talent text")
    parser.add_argument("output", help="Destination JSON file")
    parser.add_argument(
        "--mode",
        choices=["table", "prose"],
        default="prose",
        help="Parsing strategy to use",
    )
    parser.add_argument("--page", type=int)
    parser.add_argument("--source", dest="book", help="Source book name")
    args = parser.parse_args()

    text = Path(args.input).read_text()
    kwargs = {"page": args.page, "source": args.book} if args.page or args.book else {}
    if args.mode == "table":
        entries = parse_talent_table(text, **kwargs)
    else:
        entries = parse_talent_prose(text, **kwargs)
    Path(args.output).write_text(json.dumps([entry.to_dict() for entry in entries], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
