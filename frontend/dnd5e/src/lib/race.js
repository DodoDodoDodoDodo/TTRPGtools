import { ABILITIES, ABILITY_NAMES } from "./format.js";

// The book's sentence for a 5etools race ability block: "Your Intelligence score increases by 2."
export function abilitySentence(block) {
  const parts = Object.entries(block || {}).filter(([k]) => ABILITIES.includes(k)).map(([k, v]) => `Your ${ABILITY_NAMES[k]} score increases by ${v}.`);
  const ch = block?.choose;
  if (ch?.weighted) parts.push(`${ch.weighted.weights.map((w, k) => `${k ? "another" : "one"} ability score of your choice increases by ${w}`).join(", and ").replace(/^o/, "O")}.`);
  else if (ch) parts.push(`${ch.count > 1 ? `${ch.count} different ability scores` : "One ability score"} of your choice ${ch.count > 1 ? "increase" : "increases"} by ${ch.amount || 1}${ch.from?.length < 6 ? ` (${ch.from.map((a) => ABILITY_NAMES[a]).join(", ")})` : ""}.`);
  return parts.join(" ");
}

// Tasha's Customizing Your Origin (TCE p. 8), as character.py origin_blocks: a block's increases go to abilities of choice
const SIX = ["str", "dex", "con", "int", "wis", "cha"];
export function originBlocks(blocks, on) {
  if (!on || !blocks) return blocks;
  return blocks.map((block) => {
    const weights = Object.entries(block).filter(([k, v]) => SIX.includes(k) && typeof v === "number").map(([, v]) => v);
    const ch = block.choose;
    if (ch?.weighted) weights.push(...ch.weighted.weights);
    else if (ch) weights.push(...Array(ch.count || 1).fill(ch.amount || 1));
    return weights.length ? { choose: { weighted: { from: SIX, weights: weights.sort((a, b) => b - a) } } } : block;
  });
}
