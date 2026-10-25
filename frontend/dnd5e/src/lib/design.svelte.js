// "Old design" (DDB's classic builder lists) or "new design" (DDB's newer cards) for the race, class and
// background choosers; one switch in the top bar for all of them, remembered per browser.
const KEY = "dodo-chooser-design";
let initial = "new";
try {
  initial = localStorage.getItem(KEY) || "new";
} catch {
  // private window or blocked storage: the default stays
}
export const design = $state({ mode: initial });

export function setDesign(mode) {
  design.mode = mode;
  try {
    localStorage.setItem(KEY, mode);
  } catch {
    // not remembered, still switched for this page
  }
}
