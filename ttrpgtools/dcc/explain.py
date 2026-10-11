"""'What is this?' for the DCC pages: rulebook search plus a local model.

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

import json
import os
import re
import sqlite3
import subprocess
import sys
import urllib.request
from pathlib import Path

from ttrpgtools import dcc

INDEX_PATH = dcc.CONTENT_PATH.parent / "rules.sqlite"
HOSTS = [h.strip() for h in os.environ.get("DCC_EXPLAIN_HOSTS", "llm:8080").split(",") if h.strip()]
MODEL = os.environ.get("DCC_EXPLAIN_MODEL", "qwen-9b")   # llama-swap loads it on demand
CHUNK_CHARS = 1400
PASSAGE_BUDGET = 5200
STOPWORDS = set("the and for with that this from have has not are was you your their they them its but can may any all one two "
                "per each when then than into out roll rolls rolled die dice level levels character characters class value "
                "what does how why mean means number numbers page table work works use used get gets".split())
SYSTEM = ("You explain parts of a Dungeon Crawl Classics RPG character page to a player at the table. "
          "Use only the rule passages and the page data you are given. Say first what the thing is, then how this "
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


def search(terms: list[str], limit: int = 6, index_path: Path = INDEX_PATH) -> list[dict]:
    if not terms or not index_path.exists():
        return []
    db = sqlite3.connect(f"file:{index_path}?mode=ro&immutable=1", uri=True)
    query = " OR ".join('"' + t.replace('"', "") + '"' for t in terms)
    try:
        # Player chapters (to p. 127) and the class paragraphs outrank spell, monster and judge pages on a similar match.
        rows = db.execute("SELECT title, body, page FROM rules WHERE rules MATCH ? ORDER BY bm25(rules, 6.0, 1.0) * "
                          "(CASE WHEN page IS NULL OR page <= 127 THEN 1.7 ELSE 1.0 END) LIMIT ?", (query, limit)).fetchall()
    finally:
        db.close()
    return [{"title": t, "body": b, "page": p} for t, b, p in rows]


def keywords(*texts: str, limit: int = 14) -> list[str]:
    seen: list[str] = []
    for text in texts:
        for word in re.findall(r"[A-Za-z][A-Za-z'’-]{2,}", text or ""):
            w = word.lower().strip("'’-")
            if w not in STOPWORDS and w not in seen:
                seen.append(w)
    return seen[:limit]


#: Things the rulebook cannot know: a campaign registers its own notes here as {"title", "body", "words"}.
#: A note whose words occur in what was clicked goes in front of the rulebook passages.
HOUSE_NOTES: list[dict] = []


def house_notes(*texts: str) -> list[dict]:
    blob = " ".join(texts).lower()
    return [{"title": note["title"], "body": note["body"], "page": None} for note in HOUSE_NOTES if any(word in blob for word in note["words"])]


def passages(hint: str, text: str, question: str) -> list[dict]:
    """Campaign notes that fit come first; then hint and question (precise), the element's own words as a fallback."""
    house = house_notes(hint, text, question)
    if house and not question:
        return house[:3]  # the click was on something of the campaign: the rulebook would only add noise
    found = house + search(keywords(question, hint))
    if len(found) < 3:
        known = {f["body"] for f in found}
        found += [f for f in search(keywords(hint, text)) if f["body"] not in known]
    out, used = [], 0
    for f in found:
        if used + len(f["body"]) > PASSAGE_BUDGET:
            break
        out.append(f); used += len(f["body"])
    return out


# ------------------------------------------------------------------ model
def _event(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _model_stream(messages: list[dict]):
    """Text pieces from the first llama.cpp server that answers; raises OSError when none does."""
    body = json.dumps({"model": MODEL, "messages": messages, "stream": True, "max_tokens": 320, "temperature": 0.2}).encode()
    last: Exception = OSError("no model host configured")
    for host in HOSTS:
        try:
            req = urllib.request.Request(f"http://{host}/v1/chat/completions", data=body, headers={"Content-Type": "application/json"})
            resp = urllib.request.urlopen(req, timeout=120)  # the first request after an idle spell waits for the model to load
        except OSError as exc:
            last = exc
            continue
        with resp:
            for raw in resp:
                line = raw.decode("utf-8", "ignore").strip()
                if not line.startswith("data:") or line.endswith("[DONE]"):
                    continue
                delta = (json.loads(line[5:])["choices"][0].get("delta") or {}).get("content")
                if delta:
                    yield delta
        return
    raise last


def prompt(d: dict, found: list[dict]) -> list[dict]:
    rules = "\n\n".join(f"[{'p. ' + str(f['page']) if f['page'] is not None else f['title']}] {f['body']}" for f in found)
    house = any(f["page"] is None and f["title"].startswith("This campaign") for f in found)
    parts = [f"Page: {str(d.get('page') or '')[:120]}",
             f"Character: {str(d.get('character') or 'none yet')[:700]}",
             f"Clicked element (HTML): {str(d.get('html') or '')[:2200]}",
             f"Text around it: {str(d.get('context') or '')[:1200]}",
             f"Rule passages:\n{rules or 'none found'}",
             f"Question: {str(d.get('question') or 'What is this, and what does it mean for my character?')[:300]}"]
    system = SYSTEM + (" Passages marked 'This campaign' are house rules of this table: they outrank the rulebook, and you cite them "
                       "as (house rule) instead of a page." if house else "")
    return [{"role": "system", "content": system}, {"role": "user", "content": "\n\n".join(parts)}]


def answer(d: dict):
    """Server-sent events: {'text': piece}..., then {'done': true, 'pages': [...]}; {'error': ...} when no model answers."""
    found = passages(str(d.get("hint") or ""), str(d.get("text") or ""), str(d.get("question") or ""))
    pages = sorted({f["page"] for f in found if f["page"] is not None})
    try:
        for piece in _model_stream(prompt(d, found)):
            yield _event({"text": piece})
    except (OSError, ValueError, KeyError) as exc:
        yield _event({"error": "No local model answered just now (it may be restarting, or the GPU is in another mode). "
                               "What was found is shown below; try again in a minute for an explanation in plain words.",
                      "detail": str(exc)})
    yield _event({"done": True, "pages": pages,
                  "passages": [{"page": f["page"], "title": f["title"], "text": f["body"][:900]} for f in found[:2]]})


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "build":
        print(f"{build(Path(sys.argv[2]))} passages -> {INDEX_PATH}")
    else:
        sys.exit(__doc__)
