<script>
  // The newer builder's finish page (play/characters/build/finish) in DDB's markup: "Character Complete" with
  // portrait, name, race · level and class · background, and View Character Sheet. DDB's "Next Steps / How to
  // get started" cards (find a group, find a DM) are replaced by joining a campaign (Dodo, 2026-10-23).
  import Campaigns from "./Campaigns.svelte";
  import { current } from "../lib/character.svelte.js";
  import { content } from "../lib/content.svelte.js";
  import { ddb, useStyles } from "../lib/ddb.svelte.js";
  import { route } from "../lib/router.svelte.js";
  import { raceName } from "../lib/format.js";
  import { ddbName } from "../lib/backgrounds.js";

  $effect(() => useStyles(["foyer.css", "species-cards.css"]));
  const build = `${window.DND5E.ddb}/assets/www.dndbeyond.com/play/characters/build`;
  const icon = (key) => ddb.icons[key] || "";
  const c = $derived(current.character);
  const parts = $derived([
    c.race?.id ? raceName(content.byId.races[c.race.id]?.name || "") : null,
    ...(c.classes || []).map((e) => `Level ${e.level} ${content.byId.classes[e.id]?.name || e.id}`),
    c.background?.id ? ddbName(content.byId.backgrounds[c.background.id]?.name || "") : null,
  ].filter(Boolean));
  const open = $derived(current.sheet?.choices_open || []);
</script>

<div class="ddb-new-builder ddb-finish">
  <div class="styles-module__raWPyq__finishPage" style="--page-background-top: url({build}/finish/top-section.webp); --page-background-bottom: url({build}/finish/cta-section.webp);">
    <div class="styles-module__raWPyq__wideScreenBackground" style="--page-widescreen-image: url({build}/finish/widescreen_background.webp);"></div>
    <div class="styles-module__raWPyq__pageWrapper">
      <div class="styles-module__raWPyq__content">
        <section class="styles-module__raWPyq__section styles-module__raWPyq__characterSummary">
          <div class="styles-module__a0NR4a__characterPortraitWrapper styles-module__raWPyq__characterPortrait"
            style="--portrait-frame: url({build}/portraits/arch.svg); --portrait-mask: url({build}/portraits/mask.svg); --portrait-foreground: url({c.description?.avatar_url || `${build}/portraits/archer-tall.png`});">
            <div class="styles-module__a0NR4a__characterPortrait"><div class="styles-module__a0NR4a__portrait"></div></div>
          </div>
          <div class="styles-module__raWPyq__characterDetails">
            <span class="styles-module__raWPyq__eyebrow">Character Complete</span>
            <h1 title={c.name} class="styles-module__raWPyq__characterHeading">{c.name || "Unnamed"}</h1>
            <p class="styles-module__raWPyq__details">{#each parts as part, i}{#if i}{@html icon("nb-indicator")}{/if}{part}{/each}</p>
            <button type="button" class="Button-module__EPiRJW__baseButton Button-module__EPiRJW__hero Button-module__EPiRJW__large Button-module__EPiRJW__doubleArrow styles-module__raWPyq__createButton"
              onclick={() => (location.hash = `#/c/${route.id}/sheet`)}>
              <span class="Button-module__EPiRJW__capContainer Button-module__EPiRJW__left">{@html icon("nb-hero-lg-cap-left")}</span>
              <span class="Button-module__EPiRJW__content">{@html icon("nb-sheet")}View Character Sheet</span>
              <span class="Button-module__EPiRJW__capContainer Button-module__EPiRJW__right">{@html icon("nb-hero-lg-cap-right")}</span>
            </button>
            {#if open.length}
              <a class="ddb-finish-builder" href={`#/c/${route.id}/builder/class`}>{open.length} choice{open.length === 1 ? "" : "s"} still open (skills, spells, equipment…): finish them in the builder &rarr;</a>
            {/if}
          </div>
        </section>
      </div>
      <div class="styles-module__raWPyq__ctaBackdrop"><div class="styles-module__raWPyq__content">
        <section class="styles-module__raWPyq__section styles-module__raWPyq__ctaSection">
          <div><span class="styles-module__raWPyq__eyebrow">Next Steps</span><h2 class="styles-module__raWPyq__ctaTitle">Join a campaign.</h2></div>
          <Campaigns characterId={route.id} />
        </section>
      </div></div>
    </div>
  </div>
</div>
