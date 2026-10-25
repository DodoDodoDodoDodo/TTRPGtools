<script>
  // Campaigns the viewer runs as DM: who plays in each, and adding or removing characters (a character may be in
  // several campaigns). DDB has no such page; the encounter manager will take its party from these lists.
  import { api } from "./lib/api.js";

  let { characters = [], onchange } = $props();
  const me = window.DND5E.user || "";
  let list = $state([]);
  let error = $state("");
  let newName = $state("");
  const mine = $derived(list.filter((c) => c.dm && c.dm === me));
  const nameOf = (id) => characters.find((r) => r.id === id)?.name || id;

  async function load() {
    try { list = await api.campaigns(); } catch (e) { error = e.message; }
  }
  $effect(() => { load(); });
  async function act(promise) {
    try { await promise; error = ""; await load(); onchange?.(); } catch (e) { error = e.message; }
  }
</script>

<section class="dm-campaigns">
    <h2>Campaigns you run</h2>
    <p class="dim">Start a campaign and you are its DM. Add any character; a character can play in several campaigns. The encounter builder takes its party from here.</p>
    <form class="dm-campaign-new" onsubmit={(e) => { e.preventDefault(); if (newName.trim()) act(api.createCampaign(newName.trim()).then(() => (newName = ""))); }}>
      <input type="text" placeholder="Campaign name" bind:value={newName} aria-label="New campaign name" />
      <button type="submit" disabled={!newName.trim()}>Start a campaign</button>
    </form>
    {#each mine as c (c.id)}
      <div class="dm-campaign">
        <h3>{c.name} <button type="button" class="link small danger" onclick={() => confirm(`Delete the campaign "${c.name}"? Its characters stay; only the campaign and its member list go.`) && act(api.deleteCampaign(c.id))}>Delete campaign</button></h3>
        <ul>
          {#each c.characters as id}
            <li>{nameOf(id)} <button type="button" class="link small" aria-label="Remove {nameOf(id)} from {c.name}" onclick={() => act(api.leaveCampaign(c.id, id))}>Remove</button></li>
          {:else}<li class="dim">No characters yet.</li>{/each}
        </ul>
        <label>Add character
          <select value="" onchange={(e) => { if (e.target.value) act(api.joinCampaign(c.id, e.target.value)); e.target.value = ""; }}>
            <option value="">choose a character</option>
            {#each characters.filter((r) => !c.characters.includes(r.id)) as r (r.id)}<option value={r.id}>{r.name || "Unnamed"}{r.owner ? ` (${r.owner})` : ""}</option>{/each}
          </select>
        </label>
      </div>
    {/each}
    {#if error}<p class="banner error">{error}</p>{/if}
</section>
