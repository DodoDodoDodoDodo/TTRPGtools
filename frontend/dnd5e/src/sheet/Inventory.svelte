<script>
  // Inventory tab in DDB's markup: equip slot, name over a meta line, weight, qty, cost, notes,
  // grouped by container. DDB's "Legacy" marker is left out: every item here is 2014.
  import { current, changed } from "../lib/character.svelte.js";
  import { route } from "../lib/router.svelte.js";
  import { show } from "../lib/pane.svelte.js";
  import { content } from "../lib/content.svelte.js";
  import { ddb } from "../lib/ddb.svelte.js";
  import { ITEM_TYPES, title } from "../lib/format.js";
  import Num from "./ddb/Num.svelte";
  import { typeCode, equippable, STACKABLE } from "../lib/items.js";

  const s = $derived(current.sheet);
  const inv = $derived(current.character.inventory || []);
  let filter = $state("all");
  let query = $state("");

  const PROPS = { "2H": "Two-Handed", F: "Finesse", H: "Heavy", L: "Light", LD: "Loading", R: "Reach", T: "Thrown", V: "Versatile", A: "Ammunition", RLD: "Reload", S: "Special" };
  const ARMOR = { LA: "Light Armor", MA: "Medium Armor", HA: "Heavy Armor" };

  const rows = $derived(inv.map((slot, k) => ({ slot, k, item: slot.id ? content.byId.items[slot.id] : null })));
  const containers = $derived(rows.filter((r) => r.item?.containerCapacity && r.slot.uid));
  const inContainer = (r) => r.slot.inside && containers.some((c) => c.slot.uid === r.slot.inside);

  function meta(item) {
    if (!item) return ["Custom"];
    const code = typeCode(item);
    const magic = item.rarity && item.rarity !== "none";
    const base = item.baseItem ? content.byId.items[item.baseItem]?.name : null;
    if (code === "M" || code === "R") return [magic ? title(item.rarity) : null, base || item.name].filter(Boolean);
    if (ARMOR[code]) return [ARMOR[code], magic ? title(item.rarity) : null, base || item.name].filter(Boolean);
    if (code === "S") return ["Shield", magic ? title(item.rarity) : null, base || item.name].filter(Boolean);
    if (magic) return [title(item.rarity), title(ITEM_TYPES[code] || (item.wondrous ? "Wondrous Item" : "Magic Item")), item.reqAttune ? "Attunement" : null].filter(Boolean);
    return ["Gear", title(ITEM_TYPES[code] || "Adventuring Gear")];
  }
  function notes(item) {
    if (!item) return [];
    const code = typeCode(item);
    if (code === "M" || code === "R") {
      const out = [title(item.weaponCategory || ""), ...(item.property || []).map((p) => PROPS[p] || p)];
      if (item.range) out.push(`Range (${item.range})`);
      return out.filter(Boolean);
    }
    if (ARMOR[code]) return [`AC ${item.ac}`, item.strength ? `Str ${item.strength}` : null, item.stealth ? "Stealth" : null].filter(Boolean);
    if (code === "S") return [`+${item.ac || 2} AC`];
    return item.ddbTags || [];
  }
  const cost = (item) => (item?.value ? +(item.value / 100).toFixed(2) : "--");
  const weightOf = (r) => (r.item?.weight ?? r.slot.custom?.weight ?? 0) * (r.slot.qty || 1);

  function matches(r) {
    if (!query.trim()) return true;
    const q = query.trim().toLowerCase();
    return [r.item?.name || r.slot.custom?.name, ...meta(r.item), ...notes(r.item)].join(" ").toLowerCase().includes(q);
  }
  const groups = $derived.by(() => {
    const carried = rows.filter((r) => !inContainer(r) && matches(r));
    const list = [{ key: "equipment", name: "Equipment", rows: carried }];
    for (const c of containers) list.push({ key: c.slot.uid, name: c.item.name, rows: rows.filter((r) => r.slot.inside === c.slot.uid && matches(r)) });
    if (filter === "equipment") return list.slice(0, 1);
    if (filter === "backpack") return list.slice(1);
    if (filter === "attunement") return [{ key: "attune", name: "Attunement", rows: rows.filter((r) => r.item?.reqAttune && matches(r)) }];
    if (filter === "other") return [{ key: "other", name: "Other Possessions", rows: rows.filter((r) => !equippable(r.item) && !r.item?.containerCapacity && matches(r)) }];
    return list;
  });

  function toggleEquip(r) {
    r.slot.equipped = !r.slot.equipped;
    changed(150);
  }
  const coins = $derived(["pp", "gp", "ep", "sp", "cp"].filter((c) => s.currency[c]));
