<script>
  // The header's level line; with XP advancement (Home preference) DDB's XP bar, which opens Manage XP.
  import { show } from "../lib/pane.svelte.js";
  let { s } = $props();
  const fmt = (n) => Number(n).toLocaleString("en");
  const share = $derived(s.xp?.next ? Math.max(0, Math.min(1, (s.xp.total - s.xp.current) / (s.xp.next - s.xp.current))) : 1);
</script>

{#if s.xp}
  <div class="ddbc-character-progression-summary ddb-xp-summary" role="button" tabindex="0" title="Manage XP"
    onclick={() => show("xp")} onkeydown={(e) => e.key === "Enter" && show("xp")}>
    <div class="styles_xpBar__bXAND"><div class="ddbc-xp-bar">
      <div class="ddbc-xp-bar__item ddbc-xp-bar__item--cur">LVL {s.level}</div>
      <div class="ddbc-xp-bar__item ddbc-xp-bar__item--progress"><span class="ddbc-xp-bar__progress">
        <span class="ddbc-xp-bar__progress-inner" style="width: {share * 100}%"><span class="ddbc-xp-bar__progress-marker">
          <span class="ddbc-xp-bar__progress-marker-amount">{fmt(s.xp.total)} XP</span>
        </span></span>
      </span></div>
      <div class="ddbc-xp-bar__item ddbc-xp-bar__item--next" title={s.xp.next ? `${fmt(s.xp.next)} XP` : ""}>{s.xp.level_by_xp > s.level ? "LEVEL UP" : s.xp.next ? `LVL ${s.level + 1}` : "MAX"}</div>
    </div></div>
  </div>
{:else}
  <div class="ddbc-character-progression-summary"><div class="ddbc-character-progression-summary__level">Level {s.level}</div></div>
{/if}
