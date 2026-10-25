<script>
  import Foyer from "./Foyer.svelte";
  import Finish from "./Finish.svelte";
  import { design } from "../lib/design.svelte.js";
  // Builder shell in DDB's markup (class names from saved DDB builder pages): page header, step
  // links, prev/next arrows, portrait and name on every step. Step order is DDB's; wording is 2014.
  import { route } from "../lib/router.svelte.js";
  import { current, changed } from "../lib/character.svelte.js";
  import { ddb, useSheetStyles, loadFrames } from "../lib/ddb.svelte.js";
  import { content } from "../lib/content.svelte.js";
  import Home from "./Home.svelte";
  import ClassStep from "./ClassStep.svelte";
  import RaceStep from "./RaceStep.svelte";
  import AbilitiesStep from "./AbilitiesStep.svelte";
  import BackgroundStep from "./BackgroundStep.svelte";
  import EquipmentStep from "./EquipmentStep.svelte";
  import WhatsNext from "./WhatsNext.svelte";

  // [route key, DDB section class, label]
  const STEPS = [
    ["home", "home", "Home"], ["class", "class", "1. Class"], ["background", "description", "2. Background"],
    ["race", "race", "3. Race"], ["abilities", "ability_scores", "4. Abilities"], ["equipment", "equipment", "5. Equipment"],
    ["summary", "whats_next", "What's Next"],
  ];
  const step = $derived(route.step === "spells" ? "class" : STEPS.some(([k]) => k === route.step) ? route.step : "home");
  const index = $derived(STEPS.findIndex(([k]) => k === step));
  const open = $derived(current.sheet?.choices_open || []);
  const avatar = $derived(current.character.description?.avatar_url || null);
  const theme = $derived((current.character.description?.theme || "#c53131").replace("#", ""));
  const href = (key) => `#/c/${route.id}/builder/${key}`;
  // DDB's greyed arrow on the first and last step: the same chevron, --disabled and #999.
  const disabledIcon = (name) => (ddb.icons[name] || "").replace("ddbc-svg--light", "ddbc-svg--disabled").replace(/fill="#[0-9a-fA-F]{3,6}"/g, 'fill="#999999"');

  // Name suggestions from Xanathar's name tables (XGE p. 175): the race's own table, Half-Elf from Elf
  // and Human, anything without a table from Human.
  let suggestions = $state([]);
  function suggestNames(count = 6) {
    const race = content.byId.races[current.character.race?.id]?.name || "";
    const sets = content.names.filter((n) => race.startsWith(n.name) || (race.startsWith("Half-Elf") && ["Elf", "Human"].includes(n.name)));
    const tables = (sets.length ? sets : content.names.filter((n) => n.name === "Human"))
      .flatMap((n) => n.tables.filter((t) => !/clan|family|virtue|child/i.test(t.option)));
    const pick = (list) => list[Math.floor(Math.random() * list.length)];
    const out = new Set();
    for (let guard = 0; out.size < count && guard < 50; guard++) out.add(pick(pick(tables).names));
    return [...out];
  }

  $effect(() => useSheetStyles());
  $effect(() => {
    loadFrames(theme);
  });
  // DDB's builder <body>: its CSS paints the backdrop on .body-rpgcharacterbuilder (with !important) and keys
  // the 15px builder text on it; the dark header band is .character-builder-step_by_step:before.
  $effect(() => {
    const bodyClasses = ["site", "body-rpgcharacterbuilder", "site-dndbeyond", "body-rpgcharacter"];
    document.body.classList.add(...bodyClasses);
    document.body.id = "site";
    document.body.dataset.theme = "light";
    return () => {
      document.body.classList.remove(...bodyClasses);
      document.body.removeAttribute("id");
      delete document.body.dataset.theme;
    };
  });
</script>

