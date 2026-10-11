"""D&D 5e encounter tools: stat block parsing, difficulty maths, combat state.

Fixtures are SRD 5.1 creatures (CC-BY-4.0) or invented ones.
"""

import json
import xml.etree.ElementTree as ET

import pytest

from ttrpgtools.dnd5e import bestiary, combat, db, difficulty, paste_import, statblock

OGRE_2014 = """Ogre
Large giant, chaotic evil
Armor Class 11 (hide armor)
Hit Points 59 (7d10 + 21)
Speed 40 ft.
STR
19 (+4)
DEX
8 (−1)
CON
16 (+3)
INT
5 (−3)
WIS
7 (−2)
CHA
7 (−2)
Senses darkvision 60 ft., passive Perception 8
Languages Common, Giant
Challenge 2 (450 XP)
Proficiency Bonus +2
Actions
Greatclub. Melee Weapon Attack: +6 to hit, reach 5 ft., one target. Hit: 13 (2d8 + 4) bludgeoning damage.
Javelin. Melee or Ranged Weapon Attack: +6 to hit, reach 5 ft. or range 30/120 ft., one target. Hit: 11 (2d6 + 4) piercing damage.
"""

DRAGON_2014 = """Young Red Dragon
Large dragon, chaotic evil
Armor Class 18 (natural armor)
Hit Points 178 (17d10 + 85)
Speed 40 ft., climb 40 ft., fly 80 ft.
STR 23 (+6) DEX 10 (+0) CON 21 (+5) INT 14 (+2) WIS 11 (+0) CHA 19 (+4)
Saving Throws Dex +4, Con +9, Wis +4, Cha +8
Skills Perception +8, Stealth +4
Damage Immunities fire
Senses blindsight 30 ft., darkvision 120 ft., passive Perception 18
Languages Common, Draconic
Challenge 10 (5,900 XP)
Legendary Resistance (3/Day). If the dragon fails a saving throw, it can choose to succeed instead.
Innate Spellcasting. The dragon's spellcasting ability is Charisma (spell save DC 16). It can innately cast:
3/day each: detect magic, fear
1/day: wall of fire
Actions
Multiattack. The dragon makes three attacks: one with its bite and two with its claws.
Bite. Melee Weapon Attack: +10 to hit, reach 10 ft., one target. Hit: 17 (2d10 + 6) piercing damage plus 3 (1d6) fire
damage.
Claw. Melee Weapon Attack: +10 to hit, reach 5 ft., one target. Hit: 13 (2d6 + 6) slashing damage.
Fire Breath (Recharge 5–6). The dragon exhales fire in a 30-foot cone. Each creature in that area must make a DC 17 Dexterity saving throw, taking 56 (16d6) fire damage on a failed save, or half as much damage on a successful one.
Legendary Actions
The dragon can take 3 legendary actions, choosing from the options below.
Tail Attack. The dragon makes a claw attack.
Wing Attack (Costs 2 Actions). Each creature within 10 feet must succeed on a DC 18 Dexterity saving throw or take 13 (2d6 + 6) bludgeoning damage.
"""

BLOCK_2024 = """Cave Lurker
Medium Monstrosity, Unaligned
AC 14 Initiative +3 (13)
HP 45 (7d8 + 14)
Speed 30 ft., Climb 30 ft.
MOD SAVE
STR 16 +3 +3
DEX 17 +3 +5
CON 14 +2 +2
INT 3 -4 -4
WIS 12 +1 +1
CHA 6 -2 -2
Skills Stealth +7
Resistances Cold
Immunities Poison; Poisoned
Senses Darkvision 60 ft.; Passive Perception 11
Languages None
CR 3 (XP 700; PB +2)
Traits
Spider Climb. The lurker can climb difficult surfaces.
Actions
Multiattack. The lurker makes two Claw attacks.
Claw. Melee Attack Roll: +5, reach 5 ft. Hit: 8 (1d10 + 3) Slashing damage.
Venom Spray (Recharge 5-6). Constitution Saving Throw: DC 12, each creature in a 15-foot Cone. Failure: 14 (4d6) Poison damage. Success: Half damage.
Bonus Actions
Skitter. The lurker moves up to half its Speed.
"""

