<script>
  // Background step in DDB's markup (description-manage): background dropdown with Configure, the
  // background's proficiency picks, its feature and suggestion tables as paper cards, then DDB's
  // Character Details, Physical, Personal and Notes cards. Configure = PHB p. 125 customizing.
  import Entries from "../lib/Entries.svelte";
  import DdbSelect from "./DdbSelect.svelte";
  import CardChooser from "./CardChooser.svelte";
  import { design } from "../lib/design.svelte.js";
  import { content, sourceAllowed } from "../lib/content.svelte.js";
  import { current, changed } from "../lib/character.svelte.js";
  import { ddb } from "../lib/ddb.svelte.js";
  import { SKILLS, TOOLS, title, plain } from "../lib/format.js";
  import { HIDDEN, ddbName, backgroundCardGroups } from "../lib/backgrounds.js";

  $effect.pre(() => {
    current.character.description ??= {};
  });
  const d = $derived(current.character.description || {});
  const choice = $derived(current.character.background || {});
  const bg = $derived(choice.id ? content.byId.backgrounds[choice.id] : null);
  const languages = $derived([...new Map(content.languages.filter((l) => l.type === "standard" || l.type === "exotic").map((l) => [l.name.toLowerCase(), l.name])).entries()]);
  const ruleGroup = (bookId) => (bookId === "phb" ? "5e Core Rules" : "5e Expanded Rules");
  const backgroundOptions = $derived(content.backgrounds
    .filter((b) => !HIDDEN.has(b.name) && (sourceAllowed(b.book, current.character.preferences) || b.id === choice.id))
    .map((b) => ({ value: b.id, label: ddbName(b.name), group: b.name === "Custom Background" ? "---------" : ruleGroup(b.book) }))
    .sort((a, b) => ["---------", "5e Core Rules", "5e Expanded Rules"].indexOf(a.group) - ["---------", "5e Core Rules", "5e Expanded Rules"].indexOf(b.group) || a.label.localeCompare(b.label)));

  const backgroundCards = $derived(backgroundCardGroups(current.character.preferences));
  function pick(id) {
    current.character.background = id ? { id, skills: [], languages: [], tools: [] } : {};
    changed();
  }
  function configure() {
    if (choice.custom && !confirm("Go back to the book's proficiencies? Your custom picks are dropped.")) return;
    if (choice.custom) delete choice.custom;
    else choice.custom = { skills: [], tools: [], languages: [], name: bg?.name };
    changed();
  }
  function setPick(list, k, value) {
    const next = [...list];
    if (value) next[k] = value;
    else next.splice(k, 1);
    return next.filter(Boolean);
  }
  const without = (all, chosen, mine) => all.filter((o) => o.value === mine || !chosen.includes(o.value));

  // A 5etools proficiency block: fixed entries plus a number of free picks (from a list, or from all).
  function block(key) {
    const b = bg?.[key]?.[0];
    if (!b) return null;
    const out = { count: 0, from: null, fixed: [] };
    for (const [k, v] of Object.entries(b)) {
      if (k === "choose") { out.count += v.count || 1; out.from = v.from; }
      else if (k.startsWith("any") && typeof v === "number") out.count += v;
      else if (v === true) out.fixed.push(plain(k));
    }
    return out;
  }
  // DDB leaves out skills the character already has from its class or race; this background's own picks stay.
  const ownSkills = $derived([...(choice.skills || []), ...(choice.custom?.skills || []), ...(choice.replacement_skills || []), ...(block("skillProficiencies")?.fixed || [])]);
  const overlap = $derived(current.sheet?.background_overlap || []);
  const proficientElsewhere = $derived(Object.entries(current.sheet?.skills || {})
    .filter(([s, v]) => (v.proficiency === "proficient" || v.proficiency === "expertise") && !ownSkills.includes(s)).map(([s]) => s));
  const skillOptions = (from) => (from || Object.keys(SKILLS)).filter((s) => !proficientElsewhere.includes(s)).map((s) => ({ value: s, label: title(s) }));
  const toolOptions = (from) => (from || TOOLS).map((t) => ({ value: plain(t), label: title(plain(t)) }));
  const languageOptions = $derived(languages.map(([id, name]) => ({ value: id, label: name })));
  // PHB p. 125: a customized background has two skills and two tools or languages in any mix.
  const customExtras = $derived([...TOOLS.map((t) => ({ value: `tool:${t}`, label: title(t), group: "Tools" })),
    ...languages.map(([id, name]) => ({ value: `language:${id}`, label: name, group: "Languages" }))]);
  const customChosen = $derived([...(choice.custom?.tools || []).map((t) => `tool:${t}`), ...(choice.custom?.languages || []).map((l) => `language:${l}`)]);
  function setCustomExtra(k, value) {
    const next = setPick(customChosen, k, value);
    choice.custom.tools = next.filter((v) => v.startsWith("tool:")).map((v) => v.slice(5));
    choice.custom.languages = next.filter((v) => v.startsWith("language:")).map((v) => v.slice(9));
    changed();
  }

  const feature = $derived((bg?.entries || []).find((e) => e?.data?.isFeature));
  const suggestions = $derived((bg?.entries || []).find((e) => e?.name === "Suggested Characteristics"));
  const tables = $derived((suggestions?.entries || []).filter((e) => e?.type === "table"));
  const tableFor = (word) => tables.find((t) => (t.colLabels?.[1] || "").toLowerCase().startsWith(word));
  const cellText = (cell) => (typeof cell === "string" ? cell : cell?.roll ? String(cell.roll.exact ?? `${cell.roll.min}-${cell.roll.max}`) : String(cell ?? ""));
  function addLine(key, text) {
    d[key] = d[key] ? `${d[key].replace(/\n+$/, "")}\n${text}` : text;
    changed();
  }

  const alignment = $derived(content.alignments.find((a) => a.name === d.alignment));
  const lifestyle = $derived(content.lifestyles.find((l) => l.name === d.lifestyle));
  const lifestyleLabel = (l) => `${l.name} ${l.cost === "—" ? "" : `(${l.cost.replace(/ (sp|gp)/i, (m, unit) => unit.toUpperCase())})`}`.trim();

  const PHYSICAL = [["hair", "Hair", "text"], ["skin", "Skin", "text"], ["eyes", "Eyes", "text"], ["height", "Height", "text"],
    ["weight", "Weight (lbs)", "number"], ["age", "Age (Years)", "number"], ["gender", "Gender", "text"]];
  // [key, heading, button noun, suggestion table word, prompt]
  const PERSONAL = [["traits", "Personality Traits", "Traits", "personality", "How does your character act, talk and carry themselves?"],
    ["ideals", "Ideals", "Ideals", "ideal", "What does your character believe in above all?"],
    ["bonds", "Bonds", "Bonds", "bond", "Which people, places or things matter most to your character?"],
    ["flaws", "Flaws", "Flaws", "flaw", "What weakness, vice or fear could others use against your character?"]];
  const NOTES = [["organizations", "Organizations"], ["allies", "Allies"], ["enemies", "Enemies"], ["backstory", "Backstory"], ["other", "Other"]];
  let dialogs = $state({});
