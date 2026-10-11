"""
Build the Imperial Psyker character from CONFIRMED advance table data.

Sources:
  - Table 2-7 (p.75): Characteristic Advance costs
  - Advance tables (pp.75-79): Scholar track
  - ttrpgtools/dh1e/database/psychic_powers.json: power stats
"""

from __future__ import annotations
import json, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DB   = REPO / "ttrpgtools" / "dh1e" / "database"

powers_db = {}
for p in json.loads((DB / "psychic_powers.json").read_text()):
    powers_db[p["name"].lower()] = p

def get_power(name):
    k = name.lower()
    if k not in powers_db:
        return {"name": name, "DB_ERROR": f"'{name}' not in psychic_powers.json"}
    p = powers_db[k]
    return {"name": p["name"], "threshold": p.get("threshold"),
            "focus_time": p.get("focus_time"), "range": p.get("range")}

purchases = []
xp = 0

def buy(label, cost, rank, confirmed=True, note=""):
    global xp
    xp += cost
    purchases.append({"#": len(purchases), "item": label, "xp": cost,
                       "running_total": xp, "rank": rank,
                       "confirmed_from_pdf": confirmed, "note": note})

# FREE STARTING PACKAGE (Sanctionite)
buy("START: Awareness, Psyniscience, Invocation, Meditation, Pistol Training (Las), PR1 free",
    0, "Sanctionite",
    note="Psyniscience + Invocation base assumed free (prereq for +10 at Sch.Materium)")

# SANCTIONITE (p.75)
buy("Chem Geld",                      100, "Sanctionite")
buy("Minor Psychic Power → Healer",   100, "Sanctionite")

# NEONATE (p.75)
buy("Psy Rating 2",                   200, "Neonate",
    note="ASSUMED 200 XP — consistent with PR3/PR4; PDF table garbled for this entry")
buy("Chem-Use",                       100, "Neonate")
buy("Wrangling",                      100, "Neonate")
buy("Minor Psychic Power → Precognition", 100, "Neonate")
buy("Minor Psychic Power → Trick",    100, "Neonate")

# ASPIRANT (p.76)
buy("Dodge",                          100, "Aspirant")
buy("Awareness +10",                  100, "Aspirant")
buy("Minor Psychic Power → Unnatural Aim",  100, "Aspirant")
buy("Minor Psychic Power → Weapon Jinx",    100, "Aspirant")

# SCHOLAR MATERIUM (p.78)
buy("Logic",                          100, "Sch.Materium")
buy("Medicae",                        100, "Sch.Materium")
buy("Psyniscience +10",               100, "Sch.Materium")
buy("Invocation +10",                 100, "Sch.Materium")
buy("Psy Rating 3 → Telepathy primary; Compel FREE", 200, "Sch.Materium")
buy("Psychic Power → See Me Not [200 XP slot]",      200, "Sch.Materium")

# SCHOLAR MEDICAE (p.77)
buy("Discipline Focus (Telepathy)",   200, "Sch.Medicae")
buy("Psy Rating 4 → Telekinetics secondary; Catch Projectiles FREE", 200, "Sch.Medicae")
buy("Psychic Power → Dominate [100 XP slot 1/2]",    100, "Sch.Medicae")
buy("Psychic Power → Inspire  [100 XP slot 2/2]",    100, "Sch.Medicae")
buy("Medicae +10",                    100, "Sch.Medicae")
buy("Scrutiny",                       100, "Sch.Medicae")

# CHARACTERISTICS (Table 2-7 p.75)
buy("WP Simple       (WP 46→51)", 100, "Characteristic")
buy("WP Intermediate (WP 51→56)", 250, "Characteristic")
buy("WP Trained      (WP 56→61)", 500, "Characteristic")
buy("BS Simple       (BS 41→46)", 250, "Characteristic")
buy("BS Intermediate (BS 46→51)", 500, "Characteristic")
buy("T  Simple       (T  31→36)", 250, "Characteristic")
buy("T  Intermediate (T  36→41)", 500, "Characteristic")

# SCHOLAR ARCANUM (p.79)
buy("Interrogation",              100, "Sch.Arcanum")
buy("Dodge +10",                  100, "Sch.Arcanum")
buy("Invocation +20",             100, "Sch.Arcanum")
buy("Forbidden Lore (Xenos)",     100, "Sch.Arcanum",
    note="User wanted FL(Void Ships) — not on any psyker table. FL(Xenos) confirmed p.79")
buy("Psychic Power → Telepathy-power [100 XP slot 1/2]", 100, "Sch.Arcanum")
buy("Psychic Power → Psychic Shriek  [100 XP slot 2/2]", 100, "Sch.Arcanum")
buy("Peer (Void Born)",           100, "Sch.Arcanum",
    note="User wanted Peer(Navigators) — not on any psyker table. Peer(Void Born) confirmed p.79")
