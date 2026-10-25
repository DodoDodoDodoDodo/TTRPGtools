<script>
  // DDB's proficiency groups (armor, weapons, tools, languages), shared by desktop and phone.
  import { current } from "../lib/character.svelte.js";
  import { title } from "../lib/format.js";
  const s = $derived(current.sheet);
</script>

<div class="ct-proficiency-groups">
  {#each [["armor", "Armor"], ["weapons", "Weapons"], ["tools", "Tools"], ["languages", "Languages"]] as [k, label]}
    <div class="ct-proficiency-groups__group">
      <div class="ct-proficiency-groups__group-label">{label}</div>
      <div class="ct-proficiency-groups__group-items">
        {#each s.proficiencies[k] as item, i}<span class="ddbc-tooltip"><span class="ct-proficiency-groups__group-item">{title(item)}{i < s.proficiencies[k].length - 1 ? ", " : ""}</span></span>{:else}None{/each}
      </div>
    </div>
  {/each}
</div>
