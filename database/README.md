# Reference database stubs

This folder holds JSON exports parsed from the rulebooks. Each file is seeded with an empty array so you can append parsed entries without worrying about missing paths.

- `items.json` — general equipment or armour records you extract from books or tables.
- `talents.json` — parsed output from talent tables or prose sections.
- `advances.json` — skill and talent advances with XP costs.
- `characteristic_advances.json` — XP costs for characteristic tiers.
- `divinations.json` — divination table rows.
- `psychic_powers.json` — parsed psychic power definitions.

Use the CLI import helpers to populate these files once you have plain-text exports of the books. Examples:

```bash
# Parse a formatted talent table and append to talents.json
python -m ttrpgtools.cli import-text \
  --input ./data/core_talents.txt \
  --category talents-table \
  --library ./database/talents.json \
  --page 95 \
  --source "Core Rulebook"

# Parse the whole book at once; sections are detected automatically
python -m ttrpgtools.cli import-book \
  --input ./core_all.txt \
  --library ./database/talents.json \
  --source "Core Rulebook"
```

If you want to aggregate multiple sources, re-run the commands against the same target file. Entries are appended in order so you can track where each slice of the book was processed.
