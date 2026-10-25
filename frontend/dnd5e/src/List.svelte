<script>
  import DmCampaigns from "./DmCampaigns.svelte";
  import { design } from "./lib/design.svelte.js";
  // "My Characters" laid out like DDB's character list: a dark title band, one big create button,
  // import on request, a name search, and one card per character (class art strip, framed portrait,
  // quiet text links). Admins hand characters to players from the card.
  import { onMount } from "svelte";
  import { api, frame } from "./lib/api.js";
  import { go } from "./lib/router.svelte.js";
  import { content } from "./lib/content.svelte.js";
  import { raceName, BACKDROPS } from "./lib/format.js";

  let rows = $state([]);
  let name = $state("");
  let ddbRef = $state("");
  let busy = $state(false);
  let error = $state(null);
  let pitchIn = $state(null);
  let panel = $state(null); // "create" | "import" | null
  let query = $state("");
  let sortBy = $state("updated");
  // DDB's My Characters sort options
  const SORTS = { updated: ["Last saved", (a, b) => String(b.updated || "").localeCompare(String(a.updated || ""))],
    created: ["Created", (a, b) => String(b.created || "").localeCompare(String(a.created || ""))],
    name: ["Name", (a, b) => String(a.name || "").localeCompare(String(b.name || ""))],
    level: ["Level", (a, b) => (b.level || 0) - (a.level || 0)] };

  async function refresh() {
    try {
      rows = await api.list();
    } catch (e) {
      error = e.message;
    }
  }
  onMount(refresh);

  function fail(e) {
    error = e.message;
    pitchIn = e.pitchIn;
    doomed = e.doomed;
  }

  // dodo-dodo premium (Dodo, 2026-10-22): after a refused second character, anything but pitching in asks
  // whether the character should really go to the Otyugh. Browsers only allow their own generic warning
  // on closing the tab, so that is all beforeunload can do.
  let doomed = $state(null);
  let otyugh = $state(false);
  const PITCH_IN = "/#contrib";
  function condemn() {
    doomed = null;
    otyugh = false;
    error = null;
    pitchIn = null;
  }
  function interrupt(event) {
    if (!doomed || otyugh) return;
    if (event.target.closest?.(".pitch-in, .otyugh")) return;
    if (event.type === "keydown" && ["Shift", "Control", "Alt", "Meta"].includes(event.key)) return;
    event.preventDefault();
    event.stopPropagation();
    otyugh = true;
  }
  function warnOnLeave(event) {
    if (!doomed) return;
    event.preventDefault();
    event.returnValue = "";
  }
  onMount(() => {
    document.addEventListener("click", interrupt, true);
    document.addEventListener("keydown", interrupt, true);
    window.addEventListener("beforeunload", warnOnLeave);
    return () => {
      document.removeEventListener("click", interrupt, true);
      document.removeEventListener("keydown", interrupt, true);
      window.removeEventListener("beforeunload", warnOnLeave);
    };
  });
  async function create(event) {
    event.preventDefault();
    busy = true;
    try {
      const data = await api.create(name.trim() || "New character");
      go(`/c/${data.id}/builder/${design.mode === "new" ? "start" : "home"}`);  // the new design starts on DDB's start page
    } catch (e) {
      fail(e);
    } finally {
      busy = false;
    }
  }
  async function importDdb(event) {
    event.preventDefault();
    busy = true;
    error = null;
    try {
      const data = await api.importDdb(ddbRef);
      go(`/c/${data.id}/sheet`);
    } catch (e) {
      fail(e);
    } finally {
      busy = false;
    }
  }
  async function copy(row) {
    try { await api.copy(row.id); refresh(); } catch (e) { fail(e); }
  }
  async function remove(row) {
    if (!confirm(`Delete ${row.name}? It goes to the trash folder on the server and can be restored by hand.`)) return;
    await api.remove(row.id);
    refresh();
  }

  const ASSETS = window.DND5E.ddb;
  const DEFAULT_AVATAR = `${ASSETS}/assets/www.dndbeyond.com/Content/Skins/Waterdeep/images/characters/default-avatar-builder.png`;
  const backdropOf = (row) => (row.backdrop?.startsWith("http") ? row.backdrop : BACKDROPS.includes(row.backdrop) ? `${ASSETS}/img/backdrops/${row.backdrop}.jpg` : null);
  const themeOf = (row) => (row.theme || "#c53131").replace("#", "");
  const savedAt = (iso) => (iso ? new Date(iso).toLocaleString(undefined, { dateStyle: "short", timeStyle: "short" }) : "");
  const race = (id) => raceName(content.byId.races[id]?.name || "");
  const shown = $derived(rows.filter((r) => !query.trim() || `${r.name} ${r.owner || ""}`.toLowerCase().includes(query.trim().toLowerCase())).sort(SORTS[sortBy][1]));

  // Admins hand characters to players; the list holds genuinely active users unless "everyone" is asked for.
  const admin = !!window.DND5E.admin;
  let users = $state([]);
  let everyone = $state(false);
  let usersError = $state(null);
  async function loadUsers() {
    try {
      users = (await api.users(everyone)).users;
      usersError = null;
    } catch (e) {
      usersError = e.message;
    }
  }
  onMount(() => { if (admin) loadUsers(); });
  async function assign(row, owner) {
    if (!owner || owner === row.owner) return;
    try {
      await api.assign(row.id, owner);
      refresh();
    } catch (e) {
      fail(e);
    }
  }
</script>

