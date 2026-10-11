// Encounter builder: plan on the left, picker on the right, rating recomputed on every change.
"use strict";

const encounterId = document.documentElement.dataset.encounter;
const TIER_LEVEL = { None: 0, Trivial: 0, Easy: 1, Light: 1, Medium: 2, Moderate: 2, Hard: 3, Dangerous: 3,
                     Deadly: 4, Lethal: 4 };
let plan = { name: "", pcs: [], monsters: [], notes: "", resources: "normal" };
let known = {};   // monster id -> summary row
let party = [];

const percent = (x) => Math.round(x * 100) + "%";

function badge(label, value, detail, extra) {
  return h("div", { class: "badge level-" + (TIER_LEVEL[value] ?? 0) },
    h("span", { class: "label" }, label), h("span", { class: "value" }, value),
    h("span", { class: "detail" }, detail), extra || null);
}

function drawRating(rating) {
  const target = document.getElementById("rating");
  if (!plan.monsters.length || !plan.pcs.length) {
    replace(target, h("p", { class: "empty-state" }, "Add characters and monsters."));
    return;
  }
  const { dmg, lazy } = rating.official;
  const duel = rating.duel;
  const next = ["easy", "medium", "hard", "deadly"].find((k) => dmg.thresholds[k] > dmg.adjusted_xp);
  replace(target,
    h("div", { class: "badges" },
      badge("DMG 2014", dmg.tier,
        `${dmg.adjusted_xp.toLocaleString("en")} XP adjusted (${dmg.raw_xp.toLocaleString("en")} x ${dmg.multiplier})`
        + (next ? `, ${next} from ${dmg.thresholds[next].toLocaleString("en")}` : "")),
      badge("Duel estimate", duel.band,
        duel.party_wins ? `${percent(duel.hp_lost)} of party HP lost, ${duel.rounds} rounds`
                        : "Party loses on expected values",
        h("div", { class: "lossbar", role: "img", "aria-label": percent(duel.hp_lost) + " of party hit points lost" },
          h("span", { style: `width:${Math.min(100, duel.hp_lost * 100)}%` }))),
      badge("Lazy benchmark", lazy.maybe_deadly ? "Deadly" : "None",
        `CR sum ${lazy.cr_sum} against limit ${lazy.limit}` + (lazy.over_solo_cap ? ", one monster over the cap" : ""),
        null),
      h("div", { class: "badge" }, h("span", { class: "label" }, "Adventuring day"),
        h("span", { class: "value" }, percent(dmg.day_share)),
        h("span", { class: "detail" }, `of ${dmg.day_budget.toLocaleString("en")} XP daily budget`))),
    h("p", { class: "sb-line" }, duel.action_ratio + ". ",
      duel.hp_lost_range ? `Loss between ${percent(duel.hp_lost_range[0])} (damage spread) and `
        + `${percent(duel.hp_lost_range[1])} (monsters focus one PC at a time).` : ""),
    duel.warnings.length ? h("ul", { class: "warnings" }, duel.warnings.map((w) => h("li", {}, w))) : null,
    rating.disagreement.length ? [h("h4", { class: "spell-level" }, "Why the ratings differ"),
      h("ul", { class: "warnings" }, rating.disagreement.map((w) => h("li", {}, w)))] : null,
    rating.missing.length ? h("p", { class: "missing" }, "Missing from the database: " + rating.missing.join(", ")) : null,
    h("details", {}, h("summary", { class: "hint" }, "Numbers behind the duel estimate"),
      h("div", { class: "table-scroll" }, h("table", { class: "plan-table" },
        h("thead", {}, h("tr", {}, ["Monster", "HP", "Effective HP", "AC", "Damage per round", "To hit", "Reads like"]
          .map((t) => h("th", {}, t)))),
        h("tbody", {}, uniqueBy(duel.monsters, "name").map((m) => h("tr", {},
          h("td", {}, m.name), h("td", { class: "num" }, m.hp), h("td", { class: "num" }, m.ehp),
          h("td", { class: "num" }, m.ac), h("td", { class: "num" }, `${m.dpr} (${m.round_damage.join(", ")})`),
          h("td", { class: "num" }, signed(m.attack_bonus)),
          h("td", { class: "num" }, "CR " + ({ 0.125: "1/8", 0.25: "1/4", 0.5: "1/2" }[m.computed_cr] ?? m.computed_cr))))))),
      h("div", { class: "table-scroll" }, h("table", { class: "plan-table" },
        h("thead", {}, h("tr", {}, ["Character", "HP", "AC", "Damage if all hits", "To hit", "Assumed"]
          .map((t) => h("th", {}, t)))),
        h("tbody", {}, duel.party.map((p) => h("tr", {},
          h("td", {}, p.name), h("td", { class: "num" }, p.hp), h("td", { class: "num" }, p.ac),
          h("td", { class: "num" }, Math.round(p.damage * 10) / 10), h("td", { class: "num" }, signed(p.attack_bonus)),
          h("td", {}, p.assumed.join(", ") || "nothing")))))),
      h("p", { class: "hint" }, "The duel estimate plays the fight on averages: the party kills monsters in order of "
        + "threat, every living monster attacks, hit chances come from real AC and attack bonuses. It knows no "
        + "terrain, surprise, healing or clever spells. Treat it as a second opinion next to the DMG rating.")));
}

