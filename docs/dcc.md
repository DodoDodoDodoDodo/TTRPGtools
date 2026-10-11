# Dungeon Crawl Classics and the west marches

Builder, sheet, assistant and music at `/TTRPG/dcc`; the campaign (town, shops, inns, traders, villagers, the steward Hedwig) at `/TTRPG/dcc/town`.

- Code: `ttrpgtools/dcc/` (rules and builder in `__init__.py`, `explain.py`, `folio.py`, `sheetfill.py`, `routes.py`); campaign in `ttrpgtools/dcc/westmarch/`.
- Content: `content/dcc/private/core.json` (not in git; made by `scripts/dcc/dcc_extract.py` from the books), music in `content/dcc/music/`.
- Data: `data/westmarch/` (town file, sqlite, steward notes, backups). Characters: `characters/dcc/`.
- Design log: `docs/dcc/DESIGN.md`. Glossary: `docs/dcc/CONTEXT.md`.
- Scripts (`scripts/dcc/`): `westmarch_run_years.py` (fast-forward with the steward), `steward_checkin.py`, `westmarch_reset.sh` (restore a backup), `dcc_texture.py`, `sheet_grid.py`.

Run rules: deploy only while the run is paused (`data/steward/PAUSE`); take a backup first; one village, no duplicate containers.
