<script>
  // Spells tab in DDB's markup (ct-spells): casting numbers per class, search, Manage Spells, level tabs and
  // one content group per spell level with its slot boxes. Race and feat spells sit in the same groups with
  // their source as meta. DDB's advanced filter and the ritual icon were never captured and are left out.
  import { current, changed } from "../lib/character.svelte.js";
  import { useSlot, usePact, castAt } from "../lib/play.svelte.js";
  import { route } from "../lib/router.svelte.js";
  import { show } from "../lib/pane.svelte.js";
  import { ddb } from "../lib/ddb.svelte.js";
  import { castingTime, title, raceName } from "../lib/format.js";
  import Num from "./ddb/Num.svelte";
  import { damageOf } from "../lib/spells.js";

  const s = $derived(current.sheet);
  const sc = $derived(s.spellcasting);
  let filter = $state("all");
  let query = $state("");

  const ORDINAL = (n) => `${n}${["th", "st", "nd", "rd"][n % 10 > 3 || [11, 12, 13].includes(n % 100) ? 0 : n % 10]}`;
  const suffix = (n) => ORDINAL(n).slice(String(n).length);
  const UNIT = { action: "A", bonus: "BA", reaction: "R", minute: "m", hour: "h" };
  const USAGE = { "long rest": "LR", "short rest": "SR" };
  const icon = (key) => ddb.icons[key] || "";

  // A spell is listed under its own level when there is a slot of that level, else under the lowest slot level
  // above it (a warlock's 1st-level spells sit under the pact level, as on DDB). Home step "Show Level-Scaled
  // Spells" (on unless switched off) also lists a spell that does more from a higher slot under every higher level.
  const levelScaled = $derived(current.character.preferences?.level_scaled_spells !== false);
  const slotLevels = $derived([...new Set([...(sc.slots || []).filter((sl) => sl.max > 0).map((sl) => sl.level), ...(sc.pact ? [sc.pact.level] : [])])].sort((a, b) => a - b));
  function castLevels(sp) {
    if (sp.level === 0) return [0];
    const above = slotLevels.filter((lv) => lv >= sp.level);
    if (!above.length) return [sp.level];
    return levelScaled && sp.upcast ? above : [above[0]];
  }

  const rows = $derived.by(() => {
    const out = [];
    for (const c of sc.casters || []) {
      for (const sp of c.list) {
        if (!(sp.prepared || sp.always || sp.level === 0 || sp.ritual_only)) continue;
        const row = { ...sp, meta: sp.ritual_only ? `${c.class} · not prepared` : sp.note ? `${c.class} · ${sp.note}` : c.class, attackBonus: c.attack, saveDc: c.save_dc,
          slots: !sp.arcanum && !sp.ritual_only, usage: sp.ritual_only ? "ritual only" : sp.usage };
        for (const lv of row.slots ? castLevels(sp) : [sp.level]) out.push(lv > sp.level ? { ...row, castAt: lv } : row);
      }
    }
    for (const sp of sc.granted || []) {
      const ability = !!sp.ability;
      const row = { ...sp, meta: raceName(sp.source), attackBonus: ability ? sp.attack_bonus : null, saveDc: ability ? sp.save_dc : null, slots: sp.usage === "known" };
      for (const lv of row.slots ? castLevels(sp) : [sp.level]) out.push(lv > sp.level ? { ...row, castAt: lv } : row);
    }
    return out;
  });
  const levels = $derived([...new Set(rows.map((r) => r.castAt || r.level))].sort((a, b) => a - b));

  const searchText = (sp) => [sp.name, castingTime(sp.time), ...(sp.damage_types || []), ...(sp.conditions || []), sp.meta,
    sp.concentration ? "concentration" : "", sp.ritual ? "ritual" : ""].join(" ").toLowerCase();
  function shownIn(level) {
    const q = query.trim().toLowerCase();
    return rows.filter((r) => (r.castAt || r.level) === level && (!q || searchText(r).includes(q))
      && (filter === "all" || filter === level || (filter === "concentration" && r.concentration) || (filter === "ritual" && r.ritual)));
  }

  function rangeView(r) {
    const d = r?.distance || {};
    if (!r || r.type === "special") return { origin: "Special" };
    if (d.type === "self") return r.type === "point" ? { origin: "Self" } : { origin: "Self", value: d.amount };
    if (d.type === "touch" || d.type === "sight" || d.type === "unlimited") return { origin: title(d.type) };
    if (d.type === "miles") return { value: d.amount, unit: d.amount === 1 ? "mile" : "miles" };
    return { value: d.amount };
  }
  const activation = (time) => (time || []).map((t) => `${t.number}${UNIT[t.unit] || t.unit}`).join("/");
  // race/feat spells and Mystic Arcanum: their uses are counters (character.py), ticked here
  const counterOf = (sp) => sp.counter && s.counters.find((c) => c.name === sp.counter);
  function useCounter(counter, n) {
    const play = current.character.play;
    play.counters_used = { ...(play.counters_used || {}), [counter.name]: counter.used >= n ? n - 1 : n };
    changed(150);
  }
  const usageShort = (u) => u.replace(/^(\d+)\/(long rest|short rest)$/, (_, n, r) => `${n}/${USAGE[r]}`);
