# D&D 5e design

## 11. D&D 5e encounter tools (built 2026-09-29)

Live at `/TTRPG/dnd5e/`. Package `ttrpgtools/dnd5e/`, blueprint `ttrpgtools/web/dnd5e_routes.py`, pages in plain JavaScript without a build step, tests in `tests/test_dnd5e.py`.

| Module | Job |
|---|---|
| `db.py` | One SQLite file, `data/dnd5e.sqlite` (gitignored, WAL). Tables: monsters, pcs, encounters, combats. JSON `data` column plus the few columns that are searched. |
| `statblock.py` | The monster schema and `derive()`, which turns parsed fields into counters (recharge, per day, legendary, slots, innate spells). |
| `bestiary.py` | Compendium XML to monsters. 5537 entries, 3134 from Wizards books. Rebuild: `docker exec sheet python -m ttrpgtools.dnd5e.bestiary /compendium.xml`. Rebuilding replaces compendium rows only. |
| `paste_import.py` | Stat block text copied from a D&D Beyond page to the same schema. Line state machine, 2014 and 2024 layouts. |
| `ddb_character.py` | PCs from D&D Beyond's public character JSON, fetched server-side. HP, scores and slots are recomputed from parts. AC is an estimate from equipped armour until someone saves a value. |
| `difficulty.py` | DMG 2014 rating, Lazy Encounter Benchmark, and the duel estimate. |
| `combat.py` | Tracker state as one JSON document, changed only through operations. Undo stack of 50, version number against two tabs overwriting each other. Combatants carry a snapshot of their stat block. |

### Books beyond the compendium

`fivetools_import.py` reads any 5etools-format JSON file (core data or a homebrew book file) into the same schema, origin `book`. Importing a file again replaces the rows of its sources only. A corrections file overrides fields where the internet file disagrees with the printed book.

Flee, Mortals! (MCDM, v1.1) came in this way on 2026-09-29: 340 stat blocks from the 5etools homebrew repository, file kept at `content/dnd5e/private/flee_mortals_5etools.json`. Every block was checked against the owned PDF for AC, HP and all six ability scores. Two corrections resulted (`flee_mortals_corrections.json`): Zombie AC 9, spelling Forzaantilirys. MCDM additions in the schema: `role` (Brute, Minion, Solo, Companion, Retainer, ...), `villain` actions as three once-per-encounter counters, minion XP through `xp_override`.

    docker exec sheet python -m ttrpgtools.dnd5e.fivetools_import /app/content/dnd5e/private/flee_mortals_5etools.json --corrections /app/content/dnd5e/private/flee_mortals_corrections.json

Not modelled: the minion rules (group attacks, overkill damage) and scaling of companions and retainers with their mentor's level. Their text is on the stat block; the numbers are the printed base values.

### Duel estimate

An expected-value fight, round by round. The party kills monsters in order of damage per effective HP. Every living monster deals its expected damage. Hit chances come from the real AC, attack bonuses and save DCs. It runs twice, once with monster damage spread and once focused on the weakest PC, and reports the mean and both ends.

Monster offence is read from the action text: multiattack routine, limited abilities first (recharge chance in later rounds), legendary actions, area effects counted on two targets as in the DMG monster rules. Casters are estimated from slot levels with the DMG spell damage table because the compendium lists spell names only.

PC damage is a per-level baseline unless the PC carries `dpr`. `PC_POWER` scales PC damage and staying power per level. `scripts/calibrate_difficulty.py` fits it so that one official monster of CR equal to party level costs four baseline PCs 30% of their hit points in the median.

Known limits: no terrain, surprise, healing or control spells. Breath-weapon monsters rate high (young white dragon against four level 5 PCs reads as lethal). Caster monsters are coarse. Nobody has compared the bands to fights at the table yet.

### Open

- A real paste from a D&D Beyond monster page has not been tested. Fixtures follow the layout other importers expect.
- Live sync between devices. Today a second tab picks up changes when it regains focus.
- No player view, ever (the owner, 2026-09-29).
- Our own 5e character builder will feed the party list once it exists.
