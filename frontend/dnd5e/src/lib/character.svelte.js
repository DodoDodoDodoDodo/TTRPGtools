// The open character: its decision log, the derived sheet from the server, and a debounced save.
// Edits mutate `current.character` and call `changed()`; the sheet refreshes when the save returns.
import { api } from "./api.js";

export const current = $state({
  id: null,
  character: null,
  sheet: null,
  version: 0,
  status: "idle", // idle | saving | saved | error | conflict | locked
  error: null,
  locked: null, // the server's reason when this character is read only (second character without premium)
  plothole: false, // an edit was attempted on a read-only character: App shows the Plothole popup
});

let timer = null;
let inFlight = false;
let again = false;

// Throws away unsaved local edits (a read-only character) by loading the saved version again.
export function reloadCharacter() {
  const id = current.id;
  current.id = null;
  return openCharacter(id);
}

export async function openCharacter(id) {
  if (current.id === id && current.character) return;
  current.id = id;
  current.character = null;
  current.sheet = null;
  current.status = "idle";
  current.error = null;
  try {
    const data = await api.get(id);
    current.character = data.character;
    current.sheet = data.sheet;
    current.version = data.character.version || 1;
    current.locked = data.locked || null;
  } catch (e) {
    current.status = "error";
    current.error = e.message;
  }
}

export function changed(delay = 350) {
  if (current.locked) {
    current.status = "locked";
    current.plothole = true;
    return;
  }
  current.status = "saving";
  clearTimeout(timer);
  timer = setTimeout(save, delay);
}

async function save() {
  if (inFlight) {
    again = true;
    return;
  }
  inFlight = true;
  const id = current.id;
  try {
    const data = await api.save(id, $state.snapshot(current.character), current.version);
    if (current.id === id) {
      current.version = data.character.version;
      current.sheet = data.sheet;
      current.status = "saved";
    }
  } catch (e) {
    current.status = e.status === 409 ? "conflict" : e.pitchIn ? "locked" : "error";
    current.error = e.message;
    if (e.pitchIn) { current.locked = e.message; current.plothole = true; }
  } finally {
    inFlight = false;
    if (again) {
      again = false;
      save();
    }
  }
}

export async function reload() {
  const id = current.id;
  current.id = null;
  await openCharacter(id);
}

// Helpers for the decision log's nested shape.
export function classEntry(classId) {
  return current.character.classes.find((c) => c.id === classId);
}

export function ensure(obj, key, fallback) {
  if (obj[key] === undefined || obj[key] === null) obj[key] = fallback;
  return obj[key];
}