COMPENDIUM_XML = """<monster><name>Test Wyrm</name><size>H</size><type>dragon</type><alignment>CE</alignment>
<ac>19 (natural armor)</ac><hp>256 (19d12+133)</hp><speed>walk 40 ft.</speed>
<str>27</str><dex>10</dex><con>25</con><int>16</int><wis>13</wis><cha>21</cha><cr>17</cr>
<immune>fire</immune>
<trait><name>Legendary Resistance (3/Day)</name><recharge>3/Day</recharge><text>Succeeds anyway.</text></trait>
<action><name>Multiattack</name><text>The wyrm makes three attacks: one with its bite and two with its claws.</text></action>
<action><name>Bite</name><text>Melee Weapon Attack: +14 to hit, reach 10 ft., one target. Hit: 19 (2d10 + 8) piercing damage plus 7 (2d6) fire damage.</text><attack>Bite|+14|2d10+8</attack></action>
<action><name>Claw</name><text>Melee Weapon Attack: +14 to hit, reach 5 ft., one target. Hit: 15 (2d6 + 8) slashing damage.</text><attack>Claw|+14|2d6+8</attack></action>
<action><name>Fire Breath (Recharge 5-6)</name><recharge>D5</recharge><text>Each creature in a 60-foot cone must make a DC 21 Dexterity saving throw, taking 63 (18d6) fire damage on a failed save, or half as much damage on a successful one.</text></action>
<legendary><name>Legendary Actions (3/Turn)</name><recharge>3/Turn</recharge><text>The wyrm can take 3 legendary actions.</text></legendary>
<legendary><name>Tail Attack</name><text>The wyrm makes a claw attack.</text></legendary>
<legendary><name>Lair Actions</name><text>On initiative count 20, magma erupts.</text></legendary>
<slots>0, 4, 3</slots>
<description>A wyrm.

Source:\tTest Book (2014) p. 1,
\t\tAnother Book</description></monster>"""


def resources(monster):
    return {r["name"]: r for r in monster["resources"]}


# ------------------------------------------------------------------ helpers
@pytest.mark.parametrize("expr,expected", [
    ("2d10+8", 19), ("2d6 + 8", 15), ("18d6", 63), ("1d4-3", -0.5), ("1d12+4+2d6", 17.5), ("5", 5), ("", 0),
])
def test_dice_average(expr, expected):
    assert statblock.dice_average(expr) == expected


def test_usage_from_name():
    assert statblock.usage_from_name("Fire Breath (Recharge 5-6)") == {"kind": "recharge", "max": 1, "recharge_min": 5}
    assert statblock.usage_from_name("Teleport (3/Day)") == {"kind": "day", "max": 3}
    assert statblock.usage_from_name("Bite") is None


# ------------------------------------------------------------------ paste import
def test_paste_2014_one_ability_per_line():
    m = paste_import.parse(OGRE_2014)
    assert (m["name"], m["size"], m["type"], m["ac"], m["hp"], m["hp_formula"]) == \
        ("Ogre", "Large", "giant", 11, 59, "7d10+21")
    assert m["abilities"] == {"str": 19, "dex": 8, "con": 16, "int": 5, "wis": 7, "cha": 7}
    assert m["init_mod"] == -1
    assert (m["cr"], m["xp"], m["passive"]) == ("2", 450, 8)
    assert [a["name"] for a in m["actions"]] == ["Greatclub", "Javelin"]
    assert m["actions"][0]["attacks"] == [{"name": "Greatclub", "to_hit": 6, "dice": "2d8+4", "avg": 13.0}]
    assert m["import_problems"] == []


def test_paste_2014_traits_legendary_and_counters():
    m = paste_import.parse(DRAGON_2014)
    assert m["abilities"]["str"] == 23 and m["abilities"]["cha"] == 19
    assert m["immune"] == "fire"
    assert [t["name"] for t in m["traits"]] == ["Legendary Resistance (3/Day)", "Innate Spellcasting"]
    assert [a["name"] for a in m["actions"]] == ["Multiattack", "Bite", "Claw", "Fire Breath (Recharge 5-6)"]
    assert "plus 3 (1d6) fire damage" in m["actions"][1]["text"]  # wrapped line rejoined
    assert m["legendary_uses"] == 3
    assert [e["name"] for e in m["legendary"]] == ["Tail Attack", "Wing Attack (Costs 2 Actions)"]
    r = resources(m)
    assert r["Legendary Actions"]["max"] == 3
    assert r["Legendary Resistance"]["kind"] == "legendary_resistance"
    assert r["Fire Breath"] == {"key": "recharge-fire-breath", "name": "Fire Breath", "kind": "recharge",
                                "max": 1, "recharge_min": 5}
    assert r["fear"]["max"] == 3 and r["detect magic"]["max"] == 3 and r["wall of fire"]["max"] == 1


