<script>
  // The phone sheet in DDB's markup (ct-character-sheet-mobile, from the m-* captures): header with hit points
  // and inspiration, the combat strip, one section at a time under a bevelled divider (swipe or the section
  // grid to move), and DDB's bottom bar. The sections hold the same parts as the desktop tabs, as on DDB.
  import { current, changed } from "../lib/character.svelte.js";
  import { route } from "../lib/router.svelte.js";
  import { show } from "../lib/pane.svelte.js";
  import XpBar from "./XpBar.svelte";
  // the speed the header box shows (Speed pane, DDB's primary movement); walking unless the character has that speed
  const SPEED_HEADING = { walk: "Walking", fly: "Flying", swim: "Swimming", climb: "Climbing", burrow: "Burrowing" };
  const primaryMove = $derived(current.sheet?.speed?.[current.character.preferences?.primary_movement] ? current.character.preferences.primary_movement : "walk");
  import { ddb } from "../lib/ddb.svelte.js";
  import { ABILITIES, ABILITY_NAMES, raceName } from "../lib/format.js";
  import Frame from "./ddb/Frame.svelte";
  import Num from "./ddb/Num.svelte";
  import Actions from "./Actions.svelte";
  import Spells from "./Spells.svelte";
  import Inventory from "./Inventory.svelte";
  import Features from "./Features.svelte";
  import Background from "./Background.svelte";
  import Extras from "./Extras.svelte";
  import Notes from "./Notes.svelte";
  import SkillsList from "./SkillsList.svelte";
  import SavesSummary from "./SavesSummary.svelte";
  import ProficiencyGroups from "./ProficiencyGroups.svelte";

  const s = $derived(current.sheet);
  const play = $derived(current.character.play || {});
  const avatar = $derived(current.character.description?.avatar_url || null);
  const caster = $derived((s?.spellcasting?.casters || []).length > 0 || (s?.spellcasting?.granted || []).length > 0);
  // [route key, label, icon (the section grid's own), DDB container name]
  const SECTIONS = $derived([
    ["main", "Abilities, Saves, Senses", "attributes"], ["skills", "Skills", "skills"], ["actions", "Actions", "actions"],
    ["inventory", "Inventory", "equipment"], ...(caster ? [["spells", "Spells", "spells"]] : []), ["features", "Features & Traits", "featuretraits"],
    ["proficiencies", "Proficiencies & Training", "proficiencies"], ["background", "Background", "description"],
    ["notes", "Notes", "notes"], ["extras", "Extras", "extras"],
  ]);
  const section = $derived(SECTIONS.some(([k]) => k === route.step) ? route.step : "main");
  const index = $derived(SECTIONS.findIndex(([k]) => k === section));
  let navOpen = $state(false);

  const go = (key) => { navOpen = false; location.hash = `#/c/${route.id}/sheet/${key}`; window.scrollTo(0, 0); };
  const key = (fn) => (e) => (e.key === "Enter" || e.key === " ") && fn();
  function toggleInspiration() {
    current.character.play ??= {};
    current.character.play.inspiration = !current.character.play.inspiration;
    changed(100);
  }
  // Swipe sideways between sections, as on DDB's phone sheet.
  let touchX = null;
  const touchStart = (e) => { touchX = e.touches[0].clientX; };
  function touchEnd(e) {
    if (touchX === null) return;
    const dx = e.changedTouches[0].clientX - touchX;
    touchX = null;
    if (Math.abs(dx) < 70) return;
    const next = SECTIONS[index + (dx < 0 ? 1 : -1)];
    if (next) go(next[0]);
  }
  const passives = [["perception", "Perception"], ["investigation", "Investigation"], ["insight", "Insight"]];
</script>

