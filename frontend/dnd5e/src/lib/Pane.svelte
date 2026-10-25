<script>
  // DDB's right-hand detail pane. `extra.slot` (inventory index) adds equip/attune/remove controls.
  import Entries from "./Entries.svelte";
  import Tagged from "./Tagged.svelte";
  import { pane, back, close, show } from "./pane.svelte.js";
  import { content, sourceAllowed, itemByRef } from "./content.svelte.js";
  import { current, changed, reloadCharacter } from "./character.svelte.js";
  import { book, castingTime, range, components, duration, ordinal, SCHOOLS, DAMAGE, itemType, plain, title, signed, ABILITY_NAMES, raceName, TOOLS, BACKDROPS } from "./format.js";
  import { toggleCondition, setExhaustion, toggleEffect, deathSave, setHp, takeRest, castAt, castableLevels } from "./play.svelte.js";
  import { damageOf } from "./spells.js";
  import AbilityCalc from "../sheet/ddb/AbilityCalc.svelte";
  import Campaigns from "../builder/Campaigns.svelte";
  import DdbSelect from "../builder/DdbSelect.svelte";
  import ProficiencyGroups from "../sheet/ProficiencyGroups.svelte";
  import { route } from "./router.svelte.js";
  import { api } from "./api.js";
  import FeatChoices from "../builder/FeatChoices.svelte";
  import AskBox from "./AskBox.svelte";
  import NoncanonToggle from "./NoncanonToggle.svelte";
  import { canonFilter } from "./noncanon.svelte.js";
  import { ddb } from "./ddb.svelte.js";
  import { equippable, typeCode, itemIcon, packSlots } from "./items.js";

  let side = $state("right");
  let bigImage = $state(false);
  let heal = $state("");
  let openCondition = $state(null);
  let profType = $state("");
  let addOpen = $state(false);
  let decorOpen = $state("backdrops");
  let customOpen = $state(false);
  let customItem = $state({ name: "", weight: 0, qty: 1 });
  let xpAmount = $state("");
  let featQuery = $state("");
  // Manage Feats: feats outside an ASI (DM boons, a table's extra feat), stored as bonus_feats like a DDB import
  function addBonusFeat(id) {
    current.character.bonus_feats = [...(current.character.bonus_feats || []), { id }];
    featQuery = "";
    changed(100);
  }
  function removeBonusFeat(k) {
    current.character.bonus_feats.splice(k, 1);
    changed(100);
  }
  function changeXp(sign) {
    const amount = Math.abs(Number(xpAmount) || 0);
    current.character.xp = Math.max(0, (Number(current.character.xp) || 0) + sign * amount);
    xpAmount = "";
    changed(100);
  }
  function addToInventory(slot, insideUid) {
    if (!current.character.inventory) current.character.inventory = [];
    const inv = current.character.inventory;
    const pack = slot.id && content.byId.items[slot.id];
    if (pack?.packContents) { inv.push(...packSlots(pack, itemByRef, insideUid)); changed(); return; }
    inv.push({ ...slot, uid: Math.random().toString(36).slice(2, 10), ...(insideUid ? { inside: insideUid } : {}) });
    changed();
  }
  let itemQuery = $state("");
  // books the Home step allows; names that start a word with the query come first
  function itemMatches(q) {
    const needle = q.trim().toLowerCase();
    if (needle.length < 2) return [];
    const rank = (name) => (name.startsWith(needle) ? 0 : name.split(/[\s(,-]+/).some((w) => w.startsWith(needle)) ? 1 : 2);
    return content.items.filter((i) => i.name.toLowerCase().includes(needle) && sourceAllowed(i.book, current.character?.preferences) && canonFilter(i))
      .sort((a, b) => rank(a.name.toLowerCase()) - rank(b.name.toLowerCase()) || a.name.localeCompare(b.name)).slice(0, 25);
  }
  const ABILITIES_LIST = ["str", "dex", "con", "int", "wis", "cha"];
  function editSkill(i, key, value) {
    const list = [...(current.character.custom_skills || [])];
    list[i] = { ...list[i], [key]: value };
    current.character.custom_skills = list;
    changed(500);
  }
  let profPick = $state("");
  const PROF_TYPES = { armor: "Armor", weapons: "Weapon", tools: "Tool", languages: "Language" };
  function profOptions(type) {
    const have = new Set(current.sheet?.proficiencies?.[type] || []);
    const names = type === "armor" ? ["light", "medium", "heavy", "shield"]
      : type === "weapons" ? ["simple", "martial", ...new Set(content.items.filter((i) => i.weaponCategory && !i.rarity?.replace("none", "") && ["phb"].includes(i.book)).map((i) => i.name.toLowerCase()))]
      : type === "tools" ? TOOLS : content.languages.filter((l) => ["phb", "scag", "xge", "tce"].includes(l.book)).map((l) => l.name.toLowerCase());
    return [...new Set(names)].filter((n) => !have.has(n)).sort().map((n) => ({ value: n, label: title(n) }));
  }
  const exhaustionOpen = $derived(openCondition === "exhaustion");
  // Short Rest: hit dice picked to spend, per class; rolled when the rest is taken (PHB p. 186)
  let spend = $state({});
  let autoHeal = $state(true);
  let restResult = $state("");
  const REST_TEXT = {
    short: ["A short rest is a period of downtime, at least 1 hour long, during which a character does nothing more strenuous than eating, drinking, reading, and tending to wounds.",
      "A character can spend one or more Hit Dice at the end of a short rest, up to the character's maximum number of Hit Dice, which is equal to the character's level. For each Hit Die spent in this way, the player rolls the die and adds the character's Constitution modifier to it. The character regains hit points equal to the total (minimum of 0)."],
    long: ["A long rest is a period of extended downtime, at least 8 hours long, during which a character sleeps for at least 6 hours and performs no more than 2 hours of light activity, such as reading, talking, eating, or standing watch. If the rest is interrupted by a period of strenuous activity\u2014at least 1 hour of walking, fighting, casting spells, or similar adventuring activity\u2014the characters must begin the rest again to gain any benefit from it.",
      "At the end of a long rest, a character regains all lost hit points. The character also regains spent Hit Dice, up to a number of dice equal to half of the character's total number of them. You regain at least 1 Hit Die when you finish a long rest.",
      "A character can't benefit from more than one long rest in a 24-hour period, and a character must have at least 1 hit point at the start of the rest to gain its benefits."],
  };
  function shortRest() {
    const con = current.sheet.abilities.con.modifier;
    const rolls = [];
    const used = { ...(current.character.play.hit_dice_used || {}) };
    for (const hd of current.sheet.hit_dice) {
      for (let k = 0; k < (spend[hd.class_id] || 0); k++) rolls.push(Math.max(0, 1 + Math.floor(Math.random() * hd.die) + con));
      used[hd.class_id] = (used[hd.class_id] || 0) + (spend[hd.class_id] || 0);
    }
    current.character.play.hit_dice_used = used;
    const gained = rolls.reduce((a, b) => a + b, 0);
    if (rolls.length && autoHeal) setHp(Math.min(current.sheet.hp.max, current.sheet.hp.current + gained));
    takeRest("short");
    restResult = rolls.length ? `Rolled ${rolls.join(" + ")} = ${gained} hit points${autoHeal ? ", applied" : ""}.` : "Short rest taken.";
    spend = {};
  }
  let hurt = $state("");
  function setOverride(key, value) {
    if (!current.character.overrides) current.character.overrides = {};
    const o = current.character.overrides;
    if (value === "") delete o[key];
    else o[key] = Number(value);
    changed(400);
  }
  // DDB's customize: senses and speeds by hand (feet), defenses as a typed list
  function setCustomNumber(field, key, value) {
    current.character[field] = { ...(current.character[field] || {}), [key]: Math.max(0, Number(value) || 0) };
    if (!current.character[field][key]) delete current.character[field][key];
    changed(400);
  }
  let newDefense = $state({ type: "resist", name: "" });
  function addDefense() {
    if (!newDefense.name.trim()) return;
    current.character.custom_defenses = [...(current.character.custom_defenses || []), { ...newDefense, name: newDefense.name.trim() }];
    newDefense = { type: newDefense.type, name: "" };
    changed(100);
  }
  function removeDefense(k) {
    current.character.custom_defenses = current.character.custom_defenses.filter((_, i) => i !== k);
    changed(100);
  }
  $effect(() => {
    pane.ref;
    bigImage = false;  // a new item opens with the small picture
  });
  // DDB's sidebar controls arrive as static markup; one handler reads which button was pressed.
  function sidebarControl(event) {
    const label = event.target.closest("button")?.getAttribute("aria-label") || "";
    if (label === "Hide sidebar") close();
    else if (label === "Align Left") side = "left";
    else if (label === "Align Right") side = "right";
  }
  const containerSlots = $derived((current.character?.inventory || []).filter((x) => x.uid && content.byId.items[x.id]?.containerCapacity));
  function location(slotObj) {
    const box = containerSlots.find((x) => x.uid === slotObj?.inside);
    return box ? `In ${content.byId.items[box.id].name}` : "In Equipment";
  }
  function typeLine(it) {
    const kind = (it.group?.[0] || itemType(it).replace(/^(Common|Uncommon|Rare|Very Rare|Legendary|Artifact) /, "")).toLowerCase();
    const rarity = it.rarity && it.rarity !== "none" ? it.rarity : "common";
    return `${kind}, ${rarity}${it.reqAttune ? ` (requires attunement${typeof it.reqAttune === "string" ? " " + it.reqAttune : ""})` : ""}`;
  }
  function moveTo(uid) {
    slot.inside = uid || null;
    if (uid) slot.equipped = false;
    changed(150);
  }
  function stepQty(delta) {
    slot.qty = Math.max(0, (Number(slot.qty) || 1) + delta);
    changed(300);
  }

  const SPEED_NAMES = { walk: "Walking", fly: "Flying", swim: "Swimming", climb: "Climbing", burrow: "Burrowing" };
  let customizeOpen = $state(false);
  const CONDITIONS = ["blinded", "charmed", "deafened", "frightened", "grappled", "incapacitated", "invisible", "paralyzed", "petrified", "poisoned", "prone", "restrained", "stunned", "unconscious"];
  const sheet = $derived(current.sheet);
  const playState = $derived(current.character?.play || {});

  const spell = $derived(pane.kind === "spell" ? content.byId.spells[pane.ref] : null);
  const item = $derived(pane.kind === "item" ? content.byId.items[pane.ref] : null);
  const feat = $derived(pane.kind === "feat" ? content.byId.feats[pane.ref] : null);
  // the rules helper's "Explain this": the entry on show, as name and plain text (lib/AskBox.svelte)
  const explainSource = $derived(pane.kind === "spell" ? content.byId.spells[pane.ref] : pane.kind === "item" ? content.byId.items[pane.ref]
    : pane.kind === "feat" ? content.byId.feats[pane.ref] : pane.kind === "optionalfeature" ? content.byId.optionalfeatures[pane.ref]
    : pane.kind === "race" ? content.byId.races[pane.ref] : pane.kind === "feature" ? pane.extra
    : pane.kind === "condition" ? content.conditions.find((x) => x.name.toLowerCase() === String(pane.ref).toLowerCase() && x.source === "PHB") : null);
  const explainEntry = $derived(explainSource ? { name: explainSource.name,
    text: JSON.stringify(explainSource.entries || []).replace(/\{@\w+ ([^|}]*)[^}]*\}/g, "$1").replace(/["\[\]{}]/g, " ").slice(0, 2500) } : null);
  const option = $derived(pane.kind === "optionalfeature" ? content.byId.optionalfeatures[pane.ref] : null);
  const raceShown = $derived(pane.kind === "race" ? content.byId.races[pane.ref] : null);
  // basic combat actions, referred to by name (PHB entry preferred)
  const actionShown = $derived(pane.kind === "action"
    ? content.actions.filter((x) => x.name === pane.ref).sort((x, y) => (x.book === "phb" ? 0 : 1) - (y.book === "phb" ? 0 : 1))[0] : null);
  const slot = $derived(pane.extra?.slot !== undefined && current.character ? current.character.inventory[pane.extra.slot] : null);

  const PROPS = { "2H": "Two-handed", A: "Ammunition", F: "Finesse", H: "Heavy", L: "Light", LD: "Loading", R: "Reach", RLD: "Reload", S: "Special", T: "Thrown", V: "Versatile" };

  function cost(value) {
    if (!value) return "--";
    return value >= 100 ? `${value / 100} gp` : value >= 10 ? `${value / 10} sp` : `${value} cp`;
  }

  function prereq(list) {
    return (list || []).map((p) => {
      const out = [];
      if (p.level) out.push(typeof p.level === "object" ? `${p.level.class?.name ?? ""} level ${p.level.level}` : `level ${p.level}`);
      if (p.ability) out.push(p.ability.map((a) => Object.entries(a).map(([k, v]) => `${k.toUpperCase()} ${v}`).join(" or ")).join(", "));
      if (p.spell) out.push(p.spell.map((s) => plain(`{@spell ${s.split("#")[0]}}`)).join(", "));
      if (p.pact) out.push(`Pact of the ${p.pact}`);
      if (p.patron) out.push(`${p.patron} patron`);
      if (p.race) out.push(p.race.map((r) => title(r.name) + (r.subrace ? ` (${r.subrace})` : "")).join(" or "));
      if (p.proficiency) out.push(p.proficiency.map((x) => Object.keys(x).map((k) => `${x[k]} ${k}`).join(", ")).join(" or "));
      if (p.spellcasting || p.spellcasting2020) out.push("the ability to cast at least one spell");
      if (p.other) out.push(p.other);
      if (p.otherSummary) out.push(p.otherSummary.entry);
      return out.join("; ");
    }).filter(Boolean).join(" — or — ");
  }

  function toggle(key) {
    slot[key] = !slot[key];
    changed();
  }
  function removeSlot() {
    current.character.inventory.splice(pane.extra.slot, 1);
    changed();
    close();
  }
</script>

{#snippet paneBody()}
    {#snippet addItemsList(insideUid)}
      <div class="ddbc-collapsible__content ddb-container-add">
        <input type="search" placeholder="Search items" bind:value={itemQuery} aria-label="Search items to add" /> <NoncanonToggle />
        {#each itemMatches(itemQuery) as it (it.id)}
          <div class="ct-container-manager__item-header ddb-container-add-row"><span class="styles_itemName__xLCwW styles_common__4urYa">{it.name}</span>
            <button type="button" class="ct-theme-button ct-theme-button--filled ct-theme-button--interactive ct-button character-button ddbc-button character-button-small"
              onclick={() => addToInventory({ id: it.id, qty: 1, equipped: false, attuned: false }, insideUid)}><span class="ct-button__content">Add</span></button></div>
        {/each}
      </div>
    {/snippet}
    {#snippet head(name, sub = "")}
      <header class="ct-sidebar__header"><div>{sub}</div><div class="ct-sidebar__header-primary"><h1 class="ct-sidebar__heading styles_heading__j5Lvn">{name}</h1></div></header>
    {/snippet}
    {#snippet flatRules(list)}
      {#each list as e}
        {#if typeof e === "string"}<p><Tagged text={e} /></p>
        {:else if e.name && e.entries}
          {@const first = typeof e.entries[0] === "string" ? e.entries[0] : null}
          <p><b>{e.name}</b><br />{#if first}<Tagged text={first} />{/if}</p>{@render flatRules(first ? e.entries.slice(1) : e.entries)}
        {:else}<Entries entries={[e]} />{/if}
      {/each}
    {/snippet}
    {#snippet customize(cls, fields, base)}
      <div class="ddbc-collapsible {cls} {customizeOpen ? 'ddbc-collapsible--opened' : 'ddbc-collapsible--collapsed'} ddbc-collapsible--minimal">
        <div class="ddbc-collapsible__header" role="button" tabindex="0" onclick={() => (customizeOpen = !customizeOpen)} onkeydown={(e) => e.key === "Enter" && (customizeOpen = !customizeOpen)}>
          <div class="ddbc-collapsible__header-content"><div class="ddbc-collapsible__header-content-primary"><div class="ddbc-collapsible__heading">Customize</div></div></div>
          <div class="ddbc-collapsible__header-status">{@html ddb.icons[customizeOpen ? "chevron-up" : "chevron-down"] || ""}</div>
        </div>
        {#if customizeOpen}
          <div class="ddbc-collapsible__content">
            {#each fields as [key, label]}
              <div class="{base}__customize-item"><label class="{base}__customize-item-label">{label}<input class="{base}__customize-item-input" type="number" placeholder="--" value={current.character.overrides?.[key] ?? ""} oninput={(e) => setOverride(key, e.target.value)} /></label></div>
            {/each}
          </div>
        {/if}
      </div>
    {/snippet}
    {#if spell}
      {@const row = pane.extra}
      {@const school = SCHOOLS[spell.school] || spell.school}
      {@const feet = spell.range?.type === "point" && spell.range.distance?.type === "feet" ? spell.range.distance.amount : null}
      {@const comps = spell.components || {}}
      {@const dice = row ? damageOf(row, sheet?.level || 1) : ""}
      <div class="ct-spell-pane">
        <header class="ct-sidebar__header">
          <div>{row?.meta || ""}</div>
          <div class="ct-sidebar__header-primary">
            <div class="ct-sidebar__header-preview"><div class="ct-spell-pane__heading-preview ct-spell-pane__heading-preview--school-{String(school).toLowerCase()}"></div></div>
            <h1 class="ct-sidebar__heading styles_heading__j5Lvn"><div class="styles_editableName__9BMRa"><div><span class="styles_spellName__wX3ll">{spell.name}</span></div></div></h1>
          </div>
        </header>
        <div class="ct-spell-detail">
          <div class="ct-spell-detail__level-school">
            <span class="ct-spell-detail__level-school-item">{school}</span>
            <span class="ct-spell-detail__level-school-item">{spell.level === 0 ? "Cantrip" : `${ordinal(spell.level)}`}{spell.meta?.ritual ? " (Ritual)" : ""}</span>
          </div>
          {#if row}
            <div class="ct-spell-caster">
              <div class="ct-spell-caster__casting">
                <div class="ct-spell-caster__casting-label">Cast</div>
                <div class="ct-spell-caster__casting-actions">
                  {#if spell.level === 0 || row.usage === "at will"}At Will
                  {:else if !row.slots}{row.usage}
                  {:else}
                    {#each castableLevels(spell.level) as lv}
                      <button type="button" class="ct-theme-button ct-theme-button--filled ct-theme-button--interactive ct-button character-button ddbc-button character-button-small ddb-cast-at" onclick={() => castAt(lv)}><span class="ct-button__content">{ordinal(lv).replace(" level", "")}</span></button>
                    {:else}<span class="ddb-cast-none">No slots left of {ordinal(spell.level)} or higher</span>{/each}
                  {/if}
                </div>
              </div>
              {#if dice}
                <div class="ct-spell-caster__modifiers ct-spell-caster__modifiers--damages">
                  <div class="ct-spell-caster__modifier ct-spell-caster__modifier--damage">
                    <span class="ct-spell-caster__modifier-amount">{dice}</span>
                    <span class="ct-spell-caster__modifier-effect">{#if row.damage_types?.[0]}<span class="ddbc-damage-type-icon ddbc-damage-type-icon--{row.damage_types[0]}"><span class="ddbc-tooltip" title={row.damage_types[0]}>{@html ddb.icons[`damage-type-icon__img--${row.damage_types[0]}`] || ""}</span></span>{/if}Damage</span>
                  </div>
                </div>
              {/if}
            </div>
          {/if}
          <div class="ct-spell-detail__properties" role="list">
            <div class="styles_item__8bGe2 styles_inline__ufQJr" role="listitem"><p class="styles_label__My0Jp">Casting Time:</p><p class="styles_value__mg89v">{castingTime(spell.time)}</p></div>
            <div class="styles_item__8bGe2 styles_inline__ufQJr" role="listitem"><p class="styles_label__My0Jp">Range/Area:</p><p class="styles_value__mg89v">{#if feet}<span class="styles_numberDisplay__Rg1za"><span>{feet}</span><span class="styles_label__L8mZK styles_labelSignColor__Klmbs">ft.</span></span>{:else}{range(spell.range)}{/if}</p></div>
            <div class="styles_item__8bGe2 styles_inline__ufQJr" role="listitem"><p class="styles_label__My0Jp">Components:</p><p class="styles_value__mg89v"><span class="ct-spell-detail__components">{#each [["v", "V", "Verbal"], ["s", "S", "Somatic"], ["m", "M", "Material"]].filter(([k]) => comps[k]) as [k, letter, name], i}{i ? ", " : ""}<span class="ddbc-tooltip" title={name}>{letter}{k === "m" ? " *" : ""}</span>{/each}</span></p></div>
            <div class="styles_item__8bGe2 styles_inline__ufQJr" role="listitem"><p class="styles_label__My0Jp">Duration:</p><p class="styles_value__mg89v">{duration(spell.duration)}</p></div>
            <div class="styles_item__8bGe2 styles_inline__ufQJr" role="listitem"><p class="styles_label__My0Jp">Source:</p><div class="styles_value__mg89v"><p class="styles_reference__4pmEk"><span class="styles_name__mZMFY">{book(spell.book)}{spell.book === "phb" ? " (2014)" : ""}</span>{#if spell.page}<span>, pg. {spell.page}</span>{/if}</p></div></div>
            {#if !row}<div class="styles_item__8bGe2 styles_inline__ufQJr" role="listitem"><p class="styles_label__My0Jp">Classes:</p><p class="styles_value__mg89v">{[...spell.classes, ...spell.classesVariant.map((c) => `${c} (optional)`)].join(", ") || "--"}</p></div>{/if}
          </div>
          <div class="ddbc-html-content ct-spell-detail__description">
            <Entries entries={spell.entries} />{#if spell.entriesHigherLevel}<Entries entries={spell.entriesHigherLevel} />{/if}
            {#if comps.m}<p class="ct-spell-detail__components-description">* - ({typeof comps.m === "string" ? comps.m : comps.m.text})</p>{/if}
          </div>
        </div>
      </div>
    {:else if item}
      <header class="ct-sidebar__header">
        <div class="ct-sidebar__header-primary">
          {#if itemIcon(item)}<div class="ct-sidebar__header-preview"><button type="button" class="ddb-item-image-btn" onclick={() => (bigImage = !bigImage)} aria-label="Show the picture larger"><img class="ddb-item-image" src={itemIcon(item)} alt="" /></button></div>{/if}
          <h1 class="ct-sidebar__heading styles_heading__j5Lvn">{slot?.custom_name || item.name}</h1>
        </div>
      </header>
      {#if bigImage && item.ddbImage}<button type="button" class="ddb-item-big" onclick={() => (bigImage = false)} aria-label="Hide the large picture"><img src={itemIcon(item)} alt={item.name} /></button>{/if}
      <p class="ddb-item-meta"><em>{typeLine(item)}</em>{#if slot}<br />{location(slot)}{/if}</p>
      {#if slot}
        <details class="ddb-item-customize">
          <summary>Customize</summary>
          <label>Name <input type="text" value={slot.custom_name || ""} placeholder={item.name} oninput={(e) => { slot.custom_name = e.target.value || null; changed(600); }} /></label>
          <label>Notes <textarea rows="3" oninput={(e) => { slot.notes = e.target.value || null; changed(800); }}>{slot.notes || ""}</textarea></label>
        </details>
      {/if}
      <div class="ddb-item-props">
        {#if item.ac}<p><strong>Armor Class:</strong> {item.ac}{typeCode(item) === "LA" ? " + Dex modifier" : typeCode(item) === "MA" ? " + Dex modifier (max 2)" : ""}</p>{/if}
        {#if item.strength}<p><strong>Strength:</strong> {item.strength}</p>{/if}
        {#if item.stealth}<p><strong>Stealth:</strong> Disadvantage</p>{/if}
        {#if item.dmg1}<p><strong>Damage:</strong> {item.dmg1} {DAMAGE[item.dmgType] || ""}{item.dmg2 ? ` (versatile ${item.dmg2})` : ""}</p>{/if}
        {#if item.range}<p><strong>Range:</strong> {item.range} ft.</p>{/if}
        {#if item.property?.length}<p><strong>Properties:</strong> {item.property.map((p) => PROPS[p] || p).join(", ")}</p>{/if}
        {#if item.bonusWeapon}<p><strong>Attack and damage:</strong> {item.bonusWeapon}</p>{/if}
        {#if item.bonusAc}<p><strong>AC bonus:</strong> {item.bonusAc}</p>{/if}
        <p><strong>Weight:</strong> {item.weight ? `${item.weight} lb.` : "--"}</p>
        <p><strong>Cost:</strong> {cost(item.value)}</p>
        <p><strong>Source:</strong> <em>{book(item.book)}{item.page ? `, p. ${item.page}` : ""}</em></p>
      </div>
      <div class="pane-body ddb-item-desc"><Entries entries={item.entries || []} /></div>
      {#if item.ddbTags?.length}
        <div class="ddb-item-tags"><strong>Tags:</strong> {#each item.ddbTags as tag}<span class="ddb-tag">{tag}</span>{/each}</div>
      {/if}
      {#if slot}
        <div class="ddb-item-qty">
          <strong>Quantity</strong>
          <button type="button" class="ddb-qty-btn" onclick={() => stepQty(-1)} aria-label="One fewer">−</button>
          <input type="number" min="0" value={slot.qty || 1} oninput={(e) => { slot.qty = Math.max(0, Number(e.target.value) || 0); changed(500); }} aria-label="Quantity" />
          <button type="button" class="ddb-qty-btn" onclick={() => stepQty(1)} aria-label="One more">+</button>
        </div>
        <div class="ddb-item-actions">
          {#if equippable(item)}<button type="button" class="ddb-outline-btn" onclick={() => toggle("equipped")}>{slot.equipped ? "Unequip" : "Equip"}</button>{/if}
          {#if item.reqAttune}<button type="button" class="ddb-outline-btn" onclick={() => toggle("attuned")}>{slot.attuned ? "Unattune" : "Attune"}</button>{/if}
          {#if containerSlots.some((x) => x !== slot)}
            <label class="ddb-move">Move
              <select value={slot.inside || ""} onchange={(e) => moveTo(e.target.value)}>
                <option value="">Equipment</option>
                {#each containerSlots.filter((x) => x !== slot) as box}<option value={box.uid}>{content.byId.items[box.id].name}</option>{/each}
              </select>
            </label>
          {/if}
          <button type="button" class="ddb-outline-btn" onclick={removeSlot}>Delete</button>
        </div>
        {#if sheet?.infusions}
          {@const known = (sheet.features || []).filter((f) => f.optionalfeature && (content.byId.optionalfeatures[f.optionalfeature]?.featureType || []).includes("AI"))}
          <label class="ddb-move">Infusion (TCE p. 12; {sheet.infusions.used} of {sheet.infusions.max} items infused)
            <select value={slot.infusion || ""} onchange={(e) => { slot.infusion = e.target.value || undefined; changed(100); }}>
              <option value="">None</option>
              {#each known as f}<option value={f.optionalfeature}>{f.name}</option>{/each}
            </select>
          </label>
        {/if}
        <div>
        </div>
      {/if}
    {:else if actionShown}
      {@render head(actionShown.name, `Action · ${book(actionShown.book)}${actionShown.page ? `, pg. ${actionShown.page}` : ""}`)}
      <div class="pane-body"><Entries entries={actionShown.entries || []} /></div>
    {:else if raceShown}
      {@render head(raceName(raceShown.name), `Race · ${book(raceShown.book)}${raceShown.page ? `, pg. ${raceShown.page}` : ""}`)}
      {#if raceShown.blurb}<p><em>{raceShown.blurb}</em></p>{/if}
      <div class="pane-body"><Entries entries={raceShown.entries || []} /></div>
    {:else if feat}
      {@render head(feat.name, `Feat · ${book(feat.book)}${feat.page ? `, pg. ${feat.page}` : ""}`)}
      {#if feat.prerequisite}<p class="prereq"><strong>Prerequisite:</strong> {prereq(feat.prerequisite)}</p>{/if}
      <div class="pane-body"><Entries entries={feat.entries} /></div>
    {:else if option}
      {@render head(option.name, `${book(option.book)}${option.page ? `, pg. ${option.page}` : ""}`)}
      {#if option.prerequisite}<p class="prereq"><strong>Prerequisite:</strong> {prereq(option.prerequisite)}</p>{/if}
      <div class="pane-body"><Entries entries={option.entries} /></div>
    {:else if pane.kind === "feature"}
      {@render head(pane.extra?.name, `${raceName(pane.extra?.origin || "")}${pane.extra?.level ? ` · Level ${pane.extra.level}` : ""} · ${book(pane.extra?.book)}${pane.extra?.page ? `, pg. ${pane.extra.page}` : ""}`)}
      <div class="pane-body"><Entries entries={pane.extra?.entries || []} /></div>
      {@const hidden = (current.character?.hidden_features || []).includes(pane.extra?.name)}
      {#if current.character}
        <div class="ddb-item-actions"><button type="button" class="ddb-outline-btn" onclick={() => {
          const list = current.character.hidden_features || [];
          current.character.hidden_features = hidden ? list.filter((n) => n !== pane.extra.name) : [...list, pane.extra.name];
          changed(100);
        }}>{hidden ? "Show on sheet" : "Hide on sheet"}</button></div>
      {/if}
    {:else if pane.kind === "condition"}
      {@const cond = content.conditions.find((x) => x.name.toLowerCase() === String(pane.ref).toLowerCase() && x.source === "PHB")}
      {@render head(title(pane.ref), `Condition · Player's Handbook, pg. ${cond?.page || 290}`)}
      <div class="pane-body">{#if cond}<Entries entries={cond.entries} />{/if}
        <h5>All conditions</h5>
        <p>{#each content.conditions.filter((x) => x.source === "PHB") as x, i}{#if i}, {/if}<button type="button" class="ref" onclick={() => (pane.ref = x.name)}>{x.name}</button>{/each}</p>
      </div>
    {:else if pane.kind === "conditions" && sheet}
      {#snippet conditionText(name)}
        {@const cond = content.conditions.find((x) => x.name.toLowerCase() === name && x.source === "PHB")}
        <div class="ddbc-collapsible__content"><div class="ddbc-html-content"><Entries entries={cond?.entries || []} /></div></div>
      {/snippet}
      <div class="ct-condition-manage-pane">
        <header class="ct-sidebar__header"><div></div><div class="ct-sidebar__header-primary"><h1 class="ct-sidebar__heading styles_heading__j5Lvn">Conditions</h1></div></header>
        <div class="ct-condition-manage-pane__conditions">
          {#each CONDITIONS as c}
            {@const on = (playState.conditions || []).includes(c)}
            {@const opened = openCondition === c}
            <div class="ddbc-collapsible {opened ? 'ddbc-collapsible--opened' : 'ddbc-collapsible--collapsed'} ddbc-collapsible--minimal">
              <div class="ddbc-collapsible__header" role="button" tabindex="0" onclick={() => (openCondition = opened ? null : c)} onkeydown={(e) => e.key === "Enter" && (openCondition = opened ? null : c)}>
                <div class="ddbc-collapsible__header-content"><div class="ddbc-collapsible__header-content-primary"><div class="ct-condition-manage-pane__condition-heading"><div class="ct-condition-manage-pane__condition">
                  <div class="ct-condition-manage-pane__condition-preview">{@html ddb.icons[`condition-${c}`] || ""}</div>
                  <div class="ct-condition-manage-pane__condition-name">{title(c)}</div>
                  <div class="ct-condition-manage-pane__condition-toggle"><button type="button" class="styles_toggle__nDukS styles_themed__H38P+" aria-pressed={on} aria-label="{on ? 'Disable' : 'Enable'} {title(c)}" onclick={(e) => { e.stopPropagation(); toggleCondition(c); }}></button></div>
                </div></div></div></div>
                <div class="ddbc-collapsible__header-status">{@html ddb.icons[opened ? "chevron-up" : "chevron-down"] || ""}</div>
              </div>
              {#if opened}{@render conditionText(c)}{/if}
            </div>
          {/each}
        </div>
        <div class="ct-condition-manage-pane__conditions ct-condition-manage-pane__condition--special"><div>
          <div class="ddbc-collapsible {exhaustionOpen ? 'ddbc-collapsible--opened' : 'ddbc-collapsible--collapsed'} ddbc-collapsible--minimal">
            <div class="ddbc-collapsible__header" role="button" tabindex="0" onclick={() => (openCondition = exhaustionOpen ? null : "exhaustion")} onkeydown={(e) => e.key === "Enter" && (openCondition = exhaustionOpen ? null : "exhaustion")}>
              <div class="ddbc-collapsible__header-content"><div class="ddbc-collapsible__header-content-primary"><div class="ct-condition-manage-pane__condition-heading"><div class="ct-condition-manage-pane__condition">
                <div class="ct-condition-manage-pane__condition-preview">{@html ddb.icons["condition-exhaustion"] || ""}</div>
                <div class="ct-condition-manage-pane__condition-name">Exhaustion</div>
                <div class="ct-condition-manage-pane__condition-level">Level {playState.exhaustion || "--"}</div>
              </div></div></div></div>
              <div class="ddbc-collapsible__header-status">{@html ddb.icons[exhaustionOpen ? "chevron-up" : "chevron-down"] || ""}</div>
            </div>
            <div class="ddbc-collapsible__header-footer"><div class="styles_progressBar__aW4jZ">
              {#each [0, 1, 2, 3, 4, 5, 6] as n}<button type="button" class="styles_bar__zBc+W" class:styles_active__K1oX4={(playState.exhaustion || 0) >= n && n > 0} aria-pressed={(playState.exhaustion || 0) === n} aria-disabled="false" onclick={() => setExhaustion(n)}>{n || "--"}</button>{/each}
            </div></div>
            {#if exhaustionOpen}{@render conditionText("exhaustion")}{/if}
          </div>
        </div></div>
      </div>
      <h5 class="ddb-pane-extra-heading">Active Effects</h5>
      <p class="pane-sub">Not a DDB feature: spells and class features that change numbers while they last.</p>
      <ul class="pane-toggles">
        {#each sheet.effects.available as e}
          {@const on = sheet.effects.active.includes(e.name)}
          <li><label><input type="checkbox" checked={on} onchange={() => toggleEffect(e.name)} /> {on ? "✔" : "○"} {e.name}</label> <span class="dim small">{e.text}</span></li>
        {/each}
      </ul>
      {#if sheet.effects.notes.length}<ul class="effect-notes">{#each sheet.effects.notes as n}<li>{n}</li>{/each}</ul>{/if}
    {:else if pane.kind === "defenses" && sheet}
      {@const groups = [["Resistances", sheet.defenses.resist], ["Immunities", sheet.defenses.immune], ["Condition Immunities", sheet.defenses.condition_immune], ["Vulnerabilities", sheet.defenses.vulnerable || []]].filter(([, list]) => list.length)}
      <div class="ct-defense-manage-pane">
        <header class="ct-sidebar__header"><div></div><div class="ct-sidebar__header-primary"><h1 class="ct-sidebar__heading styles_heading__j5Lvn">Defenses</h1></div></header>
        {#each groups as [heading, list]}
          <div class="ct-defense-manage-pane__group">
            <div class="ct-defense-manage-pane__heading">{heading}</div>
            {#each list as x}<div class="ct-defense-manage-pane__item"><span class="ct-defense-manage-pane__item-label">{title(x)}</span></div>{/each}
          </div>
        {:else}
          <div class="ct-defense-manage-pane__default">No Resistances, Immunities, or Vulnerabilities</div>
        {/each}
        <h2 class="ct-sidebar__subheading">Customize</h2>
        {#each current.character.custom_defenses || [] as d, k}
          <div class="ddb-bonus-feat-head"><span>{({ resist: "Resistance", immune: "Immunity", condition_immune: "Condition immunity", vulnerable: "Vulnerability" })[d.type]}: {d.name}</span>
            <button type="button" class="ct-button character-button ddbc-button character-button-small" onclick={() => removeDefense(k)}><span class="ct-button__content">Remove</span></button></div>
        {/each}
        <div class="ddb-custom-grid">
          <select bind:value={newDefense.type} aria-label="Defense type"><option value="resist">Resistance</option><option value="immune">Immunity</option><option value="condition_immune">Condition immunity</option><option value="vulnerable">Vulnerability</option></select>
          <input type="text" placeholder="e.g. fire, poisoned" bind:value={newDefense.name} aria-label="Damage type or condition" />
          <button type="button" class="ct-button character-button ddbc-button character-button-small" onclick={addDefense}><span class="ct-button__content">Add</span></button>
        </div>
      </div>
    {:else if pane.kind === "hp" && sheet}
      {@const temp = Number(playState.temp_hp || 0)}
      {@const healed = Math.min(sheet.hp.max, sheet.hp.current + (Number(heal) || 0))}
      {@const absorbed = Math.min(temp, Number(hurt) || 0)}
      {@const hurtTo = Math.max(0, sheet.hp.current - ((Number(hurt) || 0) - absorbed))}
      <header class="ct-sidebar__header"><div></div><div class="ct-sidebar__header-primary"><h1 class="ct-sidebar__heading styles_heading__j5Lvn">HP Management</h1></div></header>
      <div class="styles_container__HqPuh">
        <div class="styles_container__nsTN6 styles_border__5xwH4">
          <div class="styles_innerContainer__Xn2+o">
            <div class="styles_item__UVpsr"><label class="styles_label__ysVMP" for="hp-current">Current</label><div><input id="hp-current" class="styles_input__op0gN" type="number" min="0" max={sheet.hp.max} value={sheet.hp.current} oninput={(e) => setHp(e.target.value)} /></div></div>
            <div class="styles_item__UVpsr"><div class="styles_spacer__fglT0"></div><span class="styles_number__j1d93 styles_slash__UmBPf">/</span></div>
            <div class="styles_item__UVpsr"><span class="styles_label__ysVMP">Max</span><span class="accessibility_screenreaderOnly__OEzRB">Max hit points</span><div class="styles_number__j1d93 styles_maxContainer__mt+Ff"><span>{sheet.hp.max}</span></div></div>
          </div>
          <div class="styles_item__UVpsr styles_temp__pxAha"><label class="styles_label__ysVMP" for="hp-temp">Temp</label><div><input id="hp-temp" class="styles_input__op0gN" type="number" min="0" placeholder="--" value={temp || ""} oninput={(e) => setHp(undefined, e.target.value)} /></div></div>
        </div>
        <div class="styles_column__mt+gc styles_container__2ogER styles_border__5xwH4">
          <div class="styles_row__Urkup styles_container__2ogER">
            <div class="styles_column__mt+gc styles_inputsContainer__CbmMr">
              <div class="styles_inputContainer__Lnmld styles_healingContainer__V2+4y"><label class="styles_inputLabel__VasOY styles_positiveColor__DEfXY" for="hp-heal">Healing</label><input id="hp-heal" class="styles_input__lzRfF" type="number" min="0" bind:value={heal} oninput={() => (hurt = "")} /></div>
              <div class="styles_row__Urkup styles_newValues__tBVYh"><div class="styles_column__mt+gc"><span class="styles_label__mCSwE">New HP</span><span class="styles_value__3Egg6">{hurt ? hurtTo : healed}</span></div>
                {#if hurt && absorbed}<div class="styles_column__mt+gc"><span class="styles_label__mCSwE">New Temp</span><span class="styles_value__3Egg6">{temp - absorbed}</span></div>{/if}</div>
              <div class="styles_inputContainer__Lnmld styles_damageContainer__DkOxl"><label class="styles_inputLabel__VasOY styles_negativeColor__2rFBs" for="hp-hurt">Damage</label><input id="hp-hurt" class="styles_input__lzRfF" type="number" min="0" bind:value={hurt} oninput={() => (heal = "")} /></div>
            </div>
            <div class="styles_column__mt+gc styles_modifyButtons__Hbyru">
              <button type="button" class="Button_button__B9Kr5 ButtonVariants_primary__TMQ5y ButtonSizes_medium__uHe8x styles_xx-small__Q1OkG styles_themed__AiJUu styles_solid__2ijrG styles_increase__8X2Yq" aria-label="Increase Hit Points"
                onclick={() => { if (Number(heal)) setHp(healed); heal = ""; }}></button>
              <button type="button" class="Button_button__B9Kr5 ButtonVariants_primary__TMQ5y ButtonSizes_medium__uHe8x styles_xx-small__Q1OkG styles_themed__AiJUu styles_solid__2ijrG styles_decrease__ALj21" aria-label="Decrease Hit Points"
                onclick={() => { if (Number(hurt)) setHp(hurtTo, temp - absorbed); hurt = ""; }}></button>
            </div>
          </div>
        </div>
        <div class="styles_row__egceJ styles_overrides__Dw9eH styles_border__5xwH4">
          <label class="styles_column__YJjtb styles_override__UI455 styles_label__AMNUN">Max HP Modifier<input class="styles_input__0NBCk" min="-99" max="99" placeholder="--" type="number" value={current.character.overrides?.hp_bonus ?? ""} oninput={(e) => setOverride("hp_bonus", e.target.value)} /></label>
          <label class="styles_column__YJjtb styles_override__UI455 styles_label__AMNUN">Override Max HP<input class="styles_input__0NBCk" min="1" max="999" placeholder="--" type="number" value={current.character.overrides?.hp_max ?? ""} oninput={(e) => setOverride("hp_max", e.target.value)} /></label>
        </div>
      </div>
      <h5 class="ddb-pane-extra-heading">Death Saves</h5>
      <p>Successes {#each [1, 2, 3] as n}<button type="button" class="pip" class:on={(playState.death_saves?.success || 0) >= n} onclick={() => deathSave("success", n)} aria-label="Success {n}">{(playState.death_saves?.success || 0) >= n ? "✔" : "○"}</button>{/each}
        · Failures {#each [1, 2, 3] as n}<button type="button" class="pip fail" class:on={(playState.death_saves?.failure || 0) >= n} onclick={() => deathSave("failure", n)} aria-label="Failure {n}">{(playState.death_saves?.failure || 0) >= n ? "✖" : "○"}</button>{/each}</p>
      {#if (playState.death_saves?.failure || 0) >= 3}<p class="ddb-pane-note"><strong>Dead.</strong> Three failed death saves (PHB p. 197).</p>
      {:else if (playState.death_saves?.success || 0) >= 3}<p class="ddb-pane-note"><strong>Stable.</strong> Unconscious at 0 hit points; regains 1 hit point after 1d4 hours (PHB p. 197).</p>
      {:else}<p class="ddb-pane-note">Regaining any hit points resets both counts.</p>{/if}
    {:else if pane.kind === "rest" && sheet}
      {@const short = pane.ref === "short"}
      {@const con = sheet.abilities.con.modifier}
      {@const recovers = [...(short ? [] : ["All hit points", `Up to ${Math.max(1, Math.floor(sheet.level / 2))} Hit Dice`, ...(sheet.spellcasting.slots?.some((sl) => sl.max) ? ["Spell slots"] : [])]),
        ...(sheet.spellcasting.pact ? ["Pact Magic slots"] : []), ...sheet.counters.filter((c) => !short || c.reset === "short").map((c) => c.name)]}
      <div class="ct-reset-pane">
        <header class="ct-sidebar__header"><div></div><div class="ct-sidebar__header-primary"><h1 class="ct-sidebar__heading styles_heading__j5Lvn">{short ? "Short Rest" : "Long Rest"}</h1></div></header>
        <div class="ct-reset-pane__intro">{#if short}{REST_TEXT.short[0]}{:else}{#each REST_TEXT.long as para}<p>{para}</p>{/each}{/if}</div>
        <div class="ct-reset-pane__recover">
          <div class="ct-reset-pane__recover-heading">Recover</div>
          <div class="ct-reset-pane__recover-sources">{recovers.join(", ") || "Nothing resets on a short rest."}</div>
          {#if short}
            <div class="ct-reset-pane__recover-max-hp">
              <div class="ddbc-checkbox character-checkbox {autoHeal ? 'ddbc-checkbox--is-enabled character-checkbox-enabled' : 'ddbc-checkbox--is-disabled character-checkbox-disabled'} ddbc-checkbox--is-interactive character-checkbox-interactive"
                role="checkbox" tabindex="0" aria-checked={autoHeal} onclick={() => (autoHeal = !autoHeal)} onkeydown={(e) => e.key === "Enter" && (autoHeal = !autoHeal)}>
                <div class="ddbc-checkbox__input character-checkbox-input">{#if autoHeal}{@html ddb.icons["checkbox-check"] || "✓"}{/if}</div>
                <div class="ddbc-checkbox__label character-checkbox-label">Automatically apply healing with dice result</div>
              </div>
            </div>
          {/if}
        </div>
        {#if short}
          <div class="ct-reset-pane__hitdice">
            {#each sheet.hit_dice as hd (hd.class_id)}
              {@const picked = spend[hd.class_id] || 0}
              <div class="ct-reset-pane__hitdie">
                <div class="ct-reset-pane__hitdie-heading"><span class="ct-reset-pane__hitdie-heading-class">{hd.class}</span>(Hit Die: 1d{hd.die}{con ? signed(con) : ""} • Total: {hd.total})</div>
                <div class="ct-reset-pane__hitdie-manager"><div class="ct-slot-manager ct-slot-manager--size-small">
                  {#each Array.from({ length: hd.total }, (_, k) => k + 1) as n}
                    {@const spent = n <= hd.used}
                    {@const chosen = !spent && n <= hd.used + picked}
                    <div role="checkbox" tabindex="0" aria-checked={spent || chosen} aria-label={spent ? "spent" : "spend"} class="ct-slot-manager__slot ct-slot-manager__slot--interactive" class:ct-slot-manager__slot--used={spent || chosen}
                      onclick={() => !spent && (spend = { ...spend, [hd.class_id]: chosen && n === hd.used + picked ? picked - 1 : n - hd.used })}
                      onkeydown={(e) => e.key === "Enter" && !spent && (spend = { ...spend, [hd.class_id]: n - hd.used })}></div>
                  {/each}
                </div></div>
              </div>
            {/each}
            {#if restResult}<p class="ddb-rest-result">{restResult}</p>{/if}
          </div>
        {/if}
        <div class="ct-reset-pane__actions">
          <div class="ct-reset-pane__action">
            <button type="button" class="ct-theme-button ct-theme-button--filled ct-theme-button--interactive ct-button character-button ddbc-button character-button ct-button--confirm" onclick={() => (short ? shortRest() : (takeRest("long"), close()))}><span class="ct-button__content">Take {short ? "Short" : "Long"} Rest</span></button>
          </div>
          {#if short}<div class="ct-reset-pane__action"><button type="button" class="ct-theme-button ct-theme-button--outline ct-theme-button--interactive ct-button character-button ddbc-button character-button" onclick={() => { spend = {}; restResult = ""; }}><span class="ct-button__content">Reset</span></button></div>{/if}
        </div>
      </div>
    {:else if pane.kind === "manage"}
      {@const ch = current.character}
      {@const avatar = ch?.description?.avatar_url}
      {#snippet menuItem(label, icon, onclick, external = false)}
        <div class="styles_item__-oPdy" role="button" tabindex="0" {onclick} onkeydown={(e) => e.key === "Enter" && onclick()}>
          <div class="styles_prefixIcon__ikqN1">{@html ddb.icons[icon] || ""}</div><div class="styles_label__ZLSbA">{label}</div>
          <div class="styles_suffixIcon__8XdVT">{#if external}{@html ddb.icons["manage-link"] || ""}{/if}</div>
        </div>
      {/snippet}
      <div class="styles_characterManagePane__cAzM6">
        <div class="styles_intro__DxeXR">
          <div class="styles_summary__UPXYJ">
            <div class="ddbc-character-avatar__portrait styles_avatar__t7tEz {avatar ? '' : 'ddbc-character-avatar__portrait--none'}" style={avatar ? `background-image:url("${avatar}")` : ""}></div>
            <div class="styles_characterNameContainer__hx5Tx"><h1 class="styles_characterName__2x8wQ">{ch?.name}</h1></div>
            <div class="styles_description__jCVoT">
              <div class="ddbc-character-summary styles_summaryText__SkkYY"><span class="ddbc-character-summary__race">{raceName(sheet?.race || "")}</span></div>
              <div class="ddbc-character-progression-summary"><div class="ddbc-character-progression-summary__level">Level {sheet?.level}</div></div>
            </div>
          </div>
          <div class="styles_classList__J5Oib">
            {#each ch?.classes || [] as entry}
              {@const cls = content.byId.classes[entry.id]}
              {@const sub = cls?.subclasses?.find((x) => x.id === entry.subclass)}
              <div class="styles_classItem__h4PG2">
                <div class="styles_classImage__S3Nvj" style={cls?.ddbArt ? `background-image: url("${window.DND5E.ddb}/${cls.ddbArt}")` : ""}><div class="styles_classLevel__QZRKd">{entry.level}</div></div>
                <div class="styles_classSummary__190Xx"><div>{cls?.name || entry.id}</div><div class="styles_classMeta__Pd+W2">{sub ? sub.name : "No Subclass"}</div></div>
              </div>
            {/each}
          </div>
          <div class="styles_buttonGroup__22Vci"><div class="styles_featureCallout__hhyL3">
            <button type="button" class="Button_button__B9Kr5 ButtonVariants_primary__TMQ5y ButtonVariants_outline__v36Mn ButtonSizes_x-small__AQ7c6 styles_x-small__8tmZN styles_themed__AiJUu styles_dark__O1vGK styles_outline__lyFTR styles_decorateButton__ubbJq" onclick={() => show("decorate", pane.ref)}>{@html ddb.icons["manage-appearance"] || ""}<span>Change Sheet Appearance</span></button>
          </div></div>
        </div>
        <ul class="styles_menu__phzoW">
          <div class="styles_group__tWuIt">
            <div class="styles_item__-oPdy styles_label__uDuw3"><div class="styles_label__ZLSbA">My Character</div><div class="styles_suffixIcon__8XdVT"></div></div>
            {@render menuItem("Manage Character & Levels", "manage-manage-character-and-levels", () => { close(); location.hash = `#/c/${pane.ref}/builder/class`; }, true)}
            {@render menuItem("Character Settings", "manage-character-settings", () => { close(); location.hash = `#/c/${pane.ref}/builder/home`; })}
            {@render menuItem("Custom Skills", "", () => show("skills", pane.ref))}
            {@render menuItem("Campaigns", "", () => show("campaigns", pane.ref))}
            {@render menuItem("Revert to an Earlier Day", "", () => show("history", pane.ref))}
            {@render menuItem("Open Choices and Problems", "", () => { close(); location.hash = `#/c/${pane.ref}/builder/summary`; })}
          </div>
          <div class="styles_group__tWuIt">
            <div class="styles_item__-oPdy styles_label__uDuw3"><div class="styles_label__ZLSbA">Play</div><div class="styles_suffixIcon__8XdVT"></div></div>
            {@render menuItem("Short Rest", "manage-short-rest", () => show("rest", "short"))}
            {@render menuItem("Long Rest", "manage-long-rest", () => show("rest", "long"))}
            {@render menuItem("Export to PDF", "manage-export-to-pdf", () => { close(); location.hash = `#/c/${pane.ref}/print`; })}
          </div>
        </ul>
      </div>
    {:else if pane.kind === "ability" && sheet}
      {@const ab = sheet.abilities[pane.ref]}
      {@const text = content.abilitytexts.find((x) => x.id === pane.ref)}
      <div>
      <header class="ct-sidebar__header"><div></div><div class="ct-sidebar__header-primary"><div class="ct-sidebar__header-preview">{@html (ddb.icons[`ability-${pane.ref}`] || "").replace("styles_icon__2PFMo", "styles_icon__Teo4H").replaceAll(`fill="#fff"`, `fill="#242528"`)}</div>
        <h1 class="ct-sidebar__heading styles_heading__j5Lvn">{ABILITY_NAMES[pane.ref]} {ab.score}<span class="styles_modifier__ecyZh">(<span class="styles_numberDisplay__Rg1za styles_signed__scf97 styles_signedNumber__hCdrI"><span class="styles_sign__NdR6X styles_labelSignColor__Klmbs">{ab.modifier < 0 ? "-" : "+"}</span><span>{Math.abs(ab.modifier)}</span></span>)</span></h1></div></header>
      <div><AbilityCalc a={pane.ref} /></div>
      {#snippet abilityText(list, depth)}
        {#each list as e}
          {#if typeof e === "string"}<p><Tagged text={e} /></p>
          {:else if e.name && e.entries && (!e.type || e.type === "entries")}
            {#if depth === 0}<h4>{e.name}</h4>{:else}<h5>{e.name}</h5>{/if}{@render abilityText(e.entries, depth + 1)}
          {:else}<Entries entries={[e]} />{/if}
        {/each}
      {/snippet}
      {#if text}<div class="ddbc-html-content styles_description__jru+3">{@render abilityText(text.entries, 0)}</div>{/if}
      </div>
    {:else if pane.kind === "speed" && sheet}
      {@const rules = content.ruletexts.find((x) => x.id === "speed")}
      <div class="ct-speed-manage-pane">
        <header class="ct-sidebar__header"><div></div><div class="ct-sidebar__header-primary"><h1 class="ct-sidebar__heading styles_heading__j5Lvn">Speed</h1></div></header>
        <div class="ct-speed-manage-pane__speeds">
          {#each Object.entries(sheet.speed).filter(([k]) => k !== "overridden") as [k, v]}
            <div class="ct-speed-manage-pane__speed"><span class="ct-speed-manage-pane__speed-label">{SPEED_NAMES[k] || title(k)}</span><span class="ct-speed-manage-pane__speed-amount"><span class="styles_numberDisplay__Rg1za"><span>{v}</span><span class="styles_label__L8mZK styles_labelSignColor__Klmbs">ft.</span></span></span></div>
          {/each}
        </div>
        <label class="ddb-xp-change">Speed shown in the header <select value={current.character.preferences?.primary_movement || "walk"} onchange={(e) => { current.character.preferences = { ...(current.character.preferences || {}), primary_movement: e.target.value }; changed(100); }}>
          {#each Object.keys(sheet.speed).filter((k) => k !== "overridden") as k}<option value={k}>{SPEED_NAMES[k] || title(k)}</option>{/each}</select></label>
        {@render customize("ct-speed-manage-pane__customize", [["speed", "Walking Speed (set to)"]], "ct-speed-manage-pane")}
        <div class="ddb-custom-grid">
          {#each ["fly", "swim", "climb", "burrow"] as mode}
            <label>{title(mode)} speed (ft.) <input type="number" min="0" step="5" value={current.character.custom_speeds?.[mode] || ""} oninput={(e) => setCustomNumber("custom_speeds", mode, e.target.value)} /></label>
          {/each}
        </div>
        {#if rules}<div class="ddbc-html-content ct-speed-manage-pane__description">{@render flatRules(rules.entries)}</div>{/if}
      </div>
    {:else if pane.kind === "senses" && sheet}
      {@const rules = content.ruletexts.find((x) => x.id === "senses")}
      <div class="ct-sense-manage-pane">
        <header class="ct-sidebar__header"><div></div><div class="ct-sidebar__header-primary"><h1 class="ct-sidebar__heading styles_heading__j5Lvn">Senses</h1></div></header>
        <div class="ct-sense-manage-pane__senses">
          {#each [["perception", "Passive Perception"], ["investigation", "Passive Investigation"], ["insight", "Passive Insight"]] as [k, label]}
            <div class="ct-sense-manage-pane__sense"><span class="ct-sense-manage-pane__sense-label">{label}:</span><span class="ct-sense-manage-pane__sense-value">{sheet.passives[k]}</span></div>
          {/each}
          {#each Object.entries(sheet.senses || {}) as [k, v]}
            <div class="ct-sense-manage-pane__sense"><span class="ct-sense-manage-pane__sense-label">{title(k)}:</span><span class="ct-sense-manage-pane__sense-value">{v} ft.</span></div>
          {/each}
        </div>
        <h2 class="ct-sidebar__subheading">Customize</h2>
        <div class="ddb-custom-grid">
          {#each ["darkvision", "blindsight", "tremorsense", "truesight"] as sense}
            <label>{title(sense)} (ft.) <input type="number" min="0" step="5" value={current.character.custom_senses?.[sense] || ""} oninput={(e) => setCustomNumber("custom_senses", sense, e.target.value)} /></label>
          {/each}
        </div>
        {#if rules}<div class="ddbc-html-content ct-sense-manage-pane__description">{@render flatRules(rules.entries)}</div>{/if}
      </div>
    {:else if pane.kind === "currency" && sheet}
      {@const coins = [["pp", "Platinum (pp)"], ["gp", "Gold (gp)"], ["ep", "Electrum (ep)"], ["sp", "Silver (sp)"], ["cp", "Copper (cp)"]]}
      {@const total = (Number(current.character.currency?.pp || 0) * 10 + Number(current.character.currency?.gp || 0) + Number(current.character.currency?.ep || 0) / 2 + Number(current.character.currency?.sp || 0) / 10 + Number(current.character.currency?.cp || 0) / 100)}
      {@render head("Currency")}
      {#each sheet.container_coins || [] as boxCoins}
        <p class="ddb-pane-note">In {boxCoins.name}: {["pp", "gp", "ep", "sp", "cp"].filter((c) => boxCoins.coins[c]).map((c) => `${boxCoins.coins[c]} ${c}`).join(", ") || "none"}{boxCoins.weightless ? " (weighs nothing)" : ""}</p>
      {/each}
      <div class="ct-currency-pane__total"><div class="ct-currency-pane__total-info"><div class="ct-currency-pane__total-heading">Total in Gold</div><div class="ct-currency-pane__total-count">{Math.round(total * 100) / 100} gp</div></div></div>
      {#each coins as [c, label]}
        <div class="ct-currency-pane__currency"><div class="ct-currency-pane__currency-row">
          <span class="ct-currency-pane__currency-icon ddb-coin ddb-coin--{c}">{c.toUpperCase()}</span>
          <div class="ct-currency-pane__currency-info"><div class="ct-currency-pane__currency-name">{label}</div></div>
          <input class="ct-currency-pane__currency-value-input" type="number" min="0" aria-label={label} value={current.character.currency?.[c] || 0}
            oninput={(e) => { current.character.currency = { ...(current.character.currency || {}), [c]: Math.max(0, Number(e.target.value) || 0) }; changed(500); }} />
        </div></div>
      {/each}
    {:else if pane.kind === "encumbrance" && sheet}
      {@const enc = sheet.encumbrance}
      {@const str = sheet.abilities.str.score}
      {@render head("Encumbrance")}
      <div class="ct-encumbrance-pane__weight"><span class="ct-encumbrance-pane__weight-label">Weight Carried:</span>{enc.weight} lb.</div>
      <div class="ct-encumbrance-pane__weight"><span class="ct-encumbrance-pane__weight-label">Carrying Capacity:</span>{enc.capacity} lb. (Strength × 15)</div>
      {#if enc.variant}
        <div class="ct-encumbrance-pane__weight"><span class="ct-encumbrance-pane__weight-label">Encumbered over:</span>{str * 5} lb. (speed −10 ft.)</div>
        <div class="ct-encumbrance-pane__weight"><span class="ct-encumbrance-pane__weight-label">Heavily Encumbered over:</span>{str * 10} lb. (speed −20 ft., disadvantage on Strength, Dexterity and Constitution checks, attacks and saves)</div>
      {/if}
      <div class="ct-encumbrance-pane__weight"><span class="ct-encumbrance-pane__weight-label">Status:</span>{enc.disabled ? "Encumbrance off (Home step)" : enc.status ? title(enc.status) : "Unencumbered"}</div>
    {:else if pane.kind === "proficiencies" && sheet}
      {@const customs = current.character.custom_proficiencies || []}
      <div class="ct-proficiencies-pane">
        <header class="ct-sidebar__header"><div></div><div class="ct-sidebar__header-primary"><h1 class="ct-sidebar__heading styles_heading__j5Lvn">Proficiencies &amp; Training</h1></div></header>
        <div class="ct-proficiencies-pane__customs">
          {#each customs as c, i}
            <div class="ddb-custom-prof"><span>{PROF_TYPES[c.type]}: {title(c.name)}</span>
              <button type="button" class="ct-theme-button ct-theme-button--outline ct-theme-button--interactive ct-button character-button ddbc-button character-button-small" onclick={() => { current.character.custom_proficiencies = customs.filter((_, k) => k !== i); changed(); }}><span class="ct-button__content">Remove</span></button></div>
          {/each}
        </div>
        <h2 class="ct-sidebar__subheading">Add New Proficiencies</h2>
        <label class="form_label__nzG8p" for="prof-type">Proficiency Type</label>
        <DdbSelect extraClass="styles_select__SKQCx" placeholder="-- Choose an Option --" searchable={false} value={profType} onchange={(v) => { profType = v; profPick = ""; }}
          options={[["armor", "Armor", "Existing"], ["weapons", "Weapon", "Existing"], ["tools", "Tool", "Existing"], ["languages", "Language", "Existing"], ["custom-tools", "Tool", "Custom"], ["custom-languages", "Language", "Custom"]].map(([value, label, group]) => ({ value, label, group }))} />
        {#if profType}
          <div class="ddb-custom-prof-add">
            {#if profType.startsWith("custom-")}<input type="text" placeholder="Name" bind:value={profPick} aria-label="Custom proficiency name" />
            {:else}<DdbSelect placeholder="-- Choose an Option --" value={profPick} onchange={(v) => (profPick = v)} options={profOptions(profType)} />{/if}
            <button type="button" class="ct-theme-button ct-theme-button--filled ct-theme-button--interactive ct-button character-button ddbc-button character-button-small" disabled={!profPick.trim()}
              onclick={() => { current.character.custom_proficiencies = [...customs, { type: profType.replace("custom-", ""), name: profPick.trim() }]; profPick = ""; changed(); }}><span class="ct-button__content">Add</span></button>
          </div>
        {/if}
        <div class="ct-proficiencies-pane__groups"><ProficiencyGroups /></div>
      </div>
    {:else if pane.kind === "inspiration" && sheet}
      {@const rules = content.ruletexts.find((x) => x.id === "inspiration")}
      {@const on = !!playState.inspiration}
      {@render head("Inspiration", "Player's Handbook, pg. 125")}
      <div class="ct-condition-manage-pane__condition ddb-inspiration-row">
        <div class="ct-condition-manage-pane__condition-name">{on ? "You have inspiration" : "No inspiration"}</div>
        <div class="ct-condition-manage-pane__condition-toggle"><button type="button" class="styles_toggle__nDukS styles_themed__H38P+" aria-pressed={on} aria-label="{on ? 'Spend' : 'Gain'} inspiration"
          onclick={() => { current.character.play.inspiration = !on; changed(100); }}></button></div>
      </div>
      {#if rules}<div class="ddbc-html-content">{@render flatRules(rules.entries)}</div>{/if}
    {:else if pane.kind === "xp" && sheet}
      {@const xp = sheet.xp || { total: Number(current.character.xp) || 0 }}
      {@render head("Manage XP", "Player's Handbook, pg. 15")}
      <div class="ddb-xp-pane">
        <p class="ddb-xp-total"><span>Current XP</span> <strong>{xp.total.toLocaleString("en")}</strong></p>
        {#if xp.next}<p class="ddb-pane-note">Level {sheet.level + 1} at {xp.next.toLocaleString("en")} XP, {(xp.next - xp.total > 0 ? xp.next - xp.total : 0).toLocaleString("en")} to go.</p>{/if}
        {#if xp.level_by_xp > sheet.level}<p class="ddb-pane-note"><strong>Your XP reaches level {xp.level_by_xp}.</strong> Raise a class level in the builder: <a href="#/c/{route.id}/builder/class">Class step</a>.</p>{/if}
        <label class="ddb-xp-change">XP gained or lost <input type="number" min="0" bind:value={xpAmount} /></label>
        <div class="ddb-xp-buttons">
          <button type="button" class="ct-button character-button ddbc-button character-button-small" onclick={() => changeXp(1)}><span class="ct-button__content">Add XP</span></button>
          <button type="button" class="ct-button character-button ddbc-button character-button-small" onclick={() => changeXp(-1)}><span class="ct-button__content">Remove XP</span></button>
        </div>
        <label class="ddb-xp-change">Set total XP <input type="number" min="0" value={xp.total} onchange={(e) => { current.character.xp = Math.max(0, Number(e.target.value) || 0); changed(100); }} /></label>
      </div>
    {:else if pane.kind === "feats" && sheet}
      {@const bonus = current.character.bonus_feats || []}
      {@const q = featQuery.trim().toLowerCase()}
      {@render head("Manage Feats")}
      <p class="ddb-pane-note">Feats from an ability score improvement or a race are chosen in the builder. Add here the ones your DM grants outside those.</p>
      {#each bonus as pick, k}
        {@const feat = content.byId.feats[pick.id]}
        <div class="ddb-bonus-feat">
          <div class="ddb-bonus-feat-head"><strong>{feat?.name || pick.name || pick.id}</strong>
            <button type="button" class="ct-button character-button ddbc-button character-button-small" onclick={() => removeBonusFeat(k)}><span class="ct-button__content">Remove</span></button></div>
          {#if feat}<FeatChoices {pick} />{:else}<p class="ddb-pane-note">Not in the 2014 books; it has no effect here.</p>{/if}
        </div>
      {/each}
      <label class="ddb-xp-change">Add a feat <input type="search" placeholder="Feat name" bind:value={featQuery} /></label>
      {#if q.length >= 2}
        {#each content.feats.filter((f) => f.name.toLowerCase().includes(q) && sourceAllowed(f.book, current.character.preferences)).slice(0, 30) as f}
          <div class="ddb-bonus-feat-head"><span>{f.name} <span class="ddb-pane-note">{book(f.book)}</span></span>
            <button type="button" class="ct-button character-button ddbc-button character-button-small" onclick={() => addBonusFeat(f.id)}><span class="ct-button__content">Add</span></button></div>
        {/each}
      {/if}
    {:else if pane.kind === "history"}
      {@render head("Revert to an Earlier Day")}
      <p class="ddb-pane-note">Anyone at the table may edit a character, so every day with a change is kept. Reverting brings back the character as it was saved at the end of that day (UTC); the revert is itself a change and can be undone the same way.</p>
      {#await api.history(pane.ref)}
        <p class="ddb-pane-note">Loading…</p>
      {:then data}
        {#each data.days as day, k}
          <div class="ddb-bonus-feat-head"><span>{new Date(day + "T12:00:00Z").toLocaleDateString(undefined, { weekday: "short", year: "numeric", month: "short", day: "numeric" })}{k === 0 && day === new Date().toISOString().slice(0, 10) ? " (today, current state)" : ""}</span>
            {#if !(k === 0 && day === new Date().toISOString().slice(0, 10))}
              <button type="button" class="ct-button character-button ddbc-button character-button-small" onclick={async () => {
                if (!confirm(`Revert ${current.character.name} to how it was on ${day}?`)) return;
                try { await api.revert(pane.ref, day); close(); reloadCharacter(); } catch (e) { alert(e.message); }
              }}><span class="ct-button__content">Revert to this day</span></button>
            {/if}
          </div>
        {:else}
          <p class="ddb-pane-note">No earlier days yet: snapshots start with the next change.</p>
        {/each}
      {/await}
    {:else if pane.kind === "skills" && sheet}
      {@const customs = current.character.custom_skills || []}
      {@render head("Skills")}
      <div class="ct-skills-pane__custom">
        <h2 class="ct-sidebar__subheading">Custom Skills</h2>
        <p class="ddb-pane-note">Skills your table made up (DDB's custom skills). The bonus is the ability modifier, the proficiency you pick and the misc bonus.</p>
        <div class="ct-skills-pane__custom-skills">
          {#each customs as c, i}
            {@const derived = sheet.custom_skills?.[i]}
            <div class="ct-skills-pane__proficiency ddb-custom-skill-edit">
              <div class="ct-skills-pane__proficiency-fields">
                <label>Name <input type="text" value={c.name} oninput={(e) => editSkill(i, "name", e.target.value)} /></label>
                <label>Ability <select value={c.ability || ""} onchange={(e) => editSkill(i, "ability", e.target.value || null)}><option value="">None</option>{#each ABILITIES_LIST as a}<option value={a}>{ABILITY_NAMES[a]}</option>{/each}</select></label>
                <label>Proficiency <select value={c.proficiency || ""} onchange={(e) => editSkill(i, "proficiency", e.target.value || null)}><option value="">Not proficient</option><option value="half">Half proficiency</option><option value="proficient">Proficient</option><option value="expertise">Expertise</option></select></label>
                <label>Misc bonus <input type="number" value={c.misc || 0} oninput={(e) => editSkill(i, "misc", Number(e.target.value) || 0)} /></label>
              </div>
              <div class="ct-skills-pane__proficiency-actions">
                <span class="ddb-custom-skill-total">Bonus {signed(derived?.modifier ?? 0)}</span>
                <button type="button" class="ct-theme-button ct-theme-button--outline ct-theme-button--interactive ct-button character-button ddbc-button character-button-small" onclick={() => { current.character.custom_skills = customs.filter((_, k) => k !== i); changed(); }}><span class="ct-button__content">Remove</span></button>
              </div>
            </div>
          {/each}
        </div>
        <button type="button" class="ct-theme-button ct-theme-button--filled ct-theme-button--interactive ct-button character-button ddbc-button character-button-small"
          onclick={() => { current.character.custom_skills = [...customs, { name: "New skill", ability: "int", proficiency: null, misc: 0 }]; changed(); }}><span class="ct-button__content">Add Custom Skill</span></button>
      </div>
    {:else if pane.kind === "inventory" && sheet}
      {@const inv = current.character.inventory || []}
      {@const boxes = inv.filter((x) => x.uid && content.byId.items[x.id]?.containerCapacity)}
      {@const boxUids = new Set(boxes.map((x) => x.uid))}
      {@const weigh = (list) => Math.round(list.reduce((n, x) => n + (Number(content.byId.items[x.id]?.weight ?? x.custom?.weight) || 0) * (Number(x.qty) || 1), 0) * 100) / 100}
      {@const carried = inv.filter((x) => !(x.inside && boxUids.has(x.inside)))}
      <div class="ct-equipment-manage-pane">
        {@render head("Manage Inventory")}
        <div class="ddbc-collapsible ddbc-collapsible--opened">
          <div class="ddbc-collapsible__header"><div class="ddbc-collapsible__header-content"><div class="ddbc-collapsible__header-content-primary"><div class="ddbc-collapsible__heading">Add Items</div></div></div></div>
          <div class="ddbc-collapsible__content">
            <div class="ct-equipment-shop">{@render addItemsList(null)}</div>
            <div class="ddbc-collapsible ct-equipment-manage-pane__custom {customOpen ? 'ddbc-collapsible--opened' : 'ddbc-collapsible--collapsed'} ddbc-collapsible--minimal">
              <div class="ddbc-collapsible__header" role="button" tabindex="0" onclick={() => (customOpen = !customOpen)} onkeydown={(e) => e.key === "Enter" && (customOpen = !customOpen)}>
                <div class="ddbc-collapsible__header-content"><div class="ddbc-collapsible__header-content-primary"><div class="ddbc-collapsible__heading">Add Custom Item</div></div></div>
                <div class="ddbc-collapsible__header-status">{@html ddb.icons[customOpen ? "chevron-up" : "chevron-down"] || ""}</div>
              </div>
              {#if customOpen}
                <div class="ddbc-collapsible__content ddb-custom-item">
                  <label>Name <input type="text" bind:value={customItem.name} /></label>
                  <label>Weight (lb.) <input type="number" min="0" step="0.1" bind:value={customItem.weight} /></label>
                  <label>Quantity <input type="number" min="1" bind:value={customItem.qty} /></label>
                  <button type="button" class="ct-theme-button ct-theme-button--filled ct-theme-button--interactive ct-button character-button ddbc-button character-button-small" disabled={!customItem.name.trim()}
                    onclick={() => { addToInventory({ custom: { name: customItem.name.trim(), weight: Number(customItem.weight) || 0 }, qty: Number(customItem.qty) || 1 }, null); customItem = { name: "", weight: 0, qty: 1 }; }}><span class="ct-button__content">Add</span></button>
                </div>
              {/if}
            </div>
          </div>
        </div>
        <h2 class="ct-sidebar__subheading styles_containerHeading__++AbJ">My Inventory</h2>
        {#each [{ key: "equipment", name: "Equipment", list: carried }, ...boxes.map((b) => ({ key: b.uid, name: content.byId.items[b.id]?.name, list: inv.filter((x) => x.inside === b.uid) }))] as g (g.key)}
          <div class="ddbc-collapsible ddbc-collapsible--collapsed">
            <div class="ddbc-collapsible__header" role="button" tabindex="0" onclick={() => show("container", g.key)} onkeydown={(e) => e.key === "Enter" && show("container", g.key)}>
              <div class="ddbc-collapsible__header-content">
                <div class="ddbc-collapsible__header-content-primary"><div class="ddbc-collapsible__heading">{g.name} ({g.list.length})</div></div>
                <div class="ddbc-collapsible__header-content-callout"><div class="ct-equipment-manage-pane__callout"><span class="styles_numberDisplay__Rg1za"><span>{weigh(g.list)}</span><span class="styles_label__L8mZK styles_labelSignColor__Klmbs">lb.</span></span></div></div>
              </div>
              <div class="ddbc-collapsible__header-status">{@html ddb.icons["chevron-down"] || ""}</div>
            </div>
          </div>
        {/each}
        <div class="ct-equipment-manage-pane__links">
          <div class="ct-equipment-manage-pane__link"><a class="ddbc-link ddbc-theme-link" href={`#/c/${route.id}/builder/equipment`} onclick={close}>Starting Equipment</a></div>
          <div class="ct-equipment-manage-pane__link"><a class="ddbc-link ddbc-theme-link" href={"#"} onclick={(e) => { e.preventDefault(); show("currency", route.id); }}>Currency</a></div>
          <div class="ct-equipment-manage-pane__link"><a class="ddbc-link ddbc-theme-link" href={"#"} onclick={(e) => { e.preventDefault(); show("encumbrance", route.id); }}>Encumbrance</a></div>
        </div>
      </div>
    {:else if pane.kind === "decorate" && sheet}
      {@const d = current.character.description || {}}
      {@const firstClass = current.character.classes?.[0]?.id}
      {@const backdropKey = d.backdrop || firstClass}
      {@const backdropImg = (key) => `${window.DND5E.ddb}/img/backdrops/${key}.jpg`}
      {@const setLook = (key, value) => { (current.character.description ??= {})[key] = value; changed(400); }}
      <div class="ct-decorate-pane">
        <div class="ct-decorate-pane__current-selections">
          {@render head("Current Decorations")}
          <div class="ct-decorate-pane__grid">
            <div class="ct-decorate-pane__grid-item"><div class="ct-decorate-pane__grid-item-label">Portrait</div>
              <div class="ct-decorate-pane__grid-item-inner"><div class="ddbc-character-avatar__portrait ct-decorate-pane__portrait {d.avatar_url ? '' : 'ct-decorate-pane__portrait--none ddbc-character-avatar__portrait--none'}" style={d.avatar_url ? `background-image:url("${d.avatar_url}")` : ""}></div></div></div>
            <div class="ct-decorate-pane__grid-item"><div class="ct-decorate-pane__grid-item-label">Theme</div>
              <div class="ct-decorate-pane__grid-item-inner"><div class="ct-decorate-pane__theme"><div class="ddb-theme-swatch" style="background:{d.theme || '#c53131'}"></div><div class="ct-decorate-pane__theme-color">{d.theme || "#c53131"}</div></div></div></div>
            <div class="ct-decorate-pane__grid-item"><div class="ct-decorate-pane__grid-item-label">Backdrop</div>
              <div class="ct-decorate-pane__grid-item-inner">{#if d.backdrop_url || BACKDROPS.includes(backdropKey)}<img class="ct-decoration-manager__item-img" alt="Current backdrop" src={d.backdrop_url || backdropImg(backdropKey)} />{:else}None{/if}</div></div>
          </div>
        </div>
        <div class="ct-decorate-pane__shop">
          <h2 class="ct-sidebar__subheading">Browse Decorations</h2>
          {#each [["backdrops", "Backdrops"], ["themes", "Themes"], ["portraits", "Portraits"]] as [key, label]}
            <div class="ddbc-collapsible {decorOpen === key ? 'ddbc-collapsible--opened' : 'ddbc-collapsible--collapsed'}">
              <div class="ddbc-collapsible__header" role="button" tabindex="0" onclick={() => (decorOpen = decorOpen === key ? null : key)} onkeydown={(e) => e.key === "Enter" && (decorOpen = decorOpen === key ? null : key)}>
                <div class="ddbc-collapsible__header-content"><div class="ddbc-collapsible__header-content-primary"><div class="ddbc-collapsible__heading">{label}</div></div></div>
                <div class="ddbc-collapsible__header-status">{@html ddb.icons[decorOpen === key ? "chevron-up" : "chevron-down"] || ""}</div>
              </div>
              {#if decorOpen === key}
                <div class="ddbc-collapsible__content"><div class="ct-decoration-manager">
                  {#if key === "backdrops"}
                    <div class="ct-decoration-manager__group"><h2 class="ct-sidebar__subheading">Default</h2><div class="ct-decoration-manager__list">
                      <div class="ct-decoration-manager__item" class:ct-decoration-manager__item--current={!d.backdrop && !d.backdrop_url} role="button" tabindex="0" onclick={() => { setLook("backdrop", null); setLook("backdrop_url", null); }} onkeydown={(e) => e.key === "Enter" && setLook("backdrop", null)}>
                        <div class="ct-decoration-manager__item-inner">{#if BACKDROPS.includes(firstClass)}<img class="ct-decoration-manager__item-img" alt="" src={backdropImg(firstClass)} />{/if}</div><div class="ct-decoration-manager__item-label">First class</div></div>
                    </div></div>
                    <div class="ct-decoration-manager__group"><h2 class="ct-sidebar__subheading">Class Backdrops</h2><div class="ct-decoration-manager__list">
                      {#each BACKDROPS as b}
                        <div class="ct-decoration-manager__item" class:ct-decoration-manager__item--current={d.backdrop === b && !d.backdrop_url} role="button" tabindex="0" onclick={() => { setLook("backdrop", b); setLook("backdrop_url", null); }} onkeydown={(e) => e.key === "Enter" && setLook("backdrop", b)}>
                          <div class="ct-decoration-manager__item-inner ct-decoration-manager__item-img"><img class="ct-decoration-manager__item-img" alt="{title(b)} backdrop preview" loading="lazy" src={backdropImg(b)} /></div><div class="ct-decoration-manager__item-label">{title(b)}</div></div>
                      {/each}
                    </div></div>
                  {:else if key === "themes"}
                    <label class="ddb-decor-field">Sheet colour (frames and accents) <input type="color" value={d.theme || "#c53131"} oninput={(e) => setLook("theme", e.target.value)} /></label>
                  {:else}
                    <label class="ddb-decor-field">Portrait image URL <input type="url" placeholder="https://…" value={d.avatar_url || ""} oninput={(e) => setLook("avatar_url", e.target.value || null)} /></label>
                  {/if}
                </div></div>
              {/if}
            </div>
          {/each}
        </div>
      </div>
    {:else if pane.kind === "container" && sheet}
      {@const inv = current.character.inventory || []}
      {@const box = pane.ref === "equipment" ? null : inv.find((x) => x.uid === pane.ref)}
      {@const boxUids = new Set(inv.filter((x) => x.uid && content.byId.items[x.id]?.containerCapacity).map((x) => x.uid))}
      {@const inside = inv.map((slot, k) => ({ slot, k, item: content.byId.items[slot.id] })).filter((r) => (box ? r.slot.inside === box.uid : !(r.slot.inside && boxUids.has(r.slot.inside))))}
      {@const weight = inside.reduce((n, r) => n + (Number(r.item?.weight ?? r.slot.custom?.weight) || 0) * (Number(r.slot.qty) || 1), 0)}
      <div class="ct-container-pane">
        {@render head(box ? content.byId.items[box.id]?.name : "Equipment")}
        {#if box}
          <div class="ddb-custom-grid" aria-label="Coins in this container">
            <strong>Coins in here</strong>
            {#each ["pp", "gp", "ep", "sp", "cp"] as c}
              <label>{c} <input type="number" min="0" value={box.coins?.[c] || ""} oninput={(e) => { box.coins = { ...(box.coins || {}), [c]: Math.max(0, Number(e.target.value) || 0) }; changed(500); }} /></label>
            {/each}
          </div>
        {/if}
        <div class="ct-container-manager">
          <div class="ddbc-collapsible {addOpen ? 'ddbc-collapsible--opened' : 'ddbc-collapsible--collapsed'}">
            <div class="ddbc-collapsible__header" role="button" tabindex="0" onclick={() => (addOpen = !addOpen)} onkeydown={(e) => e.key === "Enter" && (addOpen = !addOpen)}>
              <div class="ddbc-collapsible__header-content"><div class="ddbc-collapsible__header-content-primary"><div class="ddbc-collapsible__heading">Add Items</div></div></div>
              <div class="ddbc-collapsible__header-status">{@html ddb.icons[addOpen ? "chevron-up" : "chevron-down"] || ""}</div>
            </div>
            {#if addOpen}
              {@render addItemsList(box?.uid)}
            {/if}
          </div>
          <div class="ddbc-collapsible ddbc-collapsible--opened">
            <div class="ddbc-collapsible__header">
              <div class="ddbc-collapsible__header-content">
                <div class="ddbc-collapsible__header-content-primary"><div class="ddbc-collapsible__heading">Contents ({inside.length})</div></div>
                <div class="ddbc-collapsible__header-content-callout"><div class="ct-equipment-manage-pane__callout"><span class="styles_numberDisplay__Rg1za"><span>{Math.round(weight * 100) / 100}</span><span class="styles_label__L8mZK styles_labelSignColor__Klmbs">lb.</span></span></div></div>
              </div>
            </div>
            <div class="ddbc-collapsible__content"><div class="ct-container-manager__inventory">
              {#each inside as r (r.k)}
                <div class="ddbc-collapsible ct-container-manager__item ddbc-collapsible--collapsed ddbc-collapsible--minimal">
                  <div class="ddbc-collapsible__header" role="button" tabindex="0" onclick={() => r.item && show("item", r.item.id, { slot: r.k })} onkeydown={(e) => e.key === "Enter" && r.item && show("item", r.item.id, { slot: r.k })}>
                    <div class="ddbc-collapsible__header-content"><div class="ddbc-collapsible__header-content-primary"><div class="ct-container-manager__item-header">
                      <div class="ct-container-manager__item-header-action"><div class="ct-item-slot-manager">{(r.slot.qty || 1) > 1 ? `${r.slot.qty}×` : ""}</div></div>
                      <div class="ct-container-manager__item-header-name"><span class="styles_itemName__xLCwW styles_common__4urYa">{r.slot.custom_name || r.item?.name || r.slot.custom?.name || "Item"}</span></div>
                    </div></div></div>
                    <div class="ddbc-collapsible__header-status">{@html ddb.icons["chevron-down"] || ""}</div>
                  </div>
                </div>
              {/each}
            </div></div>
          </div>
        </div>
        <div class="ct-container-pane__links">
          <div class="ct-container-pane__link"><a class="ddbc-link ddbc-theme-link" href={`#/c/${route.id}/builder/equipment`} onclick={close}>Manage Inventory</a></div>
          <div class="ct-container-pane__link"><a class="ddbc-link ddbc-theme-link" href={`#/c/${route.id}/builder/equipment`} onclick={close}>Starting Equipment</a></div>
        </div>
      </div>
    {:else if pane.kind === "campaigns"}
      {@render head("Campaigns", "Which campaigns this character plays in")}
      <Campaigns characterId={pane.ref} compact />
    {:else if pane.kind === "ac" && sheet}
      {@const rules = content.ruletexts.find((x) => x.id === "ac")}
      <div>
        <header class="ct-sidebar__header"><div></div><div class="ct-sidebar__header-primary"><h1 class="ct-sidebar__heading styles_heading__j5Lvn">Armor Class: {sheet.armor_class.value}</h1></div></header>
        <div class="styles_items__rtrOH">
          {#each sheet.armor_class.parts || [] as [label, value, source], i}
            <div class="styles_item__SQmPn">
              <div class="styles_value__ZbR1s">{#if i === 0}{value}{:else}<span class="styles_numberDisplay__Rg1za styles_signed__scf97"><span class="styles_sign__NdR6X styles_labelSignColor__Klmbs">{value < 0 ? "-" : "+"}</span><span>{Math.abs(value)}</span></span>{/if}</div>
              <div class="styles_label__usGSs"><span>{label}</span>{#if source}<span class="styles_source__oZAaC">(<span class="styles_itemName__xLCwW styles_common__4urYa">{source}</span>)</span>{/if}</div>
            </div>
          {/each}
        </div>
        <details class="styles_details__Kwqwr styles_x-small__Npa2g styles_minimal__5BWb- styles_themed__tXh-0 styles_customize__JoJhJ">
          <summary class="styles_summary__BI+UG"><div class="styles_heading__RRl69"><div class="styles_summaryContent__xaQWq">Customize</div><div class="styles_actions__1-sml"></div>{@html ddb.icons["details-chevron"] || ""}</div></summary>
          <div class="styles_content__pFYp6"><div class="ct-editor-box styles_editorBox__mCHv-"><div class="ct-value-editor ct-value-editor--standard">
            {#each [["ac", "Override AC", 1], ["ac_bonus", "Additional Misc Bonus", 3]] as [key, label, n]}
              <div class="ct-value-editor__property--number ct-value-editor__property ct-value-editor__property--{n}">
                <div class="ct-value-editor__property-label">{label}</div>
                <div class="ct-value-editor__property-value"><input class="ct-value-editor__property-input" type="number" aria-label={label} value={current.character.overrides?.[key] ?? ""} oninput={(e) => setOverride(key, e.target.value)} /></div>
              </div>
            {/each}
          </div></div></div>
        </details>
        {#if rules}<div class="ddbc-html-content styles_description__iRcZV">{@render flatRules(rules.entries)}</div>{/if}
      </div>
    {:else}
      <p>Nothing to show.</p>
    {/if}
    {#if explainEntry}{#key pane.kind + pane.ref}<AskBox entry={explainEntry} />{/key}{/if}
{/snippet}

{#if pane.open}
  {#if route.view === "sheet"}
    <div class="ct-sidebar__portal">
      <div class="swipeable">
        <div role="dialog" aria-label="Information Sidebar" class="ct-sidebar styles_sidebar__RrEHr styles_{side}__e4y1G styles_visible__6s+G- ddb-sidebar-{side}" style={side === "right" ? "left: auto; right: 0px;" : "left: 0px; right: auto;"}>
          <div class="ct-sidebar__inner">
            <div class="ddb-sidebar-controls" role="toolbar" tabindex="-1" onclick={sidebarControl} onkeydown={(e) => e.key === "Enter" && sidebarControl(e)}>{@html (ddb.sidebar?.controls || "")}</div>
            <div class="styles_pane__AOt0h">
              {@html (ddb.sidebar?.border || "")}
              <div class="styles_gap__kuwYv"></div>
              <div class="styles_content__3knKz">
                <div class="styles_wrapper__6NpOy">
                  {#if pane.stack.length}<button type="button" class="ddb-pane-back" onclick={back}>&larr; Back</button>{/if}
                  {@render paneBody()}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  {:else}
    <aside class="pane" aria-label="Details">
      <div class="pane-bar">
        {#if pane.stack.length}<button type="button" class="link" onclick={back}>&larr; Back</button>{/if}
        <span class="grow"></span>
        <button type="button" class="link" onclick={close} aria-label="Close details">Close &times;</button>
      </div>
      {@render paneBody()}
    </aside>
  {/if}
{/if}
