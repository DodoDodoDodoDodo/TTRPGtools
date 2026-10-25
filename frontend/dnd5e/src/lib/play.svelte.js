// Play-state changes shared by the sheet and its side panes; each saves through the decision log.
import { current, changed } from "./character.svelte.js";

const play = () => (current.character.play ??= {});

export function toggleCondition(name) {
  const list = play().conditions || [];
  play().conditions = list.includes(name) ? list.filter((x) => x !== name) : [...list, name];
  changed(150);
}

export function setExhaustion(level) {
  play().exhaustion = Math.max(0, Math.min(6, Number(level) || 0));
  changed(100);
}

export function toggleEffect(name) {
  const list = play().effects || [];
  play().effects = list.includes(name) ? list.filter((x) => x !== name) : [...list, name];
  changed(100);
}

export function deathSave(kind, n) {
  play().death_saves = { success: 0, failure: 0, ...(play().death_saves || {}) };
  play().death_saves[kind] = play().death_saves[kind] === n ? n - 1 : n;
  changed(150);
}

export function setHp(currentHp, temp) {
  if (currentHp !== undefined) {
    play().hp_current = currentHp === null ? null : Math.max(0, Number(currentHp) || 0);
    // PHB p. 197: regaining any hit points resets death saves
    if (play().hp_current !== 0) play().death_saves = { success: 0, failure: 0 };
  }
  if (temp !== undefined) play().temp_hp = Math.max(0, Number(temp) || 0);
  changed(200);
}

export function takeRest(kind) {
  const s = current.sheet;
  const p = play();
  const used = { ...(p.counters_used || {}) };
  for (const counter of s.counters) if (kind === "long" || counter.reset === "short") delete used[counter.name];
  p.counters_used = used;
  p.pact_used = 0;
  if (kind === "long") {
    p.slots_used = {};
    p.hp_current = null;
    p.temp_hp = 0;
    p.death_saves = { success: 0, failure: 0 };
    p.exhaustion = Math.max(0, (p.exhaustion || 0) - 1);
    const dice = { ...(p.hit_dice_used || {}) };
    let regain = Math.max(1, Math.floor(s.level / 2));
    for (const hd of s.hit_dice) {
      const back = Math.min(dice[hd.class_id] || 0, regain);
      dice[hd.class_id] = (dice[hd.class_id] || 0) - back;
      regain -= back;
    }
    p.hit_dice_used = dice;
  }
  changed(100);
}

export function useSlot(level, n) {
  const used = Number((play().slots_used || {})[String(level)] || 0);
  play().slots_used = { ...(play().slots_used || {}), [String(level)]: used >= n ? n - 1 : n };
  changed(150);
}

export function usePact(n) {
  play().pact_used = (play().pact_used || 0) >= n ? n - 1 : n;
  changed(150);
}

// Casting a levelled spell spends a slot of that level: a spell slot first, then a pact slot of that level.
export function castAt(level) {
  const sc = current.sheet.spellcasting;
  const slot = (sc.slots || []).find((sl) => sl.level === level && sl.used < sl.max);
  if (slot) useSlot(level, slot.used + 1);
  else if (sc.pact?.level === level && sc.pact.used < sc.pact.count) usePact(sc.pact.used + 1);
}

// Slot levels the character can still cast a spell of this level at.
export function castableLevels(spellLevel) {
  const sc = current.sheet.spellcasting;
  const levels = (sc.slots || []).filter((sl) => sl.level >= spellLevel && sl.used < sl.max).map((sl) => sl.level);
  if (sc.pact && sc.pact.level >= spellLevel && sc.pact.used < sc.pact.count) levels.push(sc.pact.level);
  return [...new Set(levels)].sort((a, b) => a - b);
}
