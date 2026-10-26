// Shared helpers for the DCC pages: DOM builder, JSON calls, the guide overlay, "What is this?", background music.
"use strict";

const DCC = (() => {
  const root = document.body.dataset.root;
  const store = {
    get(key, fallback) { try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; } },
    set(key, value) { try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* private mode */ } },
  };

  // Text only, never innerHTML: rule text and names come from files and users.
  function h(tag, attrs, ...kids) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === null || v === undefined || v === false) continue;
      if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
      else if (k in el && k !== "list" && typeof v !== "string") el[k] = v;
      else el.setAttribute(k === "className" ? "class" : k, v === true ? "" : v);
    }
    el.append(...kids.flat(Infinity).filter((kid) => kid !== null && kid !== undefined && kid !== false));
    return el;
  }

  // The server names its version with every answer. When that changes under an open page, the page says so once.
  let build = null;
  function stale(now) {
    if (!now || now === build) return;
    if (build === null) { build = now; return; }
    build = now;
    if (document.getElementById("stale")) return;
    document.body.append(h("div", { id: "stale", class: "explain-banner", role: "status", style: "bottom:auto;top:.6rem;z-index:960" },
      "This page was updated on the server. ", h("button", { class: "mini-button", type: "button", onclick: () => location.reload() }, "Reload")));
  }

  async function api(method, path, body) {
    const resp = await fetch(root + "api/" + path, { method, headers: body ? { "Content-Type": "application/json" } : {},
                                                     body: body ? JSON.stringify(body) : undefined });
    stale(resp.headers.get("X-DCC-Build"));
    const data = await resp.json().catch(() => ({ error: "The server sent no readable answer (" + resp.status + ")." }));
    if (!resp.ok || data.error) throw new Error(data.error || "Request failed (" + resp.status + ").");
    return data;
  }

  const clamp = (n, lo, hi) => Math.max(lo, Math.min(hi, n));
  // Money is written as gold with two decimals, like cents: 1002 copper is "10,02 gp" (1 gp = 100 cp).
  const gp = (cp) => Math.floor(cp / 100).toLocaleString("de-DE") + "," + String(Math.round(cp) % 100).padStart(2, "0") + " gp";

  // One moon counts the old way (places.py, "numerals"): for a character bound to it, every number in town is written
  // in Roman numerals. The sums are the same. Thousands from four thousand up carry a bar (X\u0305 is ten thousand), nothing
  // is N (nulla), and parts of a whole are twelfths: a dot each, S for a half. Money is gold and copper apart, rounded.
  const ROMAN = [[1000, "M"], [900, "CM"], [500, "D"], [400, "CD"], [100, "C"], [90, "XC"], [50, "L"], [40, "XL"], [10, "X"], [9, "IX"], [5, "V"], [4, "IV"], [1, "I"]];
  function roman(n) {
    n = Math.floor(n);
    if (n <= 0) return "N";
    const plain = (v) => { let out = ""; for (const [value, sign] of ROMAN) while (v >= value) { out += sign; v -= value; } return out; };
    if (n < 4000) return plain(n);
    const thousands = Math.floor(n / 1000), rest = n % 1000;
    return (thousands < 4000 ? [...plain(thousands)].map((sign) => sign + "\u0305").join("") : "(" + roman(thousands) + ")") + plain(rest);
  }
  // Sums of money are rounded for the eye, or they grow too long to read. Candidates are the sum to one figure, to a
  // multiple of five, and to two figures; of those within 8 percent the shortest to read wins, where 3 percent of
  // error counts like one more letter. Only what is written is rounded, never what is charged.
  const coins = (sum) => { const g = Math.floor(sum / 100), c = sum % 100;
    return !g && !c ? "N gp" : [g ? roman(g) + " gp" : "", c ? roman(c) + " cp" : ""].filter(Boolean).join(" "); };
  function roundSum(n) {
    if (n < 10) return n;
    const top = 10 ** Math.floor(Math.log10(n));
    let best = n, bestScore = Infinity;
    for (const step of [top, top / 2, top / 10]) {
      const near = Math.round(n / step) * step, off = Math.abs(near - n) / n * 100;
      const score = coins(near).replace(/[^IVXLCDMN]/g, "").length + off / 3;
      if (off <= 8 && score < bestScore) { best = near; bestScore = score; }
    }
    return best;
  }
  function romanText(text) {
    const money = text.replace(/(\d{1,3}(?:\.\d{3})*),(\d{2})\s?gp/g, (all, gold, copper) => coins(roundSum(Number(gold.replace(/\./g, "")) * 100 + Number(copper))));
    return money.replace(/\b(\d+)(?:,(\d+))?\b/g, (all, whole, part) => {
      let n = Number(whole), twelfths = part ? Math.round(Number("0." + part) * 12) : 0;
      if (twelfths === 12) { n += 1; twelfths = 0; }
      const parts = (twelfths >= 6 ? "S" : "") + "\u00b7".repeat(twelfths % 6);
      return n || !parts ? roman(n) + parts : parts;
    });
  }
  function romanize(root) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    for (const node of nodes) {
      if (!/\d/.test(node.nodeValue) || node.parentElement.closest("select, textarea, script, style, svg, #judge, .judge-box, .judge-row")) continue;
      node.nodeValue = romanText(node.nodeValue);   // the admin's tools keep plain numbers
    }
  }

  // ---------------------------------------------------------------- guide overlay
  const tour = {
    steps: [], index: 0, parts: null,
    seen: (id) => store.get("dcc-guide-seen", []).includes(id),
    auto(id, steps) { if (!store.get("dcc-guide-off", false) && !tour.seen(id)) tour.start(id, steps); },
    start(id, steps) {
      tour.stop();
      tour.steps = steps.filter((s) => tour.find(s));
      if (!tour.steps.length) return;
      store.set("dcc-guide-seen", [...new Set([...store.get("dcc-guide-seen", []), id])]);
      const text = h("p", {}), count = h("span", { class: "count" });
      const back = h("button", { class: "mini-button", type: "button", onclick: () => tour.show(tour.index - 1) }, "Back");
      const next = h("button", { class: "button", type: "button", onclick: () => tour.show(tour.index + 1) }, "Next");
      const dismiss = h("button", { class: "mini-button", type: "button", title: "Close and do not start guides by themselves again",
                                    onclick: () => { store.set("dcc-guide-off", true); tour.stop(); } }, "Dismiss");
      const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      svg.setAttribute("class", "tour-arrow");
      const path = document.createElementNS(svg.namespaceURI, "path"), head = document.createElementNS(svg.namespaceURI, "path");
      svg.append(path, head);
      const card = h("div", { class: "tour-card", role: "dialog", "aria-label": "Guide" }, text, h("div", { class: "row" }, count, dismiss, back, next));
      const hole = h("div", { class: "tour-hole" });
      document.body.append(hole, svg, card);
      tour.parts = { hole, svg, path, head, card, text, count, back, next };
      addEventListener("keydown", tour.key);
      tour.show(0);
      // Follow the target every frame: late fonts, redraws and scrolling all move it without any event to listen for.
      const follow = () => { if (tour.parts) { tour.place(); requestAnimationFrame(follow); } };
      requestAnimationFrame(follow);
    },
    find: (step) => (typeof step.target === "function" ? step.target() : document.querySelector(step.target)),
    show(i) {
      if (i >= tour.steps.length) return tour.stop();
      tour.index = clamp(i, 0, tour.steps.length - 1);
      const step = tour.steps[tour.index], p = tour.parts;
      p.text.textContent = step.text;
      p.count.textContent = `Step ${tour.index + 1} of ${tour.steps.length}`;
      p.back.disabled = tour.index === 0;
      p.next.textContent = tour.index === tour.steps.length - 1 ? "Done" : "Next";
      const target = tour.find(step);
      if (target) target.scrollIntoView({ block: "center", behavior: "instant" });
      tour.place();
      p.next.focus({ preventScroll: true });
    },
    place() {
      const p = tour.parts, target = p && tour.find(tour.steps[tour.index]);
      if (!target) return;
      const r = target.getBoundingClientRect(), pad = 6, vw = innerWidth, vh = innerHeight;
      Object.assign(p.hole.style, { left: r.left - pad + "px", top: r.top - pad + "px", width: r.width + 2 * pad + "px", height: r.height + 2 * pad + "px" });
      const c = p.card.getBoundingClientRect(), gap = 46;
      const below = r.bottom + gap + c.height < vh, above = r.top - gap - c.height > 0;
      let top = below ? r.bottom + gap : above ? r.top - gap - c.height : clamp(r.top, 12, vh - c.height - 12);
      let left = below || above ? clamp(r.left + r.width / 2 - c.width / 2, 12, vw - c.width - 12)
                                : (r.right + gap + c.width < vw ? r.right + gap : Math.max(12, r.left - gap - c.width));
      Object.assign(p.card.style, { top: top + "px", left: left + "px" });
      // Arrow from the card edge to the edge of the lit field, bent a little like a pen stroke.
      const from = below ? [left + c.width / 2, top] : above ? [left + c.width / 2, top + c.height] : [left < r.left ? left + c.width : left, top + c.height / 2];
      const to = below ? [r.left + r.width / 2, r.bottom + pad + 4] : above ? [r.left + r.width / 2, r.top - pad - 4]
                       : [left < r.left ? r.left - pad - 4 : r.right + pad + 4, r.top + r.height / 2];
      const mid = [(from[0] + to[0]) / 2 + (to[1] - from[1]) * 0.25, (from[1] + to[1]) / 2 - (to[0] - from[0]) * 0.25];
      p.path.setAttribute("d", `M${from} Q${mid} ${to}`);
      const angle = Math.atan2(to[1] - mid[1], to[0] - mid[0]), wing = (a) => [to[0] - 13 * Math.cos(angle + a), to[1] - 13 * Math.sin(angle + a)];
      p.head.setAttribute("d", `M${wing(0.5)} L${to} L${wing(-0.5)}`);
    },
    key(e) {
      if (e.key === "Escape") tour.stop();
      else if (e.key === "ArrowRight" && !/INPUT|SELECT|TEXTAREA/.test(document.activeElement.tagName)) tour.show(tour.index + 1);
      else if (e.key === "ArrowLeft" && !/INPUT|SELECT|TEXTAREA/.test(document.activeElement.tagName)) tour.show(tour.index - 1);
    },
    stop() {
      if (!tour.parts) return;
      for (const part of [tour.parts.hole, tour.parts.svg, tour.parts.card]) part.remove();
      removeEventListener("keydown", tour.key);
      tour.parts = null;
    },
  };

  // "What is this?" moved to the shared helper (static/helper.js, 2026-10-26); the Guide and Music stay here.


  // ---------------------------------------------------------------- music
  const music = {
    audio: null, tracks: [], index: 0, slider: null,
    button: document.getElementById("assist-music"),
    async toggle(state) {
      const on = state ?? music.button.getAttribute("aria-pressed") !== "true";
      store.set("dcc-music", on);
      music.button.setAttribute("aria-pressed", on);
      if (!on) { if (music.audio) music.audio.pause(); if (music.slider) { music.slider.remove(); music.slider = null; } return; }
      if (!music.audio) {
        const data = await fetch(root + "music").then((r) => r.json()).catch(() => ({ tracks: [] }));
        music.tracks = data.tracks; music.credit = data.credit || "";
        if (!music.tracks.length) { music.button.title = "No music files in content/dcc/music"; music.button.setAttribute("aria-pressed", false); return; }
        music.audio = new Audio();
        music.audio.volume = store.get("dcc-music-vol", 0.3);
        music.audio.addEventListener("ended", () => music.play(music.index + 1, 0));
        addEventListener("pagehide", () => { try { sessionStorage.setItem("dcc-music-pos", JSON.stringify([music.index, music.audio.currentTime])); } catch { /* ignore */ } });
      }
      music.slider = h("input", { type: "range", min: 0, max: 1, step: 0.05, value: music.audio.volume, "aria-label": "Music volume",
                                  oninput: (e) => { music.audio.volume = Number(e.target.value); store.set("dcc-music-vol", music.audio.volume); } });
      music.button.after(music.slider);
      let pos = [0, 0];
      try { pos = JSON.parse(sessionStorage.getItem("dcc-music-pos")) || pos; } catch { /* ignore */ }
      music.play(pos[0], pos[1]);
    },
    play(index, time) {
      music.index = ((index % music.tracks.length) + music.tracks.length) % music.tracks.length;
      const name = music.tracks[music.index];
      music.audio.src = root + "music/" + encodeURIComponent(name);
      music.audio.currentTime = time || 0;
      music.button.title = "Playing: " + name.replace(/\.\w+$/, "") + (music.credit ? ". " + music.credit : "");
      // Browsers refuse sound before the first click on a page; start on that click instead.
      music.audio.play().catch(() => addEventListener("pointerdown", () => store.get("dcc-music", false) && music.audio.play(), { once: true }));
    },
  };

  music.button.addEventListener("click", () => music.toggle());
  document.getElementById("assist-guide").addEventListener("click", () => {
    store.set("dcc-guide-off", false);
    const guide = DCC.guide && DCC.guide();
    if (guide) tour.start(guide.id, guide.steps);
  });
  if (store.get("dcc-music", false)) music.toggle(true);

  // Paper (dcc.css, textures/). Every panel is a piece of sheet paper of its own; every darker field lying on a panel
  // is a piece of card. Which tile a piece gets and where it lies follow from its heading and its place on the page,
  // so a redraw gives the same piece the same paper.
  const PAPER = [
    { pick: ".panel, .masthead", tiles: 6, mark: "", size: 384 },
    { pick: ".stat-box, .ability, .note, .mercurial, .notices, .debt-counter, .error-banner, .die-box, .xp-block > div, "
            + ".button, .roll, .mini-button, .assist-bar button, .market .price, button.card, a.card", tiles: 4, mark: "c", size: 256 }];
  function layPaper() {
    for (const kind of PAPER) {
      let last = "";
      document.querySelectorAll(kind.pick).forEach((piece, place) => {
        if (!piece.dataset.paper) {
          const heading = piece.querySelector("h1, h2, h3");
          let hash = 2166136261;
          for (const letter of kind.mark + (heading ? heading.textContent : "") + "#" + place) hash = Math.imul(hash ^ letter.codePointAt(0), 16777619) >>> 0;
          let tile = 1 + hash % kind.tiles;
          if (kind.mark + tile === last) tile = 1 + tile % kind.tiles;  // neighbours never share a tile
          piece.dataset.paper = kind.mark + tile;
          piece.style.setProperty("--paper-x", -((hash >>> 4) % kind.size) + "px");
          piece.style.setProperty("--paper-y", -((hash >>> 14) % kind.size) + "px");
        }
        last = piece.dataset.paper;
      });
    }
  }
  layPaper();
  new MutationObserver(layPaper).observe(document.body, { childList: true, subtree: true });

  // The header follows the reader (dcc.css). Things that stick below it need to know how tall it is right now.
  const masthead = document.querySelector(".masthead");
  if (masthead && window.ResizeObserver) {
    new ResizeObserver(() => document.documentElement.style.setProperty("--masthead-h", masthead.offsetHeight + "px")).observe(masthead);
  }

  return { root, h, api, gp, store, tour, roman, romanText, romanize, guide: null, context: null };
})();
