<script>
  // Picks for the spells a race or feat grants (5etools additionalSpells), as DDB choice dropdowns:
  // which block (Magic Initiate's class), which casting ability, and every "choose" slot. Slots are
  // walked in the same order and stored under the same keys as character.py's spell_slots_of().
  import DdbSelect from "./DdbSelect.svelte";
  import { content } from "../lib/content.svelte.js";
  import { changed } from "../lib/character.svelte.js";
  import { ABILITY_NAMES, ordinal } from "../lib/format.js";
  import { spellSlotsOf } from "../lib/openpicks.js";

  let { blocks = [], pick, level = 1 } = $props();
  const block = $derived(blocks[Math.min(Number(pick.spell_block) || 0, blocks.length - 1)]);

  // "level=1|class=druid;wizard|school=E;D" or {from: [...], count}
  function candidates(choose) {
    if (typeof choose === "object") {
      const names = new Set((choose.from || []).map((n) => n.split("|")[0].toLowerCase()));
      return content.spells.filter((s) => names.has(s.name.toLowerCase()));
    }
    const rules = Object.fromEntries(choose.split("|").map((part) => part.split("=")).map(([k, v]) => [k, v.split(";").map((x) => x.toLowerCase())]));
    return content.spells.filter((s) => (!rules.level || rules.level.includes(String(s.level)))
      && (!rules.class || (s.classes || []).some((c) => rules.class.includes(c.toLowerCase())))
      && (!rules.school || rules.school.includes(String(s.school).toLowerCase())));
  }
  const slots = $derived([...spellSlotsOf(block)].filter((s) => s.entry && typeof s.entry === "object" && "choose" in s.entry)
    .map((s) => ({ ...s, count: (typeof s.entry.choose === "object" ? s.entry.choose.count : null) || s.entry.count || 1,
      options: candidates(s.entry.choose).map((sp) => ({ value: sp.id, label: sp.name })) })));
  const fixed = $derived([...spellSlotsOf(block)].filter((s) => typeof s.entry === "string"));
  const abilityChoice = $derived(block?.ability?.choose);

  function setSlot(key, k, value) {
    const list = [...((pick.spell_picks || {})[key] || [])];
    if (value) list[k] = value;
    else list.splice(k, 1);
    pick.spell_picks = { ...(pick.spell_picks || {}), [key]: list.filter(Boolean) };
    changed();
  }
  const spellName = (entry) => entry.split("#")[0].split("|")[0].replace(/\b\w/g, (c) => c.toUpperCase());
</script>

{#snippet choice(placeholder, value, options, onchange)}
  <div class="styles_choice__qE4aQ"><div class="detail-choice {value ? '' : 'detail-choice--todo'}">
    <DdbSelect highlight {placeholder} {value} {options} {onchange} />
  </div></div>
{/snippet}

{#if blocks.length}
  {#if blocks.length > 1}
    {@render choice("- Choose a Spell List -", pick.spell_block === undefined ? "" : String(pick.spell_block),
      blocks.map((b, k) => ({ value: String(k), label: b.name || `Option ${k + 1}` })),
      (v) => { pick.spell_block = v === "" ? undefined : Number(v); pick.spell_picks = {}; changed(); })}
  {/if}
  {#if abilityChoice}
    {@render choice("- Choose a Spellcasting Ability -", pick.spell_ability || "",
      abilityChoice.map((a) => ({ value: a, label: ABILITY_NAMES[a] })), (v) => { pick.spell_ability = v || undefined; changed(); })}
  {/if}
  {#if blocks.length === 1 || pick.spell_block !== undefined}
    {#each slots as slot (slot.key)}
      {#each Array.from({ length: slot.count }, (_, k) => k) as k}
        {@render choice(`- Choose a Spell (${slot.usage}${slot.needs > level ? `, from ${ordinal(slot.needs)}` : ""}) -`,
          ((pick.spell_picks || {})[slot.key] || [])[k] || "", slot.options, (v) => setSlot(slot.key, k, v))}
      {/each}
    {/each}
    {#if fixed.length}
      <p class="ddb-granted-fixed">Also granted: {fixed.map((s) => `${spellName(s.entry)} (${s.usage}${s.needs ? `, from ${ordinal(s.needs)}` : ""})`).join(", ")}</p>
    {/if}
  {/if}
{/if}
