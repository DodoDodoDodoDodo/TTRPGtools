"""Character builder and sheet: page shell plus JSON API under /TTRPG/dnd5e/characters.

The page is a Svelte app (frontend/dnd5e, built into static/dnd5e/builder/).
Characters are decision logs in characters/dnd5e/<id>.json; every read returns
the derived sheet next to the log. A save carries the version it was based on
and is refused with 409 if another tab saved in between.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
import secrets
from datetime import datetime, timezone
from pathlib import Path

from flask import Blueprint, Response, abort, jsonify, make_response, render_template, request, send_file, stream_with_context

from ttrpgtools.dnd5e import bestiary, campaigns, content as book_list, db
from ttrpgtools.dnd5e import character as ch
from ttrpgtools.dnd5e import ddb_character
from ttrpgtools.dnd5e import explain
from ttrpgtools import helper
from ttrpgtools.dnd5e.ddb_import import import_ddb
from ttrpgtools.permissions import may_delete

bp = Blueprint("dnd5e_builder", __name__, url_prefix="/TTRPG/dnd5e/characters")

CHARACTERS_DIR = Path(__file__).resolve().parents[2] / "characters" / "dnd5e"
CONTENT_KINDS = ("classes", "races", "backgrounds", "feats", "optionalfeatures", "spells", "items", "languages", "conditions", "names", "alignments", "lifestyles", "actions", "abilitytexts", "ruletexts", "books", "meta")
#: Short and revalidated, never immutable: a bad response must heal itself (CLAUDE.md rule).
CACHE = "public, max-age=60, must-revalidate"


class ApiError(Exception):
    def __init__(self, message: str, status: int = 400, **extra):
        super().__init__(message)
        self.status = status
        self.extra = extra


@bp.errorhandler(ApiError)
def _api_error(exc: ApiError):
    return jsonify({"error": str(exc), **exc.extra}), exc.status


def _owner() -> str | None:
    return request.headers.get("Remote-User") or None


#: may hand characters to players; the same names as the home app's admins (bird-tube main.py _ADMINS)
ADMINS = {"dodo", "takahe", "admin_birb"}
#: the home app, container to container; it knows who is genuinely active (bird-tube activity.py)
PORTAL_URL = os.environ.get("PORTAL_URL", "http://portal:8888")


def _has_premium() -> bool:
    """dodo-dodo premium from the home app. Admins count as premium; when the home app cannot be asked the
    answer is yes, so nobody loses the phone layout to an outage."""
    user = _owner()
    if not user or user in ADMINS:
        return True
    req = urllib.request.Request(f"{PORTAL_URL}/api/premium/me", headers={"Remote-User": user})
    try:
        with urllib.request.urlopen(req, timeout=3) as response:
            return bool(json.loads(response.read().decode()).get("premium"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return True


def _premium_gate(name: str = ""):
    """One character per player is free; a second one needs dodo-dodo premium (Dodo, 2026-10-22).
    Admins are exempt, and when the home app cannot be asked the character is allowed."""
    user = _owner()
    if not user or user in ADMINS:
        return
    owned = 0
    for path in CHARACTERS_DIR.glob("*.json"):
        try:
            owned += json.loads(path.read_text()).get("owner") == user
        except (OSError, json.JSONDecodeError):
            continue
    if not owned:
        return
    req = urllib.request.Request(f"{PORTAL_URL}/api/premium/me", headers={"Remote-User": user})
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            if json.loads(response.read().decode()).get("premium"):
                return
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return
    name = name.strip() or "your new character"
    raise ApiError(f"Don't lose {name}! Having more than one character is a dodo-dodo Premium feature. "
                   "Pitch in for the server on home.dodo-dodo.de and it unlocks.", 403, pitch_in="/#contrib", doomed=name)


def _premium_of(user: str) -> bool:
    """Whether this player (not the one asking) has premium; admins do, and an unreachable home app says yes."""
    if not user or user in ADMINS:
        return True
    req = urllib.request.Request(f"{PORTAL_URL}/api/premium/me", headers={"Remote-User": user})
    try:
        with urllib.request.urlopen(req, timeout=3) as response:
            return bool(json.loads(response.read().decode()).get("premium"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return True


def _locked(char_id: str, char: dict) -> str | None:
    """Without premium a player edits only their first character (Dodo, 2026-10-24); the others stay readable.
    Admins edit everything. Returns the reason, or None."""
    owner = char.get("owner")
    if not owner or _owner() in ADMINS:
        return None
    mine = []
    for path in CHARACTERS_DIR.glob("*.json"):
        try:
            other = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if other.get("owner") == owner:
            mine.append((other.get("created") or "", path.stem))
    if not mine or min(mine)[1] == char_id or _premium_of(owner):
        return None
    name = char.get("name") or "this character"
    return (f"Don't lose {name}! Editing more than one character is a dodo-dodo Premium feature, so {name} is read only. "
            "Pitch in for the server on home.dodo-dodo.de and it unlocks.")


def _admin_only():
    if _owner() not in ADMINS:
        raise ApiError("Only an admin can do that.", 403)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _path(char_id: str) -> Path:
    if not re.fullmatch(r"[a-z0-9-]{1,80}", char_id):
        raise ApiError("Bad character id.", 404)
    return CHARACTERS_DIR / f"{char_id}.json"


def _read(char_id: str) -> dict:
    path = _path(char_id)
    if not path.exists():
        raise ApiError("No such character.", 404)
    return json.loads(path.read_text())


HISTORY_DIR = CHARACTERS_DIR / ".history"


def _snapshot(char_id: str, char: dict, day: str | None = None) -> None:
    """One snapshot per character per day with a change (Dodo, 2026-10-25: anyone may edit, anyone may revert);
    a later save the same day replaces that day's snapshot."""
    day = day or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    folder = HISTORY_DIR / char_id
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{day}.json").write_text(json.dumps(char, ensure_ascii=False, indent=1))


