<script>
  // Equipment listing in D&D Beyond's manner: search, type and rarity filters, one row per item; a row opens the
  // item pane. The last opened item is remembered for the hub's Continue card.
  import { content } from "../lib/content.svelte.js";
  import { show } from "../lib/pane.svelte.js";
  import { typeCode, itemIcon } from "../lib/items.js";
  import { ITEM_TYPES, book, title } from "../lib/format.js";
  import NoncanonToggle from "../lib/NoncanonToggle.svelte";
  import { canonFilter } from "../lib/noncanon.svelte.js";

  let query = $state("");
  let kind = $state("");
  let rarity = $state("");
  const KINDS = [["", "All types"], ["weapon", "Weapons"], ["armor", "Armor and shields"], ["gear", "Adventuring gear and tools"], ["magic", "Magic items"]];
  const RARITIES = ["common", "uncommon", "rare", "very rare", "legendary", "artifact"];
  const isMagic = (it) => it.rarity && it.rarity !== "none";
  function kindOf(it) {
    const code = typeCode(it);
    if (["M", "R", "A"].includes(code)) return "weapon";
    if (["LA", "MA", "HA", "S"].includes(code)) return "armor";
    return "gear";
  }
  const rows = $derived.by(() => {
    const q = query.trim().toLowerCase();
    return content.items.filter((it) => canonFilter(it) && (!q || it.name.toLowerCase().includes(q))
      && (!kind || (kind === "magic" ? isMagic(it) : kindOf(it) === kind && (kind !== "gear" || !isMagic(it))))
      && (!rarity || it.rarity === rarity));
  });
  const shown = $derived(rows.slice(0, 200));
  const cost = (v) => (v ? (v >= 100 ? `${v / 100} gp` : v >= 10 ? `${v / 10} sp` : `${v} cp`) : "--");
  function open(it) {
    show("item", it.id);
    try {
      const recent = JSON.parse(localStorage.getItem("dnd5e-recent") || "{}");
      recent.equipment = { name: it.name, detail: title(it.rarity && it.rarity !== "none" ? it.rarity : ITEM_TYPES[typeCode(it)] || "Item"), href: `${window.DND5E.base}#/equipment/${it.id}` };
      localStorage.setItem("dnd5e-recent", JSON.stringify(recent));
    } catch (_) { /* private window: no Continue card */ }
  }
  let { openId = null } = $props();
  $effect(() => { if (openId && content.byId.items[openId]) show("item", openId); });
</script>

<section class="listing-page">
  <header class="listing-head">
    <h1>Equipment</h1>
    <p class="dim">Every weapon, armour, piece of gear and magic item from the 2014 books. Click an item for its full text.</p>
  </header>
  <div class="listing-filters">
    <label>Name <input type="search" placeholder="Search equipment names" bind:value={query} /></label>
    <label>Type <select bind:value={kind}>{#each KINDS as [v, l]}<option value={v}>{l}</option>{/each}</select></label>
    <label>Rarity <select bind:value={rarity}><option value="">Any rarity</option>{#each RARITIES as r}<option value={r}>{title(r)}</option>{/each}</select></label>
    <NoncanonToggle />
    <span class="dim listing-count">{rows.length} items{rows.length > shown.length ? `, first ${shown.length} shown` : ""}</span>
  </div>
  <div class="listing-table" role="table">
    <div class="listing-row listing-row--head" role="row"><span></span><span>Name</span><span>Type</span><span>Cost</span><span>Weight</span><span>Source</span></div>
    {#each shown as it (it.id)}
      <div class="listing-row" role="row" tabindex="0" onclick={() => open(it)} onkeydown={(e) => e.key === "Enter" && open(it)}>
        <span class="listing-icon">{#if itemIcon(it)}<img src={itemIcon(it)} alt="" loading="lazy" />{/if}</span>
        <span class="listing-name">{it.name}{#if it.reqAttune}<span class="dim"> · attunement</span>{/if}</span>
        <span>{isMagic(it) ? title(it.rarity) : title(ITEM_TYPES[typeCode(it)] || "Gear")}</span>
        <span>{cost(it.value)}</span>
        <span>{it.weight ? `${it.weight} lb.` : "--"}</span>
        <span class="dim">{book(it.book)}</span>
      </div>
    {/each}
  </div>
</section>
