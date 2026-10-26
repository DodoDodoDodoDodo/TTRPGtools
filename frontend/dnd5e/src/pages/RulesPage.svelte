<script>
  // "Other": one search over every rules text the app holds (names first, then words in the text), each result
  // opening in the side pane, plus the books with links to books.dodo-dodo.de or the files share.
  import { content } from "../lib/content.svelte.js";
  import { show } from "../lib/pane.svelte.js";
  import { book } from "../lib/format.js";
  import { canonFilter } from "../lib/noncanon.svelte.js";

  let query = $state("");
  let books = $state([]);
  let monsters = $state([]);
  $effect(() => {
    fetch(`${window.DND5E.start}api/books`).then((r) => (r.ok ? r.json() : { books: [] })).then((d) => (books = d.books || []));
  });

  // [label, entries, open(entry)] per kind; class features come from every class and subclass
  const KINDS = $derived([
    ["Spell", content.spells, (e) => show("spell", e.id)],
    ["Item", content.items.filter(canonFilter), (e) => show("item", e.id)],
    ["Feat", content.feats, (e) => show("feat", e.id)],
    ["Race", content.races, (e) => show("race", e.id)],
    ["Class option", content.optionalfeatures, (e) => show("optionalfeature", e.id)],
    ["Background", content.backgrounds, (e) => show("feature", e.name, { name: e.name, origin: "Background", book: e.book, page: e.page, entries: e.entries })],
    ["Class feature", content.classes.flatMap((c) => [...c.features.map((f) => ({ ...f, owner: c.name })),
      ...c.subclasses.flatMap((s) => s.features.map((f) => ({ ...f, owner: `${c.name}: ${s.name}` })))]),
      (e) => show("feature", e.name, { name: e.name, origin: e.owner, level: e.level, book: e.book, page: e.page, entries: e.entries })],
    ["Condition", content.conditions.filter((c) => c.source === "PHB"), (e) => show("condition", e.name)],
    ["Action", content.actions, (e) => show("action", e.name)],
  ]);
  const textOf = new WeakMap();
  const haystack = (e) => {
    if (!textOf.has(e)) textOf.set(e, JSON.stringify(e.entries || []).replace(/\{@\w+ ([^|}]*)[^}]*\}/g, "$1").toLowerCase());
    return textOf.get(e);
  };
  const results = $derived.by(() => {
    const q = query.trim().toLowerCase();
    if (q.length < 3) return [];
    const byName = [], byText = [];
    for (const [label, list, open] of KINDS) {
      for (const e of list) {
        if (e.name?.toLowerCase().includes(q)) byName.push({ label, e, open });
        else if (byText.length < 150 && haystack(e).includes(q)) byText.push({ label, e, open });
      }
    }
    byName.sort((a, b) => (a.e.name.toLowerCase().startsWith(q) ? 0 : 1) - (b.e.name.toLowerCase().startsWith(q) ? 0 : 1));
    return [...byName.slice(0, 150), ...byText];
  });
  let monsterTimer;
  $effect(() => {
    const q = query.trim();
    clearTimeout(monsterTimer);
    if (q.length < 3) { monsters = []; return; }
    monsterTimer = setTimeout(() => fetch(`${window.DND5E.start}api/monsters?q=${encodeURIComponent(q)}&official=1&limit=12`)
      .then((r) => (r.ok ? r.json() : { monsters: [] })).then((d) => (monsters = d.monsters || [])), 250);
  });
  function remember(name, detail, href) {
    try {
      const recent = JSON.parse(localStorage.getItem("dnd5e-recent") || "{}");
      recent.other = { name, detail, href };
      localStorage.setItem("dnd5e-recent", JSON.stringify(recent));
    } catch (_) { /* private window */ }
  }
  function open(r) {
    r.open(r.e);
    remember(r.e.name, r.label, `${window.DND5E.base}#/rules`);
  }
</script>

<section class="listing-page">
  <header class="listing-head">
    <h1>Rules and books</h1>
    <p class="dim">Search every spell, item, feat, race, background, class feature, condition and monster, then open the books themselves.</p>
  </header>
  <p class="dim">Questions go to the <strong>Rules helper</strong> button in the top bar; it answers from the books you tick there.</p>
  <h2 class="listing-subhead">Search</h2>
  <div class="listing-filters">
    <label class="rules-search">Search <input type="search" placeholder="A name or a word from the text, e.g. grapple, darkvision, Counterspell" bind:value={query} /></label>
    <span class="dim listing-count">{query.trim().length >= 3 ? `${results.length + monsters.length} results` : "3 letters or more"}</span>
  </div>
  {#if results.length || monsters.length}
    <div class="listing-table">
      <div class="listing-row listing-row--head rules-row"><span>Kind</span><span>Name</span><span>Source</span></div>
      {#each results as r}
        <div class="listing-row rules-row" role="button" tabindex="0" onclick={() => open(r)} onkeydown={(ev) => ev.key === "Enter" && open(r)}>
          <span class="dim">{r.label}{r.e.owner ? ` · ${r.e.owner}` : ""}</span><span class="listing-name">{r.e.name}</span><span class="dim">{book(r.e.book || r.e.source?.toLowerCase())}</span>
        </div>
      {/each}
      {#each monsters as m}
        <a class="listing-row rules-row" href={`${window.DND5E.start}monsters#${encodeURIComponent(m.id)}`} onclick={() => remember(m.name, "Monster", `${window.DND5E.start}monsters#${encodeURIComponent(m.id)}`)}>
          <span class="dim">Monster · CR {m.cr_text ?? m.cr}</span><span class="listing-name">{m.name}</span><span class="dim">{m.source}</span>
        </a>
      {/each}
    </div>
  {/if}

  <h2 class="listing-subhead">Books</h2>
  <p class="dim">The PDFs we own. A title opens the book in your browser; the Audiobookshelf page is its entry in our library.</p>
  <div class="books-grid">
    {#each books as b}
      <div class="book-card"><a class="book-title" href={b.url} target="_blank" rel="noopener">{b.title}</a>
        <span class="dim">PDF{#if b.shelf} · <a href={b.shelf} target="_blank" rel="noopener">Audiobookshelf page</a>{/if}</span></div>
    {:else}
      <p class="dim">No books found.</p>
    {/each}
  </div>
</section>
