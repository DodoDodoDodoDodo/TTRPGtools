// The registers of the campaign: the hundred villagers and the monsters. A player creates a character by taking
// over one of the playable villagers: the numbers are shown, the birth augur is not. The admin sets status and notes.
"use strict";

(() => {
  const { h, api } = DCC;
  const root = document.getElementById("registry");
  const ABILITIES = [["strength", "Str"], ["agility", "Agi"], ["stamina", "Sta"], ["personality", "Per"], ["intelligence", "Int"], ["luck", "Luck"]];
  let table = location.hash === "#monsters" ? "monsters" : "people", data = null, filter = "", open = null, note = "", onlyFree = true;

  async function load() { data = await api("GET", "registry/" + table); draw(); }
  async function save(row, change) {
    try { data = await api("POST", "registry/" + table, { id: row.id, ...change }); note = ""; } catch (err) { note = err.message; }
    draw();
  }
  async function claim(row, alignment, moon) {
    try {
      const made = await api("POST", "registry/people", { action: "claim", id: row.id, alignment, moon });
      location.href = DCC.root + made.character + "/level-up";
    } catch (err) { note = err.message; draw(); }
  }
  const status = (row) => !data.judge ? row.status : h("select", { "aria-label": "Status of " + row.name, onchange: (e) => save(row, { status: e.target.value }) },
    data.statuses.map((s) => h("option", { value: s, selected: s === row.status }, s)));
  const notes = (row) => !data.judge ? row.notes : h("input", { type: "text", value: row.notes, "aria-label": "Notes on " + row.name,
    onchange: (e) => save(row, { notes: e.target.value }) });

  function takeOver(row) {
    const p = row.preview;
    const alignment = h("select", { "aria-label": "Alignment" }, h("option", { value: "" }, "Alignment"), data.alignments.map((a) => h("option", { value: a }, a)));
    const moon = h("select", { "aria-label": "Moon" }, h("option", { value: "" }, "Moon"), data.moons.map((m) => h("option", { value: m.id }, `${m.name}: ${m.blurb.toLowerCase()}`)));
    return h("tr", { class: "take-over" }, h("td", { colSpan: 12 },
      h("p", {}, h("b", {}, row.name), ` carries: ${p.weapon}, ${p.goods}, ${p.item}, and ${p.copper} cp. `,
        `Luck and the birth augur stay sealed until the character is finished: class chosen, 1st level reached. The debt you can see: ${DCC.gp(row.debt_cp || 0)} owed to the tax office comes with them.`),
      h("div", { class: "button-row" }, alignment, moon,
        h("button", { class: "button", type: "button", onclick: () => alignment.value && moon.value ? claim(row, alignment.value, moon.value)
          : (note = "Choose an alignment and a moon first.", draw()) }, `Play ${row.name}`),
        h("span", { class: "hint" }, "The villager becomes your character with 10 XP: enough to choose a class at once."))));
  }

  function peopleTable(rows) {
    return h("table", { class: "registry" },
      h("thead", {}, h("tr", {}, ["Name", "Occupation", ...ABILITIES.map((a) => a[1]), "HP", "Owes", "Household", "", ...(data.judge ? ["Notes"] : [])].map((t) => h("th", {}, t)))),
      h("tbody", {}, rows.map((r) => {
        const p = r.preview;
        const what = r.locked ? h("span", { class: "tag" }, "townsfolk")
          : r.claimed_by ? h("a", { href: DCC.root + r.character_id }, "played by " + r.claimed_by)
          : r.playable ? h("button", { class: "mini-button", type: "button", onclick: () => { open = open === r.id ? null : r.id; note = ""; draw(); } }, open === r.id ? "Close" : "Play")
          : null;
        return [h("tr", { class: "status-" + r.status + (r.playable ? "" : " taken") },
          h("td", {}, h("b", {}, r.name), r.status === "alive" && !data.judge ? null : [" ", status(r)]), h("td", {}, r.occupation),
          ABILITIES.map(([key]) => h("td", { class: "num" }, p ? (p.abilities[key] ?? "?") : "")), h("td", { class: "num" }, p ? p.hp : ""),
          h("td", { class: "num owes" }, r.status === "dead" ? "" : DCC.gp(r.debt_cp || 0)),
          h("td", { class: "num" }, r.household_cp == null ? "" : DCC.gp(r.household_cp)),
          h("td", {}, what, data.judge && p && p.augur ? h("div", { class: "hint" }, "augur: " + p.augur) : null),
          data.judge ? h("td", {}, notes(r)) : null),
          open === r.id && r.playable ? takeOver(r) : null];
      })));
  }

  function draw() {
    const people = table === "people";
    let rows = data.rows.filter((r) => (r.name + " " + (r.occupation || "") + " " + r.status).toLowerCase().includes(filter.toLowerCase()));
    if (people && onlyFree && !data.judge) rows = rows.filter((r) => r.playable);
    const counts = data.statuses.map((s) => `${data.rows.filter((r) => r.status === s).length} ${s}`).join(", ");
    root.replaceChildren(h("section", { class: "panel" },
      h("div", { class: "panel-header" }, h("h1", {}, people ? "Villagers" : "Monsters"),
        h("div", { class: "button-row" },
          h("a", { class: "mini-button" + (people ? " active" : ""), href: "#people" }, "Villagers"),
          h("a", { class: "mini-button" + (people ? "" : " active"), href: "#monsters" }, "Monsters"),
          h("input", { type: "search", placeholder: "Search", value: filter, "aria-label": "Search",
            oninput: (e) => { filter = e.target.value; draw(); const s = root.querySelector("input[type=search]"); s.focus(); s.setSelectionRange(filter.length, filter.length); } }))),
      people ? h("p", { id: "how" }, "Every character begins as one of these villagers. Pick one whose numbers you like and press Play: ",
        `${data.rows.filter((r) => r.playable).length} are free. Shopkeepers, innkeepers, the mayor and the traders stay townsfolk. `,
        data.judge ? null : h("label", { style: "display:inline" }, h("input", { type: "checkbox", checked: onlyFree, onchange: (e) => { onlyFree = e.target.checked; draw(); } }), " show only free villagers")) : null,
      note ? h("p", { class: "error-banner", role: "alert" }, note) : null,
      h("p", { class: "hint" }, `${data.rows.length} in all: ${counts}.`),
      people ? peopleTable(rows) : h("table", { class: "registry" }, h("thead", {}, h("tr", {}, ["Name", "HD", "AC", "Attack", "Special", "AL", "Page", "Status", "Notes"].map((t) => h("th", {}, t)))),
        h("tbody", {}, rows.map((r) => h("tr", { class: "status-" + r.status.replace(/ /g, "-") },
          h("td", {}, h("b", {}, r.name)), h("td", {}, r.hd), h("td", { class: "num" }, r.ac), h("td", {}, r.attack), h("td", { class: "hint" }, r.special),
          h("td", {}, r.alignment), h("td", { class: "num" }, r.page), h("td", {}, status(r)), h("td", {}, notes(r))))))));
  }
  DCC.guide = () => ({ id: "villagers", steps: [
    { target: "#how", text: "This is how a character is made here: you take over one of the villagers." },
    { target: ".registry tbody tr", text: "Each free villager shows five ability scores and the hit points rolled for them. Luck and the birth augur stay hidden until the character is finished." },
    { target: ".registry .mini-button", text: "Play opens the villager: what they carry, then your two choices, alignment and moon." }] });
  addEventListener("hashchange", () => { table = location.hash === "#monsters" ? "monsters" : "people"; filter = ""; open = null; load(); });
  load().then(() => DCC.tour.auto("villagers", DCC.guide().steps)).catch((err) => root.replaceChildren(h("p", { class: "error-banner" }, err.message)));
})();
