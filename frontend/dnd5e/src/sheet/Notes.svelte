<script>
  // Notes tab in DDB's markup (ct-notes): All / Orgs / Allies / Enemies / Backstory / Other.
  import NoteText from "./ddb/NoteText.svelte";
  import { current } from "../lib/character.svelte.js";

  $effect.pre(() => {
    current.character.description ??= {};
  });
  let filter = $state("all");
  // [tab, heading, where the text lives, key]; "Other" is the sheet's free notes
  const GROUPS = $derived([
    ["orgs", "Organizations", current.character.description, "organizations"],
    ["allies", "Allies", current.character.description, "allies"],
    ["enemies", "Enemies", current.character.description, "enemies"],
    ["backstory", "Backstory", current.character.description, "backstory"],
    ["other", "Other", current.character, "notes"],
  ]);
  const TABS = [["all", "All"], ["orgs", "Orgs"], ["allies", "Allies"], ["enemies", "Enemies"], ["backstory", "Backstory"], ["other", "Other"]];
</script>

<section class="ct-notes">
  <h2 class="accessibility_screenreaderOnly__OEzRB">Notes</h2>
  <div class="styles_tabFilter__50iSv">
    <div class="styles_buttons__hGhtB">
      {#each TABS as [key, label]}<button type="button" class={filter === key ? "styles_active__oWpHc" : ""} onclick={() => (filter = key)}>{label}</button>{/each}
    </div>
    <div class="styles_content__QjnYw">
      {#each GROUPS.filter(([tab]) => filter === "all" || filter === tab) as [tab, heading, target, key] (tab)}
        <div class="ct-content-group">
          <div class="ct-content-group__header"><div class="ct-content-group__header-content">{heading}</div></div>
          <div class="ct-content-group__content">
            <NoteText {target} {key} label={heading} baseClass="ct-notes__note" emptyClass="ct-notes__note--no-content" />
          </div>
        </div>
      {/each}
    </div>
  </div>
</section>
