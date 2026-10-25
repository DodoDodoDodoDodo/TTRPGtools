<script>
  // The character sheet in DDB's own markup (class names from a saved DDB sheet), styled by DDB's
  // character-app stylesheet served from our private copy. Wording stays 2014.
  import { current, changed } from "../lib/character.svelte.js";
  import { route } from "../lib/router.svelte.js";
  import { show } from "../lib/pane.svelte.js";
  import { setHp } from "../lib/play.svelte.js";
  import XpBar from "./XpBar.svelte";
  // the speed the header box shows (Speed pane, DDB's primary movement); walking unless the character has that speed
  const SPEED_HEADING = { walk: "Walking", fly: "Flying", swim: "Swimming", climb: "Climbing", burrow: "Burrowing" };
  const primaryMove = $derived(current.sheet?.speed?.[current.character.preferences?.primary_movement] ? current.character.preferences.primary_movement : "walk");
  import { ddb, loadFrames, useSheetStyles } from "../lib/ddb.svelte.js";
  import { ABILITIES, ABILITY_NAMES, title, raceName, BACKDROPS } from "../lib/format.js";
  import Frame from "./ddb/Frame.svelte";
  import Num from "./ddb/Num.svelte";
  import Prof from "./ddb/Prof.svelte";
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
  import SheetMobile from "./SheetMobile.svelte";

  $effect.pre(() => {
    current.character.play ??= {};
  });
  const s = $derived(current.sheet);
  const play = $derived(current.character.play);
  const theme = $derived((current.character.description?.theme || "#c53131").replace("#", ""));
  const caster = $derived((s?.spellcasting?.casters || []).length > 0 || (s?.spellcasting?.granted || []).length > 0);
  const TABS = $derived([["actions", "Actions"], ...(caster ? [["spells", "Spells"]] : []), ["inventory", "Inventory"],
    ["features", "Features & Traits"], ["background", "Background"], ["notes", "Notes"], ["extras", "Extras"]]);
  const tab = $derived(TABS.some(([k]) => k === route.step) ? route.step : "actions");
  // DDB's own names for the tab containers its stylesheet sizes (Inventory is "equipment", Background "description").
  const DDB_TAB = { actions: "actions", spells: "spells", inventory: "equipment", features: "features", background: "description", notes: "notes", extras: "extras" };
  const tabIndex = $derived(Math.max(0, TABS.findIndex(([k]) => k === tab)));
  let amount = $state("");

  const backdrop = $derived.by(() => {
    const d = current.character.description || {};
    if (d.backdrop_url) return d.backdrop_url;
    const key = d.backdrop || current.character.classes?.[0]?.id;
    return BACKDROPS.includes(key) ? `${window.DND5E.ddb}/img/backdrops/${key}.jpg` : null;
  });
  const avatar = $derived(current.character.description?.avatar_url || null);

  // Our desktop sheet uses DDB's full-size frames and needs 1200 px of content (DDB's 1024-1199 px variant with
  // smaller boxes was not captured). Below a 1220 px window (1200 + scrollbar) the phone sheet (DDB's
  // ct-character-sheet-mobile) takes over whole, so no width shows desktop boxes squeezed into each other.
  const PHONE = "(max-width: 1219px)";
  // dodo-dodo premium (Dodo, 2026-10-22): the phone layout is a premium feature. Without it a phone gets the
  // desktop sheet zoomed out to fit (a 1240 px wide viewport; pinch to zoom) and a narrow desktop window scrolls
  // sideways; the top bar's premium line (App.svelte) links the pitch-in section. Never a lock: the sheet always works.
  const premium = window.DND5E.premium !== false;
  const narrowDevice = window.screen.width < 1220;
  $effect(() => {
    const meta = document.querySelector('meta[name="viewport"]');
    if (premium || !narrowDevice || !meta) return;
    const before = meta.getAttribute("content");
    meta.setAttribute("content", "width=1240");
    return () => meta.setAttribute("content", before);  // the builder and list keep the phone's own width
  });
  let mobile = $state(premium && window.matchMedia(PHONE).matches);
  $effect(() => {
    const query = window.matchMedia(PHONE);
    const update = (e) => (mobile = premium && e.matches);
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  });

  $effect(() => useSheetStyles());
  $effect(() => {
    loadFrames(theme);
  });
  // DDB puts the class backdrop on <body>, centred, starting under the dark header band, over the paper texture.
  $effect(() => {
    const texture = `url("${window.DND5E.ddb}/img/sheet-texture.png")`;
    document.body.classList.add("sheet-page", "site");  // DDB's button colours are scoped under body.site
    document.body.dataset.theme = "light";  // DDB's theme variables (pane backgrounds) hang off data-theme
    document.body.style.setProperty("--theme-color", `#${theme}`);
    // The dark header band is the first background layer, so it spans the full page width exactly.
    const band = "linear-gradient(rgba(17, 17, 17, 0.9), rgba(17, 17, 17, 0.9)) no-repeat 0 var(--topbar-height) / 100% var(--sheet-header-height)";
    document.body.classList.toggle("sheet-page--mobile", mobile);
    document.body.style.background = mobile ? `${texture} #f9f9f9`  // the phone sheet draws its own header
      : backdrop ? `${band}, url("${backdrop}") no-repeat center calc(var(--topbar-height) + var(--sheet-header-height)), ${texture} #f9f9f9`
      : `${band}, ${texture} #f9f9f9`;
    return () => {
      document.body.classList.remove("sheet-page", "site", "sheet-page--mobile");
      delete document.body.dataset.theme;
      document.body.style.removeProperty("--theme-color");
      document.body.style.background = "";
    };
  });

  function hp(delta) {
    const n = Number(amount);
    if (!n) return;
    const max = s.hp.max;
    let currentHp = play.hp_current ?? max;
    let temp = play.temp_hp || 0;
    if (delta < 0) {
      const fromTemp = Math.min(temp, n);
      temp -= fromTemp;
      currentHp = Math.max(0, currentHp - (n - fromTemp));
    } else currentHp = Math.min(max, currentHp + n);
    setHp(currentHp, temp);
    amount = "";
  }
  function toggleInspiration() {
    play.inspiration = !play.inspiration;
    changed(100);
  }
  const defenses = $derived([
    ...(s.defenses?.resist || []).map((d) => `Resistant to ${d}`),
    ...(s.defenses?.immune || []).map((d) => `Immune to ${d}`),
    ...(s.defenses?.condition_immune || []).map((d) => `Cannot be ${d}`),
    ...(s.defenses?.vulnerable || []).map((d) => `Vulnerable to ${d}`),
  ]);
  const conditions = $derived([...(play.conditions || []), ...((play.exhaustion || 0) ? [`exhaustion ${play.exhaustion}`] : [])]);
  const goTab = (key) => (location.hash = `#/c/${route.id}/sheet/${key}`);
  const key = (fn) => (e) => (e.key === "Enter" || e.key === " ") && fn();
