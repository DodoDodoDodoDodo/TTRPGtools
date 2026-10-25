<script>
  // Ask the rules helper. With `entry` ({name, text}) it is the side pane's "Explain this"; without, a question box.
  import { ask, chosenSources, loadSources } from "./explain.js";
  let { entry = null, sources = null } = $props();
  let question = $state("");
  let answer = $state("");
  let passages = $state([]);
  let error = $state("");
  let pitchIn = $state(null);
  let busy = $state(false);
  let asked = $state(false);
  async function run() {
    busy = true; asked = true; answer = ""; passages = []; error = ""; pitchIn = null;
    const ids = sources ?? chosenSources(await loadSources());
    await ask({ question: question.trim(), sources: ids, entry }, {
      onText: (t) => (answer += t),
      onDone: (p) => (passages = p),
      onError: (msg, link) => { error = msg; pitchIn = link || null; },
    });
    busy = false;
  }
</script>

<div class="ask-box" class:ask-box--entry={entry}>
  {#if entry}
    {#if !asked}<button type="button" class="ct-button character-button ddbc-button character-button-small" onclick={run}><span class="ct-button__content">Explain this</span></button>{/if}
  {:else}
    <form class="ask-form" onsubmit={(e) => { e.preventDefault(); if (question.trim() && !busy) run(); }}>
      <input type="text" placeholder="Ask a rules question, e.g. how does cover work?" bind:value={question} aria-label="Rules question" />
      <button type="submit" disabled={busy || !question.trim()}>{busy ? "Thinking…" : "Ask"}</button>
    </form>
  {/if}
  {#if asked}
    <div class="ask-answer" aria-live="polite">
      <p class="ask-label">// Rules helper (local model; check the cited pages)</p>
      {#if answer}<p>{answer}</p>{:else if busy}<p class="dim">Looking it up… the first question after a break waits for the model to load.</p>{/if}
      {#if error}<p class="ask-error">{error}{#if pitchIn} <a href={pitchIn}>Pitch in · get dodo-dodo premium</a>{/if}</p>{/if}
      {#if passages.length}
        <details class="ask-sources"><summary>Passages it read ({passages.length})</summary>
          {#each passages as p}<p><strong>{p.cite}</strong> · {p.book}: {p.title}<br /><span class="dim">{p.text}</span></p>{/each}
        </details>
      {/if}
    </div>
  {/if}
</div>
