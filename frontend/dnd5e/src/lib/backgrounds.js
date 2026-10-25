// How the builder names and lists backgrounds, shared by the Background step and the newer builder's start page.
import { content, sourceAllowed } from "./content.svelte.js";
import { SKILLS, title } from "./format.js";

// DDB's names for the book variants: three folded into their base, three under their own name, Retainers dropped.
const MERGED = { Criminal: "Spy", "Guild Artisan": "Guild Merchant", "City Watch": "Investigator" };
export const HIDDEN = new Set(["Variant Noble (Retainers)", ...Object.entries(MERGED).map(([base, v]) => `Variant ${base} (${v})`)]);

export function ddbName(name) {
  if (MERGED[name]) return `${name} / ${MERGED[name]}`;
  const variant = name.match(/^Variant .+ \((.+)\)$/);
  return (variant ? variant[1] : name).replace(/'/g, "’");
}

// New-design cards: one per background, the line under the name gives its skills and its feature
export function backgroundCardGroups(preferences) {
  return content.backgrounds
    .filter((b) => !HIDDEN.has(b.name) && sourceAllowed(b.book, preferences))
    .map((b) => {
      const skills = Object.keys((b.skillProficiencies || [])[0] || {}).filter((k) => SKILLS[k]).map(title);
      const feature = (b.entries || []).find((e) => e?.data?.isFeature)?.name?.replace(/^Feature: /, "");
      return { name: ddbName(b.name), items: [{ id: b.id, name: ddbName(b.name), book: b.book }], book: b.book,
        blurb: [skills.length ? `Skills: ${skills.join(", ")}` : null, feature ? `Feature: ${feature}` : null].filter(Boolean).join(" · ") };
    })
    .sort((a, b) => (a.book === "phb" ? 0 : 1) - (b.book === "phb" ? 0 : 1) || a.name.localeCompare(b.name));
}
