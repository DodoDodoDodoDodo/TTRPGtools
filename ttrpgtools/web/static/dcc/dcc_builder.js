// DCC builder. Two modes on one page:
//   create: collect the 0-level rolls, then save the character
//   build:  equipment, languages and level-up for a saved character
// Every rule lives on the server; this file only gathers choices and shows what the server computed.
"use strict";

const { h, api, tour } = DCC;
const page = document.getElementById("builder");
const characterId = page.dataset.character || null;
const rail = h("ol", { class: "steps" }), stage = h("section", { class: "panel stage" }), summary = h("aside", { class: "panel summary" });
page.append(rail, stage, summary);

let content = null;      // tables from the server
let state = null;        // saved character: { id, character, view }
let stepIndex = 0;
let steps = [];
let error = "";
const draft = { name: "", alignment: "", moon: "", abilities: {}, occupation: null, occupation_roll: null, extras: {}, augur_roll: null,
                hp_roll: null, copper: null, equipment_roll: null };
let lvl = null;          // level-up choices in progress
let preview = null;      // server's answer to those choices

const die = (sides) => { const a = new Uint32Array(1); crypto.getRandomValues(a); return 1 + (a[0] % sides); };
const dice = (n, sides) => Array.from({ length: n }, () => die(sides)).reduce((a, b) => a + b, 0);
const plus = (n) => (n >= 0 ? "+" + n : String(n));
const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
const mod = (score) => (content.ability_mods[String(Math.max(3, Math.min(18, score)))] || { mod: 0 }).mod;
const ABILITY_USE = { strength: "melee attack and damage", agility: "AC, missiles, initiative, Reflex", stamina: "hit points, Fortitude",
                      personality: "Willpower, cleric magic", intelligence: "languages, wizard magic", luck: "crits, fumbles, the birth augur" };
const ALIGNMENT_TEXT = { lawful: "Order, loyalty, humanity first.", neutral: "Balance; judges each case on its own.", chaotic: "Personal power; deals with strange forces." };
const CLASS_TEXT = { cleric: "Servant of a god. Heals, turns the unholy, casts by spell check.", thief: "Skills by alignment, backstab, Luck that comes back.",
                     warrior: "Deed die on every attack, Mighty Deeds, best crits.", wizard: "Random spells, mercurial magic, spellburn, corruption.",
                     dwarf: "Deed die, shield bash, sees in the dark, smells gold.", elf: "Fights and casts, bonded to a patron, hurt by iron.",
                     halfling: "Two weapons, stealth, the party's good luck charm." };

// A value that is either rolled here or typed in from real dice. opts.roll replaces the plain dice sum;
// opts.after runs once the value is final (roll click, or leaving the field) and defaults to a redraw.
// The three moons as cards: a name and a vibe, nothing about their cycles. The choice is made once.
function moonCards(chosen, pick) {
  return h("div", { class: "card-grid", id: "moons", "data-explain": "full moon" }, content.moons.map((m) =>
    h("button", { type: "button", class: "card" + (chosen === m.id ? " selected" : ""), onclick: () => pick(m.id) },
      h("b", {}, m.name), h("small", {}, m.blurb))));
}

const rolledHere = {};   // label -> the value standing in a field whose Roll button was used
function rollable(label, sides, count, value, set, opts = {}) {
  const after = opts.after || (() => draw());
  const input = h("input", { type: "number", min: opts.min ?? count, max: opts.max ?? count * sides, value: value ?? "", "aria-label": label,
                             oninput: (e) => { set(e.target.value === "" ? null : Number(e.target.value)); draw(false); },
                             onchange: (e) => { fiddled(label, e.target.value === "" ? null : Number(e.target.value)); after(); } });
  return h("div", { class: "rollable", id: opts.id, "data-explain": opts.explain || label },
    h("b", {}, label),
    h("button", { class: "roll", type: "button", onclick: async () => {
        const again = label in rolledHere;
        const got = opts.roll ? opts.roll() : dice(count, sides);
        rolledHere[label] = got; set(got);
        if (again) await rerolled();
        after();
      } },
      `Roll ${count === 1 ? "" : count}d${sides}`),
    h("span", { class: "hint" }, "or enter your own roll"), input, h("span", { class: "result" }, opts.result || ""));
}

// The tax office notices when a rolled number is "corrected" upwards by hand. Lowering it again earns one copper back.
async function fiddled(label, now) {
  if (!(label in rolledHere) || now === null || !characterId) return;
  const before = rolledHere[label];
  rolledHere[label] = now;
  if (now === before) return;
  try {
    const answer = await api("POST", `character/${characterId}/op`, { op: "taxes_for_no_reason", direction: now > before ? "up" : "down" });
    if (now > before) taxBox(answer.result.debt);
  } catch (err) { /* the tax office is closed; the number stands */ }
}

const coinsText = DCC.gp;

// A taken villager's Luck and birth augur are sealed until the character is finished (1st level): the server leaves
// them out, and this page shows a question mark. On the Finish step they are told.
const sealed = () => !!(state && state.sealed);
let wasSealed = false;

// During creation the birth augur can be rolled again. Every time, the tax debt doubles, and the figure shows it.
let debtJump = null;   // { from, to } while the doubled debt still has to be counted up on screen
const debtFigure = () => h("b", { class: "debt-figure" }, coinsText(debtJump ? debtJump.from : state.character.tax_debt_cp));

