// The hub's "Continue" tiles: characters, campaigns and encounters come from the server (the player's own,
// last saved); equipment, monsters and rules are remembered by this browser when they are opened.
"use strict";

const HUB = window.DND5E_HUB;
const CHARS = HUB.api.replace(/api$/, "");
const ENCOUNTERS = HUB.api.replace(/characters\/api$/, "");

function show(key, name, detail, href) {
  const tile = document.querySelector(`[data-recent="${key}"]`);
  if (!tile || !name) return;
  tile.querySelector(".hub-recent-name").textContent = name;
  tile.querySelector(".hub-recent-detail").textContent = detail || "";
  tile.href = href;
  tile.hidden = false;
}

function remembered() {
  try { return JSON.parse(localStorage.getItem("dnd5e-recent") || "{}"); } catch (_) { return {}; }
}

(async () => {
  const local = remembered();
  for (const key of ["equipment", "monster", "other"]) {
    const r = local[key];
    if (r && r.name && r.href) show(key, r.name, r.detail, r.href);
  }
  if (!HUB.user) return;
  try {
    const response = await fetch(HUB.api + "/recent");
    const data = response.ok ? await response.json() : {};
    if (data.character) show("character", data.character.name, data.character.detail, `${CHARS}#/c/${data.character.id}/sheet`);
    if (data.campaign) show("campaign", data.campaign.name, "Campaign", `${CHARS}#/campaigns/${data.campaign.id}`);
    if (data.encounter) show("encounter", data.encounter.name, "Encounter", `${ENCOUNTERS}encounter/${data.encounter.id}`);
  } catch (_) { /* the tiles still work without their Continue links */ }
})();
