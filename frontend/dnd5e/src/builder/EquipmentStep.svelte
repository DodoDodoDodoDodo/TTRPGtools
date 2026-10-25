<script>
  // Equipment step in DDB's markup (equipment-manage): five collapsible sections, Starting Equipment,
  // Current Inventory (paper card per item: picture, rarity-coloured name, Wield/Wear/Use button, details
  // with Equip and Remove Item), Other Possessions, Add Items and Currency. Only the inventory was open in
  // the capture; the other sections' insides follow the same parts.
  import Entries from "../lib/Entries.svelte";
  import Tagged from "../lib/Tagged.svelte";
  import { content, itemByRef, sourceAllowed } from "../lib/content.svelte.js";
  import { current, changed } from "../lib/character.svelte.js";
  import { ddb } from "../lib/ddb.svelte.js";
  import { show } from "../lib/pane.svelte.js";
  import { book, itemType, title } from "../lib/format.js";
  import { typeCode, equippable, itemIcon, packSlots } from "../lib/items.js";
  import NoncanonToggle from "../lib/NoncanonToggle.svelte";
  import { canonFilter } from "../lib/noncanon.svelte.js";

  $effect.pre(() => {
    current.character.inventory ??= [];
    current.character.currency ??= {};
    current.character.description ??= {};
  });
  const inv = $derived(current.character.inventory || []);
  const coins = $derived(current.character.currency || {});

  const starting = $derived(content.byId.classes[current.character.classes?.[0]?.id]);
  const background = $derived(content.byId.backgrounds[current.character.background?.id]);
  let picks = $state({});
  let query = $state("");
  let typeFilter = $state("");
  let open = $state({ starting: false, inventory: true, possessions: false, add: false, currency: false });

  const results = $derived.by(() => {
    const q = query.trim().toLowerCase();
    if (q.length < 2 && !typeFilter) return [];
    return content.items
      .filter((i) => canonFilter(i) && sourceAllowed(i.book, current.character.preferences) && (!q || i.name.toLowerCase().includes(q)) && (!typeFilter || typeCode(i).startsWith(typeFilter) || (typeFilter === "W" && i.wondrous)))
      .slice(0, 60);
  });

  function groups(data) {
    return (data || []).map((g, k) => ({ key: k, options: Object.entries(g) }));
  }
  function describe(entry) {
    if (typeof entry === "string") return itemByRef(entry)?.name || title(entry.split("|")[0]);
    if (entry.item) return `${entry.quantity ? entry.quantity + " × " : ""}${entry.displayName || itemByRef(entry.item)?.name || entry.item.split("|")[0]}`;
    if (entry.equipmentType) return `any ${entry.equipmentType.replace(/([A-Z])/g, " $1").toLowerCase()} (add it under Add Items)`;
    if (entry.special) return `${entry.quantity ? entry.quantity + " × " : ""}${entry.special}`;
    if (entry.value) return `${entry.value / 100} gp`;
    if (entry.containsValue) return `${entry.containsValue / 100} gp`;
    return "";
  }
  function addEntries(list) {
    for (const entry of list) {
      if (typeof entry === "string") addItem(itemByRef(entry), 1);
      else if (entry.item) {
        const it = itemByRef(entry.item);
        if (it) addItem(it, entry.quantity || 1);
        if (entry.containsValue) coins.gp = (Number(coins.gp) || 0) + entry.containsValue / 100;
      } else if (entry.special) inv.push({ custom: { name: entry.special, weight: 0 }, qty: entry.quantity || 1 });
      else if (entry.value) coins.gp = (Number(coins.gp) || 0) + entry.value / 100;
    }
  }
  function addPackage(data, prefix) {
    groups(data).forEach((g) => {
      const chosen = g.options.length === 1 ? g.options[0] : g.options.find(([k]) => k === picks[`${prefix}${g.key}`]);
      if (chosen) addEntries(chosen[1]);
    });
    open.inventory = true;
    changed();
  }
  function addItem(item, qty = 1) {
    if (!item) return;
    if (item.packContents) { for (let k = 0; k < qty; k++) inv.push(...packSlots(item, itemByRef)); changed(); return; }
    const existing = inv.find((s) => s.id === item.id && !s.equipped);
    if (existing && !["M", "R", "LA", "MA", "HA", "S"].includes(typeCode(item))) existing.qty = (existing.qty || 1) + qty;
    else inv.push({ id: item.id, qty, equipped: false, attuned: false, uid: Math.random().toString(36).slice(2, 10) });
    changed();
  }
  const itemOf = (slot) => (slot.id ? content.byId.items[slot.id] : null);
  const totalWeight = $derived(current.sheet?.encumbrance?.weight ?? 0);

  // DDB's rarity classes (hashed names from its stylesheet) and its Wield / Wear / Use wording
  const RARITY = { common: "styles_common__4urYa", uncommon: "styles_uncommon__L6lbB", rare: "styles_rare__ort-Y",
    "very rare": "styles_veryrare__rmBCl", legendary: "styles_legendary__h1DkF", artifact: "styles_artifact__K9nvQ" };
  const rarityClass = (it) => RARITY[it?.rarity] || RARITY.common;
  function verb(it, equipped) {
    const code = typeCode(it);
    if (["M", "R"].includes(code)) return equipped ? "Wielding" : "Wield";
    if (["LA", "MA", "HA", "S"].includes(code)) return equipped ? "Wearing" : "Wear";
    return equipped ? "Using" : "Use";
  }
  const CATEGORY = { M: "Weapon", R: "Weapon", A: "Ammunition", LA: "Armor", MA: "Armor", HA: "Armor", S: "Shield" };
  const metaOf = (it) => [CATEGORY[typeCode(it)] || (it?.wondrous ? "Wondrous Item" : "Gear"), itemType(it)];
  function toggleEquip(slot) {
    slot.equipped = !slot.equipped;
    if (!slot.equipped) slot.attuned = false;
    changed();
  }
  function remove(k) {
    if (!confirm(`Remove ${itemOf(inv[k])?.name || inv[k].custom?.name || "this item"} from the inventory?`)) return;
    inv.splice(k, 1);
    changed();
  }
  const COINS = [["pp", "Platinum"], ["gp", "Gold"], ["ep", "Electrum"], ["sp", "Silver"], ["cp", "Copper"]];
