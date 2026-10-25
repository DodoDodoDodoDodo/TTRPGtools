<script>
  // The newer builder's start page (play/characters/build, DDB calls it the foyer) in DDB's markup: portrait,
  // name with suggested names, one card each for class, species (our "race") and background, and Create
  // Character, which leads to the finish page (join a campaign, view the sheet). See Options opens the same cards as the steps; DDB's
  // portrait picker and randomize buttons are not built yet.
  import CardChooser from "./CardChooser.svelte";
  import RaceChooser from "./RaceChooser.svelte";
  import ClassDetail from "./ClassDetail.svelte";
  import { current, changed } from "../lib/character.svelte.js";
  import { content, sourceAllowed } from "../lib/content.svelte.js";
  import { ddb, useStyles } from "../lib/ddb.svelte.js";
  import { route } from "../lib/router.svelte.js";
  import { show } from "../lib/pane.svelte.js";
  import { book, raceName, ABILITY_NAMES } from "../lib/format.js";
  import { backgroundCardGroups, ddbName } from "../lib/backgrounds.js";

  $effect(() => useStyles(["foyer.css", "species-cards.css"]));
  const assets = window.DND5E.ddb;
  const build = `${assets}/assets/www.dndbeyond.com/play/characters/build`;
  const icon = (key) => ddb.icons[key] || "";

  let choosing = $state(null);  // "class" | "race" | "background" while its cards are open
  let viewing = $state(null);   // class id whose class page is open
  let portraitOpen = $state(false);

  const c = $derived(current.character);
  const entry = $derived(c.classes?.[0]);
  const cls = $derived(entry ? content.byId.classes[entry.id] : null);
  const race = $derived(c.race?.id ? content.byId.races[c.race.id] : null);
  const background = $derived(c.background?.id ? content.byId.backgrounds[c.background.id] : null);
  const ready = $derived(!!(cls && race && background));
  const source = (b) => `${book(b)}${b === "phb" ? " (2014)" : ""}`.replace(/'/g, "’");

  // four names from the race's name tables (XGE), any race until one is picked; the shuffle draws again
  let seed = $state(0);
  const suggestions = $derived.by(() => {
    seed;
    const base = race ? raceName(race.name).split(" ").pop().toLowerCase() : null;
    const tables = content.names.filter((n) => !base || n.name.toLowerCase().includes(base));
    const pool = (tables.length ? tables : content.names).flatMap((n) => n.tables.flatMap((t) => t.names)).filter((n) => typeof n === "string");
    return Array.from({ length: 4 }, () => pool[Math.floor(Math.random() * pool.length)]).filter(Boolean);
  });

  function pickClass(id) {
    current.character.classes = [{ id, level: 1, skills: [], expertise: [], asi: {}, optionalfeatures: [], spells: { cantrips: [], known: [], prepared: [] } }];
    choosing = null; viewing = null;
    changed();
  }
  function pickRace(id) {
    current.character.race = { id, ability_block: 0, ability_choices: [], skills: [], languages: [] };
    choosing = null;
    changed();
  }
  function pickBackground(id) {
    current.character.background = { id, skills: [], languages: [], tools: [] };
    choosing = null;
    changed();
  }
  // DDB's randomize button on each card: any option the Home step's books allow
  const any = (list) => list[Math.floor(Math.random() * list.length)];
  function randomize(kind) {
    if (kind === "class") pickClass(any(classCards).items[0].id);
    else if (kind === "species") pickRace(any(content.races.filter((r) => sourceAllowed(r.book, c.preferences))).id);
    else pickBackground(any(backgroundCardGroups(c.preferences)).items[0].id);
  }
  const classCards = $derived(content.classes.filter((x) => sourceAllowed(x.book, c.preferences)).map((x) => ({
    name: x.name, items: [{ id: x.id, name: x.name, book: x.book }], book: x.book, art: x.ddbCard,
    blurb: `Hit Die d${x.hd.faces} · Saves ${x.proficiency.map((a) => ABILITY_NAMES[a]).join(", ")}` })));
</script>

{#snippet arrowButton(kind, label, aria, onclick)}
  <button type="button" class="Button-module__EPiRJW__baseButton Button-module__EPiRJW__{kind} Button-module__EPiRJW__small Button-module__EPiRJW__rightArrow" aria-label={aria} {onclick}>
    <span class="Button-module__EPiRJW__content">{label}</span>{@html icon("button-cap-right")}
  </button>
{/snippet}

{#snippet foyerCard(kind, title, question, picked, eyebrow, footer, bg, fg, onview)}
  <section class="styles-module__XmxzHG__foyerCard styles-module__XmxzHG__isInteractive {picked ? 'styles-module__XmxzHG__hasSelection' : kind === "class" ? '' : `styles-module__XmxzHG__${kind}`} page-module___8aEwW__{kind}"
    style="--background-image: url({bg}); {fg ? `--foreground-image: url(${fg});` : ''} --background-noise: url({build}/parchment-white-background.png);">
    {#if fg}<div class="styles-module__XmxzHG__foregroundImage"></div>{/if}
    <div class="styles-module__XmxzHG__contentWrapper"><div class="styles-module__XmxzHG__mainContent">
      <h2 class="styles-module__XmxzHG__title"><span class="styles-module__XmxzHG__eyebrow">{eyebrow}&nbsp;</span><span>{picked || title}</span></h2>
      {#if !picked}<p class="styles-module__XmxzHG__description">{question}</p>{/if}
      <div class="styles-module__XmxzHG__footer">
        {#if picked && footer}<p class="styles-module__XmxzHG__footerText">{footer}</p>{/if}
        <div class="styles-module__XmxzHG__cardActions">
          <button type="button" class="Button-module__EPiRJW__baseButton Button-module__EPiRJW__tertiary Button-module__EPiRJW__small styles-module__XmxzHG__randomizeButton" aria-label="Random {title.toLowerCase()}" onclick={() => randomize(kind)}><span class="Button-module__EPiRJW__content">{@html icon("nb-shuffle")}</span></button>
          {#if picked}
            <button type="button" class="Button-module__EPiRJW__baseButton Button-module__EPiRJW__secondary Button-module__EPiRJW__small" aria-label="Change {title.toLowerCase()}" onclick={() => (choosing = kind === "species" ? "race" : kind)}><span class="Button-module__EPiRJW__content">Change</span></button>
            {@render arrowButton("primary", "View", `View ${picked} Details`, onview)}
          {:else}
            {@render arrowButton(kind === "class" ? "hero" : "primary", "See Options", `See ${title.toLowerCase()} Options`, () => (choosing = kind === "species" ? "race" : kind))}
          {/if}
        </div>
      </div>
    </div></div>
  </section>
{/snippet}

{#snippet preview(where)}
  <div class="page-module___8aEwW__previewContainer page-module___8aEwW__{where}PreviewContainer">
    <section class="page-module___8aEwW__characterPreview">
      <div class="styles-module__a0NR4a__characterPortraitWrapper page-module___8aEwW__characterPortrait"
        style="--portrait-frame: url({build}/portraits/arch.svg); --portrait-mask: url({build}/portraits/mask.svg); --portrait-foreground: url({c.description?.avatar_url || `${build}/portraits/archer-tall.png`});">
        <div class="styles-module__a0NR4a__characterPortrait"><div class="styles-module__a0NR4a__portrait"></div></div>
        <div class="styles-module__FJBYHa__portraitModal styles-module__a0NR4a__modalButton" style="--current-portrait-background: url({build}/portraits/star-burst.png);">
          <button type="button" class="Button-module__EPiRJW__baseButton Button-module__EPiRJW__primary Button-module__EPiRJW__medium styles-module__FJBYHa__choosePortraitButton styles-module__FJBYHa__desktop" aria-label="Choose Portrait" onclick={() => (portraitOpen = !portraitOpen)}>
            <span class="Button-module__EPiRJW__content">{@html icon("nb-portrait")}<span>Choose Portrait</span></span>
          </button>
        </div>
      </div>
      {#if portraitOpen}
        <label class="ddb-foyer-portrait-url">Portrait image URL
          <input type="url" placeholder="https://…" value={c.description?.avatar_url || ""} oninput={(e) => { (current.character.description ??= {}).avatar_url = e.target.value || null; changed(600); }} /></label>
      {/if}
      <div class="styles-module__Nepbjq__characterName page-module___8aEwW__characterName">
        <div class="styles-module__Nepbjq__inputContainer">
          <label class="accessibility-module__5t3tra__screenreaderOnly" for="name-input-{where}">Choose a name</label>
          <input id="name-input-{where}" placeholder="Choose a name" maxlength="128" class="styles-module__Nepbjq__nameInput" autocomplete="off" spellcheck="false" type="text"
            value={c.name || ""} oninput={(e) => { current.character.name = e.target.value; changed(600); }} />
        </div>
        <fieldset class="styles-module__Aryy7a__nameSuggestionsSet">
          <legend class="styles-module__Aryy7a__suggestedNamesLabel">Suggested Names</legend>
          <ul class="styles-module__Aryy7a__suggestedNames">
            <li><button type="button" class="Button-module__EPiRJW__baseButton Button-module__EPiRJW__tertiary Button-module__EPiRJW__small styles-module__Aryy7a__shuffleButton" aria-label="Other names" onclick={() => seed++}><span class="Button-module__EPiRJW__content">{@html icon("nb-shuffle")}</span></button></li>
            {#each where === "mobile" ? suggestions.slice(0, 1) : suggestions as name}
              <li><button type="button" class="Tag-module__KetiBq__tag Tag-module__KetiBq__tagButton styles-module__Aryy7a__suggestedName" onclick={() => { current.character.name = name; changed(); }}>
                {@html icon("nb-tag-lead")}<div class="Tag-module__KetiBq__middle"><span class="Tag-module__KetiBq__label">{name}</span></div>{@html icon("nb-tag-trail")}</button></li>
            {/each}
          </ul>
        </fieldset>
      </div>
    </section>
  </div>
{/snippet}

{#snippet create(where)}
  <div class="page-module___8aEwW__createContainer page-module___8aEwW__{where}CreateContainer">
    <div class="page-module___8aEwW__buttonsWrapper"><div class="page-module___8aEwW__createButtonWrapper">
      <button type="button" class="Button-module__EPiRJW__baseButton Button-module__EPiRJW__hero Button-module__EPiRJW__medium Button-module__EPiRJW__doubleArrow page-module___8aEwW__createButton"
        aria-disabled={!ready} disabled={!ready} aria-label={ready ? "Create Character" : "Select a Class, Species and Background to create a character"}
        onclick={() => (location.hash = `#/c/${route.id}/builder/finish`)}>
        <span class="Button-module__EPiRJW__capContainer Button-module__EPiRJW__left">{@html icon("nb-hero-cap-left")}</span>
        <span class="Button-module__EPiRJW__content">Create Character</span>
        <span class="Button-module__EPiRJW__capContainer Button-module__EPiRJW__right">{@html icon("nb-hero-cap-right")}</span>
      </button>
    </div></div>
  </div>
{/snippet}

{#if viewing && content.byId.classes[viewing]}
  <ClassDetail cls={content.byId.classes[viewing]} onselect={() => pickClass(viewing)} onback={() => (viewing = null)} />
{:else if choosing === "class"}
  <button type="button" class="ddb-class-detail-back" onclick={() => (choosing = null)}>&larr; Back</button>
  <CardChooser heading="Choose a Class" noun="class" groups={classCards} learn={(id) => (viewing = id)} onpick={pickClass} />
{:else if choosing === "race"}
  <button type="button" class="ddb-class-detail-back" onclick={() => (choosing = null)}>&larr; Back</button>
  <RaceChooser onpick={pickRace} />
{:else if choosing === "background"}
  <button type="button" class="ddb-class-detail-back" onclick={() => (choosing = null)}>&larr; Back</button>
  <CardChooser heading="Choose a Background" noun="background" groups={backgroundCardGroups(c.preferences)} onpick={pickBackground} />
{:else}
  <div class="ddb-new-builder ddb-foyer">
    <div class="pages-module__kXd57W__wrapper" style="--page-background-image: url({build}/foyer/foyer-page.png);"><div class="pages-module__kXd57W__page">
      <div class="page-module___8aEwW__contentGrid">
        <div class="page-module___8aEwW__pageHeader"><div class="styles-module__HJ046W__pageHeader page-module___8aEwW__foyerHeader">
          <h1 class="styles-module__HJ046W__heading"><span class="styles-module__HJ046W__headingIntro">Ready, Set,</span>Start your story...</h1>
          <p class="styles-module__HJ046W__description">Your character is a combination of a Class, a Background, and a Race.</p>
        </div></div>
        {@render preview("mobile")}
        {@render create("mobile")}
        {@render foyerCard("class", "Class", "What are your vocations, special talents, and favored tactics?", cls?.name, cls ? source(cls.book) : "Choose", cls ? "Level 1" : "",
          cls?.ddbHero ? `${assets}/${cls.ddbHero}` : `${build}/foyer/foyer-class.png`, cls?.ddbFigure ? `${assets}/${cls.ddbFigure}` : null, () => (viewing = cls.id))}
        {@render foyerCard("species", "Race", "Who are your ancestors? What languages do they speak?", race ? raceName(race.name) : null, race ? source(race.book) : "Choose", "",
          race?.ddbArt ? `${assets}/${race.ddbArt}` : `${build}/foyer/foyer-origin-species.png`, null, () => show("race", race.id))}
        {@render foyerCard("background", "Background", "How did you spend the years leading up to a life of adventure?", background ? ddbName(background.name) : null, background ? source(background.book) : "Choose", "",
          `${build}/foyer/foyer-origin-background.png`, null, () => (location.hash = `#/c/${route.id}/builder/background`))}
        {@render create("desktop")}
        {@render preview("desktop")}
      </div>
    </div></div>
  </div>
{/if}
