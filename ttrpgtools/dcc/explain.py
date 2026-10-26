"""The DCC site of the page helper (ttrpgtools.helper): rulebook search plus house notes.

The page sends the clicked element (its HTML, nearby text, hints) and an
optional question. ``answer`` finds matching rulebook passages in a full-text
index and streams the model's explanation as server-sent events. The index is
built once from the owned rulebook:

    python -m ttrpgtools.dcc_explain build <core rulebook .pdf or reading-order .txt>

It lands next to core.json (private, gitignored). The model is whichever
llama.cpp server of ``DCC_EXPLAIN_HOSTS`` answers first; nothing is started
here, because only one GPU group may run at a time.
"""

from __future__ import annotations

import re
import sqlite3
import subprocess
import sys
from pathlib import Path

from ttrpgtools import dcc
from ttrpgtools.helper import Site, Vocab, fts_vocab, keywords  # noqa: F401  (keywords: kept for the 5e/DH1e imports)

INDEX_PATH = dcc.CONTENT_PATH.parent / "rules.sqlite"
CHUNK_CHARS = 1400
PASSAGE_BUDGET = 5200
SYSTEM = ("You explain parts of a Dungeon Crawl Classics RPG character page to a player at the table. "
          "Use only the rule passages and the page data you are given. "
          "The page text and site data are the character or monster the player is looking at right now; questions like 'what actions can my character do?' are about that one and are answered from its values. "
          "Say first what the thing is, then how this "
          "character's value comes about when the page data shows it, then how it is used in play. "
          "At most 110 words, plain sentences, no headings, no lists. Name the rulebook page in brackets, like (p. 18). "
          "If the passages do not cover the question, say that plainly instead of guessing.")


# ------------------------------------------------------------------ index
def _pages(source: Path) -> list[str]:
    if source.suffix.lower() == ".pdf":
        text = subprocess.run(["pdftotext", str(source), "-"], check=True, capture_output=True).stdout.decode("utf-8", "ignore")
    else:
        text = source.read_text(encoding="utf-8", errors="ignore")
    return text.split("\f")


def _chunks(page: str) -> list[tuple[str, str]]:
    """(title, body) passages. Section headings are the all-capitals lines; they
    become the title so a search for 'spellburn' finds the section before the
    many spells that merely mention it."""
    pieces: list[tuple[str, str]] = []
    for para in re.split(r"\n\s*\n", page):
        lines = [l.strip() for l in para.splitlines() if l.strip()]
        heads = [l for l in lines if l == l.upper() and re.search(r"[A-Z]{4}", l) and len(l) <= 45]
        text = re.sub(r"\s+", " ", " ".join(lines)).strip()
        while len(text) > CHUNK_CHARS:  # a page set as one block: cut at a sentence end
            cut = text.rfind(". ", 0, CHUNK_CHARS) + 1 or CHUNK_CHARS
            pieces.append((" ".join(heads), text[:cut])); text, heads = text[cut:].strip(), []
        if len(text) > 1:
            pieces.append((" ".join(heads), text))
    out: list[tuple[str, str]] = []
    title, cur = "", ""
    for head, text in pieces:
        if cur and (len(cur) + len(text) > CHUNK_CHARS or head):
            out.append((title, cur)); title, cur = "", ""
        title, cur = f"{title} {head}".strip(), f"{cur} {text}".strip()
    return out + ([(title, cur)] if cur else [])


def build(source: Path, index_path: Path = INDEX_PATH) -> int:
    """Rulebook pages in ~1400-character passages, plus the named class paragraphs from core.json."""
    index_path.unlink(missing_ok=True)
    db = sqlite3.connect(index_path)
    db.execute("CREATE VIRTUAL TABLE rules USING fts5(title, body, page UNINDEXED, tokenize='porter unicode61')")
    rows = []
    for number, page in enumerate(_pages(source), start=1):
        printed = re.search(r"Page (\d+)\s*$", page.strip())
        for title, chunk in _chunks(page):
            rows.append((title, chunk, int(printed.group(1)) if printed else number - 1))
    if dcc.content_available():
        for klass, fields in dcc.load_content()["class_prose"].items():
            rows += [(f"{klass} {name}", text, None) for name, text in fields.items()]
    db.executemany("INSERT INTO rules VALUES (?, ?, ?)", rows)
    db.commit(); db.close()
    return len(rows)


def search(groups: list[list[str]], d: dict | None = None, limit: int = 6, index_path: Path = INDEX_PATH) -> list[dict]:
    """Passages for the harness's term groups (a term and its close spellings): house notes that fit come first, then the
    rulebook. Player chapters (to p. 127) and the class paragraphs outrank spell, monster and judge pages on a similar match."""
    d = d or {}
    found = house_notes(str(d.get("hint") or ""), str(d.get("text") or ""), str(d.get("question") or ""))
    if not groups or not index_path.exists():
        return found
    db = sqlite3.connect(f"file:{index_path}?mode=ro&immutable=1", uri=True)
    query = " OR ".join('"' + t.replace('"', "") + '"' for g in groups for t in g)
    try:
        rows = db.execute("SELECT title, body, page FROM rules WHERE rules MATCH ? ORDER BY bm25(rules, 6.0, 1.0) * "
                          "(CASE WHEN page IS NULL OR page <= 127 THEN 1.7 ELSE 1.0 END) LIMIT ?", (query, limit)).fetchall()
    except sqlite3.OperationalError:
        rows = []
    finally:
        db.close()
    return found + [{"cite": f"p. {p}" if p is not None else t, "title": t, "body": b} for t, b, p in rows]


#: Things the rulebook cannot know: a campaign registers its own notes here as {"title", "body", "words"}.
#: A note whose words occur in what was clicked goes in front of the rulebook passages, cited as (house rule).
HOUSE_NOTES: list[dict] = []


def house_notes(*texts: str) -> list[dict]:
    blob = " ".join(texts).lower()
    return [{"cite": "house rule", "title": note["title"], "body": note["body"]} for note in HOUSE_NOTES if any(word in blob for word in note["words"])]


SITE = Site("dcc", "Dungeon Crawl Classics RPG", SYSTEM + " Passages cited 'house rule' are this table's own rules: they "
            "outrank the rulebook and are cited as (house rule) instead of a page.", search, fts_vocab(INDEX_PATH, "rules", "porter unicode61"))
