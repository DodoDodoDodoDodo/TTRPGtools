// The town of the west marches campaign. The day is the real date. The first screen lists the places; a click on a
// name opens that place with what it offers today. Players see prices only; the admin also sees curves and tools.
"use strict";

const { h, api, store } = DCC;
const root = document.getElementById("town");
let town = null;          // { day, date, judge, shops, characters, offers, news, insight, catalog?, log?, bots? }
let shopper = store.get("dcc-shopper", "");
let message = "", failed = false, lastSeen = "", ledger = null, toast = false;

const percent = (x) => (x >= 0 ? "+" : "") + Math.round(x * 100) + "%";
const TREND = { "1": ["▲", "dearer than yesterday"], "0": ["◆", "same as yesterday"], "-1": ["▼", "cheaper than yesterday"] };
const character = () => town.characters.find((c) => c.id === shopper) || null;
const oldCount = () => !!(character() && character().roman);
const say = (text) => (oldCount() ? DCC.romanText(text) : text);   // for text written after the page was drawn
const coins = (c) => DCC.gp(c.coins_cp ?? c.coins.gp * 100 + c.coins.sp * 10 + c.coins.cp);
const place = () => town.shops.find((s) => "#" + s.id === location.hash && town.judge && !s.kinds.includes("library") && !s.kinds.includes("oracle")) || null;  // the town is one page; a shop or inn opens only for the admin's tools
const fetchTown = () => api("GET", "town" + (shopper ? "?character=" + encodeURIComponent(shopper) : ""));
const values = (form) => Object.fromEntries(new FormData(form));
const curveOf = (v) => ({ period: v.period, amplitude: v.amplitude, phase: v.phase });

async function call(path, body, ok) {
  try {
    const catalog = town.catalog;
    town = await api("POST", path, { ...body, character: shopper });
    town.catalog = town.catalog || catalog;
    message = typeof ok === "function" ? ok(town) : ok || ""; failed = false; ledger = null;
  } catch (err) { message = err.message; failed = true; }
  toast = true;   // say it once where the reader is, however far down the page
  draw();
}
const judge = (body, ok) => call("town/judge", body, ok);
const trade = (body, ok) => call("town/buy", body, ok);

