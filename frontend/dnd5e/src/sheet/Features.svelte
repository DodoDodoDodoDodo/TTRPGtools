<script>
  // Features & Traits tab in DDB's markup (ct-features): All / Class Features / Racial Traits / Feats tabs,
  // one "<Class> Features" block per class in level order, snippets with the first paragraph, the picks made
  // as choices and limited-use boxes. A heading opens the full text in the side pane. The background feature
  // stays on the Background tab, as on DDB.
  import Tagged from "../lib/Tagged.svelte";
  import { current } from "../lib/character.svelte.js";
  import { route } from "../lib/router.svelte.js";
  import { show } from "../lib/pane.svelte.js";
  import { content } from "../lib/content.svelte.js";
  import { book, raceName, title, ABILITY_NAMES } from "../lib/format.js";
  import LimitedUse, { FEATURE_FOR } from "./ddb/LimitedUse.svelte";

  const s = $derived(current.sheet);
  let filter = $state("all");
  // Class options (invocations, maneuvers, styles) are listed as choices under the feature that grants them.
  // (5etools folds Combat Superiority into the "Battle Master" feature, hence two names for maneuvers.)
  const OPTION_PARENT = { EI: ["Eldritch Invocations"], "MV:B": ["Combat Superiority", "Battle Master"], ED: ["Disciple of the Elements"], AI: ["Infuse Item"],
    "FS:F": ["Fighting Style"], "FS:R": ["Fighting Style"], "FS:P": ["Fighting Style"], "FS:B": ["Fighting Style"], MM: ["Metamagic"], AS: ["Arcane Shot"], RN: ["Rune Carver"], PB: ["Pact Boon"] };

  // DDB's hide in sheet: hidden features leave the list until "Show hidden" is on (feature pane button)
  let showHidden = $state(false);
  const hiddenNames = $derived(current.character.hidden_features || []);
  const shown = $derived(s.features.filter((f) => f.name !== "Ability Score Improvement" && f.kind !== "background" && (showHidden || !hiddenNames.includes(f.name))));
  function parentOf(f) {
    if (!f.optionalfeature) return null;
    const types = content.byId.optionalfeatures[f.optionalfeature]?.featureType || [];
    for (const name of types.flatMap((t) => OPTION_PARENT[t] || [])) {
      const parent = shown.find((p) => !p.optionalfeature && p.kind === f.kind && p.name === name);
      if (parent) return parent;
    }
    return null;
  }
  const optionsOf = (parent) => shown.filter((f) => parentOf(f) === parent);
  // DDB opens each class block with "Hit Points" and "Proficiencies" (the PHB class table text); built from the class data.
  function classIntro(entry) {
    const cls = content.byId.classes[entry.id];
    if (!cls) return [];
    const faces = cls.hd?.faces || 8, name = cls.name.toLowerCase(), start = cls.startingProficiencies || {};
    const list = (xs) => (xs || []).map((x) => (typeof x === "string" ? x.replace(/\{@\w+ ([^|}]+)[^}]*\}/g, "$1") : x.proficiency || "")).filter(Boolean).join(", ") || "None";
    const pick = (start.skills || []).find((x) => x.choose)?.choose;
    return [
      { name: "Hit Points", book: cls.book, kind: "class", intro: true, origin: cls.name, entries: [
        `Hit Dice: 1d${faces} per ${name} level`, `Hit Points at 1st Level: ${faces} + your Constitution modifier`,
        `Hit Points at Higher Levels: 1d${faces} (or ${faces / 2 + 1}) + your Constitution modifier per ${name} level after 1st`] },
      { name: "Proficiencies", book: cls.book, kind: "class", intro: true, origin: cls.name, chosen: (entry.skills || []).map(title), entries: [
        `Armor: ${list(start.armor)}`, `Weapons: ${list(start.weapons)}`, `Tools: ${list(start.tools)}`,
        `Saving Throws: ${(cls.proficiency || []).map((a) => ABILITY_NAMES[a]).join(", ")}`,
        pick ? `Skills: Choose ${pick.count} from ${pick.from.map(title).join(", ")}` : ""].filter(Boolean) },
    ];
  }
  const classBlocks = $derived.by(() => {
    const out = new Map();
    for (const f of shown) if (f.kind === "class" && !parentOf(f)) (out.get(f.class) || out.set(f.class, []).get(f.class)).push(f);
    return (current.character.classes || []).map((entry) => {
      const name = content.byId.classes[entry.id]?.name;
      const list = (out.get(name) || []).map((f, k) => [f, k]).sort((a, b) => (a[0].level ?? 99) - (b[0].level ?? 99) || a[1] - b[1]).map(([f]) => f);
      return [name, [...classIntro(entry), ...list]];
    }).filter(([name]) => name);
  });
  const racial = $derived(shown.filter((f) => f.kind === "race"));
  const feats = $derived(shown.filter((f) => f.kind === "feat" && !parentOf(f)));
  const TABS = [["all", "All"], ["class", "Class Features"], ["race", "Racial Traits"], ["feat", "Feats"]];

  const firstText = (entries) => (entries || []).find((e) => typeof e === "string") || "";
  // A counter sits under the feature of its name; one with no such feature under the feature named after its origin.
  const counterOf = (f) => s.counters.find((c) => (FEATURE_FOR[c.name] || c.name) === f.name)
    || s.counters.find((c) => c.origin === f.name && !shown.some((g) => g.name === (FEATURE_FOR[c.name] || c.name)));
  const open = (f) => show("feature", f.name, f);
