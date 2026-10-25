<script>
  // Race chooser: DDB's newer species cards (one per base race, variants in a panel) or, with the old
  // design, a plain list grouped by base race.
  import CardChooser from "./CardChooser.svelte";
  import { content, sourceAllowed } from "../lib/content.svelte.js";
  import { current } from "../lib/character.svelte.js";
  import { design } from "../lib/design.svelte.js";
  import { show } from "../lib/pane.svelte.js";
  import { book, raceName } from "../lib/format.js";

  let { onpick } = $props();
  let query = $state("");
  const CORE = new Set(["phb", "dmg"]);
  const rank = (r) => (r.book === "phb" ? 0 : r.book === "dmg" ? 1 : 2);
  const groups = $derived.by(() => {
    const map = new Map();
    for (const r of content.races) {
      if (!sourceAllowed(r.book, current.character.preferences)) continue;
      if (!map.has(r.group)) map.set(r.group, []);
      map.get(r.group).push(r);
    }
    return [...map.entries()].map(([name, races]) => {
      races.sort((a, b) => rank(a) - rank(b) || a.name.length - b.name.length);
      return { name, items: races, book: races[0].book, blurb: races[0].groupBlurb || races[0].blurb,
        art: races.find((r) => r.ddbArt)?.ddbArt, core: races.some((r) => CORE.has(r.book)) };
    }).sort((a, b) => (a.core ? 0 : 1) - (b.core ? 0 : 1) || a.name.localeCompare(b.name));
  });
  const listed = $derived(groups.filter((g) => !query.trim() || `${g.name} ${g.items.map((r) => r.name).join(" ")}`.toLowerCase().includes(query.trim().toLowerCase())));
</script>

{#if design.mode === "new"}
  <CardChooser heading="Choose a Race" {groups} {onpick} noun="race" learn={(id) => show("race", id)} itemLabel={(r) => raceName(r.name)} />
{:else}
  <div class="ddb-old-chooser">
    <h2 class="ddb-builder-heading">Choose a Race</h2>
    <input class="ddb-race-filter" type="search" placeholder="Filter races by name" bind:value={query} aria-label="Filter races" />
    {#each listed as g (g.name)}
      <section class="ddb-old-group">
        <h3>{g.name}</h3>
        {#each g.items as r (r.id)}
          <div class="ddb-old-row">
            <button type="button" class="ddb-old-pick" onclick={() => onpick(r.id)}>{raceName(r.name)}</button>
            <span class="ddb-old-book">{book(r.book)}</span>
            <button type="button" class="ddb-old-more" onclick={() => show("race", r.id)}>Details</button>
          </div>
        {/each}
      </section>
    {/each}
  </div>
{/if}
