// Combat tracker. The server owns the state; every change is one operation.
"use strict";

const combatId = document.documentElement.dataset.combat;
let state = null;
let order = [];
let selected = null;        // combatant id shown in the detail panel
const marked = new Set();   // ids marked for area damage
let reminders = [];
let busy = Promise.resolve();

const byId = (id) => state.combatants.find((c) => c.id === id);
// Before the fight starts rows keep their place, so typing initiatives does not shuffle them.
const inOrder = () => (state.started ? order.map(byId).filter(Boolean) : state.combatants);

function accept(data) {
  state = data.state;
  order = data.order;
  if (data.prompts && data.prompts.length) reminders = data.prompts;
  for (const id of [...marked]) if (!byId(id)) marked.delete(id);
  if (selected && !byId(selected)) selected = null;
  draw();
}

// Operations are sent one at a time, each with the version the page last saw.
function send(op, options) {
  busy = busy.then(async () => {
    try {
      if (!options || !options.keepReminders) reminders = [];
      accept(await api("POST", `/combats/${combatId}/op`, { op, version: state.version }));
    } catch (error) {
      toast(error.message, "error");
      if (error.conflict) await reload();
    }
  });
  return busy;
}

async function reload() {
  const data = await guard(() => api("GET", "/combats/" + combatId));
  if (data) accept(data);
}

// ------------------------------------------------------------------ rows
function hpEntry(c, input) {
  const raw = input.value.trim().toLowerCase();
  input.value = "";
  if (!raw) return;
  const amount = parseInt(raw.replace(/[^0-9]/g, ""), 10);
  if (!Number.isFinite(amount)) { toast("Enter a number: 12 damage, +12 heal, t12 temporary HP.", "error"); return; }
  const op = raw.startsWith("+") ? "heal" : raw.startsWith("t") ? "temp_hp" : "damage";
  send({ op, id: c.id, amount }, { keepReminders: true });
}

function counter(c, r) {
  const left = r.max - r.spent;
  const label = r.kind === "recharge" ? `${r.name} (recharge ${r.recharge_min === 6 ? "6" : r.recharge_min + "-6"})`
    : r.kind === "slot" ? `L${r.level}` : r.name;
  const pips = r.max <= 8
    ? h("span", { class: "pips" }, Array.from({ length: r.max }, (_, i) => h("button", {
        type: "button", class: "pip" + (i < left ? "" : " spent"),
        "aria-label": `${r.name}: ${i < left ? "use one" : "restore one"} (${left} of ${r.max} left)`,
        onclick: (e) => { e.stopPropagation();
          send({ op: i < left ? "spend" : "restore", id: c.id, key: r.key, amount: 1 }, { keepReminders: true }); },
      })))
    : h("span", { class: "row" },
        h("button", { type: "button", class: "mini-button", "aria-label": "Use one " + r.name, disabled: left <= 0,
          onclick: (e) => { e.stopPropagation(); send({ op: "spend", id: c.id, key: r.key, amount: 1 }, { keepReminders: true }); } }, "-"),
        h("span", { class: "num" }, `${left}/${r.max}`),
        h("button", { type: "button", class: "mini-button", "aria-label": "Restore one " + r.name, disabled: r.spent <= 0,
          onclick: (e) => { e.stopPropagation(); send({ op: "restore", id: c.id, key: r.key, amount: 1 }, { keepReminders: true }); } }, "+"));
  return h("span", { class: "counter " + r.kind, title: `${r.name}: ${left} of ${r.max} left` }, label, pips);
}