</script>

{#snippet card(name, meta, body, open = false)}
  <details class="styles_details__Kwqwr styles_paper__FhNqH" {open}>
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

{#snippet suggestionTable(table, key, heading)}
  <div class="ct-suggestions-table">
    <table class="ct-suggestions-table__table">
      <thead><tr class="ct-suggestions-table__header">
        <th class="ct-suggestions-table__header-col ct-suggestions-table__col--die">{table.colLabels?.[0]}</th>
        <th class="ct-suggestions-table__header-col ct-suggestions-table__col--desc">{heading || table.colLabels?.[1]}</th>
        <th class="ct-suggestions-table__header-col ct-suggestions-table__col--action">
          <button type="button" class="ct-theme-button ct-theme-button--filled ct-theme-button--interactive ct-button character-button ddbc-button character-button-small" role="button"
            onclick={() => addLine(key, cellText(table.rows[Math.floor(Math.random() * table.rows.length)][1]))}><span class="ct-button__content">Random</span></button>
        </th>
      </tr></thead>
      <tbody>
        {#each table.rows as row}
          <tr class="ct-suggestions-table__item">
            <td class="ct-suggestions-table__item-col ct-suggestions-table__col--die">{cellText(row[0])}</td>
            <td class="ct-suggestions-table__item-col ct-suggestions-table__col--desc">{cellText(row[1])}</td>
            <td class="ct-suggestions-table__item-col ct-suggestions-table__col--action">
              <button type="button" class="ct-theme-button ct-theme-button--filled ct-theme-button--interactive ct-button character-button ddbc-button character-button-small" role="button"
                onclick={() => addLine(key, cellText(row[1]))}><span class="ct-button__content">+ Add</span></button>
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{/snippet}

{#snippet textEditor(key, heading, noun, prompt, table)}
  <div class="styles_container__bOoAH">
    <header class="styles_header__K3QPR">
      <h3 class="styles_heading__e3CeE">{heading}</h3>
      <button type="button" class="Button_button__B9Kr5 ButtonVariants_primary__TMQ5y ButtonSizes_medium__uHe8x styles_xx-small__Q1OkG styles_solid__2ijrG styles_builder-green__00NLA"
        onclick={() => dialogs[key]?.showModal()}>{d[key] ? "Edit" : "Add"} {noun}</button>
    </header>
    {#if d[key]}<div class="styles_preview__cev1Z">{d[key]}</div>{/if}
    <dialog class="Dialog_dialog__+k9ss styles_dialog__T7+jw styles_confirmModal__MS4hT styles_fullScreen__hG3x4" aria-modal="true" data-testid="textarea-editor-modal" bind:this={dialogs[key]}>
      <header class="styles_header__2RJaP">
        <h2>{d[key] ? "Edit" : "Add"} {noun}</h2>
        <button type="button" class="Button_button__B9Kr5 ButtonVariants_primary__TMQ5y ButtonVariants_text__vKMzd ButtonSizes_x-small__AQ7c6 styles_x-small__8tmZN styles_light__kA91w styles_text__BLc8n styles_closeButton__Qq-hF"
          aria-label="Close {heading}" onclick={() => dialogs[key]?.close()}>{@html ddb.icons["remove-x"] || "✕"}</button>
      </header>
      <div class="styles_content__mNhoq">
        <div>
          <label class="styles_title__ldbWf" for="text-{key}"><h3>{heading}</h3></label>
          <div class="styles_textarea__7oQCq styles_textarea__QO4Cg" data-value={d[key] || ""} id="text-{key}-wrap">
            <textarea id="text-{key}" rows="1" placeholder="Add {noun.toLowerCase()} here..." bind:value={d[key]} oninput={() => changed(800)}></textarea>
          </div>
          <div class="styles_extra__J+6xL">
            <div class="description-suggestion">
              <div class="description-suggestion-info">{prompt}</div>
              {#if table}
                <div class="description-suggestion-heading">Suggestions</div>
                {@render suggestionTable(table, key)}
              {/if}
            </div>
          </div>
        </div>
      </div>
      <footer class="styles_footer__5tfjP">
        <button type="button" class="Button_button__B9Kr5 ButtonVariants_primary__TMQ5y ButtonSizes_x-small__AQ7c6 styles_x-small__8tmZN styles_light__kA91w styles_solid__2ijrG styles_builder-green__00NLA styles_footerButton__EOQCj styles_confirmOnly__9K02E"
          onclick={() => dialogs[key]?.close()}>Save and Close</button>
      </footer>
    </dialog>
  </div>
{/snippet}

{#snippet proficiency(label, fixed, picks)}
  <div class="">
    <div class="description-manage-background-proficiency">
      <span class="description-manage-background-proficiency-label">{label}</span>{#if fixed.length} {fixed.map(title).join(", ")}{/if}
    </div>
    {#if picks.length}
      <div class=""><div class="description-manage-background-choices-items">
        {#each picks as [placeholder, value, options, onchange]}
          <div class="detail-choice styles_backgroundChoiceSelect__tvLb4 {value ? '' : 'detail-choice--todo'}">
            <DdbSelect highlight {placeholder} {value} {options} {onchange} />
          </div>
        {/each}
      </div></div>
    {/if}
  </div>
{/snippet}

{#if design.mode === "new" && !choice.id}
  <CardChooser heading="Choose a Background" noun="background" groups={backgroundCards} onpick={pick} />
{/if}
<div class="description-manage builder-page">
  <div class="description-manage-information"></div>
  <div class="description-manage-background" hidden={design.mode === "new" && !choice.id}>
    <div class="builder-page-subheader">Choose a Background</div>
    <div class="ct-character-tools__marketplace-callout">Check your source settings on the <strong>Home</strong> tab if you can't find a Background.</div>
    <div class="styles_backgroundSelectContainer__8z5Qs">
      <DdbSelect extraClass="styles_backgroundSelect__cU8nz" placeholder="-- Choose an Option --" value={choice.id || ""} options={backgroundOptions} onchange={pick} />
      {#if bg}
        <button type="button" class="Button_button__B9Kr5 ButtonVariants_primary__TMQ5y ButtonSizes_x-small__AQ7c6 styles_x-small__8tmZN styles_builder-text__RlIXo styles_customBackgroundToggle__moSul"
          title={choice.custom ? "Customized (PHB p. 125): click to go back to the book's proficiencies" : "Swap the book's proficiencies for two skills and two tools or languages of your choice (PHB p. 125)"}
          onclick={configure}>Configure{@html ddb.icons["plus"] || "+"}</button>
      {/if}
    </div>
    {#if bg}
      {@const sk = block("skillProficiencies")}
      {@const tl = block("toolProficiencies")}
      {@const lg = block("languageProficiencies")}
      <div class="">
        <div class="builder-page-subheader">{choice.custom?.name || ddbName(bg.name)}</div>
        <div class="styles_accordionGroup__ijLDx">
          {#if choice.custom}
            <label class="ddb-xp-change">Background name <input type="text" value={choice.custom.name || ""} oninput={(e) => { choice.custom.name = e.target.value; changed(800); }} /></label>
            {@render proficiency("Feature:", [], [["- Feature of this background -", choice.custom.feature_from || "",
              content.backgrounds.filter((b) => b.id !== bg.id && (b.entries || []).some((e) => JSON.stringify(e).includes('"name":"Feature:'))).map((b) => ({ value: b.id, label: `${ddbName(b.name)} (${b.book.toUpperCase()})` })),
              (v) => { choice.custom.feature_from = v || undefined; changed(); }]])}
            {@render proficiency("Skill Proficiencies:", [], [0, 1].map((k) => [`- Choose a Skill -`, choice.custom.skills[k] || "",
              without(skillOptions(), choice.custom.skills, choice.custom.skills[k]), (v) => { choice.custom.skills = setPick(choice.custom.skills, k, v); changed(); }]))}
            {@render proficiency("Tool Proficiencies and Languages:", [], [0, 1].map((k) => [`- Choose a Tool or Language -`, customChosen[k] || "",
              without(customExtras, customChosen, customChosen[k]), (v) => setCustomExtra(k, v)]))}
          {:else}
            {#if sk}{@render proficiency("Skill Proficiencies:", sk.fixed, Array.from({ length: sk.count }, (_, k) => [`- Choose a Skill -`, (choice.skills || [])[k] || "",
              without(skillOptions(sk.from), choice.skills || [], (choice.skills || [])[k]), (v) => { choice.skills = setPick(choice.skills || [], k, v); changed(); }]))}{/if}
            {#if overlap.length}{@render proficiency(`You already have ${overlap.map(title).join(" and ")}; replacement (PHB p. 125):`, [], overlap.map((_, k) => [`- Choose a Skill -`, (choice.replacement_skills || [])[k] || "",
              without(Object.keys(SKILLS).filter((x) => !["proficient", "expertise"].includes(current.sheet?.skills?.[x]?.proficiency) || (choice.replacement_skills || []).includes(x)).map((x) => ({ value: x, label: title(x) })), choice.replacement_skills || [], (choice.replacement_skills || [])[k]), (v) => { choice.replacement_skills = setPick(choice.replacement_skills || [], k, v); changed(); }]))}{/if}
            {#if tl}{@render proficiency("Tool Proficiencies:", tl.fixed, Array.from({ length: tl.count }, (_, k) => [`- Choose a Tool -`, (choice.tools || [])[k] || "",
              without(toolOptions(tl.from), choice.tools || [], (choice.tools || [])[k]), (v) => { choice.tools = setPick(choice.tools || [], k, v); changed(); }]))}{/if}
            {#if lg}{@render proficiency("Languages:", lg.fixed, Array.from({ length: lg.count }, (_, k) => [`- Choose a Language -`, (choice.languages || [])[k] || "",
              without(languageOptions, choice.languages || [], (choice.languages || [])[k]), (v) => { choice.languages = setPick(choice.languages || [], k, v); changed(); }]))}{/if}
          {/if}
          {#if feature}
            {#snippet featureBody()}<div class="ddbc-html-content"><Entries entries={feature.entries} ddb /></div>{/snippet}
            {@render card(feature.name.replace(/^Feature: /, "").replace(/'/g, "\u2019"), ["Background Feature", ddbName(bg.name)], featureBody)}
          {/if}
          {#if tables.length}
            {#snippet suggestionsBody()}
              <div class="background-suggestions">
                {#each [["traits", "personality"], ["ideals", "ideal"], ["bonds", "bond"], ["flaws", "flaw"]] as [key, word]}
                  {#if tableFor(word)}{@render suggestionTable(tableFor(word), key)}{/if}
                {/each}
              </div>
            {/snippet}
            {@render card("Suggested Characteristics", [ddbName(bg.name)], suggestionsBody)}
          {/if}
        </div>
      </div>
    {/if}
  </div>

  {#snippet details()}
    <div class="description-manage-alignment">
      <label class="description-manage-alignment-label" for="alignment">Alignment</label>
      <DdbSelect placeholder="-- Choose an Option --" searchable={false} value={d.alignment || ""} options={content.alignments.map((a) => ({ value: a.name, label: a.name }))}
        onchange={(v) => { d.alignment = v || null; changed(); }} />
      <div class="ddbc-html-content description-manage-alignment-desc">{#if alignment}<Entries entries={alignment.entries} />{/if}</div>
    </div>
    <div class="description-manage-faith">
      <div>
        <label class="form_label__nzG8p" for="faith">Faith</label>
        <input class="form_input__Xyq7o" id="faith" type="text" bind:value={d.faith} oninput={() => changed(800)} />
      </div>
    </div>
    <div class="description-manage-lifestyle">
      <label class="description-manage-lifestyle-label" for="lifestyle">Lifestyle</label>
      <DdbSelect placeholder="-- Choose an Option --" searchable={false} value={d.lifestyle || ""} options={content.lifestyles.map((l) => ({ value: l.name, label: lifestyleLabel(l) }))}
        onchange={(v) => { d.lifestyle = v || null; changed(); }} />
      <div class="ddbc-html-content description-manage-lifestyle-desc">{#if lifestyle}<Entries entries={lifestyle.entries} />{/if}</div>
    </div>
  {/snippet}
  {@render card("Character Details", ["Alignment", "Faith", "Lifestyle"], details)}

  {#snippet physical()}
    {#each PHYSICAL as [key, label, type]}
      <div class="styles_inputField__WePfs">
        <label class="form_label__nzG8p" for="physical-{key}">{label}</label>
        <input class="form_input__Xyq7o" id="physical-{key}" {type} value={d[key] ?? ""} oninput={(e) => { d[key] = e.target.value; changed(800); }} />
      </div>
    {/each}
  {/snippet}
  {@render card("Physical Characteristics", ["Hair", "Skin", "Eyes", "Height", "Weight", "Age", "Gender"], physical)}

  {#snippet personal()}
    {#each PERSONAL as [key, heading, noun, word, prompt]}{@render textEditor(key, heading, noun, prompt, tableFor(word))}{/each}
  {/snippet}
  {@render card("Personal Characteristics", ["Personality", "Ideals", "Bonds", "Flaws"], personal)}

  {#snippet notes()}
    {#each NOTES as [key, heading]}{@render textEditor(key, heading, "Notes", `Anything worth remembering under ${heading.toLowerCase()}.`, null)}{/each}
  {/snippet}
  {@render card("Notes", NOTES.map(([, heading]) => heading), notes)}
</div>