def test_paste_2024_layout():
    m = paste_import.parse(BLOCK_2024)
    assert (m["ac"], m["hp"], m["init_mod"], m["cr"]) == (14, 45, 3, "3")
    assert m["abilities"] == {"str": 16, "dex": 17, "con": 14, "int": 3, "wis": 12, "cha": 6}
    assert m["saves"] == "Dex +5"
    assert (m["immune"], m["condition_immune"], m["resist"]) == ("Poison", "Poisoned", "Cold")
    assert [e["name"] for e in m["bonus_actions"]] == ["Skitter"]
    assert m["actions"][1]["attacks"][0]["to_hit"] == 5
    assert "recharge-venom-spray" in {r["key"] for r in m["resources"]}
    profile = difficulty.monster_profile(m)
    assert profile["routine"] == ["2x Claw"]
    assert profile["round_damage"][0] == 28  # spray 14 on two targets beats two claws


def test_paste_rejects_prose():
    with pytest.raises(paste_import.PasteError):
        paste_import.parse("Hello there\nthis is not\na stat block\nat all\nreally")


# ------------------------------------------------------------------ compendium
def test_compendium_conversion():
    m = bestiary.convert_monster(ET.fromstring(COMPENDIUM_XML))
    assert (m["source"], m["sources"]) == ("Test Book (2014)", ["Test Book (2014)", "Another Book"])
    assert m["description"] == "A wyrm."
    assert (m["ac"], m["hp"], m["size"], m["xp"]) == (19, 256, "Huge", 18000)
    assert m["spell_slots"] == [4, 3]
    assert m["legendary_uses"] == 3
    assert [e["name"] for e in m["lair"]] == ["Lair Actions"]
    assert {r["kind"] for r in m["resources"]} == {"legendary", "legendary_resistance", "recharge", "slot"}


def test_bestiary_store_and_search(tmp_path):
    conn = db.connect(tmp_path / "t.sqlite")
    m = bestiary.convert_monster(ET.fromstring(COMPENDIUM_XML))
    bestiary.save_monster(conn, m, "compendium", "test-wyrm")
    pasted = bestiary.save_monster(conn, paste_import.parse(OGRE_2014), "paste")
    assert pasted == "ogre-paste"
    assert [r["id"] for r in bestiary.search(conn, "wyrm")] == ["test-wyrm"]
    assert [r["id"] for r in bestiary.search(conn, "", cr_max=5)] == ["ogre-paste"]
    assert bestiary.get_monster(conn, "test-wyrm")["name"] == "Test Wyrm"


# ------------------------------------------------------------------ difficulty
def test_dmg_multiplier_and_party_size():
    assert [difficulty.dmg_multiplier(n, 4) for n in (1, 2, 3, 6, 7, 11, 15)] == [1, 1.5, 2, 2, 2.5, 3, 4]
    assert difficulty.dmg_multiplier(1, 2) == 1.5
    assert difficulty.dmg_multiplier(1, 6) == 0.5
    assert difficulty.dmg_multiplier(15, 2) == 5


def test_official_rating_matches_dmg_example():
    # DMG example: four level 3 PCs, thresholds 300/600/900/1600.
    ogre = paste_import.parse(OGRE_2014)
    rating = difficulty.official_rating([3, 3, 3, 3], [ogre, ogre])
    assert rating["dmg"]["thresholds"] == {"easy": 300, "medium": 600, "hard": 900, "deadly": 1600}
    assert (rating["dmg"]["raw_xp"], rating["dmg"]["adjusted_xp"], rating["dmg"]["tier"]) == (900, 1350, "Hard")
    assert rating["lazy"]["limit"] == 3.0 and rating["lazy"]["maybe_deadly"]


def test_monster_profile_reads_routine_breath_and_legendary():
    p = difficulty.monster_profile(paste_import.parse(DRAGON_2014))
    assert p["routine"] == ["1x Bite", "2x Claw"]
    # Round 1: breath 56 on two targets, plus three legendary claw attacks.
    assert p["round_damage"][0] == 56 * 2 + 3 * 13
    assert p["legendary"] == "Tail Attack"
    assert p["ehp"] == 178 + 3 * 20


def test_duel_scales_with_numbers_and_level():
    ogre = paste_import.parse(OGRE_2014)
    party = lambda level: [{"name": c, "level": level, "cls": c} for c in ("fighter", "rogue", "wizard", "cleric")]  # noqa: E731
    one = difficulty.duel_rating(party(3), [ogre])
    three = difficulty.duel_rating(party(3), [ogre] * 3)
    high = difficulty.duel_rating(party(9), [ogre] * 3)
    assert one["hp_lost"] < three["hp_lost"]
    assert high["hp_lost"] < three["hp_lost"]
    assert one["party_wins"] and high["band"] in ("Trivial", "Light")
    assert one["assumed"]  # baselines are declared, not hidden


