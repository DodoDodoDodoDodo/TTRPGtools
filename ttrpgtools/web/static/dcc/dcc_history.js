// The history of the village, for the admin: the price and the amount on the shelves of every good, night by night, on a logarithmic scale, and what the
// caravan would be asked for. Every line has a colour AND a dash pattern AND a name (the colour alone is never the only sign).
"use strict";

(() => {
  const { h, api } = DCC;
  const root = document.getElementById("history");
  const NS = "http://www.w3.org/2000/svg";
  const svg = (tag, attrs = {}, ...kids) => {
    const e = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) if (v != null) e.setAttribute(k, v);
    for (const kid of kids.flat()) if (kid != null) e.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
    return e;
  };
  // Okabe-Ito, which stays apart for colour-blind eyes, with four dash patterns: 32 looks before one repeats
  const COLORS = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9", "#222222", "#B8A800"];
  const DASHES = ["", "8 4", "2 3", "10 3 2 3"];
  const HATCHES = ["solid", "diag", "dots", "cross", "horiz", "back"];
  const STAPLES = ["Barley, a sack", "Ale, a jug", "Eggs, a dozen", "Hen", "Hens, the whole flock", "Humans, living", "Halflings, living", "Dwarves, living", "Elves, living", "Smoked eel", "Coal, a sack", "Rations, per day", "Scrap metal", "Tanned hide"];
  const W = 1000, PAD = { l: 62, r: 150, t: 12, b: 26 };
  let data = null, visible = new Set(), hover = null, mode = "price", filter = "", range = { since: null, until: null }, cursor = null, note = "";

  const lookOf = (names) => Object.fromEntries(names.map((n, i) => [n, { color: COLORS[i % COLORS.length], dash: DASHES[Math.floor(i / COLORS.length) % DASHES.length] }]));
  const fmtPrice = (v) => v == null ? "-" : v <= 0 ? (v < 0 ? "paid " + Math.abs(v) + " cp" : "free") : v >= 100 ? DCC.gp(Math.round(v)) : v.toFixed(v < 10 ? 1 : 0) + " cp";
  const dateOf = (day) => { const d = new Date(Date.parse(data.epoch) + (day - 1) * 86400000); return d.toISOString().slice(0, 10); };
  const yearOf = (day) => "year " + (Math.floor((day - 1) / 365) + 1);

  function niceTicks(lo, hi) {
    const out = [];
    for (let e = Math.floor(Math.log10(lo)); e <= Math.ceil(Math.log10(hi)); e++) for (const m of [1, 2, 5]) { const v = m * 10 ** e; if (v >= lo / 1.01 && v <= hi * 1.01) out.push(v); }
    return out.length > 14 ? out.filter((v) => String(v)[0] === "1") : out;
  }

  // The axis starts at -0.1 or lower and is a symmetric log, sgn(x) * log10(1 + |x| / knee): straight around zero and logarithmic far from it on both sides, so that zero, free, can be drawn and marked
  function panel(title, key, height, floor, unit) {
    const names = [...visible].filter((n) => data.series[n]);
    const knee = unit === "x" ? 0.1 : 1;   // one copper, one piece (a tenth of the usual price)
    const everything = names.flatMap((n) => data.series[n][key].filter((v) => v != null));
    const least = unit === "cp" ? -10 : unit === "x" ? -0.5 : -0.1;   // prices go down to -10 cp (-0.5 times the usual) whether or not any shop pays yet; amounts only to -0.1
    const bottom = Math.min(least, Math.min(...(everything.length ? everything : [0])) * 1.3);   // and further, as far as a shop really pays
    const T = (v) => { const x = Math.max(v, bottom); return Math.sign(x) * Math.log10(1 + Math.abs(x) / knee); };   // symmetric log: sgn(x) * log10(1 + |x|), straight near 0.0
    const vals = everything.filter((v) => v > 0);
    const top = Math.max(4 * knee, Math.max(...(vals.length ? vals : [10])) * 1.4);
    const tLo = T(bottom), tHi = T(top);
    const x0 = data.days[0], x1 = data.days[data.days.length - 1] + data.step;
    const X = (d) => PAD.l + (d - x0) / Math.max(1, x1 - x0) * (W - PAD.l - PAD.r);
    const Y = (v) => PAD.t + (1 - (T(v) - tLo) / (tHi - tLo)) * (height - PAD.t - PAD.b);
    const el = svg("svg", { viewBox: `0 0 ${W} ${height}`, class: "hist-chart", role: "img", "aria-label": title });
    el.append(svg("rect", { x: PAD.l, y: PAD.t, width: W - PAD.l - PAD.r, height: height - PAD.t - PAD.b, fill: "#fffef6", stroke: "#4d4d4d", "stroke-width": 1 }));
    if (data.real_day >= x0 && data.real_day < x1 - data.step) {   // beyond today the village is a simulation
      el.append(svg("rect", { x: X(data.real_day), y: PAD.t, width: W - PAD.r - X(data.real_day), height: height - PAD.t - PAD.b, fill: "#d4d4d4", opacity: .45 }));
      el.append(svg("line", { x1: X(data.real_day), x2: X(data.real_day), y1: PAD.t, y2: height - PAD.b, stroke: "#222", "stroke-dasharray": "4 3" }));
      el.append(svg("text", { x: X(data.real_day) + 4, y: PAD.t + 11, "font-size": 10 }, "now; simulated after"));
    }
    const label = (v) => unit === "cp" ? fmtPrice(v) : unit === "n" ? (v >= 1000 ? (v / 1000) + "k" : v) : v;
    for (const v of niceTicks(unit === "x" ? 0.1 : 1, top)) {
      el.append(svg("line", { x1: PAD.l, x2: W - PAD.r, y1: Y(v), y2: Y(v), stroke: "#c9c4a8", "stroke-width": .6 }));
      el.append(svg("text", { x: PAD.l - 5, y: Y(v) + 3, "text-anchor": "end", "font-size": 10 }, label(v)));
    }
    if (bottom <= -1) for (const v of niceTicks(unit === "x" ? 0.1 : 1, -bottom)) {   // the mirrored side: what a shop pays you to take the goods away
      el.append(svg("line", { x1: PAD.l, x2: W - PAD.r, y1: Y(-v), y2: Y(-v), stroke: "#c9c4a8", "stroke-width": .6 }));
      el.append(svg("text", { x: PAD.l - 5, y: Y(-v) + 3, "text-anchor": "end", "font-size": 10 }, "-" + label(v)));
    }
    el.append(svg("line", { x1: PAD.l, x2: W - PAD.r, y1: Y(0), y2: Y(0), stroke: "#222", "stroke-width": 1.8 }));   // zero, clearly
    el.append(svg("text", { x: PAD.l - 5, y: Y(0) + 4, "text-anchor": "end", "font-size": 11, "font-weight": 700 }, "0.0"));
    el.append(svg("text", { x: PAD.l + 4, y: Y(0) - 3, "font-size": 10, "font-weight": 700 }, unit === "n" ? "0.0 = none on the shelves" : "0.0 = free"));
    if (bottom > -1 && unit !== "cp") el.append(svg("text", { x: PAD.l - 5, y: height - PAD.b - 2, "text-anchor": "end", "font-size": 9 }, bottom.toFixed(1)));
    const span = x1 - x0, yearsShown = span / 365;
    const stepDays = yearsShown > 6 ? 365 * Math.ceil(yearsShown / 6) : yearsShown > 1.5 ? 365 : span > 120 ? 30 : span > 40 ? 10 : 5;
    for (let d = Math.ceil((x0 - 1) / stepDays) * stepDays + 1; d <= x1; d += stepDays) {
      el.append(svg("line", { x1: X(d), x2: X(d), y1: height - PAD.b, y2: height - PAD.b + 4, stroke: "#4d4d4d" }));
      el.append(svg("text", { x: X(d), y: height - 9, "text-anchor": "middle", "font-size": 10 }, stepDays >= 365 ? yearOf(d) : "day " + d));
    }
    const ends = [];
    for (const name of names) {
      const look = looks[name], ys = data.series[name][key], hot = hover === name, dim = hover && !hot;
      let d = "";
      let last = null;
      ys.forEach((v, i) => { if (v == null) { d += ""; return; } const cmd = (i > 0 && ys[i - 1] != null) ? "L" : "M"; d += `${cmd}${X(data.days[i]).toFixed(1)},${Y(v).toFixed(1)}`; last = [data.days[i], v]; });
      el.append(svg("path", { d, fill: "none", stroke: look.color, "stroke-width": hot ? 3.4 : 1.6, "stroke-dasharray": look.dash, opacity: dim ? .15 : 1, "stroke-linejoin": "round" }));
      if (last) ends.push({ name, y: Y(last[1]), look });
    }
    if (ends.length <= 18) {   // names at the right end of the lines, pushed apart so they can be read
      ends.sort((a, b) => a.y - b.y);
      let prev = -99;
      for (const e of ends) { e.ty = Math.max(e.y, prev + 11); prev = e.ty; }
      for (const e of ends) el.append(svg("text", { x: W - PAD.r + 6, y: e.ty + 3, "font-size": 10, fill: e.look.color, "font-weight": 600 }, e.name.length > 22 ? e.name.slice(0, 21) + "…" : e.name));
    }
    if (cursor != null) el.append(svg("line", { x1: X(cursor), x2: X(cursor), y1: PAD.t, y2: height - PAD.b, stroke: "#222", "stroke-width": .8 }));
    el.append(svg("text", { x: PAD.l, y: PAD.t - 2, "font-size": 11, "font-weight": 700 }, title));
    el.dataset.x0 = x0; el.dataset.x1 = x1;
    el.addEventListener("mousemove", (ev) => {
      const box = el.getBoundingClientRect(), px = (ev.clientX - box.left) / box.width * W;
      cursor = Math.max(x0, Math.min(x1 - 1, Math.round(x0 + (px - PAD.l) / (W - PAD.l - PAD.r) * (x1 - x0))));
      showTip(ev);
    });
    el.addEventListener("mouseleave", () => { cursor = null; tip.hidden = true; });
    return el;
  }

  function strip() {
    const needs = data.needs, x0 = data.days[0], x1 = data.days[data.days.length - 1] + data.step, height = 54;
    const labels = [...new Set(needs.map((n) => n.label || "(nothing)"))];
    const X = (d) => PAD.l + (d - x0) / Math.max(1, x1 - x0) * (W - PAD.l - PAD.r);
    const el = svg("svg", { viewBox: `0 0 ${W} ${height + 14}`, class: "hist-chart", role: "img", "aria-label": "What the caravan would be asked for" });
    const defs = svg("defs");
    labels.forEach((label, i) => {
      const c = COLORS[i % COLORS.length], kind = HATCHES[Math.floor(i / COLORS.length) % HATCHES.length], id = "hatch" + i;
      const pat = svg("pattern", { id, width: 6, height: 6, patternUnits: "userSpaceOnUse" }, svg("rect", { width: 6, height: 6, fill: c, opacity: kind === "solid" ? .75 : .25 }));
      if (kind === "diag") pat.append(svg("path", { d: "M0,6 L6,0", stroke: c, "stroke-width": 1.6 }));
      if (kind === "back") pat.append(svg("path", { d: "M0,0 L6,6", stroke: c, "stroke-width": 1.6 }));
      if (kind === "dots") pat.append(svg("circle", { cx: 3, cy: 3, r: 1.5, fill: c }));
      if (kind === "cross") pat.append(svg("path", { d: "M0,6 L6,0 M0,0 L6,6", stroke: c, "stroke-width": 1 }));
      if (kind === "horiz") pat.append(svg("path", { d: "M0,3 L6,3", stroke: c, "stroke-width": 1.6 }));
      defs.append(pat);
    });
    el.append(defs, svg("text", { x: PAD.l, y: 9, "font-size": 11, "font-weight": 700 }, "What the caravan would be asked for (the village's greatest need)"));
    for (const n of needs) {
      const i = labels.indexOf(n.label || "(nothing)"), x = X(n.from), w = Math.max(1.5, X(n.to + 1) - x);
      const r = svg("rect", { x, y: 14, width: w, height: height - 16, fill: `url(#hatch${i})`, stroke: COLORS[i % COLORS.length], "stroke-width": .8 });
      r.append(svg("title", {}, `${n.label || "(nothing)"}: days ${n.from} to ${n.to}\n` + n.ranking.map((q) => `${q[0]} (${fmtPrice(q[1])})`).join("\n") + (n.asked.length ? "\nasked of the caravan: " + n.asked.join(", ") : "")));
      el.append(r);
      if (w > 70) el.append(svg("text", { x: x + 3, y: 14 + (height - 16) / 2 + 4, "font-size": 10, "font-weight": 700, fill: "#111", stroke: "#fffef6", "stroke-width": 2.5, "paint-order": "stroke" }, (n.label || "").slice(0, Math.floor(w / 6))));
    }
    const legend = h("div", { class: "hist-needs-legend" }, labels.map((label, i) => {
      const days = needs.filter((n) => (n.label || "(nothing)") === label).reduce((a, n) => a + n.to - n.from + 1, 0);
      return h("span", { class: "hist-needs-item" }, svg("svg", { width: 22, height: 12 }, svg("rect", { width: 22, height: 12, fill: `url(#hatch${i})`, stroke: COLORS[i % COLORS.length] })), ` ${label} (${days} d)`);
    }));
    return h("div", {}, el, legend);
  }

  // The caravan's visits: a diamond on the night it came, the list of what it was asked for, brought, was paid and took away beneath
  function visits() {
    const list = data.caravan || [], x0 = data.days[0], x1 = data.days[data.days.length - 1] + data.step;
    if (!list.length) return h("p", { class: "hint" }, data.caravan_from == null
      ? "The caravan's visits are only written down from the night this was built on; this stretch is older (or was run before that), so it is not that the caravan stayed away: in the village it comes every 10 days."
      : `No visit in this stretch (visits are written down from night ${data.caravan_from} on).`);
    const X = (d) => PAD.l + (d - x0) / Math.max(1, x1 - x0) * (W - PAD.l - PAD.r);
    const text = (v) => `day ${v.day} (${dateOf(v.day)})\nasked for: ${v.asked.join(", ") || "-"}\nbrought: ${v.brought.join(", ") || "nothing"} (paid ${fmtPrice(v.paid_cp)})\ntook away: ${v.took.join(", ") || "nothing"}`;
    const el = svg("svg", { viewBox: `0 0 ${W} 30`, class: "hist-chart", role: "img", "aria-label": "Visits of the caravan" },
      svg("text", { x: PAD.l, y: 9, "font-size": 11, "font-weight": 700 }, "Visits of the caravan"),
      svg("line", { x1: PAD.l, x2: W - PAD.r, y1: 21, y2: 21, stroke: "#4d4d4d", "stroke-width": .8 }),
      list.map((v) => { const x = X(v.day); const d = svg("path", { d: `M${x},14 L${x + 5},21 L${x},28 L${x - 5},21 Z`, fill: "#222", stroke: "#fffef6" }); d.append(svg("title", {}, text(v))); return d; }));
    const rows = [...list].reverse().slice(0, 24);
    const table = h("table", { class: "hist-visits" },
      h("thead", {}, h("tr", {}, ["Night", "Asked for", "Brought", "Paid for it", "Took away"].map((t) => h("th", {}, t)))),
      h("tbody", {}, rows.map((v) => h("tr", {}, h("td", {}, `${v.day} (${dateOf(v.day)})`), h("td", {}, v.asked.join(", ") || "-"), h("td", {}, v.brought.join(", ") || "nothing"),
        h("td", { class: "num" }, fmtPrice(v.paid_cp)), h("td", {}, v.took.join(", ") || "nothing")))));
    return h("div", {}, el, list.length > 24 ? h("p", { class: "hint" }, `The latest 24 of ${list.length} visits are listed.`) : null, table);
  }

  let looks = {}, tip = h("div", { class: "hist-tip", hidden: true });
  function showTip(ev) {
    const key = mode === "price" || mode === "rel" ? (mode === "rel" ? "rel" : "price") : "price";
    const idx = Math.min(data.days.length - 1, Math.max(0, Math.round((cursor - data.days[0]) / data.step)));
    const rows = [...visible].filter((n) => data.series[n]).map((n) => ({ n, p: data.series[n][mode === "rel" ? "rel" : "price"][idx], s: data.series[n].stock[idx], u: data.series[n].usual[idx] }))
      .filter((r) => r.p != null).sort((a, b) => b.p - a.p).slice(0, 14);
    tip.replaceChildren(h("b", {}, `${yearOf(data.days[idx])}, day ${data.days[idx]} (${dateOf(data.days[idx])})`),
      ...rows.map((r) => h("div", { class: hover === r.n ? "hot" : "" }, `${r.n}: ${mode === "rel" ? (r.p.toFixed(2) + " x usual") : fmtPrice(r.p)}; on shelves ${r.s == null ? "plenty" : Math.round(r.s)} (usual ${Math.round(r.u || 0)})`)));
    tip.hidden = false;
    tip.style.left = Math.min(window.innerWidth - 380, ev.clientX + 14) + "px";
    tip.style.top = (ev.clientY + window.scrollY + 14) + "px";
  }

  function legend() {
    const kinds = {};
    for (const [n, s] of Object.entries(data.series)) (kinds[s.kind] ||= []).push(n);
    const groups = [["staples", STAPLES.filter((n) => data.series[n])], ...Object.entries(kinds).sort()];
    const match = (n) => !filter || n.toLowerCase().includes(filter.toLowerCase());
    const box = h("div", { class: "hist-legend" });
    for (const [g, names] of groups) {
      const shown = names.filter(match);
      if (!shown.length) continue;
      box.append(h("div", { class: "hist-group" },
        h("div", { class: "hist-group-head" }, h("b", {}, g + " (" + names.length + ")"),
          h("button", { class: "mini-button", type: "button", onclick: () => { shown.forEach((n) => visible.add(n)); draw(); } }, "all"),
          h("button", { class: "mini-button", type: "button", onclick: () => { shown.forEach((n) => visible.delete(n)); draw(); } }, "none")),
        shown.map((n) => {
          const look = looks[n], on = visible.has(n), last = data.series[n].price.filter((v) => v != null).pop();
          return h("label", { class: "hist-item" + (on ? " on" : ""), onmouseenter: () => { hover = n; redraw(); }, onmouseleave: () => { hover = null; redraw(); } },
            h("input", { type: "checkbox", checked: on, onchange: (e) => { e.target.checked ? visible.add(n) : visible.delete(n); draw(); } }),
            svg("svg", { width: 30, height: 10 }, svg("line", { x1: 0, x2: 30, y1: 5, y2: 5, stroke: look.color, "stroke-width": 2.4, "stroke-dasharray": look.dash })),
            " " + n, h("span", { class: "hint" }, " " + fmtPrice(last)));
        })));
    }
    return box;
  }

  let charts = null;
  function redraw() { if (!charts) return; charts.replaceChildren(...buildCharts()); }
  function buildCharts() {
    if (!data.days.length) return [h("p", { class: "empty-state" }, "No history yet: it is written every night, starting with the first night after this was built.")];
    const out = [h("p", { class: "hint" }, "The two charts mirror each other on purpose: the less of a good is on the shelves, the dearer it gets, and the more there is, the cheaper. " +
      "Producers answer a high price with more goods a few days later, so the amount follows the price with a delay.")];
    if (mode === "rel") out.push(h("p", { class: "hint" }, "Each price as a multiple of the good's usual price (1 = the usual): goods of every price can be compared."));
    out.push(panel(mode === "rel" ? "PRICE as a multiple of the usual price (log scale above 0.1; free is the bold 0.0)" : "PRICE of one piece: what a customer pays, in copper (log scale; free is the bold 0.0, below it a shop paying you, down to -10 cp)", mode === "rel" ? "rel" : "price", 330, 0, mode === "rel" ? "x" : "cp"));
    out.push(panel("AMOUNT FOR SALE: pieces on the shelves of all shops; the census lines (the whole flock, the living kinds) count what lives, not what is sold (log scale above 1; none is the bold 0.0)", "stock", 270, 0, "n"));
    out.push(strip());
    out.push(visits());
    return out;
  }

  function draw() {
    if (!data) return;
    looks = lookOf(Object.keys(data.series).sort());
    charts = h("div", {}, ...buildCharts());
    const range_btn = (label, f) => h("button", { class: "mini-button", type: "button", onclick: f }, label);
    const [first, last] = data.span;
    root.replaceChildren(
      h("h2", {}, "History of the village"),
      h("p", { class: "hint" }, `Nights ${first} to ${last} are written down (the village began on ${dateOf(1)}; today is day ${data.real_day}). Each line: its own colour, dash pattern and name; hover a name or a line to find it, click the names to show or hide.`),
      h("div", { class: "button-row" },
        range_btn("everything", () => reload({})), range_btn("last 10 years", () => reload({ since: Math.max(first, last - 3650) })), range_btn("last year", () => reload({ since: Math.max(first, last - 365) })),
        range_btn("last 90 days", () => reload({ since: Math.max(first, last - 90) })), range_btn("last 30 days", () => reload({ since: Math.max(first, last - 30) })),
        range_btn("last 7 days", () => reload({ since: Math.max(first, last - 7) })),
        range_btn("all lines", () => { Object.keys(data.series).forEach((n) => visible.add(n)); draw(); }), range_btn("no lines", () => { visible.clear(); draw(); }),
        h("select", { "aria-label": "What the price panel shows", onchange: (e) => { mode = e.target.value; draw(); } },
          h("option", { value: "price", selected: mode === "price" }, "price in copper"), h("option", { value: "rel", selected: mode === "rel" }, "price against the usual price")),
        h("input", { type: "search", placeholder: "find a good", value: filter, "aria-label": "Find a good", oninput: (e) => { filter = e.target.value; const keep = e.target.selectionStart; draw(); const box = root.querySelector("input[type=search]"); box.focus(); box.setSelectionRange(keep, keep); } }),
        h("span", { class: "hint" }, note)),
      charts, tip, legend());
  }

  async function reload(r) {
    range = r;
    const q = new URLSearchParams(); if (r.since != null) q.set("since", r.since); if (r.until != null) q.set("until", r.until);
    try { data = await api("GET", "history?" + q.toString()); note = ""; } catch (err) { note = err.message; }
    if (data && !visible.size) visible = new Set(STAPLES.filter((n) => data.series[n]));
    draw();
  }
  reload({});
})();
