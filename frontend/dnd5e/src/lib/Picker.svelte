<script>
  // Pick up to `max` entries from `options` ({id, name, note?, kind?}); the name opens the detail pane.
  import { show } from "./pane.svelte.js";

  let { options = [], selected = [], max = 1, onchange, label = "", filterable = false } = $props();
  let query = $state("");

  const shown = $derived(
    filterable && query.trim()
      ? options.filter((o) => o.name.toLowerCase().includes(query.trim().toLowerCase()))
      : options,
  );

  function toggle(id) {
    let next = selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id];
    if (max === 1 && !selected.includes(id)) next = [id];
    if (next.length > max) return;
    onchange(next);
  }
</script>

<div class="picker">
  {#if label}<div class="picker-head"><strong>{label}</strong> <span class="count" class:full={selected.length >= max}>{selected.length} of {max} chosen</span></div>{/if}
  {#if filterable}<input class="picker-filter" type="search" placeholder="Filter by name" bind:value={query} aria-label="Filter {label}" />{/if}
  <ul>
    {#each shown as o (o.id)}
      {@const on = selected.includes(o.id)}
      <li class:on>
        <label>
          <input type={max === 1 ? "radio" : "checkbox"} checked={on} disabled={!on && max > 1 && selected.length >= max} onchange={() => toggle(o.id)} />
          <span class="mark" aria-hidden="true">{on ? "●" : "○"}</span>
          <span>{o.name}</span>
          {#if o.note}<span class="note">{o.note}</span>{/if}
        </label>
        {#if o.kind}<button type="button" class="info" onclick={() => show(o.kind, o.id)} aria-label="Details of {o.name}">Details</button>{/if}
      </li>
    {/each}
  </ul>
</div>
