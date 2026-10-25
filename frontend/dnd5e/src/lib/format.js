// Small display helpers shared by the builder and the sheet.
export const ABILITIES = ["str", "dex", "con", "int", "wis", "cha"];
export const ABILITY_NAMES = { str: "Strength", dex: "Dexterity", con: "Constitution", int: "Intelligence", wis: "Wisdom", cha: "Charisma" };
export const SKILLS = {
  acrobatics: "dex", "animal handling": "wis", arcana: "int", athletics: "str", deception: "cha", history: "int",
  insight: "wis", intimidation: "cha", investigation: "int", medicine: "wis", nature: "int", perception: "wis",
  performance: "cha", persuasion: "cha", religion: "int", "sleight of hand": "dex", stealth: "dex", survival: "wis",
};
export const SCHOOLS = { A: "Abjuration", C: "Conjuration", D: "Divination", E: "Enchantment", V: "Evocation", I: "Illusion", N: "Necromancy", T: "Transmutation" };
export const DAMAGE = { A: "acid", B: "bludgeoning", C: "cold", F: "fire", O: "force", L: "lightning", N: "necrotic", P: "piercing", I: "poison", Y: "psychic", R: "radiant", S: "slashing", T: "thunder" };
export const ITEM_TYPES = {
  LA: "Light armor", MA: "Medium armor", HA: "Heavy armor", S: "Shield", M: "Melee weapon", R: "Ranged weapon",
  A: "Ammunition", G: "Adventuring gear", AT: "Artisan's tools", T: "Tools", GS: "Gaming set", INS: "Instrument",
  SCF: "Spellcasting focus", P: "Potion", SC: "Scroll", RD: "Rod", RG: "Ring", WD: "Wand", W: "Wondrous item",
  MNT: "Mount", VEH: "Vehicle", TAH: "Tack and harness", TG: "Trade good", FD: "Food and drink", $: "Treasure",
  EXP: "Explosive", OTH: "Other", AF: "Ammunition (futuristic)", $G: "Gemstone", $A: "Art Object", $C: "Coins",
  SHP: "Ship", AIR: "Airship", SPC: "Spelljammer Ship",
};
export const BOOKS = {
  phb: "Player's Handbook", dmg: "Dungeon Master's Guide", xge: "Xanathar's Guide", tce: "Tasha's Cauldron",
  scag: "Sword Coast Adventurer's Guide", vgm: "Volo's Guide", mtf: "Mordenkainen's Tome of Foes",
  mpmm: "Monsters of the Multiverse", eepc: "Elemental Evil Companion", ftd: "Fizban's Treasury", egw: "Explorer's Guide to Wildemount",
  erlw: "Eberron: Rising", ggr: "Guildmasters' Guide", mot: "Mythic Odysseys of Theros", vrgr: "Van Richten's Guide",
  scc: "Strixhaven", ai: "Acquisitions Inc.", bmt: "Book of Many Things", bgg: "Glory of the Giants",
  dsotdq: "Dragonlance", psa: "Planescape", aag: "Spelljammer", wbtw: "Wild Beyond the Witchlight",
};