<section class="mc-page">
  <header class="mc-band">
    <div class="mc-band-inner">
      <h1>My Characters</h1>
      <span class="mc-count">{rows.length} {rows.length === 1 ? "character" : "characters"} · 2014 rules</span>
    </div>
  </header>

  <div class="mc-toolbar">
    <button type="button" class="mc-create" onclick={() => (panel = panel === "create" ? null : "create")} aria-expanded={panel === "create"}>+ Create a Character</button>
    <button type="button" class="mc-secondary" onclick={() => (panel = panel === "import" ? null : "import")} aria-expanded={panel === "import"}>Import from D&amp;D Beyond</button>
    <input class="mc-search" type="search" placeholder="Search by name or player" bind:value={query} aria-label="Search characters" />
    <label class="mc-sort">Sort by <select bind:value={sortBy}>{#each Object.entries(SORTS) as [key, [label]]}<option value={key}>{label}</option>{/each}</select></label>
  </div>

  {#if panel === "create"}
    <form class="mc-panel" onsubmit={create}>
      <label>Character name <input type="text" bind:value={name} placeholder="You can change it later" /></label>
      <button type="submit" class="mc-create" disabled={busy}>Start building</button>
    </form>
  {:else if panel === "import"}
    <form class="mc-panel" onsubmit={importDdb}>
      <label>D&amp;D Beyond URL or number <input type="text" bind:value={ddbRef} placeholder="https://www.dndbeyond.com/characters/…" /></label>
      <button type="submit" class="mc-create" disabled={busy || !ddbRef.trim()}>Import</button>
      <p class="mc-panel-hint">The character must be Public on D&amp;D Beyond: open it there, Edit, then on Home scroll all the way down to Character Privacy and set it to <strong>Public</strong>. Picks that are not 2014 content are listed as problems.</p>
    </form>
  {/if}

  {#if error}<p class="banner error">{error}{#if pitchIn} <a class="button pitch-in" href={pitchIn}>Pitch in · get dodo-dodo premium</a>{/if}</p>{/if}

  {#if otyugh && doomed}
    <div class="otyugh-backdrop">
      <div class="otyugh" role="alertdialog" aria-modal="true" aria-labelledby="otyugh-title">
        <img src="{ASSETS}/img/monsters/otyugh.webp" alt="An otyugh, mouth open" />
        <h2 id="otyugh-title">Hey, we noticed you were about to feed {doomed} to a hungry Otyugh!</h2>
        <p>Are you sure about that?</p>
        <div class="otyugh-actions">
          <button type="button" class="otyugh-condemn" onclick={condemn}>Yes, condemn {doomed} to a cruel death</button>
          <a class="otyugh-save pitch-in" href={PITCH_IN} onclick={() => { doomed = null; }}>Save {doomed}</a>
        </div>
      </div>
    </div>
  {/if}

  {#if admin}
    <p class="mc-admin">
      // Admin: hand a character to a player with "Assign to"; the list shows {everyone ? "every account" : "genuinely active users"}.
      <label><input type="checkbox" bind:checked={everyone} onchange={loadUsers} /> show everyone</label>
      {#if usersError}<span class="char-admin-error">{usersError}</span>{/if}
    </p>
  {/if}

  <DmCampaigns characters={rows} onchange={refresh} />

  <div class="char-grid">
    {#each shown as row (row.id)}
      <article class="char-card">
        <img class="char-card-frame" src={frame("saving-throws", themeOf(row))} alt="" aria-hidden="true" />
        <div class="char-card-art" style={backdropOf(row) ? `background-image: url(${backdropOf(row)})` : ""}></div>
        <div class="char-card-body">
          <a class="char-card-portrait" href={`#/c/${row.id}/sheet`} style="--card-theme: #{themeOf(row)}; background-image: url({row.avatar || DEFAULT_AVATAR});" aria-label="Open {row.name || 'the character'}"></a>
          <div class="char-card-info">
            <h3><a href={`#/c/${row.id}/sheet`}>{row.name || "Unnamed"}</a></h3>
            <p class="meta">Level {row.level || 0}{race(row.race) ? ` | ${race(row.race)}` : ""}{row.classes.length ? ` | ${row.classes.join(" / ")}` : ""}</p>
            {#if row.campaigns?.length}<p class="meta char-card-campaigns">Campaign{row.campaigns.length > 1 ? "s" : ""}: {row.campaigns.join(", ")}</p>{/if}
            <p class="meta dim">{row.owner ? `Player: ${row.owner}` : "No player yet"}{row.updated ? ` · saved ${savedAt(row.updated)}` : ""}</p>
          </div>
        </div>
        <nav class="char-card-links" aria-label="{row.name}">
          <a href={`#/c/${row.id}/sheet`}>View</a>
          <a href={`#/c/${row.id}/builder`}>Edit</a>
          <button type="button" onclick={() => copy(row)}>Copy</button>
          {#if row.owner === window.DND5E.user || window.DND5E.user === "takahe"}<button type="button" onclick={() => remove(row)}>Delete</button>{/if}
        </nav>
        {#if admin}
          <label class="char-assign">Assign to
            <select value={row.owner || ""} onchange={(e) => assign(row, e.target.value)}>
              <option value="" disabled>choose a player</option>
              {#if row.owner && !users.some((u) => u.name === row.owner)}<option value={row.owner}>{row.owner}</option>{/if}
              {#each users as u (u.name)}<option value={u.name}>{u.name}{u.alias ? ` (${u.alias})` : ""}{everyone ? ` · ${u.tier}` : ""}</option>{/each}
            </select>
          </label>
        {/if}
      </article>
    {:else}
      <p class="hint">{rows.length ? "No character matches the search." : "No characters yet. Create one or import it from D&D Beyond."}</p>
    {/each}
  </div>
</section>
