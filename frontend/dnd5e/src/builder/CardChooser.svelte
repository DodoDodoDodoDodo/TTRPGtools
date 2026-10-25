<script>
  // DDB's newer-builder cards (play/characters/build/species) for any chooser: race, class, background.
  // groups: [{ name, items: [{ id, name, book }], blurb, book, art, blocked }]. A group with several items
  // opens a "Confirm which ..." panel over its card; DDB's open variant list was never captured, so that
  // panel is our own markup. `learn(id)` (optional) opens the side pane.
  import { ddb, useStyles } from "../lib/ddb.svelte.js";
  import { book } from "../lib/format.js";

  let { heading, groups = [], onpick, learn = null, noun = "option", filterPlaceholder = "What are you looking for?", itemLabel = (it) => it.name } = $props();
  let query = $state("");
  let openGroup = $state(null);
  $effect(() => useStyles(["species-cards.css"]));

  const assets = window.DND5E.ddb;
  // cards without a picture (backgrounds, a few races) get DDB's dark newer-builder texture, so the white titles read
  const FALLBACK_ART = "img/source/ddb-newbuilder-texture-dark.2xzwcuzv5-rrs.png";
  // DDB marks the two 2014 core books "(2014)" since the 2024 printings exist.
  const sourceName = (bookId) => `${book(bookId)}${bookId === "phb" || bookId === "dmg" ? " (2014)" : ""}`.replace(/'/g, "’");
  const shown = $derived(groups.filter((g) => !query.trim() || `${g.name} ${g.items.map((i) => i.name).join(" ")}`.toLowerCase().includes(query.trim().toLowerCase())));

  // The variant panel opens over the card that was clicked, kept inside the window.
  let panelStyle = $state("");
  function openVariants(group, event) {
    const card = event?.currentTarget?.closest("section")?.getBoundingClientRect();
    const width = Math.min(480, window.innerWidth - 32);
    const height = Math.min(window.innerHeight * 0.7, 560, 110 + group.items.length * 38);
    const left = card ? Math.min(Math.max(16, card.left + card.width / 2 - width / 2), window.innerWidth - width - 16) : (window.innerWidth - width) / 2;
    const top = card ? Math.min(Math.max(16, card.top + 24), window.innerHeight - height - 16) : 80;
    panelStyle = `left: ${left}px; top: ${Math.max(16, top)}px;`;
    openGroup = group.name;
  }
  function select(group, event) {
    if (group.blocked) return;
    if (group.items.length === 1) onpick(group.items[0].id);
    else if (openGroup === group.name) openGroup = null;
    else openVariants(group, event);
  }
</script>

<div class="ddb-new-builder ddb-race-chooser">
  <h2 class="ddb-builder-heading">{heading}</h2>
  <input class="ddb-race-filter" type="search" placeholder={filterPlaceholder} bind:value={query} aria-label="Filter" />
  <div class="styles-module__tmzXDW__cardList styles-module__tmzXDW__lg">
    <div class="styles-module__tmzXDW__cards">
      {#each shown as group (group.name)}
        <section class="styles-module__sK4ika__container styles-module__sK4ika__isInteractive" class:ddb-card-blocked={group.blocked}
          style="--background-noise: url({assets}/assets/www.dndbeyond.com/play/characters/build/parchment-white-background.png); --desktop-background-url: url({assets}/{group.art || FALLBACK_ART}); --mobile-background-url: url({assets}/{group.art || FALLBACK_ART});">
          <div class="styles-module__sK4ika__backgroundImageContainer"><div class="styles-module__sK4ika__backgroundImage"></div></div>
          <div class="styles-module__sK4ika__gradient"></div>
          <div class="styles-module__sK4ika__contentWrapper">
            <div class="styles-module__sK4ika__mainContent">
              <h2 class="styles-module__sK4ika__title">{group.name}</h2>
              {#if group.blocked}<p class="styles-module__sK4ika__description ddb-card-blocked-reason">{group.blocked}</p>
              {:else if group.blurb}<p class="styles-module__sK4ika__description">{group.blurb}</p>{/if}
            </div>
            <div class="styles-module__sK4ika__footer">
              <p class="styles-module__sK4ika__sourceName">{sourceName(group.book)}</p>
              <div class="styles-module__sK4ika__cardActions">
                {#if learn}
                  <button type="button" class="Button-module__EPiRJW__baseButton Button-module__EPiRJW__tertiary Button-module__EPiRJW__small"
                    aria-label="Learn more about {group.name}" onclick={() => learn(group.items[0].id)}><span class="Button-module__EPiRJW__content">Learn More</span></button>
                {/if}
                {#if group.items.length > 1}
                  <div>
                    <button type="button" class="Button-module__EPiRJW__baseButton Button-module__EPiRJW__primary Button-module__EPiRJW__small styles-module__sK4ika__popoverButton"
                      aria-label="Expand {group.name} list" aria-expanded={openGroup === group.name} onclick={(e) => (openGroup === group.name ? (openGroup = null) : openVariants(group, e))}>
                      <span class="Button-module__EPiRJW__content">{@html ddb.icons["list-icon"] || ""}<span>({group.items.length})</span></span>
                    </button>
                  </div>
                {/if}
                <button type="button" class="Button-module__EPiRJW__baseButton Button-module__EPiRJW__primary Button-module__EPiRJW__small Button-module__EPiRJW__rightArrow"
                  aria-label="Select {group.name}" disabled={!!group.blocked} onclick={(e) => select(group, e)}>
                  <span class="Button-module__EPiRJW__content">Select</span>{@html ddb.icons["button-cap-right"] || ""}
                </button>
              </div>
            </div>
          </div>
        </section>
      {/each}
    </div>
  </div>
  {#if openGroup}
    {@const group = groups.find((g) => g.name === openGroup)}
    {#if group}
      <div class="ddb-race-variants-backdrop" role="presentation" onclick={(e) => e.target === e.currentTarget && (openGroup = null)}>
        <div class="ddb-race-variants" role="dialog" aria-label="{group.name} options" style={panelStyle}>
          <header><h3>Confirm which {group.name} you want</h3><button type="button" aria-label="Close" onclick={() => (openGroup = null)}>{@html ddb.icons["remove-x"] || "✕"}</button></header>
          <p class="ddb-race-variants-help">{group.name} comes in {group.items.length} versions. Click the one you want to make it your {noun}{learn ? "; Learn More shows it first" : ""}.</p>
          {#each group.items as it (it.id)}
            <div class="ddb-race-variant">
              <button type="button" class="ddb-race-variant-pick" onclick={() => onpick(it.id)}>{itemLabel(it)}</button>
              <span class="ddb-race-variant-book">{book(it.book)}</span>
              {#if learn}<button type="button" class="ddb-race-variant-more" onclick={() => learn(it.id)} aria-label="Learn more about {itemLabel(it)}">Learn More</button>{/if}
            </div>
          {/each}
        </div>
      </div>
    {/if}
  {/if}
</div>
