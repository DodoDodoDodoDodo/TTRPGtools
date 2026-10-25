<script>
  // Actions tab in DDB's markup: filter buttons, attack table, basic actions per activation, feature
  // snippets with limited-use boxes. Basic actions use the 2014 PHB list, not DDB's 2024 wording.
  import Tagged from "../lib/Tagged.svelte";
  import { current } from "../lib/character.svelte.js";
  import { show } from "../lib/pane.svelte.js";
  import { ddb } from "../lib/ddb.svelte.js";
  import { DAMAGE } from "../lib/format.js";
  import Num from "./ddb/Num.svelte";
  import LimitedUse, { FEATURE_FOR } from "./ddb/LimitedUse.svelte";
  import { cantripDice } from "../lib/spells.js";

  const s = $derived(current.sheet);
  let filter = $state("all");

  const FILTERS = [["all", "All"], ["attack", "Attack"], ["action", "Action"], ["bonus", "Bonus Action"], ["reaction", "Reaction"], ["other", "Other"], ["limited", "Limited Use"]];
  const BASIC = {
    action: ["Attack", "Cast a Spell", "Dash", "Disengage", "Dodge", "Grapple", "Help", "Hide", "Ready", "Search", "Shove", "Use an Object"],
    bonus: ["Two-Weapon Fighting"],
    reaction: ["Opportunity Attack"],
    other: ["Interact with an Object"],
  };
  const HEADINGS = { action: "Actions", bonus: "Bonus Actions", reaction: "Reactions", other: "Other", limited: "Limited Use" };
  const PROPS = { "2H": "Two-Handed", F: "Finesse", H: "Heavy", L: "Light", LD: "Loading", R: "Reach", T: "Thrown", V: "Versatile", A: "Ammunition", RLD: "Reload", S: "Special" };

  function snippet(counter) {
    const name = FEATURE_FOR[counter.name] || counter.name;
    const feature = s.features.find((f) => f.name === name) || s.features.find((f) => f.name.startsWith(name));
    const first = (feature?.entries || []).find((e) => typeof e === "string");
    return { feature, text: first || "" };
  }
  const spellAttacks = $derived((s.spellcasting.casters || []).flatMap((c) =>
    c.list.filter((sp) => sp.level === 0 && (sp.attack || sp.save)).map((sp) => ({ ...sp, caster: c }))));
  const countersBy = (kind) => s.counters.filter((c) => (kind === "limited" ? true : (c.activation === "special" ? "other" : c.activation) === kind));
  const sections = $derived(
    filter === "all" ? ["action", "bonus", "reaction", "other"]
      : filter === "attack" ? ["action"]
      : [filter],
  );
  function rangeParts(a) {
    if (!a.range) return { close: a.properties.includes("R") ? 10 : 5, long: null, label: "Reach" };
    const [close, long] = String(a.range).split("/");
    return { close, long, label: "" };
  }
  const icon = (key) => ddb.icons[key] || "";
</script>