</script>

<section class="ct-equipment">
  <div class="ct-equipment__overview">
    <div class="styles_equipmentOverview__YvsSD">
      <button type="button" class="Button_button__B9Kr5 ButtonVariants_primary__TMQ5y ButtonVariants_text__vKMzd ButtonSizes_x-small__AQ7c6 styles_x-small__8tmZN styles_themed__AiJUu"
        onclick={() => show("encumbrance", route.id)}>
        <div class="styles_weightButton__CvZQT">
          <span>Weight Carried: <span class="styles_numberDisplay__Rg1za styles_weight__XXeps"><span>{s.encumbrance.weight}</span><span class="styles_label__L8mZK styles_labelSignColor__Klmbs">lb.</span></span></span>
          <span class="styles_weightSecondaryText__ezwvR">{s.encumbrance.status ? title(s.encumbrance.status) : "Unencumbered"}</span>
        </div>
      </button>
      <div role="button" tabindex="0" class="ct-currency-button__currency" onclick={() => show("currency", route.id)} onkeydown={(e) => e.key === "Enter" && show("currency", route.id)}>
        <div class="ct-currency-button__currency-items">
          {#each coins.length ? coins : ["gp"] as c}
            <div class="ct-currency-button__currency-item-count" role="listitem">
              <span class="ddbc-tooltip ct-currency-button__currency-item"><span class="ct-currency-button__currency-item-count">{s.currency[c] || 0}</span>
                <span class="ct-currency-button__currency-item-preview ddb-coin ddb-coin--{c}" aria-label={c.toUpperCase()}>{c.toUpperCase()}</span></span>
            </div>
          {/each}
        </div>
      </div>
    </div>
  </div>
  <div class="ct-equipment__filter">
    <div class="ct-inventory-filter">
      <div class="ct-inventory-filter__interactions">
        <div class="ct-inventory-filter__box">
          <div class="ct-inventory-filter__primary">
            <div class="ct-inventory-filter__primary-group ct-inventory-filter__primary-group--first"><div class="ct-inventory-filter__icon"></div></div>
            <div class="ct-inventory-filter__field"><input class="ct-inventory-filter__input" type="search" placeholder="Search Item Names, Types or Rarities" bind:value={query} aria-label="Search items" /></div>
          </div>
        </div>
        <div class="ct-inventory-filter__callout">
          <button type="button" class="ct-theme-button ct-theme-button--outline ct-theme-button--interactive ct-button character-button ddbc-button character-button-medium" onclick={() => show("inventory", route.id)}>
            <span class="ct-button__content">Manage Inventory</span>
          </button>
        </div>
      </div>
    </div>
  </div>
  <div class="styles_tabFilter__jcVsE"><div class="styles_tabFilter__50iSv">
    <div class="styles_buttons__hGhtB">
      {#each [["all", "All"], ["equipment", "Equipment"], ["backpack", "Backpack"], ["attunement", "Attunement"], ["other", "Other Possessions"]] as [key, label]}
        <button type="button" class={filter === key ? "styles_active__oWpHc" : ""} onclick={() => (filter = key)}>{label}</button>
      {/each}
    </div>
    <div class="styles_content__QjnYw">
      <div class="ct-inventory__row-header">
        <div class="ct-inventory__col ct-inventory__col--active">Active</div>
        <div class="ct-inventory__col ct-inventory__col--name">Name</div>
        <div class="ct-inventory__col ct-inventory__col--weight">Weight</div>
        <div class="ct-inventory__col ct-inventory__col--qty">Qty</div>
        <div class="ct-inventory__col ct-inventory__col--cost">Cost (gp)</div>
        <div class="ct-inventory__col ct-inventory__col--notes">Notes</div>
      </div>
      {#each groups as g (g.key)}
        <div class="ct-content-group">
          <div class="ct-content-group__header"><div class="ct-content-group__header-content">
            <div class="ct-equipment__container ct-inventory-item" role={["attune", "other"].includes(g.key) ? null : "button"} tabindex={["attune", "other"].includes(g.key) ? null : 0}
              onclick={() => !["attune", "other"].includes(g.key) && show("container", g.key)} onkeydown={(e) => e.key === "Enter" && !["attune", "other"].includes(g.key) && show("container", g.key)}>
              <div class="ct-equipment__container-action ct-inventory-item__action"></div>
              <div class="ct-equipment__container-name ct-inventory-item__name">{g.name} <span class="ct-equipment__container-quantity">({g.key === "attune" && s.attunement ? `${s.attunement.used} of ${s.attunement.max} attuned` : g.rows.length})</span></div>
              <div class="ct-equipment__container-weight ct-inventory-item__weight"><Num value={+g.rows.reduce((n, r) => n + weightOf(r), 0).toFixed(2)} unit="lb." /></div>
            </div>
          </div></div>
          <div class="ct-content-group__content"><div class="ct-inventory"><div class="ct-inventory__items">
            {#each g.rows as r (r.k)}
              {@const item = r.item}
              <div class="ct-inventory-item" role="button" tabindex="0" onclick={() => item && show("item", item.id, { slot: r.k })} onkeydown={(e) => e.key === "Enter" && item && show("item", item.id, { slot: r.k })}>
                <div class="ct-inventory-item__action">
                  <div class="ct-item-slot-manager">
                    {#if equippable(item)}
                      <div class="ct-slot-manager ct-slot-manager--size-small">
                        <div role="checkbox" tabindex="0" aria-checked={!!r.slot.equipped} aria-label="Equipped" class="ct-slot-manager__slot ct-slot-manager__slot--interactive {r.slot.equipped ? 'ct-slot-manager__slot--used' : ''}"
                          onclick={(e) => { e.stopPropagation(); toggleEquip(r); }} onkeydown={(e) => { if (e.key === "Enter" || e.key === " ") { e.stopPropagation(); toggleEquip(r); } }}></div>
                      </div>
                    {:else}
                      <div class="ct-item-slot-manager--empty">--</div>
                    {/if}
                  </div>
                </div>
                <div class="ct-inventory-item__name">
                  <div class="ct-inventory-item__heading"><span class="styles_itemName__xLCwW styles_common__4urYa">{item?.name || r.slot.custom?.name}</span>{#if r.slot.attuned} <span class="ddb-attuned" title="Attuned">◆</span>{/if}</div>
                  <div class="ct-inventory-item__meta">{#each meta(item) as m}<span class="ct-inventory-item__meta-item">{m}</span>{/each}</div>
                </div>
                <div class="ct-inventory-item__weight"><span class="ddbc-tooltip">{#if weightOf(r)}<Num value={+weightOf(r).toFixed(2)} unit="lb." />{:else}--{/if}</span></div>
                <div class="ct-inventory-item__quantity"><span class="ddbc-tooltip">{STACKABLE.has(typeCode(item)) || (r.slot.qty || 1) > 1 ? r.slot.qty || 1 : "--"}</span></div>
                <div class="ct-inventory-item__cost"><span class="ddbc-tooltip">{cost(item)}</span></div>
                <div class="ct-inventory-item__notes"><div class="ddbc-note-components">
                  {#each notes(item) as n, i}{#if i}{", "}{/if}<span class="ddbc-note-components__component ddbc-note-components__component--plain">{n}</span>{#if n === "Stealth"} <span class="ddb-disadvantage" aria-label="disadvantage">{@html ddb.icons.disadvantage || "(D)"}</span>{/if}{/each}
                </div></div>
              </div>
            {:else}
              <p class="ddb-empty">Nothing here.</p>
            {/each}
          </div></div></div>
        </div>
      {/each}
      <p class="ddb-inventory-foot"><a href={`#/c/${route.id}/builder/equipment`}>+ Add Equipment</a></p>
    </div>
  </div></div>
</section>
