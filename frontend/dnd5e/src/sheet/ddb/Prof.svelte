<script>
  // Proficiency marks as DDB draws them; half proficiency (Jack of All Trades) is the dot clipped to its left half.
  import { ddb } from "../../lib/ddb.svelte.js";
  let { level = null } = $props();
  const LABEL = { proficient: "Proficient", expertise: "Expertise", half: "Half Proficiency" };
</script>

<span aria-label={LABEL[level] || "Not Proficient"} title={LABEL[level] || "Not Proficient"}><span class="ddbc-tooltip">
  {#if level === "proficient"}
    {@html (ddb.icons.proficiency || "").replace('class="ddbc-svg', 'class="ddbc-svg ddbc-proficiency-icon ddbc-proficiency-level-icon')}
  {:else if level === "expertise"}
    <span class="ddbc-twice-proficiency-icon ddbc-proficiency-level-icon">{@html ddb.icons.expertise || ""}</span>
  {:else if level === "half"}
    <span class="ddbc-no-proficiency-icon ddbc-proficiency-level-icon ddb-half-proficiency">{@html ddb.icons.proficiency || ""}</span>
  {:else}
    <span class="ddbc-no-proficiency-icon ddbc-proficiency-level-icon"></span>
  {/if}
</span></span>