export const signed = (n) => (n === null || n === undefined ? "" : n >= 0 ? `+${n}` : `${n}`);
export const book = (key) => BOOKS[key] || (key || "").toUpperCase();
export const ordinal = (n) => (n === 0 ? "Cantrip" : `${n}${["th", "st", "nd", "rd"][n % 10 > 3 || [11, 12, 13].includes(n % 100) ? 0 : n % 10]} level`);
// Title case as the books print it: "Sleight of Hand", "Vehicles (Land)"; small words stay lower inside a name.
const SMALL_WORDS = new Set(["of", "the", "and", "or", "a", "an", "in", "on", "to", "for"]);
export const title = (s) => String(s || "").replace(/[A-Za-z][\w']*/g, (w, i) => (i > 0 && SMALL_WORDS.has(w.toLowerCase()) ? w.toLowerCase() : w[0].toUpperCase() + w.slice(1)));

export function castingTime(time, short = false) {
  return (time || []).map((t) => `${t.number} ${t.unit === "bonus" ? "bonus action" : t.unit}${t.number > 1 && t.unit !== "bonus" ? "s" : ""}${t.condition && !short ? `, ${plain(t.condition)}` : ""}`).join(" or ");
}

export function range(r) {
  if (!r) return "";
  if (r.type === "special") return "Special";
  const d = r.distance || {};
  if (d.type === "self") return r.type === "point" ? "Self" : `Self (${d.amount ?? ""}${d.amount ? "-ft. " : ""}${r.type})`;
  if (d.type === "touch") return "Touch";
  if (d.type === "sight") return "Sight";
  if (d.type === "unlimited") return "Unlimited";
  if (d.type === "feet" || d.type === "miles") return `${d.amount} ${d.type === "feet" ? "ft." : d.amount === 1 ? "mile" : "miles"}${r.type !== "point" ? ` (${r.type})` : ""}`;
  return d.type || "";
}

export function components(c) {
  if (!c) return "";
  const out = [];
  if (c.v) out.push("V");
  if (c.s) out.push("S");
  if (c.m) out.push(`M (${typeof c.m === "string" ? c.m : c.m.text})`);
  return out.join(", ");
}

export function duration(list) {
  return (list || []).map((d) => {
    if (d.type === "instant") return "Instantaneous";
    if (d.type === "permanent") return d.ends ? `Until ${d.ends.join(" or ")}` : "Permanent";
    if (d.type === "special") return "Special";
    if (d.type === "timed") {
      const u = d.duration.type, n = d.duration.amount;
      return `${d.concentration ? "Concentration, up to " : ""}${n} ${u}${n > 1 ? "s" : ""}`;
    }
    return d.type;
  }).join(" or ");
}

export function plain(text) {
  if (typeof text !== "string") return "";
  let prev;
  do {
    prev = text;
    text = text.replace(/\{@(\w+) ([^{}]*?)\}/g, (_, tag, body) => {
      const parts = body.split("|");
      if (["dice", "damage", "d20", "hit", "chance"].includes(tag)) return parts[0];
      return parts[2] || parts[0];
    });
  } while (text !== prev);
  return text;
}

export function itemType(item) {
  if (!item) return "";
  const base = ITEM_TYPES[String(item.type || "").split("|")[0]] || (item.wondrous ? "Wondrous item" : "Item");
  return [item.rarity && item.rarity !== "none" ? title(item.rarity) : null, base].filter(Boolean).join(" ");
}

// Tool proficiencies a player can pick (PHB p. 154); the first seventeen are artisan's tools.
export const TOOLS = ["alchemist's supplies", "brewer's supplies", "calligrapher's supplies", "carpenter's tools", "cartographer's tools", "cobbler's tools", "cook's utensils", "glassblower's tools", "jeweler's tools", "leatherworker's tools", "mason's tools", "painter's supplies", "potter's tools", "smith's tools", "tinker's tools", "weaver's tools", "woodcarver's tools", "disguise kit", "forgery kit", "herbalism kit", "navigator's tools", "poisoner's kit", "thieves' tools", "dice set", "playing card set", "bagpipes", "drum", "flute", "lute", "lyre", "horn", "pan flute", "shawm", "viol", "vehicles (land)", "vehicles (water)"];
export const ARTISAN_TOOLS = TOOLS.slice(0, 17);

// Race names as the books and DDB print them: "Gnome (Forest)" -> "Forest Gnome", "Human (Variant)" -> "Variant Human".
// Long variant labels ("Half-Elf (Variant; Drow Descent)") and the gith keep 5etools' form.
export function raceName(name) {
  const m = String(name || "").match(/^([^(]+) \(([^);]+)\)$/);
  if (!m || m[1] === "Gith") return m && m[1] === "Gith" ? m[2] : name;
  return `${m[2]} ${m[1]}`;
}

// class backdrops we have pictures of (content/dnd5e/private/ddb/img/backdrops/<key>.jpg)
export const BACKDROPS = ["artificer", "barbarian", "bard", "cleric", "druid", "fighter", "monk", "paladin", "ranger", "rogue", "sorcerer", "warlock", "wizard"];