def test_entered_pc_values_are_used():
    ogre = paste_import.parse(OGRE_2014)
    weak = [{"name": "A", "level": 3, "cls": "wizard", "hp": 14, "ac": 11}]
    strong = [{"name": "A", "level": 3, "cls": "wizard", "hp": 40, "ac": 19, "dpr": 25}]
    assert difficulty.duel_rating(weak, [ogre])["hp_lost"] > difficulty.duel_rating(strong, [ogre])["hp_lost"]
    assert any("one round" in w for w in difficulty.duel_rating(weak, [ogre])["warnings"]) is False
    tiny = [{"name": "A", "level": 1, "cls": "wizard", "hp": 8, "ac": 11}]
    assert any("in one round" in w for w in difficulty.duel_rating(tiny, [ogre])["warnings"])


def test_empty_encounter_rates_none():
    assert difficulty.rate([], [])["duel"]["band"] == "None"
    assert difficulty.rate([{"level": 3}], [])["official"]["dmg"]["tier"] == "None"


# ------------------------------------------------------------------ combat
@pytest.fixture
def fight():
    dragon = paste_import.parse(DRAGON_2014)
    ogre = paste_import.parse(OGRE_2014)
    pcs = [{"id": "pc1", "name": "Tira", "level": 5, "cls": "wizard", "hp": 28, "ac": 13, "init_mod": 2,
            "resources": [{"key": "slot-1", "name": "Level 1 slots", "kind": "slot", "max": 4}]}]
    state = combat.new_combat("Test", pcs, [(dragon, 1), (ogre, 3)])
    return state


def by_label(state, label):
    return next(c for c in state["combatants"] if c["label"] == label)


def test_new_combat_numbers_duplicates_and_snapshots(fight):
    labels = [c["label"] for c in fight["combatants"]]
    assert labels == ["Tira", "Young Red Dragon", "Ogre 1", "Ogre 2", "Ogre 3"]
    ogre = by_label(fight, "Ogre 2")
    assert ogre["hp"] == ogre["hp_max"] == 59 and ogre["statblock"]["name"] == "Ogre"
    assert len({c["id"] for c in fight["combatants"]}) == 5


def test_damage_heal_temp_hp_and_death(fight):
    ogre = by_label(fight, "Ogre 1")
    combat.apply(fight, {"op": "temp_hp", "id": ogre["id"], "amount": 5})
    combat.apply(fight, {"op": "damage", "id": ogre["id"], "amount": 20})
    assert (ogre["hp"], ogre["temp_hp"]) == (44, 0)
    combat.apply(fight, {"op": "heal", "id": ogre["id"], "amount": 100})
    assert ogre["hp"] == 59
    combat.apply(fight, {"op": "damage", "id": ogre["id"], "amount": 500})
    assert ogre["hp"] == 0 and ogre["defeated"]


def test_damage_many_targets_with_half(fight):
    ids = [by_label(fight, f"Ogre {n}")["id"] for n in (1, 2)]
    combat.apply(fight, {"op": "damage", "ids": ids, "amount": 21, "half": [ids[1]]})
    assert by_label(fight, "Ogre 1")["hp"] == 38 and by_label(fight, "Ogre 2")["hp"] == 49


def test_concentration_prompt_on_damage(fight):
    tira = by_label(fight, "Tira")
    combat.apply(fight, {"op": "concentration", "id": tira["id"], "spell": "Web"})
    result = combat.apply(fight, {"op": "damage", "id": tira["id"], "amount": 26})
    assert "DC 13" in result["prompts"][0] and "Web" in result["prompts"][0]


def test_resources_spend_and_restore(fight):
    dragon = by_label(fight, "Young Red Dragon")
    combat.apply(fight, {"op": "spend", "id": dragon["id"], "key": "recharge-fire-breath"})
    assert combat.resource(dragon, "recharge-fire-breath")["spent"] == 1
    with pytest.raises(combat.CombatError):
        combat.apply(fight, {"op": "spend", "id": dragon["id"], "key": "recharge-fire-breath"})
    combat.apply(fight, {"op": "restore", "id": dragon["id"], "key": "recharge-fire-breath"})
    assert combat.resource(dragon, "recharge-fire-breath")["spent"] == 0


