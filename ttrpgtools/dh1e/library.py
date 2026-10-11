"""Simple JSON-backed data store for parsed reference material."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List

__all__ = ["load_library", "save_library", "append_entries"]


def load_library(path: str | Path) -> List[dict]:
    """Load the JSON library from ``path`` if it exists, otherwise return an empty list."""

    file_path = Path(path)
    if not file_path.exists():
        return []
    data = json.loads(file_path.read_text())
    if not isinstance(data, list):
        raise ValueError("Library JSON must be a list of entries.")
    return data


def save_library(entries: Iterable[dict], path: str | Path) -> None:
    """Persist ``entries`` to ``path`` in JSON format."""

    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    serialisable = list(entries)
    file_path.write_text(json.dumps(serialisable, indent=2, sort_keys=True))


def append_entries(entries: Iterable[dict], path: str | Path) -> List[dict]:
    """Append ``entries`` to the existing JSON library and return the updated list."""

    current = load_library(path)
    current.extend(entries)
    save_library(current, path)
    return current
