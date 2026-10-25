<script>
  // Printable sheet: page 1 for the table, then features, spells and inventory in PHB two-column style.
  import Entries from "../lib/Entries.svelte";
  import { current } from "../lib/character.svelte.js";
  import { route } from "../lib/router.svelte.js";
  import { content } from "../lib/content.svelte.js";
  import { ABILITIES, ABILITY_NAMES, DAMAGE, signed, title, ordinal, SCHOOLS, castingTime, range, components, duration, itemType, book } from "../lib/format.js";

  const s = $derived(current.sheet);
  const c = $derived(current.character);
  const d = $derived(c.description || {});
  const spells = $derived(s.spellcasting.casters.flatMap((caster) => caster.list.filter((sp) => sp.prepared || sp.level === 0).map((sp) => ({ ...sp, caster: caster.class }))));
  const MARK = { proficient: "●", expertise: "◉", half: "◐" };
  const boxes = (n) => "☐".repeat(Math.min(n, 30));
</script>

<div class="print-bar no-print">
  <a class="button" href={`#/c/${route.id}/sheet`}>&larr; Back to the sheet</a>
  <button type="button" onclick={() => window.print()}>Print / Save as PDF</button>
  <span class="hint">A4. In the print dialog, switch "Background graphics" on for the parchment.</span>
</div>

