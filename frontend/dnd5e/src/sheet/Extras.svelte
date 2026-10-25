<script>
  // Extras tab in DDB's markup (ct-extras): filter box, Manage Extras, then one group per kind with DDB's
  // extra-list columns. Only DDB's empty tab was captured; rows use DDB's ct-extra-row classes from its
  // stylesheet. Manage Extras searches the 2014 bestiary; a row opens the creature's block below it.
  import { current, changed } from "../lib/character.svelte.js";
  import { signed } from "../lib/format.js";

  const KINDS = { familiar: "Familiar", companion: "Companion", wildshape: "Wild Shape", other: "Other" };
  $effect.pre(() => {
    current.character.extras ??= [];
  });
  const extras = $derived(current.character.extras || []);
  let filter = $state("");
  let managing = $state(false);
  let query = $state("");
  let kind = $state("familiar");
  let results = $state([]);
  let searching = $state(false);
  let openRow = $state(null);

  async function search(event) {
    event.preventDefault();
    if (query.trim().length < 2) return;
    searching = true;
    const response = await fetch(`${window.DND5E.api}/creatures?q=${encodeURIComponent(query.trim())}`);
    results = response.ok ? await response.json() : [];
    searching = false;
  }
  // PHB p. 66: Wild Shape takes a beast within the druid's CR, swim and fly limits (character.py wild_shape)
  const CR = (m) => { const t = String(m.cr_text ?? m.cr ?? "0"); return t.includes("/") ? Number(t.split("/")[0]) / Number(t.split("/")[1]) : Number(t) || 0; };
  const crText = (n) => ({ 0.125: "1/8", 0.25: "1/4", 0.5: "1/2" }[n] ?? String(n));
  function wildShapeBlock(m) {
    if (kind !== "wildshape") return "";
    const limits = current.sheet?.wild_shape;
    if (!limits) return "no Wild Shape (druid level 2)";
    if (!String(m.type || "").toLowerCase().startsWith("beast")) return "not a beast";
    if (CR(m) > limits.max_cr) return `CR above ${crText(limits.max_cr)}`;
    const speed = String(m.speed || "").toLowerCase();
    if (!limits.swim && speed.includes("swim")) return "swimming speed (druid level 4)";
    if (!limits.fly && speed.includes("fly")) return "flying speed (druid level 8)";
    return "";
  }
  function add(m) {
    extras.push({ kind, monster: m, hp_current: Number(m.hp) || 0, notes: "" });
    changed();
  }
  function hp(x, delta) {
    x.hp_current = Math.max(0, Math.min(Number(x.monster.hp) || 0, (x.hp_current ?? 0) + delta));
    changed(200);
  }
  const mod = (score) => signed(Math.floor((Number(score) - 10) / 2));
  const matches = (x) => !filter.trim() || `${x.monster.name} ${x.monster.type} ${x.notes || ""}`.toLowerCase().includes(filter.trim().toLowerCase());
  const groups = $derived(Object.entries(KINDS).map(([key, label]) => [key, label, extras.map((x, k) => [x, k]).filter(([x]) => x.kind === key && matches(x))]).filter(([, , list]) => list.length));
  const speedOf = (m) => String(m.speed || "").split(",")[0].replace(/^walk /, "").trim();
</script>