buy("Favoured by the Warp",       200, "Sch.Arcanum",
    note="200 XP confirmed p.79 (prereq WP 35). On the advance table — NOT free.")

print(f"XP after confirmed purchases: {xp} / 6850  (remaining: {6850-xp})")

# Remaining: 6850 - xp
remaining = 6850 - xp

# Terrify + Projection: user wants them but we've used all 5 Psychic Power slots.
# Flag and add them — let user decide with GM.
buy("Psychic Power → Terrify    [FLAGGED: exceeds 5-slot limit]", 100, "Sch.Arcanum",
    confirmed=False,
    note="FLAGGED: 5 Psychic Power purchases already used (table limit). Needs GM ruling.")
buy("Psychic Power → Projection [FLAGGED: exceeds 5-slot limit]", 100, "Sch.Arcanum",
    confirmed=False,
    note="Same issue.")

remaining = 6850 - xp
print(f"XP including flagged:         {xp} / 6850  (remaining: {remaining})")

assert xp <= 6850, f"OVER BUDGET: {xp}"

# BUILD OUTPUT
char = {
    "_meta": {
        "system": "Dark Heresy 1st Edition",
        "career": "Imperial Psyker — Scholar track",
        "rank": 6, "rank_name": "Scholar Arcanum",
        "xp_budget": 6850, "xp_spent": xp, "xp_unspent": 6850 - xp,
        "origin": "Void Born",
    },
    "_quick_reference": {
        "power_roll_TELEPATHY":    "4d10 + 8   (PR4 + WPBonus 6 + DiscFocus +2)",
        "power_roll_TELEKINETICS": "4d10 + 6   (PR4 + WPBonus 6)",
        "catch_projectiles":       "REACTION — roll 4d10+6 vs PT 16. Negates WPBonus (6) solid hits per turn.",
        "psychic_shriek":          "PT 18, Half Action, 10m. Targets fail WP or take 6 Fatigue.",
        "fatigue_threshold_self":  "T Bonus 4",
        "WP_Bonus": 6, "T_Bonus": 4, "BS_Bonus": 5,
    },
    "characteristics": {
        "starting": {"WS":21,"BS":41,"Str":22,"T":31,"Ag":36,"Int":25,"Per":22,"WP":46,"Fel":22},
        "final":    {"WS":21,"BS":51,"Str":22,"T":41,"Ag":36,"Int":25,"Per":22,"WP":61,"Fel":22},
        "bonuses":  {"WS Bonus":2,"BS Bonus":5,"Str Bonus":2,"T Bonus":4,
                     "Ag Bonus":3,"Int Bonus":2,"Per Bonus":2,"WP Bonus":6,"Fel Bonus":2},
    },
    "psy_rating": 4,
    "disciplines": {"primary": "Telepathy", "secondary": "Telekinetics"},
    "psychic_powers": {
        "telepathy": [
            {**get_power("Compel"),         "xp":0,   "source":"PR3 free"},
            {**get_power("SEE ME NOT"),     "xp":200, "source":"Sch.Materium"},
            {**get_power("Dominate"),       "xp":100, "source":"Sch.Medicae"},
            {**get_power("Inspire"),        "xp":100, "source":"Sch.Medicae"},
            {**get_power("Telepathy"),      "xp":100, "source":"Sch.Arcanum"},
            {**get_power("Psychic Shriek"), "xp":100, "source":"Sch.Arcanum"},
            {**get_power("Terrify"),        "xp":100, "source":"Sch.Arcanum [FLAGGED]",
             "FLAGGED":"may exceed Psychic Power purchase limit — see flagged_issues"},
            {**get_power("Projection"),     "xp":100, "source":"Sch.Arcanum [FLAGGED]",
             "FLAGGED":"same issue"},
        ],
        "telekinetics": [
            {**get_power("Catch Projectiles"), "xp":0, "source":"PR4 free"},
        ],
        "minor": [
            {**get_power("Healer"),           "xp":100, "rank":"Sanctionite"},
            {**get_power("Precognition"),     "xp":100, "rank":"Neonate"},
            {**get_power("Trick"),            "xp":100, "rank":"Neonate"},
            {**get_power("Unnatural AIM"),    "xp":100, "rank":"Aspirant"},
            {**get_power("Weapon Jinx"),      "xp":100, "rank":"Aspirant"},
        ],
    },
    "skills": [
        {"name":"Awareness",              "rank":"+10",    "source":"free+Aspirant p.76"},
        {"name":"Psyniscience",           "rank":"+10",    "source":"free start + Sch.Materium p.78"},
        {"name":"Invocation",             "rank":"+20",    "source":"free + Sch.Materium + Sch.Arcanum"},
        {"name":"Chem-Use",               "rank":"Trained","source":"Neonate p.75"},
        {"name":"Wrangling",              "rank":"Trained","source":"Neonate p.75"},
        {"name":"Dodge",                  "rank":"+10",    "source":"Aspirant p.76 + Sch.Arcanum p.79"},
        {"name":"Logic",                  "rank":"Trained","source":"Sch.Materium p.78"},
        {"name":"Medicae",                "rank":"+10",    "source":"Sch.Materium + Sch.Medicae"},
        {"name":"Scrutiny",               "rank":"Trained","source":"Sch.Medicae p.77"},
        {"name":"Interrogation",          "rank":"Trained","source":"Sch.Arcanum p.79"},
        {"name":"Forbidden Lore (Xenos)", "rank":"Trained","source":"Sch.Arcanum p.79",
         "NOTE":"User wanted FL(Void Ships) — not on table"},
    ],
    "talents": [
        {"name":"Chem Geld",                    "xp":100, "source":"Sanctionite p.75"},
        {"name":"Meditation",                   "xp":0,   "source":"Sanctionite p.75 free"},
        {"name":"Pistol Training (Las)",        "xp":0,   "source":"Sanctionite p.75 free"},
        {"name":"Discipline Focus (Telepathy)", "xp":200, "source":"Sch.Medicae p.77",
         "effect":"+2 Telepathy Power Rolls"},
        {"name":"Peer (Void Born)",             "xp":100, "source":"Sch.Arcanum p.79",
         "NOTE":"User wanted Peer(Navigators) — not on table"},
        {"name":"Favoured by the Warp",         "xp":200, "source":"Sch.Arcanum p.79",
         "NOTE":"Costs 200 XP on table (not free). User called this 'elite advance'."},
    ],
    "equipment": [
        {"item":"Plasma Pistol",
         "FLAGGED":"Pistol Training (Plasma) NOT confirmed on Scholar track at 6850 XP — see flagged_issues"},
        {"item":"Laspistol",     "note":"Pistol Training (Las) confirmed"},
        {"item":"Recoil Gloves", "note":"No talent required"},
        {"item":"Flak Vest",     "ap":3, "covers":"Body"},
    ],
    "purchase_history": purchases,
    "flagged_issues": [
        {"issue":"Pistol Training (Plasma)",
         "detail":"Not on Scholar track up to Scholar Arcanum. Appears on Savant Adjunct (8000+ XP military) at 300 XP. Character cannot fire plasma pistol without this talent."},
        {"issue":"Navigation (Stellar)",
         "detail":"Not on Scholar track until Preceptor-Savant (10000+ XP). Cannot buy at 6850 XP."},
        {"issue":"Demolition",
         "detail":"Only on Lieutenant-Savant (military track). Not on Scholar Arcanum table."},
        {"issue":"Peer (Navigators)",
         "detail":"Not found on any Imperial Psyker advance table. Closest available: Peer(Void Born) at Sch.Arcanum."},
        {"issue":"Forbidden Lore (Void Ships)",
         "detail":"Not on any psyker table. FL(Xenos) is confirmed on Sch.Arcanum p.79."},
        {"issue":"Terrify + Projection (7th/8th discipline powers)",
         "detail":"Scholar track Psychic Power slots: Sch.Materium 1x200XP + Sch.Medicae 2x100XP + Sch.Arcanum 2x100XP = 5 total. Plus 2 free (Compel+Catch Projectiles) = 7. User wants 7 Telepathy + 1 Telekinetics = 8 total discipline powers. That needs 6 bought. One exceeds the table limit. Needs GM ruling."},
        {"issue":"Psy Rating 2 cost assumed 200 XP",
         "detail":"PR2 entry in PDF table was not cleanly extractable. Used 200 XP based on advances.json most common value and consistency with PR3+PR4."},
        {"issue":"Invocation + Psyniscience base assumed free",
         "detail":"These appear as prerequisites for Sch.Materium +10 advances but no base purchase entry found on early rank tables. Assumed starting skills."},
    ],
    "xp_breakdown": {
        "characteristics": 2350,
        "psy_rating_2+3+4": 600,
        "discipline_focus": 200,
        "discipline_powers_5_slots": 700,
        "discipline_powers_2_flagged": 200,
        "minor_powers_5x100": 500,
        "skills_bought": 1000,
        "chem_geld": 100,
        "peer_void_born": 100,
        "favoured_by_warp": 200,
        "TOTAL": xp,
        "BUDGET": 6850,
        "UNSPENT": 6850 - xp,
    }
}

out = DB / "psyker_6850.json"
out.write_text(json.dumps(char, indent=2))
print(f"\nWrote: {out}")
print(f"XP: {xp} / 6850  (unspent: {6850-xp})")
print("\n=== FLAGGED — needs decisions ===")
for f in char["flagged_issues"]:
    print(f"  [{f['issue']}]")
    print(f"   {f['detail'][:110]}")