// Count every debt figure on the page up to the new sum, blinking, so nobody misses what a second roll cost.
function showDebtJump() {
  if (!debtJump) return;
  const { from, to } = debtJump, began = performance.now(), figures = [...document.querySelectorAll(".debt-figure")];
  debtJump = null;
  for (const figure of figures) figure.classList.add("blinking");
  const tick = (now) => {
    const part = Math.min(1, (now - began) / 2200);
    for (const figure of figures) figure.textContent = coinsText(Math.round(from + (to - from) * part * part));
    if (part < 1) requestAnimationFrame(tick);
    else setTimeout(() => figures.forEach((figure) => figure.classList.remove("blinking")), 1500);
  };
  requestAnimationFrame(tick);
}

// A die rolled a second time (hit points, mercurial magic, anything with a Roll button): the debt doubles.
async function rerolled() {
  if (!characterId) return;
  try {
    const answer = await api("POST", `character/${characterId}/op`, { op: "reroll" });
    debtJump = { from: answer.result.debt_before, to: answer.result.debt_after };
    state = answer;
  } catch (err) { /* the tax office is closed */ }
}

function augurBox() {
  const c = state.character;
  const figure = debtFigure();
  return h("div", { class: "note", id: "augur-box", "data-explain": "Birth augur lucky roll Luck modifier" },
    h("p", {}, h("b", {}, "Birth augur: "), sealed() ? "sealed. It is told, together with the Luck score, once the character is finished." : state.view.augur_effect + "."),
    h("div", { class: "button-row" },
      h("button", { class: "roll", type: "button", onclick: async () => {
        error = "";
        try {
          const answer = await api("POST", `character/${characterId}/op`, { op: "reroll_augur" });
          debtJump = { from: answer.result.debt_before, to: answer.result.debt_after };
          state = answer;
        } catch (err) { error = err.message; }
        draw();
      } }, sealed() ? "Have the birth augur drawn again, unseen" : "Roll the birth augur again"),
      h("span", {}, "Owed to the tax office: ", figure)),
    h("p", { class: "hint" }, "Fate can be asked twice. The tax office is told every time."));
}

function taxBox(debt) {
  const box = h("div", { class: "tax-box", role: "alertdialog", "aria-label": "Tax notice" },
    h("div", {}, h("p", { class: "shout" }, "FOR NO REASON IN PARTICULAR, YOUR TAXES HAVE INCREASED BY ANOTHER 6000 GP"),
      h("p", {}, `You now owe the tax office ${debt}.`),
      h("button", { class: "button", type: "button", onclick: () => box.remove() }, "Understood")));
  document.body.append(box);
  box.querySelector("button").focus();
}

// ------------------------------------------------------------------ create mode
const occupationOf = () => draft.occupation || (draft.occupation_roll && content.occupations.find((o) => o.roll[0] <= draft.occupation_roll && draft.occupation_roll <= o.roll[1])) || null;
const augurOf = () => content.augurs.find((a) => a.roll === draft.augur_roll) || null;
const itemOf = () => content.equipment.find((e) => e.roll === draft.equipment_roll) || null;
const abilitiesDone = () => content.abilities.every((a) => draft.abilities[a] >= 3 && draft.abilities[a] <= 18);

