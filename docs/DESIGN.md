# Design: multi-system character builder (DH1e, D&D 5e 2014, DCC)

Status: draft v14, 2026-09-17. Written by Claude after a prior-art survey and a read of the current repo, revised after Dodo's reviews (repo stays public with a partial private split, all 5e books available, D&D Beyond feel is the target, private table use, Fight Club 5 compendium XML chosen as the primary 5e data source, 5etools secondary).

## 1. Goal

One self-hosted web app that builds characters, fills the sheet from the build, and exports the sheet. Three rule systems: Dark Heresy 1st edition (exists, partial), D&D 5e 2014 rules (every 2014-era WotC book Dodo owns, no 2024 content), Dungeon Crawl Classics (core rulebook). No dice rolling, no VTT, no combat tracker.

Audience: one table, the three systems it plays. Players build and maintain their own characters. The comparison point is D&D Beyond: guided choices with the rules text one click away, a live computed sheet, printable output. The aim is that feel without the subscription, plus things D&D Beyond lacks: full offline export, an XP and prerequisite audit, and homebrew that costs nothing to add.

## 2. Where the repo stands

Deployed as the `sheet` container behind Tinyauth at home.dodo-dodo.de/TTRPG. Flask, server-rendered, JSON files as storage. 21 tests pass.

DH1e today:

- Career rank trees for all eight core careers, 2065 rank advances, per-career characteristic costs, prerequisite and XP gating, undo, advance history.
- Psy Rating purchase flow with power grants.
- Sheet shows characteristics, vitals, armour by location, advances, history.
- Characters carry homeworld and divination as plain strings only.
- Talents, equipment, psychic powers exist as parsed tables but have no mechanical effect on the sheet (the "modifiers should propagate" TODO).
- No skill list, no creation wizard (characteristics are typed in), no export beyond the JSON file.
- Test coverage stops at parsers and purchase rules. Nothing covers the DH1e web layer.

DCC today (built 2026-09-17, live at home.dodo-dodo.de/TTRPG/dcc/ behind Tinyauth):