</script>

{#snippet snippet(f, kind)}
  {@const options = optionsOf(f)}
  {@const counter = counterOf(f)}
  <div class="styles_snippet__CzYh+ ct-feature-snippet--{kind}">
    <div class="styles_heading__yD0Cm" role="button" tabindex="0" onclick={() => open(f)} onkeydown={(e) => e.key === "Enter" && open(f)}>{f.name}{#if s.class_values?.[f.name]}<span class="ddb-feature-value" title="At your current level"> {s.class_values[f.name]}</span>{/if}<span><span class="styles_metaItem__wEnyV"><p class="styles_reference__4pmEk"><span class="styles_name__mZMFY" title={book(f.book)}>{String(f.book || "").toUpperCase()}</span>{#if f.page}<span>, pg. {f.page}</span>{/if}</p></span></span></div>
    <div class="styles_content__VHVQW">
      {#if !f.intro && firstText(f.entries)}<div class="ddbc-snippet ddbc-snippet--parsed"><div class="jsx-parser ddbc-snippet__content"><p><Tagged text={firstText(f.entries)} /></p></div></div>{/if}
    </div>
    {#if f.chosen?.length || options.length || counter}
      <div class="styles_extra__BgeMp">
        {#if counter}<LimitedUse {counter} />{/if}
        {#if f.chosen?.length || options.length}
          <div class="ct-feature-snippet__choices">
            {#each f.chosen || [] as name}<div class="ct-feature-snippet__choice">{name}</div>{/each}
            {#each options as o}<div class="ct-feature-snippet__choice" role="button" tabindex="0" onclick={() => show("optionalfeature", o.optionalfeature)} onkeydown={(e) => e.key === "Enter" && show("optionalfeature", o.optionalfeature)}>{o.name}</div>{/each}
          </div>
        {/if}
      </div>
    {/if}
  </div>
{/snippet}

<section class="ct-features">
  <h2 class="accessibility_screenreaderOnly__OEzRB">Features and Traits</h2>
  <div class="styles_tabFilter__50iSv">
    <div class="styles_buttons__hGhtB">
      {#each TABS as [key, label]}<button type="button" class={filter === key ? "styles_active__oWpHc" : ""} onclick={() => (filter = key)}>{label}</button>{/each}
      {#if hiddenNames.length}<button type="button" class={showHidden ? "styles_active__oWpHc" : ""} onclick={() => (showHidden = !showHidden)}>{showHidden ? "Hide hidden" : `Show hidden (${hiddenNames.length})`}</button>{/if}
    </div>
    <div class="styles_content__QjnYw">
      {#if filter === "all" || filter === "class"}
        <div class="ct-content-group">
          <div class="ct-content-group__header"><div class="ct-content-group__header-content">Class Features</div></div>
          <div class="ct-content-group__content"><div class="ct-classes-detail">
            {#each classBlocks as [className, list] (className)}
              <div class="ct-class-detail">
                <div class="ct-class-detail__name">{className} Features</div>
                <div class="ct-class-detail__features">{#each list as f}{@render snippet(f, "class")}{/each}</div>
              </div>
            {/each}
          </div></div>
        </div>
      {/if}
      {#if (filter === "all" || filter === "race") && racial.length}
        <div class="ct-content-group">
          <div class="ct-content-group__header"><div class="ct-content-group__header-content">Racial Traits</div></div>
          <div class="ct-content-group__content"><div>{#each racial as f}{@render snippet({ ...f, origin: raceName(f.origin) }, "racial-trait")}{/each}</div></div>
        </div>
      {/if}
      {#if filter === "all" || filter === "feat"}
        <div class="ct-content-group">
          <div class="ct-content-group__header"><div class="ct-content-group__header-content">Feats</div></div>
          <div class="ct-content-group__content">
            <div class="ct-features__management-link">
              <button class="ct-theme-button ct-theme-button--outline ct-theme-button--interactive ct-button character-button ddbc-button character-button-medium" type="button"
                onclick={() => show("feats")}><span class="ct-button__content">Manage Feats</span></button>
            </div>
            <div class="ct-feats-detail">
              {#if feats.length}{#each feats as f}{@render snippet(f, "feat")}{/each}
              {:else}<div class="ct-feats-detail__default"><p>You have no feats chosen. Feats come from Ability Score Improvements on the Class step, or from your race.</p></div>{/if}
            </div>
          </div>
        </div>
      {/if}
    </div>
  </div>
</section>
