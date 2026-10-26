<script>
  import Picker from "../lib/Picker.svelte";
  import { content, sourceAllowed } from "../lib/content.svelte.js";
  import { current, changed, classEntry } from "../lib/character.svelte.js";
  import { ordinal, SCHOOLS, book } from "../lib/format.js";

  let { only = null } = $props();  // a class id: the class card's Spells tab shows just that class
  const casters = $derived((current.sheet?.spellcasting?.casters || []).filter((c) => !only || c.class_id === only));
  let showOptional = $state(true);

  // spell filters (Dodo, 2026-10-26: "filter spells by all relevant things"): every list below passes through `passes`
  const blank = { level: "", school: "", time: "", range: "", damage: "", save: "", conc: "", ritual: false, noMaterial: false, tag: "" };
  let f = $state({ ...blank });
  const active = $derived(Object.keys(blank).filter((k) => f[k] !== blank[k]).length);
  const DAMAGE = $derived([...new Set(content.spells.flatMap((s) => s.damageInflict || []))].sort());
  const SAVES = $derived([...new Set(content.spells.flatMap((s) => s.savingThrow || []))].sort());
  const timeOf = (s) => { const t = s.time?.[0] || {}; return t.unit === "bonus" ? "bonus" : t.unit === "reaction" ? "reaction" : t.unit === "action" ? "action" : "long"; };
  const rangeOf = (s) => { const d = s.range?.distance?.type; return d === "self" ? "self" : d === "touch" ? "touch" : "ranged"; };
  const concentration = (s) => (s.duration || []).some((d) => d.concentration);
  // the 5etools tags behind the plain words: HL healing, SMN summon, TP teleport, FMV forced movement, MAC/THP protection
  function tagsOf(s) {
    const misc = s.miscTags || [], out = [];
    if ((s.damageInflict || []).length) out.push("damage");
    if (misc.includes("HL")) out.push("healing");
    if (misc.includes("MAC") || misc.includes("THP")) out.push("protection");
    if (misc.includes("SMN")) out.push("summoning");
    if (misc.includes("TP")) out.push("teleport");
    if (misc.includes("FMV") || ((s.savingThrow || []).length && !(s.damageInflict || []).length)) out.push("control");
    if (!out.length) out.push("utility");
    return out;
  }
  function passes(s) {
    return (f.level === "" || s.level === Number(f.level)) && (!f.school || s.school === f.school) && (!f.time || timeOf(s) === f.time)
      && (!f.range || rangeOf(s) === f.range) && (!f.damage || (s.damageInflict || []).includes(f.damage)) && (!f.save || (s.savingThrow || []).includes(f.save))
      && (!f.conc || concentration(s) === (f.conc === "yes")) && (!f.ritual || Boolean(s.meta?.ritual)) && (!f.noMaterial || !s.components?.m)
      && (!f.tag || tagsOf(s).includes(f.tag));
  }

  // the Home step's books; a spell already picked stays listed so switching a book off does not hide a choice
  const inBooks = (s) => sourceAllowed(s.book, current.character.preferences);
  const chosenAnywhere = (caster, id) => Object.values(classEntry(caster.class_id)?.spells || {}).some((v) => (Array.isArray(v) ? v : Object.values(v || {})).includes(id));
  // Magical Secrets: any class's list, cantrips included (PHB p. 54)
  function anyList(caster) {
    return content.spells.filter((s) => s.level <= (caster.max_spell_level || 0) && s.classes.length && inBooks(s) && passes(s))
      .map((s) => ({ id: s.id, name: s.name, kind: "spell", note: `${s.level ? ordinal(s.level) : "Cantrip"} · ${s.classes.join(", ")} · ${book(s.book)}` }));
  }
  const ofLevel = (caster, level) => content.spells.filter((s) => s.level === level && inBooks(s) && passes(s) && s.classes.includes(content.byId.classes[caster.class_id].name))
    .map((s) => ({ id: s.id, name: s.name, kind: "spell", note: `${SCHOOLS[s.school] || ""} · ${book(s.book)}` }));
  // Spell Mastery and Signature Spells pick from the spellbook (PHB p. 115)
  const fromBook = (caster, level) => ofLevel(caster, level).filter((o) => spellsOf(caster, "known").includes(o.id));
  function setMastery(caster, level, ids) {
    const entry = classEntry(caster.class_id);
    entry.spells = { cantrips: [], known: [], prepared: [], ...(entry.spells || {}) };
    entry.spells.mastery = { ...(entry.spells.mastery || {}), [level]: ids[ids.length - 1] || null };
    changed();
  }
  function setArcanum(caster, level, ids) {
    const entry = classEntry(caster.class_id);
    entry.spells = { cantrips: [], known: [], prepared: [], ...(entry.spells || {}) };
    entry.spells.arcanum = { ...(entry.spells.arcanum || {}), [level]: ids[ids.length - 1] || null };
    changed();
  }

  function classList(caster, level) {
    const cls = content.byId.classes[caster.class_id];
    const expanded = new Set(caster.expanded || []);
    return content.spells
      .filter((s) => (inBooks(s) && passes(s)) || chosenAnywhere(caster, s.id))
      .filter((s) => (level === 0 ? s.level === 0 : s.level > 0 && s.level <= (caster.max_spell_level || 0)))
      .filter((s) => s.classes.includes(cls.name) || (showOptional && s.classesVariant.includes(cls.name)) || expanded.has(s.id)
        || (caster.progression === "1/3" && s.classes.includes("Wizard")))
      .map((s) => ({
        id: s.id, name: s.name, kind: "spell",
        note: `${ordinal(s.level)} ${SCHOOLS[s.school] || ""}${s.classesVariant.includes(cls.name) && !s.classes.includes(cls.name) ? " · Tasha's optional" : ""}${expanded.has(s.id) ? " · expanded list" : ""} · ${book(s.book)}`,
      }));
  }

  function set(caster, key, ids) {
    const entry = classEntry(caster.class_id);
    entry.spells = { cantrips: [], known: [], prepared: [], ...(entry.spells || {}), [key]: ids };
    changed();
  }
  const spellsOf = (caster, key) => (classEntry(caster.class_id)?.spells?.[key]) || [];
  const preparesFromList = (caster) => caster.prepared_max !== null && caster.class !== "Wizard";