function row(c) {
  const ratio = c.hp_max ? c.hp / c.hp_max : 0;
  const bloodied = c.hp > 0 && ratio <= 0.5;
  const hpInput = h("input", { type: "text", inputMode: "numeric", placeholder: "dmg", dataset: { hp: c.id },
    "aria-label": `Damage or healing for ${c.label}`,
    onkeydown: (e) => { if (e.key === "Enter") { hpEntry(c, e.target); e.preventDefault(); } e.stopPropagation(); },
    onclick: (e) => e.stopPropagation() });
  const slots = c.resources.filter((r) => r.kind === "slot");
  const others = c.resources.filter((r) => r.kind !== "slot");
  return h("div", {
    class: ["combatant", c.kind, c.id === state.turn ? "turn" : "", c.id === selected ? "selected" : "",
            c.defeated ? "defeated" : ""].join(" "),
    dataset: { id: c.id }, onclick: () => { selected = c.id; draw(); },
  },
    h("div", { class: "c-init" }, h("input", { type: "number", value: c.initiative ?? "", placeholder: "init",
      "aria-label": `Initiative of ${c.label} (modifier ${signed(c.init_mod || 0)})`,
      title: `Initiative modifier ${signed(c.init_mod || 0)}`,
      onclick: (e) => e.stopPropagation(), onkeydown: (e) => e.stopPropagation(),
      onchange: (e) => send({ op: "set_initiative", id: c.id, value: e.target.value }, { keepReminders: true }) })),
    h("div", {},
      h("input", { type: "checkbox", checked: marked.has(c.id), "aria-label": `Mark ${c.label} for area damage`,
        onclick: (e) => { e.stopPropagation(); e.target.checked ? marked.add(c.id) : marked.delete(c.id); drawBar(); } }),
      " ", h("button", { class: "c-name", type: "button" }, c.label),
      h("div", { class: "c-sub" }, `AC ${c.ac} · init ${signed(c.init_mod || 0)}`
        + (c.kind === "pc" ? ` · ${c.cls || "PC"} ${c.level || ""}` : c.kind === "monster" ? ` · CR ${c.statblock.cr || "?"}` : ""))),
    h("div", { class: "c-hp" },
      c.hp_max ? h("span", { class: "hp" + (c.hp === 0 ? " down" : bloodied ? " bloodied" : "") },
        `${c.hp}/${c.hp_max}` + (c.temp_hp ? ` +${c.temp_hp}` : "")) : null,
      c.hp_max ? hpInput : null),
    c.hp_max ? h("div", { class: "hpbar" }, h("span", { class: bloodied ? "bloodied" : "",
      style: `width:${Math.round(ratio * 100)}%` })) : null,
    h("div", { class: "c-extra" },
      c.conditions.map((x) => h("button", { type: "button", class: "chip condition",
        title: "Remove " + x.name, onclick: (e) => { e.stopPropagation();
          send({ op: "remove_condition", id: c.id, name: x.name }, { keepReminders: true }); } },
        x.name + (x.rounds ? ` (${x.rounds})` : "") + " ×")),
      c.concentration ? h("button", { type: "button", class: "chip conc", title: "End concentration",
        onclick: (e) => { e.stopPropagation(); send({ op: "concentration", id: c.id, spell: "" }, { keepReminders: true }); } },
        "Concentrating: " + c.concentration + " ×") : null,
      h("button", { type: "button", class: "chip" + (c.reaction_used ? " used" : ""),
        onclick: (e) => { e.stopPropagation(); send({ op: "reaction", id: c.id }, { keepReminders: true }); } },
        c.reaction_used ? "Reaction used" : "Reaction"),
      c.kind === "pc" && c.hp === 0 ? deathSaves(c) : null,
      others.map((r) => counter(c, r)),
      slots.length ? h("span", { class: "counter" }, "Slots ", slots.map((r) => counter(c, r))) : null));
}

function deathSaves(c) {
  const saves = c.death_saves || { success: 0, fail: 0 };
  const button = (success) => h("button", { type: "button", class: "chip" + (success ? "" : " used"),
    onclick: (e) => { e.stopPropagation(); send({ op: "death_save", id: c.id, success }); } },
    `${success ? "Saves" : "Fails"} ${success ? saves.success : saves.fail}/3 +`);
  return [button(true), button(false)];
}

