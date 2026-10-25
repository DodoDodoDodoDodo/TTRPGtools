<script>
  // Background tab in DDB's markup (ct-description): All / Background / Characteristics / Appearance, the
  // background and its feature, the physical characteristics grid and the four personality blocks.
  // Backstory, allies and organizations are on the Notes tab, as on DDB.
  import Entries from "../lib/Entries.svelte";
  import NoteText from "./ddb/NoteText.svelte";
  import { current, changed } from "../lib/character.svelte.js";
  import { content } from "../lib/content.svelte.js";

  $effect.pre(() => {
    current.character.description ??= {};
  });
  const d = $derived(current.character.description || {});
  const s = $derived(current.sheet);
  let filter = $state("all");
  let editing = $state(null);

  const SIZES = { T: "Tiny", S: "Small", M: "Medium", L: "Large" };
  const race = $derived(current.character.race?.id ? content.byId.races[current.character.race.id] : null);
  const size = $derived((race?.size || []).map((x) => SIZES[x] || x).join(" or ") || "--");
  const feature = $derived(s.features.find((f) => f.kind === "background"));
  // DDB's order: two columns read across
  const PHYSICAL = [["alignment", "Alignment"], ["gender", "Gender"], ["eyes", "Eyes"], ["size", "Size"], ["height", "Height"],
    ["faith", "Faith"], ["hair", "Hair"], ["skin", "Skin"], ["age", "Age"], ["weight", "Weight"]];
  const TRAITS = [["traits", "Personality Traits"], ["ideals", "Ideals"], ["bonds", "Bonds"], ["flaws", "Flaws"]];
  const TABS = [["all", "All"], ["background", "Background"], ["characteristics", "Characteristics"], ["appearance", "Appearance"]];
  const showing = (key) => filter === "all" || filter === key;
</script>

<section class="ct-description">
  <h2 class="accessibility_screenreaderOnly__OEzRB">Description</h2>
  <div class="styles_tabFilter__50iSv">
    <div class="styles_buttons__hGhtB">
      {#each TABS as [key, label]}<button type="button" class={filter === key ? "styles_active__oWpHc" : ""} onclick={() => (filter = key)}>{label}</button>{/each}
    </div>
    <div class="styles_content__QjnYw">
      {#if showing("background")}
        <div class="ct-content-group">
          <div class="ct-content-group__header"><div class="ct-content-group__header-content">Background</div></div>
          <div class="ct-content-group__content">
            <div class="ct-background">
              <div class="ct-background__name">{s.background || "No background chosen"}</div>
              {#if feature}
                <div class="ct-background__feature">
                  <div class="ct-background__feature-name">Feature: {feature.name}</div>
                  <div class="ddbc-html-content ct-background__feature-description"><Entries entries={feature.entries} /></div>
                </div>
              {/if}
            </div>
          </div>
        </div>
      {/if}
      {#if showing("characteristics")}
        <div class="ct-content-group">
          <div class="ct-content-group__header"><div class="ct-content-group__header-content">Characteristics</div></div>
          <div class="ct-content-group__content">
            <div class="ct-description__physical styles_physical__2aytL">
              {#each PHYSICAL as [key, label]}
                <div class="styles_item__8bGe2">
                  <p class="styles_label__My0Jp">{label}</p>
                  {#if key === "size"}<p class="styles_value__mg89v">{size}</p>
                  {:else if editing === key}
                    <input class="ddb-note-edit" type="text" aria-label={label} value={d[key] || ""} {@attach (el) => el.focus()}
                      oninput={(e) => { d[key] = e.target.value; changed(800); }} onblur={() => (editing = null)} onkeydown={(e) => e.key === "Enter" && (editing = null)} />
                  {:else}<p class="styles_value__mg89v ddb-note-click" role="button" tabindex="0" onclick={() => (editing = key)} onkeydown={(e) => e.key === "Enter" && (editing = key)}>{d[key] || "--"}</p>{/if}
                </div>
              {/each}
            </div>
          </div>
        </div>
        <div class="ct-description__traits">
          {#each TRAITS as [key, label]}
            <div class="ct-trait-content" class:ct-trait-content--no-content={!d[key]}>
              <div class="ct-trait-content__heading">{label}</div>
              <NoteText target={d} {key} {label} />
            </div>
          {/each}
        </div>
      {/if}
      {#if showing("appearance")}
        <div class="ct-content-group">
          <div class="ct-content-group__header"><div class="ct-content-group__header-content">Appearance</div></div>
          <div class="ct-content-group__content">
            <div class="ct-trait-content" class:ct-trait-content--no-content={!d.appearance}><NoteText target={d} key="appearance" label="Appearance" addLabel="+ Add Appearance information" /></div>
          </div>
        </div>
      {/if}
    </div>
  </div>
</section>
