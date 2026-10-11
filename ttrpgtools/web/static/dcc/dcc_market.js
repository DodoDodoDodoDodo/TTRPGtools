// Buying equipment from the character's own page: one row per item, one price column per shop. A click on a
// price buys it there. Slightly grey = this character cannot afford it; heavily grey = that shop has none.
// Mounts itself on every element with data-market="<character id>"; DCC.market(box, id, onChange) does the same by hand.
"use strict";

DCC.market = async function market(box, characterId, onChange) {
  const { h, api } = DCC;
  let town, note = "", failed = false, filter = "";
  const load = async () => { town = await api("GET", "town?character=" + encodeURIComponent(characterId)); };
  const buy = async (shop, item) => {
    try {
      town = await api("POST", "town/buy", { shop: shop.id, item: item.id, character: characterId, count: 1 });
      note = `Bought ${town.sale.item} at ${shop.name} for ${item.price}.`; failed = false;   // what was handed over, which a clause may have changed
      if (onChange) await onChange();
    } catch (err) { note = err.message; failed = true; }
    draw();
  };
  const payTaxes = async (amount) => {
    try {
      town = await api("POST", "town/buy", { taxes: amount, character: characterId });
      note = town.receipt || `Paid ${DCC.gp(town.sale.each_cp)} in taxes. The coin is gone.`; failed = false;
      if (onChange) await onChange();
    } catch (err) { note = err.message; failed = true; }
    draw();
  };
  function draw() {
    const who = town.characters.find((c) => c.id === characterId);
    if (!who) return box.replaceChildren(h("p", { class: "hint" }, "Only the character's player or the admin can shop for them."));
    const shops = town.shops.filter((s) => s.kinds.includes("shop"));
    const rows = new Map();   // "kind|name" -> { name, kind, cells: { shopId: item } }
    for (const shop of shops) for (const item of shop.stock) {
      if (item.kind === "service") continue;
      const key = item.kind + "|" + item.name;
      if (!rows.has(key)) rows.set(key, { name: item.name, kind: item.kind, units: item.units, cells: {} });
      rows.get(key).cells[shop.id] = item;
    }
    const wanted = [...rows.values()].filter((r) => r.name.toLowerCase().includes(filter.toLowerCase()))
      .sort((a, b) => a.kind.localeCompare(b.kind) || a.name.localeCompare(b.name));
    const cell = (shop, row) => {
      const item = row.cells[shop.id];
      if (!item || item.qty === 0) return h("td", { class: "none" }, item ? "sold out" : "none");
      if (item.refused) return h("td", { class: "none" }, "not for you");
      const poor = who.coins_cp < item.price_cp;
      return h("td", { class: poor ? "poor" : "" }, h("button", { class: "price", type: "button", disabled: poor,
        title: poor ? `${who.name} cannot afford this` : `Buy at ${shop.name}` + (item.qty === null ? "" : `, ${item.qty} left`),
        onclick: () => buy(shop, item) }, item.price));
    };
    const pay = h("input", { type: "text", placeholder: "5,00 gp", size: 9, "aria-label": "Amount to pay" });
    const search = h("input", { type: "search", placeholder: "Search", value: filter, "aria-label": "Search items",
      oninput: (e) => { filter = e.target.value; draw(); const s = box.querySelector("input[type=search]"); s.focus(); s.setSelectionRange(filter.length, filter.length); } });
    box.replaceChildren(
      h("div", { class: "button-row" }, h("b", {}, "Purse: "), DCC.gp(who.coins_cp), search,
        h("a", { class: "mini-button", href: DCC.root + "town" }, "Go to town (sell, inns)")),
      h("div", { class: "button-row taxes", "data-explain": "debt to the tax office" }, h("b", {}, "Tax office: "), who.tax_line || `owes ${who.tax_debt}.`, pay,
        h("button", { class: "mini-button", type: "button", disabled: who.tax_debt_cp <= 0, onclick: () => pay.value.trim() && payTaxes(pay.value.trim()) }, "Pay taxes")),
      note ? h("p", { class: failed ? "error-banner" : "note", role: "status" }, note) : null,
      h("table", { class: "market" }, h("thead", {}, h("tr", {}, h("th", {}, "Item"), shops.map((s) => h("th", { class: "num" }, s.name)))),
        h("tbody", {}, wanted.map((row) => h("tr", { "data-explain": row.kind + " " + row.name },
          h("td", {}, row.name, row.units > 1 ? ` (${row.units})` : "", h("span", { class: "tag" }, " " + row.kind)), shops.map((s) => cell(s, row)))))));
    if (who.roman) DCC.romanize(box);   // this character's moon counts the old way: Roman numerals
  }
  try { await load(); draw(); } catch (err) { box.replaceChildren(h("p", { class: "error-banner" }, err.message)); }
  return { refresh: async () => { await load(); draw(); } };
};

addEventListener("DOMContentLoaded", () => {
  for (const box of document.querySelectorAll("[data-market]")) DCC.market(box, box.dataset.market, () => location.reload());
});
