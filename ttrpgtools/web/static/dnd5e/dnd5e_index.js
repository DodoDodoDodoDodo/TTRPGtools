// Hub page: encounters, fights, party.
"use strict";

const pageUrl = (kind, id) => API.replace(/api$/, "") + kind + "/" + encodeURIComponent(id);
let classes = [];

function localTime(iso) {
  return new Date(iso).toLocaleString("de-DE", { dateStyle: "short", timeStyle: "short" });
}

async function loadEncounters() {
  const data = await guard(() => api("GET", "/encounters"));
  if (!data) return;
  replace(document.getElementById("encounters"), data.encounters.length ? h("div", { class: "table-scroll" },
    h("table", { class: "plan-table" },
      h("thead", {}, h("tr", {}, ["Name", "Monsters", "PCs", "Changed", ""].map((t) => h("th", {}, t)))),
      h("tbody", {}, data.encounters.map((e) => h("tr", {},
        h("td", {}, h("a", { class: "name", href: pageUrl("encounter", e.id) }, e.name)),
        h("td", { class: "num" }, e.monsters), h("td", { class: "num" }, e.pcs),
        h("td", {}, localTime(e.updated)),
        h("td", {}, h("button", { class: "mini-button danger", type: "button", onclick: async () => {
          if (!confirm(`Delete the encounter "${e.name}"?`)) return;
          await guard(() => api("DELETE", "/encounters/" + e.id));
          loadEncounters();
        } }, "Delete")))))))
    : h("p", { class: "empty-state" }, "No encounters yet."));
  replace(document.getElementById("combats"), data.combats.length ? h("div", { class: "table-scroll" },
    h("table", { class: "plan-table" },
      h("thead", {}, h("tr", {}, ["Name", "State", "Changed", ""].map((t) => h("th", {}, t)))),
      h("tbody", {}, data.combats.map((c) => h("tr", {},
        h("td", {}, h("a", { class: "name", href: pageUrl("combat", c.id) }, c.name)),
        h("td", {}, c.started ? `Round ${c.round}` : c.round ? `Ended, round ${c.round}` : "Not started"),
        h("td", {}, localTime(c.updated)),
        h("td", {}, h("button", { class: "mini-button danger", type: "button", onclick: async () => {
          if (!confirm(`Delete the fight "${c.name}" and its history?`)) return;
          await guard(() => api("DELETE", "/combats/" + c.id));
          loadEncounters();
        } }, "Delete")))))))
    : h("p", { class: "empty-state" }, "No fights yet."));
}

function pcForm(pc) {
  const field = (label, name, attrs) => h("label", {}, label,
    h("input", Object.assign({ name, value: pc[name] ?? "" }, attrs)));
  const cls = h("select", { name: "cls" }, h("option", { value: "" }, "Other"),
    classes.map((c) => h("option", { value: c, selected: pc.cls === c }, c[0].toUpperCase() + c.slice(1))));
  const counters = h("textarea", { name: "counters", rows: 4,
    placeholder: "One per line: name, uses, rest (short, long)\nSecond Wind, 1, short" },
    (pc.resources || []).filter((r) => r.kind !== "slot").map((r) => `${r.name}, ${r.max}, ${r.kind}`).join("\n"));
  const slots = h("input", { name: "slots", type: "text", placeholder: "4, 3, 2",
    value: (() => { const out = []; for (const r of pc.resources || []) if (r.kind === "slot") out[r.level - 1] = r.max;
                    return Array.from(out, (v) => v || 0).join(", "); })() });
  const form = h("form", { class: "form-grid" },
    field("Name", "name", { type: "text", required: true, maxLength: 60 }),
    h("label", {}, "Class", cls),
    field("Level", "level", { type: "number", min: 1, max: 20, required: true, value: pc.level ?? 1 }),
    field("Hit points (maximum)", "hp", { type: "number", min: 1, required: true }),
    h("label", {}, "Armor Class" + (pc.ac_estimated ? " (estimate: " + (pc.ac_how || "computed") + ")" : ""),
      h("input", { name: "ac", type: "number", min: 1, max: 40, required: true, value: pc.ac ?? "" })),
    field("Initiative modifier", "init_mod", { type: "number", min: -5, max: 20 }),
    h("label", {}, "Damage per round if all attacks hit (optional)",
      h("input", { name: "dpr", type: "number", min: 0, step: "0.5", value: pc.dpr ?? "" }),
      h("span", { class: "hint" }, "Empty: the difficulty estimate uses a baseline for class and level.")),
    field("Attack bonus (optional)", "attack_bonus", { type: "number", min: 0, max: 20 }),
    h("label", { class: "wide" }, "Spell slots by level, from level 1", slots),
    h("label", { class: "wide" }, "Counters", counters),
    h("button", { class: "button", type: "submit" }, "Save"));
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(form));
    const resources = [];
    values.slots.split(",").map((s) => parseInt(s, 10)).forEach((count, i) => {
      if (count > 0) {
        const old = (pc.resources || []).find((r) => r.key === `slot-${i + 1}`);
        resources.push({ key: `slot-${i + 1}`, name: `Level ${i + 1} slots`, kind: "slot", level: i + 1,
                         max: count, spent: Math.min(count, old ? old.spent || 0 : 0) });
      }
    });
    for (const line of values.counters.split("\n")) {
      const [name, uses, rest] = line.split(",").map((s) => s.trim());
      if (!name) continue;
      const key = name.toLowerCase().replace(/[^a-z0-9]+/g, "-");
      const old = (pc.resources || []).find((r) => r.key === key);
      const max = Math.max(1, parseInt(uses, 10) || 1);
      resources.push({ key, name, max, spent: Math.min(max, old ? old.spent || 0 : 0),
                       kind: ["short", "long", "day"].includes(rest) ? rest : "long" });
    }
    const body = { name: values.name, cls: values.cls, level: values.level, hp: values.hp, ac: values.ac,
                   init_mod: values.init_mod, dpr: values.dpr, attack_bonus: values.attack_bonus, resources };
    const saved = await guard(() => pc.id ? api("PUT", "/pcs/" + pc.id, body) : api("POST", "/pcs", body));
    if (saved) { box.closeDialog(); loadPcs(); }
  });
  const box = dialog(pc.id ? "Edit " + pc.name : "New character", form);
}

