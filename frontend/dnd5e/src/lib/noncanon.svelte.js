// Firearms, explosives and other Renaissance, modern and futuristic items (5etools `age`, DMG ch. 9) are hidden in
// every item list until the player ticks "Show noncanon" (Dodo, 2026-10-25); the choice is remembered per browser.
const KEY = "dnd5e-show-noncanon";
let initial = false;
try { initial = localStorage.getItem(KEY) === "1"; } catch (_) { /* private window */ }
export const noncanon = $state({ show: initial });
export function setNoncanon(on) {
  noncanon.show = on;
  try { localStorage.setItem(KEY, on ? "1" : "0"); } catch (_) { /* private window */ }
}
export const isNoncanon = (item) => !!item?.age;
export const canonFilter = (item) => noncanon.show || !isNoncanon(item);
