// Shared helpers for the D&D 5e encounter pages. No framework, no build step.
// All data reaches the DOM through h(), which sets text, never markup.
"use strict";

const API = document.documentElement.dataset.api;

function h(tag, attrs, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class") el.className = value;
    else if (key === "dataset") Object.assign(el.dataset, value);
    else if (key.startsWith("on")) el.addEventListener(key.slice(2), value);
    else if (key in el && key !== "list") el[key] = value;
    else el.setAttribute(key, value);
  }
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    el.append(child.nodeType ? child : document.createTextNode(String(child)));
  }
  return el;
}

function replace(target, ...children) {
  target.replaceChildren(...children.flat(Infinity).filter((c) => c !== null && c !== undefined && c !== false));
}

async function api(method, path, body) {
  const response = await fetch(API + path, {
    method,
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  let data = {};
  try { data = await response.json(); } catch (_) { /* empty or non-JSON body */ }
  if (!response.ok) {
    const error = new Error(data.error || `Request failed (${response.status}).`);
    error.conflict = Boolean(data.conflict);
    throw error;
  }
  return data;
}

function toast(message, kind) {
  let box = document.getElementById("toasts");
  if (!box) {
    box = h("div", { id: "toasts" });
    document.body.append(box);
  }
  const item = h("div", { class: "toast " + (kind || "info"), role: "status" }, message);
  box.append(item);
  setTimeout(() => item.remove(), kind === "error" ? 9000 : 6000);
}

async function guard(action) {
  try { return await action(); } catch (error) { toast(error.message, "error"); return undefined; }
}

function debounce(fn, delay) {
  let timer;
  return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), delay); };
}

const signed = (n) => (n >= 0 ? "+" : "") + n;
const modifier = (score) => Math.floor((score - 10) / 2);
const crText = (m) => m.cr_text ?? m.cr ?? "?";

// ------------------------------------------------------------------ stat block
function statblock(m) {
  const line = (label, value) => value ? h("p", { class: "sb-line" }, h("b", {}, label + " "), value) : null;
  const entries = (title, list, intro) => (list && list.length) ? [
    h("h4", {}, title),
    intro ? h("p", { class: "sb-entry" }, intro) : null,
    list.map((e) => h("p", { class: "sb-entry" }, e.name ? h("b", {}, e.name + ". ") : null, e.text)),
  ] : null;
  const abilities = h("div", { class: "sb-abilities" },
    ["str", "dex", "con", "int", "wis", "cha"].map((key) => {
      const score = (m.abilities || {})[key] ?? 10;
      return h("div", {}, h("span", { class: "label" }, key.toUpperCase()), `${score} (${signed(modifier(score))})`);
    }));
  const slots = (m.spell_slots || []).map((count, i) => `L${i + 1}: ${count}`).join(", ");
  return h("div", { class: "statblock" },
    h("h3", {}, m.name),
    h("p", { class: "subtitle" }, [m.size, m.type].filter(Boolean).join(" ") + (m.alignment ? ", " + m.alignment : "")
      + (m.role ? " · " + m.role : "")),
    line("Armor Class", m.ac_text || m.ac),
    line("Hit Points", m.hp_text || (m.hp + (m.hp_formula ? ` (${m.hp_formula})` : ""))),
    line("Speed", m.speed),
    abilities,
    line("Saving Throws", m.saves), line("Skills", m.skills),
    line("Vulnerabilities", m.vulnerable), line("Resistances", m.resist),
    line("Damage Immunities", m.immune), line("Condition Immunities", m.condition_immune),
    line("Senses", [m.senses, m.passive ? "passive Perception " + m.passive : ""].filter(Boolean).join(", ")),
    line("Languages", m.languages),
    line("Challenge", `${m.cr || "?"} (${(m.xp || 0).toLocaleString("en")} XP)`),
    line("Spell slots", slots),
    line("Spells", (m.spells || []).join(", ")),
    entries("Traits", m.traits), entries("Actions", m.actions), entries("Bonus Actions", m.bonus_actions),
    entries("Reactions", m.reactions),
    entries("Legendary Actions", m.legendary && m.legendary.filter((e) => !e.intro),
      (m.legendary || []).filter((e) => e.intro).map((e) => e.text).join(" ") || m.legendary_intro),
    entries("Villain Actions", m.villain, m.villain_intro),
    entries("Lair", m.lair),
    h("p", { class: "hint" }, (m.sources || [m.source]).filter(Boolean).join(" · ")));
}

