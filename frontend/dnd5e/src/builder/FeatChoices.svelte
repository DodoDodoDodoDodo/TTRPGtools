<script>
  // The picks a feat asks for, as DDB choice dropdowns: ability increase, skills, tools, languages,
  // Skilled's skill-or-tool picks, expertise. `pick` is the stored feat object ({id, ability_choices, ...}).
  import DdbSelect from "./DdbSelect.svelte";
  import GrantedSpells from "./GrantedSpells.svelte";
  import { content } from "../lib/content.svelte.js";
  import { current, changed } from "../lib/character.svelte.js";
  import { ABILITIES, ABILITY_NAMES, SKILLS, TOOLS, ARTISAN_TOOLS, title, plain } from "../lib/format.js";

  let { pick } = $props();
  const feat = $derived(content.byId.feats[pick?.id]);

  function setPick(list, k, value) {
    const next = [...(list || [])];
    if (value) next[k] = value;
    else next.splice(k, 1);
    return next.filter(Boolean);
  }
  const without = (all, chosen, mine) => all.filter((o) => o.value === mine || !(chosen || []).includes(o.value));
  const range = (n) => Array.from({ length: n }, (_, k) => k);
  // count and candidate list of a 5etools proficiency block ({choose: {from, count}} or {any: n} / {anyArtisansTool: n})
  function freePicks(blocks, universe) {
    const block = blocks?.[0];
    if (!block) return { count: 0, from: universe };
    let count = 0, from = universe;
    for (const [k, v] of Object.entries(block)) {
      if (k === "choose") { count += v.count || 1; from = v.from.map((x) => plain(x)); }
      else if (k === "anyArtisansTool") { count += v; from = ARTISAN_TOOLS; }
      else if (k.startsWith("any") && typeof v === "number" && k !== "anyProficientSkill") count += v;
    }
    return { count, from };
  }
  const languages = $derived([...new Map(content.languages.filter((l) => l.type === "standard" || l.type === "exotic").map((l) => [l.name.toLowerCase(), l.name])).entries()]);
  const proficientSkills = $derived(Object.entries(current.sheet?.skills || {})
    .filter(([, v]) => v.proficiency === "proficient" || v.proficiency === "expertise").map(([s]) => s));

  const abilityChoice = $derived(feat?.ability?.[0]?.choose);
  const skills = $derived(freePicks(feat?.skillProficiencies, Object.keys(SKILLS)));
  const tools = $derived(freePicks(feat?.toolProficiencies, TOOLS));
  const langs = $derived(freePicks(feat?.languageProficiencies, languages.map(([id]) => id)));
  const skillTool = $derived((feat?.skillToolLanguageProficiencies?.[0]?.choose || []).reduce((n, c) => n + (c.count || 1), 0));
  const expertise = $derived((feat?.expertise?.[0]?.anyProficientSkill) || 0);
  const characterLevel = $derived((current.character.classes || []).reduce((n, c) => n + (Number(c.level) || 1), 0));
  // Eldritch Adept (TCE p. 79): a non-warlock may only take invocations without prerequisites.
  const isWarlock = $derived((current.character.classes || []).some((c) => c.id === "warlock"));
  const progressions = $derived((feat?.optionalfeatureProgression || []).map((p) => ({
    name: p.name,
    count: Object.values(p.progression || {}).reduce((n, v) => n + (typeof v === "number" ? v : 0), 0),
    options: content.optionalfeatures
      .filter((o) => (o.featureType || []).some((t) => p.featureType.includes(t)))
      .filter((o) => !(p.featureType.includes("EI") && !isWarlock && o.prerequisite))
      .map((o) => ({ value: o.id, label: o.name.replace(/'/g, "\u2019") })),
  })));
  // all of a feat's optional features share one list; each progression owns the ids of its types
  const mineOf = (p) => (pick.optionalfeatures || []).filter((id) => p.options.some((o) => o.value === id));
  function setOption(p, k, value) {
    const mine = mineOf(p);
    const others = (pick.optionalfeatures || []).filter((id) => !mine.includes(id));
    pick.optionalfeatures = [...others, ...setPick(mine, k, value)];
    changed();
  }

  const set = (key, k, value) => { pick[key] = setPick(pick[key], k, value); changed(); };
  const skillTools = $derived([...Object.keys(SKILLS).map((s) => ({ value: `skill:${s}`, label: title(s), group: "Skills" })),
    ...TOOLS.map((t) => ({ value: `tool:${t}`, label: title(t), group: "Tools" }))]);
</script>

{#snippet choice(placeholder, value, options, onchange)}
  <div class="styles_choice__qE4aQ"><div class="detail-choice {value ? '' : 'detail-choice--todo'}">
    <DdbSelect highlight {placeholder} {value} {options} {onchange} />
  </div></div>
{/snippet}

{#if feat}
  {#if abilityChoice}
    {#each range(abilityChoice.count || 1) as k}
      {@render choice("- Choose an Ability Score -", (pick.ability_choices || [])[k] || "",
        without((abilityChoice.from || ABILITIES).map((a) => ({ value: a, label: ABILITY_NAMES[a] })), pick.ability_choices, (pick.ability_choices || [])[k]),
        (v) => set("ability_choices", k, v))}
    {/each}
  {/if}
  {#each range(skills.count) as k}
    {@render choice("- Choose a Skill -", (pick.skills || [])[k] || "",
      without(skills.from.filter((s) => SKILLS[s]).map((s) => ({ value: s, label: title(s) })), pick.skills, (pick.skills || [])[k]), (v) => set("skills", k, v))}
  {/each}
  {#each range(tools.count) as k}
    {@render choice("- Choose a Tool -", (pick.tools || [])[k] || "",
      without(tools.from.map((t) => ({ value: t, label: title(t) })), pick.tools, (pick.tools || [])[k]), (v) => set("tools", k, v))}
  {/each}
  {#each range(langs.count) as k}
    {@render choice("- Choose a Language -", (pick.languages || [])[k] || "",
      without(languages.map(([id, name]) => ({ value: id, label: name })), pick.languages, (pick.languages || [])[k]), (v) => set("languages", k, v))}
  {/each}
  {#each range(skillTool) as k}
    {@render choice("- Choose a Skill or Tool -", (pick.skill_tool || [])[k] || "",
      without(skillTools, pick.skill_tool, (pick.skill_tool || [])[k]), (v) => set("skill_tool", k, v))}
  {/each}
  {#each range(expertise) as k}
    {@render choice("- Choose a Skill for Expertise -", (pick.expertise || [])[k] || "",
      proficientSkills.map((s) => ({ value: s, label: title(s) })), (v) => set("expertise", k, v))}
  {/each}
  {#each progressions as p}
    {#each range(p.count) as k}
      {@render choice(`- Choose ${"AEIOU".includes(p.name[0]) ? "an" : "a"} ${p.name.replace(/s$/, "")} -`, mineOf(p)[k] || "",
        without(p.options, mineOf(p), mineOf(p)[k]), (v) => setOption(p, k, v))}
    {/each}
  {/each}
  {#if feat.name === "Elemental Adept"}
    {@render choice("- Choose a Damage Type -", pick.damage_type || "", ["acid", "cold", "fire", "lightning", "thunder"].map((t) => ({ value: t, label: title(t) })),
      (v) => { pick.damage_type = v || undefined; changed(); })}
  {/if}
  {#if feat.additionalSpells}<GrantedSpells blocks={feat.additionalSpells} {pick} level={characterLevel} />{/if}
{/if}
