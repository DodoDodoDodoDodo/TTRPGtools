"""The page helper's harness (Dodo, 2026-10-26): one loop for every site that has a helper.

A site hands over one ``Site``: its name, game, system prompt, a ``search(groups, request)`` over its own books and a
``Vocab`` of the words in them. The harness does the rest for a question or a click on the page:

  1. the model writes search terms from the question, the thread so far and what is on screen (pass 1)
  2. each term is widened to its close spellings in the site's vocabulary (fuzzy, tolerates OCR and typos)
  3. the site's search returns passages for the term groups
  4. the model answers from passages + page snapshot + thread, streamed as server-sent events (pass 2)
  5. afterwards, in the background, the model rewrites its note to self for this site (what worked, what did not),
     at most NOTE_MAX characters, read back into passes 1 and 2 (data/helper-notes/<site>.txt)

What a page sends (static/helper.js): question, thread ([{q, a}] of this window), page_text (what the player sees),
site_data (the site's own data for it), and for a clicked element: breadcrumb (ancestor chain), html, text, hint,
context. The breadcrumb tells the model WHERE the thing sits: "main > div.panel.inventory-panel (Inventory) > input[name=coin_gp]".
"""
from __future__ import annotations

import difflib
import json
import os
import re
import sqlite3
import threading
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

HOSTS = [h.strip() for h in os.environ.get("HELPER_HOSTS", os.environ.get("DCC_EXPLAIN_HOSTS", "llm:8080")).split(",") if h.strip()]
MODEL = os.environ.get("HELPER_MODEL", os.environ.get("DCC_EXPLAIN_MODEL", "qwen-9b"))
QUOTA_DB = Path(os.environ.get("HELPER_QUOTA_DB", Path(__file__).resolve().parents[1] / "data" / "helper-quota.sqlite"))
FREE_PER_HOUR = 1      # answered questions without premium (Dodo, 2026-10-25)
PREMIUM_PER_DAY = 100
THREAD_TURNS = 6
NOTES_DIR = QUOTA_DB.parent / "helper-notes"
NOTE_MAX = 600
PASSAGE_BUDGET = 6000
STOPWORDS = set("the and for with that this from have has not are was you your their they them its but can may any all one two "
                "per each when then than into out roll rolls rolled die dice level levels character characters class value "
                "what does how why mean means number numbers page table work works use used get gets".split())
COMMON = (" The page text and site data are the character or monster the player is looking at right now; questions like "
          "'what actions can my character do?' are about that one and are answered from its values. Earlier turns of this "
          "conversation come before the latest question; the page snapshot is current. If neither passages nor page answer "
          "the question, say so plainly instead of guessing.")
REWRITE = ("You are the search step of a rules helper for {game}. From the question, the conversation and what is on screen, "
           "write 3 to 8 search terms a rulebook index would use for the rule meant: single words or two-word phrases, "
           "distinctive book words over common ones, the name of the class, spell or item when one is involved. The search "
           "is exact and also fuzzy (small spelling differences and OCR errors are tolerated), so spelling variants are "
           "wasted but synonyms the book might use are welcome. Reply with the terms separated by commas and nothing else.")
NOTE_PROMPT = ("You keep a note to yourself for answering {game} questions on this site, at most {max} characters. It is "
               "read before every question. Keep what helps: book words and section names that find the rule, terms that "
               "found nothing, mistakes to avoid. Given the current note and what just happened, reply with the new note "
               "only, or with the current note unchanged when nothing was learned. No preamble.")


class Vocab:
    """The words of a site's books, for widening a search term to its close spellings. Loaded once, on first use.
    ``normalize`` puts the term into the books' word form first (the FTS stem: grapling -> grapl, close to grappl)."""

    def __init__(self, load: Callable[[], list[str]], normalize: Callable[[str], str] = lambda t: t):
        self._load, self._by, self.normalize = load, None, normalize

    def close(self, term: str, n: int = 3, cutoff: float = 0.82) -> list[str]:
        if self._by is None:
            self._by = {}
            for w in self._load():
                self._by.setdefault((w[:1], len(w)), []).append(w)
        term = self.normalize(term)
        candidates = [w for L in range(len(term) - 2, len(term) + 3) for w in self._by.get((term[:1], L), [])]
        return [w for w in difflib.get_close_matches(term, candidates, n=n, cutoff=cutoff) if w != term]