def test_turn_order_rounds_and_turn_start_effects(fight):
    inits = {"Tira": 15, "Young Red Dragon": 20, "Ogre 1": 8, "Ogre 2": 8, "Ogre 3": 3}
    for label, value in inits.items():
        combat.apply(fight, {"op": "set_initiative", "id": by_label(fight, label)["id"], "value": value})
    dragon = by_label(fight, "Young Red Dragon")
    combat.apply(fight, {"op": "start"})
    assert [c["label"] for c in combat.ordered(fight)] == ["Young Red Dragon", "Tira", "Ogre 1", "Ogre 2", "Ogre 3"]
    assert fight["round"] == 1 and combat.current(fight)["label"] == "Young Red Dragon"

    combat.apply(fight, {"op": "spend", "id": dragon["id"], "key": "legendary-legendary-actions", "amount": 2})
    combat.apply(fight, {"op": "spend", "id": dragon["id"], "key": "recharge-fire-breath"})
    combat.apply(fight, {"op": "condition", "id": dragon["id"], "name": "Frightened", "rounds": 1})
    combat.apply(fight, {"op": "damage", "id": by_label(fight, "Ogre 1")["id"], "amount": 99})
    seen = []
    for _ in range(4):
        result = combat.apply(fight, {"op": "next"})
        seen.append(combat.current(fight)["label"])
    assert seen == ["Tira", "Ogre 2", "Ogre 3", "Young Red Dragon"]  # defeated Ogre 1 skipped
    assert fight["round"] == 2
    assert combat.resource(dragon, "legendary-legendary-actions")["spent"] == 0  # refreshed at turn start
    assert any("Fire Breath" in p and "5" in p for p in result["prompts"])  # recharge roll reminder
    assert dragon["conditions"] == []  # one-round condition expired

    combat.apply(fight, {"op": "prev"})
    assert combat.current(fight)["label"] == "Ogre 3" and fight["round"] == 1


def test_add_rename_remove_mid_fight(fight):
    combat.apply(fight, {"op": "start"})
    ogre = paste_import.parse(OGRE_2014)
    combat.apply(fight, {"op": "add_monster", "statblock": ogre, "count": 2, "initiative": 12})
    assert [c["label"] for c in fight["combatants"]][-2:] == ["Ogre 4", "Ogre 5"]
    target = by_label(fight, "Ogre 4")
    combat.apply(fight, {"op": "rename", "id": target["id"], "label": "Ogre chief"})
    combat.apply(fight, {"op": "remove", "id": by_label(fight, "Ogre 5")["id"]})
    labels = [c["label"] for c in fight["combatants"]]
    assert "Ogre chief" in labels and "Ogre 5" not in labels
    combat.apply(fight, {"op": "add_custom", "label": "Falling rocks", "hp": 0, "initiative": 20})
    assert by_label(fight, "Falling rocks")["kind"] == "custom"


def test_store_roundtrip_undo_and_version_conflict(tmp_path):
    conn = db.connect(tmp_path / "c.sqlite")
    state = combat.new_combat("Saved", [], [(paste_import.parse(OGRE_2014), 1)])
    combat_id = combat.create(conn, state)
    ogre_id = state["combatants"][0]["id"]

    state, _ = combat.act(conn, combat_id, {"op": "damage", "id": ogre_id, "amount": 10}, version=0)
    assert state["version"] == 1 and state["combatants"][0]["hp"] == 49
    with pytest.raises(combat.VersionConflict):
        combat.act(conn, combat_id, {"op": "damage", "id": ogre_id, "amount": 10}, version=0)

    state, _ = combat.act(conn, combat_id, {"op": "damage", "id": ogre_id, "amount": 5}, version=1)
    assert state["combatants"][0]["hp"] == 44
    state = combat.undo(conn, combat_id)
    assert state["combatants"][0]["hp"] == 49
    assert combat.load(conn, combat_id)["combatants"][0]["hp"] == 49


# ------------------------------------------------------------------ D&D Beyond character
def ddb_character(**overrides):
    slots = [[0] * 9] + [[4, 3, 2] + [0] * 6] * 20
    data = {
        "id": 123456, "name": "Tira", "readonlyUrl": "https://dndbeyond.com/characters/123456",
        "baseHitPoints": 30, "bonusHitPoints": None, "overrideHitPoints": None, "removedHitPoints": 7,
        "temporaryHitPoints": 3,
        "stats": [{"id": i, "value": v} for i, v in enumerate([10, 14, 14, 17, 12, 8], start=1)],
        "bonusStats": [{"id": i, "value": None} for i in range(1, 7)],
        "overrideStats": [{"id": i, "value": None} for i in range(1, 7)],
        "classes": [{"level": 5, "isStartingClass": True, "subclassDefinition": {"name": "Evocation"},
                     "definition": {"name": "Wizard", "canCastSpells": True,
                                    "spellRules": {"multiClassSpellSlotDivisor": 1, "levelSpellSlots": slots}}}],
        "race": {"fullName": "High Elf"},
        "modifiers": {
            "race": [{"type": "bonus", "subType": "intelligence-score", "fixedValue": 1, "value": 1}],
            "class": [], "background": [], "feat": [], "condition": [],
            "item": [{"type": "bonus", "subType": "armor-class", "fixedValue": 1, "value": 1, "componentId": 77},
                     {"type": "bonus", "subType": "armor-class", "fixedValue": 2, "value": 2, "componentId": 78}],
        },
        "inventory": [
            {"equipped": True, "isAttuned": True, "definition": {"id": 77, "name": "Ring of Protection", "canAttune": True}},
            {"equipped": False, "isAttuned": False, "definition": {"id": 78, "name": "Shield +2 bonus", "canAttune": False}},
            {"equipped": True, "isAttuned": False,
             "definition": {"id": 79, "name": "Studded Leather", "armorClass": 12, "armorTypeId": 1}},
        ],
        "spellSlots": [{"level": 1, "used": 2, "available": 0}], "pactMagic": [],
        "actions": {"class": [
            {"name": "Arcane Recovery", "limitedUse": {"maxUses": 1, "numberUsed": 1, "resetType": 2}},
            {"name": "Summon pool", "limitedUse": {"maxUses": 70, "numberUsed": 0, "resetType": 4}}]},
    }
    data.update(overrides)
    return data