{#if route.step === "start" && design.mode === "new"}
<Foyer />
{:else if route.step === "finish"}
<Finish />
{:else}
<div class="character-builder character-builder-step_by_step styles_characterBuilder__-atY5 character-builder--dice-enabled">
  <div class="sync-blocker  sync-blocker-inactive"></div>
  <div class="character-builder-inner">
    <div class="character-builder-page-header">
      <h1 class="character-builder-page-header-heading">Character Builder</h1>
      <div class="character-builder-page-header-summary">
        <div class="ddbc-character-avatar__portrait character-builder-page-header-avatar {avatar ? '' : 'ddbc-character-avatar__portrait--none'}" style={avatar ? `background-image:url("${avatar}")` : ""}></div>
        <div class="character-builder-page-header-name">{current.character.name || "Unnamed"}</div>
      </div>
    </div>
    <div class="builder-sections builder-sections-large">
      <div class="help-text-manager help-text-manager-disabled"><div class="help-text-manager-icon"></div></div>
      <!-- DDB greys this out while choices are open; ours stays clickable then and says why it is grey. -->
      <div class="builder-sections-sheet {open.length ? 'builder-sections-sheet-disabled' : ''}">
        <div class="tss-1r5d1qn-Notification">
          {#if open.length}
            <div class="styles_characterSheetIcon__NQH1m styles_disabled__QQt8w" role="link" tabindex="0" title="Character is incomplete ({open.length} choices open)"
              onclick={() => (location.hash = `#/c/${route.id}/sheet`)} onkeydown={(e) => e.key === "Enter" && (location.hash = `#/c/${route.id}/sheet`)}>{@html ddb.icons["sheet-icon"] || ""}</div>
          {:else}
            <a class="styles_characterSheetIcon__NQH1m" href={`#/c/${route.id}/sheet`} aria-label="Open the character sheet">{@html (ddb.icons["sheet-icon"] || "").replace(" styles_disabled__QQt8w", "")}</a>
          {/if}
          <div class="Tooltip_container__20y9m"></div>
        </div>
      </div>
      <div class="builder-sections-large-routes">
        {#each STEPS as [key, cls, label]}
          <div class="builder-sections-view">
            <a class="builder-sections-link builder-sections-section-{cls} {step === key ? 'builder-sections-link-active' : ''}" href={href(key)}>{label}</a>
          </div>
        {/each}
      </div>
    </div>
    <div class="builder-navigation-large">
      {#if index > 0}
        <a class="builder-navigation-large-link" href={href(STEPS[index - 1][0])}>
          <div class="builder-navigation-large-action builder-navigation-large-action-prev"><div class="builder-navigation-large-action-icon">{@html ddb.icons["chevron-left"] || ""}</div><div class="builder-navigation-large-action-text">Prev</div></div>
        </a>
      {:else}
        <div class="builder-navigation-large-link">
          <div class="builder-navigation-large-action builder-navigation-large-action-prev builder-navigation-large-action-disabled builder-navigation-large-action-prev-disabled"><div class="builder-navigation-large-action-icon">{@html disabledIcon("chevron-left")}</div><div class="builder-navigation-large-action-text">Prev</div></div>
        </div>
      {/if}
      {#if index < STEPS.length - 1}
        <a class="builder-navigation-large-link" href={href(STEPS[index + 1][0])}>
          <div class="builder-navigation-large-action builder-navigation-large-action-next"><div class="builder-navigation-large-action-text">Next</div><div class="builder-navigation-large-action-icon">{@html ddb.icons["chevron-right"] || ""}</div></div>
        </a>
      {:else}
        <div class="builder-navigation-large-link">
          <div class="builder-navigation-large-action builder-navigation-large-action-next builder-navigation-large-action-disabled builder-navigation-large-action-next-disabled"><div class="builder-navigation-large-action-text">Next</div><div class="builder-navigation-large-action-icon">{@html disabledIcon("chevron-right")}</div></div>
        </div>
      {/if}
    </div>

    <div class="styles_portraitName__2l8+P">
      <div class="styles_nameContainer__peMda">
        <div><div class="ddbc-character-avatar__portrait styles_avatar__l+g1X {avatar ? '' : 'styles_empty__OVu5Y ddbc-character-avatar__portrait--none'}" style={avatar ? `background-image:url("${avatar}")` : ""}></div></div>
        <div class="styles_inputContainer__igbPB">
          <div>
            <label class="form_label__nzG8p" for="ddb-character-name">Character Name</label>
            <input class="form_input__Xyq7o" id="ddb-character-name" spellcheck="false" autocomplete="off" type="text" bind:value={current.character.name} oninput={() => changed(600)} />
          </div>
          <button type="button" class="Button_button__B9Kr5 ButtonVariants_primary__TMQ5y ButtonVariants_text__vKMzd ButtonSizes_medium__uHe8x styles_xx-small__Q1OkG styles_light__kA91w styles_text__BLc8n styles_suggestionButton__zLhxs"
            onclick={() => (suggestions = suggestions.length ? [] : suggestNames())}>{suggestions.length ? "Hide Suggestions" : "Show Suggestions"}</button>
          <!-- DDB's open suggestion list was never captured: own markup until it is -->
          {#if suggestions.length}
            <div class="ddb-name-suggestions">
              {#each suggestions as name}<button type="button" onclick={() => { current.character.name = name; suggestions = []; changed(); }}>{name}</button>{/each}
            </div>
          {/if}
        </div>
      </div>
    </div>
    <hr class="page_divider__MDOC2" />

    {#if step === "home"}<Home />{:else}
    <div>
      {#if step === "class"}<ClassStep />
      {:else if step === "race"}<RaceStep />
      {:else if step === "abilities"}<AbilitiesStep />
      {:else if step === "background"}<BackgroundStep />
      {:else if step === "equipment"}<EquipmentStep />
      {:else}<WhatsNext {open} {href} />
      {/if}
    </div>
    {/if}
  </div>
</div>
{/if}
