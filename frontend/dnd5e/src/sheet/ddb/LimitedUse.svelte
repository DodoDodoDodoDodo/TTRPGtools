<script module>
  //: counter name -> the feature that describes it, when the names differ
  export const FEATURE_FOR = { "Ki Points": "Ki", "Sorcery Points": "Font of Magic", "Superiority Dice": "Combat Superiority" };
</script>

<script>
  // DDB's limited-use row under a feature snippet: one box per use (a count past 20), then the reset.
  import { current, changed } from "../../lib/character.svelte.js";

  let { counter } = $props();
  const RESET = { short: "Short Rest", long: "Long Rest", dawn: "Dawn", dusk: "Dusk", midnight: "Midnight", none: "No recharge", special: "Special" };
  function use(n) {
    const play = current.character.play;
    play.counters_used = { ...(play.counters_used || {}), [counter.name]: counter.used >= n ? n - 1 : n };
    changed(150);
  }
</script>

<div class="ct-feature-snippet__limited-use">
  <div class="ct-feature-snippet__limited-use-usages">
    {#if counter.max <= 20}
      <div class="ct-slot-manager ct-slot-manager--size-small">
        {#each Array.from({ length: counter.max }, (_, k) => k + 1) as n}
          <div role="checkbox" tabindex="0" aria-checked={counter.used >= n} aria-label="use" class="ct-slot-manager__slot ct-slot-manager__slot--interactive {counter.used >= n ? 'ct-slot-manager__slot--used' : ''}"
            onclick={() => use(n)} onkeydown={(e) => e.key === "Enter" && use(n)}></div>
        {/each}
      </div>
    {:else}
      <span>{counter.max - counter.used} of {counter.max} left</span>
    {/if}
  </div>
  <div class="ct-feature-snippet__limited-use-sep">/</div>
  <div class="ct-feature-snippet__limited-use-reset">{RESET[counter.reset] || counter.reset}{counter.regain ? `: regains ${counter.regain}` : ""}</div>
</div>
