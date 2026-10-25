"""Rules questions and "Explain this" for the 5e pages: 5etools text search plus the local model.

The index holds the 5etools book and adventure text (2014 era only) cut into sections, and every rules entry of
the builder data (spells, items, feats, races, backgrounds, class options and features, conditions), each tagged
with its book and the group the page offers as checkboxes: rules, adventures, other. A question finds the best
passages in the chosen books and the model answers from those alone, citing book and page. The model is DCC's
(``dcc.explain``: the first llama.cpp server that answers); when none answers, the feature is simply unavailable.

    python -m ttrpgtools.dnd5e.explain build /path/to/5etools-src     # on the host; writes content/dnd5e/private/explain.sqlite
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
import sys
from pathlib import Path

from ttrpgtools.dcc.explain import _event, _model_stream, keywords

INDEX_PATH = Path(__file__).resolve().parents[2] / "content" / "dnd5e" / "private" / "explain.sqlite"
BUILDER_DIR = Path(__file__).resolve().parents[2] / "content" / "dnd5e" / "private" / "builder"
#: the 2024 rules arrived with the new Player's Handbook; anything published from then on stays out (2014 only)
CUTOFF = "2024-09-17"
RULES_GROUPS = {"core", "supplement", "setting", "screen"}
CHUNK_CHARS = 1400
PASSAGE_BUDGET = 6000
SYSTEM = ("You answer questions about Dungeons & Dragons 5th edition (2014 rules) for players and DMs at one table. "
          "Use only the passages you are given. Answer in at most 130 words, plain sentences, no headings. "
          "Name the source of each rule in brackets, like (PHB p. 195). If the passages do not answer the question, "
          "say so plainly instead of guessing.")
EXPLAIN = ("Explain this to a player: what it does, when it matters at the table, and the common mistakes. "
           "Use the entry text and the passages.")


def _plain(text: str) -> str:
    """5etools markup to readable text: {@spell fireball|phb} -> fireball, {@dice 1d6} -> 1d6."""
    return re.sub(r"\{@\w+ ([^|}]*)[^}]*\}", r"\1", text)


def _walk(entries, title: str, page, out: list) -> None:
    """Sections of a 5etools book: every named entry starts a new passage; text below it joins that passage."""
    buffer: list[str] = []

    def flush():
        text = re.sub(r"\s+", " ", " ".join(buffer)).strip()
        while text:
            cut = text[:CHUNK_CHARS]
            if len(text) > CHUNK_CHARS and ". " in cut:
                cut = cut[:cut.rindex(". ") + 1]
            out.append((title, page, cut))
            text = text[len(cut):].strip()
        buffer.clear()

    for e in entries if isinstance(entries, list) else [entries]:
        if isinstance(e, str):
            buffer.append(_plain(e))
        elif isinstance(e, dict):
            if e.get("name") and e.get("entries") is not None:
                flush()
                _walk(e["entries"], _plain(str(e["name"])), e.get("page", page), out)
            else:
                for key in ("entries", "items"):
                    if key in e:
                        for item in e[key]:
                            if isinstance(item, str):
                                buffer.append(_plain(item))
                            elif isinstance(item, dict) and item.get("name") and item.get("entries"):
                                buffer.append(_plain(f"{item['name']}: " + " ".join(x for x in item["entries"] if isinstance(x, str))))
                            else:
                                _walk([item], title, page, out)
                if e.get("type") == "table":
                    rows = [" | ".join(_plain(c if isinstance(c, str) else json.dumps(c)) for c in row) for row in e.get("rows", [])]
                    buffer.append(f"{e.get('caption', 'Table')}: " + "; ".join(rows))
    flush()


def build(fivetools: Path, index_path: Path = INDEX_PATH, builder_dir: Path = BUILDER_DIR) -> int:
    data = fivetools / "data"
    index_path.unlink(missing_ok=True)
    conn = sqlite3.connect(index_path)
    conn.execute("CREATE TABLE sources (id TEXT PRIMARY KEY, name TEXT, grp TEXT, published TEXT)")
    conn.execute("CREATE VIRTUAL TABLE passages USING fts5(source UNINDEXED, title, page UNINDEXED, body, tokenize='porter')")
    count = 0
    for meta_file, kind, folder in (("books.json", "book", "book"), ("adventures.json", "adventure", "adventure")):
        for meta in json.loads((data / meta_file).read_text())[kind]:
            if (meta.get("published") or "") >= CUTOFF:
                continue
            path = data / folder / f"{folder}-{meta['id'].lower()}.json"
            if not path.exists():
                continue
            grp = "adventures" if kind == "adventure" else "rules" if meta.get("group") in RULES_GROUPS else "other"
            conn.execute("INSERT INTO sources VALUES (?,?,?,?)", (meta["id"], meta["name"], grp, meta.get("published", "")))
            out: list = []
            raw = json.loads(path.read_text())
            body = raw.get(f"{kind}Data") or []  # {"bookData": [{"id", "source", "data": [...]}]}
            _walk([part for block in body for part in block.get("data", [])], meta["name"], None, out)
            conn.executemany("INSERT INTO passages VALUES (?,?,?,?)", [(meta["id"], t, p, b) for t, p, b in out])
            count += len(out)
    # the builder's rules entries, under their own book (only books the sources table knows)
    known = {r[0].lower(): r[0] for r in conn.execute("SELECT id FROM sources")}
    for kind in ("spells", "items", "feats", "races", "backgrounds", "optionalfeatures", "conditions"):
        for e in json.loads((builder_dir / f"{kind}.json").read_text()):
            source = known.get(str(e.get("source", "")).lower())
            if source:
                body = re.sub(r"\s+", " ", _plain(" ".join(_strings(e.get("entries", [])))))[:CHUNK_CHARS * 2]
                conn.execute("INSERT INTO passages VALUES (?,?,?,?)", (source, e["name"], e.get("page"), body))
                count += 1
    for cls in json.loads((builder_dir / "classes.json").read_text()):
        for owner, features in [(cls["name"], cls.get("features", []))] + [(f"{cls['name']}: {s['name']}", s.get("features", [])) for s in cls.get("subclasses", [])]:
            for f in features:
                source = known.get(str(f.get("source", "")).lower())
                if source:
                    body = re.sub(r"\s+", " ", _plain(" ".join(_strings(f.get("entries", [])))))[:CHUNK_CHARS * 2]
                    conn.execute("INSERT INTO passages VALUES (?,?,?,?)", (source, f"{owner}: {f['name']}", f.get("page"), body))
                    count += 1
    conn.commit()
    conn.close()
    return count


def _strings(entries) -> list[str]:
    out = []
    for e in entries or []:
        if isinstance(e, str):
            out.append(e)
        elif isinstance(e, dict):
            out += _strings(e.get("entries") or e.get("items") or [])
    return out


def sources(index_path: Path = INDEX_PATH) -> list[dict]:
    if not index_path.exists():
        return []
    conn = sqlite3.connect(f"file:{index_path}?mode=ro", uri=True)
    try:
        return [{"id": i, "name": n, "group": g} for i, n, g in conn.execute("SELECT id, name, grp FROM sources ORDER BY grp, name")]
    finally:
        conn.close()


def search(question: str, allowed: list[str], limit: int = 6, index_path: Path = INDEX_PATH) -> list[dict]:
    terms = keywords(question, limit=14)
    if not terms or not allowed or not index_path.exists():
        return []
    conn = sqlite3.connect(f"file:{index_path}?mode=ro", uri=True)
    marks = ",".join("?" * len(allowed))
    sql = (f"SELECT p.rowid, p.source, s.name, p.title, p.page, p.body, bm25(passages, 0, 3, 0, 1) FROM passages p "
           f"JOIN sources s ON s.id = p.source WHERE passages MATCH ? AND p.source IN ({marks}) ORDER BY 7 LIMIT 40")
    # every word brings its own best passages, so a common word (shield: 925 passages) cannot crowd out a rare one
    pool: dict[int, tuple] = {}
    weight: dict[str, float] = {}
    try:
        total = conn.execute("SELECT count(*) FROM passages").fetchone()[0] or 1
        for term in terms:
            # rare words say more about the question than common ones ("grapple" over "while", "holding")
            df = conn.execute("SELECT count(*) FROM passages WHERE passages MATCH ?", (f'"{term}"',)).fetchone()[0]
            weight[term[:5]] = math.log((total + 1) / (df + 1))
            for row in conn.execute(sql, (f'"{term}"', *allowed)):
                pool.setdefault(row[0], row)
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()
    # the passage holding the most (rarity-weighted) question words wins; the text score breaks ties
    def rank(row):
        title, text = row[3].lower(), f"{row[3]} {row[5]}".lower()
        # a word in the section's title (Grappling, Cover, Casting in Armor) counts twice
        return (-sum(w * (2 if st in title else 1) for st, w in weight.items() if st in text), row[6])
    rows = [r[1:6] for r in sorted(pool.values(), key=rank)]
    found, used = [], 0
    for source, book, title, page, body in rows:
        if used + len(body) > PASSAGE_BUDGET or len(found) >= limit:
            break
        found.append({"source": source, "book": book, "title": title, "page": page, "body": body})
        used += len(body)
    return found


def _cite(f: dict) -> str:
    return f"{f['source']}{' p. ' + str(f['page']) if f['page'] else ''}"


REWRITE = ("Turn the player's question into search terms for the D&D 5e (2014) rulebooks: the words a book's index "
           "would use for the rule they mean (for example grappling, cover, opportunity attack, attunement). "
           "Reply with 3 to 8 terms separated by commas and nothing else.")


def search_terms(question: str) -> str:
    """First model pass: what the question is about, in rulebook words ("grapple while holding a shield" ->
    "grappling, free hand, shield, Athletics"). Falls back to the question itself when no model answers."""
    try:
        terms = "".join(_model_stream([{"role": "system", "content": REWRITE}, {"role": "user", "content": question[:600]}]))
    except (OSError, ValueError, KeyError):
        return ""
    return re.sub(r"[^\w ,'-]", " ", terms)[:300]


def answer(question: str, allowed: list[str], entry: dict | None = None):
    """Server-sent events: {'text': piece}..., then {'done': true, 'passages': [...]}; {'error': ...} when no model answers.
    `entry` ({name, text}) is the thing an "Explain this" button was pressed on."""
    # two passes for a question (Dodo, 2026-10-25): the model names the rule in book words, the index finds it
    terms = search_terms(question) if question and not entry else ""
    found = search(" ".join(filter(None, [terms, question, (entry or {}).get("name", "")])), allowed)
    context = "\n\n".join(f"[{_cite(f)}: {f['title']}] {f['body']}" for f in found) or "none found"
    if entry:
        user = f"{EXPLAIN}\n\nEntry: {entry.get('name', '')}\n{str(entry.get('text', ''))[:2500]}\n\nPassages:\n{context}"
    else:
        user = f"Question: {question[:600]}\n\nPassages:\n{context}"
    try:
        for piece in _model_stream([{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]):
            yield _event({"text": piece})
    except TimeoutError:  # the model answers one request at a time; dentinf or another page holds it
        yield _event({"error": "Model currently busy, check back in a minute."})
    except (OSError, ValueError, KeyError):
        yield _event({"error": "Model currently unavailable."})
    yield _event({"done": True, "passages": [{"cite": _cite(f), "book": f["book"], "title": f["title"], "text": f["body"][:600]} for f in found[:4]]})


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "build":
        print(f"{build(Path(sys.argv[2]))} passages -> {INDEX_PATH}")
    else:
        sys.exit(__doc__)
