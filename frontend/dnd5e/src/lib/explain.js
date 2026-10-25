// The rules helper (builder_routes /api/explain): streams the local model's answer as server-sent events.
const API = window.DND5E.api;
const KEY = "dnd5e-explain-sources";

export async function loadSources() {
  try {
    const r = await fetch(`${API}/explain/sources`);
    return r.ok ? (await r.json()).sources : [];
  } catch (_) { return []; }
}

// The books a question searches: this browser's choice, else only the rules books (no spoilers by default).
export function chosenSources(all) {
  try {
    const saved = JSON.parse(localStorage.getItem(KEY) || "null");
    if (Array.isArray(saved)) return saved.filter((id) => all.some((s) => s.id === id));
  } catch (_) { /* private window */ }
  return all.filter((s) => s.group === "rules").map((s) => s.id);
}
export function saveSources(ids) {
  try { localStorage.setItem(KEY, JSON.stringify(ids)); } catch (_) { /* private window */ }
}

export async function ask(payload, { onText, onDone, onError }) {
  let response;
  try {
    response = await fetch(`${API}/explain`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  } catch (_) { onError("Model currently unavailable."); return; }
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    onError(data.error || "Model currently unavailable.", data.pitch_in);
    return;
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let cut;
    while ((cut = buffer.indexOf("\n\n")) >= 0) {
      const line = buffer.slice(0, cut).trim();
      buffer = buffer.slice(cut + 2);
      if (!line.startsWith("data:")) continue;
      const event = JSON.parse(line.slice(5));
      if (event.text) onText(event.text);
      if (event.error) onError(event.error);
      if (event.done) onDone(event.passages || []);
    }
  }
}
