// Encounters page: encounters and fights (the party now comes from campaigns).
"use strict";

const pageUrl = (kind, id) => API.replace(/api$/, "") + kind + "/" + encodeURIComponent(id);

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

document.getElementById("new-encounter").addEventListener("click", async () => {
  const created = await guard(() => api("POST", "/encounters", { name: "New encounter" }));
  if (created) location.href = pageUrl("encounter", created.id);
});
document.getElementById("quick-fight").addEventListener("click", async () => {
  const created = await guard(() => api("POST", "/combats", { name: "Quick fight", with_party: true }));
  if (created) location.href = pageUrl("combat", created.id);
});
loadEncounters();
