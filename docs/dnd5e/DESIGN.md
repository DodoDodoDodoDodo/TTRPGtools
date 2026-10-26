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
- No player view, ever (Dodo, 2026-09-29).
- Our own 5e character builder will feed the party list once it exists.

### Future TODO: dodo-dodo premium gates (Dodo, 2026-10-22, not to be built yet)

Joke features Dodo wants noted for later, after the encounter tools get their DDB-style rework:
- Encounters: building an encounter with more than one monster is a dodo-dodo premium feature.
  Later variant (Dodo, same day): each monster a non-premium DM adds is gated by a d20 roll, added only
  on 16 or higher; premium DMs add freely.
- Monster search: whatever the sort order, the first half of the results show only name and CR for
  non-premium users, the expanded stat block blurred, the way D&D Beyond blurs content one does not own.
- Characters: built for 5e on 2026-10-22 (second character refused, "Don't lose <name>!", the Otyugh popup).
  2026-10-24 (Dodo): without premium only the owner's FIRST character (earliest `created`) can be saved; later ones
  are read only (save refused with 403, banner with the pitch-in link on every builder and sheet page). Admins exempt;
  an unreachable home app counts as premium. Play state (HP, slots) of a read-only character is not saved either.
  DCC, decided by Dodo: a funnel of level-0 peasants stays free; leveled characters are limited to one per
  player like 5e. DH1e: characters need an owner field before the limit can count them.
- Mobile layout (Dodo, 2026-10-22, said in passing): the phone layout of sheet and builder as a premium feature.
  Not decided how: a nag like the Otyugh rather than a lock, so a player at the table is never stuck.
Premium status lives in the home app (bird-tube `is_premium`); the TTRPG app would read it from there.
Every gate links to the pitch-in section, `/#contrib` on home.dodo-dodo.de, like the site footer.

## 12. Character builder and sheet, D&D Beyond parity (planned 2026-10-20)