def fts_vocab(index_path: Path, table: str, tokenize: str = "porter") -> Vocab:
    """A Vocab over an FTS5 table's terms; terms are normalized with the same tokenizer, so stems meet stems."""
    def load():
        if not index_path.exists():
            return []
        conn = sqlite3.connect(f"file:{index_path}?mode=ro", uri=True)
        try:
            conn.execute(f"CREATE VIRTUAL TABLE temp.v USING fts5vocab(main, '{table}', 'row')")
            return [r[0] for r in conn.execute("SELECT term FROM temp.v WHERE length(term) > 3")]
        finally:
            conn.close()

    def normalize(term):
        conn = sqlite3.connect(":memory:")
        conn.execute(f"CREATE VIRTUAL TABLE t USING fts5(x, tokenize='{tokenize}')")
        conn.execute("INSERT INTO t VALUES (?)", (term,))
        conn.execute("CREATE VIRTUAL TABLE v USING fts5vocab('t', 'row')")
        return " ".join(r[0] for r in conn.execute("SELECT term FROM v")) or term
    return Vocab(load, normalize)


@dataclass
class Site:
    name: str
    game: str
    system: str
    search: Callable[[list[list[str]], dict], list[dict]]  # term groups (term + its close spellings), request -> passages
    vocab: Vocab | None = None
    default_question: str = "What is this, and what does it mean for my character?"
    #: a passage is {"cite": "PHB p. 195" | "p. 18" | "house rule", "title": ..., "body": ...}


