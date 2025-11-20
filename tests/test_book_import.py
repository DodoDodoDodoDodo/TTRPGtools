from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

from ttrpgtools import cli
from ttrpgtools.book_import import auto_parse_book

ROOT = Path(__file__).resolve().parents[1]


def test_auto_parse_book_discovers_sections() -> None:
    text = (ROOT / "stuff.md").read_text()
    entries = auto_parse_book(text, source="Core")

    assert len(entries) == 106
    talent_names = {entry.name for entry in entries if getattr(entry, "name", None)}
    assert "Air Of Authority" in talent_names
    assert "Telepathy" in talent_names

    divinations = [entry for entry in entries if entry.to_dict().get("type") == "divination"]
    assert any(item.roll_min == 1 and item.roll_max == 1 for item in divinations)


def test_cli_import_book_writes_library(tmp_path) -> None:
    library_path = tmp_path / "library.json"
    args = Namespace(
        input=str(ROOT / "stuff.md"),
        library=str(library_path),
        page=None,
        source="Core",
    )

    cli.cmd_import_book(args)

    data = json.loads(library_path.read_text())
    names = {item["name"] for item in data if "name" in item}
    assert len(data) == 106
    assert "Telepathy" in names
    assert any(item.get("type") == "divination" for item in data)
