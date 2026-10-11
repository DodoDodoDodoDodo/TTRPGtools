"""Fit difficulty.PC_POWER against the bestiary and print the table.

    python scripts/calibrate_difficulty.py

For each party level: four baseline PCs (fighter, rogue, wizard, cleric) fight every
official monster of CR = level alone. The factor is chosen so the median share of
hit points lost equals difficulty.CALIBRATION_TARGET. Paste the output into
ttrpgtools/dnd5e/difficulty.py.
"""

import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ttrpgtools.dnd5e import db, difficulty  # noqa: E402

PARTY = ["fighter", "rogue", "wizard", "cleric"]


def median_loss(level: int, monsters: list[dict], power: float) -> float:
    difficulty.PC_POWER[level] = power
    pcs = [{"name": cls, "level": level, "cls": cls} for cls in PARTY]
    return statistics.median(difficulty.duel_rating(pcs, [m])["hp_lost"] for m in monsters)


def main() -> None:
    fitted = {}
    with db.session() as conn:
        for level in range(1, 21):
            rows = conn.execute(
                "SELECT data FROM monsters WHERE official = 1 AND origin = 'compendium' AND cr = ?", (level,))
            monsters = [json.loads(r["data"]) for r in rows]
            monsters = [m for m in monsters if difficulty.monster_profile(m)["dpr"] > 0]
            low, high = 0.3, 6.0
            for _ in range(30):
                mid = (low + high) / 2
                if median_loss(level, monsters, mid) > difficulty.CALIBRATION_TARGET:
                    low = mid
                else:
                    high = mid
            fitted[level] = (round(high, 2), len(monsters))
    # Neighbouring levels share monsters' design; a 3-point mean removes sampling noise.
    raw = [fitted[lv][0] for lv in range(1, 21)]
    smooth = [round(statistics.mean(raw[max(0, i - 1):i + 2]), 2) for i in range(20)]
    for lv in range(1, 21):
        print(f"level {lv:2}: raw {raw[lv - 1]:.2f} smooth {smooth[lv - 1]:.2f}  ({fitted[lv][1]} monsters)")
    print("PC_POWER = {" + ", ".join(f"{lv}: {smooth[lv - 1]}" for lv in range(1, 21)) + "}")


if __name__ == "__main__":
    main()
