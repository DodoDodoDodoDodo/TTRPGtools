<script>
  // DDB's skills table (ct-skills), shared by the desktop skills box and the phone Skills section.
  import { current } from "../lib/character.svelte.js";
  import { title } from "../lib/format.js";
  import Num from "./ddb/Num.svelte";
  import Prof from "./ddb/Prof.svelte";
  const s = $derived(current.sheet);
</script>

<div class="ct-skills" role="table">
  <div class="ct-skills__header" role="row">
    <div class="ct-skills__col--proficiency" role="columnheader"><abbr title="Proficiency" class="ct-skills__heading">Prof</abbr></div>
    <div class="ct-skills__col--stat" role="columnheader"><abbr title="Modifier" class="ct-skills__heading">Mod</abbr></div>
    <div class="ct-skills__col--skill" role="columnheader"><span class="ct-skills__heading">Skill</span></div>
    <div class="ct-skills__col--modifier" role="columnheader"><span class="ct-skills__heading">Bonus</span></div>
  </div>
  <div class="ct-skills__list" role="rowgroup">
    {#each Object.entries(s.skills) as [name, sk]}
      <div class="ct-skills__item" role="row">
        <div class="ct-skills__col--proficiency" role="cell"><Prof level={sk.proficiency} /></div>
        <div class="ct-skills__col--stat" role="cell">{sk.ability.toUpperCase()}</div>
        <div class="ct-skills__col--skill" role="cell">{title(name)}</div>
        <div class="ct-skills__col--modifier" role="cell"><button type="button" class="F8U5pq_button integrated-dice__container"><Num value={sk.modifier} />{sk.overridden ? "*" : ""}</button></div>
      </div>
    {/each}
    {#each s.custom_skills || [] as sk}
      <div class="ct-skills__item ddb-custom-skill" role="row">
        <div class="ct-skills__col--proficiency" role="cell"><Prof level={sk.proficiency} /></div>
        <div class="ct-skills__col--stat" role="cell">{sk.ability ? sk.ability.toUpperCase() : "--"}</div>
        <div class="ct-skills__col--skill" role="cell">{sk.name}</div>
        <div class="ct-skills__col--modifier" role="cell"><button type="button" class="F8U5pq_button integrated-dice__container"><Num value={sk.modifier} /></button></div>
      </div>
    {/each}
  </div>
</div>