</script>

{#snippet casting(level)}
  {@const slot = (sc.slots || []).find((sl) => sl.level === level && sl.max > 0)}
  <div class="ct-spells-level-casting">
    {#if level > 0 && (slot || sc.pact?.level === level)}
      <div class="ct-spells-level-casting__slot-groups">
        {#if slot}
          <div class="ct-spells-level-casting__slot-group">
            <div class="ct-spells-level-casting__slot-group-manager"><div class="ct-slot-manager ct-slot-manager--size-small">
              {#each Array.from({ length: slot.max }, (_, k) => k + 1) as n}
                <div role="checkbox" tabindex="0" aria-checked={slot.used >= n} aria-label="use" class="ct-slot-manager__slot ct-slot-manager__slot--interactive" class:ct-slot-manager__slot--used={slot.used >= n}
                  onclick={() => useSlot(level, n)} onkeydown={(e) => e.key === "Enter" && useSlot(level, n)}></div>
              {/each}
            </div></div>
            <div class="ct-spells-level-casting__slot-group-label">Slots</div>
          </div>
        {/if}
        {#if sc.pact?.level === level}
          <div class="ct-spells-level-casting__slot-group ct-spells-level-casting__slot-group--pact">
            <div class="ct-spells-level-casting__slot-group-manager"><div class="ct-slot-manager ct-slot-manager--size-small">
              {#each Array.from({ length: sc.pact.count }, (_, k) => k + 1) as n}
                <div role="checkbox" tabindex="0" aria-checked={sc.pact.used >= n} aria-label="use" class="ct-slot-manager__slot ct-slot-manager__slot--interactive" class:ct-slot-manager__slot--used={sc.pact.used >= n}
                  onclick={() => usePact(n)} onkeydown={(e) => e.key === "Enter" && usePact(n)}></div>
              {/each}
            </div></div>
            <div class="ct-spells-level-casting__slot-group-label">Pact</div>
          </div>
        {/if}
      </div>
    {/if}
  </div>
{/snippet}

{#snippet spellRow(sp)}
  {@const rv = rangeView(sp.range)}
  {@const dice = damageOf(sp, s.level)}
  <div class="ct-spells-spell" role="button" tabindex="0" onclick={() => show("spell", sp.id, sp)} onkeydown={(e) => e.key === "Enter" && show("spell", sp.id, sp)}>
    <div class="ct-spells-spell__action">
      {#if sp.level === 0 || sp.usage === "at will"}<span class="ct-spells-spell__at-will">At Will</span>
      {:else if sp.slots}
        <button class="ct-theme-button ct-theme-button--filled ct-theme-button--interactive ct-button character-button ddbc-button character-button-block-small" type="button"
          onclick={(e) => { e.stopPropagation(); castAt(sp.castAt || sp.level); }}>
          <span class="ct-button__content"><span class="ct-spells-spell__scaled"><span class="ct-spells-spell__scaled-level"><span class="ct-spells-spell__scaled-level-number">{sp.level}</span><span class="ct-spells-spell__scaled-level-ordinal">{suffix(sp.level)}</span></span></span>Cast</span>
        </button>
      {:else if counterOf(sp)}
        {@const counter = counterOf(sp)}
        <div class="ct-slot-manager ct-slot-manager--size-small" title="{sp.usage || counter.max + '/' + counter.reset + ' rest'}">
          {#each Array.from({ length: counter.max }, (_, k) => k + 1) as n}
            <div role="checkbox" tabindex="0" aria-checked={counter.used >= n} aria-label="use" class="ct-slot-manager__slot ct-slot-manager__slot--interactive {counter.used >= n ? 'ct-slot-manager__slot--used' : ''}"
              onclick={(e) => { e.stopPropagation(); useCounter(counter, n); }} onkeydown={(e) => e.key === "Enter" && useCounter(counter, n)}></div>
          {/each}
        </div>
      {:else}<span class="ct-spells-spell__at-will">{usageShort(sp.usage)}</span>{/if}
    </div>
    <div class="ct-spells-spell__name">
      <div class="ct-spells-spell__label" class:ct-spells-spell__label--scaled={sp.castAt}><span class="styles_spellName__wX3ll">{sp.name}{#if sp.concentration}<div class="styles_concentrationIcon__BsaNr styles_icon__Heo9G" title="Concentration">{@html icon("concentration") || "C"}</div>{/if}</span></div>
      <div class="ct-spells-spell__meta"><span class="ct-spells-spell__meta-item">{sp.meta}</span>{#if sp.ritual}<span class="ct-spells-spell__meta-item">Ritual</span>{/if}</div>
    </div>
    <div class="ct-spells-spell__activation"><span class="ddbc-tooltip" title={castingTime(sp.time)}>{activation(sp.time)}</span></div>
    <div class="ct-spells-spell__range">
      {#if rv.origin}<span class="ct-spells-spell__range-origin">{rv.origin}</span>{/if}
      {#if rv.value}<span class="ct-spells-spell__range-value"><Num value={rv.value} unit={rv.unit || "ft."} /></span>{/if}
    </div>
    <div class="ct-spells-spell__attacking">
      {#if sp.attack && sp.attackBonus != null}<div class="ct-spells-spell__tohit"><button type="button" class="F8U5pq_button integrated-dice__container" onclick={(e) => e.stopPropagation()}><Num value={sp.attackBonus} /></button></div>
      {:else if sp.save && sp.saveDc != null}<div class="ct-spells-spell__save"><span class="ct-spells-spell__save-label">{sp.save.slice(0, 3)}</span><span class="ct-spells-spell__save-value">{sp.saveDc}</span></div>
      {:else}<div class="ct-spells-spell__empty-value">--</div>{/if}
    </div>
    <div class="ct-spells-spell__damage">
      <div class="ddbc-spell-damage-effect" class:ddbc-spell-damage-effect--scaled={sp.castAt && sp.scaledamage}>
        {#if dice}
          <span class="ddbc-spell-damage-effect__damages"><button type="button" class="F8U5pq_button integrated-dice__container" onclick={(e) => e.stopPropagation()}>
            <span class="ddbc-damage__value">{dice}</span>
            {#if sp.damage_types?.[0]}<span class="ddbc-damage__icon"><span class="ddbc-damage-type-icon ddbc-damage-type-icon--{sp.damage_types[0]}" aria-label="{sp.damage_types[0]} damage"><span class="ddbc-tooltip" title={sp.damage_types[0]}>{@html icon(`damage-type-icon__img--${sp.damage_types[0]}`) || sp.damage_types[0]}</span></span></span>{/if}
          </button></span>
        {:else if sp.conditions?.length}<span class="ddbc-spell-damage-effect__conditions"><span class="ddbc-tooltip">{sp.conditions.map(title).join(", ")}</span></span>
        {:else}<span class="ct-spells-spell__empty-value">--</span>{/if}
      </div>
    </div>
  </div>
{/snippet}

{#if !sc.casters.length && !sc.granted?.length}
  <p class="hint">No spellcasting.</p>
{:else}
  <section class="ct-spells">
    <h2 class="accessibility_screenreaderOnly__OEzRB">Spells</h2>
    {#if sc.casters.length}
      <div class="ct-spells__casting"><div class="ct-spells-level-casting"><div class="ct-spells-level-casting__info">
        {#each [["Modifier", (c) => c.attack - s.proficiency_bonus, true], ["Spell Attack", (c) => c.attack, true], ["Save DC", (c) => c.save_dc, false]] as [label, value, signedNum]}
          <div class="ct-spells-level-casting__info-group">
            <div class="ct-spells-level-casting__info-items">
              {#each sc.casters as c (c.class_id)}<span class="ddbc-tooltip ct-spells-level-casting__info-item" title={c.class}>{#if signedNum}<Num value={value(c)} />{:else}{value(c)}{/if}</span>{/each}
            </div>
            <div class="ct-spells-level-casting__info-label">{label}</div>
          </div>
        {/each}
      </div></div></div>
    {/if}
    <div class="ct-spells-filter"><div class="ct-spells-filter__interactions">
      <div class="ct-spells-filter__box"><div class="ct-spells-filter__primary">
        <div class="ct-spells-filter__primary-group ct-spells-filter__primary-group--first"><div class="ct-spells-filter__icon"></div></div>
        <div class="ct-spells-filter__field"><input class="ct-spells-filter__input" placeholder="Search Spell Names, Casting Times, Damage Types, Conditions or Tags" type="search" bind:value={query} /></div>
      </div></div>
      <div class="ct-spells-filter__callout">
        <button class="ct-theme-button ct-theme-button--outline ct-theme-button--interactive ct-button character-button ddbc-button character-button-medium" type="button"
          onclick={() => (location.hash = `#/c/${route.id}/builder/class`)}><span class="ct-button__content">Manage Spells</span></button>
      </div>
    </div></div>
    <div class="ct-spells__content">
      <div class="styles_tabFilter__50iSv styles_tabFilter__kfTU6">
        <div class="styles_buttons__hGhtB" data-testid="tab-filters">
          <button type="button" class={filter === "all" ? "styles_active__oWpHc" : ""} onclick={() => (filter = "all")}>All</button>
          {#each levels as lv}<button type="button" class={filter === lv ? "styles_active__oWpHc" : ""} onclick={() => (filter = lv)}>{lv === 0 ? "- 0 -" : ORDINAL(lv)}</button>{/each}
          {#if rows.some((r) => r.concentration)}
            <button type="button" class={filter === "concentration" ? "styles_active__oWpHc" : ""} aria-label="Concentration" onclick={() => (filter = "concentration")}><div class="styles_concentrationIcon__BsaNr" title="Concentration">{@html icon("concentration") || "C"}</div></button>
          {/if}
          {#if rows.some((r) => r.ritual)}
            <button type="button" class={filter === "ritual" ? "styles_active__oWpHc" : ""} onclick={() => (filter = "ritual")}>Ritual</button>
          {/if}
        </div>
        <div class="styles_content__QjnYw">
          {#each levels as lv}
            {@const list = shownIn(lv)}
            {#if list.length}
              <div class="ct-content-group">
                <div class="ct-content-group__header">
                  <div class="ct-content-group__header-content">{lv === 0 ? "Cantrip" : `${ORDINAL(lv)} Level`}</div>
                  <div class="ct-content-group__header-extra">{@render casting(lv)}</div>
                </div>
                <div class="ct-content-group__content"><div class="ct-spells-level">
                  <div class="ct-spells-level__spells-row-header">
                    <div class="ct-spells-level__spells-col ct-spells-level__spells-col--action"></div>
                    <div class="ct-spells-level__spells-col ct-spells-level__spells-col--name">Name</div>
                    <div class="ct-spells-level__spells-col ct-spells-level__spells-col--activation">Time</div>
                    <div class="ct-spells-level__spells-col ct-spells-level__spells-col--range">Range</div>
                    <div class="ct-spells-level__spells-col ct-spells-level__spells-col--tohit">Hit / DC</div>
                    <div class="ct-spells-level__spells-col ct-spells-level__spells-col--damage">Effect</div>
                  </div>
                  <div class="ct-spells-level__spells-content">
                    {#each list as sp (sp.id + sp.meta + (sp.castAt || ""))}{@render spellRow(sp)}{/each}
                  </div>
                </div></div>
              </div>
            {/if}
          {/each}
        </div>
      </div>
    </div>
  </section>
{/if}
