"""Monster pictures from 5etools for the bestiary: for every monster of the chosen books, the largest picture its
5etools entry lists (following `_copy` references and the same monster in another 2014 book), else its token.
Downloads into content/dnd5e/private/monster-art/5etools/ (private), about one file per second, skipping files
already there, so a second run continues where the first stopped. Then writes `image` onto every bestiary
monster of that name; real art replaces a token, never the other way round.

    python -m ttrpgtools.dnd5e.monster_art /path/to/5etools-src [--books MM VGM MTF MPMM CoS] [--no-tokens] [--dry-run]
    python -m ttrpgtools.dnd5e.monster_art --attach   # in the container: write the pictures from manifest.json onto the bestiary

The download run leaves manifest.json next to the pictures, so the container (which has the database but not the
5etools checkout) can attach them.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from . import db
from .fantasygrounds_import import ART_DIR

IMG_BASE = "https://5e.tools/img/"
#: the 2024-era books stay out (standing 2014-only rule); RHW is Ravenloft: The Horrors Within (2026)
SKIP_BOOKS = {"XDMG", "XMM", "XPHB", "RHW"}
DEFAULT_BOOKS = ["MM", "VGM", "MTF", "MPMM", "CoS"]
HEADERS = {"User-Agent": "Mozilla/5.0 (dodo-dodo TTRPG tools; private table use)"}


class Fluff:
    """5etools' picture index (fluff-bestiary-*.json) for every 2014 book."""

    def __init__(self, bestiary_dir: Path):
        self.entries: dict[tuple[str, str], dict] = {}
        index = json.loads((bestiary_dir / "index.json").read_text())
        for source, filename in index.items():
            path = bestiary_dir / f"fluff-{filename}"
            if source in SKIP_BOOKS or not path.exists():
                continue
            for entry in json.loads(path.read_text()).get("monsterFluff", []):
                self.entries[(entry["name"].lower(), entry["source"])] = entry
        self.sources_by_name: dict[str, list[str]] = {}
        for name, source in self.entries:
            self.sources_by_name.setdefault(name, []).append(source)

    def own(self, name: str, source: str, depth: int = 0) -> list[dict]:
        entry = self.entries.get((name.lower(), source))
        if not entry or depth > 5:
            return []
        images = [i for i in entry.get("images") or [] if i.get("type") == "image" and (i.get("href") or {}).get("path")]
        if images:
            return images
        ref = entry.get("_copy") or {}
        return self.own(ref.get("name", ""), ref.get("source", ""), depth + 1) if ref else []

    def best(self, name: str, source: str) -> dict | None:
        """The tallest picture: the monster's own, else the same monster's from another 2014 book."""
        images = self.own(name, source) or [i for s in self.sources_by_name.get(name.lower(), []) for i in self.own(name, s)]
        return max(images, key=lambda i: i.get("height") or 0) if images else None


def plan(fivetools: Path, books: list[str], tokens: bool) -> list[dict]:
    """One row per monster: name, book, picture path under 5e.tools/img/, and whether it is a token."""
    bestiary_dir = fivetools / "data" / "bestiary"
    fluff = Fluff(bestiary_dir)
    index = json.loads((bestiary_dir / "index.json").read_text())
    rows = []
    for book in books:
        for monster in json.loads((bestiary_dir / index[book]).read_text()).get("monster", []):
            picture = fluff.best(monster["name"], monster["source"])
            if picture:
                rows.append({"name": monster["name"], "book": book, "path": picture["href"]["path"], "token": False})
            elif tokens and monster.get("hasToken"):
                rows.append({"name": monster["name"], "book": book, "path": f"bestiary/tokens/{monster['source']}/{monster['name']}.webp", "token": True})
            else:
                rows.append({"name": monster["name"], "book": book, "path": None, "token": False})
    return rows