// Price multiplier over four weeks (one week back, three ahead); the dot is today, the dashed line the usual price.
function sparkline(series) {
  const w = 132, hgt = 30, lo = Math.min(...series, 0.5), hi = Math.max(...series, 1.5);
  const x = (i) => (i / (series.length - 1)) * w, y = (v) => hgt - ((v - lo) / (hi - lo)) * hgt;
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", `0 0 ${w} ${hgt}`); svg.setAttribute("class", "spark"); svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", "Price over four weeks, today marked");
  const part = (tag, attrs) => { const el = document.createElementNS(svg.namespaceURI, tag); for (const k in attrs) el.setAttribute(k, attrs[k]); svg.append(el); };
  part("line", { x1: 0, x2: w, y1: y(1), y2: y(1), class: "usual" });
  part("polyline", { points: series.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ") });
  part("circle", { cx: x(7), cy: y(series[7]), r: 3 });
  return svg;
}

function curveFields(curve) {
  return [h("label", {}, "Period (days) ", h("input", { name: "period", type: "number", min: 2, max: 365, value: curve.period })),
          h("label", {}, "Swing (0.4 = 40%) ", h("input", { name: "amplitude", type: "number", min: 0, max: 0.9, step: 0.01, value: curve.amplitude })),
          h("label", {}, "Shift (days) ", h("input", { name: "phase", type: "number", value: curve.phase }))];
}

function stockRow(shop, item) {
  const who = character(), sold = item.qty === 0, poor = who && who.coins_cp < item.price_cp, service = item.kind === "service";
  const row = h("tr", { class: sold ? "sold" : poor ? "poor" : "", "data-explain": `${item.kind} ${item.name}` },
    h("td", {}, h("b", {}, item.name), item.units > 1 ? ` (${item.units})` : "", item.detail ? h("div", { class: "hint" }, item.detail) : null,
      item.material ? h("div", { class: "hint made-of", "data-explain": "what things are made of, material and weight" }, `${item.material}, ${item.weight}`) : null,
      !town.judge && item.series ? h("div", { class: "hint" }, "Your trade knows this market: ", sparkline(item.series)) : null),
    h("td", { class: "num", title: sold && item.material ? `Making one takes ${item.weight} of ${item.material.toLowerCase()} in the workshop` : "" },
      sold ? "sold out" : item.qty === null ? (service ? "" : "plenty") : item.qty),
    h("td", { class: "num", "data-explain": "Price today, coinage" }, h("b", {}, item.price),
      item.trend === undefined ? null : [" ", h("span", { class: "trend t" + item.trend, title: TREND[item.trend][1] }, TREND[item.trend][0]),
        h("div", { class: "hint" }, `usually ${item.usual} (${percent(item.against_usual)})`)]),
    h("td", {}, h("button", { class: "button buy", type: "button", disabled: sold || !who || poor || !!shop.closed,
      title: !who ? "Choose who is shopping first" : poor ? `${who.name} cannot afford this` : "",
      onclick: () => trade({ shop: shop.id, item: item.id, count: 1 },
        (t) => `${character().name} ${service ? "paid for" : "bought"}: ${t.sale.item}, ${item.price}.`) }, service ? "Pay" : "Buy")));
  if (!town.judge) return row;
  const form = h("form", { class: "form-grid compact", onsubmit: (e) => { e.preventDefault(); const v = values(e.target);
      judge({ action: "item", shop: shop.id, item: item.id, qty: v.qty, cost: v.cost, curve: curveOf(v) }, `${item.name} updated.`); } },
    h("label", {}, "On the shelf (empty = never runs out) ", h("input", { name: "qty", type: "number", min: 0, value: item.qty ?? "" })),
    h("label", {}, "Usual price ", h("input", { name: "cost", type: "text", value: DCC.gp(item.base_cp) })),
    curveFields(item.curve),
    h("div", { class: "button-row" }, h("button", { class: "mini-button", type: "submit" }, "Save"),
      h("button", { class: "mini-button danger", type: "button", onclick: () => confirm(`Take ${item.name} off offer for good?`)
        && judge({ action: "remove_item", shop: shop.id, item: item.id }, `${item.name} removed.`) }, "Remove")));
  return [row, h("tr", { class: "judge-row" }, h("td", { colSpan: 4 }, h("details", {}, h("summary", {}, "Admin: stock and price curve ", sparkline(item.series)), form)))];
}

// Beds. An inn has no page of its own: choose the number of nights, pay, and the whole sum leaves the purse at once.
// Each real night that then passes heals at the inn's rate.
const onlyInn = (shop) => !!shop.stay && !shop.kinds.includes("shop");
const nightsWanted = {};   // what is typed per inn, kept while the page redraws itself
function inns() {
  const who = character();
  const rows = town.shops.filter((shop) => shop.stay).map((shop) => {
    const stay = shop.stay;
    const nights = h("input", { type: "number", id: "nights-" + shop.id, min: 1, max: 30, step: 1, value: nightsWanted[shop.id] || 1, "aria-label": `Nights at ${shop.name}` });
    const count = () => Math.min(30, Math.max(1, Math.floor(Number(nights.value)) || 1));
    const total = h("b", { class: "stay-total" });
    const why = !who ? "Choose who is in town first" : shop.closed ? shop.closed : who.lodging ? `${who.name} already has a bed at ${who.lodging.name}` : "";
    const pay = h("button", { class: "button buy", type: "button", onclick: () => { const n = count(); delete nightsWanted[shop.id];
      trade({ shop: shop.id, nights: n }, () => `${who.name} paid for ${n} night${n === 1 ? "" : "s"} at ${shop.name}: ${DCC.gp(stay.price_cp * n)}.`); } }, "Pay");
    const update = () => {
      const sum = stay.price_cp * count(), poor = !!who && who.coins_cp < sum;
      total.textContent = say(DCC.gp(sum));
      pay.disabled = !!why || poor;
      pay.title = why || (poor ? `${who.name} cannot afford ${say(DCC.gp(sum))}` : "");
    };
    nights.addEventListener("input", () => { nightsWanted[shop.id] = nights.value; update(); });
    nights.addEventListener("change", () => { nights.value = nightsWanted[shop.id] = count(); update(); });  // 1 to 30, shown as charged
    update();
    return h("tr", { class: "stay" + (shop.closed ? " shut" : ""), "data-explain": "Healing, rest and bed rest" },
      h("td", {}, h("b", {}, shop.name), shop.keeper ? h("div", { class: "hint" }, shop.keeper) : null,
        shop.closed ? h("div", { class: "missing" }, shop.closed) : null,
        town.judge && onlyInn(shop) ? h("a", { class: "hint", href: "#" + shop.id }, "admin: this place") : null),
      h("td", { class: "num" }, h("b", {}, stay.price), h("div", { class: "hint" }, "a night"), stay.note ? h("div", { class: "hint" }, stay.note) : null),
      h("td", {}, `${stay.hp} hit point${stay.hp === 1 ? "" : "s"} and ${stay.ability} lost ability point${stay.ability === 1 ? "" : "s"} back per night`),
      h("td", {}, h("span", { class: "button-row" }, "Sleep here for", nights, "nights:", total, pay)));
  });
  return h("section", { class: "panel", id: "inns" }, h("div", { class: "panel-header" }, h("h2", {}, "Inns")),
    h("p", { class: "hint" }, "Nights are paid up front and count as real days pass."),
    h("table", { class: "inns" }, h("tbody", {}, rows)));
}

// What this shop pays today for the shopper's own things.
function sellBox(shop) {
  const rows = (town.offers || {})[shop.id], who = character();
  if (!who || !rows) return null;
  const sellNow = (row, count) => trade({ shop: shop.id, index: row.index, count }, () => `${who.name} sold ${count} x ${row.name} to ${shop.name}.`);
  return h("div", { class: "sell-box" }, h("h3", {}, `Sell to ${shop.name}`),
    h("p", { class: "hint" }, shop.buys_anything ? "Buys anything at all, for very little." : "Pays half of what it would charge for the same thing today."),
    h("table", {}, h("tbody", {}, rows.map((row) => h("tr", {}, h("td", {}, row.name), h("td", { class: "num" }, "have " + row.qty),
      h("td", { class: "num" }, row.each + " each"),
      h("td", {}, h("div", { class: "button-row" }, h("button", { class: "mini-button", type: "button", onclick: () => sellNow(row, 1) }, "Sell 1"),
        row.qty > 1 ? h("button", { class: "mini-button", type: "button", onclick: () => sellNow(row, row.qty) }, "Sell all") : null)))))));
}

// The library's cash pot: the purses of the dead, lent to the living at interest. What is paid back fills it again.
function cashPot(shop) {
  const who = character();
  const take = h("input", { type: "text", placeholder: "5,00 gp", size: 9, "aria-label": "Amount to borrow" });
  const give = h("input", { type: "text", placeholder: "5,00 gp", size: 9, "aria-label": "Amount to pay back" });
  return h("div", { class: "note", id: "pot", "data-explain": "library cash pot loan interest" },
    h("p", {}, h("b", {}, `The cash pot holds ${DCC.gp(town.library_pot_cp)}. `),
      "It is the coin the dead left behind. Anyone may borrow from it. A loan grows a little every night until it is paid back."),
    who ? h("div", { class: "button-row" }, take,
      h("button", { class: "button buy", type: "button", disabled: !town.library_pot_cp,
        onclick: () => take.value.trim() && trade({ borrow_coin: take.value.trim() }, (t) => `${who.name} borrowed ${DCC.gp(t.sale.each_cp)} from the pot.`) }, "Borrow coin"),
      who.library_loan_cp ? [h("b", {}, `${who.name} owes the pot ${DCC.gp(who.library_loan_cp)}.`), give,
        h("button", { class: "button buy", type: "button",
          onclick: () => give.value.trim() && trade({ repay_coin: give.value.trim() }, (t) => `${who.name} paid ${DCC.gp(t.sale.each_cp)} back into the pot.`) }, "Pay back")] : null)
      : h("p", { class: "hint" }, "Choose who is in town to borrow."));
}

// The library lends for free. What is borrowed stays the library's and is brought back here.
function libraryView(shop) {
  const who = character();
  return h("section", { class: "panel shop", id: "shop-" + shop.id },
    h("div", { class: "panel-header" }, h("h2", {}, shop.name)),
    h("p", {}, shop.blurb),
    cashPot(shop),
    who && who.loans.length ? h("div", { class: "note", id: "loans" }, h("b", {}, `${who.name} has on loan: `),
      who.loans.map((loan) => h("span", { class: "button-row", style: "display:inline-flex;margin-right:.8rem" }, loan.name,
        h("button", { class: "mini-button", type: "button", onclick: () => trade({ give_back: loan.index }, () => `${who.name} brought ${loan.name} back.`) }, "Bring back")))) : null,
    shop.stock.length ? h("table", { class: "stock" }, h("thead", {}, h("tr", {}, h("th", {}, "On the shelves"), h("th", { class: "num" }, "Left"), h("th", {}))),
      h("tbody", {}, shop.stock.map((item) => h("tr", { class: item.qty ? "" : "sold", "data-explain": "library " + item.name },
        h("td", {}, h("b", {}, item.name), h("span", { class: "tag" }, " " + item.kind)), h("td", { class: "num" }, item.qty || "lent out"),
        h("td", {}, h("button", { class: "button buy", type: "button", disabled: !who || !item.qty, title: who ? "" : "Choose who is borrowing first",
          onclick: () => trade({ borrow: item.id }, () => `${who.name} borrowed ${item.name}. It still belongs to the library.`) }, "Borrow"))))))
      : h("p", { class: "empty-state" }, "The shelves are empty. Nobody has died yet."));
}

function placeView(shop) {
  if (shop.kinds.includes("library")) return libraryView(shop);
  const kinds = ["weapon", "armor", "shield", "ammo", "gear", "mount"];
  const delivery = shop.next_delivery === null ? null : h("p", { class: "hint delivery" },
    shop.next_delivery === 0 ? "Today was making day here." : `Next making day in ${shop.next_delivery} day${shop.next_delivery === 1 ? "" : "s"}.`,
    shop.materials.length ? "  In the workshop: " + shop.materials.map((m) => `${m.amount} ${m.name.toLowerCase()}`).join(", ") + "." : "  The workshop is bare.");
  const adminTools = !town.judge ? null : h("details", { class: "judge-box" }, h("summary", {}, "Admin: this place ", sparkline(shop.series)),
    h("form", { class: "form-grid compact", onsubmit: (e) => { e.preventDefault();
        judge({ action: "curve", shop: shop.id, curve: curveOf(values(e.target)) }, "Curve saved."); } },
      curveFields(shop.curve), h("div", { class: "button-row" }, h("button", { class: "mini-button", type: "submit" }, "Save the place's curve"),
        h("button", { class: "mini-button", type: "button", onclick: () => judge({ action: "restock", shop: shop.id }, `Making day held at ${shop.name}.`) }, "Hold a making day now"))),
    h("form", { class: "form-grid compact", onsubmit: (e) => { e.preventDefault(); const v = values(e.target);
        judge({ action: "material", shop: shop.id, material: v.material, kg: v.kg }, "The workshop's store was changed."); } },
      h("label", {}, "Raw material from outside the village ", h("select", { name: "material" },
        Object.entries(town.goods.census).map(([id, m]) => h("option", { value: id }, m.name)))),
      h("label", {}, "Kilograms (negative takes away) ", h("input", { name: "kg", type: "text", required: true, placeholder: "12,5", size: 6 })),
      h("button", { class: "mini-button", type: "submit" }, "Bring to this workshop")),
    h("form", { class: "form-grid compact", onsubmit: (e) => { e.preventDefault(); const v = values(e.target);
        const keys = v.key === "all" ? town.catalog.filter((c) => c.kind === v.kind).map((c) => c.key) : [v.key];
        judge({ action: "stock_book", shop: shop.id, keys, qty: v.qty }, `${keys.length} kind(s) of goods shelved.`); } },
      h("label", {}, "From the rulebook: kind ", h("select", { name: "kind", onchange: (e) => {
          e.target.form.elements.key.replaceChildren(h("option", { value: "all" }, "every " + e.target.value), ...town.catalog.filter((c) => c.kind === e.target.value)
            .map((c) => h("option", { value: c.key }, `${c.name} (${c.cost})`))); } }, kinds.map((k) => h("option", { value: k }, k)))),
      h("label", {}, "Item ", h("select", { name: "key" }, h("option", { value: "all" }, "every weapon"),
        town.catalog.filter((c) => c.kind === "weapon").map((c) => h("option", { value: c.key }, `${c.name} (${c.cost})`)))),
      h("label", {}, "How many each (empty = never runs out) ", h("input", { name: "qty", type: "number", min: 0, value: 2 })),
      h("button", { class: "mini-button", type: "submit" }, "Put on the shelf")),
    h("form", { class: "form-grid compact", onsubmit: (e) => { e.preventDefault(); judge({ action: "stock", shop: shop.id, ...values(e.target) }, "Shelved."); } },
      h("label", {}, "Something else ", h("input", { name: "name", type: "text", required: true, placeholder: "Silvered dagger" })),
      h("label", {}, "Kind ", h("select", { name: "kind" }, [...kinds, "trade", "other", "service"].map((k) => h("option", { value: k, selected: k === "gear" }, k)))),
      h("label", {}, "Usual price ", h("input", { name: "cost", type: "text", required: true, placeholder: "25 gp" })),
      h("label", {}, "How many ", h("input", { name: "qty", type: "number", min: 0, value: 1 })),
      h("button", { class: "mini-button", type: "submit" }, "Put on the shelf")));
  return h("section", { class: "panel shop", id: "shop-" + shop.id },
    h("p", {}, h("a", { href: "#", class: "mini-button", id: "back" }, "← Back to town")),
    h("div", { class: "panel-header" }, h("h2", {}, shop.name, shop.kinds.map((k) => h("span", { class: "kind-badge" }, k))),
      shop.mood === null ? null : h("span", { class: "hint mood" }, `Prices run ${percent(shop.mood)} against usual today.`)),
    h("p", {}, shop.keeper ? h("b", {}, shop.keeper + ". ") : null, shop.blurb), delivery,
    shop.closed ? h("p", { class: "error-banner" }, shop.closed + " Nothing can be bought or sold here until then.") : null,
    shop.stock.length ? h("table", { class: "stock" }, h("thead", {}, h("tr", {}, h("th", {}, "On offer"), h("th", { class: "num" }, "Left"), h("th", { class: "num" }, "Price today"), h("th", {}))),
      h("tbody", {}, shop.stock.map((item) => stockRow(shop, item)))) : h("p", { class: "empty-state" }, "Nothing on offer."),
    sellBox(shop), adminTools);
}

// Everything for sale in town in one table: a row per thing, a price column per shop. A click on a price buys one
// there. Slightly grey: the shopper cannot afford it. Heavily grey: that shop has none. Shops have no pages of their
// own; the admin reaches a shop's tools by the link under its name.
let marketFilter = "";
const shopsOnly = () => town.shops.filter((shop) => shop.kinds.includes("shop"));
const shopHead = (shop) => h("th", { class: "num" + (shop.closed ? " shut" : "") }, shop.name,
  shop.keeper ? h("div", { class: "hint" }, shop.keeper) : null, shop.closed ? h("div", { class: "missing" }, shop.closed) : null,
  town.judge ? h("a", { class: "hint", href: "#" + shop.id }, "admin: this shop") : null);
function market() {
  const who = character(), shops = shopsOnly();
  const rows = new Map();   // "kind|name" -> { name, kind, units, material, weight, cells: { shop id: item } }
  for (const shop of shops) for (const item of shop.stock) {
    if (item.kind === "service") continue;
    const key = item.kind + "|" + item.name;
    if (!rows.has(key)) rows.set(key, { name: item.name, kind: item.kind, units: item.units, material: item.material, weight: item.weight, cells: {} });
    rows.get(key).cells[shop.id] = item;
  }
  const wanted = [...rows.values()].filter((row) => row.name.toLowerCase().includes(marketFilter.toLowerCase()))
    .sort((a, b) => a.kind.localeCompare(b.kind) || a.name.localeCompare(b.name));
  const cell = (shop, row) => {
    const item = row.cells[shop.id];
    if (!item || item.qty === 0) return h("td", { class: "none", title: item && row.material ? `Making one takes ${row.weight} of ${row.material.toLowerCase()} in the workshop` : "" }, item ? "sold out" : "none");
    if (item.refused) return h("td", { class: "none refused" }, "not for you");   // the keeper will not say why
    const poor = !!who && who.coins_cp < item.price_cp;
    return h("td", { class: poor ? "poor" : "" },
      h("button", { class: "price", type: "button", disabled: !who || poor || !!shop.closed,
        title: !who ? "Choose who is in town first" : shop.closed ? shop.closed : poor ? `${who.name} cannot afford this` : `Buy one at ${shop.name}`,
        onclick: () => trade({ shop: shop.id, item: item.id, count: 1 }, (t) => `${who.name} bought ${t.sale.item} at ${shop.name} for ${item.price}.`) }, item.price),
      h("div", { class: "hint" }, item.lot > 1 ? `for ${item.lot}. ` : "", item.qty === null ? "" : `${item.qty} left`,
        item.trend === undefined ? null : [" ", h("span", { class: "trend t" + item.trend, title: `${TREND[item.trend][1]}; usually ${item.usual}` }, TREND[item.trend][0])]),
      item.mark ? h("div", { class: "hint moon-make", title: item.mark.text, "data-explain": "moon make one die better worse" }, item.mark.moon.replace("The ", "") + " make") : null,
      !town.judge && item.series ? h("div", { class: "hint", title: "Your trade knows this market" }, sparkline(item.series)) : null);
  };
  return h("section", { class: "panel", id: "market" },
    h("div", { class: "panel-header" }, h("h2", {}, "Everything for sale in town"),
      h("input", { type: "search", id: "market-search", placeholder: "Search", value: marketFilter, "aria-label": "Search the goods",
        oninput: (e) => { marketFilter = e.target.value; draw(); } })),
    h("p", { class: "hint" }, "A click on a price buys one at that shop. Pale: too dear for this purse. Faint: that shop has none."),
    h("table", { class: "market" }, h("thead", {}, h("tr", {}, h("th", {}, "Item"), shops.map(shopHead))),
      h("tbody", {}, wanted.map((row) => h("tr", { "data-explain": row.kind + " " + row.name },
        h("td", {}, h("b", {}, row.name), row.units > 1 ? ` (${row.units})` : "", h("span", { class: "tag" }, " " + row.kind),
          row.material ? h("div", { class: "hint made-of", "data-explain": "what things are made of, material and weight" }, `${row.material}, ${row.weight}`) : null),
        shops.map((shop) => cell(shop, row)))))),
    h("ul", { class: "hint workshops", "data-explain": "making day workshop material" }, shops.filter((shop) => shop.next_delivery !== null).map((shop) => h("li", {},
      h("b", {}, shop.name + ": "), shop.next_delivery === 0 ? "making day was today" : `next making day in ${shop.next_delivery} day${shop.next_delivery === 1 ? "" : "s"}`,
      shop.materials.length ? "; in the workshop " + shop.materials.map((m) => `${m.amount} ${m.name.toLowerCase()}`).join(", ") : "; the workshop is bare", "."))));
}

// Everything the shopper carries that some shop would buy, and what each shop pays for one of it today.
function sellTable() {
  const who = character(), offers = town.offers || {};
  const shops = [...shopsOnly(), ...town.shops.filter((shop) => shop.kinds.includes("caravan"))];   // while the caravan is in town it buys too, low
  if (!who) return null;
  const lines = new Map();   // pack index -> { name, qty, cells: { shop id: offer } }
  for (const shop of shops) for (const offer of offers[shop.id] || []) {
    if (!lines.has(offer.index)) lines.set(offer.index, { index: offer.index, name: offer.name, qty: offer.qty, cells: {} });
    lines.get(offer.index).cells[shop.id] = offer;
  }
  const sellNow = (shop, line, count) => trade({ shop: shop.id, index: line.index, count }, () => `${who.name} sold ${count} x ${line.name} to ${shop.name}.`);
  const cell = (shop, line) => {
    const offer = line.cells[shop.id];
    if (!offer) return h("td", { class: "none" }, "does not buy it");
    return h("td", {}, h("button", { class: "price", type: "button", disabled: !!shop.closed, title: shop.closed || `Sell one to ${shop.name}`, onclick: () => sellNow(shop, line, 1) }, offer.each),
      line.qty > 1 ? h("div", {}, h("button", { class: "mini-button", type: "button", disabled: !!shop.closed, onclick: () => sellNow(shop, line, line.qty) }, `all ${line.qty}`)) : null);
  };
  return h("section", { class: "panel sell-box", id: "sell" },
    h("div", { class: "panel-header" }, h("h2", {}, `What the shops pay ${who.name}`)),
    h("p", { class: "hint" }, "A click on a price sells one to that shop. A shop pays half of what it would charge today, and only what its till can pay. Groderick buys anything, for very little."),
    lines.size ? h("table", { class: "market" }, h("thead", {}, h("tr", {}, h("th", {}, "In the pack"), shops.map(shopHead))),
      h("tbody", {}, [...lines.values()].map((line) => h("tr", {}, h("td", {}, h("b", {}, line.name), h("div", { class: "hint" }, `carries ${line.qty}`)),
        shops.map((shop) => cell(shop, line))))))
      : h("p", { class: "empty-state" }, `${who.name} carries nothing a shop would pay for.`));
}

// The herb woman: a copper buys the answer to "when is this moon next full, and for how long?" Every question costs again.
let herbAnswer = "";
function herbWoman() {
  const who = character();
  return town.shops.filter((shop) => shop.ask).map((shop) => {
    const why = !who ? "Choose who is in town first" : shop.closed ? shop.closed : who.coins_cp < shop.ask.price_cp ? `${who.name} has not even that` : "";
    return h("section", { class: "panel", id: "oracle", "data-explain": "full moon herb woman" },
      h("div", { class: "panel-header" }, h("h2", {}, shop.name)),
      h("p", {}, shop.keeper ? h("b", {}, shop.keeper + ". ") : null, shop.blurb),
      shop.closed ? h("p", { class: "error-banner" }, shop.closed) : null,
      h("div", { class: "button-row" }, `"Which moon?" ${shop.ask.price} a question:`,
        town.moons.map((m) => h("button", { class: "mini-button", type: "button", disabled: !!why, title: why,
          onclick: () => trade({ shop: shop.id, ask_moon: m.id }, (t) => (herbAnswer = t.receipt)) }, m.name))),
      herbAnswer ? h("p", { class: "note", id: "herb-answer" }, herbAnswer) : null,
      shop.augurs ? augurTrade(shop) : null);
  });
}

// She deals in birth augurs: augur and modifier as one package, so much coin a point. A good one she buys, a bad one
// she is paid to take, and what lies on her shelf can be taken by whoever has none, each worn by one point.
function augurTrade(shop) {
  const who = character(), mine = who && who.augur, point = shop.augur_point_cp;
  const value = mine && mine.has ? mine.modifier * point : 0;
  const offer = !mine ? null : !mine.has ? `${who.name} was born under nothing now. An augur from her shelf can be taken.`
    : value > 0 ? `She pays ${DCC.gp(value)} for it.` : value < 0 ? `She takes it off ${who.name} for ${DCC.gp(-value)}.` : "She takes it for nothing. It is worth nothing.";
  return h("div", { id: "augurs", "data-explain": "birth augur trade herb woman" },
    h("h3", {}, "Birth augurs, bought and sold"),
    h("p", { class: "hint" }, `An augur changes hands with its modifier, ${DCC.gp(point)} a point. A bad one costs that to be rid of. One at a time.`),
    !who ? h("p", { class: "hint" }, "Choose who is in town first.")
      : !mine ? h("p", { class: "hint" }, `${who.name} does not know their own augur yet. Finish the character first.`)
      : h("div", { class: "button-row" }, mine.has ? h("span", {}, h("b", {}, `${who.name} carries: `), mine.effect + ". ") : null, offer,
          mine.has ? h("button", { class: "button buy", type: "button", disabled: !!shop.closed,
            onclick: () => confirm(`Hand over ${mine.name}? ${who.name} is then born under nothing, and hit points change if the augur touched them.`)
              && trade({ shop: shop.id, sell_augur: true }, (t) => (herbAnswer = t.receipt)) }, "Sell the augur") : null),
    shop.augurs.length ? h("table", { class: "augur-shelf" }, h("tbody", {}, shop.augurs.map((a) => h("tr", {},
        h("td", {}, h("b", {}, a.effect), a.from ? h("div", { class: "hint" }, `once ${a.from}'s`) : null),
        h("td", { class: "num" }, a.price_cp > 0 ? `costs ${a.price}` : a.price_cp < 0 ? `she pays ${a.price} to whoever takes it` : "for nothing"),
        h("td", {}, h("button", { class: "button buy", type: "button", disabled: !mine || mine.has || !!shop.closed || (a.price_cp > 0 && who.coins_cp < a.price_cp),
          title: !mine ? "" : mine.has ? "One at a time: sell the old augur first" : a.price_cp > 0 && who.coins_cp < a.price_cp ? `${who.name} cannot afford it` : "",
          onclick: () => trade({ shop: shop.id, take_augur: a.index }, (t) => (herbAnswer = t.receipt)) }, "Take"))))))
      : h("p", { class: "empty-state" }, "Her shelf of augurs is empty."));
}

// The books: where every coin sits tonight, the two taps (bank and Finanzamt), and the nightly record.
function moneyPanel(pick) {
  const m = town.money, gp = DCC.gp;
  const accounts = [["bank", "the bank's vault"], ["finanzamt", "the Finanzamt"], ["library", "the library's cash pot"], ["caravan", "the caravans' takings"], ...town.shops.filter((s) => !s.kinds.includes("library")).map((s) => ["till:" + s.id, s.name + "'s till"]),
                    ["character", "a character"]];
  const choose = (name) => h("select", { name }, accounts.map(([value, label]) => h("option", { value }, label)));
  return h("details", { id: "money", open: true }, h("summary", {}, `Money in the village: ${gp(m.money_cp)} (${gp(m.circulating_cp)} in circulation), prices at ${Math.round(m.price_index * 100)}% of usual`),
    h("table", {}, h("tbody", {},
      [["Characters' purses", m.characters_cp], ["Unplayed villagers' purses", m.villagers_cp], ["Traders' purses", m.traders_cp], ["Tills of shops and inns", m.tills_cp],
       ["The library's cash pot", m.library_cp], ["Bank vault (not in circulation)", m.bank_cp], ["Finanzamt (not in circulation)", m.finanzamt_cp],
       ["Left with the caravans (not in circulation)", m.caravan_cp]].map(([label, cp]) => h("tr", {}, h("td", {}, label), h("td", { class: "num" }, gp(cp)))),
      h("tr", {}, h("td", { class: "hint" }, "Tills: " + Object.entries(m.tills).map(([name, cp]) => `${name} ${gp(cp)}`).join(", ")), h("td", {})))),
    h("form", { class: "form-grid compact", onsubmit: (e) => { e.preventDefault(); const v = values(e.target);
        judge({ action: e.submitter.value, amount: v.amount }, e.submitter.value === "issue" ? "The bank issued new coin." : "The bank retired coin."); } },
      h("label", {}, "The bank's tap: amount ", h("input", { name: "amount", type: "text", required: true, placeholder: "500,00 gp" })),
      h("div", { class: "button-row" }, h("button", { class: "mini-button", type: "submit", name: "do", value: "issue" }, "Issue new coin"),
        h("button", { class: "mini-button danger", type: "submit", name: "do", value: "retire" }, "Retire coin from the vault"))),
    h("form", { class: "form-grid compact", onsubmit: (e) => { e.preventDefault(); const v = values(e.target);
        judge({ action: "move", source: v.source, to: v.to, amount: v.amount, target: v.target }, "Coin moved."); } },
      h("label", {}, "Move coin from ", choose("source")), h("label", {}, "to ", choose("to")),
      h("label", {}, "Which character (if one is involved) ", pick("target", false)),
      h("label", {}, "Amount ", h("input", { name: "amount", type: "text", required: true, placeholder: "25,00 gp" })),
      h("button", { class: "mini-button", type: "submit" }, "Move")),
    m.history.length ? h("details", {}, h("summary", {}, `Nightly record (${m.history.length} nights)`),
      h("table", {}, h("thead", {}, h("tr", {}, ["Date", "In circulation", "Bank", "Finanzamt", "All money", "Town debt", "Prices"].map((x) => h("th", {}, x)))),
        h("tbody", {}, m.history.map((r) => h("tr", {}, h("td", {}, r.date), h("td", { class: "num" }, gp(r.circulating_cp)), h("td", { class: "num" }, gp(r.bank_cp)),
          h("td", { class: "num" }, gp(r.finanzamt_cp)), h("td", { class: "num" }, gp(r.money_cp)), h("td", { class: "num" }, gp(r.debt_cp)),
          h("td", { class: "num" }, Math.round(r.price_index * 100) + "%")))))) : h("p", { class: "hint" }, "The nightly record starts with tonight's update."),
    m.log.length ? h("details", {}, h("summary", {}, "Last movements by the admin, the Finanzamt and the bank"),
      h("ul", {}, m.log.map((l) => h("li", {}, `${l.date}: ${l.what}, ${gp(Math.abs(l.cp))}` + (l.by ? ` (${l.by})` : ""))))) : null);
}

// Goods are a closed system like the coin: weight moves between the workshops' stores and finished things.
function goodsPanel() {
  const g = town.goods, kg = (grams) => (grams / 1000).toFixed(1).replace(".", ",") + " kg";
  return h("details", { id: "goods" }, h("summary", {}, "Materials in the village: " + Object.values(g.census).map((m) => `${m.name} ${kg(m.total_g)}`).join(", ")),
    h("table", {}, h("thead", {}, h("tr", {}, ["Material", "Raw, in workshops", "Bound in things", "Together"].map((x) => h("th", {}, x)))),
      h("tbody", {}, Object.values(g.census).map((m) => h("tr", {}, h("td", {}, m.name), h("td", { class: "num" }, kg(m.raw_g)),
        h("td", { class: "num" }, kg(m.things_g)), h("td", { class: "num" }, kg(m.total_g)))))),
    h("p", { class: "hint" }, "Things: on shelves, at the library, in traders' and characters' packs. Raw material is brought in at each place's admin box."),
    g.log.length ? h("ul", {}, g.log.map((l) => h("li", {}, `${l.date}: ${l.what}` + (l.by ? ` (${l.by})` : "")))) : null);
}

function adminTable() {
  const pick = (name, required = true) => h("select", { name, required }, h("option", { value: "" }, "Choose"), town.characters.map((c) => h("option", { value: c.id }, `${c.name} (${coins(c)}; owes ${c.tax_debt})`)));
  const showLedger = async (e) => {
    if (!e.target.open || ledger) return;
    ledger = (await api("GET", "town/items")).items; draw(); root.querySelector("#ledger").open = true;
  };
  return h("section", { class: "panel judge-box", id: "judge" },
    h("div", { class: "panel-header" }, h("h2", {}, "Admin table"), h("span", { class: "hint" }, "only the admin sees this panel")),
    h("form", { class: "form-grid compact", onsubmit: (e) => { e.preventDefault(); const v = values(e.target);
        judge({ action: "coins", target: v.target, amount: v.amount }, "Purse set."); } },
      h("label", {}, "Set the purse of (the bank's vault pays or takes the difference) ", pick("target")), h("label", {}, "Purse ", h("input", { name: "amount", type: "text", required: true, placeholder: "12,50 gp" })),
      h("button", { class: "mini-button", type: "submit" }, "Set coins")),
    h("form", { class: "form-grid compact", onsubmit: (e) => { e.preventDefault(); const v = values(e.target);
        judge({ action: "debt", target: v.target, amount: v.amount }, "Tax debt set."); } },
      h("label", {}, "Set the tax debt of ", pick("target")), h("label", {}, "Debt ", h("input", { name: "amount", type: "text", placeholder: "10.000,00 gp", required: true })),
      h("button", { class: "mini-button", type: "submit" }, "Set debt")),
    h("form", { class: "form-grid compact", onsubmit: (e) => { e.preventDefault(); judge({ action: "notice", text: values(e.target).text }, "Notice posted."); } },
      h("label", { class: "wide" }, "Post on the notice board ", h("input", { name: "text", type: "text", required: true, placeholder: "Market day on Friday." })),
      h("button", { class: "mini-button", type: "submit" }, "Post")),
    moneyPanel(pick), goodsPanel(),
    h("div", { class: "button-row" }, h("button", { class: "mini-button", type: "button",
      onclick: () => judge({ action: "run_daily" }, "Today's produce, making days and traders were played again.") }, "Play today's update again"),
      h("span", { class: "hint" }, `last update: campaign day ${town.last_daily ?? "none yet"}`)),
    h("details", {}, h("summary", {}, "Traders' purses and packs"),
      h("ul", {}, Object.values(town.bots).map((b) => h("li", {}, h("b", {}, b.name), `: ${coins(b)}; carries `,
        (b.inventory || []).map((i) => `${i.qty} x ${i.name}`).join(", ") || "nothing",
        b.note || (b.notes || []).length ? h("div", { class: "hint" }, "note: " + (b.note || b.notes[b.notes.length - 1].text)) : null)))),
    h("details", { open: town.needs_board.length > 0 }, h("summary", {}, `Village needs: the traders' shared notepad (${town.needs_board.length})`),
      town.needs_board.length ? h("ol", {}, town.needs_board.map((line) => h("li", {}, h("b", {}, line.what), ": " + line.by.join(", "))))
        : h("p", { class: "hint" }, "Empty. The traders write on it when a model plays them.")),
    h("details", {}, h("summary", {}, `Town log: what the nightly update did (${town.chronicle.length})`),
      h("ul", { class: "hint" }, town.chronicle.map((n) => h("li", {}, `${n.date}: ${n.text}`)))),
    h("details", {}, h("summary", {}, `Sales log (${town.log.length})`),
      h("table", {}, h("thead", {}, h("tr", {}, ["When", "Place", "What", "Price", "Who", "Login"].map((t) => h("th", {}, t)))),
        h("tbody", {}, town.log.map((s) => h("tr", {}, h("td", {}, `${s.date} ${s.at}`), h("td", {}, s.shop), h("td", {}, `${s.count} x ${s.item}`),
          h("td", { class: "num" }, DCC.gp(s.each_cp)), h("td", {}, s.character), h("td", {}, s.by || "")))))),
    h("details", { id: "ledger", ontoggle: showLedger }, h("summary", {}, "All items: who holds what"),
      !ledger ? h("p", { class: "hint" }, "Loading") : h("table", {}, h("thead", {}, h("tr", {}, ["Holder", "Item", "Kind", "Qty", "Usual", "Notes"].map((t) => h("th", {}, t)))),
        h("tbody", {}, ledger.filter((i) => !i.gone).map((i) => h("tr", {}, h("td", {}, `${i.holder_type} ${i.holder_id}`), h("td", {}, i.name), h("td", { class: "tag" }, i.kind),
          h("td", { class: "num" }, i.qty ?? "plenty"), h("td", { class: "num" }, i.base_cp ? DCC.gp(i.base_cp) : i.cost || ""), h("td", { class: "hint" }, i.notes || "")))))));
}

// The town note: one scrap everybody shares, in two parts. TALK is what villagers scribble for each other (gossip, grumbles, jokes);
// REQUESTS is what the village asks for. Any character may add a line to either; the traders read both and add theirs at night.
// The oldest lines fall off the top.
function townNote() {
  const who = character();
  const request = h("input", { type: "text", id: "town-note-line", maxLength: 160, placeholder: "a request for everyone, 20 words or so", "aria-label": "A line for the town note" });
  const talk = h("input", { type: "text", id: "town-talk-line", maxLength: 160, placeholder: "a line of talk: gossip, a grumble, a joke", "aria-label": "A line of talk for the town note" });
  const part = (name, text, input, key) => [h("span", { class: "tag" }, name),
    ...((text || "").split("\n").filter(Boolean).map((l) => h("span", { class: "said" }, l))),
    !(text || "").trim() ? h("span", { class: "said" }, "Nothing written yet.") : null,
    who ? h("span", { class: "button-row" }, input, h("button", { class: "mini-button", type: "button",
      onclick: () => input.value.trim() && trade({ [key]: input.value.trim() }, (t) => t.receipt) }, "Write")) : null];
  return h("div", { id: "town-note", class: "news", "data-explain": "town note shared by everyone" },
    part("Town talk", town.town_flavour, talk, "flavour"), part("Town requests", town.town_note, request, "town_note"),
    town.judge ? h("button", { class: "mini-button danger", type: "button", onclick: () => confirm("Wipe the town note?") && judge({ action: "town_note", text: "" }, "Town note wiped.") }, "Wipe") : null);
}

function header() {
  const who = character();
  const pay = h("input", { type: "text", placeholder: who && who.tax_step_cp ? DCC.gp(who.tax_step_cp) : "5,00 gp", "aria-label": "Amount to pay", size: 9 });
  return h("section", { class: "panel" },
    h("div", { class: "panel-header" }, h("h1", {}, "Town"), h("span", { class: "day", title: "Campaign day " + town.day }, town.date)),
    h("div", { class: "button-row", id: "shopper" }, h("label", {}, "In town as ",
      h("select", { onchange: async (e) => { shopper = e.target.value; store.set("dcc-shopper", shopper); town = await fetchTown(); draw(); } }, h("option", { value: "" }, "Choose a character"),
        town.characters.map((c) => h("option", { value: c.id, selected: c.id === shopper }, c.name + (town.judge && c.owner ? ` (${c.owner}${c.clause ? ", " + c.clause : ""})` : ""))))),
      who ? h("span", { id: "purse", "data-explain": "Coinage copper silver gold" }, h("b", {}, "Purse: "), coins(who), h("b", {}, "  Hit points: "), who.hp,
        who.lodging ? `  Sleeping at ${who.lodging.name}, ${who.lodging.nights - who.lodging.applied} night(s) left.` : "",
        who.library_loan_cp ? h("b", {}, `  Owes the library ${DCC.gp(who.library_loan_cp)}.`) : null)
          : h("span", { class: "hint" }, town.characters.length ? "" : "You have no characters yet.")),
    who ? h("div", { class: "button-row", id: "taxes", "data-explain": "debt to the tax office" }, h("b", {}, "Tax office: "), who.tax_line || `${who.name} owes ${who.tax_debt}.`, pay,
      h("button", { class: "button buy", type: "button", disabled: who.tax_debt_cp <= 0,
        onclick: () => pay.value.trim() && trade({ taxes: pay.value.trim() }, (t) => t.receipt || `Paid ${DCC.gp(t.sale.each_cp)} in taxes. The coin is gone.`) }, "Pay taxes")) : null,
    message ? h("p", { class: failed ? "error-banner" : "note", role: "status" }, message) : null,
    h("p", { class: "hint", "data-explain": "full moon" }, `Campaign day ${town.day}. Time here runs with the real calendar: prices move at midnight, and nobody posts tomorrow's.`),
    place() ? null : h("div", { class: "button-row", id: "jump" }, [["Buy", "market"], ["Sell", "sell"], ["Inns", "inns"], ["Herb woman", "oracle"], ["Library", "shop-library"]].map(([label, id]) =>
      h("button", { class: "mini-button", type: "button", onclick: () => { const part = document.getElementById(id); if (part) part.scrollIntoView({ behavior: "smooth" }); } }, label))),
    h("ul", { class: "moons", id: "moons", "data-explain": "full moon" }, town.moons.map((m) => h("li", { class: who && who.moon === m.id ? "mine" : "" },
      m.text + ".", who && who.moon === m.id ? h("span", { class: "tag" }, ` ${who.name}'s moon`) : null))),
    who && who.moon_rule ? h("p", { id: "moon-rule", "data-explain": "moon enemies one die better one die worse" }, who.moon_rule.text) : null,
    town.notices.length ? h("div", { class: "notices", id: "notices" }, h("b", {}, "Notice board"),
      h("ul", {}, town.notices.map((n, index) => h("li", {}, n.text, h("span", { class: "tag" }, " " + n.date),
        town.judge ? h("button", { class: "mini-button danger", type: "button", style: "margin-left:.5rem", onclick: () => judge({ action: "remove_notice", index }, "Notice taken down.") }, "Take down") : null)))) : null,
    who && town.record.length ? h("details", { id: "record" }, h("summary", {}, `${who.name}'s dealings (${town.record.length})`),
      h("table", {}, h("tbody", {}, town.record.map((s) => h("tr", {}, h("td", {}, s.date), h("td", {}, s.shop),
        h("td", {}, (s.count < 0 ? "sold " : s.shop === "Tax office" ? "" : "bought ") + `${Math.abs(s.count)} x ${s.item}`), h("td", { class: "num" }, DCC.gp(s.each_cp) + " each")))))) : null,
    townNote(),
    town.news.length ? h("div", { id: "news", class: "news" }, h("span", { class: "tag" }, "Town talk"),
      town.news.map((n) => h("span", { class: "said" }, n.text,
        town.judge ? h("button", { class: "mini-button danger", type: "button", title: "Remove this line for everyone",
          onclick: () => judge({ action: "remove_news", text: n.text }, "Line removed.") }, "x") : null))) : null);
}

function draw() {
  const here = place();
  const focus = document.activeElement && root.contains(document.activeElement) ? document.activeElement.id : "";
  root.replaceChildren(...[header(), here ? placeView(here) : [market(), sellTable(), inns(), herbWoman(), town.shops.filter((s) => s.kinds.includes("library")).map(libraryView)], !here && town.judge ? adminTable() : null,
    message && toast ? h("p", { class: "toast" + (failed ? " bad" : ""), "aria-hidden": "true" }, message) : null].flat(Infinity).filter(Boolean));
  toast = false;
  if (oldCount()) DCC.romanize(root);   // this character's moon counts the old way: Roman numerals
  const again = focus && document.getElementById(focus);   // the page was rebuilt under a field somebody is typing in
  if (again) { again.focus(); if (again.type === "search") again.setSelectionRange(again.value.length, again.value.length); }
  lastSeen = JSON.stringify(town);
}

async function refresh() {
  if (document.hidden || root.contains(document.activeElement) && /INPUT|SELECT|TEXTAREA/.test(document.activeElement.tagName)) return;
  if (root.querySelector("details[open]:not(#news):not(#record):not(#money)")) return;   // someone is mid-edit
  try {
    const fresh = await fetchTown();
    fresh.catalog = fresh.catalog || town.catalog;
    if (JSON.stringify(fresh) !== lastSeen) { town = fresh; draw(); }
  } catch { /* next round */ }
}

DCC.guide = () => ({ id: "town", steps: [
  { target: "#shopper", text: "Pick which of your characters is in town. Purse and hit points shown are theirs." },
  { target: "#taxes", text: "Every character owes the tax office. Type an amount and pay: the coin is gone, the debt shrinks." },
  { target: "#moons", text: "Three moons cross this sky. The one your character is bound to is marked." },
  { target: "#market", text: "Everything for sale in town, with today's price at each shop. Prices change every day." },
  { target: ".market .price", text: "A click on a price buys one there. A shelf holds what it holds: once someone buys the last one, it is gone for everybody until the keeper can make another." },
  { target: "#inns", text: "Beds. Set the number of nights and pay: the whole sum leaves the purse at once. Each real night that passes heals; a better inn heals more." },
  { target: "#sell", text: "Shops buy too: what each pays for your things today. What you sell lands on the shelf for others." },
  { target: "#oracle", text: "The herb woman knows when each moon is next full, a copper a question: a thing made that day belongs to that moon. She also buys and sells birth augurs." },
  { target: "#shop-library", text: "The library lends what the dead left behind, things and coin. Lent things cannot be sold." },
  { target: "#news", text: "Now and then the town talks about who sold what. Most of what happens is never told." }] });
DCC.context = () => ({ date: town && town.date, in_town_as: character() && character().name, purse: character() && character().coins });

addEventListener("hashchange", () => { message = ""; draw(); scrollTo({ top: 0 }); });
(async () => {
  try { town = await fetchTown(); draw(); DCC.tour.auto("town", DCC.guide().steps); setInterval(refresh, 15000); addEventListener("focus", refresh); }
  catch (err) { root.replaceChildren(h("p", { class: "error-banner" }, err.message)); }
})();