- `ttrpgtools/dcc.py`: content access, rules (ability modifiers, AC, saves, speed, deed dice, thief skills with governing abilities, spell allowance and max level from class table and casting ability, race-locked classes, XP gating, titles), funnel generation, JSON storage under `characters/dcc/`.
- `ttrpgtools/web/dcc_routes.py` (blueprint under `/TTRPG/dcc`): list, funnel generator (batch, seedable, tick survivors to keep), manual entry of table-rolled characters, sheet with abilities, combat block, saves, gear, thief skills, spells with full result bands, class ability prose, Mighty Deeds, the character's crit table, level-up, spell picker, edit form, JSON download, print CSS, delete.
- `tests/test_dcc.py`: 10 tests on a synthetic content fixture plus one web flow test on the real pack. 31 tests pass overall.
- The container mounts `content/` read-only, so the pack is rebuilt on the host without an image rebuild.
- Second-order rules on the sheet (added 2026-09-17 at Dodo's request): a Rolls panel breaks every roll into its components (class, ability, birth augur where its "lucky roll" applies, doubled for crits and fumbles, lucky weapon, luck die); mercurial magic is recorded per known spell from a d% the player rolls (with the Luck x10 modifier shown) and its text sits on the spell; a "Rules in Play" panel per class carries the warrior's and dwarf's lucky weapon fixed at level 1, the elf's lucky spell and free patron bond and invoke patron, the cleric's deity, disapproval range with the 1d4-per-point rule and the lay on hands and turn unholy matrices, the thief's luck die, the halfling's luck charm, and the reference tables (spellburn, corruption, misfire, disapproval, fumbles). This is the DCC instance of the effects engine idea in section 4.3; the DH1e and 5e versions should follow the same shape: a roll list with named parts.
- Third-order rules and play state (2026-09-17, later the same night): temporary ability loss (spellburn, poison, disapproval illness) is tracked per ability and every modifier on the sheet uses the reduced score; an In Play panel offers HP steps, Luck burn with the class's rate, Luck regain (thieves and halflings by level per night), spellburn for casters, the cleric's failed-check counter, and "New day" (heals one ability point, regains Luck, resets disapproval); the armour check penalty is applied to wizard and elf spell checks; the hit-point birth augur is added automatically on level-up; the two-weapon line for the character's Agility and backstab damage on thief weapons show in Rolls; corruption results are kept as a list. The augur line reads as a sentence ("Charmed House: -1 to armor class, fixed for life").
- Inventory (same night): items are structured (name, kind, quantity, cost, equipped, notes), migrated once from the old free-text fields which stay in sync for the printed sheet. A catalog picker covers weapons, armour, shield, ammunition, gear and mounts (tables 3-1 to 3-5, ammunition and mounts extracted for this) with an optional purchase that deducts coins and makes change; equip toggles drive AC, check penalty, fumble die and the weapons table; countables have quantity buttons; custom items take any kind and price.
- Class audit (2026-09-17, last pass): weapon training per class is parsed from the class prose (0-level: occupation weapon only; warriors all; clerics per deity) and untrained weapons in hand get the -1d note on the attack rolls and in the weapons table; bows, crossbows and slings show their ammunition count from the inventory and warn at zero; halflings get the stealth rows (table bonus plus Agility), the two-weapon line at minimum Agility 16 with the natural-16 crit and double-1 fumble, and the small size and luck charm text; elves get the +4 secret doors row, immunities, and an iron warning that flags iron weapons and armour carried; dwarves get the shield bash row (1d14 plus deed die, 1d3) when a shield is worn and the underground detection bonus; thieves get the backstab attack row with auto-crit and the trap augur on their trap skills. The prose extractor now accepts hyphenated headings ("Two-weapon Fighting").
- Still server-rendered Jinja like DH1e. The D&D Beyond style client (section 6) is not started; the DCC pages port into it at M2.

Two facts that shape everything below:

1. `core_all.txt` (1.5 MB, the full core rulebook text) and the parsed `database/*.json` are committed to a public GitHub repo. FFG/GW content has no open license. The DH1e Steam Workshop generator was removed for exactly this. Section 7 handles it: repo stays public, the book-derived bulk goes private and becomes rebuildable from an owned PDF.
2. The `characters/` folder mixes Dodo's and a friend's characters with no owner field, while Tinyauth already forwards `Remote-User`. Multi-user is cheap now and expensive later.

## 3. Prior art survey (2026-09-16)

Full agent reports are summarised here. Unverified items are marked.

### 3.1 D&D 5e, 2014 rules only

| Project | Stack, license | 2014 vs 2024 | What it is | Verdict |
|---|---|---|---|---|
| "Complete Compendium PHB2014" XML (local, in the share) | XML in the Fight Club 5th Edition / Game Master 5th Edition app compendium format (see the note below on how that was identified) | 2014 only by construction; every entry has a `Source:` line | Sheet-oriented data: classes with per-level features, slots, counters, ASI flags; races with ability strings; items with damage and structured `modifier` elements; spells with school, components, class lists; feats with modifiers | Primary 5e data source (section 5.2) |
| 5etools-src (5e.tools) | JSON + JS, MIT code; data is WotC text under the same badge | Clean split by `source` key: `PHB` (2014) vs `XPHB` (2024), plus `reprintedAs` links and `edition: classic` | Full structured data for every book (classes with per-level features, subclasses, races, backgrounds, feats, spells, items, optional features, full book prose) and a renderer | Secondary 5e source: book prose, structured starting equipment, multiclass rules, cross-check |
| 5e-bits/5e-database | JSON + TS, MIT; content CC-BY-4.0 | Hard split: `src/2014/en/` vs `src/2024/` | SRD data, normalised, active (last commit 2026-09-13) | The only open-licensed pack; bundled |
| Open5e API | Django, license unclear (NOASSERTION) | Filter `document__slug=wotc-srd` | Reference API, no builder | Fallback data source |
| Orcpub / DM's Vault | Clojure, EPL-2.0 | 2014 only, active | Full builder, `.orcbrew` private homebrew packs, PDF export | Best engine reference; stack mismatch, do not fork |
| PCGen | Java, LGPL | 2014 SRD dataset only | 20-year builder engine, LST format | Reference for edge cases (multiclass, prereq trees) |
| MPMB sheet | PDF + JS, custom terms | Separate repos per ruleset | Computed PDF sheet | Reference for sheet field logic and for the "fork, never mix" precedent |
| Foundry dnd5e | JS, MIT + CC-BY | Mixed, 2014 as legacy toggle | VTT actor model | Not usable, contamination risk |
| Aurora Builder + AuroraLegacy/elements | XML packs | Now mixed with 2024 | App is dead, packs alive | XML pack index is a good pattern; content legally grey |
| dnd-character (Python) | EPL-2.0 | 2014 | Random generator lib, stale 2023 | No |

Licensing: SRD 5.1 (2014) is CC-BY-4.0 since 2023-01-27. SRD 5.2 (2024) is a separate CC-BY document. They differ in content (weapon mastery, revised classes). Any "SRD" dataset must be checked for which one it is.

5etools in detail (verified 2026-09-16 against the repo): `data/class/class-<name>.json` holds `class[]`, `subclass[]`, `classFeature[]`, `subclassFeature[]`. Class features are an ordered list of pointers like `Action Surge|Fighter||2` resolved against `classFeature[]`. Choices use one idiom everywhere: `{"choose": {"from": [...], "count": N}}` for skills, tools, languages, abilities, and `{"type": "options", "count": 1, "entries": [{"type": "refOptionalfeature", ...}]}` for fighting styles, invocations, maneuvers, metamagic, resolved against `data/optionalfeatures.json`. `data/spells/spells-phb.json`, `data/races.json`, `data/backgrounds.json`, `data/feats.json`, `data/items.json`, `data/book/book-phb.json` complete the set. 2014 feats in `feats.json`: 42 with source `PHB`; 2024 ones are `XPHB`. Known quirk: PHB Human has no structured `ability` block, so its +1 to all scores is hardcoded. The renderer (`js/render.js`, 18k lines) is global-scope script, not a module, so reuse means vendoring, not importing.

Local material in the DnD_books share, checked 2026-09-16:

- `Complete_Compendium_PHB2014 2.xml` and `... 3.xml` (40 MB, byte-identical, one compendium). Format identification: the file never names its own format. The only "Fight Club" strings inside it belong to a homebrew Pugilist subclass. The identification rests on the schema: `<compendium version="5">` root with `<autolevel level=N>`, `<feature optional="YES">`, `<counter>`, `<slots>`, `<slotsReset>`, `<modifier category=...>`, `<roll>`, which is the import format of the Fight Club 5th Edition and Game Master 5th Edition apps (Lion's Den, iOS and Android). The public reference for that format is `kinkofer/FightClub5eXML` on GitHub (MIT, 741 stars, per-book XML under `Sources/`, merged into a "Complete" collection with `Utilities/merge.xslt`). That project stopped in May 2023 and lacks everything after Tasha's, while this file is dated 2025-03 and includes Fizban's, Bigby's, Planescape, Book of Many Things and homebrew, so it is a newer community build from another compiler. `<compendium version="5">`, 36 classes, 338 races, 157 backgrounds, 498 feats, 1832 spells, 9097 items, 5537 monsters, everything tagged with a `Source:` line, no 2024 content anywhere. Filtered to "Player's Handbook (2014)" it holds 13 classes, 66 race entries (subraces as separate entries like "Elf, High" with `ability`, `proficiency`, `spellAbility`), 18 backgrounds, 73 feats, 434 spells, 467 items. What makes it a builder source rather than a text dump, measured on 2026-09-16:
  - Classes: `hd`, `proficiency` (saves plus skill list), `numSkills`, `armor`, `weapons`, `tools`, `wealth` (dice), `spellAbility`, `slotsReset`, `subclass` title; `<autolevel level=N scoreImprovement=YES>` rows with `<slots>` per level, `<counter>` elements with value and reset cadence (Rage 2 at 1, 3 at 3, 4 at 6; Arcane Recovery 1 per long rest; Spells Known 3, 4, 4, 4, 5), and `<feature optional="YES">` for subclass and option features, named "Prefix: Feature" (Fighting Style: Archery, School of Abjuration: Abjuration Savant), which makes subclass and option extraction a name-prefix rule.
  - Items: `type`, `weight`, `value`, `property`, `dmg1`, `dmg2`, `dmgType`, `ac`, and 8170 `<modifier category="bonus">` elements over 4122 items ("ac +1", "Melee Attacks +1", "Ranged Damage +2"), which map onto the effects engine with no prose parsing.
  - Feats: `prerequisite`, `text`, `<modifier category="ability score">` (308 across the file).
  - Spells: `level`, `school`, `ritual`, `time`, `range`, `components`, `duration`, `classes` (with subclass lists such as "Cleric (Light)"), `<roll>` damage expressions.
  - Weak spots: starting equipment and multiclass requirements are prose inside "Starting <Class>" and "Multiclass <Class>" features; backgrounds carry only `proficiency` plus prose; the `classes` field on spells mixes in homebrew subclasses; no book prose beyond entry text; no images. Homebrew is filtered out by the `Source:` allow-list.
  - Book coverage, measured 2026-09-16 (subclasses counted from feature prefixes, so they are approximate): PHB 40 subclasses, 434 spells, 467 items, 73 feats, 18 backgrounds; XGE 29 subclasses, 117 spells, 35 feats; TCE 24 subclasses, 49 spells, 39 feats; SCAG 8 subclasses, 13 backgrounds; Eberron, Wildemount, Ravnica, Theros, Strixhaven, Fizban's, Van Richten's, Dragonlance, Bigby's, Book of Many Things, Planescape, Acquisitions Incorporated, Tal'Dorei all present with items, feats, races, backgrounds; 207 distinct sources in total, most of them homebrew. Gaps found so far: Mordenkainen Presents: Monsters of the Multiverse appears only in 33 text mentions, so its reprinted races are missing or mislabelled; XGE and TCE subclass counts are a few short of the printed books. Those are the gaps the 5etools overlay fills.
- `5e_stuff/*.webarchive` (nine files): 5etools book-viewer pages, each saved with only the expanded chapter loaded (PHB about 62k words, TCoE about 2.6k). Not full-text sources and not D&D Beyond pages. They do contain the 5etools CSS and JS, which the upstream repo provides more cleanly.
- English 2014 PHB: `/mnt/ssd/homelab/media/books/Wizards RPG Team/Players Handbook/Players Handbook - Wizards RPG Team.pdf`, 322 pages, verified English. The PHB in the share root is the Italian edition.

### 3.2 DCC

| Project | Stack, license | What it is | Verdict |
|---|---|---|---|
| foundryvtt-dcc/dcc | JS, MIT, active (2026-09-15) | Engine and schema only, ships zero DCC text by design | Schema reference (action dice, crit die, deed die, thief skills as fields) |
| Purple Sorcerer generators | PHP, closed | Most complete DCC chargen on the web, funnel + upper level + PDF | UX reference only, nothing to reuse |
| Roll20 DCC sheets | HTML/JS, MIT repo | Sheet with DCC tables baked in, no permission statement | Reference for what a computed DCC sheet must show |
| mark-tasaka php generators | PHP, per-class repos | Old, one repo per class | No |

Licensing: DCC is OGL 1.0a with Goodman's own content declared Product Identity. Goodman publishes no free SRD. The occupation table, class tables, spell texts, and Mighty Deeds are not open. Nothing bundles them legally. The owned core rulebook (10th print, in the DnD_books share) is the only source.

### 3.3 DH1e and malleus.dk

malleus.dk is not dead as a domain, but the DH tool is. The old ASP.NET app (`/Ordo/NpcGenerator/Default.aspx`) launched 2009, got a psyker UI, cloning, group printing, a two-page PDF sheet by 2010, and stalled by 2014. The new `malleus.dk/forge/...` layout says the DH generator "is not converted yet". Author handle "Thomas62", Copenhagen. No code or data dump was ever published. Wayback fetches were blocked for the research agent, so the feature list rests on FFG forum archive threads.

Confirmed malleus features, which are the spec for section 5.1:

- Build PC or NPC by choosing homeworld, career, then buying advances. The tool computed rank progression and XP validity.
- Hover tooltips showing at which rank an advance becomes available. Used to audit hand-built sheets.
- Accounts, save, clone, share to a public archive.
- Two-page printable sheet with skills, talents, weapons, armour, gear, psychic powers.
- Core rulebook only. No Ascension, no other 40k lines. Sourcebook coverage unverified.

Open-source DH1e landscape: thin. Foundry systems are all 2e. `tobast/darkheresy_character_gen` (C++, GPL-3) and `justricky21/dark-heresy-1e-tools` (MIT, small) are the only licensed 1e code. Memetix's Excel builder has the widest data coverage but is a spreadsheet. The sup/tg dhroller tool has the closest feature set to malleus (Inquisitor's Handbook homeworlds, divinations, multi-format export) but no source. Our own repo already has more structured DH1e data than any of these.

Conclusion: nothing to fork for any of the three. Data comes from 5e-bits (5e) and from Dodo's own books (DCC, DH1e). Engine patterns come from Orcpub (choice tree, private packs), foundryvtt-dcc (DCC schema), and our existing DH1e models.

## 4. Architecture

### 4.1 One app, three system modules

Keep Python and Flask for the backend. Reasons: it is deployed, tested, and the DH1e domain code is 3000 lines that already encode the hardest part (branching ranks). The frontend changes (section 6): Flask becomes a JSON API plus static file host, and the builder and sheet are a client-side app.

```
ttrpgtools/
  core/          character store, content packs, effects engine, export, api
  systems/
    dh1e/        models, creation steps, rules, derive, pdf field map
    dnd5e/       same
    dcc/         same
frontend/        Vite app: builder, sheet, list, audit (section 6)
content/
  dh1e/
    public/      tables: ranks, advance costs, equipment stats, talent names and prereqs (committed)
    private/     prose and raw text, rebuilt from an owned PDF (gitignored)
  dnd5e/
    srd51/       bundled, CC-BY-4.0, generated from 5e-bits src/2014 (committed)
    private/     PHB, XGtE, TCoE, ... parsed from owned PDFs (gitignored)
  dcc/
    private/     everything, parsed from the owned core PDF (gitignored)
characters/
  <system>/<id>.json
```

Each system module implements one interface:

```python
class System(Protocol):
    key: str                      # "dh1e"
    def creation_steps(self, char) -> list[Step]
    def available_choices(self, char, step) -> list[Option]
    def apply(self, char, decision) -> None
    def derive(self, char) -> SheetView
    def validate(self, char) -> list[Problem]
```

The core never knows what a "career" or a "subclass" is. It knows steps, options, decisions, and a derived sheet. The API exposes exactly these five calls per system plus character CRUD and export, so the frontend is one app with per-system option renderers, not three apps.

The `DnDzuhause/` sibling folder should not become a second repo. It would duplicate auth wiring, the character store, export, and deployment. Recommendation: delete it or make it a scratch folder for 5e PDF text dumps that feed `content/dnd5e/private/`.

### 4.2 Character file = decision log

The DH1e `advance_history` already works this way. Generalise: a character is an ordered list of decisions plus free-text fields (name, notes, current wounds). Everything else is derived on load. Benefits: XP validity audit for free (replay and check, the malleus feature), undo is a pop, and a rules fix re-derives every existing character.

```json
{
  "system": "dnd5e",
  "owner": "dodo",
  "name": "Tira",
  "content_packs": ["srd51", "phb"],
  "decisions": [
    {"step": "race", "choice": "elf", "sub": "high-elf"},
    {"step": "class", "choice": "wizard", "level": 1},
    {"step": "ability_scores", "method": "point_buy", "values": {...}},
    {"step": "skill_proficiency", "choice": ["arcana", "history"]},
    {"step": "level_up", "class": "wizard", "level": 2},
    {"step": "asi", "level": 4, "choice": {"int": 2}}
  ],
  "state": {"hp_current": 12, "notes": "..."}
}
```

DH1e migration: `advance_history` and `career_path` map onto `decisions` directly. Write the migration once and keep the loader accepting the old shape for one release.

### 4.3 Effects engine (fixes the DH1e "urgent" TODO, needed by all three)

Every content entry (talent, feat, item, class feature, racial trait, divination) can declare effects. The derive step folds them.

```json
{"name": "Power Armour", "effects": [
  {"target": "characteristic.strength", "op": "add", "value": 20, "when": "equipped"},
  {"target": "armour.all", "op": "set", "value": 8, "when": "equipped"}
]}
```

Targets are dotted paths into the derived sheet. Ops: `add`, `set`, `max`, `grant` (skill, proficiency, language), `text` (a note attached to a sheet field for effects the engine cannot compute, such as "re-roll a missed attack once per round"). Rule of thumb: model what changes a number or a list on the sheet, put the rest in `text`. This keeps the transcription effort bounded. Coverage target for a first pass: characteristic and ability modifiers, armour, wounds and HP, movement, skill and proficiency grants, saves, AC, attack and damage bonuses.

Ordering matters (5e: base, then racial, then set-to-value items like Gauntlets of Ogre Power, then bonuses). Use fixed phases: `base`, `set`, `add`, `max`, `grant`.

### 4.4 Content packs

A pack is a folder with `pack.json` (key, name, system, source book, edition, license) and one JSON file per entry type. Three kinds:

- Bundled open: content under an open license. Today that is exactly SRD 5.1. Committed.
- Bundled tables: DH1e structural data that is numbers and names (rank trees, XP costs, equipment stat lines, talent names and prerequisites). Committed. See section 7 for why this is acceptable.
- Private: prose and everything from owned books. `content/*/private/` is gitignored. Lives on the server, backed up with the SSD data.

Every private pack is produced by a repeatable pipeline, not by hand-editing JSON. Two pipelines:

- PDF pipeline (DH1e, DCC): `pdftotext` (poppler) into a text dump, then the existing parser family (`parsers.py`, `career_scheme_parser.py`, `equipment_parsers.py`) extended per book, then a validation step that counts entries against expected numbers and fails loudly.
- Compendium pipeline (5e, primary): read the Fight Club 5 XML, split by the `Source:` line into one pack per book, convert to our pack schema. The same converter accepts any future compendium update in that format.
- 5etools pipeline (5e, secondary): clone `5etools-src` at a pinned commit, filter by source key, and take only what the XML lacks: book prose for popovers and reference pages, structured starting equipment, multiclass requirements. Its counts also validate the XML import. The PDFs are the ownership record.

One command per book, same shape for both:

```
python -m ttrpgtools.dh1e.cli build-pack --system dh1e --book core --pdf /path/to/DH1e.pdf
python -m ttrpgtools.dh1e.cli build-pack --system dnd5e --book phb --from-compendium /path/to/Complete_Compendium.xml
python -m ttrpgtools.dh1e.cli build-pack --system dnd5e --book phb --from-5etools /path/to/5etools-src --only prose,equipment,multiclass
```

Anyone cloning the repo runs the same command against their own PDF or checkout. That is the whole point of the public split. Parsers and converters are tested on short snippets committed as fixtures, never on whole books.

A character records which packs it used. The sheet shows a pack badge on entries. Loading a character whose pack is missing yields validation problems, not a crash.

5e guard: the compendium converter keeps only entries whose `Source:` line matches an explicit allow-list of 2014-era book titles (each ending in "(2014)" where the compendium uses that suffix) and rejects anything mentioning 2024 or Product Identity-free rewrites. The 5etools converter keeps only entries whose `source` is in an explicit allow-list (`PHB`, `XGE`, `TCE`, `SCAG`, `VGM`, `MTF`, `MPMM`, `ERLW`, `EGW`, `FTD`, `SCC`, `GGR`, `MOT`, and the adventure sources on request) and refuses `XPHB`, `XDMG`, `XMM` and any entry whose `edition` is not `classic` where the field exists. A test asserts that no built pack contains a 2024 source key or 2024-only feature names (weapon mastery, "Origin" feats, species). The 5e-bits import pins a commit hash and reads only `src/2014/en/`.

### 4.5 Multi-user

Read `Remote-User` from Tinyauth. Characters get an `owner`. Everyone at the table sees every character (it is one table), edits only their own, and the GM account can edit all. No accounts in the app itself, no public archive. Cloning any visible character is one button.

### 4.6 Export

Three tiers, in order of build effort:

1. JSON download of the character file (exists in effect).
2. Print view: the sheet page itself with `@media print` CSS. Browser "save as PDF" covers most needs.
3. Official-sheet fill, built 2026-09-17 in `ttrpgtools/sheetfill.py`. The official sheets turned out to be flat PDFs with no form fields, so the method is a text overlay: a layout JSON names the template (PDF or PNG) and gives each field a page, x, y, size, optional width (single-line text shrinks to fit) or a wrap box. `scripts/sheet_grid.py` draws a labelled coordinate grid over a template so positions can be read off a preview. Layouts live next to their templates in `content/<system>/private/sheets/` (the art is the publisher's), and every layout there appears as a "Sheet PDF" button on the sheet page. First calibrated layout: the Goodman standard sheet page 1, `dcc-standard.json`, about 100 fields including abilities, saves, weapons, thief skills, common activities, notes. Dodo's own sheet, PDF or PNG, becomes another layout file with no code change; the grid script and one render-and-look pass calibrate it.

## 5. Per-system plans

### 5.1 DH1e (finish what exists)

Content gaps, from the core book text already parsed:

- Skills list with governing characteristic, basic vs advanced, and +10/+20 upgrades. Currently skills exist only as advance names.
- Homeworlds with their characteristic modifiers, wounds and fate rolls, starting skills and traits.
- Career starting packages: characteristics base, starting skills, talents, gear, wounds, fate.
- Divination table as effects (the parsed table has the text, not the effect).
- Equipment with mechanics: armour by location with weight and AP, weapons with damage and class, gear with effects.

Features, in order:

1. Effects engine and re-derived sheet (section 4.3). Talents, divination, and armour finally change numbers.
2. Creation wizard: homeworld, career, characteristics (2d10 plus base, rolled or entered), wounds and fate, divination, starting package. Replaces the manual `new.html`.
3. Selectable equipment with carry weight and per-location AP.
4. Audit view: replay decisions, list every advance with the rank it became available at, flag anything bought early. This is the malleus tooltip feature and it falls out of the decision log.
5. Print view and PDF fill on the 3-page editable sheet.
6. Sourcebooks: Inquisitor's Handbook first (alternate homeworlds, alternate career ranks, gear). The PDF is in the share. Radical's Handbook, Blood of Martyrs, Daemon Hunter, Book of Judgement after, each as its own private pack.

### 5.2 D&D 5e, 2014 rules

Content:

- Primary: the compendium converter (section 4.4). Class rows give per-level features, slots, counters, and ASI levels directly. Option features ("Fighting Style: Archery") and subclass features ("School of Evocation: Evocation Savant") are grouped by name prefix into our `Option` lists. Item and feat `modifier` elements become effects. Race `ability` strings ("Dex 2, Int 1") parse into effects. Names plus source titles become our IDs.
- Secondary: the 5etools converter, restricted to book prose for popovers and reference pages, structured starting equipment, and multiclass requirements, keyed by name so it overlays the compendium entries. Its `choose`/`count` idiom also fills the few choices the compendium leaves in prose (Expertise picks, skill choices on backgrounds).
- Bundled: the 5e-bits SRD 5.1 pack, imported by `scripts/import_5ebits.py` from `src/2014/en/`, so a fresh clone has a playable 5e without any private pack.
- Cross-check: entry counts per source between the compendium and 5etools must agree within a documented tolerance before a pack is accepted; the diff list is kept as a build artifact.
- Requirement (Dodo, 2026-09-16): serve all of 5e, every book. The data source is whichever file has the entry. Rule: the compendium is read first, 5etools fills every gap, and each build emits a coverage matrix (book by entry type by source) that is checked against the known counts per book. A book counts as served only when the matrix says so.
- SRD 5.1 is the bundled pack so a fresh clone works. Everything else is private packs, one per book. Dodo owns all 5e books; the PDFs live in the DnD_books share and the books library and are the ownership record. Order of validation: PHB, XGE, TCE, SCAG, MPMM, then the setting and adventure books. The converters are generic, so a new book is an allow-list entry plus a validation pass. The expensive part moves from transcription to rules coverage in the engine.
- Data quirks are handled in the converter with a test each. Known so far: the compendium's "Multiclass <Class>" and "Starting <Class>" pseudo-features must not appear as features on the sheet; the spell `classes` field carries homebrew subclasses that the allow-list strips; 5etools' PHB Human lacks a structured ability block.

Builder steps: race and subrace, class (subclass at the class's own level), background, ability scores (point buy, standard array, manual), proficiency choices, starting equipment or gold, spells (cantrips, known or prepared per class rules), level-up with hit points (average or entered), ASI or feat, subclass features, spell slots. Multiclassing in a second pass; the decision log supports it without schema change.

Derived: proficiency bonus, saves, skills with expertise, AC from armour and Dex with the class-specific formulas (Unarmoured Defense, Mage Armor as a set-op effect), HP, initiative, passive Perception, spell save DC and attack, attacks list, carry weight.

Export: print view modeled on the official two-page layout, then PDF fill.

### 5.3 DCC

Content: entirely private, extracted from the owned PDFs with the PDF pipeline. Two source files, both in the DnD_books share under `Other_RPGs/DCC/`:

- `DCC_Ref_Book_v1.09_cover.pdf` (58 pages): the Reference Booklet, single-column, uppercase table headings. It is the table source. `pdftotext -layout` gives clean rows.
- `Dungeon Crawl Classics RPG (10th print).pdf` (514 pages): the core rulebook. Two-column layout interleaves neighbouring tables, so it is used only for what the booklet lacks: the spell entries, class ability prose, and the Mighty Deeds text. Small-caps headings come out as "Magic MiSSile" and are normalised.

Extraction, finished 2026-09-17 (`scripts/dcc_extract.py`, output `content/dcc/private/core.json`, gitignored; runs from the two PDFs in one command, results identical from cached text dumps). Every table below was checked against its printed row count:

| Content | Parsed |
|---|---|
| 1-3 Occupation (d100) | 79 rows covering 100/100: occupation, starting weapon, trade goods |
| 1-1 Ability modifiers, 1-2 birth augurs, 1-4 XP thresholds | 16/16, 30/30, 11/11 |
| Class tables (1-5, 1-7, 1-10, 1-12, 1-14, 1-16, 1-18) | 7 classes, 10 levels each: attack or deed die, crit die and table, action dice, saves, threat range, luck die, spells known, max spell level, cleric spells by level, halfling sneak bonus |
| Class titles by level and alignment | 7 classes, 5 levels each |
| Class ability prose (core rulebook, reading order) | 8 to 16 named paragraphs per class (hit points, weapon training, alignment, attack modifier, magic, luck, languages, action dice, class specials) |
| 1-9 Thief skills | 13 skills x 3 alignments |
| 3-1 Weapons, 3-3 Armor, 3-4 Equipment | 23, 11, 24, all complete |
| 4-1 Attack roll modifiers, 4-2 Fumbles | 14 conditions, 17 rows |
| Crit tables I to V | 21, 25, 29, 25, 24 rows, each from "0 or less" to the top band |
| Mighty Deeds (7 kinds) | 5 result bands each |
| 4-4 Turn unholy, Lay on hands | 9 and 5 spell-check bands, full matrices |
| 5-1 Spellburn, 5-2 Mercurial magic, 5-3 to 5-5 Corruption, 5-6 Generic misfire, 5-7 Disapproval | 24, 100/100 (81 rows), 10 each, 8, 20 |
| Spells | 130/130: 79 wizard, 36 cleric, 15 patron; level, range, duration, casting time, save, general, manifestation, corruption, misfire, and every spell check result band as its own record |
| 0-level rules | encoded as a rules block (3d6 in order, 1d4 hp, 5d12 cp, d100 occupation, d30 augur, d24 item, alignment, languages) |

Lessons that carry over to the DH1e and 5e PDF work: the two-column core book must be read in reading order (no `-layout`) for prose and with `-layout` for tables; small-caps fonts come out as mixed case; a table that continues on the next page repeats its own title with no "continued" marker; roll tokens wider than four characters get one space instead of two; "1 or less" can wrap across two lines.

Not extracted, by choice: monster crit tables (DR, DN, G, U, M), patron descriptions and invoke-patron result tables, deity list, Appendix L languages table (the rule is encoded instead), and the spell result bands of patron spells beyond what the generic parser captured. None of these block the builder.

Data model (schema shape borrowed from foundryvtt-dcc, MIT):

- Character: six abilities with modifiers from table 1-1, luck with the birth augur target, hp, alignment, occupation, class or "0-level", level, xp, coins, inventory, known spells, luck spent, notes. Warriors and dwarves carry a deed die rather than a fixed attack bonus, so the attack field is a dice expression, not an integer.
- Derived per level from the class table row: attack, crit die and table, action dice, saves, threat range, thief skills (by alignment), spells known and max spell level, speed with armour, AC from armour and Agility, initiative, fumble die from armour.
- Spells as references into the pack; the result bands are shown in a popover in play mode, not modelled beyond text.

Builder:

- Funnel mode (Purple Sorcerer flow): generate N 0-level characters at once, each with 3d6 in order, occupation with weapon and trade good, birth augur, 1d4 hp, 5d12 cp, one d24 item, alignment, languages by Intelligence. Checkboxes keep the survivors, one click promotes a survivor to level 1.
- Level 1: choose class (Cleric, Thief, Warrior, Wizard, Dwarf, Elf, Halfling), pick alignment if not set, pick spells for wizard and elf (spells known from the class table plus the Intelligence adjustment), pick a patron if bonded, choose the Warrior's and Dwarf's starting Mighty Deed style if the table uses one.
- Level up: apply the next class-table row, add spells known, roll or enter hp.
- Luck spends and permanent luck burn are state edits on the sheet, not decisions.

Export: print view, then PDF fill of the official folder sheet (`dccrpg_foldercharsheet_v01.pdf`) and the 0-level sheet (`DCCRPGb_ZeroLvlCharSheet_v01.pdf`, four per page) already in the share.

### 5.4 DCC character folio (built 2026-09-17)

`ttrpgtools/dcc_folio.py` draws an 8-page A5 booklet per character with reportlab in a plain ruled style, served at `/TTRPG/dcc/<id>/folio` (sequential A5) and `?print=1` (imposed on landscape A4 for duplex: 8|1, 2|7, 6|3, 4|5). Dodo's constraints: 8 pages maximum, class pages separate, stats on page 2 and class on page 3 so the open booklet shows them together.

Pages: 1 cover (name, class, level, title, occupation, alignment, portrait box, player, campaign, augur sentence); 2 stats (six ability boxes with current score and modifier, two action-die boxes holding the dice, HP with max, AC, init, speed, three saves, crit die and table with threat, fumble die, main and secondary weapon with to-hit, damage, range and ammo, primary equipment list with CP/SP/GP boxes at the foot); 3 class (level, XP with next threshold, Luck, action dice, class rolls with components, rules in play, thief skills or halfling stealth, titles by level, class abilities condensed to three sentences each); 4 the class's crit table and the fumble table in two columns, remaining inventory lines; 5 campaign (map box, "in my home I own", religion, relations to everyone in the valley, goals checklist with done marks); 6 to 8 for casters: spells with mercurial result, general text and all result bands, at the first of four density tiers at which every spell fits three pages (the tightest tier keeps one sentence per band); a caster with more spells than fits gets four extra pages. 6 to 8 for others: hirelings and adventure journal, class tables (Mighty Deeds, thief skills by level, halfling rules) with the dice chain, reference (weapons, armor, ammunition, mounts, attack modifiers) and last will.

Campaign fields (name, home, religion, relations one per line, goals one per line with "[x]" for done) are edited on the web sheet. Pre-printed goal prompts wait for Dodo's wording.

## 6. Shared UI

Target: the D&D Beyond feel, for all three systems. Concretely, the things that make it feel that way:

- Builder as a left-hand step list (Race, Class, Abilities, Background, Equipment, Spells) that can be visited in any order, with each option as a card that expands to the full rules text. Choices already made stay visible and editable. A summary column updates live.
- Sheet with the recognisable layout: ability boxes on top, saves and skills down the left, the combat block in the middle, and tabs for Actions, Spells, Inventory, Features and Traits, Description, Notes. Every name on the sheet opens a popover with its rules text and source page. Current HP, temp HP, conditions, and spell slots are editable in place without leaving the sheet.
- Level-up is a mode on the same builder, not a separate page.
- Long lists (spells, equipment) have instant search and filters (level, school, class, availability).
- Dark theme by default.

Dodo's requirement: the same frames and borders as D&D Beyond, not an approximation. That means the actual sheet chrome (ability score frames, saving throw and skill boxes, the HP and AC shields, the section borders and dice art). Findings: those assets are WotC property and no open project ships them; the two MIT Foundry modules that mimic the layout (`jopeek/fvtt-dndbeyond-character-sheet`, `ElfFriend-DnD/foundryvtt-compactBeyond5eSheet`) use their own redrawn CSS and SVG. For private use at one table the plan is to take the real ones: Dodo saves the D&D Beyond character sheet page and the builder pages (logged in, one character, Safari webarchive like the 5etools ones) and the SVG and CSS are extracted from the archive into `frontend/assets/ddb/`, gitignored like private packs. The 5etools webarchives in the share are not D&D Beyond pages and do not contain these assets.

Each system gets its own sheet layout. 5e follows D&D Beyond exactly. DH1e and DCC reuse the same frame family with their own field layout, so the three feel like one app. The builder skeleton, popovers, search, and tabs are shared.

This is a client-side app. Server-rendered forms with a little JavaScript would fight every item above. Stack: Vite plus Svelte (small, no runtime framework weight, easy for a two-person team), TypeScript, built into static files that Flask serves under `/sheet/`. No separate Node service in production, only a build step in the Dockerfile. Flask exposes the JSON API from section 4.1. The current Jinja templates stay live until the DH1e sheet is ported (M2), then go.

Pages: character list (all table characters, own first), new (system picker), builder, sheet, audit, export, funnel (DCC only).

## 7. Legal hygiene, public repo with a private split

Decision (Dodo, 2026-09-16): the repo stays public. Roughly 60 percent of the book-derived material goes private, so a clone is not a copy of the book, but anyone with their own PDF can rebuild the full dataset with one command.

The split, by what a file is rather than by size:

- Stays public: parsers, importers, tests with short snippet fixtures, `career_ranks.json`, `career_characteristic_advances.json`, `career_advances.json` (names, costs, types, prerequisites), equipment stat lines (name, damage, AP, weight, cost, availability), talent and skill names with prerequisites and a one-line summary, divination roll ranges with effects but without the quotes. These are tables that any published sheet or wiki already reproduces, and they are what the rules engine needs.
- Goes private: `core_all.txt`, `ttrpgtools/DH1e_cleaned.txt`, `stuff.md` and the two other text dumps, `all_entries.json`, `advances.json` (raw parse superseded by the career files), and every prose description field (talent text, psychic power text, equipment descriptions, divination quotes, career and homeworld flavour). The private files are regenerated by `build-pack --system dh1e --pdf`.

By byte count that is about 2.5 MB private against roughly 1 MB public, which is above the 60 percent target and satisfies the intent.

Git history still contains the full text. Decision (Dodo): a `git filter-repo` purge of the raw text files happens right before the next big push to the public repo, not earlier. Until then nothing new is pushed. M0 ends with that purge and push.

Going forward: nothing under `content/*/private/` is ever committed regardless of visibility. Bundled packs carry their license file. The SRD 5.1 CC-BY attribution goes in the 5e pack and in the app footer. Private use at one table is the intended scope, and the repo says so in the README.

## 8. Roadmap

Milestones in dependency order. Sizes are rough working-session counts for Claude with Dodo reviewing.

| # | Milestone | Depends on | Size |
|---|---|---|---|
| M0 | Public/private split with `build-pack` for DH1e, `owner` on characters, `systems/dh1e` move, decision-log migration, JSON API, history purge then push | none | 3 |
| M1 | Effects engine, DH1e skills and homeworlds and starting packages as content, re-derived sheet | M0 | 4 |
| M2 | Frontend shell (Svelte): list, builder skeleton, popovers, search; DH1e wizard, sheet, equipment, audit, print. Old templates removed | M1 | 6 |
| M3 | 5e: compendium converter with source allow-list, PHB pack, 5etools overlay (prose, equipment, multiclass), srd51 bundled pack, 2014 guard, builder to level 20 single class, D&D Beyond sheet with extracted frames, print | M2, Dodo's D&D Beyond webarchives | 7 |
| M4 | DCC: done 2026-09-17 as Jinja pages (funnel, classes to level 10, sheet, spells, print). Remaining: port to the client-side shell at M2, PDF fill at M5 | none | done |
| M5 | PDF fill for the sheets Dodo uploads, field maps tuned together | M2 to M4, Dodo's PDFs | 3 |
| M6 | 5e packs: XGE, TCE, SCAG, MPMM, setting books, all already inside the compendium, one allow-list entry and a validation pass each; DH1e Inquisitor's Handbook and the rest via the PDF pipeline | M3, M2 | under 1 per 5e book, 1 per DH1e book |
| M7 | Multiclass, bug report with character snapshot (existing TODO), GM edit-all, cloning | M5 | 3 |

M3 and M4 can run in parallel after M2. Book packs (M6) are the long tail. The first visible payoff for the table is M2, the first 5e character is M3.

## 9. Questions for Dodo

Answered 2026-09-16: repo stays public with a partial private split, history purge right before the next big push; all 5e books are owned, English 2014 PHB located in the books library; the Fight Club 5 compendium XML is the primary 5e source with 5etools as overlay; D&D Beyond frames must be the real ones; private table use; PDF sheet filling later with Dodo supplying the sheets.

Still open:

1. D&D Beyond webarchives: please save the character sheet page and each builder tab of one character (logged in, Safari, "Web Archive" format) into `DnD_books/5e_stuff/ddb/`. Without them M3 ships a redrawn approximation.
2. Delete `DnDzuhause/`, or keep it as scratch?
3. Frontend stack: Svelte is proposed. Any preference for React or something else?
4. DH1e sourcebook order: Inquisitor's Handbook first is assumed.
5. DCC: core classes only, or also Lankhmar and the Annual classes later?
6. Who at the table is GM per system, for the edit-all right?
7. Where does the compendium XML come from, and does it get updates? The public FightClub5eXML project is dead since 2023, so this file has another compiler. If it gets releases, the converter should track them. The `2.xml`/`3.xml` duplicate can be deleted either way.

## 10. Non-goals

Dice rolling, campaign notes, D&D 2024 rules in any form, DH2e, Rogue Trader and the other 40k lines, mobile app, accounts beyond Tinyauth, public hosting for anyone outside the table.

Initiative and combat tracking, monsters and encounters left this list on 2026-09-29 at Dodo's request (section 11).