def _write(char_id: str, char: dict) -> None:
    CHARACTERS_DIR.mkdir(parents=True, exist_ok=True)
    path = _path(char_id)
    if path.exists():  # the first change of a day keeps the state before it, under the day it was last saved
        before = json.loads(path.read_text())
        day = str(before.get("updated") or "")[:10] or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if not (HISTORY_DIR / char_id / f"{day}.json").exists():
            _snapshot(char_id, before, day)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(char, ensure_ascii=False, indent=1))
    os.replace(tmp, path)
    _snapshot(char_id, char)


def _new_id(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "character"
    return f"{base}-{secrets.token_hex(2)}"


def _summary(char_id: str, char: dict, campaign_names: dict | None = None) -> dict:
    classes = [c for c in char.get("classes", []) if c.get("id")]
    looks = char.get("description") or {}
    return {"id": char_id, "name": char.get("name", ""), "owner": char.get("owner"), "updated": char.get("updated"), "created": char.get("created"),
            "avatar": looks.get("avatar_url"), "theme": looks.get("theme"),
            "backdrop": looks.get("backdrop_url") or looks.get("backdrop") or (classes[0]["id"] if classes else None),
            "level": sum(int(c.get("level", 1)) for c in classes),
            "classes": [f"{c['id'].title()} {c.get('level', 1)}" for c in classes],
            "race": (char.get("race") or {}).get("id"), "campaigns": (campaign_names or {}).get(char_id, [])}


def _with_sheet(char_id: str, char: dict) -> dict:
    return {"id": char_id, "character": char, "sheet": ch.derive(char), "campaigns": campaigns.of_character(char_id),
            "locked": _locked(char_id, char)}


# ------------------------------------------------------------------ pages
@bp.get("/", defaults={"rest": ""})
@bp.get("/<path:rest>")
def shell(rest):
    if rest.startswith("api/"):
        abort(404)
    built = Path(__file__).resolve().parents[1] / "web" / "static" / "dnd5e" / "builder" / "builder.js"
    version = int(built.stat().st_mtime) if built.exists() else 0
    return render_template("dnd5e/dnd5e_builder.html", build_version=version, admin=_owner() in ADMINS, premium=_has_premium())


# ------------------------------------------------------------------ DDB frames and fonts
DDB_DIR = Path(__file__).resolve().parents[2] / "content" / "dnd5e" / "private" / "ddb"
DDB_SUBDIRS = ("svg", "assets", "builder", "fonts", "img")


_FRAME_CLASS = re.compile(r'class="ddbc-svg ([a-z-]+)-svg')


#: Frames without a class attribute, by the sha1 key grab.py gave them (context from index.json, desktop size).
_UNNAMED_FRAMES = {
    "proficiency-bonus-box": "b9b37f19c6f1", "speed-box": "3dde08ce0ebb", "hit-points-box": "ec287fa893ff",
    "saving-throws-box": "9c7dd51edd19", "senses-callout": "f8a4ced28a5c", "proficiency-groups-box": "b3da5ddee62a",
    "skills-box": "c0523f4f4454", "value-box": "76d3da9572ed", "combat-statuses": "861630cc1d95",
    "primary-box": "dbe48bccbe23", "attunement-box": "94878ac8a7b9",
}


def _frames() -> dict[str, Path]:
    """DDB frame name ("ability-score-box") -> svg file, read from each file's own class attribute."""
    out: dict[str, Path] = {name: next(iter((DDB_DIR / "svg").glob(f"*__{key}.svg")), None)
                            for name, key in _UNNAMED_FRAMES.items()}
    out = {k: v for k, v in out.items() if v}
    for path in sorted((DDB_DIR / "svg").glob("*.svg")):
        m = _FRAME_CLASS.search(path.read_text()[:400])
        if m:
            out.setdefault(m.group(1).removeprefix("ddbc-"), path)
    return out


_CSS_URL = re.compile(r"url\(\s*['\"]?(https?://([^/'\")]+)/([^'\")?#]+))[^)]*\)")


#: DDB stylesheets we serve, in the order a DDB builder page loads them (site first, character app last).
DDB_STYLESHEETS = {"site": "css-main.css", "tooltip": "css-core-tooltip.css", "character-app": "css-main.875602ca.css"}


#: Parts of DDB's newer builder (play/characters/build) used on our pages: name -> (stylesheets, CSS-module keys).
DDB_EXTRACTS = {"species-cards": (("css-32tv7ohqb01wt.css", "css-2mo-5yhbr56uh.css"), ("sK4ika", "EPiRJW", "tmzXDW")),
                "foyer": (("css-2mo-5yhbr56uh.css", "css-32tv7ohqb01wt.css"),
                          ("_8aEwW", "HJ046W", "a0NR4a", "FJBYHa", "Nepbjq", "Aryy7a", "KetiBq", "XmxzHG", "kXd57W", "EPiRJW", "_iwSUW", "5t3tra", "OUwkBG", "raWPyq", "WO0BgG", "tmzXDW")),
                "class-detail": (("css-0vqov8dbjhn--.css", "css-2mo-5yhbr56uh.css", "css-32tv7ohqb01wt.css"),
                                 ("oQuihG", "zQU0aW", "EfttyG", "LS0KTq", "txXWja", "fl6YuG", "zfee_G", "0u7Fdq", "jjeeRW", "PzKZ2G", "j7mhJq", "tmzXDW", "EPiRJW", "bo3sjW", "MHRkpa", "AD-FeG", "kXd57W"))}


def _css_blocks(css: str):
    """Top-level (prelude, body) pairs of a minified stylesheet; nested braces stay inside body."""
    depth, start, prelude_end = 0, 0, None
    for i, ch in enumerate(css):
        if ch == "{":
            if depth == 0:
                prelude_end = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                yield css[start:prelude_end].strip(), css[prelude_end + 1:i]
                start = i + 1


def extract_css(css_files: tuple, keys: tuple, scope: str) -> str:
    """The rules of the given CSS modules (and their @media wrappers), plus every custom property and
    font face they use, the properties re-declared on `scope` so the newer builder's design tokens
    cannot leak into the older pages. Tokens and faces may sit in any of DDB's saved chunks."""
    rules, definitions, faces = [], {}, []
    for sheet in sorted((DDB_DIR / "css").glob("css-*.css")):
        own = sheet.name in css_files
        for prelude, body in _css_blocks(sheet.read_text()):
            if prelude.startswith(("@media", "@supports")):
                inner = [f"{p}{{{b}}}" for p, b in _css_blocks(body) if any(k in p for k in keys)]
                if inner and own:
                    rules.append(f"{prelude}{{{''.join(inner)}}}")
            elif prelude == "@font-face":
                faces.append(body)
            elif prelude.startswith("@"):
                continue
            elif any(k in prelude for k in keys):
                if own:
                    rules.append(f"{prelude}{{{body}}}")
            else:
                for decl in body.split(";"):
                    if decl.strip().startswith("--") and ":" in decl:
                        var, value = decl.split(":", 1)
                        definitions.setdefault(var.strip(), value.strip())
    needed, queue = set(), re.findall(r"var\((--[\w-]+)", "".join(rules))
    while queue:
        var = queue.pop()
        if var in needed or var not in definitions:
            continue
        needed.add(var)
        queue.extend(re.findall(r"var\((--[\w-]+)", definitions[var]))
    tokens = ";".join(f"{v}:{definitions[v]}" for v in sorted(needed))
    used = tokens + "".join(rules)
    family = lambda face: re.search(r"font-family:\s*['\"]?([^;'\"]+)", face).group(1).strip()
    fonts = "".join(f"@font-face{{{face}}}" for face in dict.fromkeys(faces) if family(face) in used)
    return fonts + f"{scope}{{{tokens}}}" + "".join(rules)


@bp.get("/ddb/<name>.css")
def ddb_stylesheet(name):
    """A DDB stylesheet unchanged except that its images and fonts point at our private copies
    and its Google Fonts import is dropped (no requests to DDB or Google)."""
    if name == "vars":
        return ddb_vars_css()
    if name in DDB_EXTRACTS:
        css = extract_css(*DDB_EXTRACTS[name], scope=".ddb-new-builder")
    elif name in DDB_STYLESHEETS:
        css = (DDB_DIR / "css" / DDB_STYLESHEETS[name]).read_text()
    else:
        abort(404)
    base = request.script_root + bp.url_prefix + "/ddb/assets/"

    def local(m):
        host, path = m.group(2), m.group(3)
        if (DDB_DIR / "assets" / host / path).is_file():
            return f'url("{base}{host}/{path}")'
        return "url(data:,)" if host.startswith("fonts.") else m.group(0)

    css = re.sub(r"@import[^;]+;", "", css)
    css = _CSS_URL.sub(local, css)
    response = make_response(css)
    response.mimetype = "text/css"
    response.headers["Cache-Control"] = "public, max-age=300, must-revalidate"
    return response


def ddb_vars_css():
    """DDB's theme variables and tooltip styles: the inline <style> blocks of a saved builder page,
    minus their site navigation (lanyard) and anything empty."""
    capture = json.loads((DDB_DIR / "builder" / "ddb-class-level-select.json").read_text())
    blocks = [b for b in capture.get("inlineStyles", []) if b.strip() and "#lanyard_root" not in b and "TIZEN" not in b]
    response = make_response("\n".join(blocks))
    response.mimetype = "text/css"
    response.headers["Cache-Control"] = "public, max-age=300, must-revalidate"
    return response


@bp.get("/ddb/frames.json")
def ddb_frames():
    """DDB's sheet frames and icons lifted from a saved sheet (extract_frames.py), in the character's colour."""
    path = DDB_DIR / "frames.json"
    if not path.exists():
        raise ApiError("frames.json is not built on this server.", 503)
    theme = request.args.get("theme", "")
    colour = f"#{theme}" if re.fullmatch(r"[0-9a-fA-F]{6}", theme) else "#C53131"
    response = make_response(path.read_text().replace("THEME", colour))
    response.mimetype = "application/json"
    response.headers["Cache-Control"] = "public, max-age=300, must-revalidate"
    return response


@bp.get("/ddb/frame/<name>")
def ddb_frame(name):
    """A frame by name, made stretchable: our boxes are sized by content, DDB's were fixed."""
    path = _frames().get(name)
    theme = request.args.get("theme", "")
    colour = f"#{theme}" if re.fullmatch(r"[0-9a-fA-F]{6}", theme) else "#C53131"
    if path is not None:
        body = path.read_text().replace("#C53131", colour).replace("#c53131", colour)
    else:  # the sheet's own box frames (frames.json, extract_frames.py), e.g. "saving-throws"
        sheet_frames = json.loads((DDB_DIR / "frames.json").read_text())["frames"] if (DDB_DIR / "frames.json").exists() else {}
        if name not in sheet_frames:
            abort(404)
        body = sheet_frames[name].replace("THEME", colour)
        if "xmlns=" not in body[:200]:
            body = body.replace("<svg ", '<svg xmlns="http://www.w3.org/2000/svg" ', 1)
    if "preserveAspectRatio" not in body[:300]:
        body = body.replace("<svg ", '<svg preserveAspectRatio="none" ', 1)
    if request.args.get("outline") == "1":  # only the border, e.g. laid over artwork (the 5e hub tiles)
        body = body.replace('fill="#FEFEFE"', 'fill="none"').replace('fill="#fefefe"', 'fill="none"')
    response = make_response(body)
    response.mimetype = "image/svg+xml"
    response.headers["Cache-Control"] = "public, max-age=300, must-revalidate"
    return response


@bp.get("/ddb/<path:asset>")
def ddb_asset(asset):
    """The grabbed DDB frames, icons, textures and fonts; private, so served from content/, not static/.
    SVG frames carry DDB's red inline; ?theme=RRGGBB swaps it for the character's colour."""
    top = asset.split("/", 1)[0]
    path = (DDB_DIR / asset).resolve()
    if top not in DDB_SUBDIRS or DDB_DIR.resolve() not in path.parents or not path.is_file():
        abort(404)
    theme = request.args.get("theme", "")
    if path.suffix == ".svg" and re.fullmatch(r"[0-9a-fA-F]{6}", theme):
        body = path.read_text().replace("#C53131", f"#{theme}").replace("#c53131", f"#{theme}")
        response = make_response(body)
        response.mimetype = "image/svg+xml"
    else:
        response = send_file(path, conditional=True, max_age=300)
    response.headers["Cache-Control"] = "public, max-age=300, must-revalidate"
    return response


# ------------------------------------------------------------------ campaigns

def _may_move(char: dict, campaign: dict | None = None) -> bool:
    """A character joins or leaves by its owner (or an admin); the campaign's DM may also add it or take it out."""
    user = _owner()
    return (not user or user in ADMINS or char.get("owner") in (None, "", user)
            or (campaign is not None and campaign.get("dm") == user))


@bp.get("/api/campaigns")
def list_campaigns():
    return jsonify(campaigns.all_campaigns())


@bp.post("/api/campaigns")
def create_campaign():
    body = request.get_json(silent=True) or {}
    try:
        return jsonify(campaigns.create(str(body.get("name") or ""), _owner(), str(body.get("description") or ""))), 201
    except ValueError as exc:
        raise ApiError(str(exc)) from None


@bp.delete("/api/campaigns/<campaign_id>")
def delete_campaign(campaign_id):
    campaign = campaigns.get(campaign_id)
    if campaign is None:
        raise ApiError("No such campaign.", 404)
    user = _owner()
    if user and user not in ADMINS and campaign.get("dm") != user:
        raise ApiError("Only the campaign's DM can delete it.", 403)
    campaigns.delete(campaign_id)
    return jsonify({"deleted": campaign_id})


@bp.post("/api/campaigns/<campaign_id>/characters")
def join_campaign(campaign_id):
    char_id = str((request.get_json(silent=True) or {}).get("character_id") or "")
    char = _read(char_id)
    campaign = campaigns.get(campaign_id)
    if campaign is None:
        raise ApiError("No such campaign.", 404)
    if not _may_move(char, campaign):  # the player brings it in, or the DM adds it (Dodo, 2026-10-23)
        raise ApiError("Only the character's player or the campaign's DM can bring it into a campaign.", 403)
    return jsonify(campaigns.join(campaign_id, char_id, _owner()))


@bp.delete("/api/campaigns/<campaign_id>/characters/<char_id>")
def leave_campaign(campaign_id, char_id):
    campaign = campaigns.get(campaign_id)
    if campaign is None:
        raise ApiError("No such campaign.", 404)
    if not _may_move(_read(char_id), campaign):
        raise ApiError("Only the character's player or the campaign's DM can take it out.", 403)
    return jsonify(campaigns.leave(campaign_id, char_id))


# ------------------------------------------------------------------ content
@bp.get("/api/content/<kind>")
def content(kind):
    if kind not in CONTENT_KINDS:
        raise ApiError("Unknown content kind.", 404)
    path = ch.DATA_DIR / f"{kind}.json"
    if not path.exists():
        raise ApiError("Builder data is not built on this server.", 503)
    response = send_file(path, mimetype="application/json", conditional=True, etag=True, max_age=60)
    response.headers["Cache-Control"] = CACHE
    return response


# ------------------------------------------------------------------ characters
@bp.get("/api/characters")
def list_characters():
    CHARACTERS_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    names = campaigns.by_character()
    for path in sorted(CHARACTERS_DIR.glob("*.json")):
        try:
            rows.append(_summary(path.stem, json.loads(path.read_text()), names))
        except (OSError, json.JSONDecodeError):
            continue
    return jsonify(sorted(rows, key=lambda r: r.get("updated") or "", reverse=True))


@bp.get("/api/recent")
def recent_for_user():
    """The hub's small "recent" tiles: the logged-in player's last-saved character, the campaign they last
    started or joined a character into, and their last-saved encounter."""
    user = _owner()
    out: dict = {}
    if not user:
        return jsonify(out)
    mine = []
    for path in CHARACTERS_DIR.glob("*.json"):
        try:
            char = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if char.get("owner") == user:
            mine.append((char.get("updated") or "", path.stem, char))
    if mine:
        _, char_id, char = max(mine)
        summary = _summary(char_id, char)
        out["character"] = {"id": char_id, "name": summary["name"] or "Unnamed",
                            "detail": " / ".join(summary["classes"]) or "No class yet", "avatar": summary["avatar"]}
    conn = db.connect()
    try:
        own_ids = {stem for _, stem, _ in mine}
        rows = conn.execute("SELECT c.id, c.name, c.created, m.character_id, m.joined FROM campaigns c "
                            "LEFT JOIN campaign_members m ON m.campaign_id = c.id").fetchall()
        # (time, id, name): one of the player's characters joined it, or the player started it as DM
        candidates = [(r["joined"], r["id"], r["name"]) for r in rows if r["character_id"] in own_ids and r["joined"]]
        candidates += [(r["created"], r["id"], r["name"]) for r in conn.execute("SELECT id, name, created FROM campaigns WHERE dm = ?", (user,))]
        best = max(candidates) if candidates else None
        if best:
            out["campaign"] = {"id": best[1], "name": best[2]}
        enc = conn.execute("SELECT id, name, updated FROM encounters WHERE owner = ? ORDER BY updated DESC LIMIT 1", (user,)).fetchone()
        if enc:
            out["encounter"] = {"id": enc["id"], "name": enc["name"]}
    finally:
        conn.close()
    return jsonify(out)


#: answered questions (Dodo, 2026-10-25): one an hour free; premium is a token amount, so it is capped at 100 a day
FREE_QUESTIONS_PER_HOUR = 1
PREMIUM_QUESTIONS_PER_DAY = 100


@bp.get("/api/explain/sources")
def explain_sources():
    return jsonify(sources=explain.sources())


@bp.post("/api/explain")
def explain_question():
    """The rules helper: server-sent events from explain.answer. A question only counts once the model answered."""
    body = request.get_json(silent=True) or {}
    user = _owner()
    if not user:
        raise ApiError("Log in to ask the rules helper.", 401)
    if not (body.get("question") or body.get("entry") or body.get("html") or body.get("breadcrumb")):
        raise ApiError("Ask a question first.")
    out = helper.serve(explain.SITE, user, _premium_of(user), body)
    if isinstance(out, tuple):
        raise ApiError(out[0], out[1], pitch_in="/#contrib" if out[1] == 403 else None)
    stream = out
    return Response(stream_with_context(stream), mimetype="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@bp.get("/api/users")
def users_for_assignment():
    """Admins: who a character can be handed to. ?all=1 lists everyone, else only active users."""
    _admin_only()
    query = "?all=1" if request.args.get("all") == "1" else ""
    req = urllib.request.Request(f"{PORTAL_URL}/api/users/activity{query}", headers={"Remote-User": _owner()})
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return jsonify(json.loads(response.read().decode()))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ApiError(f"The home app did not answer: {exc}", 503) from exc


@bp.put("/api/characters/<char_id>/owner")
def assign_character(char_id):
    """Admins: hand a character to a player (its owner)."""
    _admin_only()
    owner = str((request.get_json(silent=True) or {}).get("owner") or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", owner):
        raise ApiError("Pick a user.")
    char = _read(char_id)
    char["owner"] = owner
    char["updated"] = _now()
    char["version"] = int(char.get("version", 1)) + 1
    _write(char_id, char)
    return jsonify(_summary(char_id, char))


@bp.post("/api/characters")
def create_character():
    body = request.get_json(silent=True) or {}
    _premium_gate(str(body.get("name") or ""))
    name = str(body.get("name") or "New character").strip()[:80]
    char = {"name": name, "owner": _owner(), "created": _now(), "updated": _now(), "version": 1,
            "abilities": {"method": "standard", "base": {a: 10 for a in ch.ABILITIES}},
            "race": {}, "background": {}, "classes": [], "inventory": [], "currency": {}, "play": {},
            "description": {}, "notes": ""}
    char_id = _new_id(name)
    _write(char_id, char)
    return jsonify(_with_sheet(char_id, char)), 201


@bp.post("/api/characters/<char_id>/copy")
def copy_character(char_id):
    """DDB's Copy: the same build under a new id for the requester; play state, campaigns and owner start fresh."""
    source = _read(char_id)
    name = f"{source.get('name') or 'Character'} (copy)"[:80]
    _premium_gate(name)
    char = {**source, "name": name, "owner": _owner(), "created": _now(), "updated": _now(), "version": 1, "play": {}}
    char.pop("source", None)
    new_id = _new_id(name)
    _write(new_id, char)
    return jsonify(_with_sheet(new_id, char)), 201


@bp.get("/api/characters/<char_id>")
def get_character(char_id):
    return jsonify(_with_sheet(char_id, _read(char_id)))


@bp.put("/api/characters/<char_id>")
def save_character(char_id):
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or not isinstance(body.get("character"), dict):
        raise ApiError("Send {\"character\": {...}, \"version\": n}.")
    current = _read(char_id)
    reason = _locked(char_id, current)
    if reason:
        raise ApiError(reason, 403, pitch_in="/#contrib", doomed=current.get("name"))
    if int(body.get("version", -1)) != int(current.get("version", 1)):
        raise ApiError("Someone saved this character in the meantime; reload to see their change.", 409)
    char = body["character"]
    for key in ("owner", "created", "source"):
        if key in current:
            char[key] = current[key]
    char["updated"] = _now()
    char["version"] = int(current.get("version", 1)) + 1
    _write(char_id, char)
    return jsonify(_with_sheet(char_id, char))


@bp.get("/api/characters/<char_id>/history")
def character_history(char_id):
    """The days this character can be reverted to, newest first (today's entry is the current state)."""
    _read(char_id)
    folder = HISTORY_DIR / char_id
    days = sorted((p.stem for p in folder.glob("*.json")), reverse=True) if folder.exists() else []
    return jsonify(days=days)


@bp.post("/api/characters/<char_id>/revert")
def revert_character(char_id):
    """Back to the state saved on a day; the revert is itself a change, so it can be undone the same way."""
    day = str((request.get_json(silent=True) or {}).get("day") or "")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day) or not (HISTORY_DIR / char_id / f"{day}.json").exists():
        raise ApiError("No snapshot for that day.", 404)
    current = _read(char_id)
    reason = _locked(char_id, current)
    if reason:
        raise ApiError(reason, 403, pitch_in="/#contrib", doomed=current.get("name"))
    char = json.loads((HISTORY_DIR / char_id / f"{day}.json").read_text())
    for key in ("owner", "created", "source"):
        if key in current:
            char[key] = current[key]
    char["updated"] = _now()
    char["version"] = int(current.get("version", 1)) + 1
    _write(char_id, char)
    return jsonify(_with_sheet(char_id, char))


@bp.delete("/api/characters/<char_id>")
def delete_character(char_id):
    path = _path(char_id)
    if not path.exists():
        raise ApiError("No such character.", 404)
    if not may_delete(json.loads(path.read_text()).get("owner")):
        raise ApiError("Only the character's player can delete it.", 403)
    trash = CHARACTERS_DIR / ".trash"
    trash.mkdir(exist_ok=True)
    os.replace(path, trash / f"{char_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}.json")
    return jsonify({"deleted": char_id})


@bp.get("/api/creatures")
def creatures():
    """Bestiary search for extras (familiars, companions, Wild Shape), 2014 Wizards books only."""
    conn = db.connect()
    try:
        rows = bestiary.search(conn, request.args.get("q", ""), limit=200)
        full = [bestiary.get_monster(conn, r["id"]) for r in rows]
    finally:
        conn.close()
    def official(m):
        titles = m.get("sources") or [m.get("source", "")]
        return any(book_list.book_of(re.sub(r"\s+p\.?\s*\d+.*$", "", t)) for t in titles)

    keep = [m for m in full if m and official(m)]
    return jsonify(keep[:40])


@bp.post("/api/derive")
def derive_preview():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ApiError("Send a character as JSON.")
    return jsonify(ch.derive(body))


@bp.post("/api/import-ddb")
def import_from_ddb():
    body = request.get_json(silent=True) or {}
    try:
        ddb = ddb_character.fetch(str(body.get("ref") or ""))
    except ddb_character.DDBError as exc:
        # 422, not 502: Cloudflare swaps an origin's 502 body for its own page and the reason would be lost
        raise ApiError(str(exc), 422) from exc
    except ValueError as exc:
        raise ApiError(str(exc)) from exc
    _premium_gate(str(ddb.get("name") or ""))  # after the fetch, so the refusal can name the character
    char = import_ddb(ddb)
    char.update(owner=_owner(), created=_now(), updated=_now(), version=1)
    char_id = _new_id(char.get("name") or "imported")
    _write(char_id, char)
    return jsonify(_with_sheet(char_id, char)), 201