const createSteps = [
  { title: "Name, alignment, moon", done: () => draft.name.trim() && draft.alignment && draft.moon,
    guide: [{ target: "#name", text: "Every adventurer starts as a nobody. Give yours a name." },
            { target: "#alignments", text: "Pick a side in the struggle of Law and Chaos. It decides titles, cleric gods and thief skills later." },
            { target: "#moons", text: "Three moons cross this sky. Your character is bound to one, for life." },
            { target: "#assist-explain", text: "Unsure about a word or number? Click this, then click the thing itself." },
            { target: "#next", text: "When all three are set, continue here." }],
    render: () => [h("h2", {}, "Who is this?"),
      h("label", {}, "Name ", h("input", { id: "name", type: "text", maxLength: 60, value: draft.name, oninput: (e) => { draft.name = e.target.value; draw(false); } })),
      h("h3", { style: "margin-top:1rem" }, "Alignment"),
      h("div", { class: "card-grid", id: "alignments", "data-explain": "Alignment: lawful, neutral, chaotic" }, content.alignments.map((a) =>
        h("button", { type: "button", class: "card" + (draft.alignment === a ? " selected" : ""), onclick: () => { draft.alignment = a; draw(); } },
          h("b", {}, cap(a)), h("small", {}, ALIGNMENT_TEXT[a])))),
      h("h3", { style: "margin-top:1rem" }, "Moon"), moonCards(draft.moon, (id) => { draft.moon = id; draw(); })] },
  { title: "Abilities", done: abilitiesDone,
    guide: [{ target: "#roll-abilities", text: "Roll 3d6 six times, in order. No swapping, no rerolls: the dice decide who you are." },
            { target: ".ability", text: "Each score gives a modifier. It is added to the rolls named below it." },
            { target: "#next", text: "Rolled at the table instead? Type the six numbers in, then continue." }],
    render: () => [h("h2", {}, "Ability scores"), h("p", {}, "3d6 for each, in this order. Low scores are part of the game."),
      h("div", { class: "button-row" }, h("button", { class: "roll", id: "roll-abilities", type: "button",
        onclick: () => { for (const a of content.abilities) draft.abilities[a] = dice(3, 6); draw(); } }, "Roll all six")),
      h("div", { class: "abilities", style: "margin-top:.8rem" }, content.abilities.map((a) => h("div", { class: "ability", "data-explain": cap(a) + " ability score and modifier" },
        h("span", { class: "label", title: cap(a) }, content.labels[a]),
        h("input", { type: "number", min: 3, max: 18, value: draft.abilities[a] ?? "", "aria-label": cap(a),
                     oninput: (e) => { draft.abilities[a] = Number(e.target.value); draw(false); }, onchange: () => draw() }),
        h("span", { class: "mod" }, draft.abilities[a] ? plus(mod(draft.abilities[a])) : ""),
        h("span", { class: "what" }, h("b", {}, cap(a)), h("br"), ABILITY_USE[a]))))] },
  { title: "Occupation", done: () => occupationOf() && occupationOf().extras.every((x) => draft.extras[x.key]),
    guide: [{ target: "#occupation-roll", text: "Roll d100 for the job your character had before adventure called." },
            { target: "#occupation-table", text: "Or pick one, if your judge allows it. Dwarven, elven and halfling jobs fix the race and later the class." }],
    render: () => {
      const occ = occupationOf();
      return [h("h2", {}, "Occupation"),
        rollable("Occupation (d100)", 100, 1, draft.occupation_roll, (v) => { draft.occupation_roll = v; draft.occupation = null; draft.extras = {}; },
                 { id: "occupation-roll", explain: "Occupation table 1-3" }),
        occ ? h("div", { class: "note", "data-explain": "Occupation trained weapon and trade goods" }, h("b", {}, occ.occupation), `: trained weapon ${occ.weapon}, trade goods ${occ.trade_goods.replace(/\*/g, "")}.`,
          occ.extras.map((x) => rollable(x.label, x.die, 1, draft.extras[x.key], (v) => { draft.extras[x.key] = v; },
            { result: x.options && draft.extras[x.key] ? x.options[draft.extras[x.key] - 1] : "" }))) : null,
        h("details", { id: "occupation-table" }, h("summary", {}, "Choose from the table instead"),
          h("div", { class: "picker" }, h("table", {}, h("tbody", {}, content.occupations.map((o) =>
            h("tr", { class: occ === o ? "selected" : "", onclick: () => { draft.occupation = o; draft.occupation_roll = null; draft.extras = {}; draw(); } },
              h("td", { class: "num" }, o.roll[0] === o.roll[1] ? o.roll[0] : o.roll.join("-")), h("td", {}, o.occupation), h("td", {}, o.weapon),
              h("td", {}, o.trade_goods.replace(/\*/g, ""))))))))];
    } },
  { title: "Birth augur", done: augurOf,
    guide: [{ target: "#augur-roll", text: "Roll d30. Your Luck modifier at birth is tied to one kind of roll for life, even when Luck changes later." }],
    render: () => {
      const augur = augurOf(), luck = mod(draft.abilities.luck || 10);
      return [h("h2", {}, "Birth augur"),
        rollable("Birth augur (d30)", 30, 1, draft.augur_roll, (v) => { draft.augur_roll = v; }, { id: "augur-roll", explain: "Birth augur and lucky roll, table 1-2" }),
        augur ? h("div", { class: "note", "data-explain": "Birth augur lucky roll Luck modifier" }, h("b", {}, augur.augur), `: your Luck modifier of ${plus(luck)} applies to ${augur.applies_to.replace(/\*/g, "").toLowerCase()}, for life.`,
          luck === 0 ? " With a modifier of 0 it has no effect." : "") : null];
    } },
  { title: "Hit points and coin", done: () => draft.hp_roll >= 1 && draft.hp_roll <= 4 && draft.copper >= 5 && draft.copper <= 60 && itemOf(),
    guide: [{ target: "#hp-roll", text: "1d4 hit points, changed by Stamina. At 0 hit points a 0-level character is dead." },
            { target: "#copper-roll", text: "5d12 copper pieces is all the money you own." },
            { target: "#item-roll", text: "One random piece of gear from the d24 table." },
            { target: "#next", text: "This saves the character. Shopping and languages come next." }],
    render: () => {
      const sta = mod(draft.abilities.stamina || 10), item = itemOf();
      return [h("h2", {}, "Hit points, coin, one item"),
        rollable("Hit points (1d4)", 4, 1, draft.hp_roll, (v) => { draft.hp_roll = v; },
                 { id: "hp-roll", explain: "0-level hit points 1d4 Stamina", result: draft.hp_roll ? `${plus(sta)} Stamina, at least 1` : "" }),
        rollable("Copper pieces (5d12)", 12, 5, draft.copper, (v) => { draft.copper = v; }, { id: "copper-roll", explain: "Starting gold 5d12 copper pieces" }),
        rollable("Equipment (d24)", 24, 1, draft.equipment_roll, (v) => { draft.equipment_roll = v; },
                 { id: "item-roll", explain: "Starting equipment table 3-4", result: item ? item.item : "" })];
    } },
];

async function createCharacter() {
  const occ = occupationOf();
  const made = await api("POST", "character", { ...draft, occupation: draft.occupation_roll ? null : occ.occupation });
  location.href = DCC.root + made.id + "/build";
}

// ------------------------------------------------------------------ build mode: a saved character
async function op(body) {
  error = "";
  try { state = await api("POST", `character/${characterId}/op`, body); } catch (err) { error = err.message; }
  draw();
}

// The price table is built once and re-used, so a redraw of the step does not fetch it again.
let marketNode = null;
function marketBox() {
  if (!marketNode) {
    marketNode = h("div", { id: "to-town" });
    DCC.market(marketNode, characterId, async () => { state = await api("GET", "character/" + characterId); draw(); });
  }
  return marketNode;
}

