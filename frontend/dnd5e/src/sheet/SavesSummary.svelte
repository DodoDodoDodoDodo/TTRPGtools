<script>
  // DDB's saving-throw rows (ddbc-saving-throws-summary), shared by the desktop box and the phone main section.
  import { current } from "../lib/character.svelte.js";
  import { ABILITIES, ABILITY_NAMES } from "../lib/format.js";
  import { ddb } from "../lib/ddb.svelte.js";
  import Frame from "./ddb/Frame.svelte";
  import Num from "./ddb/Num.svelte";
  import Prof from "./ddb/Prof.svelte";
  const s = $derived(current.sheet);
</script>

<div class="ddbc-saving-throws-summary">
  {#each ABILITIES as a}
    {@const sv = s.saving_throws[a]}
    <div class="ddbc-saving-throws-summary__ability ddbc-saving-throws-summary__ability--{a}">
      <Frame name="save-row" />
      <div class="ddbc-saving-throws-summary__ability-proficiency"><Prof level={sv.proficient ? "proficient" : null} /></div>
      <div class="ddbc-saving-throws-summary__ability-name"><abbr title={ABILITY_NAMES[a]}>{a}</abbr></div>
      <div class="ddbc-saving-throws-summary__ability-modifier">
        <button type="button" class="F8U5pq_button integrated-dice__container"><Num value={sv.modifier} />{sv.overridden ? "*" : ""}</button>
        {@html (ddb.frames["save-modifier"] || "").replace('class="', 'class="ddbc-saving-throws-summary__ability-modifier-background ')}
      </div>
    </div>
  {/each}
</div>