Research 2026-10-20. Feature list: `docs/dnd5e/ddb-features.md` (102 core, 119 full, 14 skip items, the 2014 formula for every derived value, DDB's override catalog, the 2024-only exclusions). Assets: `content/dnd5e/private/ddb/` (gitignored, 156 MB), grabbed with `grab.py` in that folder from the four public table characters at three viewports.

### What the grab holds

- `svg/`: 94 inline SVGs. 22 are sheet frames (`ddbc-box-background`: ability box, AC shield, initiative hexagon, proficiency and speed boxes, section borders), the rest are icons (concentration, ritual, attack types, currency, placeholders, tooltips). `contact-sheet.html` shows all of them with size and origin.
- `assets/`: 265 files referenced by the three stylesheets: condition, action, ability, item-type, spell-school and attack-type icons, sheet textures (`background_texture`, `texture-dark`, `texture-light`), avatar frames. About 120 MB of it is animated premium avatar frames and marketing art, unused.
- `css/`: the character-app stylesheet (890 KB) and two site sheets. `shots/`: full-page screenshots per viewport and tab. `character-86402858.json`: one public character JSON.
- Missing: Spells, Description and Notes tabs (the tab click hit the site menu), sidebar panes, the builder (needs a DDB login).

Facts that shape the build:

- Frames carry the theme colour inline (`#C53131`, `#C5313180`). Import replaces it with `var(--theme)`, so a per-character colour costs nothing.
- Large boxes are drawn per size, not stretched: the 230x765 skills box and the 228x338 box are different paths. Copy DDB's fixed grid per breakpoint at exact pixel sizes. Arbitrary sizes need CSS `border-image` slices of the corners.
- The live DDB sheet shows 2024 wording on 2014 characters (Heroic Inspiration, the Nick property, Study, Influence, Magic, Utilize). We take layout and frames, never wording. All text comes from the compendium.
- DDB's model is choices plus typed modifiers, summed at render. That is our decision log plus effects engine (`docs/DESIGN.md` 4.2, 4.3).

### Test oracle

The four table characters exist on DDB as public JSON and as rendered sheets. Each is rebuilt from a decision log, and its derived numbers (AC, HP, saves, skills, passives, attacks, spell DC, slots) are compared with DDB's rendered values as golden tests. Alex Wilhelms covers multiclass and pact magic, the two barbarians cover Unarmored Defense and Rage, the cleric covers armour, shield and prepared casting.

### Compendium facts for the builder (census 2026-10-20)

- 36 classes, of which 12 PHB plus Artificer are Wizards; the rest are homebrew (Tanares, LaserLlama, Illrigger, Gunslinger, Pugilist, Blood Hunter, UA). Class rows carry no source; each feature row does.
- Subclasses and options are optional feature rows named by prefix: `Otherworldly Patron: The Fiend`, `Invocation: Agonizing Blast`, `Maneuver: Precision Attack`, `Metamagic: Quickened Spell`, `Infusion: Enhanced Weapon`, `Pact Boon: Pact of the Blade`, `Fighting Style: Archery`. Prerequisites are prose. Warlock alone has 340 rows, about half homebrew or UA.
- 193 source titles. `bestiary.is_official` is a deny-list and passes Griffon's Saddlebag, HeavyArms, Ben Huffman, Mordenkainen's Codex of Allies. The builder uses an exact allow-list of Wizards titles instead (DESIGN 4.4). Unearthed Arcana, Plane Shift, Critical Role's Blood Hunter and DMs Guild titles stay out unless Dodo adds them.

### Minimum viable version (target 2026-10-20)

Dodo: "the 5e character builder with ALL official 5e options", built on what exists. Content breadth is full from the start because the converter is generic; feature depth starts small.

1. `ttrpgtools/dnd5e/content.py`: compendium to one JSON pack per allow-listed book in `content/dnd5e/private/packs/`. Classes with subclass groups and option groups by prefix, races and subraces, backgrounds, feats, spells, items, prerequisites parsed where the prose is regular. A coverage table per book is printed on every build.
2. API in `ttrpgtools/dnd5e/routes.py`: content lists, character CRUD on `characters/dnd5e/<id>.json` (decision log, owner from `Remote-User`).
3. `frontend/dnd5e/`: Svelte with Vite, built in a Node stage of the Dockerfile, served by Flask under `/TTRPG/dnd5e/characters/`. Builder steps in any order: race, class with subclass and every option group at its level, abilities (standard array, point buy, manual), background, equipment (pack or gold), spells, level-up with ASI or feat, multiclass add.
4. `ttrpgtools/dnd5e/character.py`: decision log to sheet (abilities, proficiency, saves, skills, passives, initiative, HP, AC formulas, speed, attacks, spell DC and slots including pact and multiclass tables, limited-use maxima). Golden tests against the four DDB characters.
5. Sheet on the real DDB frames, desktop first, with rules-text popovers and play state.

Risk accepted for the minimum: anyone at the table can edit any character until edit rights exist.

### Intended design (after the minimum runs end to end)

- Multiclass with prerequisites, the combined slot table and separate pact slots.
- Every option picker: invocations, pact boon, metamagic, maneuvers, infusions, arcanum, magical secrets, totem and draconic choices, Tasha's optional features and Customizing Your Origin.
- Per-character book toggles.
- Inventory: containers, attunement slots, charges with reset, consumables, encumbrance rules, coin weight, custom items, party inventory.
- One override table (target, field, value, note) shown with an asterisk, covering DDB's catalog.
- Conditions with mechanics, 2014 exhaustion, active-effect toggles (Rage, Bladesong, Mage Armor).
- Extras: familiars, companions, Wild Shape forms from the bestiary.
- Tablet and mobile layouts with DDB's per-breakpoint frames, theme colour, backdrop.
- Import of a DDB character JSON into a decision log (extends `ddb_character.py`), print and PDF fill through `sheetfill.py`.

### Decided 2026-10-20 (Dodo)

- Svelte with Vite.
- 5e builder now, on top of the existing code; the DH1e port waits.
- Builder look: Dodo saves the logged-in DDB builder pages into `DnD_books/5e_stuff/ddb/`. Until then the builder uses the sheet frames.

### Built 2026-10-21 (night), minimum viable version

Live at `/TTRPG/dnd5e/characters/` (Characters link in the 5e nav). Status by MVP step:

| Step | File | Check |
|---|---|---|
| 1 Content | `ttrpgtools/dnd5e/builder_data.py` (5etools-src to `content/dnd5e/private/builder/`), `content.py` (compendium packs, kept as cross-check) | `tests/dnd5e/test_content.py`; counts equal the books (PHB 361 spells, feats 42/15/15, 118 subclasses) |
| 2 API | `ttrpgtools/dnd5e/builder_routes.py` | content, character CRUD with version check (409), derive, DDB import, DDB frames/fonts from `content/` |
| 3 Frontend | `frontend/dnd5e/` (Svelte 5.57, Vite 6.4), built in the Dockerfile's Node stage | browser run: create, all 8 steps, sheet, spell and item panes |
| 4 Sheet math | `ttrpgtools/dnd5e/character.py`, `ddb_import.py` | `tests/dnd5e/test_character.py`: hand-checked cleric, multiclass and pact slots, point buy, and the four DDB table characters match DDB's rendered sheet on AC, HP, abilities, saves, 18 skills, passives, speed, initiative |
| 5 Sheet | `frontend/dnd5e/src/sheet/` on DDB frames by name (`/ddb/frame/<name>`) | spells and inventory link to detail panes; play state (HP, slots, pact, counters, hit dice, conditions, rests) saves to the log |

Decision taken without Dodo, to confirm: builder mechanics come from 5etools-src (pinned by `meta.json` commit), not the compendium. Reason: 5etools has the choices as data (spells known, invocations known, skill and ability choices, starting equipment, prerequisites); the compendium has them as prose. Same allow-list of 2014 books; `edition: "one"` refused. The compendium converter stays as the counts oracle.

Done later the same night: Tasha's optional class features opt-in per feature (TCE p. 8), multiclass prerequisite problems (PHB p. 163), subclass darkvision (Shadow Magic, Gloom Stalker, Twilight), magic item variants expanded from `magicvariants.json` (3490 items, "+1 Longsword" etc.).

Done 2026-10-22 00:30 tick: feature-internal choices (Favored Enemy, Natural Explorer, Dragon Ancestor, Hunter x4, Totem Warrior x3, Storm Herald x3; only real one-time choices, since 5etools also uses options blocks for lists you get in full), Dragonborn ancestry with resistance, a Defenses line, override table (AC, HP, speed, initiative, saves, skills, spell DC and attack; asterisk on the sheet), print view `#/c/<id>/print` (page one for the table with tick boxes, then PHB-style features, spells, equipment in homebrewery's CC-BY-SA fonts; Chromium PDF checked: 7 A4 pages for Veerde), phone width checked at 390 px.

Done 2026-10-22 02:30 tick: active-effect toggles (Rage with rage damage and resistances incl. Bear totem, Bladesong, Mage Armor, Shield of Faith, Barkskin, Haste, Shield, Bless), condition and exhaustion effects (speed 0 or halved, HP max halved at 4, notes for the disadvantages), PHB condition texts in the pane, Extras tab (familiar, companion, Wild Shape, other) from the bestiary filtered to the 2014 Wizards books, with its own HP tracker.

Done 2026-10-22 02:35, deployed 06:20: containers (contents nested under Backpack, Bag of Holding contents weightless), coin weight option (50 coins = 1 lb.), variant encumbrance with speed penalties.

Done 2026-10-22 16:40 to 17:09 (commits 98460f5 to fb99331), each gated against its DDB capture with the compare tool and driven in a browser: builder Abilities step (method dropdown, point buy with DDB's refund labels, standard array, manual, Score Calculations with bonus suppliers, Other Modifier, Override Score) and What's Next; sheet tabs Spells (casting numbers, search, level/concentration/ritual tabs, slot and pact boxes, Cast spends a slot, warlock spells under the pact level, upcast damage), Features & Traits (per-class blocks with Hit Points and Proficiencies, options and limited use under their parent feature), Background, Notes and Extras. DDB import now brings characteristics, personality and notes. Not captured, so our own markup: the edit side panes (texts edit in place), the advanced spell filter, the ritual icon, extras rows with creatures.

Done 2026-10-22 evening (commits 4a8465d to a856bbd): side panes in DDB markup, gated where a capture exists: Spell (cast at any open slot level), HP Management, Short and Long Rest (hit dice rolled on the short rest; 2014 PHB texts, DDB shows 2024's), Manage (the phone sheet's way to the rests), Ability (shared score table, PHB "Using Each Ability"), Conditions (toggles, exhaustion bar), Defenses, Speed, Senses (new), Armor Class (AC broken into parts by character.py), Proficiencies (hand-added proficiencies, `custom_proficiencies`, count for attacks); the remaining panes got DDB's header. New content kinds abilitytexts and ruletexts from 5etools' PHB and MM. Not done: DDB custom skills (two golden characters have them; no model yet), Inspiration, Container, Manage Inventory, Add Items, Appearance and desktop Manage Character panes.

Done 2026-10-23 morning (commits 4b6bf1d to 56af55c): one old/new design switch in the top bar (was one per chooser); phone builder band (DDB draws it only from 768px); premium label on the phone sheet for premium accounts; Inspiration pane with PHB text; custom skills (`custom_skills`, DDB import of type-1 custom proficiencies); Container, Manage Inventory (with custom items) and Appearance panes. Every pane with a capture is now ported; Add Items list pane was captured closed.

Done 2026-10-23 (c0e0a1e, 15f467c): new design = DDB's newer builder: start page (builder/start: portrait, name, Class/Race/Background cards, Create Character) and finish page (builder/finish: Character Complete, View Character Sheet). DDB's "How to get started" cards are replaced by campaigns (Dodo): tables `campaigns` (id, name, dm, created, data) and `campaign_members` (campaign_id, character_id, added_by, joined) in data/dnd5e.sqlite, module `ttrpgtools/dnd5e/campaigns.py`, API `/api/campaigns` (GET, POST), `/api/campaigns/<id>/characters` (POST join, DELETE leave). Open list for now; intended: invite links, a DM view of the party, the encounter manager taking its party from `campaigns.get(id)["characters"]`.

Done 2026-10-23 10:40 to 16:52 (a9fe22c to 068f69b, checklist audit against ddb-features.md, every item checked on the live site with a throwaway character):
- Bugs: MPMM/VRGR/AAG lineage races had no ASI (builder_data.expand_lineage, 5etools adds it at render time); Extra Attack and Channel Divinity stacked across classes; monk unarmed strike "6+3"; desktop Spells tab hidden for racial-only casters; header healing kept death saves; first override/bonus feat on a fresh character not saved (Svelte `??=` on a proxy).
- Builder: XP advancement (XP bar, Manage XP pane), packs expand into their container, Mystic Arcanum, Magical Secrets (+ Lore's extra), Spell Mastery, Signature Spells, invocation prerequisites, rogue thieves' tools expertise, Customize Your Origin, Custom Lineage variable trait, background skill overlap replacement, customized background name and feature, Elemental Adept type, EK/AT school count, picks drop when a level is removed.
- Sheet math: item and Aura of Protection saves, item spell DC/attack, attunement limit, Remarkable Athlete, size/Powerful Build capacity, Mobile, item speeds, defenses from items and class features, race/feat trait uses from their text, racial spell use boxes, item charges, class values (Sneak Attack...), monk weapons, off-hand attack, Wild Shape limits, wizard book rituals, save advantage notes.
- Sheet UI: Manage Feats pane, customize senses/speeds/defenses, primary movement in the header, Show Unarmed Strike, My Characters copy and sort.
- Checked and NOT built because DDB does not have it: subclass in the header, lifestyle on the sheet.

Open, needs Dodo: edit rights/privacy (anyone can edit any character), party inventory, homebrew toggle, per-book source toggles (DDB itself has only category toggles). Done later 10-23 (63d930e..): artificer infusions on items, coins in containers, hide-in-sheet, passives -5 while poisoned/exhausted; Noble's Retainers is reachable through Configure (feature from Variant Noble), as DDB drops that variant. Open, smaller: DDB-style mobile carousel (5/10, OPEN_TODOs). 5etools as the mechanics source: confirmed by Dodo 2026-10-25. Per-book source switches built 2026-10-25 (books.json kind; groups rules / adventures / other; preferences.books_off). Party inventory and homebrew: 1/10 future TODOs.

### 5e start page and navigation (2026-10-25, Dodo)

`/TTRPG/dnd5e/` is a hub in D&D Beyond's look (`dnd5e_hub.html`, `static/dnd5e/hub.css`, `hub.js`): six art tiles, Characters, Encounters, Campaigns, Equipment, Monsters, Other, 3x2, each with a "Continue" card. Characters, campaigns and encounters come from `GET /characters/api/recent` (the player's own, last saved); equipment, monsters and Other from this browser's `localStorage["dnd5e-recent"]`, written when an item, monster or rules entry is opened. Encounters and fights moved to `/TTRPG/dnd5e/encounters`; the imported-PC party section is gone (campaigns are the party). Campaigns (`#/campaigns[/<id>]`), Equipment (`#/equipment[/<item>]`) and Other (`#/rules`, search over every rules text plus the books from Audiobookshelf's DB and the DnD_books share, both mounted read-only) are pages of the character app; its top bar carries the same six links. Intended, not built: the local model helping with the Other search, PDFs embedded (Dodo 2/10), full-text search inside the PDFs.

### Rules helper (2026-10-25, Dodo)

`ttrpgtools/dnd5e/explain.py`: an FTS5 index (`content/dnd5e/private/explain.sqlite`, 52k passages, built on the host with `python -m ttrpgtools.dnd5e.explain build ~/TTRPGtools/5etools-src`) of the 5etools book and adventure text published before 2024-09-17 plus the builder's rules entries, each passage tagged with its book; books are grouped rules (core, supplement, setting, screen), adventures, other. Retrieval: every question word brings its own best passages, ranked by rarity-weighted word coverage, then bm25. The answer comes from DCC's model harness (`dcc.explain._model_stream`, the 9B in `llm`), at most 130 words, citing book and page. UI: question box and a hidden "Search in" picker on the Other page (only rules on by default, remembered per browser), "Explain this" in the side pane. Limits: 1 answered question an hour free, 100 a day with premium (`explain_log` in dnd5e.sqlite; only answered questions count). Errors: "Model currently unavailable" (no answer), "Model currently busy, check back in a minute" (timeout while another service holds the model). Known limit: word matching, not meaning (e.g. "grapple while holding a shield" misses PHB p. 195); intended: semantic retrieval.
Noncanon items (5etools `age`: Renaissance, modern, futuristic; 272 items) are hidden in every item list behind "Show noncanon" (default off, per browser).

## 2026-10-26 · shared page helper
One helper for every site (Dodo: "build an overall helper framework"): `ttrpgtools/helper.py` (model stream, prompt with the page breadcrumb, SSE, quota 1/h free, 100/day premium, sqlite in data/helper-quota.sqlite) and `web/static/helper.js` + `helper.css` (header button, sticky header, small window, question box, "What is this?" click mode that sends breadcrumb + element HTML + surrounding text + site extra). Configured per page with `window.DODO_HELPER = {site, api, header, title, placeholder, extra}`; the site's `/api/explain` builds its passages and calls `helper.user_prompt` + `helper.answer_events`. Live on DCC (replaces dcc_assist's own explain) and all 5e pages. The breadcrumb fixed the DCC gold-field answer (was "fixed by the bank"; now the Inventory coin field under the campaign money rule). DCC players now share the same 1/h free quota (they had none before). Next sites: DH1e, home.dodo-dodo.de.

## 2026-10-26 evening · harness redesign (Dodo: "simple, clean, elegant", follow-ups)
`ttrpgtools/helper.py` is the whole loop; a site is one `Site(name, game, system, search, vocab, default_question)` (dcc/explain.py, dnd5e/explain.py, dh1e/explain.py, each ≈ 40 lines of search). Per question: (1) the model writes 3–8 search terms from question + thread + what is on screen, told the search is exact and fuzzy; (2) `Vocab.close` widens each term to close spellings of the books' own words (FTS stems via the same tokenizer; difflib ≥ 0.82); same-stem terms merge into one group; (3) `site.search(groups, request)`: main terms fill the pool, variants add a few, rank = rarity × (title 2, title-is-term 3, variant ½); (4) streamed answer with the thread as prior turns and the page snapshot in the last turn. Routes call `helper.serve(SITE, user, premium, body)`. Window: Q/A bubbles, selected-element chip, "New thread"; a click only selects and highlights the question box (Dodo). Verified: DCC actions + follow-up on carrying, DH1e "fate poins" typo → Fate Points rules, 5e "sheild" → Grappling p. 195. Next: note-to-self per site (≤600 chars, fed into passes 1 and 2), then a second search round when the first is poor.

## 2026-10-26 late · spell filters, home site
Spell step: a "Filter spells" panel (level, school, casting time, range, damage type, saving throw, concentration, "Does" = damage/healing/protection/control/summoning/teleport/utility from 5etools miscTags, ritual, no material component) narrows every picker; chosen spells stay listed. Checked with a throwaway wizard: 30 cantrips → 10 Evocation → 8 damage → 30 after Clear. The helper harness now also serves home.dodo-dodo.de (bird-tube mounts `ttrpgtools/` and `web/static` read-only; its Site searches the guide and home page text). Phrases from the model ride along with their words as variants.
