<script>
  // Which campaigns this character plays in, with Join / Leave and a card to start a new one. DDB's finish page
  // ends on "How to get started" cards (find a group, find a DM); ours ends here, since the table already exists.
  // The cards use DDB's finish-page card markup (WO0BgG); the encounter manager will take its party from these.
  import { api } from "../lib/api.js";
  import { useStyles } from "../lib/ddb.svelte.js";

  let { characterId, compact = false } = $props();
  $effect(() => useStyles(["foyer.css"]));
  const build = `${window.DND5E.ddb}/assets/www.dndbeyond.com/play/characters/build`;
  let list = $state([]);
  let error = $state("");
  let newName = $state("");
  const me = window.DND5E.user || "";

  async function load() {
    try { list = await api.campaigns(); error = ""; } catch (e) { error = e.message; }
  }
  $effect(() => { load(); });
  async function act(promise) {
    try { await promise; await load(); } catch (e) { error = e.message; }
  }
  const inIt = (c) => c.characters.includes(characterId);
</script>

<div class="styles-module__tmzXDW__cardList styles-module__tmzXDW__lg styles-module__raWPyq__ctaCardList ddb-campaign-cards" class:ddb-campaign-cards--compact={compact}>
  <div class="styles-module__tmzXDW__cards">
    {#each list as c (c.id)}
      <section class="styles-module__WO0BgG__container" style="--desktop-background-url: url({build}/finish/card_background_{inIt(c) ? 'gold' : 'grey'}.webp); --desktop-foreground-url: url({build}/finish/foreground_{inIt(c) ? 1 : 2}.webp); --mobile-background-url: url({build}/finish/card_background_{inIt(c) ? 'gold' : 'grey'}.webp); --mobile-foreground-url: url({build}/finish/foreground_{inIt(c) ? 1 : 2}.webp);">
        <div class="styles-module__WO0BgG__backgroundImageContainer"><div class="styles-module__WO0BgG__backgroundImage"></div><div class="styles-module__WO0BgG__foregroundImage"></div><div class="styles-module__WO0BgG__gradient"></div></div>
        <div class="styles-module__WO0BgG__contentWrapper">
          <div>
            <h3 class="styles-module__WO0BgG__title">{c.name}</h3>
            <p class="ddb-campaign-meta">DM: {c.dm || "nobody yet"} · {c.characters.length} character{c.characters.length === 1 ? "" : "s"}{inIt(c) ? " · this character plays here" : ""}</p>
          </div>
          <div class="styles-module__WO0BgG__footer">
            {#if inIt(c)}
              <button type="button" class="Button-module__EPiRJW__baseButton Button-module__EPiRJW__secondary Button-module__EPiRJW__medium" onclick={() => act(api.leaveCampaign(c.id, characterId))}><span class="Button-module__EPiRJW__content">Leave Campaign</span></button>
            {:else}
              <button type="button" class="Button-module__EPiRJW__baseButton Button-module__EPiRJW__primary Button-module__EPiRJW__medium" onclick={() => act(api.joinCampaign(c.id, characterId))}><span class="Button-module__EPiRJW__content">Join Campaign</span></button>
            {/if}
          </div>
        </div>
      </section>
    {/each}
    <section class="styles-module__WO0BgG__container" style="--desktop-background-url: url({build}/finish/card_background_grey.webp); --mobile-background-url: url({build}/finish/card_background_grey.webp);">
      <div class="styles-module__WO0BgG__backgroundImageContainer"><div class="styles-module__WO0BgG__backgroundImage"></div><div class="styles-module__WO0BgG__gradient"></div></div>
      <div class="styles-module__WO0BgG__contentWrapper">
        <div><h3 class="styles-module__WO0BgG__title">Start a New Campaign</h3><p class="ddb-campaign-meta">You become its DM{me ? ` (${me})` : ""}; this character joins it.</p></div>
        <div class="styles-module__WO0BgG__footer ddb-campaign-new">
          <input type="text" placeholder="Campaign name" bind:value={newName} aria-label="New campaign name" />
          <button type="button" class="Button-module__EPiRJW__baseButton Button-module__EPiRJW__primary Button-module__EPiRJW__medium" disabled={!newName.trim()}
            onclick={() => act(api.createCampaign(newName).then((c) => api.joinCampaign(c.id, characterId)).then(() => (newName = "")))}><span class="Button-module__EPiRJW__content">Start</span></button>
        </div>
      </div>
    </section>
  </div>
  {#if error}<p class="banner error">{error}</p>{/if}
</div>