<section class="ct-actions">
  <div class="styles_tabFilter__50iSv">
    <div class="styles_buttons__hGhtB">
      {#each FILTERS as [key, label]}
        <button type="button" class={filter === key ? "styles_active__oWpHc" : ""} onclick={() => (filter = key)}>{label}</button>
      {/each}
    </div>
    <div class="styles_content__QjnYw">
      {#each sections as kind}
        <div class="styles_actionsList__tw2cW">
          <div class="styles_heading__jqSRm">
            {#if kind === "action"}
              <div class="ct-actions__attacks-heading">Actions • <span class="ct-actions__attacks-per-action">Attacks per Action: {s.attacks_per_action}</span></div>
            {:else}{HEADINGS[kind]}{/if}
          </div>
          <div>
            {#if kind === "action" && filter !== "limited"}
              <div class="styles_attackTable__E+HtW">
                <div class="styles_tableHeader__Ow6Oy">
                  <div class="styles_col__3hY1K styles_icon__1IA7a"></div>
                  <div class="styles_col__3hY1K styles_name__MDLaF">Attack</div>
                  <div class="styles_col__3hY1K styles_range__Wxk2r">Range</div>
                  <div class="styles_col__3hY1K styles_tohit__zsX78">Hit / DC</div>
                  <div class="styles_col__3hY1K styles_damage__2d1fl">Damage</div>
                  <div class="styles_col__3hY1K styles_notes__mSXl3">Notes</div>
                </div>
                <div>
                  {#each s.attacks.filter((a) => a.item_id || a.name !== "Unarmed Strike" || current.character.preferences?.show_unarmed !== false) as a}
                    {@const r = rangeParts(a)}
                    {@const ranged = !!a.range && !a.properties.includes("T")}
                    <div class="ddbc-combat-attack--item {ranged ? 'ddbc-combat-item-attack--ranged' : 'ddbc-combat-item-attack--melee'} styles_attack__6-4vH ddbc-combat-attack"
                      role="button" tabindex="0" onclick={() => a.item_id && show("item", a.item_id)} onkeydown={(e) => e.key === "Enter" && a.item_id && show("item", a.item_id)}>
                      <div class="ddbc-combat-attack__icon">{@html icon(a.item_id ? (ranged ? "combat-attack__icon-img--weapon-ranged" : "combat-attack__icon-img--weapon-melee") : "attack-type-icon--3-1")}</div>
                      <div class="ddbc-combat-attack__name">
                        <div class="ddbc-combat-attack__label"><span class="styles_itemName__xLCwW styles_common__4urYa">{a.name}</span></div>
                        <div class="ddbc-combat-attack__meta"><span class="ddbc-combat-attack__meta-item">{a.item_id ? (ranged ? "Ranged Weapon" : "Melee Weapon") : "Melee Attack"}</span>{#if a.offhand}<span class="ddbc-combat-attack__meta-item">Bonus Action</span>{/if}</div>
                      </div>
                      <div class="ddbc-combat-attack__range">
                        <div class="ddbc-combat-attack__range-value">
                          {#if r.long}<span class="ddbc-combat-attack__range-value-close">{r.close}</span><span class="ddbc-combat-attack__range-value-long">({r.long})</span>
                          {:else}<Num value={r.close} unit="ft." />{/if}
                        </div>
                        <div class="ddbc-combat-attack__range-label">{r.label}</div>
                      </div>
                      <div class="ddbc-combat-attack__action"><div class="ddbc-combat-attack__tohit">
                        <button type="button" class="F8U5pq_button integrated-dice__container"><Num value={a.to_hit} /></button>
                      </div></div>
                      <div class="ddbc-combat-attack__damage">
                        <div class="ddbc-combat-item-attack__damage {a.versatile ? 'ddb-combat-item-attack__damage--is-versatile' : ''}">
                          <button type="button" class="F8U5pq_button integrated-dice__container"><span class="ddbc-tooltip ddbc-damage">
                            <span class="ddbc-damage__value">{a.damage}</span>
                            {#if a.damage_type}<span class="ddbc-damage__icon"><span class="ddbc-damage-type-icon ddbc-damage-type-icon--{DAMAGE[a.damage_type]}" aria-label="{DAMAGE[a.damage_type]} damage">{@html icon(`damage-type-icon__img--${DAMAGE[a.damage_type]}`)}</span></span>{/if}
                          </span></button>
                          {#if a.versatile}<button type="button" class="F8U5pq_button integrated-dice__container"><span class="ddbc-tooltip ddbc-damage ddbc-damage--versatile"><span class="ddbc-damage__value">{a.versatile}</span></span></button>{/if}
                        </div>
                      </div>
                      <div class="ddbc-combat-attack__notes"><div class="ddbc-combat-item-attack__notes"><div class="ddbc-note-components">
                        {#each [a.proficient ? null : "Not proficient", ...a.properties.map((p) => PROPS[p] || p), a.rage ? `Rage +${a.rage}` : null].filter(Boolean) as note, i}{#if i}{", "}{/if}<span class="ddbc-note-components__component ddbc-note-components__component--plain">{note}</span>{/each}
                      </div></div></div>
                    </div>
                  {/each}
                  {#each spellAttacks as sp}
                    <div class="ddbc-combat-attack--spell styles_attack__6-4vH ddbc-combat-attack" role="button" tabindex="0" onclick={() => show("spell", sp.id)} onkeydown={(e) => e.key === "Enter" && show("spell", sp.id)}>
                      <div class="ddbc-combat-attack__icon">{@html icon("combat-attack__icon-img--action-attack-weapon-melee")}</div>
                      <div class="ddbc-combat-attack__name">
                        <div class="ddbc-combat-attack__label"><span class="styles_itemName__xLCwW styles_common__4urYa">{sp.name}</span></div>
                        <div class="ddbc-combat-attack__meta"><span class="ddbc-combat-attack__meta-item">Cantrip · {sp.caster.class}</span></div>
                      </div>
                      <div class="ddbc-combat-attack__range"><div class="ddbc-combat-attack__range-value">{#if sp.range?.distance?.amount}<Num value={sp.range.distance.amount} unit="ft." />{:else}{sp.range?.distance?.type || ""}{/if}</div></div>
                      <div class="ddbc-combat-attack__action"><div class="ddbc-combat-attack__tohit">
                        {#if sp.attack}<button type="button" class="F8U5pq_button integrated-dice__container"><Num value={sp.caster.attack} /></button>
                        {:else}<div class="ddbc-combat-attack__save-value">{sp.save.slice(0, 3).toUpperCase()} {sp.caster.save_dc}</div>{/if}
                      </div></div>
                      <div class="ddbc-combat-attack__damage">{#if cantripDice(sp, s.level)}<button type="button" class="F8U5pq_button integrated-dice__container"><span class="ddbc-tooltip ddbc-damage"><span class="ddbc-damage__value">{cantripDice(sp, s.level)}</span>
                        {#if sp.damage_types?.[0]}<span class="ddbc-damage__icon"><span class="ddbc-damage-type-icon ddbc-damage-type-icon--{sp.damage_types[0]}">{@html icon(`damage-type-icon__img--${sp.damage_types[0]}`)}</span></span>{/if}</span></button>{:else}--{/if}</div>
                      <div class="ddbc-combat-attack__notes"><div class="ddbc-note-components">{(sp.damage_types || []).join(", ")}</div></div>
                    </div>
                  {/each}
                </div>
              </div>
            {/if}
            {#if filter !== "attack" && filter !== "limited" && BASIC[kind]}
              <div class="styles_section__sO+fQ">
                <div class="styles_sectionHeading__f715p">Actions in Combat</div>
                <div class="styles_list__8r0ai"><div class="ct-basic-actions">
                  {#each BASIC[kind] as action, i}<span class="ct-basic-actions__action" role="button" tabindex="0" onclick={() => show("action", action)} onkeydown={(e) => e.key === "Enter" && show("action", action)}>{action}{#if i < BASIC[kind].length - 1}<span class="ct-basic-actions__action-sep">{", "}</span>{/if}</span>{/each}
                </div></div>
              </div>
            {/if}
            {#if filter !== "attack"}
              {#each countersBy(kind) as counter}
                {@const sn = snippet(counter)}
                <div class="styles_activatable__ismyq">
                  <div class="ct-feature-snippet">
                    <div class="ct-feature-snippet__heading" role="button" tabindex="0"
                      onclick={() => sn.feature && show("feature", counter.name, sn.feature)} onkeydown={(e) => e.key === "Enter" && sn.feature && show("feature", counter.name, sn.feature)}>
                      {counter.name}{#if counter.activation === "special"} <span class="ct-feature-snippet__heading-activation">(Special)</span>{/if}
                    </div>
                    {#if sn.text}<div class="ct-feature-snippet__content"><div class="ddbc-snippet ddbc-snippet--parsed"><div class="jsx-parser ddbc-snippet__content"><p><Tagged text={sn.text} /></p></div></div></div>{/if}
                    <LimitedUse {counter} />
                  </div>
                </div>
              {/each}
            {/if}
          </div>
        </div>
      {/each}
    </div>
  </div>
</section>