def test_ddb_character_is_recomputed_from_parts():
    from ttrpgtools.dnd5e import ddb_character as ddb
    pc = ddb.parse_character(ddb_character())
    assert (pc["name"], pc["level"], pc["cls"]) == ("Tira", 5, "wizard")
    assert pc["abilities"]["int"] == 18
    assert (pc["hp"], pc["hp_current"], pc["temp_hp"]) == (30 + 2 * 5, 33, 3)
    # Studded leather 12 + Dex 2 + worn ring 1; the unworn +2 item does not count.
    assert (pc["ac"], pc["ac_estimated"]) == (15, True)
    r = {x["key"]: x for x in pc["resources"]}
    assert (r["slot-1"]["max"], r["slot-1"]["spent"], r["slot-3"]["max"]) == (4, 2, 2)
    assert r["arcane-recovery"] == {"key": "arcane-recovery", "name": "Arcane Recovery", "kind": "long",
                                    "max": 1, "spent": 1}
    assert "summon-pool" not in r


def test_ddb_reference_forms():
    from ttrpgtools.dnd5e import ddb_character as ddb
    assert ddb.character_id("https://www.dndbeyond.com/characters/48690485/aBc") == "48690485"
    assert ddb.character_id(" 48690485 ") == "48690485"
    with pytest.raises(ddb.DDBError):
        ddb.character_id("not a link")


# ------------------------------------------------------------------ web
@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("TTRPG_DND5E_DB", str(tmp_path / "web.sqlite"))
    from ttrpgtools.web.app import create_app
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def test_web_flow_from_paste_to_fight(client):
    assert client.post("/TTRPG/dnd5e/api/monsters/parse", json={"text": "nope"}).status_code == 400
    parsed = client.post("/TTRPG/dnd5e/api/monsters/parse", json={"text": OGRE_2014}).get_json()
    assert parsed["name"] == "Ogre" and parsed["profile"]["dpr"] == 13
    ogre_id = client.post("/TTRPG/dnd5e/api/monsters", json={"text": OGRE_2014}).get_json()["id"]
    assert client.get("/TTRPG/dnd5e/api/monsters?q=ogr").get_json()["monsters"][0]["id"] == ogre_id

    pcs = [client.post("/TTRPG/dnd5e/api/pcs", json={"name": n, "cls": c, "level": 3, "hp": hp, "ac": ac}).get_json()["id"]
           for n, c, hp, ac in [("Tira", "wizard", 17, 12), ("Bram", "fighter", 31, 18)]]
    assert client.post("/TTRPG/dnd5e/api/pcs", json={"name": "", "level": 1}).status_code == 400

    encounter_id = client.post("/TTRPG/dnd5e/api/encounters", json={"name": "Bridge"}).get_json()["id"]
    updated = client.put(f"/TTRPG/dnd5e/api/encounters/{encounter_id}",
                         json={"monsters": [{"id": ogre_id, "count": 2}]}).get_json()
    assert updated["encounter"]["pcs"] == sorted(pcs)
    # Two PCs: the DMG moves the multiplier one step up (x2 instead of x1.5).
    assert updated["rating"]["official"]["dmg"]["adjusted_xp"] == 1800
    assert updated["rating"]["duel"]["band"] in ("Dangerous", "Lethal")
    for page in ("", "monsters", f"encounter/{encounter_id}"):
        assert client.get("/TTRPG/dnd5e/" + page).status_code == 200

    combat_id = client.post(f"/TTRPG/dnd5e/api/encounters/{encounter_id}/run").get_json()["id"]
    assert client.get(f"/TTRPG/dnd5e/combat/{combat_id}").status_code == 200
    state = client.get(f"/TTRPG/dnd5e/api/combats/{combat_id}").get_json()["state"]
    assert [c["label"] for c in state["combatants"]] == ["Bram", "Tira", "Ogre 1", "Ogre 2"]
    tira = next(c for c in state["combatants"] if c["label"] == "Tira")

    url = f"/TTRPG/dnd5e/api/combats/{combat_id}/op"
    after = client.post(url, json={"op": {"op": "damage", "id": tira["id"], "amount": 6}, "version": 0}).get_json()
    assert after["state"]["version"] == 1
    stale = client.post(url, json={"op": {"op": "damage", "id": tira["id"], "amount": 6}, "version": 0})
    assert stale.status_code == 409 and stale.get_json()["conflict"]
    added = client.post(url, json={"op": {"op": "add_monster", "monster_id": ogre_id, "count": 1}, "version": 1})
    assert [c["label"] for c in added.get_json()["state"]["combatants"]][-1] == "Ogre 3"
    assert client.post(url, json={"op": {"op": "bogus"}, "version": 2}).status_code == 400

    assert client.post(f"/TTRPG/dnd5e/api/combats/{combat_id}/sync-pcs").get_json()["updated"] == ["Bram", "Tira"]
    party = {p["name"]: p for p in client.get("/TTRPG/dnd5e/api/pcs").get_json()["pcs"]}
    assert party["Tira"]["hp_current"] == 11

    undone = client.post(f"/TTRPG/dnd5e/api/combats/{combat_id}/undo").get_json()["state"]
    assert len(undone["combatants"]) == 4
    assert client.delete(f"/TTRPG/dnd5e/api/monsters/{ogre_id}").status_code == 200
    # The running fight keeps its own copy of the stat block.
    assert client.get(f"/TTRPG/dnd5e/api/combats/{combat_id}").get_json()["state"]["combatants"][2]["statblock"]["name"] == "Ogre"