// ------------------------------------------------------------------ detail
function detail() {
  const target = document.getElementById("detail");
  const c = selected && byId(selected);
  if (!c) { replace(target, h("p", { class: "empty-state" }, "Select a combatant.")); return; }
  const condition = h("select", { "aria-label": "Condition" }, window.CONDITIONS.map((n) => h("option", {}, n)));
  const rounds = h("input", { type: "number", min: 1, max: 100, placeholder: "rounds", class: "cr",
                              "aria-label": "Duration in rounds, empty for open-ended" });
  const spell = h("input", { type: "text", placeholder: "Concentration spell", value: c.concentration || "",
                             "aria-label": "Concentration spell" });
  const label = h("input", { type: "text", value: c.label, maxLength: 60, "aria-label": "Name" });
  const hpMax = h("input", { type: "number", class: "cr", value: c.hp_max, min: 0, "aria-label": "Maximum HP" });
  const hp = h("input", { type: "number", class: "cr", value: c.hp, min: 0, "aria-label": "Current HP" });
  const ac = h("input", { type: "number", class: "cr", value: c.ac, min: 0, "aria-label": "Armor Class" });
  const notes = h("textarea", { rows: 3, style: "width:100%", "aria-label": "Notes" }, c.notes || "");
  const counterName = h("input", { type: "text", placeholder: "New counter", "aria-label": "New counter name" });
  const counterMax = h("input", { type: "number", class: "cr", min: 1, max: 99, value: 1, "aria-label": "Uses" });
  const stop = (e) => e.stopPropagation();
  const form = (...children) => h("div", { class: "row", onkeydown: stop }, children);

  replace(target,
    h("div", { class: "panel-header" }, h("h2", {}, c.label),
      h("button", { class: "mini-button danger", type: "button", onclick: () => {
        if (confirm(`Remove ${c.label} from the fight?`)) send({ op: "remove", id: c.id });
      } }, "Remove")),
    form(label, h("button", { class: "mini-button", type: "button",
      onclick: () => send({ op: "rename", id: c.id, label: label.value }, { keepReminders: true }) }, "Rename")),
    form(h("label", { class: "hint" }, "HP ", hp), h("label", { class: "hint" }, "Max ", hpMax),
      h("label", { class: "hint" }, "AC ", ac),
      h("button", { class: "mini-button", type: "button", onclick: () => send(
        { op: "set", id: c.id, hp: hp.value, hp_max: hpMax.value, ac: ac.value }, { keepReminders: true }) }, "Set"),
      c.kind !== "pc" ? h("button", { class: "mini-button", type: "button",
        onclick: () => send({ op: "defeated", id: c.id }, { keepReminders: true }) },
        c.defeated ? "Back in the fight" : "Mark defeated") : null),
    form(condition, rounds, h("button", { class: "mini-button", type: "button", onclick: () => send(
      { op: "condition", id: c.id, name: condition.value, rounds: rounds.value || null }, { keepReminders: true }) },
      "Add condition")),
    form(spell, h("button", { class: "mini-button", type: "button",
      onclick: () => send({ op: "concentration", id: c.id, spell: spell.value }, { keepReminders: true }) }, "Set concentration")),
    form(counterName, counterMax, h("button", { class: "mini-button", type: "button", onclick: () => send(
      { op: "add_resource", id: c.id, name: counterName.value, max: counterMax.value }, { keepReminders: true }) },
      "Add counter")),
    c.resources.length ? h("p", { class: "hint" }, "Counters: ", c.resources.map((r, i) => [i ? ", " : "",
      `${r.name} ${r.max - r.spent}/${r.max}`]),
      " ", h("button", { class: "mini-button", type: "button",
        onclick: () => send({ op: "rest", id: c.id, kind: "long" }, { keepReminders: true }) }, "Restore all")) : null,
    h("div", { onkeydown: stop }, notes, h("button", { class: "mini-button", type: "button",
      onclick: () => send({ op: "set", id: c.id, notes: notes.value }, { keepReminders: true }) }, "Save notes")),
    c.statblock ? statblock(c.statblock) : null);
}

// ------------------------------------------------------------------ bar, log
function drawBar() {
  const current = byId(state.turn);
  document.getElementById("round").textContent = state.started
    ? `Round ${state.round}` + (current ? ` · ${current.label}` : "") : state.round ? "Ended" : "Not started";
  document.getElementById("start").hidden = state.started;
  document.getElementById("next").hidden = !state.started;
  document.getElementById("prev").hidden = !state.started;
  document.getElementById("area").textContent = marked.size ? `Area damage (${marked.size})` : "Area damage";
  replace(document.getElementById("reminders"),
    reminders.map((text) => h("div", { class: "toast prompt" }, text)));
  document.title = (state.started ? `R${state.round} ` : "") + state.name + " :: Fight";
}

function draw() {
  drawBar();
  const list = document.getElementById("combatants");
  const focused = document.activeElement && document.activeElement.dataset ? document.activeElement.dataset.hp : null;
  replace(list, inOrder().length ? inOrder().map(row)
    : h("p", { class: "empty-state" }, "Nobody here yet. Add monsters with A."));
  if (focused) { const again = list.querySelector(`[data-hp="${focused}"]`); if (again) again.focus(); }
  replace(document.getElementById("log"), [...state.log].reverse().slice(0, 60).map((entry) =>
    h("li", {}, `R${entry.round}: ${entry.text}`)));
  detail();
}

// ------------------------------------------------------------------ dialogs
function areaDamage() {
  const targets = inOrder().filter((c) => marked.has(c.id));
  if (!targets.length) { toast("Mark targets first: tick the box beside each name, or press X.", "error"); return; }
  const amount = h("input", { type: "number", min: 0, required: true, "aria-label": "Damage", placeholder: "Damage" });
  const saved = new Map(targets.map((c) => [c.id, h("input", { type: "checkbox" })]));
  const form = h("form", {},
    h("div", { class: "row" }, h("label", {}, "Damage on a failed save ", amount)),
    h("p", { class: "hint" }, "Tick who made the save; they take half."),
    targets.map((c) => h("label", { class: "row" }, saved.get(c.id), `${c.label} (${c.hp}/${c.hp_max})`)),
    h("div", { class: "row" }, h("button", { class: "button", type: "submit" }, "Apply")));
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    send({ op: "damage", ids: targets.map((c) => c.id), amount: Number(amount.value),
           half: targets.filter((c) => saved.get(c.id).checked).map((c) => c.id) });
    marked.clear();
    box.closeDialog();
  });
  const box = dialog(`Area damage on ${targets.length}`, form);
  amount.focus();
}

