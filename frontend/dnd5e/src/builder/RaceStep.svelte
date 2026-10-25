<script>
  // Race step in DDB's markup (manage-race race-detail): picture, "Change Race", description and trait
  // summary, then one paper card per racial trait. Each pick sits in the trait it belongs to: ability
  // increases, languages, draconic ancestry, the Variant Human feat, racial spells.
  import Entries from "../lib/Entries.svelte";
  import DdbSelect from "./DdbSelect.svelte";
  import RaceChooser from "./RaceChooser.svelte";
  import FeatChoices from "./FeatChoices.svelte";
  import GrantedSpells from "./GrantedSpells.svelte";
  import { content, sourceAllowed } from "../lib/content.svelte.js";
  import { featOption } from "../lib/prereq.js";
  import { featOpen, spellsOpen } from "../lib/openpicks.js";
  import { current, changed } from "../lib/character.svelte.js";
  import { ddb } from "../lib/ddb.svelte.js";
  import { show } from "../lib/pane.svelte.js";
  import { ABILITIES, ABILITY_NAMES, SKILLS, title, plain, raceName } from "../lib/format.js";
  import { abilitySentence, originBlocks } from "../lib/race.js";

  const DRAGONS = { Black: "acid", Blue: "lightning", Brass: "fire", Bronze: "lightning", Copper: "acid", Gold: "fire", Green: "poison", Red: "fire", Silver: "cold", White: "cold" };
  // traits DDB leaves out of its "Racial Traits:" summary line
  const NOT_SUMMARIZED = /^(Ability Score Increase|Age|Alignment|Size|Speed|Languages|Creature Type)$/;
  const choice = $derived(current.character.race || {});
  const race = $derived(choice.id ? content.byId.races[choice.id] : null);
  const level = $derived((current.character.classes || []).reduce((n, c) => n + (Number(c.level) || 1), 0));

  function pick(id) {
    current.character.race = { id, ability_block: 0, ability_choices: [], skills: [], languages: [] };
    changed();
  }
  function change() {
    if (!confirm("Choose a different race? The picks made for this one are dropped.")) return;
    current.character.race = {};
    changed();
  }
  function setPick(list, k, value) {
    const next = [...(list || [])];
    if (value) next[k] = value;
    else next.splice(k, 1);
    return next.filter(Boolean);
  }
  const without = (all, chosen, mine) => all.filter((o) => o.value === mine || !(chosen || []).includes(o.value));
  const range = (n) => Array.from({ length: n }, (_, k) => k);

  function abilityText(block) {
    const fixed = Object.entries(block).filter(([k]) => ABILITIES.includes(k)).map(([k, v]) => `+${v} ${ABILITY_NAMES[k]}`);
    const ch = block.choose;
    if (ch?.weighted) fixed.push(`${ch.weighted.weights.map((w) => `+${w}`).join(" and ")} to abilities of your choice`);
    else if (ch) fixed.push(`+${ch.amount || 1} to ${ch.count || 1} ${ch.from?.length === 6 ? "abilities of your choice" : ch.from.map((a) => ABILITY_NAMES[a]).join(" or ")}`);
    return fixed.join(", ") || "No increase";
  }
  const abilityBlocks = $derived(originBlocks(race?.ability, current.character.preferences?.customize_origin));
  const block = $derived(abilityBlocks?.[Math.min(choice.ability_block || 0, (abilityBlocks?.length || 1) - 1)]);
  const chooseCount = $derived(block?.choose ? (block.choose.weighted ? block.choose.weighted.weights.length : block.choose.count || 1) : 0);
  const chooseFrom = $derived(block?.choose ? (block.choose.weighted ? block.choose.weighted.from : block.choose.from) || ABILITIES : []);

  function profBlock(key) {
    const b = race?.[key]?.[0];
    if (!b) return null;
    let count = 0, from = null;
    for (const [k, v] of Object.entries(b)) {
      if (k === "choose") { count += v.count || 1; from = v.from; }
      else if (k === "any" || k.startsWith("any")) count += typeof v === "number" ? v : 0;
    }
    return count ? { count, from } : null;
  }
  const languages = $derived([...new Map(content.languages.filter((l) => l.type === "standard" || l.type === "exotic").map((l) => [l.name.toLowerCase(), l.name])).entries()]);
  // Custom Lineage (TCE p. 8): the Variable Trait is darkvision or one skill; the skill pick shows once "skill" is chosen
  const lineage = $derived(race?.name === "Custom Lineage");
  const skillPicks = $derived(lineage && choice.variable_trait !== "skill" ? null : profBlock("skillProficiencies"));
  const languagePicks = $derived(profBlock("languageProficiencies"));
  const skillOptions = $derived((skillPicks?.from || Object.keys(SKILLS)).map((s) => ({ value: plain(s), label: title(plain(s)) })));

  // DDB's trait cards: no Age, Alignment, Size or Speed; Languages only when it asks for a pick; an
  // Ability Score Increase card first.
  const HIDDEN_TRAITS = /^(Age|Alignment|Size|Speed)$/;
  const traits = $derived.by(() => {
    if (!race) return [];
    const named = (race.entries || []).filter((e) => e && typeof e === "object" && e.name && !HIDDEN_TRAITS.test(e.name))
      .filter((e) => !/^Languages?$/.test(e.name) || (profBlock("languageProficiencies") && !(race.entries || []).some((x) => /Extra Language/.test(x?.name || ""))));
    const asi = abilityBlocks?.length ? [{ name: "Ability Score Increase", entries: abilityBlocks.length > 1
      ? ["Choose one of these options:", ...abilityBlocks.map((b) => abilitySentence(b))] : [abilitySentence(abilityBlocks[0])] }] : [];
    return [...asi, ...named];
  });
  const mentions = (trait, pattern) => pattern.test(JSON.stringify(trait.entries || []));
  // which trait card carries which pick; skills and spells without a trait of their own get a card of their own
  const homeOf = $derived.by(() => {
    const find = (test) => traits.find(test)?.name;
    return {
      ability: find((t) => /^Ability Score/.test(t.name)),
      languages: find((t) => /Extra Language/.test(t.name)) || find((t) => /^Languages?$/.test(t.name)),
      skills: skillPicks && find((t) => /skill/i.test(t.name) || (mentions(t, /proficiency in (one|two|\w+)( of the following)? skills?/i) && mentions(t, /choice/i))),
      ancestry: race?.name.startsWith("Dragonborn") && find((t) => /Ancestry/.test(t.name)),
      variable: lineage && find((t) => t.name === "Variable Trait"),
      feat: race?.feats && find((t) => /^Feat/.test(t.name)),
      spells: race?.additionalSpells && (find((t) => mentions(t, /\{@spell |\{@filter [^}]*\|spells\|/)) || find((t) => /Cantrip|Magic|Legacy|Spellcasting/.test(t.name))),
    };
  });
  function choiceCount(name) {
    const h = homeOf;
    let n = 0;
    if (name === h.ability) n += (abilityBlocks?.length > 1 ? 1 : 0) + chooseCount;
    if (name === h.languages && languagePicks) n += languagePicks.count;
    if (name === h.skills) n += skillPicks.count;
    if (name === h.ancestry) n += 1;
    if (name === h.variable) n += 1;
    if (name === h.feat) n += 1;
    return n;
  }
  // Picks still unmade in a trait card: DDB puts its "!" on such cards (styles_alert__tPDGl).
  function openCount(name) {
    const h = homeOf;
    let open = 0;
    if (name === h.ability) open += Math.max(0, chooseCount - (choice.ability_choices || []).filter(Boolean).length);
    if (name === h.languages && languagePicks) open += Math.max(0, languagePicks.count - (choice.languages || []).length);
    if (name === h.skills) open += Math.max(0, skillPicks.count - (choice.skills || []).length);
    if (name === h.ancestry && !choice.ancestry) open += 1;
    if (name === h.variable && !choice.variable_trait) open += 1;
    if (name === h.feat) open += choice.feat?.id ? featOpen(content.byId.feats[choice.feat.id], choice.feat, level) : 1;
    if (name === h.spells) open += spellsOpen(race.additionalSpells, choice, level);
    return open;
  }
  const featOptions = $derived(content.feats.filter((f) => sourceAllowed(f.book, current.character.preferences) || f.id === choice.feat?.id)
    .map((f) => featOption(f, { sheet: current.sheet, character: current.character, level },
      { enforce: current.character.preferences?.feat_prerequisites !== false, chosen: choice.feat?.id, group: f.book === "phb" ? "5e Core Rules" : "5e Expanded Rules" })));
  const summary = $derived(traits.map((t) => t.name).filter((n) => !NOT_SUMMARIZED.test(n)));
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

{#snippet pickBox(placeholder, value, options, onchange)}
  <div class="styles_choice__qE4aQ"><div class="detail-choice {value ? '' : 'detail-choice--todo'}">
    <DdbSelect highlight {placeholder} {value} {options} {onchange} />
  </div></div>
{/snippet}

{#snippet skillChoices()}
  {#each range(skillPicks.count) as k}
    {@render pickBox("- Choose a Skill -", (choice.skills || [])[k] || "", without(skillOptions, choice.skills, (choice.skills || [])[k]),
      (v) => { choice.skills = setPick(choice.skills, k, v); changed(); })}
  {/each}
{/snippet}

{#snippet picksFor(name)}
  {@const h = homeOf}
  {#if name === h.ability}
    {#if abilityBlocks?.length > 1}
      {@render pickBox("- Choose an Option -", String(choice.ability_block || 0), abilityBlocks.map((b, k) => ({ value: String(k), label: abilityText(b) })),
        (v) => { choice.ability_block = Number(v) || 0; choice.ability_choices = []; changed(); })}
    {/if}
    {#each range(chooseCount) as k}
      {@const weight = block.choose.weighted?.weights[k]}
      {@render pickBox(`- Choose an Ability Score${weight ? ` (+${weight})` : ""} -`, (choice.ability_choices || [])[k] || "",
        without(chooseFrom.map((a) => ({ value: a, label: ABILITY_NAMES[a] })), choice.ability_choices, (choice.ability_choices || [])[k]),
        (v) => { const next = [...(choice.ability_choices || [])]; next[k] = v; choice.ability_choices = block.choose.weighted ? next : next.filter(Boolean); changed(); })}
    {/each}
  {/if}
  {#if name === h.languages && languagePicks}
    {#each range(languagePicks.count) as k}
      {@render pickBox("- Choose a Language -", (choice.languages || [])[k] || "",
        without(languagePicks.from ? languagePicks.from.map((l) => ({ value: plain(l).toLowerCase(), label: title(plain(l)) })) : languages.map(([id, n]) => ({ value: id, label: n })), choice.languages, (choice.languages || [])[k]),
        (v) => { choice.languages = setPick(choice.languages, k, v); changed(); })}
    {/each}
  {/if}
  {#if name === h.variable}
    {@render pickBox("- Choose an Option -", choice.variable_trait || "", [{ value: "darkvision", label: "Darkvision (60 feet)" }, { value: "skill", label: "Proficiency in one skill" }],
      (v) => { choice.variable_trait = v || undefined; if (v !== "skill") choice.skills = []; changed(); })}
  {/if}
  {#if name === h.skills}{@render skillChoices()}{/if}
  {#if name === h.ancestry}
    {@render pickBox("- Choose a Draconic Ancestry -", choice.ancestry || "", Object.entries(DRAGONS).map(([dragon, type]) => ({ value: dragon, label: `${dragon} (${type})` })),
      (v) => { choice.ancestry = v || undefined; changed(); })}
  {/if}
  {#if name === h.feat}
    {@render pickBox("- Choose a Feat -", choice.feat?.id || "", featOptions, (v) => { choice.feat = v ? { id: v } : undefined; changed(); })}
    {#if choice.feat?.id}<FeatChoices pick={choice.feat} />{/if}
  {/if}
  {#if name === h.spells}<GrantedSpells blocks={race.additionalSpells} pick={choice} {level} />{/if}
{/snippet}

<div class="builder-page">
  {#if race}
    <div class="manage-race race-detail">
      <div class="race-detail-primary">
        <div class="race-detail-aside">
          <div class="race-detail-preview">{#if race.ddbArt}<img class="race-detail-preview-img" alt={raceName(race.name)} src="{window.DND5E.ddb}/{race.ddbArt}" />{/if}</div>
          <div class="manage-race-chosen-action" role="button" tabindex="0" onclick={change} onkeydown={(e) => e.key === "Enter" && change()}>Change Race</div>
        </div>
        <div class="builder-page-header">{raceName(race.name)}</div>
        <div class="ddbc-html-content race-detail-description race-detail-description--hide-traits">
          {#if race.groupBlurb}<p>{race.groupBlurb}</p>{/if}
          <p class="characters-statblock" style="font-family: Roboto Condensed;"><strong>Racial Traits</strong><br />{[abilityBlocks?.[0] ? abilityText(abilityBlocks[0]) : null, ...summary.slice(0, 2)].filter(Boolean).join(", ")}</p>
          {#if race.blurb && race.blurb !== race.groupBlurb}<p>{race.blurb}</p>{/if}
        </div>
        {#if summary.length}
          <div class="styles_summaryList__-zLwh"><p class="styles_title__pjCq7">Racial Traits: <span class="styles_listItems__w+Kpf">{summary.join(", ")}</span></p></div>
        {/if}
        <div class="race-detail-more"><a class="race-detail-more-link" href="#race" onclick={(e) => { e.preventDefault(); show("race", race.id); }}>{raceName(race.name)} Details</a></div>
      </div>
      <div class="race-detail-secondary">
        <div class="race-detail-racial-traits">
          {#each traits as trait (trait.name)}
            {@const n = choiceCount(trait.name)}
            {#snippet body()}
              <div class="ddbc-html-content race-detail-racial-trait-description"><Entries entries={trait.entries} /></div>
              {#if n || trait.name === homeOf.spells}<div class="">{@render picksFor(trait.name)}</div>{/if}
            {/snippet}
            {@render card(trait.name, n ? [`${n} Choice${n > 1 ? "s" : ""}`] : [], body, openCount(trait.name) > 0)}
          {/each}
          {#if skillPicks && !homeOf.skills}
            {#snippet skillsBody()}<div class="">{@render skillChoices()}</div>{/snippet}
            {@render card("Skill Proficiencies", [`${skillPicks.count} Choice${skillPicks.count > 1 ? "s" : ""}`], skillsBody, (choice.skills || []).length < skillPicks.count)}
          {/if}
          {#if race.additionalSpells && !homeOf.spells}
            {#snippet spellsBody()}<GrantedSpells blocks={race.additionalSpells} pick={choice} {level} />{/snippet}
            {@render card("Racial Spells", [], spellsBody, spellsOpen(race.additionalSpells, choice, level) > 0)}
          {/if}
        </div>
      </div>
    </div>
  {:else}
    <RaceChooser onpick={pick} />
  {/if}
</div>