function equipmentStep() {
  const c = state.character, v = state.view;
  let kind = equipmentStep.kind || "weapon", search = equipmentStep.search || "";
  const rows = content.catalog.filter((e) => e.kind === kind && e.name.toLowerCase().includes(search.toLowerCase()));
  const elf = c.class === "elf";
  return [h("h2", {}, "Equipment"),
    h("p", { id: "purse", "data-explain": "Coinage copper silver gold" }, h("b", {}, "Purse: "), DCC.gp(v.coins_cp) + " ",
      h("span", { class: "hint" }, "(1 gp = 100 cp, written like cents)")),
    h("table", { id: "carried" }, h("thead", {}, h("tr", {}, ["Carried", "Kind", "Qty", "", ""].map((t) => h("th", {}, t)))),
      h("tbody", {}, v.inventory.map((item, index) => h("tr", {},
        h("td", {}, item.name, item.mithril ? h("span", { class: "tag" }, " mithril") : null), h("td", { class: "tag" }, item.kind), h("td", { class: "num" }, item.qty),
        h("td", {}, ["weapon", "armor", "shield"].includes(item.kind) ? h("button", { class: "mini-button", type: "button",
          onclick: () => op({ op: "equip", index, equipped: !item.equipped }) }, item.equipped ? (item.kind === "weapon" ? "In hand" : "Worn") : "Packed") : null),
        h("td", {}, h("button", { class: "mini-button danger", type: "button", "aria-label": "Remove " + item.name,
          onclick: () => confirm(`Remove ${item.name}? No coin comes back.`) && op({ op: "remove_item", index }) }, "Remove")))))),
    content.town.shops ? [h("h3", { style: "margin-top:1rem" }, "Buy in town"), marketBox()] : null,
    content.town.shops && !content.town.judge ? null : [h("h3", { style: "margin-top:1rem" }, content.town.shops ? "Rulebook list (judge only)" : "Shop"),
    h("div", { class: "button-row", id: "shop-filter" },
      ["weapon", "armor", "shield", "ammo", "gear", "mount"].map((k) => h("button", { type: "button", class: "mini-button", "aria-pressed": String(k === kind),
        style: k === kind ? "border-color:var(--blue);background:#fff" : "", onclick: () => { equipmentStep.kind = k; draw(); } }, cap(k))),
      h("input", { type: "search", placeholder: "Search", value: search, "aria-label": "Search the shop",
                   oninput: (e) => { equipmentStep.search = e.target.value; draw();
                                     const box = document.querySelector("#shop-filter input"); box.focus(); box.setSelectionRange(box.value.length, box.value.length); } })),
    h("div", { class: "picker", id: "shop" }, h("table", {}, h("tbody", {}, rows.map((e) => h("tr", { "data-explain": e.kind + " " + e.name },
      h("td", {}, e.name), h("td", { class: "hint" }, e.detail), h("td", { class: "num" }, e.cost),
      h("td", {}, h("button", { class: "mini-button", type: "button", onclick: () => op({ op: "buy", key: e.key, count: 1 }) }, "Buy"),
        elf && ["weapon", "armor"].includes(e.kind) ? h("button", { class: "mini-button", type: "button", title: "An elf's first weapon and armor come in mithril at the normal price",
          onclick: () => op({ op: "buy", key: e.key, count: 1, mithril: true }) }, "Buy in mithril") : null,
        h("button", { class: "mini-button", type: "button", title: "Add without paying (found, given, already owned)",
          onclick: () => op({ op: "buy", key: e.key, count: 1, pay: false }) }, "Take free")))))))],
  ];
}

function languagesStep() {
  const c = state.character, slots = state.view.languages, open = slots.total - c.languages.length;
  const add = async () => {
    error = "";
    for (let tries = 0; tries < 40; tries++) {
      const roll = die(100);
      const got = await api("POST", "language", { column: slots.column, roll, alignment: c.alignment });
      if (got.language && !c.languages.includes(got.language)) return op({ op: "languages", languages: [...c.languages, got.language] });
    }
  };
  const custom = h("input", { type: "text", placeholder: "Language", "aria-label": "Language name" });
  return [h("h2", {}, "Languages"),
    h("p", { "data-explain": "Languages known Intelligence modifier Appendix L" }, `${cap(c.name)} knows ${slots.total} language${slots.total === 1 ? "" : "s"}: `, h("b", {}, c.languages.join(", ")), "."),
    slots.note ? h("p", { class: "note" }, slots.note) : null,
    open > 0 ? h("div", { class: "rollable", id: "language-roll" }, h("b", {}, `${open} more to learn`),
      h("button", { class: "roll", type: "button", onclick: add }, "Roll d% on Appendix L"), h("span", { class: "hint" }, "or name it"), custom,
      h("button", { class: "mini-button", type: "button", onclick: () => custom.value.trim() && op({ op: "languages", languages: [...c.languages, custom.value.trim()] }) }, "Add"))
      : h("p", { class: "hint" }, "Nothing left to choose here."),
    c.languages.filter((l) => !slots.automatic.includes(l)).map((l) => h("button", { class: "mini-button danger", type: "button",
      onclick: () => op({ op: "languages", languages: c.languages.filter((x) => x !== l) }) }, "Forget " + l))];
}

async function refreshPreview() {
  error = "";
  try { preview = await api("POST", `character/${characterId}/level`, { ...lvl, preview: true }); }
  catch (err) { error = err.message; }
  draw();
}

