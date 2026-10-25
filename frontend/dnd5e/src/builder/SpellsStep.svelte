<script>
  import Picker from "../lib/Picker.svelte";
  import { content, sourceAllowed } from "../lib/content.svelte.js";
  import { current, changed, classEntry } from "../lib/character.svelte.js";
  import { ordinal, SCHOOLS, book } from "../lib/format.js";

  let { only = null } = $props();  // a class id: the class card's Spells tab shows just that class
  const casters = $derived((current.sheet?.spellcasting?.casters || []).filter((c) => !only || c.class_id === only));
  let showOptional = $state(true);

  // the Home step's books; a spell already picked stays listed so switching a book off does not hide a choice
  const inBooks = (s) => sourceAllowed(s.book, current.character.preferences);
  const chosenAnywhere = (caster, id) => Object.values(classEntry(caster.class_id)?.spells || {}).some((v) => (Array.isArray(v) ? v : Object.values(v || {})).includes(id));
  // Magical Secrets: any class's list, cantrips included (PHB p. 54)
  function anyList(caster) {
    return content.spells.filter((s) => s.level <= (caster.max_spell_level || 0) && s.classes.length && inBooks(s))
      .map((s) => ({ id: s.id, name: s.name, kind: "spell", note: `${s.level ? ordinal(s.level) : "Cantrip"} · ${s.classes.join(", ")} · ${book(s.book)}` }));
  }
  const ofLevel = (caster, level) => content.spells.filter((s) => s.level === level && inBooks(s) && s.classes.includes(content.byId.classes[caster.class_id].name))
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
      .filter((s) => inBooks(s) || chosenAnywhere(caster, s.id))
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
