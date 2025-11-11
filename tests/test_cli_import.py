from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import pytest

from ttrpgtools import cli


def test_import_text_appends_entries(tmp_path) -> None:
    input_text = "\n".join(
        [
            "Talent Name Prerequisite Benefit",
            "Test Talent — Grants a bonus to something.",
        ]
    )
    input_path = tmp_path / "input.txt"
    input_path.write_text(input_text)
    library_path = tmp_path / "library.json"

    args = Namespace(
        input=str(input_path),
        category="talents-table",
        library=str(library_path),
        page=321,
        source="Core Rulebook",
    )

    cli.cmd_import_text(args)

    data = json.loads(library_path.read_text())
    assert len(data) == 1
    assert data[0]["name"] == "Test Talent"
    assert data[0]["page"] == 321
    assert data[0]["source"] == "Core Rulebook"
    assert data[0]["description"].startswith("Grants a bonus")


def test_import_text_reports_parse_error(tmp_path) -> None:
    input_path = tmp_path / "input.txt"
    input_path.write_text("not a table")
    library_path = tmp_path / "library.json"

    args = Namespace(
        input=str(input_path),
        category="talents-table",
        library=str(library_path),
        page=None,
        source=None,
    )

    with pytest.raises(SystemExit):
        cli.cmd_import_text(args)
