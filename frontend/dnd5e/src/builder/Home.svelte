<script>
  // Home step in DDB's markup: "Character Preferences" with DDB's groups, in DDB's order. Groups that do not
  // apply to a 2014-only private builder (Homebrew, 5.5e, Drops, partners, dice, privacy) are left out.
  // Below them, under their own heading, the sheet look and number overrides DDB keeps in its sheet panes.
  import DdbSelect from "./DdbSelect.svelte";
  import { current, changed } from "../lib/character.svelte.js";
  import { ddb } from "../lib/ddb.svelte.js";
  import { content, booksOff } from "../lib/content.svelte.js";
  import { ABILITIES, SKILLS, title } from "../lib/format.js";

  // The character can arrive (or be reloaded) after this component starts: the objects are made whenever it changes.
  $effect.pre(() => {
    current.character.description ??= {};
    current.character.overrides ??= {};
    current.character.preferences ??= {};
  });
  const description = $derived(current.character.description || {});
  const prefs = $derived(current.character.preferences || {});
  const o = $derived(current.character.overrides || {});

  // [group title, group description, [[key, label, description, get, set]]]
  // one switch per book, grouped rules / adventures / other (Dodo, 2026-10-25); off books are stored, not on ones
  const BOOK_GROUPS = [["rules", "Rule books", "Player's Handbook, Xanathar's, Tasha's, setting books and the other rule books."],
    ["adventures", "Adventure books", "Races, items and spells first printed in an adventure."], ["other", "Other", "Organised play and odds and ends."]];
  const off = $derived(booksOff(prefs));
  function setBooks(ids, on) {
    const next = new Set(off);
    for (const id of ids) on ? next.delete(id) : next.add(id);
    prefs.books_off = [...next];
    delete prefs.sources;
    changed();
  }
  const flag = (key, label, text = "") => [key, label, text, () => !!prefs[key], (on) => { prefs[key] = on; }];
  const GROUPS = [
    ["Optional Features", "Allow or restrict optional features for this character", [
      flag("optional_class_features", "Optional Class Features"),
      flag("customize_origin", "Customize Your Origin"),
    ]],
  ];
  const GROUPS_AFTER_HP = [
    ["Use Prerequisites", "Allow or restrict choices based on rule prerequisites for the following for this character", [
      [ "feat_prerequisites", "Feats", "", () => prefs.feat_prerequisites !== false, (on) => { prefs.feat_prerequisites = on; }],
      [ "multiclass_prerequisites", "Multiclass Requirements", "", () => prefs.multiclass_prerequisites !== false, (on) => { prefs.multiclass_prerequisites = on; }],
    ]],
    ["Show Unarmed Strike", "Display Unarmed Strike in the attack list on the Actions tab", [
      ["show_unarmed", "Show Unarmed Strike", "", () => prefs.show_unarmed !== false, (on) => { prefs.show_unarmed = on; }],
    ]],
    ["Show Level-Scaled Spells", "Display and highlight available spells to cast with higher level spell slots", [
      ["level_scaled_spells", "Show Level-Scaled Spells", "", () => prefs.level_scaled_spells !== false, (on) => { prefs.level_scaled_spells = on; }],
    ]],
  ];
  // Our coin_weight says "coins weigh" (default yes, as on DDB); DDB's box says the opposite.
  const COIN_GROUP = ["Ignore Coin Weight", "Coins do not count against your total weight carried (50 coins weigh 1 lb.)", [
    ["ignore_coin_weight", "Ignore Coin Weight", "", () => description.coin_weight === false, (on) => { description.coin_weight = !on; }],
  ]];

  const NUMBERS = [
    ["ac", "Armor class, set to"], ["ac_bonus", "Armor class, add"], ["hp_max", "Max hit points, set to"], ["hp_bonus", "Max hit points, add"],
    ["speed", "Walking speed, set to (ft.)"], ["initiative_bonus", "Initiative, add"], ["spell_dc_bonus", "Spell save DC, add"], ["spell_attack_bonus", "Spell attack, add"],
  ];
  function setNum(key, value) {
    if (value === "") delete o[key];
    else o[key] = Number(value);
    changed();
  }
  function setMap(group, key, value) {
    const map = { ...(o[group] || {}) };
    if (value === "" || Number(value) === 0) delete map[key];
    else map[key] = Number(value);
    o[group] = map;
    changed();
  }