function classStep() {
  const v = state.view;
  return [h("h2", {}, "Choose a class"),
    state.character.level === 0 ? augurBox() : null,
    v.race ? h("p", { class: "note" }, `A ${v.race} occupation becomes a ${v.race}: demi-humans advance in their own class.`) : null,
    h("div", { class: "card-grid", id: "classes" }, Object.entries(content.classes).map(([k, info]) =>
      h("button", { type: "button", class: "card" + (lvl.class === k ? " selected" : ""), disabled: !v.class_choices.includes(k), "data-explain": k + " class",
                    onclick: () => { lvl = { ...lvl, class: k, spells: null, mercurial: {}, mercurial_more: {} }; buildSteps(); refreshPreview(); } },
        h("b", {}, cap(k)), h("small", {}, `d${info.hit_die} hit points per level. ${CLASS_TEXT[k]}`)))),
    lvl.class ? h("details", {}, h("summary", {}, `What the book says about the ${lvl.class}`),
      Object.entries(content.classes[lvl.class].prose).map(([name, text]) => h("p", {}, h("b", {}, name + ". "), text))) : null];
}

function hitPointStep() {
  const sides = preview.hit_die, gained = lvl.hp_roll ? preview.character.hp_max - state.character.hp_max : null;
  const c = state.character, need = preview.xp_needed;
  return [h("h2", {}, `Level ${preview.character.level}: hit points`),
    need > c.xp ? h("label", { class: "note", id: "raise-xp" }, h("input", { type: "checkbox", checked: !!lvl.raise_xp, onchange: (e) => { lvl.raise_xp = e.target.checked; draw(); } }),
      ` ${c.name} has ${c.xp} XP; this level needs ${need}. Tick if the judge grants the level: XP is then set to ${need}.`) : null,
    rollable(`Hit points (1d${sides})`, sides, 1, lvl.hp_roll, (v) => { lvl.hp_roll = v; },
             { after: refreshPreview, id: "level-hp", explain: "Hit points per level hit die Stamina", result: gained ? `gains ${gained} (Stamina and augur included, at least 1)` : "" }),
    c.level === 0 && content.town.judge && content.classes[lvl.class].starting_gold ? h("label", { "data-explain": "Starting gold for campaigns above level 0" },
      `Only if the campaign starts at 1st level: starting gold (${content.classes[lvl.class].starting_gold[0]} gp) `,
      h("input", { type: "number", min: 0, value: lvl.gold ?? "", oninput: (e) => { lvl.gold = e.target.value === "" ? null : Number(e.target.value); } })) : null];
}

function choiceStep() {
  const klass = lvl.class, c = state.character, out = [h("h2", {}, `${cap(klass)} choices`)];
  if (klass === "cleric") {
    const gods = (content.deities[c.alignment] || { gods: [] });
    // a god is chosen once, at 1st level (p. 28); afterwards it is only shown
    out.push(c.deity ? h("p", { id: "deity", "data-explain": "Choosing a god cleric alignment" }, h("b", {}, "God: "), c.deity, h("span", { class: "hint" }, "  chosen at 1st level"))
      : h("label", { id: "deity", "data-explain": "Choosing a god cleric alignment" }, `God (${c.alignment}) `,
        h("select", { onchange: (e) => { lvl.deity = e.target.value; refreshPreview(); } }, h("option", { value: "" }, "Choose"),
          gods.gods.map((g) => h("option", { value: g, selected: lvl.deity === g }, g)))),
      h("p", { class: "hint" }, `Weapons of the faith: ${gods.weapons_text}. Unholy to this cleric: ${gods.unholy}`));
  }
  if (["wizard", "elf"].includes(klass)) {
    const patrons = [...new Set(preview.spell_options.filter((s) => s.patron).map((s) => s.patron))];
    out.push(h("label", { id: "patron", "data-explain": "Supernatural patrons patron bond invoke patron" }, klass === "elf" ? "Patron (every elf has one) " : "Patron (only with the spell Patron Bond) ",
      h("input", { type: "text", list: "patron-list", value: lvl.patron ?? c.patron ?? "", onchange: (e) => { lvl.patron = e.target.value; refreshPreview(); } }),
      h("datalist", { id: "patron-list" }, patrons.map((p) => h("option", { value: p })))));
  }
  if (["warrior", "dwarf"].includes(klass) && !c.lucky_weapon) {
    out.push(h("label", { id: "lucky-weapon", "data-explain": "Warrior Luck lucky weapon" }, `Lucky weapon: ${sealed() ? "your Luck modifier, whatever it turns out to be," : "Luck " + plus(preview.character.first_level_luck_mod)} to attacks with one weapon type, for life `,
      h("select", { onchange: (e) => { lvl.lucky_weapon = e.target.value; refreshPreview(); } }, h("option", { value: "" }, "Choose"),
        content.weapons.map((w) => h("option", { value: w, selected: lvl.lucky_weapon === w }, w)))));
  }
  if (out.length === 1) out.push(h("p", { class: "hint" }, "Nothing to choose for this class at this level."));
  return out;
}