def event(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def stream_model(messages: list[dict], max_tokens: int = 320):
    """Text pieces from the first llama.cpp server that answers; OSError when none does, TimeoutError when busy."""
    body = json.dumps({"model": MODEL, "messages": messages, "stream": True, "max_tokens": max_tokens, "temperature": 0.2}).encode()
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


def keywords(*texts: str, limit: int = 14) -> list[str]:
    """Plain words of the texts, stopwords out, coins spelled out (gp -> gold pieces); the fallback when no model answers."""
    seen: list[str] = []
    COINS = {"gp": "gold", "sp": "silver", "cp": "copper"}
    for text in texts:
        text = re.sub(r"\b(gp|sp|cp)\b", lambda m: COINS[m.group(1)] + " pieces", text or "")
        for word in re.findall(r"[A-Za-z][A-Za-z'’-]{2,}", text):
            w = word.lower().strip("'’-")
            if w not in STOPWORDS and w not in seen:
                seen.append(w)
    return seen[:limit]


def note(site: Site) -> str:
    try:
        return (NOTES_DIR / f"{site.name}.txt").read_text()[:NOTE_MAX].strip()
    except OSError:
        return ""


def update_note(site: Site, question: str, terms: list[str], found: list[dict], answer: str) -> None:
    """Pass 3, after the answer: the model rewrites its note to self for this site. Runs in a thread; failures are dropped."""
    current = note(site)
    user = (f"Current note:\n{current or '(empty)'}\n\nQuestion: {question[:300]}\nSearch terms you chose: {', '.join(terms)}\n"
            f"Passages found: {'; '.join(f['title'] for f in found[:6]) or 'none'}\nYour answer: {answer[:700]}")
    try:
        new = "".join(stream_model([{"role": "system", "content": NOTE_PROMPT.format(game=site.game, max=NOTE_MAX)},
                                    {"role": "user", "content": user}], max_tokens=220)).strip()
        new = re.sub(r"^(current|new) note:\s*", "", new, flags=re.I)[:NOTE_MAX]  # the model likes to echo the label
        if new and new != current:
            NOTES_DIR.mkdir(parents=True, exist_ok=True)
            (NOTES_DIR / f"{site.name}.txt").write_text(new)
    except (OSError, ValueError, KeyError):
        pass


def search_terms(site: Site, d: dict, thread: list[dict], question: str) -> list[str]:
    """Pass 1: the model names the rule in book words; the question's own words follow as a safety net."""
    screen = " ".join(filter(None, [d.get("hint"), d.get("text"), str(d.get("site_data") or "")[:400], str(d.get("page_text") or "")[:400]]))
    history = "\n".join(f"Q: {t.get('q', '')[:200]}\nA: {t.get('a', '')[:300]}" for t in thread[-2:])
    user = f"Conversation so far:\n{history}\n\n" if history else ""
    user += f"On screen: {screen[:900]}\n\nQuestion: {question[:500]}"
    memo = note(site)
    system = REWRITE.format(game=site.game) + (f"\nYour note to self from earlier questions: {memo}" if memo else "")
    try:
        raw = "".join(stream_model([{"role": "system", "content": system}, {"role": "user", "content": user}], max_tokens=60))
        terms = [t.strip().lower() for t in re.sub(r"[^\w ,'-]", " ", raw).split(",") if 2 < len(t.strip()) < 40]
    except (OSError, ValueError, KeyError):
        terms = []
    # the question's own words only when no model answered: mixed in, they double-count ("shield" + "sheild") and
    # drag in filler ("while", "holding") that outranks the rare rule word
    return (terms or keywords(question, d.get("hint") or ""))[:12]


def expand(terms: list[str], vocab: Vocab | None) -> list[list[str]]:
    """Each term with its close spellings in the books; phrases stay as they are. Terms that are the same book word
    (grapple, grappling) form one group, so a rule is not counted twice."""
    groups, seen = [], set()
    for t in terms:
        key = vocab.normalize(t) if vocab else t
        if key in seen:
            continue
        seen.add(key)
        groups.append([t] + (vocab.close(t) if vocab and " " not in t else []))
    return groups


def breadcrumb_line(crumbs) -> str:
    """[{tag, id, class, label}] from the page -> 'main > div.panel.inventory-panel (Inventory) > input[name=coin_gp]'."""
    parts = []
    for c in crumbs or []:
        if not isinstance(c, dict):
            continue
        s = str(c.get("tag", "")).lower()
        if c.get("id"):
            s += f"#{c['id']}"
        if c.get("class"):
            s += "." + ".".join(str(c["class"]).split()[:3])
        if c.get("name"):
            s += f"[name={c['name']}]"
        if c.get("label"):
            s += f" ({str(c['label'])[:60]})"
        parts.append(s)
    return " > ".join(parts)[:600]


def user_prompt(d: dict, found: list[dict], question: str) -> str:
    """The latest user turn: where on the page, what is on screen, what was clicked, the passages, the question."""
    parts = [f"Page: {str(d.get('page') or '')[:120]}"]
    crumb = breadcrumb_line(d.get("breadcrumb"))
    if crumb:
        parts.append(f"Where on the page (outermost to the clicked element): {crumb}")
    if d.get("site_data"):
        parts.append(f"Site data for what is on screen: {str(d.get('site_data'))[:3000]}")
    if d.get("page_text"):
        parts.append(f"Page text, what the player sees right now (the character or monster in question):\n{str(d.get('page_text'))[:6000]}")
    if d.get("html"):
        parts.append(f"Clicked element (HTML): {str(d.get('html'))[:2200]}")
    if d.get("context"):
        parts.append(f"Text around it: {str(d.get('context'))[:1200]}")
    if isinstance(d.get("entry"), dict):  # the 5e "Explain this" button: the rules entry itself
        parts.append(f"Entry: {d['entry'].get('name', '')}\n{str(d['entry'].get('text', ''))[:2500]}")
    text, used = [], 0
    for f in found:
        if used + len(f["body"]) > PASSAGE_BUDGET:
            break
        text.append(f"[{f['cite']}: {f['title']}] {f['body']}")
        used += len(f["body"])
    parts.append("Passages:\n" + ("\n\n".join(text) or "none found"))
    parts.append(f"Question: {question[:400]}")
    return "\n\n".join(parts)


def respond(site: Site, d: dict):
    """Server-sent events for one question: {'text': piece}..., then {'done': true, 'passages': [...], 'terms': [...]}."""
    thread = [t for t in (d.get("thread") or []) if isinstance(t, dict)][-THREAD_TURNS:]
    clicked = bool(d.get("html") or d.get("breadcrumb") or d.get("entry"))
    question = str(d.get("question") or "").strip() or (site.default_question if clicked else "")
    terms = search_terms(site, d, thread, question)
    found = site.search(expand(terms, site.vocab), d)
    memo = note(site)
    messages = [{"role": "system", "content": site.system + COMMON + (f" Your note to self from earlier questions: {memo}" if memo else "")}]
    for t in thread:
        messages += [{"role": "user", "content": str(t.get("q", ""))[:600]}, {"role": "assistant", "content": str(t.get("a", ""))[:800]}]
    messages.append({"role": "user", "content": user_prompt(d, found, question)})
    answer = []
    try:
        for piece in stream_model(messages):
            answer.append(piece)
            yield event({"text": piece})
    except TimeoutError:  # the model answers one request at a time; another service holds it
        yield event({"error": "Model currently busy, check back in a minute."})
    except (OSError, ValueError, KeyError):
        yield event({"error": "Model currently unavailable."})
    yield event({"done": True, "terms": terms, "passages": [{"cite": f["cite"], "title": f["title"], "text": f["body"][:600]} for f in found[:4]]})
    if answer:
        threading.Thread(target=update_note, args=(site, question, terms, found, "".join(answer)), daemon=True).start()


PORTAL_URL = os.environ.get("PORTAL_URL", "http://portal:8888")


def premium_of(user: str) -> bool:
    """dodo-dodo premium from the home app; an unreachable home app counts as premium so nobody is locked out."""
    if not user:
        return False
    try:
        req = urllib.request.Request(f"{PORTAL_URL}/api/premium/me", headers={"Remote-User": user})
        with urllib.request.urlopen(req, timeout=3) as response:
            return bool(json.loads(response.read().decode()).get("premium"))
    except (OSError, json.JSONDecodeError):
        return True


# --- quota: answered questions per user, every site counts into the same pot ---------------------------------
def _quota_conn() -> sqlite3.Connection:
    QUOTA_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(QUOTA_DB, timeout=10)
    conn.execute("CREATE TABLE IF NOT EXISTS answered (user TEXT NOT NULL, site TEXT, ts TEXT NOT NULL)")
    return conn


def quota_block(user: str, premium: bool) -> tuple[str, int] | None:
    """(message, http status) when this user may not ask now, else None."""
    conn = _quota_conn()
    try:
        now = datetime.now(timezone.utc).timestamp()
        def since(seconds):
            t = datetime.fromtimestamp(now - seconds, timezone.utc).isoformat(timespec="seconds")
            return conn.execute("SELECT count(*) FROM answered WHERE user = ? AND ts > ?", (user, t)).fetchone()[0]
        if not premium and since(3600) >= FREE_PER_HOUR:
            return ("One question an hour is free; more is a dodo-dodo Premium feature (up to 100 a day). "
                    "Pitch in for the server on home.dodo-dodo.de.", 403)
        if premium and since(86400) >= PREMIUM_PER_DAY:
            return (f"That was {PREMIUM_PER_DAY} questions in a day, the premium limit. The helper is yours again tomorrow.", 429)
    finally:
        conn.close()
    return None


def record_answered(user: str, site: str) -> None:
    conn = _quota_conn()
    try:
        conn.execute("INSERT INTO answered (user, site, ts) VALUES (?, ?, ?)", (user, site, datetime.now(timezone.utc).isoformat(timespec="seconds")))
        conn.commit()
    finally:
        conn.close()


def counted_stream(events, user: str, site: str):
    """Pass the events through; count the question once the model has said something."""
    answered = False
    for ev in events:
        answered = answered or ev.startswith('data: {"text"')
        yield ev
    if answered and user:
        record_answered(user, site)


def serve(site: Site, user: str, premium: bool, d: dict):
    """What a site's /api/explain route returns: (error message, status) when blocked, else the counted SSE generator."""
    block = quota_block(user, premium)
    if block:
        return block
    return counted_stream(respond(site, d), user, site.name)
