<script>
  import PlotholePopup from "./sheet/PlotholePopup.svelte";
  import CampaignsPage from "./pages/CampaignsPage.svelte";
  import EquipmentPage from "./pages/EquipmentPage.svelte";
  import RulesPage from "./pages/RulesPage.svelte";
  import DesignToggle from "./builder/DesignToggle.svelte";
  import { onMount } from "svelte";
  import { route, go } from "./lib/router.svelte.js";
  import { content, loadContent } from "./lib/content.svelte.js";
  import { current, openCharacter, reload } from "./lib/character.svelte.js";
  import Pane from "./lib/Pane.svelte";
  import List from "./List.svelte";
  import Builder from "./builder/Builder.svelte";
  import Sheet from "./sheet/Sheet.svelte";
  import Print from "./sheet/Print.svelte";

  onMount(loadContent);

  $effect(() => {
    if (route.id) openCharacter(route.id);
  });

  // dodo-dodo premium (Dodo, 2026-10-23): on a phone every page says the dedicated mobile layout is premium and
  // links the pitch-in section. Same phone test as the sheet; without premium the sheet is the zoomed-out desktop one.
  const onPhone = window.screen.width < 1220;
  const zoomedSheet = $derived(onPhone && window.DND5E.premium === false && route.view === "sheet");
  // the phone sheet's fixed header sits under the top bar; with the premium line it moves down by the line's height
  $effect(() => {
    document.documentElement.classList.toggle("has-premium-line", onPhone && !zoomedSheet);
  });
  const STATUS = { saving: "Saving…", saved: "Saved", error: "Not saved", conflict: "Changed elsewhere", locked: "Read only, not saved", idle: "" };
</script>

<header class="topbar no-print">
  <a class="brand-logo" href={window.DND5E.start} aria-label="Dodo Beyond: start page"><span class="brand-top">Dodo</span><span class="brand-bottom">Beyond</span></a>
  {#if !route.id}
    <nav class="topbar-nav" aria-label="D&D 5e">
      <a href="#/" class:active={route.view === "list"}>Characters</a>
      <a href={window.DND5E.encounters}>Encounters</a>
      <a href="#/campaigns" class:active={route.view === "campaigns"}>Campaigns</a>
      <a href="#/equipment" class:active={route.view === "equipment"}>Equipment</a>
      <a href={window.DND5E.start + "monsters"}>Monsters</a>
      <a href="#/rules" class:active={route.view === "rules"}>Other</a>
    </nav>
  {/if}
  {#if route.id && current.character}
    <span class="char-name">{current.character.name || "Unnamed"}</span>
    <nav class="view-switch" aria-label="Character view">
      <a href={`#/c/${route.id}/builder`} class:active={route.view === "builder"}>Builder</a>
      <a href={`#/c/${route.id}/sheet`} class:active={route.view === "sheet"}>Sheet</a>
    </nav>
    <span class="save-status status-{current.status}" title={current.error || ""}>{STATUS[current.status]}</span>
  {/if}
  <span class="grow"></span>
  <DesignToggle />
  {#if route.id}<a class="topbar-encounters" href={window.DND5E.encounters}>Encounters</a>{/if}
  <a href={window.DND5E.hub}>&larr; <span class="topbar-long">Back to /</span>TTRPG</a>
</header>

{#if onPhone}
  <a class="topbar-premium no-print" class:topbar-premium--zoomed={zoomedSheet} href="/#contrib">Dedicated mobile layout is a dodo-dodo premium feature</a>
{/if}

<PlotholePopup />
{#if current.locked && route.id}
  <div class="banner error ddb-locked">{current.locked} <a class="button pitch-in" href="/#contrib">Pitch in · get dodo-dodo premium</a></div>
{/if}
{#if current.status === "conflict"}
  <div class="banner warn">
    Another tab or player saved this character after you opened it. Your last change was not saved.
    <button type="button" onclick={reload}>Reload their version</button>
  </div>
{:else if current.status === "error" && current.error}
  <div class="banner error">Error: {current.error}</div>
{/if}

<main class="app-main" class:print-main={route.view === "print"}>
  {#if content.error}
    <p class="banner error">The builder data could not be loaded: {content.error}</p>
  {:else if !content.ready}
    <p class="loading">Loading rules data (classes, races, spells, items)…</p>
  {:else if route.view === "list"}
    <List />
  {:else if route.view === "campaigns"}
    <CampaignsPage focus={route.step} />
  {:else if route.view === "equipment"}
    <EquipmentPage openId={route.step} />
  {:else if route.view === "rules"}
    <RulesPage />
  {:else if !current.character}
    <p class="loading">{current.error ? `Error: ${current.error}` : "Loading character…"}</p>
  {:else if route.view === "builder"}
    <Builder />
  {:else if route.view === "print"}
    <Print />
  {:else}
    <Sheet />
  {/if}
</main>

<Pane />
