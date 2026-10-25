# TTRPGtools

Three separate tools in one web app, served under `/TTRPG`.

| System | Code | Docs | Characters | Tests |
|---|---|---|---|---|
| Dark Heresy 1e | `ttrpgtools/dh1e/` | `docs/dh1e.md` | `characters/dh1e/` | `tests/dh1e/` |
| Dungeon Crawl Classics + west marches | `ttrpgtools/dcc/` | `docs/dcc.md` | `characters/dcc/` | `tests/dcc/` |
| D&D 5e (2014) | `ttrpgtools/dnd5e/` | `docs/dnd5e.md` | none | `tests/dnd5e/` |

Web layer: `ttrpgtools/web/` holds the front door (`app.py`), shared `base.html` and `style.css`, and one `templates/<system>/` and `static/<system>/` folder per system. Each system registers its own Flask blueprint (`<system>/routes.py`).

## Run

```
pip install -r requirements.txt
python -m ttrpgtools.web          # dev server
python -m pytest tests -q
docker compose -f /home/dodo/stacks/core/ttrpgtools-compose.yml up -d --build sheet   # deploy
```

## Rulebooks and private content

Rulebook text is not in git. DH1e: put `core_all.txt`, `core_tables.txt` and `DH1e_cleaned.txt` in `rulebooks/dh1e/`. DCC extracts go to `content/dcc/private/` (see `docs/dcc.md`).

## Conventions

- Code over docs: when they disagree, fix the doc.
- Match existing style; reuse helpers before writing new ones; no new dependencies without a reason.
- Small commits with green tests. Docs stay short.
- No emoji.

Planning notes: `docs/DESIGN.md`. Branches: `main` (integration), `dh1e`, `dcc`, `dnd5e` (one per system).
