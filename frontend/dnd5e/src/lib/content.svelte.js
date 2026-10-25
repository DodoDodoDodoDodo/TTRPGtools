// Builder data from builder_data.py, loaded once per page and indexed by id.
import { api } from "./api.js";

export const content = $state({
  ready: false,
  error: null,
  classes: [],
  races: [],
  backgrounds: [],
  feats: [],
  optionalfeatures: [],
  spells: [],
  items: [],
  languages: [],
  conditions: [],
  names: [],
  alignments: [],
  abilitytexts: [],
  ruletexts: [],
  books: [],
  lifestyles: [],
  actions: [],
  byId: { classes: {}, subclasses: {}, races: {}, backgrounds: {}, feats: {}, optionalfeatures: {}, spells: {}, items: {} },
  spellByName: {},
  itemByName: {},
});

let loading = null;

export function loadContent() {
  if (loading) return loading;
  const kinds = ["classes", "races", "backgrounds", "feats", "optionalfeatures", "spells", "items", "languages", "conditions", "names", "alignments", "lifestyles", "actions", "abilitytexts", "ruletexts", "books"];
  loading = Promise.all(kinds.map((k) => api.content(k)))
    .then((lists) => {
      kinds.forEach((kind, i) => {
        content[kind] = lists[i];
        if (content.byId[kind]) content.byId[kind] = Object.fromEntries(lists[i].map((e) => [e.id, e]));
      });
      for (const cls of content.classes) for (const sub of cls.subclasses) content.byId.subclasses[sub.id] = { ...sub, className: cls.name, classId: cls.id };
      for (const s of content.spells) {
        content.spellByName[s.name.toLowerCase()] ??= s;
        content.spellByName[`${s.name.toLowerCase()}|${s.source.toLowerCase()}`] = s;
      }
      for (const it of content.items) {
        content.itemByName[it.name.toLowerCase()] ??= it;
        content.itemByName[`${it.name.toLowerCase()}|${it.source.toLowerCase()}`] = it;
      }
      content.ready = true;
    })
    .catch((e) => {
      content.error = e.message;
    });
  return loading;
}

export function spellByRef(ref) {
  const key = String(ref).toLowerCase().split("#")[0];
  return content.spellByName[key] || content.spellByName[key.split("|")[0]] || null;
}

export function itemByRef(ref) {
  const key = String(ref).toLowerCase();
  return content.itemByName[key] || content.itemByName[key.split("|")[0]] || null;
}

// Home step "Sources": PHB content is "5e Core Rules", every other 2014 book "5e Expanded Rules" (DDB's split).
// Both are on unless the character's preferences switch one off.
// The books the Home step switched off (Dodo, 2026-10-25: one switch per book, grouped rules / adventures / other).
// Characters saved before that keep their old two switches (5e Core = PHB, 5e Expanded = everything else).
export function booksOff(preferences) {
  if (Array.isArray(preferences?.books_off)) return preferences.books_off;
  const sources = preferences?.sources || {};
  return content.books.map((b) => b.id).filter((id) => (id === "phb" ? sources.core === false : sources.expanded === false));
}
export function sourceAllowed(book, preferences) {
  return !booksOff(preferences).includes(book);
}