function addMonster() {
  const initiative = h("input", { type: "number", class: "cr", placeholder: "init", "aria-label": "Initiative for the new monsters" });
  const picker = monsterPicker({
    pickLabel: "Add to fight", onShow: (row) => showMonster(row.id),
    onPick: (row, count) => {
      send({ op: "add_monster", monster_id: row.id, count, initiative: initiative.value === "" ? null : Number(initiative.value) },
           { keepReminders: true });
      toast(`${count} x ${row.name} added.`);
    },
  });
  dialog("Add monster", h("div", {}, h("label", { class: "hint" }, "Initiative (optional) ", initiative), picker));
  picker.focusSearch();
}

function addCustom() {
  const name = h("input", { type: "text", required: true, maxLength: 60, placeholder: "Name", "aria-label": "Name" });
  const hp = h("input", { type: "number", class: "cr", min: 0, placeholder: "HP", "aria-label": "Hit points" });
  const ac = h("input", { type: "number", class: "cr", min: 0, placeholder: "AC", "aria-label": "Armor Class" });
  const initiative = h("input", { type: "number", class: "cr", placeholder: "init", "aria-label": "Initiative" });
  const form = h("form", { class: "row" }, name, hp, ac, initiative,
    h("button", { class: "button", type: "submit" }, "Add"));
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    send({ op: "add_custom", label: name.value, hp: hp.value || 0, ac: ac.value || 10,
           initiative: initiative.value === "" ? null : Number(initiative.value) }, { keepReminders: true });
    box.closeDialog();
  });
  const box = dialog("Add an ally, hazard or lair action marker", form);
  name.focus();
}

function more() {
  const box = dialog("More", h("div", { class: "row" },
    h("button", { class: "mini-button", type: "button", onclick: async () => {
      const result = await guard(() => api("POST", `/combats/${combatId}/sync-pcs`));
      if (result) toast(result.updated.length ? "Party updated: " + result.updated.join(", ") + "." : "No party members in this fight.");
      box.closeDialog();
    } }, "Write HP and counters back to the party"),
    h("button", { class: "mini-button", type: "button",
      onclick: () => { send({ op: "rest", kind: "short" }); box.closeDialog(); } }, "Short rest for all"),
    h("button", { class: "mini-button", type: "button",
      onclick: () => { if (confirm("Long rest: everyone to full HP, all counters restored?")) { send({ op: "rest", kind: "long" }); box.closeDialog(); } } },
      "Long rest for all"),
    h("button", { class: "mini-button danger", type: "button",
      onclick: () => { send({ op: "end" }); box.closeDialog(); } }, "End combat")));
}

async function undo() {
  busy = busy.then(async () => {
    const data = await guard(() => api("POST", `/combats/${combatId}/undo`));
    if (data) { reminders = []; accept(data); toast("Undone."); }
  });
}

// ------------------------------------------------------------------ wiring
document.getElementById("start").addEventListener("click", () => send({ op: "start" }));
document.getElementById("next").addEventListener("click", () => send({ op: "next" }));
document.getElementById("prev").addEventListener("click", () => send({ op: "prev" }));
document.getElementById("undo").addEventListener("click", undo);
document.getElementById("area").addEventListener("click", areaDamage);
document.getElementById("add-monster").addEventListener("click", addMonster);
document.getElementById("add-custom").addEventListener("click", addCustom);
document.getElementById("more").addEventListener("click", more);

document.addEventListener("keydown", (event) => {
  const typing = ["INPUT", "TEXTAREA", "SELECT"].includes(event.target.tagName);
  if (typing || event.ctrlKey || event.metaKey || event.altKey || document.querySelector("dialog[open]") || !state) return;
  const list = inOrder();
  const index = Math.max(0, list.findIndex((c) => c.id === selected));
  const key = event.key.toLowerCase();
  if (key === "n") state.started ? send({ op: "next" }) : send({ op: "start" });
  else if (key === "u") undo();
  else if (key === "a") addMonster();
  else if (key === "j" || key === "arrowdown") { selected = (list[Math.min(list.length - 1, selected ? index + 1 : 0)] || {}).id; draw(); }
  else if (key === "k" || key === "arrowup") { selected = (list[Math.max(0, index - 1)] || {}).id; draw(); }
  else if (key === "x" && selected) { marked.has(selected) ? marked.delete(selected) : marked.add(selected); draw(); }
  else if (key === "d") {
    const id = selected || state.turn;
    const input = id && document.querySelector(`[data-hp="${id}"]`);
    if (input) input.focus();
  } else return;
  event.preventDefault();
});

// Another tab or device may run the same fight; pick up its changes when this one regains focus.
document.addEventListener("visibilitychange", () => { if (!document.hidden) busy = busy.then(reload); });
reload();
