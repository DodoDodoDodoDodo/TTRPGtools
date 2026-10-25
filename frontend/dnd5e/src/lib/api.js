// JSON API of builder_routes.py. Errors come back as {"error": "..."}; we throw them as Error(message).
const API = window.DND5E.api;

async function call(method, path, body) {
  const response = await fetch(`${API}${path}`, {
    method,
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(data.error || `HTTP ${response.status}`);
    error.status = response.status;
    error.pitchIn = data.pitch_in || null;
    error.doomed = data.doomed || null;
    throw error;
  }
  return data;
}

export const api = {
  content: (kind) => call("GET", `/content/${kind}`),
  list: () => call("GET", "/characters"),
  create: (name) => call("POST", "/characters", { name }),
  get: (id) => call("GET", `/characters/${id}`),
  save: (id, character, version) => call("PUT", `/characters/${id}`, { character, version }),
  remove: (id) => call("DELETE", `/characters/${id}`),
  copy: (id) => call("POST", `/characters/${id}/copy`),
  history: (id) => call("GET", `/characters/${id}/history`),
  revert: (id, day) => call("POST", `/characters/${id}/revert`, { day }),
  importDdb: (ref) => call("POST", "/import-ddb", { ref }),
  users: (all = false) => call("GET", `/users${all ? "?all=1" : ""}`),
  assign: (id, owner) => call("PUT", `/characters/${id}/owner`, { owner }),
  campaigns: () => call("GET", "/campaigns"),
  createCampaign: (name) => call("POST", "/campaigns", { name }),
  joinCampaign: (campaignId, characterId) => call("POST", `/campaigns/${campaignId}/characters`, { character_id: characterId }),
  leaveCampaign: (campaignId, characterId) => call("DELETE", `/campaigns/${campaignId}/characters/${characterId}`),
  deleteCampaign: (campaignId) => call("DELETE", `/campaigns/${campaignId}`),
};

export const frame = (name, theme) =>
  `${window.DND5E.ddb}/frame/${name}${theme ? `?theme=${theme.replace("#", "")}` : ""}`;