</script>

{#snippet bookSources()}
  <div class="styles_checkboxGroup__lmZTn styles_checkboxGroup__TpQcD">
    <header class="">
      <div class="styles_checkboxGroupHeader__q6ySy"><p class="styles_checkboxGroupTitle__C2DFH">Sources</p></div>
      <div class="styles_checkboxGroupDescription__eKD6P">You will only see character options from the books you enable here.</div>
    </header>
    <div class="styles_checkboxOptions__+pPcc">
      {#each BOOK_GROUPS as [group, label, text]}
        {@const books = content.books.filter((b) => b.group === group)}
        {@const onCount = books.filter((b) => !off.includes(b.id)).length}
        <div class="styles_checkboxOption__VFy5A">
          <div class="Checkbox_container__Z2TB6 styles_checkbox__6h8Zt styles_checkbox__4Rrwz">
            <span class="Checkbox_inputContainer__82z5+"><input class="Checkbox_checkbox__GJtMy" id="books-{group}" type="checkbox" checked={onCount === books.length}
              onchange={(e) => setBooks(books.map((b) => b.id), e.target.checked)} />{#if onCount === books.length}{@html ddb.icons["checkbox-check"] || ""}{/if}</span>
          </div>
          <div class="styles_optionContent__v91sl">
            <label class="styles_label__JthJA" for="books-{group}">{label} ({onCount} of {books.length})</label>
            <div class="styles_description__KwP2U"><p>{text}</p></div>
            <details class="home-books"><summary>Choose books</summary>
              {#each books as b}
                <label class="home-book"><input type="checkbox" checked={!off.includes(b.id)} onchange={(e) => setBooks([b.id], e.target.checked)} /> {b.name}</label>
              {/each}
            </details>
          </div>
        </div>
      {/each}
    </div>
  </div>
{/snippet}

{#snippet checkboxGroup([groupTitle, groupText, options])}
  <div class="styles_checkboxGroup__lmZTn styles_checkboxGroup__TpQcD">
    <header class="">
      <div class="styles_checkboxGroupHeader__q6ySy"><p class="styles_checkboxGroupTitle__C2DFH">{groupTitle}</p></div>
      <div class="styles_checkboxGroupDescription__eKD6P">{groupText}</div>
    </header>
    <div class="styles_checkboxOptions__+pPcc">
      {#each options as [key, label, text, get, set]}
        <div class="styles_checkboxOption__VFy5A" data-testid="form-checkbox-group">
          <div class="Checkbox_container__Z2TB6 styles_checkbox__6h8Zt styles_checkbox__4Rrwz">
            <span class="Checkbox_inputContainer__82z5+"><input class="Checkbox_checkbox__GJtMy" id="pref-{key}" type="checkbox" name={key} checked={get()}
              onchange={(e) => { set(e.target.checked); changed(); }} />{#if get()}{@html ddb.icons["checkbox-check"] || ""}{/if}</span>
          </div>
          <div class="styles_optionContent__v91sl">
            <label class="styles_label__JthJA" for="pref-{key}">{label}</label>
            {#if text}<div class="styles_description__KwP2U"><p>{@html text}</p></div>{/if}
          </div>
        </div>
      {/each}
    </div>
  </div>
{/snippet}

{#snippet selectField(key, label, text, value, options, onchange)}
  <div class="styles_selectField__RENAl" data-testid="select-field-container">
    <div><label class="styles_label__stijJ" for={key}>{label}</label><div class="styles_description__HJOkQ">{text}</div></div>
    <DdbSelect extraClass="styles_field__jMyq0" placeholder="" searchable={false} {value} {options} {onchange} />
  </div>
{/snippet}

<div class="page_page__NWf2H styles_home__VTUDc">
  <h2 class="page_title__xL1kF">Character Preferences</h2>
  <div class="home-manage-preferences">
    {@render bookSources()}
    {#each GROUPS as group}{@render checkboxGroup(group)}{/each}
    {@render selectField("advancementType", "Advancement Type", "Story-based character progression / XP-based character progression",
      prefs.advancement || "milestone", [{ value: "milestone", label: "Milestone" }, { value: "xp", label: "XP" }],
      (v) => { prefs.advancement = v; changed(); })}
    {@render selectField("hitPointType", "Hit Point Type", "When leveling up, increase hit points by the fixed value for your chosen class or manually enter a rolled value",
      description.hp_mode || "average", [{ value: "average", label: "Fixed" }, { value: "rolled", label: "Manual" }],
      (v) => { description.hp_mode = v; changed(); })}
    {#each GROUPS_AFTER_HP as group}{@render checkboxGroup(group)}{/each}
    {@render selectField("encumbranceType", "Encumbrance Type", "Use the standard encumbrance rules / Disable the encumbrance display / Use the more detailed rules for encumbrance",
      description.encumbrance || "standard", [{ value: "standard", label: "Use Encumbrance" }, { value: "none", label: "No Encumbrance" }, { value: "variant", label: "Variant Encumbrance" }],
      (v) => { description.encumbrance = v; changed(); })}
    {@render checkboxGroup(COIN_GROUP)}
    {@render selectField("abilityScoreDisplayType", "Ability Score/Modifier Display", "Reverse the arrangement of ability modifiers and scores",
      prefs.ability_display || "modifiers", [{ value: "modifiers", label: "Modifiers Top" }, { value: "scores", label: "Scores Top" }],
      (v) => { prefs.ability_display = v; changed(); })}
  </div>
  <hr class="page_divider__MDOC2" />

  <!-- Not on DDB's Home: DDB edits these in the sheet's Manage Character and stat panes. -->
  <div class="ddb-extras">
    <h2 class="page_title__xL1kF">Sheet Look and Overrides</h2>
    <div class="form-grid">
      <label>Player <input type="text" bind:value={description.player} oninput={() => changed()} /></label>
      <label>Sheet colour (frames and accents)
        <input type="color" value={description.theme || "#c53131"} oninput={(e) => { description.theme = e.target.value; changed(); }} />
      </label>
      <label>Sheet backdrop (the art behind the sheet)
        <select value={description.backdrop || ""} onchange={(e) => { description.backdrop = e.target.value || null; description.backdrop_url = null; changed(); }}>
          <option value="">Same as the first class</option>
          {#each ["artificer", "barbarian", "bard", "cleric", "druid", "fighter", "monk", "paladin", "ranger", "rogue", "sorcerer", "warlock", "wizard"] as k}<option value={k}>{title(k)}</option>{/each}
        </select>
      </label>
      <label>Portrait image URL <input type="url" value={description.avatar_url || ""} placeholder="https://…" oninput={(e) => { description.avatar_url = e.target.value || null; changed(800); }} /></label>
    </div>
    <p class="hint">Numbers set by hand: magic items the rules data does not model, DM boons, house rules. They apply after everything else and show an asterisk (*) on the sheet. Leave a field empty for no override.</p>
    <div class="form-grid">
      {#each NUMBERS as [key, label]}
        <label>{label} <input type="number" value={o[key] ?? ""} oninput={(e) => setNum(key, e.target.value)} /></label>
      {/each}
    </div>
    <details class="features">
      <summary>Saving throw and skill bonuses</summary>
      <div class="form-grid">
        {#each ABILITIES as a}
          <label>{a.toUpperCase()} save, add <input type="number" value={o.save_bonus?.[a] ?? ""} oninput={(e) => setMap("save_bonus", a, e.target.value)} /></label>
        {/each}
        {#each Object.keys(SKILLS) as sk}
          <label>{title(sk)}, add <input type="number" value={o.skill_bonus?.[sk] ?? ""} oninput={(e) => setMap("skill_bonus", sk, e.target.value)} /></label>
        {/each}
      </div>
    </details>
  </div>
  <hr class="page_divider__MDOC2" />
  <div class="styles_versionInfo__ElLLU"><p>Version: <span>Dodo Beyond, 2014 rules</span></p></div>
</div>