def download(rows: list[dict], delay: float = 1.0, max_errors: int = 10) -> dict:
    stats = {"downloaded": 0, "had": 0, "failed": []}
    errors_in_a_row = 0
    for row in rows:
        if not row["path"]:
            continue
        target = ART_DIR / "5etools" / row["path"]
        if target.exists():
            stats["had"] += 1
            continue
        url = IMG_BASE + urllib.parse.quote(row["path"])
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=30) as response:
                data = response.read()
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            stats["downloaded"] += 1
            errors_in_a_row = 0
            if stats["downloaded"] % 50 == 0:
                print(f"  {stats['downloaded']} downloaded", flush=True)
        except Exception as exc:  # noqa: BLE001 - any network failure is recorded, the run goes on
            stats["failed"].append(f"{row['name']} ({row['book']}): {exc}")
            errors_in_a_row += 1
            if errors_in_a_row >= max_errors:
                print(f"  stopping: {max_errors} failures in a row (last: {exc})", flush=True)
                break
        time.sleep(delay)
    return stats


def attach(rows: list[dict], conn) -> dict:
    """Write `image` onto every bestiary monster of each name that has a downloaded picture."""
    best: dict[str, dict] = {}
    for row in rows:
        if row["path"] and (ART_DIR / "5etools" / row["path"]).exists():
            current = best.get(row["name"].lower())
            if current is None or (current["token"] and not row["token"]):
                best[row["name"].lower()] = row
    stats = {"monsters": 0, "kept_art": 0}
    for record in conn.execute("SELECT id, name, data FROM monsters").fetchall():
        row = best.get(record["name"].lower())
        if not row:
            continue
        data = json.loads(record["data"])
        has_art = data.get("image") and not data.get("image_token")
        if row["token"] and has_art:  # a token never replaces a real picture (e.g. a Fantasy Grounds portrait)
            stats["kept_art"] += 1
            continue
        data["image"] = f"5etools/{row['path']}"
        data["image_token"] = row["token"]
        conn.execute("UPDATE monsters SET data = ? WHERE id = ?", (db.dumps(data), record["id"]))
        stats["monsters"] += 1
    return stats


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("fivetools", nargs="?", help="the 5etools-src checkout")
    parser.add_argument("--attach", action="store_true", help="only write manifest.json's pictures onto the bestiary")
    parser.add_argument("--books", nargs="+", default=DEFAULT_BOOKS)
    parser.add_argument("--no-tokens", action="store_true", help="no token fallback for monsters without art")
    parser.add_argument("--delay", type=float, default=1.0, help="seconds between downloads")
    parser.add_argument("--dry-run", action="store_true", help="only count")
    args = parser.parse_args(argv)
    manifest = ART_DIR / "5etools" / "manifest.json"
    if args.attach:
        with db.session() as conn:
            attached = attach(json.loads(manifest.read_text()), conn)
        print(f"pictures written onto {attached['monsters']} bestiary monsters; {attached['kept_art']} kept their own art instead of a token")
        return 0
    rows = plan(Path(args.fivetools), args.books, not args.no_tokens)
    art = sum(1 for r in rows if r["path"] and not r["token"])
    token = sum(1 for r in rows if r["token"])
    print(f"{len(rows)} monsters: {art} with art, {token} with a token only, {len(rows) - art - token} without a picture")
    if args.dry_run:
        return 0
    stats = download(rows, args.delay)
    print(f"downloaded {stats['downloaded']}, already had {stats['had']}, failed {len(stats['failed'])}")
    for line in stats["failed"][:20]:
        print("  failed:", line)
    known = json.loads(manifest.read_text()) if manifest.exists() else []
    merged = {(r["name"], r["book"]): r for r in known + rows}
    manifest.write_text(json.dumps(list(merged.values()), indent=0))
    with db.session() as conn:
        attached = attach(rows, conn)
    print(f"pictures written onto {attached['monsters']} bestiary monsters; {attached['kept_art']} kept their own art instead of a token")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