function spellStep() {
  const info = preview.view.spellcasting, klass = lvl.class, c = state.character;
  const free = klass === "elf" ? ["Patron Bond", "Invoke Patron"] : [];
  const chosen = lvl.spells || preview.character.spells.filter((s) => !free.includes(s));
  const patron = (lvl.patron ?? c.patron ?? "").toLowerCase();
  const bonded = klass === "elf" || chosen.includes("Patron Bond") || chosen.includes("Invoke Patron");
  const options = preview.spell_options.filter((s) => s.level <= info.max_level && !free.includes(s.name)
    && (s.class !== "patron" || (bonded && patron && s.patron.toLowerCase().includes(patron))));
  const pair = chosen.includes("Patron Bond") && chosen.includes("Invoke Patron") ? 1 : 0;
  const limit = (level) => (info.kind === "cleric" ? info.per_level[level] : info.total);
  const used = (level) => (info.kind === "cleric" ? chosen.filter((n) => options.find((s) => s.name === n && s.level === level)).length : chosen.length - pair);
  const set = (list) => { lvl.spells = list; for (const n of Object.keys(lvl.mercurial)) if (![...list, ...free].includes(n)) delete lvl.mercurial[n]; refreshPreview(); };
  const toggle = (name) => {
    let list = chosen.includes(name) ? chosen.filter((n) => n !== name) : [...chosen, name];
    if (klass === "wizard" && ["Patron Bond", "Invoke Patron"].includes(name))  // the pair comes and goes together, as one slot
      list = chosen.includes(name) ? list.filter((n) => !["Patron Bond", "Invoke Patron"].includes(n)) : [...new Set([...list, "Patron Bond", "Invoke Patron"])];
    set(list);
  };
  const rollOne = (level) => {
    const pool = options.filter((s) => s.level === level && !chosen.includes(s.name));
    if (pool.length && used(level) < limit(level)) toggle(pool[die(pool.length) - 1].name);
  };
  if (info.blocked) return [h("h2", {}, "Spells"), h("p", { class: "error-banner" }, info.blocked)];
  const levels = [...new Set(options.map((s) => s.level))].sort();
  const mercurialFor = (roll) => (preview.mercurial_table || []).find((row) => {
    const m = /^(\d+)(?:-(\d+))?/.exec(row.roll), lo = Number(m[1]) || 100, hi = Number(m[2] ?? m[1]) || 100;
    return lo <= roll && roll <= hi;
  });
  const fresh = [...free, ...chosen].filter((n) => !(c.spell_details || {})[n] || !c.spell_details[n].mercurial);
  const luck = preview.view.mods.luck;
  return [h("h2", {}, "Spells"),
    h("p", { id: "spell-count", "data-explain": "Spells known wizard table max spell level" }, info.kind === "cleric"
      ? "A cleric chooses spells per spell level, as the class table allows."
      : `${used()} of ${info.total} known. The book finds wizard spells by die roll: pick the spell level, then roll. Choose by hand only for a spell found in play.`,
      free.length ? ` Always known on top: ${free.join(", ")}.` : ""),
    levels.map((level) => h("div", { class: "spell-level" },
      h("div", { class: "button-row" }, h("h3", {}, `Level ${level}`), h("span", { class: "hint" }, info.kind === "cleric" ? `${used(level)} of ${limit(level)}` : ""),
        h("button", { class: "roll", type: "button", disabled: used(level) >= limit(level), onclick: () => rollOne(level) }, `Roll a level ${level} spell`)),
      h("div", { class: "checks" }, options.filter((s) => s.level === level).map((s) => h("label", { title: s.general || "", "data-explain": "spell " + s.name },
        h("input", { type: "checkbox", checked: chosen.includes(s.name), disabled: !chosen.includes(s.name) && used(level) >= limit(level), onchange: () => toggle(s.name) }),
        s.name, s.patron ? h("span", { class: "tag" }, " " + s.patron) : null, s.check_penalty ? h("span", { class: "tag" }, " -2 check") : null))))),
    ["wizard", "elf"].includes(klass) && fresh.length ? h("div", { id: "mercurial", "data-explain": "Mercurial magic table 5-2 Luck" },
      h("h3", { style: "margin-top:1rem" }, "Mercurial magic"),
      h("p", { class: "hint" }, sealed() ? "Each new spell behaves in its own way for this caster: d%, shifted by ten times the Luck modifier. The Roll button applies it unseen."
        : `Each new spell behaves in its own way for this caster: d% ${plus(luck * 10)} (Luck modifier times 10).`),
      fresh.map((name) => {
        const roll = lvl.mercurial[name], row = roll ? mercurialFor(roll) : null;
        // The Roll button applies the Luck adjustment; a typed number counts as the final result.
        const first = rollable(name, 100, 1, roll, (v) => { lvl.mercurial[name] = v === null ? null : Math.max(1, Math.min(100, v)); },
                        { min: 1, max: 100, result: row ? row.text : "", roll: () => die(100) + luck * 10 });
        if (!roll || roll < 99) return first;
        // 99 and 00 say "roll again twice": two further results, on d% for 99 and on 4d20 for 00, both with the Luck
        // adjustment. A further 99 or 00 is rolled again, so there are always two effects.
        lvl.mercurial_more = lvl.mercurial_more || {};
        const more = (lvl.mercurial_more[name] = lvl.mercurial_more[name] || [null, null]);
        const again = () => { let got; do { got = (roll === 100 ? dice(4, 20) : die(100)) + luck * 10; } while (got >= 99); return Math.max(1, got); };
        return [first, [0, 1].map((slot) => {
          const got = more[slot], found = got ? mercurialFor(got) : null;
          return rollable(`${name}, ${slot ? "second" : "first"} of the two further rolls`, roll === 100 ? 20 : 100, roll === 100 ? 4 : 1, got,
            (v) => { more[slot] = v === null ? null : Math.max(1, Math.min(98, v)); },
            { min: 1, max: 98, result: found ? found.text : "", roll: again, explain: "Mercurial magic roll again twice" });
        })];
      })) : null,
    klass === "elf" && !c.lucky_spell ? h("label", { "data-explain": "Elf Luck one spell" }, `Lucky spell (an elf may choose one): ${sealed() ? "your Luck modifier, whatever it turns out to be," : "Luck " + plus(preview.character.first_level_luck_mod)} to its spell checks, for life `,
      h("select", { onchange: (e) => { lvl.lucky_spell = e.target.value; refreshPreview(); } }, h("option", { value: "" }, "Choose"),
        [...free, ...chosen].map((n) => h("option", { value: n, selected: lvl.lucky_spell === n }, n)))) : null];
}