</script>

{#snippet section(key, cls, heading, callout, body)}
  <div class="ddbc-collapsible {cls} {open[key] ? 'ddbc-collapsible--opened' : 'ddbc-collapsible--collapsed'}">
    <div class="ddbc-collapsible__header" role="button" tabindex="0" onclick={() => (open[key] = !open[key])} onkeydown={(e) => e.key === "Enter" && (open[key] = !open[key])}>
      <div class="ddbc-collapsible__header-content ">
        <div class="ddbc-collapsible__header-content-primary"><div class="ddbc-collapsible__heading">{heading}</div></div>
        {#if callout}<div class="ddbc-collapsible__header-content-callout"><div class="equipment-manage__callout">{callout}</div></div>{/if}
      </div>
      <div class="ddbc-collapsible__header-status">{@html ddb.icons[open[key] ? "chevron-up" : "chevron-down"] || ""}</div>
    </div>
    {#if open[key]}<div class="ddbc-collapsible__content">{@render body()}</div>{/if}
  </div>
{/snippet}

{#snippet startingBody()}
  {#each [[starting, "class", starting?.startingEquipment?.defaultData, starting?.startingEquipment?.default], [background, "background", background?.startingEquipment, null]] as [source, prefix, data, text]}
    {#if source && data}
      <div class="ddb-equipment-package">
        <div class="ddb-equipment-package-title">{source.name}</div>
        {#if text}<ul class="ddb-equipment-package-text">{#each text as line}<li><Tagged text={line} /></li>{/each}</ul>{/if}
        {#each groups(data) as g}
          <div class="ddb-equipment-package-group">
            {#if g.options.length === 1}
              <p>{g.options[0][1].map(describe).join(", ")}</p>
            {:else}
              {#each g.options as [key, list]}
                <label class="ddb-equipment-package-option"><input type="radio" name={`${prefix}${g.key}`} checked={picks[`${prefix}${g.key}`] === key} onchange={() => (picks[`${prefix}${g.key}`] = key)} />
                  <span>({key}) {list.map(describe).join(", ")}</span></label>
              {/each}
            {/if}
          </div>
        {/each}
        <button type="button" class=" ct-button character-button ddbc-button character-button-small" role="button" onclick={() => addPackage(data, prefix)}><span class="ct-button__content">Add {source.name} equipment</span></button>
        {#if prefix === "class" && starting.startingEquipment?.goldAlternative}
          <p class="ddb-equipment-gold">Or take gold instead: <Tagged text={starting.startingEquipment.goldAlternative} /> gp; roll it and enter it under Currency.</p>
        {/if}
      </div>
    {/if}
  {:else}
    <p class="ddb-equipment-empty">Choose a class and a background first; their starting equipment appears here.</p>
  {/each}
{/snippet}

{#snippet inventoryBody()}
  {#each inv as slot, k (slot.uid || k)}
    {@const it = itemOf(slot)}
    <details class="styles_details__Kwqwr styles_paper__FhNqH">
      <summary class="styles_summary__BI+UG" data-testid="accordion-summary">
        {#if it && itemIcon(it)}<img class="styles_image__cn+gs" alt={it.name} width="32" src={itemIcon(it)} />{/if}
        <div class="styles_heading__RRl69">
          <div class="styles_summaryContent__xaQWq">
            <span class="styles_itemName__xLCwW {rarityClass(it)}">{it?.name || slot.custom?.name}{#if it?.reqAttune}<span class="styles_icon__cSkYX"><span class=" ddbc-attunement-icon" title="Requires attunement">{@html ddb.icons["attunement"] || ""}</span></span>{/if}</span>
            <div class="styles_metaItems__Pt+Po">{#each it ? metaOf(it) : ["Custom"] as m}<div class="styles_metaItem__+kjrf">{m}</div>{/each}</div>
          </div>
          <div class="styles_actions__1-sml">
            {#if !(it && equippable(it))}
              <div class="equipment-list-item-callout-quantity"><span class="equipment-list-item-callout-quantity-extra">Qty</span><span class="equipment-list-item-callout-quantity-value">{slot.qty || 1}</span></div>
            {/if}
            {#if it && equippable(it)}
              <div class="equipment-list-item-callout-action">
                <button type="button" class="Button_button__B9Kr5 ButtonVariants_primary__TMQ5y {slot.equipped ? '' : 'ButtonVariants_outline__v36Mn'} ButtonSizes_medium__uHe8x styles_xx-small__Q1OkG {slot.equipped ? 'styles_solid__2ijrG' : 'styles_outline__lyFTR'} styles_builder-green__00NLA"
                  onclick={(e) => { e.preventDefault(); toggleEquip(slot); }}>{verb(it, slot.equipped)}</button>
              </div>
            {/if}
          </div>
          {@html ddb.icons["details-chevron"] || ""}
        </div>
      </summary>
      <div class="styles_content__pFYp6">
        <div class=" ct-item-detail">
          <div class="ct-item-detail__intro">{it ? itemType(it) : "Custom item"}{it?.reqAttune ? " (requires attunement)" : ""}</div>
          <div class="ct-item-detail__customize" role="list">
            <div class="styles_item__8bGe2 styles_inline__ufQJr" role="listitem"><p class="styles_label__My0Jp">Quantity:</p>
              <p class="styles_value__mg89v"><input class="ddb-equipment-qty-input" type="number" min="1" value={slot.qty || 1} oninput={(e) => { slot.qty = Math.max(1, Number(e.target.value) || 1); changed(800); }} aria-label="Quantity" /></p></div>
            {#if it?.weight}<div class="styles_item__8bGe2 styles_inline__ufQJr" role="listitem"><p class="styles_label__My0Jp">Weight:</p><p class="styles_value__mg89v">{it.weight} lb.</p></div>{/if}
            {#if it?.value}<div class="styles_item__8bGe2 styles_inline__ufQJr" role="listitem"><p class="styles_label__My0Jp">Cost:</p><p class="styles_value__mg89v">{it.value >= 100 ? `${it.value / 100} gp` : `${it.value / 10} sp`}</p></div>{/if}
            {#if it}<div class="styles_item__8bGe2 styles_inline__ufQJr" role="listitem"><p class="styles_label__My0Jp">Source:</p><p class="styles_value__mg89v">{book(it.book)}</p></div>{/if}
            {#if it?.reqAttune && slot.equipped}
              <div class="styles_item__8bGe2 styles_inline__ufQJr" role="listitem"><p class="styles_label__My0Jp">Attuned:</p>
                <p class="styles_value__mg89v"><input type="checkbox" checked={!!slot.attuned} onchange={(e) => { slot.attuned = e.target.checked; changed(); }} aria-label="Attuned" /></p></div>
            {/if}
          </div>
          {#if it?.entries}<div class="ddbc-html-content ct-item-detail__description ct-item-detail__description--rich"><Entries entries={it.entries} /></div>{/if}
          {#if it}<button type="button" class="ddb-link-button" onclick={() => show("item", it.id, { slot: k })}>Open in the item pane</button>{/if}
        </div>
        <div class="equipment-list-item-actions">
          {#if it && equippable(it)}
            <button type="button" class=" ct-button character-button ddbc-button character-button-small {slot.equipped ? '' : 'character-button-outline'}" role="button" onclick={() => toggleEquip(slot)}><span class="ct-button__content">{slot.equipped ? "Unequip" : "Equip"}</span></button>
          {/if}
          <div class="equipment-list-item-remove" role="button" tabindex="0" onclick={() => remove(k)} onkeydown={(e) => e.key === "Enter" && remove(k)}><span class="equipment-list-item-remove-icon"></span> Remove Item</div>
        </div>
      </div>
    </details>
  {:else}
    <p class="ddb-equipment-empty">Nothing yet: take your starting equipment above or add items below.</p>
  {/each}
{/snippet}

{#snippet possessionsBody()}
  <label class="ddb-equipment-possessions">Things your character owns that are not items on the list: a house, a ship, a debt, a letter.
    <textarea rows="4" value={current.character.description?.possessions || ""} oninput={(e) => { current.character.description.possessions = e.target.value; changed(800); }}></textarea>
  </label>
{/snippet}

{#snippet addBody()}
  <div class="ddb-equipment-search">
    <input type="search" placeholder="Search items (2+ letters)" bind:value={query} aria-label="Search items" />
    <NoncanonToggle />
    <select bind:value={typeFilter} aria-label="Item type">
      <option value="">All types</option>
      <option value="M">Melee weapons</option><option value="R">Ranged weapons</option>
      <option value="LA">Light armor</option><option value="MA">Medium armor</option><option value="HA">Heavy armor</option><option value="S">Shields</option>
      <option value="G">Adventuring gear</option><option value="P">Potions</option><option value="SC">Scrolls</option>
      <option value="RG">Rings</option><option value="WD">Wands</option><option value="RD">Rods</option><option value="W">Wondrous items</option>
    </select>
  </div>
  <div class="ddb-equipment-results">
    {#each results as it (it.id)}
      <div class="ddb-equipment-result">
        {#if itemIcon(it)}<img src={itemIcon(it)} alt="" width="28" />{:else}<span class="ddb-equipment-noimg"></span>{/if}
        <button type="button" class="ddb-equipment-result-name styles_itemName__xLCwW {rarityClass(it)}" onclick={() => show("item", it.id)}>{it.name}</button>
        <span class="ddb-equipment-result-meta">{itemType(it)} · {book(it.book)}</span>
        <button type="button" class=" ct-button character-button ddbc-button character-button-small" role="button" onclick={() => addItem(it)}><span class="ct-button__content">Add</span></button>
      </div>
    {:else}
      {#if query.trim().length >= 2 || typeFilter}<p class="ddb-equipment-empty">No item matches.</p>{/if}
    {/each}
  </div>
{/snippet}

{#snippet currencyBody()}
  <div class="ddb-equipment-coins">
    {#each COINS as [c, label]}
      <label class="ddb-equipment-coin"><span class="ddb-equipment-coin-label">{label} ({c.toUpperCase()})</span>
        <input type="number" min="0" value={coins[c] || 0} oninput={(e) => { coins[c] = Math.max(0, Number(e.target.value) || 0); changed(800); }} /></label>
    {/each}
  </div>
{/snippet}

<div class="builder-page">
  <div class="builder-page-header">Choose Equipment</div>
  <div class="equipment-manage">
    {@render section("starting", "equipment-manage__starting", "Starting Equipment", null, startingBody)}
    {@render section("inventory", "equipment-manage__inventory", `Current Inventory (${inv.length})`, `Total Weight: ${totalWeight} lb`, inventoryBody)}
    {@render section("possessions", "equipment-manage__possessions", "Other Possessions", null, possessionsBody)}
    {@render section("add", "equipment-manage__add-items", "Add Items", null, addBody)}
    {@render section("currency", "equipment-manage__currency", "Currency", null, currencyBody)}
  </div>
</div>