<section class="ct-extras">
  <h2 class="accessibility_screenreaderOnly__OEzRB">Extras</h2>
  <div class="ct-extras__filter"><div class="ct-extras-filter"><div class="ct-extras-filter__interactions">
    <div class="ct-extras-filter__box"><div class="ct-extras-filter__primary">
      <div class="ct-extras-filter__primary-group ct-extras-filter__primary-group--first"><div class="ct-extras-filter__icon"></div></div>
      <div class="ct-extras-filter__field"><input class="ct-extras-filter__input" type="search" placeholder="Search Extras by Name or Type" bind:value={filter} /></div>
    </div></div>
    <div class="ct-extras-filter__callout">
      <button class="ct-theme-button ct-theme-button--outline ct-theme-button--interactive ct-button character-button ddbc-button character-button-medium" type="button"
        aria-expanded={managing} onclick={() => (managing = !managing)}><span class="ct-button__content">Manage Extras</span></button>
    </div>
  </div></div></div>

  {#if managing}
    <div class="ct-extra-manage-pane ddb-extras-manage">
      <form class="ct-extra-manage-pane__filters" onsubmit={search}>
        <input type="search" placeholder="Creature name, e.g. owl, wolf, imp" bind:value={query} aria-label="Search creatures" />
        <select bind:value={kind} aria-label="Add as">{#each Object.entries(KINDS) as [k, label]}<option value={k}>{label}</option>{/each}</select>
        <button type="submit" disabled={searching}>Search</button>
      </form>
      <p class="ct-extra-manage-pane__default">Monster Manual and the other 2014 Wizards books. Add puts the creature on this sheet with its own hit points.</p>
      {#if kind === "wildshape" && current.sheet?.wild_shape}<p class="ct-extra-manage-pane__default">Your Wild Shape: beasts up to CR {crText(current.sheet.wild_shape.max_cr)}{current.sheet.wild_shape.swim ? "" : ", no swimming speed"}{current.sheet.wild_shape.fly ? "" : ", no flying speed"} (PHB p. 66).</p>{/if}
      {#if results.length}
        <div class="ct-extra-manage-pane__extras">
          {#each results as m (m.id)}
            <div class="ct-extra-manage-pane__extra"><span>{m.name}</span> <span class="ct-extra-row__meta-item">{m.size} {m.type} · CR {m.cr_text || m.cr} · {(m.sources || [m.source])[0]}</span>
              {#if wildShapeBlock(m)}<span class="ct-extra-row__meta-item">Not allowed: {wildShapeBlock(m)}</span>
              {:else}<button type="button" class="ct-theme-button ct-theme-button--filled ct-theme-button--interactive ct-button character-button ddbc-button character-button-small" onclick={() => add(m)}><span class="ct-button__content">Add as {KINDS[kind]}</span></button>{/if}</div>
          {/each}
        </div>
      {/if}
    </div>
  {/if}

  {#if !extras.length}
    <div class="ct-extras__empty">Extras that you add will display here.</div>
  {:else}
    <div class="ct-extras__content">
      {#each groups as [key, label, list] (key)}
        <div class="ct-content-group">
          <div class="ct-content-group__header"><div class="ct-content-group__header-content">{label}</div></div>
          <div class="ct-content-group__content"><div class="ct-extra-list">
            <div class="ct-extra-list__row-header">
              <div class="ct-extra-list__col ct-extra-list__col--preview"></div>
              <div class="ct-extra-list__col ct-extra-list__col--primary">Name</div>
              <div class="ct-extra-list__col ct-extra-list__col--ac">AC</div>
              <div class="ct-extra-list__col ct-extra-list__col--hp">HP</div>
              <div class="ct-extra-list__col ct-extra-list__col--speed">Speed</div>
              <div class="ct-extra-list__col ct-extra-list__col--notes">Notes</div>
            </div>
            {#each list as [x, k] (k)}
              {@const m = x.monster}
              <div class="ct-extra-row" role="button" tabindex="0" aria-expanded={openRow === k} onclick={() => (openRow = openRow === k ? null : k)} onkeydown={(e) => e.key === "Enter" && (openRow = openRow === k ? null : k)}>
                <div class="ct-extra-row__preview"></div>
                <div class="ct-extra-row__primary">
                  <div class="ct-extra-row__name">{m.name}</div>
                  <div class="ct-extra-row__meta"><span class="ct-extra-row__meta-item">{m.size} {m.type}</span><span class="ct-extra-row__meta-item">CR {m.cr_text || m.cr}</span></div>
                </div>
                <div class="ct-extra-row__ac">{m.ac}</div>
                <div class="ct-extra-row__hp"><span class="ct-extra-row__hp-value ct-extra-row__hp-value--current">{x.hp_current}</span><span class="ct-extra-row__hp-sep">/</span><span class="ct-extra-row__hp-value ct-extra-row__hp-value--total">{m.hp}</span></div>
                <div class="ct-extra-row__speed"><span class="ct-extra-row__speed-value">{speedOf(m)}</span></div>
                <div class="ct-extra-row__notes">{x.notes || "--"}</div>
              </div>
              {#if openRow === k}
                <div class="ddb-extra-detail">
                  <p><b>AC</b> {m.ac_text || m.ac} · <b>HP</b>
                    <button type="button" class="mini" onclick={() => hp(x, -1)} aria-label="Lose 1 hit point">−</button>
                    {x.hp_current} / {m.hp}
                    <button type="button" class="mini" onclick={() => hp(x, 1)} aria-label="Regain 1 hit point">+</button>
                    · <b>Speed</b> {m.speed}</p>
                  <p class="extra-abilities">{#each ["str", "dex", "con", "int", "wis", "cha"] as a}<span><b>{a.toUpperCase()}</b> {m.abilities?.[a]} ({mod(m.abilities?.[a])})</span>{/each}</p>
                  <p class="small">{m.senses ? `Senses ${m.senses}. ` : ""}{m.skills ? `Skills ${m.skills}. ` : ""}{m.languages ? `Languages ${m.languages}.` : ""}</p>
                  {#each [["Traits", m.traits], ["Actions", m.actions], ["Reactions", m.reactions]] as [heading, entries]}
                    {#if entries?.length}<h5>{heading}</h5>{#each entries as t}<p class="small"><strong>{t.name}.</strong> {t.text}</p>{/each}{/if}
                  {/each}
                  <label class="notes small">Notes <input type="text" bind:value={x.notes} oninput={() => changed(800)} /></label>
                  <button type="button" class="mini danger" onclick={() => { extras.splice(k, 1); openRow = null; changed(); }}>Remove {m.name}</button>
                </div>
              {/if}
            {/each}
          </div></div>
        </div>
      {/each}
    </div>
  {/if}
</section>