function uniqueBy(list, key) {
  const seen = new Set();
  return list.filter((item) => !seen.has(item[key]) && seen.add(item[key]));
}

function drawPlan() {
  const target = document.getElementById("plan");
  if (!plan.monsters.length) {
    replace(target, h("p", { class: "empty-state" }, "No monsters yet. Search on the right, Enter adds."));
    return;
  }
  const totalXp = plan.monsters.reduce((sum, m) => sum + ((known[m.id] || {}).xp || 0) * m.count, 0);
  replace(target, h("div", { class: "table-scroll" }, h("table", { class: "plan-table" },
    h("thead", {}, h("tr", {}, ["Count", "Monster", "CR", "HP", "AC", "XP", ""].map((t) => h("th", {}, t)))),
    h("tbody", {}, plan.monsters.map((entry) => {
      const m = known[entry.id] || { name: entry.id + " (missing)" };
      return h("tr", {},
        h("td", {}, h("input", { type: "number", min: 1, max: 50, value: entry.count,
          "aria-label": "Count of " + m.name,
          onchange: (e) => { entry.count = Math.max(1, Math.min(50, Number(e.target.value) || 1)); save(); } })),
        h("td", {}, h("button", { class: "c-name", type: "button", onclick: () => showMonster(entry.id) }, m.name)),
        h("td", { class: "num" }, m.cr ?? "?"), h("td", { class: "num" }, m.hp ?? ""),
        h("td", { class: "num" }, m.ac ?? ""),
        h("td", { class: "num" }, ((m.xp || 0) * entry.count).toLocaleString("en")),
        h("td", {}, h("button", { class: "mini-button danger", type: "button", "aria-label": "Remove " + m.name,
          onclick: () => { plan.monsters = plan.monsters.filter((x) => x !== entry); save(); } }, "Remove")));
    })),
    h("tfoot", {}, h("tr", {}, h("td", { colSpan: 5 }, "Total XP awarded"),
      h("td", { class: "num" }, totalXp.toLocaleString("en")), h("td", {}))))));
}

function drawParty() {
  const target = document.getElementById("party");
  if (!party.length) {
    replace(target, h("p", { class: "empty-state" }, "No characters exist yet. Add them on the ",
      h("a", { href: API.replace(/api$/, "") }, "party page"), "."));
    return;
  }
  replace(target, party.map((pc) => h("label", { class: "row" },
    h("input", { type: "checkbox", checked: plan.pcs.includes(pc.id), onchange: (e) => {
      plan.pcs = e.target.checked ? [...plan.pcs, pc.id] : plan.pcs.filter((id) => id !== pc.id);
      save();
    } }),
    `${pc.name}, ${pc.cls || "?"} ${pc.level}, HP ${pc.hp}, AC ${pc.ac}`)));
}

let saving = Promise.resolve();
function save() {
  drawPlan();
  // Saves run one after another so an older answer never overwrites a newer plan.
  saving = saving.then(async () => {
    const data = await guard(() => api("PUT", "/encounters/" + encounterId, plan));
    if (data) drawRating(data.rating);
  });
  return saving;
}

async function load() {
  const [data, pcs] = await Promise.all([
    guard(() => api("GET", "/encounters/" + encounterId)), guard(() => api("GET", "/pcs"))]);
  if (!data || !pcs) return;
  plan = data.encounter;
  known = data.monsters;
  party = pcs.pcs;
  document.getElementById("name").value = plan.name;
  document.getElementById("notes").value = plan.notes || "";
  document.getElementById("resources").value = plan.resources || "normal";
  document.title = plan.name + " :: Encounter";
  drawPlan(); drawParty(); drawRating(data.rating);
}

document.getElementById("name").addEventListener("change", (e) => { plan.name = e.target.value; save(); });
document.getElementById("notes").addEventListener("change", (e) => { plan.notes = e.target.value; save(); });
document.getElementById("resources").addEventListener("change", (e) => { plan.resources = e.target.value; save(); });
document.getElementById("run").addEventListener("click", async () => {
  await save();
  const created = await guard(() => api("POST", `/encounters/${encounterId}/run`));
  if (created) location.href = API.replace(/api$/, "") + "combat/" + created.id;
});

const picker = monsterPicker({
  onShow: (row) => showMonster(row.id),
  onPick: (row, count) => {
    known[row.id] = { id: row.id, name: row.name, cr: crText(row), xp: row.xp, hp: row.hp, ac: row.ac };
    const existing = plan.monsters.find((m) => m.id === row.id);
    if (existing) existing.count = Math.min(50, existing.count + count);
    else plan.monsters.push({ id: row.id, count });
    save();
  },
});
document.getElementById("picker").append(picker);
load().then(() => picker.focusSearch());