</script>

{#if s}
<div class="ct-character-sheet ct-character-sheet--dice-enabled {premium ? '' : 'ddb-sheet-fixed-width'}" style="--theme:#{theme}; --theme-color:#{theme};">
  <div class="ct-character-sheet__inner">
    {#if mobile}<SheetMobile />{:else}
    <div class="ct-character-sheet-desktop">
      <div class="ct-character-header-desktop">
        <div class="ct-character-header-desktop__group ct-character-header-desktop__group-tidbits">
          <div class="ct-character-header-info"><div class="ct-character-header-info__content">
            <div class="ddbc-character-tidbits ddbc-character-tidbits--is-interactive">
              <div class="ddbc-character-tidbits__avatar"><div class="ddbc-character-avatar">
                <div class="ddbc-character-avatar__portrait {avatar ? '' : 'ddbc-character-avatar__portrait--none'}" style={avatar ? `background-image:url("${avatar}")` : ""}></div>
              </div></div>
              <div class="ddbc-character-tidbits__body">
                <div class="ddbc-character-tidbits__heading">
                  <h1 class="styles_characterName__2x8wQ">{s.name || "Unnamed"}</h1>
                  <div class="ddbc-character-tidbits__menu-callout">
                    <button type="button" class="ct-theme-button ct-theme-button--outline ct-theme-button--interactive ct-button character-button ddbc-button character-button-small" onclick={() => show("manage", route.id)}>
                      <span class="ct-button__content">Manage</span>
                    </button>
                  </div>
                </div>
                <div class="ddbc-character-tidbits__meta"><div class="ddbc-character-summary">
                  <span class="ddbc-character-summary__race">{raceName(s.race || "")}</span>
                  <span class="ddbc-character-summary__classes">{s.classes.map((c) => `${c.name} ${c.level}`).join(" / ")}</span>
                </div></div>
                <div class="ddbc-character-tidbits__progression"><XpBar {s} /></div>
              </div>
            </div>
          </div></div>
        </div>
        <div class="ct-character-header-desktop__group ct-character-header-desktop__group--gap"></div>
        <div class="ct-character-header-desktop__group ct-character-header-desktop__group--short-rest">
          <div class="ct-character-header-desktop__button" role="button" tabindex="0" onclick={() => show("rest", "short")} onkeydown={key(() => show("rest", "short"))}>
            <div class="ct-character-header-desktop__button-icon">{@html ddb.icons["short-rest"] || ""}</div>
            <span class="ct-character-header-desktop__button-label">Short Rest</span>
          </div>
        </div>
        <div class="ct-character-header-desktop__group ct-character-header-desktop__group--long-rest">
          <div class="ct-character-header-desktop__button" role="button" tabindex="0" onclick={() => show("rest", "long")} onkeydown={key(() => show("rest", "long"))}>
            <div class="ct-character-header-desktop__button-icon">{@html ddb.icons["long-rest"] || ""}</div>
            <span class="ct-character-header-desktop__button-label">Long Rest</span>
          </div>
        </div>
        <div class="ct-character-header-desktop__group ct-character-header-desktop__group--builder">
          <span class="ddbc-tooltip ct-character-header-desktop__builder">
            <a class="ct-character-header-desktop__builder-link" aria-label="Go to builder" href={`#/c/${route.id}/builder`}>{@html ddb.icons.builder || ""}</a>
          </span>
        </div>
      </div>

      <div class="ct-quick-info">
        <section class="ct-quick-info__abilities">
          {#each ABILITIES as a}
            {@const ab = s.abilities[a]}
            <div class="ct-quick-info__ability">
              <div class=" ddbc-ability-summary" role="button" tabindex="0" onclick={() => show("ability", a)} onkeydown={key(() => show("ability", a))}>
                <Frame name="ability" />
                <div class="ddbc-ability-summary__heading">
                  <span class="ddbc-ability-summary__label">{ABILITY_NAMES[a]}</span>
                  <span class="ddbc-ability-summary__abbr">{a}</span>
                </div>
                <div class="ddbc-ability-summary__primary"><button type="button" class="F8U5pq_button integrated-dice__container"><Num value={ab.modifier} large /></button></div>
                <div class="ddbc-ability-summary__secondary">{ab.score}</div>
              </div>
            </div>
          {/each}
        </section>
        <div class="ct-quick-info__box ct-quick-info__box--proficiency">
          <section class="ct-proficiency-bonus-box">
            <Frame name="proficiency" />
            <div class="ct-proficiency-bonus-box__heading">Proficiency</div>
            <div class="ct-proficiency-bonus-box__value"><Num value={s.proficiency_bonus} large /></div>
            <div class="ct-proficiency-bonus-box__label">Bonus</div>
          </section>
        </div>
        <div class="ct-quick-info__box ct-quick-info__box--speed">
          <section class="ct-speed-box" role="button" tabindex="0" onclick={() => show("speed", route.id)} onkeydown={key(() => show("speed", route.id))}>
            <Frame name="speed" />
            <div class="ct-speed-box__heading">{SPEED_HEADING[primaryMove] || "Walking"}</div>
            <div class="ct-speed-box__box-value"><Num value={s.speed[primaryMove] ?? s.speed.walk} large unit="ft." /></div>
            <div class="ct-speed-box__label">Speed</div>
          </section>
        </div>
        <section class="ct-quick-info__inspiration">
          <div>
            <div class="styles_box__6xvSR styles_interactive__0wY9H" role="checkbox" aria-checked={!!play.inspiration} tabindex="0"
              onclick={toggleInspiration} onkeydown={key(toggleInspiration)}>
              <Frame name="inspiration" />
              <div class="styles_status__wfjbc">{#if play.inspiration}<svg class="ddb-inspiration-mark" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2l2.9 6.9 7.1.6-5.4 4.7 1.7 7-6.3-3.8-6.3 3.8 1.7-7L2 9.5l7.1-.6z" /></svg>{/if}</div>
            </div>
          </div>
          <div class="styles_label__Bj6YW ddb-pane-link" role="button" tabindex="0" onclick={() => show("inspiration", route.id)} onkeydown={key(() => show("inspiration", route.id))}>Inspiration</div>
        </section>
        <section class="ct-quick-info__health">
          <div class="styles_hitPointsBox__iqcr7">
            <Frame name="hit-points" />
            <div class="styles_content__nPt0e">
              <h1 class="styles_label__Ivf2i">Hit Points</h1>
              <div class="styles_container__1cATf">
                <button type="button" class="Button_button__B9Kr5 ButtonVariants_primary__TMQ5y ButtonVariants_outline__v36Mn ButtonSizes_medium__uHe8x styles_xx-small__Q1OkG styles_themed__AiJUu styles_outline__lyFTR styles_button__ZEn+Q styles_heal__4AW3J" onclick={() => hp(1)}>Heal</button>
                <input class="styles_input__coHiS" aria-label="Hit Points Adjustment" type="number" min="0" bind:value={amount} />
                <button type="button" class="Button_button__B9Kr5 ButtonVariants_primary__TMQ5y ButtonVariants_outline__v36Mn ButtonSizes_medium__uHe8x styles_xx-small__Q1OkG styles_themed__AiJUu styles_outline__lyFTR styles_button__ZEn+Q styles_damage__cxeXD" onclick={() => hp(-1)}>Damage</button>
              </div>
              <div class="styles_container__nsTN6">
                <div class="styles_innerContainer__Xn2+o">
                  <div class="styles_item__UVpsr">
                    <span class="styles_label__ysVMP">Current</span>
                    <button type="button" class="styles_valueButton__0rK5Z styles_number__j1d93" onclick={() => show("hp", route.id)}>{s.hp.current}</button>
                  </div>
                  <div class="styles_item__UVpsr"><div class="styles_spacer__fglT0"></div><span class="styles_number__j1d93 styles_slash__UmBPf">/</span></div>
                  <div class="styles_item__UVpsr">
                    <span class="styles_label__ysVMP">Max</span>
                    <div class="styles_number__j1d93 styles_maxContainer__mt+Ff"><span>{s.hp.max}{s.hp.overridden ? "*" : ""}</span></div>
                  </div>
                </div>
                <div class="styles_item__UVpsr styles_temp__pxAha">
                  <span class="styles_label__ysVMP">Temp</span>
                  <button type="button" class="styles_valueButton__0rK5Z {play.temp_hp ? '' : 'styles_tempEmpty__fI4gV'} styles_number__j1d93" onclick={() => show("hp", route.id)}>{play.temp_hp || "--"}</button>
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>

      <div class="ct-subsections">
        <div class="ct-subsection ct-subsection--saving-throws">
          <section class="ct-saving-throws-box">
            <Frame name="saving-throws" />
            <div class="ct-saving-throws-box__abilities"><SavesSummary /></div>
            <div class="ct-saving-throws-box__info">
              {#if s.save_notes?.length}
                <div class="ct-saving-throws-box__modifiers ct-saving-throws-box__modifiers--multi">
                  {#each s.save_notes as n}<span class="ddbc-tooltip ct-saving-throws-box__modifier" title="{n.source}: advantage on {n.text}"><div class="ct-dice-adjustment-summary"><span class="ct-dice-adjustment-summary__icon ddbc-advantage-icon"><span aria-label="Advantage">{@html ddb.icons["advantage"] || "ADV"}</span></span><span class="ct-dice-adjustment-summary__restriction">on {n.text}</span></div></span>{/each}
                </div>
              {:else}<div class="ct-saving-throws-box__modifiers ct-saving-throws-box__modifiers--empty">Saving Throw Modifiers</div>{/if}
            </div>
          </section>
          <div class="ct-subsection__footer"><span class="ddbc-manage-icon ddbc-manage-icon--edge-icon"><span class="ddbc-manage-icon__content">Saving Throws</span><span class="ddbc-manage-icon__icon"></span></span></div>
        </div>

        <div class="ct-senses-desktop ct-subsection ct-subsection--senses">
          <section class="ct-senses-box" role="button" tabindex="0" onclick={() => show("senses", route.id)} onkeydown={key(() => show("senses", route.id))}>
            <Frame name="senses" />
            <div class="styles_senses__lmYdl">
              <div>
                {#each [["perception", "Passive Perception"], ["investigation", "Passive Investigation"], ["insight", "Passive Insight"]] as [k, label]}
                  <div class="styles_callout__l5aTv">
                    <Frame name="sense-row" />
                    <div class="styles_calloutValue__NE8EI">{s.passives[k]}</div>
                    <div class="styles_calloutLabel__6JU6c styles_regularCalloutLabel__cTMsy">{label}</div>
                  </div>
                {/each}
              </div>
              <div class="styles_summary__5jXPt {Object.keys(s.senses).length ? '' : 'styles_summaryEmpty__Ucdcc'}">{Object.keys(s.senses).length ? Object.entries(s.senses).map(([k, v]) => `${k[0].toUpperCase()}${k.slice(1)} ${v} ft.`).join(", ") : "Additional Sense Types"}</div>
            </div>
          </section>
          <div class="ct-subsection__footer"><span class="ddbc-manage-icon ddbc-manage-icon--edge-icon"><span class="ddbc-manage-icon__content">Senses</span><span class="ddbc-manage-icon__icon"></span></span></div>
        </div>

        <div class="ct-subsection ct-subsection--proficiency-groups">
          <section class="ct-proficiency-groups-box" role="button" tabindex="0" onclick={() => show("proficiencies", route.id)} onkeydown={key(() => show("proficiencies", route.id))}>
            <Frame name="proficiency-groups" />
            <ProficiencyGroups />
          </section>
          <div class="ct-subsection__footer"><span class="ddbc-manage-icon ddbc-manage-icon--edge-icon"><span class="ddbc-manage-icon__content">Proficiencies &amp; Training</span><span class="ddbc-manage-icon__icon"></span></span></div>
        </div>

        <div class="ct-subsection ct-subsection--skills">
          <section class="ct-skills-box">
            <Frame name="skills" />
            <SkillsList />
          </section>
          <div class="ct-subsection__footer" role="button" tabindex="0" onclick={() => show("skills", route.id)} onkeydown={key(() => show("skills", route.id))}><span class="ddbc-manage-icon ddbc-manage-icon--edge-icon"><span class="ddbc-manage-icon__content">Skills</span><span class="ddbc-manage-icon__icon"></span></span></div>
        </div>

        <div class="ct-subsection ct-subsection--combat">
          <div class="ct-combat"><div class="ct-combat__summary">
            <div class="ct-combat__summary-group ct-combat__summary-group--initiative">
              <section class="styles_box__PLQui">
                <div class="styles_label__6xv1b">Initiative</div>
                <div class="styles_value__hqDak">
                  <Frame name="initiative" />
                  <button type="button" class="F8U5pq_button integrated-dice__container"><Num value={s.initiative} large /></button>
                </div>
              </section>
            </div>
            <div class="ct-combat__summary-group ct-combat__summary-group--ac">
              <section class=" ddbc-armor-class-box" role="button" tabindex="0" onclick={() => show("ac", route.id)} onkeydown={key(() => show("ac", route.id))}>
                <Frame name="armor-class" />
                <div class="ddbc-armor-class-box__label">Armor</div>
                <div class="ddbc-armor-class-box__value">{s.armor_class.value}{s.armor_class.overridden ? "*" : ""}</div>
                <div class="ddbc-armor-class-box__label">Class</div>
              </section>
            </div>
            <section class="ct-combat__summary-group ct-combat__summary-group--statuses">
              <div class="ct-combat__statuses">
                <Frame name="statuses" />
                <div class="ct-combat__statuses-group ct-combat__statuses-group--defenses" role="button" tabindex="0" onclick={() => show("defenses", route.id)} onkeydown={key(() => show("defenses", route.id))}>
                  <div class="ct-combat__summary-label">Defenses</div>
                  <div class="ct-defenses-summary">
                    {#if defenses.length}{#each defenses as d}<div class="ct-defenses-summary__group">{d}</div>{/each}
                    {:else}<div class="ct-defenses-summary__default">Resistances, Immunities, or Vulnerabilities</div>{/if}
                  </div>
                </div>
                <div class="ct-combat__statuses-group ct-combat__statuses-group--conditions" role="button" tabindex="0" onclick={() => show("conditions", route.id)} onkeydown={key(() => show("conditions", route.id))}>
                  <div class="ct-combat__summary-label">Conditions</div>
                  <div class="ct-conditions-summary">
                    {#if conditions.length}{#each conditions as c}<div class="ct-conditions-summary__condition">{title(c)}</div>{/each}
                    {:else}<div class="ct-conditions-summary__default">Add Active Conditions</div>{/if}
                  </div>
                </div>
              </div>
            </section>
          </div></div>
        </div>

        <div class="ct-subsection ct-subsection--primary-box">
          <div class="ct-primary-box styles_primaryBox__2cqbd">
            <Frame name="primary-box" />
            <div class="styles_tabList__fix2X styles_themed__Plffn styles_tabList__Q4CqK" style="--tab-count: {TABS.length}; --tab-active-position: {tabIndex};">
              <menu class="styles_tabs__aTttL">
                {#each TABS as [k, label]}
                  <li><button type="button" class="styles_tabButton__wvSLf" role="radio" aria-checked={tab === k} onclick={() => goTab(k)}>{label}</button></li>
                {/each}
              </menu>
              <div class="ct-primary-box__tab--{DDB_TAB[tab]} ddb-tab-body">
                {#if tab === "actions"}<Actions />
                {:else if tab === "inventory"}<Inventory />
                {:else if tab === "spells"}<Spells />
                {:else if tab === "features"}<Features />
                {:else if tab === "background"}<Background />
                {:else if tab === "notes"}<Notes />
                {:else}<Extras />
                {/if}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    {/if}
  </div>
</div>
{/if}
