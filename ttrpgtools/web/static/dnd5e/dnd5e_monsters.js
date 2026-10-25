// Monsters page: paste import with live preview, bestiary browser.
"use strict";

const paste = document.getElementById("paste");
const saveButton = document.getElementById("save");
const parseStatus = document.getElementById("parse-status");
const preview = document.getElementById("preview");

const parse = debounce(async () => {
  saveButton.disabled = true;
  if (!paste.value.trim()) {
    parseStatus.textContent = "Nothing pasted yet.";
    replace(preview);
    return;
  }
  try {
    const monster = await api("POST", "/monsters/parse", { text: paste.value });
    const counters = monster.resources.map((r) => `${r.name} (${r.kind === "recharge"
      ? "recharge " + r.recharge_min + "+" : r.max})`).join(", ");
    parseStatus.textContent = monster.import_problems.length
      ? "Read with gaps: " + monster.import_problems.join(" ")
      : `Read ${monster.name}: CR ${monster.cr}, ${monster.actions.length} actions.`;
    replace(preview,
      h("p", { class: "sb-line" }, h("b", {}, "Counters the tracker will keep: "), counters || "none"),
      statblock(monster), profileNote(monster.profile));
    saveButton.disabled = false;
  } catch (error) {
    parseStatus.textContent = error.message;
    replace(preview);
  }
}, 300);
paste.addEventListener("input", parse);

saveButton.addEventListener("click", async () => {
  const saved = await guard(() => api("POST", "/monsters", { text: paste.value }));
  if (!saved) return;
  toast(`${saved.name} saved.`);
  paste.value = "";
  parse();
  loadCustom();
  picker.refresh();
});

async function loadCustom() {
  const lists = await Promise.all(["paste", "manual"].map((origin) =>
    guard(() => api("GET", "/monsters?limit=200&origin=" + origin))));
  const rows = lists.filter(Boolean).flatMap((l) => l.monsters);
  replace(document.getElementById("custom"), rows.length ? h("div", { class: "table-scroll" },
    h("table", { class: "plan-table" },
      h("thead", {}, h("tr", {}, ["Name", "CR", "HP", "AC", ""].map((t) => h("th", {}, t)))),
      h("tbody", {}, rows.map((row) => h("tr", {},
        h("td", {}, h("button", { class: "c-name", type: "button", onclick: () => showMonster(row.id) }, row.name)),
        h("td", { class: "num" }, crText(row)), h("td", { class: "num" }, row.hp), h("td", { class: "num" }, row.ac),
        h("td", {}, h("button", { class: "mini-button danger", type: "button", onclick: async () => {
          if (!confirm(`Delete ${row.name} from the bestiary? Fights already running keep their copy.`)) return;
          await guard(() => api("DELETE", "/monsters/" + encodeURIComponent(row.id)));
          loadCustom();
          picker.refresh();
        } }, "Delete")))))))
    : h("p", { class: "empty-state" }, "Nothing imported yet."));
}

const picker = monsterPicker({ onPick: (row) => showMonster(row.id), pickLabel: "View", single: true });
document.getElementById("picker").append(picker);
loadCustom();

// #<monster id> (the hub's Continue card) opens that stat block
if (location.hash.length > 1) showMonster(decodeURIComponent(location.hash.slice(1)));
