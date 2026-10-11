# D&D 5e (2014)

Encounter builder, difficulty estimate and combat tracker at `/TTRPG/dnd5e`.

- Code: `ttrpgtools/dnd5e/` (bestiary, combat, difficulty, importers, `routes.py`). Database: `data/dnd5e.sqlite`.
- Bestiary import: `docker exec sheet python -m ttrpgtools.dnd5e.bestiary /compendium.xml`.
- Difficulty calibration: `python scripts/dnd5e/calibrate_difficulty.py`.
- Design: `docs/dnd5e/DESIGN.md`.
