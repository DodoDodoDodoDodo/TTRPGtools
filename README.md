# TTRPGtools

Utilities for managing tabletop role-playing game characters from the command line.

## Installation

The project is a pure Python package that can be executed directly from the repository:

```bash
python -m ttrpgtools.cli --help
```

## Careers and advances

Two sample careers are bundled so you can get started immediately:

- **Soldier** with the advances Basic Training, Shield Wall, and Battlefield Commander.
- **Acolyte** with the advances Initiate's Blessing, Sacred Ward, and Miracle Worker.

Each advance has an XP cost, a rulebook page reference, and optional prerequisites. A
character cannot purchase an advance unless they have enough unspent XP and own all of
its prerequisites.

## CLI usage

Create a new character and save it to disk:

```bash
python -m ttrpgtools.cli new \
  --name "Sera" \
  --career "Soldier" \
  --xp 500 \
  --output sera.json
```

List the built-in careers and their advances:

```bash
python -m ttrpgtools.cli list
```

Buy an advance, automatically recording the rulebook page number:

```bash
python -m ttrpgtools.cli buy-advance --file sera.json --advance "Shield Wall"
```

Override the recorded page number if your table uses a different printing:

```bash
python -m ttrpgtools.cli buy-advance \
  --file sera.json \
  --advance "Shield Wall" \
  --page 148
```

View a character summary:

```bash
python -m ttrpgtools.cli show --file sera.json
```

Export the character as JSON (the `load` command mirrors `show` but supports raw JSON):

```bash
python -m ttrpgtools.cli load --file sera.json --json
```

Import or update a character from a JSON document:

```bash
python -m ttrpgtools.cli save --source ./sera-updated.json --file sera.json
```

You can also pipe JSON directly from other tools:

```bash
jq '{"name":"Sera","career":"Soldier","xp_total":500,"purchases":[]}' \
  | python -m ttrpgtools.cli save --stdin --file sera.json
```

## JSON schema notes

Characters are stored as human-editable JSON files with the following structure:

```json
{
  "name": "Sera",
  "career": "Soldier",
  "xp_total": 500,
  "purchases": [
    {"name": "Basic Training", "xp_cost": 100, "page": 45}
  ]
}
```

The `purchases` array records each advance by name, the XP spent, and the rulebook page
number. XP spent is automatically calculated from the canonical advance definition for
that career, so you only need to adjust the page number when editing manually.
