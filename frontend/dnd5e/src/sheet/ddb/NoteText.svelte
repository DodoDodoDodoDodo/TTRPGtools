<script>
  // One DDB note block (ct-trait-content / ct-notes__note): the text, or "+ Add <label>" when empty.
  // A click edits it in place; DDB opens a side pane for this, which was never captured.
  import { changed } from "../../lib/character.svelte.js";

  let { target, key, label, addLabel = `+ Add ${label}`, baseClass = "ct-trait-content__content", emptyClass = "" } = $props();
  let editing = $state(false);
  const value = $derived(target?.[key] || "");
</script>

{#if editing}
  <textarea class="ddb-note-edit" rows="6" aria-label={label} value={value}
    oninput={(e) => { target[key] = e.target.value; changed(800); }} onblur={() => (editing = false)} {@attach (el) => el.focus()}></textarea>
{:else}
  <div class="{baseClass} {value ? '' : emptyClass} ddb-note-click" role="button" tabindex="0" onclick={() => (editing = true)} onkeydown={(e) => e.key === "Enter" && (editing = true)}>
    {#if value}{#each value.split("\n") as line}<p>{line}</p>{/each}{:else}{addLabel}{/if}
  </div>
{/if}
