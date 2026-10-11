# Dark Heresy 1e

Character sheets at `/TTRPG/dh1e`: careers, ranks, advances, characteristic tiers, psy ratings, undo. Data in `ttrpgtools/dh1e/database/` (career JSON, parsed from the core book); characters in `characters/dh1e/` as JSON.

## CLI

```
python -m ttrpgtools.dh1e.cli list
python -m ttrpgtools.dh1e.cli new --name Sera --career Soldier --xp 500 --output sera.json
python -m ttrpgtools.dh1e.cli buy-advance --file sera.json --advance "Shield Wall"
python -m ttrpgtools.dh1e.cli show --file sera.json     # or: load --json, save --source/--stdin
```

## Importing book text

Needs the rulebook text in `rulebooks/dh1e/` (see README).

```
python -m ttrpgtools.dh1e.cli import-book --input rulebooks/dh1e/core_all.txt --library ttrpgtools/dh1e/database/talents.json --source Core
python -m ttrpgtools.dh1e.cli import-text --input snippet.txt --category talents-table --library <file> --page 95
```

Parser fixtures: `tests/fixtures/dh1e_tables.md`. Psyker build scripts: `scripts/dh1e/`.

## Open

- Bug report field on the sheet: attaches the character JSON as it stood.
- Printable sheet (PDF) from a built character.
- More sourcebooks.
- Modifiers must propagate (a +10 melee damage talent shows in attack damage).
- Selectable equipment with computed weight and armour points.
- Study malleus.dk (Wayback) and match its features.