# ------------------------------------------------------------------ 5etools format
FIVETOOLS_FILE = {
    "_meta": {"sources": [{"json": "TestBook", "full": "Test Book"}]},
    "legendaryGroup": [{"name": "Cave", "source": "TestBook",
                        "lairActions": ["On initiative count 20:", {"type": "list", "items": [
                            {"type": "item", "name": "Rockfall", "entries": ["Stones fall, {@dc 13} Dexterity."]}]}]}],
    "monster": [
        {"name": "Cave Tyrant", "source": "TestBook", "page": 12, "size": ["L"],
         "type": {"type": "monstrosity", "tags": ["Solo"]}, "alignment": ["C", "E"], "alignmentPrefix": "typically ",
         "ac": [{"ac": 16, "from": ["natural armor"]}], "hp": {"average": 120, "formula": "16d10 + 32"},
         "speed": {"walk": 40, "fly": {"number": 30, "condition": "(hover)"}, "canHover": True},
         "str": 20, "dex": 12, "con": 15, "int": 6, "wis": 12, "cha": 8, "save": {"con": "+5"},
         "skill": {"perception": "+4"}, "senses": ["darkvision 60 ft."], "passive": 14, "cr": "5",
         "resist": ["cold", {"resist": ["bludgeoning", "piercing"], "note": "from mundane attacks", "cond": True}],
         "conditionImmune": ["frightened"], "languages": ["Common"],
         "trait": [{"name": "Tough (2/Day)", "entries": ["Shrugs it off."]}],
         "action": [
             {"name": "Multiattack", "entries": ["The tyrant makes two Claw attacks."]},
             {"name": "Claw", "entries": ["{@atk mw} {@hit 7} to hit, reach 5 ft., one target. {@h}14 ({@damage 2d8 + 5}) slashing damage and the target is {@condition prone}."]},
             {"name": "Roar {@recharge 5}", "entries": ["Each creature within 30 feet must make a {@dc 15} Wisdom saving throw, taking 22 ({@damage 4d10}) thunder damage on a failed save."]}],
         "bonus": [{"name": "Leap", "entries": ["Jumps. See {@creature goblin|MM|goblins}.{@sup {@cite Casting Times|X|A}}"]}],
         "legendaryHeader": ["The tyrant has three villain actions. They can take each action once during an encounter."],
         "legendary": [{"name": "Action 1: Crush", "entries": ["One creature takes 10 ({@damage 3d6}) bludgeoning damage."]},
                       {"name": "Action 2: Shake", "entries": ["The cave shakes."]},
                       {"name": "Action 3: Bury", "entries": ["Everything collapses."]}],
         "legendaryGroup": {"name": "Cave", "source": "TestBook"},
         "spellcasting": [{"name": "Spellcasting (Utility)", "headerEntries": ["Casts with Wisdom (spell save {@dc 13}):"],
                           "will": ["{@spell light}"], "daily": {"2e": ["{@spell fear}", "{@spell fly}"]}, "ability": "wis"}]},
        {"name": "Cave Rat", "source": "TestBook", "size": ["S"], "type": {"type": "beast", "tags": ["Minion"]},
         "alignment": ["U"], "ac": [12], "hp": {"special": "5"}, "speed": {"walk": 30},
         "str": 6, "dex": 14, "con": 10, "int": 2, "wis": 10, "cha": 4, "passive": "10 plus PB",
         "cr": {"cr": "1/2", "xp": 20},
         "action": [{"name": "Bite", "entries": ["{@atk mw} {@hit 4} to hit, reach 5 ft., one target. {@h}2 piercing damage."]}]},
    ],
}


