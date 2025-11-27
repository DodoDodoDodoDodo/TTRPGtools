# Repository Status & Cleanup Plan

## Current State (Nov 27, 2025)

### Active Branch: `bold-dirac`
Working branch with all recent improvements:
- Career/rank context extraction in parsers
- Equipment parsing system
- Enhanced character sheet format
- Database with 4,211 entries
- TESTING.md documentation

### Commits Status
- Latest: e950e80 "Add .gitignore to exclude cache and generated files"
- Previous: f27b8e7 "some changes" (equipment parsers + generated characters)
- Previous: 6e9eb9a "big overhaul" (career/rank context fixes)

All working directory changes are committed.

## Branch Structure Analysis

### Main Branches
- **bold-dirac** (current) - Ahead of origin/bold-dirac by 1 commit (.gitignore)
- **main** - Local is diverged from origin/main
- **origin/main** - Has merged bold-dirac work via PR #14

### Stale Branches (can be deleted)
- **6_parse** - Old parsing experiments
- **dev** - Old development branch
- **codex/add-ttrpgtools-package-and-cli** - Merged via PR
- **codex/create-character-generation-and-modification-scripts** - Merged via PR
- **codex/create-parsing-module-for-game-data** - Merged via PR
- **codex/review-and-test-dark-heresy-1e-code** - Merged via PR
- **codex/write-parsing-scripts-for-json-data** - Merged via PR

## Recommended Actions

### 1. Sync with Remote

```bash
# Fetch latest from remote
git fetch origin

# Reset local main to match origin/main
git checkout main
git reset --hard origin/main

# Return to working branch
git checkout bold-dirac
```

### 2. Push Current Work

```bash
# Push bold-dirac with latest changes
git push origin bold-dirac

# This will update PR #14 or can create a new PR if needed
```

### 3. Clean Up Stale Branches

```bash
# Delete local stale branches
git branch -d 6_parse dev
git branch -d codex/add-ttrpgtools-package-and-cli
git branch -d codex/create-character-generation-and-modification-scripts
git branch -d codex/create-parsing-module-for-game-data
git branch -d codex/review-and-test-dark-heresy-1e-code

# Delete remote stale branches (if you have permission)
git push origin --delete 6_parse dev
git push origin --delete codex/write-parsing-scripts-for-json-data
```

### 4. Merge to Main (when ready)

```bash
# Option A: Via GitHub PR (recommended)
# - Push bold-dirac to origin
# - Create/update PR #14
# - Review and merge via GitHub UI

# Option B: Local merge
git checkout main
git merge bold-dirac
git push origin main
```

## What's Been Built

### Core Functionality
1. **Character Management** - Create, track XP, buy advances
2. **Career System** - 8 careers, 33+ ranks, 3,065 advances
3. **Characteristic Advances** - 612 stat improvements with costs per career
4. **Equipment Database** - 87 items (weapons, armor) parsed from rulebooks
5. **Psychic Powers** - 113 powers parsed
6. **Talents** - 395 unique talents
7. **Divination Table** - 26 results

### Database Quality
- 98% of characteristic advances have career context
- 38% of advances have rank information
- All tests passing (13/13)

### New Features in This Branch
- Career and rank context extraction from rulebook text
- Equipment parsers for weapons and armor
- Enhanced character sheet format with:
  - Full characteristics
  - Purchase history with order tracking
  - Equipment integration
  - Psychic powers for psykers
- Documentation (TESTING.md) on writing semantic tests

## Files Overview

### Python Modules
- `ttrpgtools/models.py` - Domain models (Character, Advance, Career)
- `ttrpgtools/parsers.py` - Text parsing for talents, advances, etc.
- `ttrpgtools/equipment_parsers.py` - NEW: Weapon and armor parsing
- `ttrpgtools/book_import.py` - Auto-detection and career context extraction
- `ttrpgtools/cli.py` - Command-line interface
- `ttrpgtools/storage.py` - JSON serialization
- `ttrpgtools/library.py` - Database management

### Databases
- `database/all_entries.json` - Master database (4,211 entries)
- `database/advances.json` - Skills/talents by career
- `database/characteristic_advances.json` - Stat costs by career
- `database/talents.json` - Talent definitions
- `database/psychic_powers.json` - Psychic power descriptions
- `database/divinations.json` - Divination table
- `database/equipment.json` - Weapons and armor

### Documentation
- `README.md` - Project overview
- `instructions.md` - Usage guide
- `agents.md` - Development guidelines
- `TESTING.md` - Testing philosophy and practices

### Test Data (Now Gitignored)
- `george*.json` - Test guardsman characters
- `mordecai_psyker.json` - Test psyker character
- Character files are now ignored via .gitignore

## Next Steps

1. **Immediate**: Push bold-dirac branch to sync with remote
2. **Short-term**: Clean up stale branches
3. **Medium-term**:
   - Improve equipment parser (some fields get mixed up)
   - Add weapon/armor to character creation workflow
   - Build Career objects dynamically from database
4. **Long-term**:
   - Parse remaining equipment types (grenades, tools, gear)
   - Add prerequisite validation for equipment (training requirements)
   - Build character sheet PDF generator
