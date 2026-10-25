// Spell numbers shared by the Spells tab and the spell pane.

// A cantrip's dice at this character level (5etools scalingLevelDice), else the spell's first damage dice.
export function cantripDice(sp, characterLevel) {
  if (!sp.scaling) return sp.dice || "";
  const steps = Object.keys(sp.scaling).map(Number).filter((lv) => lv <= characterLevel).sort((a, b) => b - a);
  return steps.length ? sp.scaling[steps[0]] : "";
}

// Damage cast at sp.castAt: "8d6" + 2 x "1d6" -> "10d6"; different dice are listed side by side.
export function damageOf(sp, characterLevel) {
  if (sp.level === 0) return cantripDice(sp, characterLevel);
  if (!sp.castAt || !sp.scaledamage) return sp.dice || "";
  const [base, step] = sp.scaledamage;
  const extra = sp.castAt - sp.level;
  const [bn, bd] = base.split("d").map(Number), [sn, sd] = step.split("d").map(Number);
  return bd === sd ? `${bn + sn * extra}d${bd}` : `${base}+${sn * extra}d${sd}`;
}
