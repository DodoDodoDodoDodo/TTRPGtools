<script>
  // Which books the rules helper searches: rules, adventures, other, each with its books (Dodo, 2026-10-25).
  // Only rules by default, so nobody gets adventure spoilers without asking; a DM ticks the adventure they run.
  import { loadSources, chosenSources, saveSources } from "./explain.js";
  let { selected = $bindable([]) } = $props();
  let all = $state([]);
  $effect(() => { loadSources().then((s) => { all = s; selected = chosenSources(s); }); });
  const GROUPS = [["rules", "Rules"], ["adventures", "Adventures"], ["other", "Other"]];
  const inGroup = (g) => all.filter((s) => s.group === g);
  const groupOn = (g) => inGroup(g).length && inGroup(g).every((s) => selected.includes(s.id));
  function setGroup(g, on) {
    const ids = inGroup(g).map((s) => s.id);
    selected = on ? [...new Set([...selected, ...ids])] : selected.filter((id) => !ids.includes(id));
    saveSources(selected);
  }
  function toggle(id) {
    selected = selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id];
    saveSources(selected);
  }
</script>

<details class="source-picker">
  <summary>Search in: {selected.length} of {all.length} books</summary>
  {#each GROUPS as [g, label]}
    <fieldset class="source-group">
      <legend><label><input type="checkbox" checked={groupOn(g)} onchange={(e) => setGroup(g, e.target.checked)} /> {label} ({inGroup(g).length})</label></legend>
      <div class="source-books">
        {#each inGroup(g) as s}<label><input type="checkbox" checked={selected.includes(s.id)} onchange={() => toggle(s.id)} /> {s.name}</label>{/each}
      </div>
    </fieldset>
  {/each}
</details>
