<script>
  // The one old/new design switch, in the top bar. It flips every screen that has both versions:
  // the race, class and background choosers.
  import { design, setDesign } from "../lib/design.svelte.js";
</script>

<div class="ddb-design-toggle" role="radiogroup" aria-label="Design">
  <span class="ddb-design-toggle-label">Design:</span>
  {#each [["old", "Old"], ["new", "New"]] as [mode, label]}
    <button type="button" role="radio" aria-checked={design.mode === mode} class:active={design.mode === mode} onclick={() => setDesign(mode)}>{label}<span class="ddb-design-long">&nbsp;design</span></button>
  {/each}
</div>
