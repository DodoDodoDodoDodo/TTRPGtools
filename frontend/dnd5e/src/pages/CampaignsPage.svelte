<script>
  // Campaigns: the ones you run (start, add and remove characters: DmCampaigns), then every campaign with its DM
  // and party, each character linking to its sheet. #/campaigns/<id> scrolls to that campaign.
  import { api } from "../lib/api.js";
  import DmCampaigns from "../DmCampaigns.svelte";

  let { focus = null } = $props();
  let campaigns = $state([]);
  let characters = $state([]);
  let error = $state("");
  async function load() {
    try { [campaigns, characters] = await Promise.all([api.campaigns(), api.list()]); } catch (e) { error = e.message; }
  }
  $effect(() => { load(); });
  const charOf = (id) => characters.find((c) => c.id === id);
  $effect(() => {
    if (focus && campaigns.length) document.getElementById(`campaign-${focus}`)?.scrollIntoView({ block: "center" });
  });
</script>

<section class="listing-page">
  <header class="listing-head">
    <h1>Campaigns</h1>
    <p class="dim">Anyone can start a campaign and becomes its DM. The encounter builder takes its party from a campaign.</p>
  </header>
  {#if error}<p class="banner error">{error}</p>{/if}
  <DmCampaigns {characters} onchange={load} />
  <h2 class="listing-subhead">All campaigns</h2>
  <div class="campaign-grid">
    {#each campaigns as c (c.id)}
      <article class="campaign-card" class:campaign-card--focus={c.id === focus} id="campaign-{c.id}">
        <h3>{c.name}</h3>
        <p class="dim">DM: {c.dm || "nobody yet"} · {c.characters.length} character{c.characters.length === 1 ? "" : "s"}</p>
        {#if c.description}<p>{c.description}</p>{/if}
        <ul class="campaign-party">
          {#each c.characters as id}
            {@const ch = charOf(id)}
            <li>{#if ch}<a href={`#/c/${id}/sheet`}>{ch.name || "Unnamed"}</a> <span class="dim">{ch.classes.join(" / ")}{ch.owner ? ` · ${ch.owner}` : ""}</span>{:else}<span class="dim">{id}</span>{/if}</li>
          {:else}
            <li class="dim">No characters yet.</li>
          {/each}
        </ul>
      </article>
    {:else}
      <p class="dim">No campaigns yet. Start one above.</p>
    {/each}
  </div>
</section>