function profileNote(profile) {
  if (!profile) return null;
  const rows = [
    ["Damage per round", `${profile.dpr} (rounds 1 to 3: ${profile.round_damage.join(", ")})`],
    ["Routine", (profile.routine || []).join(" + ") || "none read"],
    ["Legendary", profile.legendary],
    ["Effective HP", profile.ehp + (profile.ehp_factors.length ? ` (${profile.ehp_factors.join(", ")})` : "")],
    ["Stats read like", "CR " + ({ 0.125: "1/8", 0.25: "1/4", 0.5: "1/2" }[profile.computed_cr] ?? profile.computed_cr)],
  ];
  return h("div", { class: "profile" },
    h("h4", {}, "What the difficulty estimate reads"),
    h("dl", { class: "kv" }, rows.filter((r) => r[1]).map(([k, v]) => [h("dt", {}, k), h("dd", {}, v)])),
    profile.notes.map((n) => h("p", { class: "hint" }, n)));
}

// ------------------------------------------------------------------ monster picker
// onPick(row, count) is called for every add. Arrow keys move, Enter adds, a
// number typed before Enter in the count box adds that many.
function monsterPicker({ onPick, onShow, pickLabel }) {
  const query = h("input", { type: "search", placeholder: "Search monsters (name)", autocomplete: "off",
                             "aria-label": "Search monsters" });
  const crMin = h("input", { type: "text", class: "cr", placeholder: "CR from", "aria-label": "CR from" });
  const crMax = h("input", { type: "text", class: "cr", placeholder: "CR to", "aria-label": "CR to" });
  const type = h("input", { type: "text", class: "type", placeholder: "Type", "aria-label": "Creature type" });
  const official = h("input", { type: "checkbox", checked: true, id: "pick-official" });
  const count = h("input", { type: "number", class: "cr", min: 1, max: 50, value: 1, "aria-label": "How many" });
  const results = h("ul", { class: "pick-results", role: "listbox" });
  const status = h("p", { class: "hint" });
  let rows = [], cursor = 0;

  function draw() {
    replace(results, rows.map((row, i) => h("li", {
      class: i === cursor ? "active" : "", role: "option", "aria-selected": i === cursor,
      onclick: () => { cursor = i; pick(); },
    },
      h("span", { class: "pick-name" }, row.name),
      h("span", { class: "pick-meta" }, `CR ${crText(row)} · HP ${row.hp} · AC ${row.ac} · ${row.type || ""}`),
      h("span", { class: "pick-source" }, row.origin === "compendium" ? row.source : row.origin),
      onShow ? h("button", { class: "mini-button", type: "button",
                             onclick: (e) => { e.stopPropagation(); onShow(row); } }, "View") : null)));
    const active = results.querySelector(".active");
    if (active) active.scrollIntoView({ block: "nearest" });
  }
  function pick() {
    if (!rows[cursor]) return;
    onPick(rows[cursor], Math.max(1, Math.min(50, Number(count.value) || 1)));
    count.value = 1;
  }
  const search = debounce(async () => {
    const params = new URLSearchParams({ q: query.value, cr_min: crMin.value, cr_max: crMax.value,
                                         type: type.value, official: official.checked ? "1" : "0" });
    const data = await guard(() => api("GET", "/monsters?" + params));
    if (!data) return;
    rows = data.monsters; cursor = 0;
    status.textContent = data.bestiary_size === 0
      ? "The bestiary is empty. Build it from the compendium or paste a stat block."
      : rows.length ? "" : "Nothing matches.";
    draw();
  }, 180);
  for (const input of [query, crMin, crMax, type]) input.addEventListener("input", search);
  official.addEventListener("change", search);
  query.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") { cursor = Math.min(rows.length - 1, cursor + 1); draw(); e.preventDefault(); }
    else if (e.key === "ArrowUp") { cursor = Math.max(0, cursor - 1); draw(); e.preventDefault(); }
    else if (e.key === "Enter") { pick(); e.preventDefault(); }
  });
  search();
  const root = h("div", { class: "picker" },
    h("div", { class: "picker-bar" }, query, crMin, crMax, type, count,
      h("button", { class: "mini-button", type: "button", onclick: pick }, pickLabel || "Add")),
    h("label", { class: "hint", for: "pick-official" }, official, " Official books only (off: third party and homebrew too)"),
    status, results);
  root.focusSearch = () => query.focus();
  root.refresh = search;
  return root;
}

function dialog(title, body, onClose) {
  const box = h("dialog", { class: "sheet-dialog" });
  const close = () => { box.close(); box.remove(); if (onClose) onClose(); };
  box.append(h("div", { class: "panel-header" }, h("h2", {}, title),
    h("button", { class: "mini-button", type: "button", onclick: close }, "Close")), body);
  box.addEventListener("cancel", (e) => { e.preventDefault(); close(); });
  document.body.append(box);
  box.showModal();
  box.closeDialog = close;
  return box;
}

async function showMonster(id) {
  const monster = await guard(() => api("GET", "/monsters/" + encodeURIComponent(id)));
  if (monster) dialog(monster.name, h("div", {}, statblock(monster), profileNote(monster.profile)));
}
