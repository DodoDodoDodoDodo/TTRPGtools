"""The Dark Heresy site of the page helper (ttrpgtools.helper): overlapping windows of the cleaned core rulebook text
(rulebooks/dh1e, private, mounted into the container) scored by how many term groups they contain."""

from __future__ import annotations

import re
from pathlib import Path

from ttrpgtools.helper import Site, Vocab

BOOK = Path(__file__).resolve().parents[2] / "rulebooks" / "dh1e" / "DH1e_cleaned.txt"
SYSTEM = ("You answer questions about Dark Heresy, first edition (Fantasy Flight, 2008) for the players at one table. "
          "Use only the passages and page data you are given. Answer in at most 130 words, plain sentences, no headings.")
_chunks: list[str] | None = None


def chunks() -> list[str]:
    global _chunks
    if _chunks is None:  # the cleaned text has no blank lines (56-char lines), so passages are overlapping windows of lines
        lines = [l.strip() for l in BOOK.read_text(errors="replace").splitlines() if l.strip()] if BOOK.exists() else []
        _chunks = [" ".join(lines[i:i + 12]) for i in range(0, len(lines), 8)]
    return _chunks


def words() -> list[str]:
    return sorted({w for w in re.findall(r"[a-z][a-z'-]{3,}", " ".join(chunks()).lower())})


def search(groups: list[list[str]], d: dict | None = None, limit: int = 5) -> list[dict]:
    if not groups:
        return []
    scored = []
    for c in chunks():
        low = c.lower()
        hits = sum(1 for g in groups if any(t in low for t in g))
        if hits >= max(1, len(groups) // 3):
            scored.append((-hits, len(c), c))
    return [{"cite": "Core Rulebook", "title": p[:40] + "…", "body": p} for _, _, p in sorted(scored)[:limit]]


SITE = Site("dh1e", "Dark Heresy, first edition", SYSTEM, search, Vocab(words), "What is this, and what does it mean for my Acolyte?")
