// Item rules shared by the inventory table and the item pane.
export const typeCode = (item) => String(item?.type || "").split("|")[0];

const WORN_OR_WIELDED = new Set(["M", "R", "LA", "MA", "HA", "S", "RG", "RD", "WD", "ST"]);
// Consumables, focuses and trade goods are never "active" on DDB.
const NEVER_ACTIVE = new Set(["P", "SC", "A", "FD", "EXP", "$", "$G", "$A", "$C", "TG", "SCF", "G", "AT", "T", "GS", "INS"]);

export function equippable(item) {
  if (!item) return false;
  const code = typeCode(item);
  if (WORN_OR_WIELDED.has(code)) return true;
  if (NEVER_ACTIVE.has(code) && !item.reqAttune) return false;
  return !!item.reqAttune || !!item.bonusAc || !!item.wondrous;
}

export const STACKABLE = new Set(["A", "G", "P", "SC", "FD", "TG", "$", "$G", "$A", "$C", "EXP"]);

// DDB's per-type item icons (private copies); gear has no known icon yet, so it shows none.
const ICON_FOR = { M: "weapon", R: "weapon", A: "weapon", LA: "armor", MA: "armor", HA: "armor", S: "armor", P: "potion", RG: "ring", RD: "rod", SC: "scroll", ST: "staff", WD: "wand" };
export function itemIcon(item) {
  if (!item) return null;
  if (item.ddbImage) return `${window.DND5E.ddb}/img/magic-items/${item.ddbImage}`;
  const name = item.rarity === "artifact" ? "artifact" : ICON_FOR[typeCode(item)] || (item.wondrous ? "wondrousitem" : null);
  return name ? `${window.DND5E.ddb}/assets/www.dndbeyond.com/content/skins/waterdeep/images/icons/item_types/${name}.jpg` : null;
}

const newUid = () => Math.random().toString(36).slice(2, 10);

// A pack becomes its contents (PHB p. 151), stowed in the pack's own backpack or chest, as on D&D Beyond.
// `inside` puts the whole pack into a container the player chose.
export function packSlots(pack, itemByRef, inside) {
  const contents = pack.packContents.map((e) => typeof e === "string" ? { item: e } : e);
  const holder = contents.map((e) => e.item && itemByRef(e.item)).find((it) => it?.containerCapacity);
  const holderSlot = holder ? { id: holder.id, qty: 1, equipped: false, attuned: false, uid: newUid(), ...(inside ? { inside } : {}) } : null;
  const into = holderSlot?.uid || inside;
  const slots = holderSlot ? [holderSlot] : [];
  for (const entry of contents) {
    const it = entry.item && itemByRef(entry.item);
    const qty = entry.quantity || 1;
    if (it && it === holder) continue;
    if (it) slots.push({ id: it.id, qty, equipped: false, attuned: false, uid: newUid(), ...(into ? { inside: into } : {}) });
    else if (entry.special) slots.push({ custom: { name: entry.special, weight: 0 }, qty, uid: newUid(), ...(into ? { inside: into } : {}) });
  }
  return slots;
}