function confirmStep() {
  const a = preview.before, b = preview.view;
  const rows = [["Hit points", state.character.hp_max, lvl.hp_roll ? preview.character.hp_max : "roll first"], ["Attack", a.attack, b.attack],
    ["Action dice", a.action_dice, b.action_dice], ["Crit", `${a.crit_die} / ${a.crit_table}`, `${b.crit_die} / ${b.crit_table}`],
    ["Reflex", a.saves_text.reflex, b.saves_text.reflex], ["Fortitude", a.saves_text.fortitude, b.saves_text.fortitude], ["Willpower", a.saves_text.willpower, b.saves_text.willpower],
    ["Title", a.title || "none", b.title || "none"], ["Threat range", a.threat_range || "20", b.threat_range || "20"], ["Luck die", a.luck_die || "", b.luck_die || ""],
    ["Languages", a.languages.total, b.languages.total]].filter((r) => r[1] !== "" || r[2] !== "");
  return [h("h2", {}, `Become a level ${preview.character.level} ${lvl.class}`),
    h("table", { class: "diff", id: "diff" }, h("thead", {}, h("tr", {}, ["", "Now", "After"].map((t) => h("th", {}, t)))),
      h("tbody", {}, rows.map((r) => h("tr", { class: String(r[1]) !== String(r[2]) ? "changed" : "" }, r.map((cell) => h("td", {}, String(cell))))))),
    h("div", { class: "stage-nav" }, h("span", {}), h("button", { class: "button", id: "confirm", type: "button", disabled: !lvl.hp_roll,
      onclick: async () => {
        error = "";
        try {
          state = await api("POST", `character/${characterId}/level`, lvl); lvl = null; preview = null; buildSteps(); stepIndex = steps.length - 1;
          for (const label of Object.keys(rolledHere)) delete rolledHere[label];  // the next level's dice are new dice: their first roll is free again
        }
        catch (err) { error = err.message; }
        draw();
      } }, "Confirm the level"))];
}

function finishStep() {
  const v = state.view, c = state.character;
  return [h("h2", {}, c.name), h("p", {}, c.class ? `Level ${c.level} ${c.class}${v.title ? ", " + v.title : ""}` : "0-level " + c.occupation.occupation, `, ${c.alignment}. `,
      `${c.hp_max} hit points, AC ${v.ac}.`),
    wasSealed && !sealed() ? h("div", { class: "note reveal", id: "reveal", "data-explain": "Birth augur lucky roll Luck modifier" },
      h("p", {}, h("b", {}, "Now it can be told. "), `${c.name} has Luck ${c.luck_current} (${v.mods_text.luck}).`),
      h("p", {}, h("b", {}, "Birth augur: "), v.augur_effect + ".")) : null,
    sealed() ? h("p", { class: "note", id: "sealed-note" }, "Luck and the birth augur stay sealed until this character has a class and 1st level.") : null,
    v.todo.length ? [h("h3", {}, "Still open"), h("ul", { id: "todo" }, v.todo.map((t) => h("li", {}, t)))] : h("p", { class: "note" }, "Nothing open. Ready for the table."),
    c.moon ? h("p", { "data-explain": "full moon" }, h("b", {}, "Moon: "), state.moon.text + ".", state.moon_rule ? " " + state.moon_rule.text : "") : [h("h3", {}, "Choose a moon"), moonCards("", (id) => op({ op: "set", moon: id }))],
    v.warnings.length ? [h("h3", {}, "Rules to keep in mind"), h("ul", {}, v.warnings.map((t) => h("li", {}, t)))] : null,
    h("div", { class: "button-row", style: "margin-top:1rem" },
      sealed() ? null : h("a", { class: "button", id: "open-sheet", href: DCC.root + characterId }, "Open the character sheet"),
      c.level < 10 ? h("button", { class: "mini-button", id: "level-up", type: "button", onclick: startLevel }, c.level ? `Level up to ${c.level + 1}` : "Choose a class (level 1)") : null)];
}

function startLevel() {
  const c = state.character;
  lvl = { class: c.class || (state.view.class_choices.length === 1 ? state.view.class_choices[0] : null), hp_roll: null, raise_xp: false,
          spells: null, mercurial: {}, mercurial_more: {} };
  preview = null;
  buildSteps();
  stepIndex = steps.findIndex((s) => s.level);
  if (lvl.class) refreshPreview(); else draw();
}

function buildSteps() {
  const base = [
    { title: "Equipment", render: equipmentStep, done: () => true,
      guide: [{ target: "#purse", text: "Your money. Everything in the shop is paid from here, with change made for you." },
              { target: "#shop-filter", text: "Pick a kind of gear or search by name." },
              { target: "#shop", text: "Buy pays the price. Take free adds something you already own or found." },
              { target: "#carried", text: "What you carry. Weapons in hand and worn armor change attacks and Armor Class." }] },
    { title: "Languages", render: languagesStep, done: () => state.character.languages.length >= state.view.languages.total,
      guide: [{ target: "#language-roll", text: "Smart characters know more languages. Roll d% and the book's table names one." }] },
  ];
  const level = [];
  if (lvl) {
    const ready = () => !!preview;
    if (state.character.level === 0) level.push({ title: "Class", render: classStep, done: () => !!lvl.class, level: true,
      guide: [{ target: "#classes", text: "At 10 XP a survivor picks a class. Greyed-out classes are closed to this character's race." }] });
    level.push({ title: "Hit points", render: hitPointStep, done: () => !!lvl.hp_roll, level: true, needs: ready,
      guide: [{ target: "#level-hp", text: "Roll the class hit die. Stamina is added; you always gain at least 1." }] });
    level.push({ title: "Class choices", render: choiceStep, done: () => true, level: true, needs: ready,
      guide: [{ target: "#deity, #patron, #lucky-weapon", text: "This choice is made once and stays for the character's life." }] });
    if (lvl.class && content.classes[lvl.class].caster) level.push({ title: "Spells", render: spellStep, done: () => true, level: true, needs: ready,
      guide: [{ target: "#spell-count", text: "How many spells this level allows, and how the book wants them chosen." },
              { target: ".spell-level .roll", text: "Roll to let fate pick an unknown spell of that level." },
              { target: "#mercurial", text: "Roll once per new spell. The result changes how that spell works for you alone." }] });
    level.push({ title: "Confirm", render: confirmStep, done: () => false, level: true, needs: ready,
      guide: [{ target: "#diff", text: "What changes with this level. Green rows are new values." }, { target: "#confirm", text: "Nothing is saved until you confirm." }] });
  }
  steps = [...base, ...level, { title: "Finish", render: finishStep, done: () => false,
    guide: [{ target: "#todo", text: "Choices the rules still expect from you." }, { target: "#open-sheet", text: "The finished sheet, for play." },
            { target: "#level-up", text: "Enough XP, or the judge says so? Advance a level here." }] }];
}

