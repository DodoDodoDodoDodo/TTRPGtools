"""Rules questions and "Explain this" for the 5e pages: 5etools text search plus the local model.

The index holds the 5etools book and adventure text (2014 era only) cut into sections, and every rules entry of
the builder data (spells, items, feats, races, backgrounds, class options and features, conditions), each tagged
with its book and the group the page offers as checkboxes: rules, adventures, other. The harness (``ttrpgtools.helper``)
asks the model for search terms, widens them to close spellings, and answers from the passages found here.

    python -m ttrpgtools.dnd5e.explain build /path/to/5etools-src     # on the host; writes content/dnd5e/private/explain.sqlite
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
import sys
from pathlib import Path

from ttrpgtools.helper import Site, Vocab, fts_vocab

INDEX_PATH = Path(__file__).resolve().parents[2] / "content" / "dnd5e" / "private" / "explain.sqlite"
BUILDER_DIR = Path(__file__).resolve().parents[2] / "content" / "dnd5e" / "private" / "builder"
#: the 2024 rules arrived with the new Player's Handbook; anything published from then on stays out (2014 only)
CUTOFF = "2024-09-17"
RULES_GROUPS = {"core", "supplement", "setting", "screen"}
CHUNK_CHARS = 1400
PASSAGE_BUDGET = 6000
SYSTEM = ("You answer questions about Dungeons & Dragons 5th edition (2014 rules) for players and DMs at one table. "
          "Use only the passages you are given. "
          "The page text and site data are the character or monster the player is looking at right now; questions like 'what actions can my character do?' are about that one and are answered from its values. "
          "Answer in at most 130 words, plain sentences, no headings. "
          "Name the source of each rule in brackets, like (PHB p. 195). If the passages do not answer the question, "
          "say so plainly instead of guessing.")


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
    tmp = index_path.with_suffix(".building")
    tmp.unlink(missing_ok=True)
    conn = sqlite3.connect(tmp)
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
    # monsters: one passage per stat block (AC, HP, speed, scores, traits, actions), so "what is the Tarrasque's AC" has an answer
    for path in sorted((data / "bestiary").glob("bestiary-*.json")):
        for m in json.loads(path.read_text()).get("monster", []):
            source = known.get(str(m.get("source", "")).lower())
            if source and not m.get("_copy"):
                conn.execute("INSERT INTO passages VALUES (?,?,?,?)", (source, m["name"], m.get("page"), _statblock(m)[:CHUNK_CHARS * 3]))
                count += 1
    conn.commit()
    conn.close()
    tmp.replace(index_path)
    return count


def _statblock(m: dict) -> str:
    def named(key, label):
        rows = [f"{e.get('name', '')}: {_plain(' '.join(_strings(e.get('entries', []))))}" for e in m.get(key) or [] if isinstance(e, dict)]
        return f" {label}: " + " ".join(rows) if rows else ""
    ac = ", ".join(str(a.get("ac", a.get("special", ""))) + (f" ({', '.join(map(str, a['from']))})" if a.get("from") else "") if isinstance(a, dict) else str(a) for a in m.get("ac") or [])
    hp = m.get("hp") or {}
    hp_text = (f"{hp.get('average', '')} ({hp.get('formula', '')})" if "average" in hp else str(hp.get("special", ""))) if isinstance(hp, dict) else str(hp)
    kind = m.get("type"); kind = kind.get("type") if isinstance(kind, dict) else kind
    speed = ", ".join(f"{k} {v if not isinstance(v, dict) else v.get('number', '')}" for k, v in (m.get("speed") or {}).items() if k != "canHover")
    scores = " ".join(f"{k.upper()} {m.get(k, '')}" for k in ("str", "dex", "con", "int", "wis", "cha"))
    return (f"{m['name']}. Size {', '.join(map(str, m.get('size') or []))} {kind}, CR {m.get('cr') if not isinstance(m.get('cr'), dict) else m['cr'].get('cr')}. "
            f"Armor Class {ac}. Hit Points {hp_text}. Speed {speed}. {scores}."
            + named("trait", "Traits") + named("action", "Actions") + named("legendary", "Legendary actions") + named("reaction", "Reactions"))


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


def search(groups: list[list[str]], d: dict | None = None, limit: int = 6, index_path: Path = INDEX_PATH) -> list[dict]:
    """Passages for the harness's term groups in the books the page chose (d["sources"]). Every term brings its own best
    passages (so a common word cannot crowd out a rare one; close spellings bring a few), then the passage holding the most
    rarity-weighted terms wins: a term in the title counts double, a title that IS the term triple, a spelling variant half."""
    allowed = [str(x) for x in (d or {}).get("sources") or [] if isinstance(x, str)][:200]
    if not groups or not allowed or not index_path.exists():
        return []
    norm = SITE.vocab.normalize
    conn = sqlite3.connect(f"file:{index_path}?mode=ro", uri=True)
    marks = ",".join("?" * len(allowed))
    sql = (f"SELECT p.rowid, p.source, s.name, p.title, p.page, p.body, bm25(passages, 0, 3, 0, 1) FROM passages p "
           f"JOIN sources s ON s.id = p.source WHERE passages MATCH ? AND p.source IN ({marks}) AND length(p.body) > 40 ORDER BY 7 LIMIT ?")
    pool: dict[int, tuple] = {}
    terms: list[tuple[str, list[str], float]] = []  # (stem of the term, stems of its variants, rarity weight)
    try:
        total = conn.execute("SELECT count(*) FROM passages").fetchone()[0] or 1
        for g in groups:
            main = '"' + g[0].replace('"', "") + '"'
            df = conn.execute("SELECT count(*) FROM passages WHERE passages MATCH ?", (main,)).fetchone()[0]
            terms.append((norm(g[0]), [norm(v) for v in g[1:]], math.log((total + 1) / (df + 1))))
            for row in conn.execute(sql, (main, *allowed, 40)):
                pool.setdefault(row[0], row)
            for v in g[1:]:
                for row in conn.execute(sql, ('"' + v.replace('"', "") + '"', *allowed, 8)):
                    pool.setdefault(row[0], row)
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()
    def rank(row):
        title, body = row[3].lower(), row[5].lower()
        score = 0.0
        for stem, variants, w in terms:
            if stem in title or stem in body:
                score += w * (3 if any(norm(part.strip()) == stem for part in title.split(":")) else 2 if stem in title else 1)
            elif any(v in title or v in body for v in variants):
                score += w * 0.5
        return (-score, row[6])
    rows = sorted(pool.values(), key=rank)[:limit]
    return [{"cite": f"{source}{' p. ' + str(page) if page else ''}", "title": title, "body": body, "book": book}
            for _, source, book, title, page, body, _ in rows]


SITE = Site("dnd5e", "Dungeons & Dragons 5th edition (2014 rules)", SYSTEM, search, fts_vocab(INDEX_PATH, "passages"),
            "Explain this to a player: what it does, when it matters at the table, and the common mistakes.")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "build":
        print(f"{build(Path(sys.argv[2]))} passages -> {INDEX_PATH}")
    else:
        sys.exit(__doc__)