{#snippet divider(label, manage = null)}
  <div class="ct-mobile-divider ct-mobile-divider--has-label">
    <div class="ct-mobile-divider__divider">
      <div class="ct-mobile-divider__edge ct-mobile-divider__edge--first">{@html ddb.icons["beveled-edge-corner"] || ""}</div>
      <div class="ct-mobile-divider__repeat">{@html ddb.icons["beveled-edge-repeat"] || ""}</div>
      <div class="ct-mobile-divider__edge ct-mobile-divider__edge--last">{@html ddb.icons["beveled-edge-corner"] || ""}</div>
    </div>
    <div class="ct-mobile-divider__label ">
      <span class="ct-mobile-divider__label-text">{label}{#if manage}<span class=" ddbc-manage-icon ddbc-manage-icon--interactive" role="button" tabindex="0" aria-label="Manage" onclick={manage} onkeydown={key(manage)}><span class="ddbc-manage-icon__icon "></span></span>{/if}</span>
    </div>
  </div>
{/snippet}

<div class="ct-character-sheet-mobile ">
  <div class="ct-character-sheet-mobile__header">
    <div class="ct-character-header-mobile">
      <div class="ct-character-header-mobile__group ct-character-header-mobile__group-tidbits">
        <div class="ct-character-header-info"><div class="ct-character-header-info__content">
          <div class=" ddbc-character-tidbits ddbc-character-tidbits--is-interactive">
            <div class="ddbc-character-tidbits__avatar"><div class="ddbc-character-avatar ">
              <div class="ddbc-character-avatar__portrait {avatar ? '' : ' ddbc-character-avatar__portrait--none'}" style={avatar ? `background-image:url("${avatar}")` : ""}></div>
            </div></div>
            <div class="ddbc-character-tidbits__body">
              <div class="ddbc-character-tidbits__heading">
                <h1 class="styles_characterName__2x8wQ">{s.name || "Unnamed"}</h1>
                <div class="ddbc-character-tidbits__menu-callout">
                  <button type="button" class="ct-theme-button ct-theme-button--outline ct-theme-button--interactive ct-button character-button ddbc-button character-button-small" onclick={() => show("manage", route.id)}><span class="ct-button__content">Manage</span></button>
                </div>
              </div>
              <div class="ddbc-character-tidbits__meta"><div class="ddbc-character-summary ">
                <span class="ddbc-character-summary__race">{raceName(s.race || "")}</span>
                <span class="ddbc-character-summary__classes">{s.classes.map((c) => `${c.name} ${c.level}`).join(" / ")}</span>
              </div></div>
              <div class="ddbc-character-tidbits__progression"><XpBar {s} /></div>
            </div>
          </div>
        </div></div>
      </div>
      <div class="ct-character-header-mobile__group ct-character-header-mobile__group--summary">
        <div class="ct-status-summary-mobile">
          <div class="ct-status-summary-mobile__health" role="button" tabindex="0" onclick={() => show("hp", route.id)} onkeydown={key(() => show("hp", route.id))}>
            <div class="ct-status-summary-mobile__health-label">Hit Points</div>
            <div class="ct-status-summary-mobile__data ct-status-summary-mobile__hp">
              <span class="ct-status-summary-mobile__hp-current">{s.hp.current}</span><span class="ct-status-summary-mobile__hp-sep">/</span><span class="ct-status-summary-mobile__hp-max">{s.hp.max}</span>
              {#if play.temp_hp}<span class="ct-status-summary-mobile__hp-temp"> +{play.temp_hp}</span>{/if}
            </div>
          </div>
          <div class="styles_mobileWrapper__HJy9T">
            <div class="styles_mobileButton__Y5iMu {play.inspiration ? 'styles_active__AdRTc' : ''} styles_interactive__0wY9H" role="checkbox" aria-checked={!!play.inspiration} tabindex="0" data-testid="inspiration"
              onclick={toggleInspiration} onkeydown={key(toggleInspiration)}>Inspiration</div>
          </div>
        </div>
      </div>
    </div>
    <div class="ct-combat-mobile ">
      <div class="ct-combat-mobile__extras">
        <div class="ct-combat-mobile__extra ct-combat-mobile__extra--proficiency">
          <div class="ct-combat-mobile__extra-heading"><div class="ct-combat-mobile__extra-label">Proficiency</div></div>
          <div class="ct-combat-mobile__extra-value"><Num value={s.proficiency_bonus} large /></div>
          <div class="ct-combat-mobile__extra-footer"><div class="ct-combat-mobile__extra-label">Bonus</div></div>
        </div>
        <div class="ct-combat-mobile__extra  ct-combat-mobile__extra--speed" role="button" tabindex="0" onclick={() => show("speed", route.id)} onkeydown={key(() => show("speed", route.id))}>
          <div class="ct-combat-mobile__extra-heading"><div class="ct-combat-mobile__extra-subheading">{SPEED_HEADING[primaryMove] || "Walking"}</div></div>
          <div class="ct-combat-mobile__extra-value"><Num value={s.speed[primaryMove] ?? s.speed.walk} large unit="ft." /></div>
          <div class="ct-combat-mobile__extra-footer"><div class="ct-combat-mobile__extra-label">Speed</div></div>
        </div>
        <section class="styles_boxMobile__5e4Sm">
          <div class="styles_valueMobile__XCC2z"><button type="button" class="F8U5pq_button integrated-dice__container"><Num value={s.initiative} large /></button></div>
          <div class="styles_labelMobile__kN2Is">Initiative</div>
        </section>
        <div class="ct-combat-mobile__extra  ct-combat-mobile__extra--ac" role="button" tabindex="0" onclick={() => show("ac", route.id)} onkeydown={key(() => show("ac", route.id))}>
          <div class="ct-combat-mobile__extra-heading"><div class="ct-combat-mobile__extra-label">Armor</div></div>
          <div class="ct-combat-mobile__extra-value" data-testid="armor-class-value">{s.armor_class.value}{s.armor_class.overridden ? "*" : ""}</div>
          <div class="ct-combat-mobile__extra-footer"><div class="ct-combat-mobile__extra-label">Class</div></div>
        </div>
        <div class="ct-combat-mobile__extra ct-combat-mobile__extra--statuses">
          <div class="ct-combat-mobile__ctas">
            <div class="ct-combat-mobile__cta" role="button" tabindex="0" onclick={() => show("defenses", route.id)} onkeydown={key(() => show("defenses", route.id))}><div class="ct-combat-mobile__cta-button">Defenses</div></div>
            <div class="ct-combat-mobile__cta" role="button" tabindex="0" onclick={() => show("conditions", route.id)} onkeydown={key(() => show("conditions", route.id))}><div class="ct-combat-mobile__cta-button">Conditions{(play.conditions || []).length ? ` (${play.conditions.length})` : ""}</div></div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <div class="swipeable" ontouchstart={touchStart} ontouchend={touchEnd}>
    <div class="ct-component-carousel">
      <div class="ct-component-carousel__active">
        {#if section === "main"}
          <div class=" ct-subsection-mobile ct-subsection-mobile--main">
            <div class="ct-main-mobile ">
              <section class="ct-main-mobile__abilities">
                <h2 class="accessibility_screenreaderOnly__OEzRB">Abilities</h2>
                {#each ABILITIES as a}
                  {@const ab = s.abilities[a]}
                  <div class="ct-main-mobile__ability">
                    <div class=" ddbc-ability-summary" role="button" tabindex="0" onclick={() => show("ability", a)} onkeydown={key(() => show("ability", a))}>
                      <Frame name="ability" />
                      <div class="ddbc-ability-summary__heading"><span class="ddbc-ability-summary__label ">{ABILITY_NAMES[a]}</span><span class="ddbc-ability-summary__abbr">{a}</span></div>
                      <div class="ddbc-ability-summary__primary "><button type="button" class="F8U5pq_button integrated-dice__container"><Num value={ab.modifier} large /></button></div>
                      <div class="ddbc-ability-summary__secondary ">{ab.score}</div>
                    </div>
                  </div>
                {/each}
              </section>
              {@render divider("Saving Throws")}
              <section class="ct-main-mobile__saving-throws "><SavesSummary /></section>
              {@render divider("Passive Senses", () => show("speed", route.id))}
              <h2 class="accessibility_screenreaderOnly__OEzRB">Passive Senses</h2>
              <div class="styles_senses__lmYdl" role="button" tabindex="0" onclick={() => show("senses", route.id)} onkeydown={key(() => show("senses", route.id))}>
                <div class="styles_minimalRow__sqDta">
                  {#each passives as [k, label]}
                    <div class="styles_minimalItem__42VR2">
                      <div class="styles_minimalCallout__783ES"><div class="ddbc-box-background ">{@html ddb.icons["sense-mini-box"] || ""}</div><div class="styles_calloutValue__NE8EI">{s.passives[k]}</div></div>
                      <div class="styles_calloutLabel__6JU6c styles_minimalCalloutLabel__H5vZF">{label}</div>
                    </div>
                  {/each}
                </div>
                <div class="styles_summary__5jXPt {Object.keys(s.senses).length ? '' : 'styles_summaryEmpty__Ucdcc'}">{Object.keys(s.senses).length ? Object.entries(s.senses).map(([k, v]) => `${k[0].toUpperCase()}${k.slice(1)} ${v} ft.`).join(", ") : "Additional Sense Types"}</div>
              </div>
            </div>
          </div>
        {:else if section === "skills"}
          <div class=" ct-subsection-mobile ct-subsection-mobile--skills">
            <section class="ct-skills-mobile ">{@render divider("Skills")}<h2 class="accessibility_screenreaderOnly__OEzRB">Skills</h2><SkillsList /></section>
          </div>
        {:else if section === "proficiencies"}
          <div class=" ct-subsection-mobile ct-subsection-mobile--proficiencies">
            <section class="ct-proficiencies-mobile">{@render divider("Proficiencies & Training")}<div role="button" tabindex="0" onclick={() => show("proficiencies", route.id)} onkeydown={key(() => show("proficiencies", route.id))}><ProficiencyGroups /></div></section>
          </div>
        {:else if section === "actions"}
          <div class=" ct-subsection-mobile"><section class="ct-actions-mobile">{@render divider("Actions")}<Actions /></section></div>
        {:else if section === "inventory"}
          <div class=" ct-subsection-mobile"><section class="ct-equipment-mobile">{@render divider("Inventory")}<Inventory /></section></div>
        {:else if section === "spells"}
          <div class=" ct-subsection-mobile"><section class="ct-spells-mobile">{@render divider("Spells")}<Spells /></section></div>
        {:else if section === "features"}
          <div class=" ct-subsection-mobile"><section class="ct-features-mobile">{@render divider("Features & Traits")}<Features /></section></div>
        {:else if section === "background"}
          <div class="ct-description-mobile ct-subsection-mobile"><section>{@render divider("Background")}<Background /></section></div>
        {:else if section === "notes"}
          <div class="ct-notes-mobile ct-subsection-mobile"><section>{@render divider("Notes")}<Notes /></section></div>
        {:else if section === "extras"}
          <div class=" ct-subsection-mobile"><section class="ct-extras-mobile">{@render divider("Extras")}<Extras /></section></div>
        {/if}
      </div>
    </div>
  </div>

  <div class="styles_mobileNav__0wxie">
    <div><button type="button" class="styles_navToggle__0Wm5t" aria-label="Show navigation" aria-expanded={navOpen} onclick={() => (navOpen = !navOpen)}>{@html ddb.icons["mobile-nav-toggle"] || "☰"}</button></div>
    <button type="button" class="styles_sidebarToggle__GQqor" aria-label="Character menu" onclick={() => show("manage", route.id)}>{@html ddb.icons["mobile-sidebar-toggle"] || "⋮"}</button>
  </div>
  {#if navOpen}
    <div class="ddb-mobile-nav-backdrop" role="presentation" onclick={() => (navOpen = false)}></div>
    <dialog class="Dialog_dialog__+k9ss styles_dialog__T7+jw styles_sectionNav__LQ33s" aria-modal="true" open>
      {#each SECTIONS as [k, label, icon]}
        <button type="button" class="Button_button__B9Kr5 ButtonVariants_primary__TMQ5y ButtonSizes_medium__uHe8x styles_solid__2ijrG styles_sectionButton__DLVhH styles_fullWidth__dRMhB {k === section ? 'ddb-section-current' : ''}" onclick={() => go(k)}>
          {@html ddb.icons[`section-${icon}`] || ""}{label}
        </button>
      {/each}
    </dialog>
  {/if}
</div>
