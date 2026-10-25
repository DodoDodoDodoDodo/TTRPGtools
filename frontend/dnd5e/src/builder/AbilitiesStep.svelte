<script>
  // Abilities step in DDB's markup (ability-scores/manage): generation method, the six score pickers,
  // the race's Ability Score Increase card and the Score Calculations tables with Other Modifier and
  // Override Score. Only point buy was captured; standard array and manual reuse its layout.
  import DdbSelect from "./DdbSelect.svelte";
  import AbilityCalc from "../sheet/ddb/AbilityCalc.svelte";
  import { current, changed } from "../lib/character.svelte.js";
  import { content } from "../lib/content.svelte.js";
  import { ddb } from "../lib/ddb.svelte.js";
  import { ABILITIES, ABILITY_NAMES, raceName } from "../lib/format.js";
  import { abilitySentence } from "../lib/race.js";

  const ARRAY = [15, 14, 13, 12, 10, 8];
  const COST = { 8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9 };
  const BUDGET = 27;
  const METHODS = [{ value: "standard", label: "Standard Array" }, { value: "manual", label: "Manual/Rolled" }, { value: "pointbuy", label: "Point Buy" }];

  $effect.pre(() => {
    current.character.abilities ??= { base: {} };
    current.character.abilities.base ??= {};
  });
  const ab = $derived(current.character.abilities || { base: {} });
  const base = $derived(ab.base || {});
  const rows = $derived(current.sheet?.abilities || {});
  // Characters saved before the method dropdown existed have scores but no method; character.py reads those as manual.
  const method = $derived(ab.method || (Object.values(base).some((v) => v !== null && v !== undefined) ? "manual" : ""));
  const spent = $derived(ABILITIES.reduce((n, a) => n + (COST[base[a] ?? 8] ?? 0), 0));

  function setMethod(value) {
    ab.method = value || undefined;
    ab.base = value === "pointbuy" ? Object.fromEntries(ABILITIES.map((a) => [a, 8])) : {};
    changed();
  }
  function setBase(a, value) {
    ab.base = { ...base, [a]: value === "" || value === null ? null : Number(value) };
    changed();
  }

  const points = (n) => `${n >= 0 ? "+" : ""}${n} Point${Math.abs(n) === 1 ? "" : "s"}`;
  // DDB lists only the values the remaining points can pay for, each labelled with what it gives back.
  function pointOptions(a) {
    const now = COST[base[a] ?? 8];
    return Object.keys(COST).map(Number).filter((v) => COST[v] - now <= BUDGET - spent)
      .map((v) => ({ value: String(v), label: COST[v] === now ? String(v) : `${v} (${points(now - COST[v])})` }));
  }
  function arrayOptions(a) {
    const left = [...ARRAY];
    for (const other of ABILITIES) if (other !== a && left.includes(base[other])) left.splice(left.indexOf(base[other]), 1);
    return [...new Set(left)].map((v) => ({ value: String(v), label: String(v) }));
  }

  const race = $derived(current.character.race?.id ? content.byId.races[current.character.race.id] : null);
  const raceBlocks = $derived(race?.ability?.length ? race.ability : []);

</script>


<div class="builder-page">
  <div class="builder-page-header">Ability Scores</div>
  <div class="styles_typeChooser__nqxgg">
    <DdbSelect placeholder="-- Choose a Generation Method --" searchable={false} value={method} options={METHODS} onchange={setMethod} />
  </div>

  {#if method}
    <div class="ability-score-manager {method === 'pointbuy' ? 'ability-score-manager-point' : 'ability-score-manager-standard'}">
      {#if method === "pointbuy"}
        <div class="ability-score-manager-points">
          <div class="ability-score-manager-points-heading">Points Remaining</div>
          <div class="ability-score-manager-points-value"><span class="ability-score-manager-points-value-remaining">{BUDGET - spent}</span><span class="ability-score-manager-points-value-sep">/</span><span class="ability-score-manager-points-value-total">{BUDGET}</span></div>
        </div>
      {/if}
      <div class="ability-score-manager-stats">
        {#each ABILITIES as a}
          <div class="ability-score-manager-stat">
            <div class="builder-field {method === 'manual' ? 'form-input-field' : 'form-select-field'}">
              <span class="builder-field-label"><label class="builder-field-heading form-select-field-label" for="ability-{a}">{ABILITY_NAMES[a]}</label></span>
              <span class="builder-field-input">
                {#if method === "manual"}
                  <input id="ability-{a}" class="builder-field-value" type="number" min="1" max="30" placeholder="--" value={base[a] ?? ""} oninput={(e) => setBase(a, e.target.value)} />
                {:else if method === "pointbuy"}
                  <DdbSelect placeholder="" optionsClass="styles_large__21Y3q" searchable={false} value={String(base[a] ?? 8)} options={pointOptions(a)} onchange={(v) => setBase(a, v)} />
                {:else}
                  <DdbSelect placeholder="--" optionsClass="styles_large__21Y3q" searchable={false} value={base[a] == null ? "" : String(base[a])} options={arrayOptions(a)} onchange={(v) => setBase(a, v)} />
                {/if}
              </span>
              <div class="ability-score-manager-stat-total">Total: {rows[a]?.score ?? "--"}</div>
            </div>
          </div>
        {/each}
      </div>
    </div>
  {/if}

  {#each raceBlocks.length ? [raceBlocks] : [] as blocks}
    <details class="styles_details__Kwqwr styles_paper__FhNqH">
      <summary class="styles_summary__BI+UG" data-testid="accordion-summary">
        <div class="styles_heading__RRl69">
          <div class="styles_summaryContent__xaQWq">Ability Score Increase ({raceName(race.name)})<div class="styles_metaItems__Pt+Po"></div></div>
          <div class="styles_actions__1-sml"></div>{@html ddb.icons["details-chevron"] || "▾"}
        </div>
      </summary>
      <div class="styles_content__pFYp6"><div class="ddbc-html-content race-detail-racial-trait-description">
        {#if blocks.length > 1}<p>Choose one of these options (on the Race step):</p><ul>{#each blocks as b}<li>{abilitySentence(b)}</li>{/each}</ul>
        {:else}<p>{abilitySentence(blocks[0])}</p>{/if}
      </div></div>
    </details>
  {/each}

  <div class="builder-page-header">Score Calculations</div>
  <p>Calculations, including the base scores you set above and any modifiers, are found below. You can also override any automatic calculations or modify them under each ability summary.</p>
  <div class="ability-score-calcs">
    {#each ABILITIES as a}
      <div>
        <div class="styles_header__wZkdy">{@html ddb.icons[`ability-${a}`] || ""}<div class="styles_name__g-meS">{ABILITY_NAMES[a]}</div></div>
        <AbilityCalc {a} builder />
      </div>
    {/each}
  </div>
</div>