</script>

{#if !only}
  <h2>Spells</h2>
  <p class="hint">One panel per spellcasting class. Counts come from the class tables; spells always prepared by your subclass are listed and do not count.</p>
{/if}
<label class="radio-line"><input type="checkbox" bind:checked={showOptional} /> Include Tasha's optional class spells (TCE p. 13)</label>
<details class="spell-filters" open={active > 0}>
  <summary>Filter spells{active ? ` · ${active} active` : ""}</summary>
  <p class="hint">Narrows every list below. Spells already chosen stay listed.</p>
  <div class="spell-filter-grid">
    <label>Level <select bind:value={f.level}><option value="">any</option>{#each [0, 1, 2, 3, 4, 5, 6, 7, 8, 9] as l}<option value={String(l)}>{l === 0 ? "Cantrip" : ordinal(l)}</option>{/each}</select></label>
    <label>School <select bind:value={f.school}><option value="">any</option>{#each Object.entries(SCHOOLS) as [k, v]}<option value={k}>{v}</option>{/each}</select></label>
    <label>Casting time <select bind:value={f.time}><option value="">any</option><option value="action">1 action</option><option value="bonus">1 bonus action</option><option value="reaction">1 reaction</option><option value="long">1 minute or longer</option></select></label>
    <label>Range <select bind:value={f.range}><option value="">any</option><option value="self">Self</option><option value="touch">Touch</option><option value="ranged">Ranged</option></select></label>
    <label>Damage type <select bind:value={f.damage}><option value="">any</option>{#each DAMAGE as d}<option value={d}>{d}</option>{/each}</select></label>
    <label>Saving throw <select bind:value={f.save}><option value="">any</option>{#each SAVES as d}<option value={d}>{d}</option>{/each}</select></label>
    <label>Concentration <select bind:value={f.conc}><option value="">any</option><option value="yes">yes</option><option value="no">no</option></select></label>
    <label>Does <select bind:value={f.tag}><option value="">anything</option>{#each ["damage", "healing", "protection", "control", "summoning", "teleport", "utility"] as t}<option value={t}>{t}</option>{/each}</select></label>
    <label class="radio-line"><input type="checkbox" bind:checked={f.ritual} /> Ritual only</label>
    <label class="radio-line"><input type="checkbox" bind:checked={f.noMaterial} /> No material component</label>
    <button type="button" class="ct-button character-button ddbc-button character-button-small" disabled={!active} onclick={() => (f = { ...blank })}><span class="ct-button__content">Clear filters</span></button>
  </div>
</details>

{#each casters as caster (caster.class_id)}
  <article class="class-block">
    <header class="class-head">
      <h3>{caster.class}</h3>
      <span class="dim">Save DC {caster.save_dc} · spell attack +{caster.attack} · {caster.ability.toUpperCase()} · spells up to {ordinal(caster.max_spell_level || 0)}</span>
    </header>
    {#if caster.school_limit}
      {@const lim = caster.school_limit}
      <p class="hint" class:ddb-over={lim.outside > lim.free}>Spells known must be {lim.schools.map((x) => SCHOOLS[x]).join(" or ")} (PHB p. 75, 98), except {lim.free} from any school at your level: <strong>{lim.outside} of {lim.free} used</strong>.</p>
    {/if}

    {#if caster.cantrips_known}
      <div class="choice"><Picker label="Cantrips" max={caster.cantrips_known} filterable options={classList(caster, 0)}
        selected={spellsOf(caster, "cantrips")} onchange={(ids) => set(caster, "cantrips", ids)} /></div>
    {/if}

    {#if caster.spells_known !== null && caster.spells_known !== undefined}
      <div class="choice"><Picker label="Spells known" max={caster.spells_known - Math.max(0, spellsOf(caster, "secrets").length - (caster.secrets_extra || 0))} filterable options={classList(caster, 1)}
        selected={spellsOf(caster, "known")} onchange={(ids) => set(caster, "known", ids)} /></div>
    {:else if caster.class === "Wizard"}
      <div class="choice"><Picker label={`Spellbook: ${6 + 2 * ((classEntry(caster.class_id)?.level || 1) - 1)} from your wizard levels (PHB p. 114), plus any you copy`} max={999} filterable options={classList(caster, 1)}
        selected={spellsOf(caster, "known")} onchange={(ids) => set(caster, "known", ids)} /></div>
      <div class="choice"><Picker label="Prepared from the spellbook" max={caster.prepared_max}
        options={classList(caster, 1).filter((o) => spellsOf(caster, "known").includes(o.id))}
        selected={spellsOf(caster, "prepared")} onchange={(ids) => set(caster, "prepared", ids)} /></div>
    {:else if preparesFromList(caster)}
      <div class="choice"><Picker label="Prepared spells" max={caster.prepared_max} filterable options={classList(caster, 1)}
        selected={spellsOf(caster, "prepared")} onchange={(ids) => set(caster, "prepared", ids)} /></div>
    {/if}

    {#if caster.secrets_max || caster.secrets_extra}
      <div class="choice"><Picker label={`Magical Secrets (any class's spells; ${caster.secrets_max ? `${caster.secrets_max} count as spells known` : ""}${caster.secrets_max && caster.secrets_extra ? ", " : ""}${caster.secrets_extra ? `${caster.secrets_extra} from Additional Magical Secrets do not` : ""})`}
        max={caster.secrets_max + caster.secrets_extra} filterable options={anyList(caster)}
        selected={spellsOf(caster, "secrets")} onchange={(ids) => set(caster, "secrets", ids)} /></div>
    {/if}
    {#each caster.arcanum_levels || [] as level}
      <div class="choice"><Picker label={`Mystic Arcanum (${ordinal(level)}, once per long rest)`} max={1} filterable options={ofLevel(caster, level)}
        selected={[(classEntry(caster.class_id)?.spells?.arcanum || {})[level]].filter(Boolean)} onchange={(ids) => setArcanum(caster, level, ids)} /></div>
    {/each}

    {#each caster.mastery_levels || [] as level}
      <div class="choice"><Picker label={`Spell Mastery: ${ordinal(level)} from your spellbook, cast at will at its lowest level`} max={1} filterable options={fromBook(caster, level)}
        selected={[(classEntry(caster.class_id)?.spells?.mastery || {})[level]].filter(Boolean)} onchange={(ids) => setMastery(caster, level, ids)} /></div>
    {/each}
    {#if caster.signature_max}
      <div class="choice"><Picker label="Signature Spells: two 3rd-level spells, always prepared, each once per short rest without a slot" max={caster.signature_max} filterable options={fromBook(caster, 3)}
        selected={spellsOf(caster, "signature")} onchange={(ids) => set(caster, "signature", ids)} /></div>
    {/if}
    {#if caster.always_prepared?.length}
      <p><strong>Always prepared:</strong> {caster.always_prepared.map((s) => s.name).join(", ")}</p>
    {/if}
  </article>
{:else}
  <p class="hint">No spellcasting class yet. Spellcasting arrives with the class (or subclass, for Eldritch Knight and Arcane Trickster at level 3).</p>
{/each}

<style>
  .spell-filters { margin: 8px 0 12px; border: 1px solid var(--ddb-border, #d9d6cf); border-radius: 4px; padding: 6px 10px; }
  .spell-filters summary { cursor: pointer; font-weight: 700; font-size: 13px; text-transform: uppercase; letter-spacing: .04em; }
  .spell-filter-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 6px 14px; align-items: end; font-size: 13px; }
  .spell-filter-grid label { display: flex; flex-direction: column; gap: 2px; }
  .spell-filter-grid label.radio-line { flex-direction: row; align-items: center; }
  .spell-filter-grid select { font: inherit; padding: 3px 4px; }
</style>
