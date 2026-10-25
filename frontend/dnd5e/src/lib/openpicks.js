// Picks still unmade inside a feat or a race's spells, for DDB's "!" on builder cards. The spell-slot walk
// is the same as character.py's spell_slots_of(), so the keys match what GrantedSpells stores.
import { SKILLS } from "./format.js";

const USAGE = { daily: "{n}/long rest", rest: "{n}/short rest", will: "at will", ritual: "ritual only" };

export function* spellSlotsOf(block) {
  for (const kind of ["innate", "known"]) {
    for (const [levelKey, body] of Object.entries(block?.[kind] || {})) {
      const needs = levelKey === "_" ? 0 : Number(levelKey.replace(/\D/g, "")) || 0;
      const groups = Array.isArray(body) ? [["_", body]] : Object.entries(body);
      for (const [freq, value] of groups) {
        const parts = value && !Array.isArray(value) && typeof value === "object"
          ? Object.entries(value).map(([n, v]) => [(USAGE[freq] || "{n}").replace("{n}", n.replace(/\D/g, "") || n), v])
          : [[USAGE[freq] || (kind === "known" ? "known" : "at will"), value]];
        for (const [usage, entries] of parts) {
          const list = Array.isArray(entries) ? entries : [entries];
          for (let i = 0; i < list.length; i++) yield { kind, needs, usage, entry: list[i], key: `${kind}|${levelKey}|${freq}|${usage}|${i}` };
        }
      }
    }
  }
}

const choiceCount = (entry) => (typeof entry.choose === "object" ? entry.choose.count : null) || entry.count || 1;

export function spellsOpen(blocks, pick, level) {
  if (!blocks?.length) return 0;
  if (blocks.length > 1 && pick.spell_block === undefined) return 1;
  const block = blocks[Math.min(Number(pick.spell_block) || 0, blocks.length - 1)];
  let open = block?.ability?.choose && !pick.spell_ability ? 1 : 0;
  for (const slot of spellSlotsOf(block)) {
    if (slot.needs > level || !(slot.entry && typeof slot.entry === "object" && "choose" in slot.entry)) continue;
    open += Math.max(0, choiceCount(slot.entry) - ((pick.spell_picks || {})[slot.key] || []).length);
  }
  return open;
}

function freeCount(blocks) {
  let n = 0;
  for (const [k, v] of Object.entries(blocks?.[0] || {})) {
    if (k === "choose") n += v.count || 1;
    else if (k.startsWith("any") && typeof v === "number" && k !== "anyProficientSkill") n += v;
  }
  return n;
}

export function featOpen(feat, pick, level) {
  if (!feat || !pick) return 0;
  const missing = (want, have) => Math.max(0, want - (have || []).filter(Boolean).length);
  let open = 0;
  const ability = feat.ability?.[0]?.choose;
  if (ability) open += missing(ability.count || 1, pick.ability_choices);
  open += missing(freeCount(feat.skillProficiencies), (pick.skills || []).filter((s) => SKILLS[s]));
  open += missing(freeCount(feat.toolProficiencies), pick.tools);
  open += missing(freeCount(feat.languageProficiencies), pick.languages);
  open += missing((feat.skillToolLanguageProficiencies?.[0]?.choose || []).reduce((n, c) => n + (c.count || 1), 0), pick.skill_tool);
  open += missing(feat.expertise?.[0]?.anyProficientSkill || 0, pick.expertise);
  const options = (feat.optionalfeatureProgression || []).reduce((n, p) => n + Object.values(p.progression || {}).reduce((m, v) => m + (typeof v === "number" ? v : 0), 0), 0);
  open += missing(options, pick.optionalfeatures);
  open += spellsOpen(feat.additionalSpells, pick, level);
  return open;
}
