# D&D Beyond builder + sheet: feature inventory for our 5e-2014 tool

Researched 2026-10-20. Target: D&D 5e **2014 rules only**, single home table, no dice rolling.

Legend: **[core]** needed for a usable first character. **[full]** needed for DDB parity. **[skip]** low value for one home table.
Marker `(unverified)` = from forum reports or inferred from JSON enum values, not from an official page.

Primary sources used throughout:
- S1 Builder Sections (official): https://dndbeyond-support.wizards.com/hc/en-us/articles/7747202748436-Builder-Sections
- S2 Sheet Sections (official): https://dndbeyond-support.wizards.com/hc/en-us/articles/7747193946388-Sheet-Sections
- S3 Character Header (official): https://dndbeyond-support.wizards.com/hc/en-us/articles/7747193980820-Character-Header
- S4 Miscellaneous Features (official): https://dndbeyond-support.wizards.com/hc/en-us/articles/7747193953556-Miscellaneous-Features
- S5 Content Categories (official): https://dndbeyond-support.wizards.com/hc/en-us/articles/7747201820948-Enabling-Content-Categories-for-your-Character-Sheet
- S6 Extras (official): https://dndbeyond-support.wizards.com/hc/en-us/articles/7747209465748-Extras
- S7 Export Sheet (official): https://dndbeyond-support.wizards.com/hc/en-us/articles/7747238449556-Export-Sheet
- S8 Speeds (official): https://dndbeyond-support.wizards.com/hc/en-us/articles/7747241091988-How-to-Add-or-Customize-Speeds
- S9 Party Inventory FAQ (official): https://dndbeyond-support.wizards.com/hc/en-us/articles/40964522619540-Shared-Party-Inventory-FAQ
- S10 Changelog, customization/senses/defenses (2017): https://www.dndbeyond.com/old-changelog/122-more-customization-options-custom-senses-and
- S11 Changelog, coin containers: https://www.dndbeyond.com/old-changelog/1167-cointainers-are-now-available-in-your-inventory
- S12 Changelog, custom items: https://www.dndbeyond.com/old-changelog/1133-custom-items-upgrade
- S13 Character JSON (public, fetched once): https://character-service.dndbeyond.com/character/v5/character/86402858 (a 2014 Sorcerer 4 / Warlock 2 from our table; local copy in `content/dnd5e/private/ddb/`)
- S14 ddb-importer source (Foundry importer that parses S13's format; types and calc logic): https://github.com/MrPrimate/ddb-importer (files `src/types/ddb-character-source.d.ts`, `src/parser/character/*.ts`, `src/parser/lib/DDBDataUtils.ts`, `src/parser/DDBExtras.ts`, `src/config/dictionary/actor/resets.ts`)
- S15 Forum threads (anecdotal): encumbrance https://www.dndbeyond.com/forums/d-d-beyond-general/bugs-support/19767-variant-encumbrance ; max HP https://www.dndbeyond.com/forums/d-d-beyond-general/bugs-support/53380-permanently-changing-max-hp ; manual HP https://www.dndbeyond.com/forums/d-d-beyond-general/general-discussion/41300-ddb-manual-hp-when-leveling-up ; AC override https://www.dndbeyond.com/forums/d-d-beyond-general/d-d-beyond-feedback/143309-ac-override
- Rules values in section 3 are 2014 PHB / SRD 5.1 rules, not DDB-specific.

Caveat: S1 and S2 carry the banner "has not yet been updated" after the 2024 builder rework; layout details may differ from today's live site.

---

## 0. DDB data model (from S13 + S14), for reference

One character document; everything else is derived at render time. Top-level fields worth mirroring:

- identity: `name, gender, age, hair, eyes, skin, height, weight, faith, alignmentId, lifestyleId, decorations{avatarUrl, frame, backdrop, themeColor}`
- stats: `stats[6]` (base), `bonusStats[6]`, `overrideStats[6]`
- HP: `baseHitPoints` (sum of per-level rolls/fixed), `bonusHitPoints`, `overrideHitPoints`, `removedHitPoints` (damage taken), `temporaryHitPoints`, `deathSaves{failCount, successCount, isStabilized}`
- progress: `currentXp`, `inspiration` (bool), `classes[]{level, isStartingClass, hitDiceUsed, definition, subclassDefinition, classFeatures[]{definition, levelScale}}`
- origin: `race{racialTraits[], isSubRace, ...}`, `background{definition | customBackground, hasCustomBackground}`, `feats[]`, `optionalOrigins[]`, `optionalClassFeatures[]`
- choices: `choices{race,class,background,item,feat}[]{type, label, optionValue, options}`; selected sub-options in `options{...}` (e.g. Quickened Spell, Agonizing Blast)
- effects: `modifiers{race,class,background,item,feat,condition}[]{type, subType, value, fixedValue, statId, dice, restriction, requiresAttunement, isGranted}`. Types seen: `bonus, set, set-base, proficiency, half-proficiency, expertise, advantage, disadvantage, resistance, immunity, vulnerability, language, sense, ignore, protection`. Subtypes include `armor-class, armored-armor-class, unarmored-armor-class, minimum-base-armor, ac-max-dex-modifier, unarmored-dex-ac-bonus, hit-points(-per-level), speed/unarmored-movement, ability-score-maximum, <ability>-score, <ability>-saving-throws, <skill>, darkvision, spell-save-dc, ...`
- actions: `actions{race,class,feat,...}[]{name, activation, actionType, attackTypeRange, dice, abilityModifierStatId, saveStatId, fixedSaveDc, isProficient, displayAsAttack, limitedUse}`
- limited use: `limitedUse{maxUses, numberUsed, resetType(1 SR, 2 LR, 3 Dawn/day, 4 Other/charges), statModifierUsesId, useProficiencyBonus, operator}`
- spells: `classSpells[]{characterClassId, spells[]{prepared, alwaysPrepared, countsAsKnownSpell, usesSpellSlot, castOnlyAsRitual, limitedUse, spellCastingAbilityId}}`, `spells{race,feat,item,background}[]`, `spellSlots[9]{level, used, available}`, `pactMagic[]{level, used, available}`; class `spellRules{levelSpellSlots, levelCantripsKnownMaxes, levelSpellKnownMaxes, levelPreparedSpellMaxes, multiClassSpellSlotDivisor, multiClassSpellSlotRounding, isRitualSpellCaster}`, `spellPrepareType`, `knowsAllSpells`
- inventory: `inventory[]{definition, quantity, equipped, isAttuned, chargesUsed, limitedUse, containerEntityId, currency}`; item def has `weight, weightMultiplier (container), capacityWeight, canAttune, armorClass, armorTypeId, strengthRequirement, stealthCheck, damage, damageType, properties, range/longRange, isMonkWeapon, grantedModifiers, isConsumable`; `customItems[]{name, description, weight, cost, quantity, notes}`; `currencies{cp,sp,ep,gp,pp}`
- customizations: `characterValues[]{typeId, value, valueId, valueTypeId, notes}` (catalog in section 4), `customDefenseAdjustments, customSenses, customSpeeds, customProficiencies, customActions`
- prose: `traits{personalityTraits, ideals, bonds, flaws, appearance}`, `notes{allies, enemies, organizations, backstory, personalPossessions, otherHoldings, otherNotes}`
- `conditions[]{id, level}` (exhaustion carries level), `creatures[]` (extras), `campaign{...}`, `preferences{...}`, `configuration{...}` (section 1.1)

Design hint: DDB's engine is "modifier list in, numbers out". Every source (race, class feature, feat, item, condition) contributes typed modifiers; the sheet sums them. Copying that shape is the main architectural decision.

---

## 1. Builder

### 1.1 Home / preferences
Sources: S1, S4, S5, S13 `preferences`/`configuration`, S14 `IDDBPreferences`, S15.

- [ ] [core] Character name + portrait upload/URL (skippable at start, editable later)
- [ ] [full] Source toggles by category (2014 Core, 2014 Expanded, Legacy, Homebrew); for us: per-book toggles (PHB, XGtE, TCoE, ...) filtering every option list
- [ ] [skip] Partnered content toggles, purchase/content-sharing gating
- [ ] [full] Homebrew toggle (`useHomebrewContent`); needs our own homebrew authoring to mean anything
- [ ] [full] Optional class features toggle (TCoE; `enableOptionalClassFeatures`)
- [ ] [full] Customize Your Origin toggle (TCoE; `enableOptionalOrigins`); adds an "Origin Manager" to the race step (S15, unverified wording)
- [ ] [core] Advancement type: Milestone (default) vs XP (`progressionType`)
- [ ] [core] Hit point type: Fixed (default, average) vs Manual (enter rolled value per level) (`hitPointType`, 2 = manual per S14)
- [ ] [full] Encumbrance type: Use Encumbrance / No Encumbrance / Variant Encumbrance (`encumbranceType` 1/2/3, numbering unverified)
- [ ] [full] Ignore coin weight (`ignoreCoinWeight`)
- [ ] [full] Put coins in containers (`enableContainerCurrency`, set in the currency sidebar; S11)
- [ ] [full] Enforce multiclass ability requirements (`enforceMulticlassRules`)
- [ ] [full] Enforce feat prerequisites (`enforceFeatRules`)
- [ ] [full] Show level-scaled spells (upcast options highlighted; `showScaledSpells`)
- [ ] [full] Show unarmed strike in actions (`showUnarmedStrike`)
- [ ] [skip] Ability score display: score on top vs modifier on top (`abilityScoreDisplayType`)
- [ ] [full] Primary sense / primary movement shown in header (`primarySense`, `primaryMovement`; S8, S10)
- [ ] [full] Character privacy: Private / Campaign Only / Public (`privacyType`; semantics conflict across forum threads)
- [ ] [skip] `sharingType`, `longRestType` (meaning not documented; longRestType possibly 2014-vs-2024 hit-dice recovery, unverified)
- [ ] [skip] Dark mode ("Underdark") and sheet decorations (frame, backdrop, theme color) (S3); cheap later polish
- [ ] [full] Help text toggle (`showHelpText`) and "(!)" markers on unmade choices (S4)
- [ ] [core] "Sheet ready" gate: sheet opens once class, race, background, ability scores are set (S4)
- [ ] [skip] Creation methods besides Standard: Quickbuilder (guided L1), Premade claim (S4 creation methods article 7747193997716)
- [ ] [excluded] Digital dice preference, dice set (`diceSetId`)

### 1.2 Class step
Sources: S1, S13 `classes`, `choices`, `options`, `spellRules`.

- [ ] [core] Pick class; show hit die, primary ability, saving throw profs, armor/weapon/tool profs
- [ ] [core] Class level selector (1-20); features listed per level, collapsed/expanded
- [ ] [core] Class skill choices (choose N from list)
- [ ] [core] Subclass choice at the class's own level (2014: Cleric/Sorcerer/Warlock L1; Druid/Wizard L2; others L3); subclass features merged into the level list
- [ ] [core] Fighting Style (Fighter L1, Paladin L2, Ranger L2; Champion L10 second style)
- [ ] [core] Expertise picks (Rogue L1/L6, Bard L3/L10); restricted to proficient skills (+ thieves' tools for Rogue)
- [ ] [full] Eldritch Invocations (Warlock; known count by level; prerequisites: level, pact boon, cantrip; swap one on level up)
- [ ] [full] Pact Boon (Warlock L3: Chain/Blade/Tome; TCoE Talisman)
- [ ] [full] Metamagic (Sorcerer L3/10/17)
- [ ] [full] Maneuvers (Battle Master, known count + superiority dice), Arcane Shot options, Rune Knight runes
- [ ] [full] Artificer infusions (known vs active, attach to items, `levelInfusionGranted`)
- [ ] [full] Favored Enemy / Natural Explorer (Ranger 2014) with terrain/enemy choices; TCoE replacements via optional features
- [ ] [full] Totem / Aspect / Path choices with sub-options (Barbarian Totem Warrior animals per tier)
- [ ] [full] Draconic ancestry (Sorcerer) and similar damage-type picks
- [ ] [full] Mystic Arcanum picks (Warlock L11/13/15/17, one spell each, 1/LR)
- [ ] [full] Magical Secrets (Bard, any class list), Additional Magical Secrets (Lore)
- [ ] [full] Optional class features (TCoE) shown as opt-in per level when the toggle is on
- [ ] [core] Hit points per level: fixed average or manual entry ("Manage HP" box) per class level
- [ ] [core] Proficiencies granted per class; multiclass gets the reduced multiclass proficiency set
- [ ] [core] Class spells management entry point (see 1.9)
- [ ] [full] Feature choices change-able after the fact (retrain: invocation swap, spell swap on level)

### 1.3 Multiclassing
Sources: S1 (multiclass in Class step), S13 (`isStartingClass`, `spellRules.multiClassSpellSlotDivisor/Rounding`), PHB ch.6.

- [ ] [full] Add another class; starting class flag drives saves, full proficiencies, and equipment
- [ ] [full] Prerequisite check (13 in class prereq abilities, both in-class and out) honoring the enforce toggle
- [ ] [full] Multiclass proficiency subsets per class
- [ ] [full] Combined spell slot table: caster level = full + floor(half/2) (+ ceil for Artificer) + floor(third/3); single-class half casters use their own table
- [ ] [full] Pact Magic slots kept separate from the combined table
- [ ] [full] Per-class spell lists, spellcasting ability and DC kept separate
- [ ] [full] Channel Divinity, Extra Attack, Unarmored Defense non-stacking rules
- [ ] [full] Total level drives proficiency bonus and ASI/feat schedule per class levels

### 1.4 Race / subrace (2014 "Species" tab)
Sources: S1, S13 `race`, S15 Customize Origin thread, changelog 1108 (subraces & variants): https://www.dndbeyond.com/old-changelog/1108-character-builder-races-subraces-variants

- [ ] [core] Pick race, then subrace if required (e.g. Hill Dwarf, Lightfoot Halfling, High Elf)
- [ ] [core] Racial ASIs (fixed per race; Half-Elf +2 Cha and two +1 of choice; Variant Human two +1)
- [ ] [core] Racial traits list with full text (speed, size, darkvision, languages, proficiencies, resistances)
- [ ] [core] Race choices: extra language, skill (Half-Elf, Variant Human), feat (Variant Human), cantrip (High Elf), draconic ancestry (Dragonborn)
- [ ] [core] Racial innate spellcasting (e.g. Tiefling Infernal Legacy, Drow Magic) with level gating and 1/LR uses
- [ ] [full] Tasha's Customizing Your Origin: move ASIs to any abilities, swap languages, swap proficiencies of same kind
- [ ] [full] Custom Lineage (TCoE): +2 one ability, feat, darkvision or skill, size choice
- [ ] [full] Monsters of the Multiverse style races (2022, still 2014 ruleset): floating +2/+1 or +1/+1/+1, uses = proficiency bonus
- [ ] [full] Powerful Build, natural armor, natural weapons fed into engine
- [ ] [skip] Legacy/duplicate race versions

### 1.5 Abilities
Sources: S1, S13 `configuration.abilityScoreType`, PHB ch.1.

- [ ] [core] Standard array (15, 14, 13, 12, 10, 8) assigned via dropdowns, each value once
- [ ] [core] Point buy (27 points, 8-15 range, cost table 8:0 ... 13:5, 14:7, 15:9) with remaining-points counter
- [ ] [core] Manual / rolled entry (3-18 typed in; we do not roll)
- [ ] [core] Breakdown per ability: base + racial + ASI/feat + misc bonus + override = total, and modifier
- [ ] [full] Per-ability "other bonus" and "override" fields (S14 characterValues typeId 39/40/41)
- [ ] [full] Score cap 20 with raise-cap effects (Primal Champion 24, manuals/tomes)
- [ ] [full] Set-to-value items (Headband of Intellect 19, Belt of Giant Strength) applied only if higher

### 1.6 Background
Sources: S1, S13 `background`, `traits`.

- [ ] [core] Pick background; grants 2 skills, tools/languages, equipment, feature text
- [ ] [core] Personality traits / ideals / bonds / flaws: pick from d8/d6 tables or write free text
- [ ] [full] Background variants (e.g. Criminal / Spy) and choice of feature variant
- [ ] [full] Customized background (PHB): pick feature from any background, any 2 skills, 2 tools/languages, custom name/description
- [ ] [full] Overlapping proficiency rule: duplicate skill from race/class lets you pick a replacement

### 1.7 Equipment step
Sources: S1, S13 `configuration.startingEquipmentType`, class `wealthDice`, PHB ch.5.

- [ ] [core] Starting equipment: class option sets (a or b), plus background equipment, auto-added to inventory
- [ ] [core] Equipment packs (Explorer's, Dungeoneer's, Burglar's ...) expand into contents
- [ ] [full] Starting gold instead: enter gold (class wealth dice table shown as text, we do not roll)
- [ ] [core] Add items manually (search catalog: weapons, armor, gear, tools, magic items)
- [ ] [core] Equip armor/shield/weapons from builder; sheet recomputes
- [ ] [full] Attunement from builder
- [ ] [full] Custom items (name, description, weight, cost, quantity, notes; S12)

### 1.8 Description
Sources: S1, S13 identity fields, `notes`, `traits`, `lifestyleId`.

- [ ] [core] Alignment (9 options + unaligned)
- [ ] [full] Faith / deity (free text)
- [ ] [full] Lifestyle (wretched ... aristocratic) with daily cost
- [ ] [core] Physical: age, height, weight, eyes, hair, skin, gender, appearance text
- [ ] [core] Personal characteristics (from 1.6)
- [ ] [full] Notes: organizations, allies, enemies, backstory, other notes
- [ ] [skip] Size picker (only where race offers a choice)

### 1.9 Spells management (builder + sheet "Manage Spells")
Sources: S1, S2, S13 `classSpells`, `spellRules`, PHB ch.10-11.

- [ ] [core] Cantrips known count per class level (table)
- [ ] [core] Known casters (Bard, Sorcerer, Warlock, Ranger, EK, AT): pick up to known max; swap one per level
- [ ] [core] Prepared casters (Cleric, Druid, Paladin, Wizard, Artificer): whole class list available (or spellbook), prepare up to max
- [ ] [core] Prepared max: Cleric/Druid/Wizard = mod + level; Paladin = mod + floor(level/2); Artificer = mod + floor(level/2); minimum 1
- [ ] [core] Always-prepared spells (domain, oath, circle, Artificer subclass, Warlock expanded list adds to options only) not counting toward max
- [ ] [full] Wizard spellbook: 6 at L1, +2 per level, add copied spells (cost/time as text); prepare from book only
- [ ] [full] Ritual casting: Wizard from book without preparing; Cleric/Druid if prepared; Bard if known; Ritual Caster feat book; ritual tag + filter
- [ ] [full] EK / AT school restrictions (abjuration/evocation, enchantment/illusion) with free picks at set levels
- [ ] [full] Spells from race/feat/item: separate entries with own ability, DC, uses (1/LR) and no slot use
- [ ] [full] Max spell level available per class (from slot table, pact slot level for Warlock)
- [ ] [full] Spell detail view: level, school, casting time, range, components (material text), duration, concentration, ritual, full text, at-higher-levels
- [ ] [full] Signature Spells / Spell Mastery (Wizard L18/L20) flags
- [ ] [skip] Spell list filtering by source book beyond the global source toggles

### 1.10 Level up flow
Sources: S1, S3 ("Manage Character & Levels", "Manage Experience"), S15 manual HP.

- [ ] [core] Change level in class step (or add a level of another class)
- [ ] [core] XP mode: XP total, next-level threshold, level-up prompt when crossed; milestone mode: direct level set
- [ ] [core] HP added per level (fixed or manual entry)
- [ ] [core] New features listed; "(!)" markers on new choices (subclass, ASI, invocation, spells)
- [ ] [full] Level-down supported (choices above new level dropped, kept in history)
- [ ] [full] XP log / adjust XP by amount (DDB `adjustmentXp`)

### 1.11 ASI vs feat
Sources: S13 class features "Ability Score Improvement" at 4/8/12/16/19 (Fighter +6/14, Rogue +10), `feats[]`, `enforceFeatRules`.

- [ ] [core] At each ASI level: +2 to one or +1 to two abilities (cap 20)
- [ ] [full] Or a feat instead (variant rule, on by default in DDB)
- [ ] [full] Feat prerequisites (ability score, proficiency, spellcasting, race) honoring enforce toggle
- [ ] [full] Half-feats (+1 ability choice inside the feat)
- [ ] [full] Feats with sub-choices (Magic Initiate class + spells, Skilled, Elemental Adept type, Ritual Caster class)
- [ ] [full] Feats granted outside ASI slots (Variant Human, Custom Lineage, DM-granted boons; S13 shows "Hero's Journey Boon", "Dark Bargain" as feats)
- [ ] [full] "Manage Feats" on sheet: add arbitrary feat (S2)

---

## 2. Sheet

Sources for this section: S2, S3, S6, S7, S8, S9, S10, S13.

### 2.1 Header
- [ ] [core] Portrait, name, race, class/subclass with level per class, total level
- [ ] [core] XP bar (current / next threshold) in XP mode; level only in milestone mode
- [ ] [core] Short Rest button: spend hit dice (count per die size, we do not roll: enter HP regained), reset SR resources, pact slots
- [ ] [core] Long Rest button: full HP, regain half total hit dice (min 1), reset LR resources and slots, clear temp HP; option to keep max-HP changes (S15)
- [ ] [full] Dawn reset button (magic item charges) (S2)
- [ ] [core] Inspiration toggle (2014: boolean)
- [ ] [full] Campaign name link
- [ ] [core] Edit / go-to-builder link; character menu (rename, settings, manage XP, export)
- [ ] [skip] Sheet appearance (frame, backdrop, theme, Underdark mode)

### 2.2 Ability scores and saving throws
- [ ] [core] Six boxes: modifier prominent, score secondary (or swapped by pref)
- [ ] [core] Saving throws with proficiency marker and total
- [ ] [full] Save advantage/disadvantage notes (e.g. Dwarven Resilience vs poison, Gnome Cunning, Brave, Danger Sense, Magic Resistance); text list under saves
- [ ] [full] Per-save override / misc bonus

### 2.3 Senses
- [ ] [core] Passive Perception, Passive Investigation, Passive Insight
- [ ] [core] Darkvision etc. with range (blindsight, tremorsense, truesight)
- [ ] [full] Custom senses and passive overrides with notes; pick which sense shows in header (S10)

### 2.4 Proficiencies and languages
- [ ] [core] Armor, weapons, tools, languages lists aggregated from all sources
- [ ] [core] Proficiency bonus shown
- [ ] [full] "Manage Proficiencies": add custom proficiency/language with source note (S2)

### 2.5 Skills
- [ ] [core] 18 skills: ability tag, proficiency state (none / half / proficient / expertise), total
- [ ] [full] Skill advantage notes (e.g. Naturally Stealthy text, Stonecunning), Jack of All Trades half proficiency shown
- [ ] [full] Per-skill override, misc bonus, magic bonus, proficiency-level override, ability swap (S14 typeId 24-27)
- [ ] [full] Tool checks with proficiency (separate list)

### 2.6 Combat block
- [ ] [core] Initiative (Dex mod + bonuses); override
- [ ] [core] AC with breakdown popover (base, Dex, shield, magic, misc) (section 3)
- [ ] [core] Speed (walking), plus fly/swim/climb/burrow when granted (S8)
- [ ] [full] Custom speeds and choose displayed movement mode (S8)
- [ ] [core] HP panel: current / max / temp; damage and heal input (temp HP absorbs first); max shows modified value
- [ ] [core] Death saves at 0 HP: 3 success / 3 fail pips, stabilized flag, reset on heal
- [ ] [full] Max HP modifiers: bonus HP, override max (S13 `bonusHitPoints`, `overrideHitPoints`)
- [ ] [full] Hit dice remaining per die size
- [ ] [core] Conditions toggles (blinded ... unconscious, 14 + exhaustion 1-6 with 2014 effects table)
- [ ] [full] Condition effects applied to computed values where mechanical (exhaustion 2 halves speed, 4 halves max HP, 5 speed 0; grappled/restrained speed 0)
- [ ] [core] Defenses: resistances, immunities, vulnerabilities, condition immunities from all sources
- [ ] [full] "Manage Defenses": custom defenses with notes, marked with asterisk (S10)

### 2.7 Actions tab
- [ ] [core] Attacks table: name, range, to-hit, damage + type, notes (properties); equipped weapons + attack cantrips/spells
- [ ] [core] Sections: Actions, Bonus Actions, Reactions, Other (e.g. Sneak Attack), with the standard combat actions list (Attack, Dash, Disengage, Dodge, Help, Hide, Ready, Search, Use an Object, Opportunity Attack, Grapple, Shove, Two-Weapon Fighting)
- [ ] [core] Limited-use trackers (checkbox pips) inline with features (Rage, Second Wind, Action Surge, Channel Divinity, Bardic Inspiration, Ki, Sorcery Points)
- [ ] [full] Limited Use aggregate view with SR/LR/Dawn grouping (S2)
- [ ] [full] Extra Attack count shown; off-hand attack damage without mod; unarmed strike (pref)
- [ ] [full] Customize per action: name, to-hit override/bonus, damage bonus, DC override/bonus, display as attack, silvered/adamantine, notes (S14 typeIds)
- [ ] [full] Custom actions (S13 `customActions`)
- [ ] [core] Filters: All / Attack / Action / Bonus / Reaction / Other / Limited Use

### 2.8 Spells tab
- [ ] [core] Spellcasting ability, modifier, spell attack bonus, save DC (per class if multiclass)
- [ ] [core] Slots per level with used pips; pact slots separate (short-rest reset)
- [ ] [core] Spells grouped by level (cantrips, 1-9); prepared/known only by default
- [ ] [core] Concentration (C) and ritual (R) markers; casting time, range, hit/DC, effect column
- [ ] [full] Filters by level, by action type, concentration, ritual; search
- [ ] [full] Show upcast options (scaled spells pref)
- [ ] [full] Non-slot spells (racial/feat/item) with their uses
- [ ] [full] Cantrip damage scaling by total character level (5/11/17)
- [ ] [full] Per-spell customize: DC override, name, notes, display as attack
- [ ] [skip] Spell components/material cost tracking

### 2.9 Inventory tab
- [ ] [core] Equipment list: name, weight, quantity, cost, equipped toggle, notes
- [ ] [core] Attunement: 3 slots (Artificer 4/5/6 at 10/14/18), attune toggle, "requires attunement" marker
- [ ] [core] Currency: cp, sp, ep, gp, pp; add/subtract; total gp equivalent
- [ ] [full] Containers: items nest in backpack/bag/chest; container weight multiplier (Bag of Holding contents weigh 0); equipped vs stored container counts toward carried weight (S11, S12)
- [ ] [full] Coins inside containers (pref) (S11)
- [ ] [core] Total weight vs carrying capacity; encumbrance status per chosen rule
- [ ] [full] Item detail popover: full text, properties, charges, attunement text
- [ ] [full] Charges tracking (wands, staffs) with reset type (dawn)
- [ ] [full] Consumables with quantity decrement (potions, ammunition)
- [ ] [full] Item customization: name, cost/weight override, magic bonus, damage bonus, to-hit, notes (S12, S14)
- [ ] [full] Custom items
- [ ] [full] Party inventory shared across campaign characters (S9); useful for a single table
- [ ] [full] Other possessions / holdings free text (S13 `notes.personalPossessions`, `otherHoldings`)

### 2.10 Features & Traits tab
- [ ] [core] Class features (by class, by level, with subclass), racial traits, feats; full text expandable
- [ ] [core] Choices made shown inline (e.g. chosen invocations, metamagic)
- [ ] [full] Filter by source (class/race/feat); "Manage Feats" link (S2)
- [ ] [full] Hide-in-sheet flags for boilerplate features (DDB `hideInSheet`)

### 2.11 Description, Notes, Extras
- [ ] [core] Description: background (name + feature text), characteristics, appearance, alignment, faith, lifestyle, physical traits
- [ ] [core] Notes: organizations, allies, enemies, backstory, other; freeform notes
- [ ] [full] Extras: attach creature stat blocks (S6). Groups from S14: Wildshape, Familiar, Beast Companion, Mount, Pet, Summoned, Misc, Battle Smith Defender, Sidekick, Infusion
- [ ] [full] Extras stat block with per-creature tweaks: AC, max HP, type, alignment, size, notes (S14 typeIds 42-47); auto-updates for Ranger companion (prof bonus) and Wild Shape limits
- [ ] [full] Wild Shape: CR/fly/swim limits by Druid level, Moon druid CR; beast HP pool separate
- [ ] [skip] Pet/mount tracking beyond notes

### 2.12 Cross-cutting UI
- [ ] [core] Popovers/sidebars with full rules text for every feature, spell, item, condition, action
- [ ] [core] Computed-value breakdown on click ("where does +7 come from")
- [ ] [full] Manage/customize overrides on every computed value with notes; customized marker (asterisk) (S10, section 4)
- [ ] [full] Mobile layout: single column, tabbed sections (Abilities/Saves/Senses, Skills, Actions, Inventory, Spells, Features, Description, Notes, Extras; S2 lists these as separate mobile screens)
- [ ] [full] Print / PDF export: fill a classic sheet PDF (DDB uses a form-fillable PDF, S7)
- [ ] [full] Read-only share link (privacy setting); DM can view all campaign sheets
- [ ] [full] Campaign: list of characters, DM view, party inventory
- [ ] [full] Character list page: create, copy, delete, search, sort (S4)
- [ ] [skip] Offline mode (mobile app caches last sheet)
- [ ] [skip] Game log (DDB: dice roll history; for us only meaningful as an HP/resource change log)

---

## 3. Derived-value engine (2014 rules)

Inputs: base scores, race/subrace, classes+levels+subclasses, background, feats, choices, equipped/attuned items, conditions, preferences, overrides.
Mechanism (DDB, S13/S14): collect all active modifiers (item modifiers only if equipped, and attuned when `requiresAttunement`), then evaluate per target. Overrides win last.

- [ ] [core] Total level = sum of class levels
- [ ] [core] Proficiency bonus = 2 + floor((total level - 1) / 4)
- [ ] [core] Ability score = base + racial + ASI + feats + bonus modifiers; `set` modifiers take max(score, set); cap 20 unless raised; then override
- [ ] [core] Ability modifier = floor((score - 10) / 2)
- [ ] [core] Saving throw = mod + (prof if proficient) + bonuses (Cloak/Ring of Protection, Paladin Aura of Protection +Cha min 1)
- [ ] [core] Skill = mod + prof x {0, 0.5 floor (Jack of All Trades), 1, 2 (expertise)} + bonuses; Remarkable Athlete half prof rounded up on Str/Dex/Con checks without proficiency
- [ ] [core] Passive score = 10 + skill total (+5 advantage, -5 disadvantage; Observant +5 Perception/Investigation)
- [ ] [core] Initiative = Dex mod + bonuses (Alert +5, Jack of All Trades, Remarkable Athlete)
- [ ] [core] Max HP = L1: hit die max + Con mod; later levels: (die/2 + 1) or entered roll, + Con mod each; + per-level bonuses (Hill Dwarf +1, Tough +2, Draconic Resilience +1); Con changes apply retroactively; min 1 per level; then bonus, then override
- [ ] [core] Current HP = max - damage taken (DDB stores `removedHitPoints`); temp HP separate, never stacks (take higher)
- [ ] [core] Hit dice pool = one die per class level, by class die size; long rest regains floor(total/2) min 1
- [ ] [core] AC = max over applicable formulas, then + shield + bonuses, then override:
  - Unarmored: 10 + Dex
  - Light armor: base + Dex; Medium: base + min(Dex, 2) (Medium Armor Master: 3); Heavy: base, no Dex
  - Shield +2 (not with Monk Unarmored Defense)
  - Barbarian Unarmored Defense: 10 + Dex + Con (shield ok)
  - Monk Unarmored Defense: 10 + Dex + Wis (no armor, no shield)
  - Draconic Resilience: 13 + Dex; Mage Armor: 13 + Dex (no armor)
  - Natural armor: Lizardfolk 13 + Dex, Loxodon 12 + Con, Tortle 17 flat (no Dex), shield allowed
  - Warforged Integrated Protection +1; Defense fighting style +1 while armored; Dual Wielder +1 when wielding two weapons
  - Bladesinging + Int (no medium/heavy armor, no shield); Barkskin minimum 16 (`minimum-base-armor`)
  - Magic armor/shield +N, Ring/Cloak of Protection +1, Bracers of Defense +2 (no armor, no shield), Robe of the Archmagi base 15 + Dex
  - DDB vocabulary (S14): `set unarmored-armor-class (statId)`, `minimum-base-armor`, `ac-max-dex-modifier`, `ignore unarmored-dex-ac-bonus`, `bonus armor-class / armored-armor-class / unarmored-armor-class`
- [ ] [core] Speed = race base + bonuses (Monk Unarmored Movement +10..+30 no armor/shield, Barbarian Fast Movement +10 no heavy armor, Mobile +10, Longstrider) - heavy armor Str requirement penalty -10 (Dwarf exempt) - encumbrance penalty; conditions may zero it
- [ ] [full] Other speeds: granted fly/swim/climb/burrow, or "equal to walking speed"
- [ ] [core] Weapon attack bonus = ability mod + prof (if proficient) + magic bonus + Archery (+2 ranged) + other bonuses
  - ability: Str melee, Dex ranged, finesse = higher of Str/Dex, thrown uses Str unless finesse, monk weapon/unarmed may use Dex, Hex Warrior = Cha (pact weapon / hexblade weapon), Battle Smith = Int (magic weapons), Shillelagh = spell mod
- [ ] [core] Weapon damage = die (versatile two-handed die, Martial Arts die if higher for monk weapons) + ability mod (off-hand: no positive mod unless Two-Weapon Fighting style) + magic bonus + Dueling +2 + Rage bonus (Str melee) + other
- [ ] [core] Spell save DC = 8 + prof + spellcasting mod (+ item bonuses); spell attack = prof + mod (+ item bonuses, e.g. Rod of the Pact Keeper, Wand of the War Mage attack only)
- [ ] [core] Spell slots: single class table; multiclass combined caster level (1.3); pact slots by Warlock level (count + slot level)
- [ ] [core] Cantrips known, spells known, prepared max from class tables / formulas (1.9)
- [ ] [core] Cantrip damage dice by total character level
- [ ] [core] Carrying capacity = Str x 15 lb; push/drag/lift = Str x 30; size multiplier (Large x2, Tiny x0.5; Powerful Build counts one size larger)
- [ ] [full] Variant encumbrance: > Str x 5 encumbered (-10 ft), > Str x 10 heavily encumbered (-20 ft, disadvantage on Str/Dex/Con checks, attacks, saves)
- [ ] [full] Carried weight = sum(item weight x qty) with container multipliers + coins at 50 per lb (unless ignored)
- [ ] [core] Limited-use max = fixed, or ability mod (min 1), or proficiency bonus, or level-scaled table (Rage count, Ki = monk level, Sorcery Points = sorcerer level, Superiority Dice, Channel Divinity, Wild Shape 2/SR); reset type SR/LR/Dawn/charges
- [ ] [core] Class scaling values shown in feature text: Sneak Attack dice, Martial Arts die, Rage damage, Bardic Inspiration die, Brutal Critical dice, Unarmored Movement, Superiority die size
- [ ] [full] Attunement slot count (3, Artificer more)
- [ ] [full] Exhaustion effects (2014 six-level table) applied to speed, max HP, checks
- [ ] [full] Language and proficiency aggregation with dedupe and source attribution
- [ ] [full] Resistances/immunities aggregation (race, class e.g. Rage B/P/S while raging, items, conditions)
- [ ] [full] Conditional bonuses as toggles (Rage active, Bladesong active, Mage Armor active): DDB lacked toggles in 2017 (S10); worth having as "active effects" switches
- [ ] [full] Lifestyle cost lookup; XP thresholds table (300, 900, 2700, ...)

---

## 4. Override catalog (DDB `characterValues.typeId`, from S14)

Pattern: `{typeId, value, valueId (target entity), valueTypeId, notes}`. Mapping from importer code, partial:

- 1 AC override (whole value); 2 / 3 AC magic bonus / misc bonus; base armor override exists per S10
- 8 custom name (action/spell/item)
- 10 damage bonus; 12 to-hit bonus; 13 to-hit override; 14 DC bonus; 15 DC override
- 16 display as attack; 18 dual wielding flag (Dual Wielder AC)
- 19 cost override; 22 weight override; 20 silvered; 21 adamantine
- 24 / 25 skill misc/magic bonus; 26 skill override; 27 skill proficiency-level override (exact split unverified)
- 39 / 40 ability bonus fields; 41 ability override
- 42-47 creature (extra) tweaks: AC, max HP, type, alignment, size, notes
- Plus dedicated fields: `overrideStats`, `bonusStats`, `overrideHitPoints`, `bonusHitPoints`, `customSenses`, `customSpeeds`, `customDefenseAdjustments`, `customProficiencies`, `customActions`

For us: [full] one generic override table keyed by (target, field) with value + note, rendered with an asterisk; enough to cover all of the above.

---

## 5. Excluded: 2024-only (skip)

- Weapon mastery properties (Cleave, Graze, Nick, Push, Sap, Slow, Topple, Vex) and mastery slots
- Backgrounds granting ASIs (+2/+1 or +1/+1/+1) and an Origin feat; "Background ASI" sheet block
- Species without ASIs; 2024 species lineages (Elven Lineage, Fiendish Legacy), size choice per species
- Origin feats category; Epic Boon feats at L19; fighting styles as feats
- 2024 classes/subclasses: all subclasses at L3, Wild Shape known forms + temp HP, invocations absorbing pact boons, 2024 spell lists and spell changes, "prepared" model for all casters
- Long rest regains all hit dice (2024); 2024 exhaustion (-2 per level to d20 tests, -5 ft speed)
- Heroic Inspiration naming and Human "Resourceful" inspiration on long rest
- 2024 unarmed strike options (damage/grapple/shove) and grapple/shove save DC rules
- New 2024 action names (Study, Influence, Magic, Utilize)
- 2024 starting equipment "option A/B or 50 gp" format; 2024 crafting and Bastions
- 2024 core sources (PHB 2024, DMG 2024, MM 2024) in source toggles

Kept although newer than the PHB: Tasha's optional class features and Customizing Your Origin, Xanathar's options, MotM-style races (all 2014-ruleset).

---

## 6. Excluded by design

- Digital dice roller, dice sets, rollable hit dice / attacks / damage, shared dice
- Game log of rolls (DDB's log is dice history)
- Maps VTT, "Launch game", tokens, combat encounters on maps
- Marketplace, content unlocking, content sharing by purchase, Drops, character slots, subscriptions
- Partnered content toggles
- Mobile app offline cache (web layout only)

---

## 7. Open risks

- Content licensing: only SRD 5.1 (CC-BY-4.0) is free to embed: one subclass per class, one background (Acolyte), one subrace per race, one feat (Grappler). Every other subclass, race, feat, spell and item text from PHB/XGtE/TCoE is WotC copyright. The full list above assumes either SRD-only data or user-entered/private data for a closed home table.
- DDB art and SVG sheet assets (frames, ability boxes, icons, backdrops) are WotC/DDB copyright; usable for a private table at most, not for a public page.
- Enum numbering for `encumbranceType`, `privacyType`, `longRestType`, `sharingType` and the skill override split is inferred, not documented.
- S1/S2 are flagged by DDB as not updated after the 2024 builder rework.
