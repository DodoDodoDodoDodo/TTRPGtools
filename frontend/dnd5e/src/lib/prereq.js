// Prerequisite checks for the builder (Home step "Use Prerequisites"): multiclassing (PHB p. 163) and
// feats (5etools `prerequisite`: a list of alternatives, each an object whose keys must all hold).
// Each check returns the unmet requirement in words, or "" when it is met.
import { ABILITY_NAMES } from "./format.js";

const score = (sheet, a) => sheet?.abilities?.[a]?.score ?? 10;
const needs = (a, v) => `${ABILITY_NAMES[a]} ${v}`;

// 5etools multiclassing.requirements: {"int": 13} (all) or {"or": [{"str": 13, "dex": 13}]} (any one)
export function classRequirement(cls, sheet) {
  const req = cls?.multiclassing?.requirements || {};
  const all = Object.entries(req).filter(([a]) => a !== "or");
  const any = (req.or || []).flatMap((alt) => Object.entries(alt));
  const missing = all.filter(([a, v]) => score(sheet, a) < v).map(([a, v]) => needs(a, v));
  if (any.length && !any.some(([a, v]) => score(sheet, a) >= v)) missing.push(any.map(([a, v]) => needs(a, v)).join(" or "));
  return missing.join(", ");
}

// Taking a new class needs the minimum scores of the new class and of every class already taken.
export function multiclassBlock(cls, entries, classesById, sheet) {
  if (!entries.length) return "";
  const own = classRequirement(cls, sheet);
  if (own) return `needs ${own}`;
  const current = entries.map((e) => classesById[e.id]).find((c) => c && classRequirement(c, sheet));
  return current ? `your ${current.name} needs ${classRequirement(current, sheet)}` : "";
}

function featNames(sheet) {
  return new Set((sheet?.features || []).filter((f) => f.origin === "Feat").map((f) => f.name.toLowerCase()));
}

function unmet(part, ctx) {
  const { sheet, character, level } = ctx;
  const out = [];
  for (const [key, value] of Object.entries(part)) {
    if (key === "level") {
      const lv = typeof value === "object" ? value.level : value;
      const cls = typeof value === "object" ? value.class?.name : null;
      const have = cls ? (sheet?.classes || []).find((c) => c.name === cls)?.level || 0 : level;
      if (have < lv) out.push(`${cls ? `${cls} ` : ""}level ${lv}`);
    } else if (key === "ability") {
      if (!value.some((alt) => Object.entries(alt).every(([a, v]) => score(sheet, a) >= v)))
        out.push(value.map((alt) => Object.entries(alt).map(([a, v]) => needs(a, v)).join(" and ")).join(" or "));
    } else if (key === "race") {
      const race = (sheet?.race || "").toLowerCase();
      if (!value.some((r) => race.startsWith(r.name.toLowerCase()) && (!r.subrace || race.includes(r.subrace.toLowerCase()))))
        out.push(value.map((r) => r.displayEntry?.replace(/\{@\w+ ([^|}]+)[^}]*\}/g, "$1") || `${r.name}${r.subrace ? ` (${r.subrace})` : ""}`).join(" or "));
    } else if (key === "spellcasting" || key === "spellcasting2020" || key === "spellcastingFeature") {
      const casts = (sheet?.spellcasting?.casters || []).length || (key !== "spellcastingFeature" && (sheet?.spellcasting?.granted || []).length);
      if (!casts) out.push(key === "spellcastingFeature" ? "the Spellcasting or Pact Magic feature" : "the ability to cast at least one spell");
    } else if (key === "proficiency") {
      const profs = sheet?.proficiencies || {};
      if (!value.some((p) => Object.entries(p).every(([kind, what]) => (profs[kind === "weapon" ? "weapons" : kind] || []).some((x) => x.toLowerCase().includes(what)))))
        out.push(value.map((p) => Object.entries(p).map(([kind, what]) => `${what} ${kind} proficiency`).join(" and ")).join(" or "));
    } else if (key === "feat") {
      const have = featNames(sheet);
      if (!value.some((f) => have.has(f.split("|")[0].toLowerCase()))) out.push(value.map((f) => (f.split("|")[2] || f.split("|")[0])).join(" or "));
    } else if (key === "pact") {
      // Eldritch Invocations (PHB p. 110): the Pact Boon chosen at warlock level 3
      const names = new Set((sheet?.features || []).map((f) => f.name.toLowerCase()));
      if (!names.has(`pact of the ${String(value).toLowerCase()}`)) out.push(`Pact of the ${value}`);
    } else if (key === "spell") {
      const known = new Set((sheet?.spellcasting?.casters || []).flatMap((c) => c.list.map((sp) => sp.name.toLowerCase())));
      if (!value.some((sp) => known.has(sp.split("#")[0].split("|")[0].toLowerCase())))
        out.push(value.map((sp) => sp.split("#")[0].split("|")[0].replace(/\b\w/g, (ch) => ch.toUpperCase())).join(" or ") + " known");
    } else if (key === "background") {
      const bg = (sheet?.background || "").toLowerCase();
      if (!value.some((b) => bg === b.name.toLowerCase())) out.push(`the ${value.map((b) => b.name).join(" or ")} background`);
    }
    // "campaign" (a setting) and "other" (free text) cannot be checked: the label shows them instead
  }
  return out;
}

export function featBlock(feat, ctx) {
  const alternatives = feat?.prerequisite || [];
  if (!alternatives.length) return "";
  const results = alternatives.map((part) => unmet(part, ctx));
  if (results.some((r) => !r.length)) return "";
  return `needs ${results.map((r) => r.join(", ")).join("; or ")}`;
}

// The unchecked parts, for the label: "Dragonlance", "No other dragonmark"
export function featNotes(feat) {
  return (feat?.prerequisite || []).flatMap((p) => [...(p.campaign || []), ...(p.other ? [p.other] : []), ...(p.item || [])]);
}

// A feat as a dropdown option: greyed out with the reason while its prerequisite is unmet (when enforced);
// the feat already chosen stays pickable so a changed score does not silently drop it.
export function featOption(feat, ctx, { enforce = true, chosen = null, group = null } = {}) {
  const blocked = enforce && feat.id !== chosen ? featBlock(feat, ctx) : "";
  const notes = featNotes(feat);
  const name = feat.name.replace(/'/g, "’");
  return { value: feat.id, group, disabled: !!blocked,
    label: `${name}${blocked ? ` (${blocked})` : notes.length ? ` (${notes.join(", ")})` : ""}` };
}
