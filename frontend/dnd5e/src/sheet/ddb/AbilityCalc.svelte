<script>
  // DDB's score table for one ability (Total, Modifier, Base, Bonus with its suppliers, Set Score, Stacking
  // Bonus) with Other Modifier and Override Score. Used by the Abilities step (`builder`) and the ability pane.
  import { current, changed } from "../../lib/character.svelte.js";
  import { content } from "../../lib/content.svelte.js";
  import { ABILITY_NAMES, title, raceName } from "../../lib/format.js";

  let { a, builder = false } = $props();
  const ab = $derived(current.character.abilities || {});
  const row = $derived(current.sheet?.abilities?.[a] || {});
  const race = $derived(current.character.race?.id ? content.byId.races[current.character.race.id] : null);
  const bonus = $derived((row.race || 0) + (row.asi || 0) + (row.feat || 0));
  // Bonus suppliers, named as DDB names them: the race, each class that granted an improvement, feats.
  const from = $derived.by(() => {
    const out = [];
    if (row.race) out.push([race ? raceName(race.name) : "Race", row.race]);
    for (const entry of current.character.classes || []) {
      const amount = Object.entries(entry.asi || {}).filter(([lvl]) => Number(lvl) <= entry.level)
        .reduce((n, [, pick]) => n + (pick.abilities?.[a] || 0), 0);
      if (amount) out.push([content.byId.classes[entry.id]?.name || title(entry.id), amount]);
    }
    if (row.feat) out.push(["Feats", row.feat]);
    return out;
  });
  function setNumber(group, value) {
    current.character.abilities ??= { base: {} };
    const map = { ...(current.character.abilities[group] || {}) };
    if (value === "" || (group === "bonus" && Number(value) === 0)) delete map[a];
    else map[a] = Number(value);
    current.character.abilities[group] = map;
    changed();
  }
</script>

{#snippet signedNumber(n, extra = "")}
  <span class="styles_numberDisplay__Rg1za styles_signed__scf97 {extra}"><span class="styles_sign__NdR6X styles_labelSignColor__Klmbs" aria-label={n < 0 ? "minus" : "plus"}>{n < 0 ? "-" : "+"}</span><span>{Math.abs(n)}</span></span>
{/snippet}

<div class="styles_table__KEe14">
  <div class="styles_row__qpCLB {builder ? 'styles_highlight__9UzJL' : ''}"><div class="styles_label__WJbyc">Total Score</div><div class="styles_value__0L5in">{row.score ?? "--"}</div></div>
  <div class="styles_row__qpCLB {builder ? 'styles_highlight__9UzJL' : ''}"><div class="styles_label__WJbyc">Modifier</div><div class="styles_value__0L5in">{@render signedNumber(row.modifier ?? 0)}</div></div>
  <div class="styles_row__qpCLB"><div class="styles_label__WJbyc">Base Score</div><div class="styles_value__0L5in">{ab.base?.[a] ?? "--"}</div></div>
  <div class="styles_row__qpCLB" class:styles_hasSuppliers__3B0xn={from.length}><div class="styles_label__WJbyc"><div>Bonus</div></div><div class="styles_value__0L5in">{@render signedNumber(bonus)}</div></div>
  <div class="styles_suppliers__ANZA+">
    {#each from as [name, amount]}
      <div class="styles_supplier__sVT7g {builder ? 'styles_builder__lg0T-' : ''}"><div class="styles_label__WJbyc"><span class="{builder ? 'styles_builder__lg0T-' : ''} ddbc-data-origin-name">{name}</span></div><div class="styles_value__0L5in">({@render signedNumber(amount, "styles_number__yUyk3")})</div></div>
    {/each}
  </div>
  <!-- Set Score and Stacking Bonus come from magic items on DDB; items here do not set scores, so these stay 0. -->
  <div class="styles_row__qpCLB"><div class="styles_label__WJbyc"><div>Set Score</div></div><div class="styles_value__0L5in">0</div></div>
  <div class="styles_suppliers__ANZA+"></div>
  <div class="styles_row__qpCLB"><div class="styles_label__WJbyc"><div>Stacking Bonus</div></div><div class="styles_value__0L5in">{@render signedNumber(0)}</div></div>
  <div class="styles_suppliers__ANZA+"></div>
</div>
<div class="styles_overrides__kg8cB">
  <div class="styles_override__RMizc"><div class="styles_label__WJbyc">Other Modifier</div><div class="styles_value__0L5in"><input placeholder="--" type="number" aria-label="{ABILITY_NAMES[a]} other modifier" value={ab.bonus?.[a] ?? ""} oninput={(e) => setNumber("bonus", e.target.value)} /></div></div>
  <div class="styles_override__RMizc"><div class="styles_label__WJbyc">Override Score</div><div class="styles_value__0L5in"><input placeholder="--" type="number" aria-label="{ABILITY_NAMES[a]} override score" value={ab.override?.[a] ?? ""} oninput={(e) => setNumber("override", e.target.value)} /></div></div>
</div>