// ------------------------------------------------------------------ frame
function draw(full = true) {
  const step = steps[stepIndex];
  if (!full) return drawChrome();   // typing: keep the focused field alive
  stage.replaceChildren(...[error ? h("p", { class: "error-banner", role: "alert" }, error) : null,
    step.needs && !step.needs() ? h("p", { class: "hint" }, "Choose a class first.") : step.render(),
    h("div", { class: "stage-nav no-print" },
      h("button", { class: "mini-button", type: "button", disabled: stepIndex === 0, onclick: () => go(stepIndex - 1) }, "Back"),
      stepIndex < steps.length - 1 || !characterId ? h("button", { class: "button", id: "next", type: "button", onclick: next },
        !characterId && stepIndex === steps.length - 1 ? "Create the character" : "Next") : null)].flat(Infinity).filter(Boolean));
  drawChrome();
  if (!tour.parts) tour.auto((characterId ? "build:" : "create:") + step.title, step.guide || []);
}

function drawChrome() {
  document.documentElement.dataset.land = content.lands[(lvl && lvl.class) || (state && state.character.class) || ""];
  rail.replaceChildren(...steps.map((s, i) => h("li", { class: (i === stepIndex ? "current" : s.done() && i < stepIndex ? "done" : ""), onclick: () => go(i) }, h("span", {}, s.title))));
  const next = document.getElementById("next");
  if (next) next.disabled = !characterId && !steps[stepIndex].done();
  const c = state ? state.character : null;
  if (sealed()) wasSealed = true;
  const lines = c ? [["Name", c.name], ["Tax debt", debtFigure()], ["Level", c.class ? `${c.level} ${c.class}` : "0"], ["Occupation", c.occupation.detail || c.occupation.occupation], ["Alignment", c.alignment],
                     ["Hit points", `${c.hp_current} / ${c.hp_max}`], ["AC", state.view.ac], ["XP", c.xp], ["Luck", sealed() ? "?" : c.luck_current], ["Augur", sealed() ? "told when the character is finished" : state.view.augur_effect],
                     ["Moon", state.moon ? state.moon.name : ""]]
    : [["Name", draft.name], ["Alignment", draft.alignment], ["Moon", (content.moons.find((m) => m.id === draft.moon) || {}).name || ""], ...content.abilities.map((a) => [cap(a), draft.abilities[a] ? `${draft.abilities[a]} (${plus(mod(draft.abilities[a]))})` : ""]),
       ["Occupation", occupationOf() ? occupationOf().occupation : ""], ["Augur", augurOf() ? augurOf().augur : ""], ["Hit points", draft.hp_roll ? Math.max(1, draft.hp_roll + mod(draft.abilities.stamina || 10)) : ""],
       ["Copper", draft.copper || ""], ["Item", itemOf() ? itemOf().item : ""]];
  summary.replaceChildren(h("h3", {}, "So far"), h("dl", {}, lines.filter((l) => l[1] !== "" && l[1] != null).map(([k, val]) => [h("dt", {}, k), h("dd", {}, val instanceof Node ? val : String(val))])));
  showDebtJump();
}

function go(i) {
  if (i < 0 || i >= steps.length) return;
  if (!characterId && i > stepIndex && !steps.slice(0, i).every((s) => s.done())) return;  // creation runs in order
  error = ""; stepIndex = i; tour.stop(); draw(); scrollTo({ top: 0 });
}

async function next() {
  if (!characterId && stepIndex === steps.length - 1) {
    try { await createCharacter(); } catch (err) { error = err.message; draw(); }
    return;
  }
  go(stepIndex + 1);
}

DCC.guide = () => ({ id: "manual", steps: steps[stepIndex].guide || [] });
DCC.context = () => (state ? { name: state.character.name, level: state.character.level, class: state.character.class, alignment: state.character.alignment,
                               abilities: state.view.effective, modifiers: state.view.mods, augur: state.view.augur_effect, ac: state.view.ac, saves: state.view.saves }
                           : { creating: true, abilities: draft.abilities, alignment: draft.alignment, occupation: occupationOf() && occupationOf().occupation });

(async () => {
  try {
    content = await api("GET", "content");
    if (characterId) {
      state = await api("GET", "character/" + characterId);
      buildSteps();
      if (page.dataset.start === "level") startLevel(); else draw();
    } else { steps = createSteps; draw(); }
  } catch (err) { stage.replaceChildren(h("p", { class: "error-banner" }, err.message)); }
})();
