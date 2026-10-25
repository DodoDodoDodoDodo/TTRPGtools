<script>
  // Class step in DDB's markup: level summary, HP box, one class-manager per class with Class
  // Features / Spells tabs, every feature as a paper <details> with its picks as DDB dropdowns.
  import Entries from "../lib/Entries.svelte";
  import DdbSelect from "./DdbSelect.svelte";
  import SpellsStep from "./SpellsStep.svelte";
  import FeatChoices from "./FeatChoices.svelte";
  import CardChooser from "./CardChooser.svelte";
  import ClassDetail from "./ClassDetail.svelte";
  import { design } from "../lib/design.svelte.js";
  import { content, sourceAllowed } from "../lib/content.svelte.js";
  import { featOption, multiclassBlock } from "../lib/prereq.js";
  import { featOpen } from "../lib/openpicks.js";
  import { current, changed } from "../lib/character.svelte.js";
  import { ddb } from "../lib/ddb.svelte.js";
  import { show } from "../lib/pane.svelte.js";
  import { ABILITIES, ABILITY_NAMES, SKILLS, book, title } from "../lib/format.js";

  const EXPERTISE = { Rogue: { 1: 2, 6: 2 }, Bard: { 3: 2, 10: 2 } };
  const ORDINAL = (n) => `${n}${["th", "st", "nd", "rd"][n % 10 > 3 || [11, 12, 13].includes(n % 100) ? 0 : n % 10]} level`;

  const entries = $derived(current.character.classes);
  const total = $derived(entries.reduce((n, e) => n + (Number(e.level) || 1), 0));
  const rolled = $derived(current.character.description?.hp_mode === "rolled");
  let tabs = $state({});
  let showHp = $state(false);

  const cls = (entry) => content.byId.classes[entry.id];
  const subOf = (entry) => (entry.subclass ? content.byId.subclasses[entry.subclass] : null);
  const subclassLevel = (c) => c.features.find((f) => f.gainSubclassFeature)?.level ?? 3;

  function addClass(id) {
    if (!id || total >= 20) return;
    current.character.classes.push({ id, level: 1, skills: [], expertise: [], asi: {}, optionalfeatures: [], spells: { cantrips: [], known: [], prepared: [] } });
    changed();
  }
  function removeClass(i) {
    if (!confirm(`Remove ${cls(entries[i]).name} and every pick made for it?`)) return;
    current.character.classes.splice(i, 1);
    changed();
  }
  function setLevel(entry, value) {
    const others = total - (Number(entry.level) || 1);
    entry.level = Math.max(1, Math.min(20 - others, Number(value) || 1));
    changed();
  }
  // One dropdown per pick: options exclude what the other dropdowns of the same group already hold.
  function setPick(list, k, value) {
    const next = [...list];
    if (value) next[k] = value;
    else next.splice(k, 1);
    return next.filter(Boolean);
  }
  const optionsFor = (all, chosen, mine) => all.filter((o) => o.value === mine || !chosen.includes(o.value));

  function skillBlock(i, c) {
    const profs = i === 0 ? c.startingProficiencies : c.multiclassing?.proficienciesGained;
    const block = profs?.skills?.[0];
    if (!block) return null;
    if (block.any) return { count: block.any, from: Object.keys(SKILLS) };
    if (block.choose) return { count: block.choose.count || 1, from: block.choose.from };
    return null;
  }
  // PHB wording, as DDB prints it: "Light armor, medium armor, shields", "Tools: None", "Choose two skills from ..."
  const NUMBER_WORDS = ["zero", "one", "two", "three", "four", "five", "six"];
  const KIND_SUFFIX = { armor: " armor", weapons: " weapons" };
  function proficiencyText(i, c) {
    const profs = (i === 0 ? c.startingProficiencies : c.multiclassing?.proficienciesGained) || {};
    const plain = (list, kind) => (list || [])
      .map((x) => (typeof x === "string" ? x.replace(/\{@\w+ ([^|}]+)[^}]*\}/g, "$1") : x.proficiency || ""))
      .filter(Boolean)
      .map((x) => (/^(light|medium|heavy|simple|martial)$/.test(x) ? x + KIND_SUFFIX[kind] : x));
    const sentence = (parts) => parts.map((x, k) => (k === 0 ? x[0].toUpperCase() + x.slice(1) : x)).join(", ") || "None";
    const andList = (parts) => (parts.length > 1 ? `${parts.slice(0, -1).join(", ")}, and ${parts[parts.length - 1]}` : parts[0] || "");
    const lines = [["Armor", sentence(plain(profs.armor, "armor"))], ["Weapons", sentence(plain(profs.weapons, "weapons"))], ["Tools", sentence(plain(profs.tools))]];
    if (i === 0) lines.push(["Saving Throws", (c.proficiency || []).map((a) => ABILITY_NAMES[a]).join(", ")]);
    const b = skillBlock(i, c);
    if (b) lines.push(["Skills", b.from.length >= 18 ? `Choose any ${NUMBER_WORDS[b.count] || b.count}` : `Choose ${NUMBER_WORDS[b.count] || b.count} skills from ${andList(b.from.map(title))}`]);
    return lines;
  }

  function progressions(c, sub) {
    return [...(c.optionalfeatureProgression || []), ...(sub?.optionalfeatureProgression || [])];
  }
  function progressionCount(p, level) {
    if (Array.isArray(p.progression)) return p.progression[level - 1] || 0;
    return Math.max(0, ...Object.entries(p.progression).filter(([k]) => Number(k) <= level).map(([, v]) => v));
  }
  // invocation prerequisites (level, pact boon, Eldritch Blast) follow the same "Use Prerequisites" switch as feats
  const optionList = (p, chosen = null) => content.optionalfeatures
    .filter((o) => (o.featureType || []).some((t) => p.featureType.includes(t)))
    .map((o) => featOption(o, prereqContext, { enforce: enforceFeats, chosen }));
  const chosenOf = (entry, p) => (entry.optionalfeatures || []).filter((id) => (content.byId.optionalfeatures[id]?.featureType || []).some((t) => p.featureType.includes(t)));
  function setOption(entry, p, k, value) {
    const mine = chosenOf(entry, p);
    const keep = (entry.optionalfeatures || []).filter((id) => !mine.includes(id));
    entry.optionalfeatures = [...keep, ...setPick(mine, k, value)];
    changed();
  }
  // A progression's picks live in the feature that introduces it ("Fighting Style", "Eldritch Invocations"...).
  const PROGRESSION_FEATURE = { Maneuvers: "Combat Superiority", Infusions: "Infuse Item", Runes: "Rune Carver", "Arcane Shots": "Arcane Archer Lore", "Elemental Disciplines": "Disciple of the Elements" };
  function progressionsAt(c, sub, f) {
    return progressions(c, sub).filter((p) => {
      const home = PROGRESSION_FEATURE[p.name] || p.name;
      return f.name === home || f.name.startsWith(home) || home.startsWith(f.name);
    });
  }

  function asiPick(entry, level) {
    return (entry.asi || {})[String(level)] || null;
  }
  function setAsiMode(entry, level, mode) {
    entry.asi = { ...(entry.asi || {}) };
    entry.asi[String(level)] = mode === "feat" ? { feat: { id: "" } } : mode === "two" ? { abilities: {}, mode: "two" } : mode === "one" ? { abilities: {}, mode: "one" } : undefined;
    if (!mode) delete entry.asi[String(level)];
    changed();
  }
  function setAsiAbility(entry, level, slot, ability) {
    const pick = entry.asi[String(level)];
    const chosen = Object.keys(pick.abilities || {});
    if (pick.mode === "one") pick.abilities = ability ? { [ability]: 2 } : {};
    else {
      chosen[slot] = ability;
      pick.abilities = Object.fromEntries(chosen.filter(Boolean).map((a) => [a, 1]));
    }
    changed();
  }
  // Home step "Use Prerequisites": both on unless switched off
  const enforceFeats = $derived(current.character.preferences?.feat_prerequisites !== false);
  const enforceMulticlass = $derived(current.character.preferences?.multiclass_prerequisites !== false);
  const prereqContext = $derived({ sheet: current.sheet, character: current.character, level: total });
  // New-design class cards: DDB's class illustration, hit die and saves as the line, multiclass blocks shown
  const classCards = $derived(content.classes
    .filter((c) => !entries.some((e) => e.id === c.id) && sourceAllowed(c.book, current.character.preferences))
    .map((c) => {
      const blocked = enforceMulticlass ? multiclassBlock(c, entries, content.byId.classes, current.sheet) : "";
      return { name: c.name, items: [{ id: c.id, name: c.name, book: c.book }], book: c.book, art: c.ddbCard,
        blurb: `Hit Die d${c.hd.faces} · Saves ${c.proficiency.map((a) => ABILITY_NAMES[a]).join(", ")}`,
        blocked: blocked ? `Cannot multiclass: ${blocked} (PHB p. 163)` : "" };
    }));
  const featOptions = (chosen) => content.feats.filter((f) => sourceAllowed(f.book, current.character.preferences) || f.id === chosen)
    .map((f) => featOption(f, prereqContext, { enforce: enforceFeats, chosen, group: ruleGroup(f.book) }));
  const abilityOptions = ABILITIES.map((a) => ({ value: a, label: ABILITY_NAMES[a] }));

  // PHB text order where 5etools lists a level's features differently (DDB follows the book: PHB p. 107).
  const FIRST_AT_LEVEL = { warlock: ["Otherworldly Patron"] };
  // Features shown in DDB's order: Hit Points, Proficiencies, then class and subclass features by level.
  // DDB splits the subclass introduction ("The Fiend") into its named parts, one card each.
  // Optional (Tasha's) class features show only with the Home step's "Optional Class Features" preference,
  // or once one is in use; "Otherworldly Patron feature" placeholders give way to the chosen subclass's features.
  function features(i, c, sub, level, entry) {
    const optional = current.character.preferences?.optional_class_features;
    const list = c.features.filter((f) => f.level <= level)
      .filter((f) => !f.variant || optional || (entry.variant_features || []).includes(f.name))
      .filter((f) => !(sub && f.gainSubclassFeature && f.level !== subclassLevel(c)))
      .map((f) => ({ ...f, origin: c.name }));
    for (const f of sub?.features.filter((f) => f.level <= level) || []) {
      const intro = f.name === sub.name || f.name === sub.shortName;
      const parts = intro ? f.entries.filter((e) => e?.type === "entries" && e.name) : [];
      if (parts.length) list.push(...parts.map((e) => ({ name: e.name, entries: e.entries, level: f.level, origin: sub.name, isSub: true })));
      else list.push({ ...f, origin: sub.name, isSub: true });
    }
    const first = (f) => ((FIRST_AT_LEVEL[c.id] || []).includes(f.name) ? 0 : 1);
    return list.sort((a, b) => a.level - b.level || (a.isSub ? 1 : 0) - (b.isSub ? 1 : 0) || first(a) - first(b));
  }
  // DDB clips long descriptions to 92px behind "Show More"; a text-length cut stands in for its measurement.
  const isLong = (entries) => JSON.stringify(entries || []).length > 500;
  let expanded = $state({});
  const pretty = (name) => name.replace(/'/g, "\u2019");
  let choosing = $state(false);
  // the newer builder's class page, opened from a card's Learn More
  let detailId = $state(null);
  const ruleGroup = (bookId) => (bookId === "phb" ? "5e Core Rules" : "5e Expanded Rules");
  function choiceCount(i, entry, c, sub, f, level) {
    let n = 0;
    if (f.gainSubclassFeature && f.level === subclassLevel(c)) n += 1;
    if (f.name === "Ability Score Improvement") n += 1;
    for (const p of progressionsAt(c, sub, f)) n += progressionCount(p, level);
    const pick = (current.sheet?.feature_picks || []).find((fp) => fp.class === entry.id && fp.feature === f.name);
    if (pick) n += pick.count;
    if (f.name === "Expertise" && EXPERTISE[c.name]?.[f.level]) n += EXPERTISE[c.name][f.level];
    return n;
  }
  // Picks still unmade in a feature: DDB marks such cards (red edge) and their empty dropdowns.
  function openChoices(entry, c, sub, f) {
    const level = Number(entry.level) || 1;
    let open = 0;
    if (f.gainSubclassFeature && f.level === subclassLevel(c) && !entry.subclass) open += 1;
    if (f.name === "Ability Score Improvement") {
      const pick = asiPick(entry, f.level);
      if (!pick || (pick.feat ? !pick.feat.id : !Object.keys(pick.abilities || {}).length)) open += 1;
      else if (pick.feat?.id) open += featOpen(content.byId.feats[pick.feat.id], pick.feat, total);
    }
    for (const p of progressionsAt(c, sub, f)) open += Math.max(0, progressionCount(p, level) - chosenOf(entry, p).length);
    const fp = featurePick(entry, f);
    if (fp) open += Math.max(0, fp.count - fp.chosen.length);
    if (f.name === "Expertise" && EXPERTISE[c.name]?.[f.level]) {
      const upTo = Object.entries(EXPERTISE[c.name]).filter(([lv]) => Number(lv) <= f.level).reduce((m, [, v]) => m + v, 0);
      open += Math.max(0, upTo - (entry.expertise || []).length);
    }
    return open;
  }
  const featurePick = (entry, f) => (current.sheet?.feature_picks || []).find((fp) => fp.class === entry.id && fp.feature === f.name);
  const proficientSkills = $derived(Object.entries(current.sheet?.skills || {}).filter(([, v]) => v.proficiency === "proficient" || v.proficiency === "expertise").map(([s]) => ({ value: s, label: title(s) })));
  const tabOf = (entry) => tabs[entry.id] || "features";
  const hasSpells = (entry) => (current.sheet?.spellcasting?.casters || []).some((x) => x.class_id === entry.id);
  const hitDice = $derived((current.sheet?.hit_dice || []).map((h) => `${h.total}d${h.die}`).join(" + "));
  const TAB_LABELS = [["features", "Class Features"], ["spells", "Spells"]];
</script>

{#snippet card(name, meta, body, todo = false)}
  <details class="styles_details__Kwqwr styles_paper__FhNqH {todo ? 'styles_alert__tPDGl' : ''}">
    <summary class="styles_summary__BI+UG" data-testid="accordion-summary">
      <div class="styles_heading__RRl69">
        <div class="styles_summaryContent__xaQWq">{name}
          <div class="styles_metaItems__Pt+Po">{#each meta as m}<div class="styles_metaItem__+kjrf">{m}</div>{/each}</div>
        </div>
        <div class="styles_actions__1-sml"></div>{@html ddb.icons["details-chevron"] || "▾"}
      </div>
    </summary>
    <div class="styles_content__pFYp6">{@render body()}</div>
  </details>
{/snippet}

{#snippet choice(placeholder, value, options, onchange)}
  <div class="styles_choice__qE4aQ"><div class="detail-choice {value ? '' : 'detail-choice--todo'}">
    <DdbSelect highlight {placeholder} {value} {options} {onchange} />
  </div></div>
{/snippet}

{#snippet description(key, entries)}
  {#if isLong(entries)}
    <div class="styles_collapsible__R+ovD class-manager-feature-description {expanded[key] ? 'styles_open__THaid' : ''}">
      <div class="ddbc-html-content styles_content__cRybC"><Entries {entries} ddb /></div>
      <button type="button" class="styles_button__AcpmG" onclick={() => (expanded[key] = !expanded[key])}>{expanded[key] ? "Show Less" : "Show More"}</button>
    </div>
  {:else}
    <div class="ddbc-html-content class-manager-feature-description"><Entries {entries} ddb /></div>
  {/if}
{/snippet}

<div class="classes-manage builder-page">
  {#if !entries.length || choosing}
    {#if design.mode === "new"}
      {#if detailId && content.byId.classes[detailId]}
        <ClassDetail cls={content.byId.classes[detailId]} blocked={classCards.find((g) => g.items[0].id === detailId)?.blocked || ""}
          onselect={() => { addClass(detailId); detailId = null; choosing = false; }} onback={() => (detailId = null)} />
      {:else}
        <CardChooser heading={entries.length ? "Choose Another Class" : "Choose a Class"} noun="class" groups={classCards} learn={(id) => (detailId = id)} onpick={(id) => { addClass(id); choosing = false; }} />
      {/if}
    {:else}
    <div class="ddb-class-choose">
      <h2 class="ddb-builder-heading">Choose a Class</h2>
      <div class="ddb-class-choose-list">
        {#each content.classes.filter((c) => !entries.some((e) => e.id === c.id) && sourceAllowed(c.book, current.character.preferences)) as c (c.id)}
          {@const blocked = enforceMulticlass ? multiclassBlock(c, entries, content.byId.classes, current.sheet) : ""}
          <button type="button" class="ddb-class-choose-item" disabled={!!blocked} title={blocked ? `Multiclassing (PHB p. 163): ${blocked}` : ""} onclick={() => { addClass(c.id); choosing = false; }}>
            <span class="ddb-class-choose-name">{c.name}</span>
            <span class="ddb-class-choose-meta">Hit die d{c.hd.faces} · saves {c.proficiency.map((a) => a.toUpperCase()).join(", ")} · {book(c.book)}</span>
            {#if blocked}<span class="ddb-class-choose-blocked">Cannot multiclass: {blocked} (PHB p. 163)</span>{/if}
          </button>
        {/each}
      </div>
    </div>
    {/if}
  {:else}
    <div class="classes-manage-primary">
      <div class="classes-manage-primary-section classes-manage-primary-section-progression">
        <div class="progression-manager">
          <div class="progression-manager-info"><div class="progression-manager-heading">Character Level: {total}</div></div>
          <div class="progression-manager-meta">{current.character.preferences?.advancement === "xp" ? `XP Advancement: ${(Number(current.character.xp) || 0).toLocaleString("en")} XP` : "Milestone Advancement"}</div>
        </div>
      </div>
      <div>
        <div class="styles_hpSummaryContent__Im4dO">
          <div>
            <p><span class="styles_label__Jrq2J">Max Hit Points:</span><span>{current.sheet?.hp?.max ?? "--"}</span></p>
            <p><span class="styles_label__Jrq2J">Hit Dice:</span><span>{hitDice || "--"}</span></p>
          </div>
          <button type="button" class="Button_button__B9Kr5 ButtonVariants_primary__TMQ5y ButtonSizes_x-small__AQ7c6 styles_x-small__8tmZN styles_builder__iFp8R styles_button__e1Ctk" onclick={() => (showHp = !showHp)}>Manage HP</button>
        </div>
      </div>
    </div>

    {#if showHp}
      <div class="ddb-hp-manager">
        <label class="ddb-inline">Hit point type
          <DdbSelect value={current.character.description?.hp_mode || "average"} placeholder=""
            options={[{ value: "average", label: "Fixed (average)" }, { value: "rolled", label: "Manual (rolled)" }]}
            onchange={(v) => { current.character.description = { ...(current.character.description || {}), hp_mode: v }; changed(); }} />
        </label>
        {#if rolled}
          {#each entries as entry, i (entry.id)}
            {@const c = cls(entry)}
            <div class="ddb-rolls"><strong>{c.name} (d{c.hd.faces})</strong>
              {#each Array.from({ length: (Number(entry.level) || 1) - (i === 0 ? 1 : 0) }, (_, k) => k) as k}
                <label>Level {k + (i === 0 ? 2 : 1)} <input type="number" min="1" max={c.hd.faces} value={entry.hp_rolls?.[k] || ""}
                  oninput={(e) => { entry.hp_rolls ??= []; entry.hp_rolls[k] = Number(e.target.value) || null; changed(); }} /></label>
              {/each}
            </div>
          {/each}
        {/if}
      </div>
    {/if}

    {#each entries as entry, i (entry.id)}
      {@const c = cls(entry)}
      {@const sub = subOf(entry)}
      {@const level = Number(entry.level) || 1}
      {#if c}
        <div class="class-manager">
          <div class="styles_container__g8gPn">
            {#if c.ddbArt}<img class="styles_classImg__2QAJc" alt="{c.name} Class avatar" src="{window.DND5E.ddb}/{c.ddbArt}" />{/if}
            <div class="styles_nameGroup__u87N1">
              {#if sub}<div class="styles_subclassName__JQinv">{sub.name}</div>{/if}
              <div class="styles_name__KLcTZ">{c.name}</div>
            </div>
            <div class="styles_container__g8gPn">
              <div class="styles_levelManager__-7mXa">
                <label class="styles_levelLabel__kONXJ" for="class-level-{entry.id}">Level</label>
                <DdbSelect extraClass="styles_levelSelect__3Agsd" width="75px" placeholder="" searchable={false} value={level}
                  options={Array.from({ length: 20 }, (_, k) => ({ value: k + 1, label: String(k + 1), disabled: k + 1 - level + total > 20 }))}
                  onchange={(v) => setLevel(entry, v)} />
              </div>
              <button type="button" class="Button_button__B9Kr5 ButtonVariants_primary__TMQ5y ButtonVariants_text__vKMzd ButtonSizes_x-small__AQ7c6 styles_x-small__8tmZN styles_light__kA91w styles_text__BLc8n styles_removeClassButton__PGgIP" aria-label="Remove {c.name}" onclick={() => removeClass(i)}>{@html ddb.icons["remove-x"] || "✕"}</button>
            </div>
          </div>

          <div class="styles_tabList__fix2X styles_tabList__nY1Jq" style="--tab-count: {hasSpells(entry) ? 2 : 1}; --tab-active-position: {tabOf(entry) === 'spells' ? 1 : 0};">
            <menu class="styles_tabs__aTttL">
              {#each TAB_LABELS.filter(([k]) => k === "features" || hasSpells(entry)) as [k, label]}
                <li><button type="button" class="styles_tabButton__wvSLf" role="radio" aria-checked={tabOf(entry) === k} onclick={() => (tabs[entry.id] = k)}>{label} {@html ddb.icons["select-chevron"] || ""}</button></li>
              {/each}
            </menu>
            <div>
              {#if tabOf(entry) === "spells"}
                <SpellsStep only={entry.id} />
              {:else}
                <div class="class-manager-features class-manager-features-opened"><div class="class-manager-features-groups"><div class="class-manager-features-group"><div class="class-manager-features-group-items">

                  {#snippet hitPoints()}
                    <div class="ddbc-html-content class-manager-feature-description">
                      <p><strong><span class="Serif-Character-Style_Bold-Serif">Hit Dice:</span></strong> 1d{c.hd.faces} per {c.name.toLowerCase()} level<br />{#if i === 0}<strong><span class="Serif-Character-Style_Bold-Serif">Hit Points at 1st Level:</span></strong> {c.hd.faces} + your Constitution modifier<br />{/if}<strong><span class="Serif-Character-Style_Bold-Serif">Hit Points at Higher Levels:</span></strong> 1d{c.hd.faces} (or {c.hd.faces / 2 + 1}) + your Constitution modifier per {c.name.toLowerCase()} level{i === 0 ? " after 1st" : ""}</p>
                    </div>
                  {/snippet}
                  {@render card("Hit Points", [ORDINAL(1)], hitPoints)}

                  {#snippet proficiencies()}
                    {@const block = skillBlock(i, c)}
                    {@const key = `${entry.id}:proficiencies`}
                    <div class="styles_collapsible__R+ovD class-manager-feature-description {expanded[key] ? 'styles_open__THaid' : ''}">
                      <div class="ddbc-html-content styles_content__cRybC">
                        <p>{#each proficiencyText(i, c) as [label, text], k}{#if k}<br />{/if}<strong><span class="Serif-Character-Style_Bold-Serif">{label}:</span></strong> {text}{/each}</p>
                      </div>
                      <button type="button" class="styles_button__AcpmG" onclick={() => (expanded[key] = !expanded[key])}>{expanded[key] ? "Show Less" : "Show More"}</button>
                    </div>
                    {#if block}
                      <div class="">
                        {#each Array.from({ length: block.count }, (_, k) => k) as k}
                          {@render choice(`- Choose a ${c.name} Skill -`, (entry.skills || [])[k] || "",
                            optionsFor(block.from.map((s) => ({ value: s, label: title(s) })), entry.skills || [], (entry.skills || [])[k]),
                            (v) => { entry.skills = setPick(entry.skills || [], k, v); changed(); })}
                        {/each}
                      </div>
                    {/if}
                  {/snippet}
                  {@render card("Proficiencies", [...(skillBlock(i, c) ? [`${skillBlock(i, c).count} Choices`] : []), ORDINAL(1)], proficiencies,
                    (entry.skills || []).length < (skillBlock(i, c)?.count || 0))}

                  {#each features(i, c, sub, level, entry) as f, k (f.origin + f.name + f.level + k)}
                    {#if !(f.variant && false)}
                      {@const n = choiceCount(i, entry, c, sub, f, level)}
                      {#snippet body()}
                        {#if f.variant}
                          <label class="ddb-optional-toggle"><input type="checkbox" checked={(entry.variant_features || []).includes(f.name)}
                            onchange={(e) => { const list = (entry.variant_features || []).filter((x) => x !== f.name); entry.variant_features = e.target.checked ? [...list, f.name] : list; changed(); }} />
                            Use this optional class feature (Tasha's Cauldron of Everything)</label>
                        {/if}
                        {@render description(`${entry.id}:${f.origin}:${f.name}:${f.level}`, f.entries)}
                        {#if n}
                          <div class="">
                            {#if f.gainSubclassFeature && f.level === subclassLevel(c)}
                              {@render choice(`- Choose a ${c.subclassTitle || "Subclass"} -`, entry.subclass || "",
                                c.subclasses.filter((s) => sourceAllowed(s.book, current.character.preferences) || s.id === entry.subclass).map((s) => ({ value: s.id, label: s.name, group: ruleGroup(s.book) })),
                                (v) => { entry.subclass = v || null; changed(); })}
                            {/if}
                            {#if f.name === "Ability Score Improvement"}
                              {@const pick = asiPick(entry, f.level)}
                              {@render choice("- Choose an Option -", pick?.feat ? "feat" : pick?.mode || (pick ? (Object.keys(pick.abilities || {}).length === 2 ? "two" : "one") : ""),
                                [{ value: "one", label: "+2 to one ability score" }, { value: "two", label: "+1 to two ability scores" }, { value: "feat", label: "Choose a feat" }],
                                (v) => setAsiMode(entry, f.level, v))}
                              {#if pick && !pick.feat}
                                {#each (pick.mode === "two" || Object.keys(pick.abilities || {}).length === 2 ? [0, 1] : [0]) as slot}
                                  {@render choice("- Choose an Ability Score -", Object.keys(pick.abilities || {})[slot] || "", abilityOptions, (v) => setAsiAbility(entry, f.level, slot, v))}
                                {/each}
                              {:else if pick?.feat}
                                {@render choice("- Choose a Feat -", pick.feat.id, featOptions(pick.feat.id), (v) => { pick.feat = { id: v }; changed(); })}
                                {#if pick.feat.id}<button type="button" class="ddb-link-button" onclick={() => show("feat", pick.feat.id)}>Read the feat</button>{/if}
                                {#if pick.feat.id}<FeatChoices pick={pick.feat} />{/if}
                              {/if}
                            {/if}
                            {#each progressionsAt(c, sub, f) as p}
                              {@const count = progressionCount(p, level)}
                              {@const mine = chosenOf(entry, p)}
                              {#each Array.from({ length: count }, (_, s) => s) as s}
                                {@render choice(`- Choose ${/^[AEIOU]/.test(p.name) ? "an" : "a"} ${p.name.replace(/s$/, "")} -`, mine[s] || "",
                                  optionsFor(optionList(p, mine[s]), mine, mine[s]), (v) => setOption(entry, p, s, v))}
                              {/each}
                              {#if mine.length}<p class="ddb-chosen-links">{#each mine as id, s}{#if s}, {/if}<button type="button" class="ddb-link-button" onclick={() => show("optionalfeature", id)}>{content.byId.optionalfeatures[id]?.name}</button>{/each}</p>{/if}
                            {/each}
                            {#if featurePick(entry, f)}
                              {@const fp = featurePick(entry, f)}
                              {#each Array.from({ length: fp.count }, (_, s) => s) as s}
                                {@render choice("- Choose an Option -", fp.chosen[s] || "",
                                  optionsFor(fp.options.map((o) => ({ value: o, label: o })), fp.chosen, fp.chosen[s]),
                                  (v) => { entry.feature_choices = { ...(entry.feature_choices || {}), [fp.key]: setPick(fp.chosen, s, v) }; changed(); })}
                              {/each}
                            {/if}
                            {#if f.name === "Expertise" && EXPERTISE[c.name]?.[f.level]}
                              {@const before = Object.entries(EXPERTISE[c.name]).filter(([lv]) => Number(lv) < f.level).reduce((m, [, v]) => m + v, 0)}
                              {#each Array.from({ length: EXPERTISE[c.name][f.level] }, (_, s) => before + s) as s}
                                {@render choice("- Choose a Skill -", (entry.expertise || [])[s] || "",
                                  optionsFor(c.name === "Rogue" && (current.sheet?.proficiencies?.tools || []).some((t) => t.startsWith("thieves' tools")) ? [...proficientSkills, { value: "thieves' tools", label: "Thieves' Tools" }] : proficientSkills, entry.expertise || [], (entry.expertise || [])[s]),
                                  (v) => { const next = [...(entry.expertise || [])]; next[s] = v; entry.expertise = next.filter(Boolean); changed(); })}
                              {/each}
                            {/if}
                          </div>
                        {/if}
                      {/snippet}
                      {@render card(pretty(f.name), [...(n ? [`${n} Choice${n > 1 ? "s" : ""}`] : []), ...(f.variant ? ["Optional"] : []), ORDINAL(f.level)], body, n > 0 && openChoices(entry, c, sub, f) > 0)}
                    {/if}
                  {/each}
                </div></div>
                  {#each [features(i, c, sub, 20, entry).filter((f) => f.level > level)] as later}{#if later.length}
                    <div class="class-manager-features-group {tabs[entry.id + ':later'] ? '' : 'class-manager-features-group-collapsed'}">
                      <div class="class-manager-features-group-header" role="button" tabindex="0"
                        onclick={() => (tabs[entry.id + ':later'] = !tabs[entry.id + ':later'])} onkeydown={(e) => e.key === "Enter" && (tabs[entry.id + ':later'] = !tabs[entry.id + ':later'])}>
                        <div class="class-manager-features-group-heading">Available at Higher Levels ({later.length})</div>
                        <div class="class-manager-features-group-trigger"></div>
                      </div>
                      {#if tabs[entry.id + ':later']}
                        <div class="class-manager-features-group-items">
                          {#each later as f, k (f.origin + f.name + f.level + k)}
                            {#snippet laterBody()}{@render description(`${entry.id}:${f.origin}:${f.name}:${f.level}`, f.entries)}{/snippet}
                            {@render card(pretty(f.name), [ORDINAL(f.level)], laterBody)}
                          {/each}
                        </div>
                      {/if}
                    </div>
                  {/if}{/each}
                </div></div>
              {/if}
            </div>
          </div>
        </div>
      {/if}
    {/each}

    {#if total < 20}
      <div class="classes-manage-actions">
        <div class="classes-manage-actions-action" role="button" tabindex="0" onclick={() => (choosing = !choosing)} onkeydown={(e) => e.key === "Enter" && (choosing = !choosing)}>+ Add Another Class</div>
      </div>
    {/if}
  {/if}
</div>
