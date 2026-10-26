// The page helper, shared by every site that has one (Dodo, 2026-10-26): a button in the header opens a small
// window with a question box; "What is this?" inside it turns on click-to-explain, where a click on anything
// sends the element's breadcrumb (its ancestor chain), HTML and surrounding text to the site's explain endpoint.
// Follow-up questions continue the thread shown in the window; "New thread" forgets it.
// Config: window.DODO_HELPER = { api, site, header (selector the button mounts into), title, placeholder, extra() }.
"use strict";
(() => {
  const cfg = window.DODO_HELPER || {};
  const API = cfg.api;
  if (!API) return;
  const KEY = "helper-sources";
  let sources = [], chosen = null, open = false, busy = false, mode = false, marked = null, banner = null, request = null, pending = null, thread = [];

  const el = (tag, attrs, ...kids) => {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) k === "class" ? (n.className = v) : k.startsWith("on") ? n.addEventListener(k.slice(2), v) : n.setAttribute(k, v);
    for (const c of kids.flat()) if (c != null) n.append(c.nodeType ? c : document.createTextNode(String(c)));
    return n;
  };

  // --- book picker (only on sites whose api offers /explain/sources) ---------------------------------------
  function chosenIds() {
    if (chosen === null) {
      let saved = null;
      try { saved = JSON.parse(localStorage.getItem(KEY) || "null"); } catch (_) { /* private window */ }
      chosen = (Array.isArray(saved) ? saved : sources.filter((s) => s.group === "rules").map((s) => s.id)).filter((id) => sources.some((s) => s.id === id));
    }
    return chosen;
  }
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(chosen)); } catch (_) { /* private window */ } };
  const picker = el("details", { class: "rh-picker", hidden: "" });
  function drawPicker() {
    picker.hidden = !sources.length;
    picker.replaceChildren(el("summary", {}, `Search in: ${chosenIds().length} of ${sources.length} books`));
    for (const [g, label] of [["rules", "Rules"], ["adventures", "Adventures"], ["other", "Other"]]) {
      const books = sources.filter((s) => s.group === g);
      if (!books.length) continue;
      const groupBox = el("input", { type: "checkbox", onchange: (e) => { const ids = books.map((b) => b.id); chosen = e.target.checked ? [...new Set([...chosenIds(), ...ids])] : chosenIds().filter((id) => !ids.includes(id)); save(); drawPicker(); } });
      groupBox.checked = books.every((b) => chosenIds().includes(b.id));
      const list = el("div", { class: "rh-books" }, books.map((b) => {
        const box = el("input", { type: "checkbox", onchange: () => { chosen = chosenIds().includes(b.id) ? chosenIds().filter((x) => x !== b.id) : [...chosenIds(), b.id]; save(); drawPicker(); } });
        box.checked = chosenIds().includes(b.id);
        return el("label", {}, box, " ", b.name);
      }));
      picker.append(el("fieldset", { class: "rh-group" }, el("legend", {}, el("label", {}, groupBox, ` ${label} (${books.length})`)), list));
    }
  }

  // --- the window ------------------------------------------------------------------------------------------
  const input = el("input", { type: "text", placeholder: cfg.placeholder || "Ask a rules question, e.g. how does cover work?", "aria-label": "Question" });
  const askBtn = el("button", { type: "submit", class: "rh-ask" }, "Ask");
  const modeBtn = el("button", { type: "button", class: "rh-mode", "aria-pressed": "false", title: "Then click anything on the page", onclick: () => setMode(!mode) }, "What is this?");
  const chip = el("div", { class: "rh-chip", hidden: "" });
  const answer = el("div", { class: "rh-answer", "aria-live": "polite" });
  function reset() { thread = []; pending = null; mark(null); chip.hidden = true; answer.replaceChildren(); input.value = ""; input.focus(); }
  function showChip() {
    chip.hidden = !pending;
    if (pending) chip.replaceChildren(`Selected: ${pending.heading}`, el("button", { type: "button", "aria-label": "Clear selection", onclick: () => { pending = null; mark(null); chip.hidden = true; } }, "×"));
  }
  const win = el("section", { class: "rh-window", hidden: "", "aria-label": "Helper" },
    el("header", { class: "rh-head" }, el("strong", {}, cfg.title || "Rules helper"),
      el("span", { class: "rh-sub" }, "local model, cites pages; 1 question an hour free, 100 a day with premium"),
      el("button", { type: "button", class: "rh-new", title: "Forget this conversation and the selected element", onclick: () => reset() }, "New thread"),
      el("button", { type: "button", class: "rh-close", "aria-label": "Close", onclick: () => toggle(false) }, "×")),
    el("form", { class: "rh-form", onsubmit: (e) => { e.preventDefault(); run({ ...(pending || {}), question: input.value.trim() }); } }, input, askBtn, modeBtn),
    chip, answer, picker);
  const button = el("button", { type: "button", class: "rh-button", "aria-pressed": "false", onclick: () => toggle() }, cfg.title || "Rules helper");

  async function toggle(force) {
    open = force === undefined ? !open : force;
    win.hidden = !open;
    button.setAttribute("aria-pressed", String(open));
    if (!open) setMode(false);
    if (open && !sources.length && !picker.dataset.tried) {
      picker.dataset.tried = "1";
      try { const r = await fetch(`${API}/explain/sources`); sources = r.ok ? (await r.json()).sources || [] : []; } catch (_) { sources = []; }
      drawPicker();
    }
    if (open) input.focus();
  }

  // --- click-to-explain: breadcrumb + element + surrounding text -----------------------------------------
  const ours = (n) => n.closest && n.closest(".rh-window, .rh-button, .assist-bar, .explain-banner");
  function pick(target) {  // the smallest element that still says something
    let n = target.nodeType === 1 ? target : target.parentElement;
    while (n && n !== document.body && !(n.innerText || n.value || n.getAttribute("aria-label") || "").trim()) n = n.parentElement;
    return !n || n === document.body || n.tagName === "MAIN" ? null : n;
  }
  function crumb(n) {  // one ancestor as the model sees it: tag, id, classes, name, and the heading or label it carries
    const own = (n.tagName === "LABEL" || /^H[1-6]$/.test(n.tagName) || n.tagName === "SUMMARY" || n.tagName === "LEGEND") ? n.innerText
      : n.dataset.explain || n.getAttribute("aria-label") || (n.querySelector && [...n.children].find((c) => /^H[1-6]$/.test(c.tagName))?.innerText) || "";
    return { tag: n.tagName, id: n.id || "", class: [...n.classList].filter((c) => !/^(styles?_|css-|sc-)/.test(c)).slice(0, 3).join(" "),
             name: n.getAttribute("name") || "", label: String(own || "").trim().slice(0, 60) };
  }
  function describe(n) {
    const chain = [];
    for (let a = n; a && a !== document.documentElement; a = a.parentElement) chain.unshift(crumb(a));
    const hints = chain.map((c) => c.label).filter(Boolean);
    const box = n.closest(".panel, section, .card, tr, li, fieldset, form") || n.parentElement;
    return { breadcrumb: chain.slice(-12), html: n.outerHTML.slice(0, 2200), text: (n.innerText || n.value || "").trim().slice(0, 300),
             hint: [...new Set(hints)].join("; "), context: (box ? box.innerText : "").trim().slice(0, 1200), page: document.title };
  }
  function mark(n) { if (marked) marked.classList.remove("explain-target"); marked = n; if (n) n.classList.add("explain-target"); }
  function setMode(on) {
    mode = on;
    document.body.classList.toggle("explain-mode", on);
    modeBtn.setAttribute("aria-pressed", String(on));
    mark(null);
    if (on && !banner) { banner = el("div", { class: "explain-banner" }, "Click anything on the page to have it explained. Esc leaves."); document.body.append(banner); }
    if (!on && banner) { banner.remove(); banner = null; }
  }
  document.addEventListener("click", (e) => {
    if (!mode || ours(e.target)) return;
    const n = pick(e.target);
    if (!n) return;
    e.preventDefault(); e.stopPropagation();
    // the click only selects (Dodo, 2026-10-26): the player types what they want to know, then presses Ask
    setMode(false);
    mark(n);
    pending = describe(n);
    pending.heading = pending.hint.split(";")[0] || pending.text.slice(0, 48);
    toggle(true);
    showChip();
    answer.append(el("p", { class: "rh-dim" }, "Type your question about it, or press Ask for a general explanation."));
    for (const x of [input, askBtn]) x.classList.add("rh-hot");
    input.focus();
  }, true);
  document.addEventListener("mouseover", (e) => { if (mode && !ours(e.target)) mark(pick(e.target)); }, true);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") setMode(false); });

  // --- asking -----------------------------------------------------------------------------------------------
  // every question carries what the player sees right now (the character or monster on screen) and the site's own
  // data for it, so "what actions can my character do?" is answered for THAT character (Dodo, 2026-10-26)
  function onScreen() {
    const main = document.querySelector("main") || document.body;
    return { site_data: cfg.extra ? cfg.extra() : "", page_text: (main.innerText || "").replace(/\n{3,}/g, "\n\n").slice(0, 6000) };
  }
  function draw(live) {  // the whole thread, then the live turn (question + streaming answer)
    answer.replaceChildren(...thread.flatMap((t) => [el("p", { class: "rh-q" }, t.q), el("p", { class: "rh-a" }, t.a)]), ...(live ? [live.q, live.a] : []));
    answer.scrollTop = answer.scrollHeight;
  }
  async function run(payload) {
    if (busy || (!payload.question && !payload.html && !payload.entry)) return;
    if (request) request.abort();
    request = new AbortController();
    busy = true; askBtn.textContent = "Thinking…"; askBtn.disabled = true;
    for (const x of [input, askBtn]) x.classList.remove("rh-hot");
    const shown = payload.question || (payload.entry ? `Explain ${payload.entry.name}` : `What is this? (${pending ? pending.heading : ""})`);
    const live = { q: el("p", { class: "rh-q" }, shown), a: el("p", { class: "rh-a rh-dim" }, "Looking it up… the first question after a break waits for the model to load.") };
    draw(live);
    input.value = "";
    let text = "", passages = [];
    try {
      const r = await fetch(`${API}/explain`, { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...payload, ...onScreen(), thread: thread.slice(-6), sources: chosenIds() }), signal: request.signal });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        live.a.className = "rh-a rh-error";
        live.a.replaceChildren(d.error || "Model currently unavailable.", ...(d.pitch_in ? [" ", el("a", { href: d.pitch_in }, "Pitch in · get dodo-dodo premium")] : []));
        return;
      }
      live.a.className = "rh-a";
      const reader = r.body.getReader(), dec = new TextDecoder();
      let buf = "";
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        let cut;
        while ((cut = buf.indexOf("\n\n")) >= 0) {
          const line = buf.slice(0, cut).trim(); buf = buf.slice(cut + 2);
          if (!line.startsWith("data:")) continue;
          const ev = JSON.parse(line.slice(5));
          if (ev.text) { text += ev.text; live.a.textContent = text; answer.scrollTop = answer.scrollHeight; }
          if (ev.error) answer.append(el("p", { class: "rh-error" }, ev.error));
          if (ev.done) passages = ev.passages || [];
        }
      }
      if (text) thread.push({ q: shown, a: text });
      if (passages.length) answer.append(el("details", { class: "rh-sources" }, el("summary", {}, `Passages it read (${passages.length})`),
        passages.map((x) => el("p", {}, el("strong", {}, x.cite), x.title ? ` · ${x.title}` : "", el("br"), el("span", { class: "rh-dim" }, x.text)))));
    } catch (err) {
      if (err.name !== "AbortError") { live.a.className = "rh-a rh-error"; live.a.textContent = "Model currently unavailable."; }
    } finally {
      busy = false; askBtn.textContent = "Ask"; askBtn.disabled = false;
    }
  }

  window.DODO_HELPER.explain = (entry) => { toggle(true).then(() => run({ entry, question: "" })); };
  window.DODO_HELPER.explainMode = () => { toggle(true).then(() => setMode(true)); };
  window.DODO_HELPER.mount = (header) => { header.append(button); document.body.append(win); };
  const header = document.querySelector(cfg.header || ".hub-bar, .topbar");
  if (header) window.DODO_HELPER.mount(header);
})();