<article class="print">
  <section class="page page-one">
    <header class="p-head">
      <h1>{s.name}</h1>
      <p>{s.race || "—"} · {s.classes.map((k) => `${k.name}${k.subclass ? ` (${k.subclass})` : ""} ${k.level}`).join(" / ")} · {s.background || "—"}{d.player ? ` · player ${d.player}` : ""}</p>
    </header>
    <div class="p-abilities">
      {#each ABILITIES as a}
        <div class="p-ability"><span class="lbl">{ABILITY_NAMES[a]}</span><b>{signed(s.abilities[a].modifier)}</b><span>{s.abilities[a].score}</span></div>
      {/each}
    </div>
    <div class="p-stats">
      <div><span class="lbl">Armor class</span><b>{s.armor_class.value}</b></div>
      <div><span class="lbl">Hit points</span><b>{s.hp.max}</b><span class="write">current ______ temp ____</span></div>
      <div><span class="lbl">Initiative</span><b>{signed(s.initiative)}</b></div>
      <div><span class="lbl">Speed</span><b>{s.speed.walk} ft.</b></div>
      <div><span class="lbl">Proficiency</span><b>{signed(s.proficiency_bonus)}</b></div>
      <div><span class="lbl">Passive perception</span><b>{s.passives.perception}</b></div>
    </div>
    <div class="p-cols">
      <div>
        <h3>Saving throws</h3>
        <ul class="p-list">{#each ABILITIES as a}<li><span>{s.saving_throws[a].proficient ? "●" : "○"} {ABILITY_NAMES[a]}</span><b>{signed(s.saving_throws[a].modifier)}</b></li>{/each}</ul>
        <h3>Skills</h3>
        <ul class="p-list">{#each Object.entries(s.skills) as [name, sk]}<li><span>{MARK[sk.proficiency] || "○"} {title(name)} <small>({sk.ability})</small></span><b>{signed(sk.modifier)}</b></li>{/each}</ul>
        <p class="p-small">● proficient · ◉ expertise · ◐ half proficiency. Passive investigation {s.passives.investigation}, insight {s.passives.insight}.{s.senses.darkvision ? ` Darkvision ${s.senses.darkvision} ft.` : ""}</p>
      </div>
      <div>
        <h3>Attacks</h3>
        <table class="p-table">
          <thead><tr><th>Name</th><th>Hit</th><th>Damage</th></tr></thead>
          <tbody>{#each s.attacks as a}<tr><td>{a.name}</td><td>{signed(a.to_hit)}</td><td>{a.damage} {DAMAGE[a.damage_type] || ""}</td></tr>{/each}</tbody>
        </table>
        {#if s.spellcasting.casters.length}
          <h3>Spellcasting</h3>
          {#each s.spellcasting.casters as caster}<p class="p-small"><b>{caster.class}</b>: save DC {caster.save_dc}, attack {signed(caster.attack)}</p>{/each}
          {#each s.spellcasting.slots as sl}<p class="p-small">{ordinal(sl.level)} slots {boxes(sl.max)}</p>{/each}
          {#if s.spellcasting.pact}<p class="p-small">Pact slots ({ordinal(s.spellcasting.pact.level)}) {boxes(s.spellcasting.pact.count)}</p>{/if}
        {/if}
        {#if s.counters.length}
          <h3>Limited uses</h3>
          {#each s.counters as k}<p class="p-small">{k.name} ({k.reset} rest) {k.max <= 20 ? boxes(k.max) : `____ / ${k.max}`}</p>{/each}
        {/if}
        <h3>Hit dice</h3>
        {#each s.hit_dice as hd}<p class="p-small">d{hd.die} ({hd.class}) {boxes(hd.total)}</p>{/each}
        <p class="p-small">Death saves: success ☐☐☐ failure ☐☐☐</p>
        <h3>Proficiencies</h3>
        <p class="p-small"><b>Armor</b> {s.proficiencies.armor.map(title).join(", ") || "none"}. <b>Weapons</b> {s.proficiencies.weapons.map(title).join(", ") || "none"}. <b>Tools</b> {s.proficiencies.tools.map(title).join(", ") || "none"}. <b>Languages</b> {s.proficiencies.languages.map(title).join(", ") || "none"}.</p>
        {#if s.defenses.resist.length}<p class="p-small"><b>Resistances</b> {s.defenses.resist.join(", ")}.</p>{/if}
      </div>
    </div>
  </section>

  <section class="page phb">
    <h2>Features &amp; Traits</h2>
    <div class="phb-cols">
      {#each s.features.filter((f) => f.name !== "Ability Score Improvement") as f}
        <div class="phb-feature">
          <h4>{f.name}</h4>
          <p class="phb-sub">{f.origin}{f.level ? `, level ${f.level}` : ""}{f.chosen?.length ? ` — chosen: ${f.chosen.join(", ")}` : ""}</p>
          <Entries entries={f.entries} />
        </div>
      {/each}
    </div>
  </section>

  {#if spells.length}
    <section class="page phb">
      <h2>Spells</h2>
      <div class="phb-cols">
        {#each spells as sp (sp.caster + sp.id)}
          {@const full = content.byId.spells[sp.id]}
          <div class="phb-spell">
            <h4>{sp.name}</h4>
            <p class="phb-sub">{ordinal(sp.level)} {(SCHOOLS[sp.school] || "").toLowerCase()}{sp.ritual ? " (ritual)" : ""} · {sp.caster}</p>
            <p class="phb-facts"><b>Casting Time:</b> {castingTime(full.time)}<br><b>Range:</b> {range(full.range)}<br><b>Components:</b> {components(full.components)}<br><b>Duration:</b> {duration(full.duration)}</p>
            <Entries entries={full.entries} />
            {#if full.entriesHigherLevel}<Entries entries={full.entriesHigherLevel} />{/if}
          </div>
        {/each}
      </div>
    </section>
  {/if}

  <section class="page phb">
    <h2>Equipment</h2>
    <table class="p-table">
      <thead><tr><th>Item</th><th>Qty</th><th>Weight</th><th>Notes</th></tr></thead>
      <tbody>
        {#each s.inventory as it}<tr><td>{it.name}</td><td>{it.qty}</td><td>{it.weight ? `${it.weight} lb.` : ""}</td><td>{it.equipped ? "equipped" : ""}{it.attuned ? ", attuned" : ""}</td></tr>{/each}
      </tbody>
    </table>
    <p class="p-small">Carrying {s.encumbrance.weight} of {s.encumbrance.capacity} lb. · {["pp", "gp", "ep", "sp", "cp"].map((k) => `${s.currency[k]} ${k}`).join(", ")}</p>
    {#if c.notes}<h3>Notes</h3><p class="phb-notes">{c.notes}</p>{/if}
    {#if d.backstory}<h3>Backstory</h3><p class="phb-notes">{d.backstory}</p>{/if}
  </section>
</article>