def test_fivetools_conversion(tmp_path):
    from ttrpgtools.dnd5e import fivetools_import
    path = tmp_path / "book.json"
    path.write_text(json.dumps(FIVETOOLS_FILE), encoding="utf-8")
    conn = db.connect(tmp_path / "f.sqlite")
    stats = fivetools_import.import_file(str(path), conn, corrections={"Cave Rat": {"ac": [13]}})
    assert (stats["imported"], stats["sources"]) == (2, ["Test Book"])

    tyrant = bestiary.get_monster(conn, "cave-tyrant")
    assert (tyrant["role"], tyrant["type"], tyrant["alignment"]) == ("Solo", "monstrosity", "typically chaotic evil")
    assert (tyrant["ac"], tyrant["ac_text"], tyrant["hp"], tyrant["hp_formula"]) == (16, "16 (natural armor)", 120, "16d10+32")
    assert tyrant["speed"] == "40 ft., fly 30 ft. (hover)"
    assert tyrant["resist"] == "cold; bludgeoning, piercing from mundane attacks"
    claw = tyrant["actions"][1]
    assert claw["text"] == ("Melee Weapon Attack: +7 to hit, reach 5 ft., one target. "
                            "Hit: 14 (2d8 + 5) slashing damage and the target is prone.")
    assert claw["attacks"] == [{"name": "Claw", "to_hit": 7, "dice": "2d8+5", "avg": 14.0}]
    assert tyrant["actions"][2]["name"] == "Roar (Recharge 5-6)"
    assert tyrant["bonus_actions"][0]["text"] == "Jumps. See goblins."
    assert [v["name"] for v in tyrant["villain"]] == ["Action 1: Crush", "Action 2: Shake", "Action 3: Bury"]
    assert tyrant["legendary"] == [] and tyrant["legendary_uses"] == 0
    assert "Rockfall. Stones fall, DC 13 Dexterity." in tyrant["lair"][0]["text"]
    kinds = {r["name"]: (r["kind"], r["max"]) for r in tyrant["resources"]}
    assert kinds == {"Action 1: Crush": ("encounter", 1), "Action 2: Shake": ("encounter", 1),
                     "Action 3: Bury": ("encounter", 1), "Tough": ("day", 2), "Roar": ("recharge", 1),
                     "fear": ("day", 2), "fly": ("day", 2)}
    profile = difficulty.monster_profile(tyrant)
    # Round 1: Roar 22 on two targets plus villain action 1 (10).
    assert profile["routine"] == ["2x Claw"] and profile["round_damage"][0] == 54

    rat = bestiary.get_monster(conn, "cave-rat")
    assert (rat["role"], rat["cr"], rat["xp"], rat["hp"], rat["ac"], rat["passive"]) == ("Minion", "1/2", 20, 5, 13, 10)

    # A second import replaces the book's rows instead of duplicating them.
    fivetools_import.import_file(str(path), conn)
    assert conn.execute("SELECT COUNT(*) FROM monsters").fetchone()[0] == 2


def test_villain_actions_are_restored_by_a_rest():
    from ttrpgtools.dnd5e import fivetools_import
    tyrant = fivetools_import.convert_monster(FIVETOOLS_FILE["monster"][0], "Test Book", {})
    state = combat.new_combat("Lair", [], [(tyrant, 1)])
    c = state["combatants"][0]
    combat.apply(state, {"op": "spend", "id": c["id"], "key": "encounter-action-1-crush"})
    with pytest.raises(combat.CombatError):
        combat.apply(state, {"op": "spend", "id": c["id"], "key": "encounter-action-1-crush"})
    combat.apply(state, {"op": "rest", "kind": "short"})
    assert combat.resource(c, "encounter-action-1-crush")["spent"] == 0
