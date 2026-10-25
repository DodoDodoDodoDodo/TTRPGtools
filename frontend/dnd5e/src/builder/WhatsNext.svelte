<script>
  // What's Next in DDB's markup (builder/whats-next). Ours adds the list of open choices and rules problems
  // (DDB only marks those with "!" in the nav); DDB's campaign links are left out, there are no campaigns here.
  import { current } from "../lib/character.svelte.js";
  import { route } from "../lib/router.svelte.js";
  import { ddb } from "../lib/ddb.svelte.js";

  let { open = [], href } = $props();
  const STEP_LABEL = { home: "Home", class: "Class", spells: "Class", background: "Background", race: "Race", abilities: "Abilities", equipment: "Equipment" };
  const problems = $derived(current.sheet?.problems || []);
</script>

<div class="page_page__NWf2H ddb-whats-next">
  <p>Once you have completed creating your character, you can view your statistics on the digital character sheet or export it for printing.</p>
  <div class="styles_buttonWrapper__gSJI5">
    <a class="Button_button__B9Kr5 ButtonVariants_primary__TMQ5y ButtonSizes_large__KHVgJ styles_builder__iFp8R styles_button__qhAIh" aria-disabled="false" href={`#/c/${route.id}/sheet`}>{@html ddb.icons["view-sheet"] || ""}<span class="styles_buttonText__YmHHQ">View Character Sheet</span></a>
    <button type="button" class="Button_button__B9Kr5 ButtonVariants_primary__TMQ5y ButtonSizes_large__KHVgJ styles_builder__iFp8R styles_button__qhAIh" aria-disabled="false" onclick={() => (location.hash = `#/c/${route.id}/print`)}>{@html ddb.icons["export-pdf"] || ""}Export to PDF</button>
  </div>
  {#if open.length || problems.length}
    <div class="styles_section__enRzv ddb-whats-next-open">
      {#if open.length}
        <h2 class="page_title__xL1kF">Still to Choose</h2>
        <ul>{#each open as c}<li><a href={href(c.step === "spells" ? "class" : c.step)}>{STEP_LABEL[c.step] || c.step}</a>: {c.what}</li>{/each}</ul>
      {/if}
      {#if problems.length}
        <h2 class="page_title__xL1kF">Problems</h2>
        <ul class="problems">{#each problems as p}<li>{p}</li>{/each}</ul>
      {/if}
    </div>
  {/if}
  <div class="styles_section__enRzv">
    <a class="Button_button__B9Kr5 ButtonVariants_primary__TMQ5y ButtonSizes_medium__uHe8x styles_builder-text__RlIXo styles_button__qhAIh" href="#/">View all my characters</a>
    <h2 class="page_title__xL1kF">Come Together</h2>
    <p>Most D&amp;D characters don't work alone. Each character plays a role within a party, a group of adventurers working together for a common purpose. Talk to your fellow players and your DM to decide whether your characters know one another, how they met, and what sorts of quests the group might undertake.</p>
  </div>
</div>
