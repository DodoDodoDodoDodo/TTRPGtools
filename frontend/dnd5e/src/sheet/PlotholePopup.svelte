<script>
  // Editing a read-only character (second character without premium): the edit is not saved, and this asks
  // whether the character should really stay unchanged forever (Dodo, 2026-10-25). Condemning reloads the saved version.
  import { current, reloadCharacter } from "../lib/character.svelte.js";
  const name = $derived(current.character?.name || "this character");
  let noImage = $state(false);
  function condemn() {
    current.plothole = false;
    reloadCharacter();
  }
</script>

{#if current.plothole && current.locked}
  <div class="otyugh-backdrop">
    <div class="otyugh plothole" role="alertdialog" aria-modal="true" aria-labelledby="plothole-title">
      {#if !noImage}<img src="{window.DND5E.ddb}/img/plothole.webp" alt="A swirl of warped time" onerror={() => (noImage = true)} />{/if}
      <h2 id="plothole-title">Hey, we noticed you were about to throw {name} back into a Plothole, and deny them the character-development!</h2>
      <p>Are you sure about that?</p>
      <div class="otyugh-actions">
        <button type="button" class="otyugh-condemn" onclick={condemn}>Yes, condemn {name} to stagnant immortality</button>
        <a class="otyugh-save pitch-in" href="/#contrib">Save {name}</a>
      </div>
    </div>
  </div>
{/if}
