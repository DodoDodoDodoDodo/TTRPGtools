# Instructions

Use Python 3.11+ from the repository root. Install nothing; the tools run in-place with the standard library.

## Character CLI
- Inspect built-in sample careers: `python -m ttrpgtools.cli list`
- Create and view a character: `python -m ttrpgtools.cli new --name "Sera" --career "Soldier" --xp 500 --output sera.json`
- Buy an advance (prerequisites and XP are enforced): `python -m ttrpgtools.cli buy-advance --file sera.json --advance "Shield Wall"`
- Show a summary at any time: `python -m ttrpgtools.cli show --file sera.json`
- Emit raw JSON instead of the summary: `python -m ttrpgtools.cli load --file sera.json --json`
- Save a character from an existing JSON document: `python -m ttrpgtools.cli save --source ./sera.json --file ./sera-copy.json`
- Pipe JSON in from other tools: `jq '{"name":"Nova","career":"Acolyte","xp_total":400,"purchases":[]}' | python -m ttrpgtools.cli save --stdin --file nova.json`

## Import helpers
- Parse a small snippet (table headings required) into a library file:
  - `cat <<'EOF' > /tmp/talent_snippet.txt`
  - `Talent Name Prerequisite Benefit`
  - `Test Talent — Grants a bonus to something.`
  - `EOF`
  - `python -m ttrpgtools.cli import-text --input /tmp/talent_snippet.txt --category talents-table --library ./database/talents.json --page 321 --source "Core Rulebook"`
- Parse the bundled `stuff.md` book export and append all detected sections: `python -m ttrpgtools.cli import-book --input ./stuff.md --library ./database/talents.json --source "Core"`
- Re-run either command against the same `--library` to accumulate entries; files default to an empty list if missing.

## Sample character workflow
- Generate the verbose sample sheet (overwrites `sample_character.json`): `python scripts/generate_sample_character.py`
- Adjust XP or actions in-place: `python scripts/modify_character.py sample_character.json --set-xp-total 1250 --set-skill "Dodge=+10" --add-action "Hail Mary|Full Action|Throw a frag grenade with +20 to hit|Explosive"`

## What currently works
- CLI commands for listing careers, creating characters, enforcing advance prerequisites, saving/loading JSON, and summarizing characters.
- Text and book importers that can auto-detect talent tables, advances, characteristic advances, divinations, psychic powers, and talent prose; `stuff.md` parses into 106 entries.
- Sample character generator and modifier scripts for quick end-to-end JSON workflows.

## Known gaps
- Only two sample careers are registered; broader career content is not yet encoded.
- Library JSON files in `database/` ship empty; you must import book text to populate them.
- Importers assume cleaned text exports with intact headings; malformed input will raise a parse error and exit.
- No ticket/issue list is present in the repository; open tasks must be tracked elsewhere.