async function loadPcs() {
  const data = await guard(() => api("GET", "/pcs"));
  if (!data) return;
  classes = data.classes;
  replace(document.getElementById("pcs"), data.pcs.length ? h("div", { class: "table-scroll" },
    h("table", { class: "plan-table" },
      h("thead", {}, h("tr", {}, ["Name", "Class", "HP", "AC", ""].map((t) => h("th", {}, t)))),
      h("tbody", {}, data.pcs.map((pc) => h("tr", {},
        h("td", { class: "name" }, pc.name),
        h("td", {}, (pc.classes || [{ name: pc.cls || "?", level: pc.level }])
          .map((c) => `${c.name} ${c.level}`).join(" / ")),
        h("td", { class: "num" }, `${pc.hp_current ?? pc.hp}/${pc.hp}`),
        h("td", { class: "num" }, pc.ac + (pc.ac_estimated ? " ?" : "")),
        h("td", {}, h("div", { class: "button-row" },
          h("button", { class: "mini-button", type: "button", onclick: () => pcForm(pc) }, "Edit"),
          pc.ddb_id ? h("button", { class: "mini-button", type: "button", onclick: async () => {
            const result = await guard(() => api("POST", "/pcs/import-ddb", { reference: pc.ddb_id }));
            if (result) { toast(`${result.pc.name} refreshed from D&D Beyond.`); loadPcs(); }
          } }, "Refresh") : null,
          h("button", { class: "mini-button danger", type: "button", onclick: async () => {
            if (!confirm(`Remove ${pc.name} from the party?`)) return;
            await guard(() => api("DELETE", "/pcs/" + pc.id));
            loadPcs();
          } }, "Remove"))))))),
    data.pcs.some((pc) => pc.ac_estimated)
      ? h("p", { class: "hint" }, "AC with a question mark is computed from equipped armour. Check it once and save; the saved value then stays.")
      : null)
    : h("p", { class: "empty-state" }, "No characters yet. Import from D&D Beyond or add by hand."));
}

document.getElementById("new-pc").addEventListener("click", () => pcForm({}));
document.getElementById("ddb-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const input = document.getElementById("ddb-ref");
  const button = event.target.querySelector("button");
  button.disabled = true; button.textContent = "Importing";
  const result = await guard(() => api("POST", "/pcs/import-ddb", { reference: input.value }));
  button.disabled = false; button.textContent = "Import";
  if (result) { input.value = ""; toast(`${result.pc.name} ${result.refreshed ? "refreshed" : "imported"}.`); loadPcs(); }
});
document.getElementById("new-encounter").addEventListener("click", async () => {
  const created = await guard(() => api("POST", "/encounters", { name: "New encounter" }));
  if (created) location.href = pageUrl("encounter", created.id);
});
document.getElementById("quick-fight").addEventListener("click", async () => {
  const created = await guard(() => api("POST", "/combats", { name: "Quick fight", with_party: true }));
  if (created) location.href = pageUrl("combat", created.id);
});
loadEncounters();
loadPcs();
