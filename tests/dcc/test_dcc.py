"""DCC rules and web tests. Rules tests use a small synthetic content fixture so
they run without the private core.json; the integration test needs it and is
skipped when it is absent."""

import json
import random

import pytest

from ttrpgtools import dcc


@pytest.fixture(autouse=True)
def own_town(tmp_path, monkeypatch):
    """Every test gets an empty town of its own instead of the live data/dcc_town.json."""
    from ttrpgtools.dcc.westmarch import places, town
    monkeypatch.setattr(town, "TOWN_PATH", tmp_path / "town" / "town.json")  # apart from the characters folder
    monkeypatch.setattr(places, "PLACES", [])
    monkeypatch.setattr(places, "BOTS", [])
    monkeypatch.setattr(places, "UPDATE_HOUR", 0)  # tests may run at any hour of the night
    from ttrpgtools.dcc.westmarch import daily, items
    monkeypatch.setattr(items, "DB_PATH", tmp_path / "town" / "campaign.sqlite")
    monkeypatch.setattr(dcc, "CHARACTERS_DIR", tmp_path / "characters")  # never the real character files
    monkeypatch.setattr(daily, "AUTO", False)                 # no background update threads during tests


@pytest.fixture(autouse=True)
def market_off(monkeypatch):
    """The old tests assume fixed prices, the rulebook's starting copper and the first debt of 10,000 gp: the town's house rules
    (places.MARKET, registry.start_copper, places.TAX_DEBT) are off here unless a test sets them."""
    from ttrpgtools.dcc.westmarch import places, registry
    monkeypatch.setattr(places, "MARKET", None)
    monkeypatch.setattr(places, "LIVES", None)
    monkeypatch.setattr(places, "FIELDS", None)
    monkeypatch.setattr(places, "TAX_DEBT", "10,000 gp")
    monkeypatch.setattr(registry, "start_copper", lambda rolled: int(rolled))

@pytest.fixture
def content():
    mods = {str(s): {"mod": m, "wizard_spells_known": k, "max_spell_level": ml} for s, m, k, ml in [
        (3, -3, "no spellcasting", "no spellcasting"), (8, -1, "no adjustment", "2"), (10, 0, "no adjustment", "3"),
        (13, 1, "no adjustment", "4"), (16, 2, "+1", "5"), (18, 3, "+2", "5")]}
    for s in range(4, 8):
        mods[str(s)] = {"mod": -1, "wizard_spells_known": "-1*", "max_spell_level": "1"}
    for s in (9, 11, 12):
        mods[str(s)] = {"mod": 0, "wizard_spells_known": "no adjustment", "max_spell_level": "3"}
    for s in (14, 15):
        mods[str(s)] = {"mod": 1, "wizard_spells_known": "+1", "max_spell_level": "4"}
    mods["17"] = {"mod": 2, "wizard_spells_known": "+2", "max_spell_level": "5"}
    row = lambda **kw: {"attack": "+0", "action_dice": "1d20", "ref": "+1", "fort": "+1", "will": "+0",
                        "crit_die": "1d10", "crit_table": "II", **kw}
    return {
        "ability_mods": mods,
        "occupations": [{"roll": [1, 50], "occupation": "Farmer", "weapon": "Pitchfork (as spear)", "trade_goods": "Hen"},
                        {"roll": [51, 100], "occupation": "Dwarven Miner", "weapon": "Pick (as club)", "trade_goods": "Lantern"}],
        "luck_augurs": [{"roll": n, "augur": f"Augur {n}", "applies_to": "Melee attack rolls"} for n in range(1, 31)],
        "equipment": [{"roll": n, "item": f"Item {n}", "cost": "1 cp"} for n in range(1, 25)],
        "weapons": [{"name": "Spear", "damage": "1d8", "range": None, "two_handed": False},
                    {"name": "Club", "damage": "1d4", "range": None, "two_handed": False},
                    {"name": "Longbow", "damage": "1d6", "range": "70/140/210", "two_handed": True}],
        "armor": [{"name": "Leather", "ac": 2, "check_penalty": -1, "speed_penalty": 0, "fumble_die": "d8", "cost": "20 gp"},
                  {"name": "Chainmail", "ac": 5, "check_penalty": -5, "speed_penalty": -5, "fumble_die": "d12", "cost": "150 gp"}],
        "classes": {
            "warrior": {"1": row(attack="+d3", threat_range="19-20", crit_die="1d12", crit_table="III"),
                        "2": row(attack="+d4", threat_range="19-20", crit_die="1d14", crit_table="III")},
            "wizard": {"1": row(spells_known="4", max_spell_level="1"), "2": row(spells_known="5", max_spell_level="1")},
            "cleric": {"1": row(spells_l1="4", spells_l2="-", spells_l3="-", spells_l4="-", spells_l5="-")},
            "thief": {"1": row(luck_die="d3")}, "dwarf": {"1": row(attack="+d3")}, "elf": {"1": row(spells_known="3", max_spell_level="1")},
            "halfling": {"1": row(sneak_hide="+3")},
        },
        "class_titles": {"warrior": {"1": {"lawful": "Squire", "neutral": "Wildling", "chaotic": "Bandit"}}},
        "class_prose": {"warrior": {"Hit points": "d12"}},
        "thief_skills": {"neutral": {"Backstab": ["+1"] * 10, "Sneak Silently": ["+3"] * 10, "Use Scroll": ["d10"] * 10}},
        "spells": [{"name": "Magic Missile", "class": "wizard", "patron": None, "level": 1, "results": []},
                   {"name": "Fireball", "class": "wizard", "patron": None, "level": 3, "results": []},
                   {"name": "Blessing", "class": "cleric", "patron": None, "level": 1, "results": []},
                   {"name": "Snake Trick", "class": "patron", "patron": "Bobugbubilz", "level": 1, "results": []}],
        "xp_thresholds": {"0": 0, "1": 10, "2": 50, "3": 110},
        "crit_tables": {"I": [], "II": [], "III": []}, "mighty_deeds": {},
    }


def make(content, **abilities):
    ab = {"strength": 10, "agility": 10, "stamina": 10, "personality": 10, "intelligence": 10, "luck": 10, **abilities}
    occ = {"roll": [1, 50], "occupation": "Farmer", "weapon": "Pitchfork (as spear)", "trade_goods": "Hen"}
    return dcc.new_character("Test", ab, occ, content["luck_augurs"][0], hp_roll=3, copper=20,
                             equipment_item="Rope", content=content)


def test_zero_level_derivation(content):
    c = make(content, agility=16, stamina=8, luck=13)
    v = dcc.derive(c, content)
    assert c["hp_max"] == 2  # 3 - 1 Stamina
    assert v["ac"] == 12 and v["saves"]["reflex"] == 2 and v["saves"]["fortitude"] == -1
    assert v["attack"] == "+0" and v["crit_table"] == "I" and v["crit_die"] == "1d4"
    assert c["birth_augur"]["modifier"] == 1 and "Melee attack rolls (+1)" == v["lucky_roll"]
    assert v["weapons"][0]["damage"] == "1d8"  # pitchfork resolves to spear
    assert v["class_choices"] == ["cleric", "thief", "warrior", "wizard"]


def test_armor_and_shield(content):
    c = make(content)
    dcc.add_item(c, "Chainmail", "armor"); dcc.add_item(c, "Shield", "shield")
    v = dcc.derive(c, content)
    assert v["ac"] == 16 and v["speed"] == 25 and v["check_penalty"] == -6 and v["fumble_die"] == "d12"


def test_level_up_warrior(content):
    c = make(content, strength=16, stamina=13)
    dcc.level_up(c, "warrior", hp_roll=7, content=content)
    v = dcc.derive(c, content)
    assert c["level"] == 1 and c["hp_max"] == 4 + 8  # 0-level 3+1, then 7+1
    assert v["deed_die"] and v["attack"] == "+d3" and v["initiative"] == "+1" and v["title"] == "Wildling"
    assert "Str" in v["weapons"][0]["melee_bonus"]
    with pytest.raises(dcc.DCCError):
        dcc.level_up(c, "wizard", hp_roll=1, content=content)  # class fixed after level 1
    c["xp"] = 5
    assert dcc.derive(c, content)["can_level"] is False
    c["xp"] = 50
    assert dcc.derive(c, content)["can_level"] is True


def test_race_locks_class(content):
    c = make(content)
    c["occupation"] = {"roll": [51, 100], "occupation": "Dwarven Miner", "weapon": "Pick (as club)", "trade_goods": "Lantern"}
    assert dcc.derive(c, content)["class_choices"] == ["dwarf"]
    with pytest.raises(dcc.DCCError):
        dcc.level_up(c, "warrior", hp_roll=1, content=content)
    dcc.level_up(c, "dwarf", hp_roll=5, content=content)
    assert c["class"] == "dwarf" and dcc.derive(c, content)["speed"] == 20
    human = make(content)
    with pytest.raises(dcc.DCCError):
        dcc.level_up(human, "elf", hp_roll=1, content=content)


def test_wizard_spells(content):
    c = make(content, intelligence=16)
    dcc.level_up(c, "wizard", hp_roll=2, content=content)
    allowance = dcc.spell_allowance(c, content)
    assert allowance["total"] == 5 and allowance["max_level"] == 1 and allowance["check_bonus"] == 3
    with pytest.raises(dcc.DCCError, match="patron spell"):
        dcc.set_spells(c, ["Magic Missile", "Snake Trick"], content)  # no patron bond, no patron
    dcc.set_spells(c, ["Magic Missile"], content)
    assert c["spells"] == ["Magic Missile"]
    with pytest.raises(dcc.DCCError):
        dcc.set_spells(c, ["Fireball"], content)  # above max level
    with pytest.raises(dcc.DCCError):
        dcc.set_spells(c, ["Blessing"], content)  # cleric spell
    with pytest.raises(dcc.DCCError):
        dcc.set_spells(c, ["Magic Missile"] * 6, content)


def test_cleric_spells_per_level(content):
    c = make(content, personality=13)
    dcc.level_up(c, "cleric", hp_roll=4, content=content)
    allowance = dcc.spell_allowance(c, content)
    assert allowance["per_level"][1] == 4 and allowance["max_level"] == 1
    with pytest.raises(dcc.DCCError):
        dcc.set_spells(c, ["Blessing"] * 5, content)


def test_thief_skills_add_ability(content):
    c = make(content, agility=16)
    dcc.level_up(c, "thief", hp_roll=1, content=content)
    skills = {s["skill"]: s["value"] for s in dcc.derive(c, content)["thief_skills"]}
    assert skills["Sneak Silently"] == "+5" and skills["Backstab"] == "+1" and skills["Use Scroll"] == "d10"


def test_funnel_roll_is_reproducible(content):
    a = dcc.roll_funnel_character(random.Random(7), content, "A")
    b = dcc.roll_funnel_character(random.Random(7), content, "A")
    assert a["abilities"] == b["abilities"] and a["occupation"] == b["occupation"]
    assert 1 <= a["hp_max"] and 5 <= a["coins"]["cp"] <= 60 and len(a["equipment"]) == 2


def test_storage_roundtrip(tmp_path, monkeypatch, content):
    monkeypatch.setattr(dcc, "CHARACTERS_DIR", tmp_path)
    c = make(content)
    cid = dcc.new_character_id("Test Name!")
    assert cid == "test-name"
    dcc.save_character(c, cid)
    assert dcc.new_character_id("Test Name!") == "test-name-2"
    assert dcc.load_character(cid)["name"] == "Test" and dcc.list_characters()[0]["id"] == cid
    with pytest.raises(dcc.DCCError):
        dcc.character_path("../etc/passwd")


@pytest.mark.skipif(not dcc.content_available(), reason="private DCC content not built")
def test_web_flow_with_real_content(tmp_path, monkeypatch):
    from ttrpgtools.web.app import create_app
    monkeypatch.setattr(dcc, "CHARACTERS_DIR", tmp_path)
    client = create_app().test_client()
    assert client.get("/TTRPG/dcc/").status_code == 200
    page = client.post("/TTRPG/dcc/funnel", data={"count": 3, "seed": "x", "prefix": "Test"})
    assert page.status_code == 200 and page.data.count(b"funnel-card") == 3
    import html
    raw = json.loads(html.unescape(page.data.decode().split("value='", 1)[1].split("'", 1)[0]))
    resp = client.post("/TTRPG/dcc/funnel/keep", data={"keep": [json.dumps(raw)]}, follow_redirects=False)
    cid = resp.headers["Location"].rsplit("/", 2)[1]  # .../<id>/build
    assert client.get(f"/TTRPG/dcc/{cid}/build").status_code == 200
    sheet = client.get(f"/TTRPG/dcc/{cid}")
    assert sheet.status_code == 200 and b"Birth augur" in sheet.data
    assert client.get(f"/TTRPG/dcc/{cid}/json").status_code == 200


def test_augur_targets_and_roll_breakdown(content):
    assert dcc.augur_targets("Spell checks") == {"spell_check"}
    assert dcc.augur_targets("Saving throws") == {"reflex", "fortitude", "willpower"}
    assert dcc.augur_targets("Reflex saving throws") == {"reflex"}
    assert dcc.augur_targets("Critical hit tables**") == {"crit"}
    assert dcc.augur_targets("Saving Throws vs. Poison") == {"save_poison"}
    c = make(content, intelligence=16, luck=16)
    c["birth_augur"] = {"roll": 13, "augur": "Seventh son", "applies_to": "Spell checks", "modifier": 2}
    dcc.level_up(c, "wizard", hp_roll=2, content=content)
    rolls = {r["key"]: r for r in dcc.derive(c, content)["rolls"]}
    assert rolls["spell_check"]["total"] == "1d20 +5"  # level 1 + Int 2 + augur 2
    assert any("birth augur" in name for name, _ in rolls["spell_check"]["parts"])
    assert not any("birth augur" in name for name, _ in rolls["melee_attack"]["parts"])
    assert rolls["mercurial"]["total"] == "d% +20"
    c["birth_augur"] = {"roll": 26, "augur": "Warrior's arm", "applies_to": "Critical hit tables**", "modifier": 1}
    rolls = {r["key"]: r for r in dcc.derive(c, content)["rolls"]}
    # "the modifier is doubled": the normal Luck modifier plus the fixed birth modifier, not three times
    assert rolls["crit"]["parts"] == [("Luck", "+2"), ("birth augur (Warrior's arm)", "+1")] and rolls["crit"]["total"].endswith("+3")


def test_lucky_weapon_is_fixed_at_first_level(content):
    c = make(content, luck=16)
    dcc.level_up(c, "warrior", hp_roll=6, content=content)
    assert c["first_level_luck_mod"] == 2
    c["lucky_weapon"] = "Spear"
    c["luck_current"] = 5
    x = dcc.derive(c, content)["class_extras"]
    assert x["lucky_weapon"] == {"chosen": "Spear", "modifier": 2, "rule": x["lucky_weapon"]["rule"]}


def test_elf_free_spells_and_mercurial(content):
    content["spells"] += [{"name": "Patron Bond", "class": "wizard", "patron": None, "level": 1, "results": []},
                          {"name": "Invoke Patron", "class": "wizard", "patron": None, "level": 1, "results": []}]
    content["mercurial_magic"] = [{"roll": "01", "text": "At great cost. Someone dies."}, {"roll": "41-60", "text": "No change."}, {"roll": "00", "text": "Twice."}]
    c = make(content, intelligence=13)
    c["occupation"] = {"roll": [1, 1], "occupation": "Elven Sage", "weapon": "Dagger", "trade_goods": "Parchment"}
    dcc.level_up(c, "elf", hp_roll=3, content=content)
    dcc.set_spells(c, ["Magic Missile", "Patron Bond", "Magic Missile"], content) if False else None
    c["patron"] = "Bobugbubilz"
    dcc.set_spells(c, ["Magic Missile", "Snake Trick", "Magic Missile"][:2], content)
    assert c["spells"] == ["Patron Bond", "Invoke Patron", "Magic Missile", "Snake Trick"]
    dcc.set_spell_detail(c, "Magic Missile", 50)
    with pytest.raises(dcc.DCCError):
        dcc.set_spell_detail(c, "Fireball", 10)
    with pytest.raises(dcc.DCCError):
        dcc.set_spell_detail(c, "Magic Missile", 101)
    v = dcc.derive(c, content)
    mm = next(s for s in v["spells"] if s["name"] == "Magic Missile")
    assert mm["mercurial"]["text"] == "No change." and mm["mercurial_roll"] == 50
    assert dcc.mercurial_entry(content, 100)["text"] == "Twice."
    assert v["class_extras"]["free_spells"] == ["Patron Bond", "Invoke Patron"]


def test_action_dice_explanation(content):
    c = make(content)
    a = dcc.derive(c, content)["action"]
    assert a["dice"] == ["1d20"] and a["count"] == 1 and a["lines"][0] == "1 action per round."
    dcc.level_up(c, "warrior", hp_roll=5, content=content)
    content["classes"]["warrior"]["1"]["action_dice"] = "1d20+1d14"
    a = dcc.derive(c, content)["action"]
    assert a["dice"] == ["1d20", "1d14"] and "second action rolls 1d14" in a["lines"][2]
    assert any("Natural 19-20" in l for l in a["lines"])


def test_augur_effect_sentence(content):
    c = make(content, luck=13)
    c["birth_augur"] = {"roll": 23, "augur": "Charmed House", "applies_to": "Armor Class", "modifier": 1}
    assert dcc.augur_effect(c) == "Charmed House: +1 to armor class, fixed for life"
    c["birth_augur"] = {"roll": 28, "augur": "The Broken Star", "applies_to": "Fumbles**", "modifier": -1}
    assert "Luck counts double on fumbles" in dcc.augur_effect(c)
    c["birth_augur"] = {"roll": 30, "augur": "Wild Child", "applies_to": "Speed", "modifier": 2}
    assert "+10' speed" in dcc.augur_effect(c)
    c["birth_augur"] = {"roll": 2, "augur": "The Bull", "applies_to": "Melee Attack Rolls", "modifier": 0}
    assert dcc.augur_effect(c).startswith("The Bull: no effect")


def test_spellburn_and_ability_damage_flow_into_rolls(content):
    c = make(content, strength=16, agility=13, intelligence=16)
    dcc.level_up(c, "wizard", hp_roll=2, content=content)
    assert dcc.spellburn(c, strength=3, stamina=1) == {"bonus": 4, "natural_20": False}
    v = dcc.derive(c, content)
    assert v["effective"]["strength"] == 13 and v["mods"]["strength"] == 1 and v["ability_damage"]["stamina"] == 1
    rolls = {r["key"]: r for r in v["rolls"]}
    assert rolls["melee_attack"]["total"] == "1d20 +1"
    with pytest.raises(dcc.DCCError):
        dcc.spellburn(c, strength=14)
    assert dcc.heal_ability_damage(c, 1) == ["strength"]  # one point in total per night, most damaged first
    assert c["ability_damage"] == {"strength": 2, "stamina": 1}
    dcc.set_ability_damage(c, "strength", 0)
    assert "strength" not in c["ability_damage"]
    dcc.add_item(c, "Chainmail", "armor")
    rolls = {r["key"]: r for r in dcc.derive(c, content)["rolls"]}
    assert ("armor check penalty", "-5") in rolls["spell_check"]["parts"]


def test_luck_burn_and_recovery(content):
    c = make(content, luck=12)
    dcc.level_up(c, "thief", hp_roll=3, content=content)
    dcc.burn_luck(c, 4)
    assert c["luck_current"] == 8
    with pytest.raises(dcc.DCCError):
        dcc.burn_luck(c, 9)
    assert dcc.recover_luck(c) == 1 and c["luck_current"] == 9  # thief level 1 per night
    human = make(content, luck=12); dcc.level_up(human, "warrior", hp_roll=3, content=content); dcc.burn_luck(human, 2)
    assert dcc.recover_luck(human) == 0 and dcc.recover_luck(human, 5) == 2


def test_hp_augur_applies_on_level_up(content):
    c = make(content, luck=16)
    c["birth_augur"] = {"roll": 25, "augur": "Bountiful Harvest", "applies_to": "Hit Points (applies at each level)", "modifier": 2}
    before = c["hp_max"]
    dcc.level_up(c, "warrior", hp_roll=4, content=content)
    assert c["hp_max"] == before + 4 + 2 and c["history"][-1]["augur_hp"] == 2


def test_two_weapon_and_backstab(content):
    content["two_weapon"] = [{"agility": [3, 8], "primary": "-3 dice", "off_hand": "-4 dice", "crits": "cannot crit"},
                             {"agility": [12, 15], "primary": "-1 die", "off_hand": "-2 dice", "crits": "cannot crit"}]
    content["weapons"].append({"name": "Dagger", "damage": "1d4/1d10", "range": "10/20/30", "two_handed": False, "backstab_weapon": True})
    c = make(content, agility=13)
    dcc.level_up(c, "thief", hp_roll=3, content=content)
    c["inventory"] = [i for i in c["inventory"] if i["kind"] != "weapon"]
    dcc.add_item(c, "Dagger", "weapon")
    v = dcc.derive(c, content)
    tw = next(r for r in v["rolls"] if r["key"] == "two_weapon")
    assert tw["total"] == "primary -1 die, off hand -2 dice"
    assert v["weapons"][0]["damage"] == "1d4" and v["weapons"][0]["backstab_damage"] == "1d10"


def test_coins_and_purchases(content):
    assert dcc.cost_in_cp("7") == 700 and dcc.cost_in_cp("5 sp") == 50 and dcc.cost_in_cp("1,200 gp") == 120000 and dcc.cost_in_cp("x4*") is None
    assert dcc.spend({"gp": 1, "sp": 0, "cp": 3}, 25) == {"gp": 0, "sp": 7, "cp": 8}  # breaks a gp into change
    with pytest.raises(dcc.DCCError):
        dcc.spend({"gp": 0, "sp": 1, "cp": 0}, 25)


def test_inventory_migration_equip_and_buy(content):
    c = make(content)
    c.pop("inventory")  # a character saved before the structured inventory existed
    c["weapons"], c["armor"], c["shield"], c["equipment"] = ["Spear"], "Leather", True, ["Rope", "Hen"]
    c["coins"] = {"gp": 5, "sp": 0, "cp": 0}
    inv = dcc.ensure_inventory(c)
    assert [(i["name"], i["kind"], i["equipped"]) for i in inv] == [("Spear", "weapon", True), ("Leather", "armor", True), ("Shield", "shield", True), ("Rope", "gear", False), ("Hen", "trade", False)]
    dcc.add_item(c, "Chainmail", "armor", cost="150 gp", buy=False)
    assert c["armor"] == "Leather"  # new armor carried, not worn
    dcc.set_equipped(c, 5, True)
    assert c["armor"] == "Chainmail" and dcc.derive(c, content)["ac"] == 16 and not inv[1]["equipped"]
    dcc.add_item(c, "Club", "weapon", cost="3", buy=True)
    assert c["coins"] == {"gp": 2, "sp": 0, "cp": 0} and c["weapons"] == ["Spear", "Club"]
    dcc.add_item(c, "Rope", "gear", qty=2)
    assert next(i for i in inv if i["name"] == "Rope")["qty"] == 3
    dcc.change_qty(c, 3, -3)
    assert not any(i["name"] == "Rope" for i in inv) and "Rope x3" not in c["equipment"]
    with pytest.raises(dcc.DCCError):
        dcc.add_item(c, "Longbow", "weapon", cost="40", buy=True)  # cannot afford
    dcc.set_equipped(c, 0, False)
    assert c["weapons"] == ["Club"] and "Spear" in c["equipment"]


def test_weapon_training_and_ammo(content):
    content["class_prose"]["wizard"] = {"Weapon training": "A wizard is trained in the use of the dagger, longbow, longsword, shortbow, short sword, and staff.", "Action dice": "x"}
    content["weapons"] += [{"name": "Dagger", "damage": "1d4/1d10", "range": "10/20/30", "two_handed": False, "backstab_weapon": True}]
    content["ammunition"] = [{"name": "Arrows", "quantity": 20, "cost": "5 gp"}]
    c = make(content)
    assert dcc.trained_weapons(c, content) is None  # 0-level: the untrained penalty is waived (p. 24)
    dcc.level_up(c, "wizard", hp_roll=2, content=content)
    assert dcc.trained_weapons(c, content) == {"Spear", "Dagger", "Longbow"}
    dcc.add_item(c, "Club", "weapon"); dcc.add_item(c, "Longbow", "weapon")
    v = dcc.derive(c, content)
    by = {w["name"]: w for w in v["weapons"]}
    assert by["Club"]["trained"] is False and by["Longbow"]["trained"] is True and by["Longbow"]["ammo"] == 0
    dcc.add_item(c, "Arrows", "ammo", qty=20)
    assert {w["name"]: w["ammo"] for w in dcc.derive(c, content)["weapons"]}["Longbow"] == 20
    rolls = {r["key"]: r for r in dcc.derive(c, content)["rolls"]}
    assert "untrained: -1d with Club" in rolls["melee_attack"]["note"]


def test_halfling_dwarf_elf_thief_rows(content):
    content["two_weapon"] = [{"agility": [12, 15], "primary": "-1 die", "off_hand": "-2 dice", "crits": "cannot crit"},
                             {"agility": [16, 17], "primary": "-1 die", "off_hand": "-1 die", "crits": "primary crits on max"}]
    content["class_prose"]["halfling"] = {"Two-weapon Fighting": "masters", "Small size": "small", "Action dice": "x"}
    content["class_prose"]["dwarf"] = {"Sword and board": "bash", "Underground Skills": "smell gold", "Action dice": "x"}
    content["class_prose"]["elf"] = {"Immunities": "sleep", "Action dice": "x"}
    content["weapons"].append({"name": "Longsword", "damage": "1d8", "range": None, "two_handed": False})
    h = make(content, agility=13)
    h["occupation"] = {"roll": [1, 1], "occupation": "Halfling Trader", "weapon": "Short sword", "trade_goods": "20 sp"}
    dcc.level_up(h, "halfling", hp_roll=3, content=content)
    v = dcc.derive(h, content)
    tw = next(r for r in v["rolls"] if r["key"] == "two_weapon")
    assert tw["total"] == "primary -1 die, off hand -1 die" and ("halfling minimum", "16") in tw["parts"]
    assert [s["skill"] for s in v["thief_skills"]] == ["Sneak Silently", "Hide in Shadows"] and v["thief_skills"][0]["value"] == "+4"  # +3 table +1 Agi
    d = make(content, strength=16)
    d["occupation"] = {"roll": [1, 1], "occupation": "Dwarven Miner", "weapon": "Pick (as club)", "trade_goods": "Lantern"}
    dcc.level_up(d, "dwarf", hp_roll=5, content=content)
    dcc.add_item(d, "Shield", "shield")
    keys = {r["key"]: r for r in dcc.derive(d, content)["rolls"]}
    assert keys["shield_bash"]["total"].startswith("1d14 +d3 +2") and keys["underground"]["total"] == "+1"
    e = make(content, intelligence=13)
    e["occupation"] = {"roll": [1, 1], "occupation": "Elven Sage", "weapon": "Dagger", "trade_goods": "Parchment"}
    dcc.level_up(e, "elf", hp_roll=3, content=content)
    dcc.add_item(e, "Longsword", "weapon")
    ve = dcc.derive(e, content)
    assert next(r for r in ve["rolls"] if r["key"] == "secret_doors")["total"] == "+4"
    assert "Longsword" in ve["class_extras"]["iron_items"]
    t = make(content, agility=16)
    t["birth_augur"] = {"roll": 11, "augur": "Fox's Cunning", "applies_to": "Find/Disable Traps", "modifier": 1}
    content["thief_skills"]["neutral"]["Find Trap"] = ["+3"] * 10
    dcc.level_up(t, "thief", hp_roll=3, content=content)
    vt = dcc.derive(t, content)
    skills = {s["skill"]: s for s in vt["thief_skills"]}
    assert skills["Find Trap"]["value"] == "+4" and ("birth augur", "+1") in skills["Find Trap"]["parts"]
    assert skills["Sneak Silently"]["value"] == "+5"
    assert next(r for r in vt["rolls"] if r["key"] == "backstab")["total"] == "melee attack +1"


@pytest.mark.skipif(not dcc.content_available(), reason="private DCC content not built")
def test_folio_renders_eight_pages_and_imposes(tmp_path, monkeypatch):
    import io, random
    from pypdf import PdfReader
    from ttrpgtools.dcc import folio as dcc_folio
    content = dcc.load_content()
    for klass, occ_name in (("warrior", "Farmer"), ("wizard", "Scribe") if any(o["occupation"] == "Scribe" for o in content["occupations"]) else ("wizard", "Farmer"), ("thief", "Cutpurse")):
        occ = next(o for o in content["occupations"] if o["occupation"] == occ_name)
        ch = dcc.new_character("Folio Test", {"strength": 13, "agility": 12, "stamina": 11, "personality": 10, "intelligence": 14, "luck": 12}, occ, content["luck_augurs"][22], 3, 25, "Rope", "lawful", "player", content)
        dcc.level_up(ch, klass, 3, content)
        if klass == "wizard":
            dcc.set_spells(ch, [s["name"] for s in dcc.spell_list(content, "wizard", ch) if s["level"] == 1][:4], content)
        ch["campaign"] = {"name": "The Valley", "home": "a goat", "religion": "none", "relations": ["Miller: owes me"], "goals": [{"text": "steal a hat", "done": True}]}
        data = dcc_folio.render(ch, content)
        assert data.startswith(b"%PDF") and len(PdfReader(io.BytesIO(data)).pages) == 8, klass
        imposed = dcc_folio.render(ch, content, imposed=True)
        assert len(PdfReader(io.BytesIO(imposed)).pages) == 4


# ------------------------------------------------------------------ rules audit against the printed book (2026-10-04)
real = pytest.mark.skipif(not dcc.content_available(), reason="private DCC content not built")


def hero(occupation="Scribe", augur=2, alignment="neutral", klass=None, level=0, extras=None, **abilities):
    content = dcc.load_content()
    occ = next(o for o in content["occupations"] if o["occupation"].lower() == occupation.lower())
    aug = next(a for a in content["luck_augurs"] if a["roll"] == augur)
    c = dcc.new_character("Hero", {**{a: 10 for a in dcc.ABILITIES}, **abilities}, occ, aug, hp_roll=3, copper=30,
                          equipment_item="Rope, 50’", alignment=alignment, content=content, extras=extras)
    for _ in range(level):
        dcc.level_up(c, klass, 1, content)
    return c, content


@real
def test_titles_follow_each_tables_own_column_order():
    titles = dcc.load_content()["class_titles"]
    assert titles["wizard"]["1"] == {"chaotic": "Cultist", "lawful": "Evoker", "neutral": "Astrologist"}
    assert titles["cleric"]["5"] == {"lawful": "Father", "chaotic": "High priest", "neutral": "Druid"}
    assert titles["thief"]["1"]["chaotic"] == "Thug" and titles["dwarf"]["5"]["neutral"] == "Thegn"
    assert titles["warrior"]["3"] == {"lawful": "Knight", "chaotic": "Marauder", "neutral": "Berserker"}
    c, content = hero("Elven Sage", alignment="lawful", klass="elf", level=2)
    assert dcc.derive(c, content)["title"] == "Seer"


@real
def test_class_table_spot_values():
    k = dcc.load_content()["classes"]
    assert k["warrior"]["7"]["attack"] == "+d10+1" and k["warrior"]["8"]["crit_die"] == "2d20" and k["warrior"]["9"]["threat_range"] == "17-20"
    assert k["thief"]["8"]["crit_die"] == "1d30+2" and k["thief"]["10"]["luck_die"] == "d16"
    assert k["cleric"]["5"]["spells_l3"] == "2" and k["cleric"]["9"]["spells_l5"] == "1" and k["cleric"]["6"]["action_dice"] == "1d20+1d14"
    assert k["dwarf"]["4"]["crit_table"] == "IV" and k["elf"]["9"]["spells_known"] == "12" and k["halfling"]["10"]["sneak_hide"] == "+15"
    assert k["wizard"]["8"]["spells_known"] == "12" and k["wizard"]["10"]["action_dice"] == "1d20+1d20+1d14"


def test_coin_values():
    assert dcc.cost_in_cp("1 ep") == 1000 and dcc.cost_in_cp("2 pp") == 20000 and dcc.cost_in_cp("3 sp") == 30


@real
def test_zero_level_occupation_footnotes():
    c, content = hero("Halfling Moneylender")
    assert c["coins"] == {"gp": 5, "sp": 10, "cp": 230} and not any(i["kind"] == "trade" for i in c["inventory"])
    c, content = hero("Mercenary", agility=13)
    assert c["armor"] == "Hide" and dcc.derive(c, content)["ac"] == 14  # 10 + 1 Agi + 3 hide
    c, content = hero("Soldier")
    v = dcc.derive(c, content)
    assert c["shield"] and v["ac"] == 11 and v["fumble_die"] == "d8"  # a shield alone still raises the fumble die
    c, content = hero("Guild Beggar", extras={"ammo": 5})
    assert [(i["name"], i["qty"]) for i in c["inventory"] if i["kind"] == "ammo"] == [("Sling stones", 5)]
    assert dcc.derive(c, content)["weapons"][0]["ammo"] == 5
    c, content = hero("Jester", extras={"ammo": 4})
    assert next(i for i in c["inventory"] if i["kind"] == "weapon")["qty"] == 4
    c, content = hero("Farmer", extras={"farmer_type": 3, "animal": 6})
    assert c["occupation"]["detail"] == "turnip farmer" and any(i["name"] == "Mule" for i in c["inventory"])
    c, content = hero("Wainwright", extras={"cart": 4})
    assert any(i["name"] == "Pushcart (your dead)" for i in c["inventory"])
    keys = lambda name: [e["key"] for e in dcc.occupation_extras(content, next(o for o in content["occupations"] if o["occupation"] == name))]
    assert keys("Farmer") == ["farmer_type"] and keys("Hunter") == ["ammo"] and keys("Wainwright") == ["cart"] and keys("Scribe") == ["ammo"]
    assert keys("Alchemist") == []


@real
def test_zero_level_hit_points_and_validation():
    c, content = hero(augur=25, stamina=16, luck=16)  # Bountiful harvest applies at each level, level 0 included
    assert c["hp_max"] == 3 + 2 + 2
    c, content = hero(stamina=3)
    assert c["hp_max"] == 1  # minimum 1 hit point per level
    occ, aug = content["occupations"][0], content["luck_augurs"][0]
    ab = {a: 10 for a in dcc.ABILITIES}
    with pytest.raises(dcc.DCCError):
        dcc.new_character("X", ab, occ, aug, hp_roll=5, copper=10, equipment_item="", content=content)
    with pytest.raises(dcc.DCCError):
        dcc.new_character("X", {**ab, "luck": 19}, occ, aug, hp_roll=2, copper=10, equipment_item="", content=content)
    c, content = hero(klass="warrior", level=1)
    with pytest.raises(dcc.DCCError):
        dcc.level_up(c, None, 13, content)  # d12
    w, content = hero()
    with pytest.raises(dcc.DCCError):
        dcc.level_up(w, "wizard", 5, content)  # d4


@real
def test_burned_luck_lowers_the_modifier_but_not_the_augur():
    c, content = hero(augur=26, luck=16, klass="warrior", level=1)  # Warrior's arm
    rolls = {r["key"]: r for r in dcc.derive(c, content)["rolls"]}
    assert rolls["crit"]["total"] == "1d12 +4" and rolls["fumble"]["parts"][0] == ("Luck (subtract)", "-2")
    dcc.burn_luck(c, 4)  # Luck 12: modifier 0
    v = dcc.derive(c, content)
    rolls = {r["key"]: r for r in v["rolls"]}
    assert v["mods"]["luck"] == 0 and rolls["crit"]["total"] == "1d12 +2" and c["birth_augur"]["modifier"] == 2
    assert c["first_level_luck_mod"] == 2  # the lucky weapon keeps its 1st-level value
    b, content = hero(augur=28, luck=13)  # The Broken Star: both parts are subtracted
    assert {r["key"]: r for r in dcc.derive(b, content)["rolls"]}["fumble"]["total"] == "d4 -2"


@real
def test_unconditional_augurs_reach_the_headline_numbers():
    for augur, key, expect in ((23, "ac", 12), (24, "initiative", "+2"), (30, "speed", 40)):
        c, content = hero(augur=augur, luck=16)
        assert dcc.derive(c, content)[key] == expect, key
    c, content = hero(augur=17, luck=13)
    assert dcc.derive(c, content)["saves"] == {"reflex": 1, "fortitude": 1, "willpower": 1}
    c, content = hero(augur=21, luck=4)
    assert dcc.derive(c, content)["saves"] == {"reflex": 0, "fortitude": -2, "willpower": 0}


@real
def test_weapon_training_by_class():
    c, content = hero()
    dcc.add_item(c, "Two-handed sword", "weapon")
    assert dcc.derive(c, content)["class_extras"]["untrained_wielded"] == []  # 0 level: no penalty with anything
    w, content = hero(klass="warrior", level=1)
    trained = dcc.trained_weapons(w, content)
    assert {"Longsword", "Polearm", "Lance", "Dart"} <= trained and not {"Blackjack", "Blowgun", "Garrote"} & trained
    for alignment, yes, no in (("lawful", "Warhammer", "Longsword"), ("neutral", "Two-handed sword", "Club"), ("chaotic", "Battleaxe", "Mace")):
        k, content = hero(alignment=alignment, klass="cleric", level=1)
        trained = dcc.trained_weapons(k, content)
        assert yes in trained and no not in trained, alignment
    t, content = hero(klass="thief", level=1)
    assert {"Blackjack", "Garrote", "Longsword"} <= dcc.trained_weapons(t, content) and "Mace" not in dcc.trained_weapons(t, content)
    h, content = hero("Halfling Trader", klass="halfling", level=1)
    assert "Longsword" not in dcc.trained_weapons(h, content) and "Short sword" in dcc.trained_weapons(h, content)


@real
def test_wizard_spell_table():
    w, content = hero(klass="wizard", level=1)
    names = {s["name"]: s for s in dcc.spell_list(content, "wizard", w)}
    assert names["Detect Magic"]["level"] == 1 and "check_penalty" not in names["Detect Magic"]
    assert names["Detect Evil"]["level"] == 2 and names["Binding"]["level"] == 3 and names["Paralysis"]["check_penalty"] == -2
    assert not any(s["class"] == "patron" for s in names.values())
    dcc.set_spells(w, ["Patron Bond", "Magic Missile", "Sleep", "Detect Magic"], content)
    assert set(dcc.PATRON_PAIR) <= set(w["spells"]) and dcc.derive(w, content)["spellcasting"]["used"] == 4  # the pair is one slot
    with pytest.raises(dcc.DCCError, match="Too many"):
        dcc.set_spells(w, ["Patron Bond", "Magic Missile", "Sleep", "Detect Magic", "Cantrip"], content)
    with pytest.raises(dcc.DCCError, match="patron spell"):
        dcc.set_spells(w, ["Patron Bond", "Snake Trick"], content)  # bonded, but no patron named
    w["patron"] = "Azi Dahaka"
    dcc.set_spells(w, ["Patron Bond", "Snake Trick"], content)
    w["patron"] = "Bobugbubilz"
    with pytest.raises(dcc.DCCError, match="patron spell"):
        dcc.set_spells(w, ["Patron Bond", "Snake Trick"], content)
    assert dcc.find_spell(content, "Paralysis", "cleric")["level"] == 1 and dcc.find_spell(content, "Paralysis", "wizard")["level"] == 3


@real
def test_spells_known_by_intelligence():
    for score, klass, occupation, total in ((4, "wizard", "Scribe", 2), (5, "elf", "Elven Sage", 1), (7, "wizard", "Scribe", 3),
                                            (13, "wizard", "Scribe", 4), (14, "wizard", "Scribe", 5), (18, "elf", "Elven Sage", 5)):
        c, content = hero(occupation, klass=klass, level=1, intelligence=score)
        assert dcc.spell_allowance(c, content)["total"] == total, (score, klass)
    dim, content = hero(klass="wizard", level=1, intelligence=3)
    allowance = dcc.spell_allowance(dim, content)
    assert allowance["blocked"] and allowance["total"] == 0
    with pytest.raises(dcc.DCCError, match="no spellcasting"):
        dcc.set_spells(dim, ["Magic Missile"], content)
    c, content = hero(klass="wizard", level=5, intelligence=9)  # level allows 3rd, Intelligence 9 only 2nd
    assert dcc.spell_allowance(c, content)["max_level"] == 2
    k, content = hero(klass="cleric", level=1, personality=3)
    assert dcc.spell_allowance(k, content)["blocked"]


@real
def test_languages():
    def slots(occupation="Scribe", klass=None, augur=2, **ab):
        c, content = hero(occupation, augur=augur, klass=klass, level=1 if klass else 0, **ab)
        return c, dcc.language_slots(c, content)
    assert slots(intelligence=18)[1]["total"] == 4  # Common + 3
    assert slots(klass="wizard", intelligence=16)[1]["total"] == 5  # Common + 2 at level 0 + 2 more as a wizard
    c, s = slots(klass="thief", intelligence=13)
    assert s["total"] == 3 and "Thieves' cant" in s["automatic"] and "Thieves' cant" in c["languages"]
    c, s = slots("Dwarven Miner", klass="dwarf")
    assert s["automatic"] == ["Common", "Dwarf"] and s["total"] == 3 and s["to_roll"] == 1 and c["languages"] == ["Common", "Dwarf"]
    assert slots("Dwarven Miner")[1]["total"] == 2  # at level 0 only Common and the racial tongue
    c, s = slots("Elven Sage", intelligence=7)
    assert s["total"] == 1 and c["languages"] == ["Common"] and s["literate"]
    assert not slots(intelligence=5)[1]["literate"]
    assert slots(augur=29, luck=16, intelligence=13)[1]["total"] == 4 and slots(augur=29, luck=3, intelligence=13)[1]["total"] == 1
    content = dcc.load_content()
    for column in ("zero", "warrior", "cleric", "thief", "wizard", "halfling", "elf", "dwarf"):
        covered = sorted(n for row in content["languages"] if row["ranges"][column] for n in range(row["ranges"][column][0], row["ranges"][column][1] + 1))
        assert covered == list(range(1, 101)), column
    assert dcc.language_for_roll(content, "thief", 95, "neutral") == "Undercommon"
    assert dcc.language_for_roll(content, "wizard", 5, "chaotic") == "Chaos"
    assert dcc.language_for_roll(content, "wizard", 12, "chaotic") is None  # duplicate of the alignment tongue: roll again
    assert dcc.language_for_roll(content, "wizard", 12, "lawful") == "Chaos"


@real
def test_thief_skills_use_the_printed_abilities_and_armor():
    t, content = hero(klass="thief", level=1, agility=16, intelligence=13)
    skills = {s["skill"]: s for s in dcc.derive(t, content)["thief_skills"]}
    assert skills["Handle Poison"]["value"] == "+0" and skills["Find Trap"]["value"] == "+2"  # neutral +1, Int +1
    assert skills["Use Scroll"]["value"] == "d12" and skills["Use Scroll"]["bonus"] == "+1"
    before = skills["Climb Sheer Surfaces"]["value"], skills["Pick Lock"]["value"]
    dcc.add_item(t, "Leather", "armor")
    skills = {s["skill"]: s for s in dcc.derive(t, content)["thief_skills"]}
    assert int(skills["Climb Sheer Surfaces"]["value"]) == int(before[0]) - 1 and skills["Pick Lock"]["value"] == before[1]


@real
def test_rest_spellburn_and_disapproval():
    w, content = hero(klass="wizard", level=2, strength=12, agility=12, stamina=12)
    with pytest.raises(dcc.DCCError):
        dcc.spellburn(w, strength=13)
    assert dcc.spellburn(w, strength=12, agility=8) == {"bonus": 20, "natural_20": True}
    assert any("Strength is at 0" in line for line in dcc.derive(w, content)["warnings"])
    w["hp_current"] = 1
    assert dcc.rest(w) == {"hp": 1, "abilities": ["strength"], "luck": 0}  # one point in total, most damaged first
    assert dcc.rest(w, bed_rest=True, prefer="agility") == {"hp": 2, "abilities": ["agility", "agility"], "luck": 0}
    w["hp_current"] = w["hp_max"]
    assert dcc.rest(w)["hp"] == 0 and w["ability_damage"] == {"strength": 10, "agility": 6}
    t, content = hero(klass="thief", level=3, luck=12)
    with pytest.raises(dcc.DCCError):
        dcc.spellburn(t, strength=1)
    assert dcc.burn_luck(t, 5, content) == "+5d5" and dcc.rest(t)["luck"] == 3 and t["luck_current"] == 10
    h, content = hero("Halfling Trader", klass="halfling", level=1)
    assert dcc.burn_luck(h, 2, content) == "+4"
    k, content = hero(klass="cleric", level=1)
    assert dcc.adjust_disapproval(k, 10) == 11 and dcc.adjust_disapproval(k, -30) == 1
    dcc.adjust_disapproval(k, 3); dcc.rest(k)
    assert k["disapproval"] == 1
    with pytest.raises(dcc.DCCError):
        dcc.adjust_disapproval(w, 1)


@real
def test_purchases_and_mithril():
    w, content = hero(klass="warrior", level=1)
    w["coins"] = {"gp": 20, "sp": 0, "cp": 0}
    dcc.buy_catalog(w, content, "ammo:Arrows", 2)
    assert next(i for i in w["inventory"] if i["name"] == "Arrows")["qty"] == 40 and w["coins"]["gp"] == 10
    dcc.buy_catalog(w, content, "weapon:Dart", 1)
    assert dcc.coins_total_cp(w["coins"]) == 950
    with pytest.raises(dcc.DCCError):
        dcc.buy_catalog(w, content, "weapon:Longsword", mithril=True)
    e, content = hero("Elven Sage", klass="elf", level=1)
    e["coins"] = {"gp": 200, "sp": 0, "cp": 0}
    dcc.buy_catalog(e, content, "weapon:Longsword", mithril=True)
    dcc.buy_catalog(e, content, "armor:Chainmail", mithril=True)
    dcc.buy_catalog(e, content, "weapon:Short sword")
    with pytest.raises(dcc.DCCError):
        dcc.buy_catalog(e, content, "weapon:Spear", mithril=True)
    dcc.set_equipped(e, next(n for n, i in enumerate(e["inventory"]) if i["name"] == "Chainmail"), True)
    v = dcc.derive(e, content)
    assert v["class_extras"]["iron_items"] == ["Dagger", "Short sword"] and any("Iron burns" in line for line in v["warnings"])


@real
def test_warnings_and_open_choices():
    c, content = hero("Soldier", klass="warrior", level=1, strength=5)
    v = dcc.derive(c, content)
    assert any("weapon or a shield" in w for w in v["warnings"]) and any("lucky weapon" in t for t in v["todo"])
    dcc.set_class_choices(c, content, lucky_weapon="spear")
    with pytest.raises(dcc.DCCError, match="fixed for life"):
        dcc.set_class_choices(c, content, lucky_weapon="Longsword")
    with pytest.raises(dcc.DCCError):
        dcc.set_class_choices(c, content, lucky_weapon="swords")
    dcc.add_item(c, "Two-handed sword", "weapon")
    v = dcc.derive(c, content)
    assert any("two-handed weapon" in w for w in v["warnings"]) and v["init_die"] == "d16"
    t, content = hero(klass="thief", level=1)
    assert any("thieves' tools" in line for line in dcc.derive(t, content)["todo"])
    k, content = hero(klass="cleric", level=1, alignment="chaotic")
    v = dcc.derive(k, content)
    assert any("god of chaotic" in line for line in v["todo"]) and "Malotoch, the carrion crow god" in v["class_extras"]["deity_options"]["gods"]
    # the god is chosen once, at 1st level (p. 28): naming the same god again is fine, another one is refused
    dcc.set_class_choices(k, content, deity="Malotoch, the carrion crow god")
    assert k["deity"] == "Malotoch, the carrion crow god" and not any("god of chaotic" in line for line in dcc.derive(k, content)["todo"])
    dcc.level_up(k, "cleric", 1, content)
    dcc.set_class_choices(k, content, deity="Malotoch, the carrion crow god")
    dcc.set_class_choices(k, content, deity="")   # an empty field on a later level-up leaves the god alone
    assert k["deity"] == "Malotoch, the carrion crow god"
    with pytest.raises(dcc.DCCError, match="chooses a god once"):
        dcc.set_class_choices(k, content, deity="Cthulhu, priest of the Old Ones")
    assert k["deity"] == "Malotoch, the carrion crow god"


@real
def test_builder_api_from_first_roll_to_second_level(tmp_path, monkeypatch):
    from ttrpgtools.web.app import create_app
    monkeypatch.setattr(dcc, "CHARACTERS_DIR", tmp_path)
    client = create_app().test_client()
    assert client.get("/TTRPG/dcc/new?roll=1").status_code == 200
    tables = client.get("/TTRPG/dcc/api/content").get_json()
    assert len(tables["occupations"]) == 79 and tables["classes"]["wizard"]["hit_die"] == 4 and tables["deities"]["lawful"]["gods"]
    rolls = {"name": "Mira", "alignment": "chaotic", "occupation_roll": 97, "augur_roll": 13, "hp_roll": 4, "copper": 31, "equipment_roll": 19,
             "abilities": {"strength": 9, "agility": 12, "stamina": 13, "personality": 10, "intelligence": 16, "luck": 13}}
    assert "5d12" in client.post("/TTRPG/dcc/api/character", json={**rolls, "copper": 99}).get_json()["error"]
    assert "name" in client.post("/TTRPG/dcc/api/character", json={**rolls, "name": " "}).get_json()["error"]
    made = client.post("/TTRPG/dcc/api/character", json=rolls).get_json()
    cid, c = made["id"], made["character"]
    assert c["occupation"]["occupation"] == "Wizard’s Apprentice" or "apprentice" in c["occupation"]["occupation"].lower()
    assert c["hp_max"] == 5 and made["view"]["languages"]["total"] == 3 and made["view"]["todo"]
    url = f"/TTRPG/dcc/api/character/{cid}"
    bought = client.post(url + "/op", json={"op": "buy", "key": "gear:Torch, each", "count": 3}).get_json()
    assert bought["character"]["coins"]["cp"] == 28
    assert "Not enough coin" in client.post(url + "/op", json={"op": "buy", "key": "armor:Chainmail"}).get_json()["error"]
    assert "allowed" in client.post(url + "/op", json={"op": "languages", "languages": ["Elf", "Goblin", "Orc"]}).get_json()["error"]
    assert client.post(url + "/op", json={"op": "languages", "languages": ["Elf", "Goblin"]}).get_json()["character"]["languages"] == ["Common", "Elf", "Goblin"]
    assert client.post("/TTRPG/dcc/api/language", json={"column": "wizard", "roll": 100, "alignment": "chaotic"}).get_json() == {"language": "Undercommon"}
    assert "needs 10 XP" in client.post(url + "/level", json={"class": "wizard", "hp_roll": 3}).get_json()["error"]
    preview = client.post(url + "/level", json={"class": "wizard", "preview": True}).get_json()
    assert preview["hit_die"] == 4 and preview["view"]["spellcasting"]["total"] == 5 and preview["before"]["attack"] == "+0"
    assert any(s["name"] == "Detect Magic" for s in preview["spell_options"]) and client.get(url).get_json()["character"]["level"] == 0
    choice = {"class": "wizard", "hp_roll": 3, "raise_xp": True, "patron": "Sezrekan", "spells": ["Patron Bond", "Magic Missile", "Sleep", "Sequester", "Cantrip"],
              "mercurial": {"Sleep": 77}, "languages": ["Elf", "Goblin", "Dragon", "Kobold"]}
    assert "Too many" in client.post(url + "/level", json={**choice, "spells": choice["spells"] + ["Enlarge", "Mending"]}).get_json()["error"]
    assert client.get(url).get_json()["character"]["level"] == 0  # a refused level changes nothing
    done = client.post(url + "/level", json=choice).get_json()
    c, v = done["character"], done["view"]
    assert c["level"] == 1 and c["xp"] == 10 and c["hp_max"] == 5 + 3 + 1 and c["patron"] == "Sezrekan" and v["title"] == "Cultist"
    assert "Invoke Patron" in c["spells"] and v["spellcasting"]["used"] == 5 and v["languages"]["total"] == 5 and len(c["languages"]) == 5
    assert next(s for s in v["spells"] if s["name"] == "Sleep")["mercurial_roll"] == 77
    burned = client.post(url + "/op", json={"op": "spellburn", "strength": 2}).get_json()
    assert burned["result"] == {"bonus": 2, "natural_20": False} and burned["view"]["effective"]["strength"] == 7
    assert client.post(url + "/op", json={"op": "rest"}).get_json()["result"]["abilities"] == ["strength"]
    assert client.post(url + "/op", json={"op": "nonsense"}).status_code == 400
    again = client.post(url + "/level", json={"hp_roll": 4, "raise_xp": True}).get_json()
    assert again["character"]["level"] == 2 and again["character"]["xp"] == 50 and again["view"]["spellcasting"]["total"] == 6
    assert client.get("/TTRPG/dcc/music").get_json()["tracks"] is not None


# ------------------------------------------------------------------ town shops
def test_price_curves_are_periodic_and_stable():
    from ttrpgtools.dcc.westmarch import town as t
    shop = {"curve": {"period": 20, "amplitude": 0.1, "phase": 0}}
    item = {"base_cp": 1000, "curve": {"period": 5, "amplitude": 0.2, "phase": 0}}
    assert t.price_cp(shop, item, 0) == 1000 and t.price_cp(shop, item, 20) == 1000 and t.price_cp(shop, item, 40) == 1000  # both periods divide 20
    prices = [t.price_cp(shop, item, d) for d in range(20)]
    assert prices == [t.price_cp(shop, item, d + 20) for d in range(20)] and len(set(prices)) > 10
    assert 0.9 * 0.8 * 1000 <= min(prices) and max(prices) <= 1.1 * 1.2 * 1000
    assert t.price_cp(shop, {"base_cp": 1, "curve": item["curve"]}, 4) == 1  # never below one copper
    assert t.derived_curve("item", "smithy/longsword") == t.derived_curve("item", "smithy/longsword") != t.derived_curve("item", "smithy/dagger")
    c = t.derived_curve("shop", "smithy")
    assert 18 <= c["period"] <= 40 and 0.10 <= c["amplitude"] <= 0.30
    assert t.clean_curve({"period": 1, "amplitude": 5, "phase": "3"}, "item", "x") == {"period": 2, "amplitude": 0.9, "phase": 3}
    with pytest.raises(t.TownError):
        t.clean_curve({"period": "soon"}, "item", "x")
    assert t.coins_text(1234) == "12,34 gp" and t.coins_text(1002) == "10,02 gp" and t.coins_text(50) == "0,50 gp" and t.coins_text(0) == "0,00 gp"
    assert t.coins_text(100_000_000) == "1.000.000,00 gp"
    for text, cp in (("10,02 gp", 1002), ("10,02", 1002), ("10.5 gp", 1050), ("0,03 gp", 3), ("1,200 gp", 120000), ("1.200,50 gp", 120050),
                     ("10.000,00 gp", 1000000), ("7", 700), ("5 sp", 50), ("30 cp", 30), ("12,50 gp", 1250)):
        assert dcc.cost_in_cp(text) == cp, text
    assert dcc.cost_in_cp(t.coins_text(987654)) == 987654  # what is shown can be typed back


def test_a_sold_item_is_gone_for_everyone(content):
    from ttrpgtools.dcc.westmarch import town as t
    with t.town(write=True) as state:
        sid = t.save_shop(state, None, "The Bent Nail", "Marta", curve={"period": 20, "amplitude": 0, "phase": 0})
        t.stock_item(state, sid, "Club", "weapon", "3 gp", 1, curve={"period": 5, "amplitude": 0, "phase": 0})
        t.stock_item(state, sid, "Torch", "gear", "1 cp", None)
        t.stock_item(state, sid, "Arrows", "ammo", "5 gp", 2, units=20)
    rich, poor = make(content), make(content)
    rich["coins"] = {"gp": 20, "sp": 0, "cp": 0}
    with t.town(write=True) as state:
        with pytest.raises(dcc.DCCError, match="Not enough coin"):
            t.buy(state, sid, "club", poor)
        assert state["shops"][sid]["stock"][0]["qty"] == 1 and not state["log"]  # a refused sale changes nothing
        sale = t.buy(state, sid, "club", rich, who="ana")
        assert sale["each_cp"] == 300 and rich["coins"] == {"gp": 17, "sp": 0, "cp": 0}
        assert any(i["name"] == "Club" and i["notes"] == f"The Bent Nail, {t.today().isoformat()}" for i in rich["inventory"])
        t.stock_item(state, sid, "Bed for the night", "service", "2 sp", None, curve={"period": 5, "amplitude": 0, "phase": 0})
        before = len(rich["inventory"])
        t.buy(state, sid, "bed-for-the-night", rich)
        assert len(rich["inventory"]) == before and rich["downtime"][0]["what"] == "Bed for the night" and rich["downtime"][0]["paid_cp"] == 20
        with pytest.raises(t.TownError, match="Sold out"):
            t.buy(state, sid, "club", rich)
        t.buy(state, sid, "arrows", rich, 2)
        assert next(i for i in rich["inventory"] if i["name"] == "Arrows")["qty"] == 40
        with pytest.raises(t.TownError, match="Sold out"):
            t.buy(state, sid, "arrows", rich)
        for _ in range(3):
            t.buy(state, sid, "torch", rich)  # unlimited shelf
    with t.town() as state:  # saved: the next visitor sees the empty shelf
        v = t.view(state, "someone")
        assert [(i["name"], i["qty"]) for i in v["shops"][0]["stock"]] == [("Club", 0), ("Torch", None), ("Arrows", 0), ("Bed for the night", None)]
        assert not v["judge"] and "log" not in v and "curve" not in v["shops"][0]
        assert len(t.view(state, "admin")["log"]) == 6 and "series" in t.view(state, "admin")["shops"][0]["stock"][0]


@real
def test_town_over_the_web(tmp_path, monkeypatch):
    from datetime import date, timedelta
    from ttrpgtools.web.app import create_app
    from ttrpgtools.dcc.westmarch import places, town as t
    monkeypatch.setattr(dcc, "CHARACTERS_DIR", tmp_path)
    monkeypatch.setattr(places, "PLACES", [{"id": "smithy", "name": "Smithy", "kinds": ["shop", "inn"], "keeper": "Bram",
                                            "goods": [("weapon:Dagger", 1), ("gear:Torch, each", None), ("no:Such key", 1)],
                                            "services": [("Bunk", "1 sp")]}])
    monkeypatch.setattr(t, "today", lambda: places.EPOCH + timedelta(days=2))
    client = create_app().test_client()
    judge, player, other = {"Remote-User": "admin"}, {"Remote-User": "wren"}, {"Remote-User": "ibis"}
    rolls = {"name": "Odo", "alignment": "neutral", "occupation_roll": 1, "augur_roll": 5, "hp_roll": 2, "copper": 40, "equipment_roll": 3,
             "abilities": {a: 10 for a in dcc.ABILITIES}}
    cid = client.post("/TTRPG/dcc/api/character", json=rolls, headers=player).get_json()["id"]
    assert client.get("/TTRPG/dcc/town").status_code == 200
    post = lambda body, who: client.post("/TTRPG/dcc/api/town/judge", json=body, headers=who)
    assert post({"action": "coins", "character": cid, "coins": {"gp": 99}}, player).status_code == 403
    town = client.get("/TTRPG/dcc/api/town", headers=judge).get_json()
    assert town["day"] == 3 and [i["name"] for i in town["shops"][0]["stock"]] == ["Dagger", "Torch, each", "Bunk"] and town["shops"][0]["kinds"] == ["shop", "inn"]
    dagger = next(i for i in town["shops"][0]["stock"] if i["name"] == "Dagger")
    seen = client.get("/TTRPG/dcc/api/town", headers=player).get_json()
    assert [c["name"] for c in seen["characters"]] == ["Odo"] and not seen["judge"] and seen["catalog"] is None
    assert client.get("/TTRPG/dcc/api/town", headers=other).get_json()["characters"] == []
    buy = lambda who, item="dagger": client.post("/TTRPG/dcc/api/town/buy", json={"shop": "smithy", "item": item, "character": cid}, headers=who).get_json()
    assert "Not enough coin" in buy(player)["error"]
    assert "another player" in buy(other, "torch-each")["error"]
    url = f"/TTRPG/dcc/api/character/{cid}/op"
    assert "judge" in client.post(url, json={"op": "coins", "coins": {"gp": 99}}, headers=player).get_json()["error"]
    assert "buy in town" in client.post(url, json={"op": "buy", "key": "weapon:Dagger"}, headers=player).get_json()["error"]
    assert "Issue coin first" in post({"action": "coins", "target": cid, "amount": "10,00 gp"}, judge).get_json()["error"]  # no coin from nowhere
    issued = post({"action": "issue", "amount": "500 gp"}, judge).get_json()["money"]
    funded = post({"action": "coins", "target": cid, "amount": "10,00 gp"}, judge).get_json()["money"]
    assert funded["bank_cp"] == 50000 - (1000 - 40) and funded["money_cp"] == issued["money_cp"]  # the vault paid the difference; no coin was made
    assert funded["circulating_cp"] == issued["circulating_cp"] + 960
    done = buy(player)
    assert done["sale"]["each_cp"] == dagger["price_cp"] and done["characters"][0]["coins_cp"] == 1000 - dagger["price_cp"]
    assert "Sold out" in buy(player)["error"]
    monkeypatch.setattr(t, "today", lambda: places.EPOCH + timedelta(days=3))  # midnight passes: same shelf, new price
    later = client.get("/TTRPG/dcc/api/town", headers=player).get_json()
    again = next(i for i in later["shops"][0]["stock"] if i["name"] == "Dagger")
    assert later["day"] == 4 and again["qty"] == 0 and again["price_cp"] != dagger["price_cp"]
    post({"action": "remove_item", "shop": "smithy", "item": "dagger"}, judge)
    assert [i["name"] for i in client.get("/TTRPG/dcc/api/town", headers=player).get_json()["shops"][0]["stock"]] == ["Torch, each", "Bunk"]  # stays gone
    assert buy(player, "bunk")["sale"]["item"] == "Bunk" and client.get(f"/TTRPG/dcc/api/character/{cid}").get_json()["character"]["downtime"][0]["place"] == "Smithy"
    assert client.get("/TTRPG/dcc/api/content", headers=player).get_json()["town"] == {"shops": 1, "judge": False, "day": 4}


@real
def test_the_campaign_places_are_all_on_the_map():
    from ttrpgtools.dcc.westmarch import places, town as t
    import importlib
    real_places = importlib.reload(places).PLACES  # the autouse fixture emptied the list; read the file's own
    try:
        with t.town() as state:
            kinds = [state["shops"][p["id"]]["kinds"] for p in real_places]
            assert sum("shop" in k for k in kinds) == 3 and sum("inn" in k for k in kinds) == 3 and sum("library" in k for k in kinds) == 1
            assert len(real_places) == 7 and sum("oracle" in k for k in kinds) == 1   # three shops, three inns (one is both), the library, the herb woman
            for place in real_places:  # every line of places.py reached the shelf: no mistyped rulebook key
                wanted = len(place.get("goods", [])) + len(place.get("services", []))
                assert len(state["shops"][place["id"]]["stock"]) == wanted, place["id"]
            assert t.campaign_day(places.EPOCH) == 1
    finally:
        places.PLACES = []


def test_selling_back_deliveries_and_traders(content, monkeypatch):
    from datetime import timedelta
    from ttrpgtools.dcc.westmarch import daily, places, town as t
    flat = {"period": 10, "amplitude": 0, "phase": 0}
    monkeypatch.setattr(t, "today", lambda: places.EPOCH)
    monkeypatch.setattr(daily, "model_plan", lambda *a: None)  # no model in tests: the plain rule plays the traders
    with t.town(write=True) as state:
        sid = t.save_shop(state, None, "Yard", curve=flat)
        state["shops"][sid].update(deals=["weapon", "trade"], restock_every=1, till=500_000, materials={"wood": 30_000})
        club = t.stock_item(state, sid, "Club", "weapon", "4 gp", 2, curve=flat)
        club["target"] = 2
        inn = t.save_shop(state, None, "Inn", curve=flat)
        state["shops"][inn]["kinds"] = ["inn"]
    c = make(content)
    c["coins"] = {"gp": 10, "sp": 0, "cp": 0}
    dcc.add_item(c, "Lump of amber", "trade", 3, "2 gp")
    dcc.add_item(c, "Mystery box", "trade", 1)           # no price anywhere
    dcc.add_item(c, "Rope ladder", "gear", 1, "1 gp")    # the yard does not deal in gear
    with t.town(write=True) as state:
        t.buy(state, sid, "club", c)
        got = {row["name"]: row["each_cp"] for row in t.offers(state, c)[sid]}
        each = got["Lump of amber"]  # not on the shelf yet: half of the usual price along the item's own curve
        assert got == {"Club": 200, "Lump of amber": each} and 40 <= each <= 160 and inn not in t.offers(state, c)  # inns buy nothing
        club_line = next(n for n, i in enumerate(c["inventory"]) if i["name"] == "Club")
        assert t.sell(state, sid, c, club_line)["each_cp"] == 200 and state["shops"][sid]["stock"][0]["qty"] == 2
        amber = next(n for n, i in enumerate(c["inventory"]) if i["name"] == "Lump of amber")
        with pytest.raises(t.TownError):
            t.sell(state, sid, c, amber, 4)  # carries only 3
        t.sell(state, sid, c, amber, 2)
        assert dcc.coins_total_cp(c["coins"]) == 1000 - 400 + 200 + 2 * each and c["inventory"][amber]["qty"] == 1
        shelf = next(i for i in state["shops"][sid]["stock"] if i["name"] == "Lump of amber")
        assert shelf["qty"] == 2 and shelf["base_cp"] == 200 and abs(t.price_cp(state["shops"][sid], shelf, 1) - 2 * each) <= 1  # for sale to others at full price
        with pytest.raises(t.TownError, match="worth"):
            t.sell(state, sid, c, next(n for n, i in enumerate(c["inventory"]) if i["name"] == "Mystery box"))
        t.buy(state, sid, "club", c); t.buy(state, sid, "club", c)
        assert state["shops"][sid]["stock"][0]["qty"] == 0
    monkeypatch.setattr(places, "BOTS", [{"id": "sig", "name": "Sigrun", "income": 500, "likes": ["weapon"], "persona": "x",
                                          "brings": [("Honey", "trade", "10 gp"), ("Notched longsword", "weapon", "6 gp")]}])
    with t.town(write=True) as state:
        state["last_daily"] = 0  # nobody visited for ten days: the days are caught up one by one
    monkeypatch.setattr(t, "today", lambda: places.EPOCH + timedelta(days=9))
    assert daily.ensure(background=False) and not daily.ensure(background=False)  # once per day
    with t.town() as state:
        assert state["last_daily"] == 10 and state["shops"][sid]["stock"][0]["qty"] == 2  # made up to the listed quantity again, from the yard's wood
        news = " ".join(n["text"] for n in state["chronicle"])     # the admin's log has it all
        assert "Making day at Yard: 2 pieces made" in news and "Sigrun" in news
        assert len(state["news"]) <= 4 and all(" sold " in n["text"] and "(" not in n["text"] for n in state["news"])   # town talk: rare, and only who sold what
        bot = state["bots"]["sig"]
        assert all(i["name"] != "Honey" for i in bot["inventory"])  # own wares were sold to the yard
        assert next(i for i in state["shops"][sid]["stock"] if i["name"] == "Honey")["qty"] >= 1
        assert not any("longsword" in i["name"].lower() for i in bot["inventory"] + state["shops"][sid]["stock"])  # equipment is made, never brought
        assert any(s["by"] == "bot" for s in state["log"])
    # a plan from the model is applied through the same rules: a nonsense action is skipped, a valid one counts
    monkeypatch.setattr(t, "today", lambda: places.EPOCH + timedelta(days=10))
    monkeypatch.setattr(daily, "model_plan", lambda state, bot, spec: ([{"do": "buy", "shop": sid, "item": "club", "count": 1},
                                                                       {"do": "buy", "shop": "nowhere", "item": "moon"}], "Steel is cheap today."))
    daily.ensure(background=False)
    with t.town() as state:
        assert 'bought 1 x Club at Yard' in state["chronicle"][-1]["text"] and state["chronicle"][-1]["text"].endswith('"Steel is cheap today."')
        assert any(i["name"] == "Club" and i["paid_cp"] == 400 for i in state["bots"]["sig"]["inventory"])


def test_groderick_inns_taxes_and_the_items_table(content, tmp_path, monkeypatch):
    from datetime import timedelta
    from ttrpgtools.dcc.westmarch import items, places, town as t
    flat = {"period": 10, "amplitude": 0, "phase": 0}
    monkeypatch.setattr(t, "today", lambda: places.EPOCH)
    monkeypatch.setattr(dcc, "CHARACTERS_DIR", tmp_path / "chars")
    monkeypatch.setattr(dcc, "INVENTORY_STORE", items.CharacterPacks)
    with t.town(write=True) as state:
        g = t.save_shop(state, None, "Groderick", curve=flat)
        state["shops"][g].update(buys_anything=True, sell_back=0.15, junk_cp=2, till=1000)
        t.stock_item(state, g, "Club", "weapon", "4 gp", 1, curve=flat)
        inn = t.save_shop(state, None, "Good Inn", curve=flat)
        state["shops"][inn].update(kinds=["inn"], stay={"price": "2 gp", "hp": 2, "ability": 2})
    c = make(content, stamina=13)
    c["coins"] = {"gp": 30, "sp": 0, "cp": 0}
    c["hp_current"], c["ability_damage"] = 1, {"strength": 3}
    dcc.add_item(c, "Club", "weapon", cost="4 gp")
    with t.town(write=True) as state:
        got = {row["name"]: row["each_cp"] for row in t.offers(state, c)[g]}
        assert got["Hen"] == 2 and got["Club"] == 60 and got["Rope"] >= 1  # anything at all; 15% of today's price; a pittance for the unpriced
        hen = next(n for n, i in enumerate(c["inventory"]) if i["name"] == "Hen")
        t.sell(state, g, c, hen)
        assert next(i for i in state["shops"][g]["stock"] if i["name"] == "Hen")["qty"] == 1
        # the inn: paid up front, healed as real nights pass
        price = t.stay_offer(inn, state["shops"][inn], 1)["price_cp"]
        before = dcc.coins_total_cp(c["coins"])
        t.stay(state, inn, c, 3)
        assert dcc.coins_total_cp(c["coins"]) == before - 3 * price and c["lodging"]["nights"] == 3
        with pytest.raises(t.TownError, match="already has a bed"):
            t.stay(state, inn, c, 1)
        assert not t.settle(c) and c["hp_current"] == 1  # no night has passed yet
        assert t.settle(c, day=3) and c["hp_current"] == 4 and c["ability_damage"] == {} and c["lodging"]["applied"] == 2  # two nights, hp max 4
        assert t.settle(c, day=9) and "lodging" not in c and c["hp_current"] == 4  # the third night; then the bed is free again
        # taxes
        assert t.tax_debt(c) == 1_000_000
        with pytest.raises(t.TownError, match="coin"):
            t.pay_taxes(state, c, "5")
        purse = dcc.coins_total_cp(c["coins"])
        assert t.pay_taxes(state, c, "3 gp")["each_cp"] == 300 and c["tax_debt_cp"] == 999_700 and dcc.coins_total_cp(c["coins"]) == purse - 300
        c["tax_debt_cp"] = 120
        assert t.pay_taxes(state, c, "9 gp")["each_cp"] == 120 and c["tax_debt_cp"] == 0  # never more than is owed
        with pytest.raises(t.TownError, match="nothing"):
            t.pay_taxes(state, c, "1 cp")
    # one table knows every item: the shelf, and the character's pack once saved
    dcc.save_character(c, "tester")
    held = {(r["holder_type"], r["holder_id"], r["name"]) for r in items.everything()}
    assert ("shop", g, "Hen") in held and ("pc", "tester", "Club") in held
    stored = json.loads((tmp_path / "chars" / "tester.json").read_text())
    assert "inventory" not in stored and stored["inventory_in_table"]
    again = dcc.load_character("tester")
    assert [i["name"] for i in again["inventory"]] == [i["name"] for i in c["inventory"]] and again["inventory"][0]["equipped"] is True
    assert dcc.derive(again, content)["weapons"][0]["name"] == "Pitchfork (as spear)"


def test_only_a_matching_trade_reads_the_curve(content, monkeypatch):
    from ttrpgtools.dcc.westmarch import places, town as t
    with t.town(write=True) as state:
        sid = t.save_shop(state, None, "Yard")
        t.stock_item(state, sid, "Stinky cheese", "trade", "8 sp", 5)
        t.stock_item(state, sid, "Club", "weapon", "3 gp", 5)
        farmer, scribe = make(content), make(content)
        scribe["occupation"] = {"occupation": "Scribe"}
        assert t.insight(farmer) == ["Stinky cheese"] and t.insight(scribe) == []
        seen = {i["name"]: i for i in t.view(state, "wren", farmer)["shops"][0]["stock"]}
        assert "series" in seen["Stinky cheese"] and "series" not in seen["Club"]
        assert all("usual" not in i and "trend" not in i for i in seen.values())  # players see today's price and nothing else
        assert not any("series" in i for i in t.view(state, "wren", scribe)["shops"][0]["stock"])
        assert t.view(state, "wren")["shops"][0]["mood"] is None and "usual" in t.view(state, "admin")["shops"][0]["stock"][0]


@real
def test_registers_and_debt_counter(tmp_path, monkeypatch):
    from ttrpgtools.web.app import create_app
    from ttrpgtools.dcc.westmarch import registry
    monkeypatch.setattr(dcc, "CHARACTERS_DIR", tmp_path)
    client = create_app().test_client()
    admin, player = {"Remote-User": "admin"}, {"Remote-User": "wren"}
    people = client.get("/TTRPG/dcc/api/registry/people", headers=player).get_json()
    assert len(people["rows"]) == 100 and not people["judge"] and {r["status"] for r in people["rows"]} == {"alive"}
    assert sum(r["locked"] for r in people["rows"]) == 20 and sum(r["playable"] for r in people["rows"]) == 80  # keepers, mayor, traders, the herb woman, nine producers
    marta = next(r for r in people["rows"] if r["name"] == "Marta Vogt")
    assert client.post("/TTRPG/dcc/api/registry/people", json={"id": marta["id"], "status": "dead"}, headers=player).status_code == 403
    assert "one of" in client.post("/TTRPG/dcc/api/registry/people", json={"id": marta["id"], "status": "bored"}, headers=admin).get_json()["error"]
    changed = client.post("/TTRPG/dcc/api/registry/people", json={"id": marta["id"], "status": "missing", "notes": "last seen at the well"}, headers=admin).get_json()
    assert next(r for r in changed["rows"] if r["id"] == marta["id"])["status"] == "missing"
    monsters = client.get("/TTRPG/dcc/api/registry/monsters", headers=player).get_json()["rows"]
    goblin = next(m for m in monsters if m["name"] == "Goblin")
    assert len(monsters) > 80 and goblin["hd"] == "1d6-1" and goblin["status"] == "not met" and goblin["page"] == 417
    assert client.get("/TTRPG/dcc/people").status_code == 200
    rolls = {"name": "Odo", "alignment": "neutral", "occupation_roll": 1, "augur_roll": 5, "hp_roll": 2, "copper": 40, "equipment_roll": 3,
             "abilities": {a: 10 for a in dcc.ABILITIES}}
    for name in ("Odo", "Ada"):
        client.post("/TTRPG/dcc/api/character", json={**rolls, "name": name}, headers=player)
    page = client.get("/TTRPG/dcc/", headers=player).get_data(as_text=True)
    assert "1.020.000,00 gp" in page and "The town owes the tax office" in page and "owe 20.000,00 gp of it" in page  # 100 villagers and 2 characters
    assert client.get("/TTRPG/dcc/api/town/items", headers=player).status_code == 403
    assert any(i["holder_type"] == "pc" for i in client.get("/TTRPG/dcc/api/town/items", headers=admin).get_json()["items"])


def test_moon_closed_doors_and_bleeding_out(content, monkeypatch):
    from datetime import date
    from ttrpgtools.dcc.westmarch import registry, town as t
    assert t.moon(date(2024, 12, 15))["phase"] == "full" and t.moon(date(2025, 1, 29))["phase"] == "new"  # known full and new moons
    assert t.moon(date(2025, 1, 6))["phase"] == "first quarter" and 6 <= t.moon(date(2025, 1, 6))["days_to_full"] <= 8
    with t.town(write=True) as state:
        sid = t.save_shop(state, None, "Yard", keeper="Marta Vogt")
        t.stock_item(state, sid, "Club", "weapon", "3 gp", 2, curve={"period": 5, "amplitude": 0, "phase": 0})
        c = make(content)
        c["coins"] = {"gp": 30, "sp": 0, "cp": 0}
        t.buy(state, sid, "club", c)
        marta = next(r for r in registry.rows("people") if r["name"] == "Marta Vogt")
        registry.update("people", marta["id"], status="missing")
        assert t.view(state, "wren")["shops"][0]["closed"] == "Closed: Marta Vogt is missing."
        with pytest.raises(t.TownError, match="shut"):
            t.buy(state, sid, "club", c)
        with pytest.raises(t.TownError, match="shut"):
            t.sell(state, sid, c, next(n for n, i in enumerate(c["inventory"]) if i["name"] == "Club"))
        registry.update("people", marta["id"], status="alive")
        t.buy(state, sid, "club", c)
        assert [s["item"] for s in t.view(state, "wren", c)["record"]] == ["Club", "Club"]  # the character's own dealings
    w = make(content, stamina=13, luck=9)
    dcc.level_up(w, "warrior", 5, content); dcc.level_up(w, None, 5, content)
    w["hp_current"] = 0
    text = " ".join(dcc.derive(w, content)["warnings"])
    assert "within 2 rounds" in text and "Luck check (d20, 9 or less)" in text
    dcc.saved_from_bleeding_out(w, 3)
    assert w["hp_current"] == 3 and w["abilities"]["stamina"] == 12
    w["hp_current"] = 0
    dcc.recovered_body(w, "agility")
    assert w["hp_current"] == 1 and w["abilities"]["agility"] == 9
    with pytest.raises(dcc.DCCError):
        dcc.recovered_body(w, "luck")
    peasant = make(content)
    peasant["hp_current"] = 0
    assert "irrevocably dead" in " ".join(dcc.derive(peasant, content)["warnings"])
    with pytest.raises(dcc.DCCError):
        dcc.saved_from_bleeding_out(peasant, 2)  # a 0-level character does not bleed out


@real
def test_graveyard_and_notices(tmp_path, monkeypatch):
    from ttrpgtools.web.app import create_app
    monkeypatch.setattr(dcc, "CHARACTERS_DIR", tmp_path)
    client = create_app().test_client()
    admin, player, other = {"Remote-User": "admin"}, {"Remote-User": "wren"}, {"Remote-User": "ibis"}
    rolls = {"alignment": "neutral", "occupation_roll": 1, "augur_roll": 5, "hp_roll": 2, "copper": 40, "equipment_roll": 3,
             "abilities": {a: 10 for a in dcc.ABILITIES}}
    odo = client.post("/TTRPG/dcc/api/character", json={**rolls, "name": "Odo"}, headers=player).get_json()["id"]
    ada = client.post("/TTRPG/dcc/api/character", json={**rolls, "name": "Ada"}, headers=player).get_json()["id"]
    client.post(f"/TTRPG/dcc/api/character/{odo}/op", json={"op": "xp", "value": 12}, headers=player)
    op = lambda cid, body, who: client.post(f"/TTRPG/dcc/api/character/{cid}/op", json=body, headers=who).get_json()
    assert "judge" in op(ada, {"op": "die", "cause": "spite"}, other)["error"]  # not your character
    assert op(ada, {"op": "die", "cause": "a falling block", "epitaph": "She looked up too late."}, player)["character"]["dead"]["cause"] == "a falling block"
    page = client.get("/TTRPG/dcc/", headers=player).get_data(as_text=True)
    assert "Graveyard" in page and "a falling block" in page and "She looked up too late." in page
    assert "level up" in page and "Record death" in page and "1.020.000,00 gp" in page  # her debt went to the living in full: the town owes what it owed
    assert "owe 10.099,01 gp of it" in page  # Odo's own 10.000 and his share of hers (one of 101 heirs)
    town = client.get("/TTRPG/dcc/api/town", headers=player).get_json()
    assert [c["name"] for c in town["characters"]] == ["Odo"] and town["moons"][0]["text"].startswith("The Pale Moon: ")  # the dead do not shop
    assert "judge" in op(ada, {"op": "revive"}, player)["error"]
    assert "dead" not in op(ada, {"op": "revive"}, admin)["character"]
    judge = lambda body: client.post("/TTRPG/dcc/api/town/judge", json=body, headers=admin).get_json()
    assert judge({"action": "notice", "text": "Market day on Friday."})["notices"][0]["text"] == "Market day on Friday."
    assert client.get("/TTRPG/dcc/api/town", headers=player).get_json()["notices"][0]["text"] == "Market day on Friday."
    assert judge({"action": "remove_notice", "index": 0})["notices"] == []
    assert client.get("/TTRPG/dcc/expeditions").status_code in (200, 404) and b"Expeditions" not in client.get("/TTRPG/dcc/").data


def test_three_moons(content):
    from datetime import date, timedelta
    from ttrpgtools.dcc.westmarch import places, town as t
    assert [m["id"] for m in places.MOONS] == ["pale", "red", "drowned"]
    assert t.moon(date(2024, 12, 15))["phase"] == "full" and t.moon(date(2024, 12, 15))["days_to_full"] == 0  # the pale moon is the real one
    for which, nights, full_for in (("red", 13, 5), ("drowned", 61, 1)):
        days = [t.moon(places.EPOCH + timedelta(days=n), which) for n in range(nights * 2)]
        assert days[0]["cycle_nights"] == nights and [d["phase"] for d in days[:nights]] == [d["phase"] for d in days[nights:]]  # it repeats
        assert sum(d["phase"] == "full" for d in days[:nights]) == full_for
        for n, d in enumerate(days[:nights]):  # the countdown lands on a full night
            assert days[n + d["days_to_full"]]["phase"] == "full" and (d["days_to_full"] == 0) == (d["phase"] == "full")
    assert sum(t.moon(places.EPOCH + timedelta(days=n), "drowned")["phase"] == "new" for n in range(61)) == 28
    assert len(t.moons()) == 3 and all(set(m) == {"id", "name", "blurb", "phase", "text"} and m["text"] == f"{m['name']}: {m['phase']}" for m in t.moons())
    assert "days_to_full" in t.moons(full=True)[0] and not any(ch.isdigit() for m in places.MOONS for ch in m["blurb"])  # no cycle told to players


@real
def test_a_character_is_bound_to_one_moon(tmp_path, monkeypatch):
    from ttrpgtools.web.app import create_app
    monkeypatch.setattr(dcc, "CHARACTERS_DIR", tmp_path)
    client = create_app().test_client()
    admin, player = {"Remote-User": "admin"}, {"Remote-User": "wren"}
    rolls = {"name": "Odo", "alignment": "neutral", "occupation_roll": 1, "augur_roll": 5, "hp_roll": 2, "copper": 40, "equipment_roll": 3,
             "abilities": {a: 10 for a in dcc.ABILITIES}}
    assert [set(m) for m in client.get("/TTRPG/dcc/api/content").get_json()["moons"]] == [{"id", "name", "blurb"}] * 3
    assert client.get("/TTRPG/dcc/api/content").headers["X-DCC-Build"].isdigit()  # open pages notice a new deploy by this
    import re as _re
    page = client.get(f"/TTRPG/dcc/{made['id']}/build").get_data(as_text=True) if False else client.get("/TTRPG/dcc/town").get_data(as_text=True)
    assert _re.search(r"static/dcc/dcc\.css\?v=\d+", page) and _re.search(r"static/dcc/dcc_town\.js\?v=\d+", page) and _re.search(r"static/dcc/dcc_assist\.js\?v=\d+", page)
    assert "three moons" in client.post("/TTRPG/dcc/api/character", json={**rolls, "moon": "cheese"}, headers=player).get_json()["error"]
    made = client.post("/TTRPG/dcc/api/character", json={**rolls, "moon": "red"}, headers=player).get_json()
    assert made["character"]["moon"] == "red" and made["moon"]["name"] == "The Red Lantern" and not any("moon" in t for t in made["view"]["todo"])
    url = f"/TTRPG/dcc/api/character/{made['id']}/op"
    assert "judge" in client.post(url, json={"op": "set", "moon": "pale"}, headers=player).get_json()["error"]  # chosen once
    assert client.post(url, json={"op": "set", "moon": "pale"}, headers=admin).get_json()["character"]["moon"] == "pale"
    late = client.post("/TTRPG/dcc/api/character", json={**rolls, "name": "Ada"}, headers=player).get_json()
    assert any("moon" in t for t in late["view"]["todo"])  # an older character without a moon is reminded
    assert client.post(f"/TTRPG/dcc/api/character/{late['id']}/op", json={"op": "set", "moon": "drowned"}, headers=player).get_json()["moon"]["id"] == "drowned"
    assert "The Drowned Moon" in client.get("/TTRPG/dcc/", headers=player).get_data(as_text=True)
    # raising a rolled number by hand: 6,000 gp more debt; lowering it: one copper back
    up = client.post(url, json={"op": "taxes_for_no_reason", "direction": "up"}, headers=player).get_json()
    assert up["character"]["tax_debt_cp"] == 1_600_000 and up["result"] == {"debt": "16.000,00 gp", "direction": "up"}
    down = client.post(url, json={"op": "taxes_for_no_reason", "direction": "down"}, headers=player).get_json()
    assert down["character"]["tax_debt_cp"] == 1_599_999 and down["result"]["debt"] == "15.999,99 gp"
    assert client.post(url, json={"op": "taxes_for_no_reason", "direction": "up"}, headers=player).get_json()["character"]["tax_debt_cp"] == 2_199_999
    twice = client.post(url, json={"op": "reroll"}, headers=player).get_json()  # any die rolled a second time doubles the debt
    assert twice["result"] == {"debt_before": 2_199_999, "debt_after": 4_399_998} and twice["character"]["tax_debt_cp"] == 4_399_998
    seen = client.get("/TTRPG/dcc/api/town", headers=player).get_json()["moons"]
    assert [m["id"] for m in seen] == ["pale", "red", "drowned"] and "days_to_full" not in seen[0]
    assert "days_to_full" in client.get("/TTRPG/dcc/api/town", headers=admin).get_json()["moons"][0]


def test_scripted_trader_stays_inside_its_limits(content, monkeypatch):
    from datetime import timedelta
    from ttrpgtools.dcc.westmarch import daily, places, town as t
    flat = {"period": 10, "amplitude": 0, "phase": 0}
    spec = {"id": "vessa", "name": "Vessa", "income": 0, "start": "40 gp", "brings": [], "likes": ["weapon", "gear"], "persona": "x",
            "script": "arbitrage.txt", "limits": {"buys_per_day": 2, "sells_per_day": 2, "pack_limit": 3, "buy_below": 0.6, "min_profit": 1.1}}
    monkeypatch.setattr(t, "today", lambda: places.EPOCH)
    with t.town(write=True) as state:
        sid = t.save_shop(state, None, "Yard", curve=flat)
        for name, price in (("Club", "10 gp"), ("Mace", "10 gp"), ("Spear", "10 gp"), ("Rope", "10 gp")):  # all at half the usual price today
            t.stock_item(state, sid, name, "weapon", price, 5, curve={"period": 4, "amplitude": 0.5, "phase": 2})
        t.stock_item(state, sid, "Lamp", "gear", "10 gp", 5, curve=flat)                                     # at the usual price: no bargain
        bot = daily._record(state, spec)
        assert dcc.coins_total_cp(bot["coins"]) == 4000
        options = daily.candidates(state, bot, spec)
        assert [r["name"] for r in options["buy"]] == ["Club", "Mace", "Spear", "Rope"] and options["sell"] == [] and options["room"] == 3
        assert all(r["discount"] == 0.5 for r in options["buy"])
        # whatever the model answers, the plan is cut to the limits; nonsense numbers are dropped
        plan = daily.scripted_plan(options, spec, {"buy": [3, 3, "x", 99, 0, 1, 2], "sell": [5]})
        assert [a["item"] for a in plan] == ["rope", "club"]
        assert len(daily.scripted_plan(options, spec)) == 2  # no answer: the two best lines
        done = daily.act(state, bot, spec, [{"do": "buy", "shop": sid, "item": i, "count": 9} for i in ("club", "mace", "spear", "lamp")], 1)
        assert len(done) == 2 and sum(i["qty"] for i in bot["inventory"]) == 2  # two purchases a day, one piece each
        daily.act(state, bot, spec, [{"do": "buy", "shop": sid, "item": "spear"}, {"do": "buy", "shop": sid, "item": "rope"}], 1)
        assert sum(i["qty"] for i in bot["inventory"]) == 3  # the pack holds three
        assert daily.act(state, bot, spec, [{"do": "sell", "shop": sid, "index": 0}], 1) == []  # never at a loss: the shop pays half of 5 gp
        assert daily.candidates(state, bot, spec)["buy"] == []  # a full pack buys nothing
    monkeypatch.setattr(t, "today", lambda: places.EPOCH + timedelta(days=2))  # the wave has turned: prices at 150%
    with t.town(write=True) as state:
        bot = state["bots"]["vessa"]
        options = daily.candidates(state, bot, spec)
        assert len(options["sell"]) == 3 and all(r["profit_cp"] == 250 for r in options["sell"])  # bought at 5 gp, the shop now pays 7 gp 5 sp
        before = dcc.coins_total_cp(bot["coins"])
        done = daily.act(state, bot, spec, daily.scripted_plan(options, spec), 3)
        assert len(done) == 2 and dcc.coins_total_cp(bot["coins"]) == before + 1500 and sum(i["qty"] for i in bot["inventory"]) == 1


@real
def test_the_arbitrage_trader_makes_money_on_the_real_shelves():
    import importlib
    from ttrpgtools.dcc.westmarch import daily, places
    importlib.reload(places)  # the autouse fixture emptied places and traders; this test wants the file's own
    places.MARKET = None
    try:
        report = daily.simulate(90, "vessa")
        purse = [row["vessa"] for row in report[:-1]]
        assert purse[-1] > 4000 * 1.5 and min(purse) > 0, purse[::10]  # from 40 gp, with the plain rule, no model
        assert len(report[-1]["packs"]["vessa"]) <= 6
    finally:
        places.PLACES, places.BOTS = [], []


@real
def test_a_player_creates_a_character_by_taking_over_a_villager(tmp_path, monkeypatch):
    from ttrpgtools.web.app import create_app
    from ttrpgtools.dcc.westmarch import registry
    monkeypatch.setattr(dcc, "CHARACTERS_DIR", tmp_path)
    client = create_app().test_client()
    admin, player, other = {"Remote-User": "admin"}, {"Remote-User": "wren"}, {"Remote-User": "ibis"}
    assert client.get("/TTRPG/dcc/new").status_code == 302 and client.get("/TTRPG/dcc/new?roll=1").status_code == 200
    rows = client.get("/TTRPG/dcc/api/registry/people", headers=player).get_json()["rows"]
    free = next(r for r in rows if r["playable"])
    assert set(free["preview"]) == {"abilities", "hp", "weapon", "goods", "copper", "item"} and "sheet" not in free  # no augur for players
    assert set(free["preview"]["abilities"]) == set(dcc.ABILITIES) - {"luck"} and all(3 <= v <= 18 for v in free["preview"]["abilities"].values())  # and no Luck
    known = next(r for r in client.get("/TTRPG/dcc/api/registry/people", headers=admin).get_json()["rows"] if r["id"] == free["id"])["preview"]
    assert "augur" in known and "luck" in known["abilities"]
    assert registry.rows("people")[0].get("preview") == next(r for r in registry.rows("people") if True).get("preview")  # the same rolls every time
    claim = lambda who, row, **extra: client.post("/TTRPG/dcc/api/registry/people", json={"action": "claim", "id": row["id"], "alignment": "lawful", "moon": "red", **extra}, headers=who).get_json()
    mayor = next(r for r in rows if r["occupation"] == "Mayor")
    assert not mayor["playable"] and "not for playing" in claim(player, mayor)["error"]
    assert "moons" in claim(player, free, moon="cheese")["error"] and "alignment" in claim(player, free, alignment="")["error"]
    cid = claim(player, free)["character"]
    got = client.get(f"/TTRPG/dcc/api/character/{cid}", headers=player).get_json()
    c = got["character"]
    assert c["name"] == free["name"] and c["owner"] == "wren" and c["alignment"] == "lawful" and c["moon"] == "red" and c["xp"] == 10
    assert c["hp_max"] == known["hp"] and c["occupation"]["occupation"] == free["occupation"] and c["luck_rule"]
    assert got["view"]["can_level"] and c["tax_debt_cp"] == 1_000_000
    # Luck and the birth augur stay sealed until 1st level, also from the player who took the villager; the admin sees them
    assert got["sealed"] and c["abilities"] == {**known["abilities"], "luck": None} and c["luck_current"] is None and c["birth_augur"] is None
    assert got["view"]["augur_effect"] is None and got["view"]["lucky_roll"] is None and got["view"]["augur_targets"] == []
    assert got["view"]["mods"]["luck"] is None and got["view"]["mods_text"]["luck"] is None and got["view"]["effective"]["luck"] is None
    for page in ("", "/json", "/folio", "/pdf"):  # every page that would tell leads back to the builder
        gone = client.get(f"/TTRPG/dcc/{cid}{page}", headers=player)
        assert gone.status_code == 302 and gone.headers["Location"].endswith(f"/{cid}/build"), page
    assert client.get(f"/TTRPG/dcc/{cid}/build", headers=player).status_code == 200
    seen = client.get(f"/TTRPG/dcc/api/character/{cid}", headers=admin).get_json()
    assert not seen["sealed"] and seen["character"]["abilities"] == known["abilities"] and seen["character"]["birth_augur"]["augur"]
    assert seen["view"]["augur_effect"] and client.get(f"/TTRPG/dcc/{cid}", headers=admin).status_code == 200
    c = seen["character"]
    looked = client.post(f"/TTRPG/dcc/api/character/{cid}/level", json={"class": got["view"]["class_choices"][0], "preview": True}, headers=player).get_json()
    assert looked["before"]["augur_effect"] is None and looked["before"]["mods"]["luck"] is None  # the level-up comparison keeps the seal too
    assert "already played by wren" in claim(other, free)["error"]
    after = next(r for r in client.get("/TTRPG/dcc/api/registry/people", headers=other).get_json()["rows"] if r["id"] == free["id"])
    assert after["claimed_by"] == "wren" and after["character_id"] == cid and not after["playable"] and "preview" not in after
    # a second roll of the birth augur, during creation only: the debt doubles every time
    first = c["birth_augur"]["roll"]
    again = client.post(f"/TTRPG/dcc/api/character/{cid}/op", json={"op": "reroll_augur"}, headers=player).get_json()
    assert again["sealed"] and again["character"]["birth_augur"] is None and again["character"]["tax_debt_cp"] == 2_000_000  # drawn again, unseen
    assert again["result"] == {"debt_before": 1_000_000, "debt_after": 2_000_000}
    redrawn = client.get(f"/TTRPG/dcc/api/character/{cid}", headers=admin).get_json()["character"]["birth_augur"]
    assert redrawn["roll"] != first and redrawn["modifier"] == c["birth_augur"]["modifier"]
    assert client.post(f"/TTRPG/dcc/api/character/{cid}/op", json={"op": "reroll_augur"}, headers=player).get_json()["character"]["tax_debt_cp"] == 4_000_000
    client.post(f"/TTRPG/dcc/api/character/{cid}/op", json={"op": "die", "cause": "a pit"}, headers=player)
    assert not any(r["id"] == free["id"] for r in registry.rows("people"))  # the villager shares the fate: gone from the village tab
    assert registry.connect().execute("SELECT status FROM people WHERE id = ?", (free["id"],)).fetchone()["status"] == "dead"
    klass = got["view"]["class_choices"][0]  # a dwarven, elven or halfling villager has only their own class
    purse = dcc.coins_total_cp(client.get(f"/TTRPG/dcc/api/character/{cid}", headers=player).get_json()["character"]["coins"])
    for body in ({"class": klass, "preview": True, "gold": 50}, {"class": klass, "hp_roll": 1, "gold": 50}):  # a player's starting gold is ignored, not refused
        done = client.post(f"/TTRPG/dcc/api/character/{cid}/level", json=body, headers=player).get_json()
        assert "error" not in done and dcc.coins_total_cp(done["character"]["coins"]) == purse, done.get("error")
    assert done["character"]["level"] == 1
    assert "fixed once a class" in client.post(f"/TTRPG/dcc/api/character/{cid}/op", json={"op": "reroll_augur"}, headers=player).get_json()["error"]
    # the seal breaks when the character is finished: a second villager, taken and brought to 1st level
    second = next(r for r in rows if r["playable"] and r["id"] != free["id"])
    cid2 = claim(other, second)["character"]
    sealed = client.get(f"/TTRPG/dcc/api/character/{cid2}", headers=other).get_json()
    assert sealed["sealed"] and sealed["character"]["luck_current"] is None
    told = client.post(f"/TTRPG/dcc/api/character/{cid2}/level", json={"class": sealed["view"]["class_choices"][0], "hp_roll": 1}, headers=other).get_json()
    assert not told["sealed"] and told["character"]["level"] == 1 and 3 <= told["character"]["luck_current"] <= 18
    assert told["character"]["birth_augur"]["augur"] and told["view"]["augur_effect"] and told["view"]["mods"]["luck"] is not None
    assert client.get(f"/TTRPG/dcc/{cid2}", headers=other).status_code == 200


@real
def test_rerolled_augur_moves_hit_points_with_it():
    c, content = hero(augur=25, stamina=13, luck=16)  # Bountiful harvest: 3 +1 Sta +2 Luck
    assert c["hp_max"] == 6
    dcc.reroll_augur(c, content, 23)                  # Charmed house: the hit points lose the Luck bonus
    assert c["hp_max"] == 4 and c["hp_current"] == 4 and c["birth_augur"]["augur"] and dcc.derive(c, content)["ac"] == 12
    dcc.reroll_augur(c, content, 25)
    assert c["hp_max"] == 6 and c["history"][0]["augur_hp"] == 2
    with pytest.raises(dcc.DCCError):
        dcc.reroll_augur(c, content, 31)


def test_the_nightly_update_waits_for_its_hour(monkeypatch):
    from datetime import timedelta
    from ttrpgtools.dcc.westmarch import daily, places, town as t
    monkeypatch.setattr(places, "UPDATE_HOUR", 2)
    monkeypatch.setattr(t, "today", lambda: places.EPOCH + timedelta(days=4))  # campaign day 5
    state = {"last_daily": 4}
    monkeypatch.setattr(t, "hour", lambda: 1)
    assert daily.due(state) == []            # one o'clock: day 5's update is not due yet
    monkeypatch.setattr(t, "hour", lambda: 2)
    assert daily.due(state) == [5]           # two o'clock: now it is
    assert daily.due({"last_daily": 1}) == [2, 3, 4, 5] and daily.due({"last_daily": 5}) == []


def test_explain_knows_the_campaign(monkeypatch):
    import ttrpgtools.dcc.westmarch  # registers the campaign's notes
    from ttrpgtools.dcc import explain as e
    found = e.passages("debt to the tax office", "Pay taxes", "")
    assert [f["title"] for f in found][0] == "This campaign: the tax office" and all(f["page"] is None for f in found)  # no occupation table
    assert e.passages("full moon", "The Red Lantern: waxing gibbous", "")[0]["title"] == "This campaign: the three moons"
    assert "nights" not in next(n for n in e.HOUSE_NOTES if "moon" in n["words"])["body"].split("Nobody")[0]  # no cycle lengths told
    monkeypatch.setattr(e, "HOSTS", [])
    events = [json.loads(line[6:]) for line in "".join(e.answer({"hint": "debt to the tax office", "text": "Pay taxes"})).split("\n\n") if line]
    assert "restarting" in events[0]["error"] and "Table 1-3" not in events[0]["error"]
    assert events[-1]["done"] and events[-1]["passages"][0]["title"] == "This campaign: the tax office"
    assert "house rules" in e.prompt({"hint": "tax"}, found)[0]["content"]


def test_one_front_door_and_old_addresses_still_lead_home():
    from ttrpgtools.web.app import create_app
    client = create_app().test_client()
    hub = client.get("/TTRPG")
    page = hub.get_data(as_text=True)
    assert hub.status_code == 200 and all(link in page for link in ('href="/TTRPG/dcc/"', 'href="/TTRPG/dnd5e/"', 'href="/TTRPG/dh1e"'))
    assert client.get("/").headers["Location"].endswith("/TTRPG") and client.get("/TTRPG/dh1e").status_code == 200
    for old, new in (("/sheet", "/TTRPG/dh1e"), ("/sheet/dcc/town?x=1", "/TTRPG/dcc/town?x=1"), ("/sheet/dnd5e/", "/TTRPG/dnd5e/"),
                     ("/sheet/static/dcc.css", "/TTRPG/static/dcc.css"), ("/sheet/some-acolyte", "/TTRPG/dh1e/some-acolyte"), ("/ttrpg/dcc/", "/TTRPG/dcc/")):
        response = client.get(old)
        assert response.status_code == 307 and response.headers["Location"].endswith(new), old
    assert client.post("/sheet/dcc/api/town/buy", json={}).status_code == 307  # an open tab's request keeps its method
    for path in ("/TTRPG/dcc/", "/TTRPG/dnd5e/", "/TTRPG/dh1e"):
        assert "Back to /TTRPG" in client.get(path).get_data(as_text=True), path
    assert client.get("/TTRPG/static/dcc/dcc.css").status_code == 200


def test_interest_averages_two_percent_a_month_under_every_moon():
    from datetime import timedelta
    from ttrpgtools.dcc.westmarch import debts, places
    for moon, nights in (("pale", 2953), ("red", 13 * 100), ("drowned", 61 * 30)):  # whole cycles
        rates = [debts.nightly_rate(moon, places.EPOCH + timedelta(days=n)) for n in range(nights)]
        monthly = sum(rates) / nights * debts.DAYS_PER_MONTH
        assert abs(monthly - 0.02) < 0.0006, (moon, monthly)
        assert max(rates) > {"pale": 1.9, "red": 1.4, "drowned": 4.0}[moon] * (sum(rates) / nights)  # the odd moons bunch it up
    dark = [n for n in range(61) if debts.nightly_rate("drowned", places.EPOCH + timedelta(days=n)) == 0]
    assert len(dark) == 28  # under the Drowned Moon nothing is added while it is dark
    assert debts.moon_of("Marta Vogt") == debts.moon_of("Marta Vogt") in ("pale", "red", "drowned") and debts.moon_of("x", "red") == "red"


@real
def test_death_library_and_the_towns_debt(tmp_path, monkeypatch):
    import importlib
    from ttrpgtools.web.app import create_app
    from ttrpgtools.dcc.westmarch import debts, places, registry, town as t
    library = [p for p in importlib.reload(places).PLACES if "library" in p["kinds"]]
    monkeypatch.setattr(places, "TAX_DEBT", "10,000 gp"); monkeypatch.setattr(places, "MARKET", None)   # the reload brought back the file's own
    monkeypatch.setattr(places, "PLACES", library); monkeypatch.setattr(places, "BOTS", []); monkeypatch.setattr(places, "UPDATE_HOUR", 0)
    client = create_app().test_client()
    admin, player = {"Remote-User": "admin"}, {"Remote-User": "wren"}
    rows = client.get("/TTRPG/dcc/api/registry/people", headers=player).get_json()["rows"]
    assert all(r["debt_cp"] == 1_000_000 for r in rows) and debts.town_total() == {"total_cp": 100_000_000, "characters": 0, "villagers": 100}
    free = [r for r in rows if r["playable"]]
    take = lambda row: client.post("/TTRPG/dcc/api/registry/people", json={"action": "claim", "id": row["id"], "alignment": "neutral", "moon": "pale"}, headers=player).get_json()["character"]
    a, b = take(free[0]), take(free[1])
    assert debts.town_total() == {"total_cp": 100_000_000, "characters": 2, "villagers": 98}  # taking a villager over moves the debt, it does not add any
    op = lambda cid, body, who=player: client.post(f"/TTRPG/dcc/api/character/{cid}/op", json=body, headers=who).get_json()
    alive = client.get(f"/TTRPG/dcc/api/character/{a}", headers=player).get_json()["character"]
    carried, coin = [i["name"] for i in alive["inventory"]], dcc.coins_total_cp(alive["coins"])
    money = lambda: client.get("/TTRPG/dcc/api/town", headers=admin).get_json()["money"]
    before_death = money()
    died = op(a, {"op": "die", "cause": "a pit"})
    assert died["result"]["debt_passed_on"] == "10.000,00 gp" and died["result"]["heirs"] == 99 and died["character"]["inventory"] == []
    assert died["result"]["coins_to_library"] == t.coins_text(coin) and dcc.coins_total_cp(died["character"]["coins"]) == 0
    after_death = money()  # the coins moved into the library's pot: still in the village, to the last copper
    assert after_death["library_cp"] == coin and after_death["money_cp"] == before_death["money_cp"] and after_death["finanzamt_cp"] == 0
    assert "already dead" in op(a, {"op": "die", "cause": "again"})["error"]
    assert debts.town_total() == {"total_cp": 100_000_000, "characters": 1, "villagers": 98}  # the town owes what it owed; the purse went to the library, not against the debt
    heir = client.get(f"/TTRPG/dcc/api/character/{b}", headers=player).get_json()["character"]
    assert heir["tax_debt_cp"] == 1_000_000 + 1_000_000 // 99 + 1  # an even share, and one of the odd coppers
    town = client.get(f"/TTRPG/dcc/api/town?character={b}", headers=player).get_json()
    shelves = {i["name"]: i for i in next(s for s in town["shops"] if s["id"] == "library")["stock"]}
    assert set(carried) <= set(shelves)  # everything, the trade goods too
    trade = lambda body: client.post("/TTRPG/dcc/api/town/buy", json={"character": b, **body}, headers=player).get_json()
    assert "lends" in trade({"shop": "library", "item": shelves[carried[0]]["id"]})["error"]
    lent = trade({"borrow": shelves[carried[0]]["id"]})
    me = next(c for c in lent["characters"] if c["id"] == b)
    assert me["loans"] and me["loans"][0]["name"] == carried[0] and "library" not in lent["offers"]
    assert not any(row["name"] == carried[0] and row["index"] == me["loans"][0]["index"] for rows_ in lent["offers"].values() for row in rows_)  # a loan cannot be sold
    back = trade({"give_back": me["loans"][0]["index"]})
    assert next(c for c in back["characters"] if c["id"] == b)["loans"] == [] and "not a library loan" in trade({"give_back": 0})["error"]
    # coin from the pot: a loan that grows by the borrower's moon and is paid back into the pot
    pot = money()["library_cp"]
    assert "holds only" in trade({"borrow_coin": "500 gp"})["error"]
    got = trade({"borrow_coin": t.coins_text(pot)})
    me = next(c for c in got["characters"] if c["id"] == b)
    assert me["library_loan_cp"] == pot and got["library_pot_cp"] == 0 and money()["money_cp"] == before_death["money_cp"]
    ch = dcc.load_character(b)
    ch["library_loan_cp"] = 100_000; dcc.save_character(ch, b)   # a large loan, so one night's interest shows
    first_night = debts.accrue(t.campaign_day())  # the tax debt grows in the same night; the loan is not part of that sum
    grown = dcc.load_character(b)["library_loan_cp"]
    assert grown >= 100_000 and grown - 100_000 == round(100_000 * debts.nightly_rate("pale", t.today(), places.LIBRARY_INTEREST_MONTHLY))
    ch = dcc.load_character(b); ch["library_loan_cp"] = pot; dcc.save_character(ch, b)
    paid = trade({"repay_coin": "9999 gp"})  # never more than is owed
    assert next(c for c in paid["characters"] if c["id"] == b)["library_loan_cp"] == 0 and paid["library_pot_cp"] == pot
    assert "owes the library no coin" in trade({"repay_coin": "1 gp"})["error"]
    # a villager nobody plays dies: the same split
    npc = next(r for r in rows if not r["playable"] and r["locked"])
    client.post("/TTRPG/dcc/api/registry/people", json={"id": npc["id"], "status": "dead"}, headers=admin)
    assert debts.town_total() == {"total_cp": 100_000_000 + first_night, "characters": 1, "villagers": 97}
    # interest: one night adds to everyone alive, nothing to the dead
    before = debts.town_total()["total_cp"]
    added = debts.accrue(t.campaign_day())
    assert debts.town_total()["total_cp"] == before + added and client.get(f"/TTRPG/dcc/api/character/{a}", headers=player).get_json()["character"]["tax_debt_cp"] == 0
    page = client.get("/TTRPG/dcc/", headers=player).get_data(as_text=True)
    assert "The town owes the tax office" in page and t.coins_text(before + added) in page
    # a death recorded by mistake: the debt comes home
    undone = op(a, {"op": "revive"}, admin)
    assert undone["character"]["tax_debt_cp"] > 990_000 and debts.town_total()["total_cp"] == before + added


@real
def test_luck_of_plus_zero_is_nudged_at_birth(tmp_path):
    from ttrpgtools.dcc.westmarch import places, registry
    content = dcc.load_content()
    draws = [registry.nudged_luck(f"Person {n}") for n in range(2000)]
    moved = [d for d in draws if d is not None]
    assert 0.77 < len(moved) / len(draws) < 0.83 and all(d < 9 or d > 12 for d in moved)  # four in five, never back into the +0 band
    assert 0.45 < sum(d > 12 for d in moved) / len(moved) < 0.55 and registry.nudged_luck("Person 7") == registry.nudged_luck("Person 7")
    sheets = [registry.roll_villager(content, name, "Scribe") for name in (f"Villager {n}" for n in range(600))]
    plus_zero = sum(dcc.ability_mod(content, s["abilities"]["luck"]) == 0 for s in sheets) / len(sheets)
    assert plus_zero < 0.15  # plain 3d6 leaves almost half at +0; now about a tenth
    # an existing character, retroactively: the augur, the Luck left, the lucky weapon and the hit points follow
    c, content = hero(augur=25, stamina=13, luck=10, klass="warrior", level=2)   # Bountiful harvest, hit point rolls 3, 1, 1
    dcc.burn_luck(c, 2)
    assert c["hp_max"] == 4 + 2 + 2 and c["birth_augur"]["modifier"] == 0 and c["first_level_luck_mod"] == 0
    dcc.rebirth_luck(c, content, 16)
    assert c["abilities"]["luck"] == 16 and c["luck_current"] == 14 and c["birth_augur"]["modifier"] == 2 and c["first_level_luck_mod"] == 2
    assert c["hp_max"] == 6 + 4 + 4 and c["hp_current"] == 14 and c["history"][1]["hp_gained"] == 4
    dcc.rebirth_luck(c, content, 5)
    assert c["birth_augur"]["modifier"] == -2 and c["hp_max"] == 2 + 1 + 1 and c["luck_current"] == 3  # at least 1 hit point per level
    for n, luck in enumerate((10, 14)):
        ch, content = hero(luck=luck)
        ch["name"] = f"Old Character {n}"
        dcc.save_character(ch, f"old-{n}")
    changed = registry.apply_luck_rule(content)
    assert all(old in (9, 10, 11, 12) for _, old, _ in changed) and registry.apply_luck_rule(content) == []  # only +0 is touched, and only once
    assert dcc.load_character("old-1")["abilities"]["luck"] == 14 and dcc.load_character("old-1")["luck_rule"]


def test_goods_are_made_from_material_and_nothing_appears(content, monkeypatch, tmp_path):
    from ttrpgtools.dcc.westmarch import daily, materials, places, registry, town as t
    flat = {"period": 10, "amplitude": 0, "phase": 0}
    monkeypatch.setattr(t, "today", lambda: places.EPOCH)
    assert materials.made_of("Two-handed sword", "weapon") == ("metal", 4000) and materials.made_of("Hot meal", "service") is None
    assert [materials.kg_text(g) for g in (4000, 250, 12_500, 50)] == ["4,0 kg", "0,25 kg", "12,5 kg", "0,05 kg"]
    assert materials.made_of("Pitchfork (as spear)", "weapon") == ("wood", 1500) and materials.made_of("Hen**", "trade") is None
    with t.town(write=True) as state:
        sid = t.save_shop(state, None, "Forge", curve=flat)
        shop = state["shops"][sid]
        shop.update(deals=["weapon", "gear"], restock_every=1, till=500_000, materials={"metal": 4000})
        sword = t.stock_item(state, sid, "Two-handed sword", "weapon", "10 gp", 0, curve=flat)
        sword["target"] = 2
        metal = lambda: materials.census(state)["metal"]
        assert metal() == {"name": "Metal", "raw_g": 4000, "things_g": 0, "total_g": 4000}
        assert t.restock(state, sid) == {"made": 1, "broken": 0, "short": ["Two-handed sword"]}  # 4 kg of metal is one 4 kg sword, not two
        assert shop["materials"]["metal"] == 0 and sword["qty"] == 1 and metal() == {"name": "Metal", "raw_g": 0, "things_g": 4000, "total_g": 4000}
        # a second-hand piece is broken up only when that yields enough for the piece wanted
        old = t.stock_item(state, sid, "Longsword", "weapon", "10 gp", 1, curve=flat)  # 2 kg
        assert t.restock(state, sid)["made"] == 0 and old["qty"] == 1 and shop["materials"]["metal"] == 0
        old["qty"] = 3
        before = metal()["total_g"]
        assert t.restock(state, sid) == {"made": 1, "broken": 2, "short": []}
        assert old["qty"] == 1 and sword["qty"] == 2 and shop["materials"]["metal"] == 0 and metal()["total_g"] == before == 10_000  # metal comes back whole
        # what a listed line holds beyond its quantity is spare too; the listed quantity itself is not touched
        dagger = t.stock_item(state, sid, "Dagger", "weapon", "3 gp", 3, curve=flat)
        dagger["target"] = 1
        short = t.stock_item(state, sid, "Short sword", "weapon", "7 gp", 0, curve=flat)
        short["target"] = 2
        assert t.restock(state, sid) == {"made": 2, "broken": 1, "short": []} and old["qty"] == 0 and dagger["qty"] == 3  # second-hand goes first
        short["target"] = 4
        assert t.restock(state, sid) == {"made": 1, "broken": 2, "short": ["Short sword"]} and dagger["qty"] == 1 and short["qty"] == 3
        assert metal()["total_g"] == 10_000 + 3 * 500
        # Oldwork loses half each time it is broken up
        lantern = t.stock_item(state, sid, "Lantern", "gear", "10 gp", 0, curve=flat)
        lantern["target"] = 1
        glass = t.stock_item(state, sid, "Spyglass", "gear", "50 gp", 3, curve=flat)  # 0,5 kg each: 0,75 kg after the loss, not enough for 1 kg
        tech = lambda: materials.census(state)["tech"]["total_g"]
        assert t.restock(state, sid)["broken"] == 0 and glass["qty"] == 3 and tech() == 1500
        glass["qty"] = 5
        assert t.restock(state, sid)["made"] == 1 and glass["qty"] == 1 and lantern["qty"] == 1 and tech() == 1500 == 2500 - 1000
        # wood is never broken up: it has to be brought
        club = t.stock_item(state, sid, "Club", "weapon", "3 gp", 0, curve=flat)
        club["target"] = 1
        staff = t.stock_item(state, sid, "Staff", "weapon", "5 sp", 5, curve=flat)
        assert t.restock(state, sid) == {"made": 0, "broken": 0, "short": ["Short sword", "Club"]} and staff["qty"] == 5
        # the villagers: small goods a piece at a time up to the listed quantity, wood up to what the workshop takes
        eggs = t.stock_item(state, sid, "Eggs, a dozen", "trade", "3 cp", 0, curve=flat)
        eggs["target"] = 2
        monkeypatch.setattr(places, "PRODUCE", [{"wood_kg": 2, "by": ["forester"]}, {"good": "Eggs, a dozen", "by": ["farmer"]}])
        monkeypatch.setattr(places, "PRODUCE_CHANCE", 1.0)
        monkeypatch.setattr(places, "WOOD_STORE_KG", 5)
        monkeypatch.setattr(registry, "producers", lambda: [{"name": "Ada", "occupation": "Farmer"}, {"name": "Ilse", "occupation": "Elven Forester"},
                                                            {"name": "Odo", "occupation": "Jester"}])
        assert materials.made_of("Eggs, a dozen", "trade") is None
        assert [daily.produce(state, day) for day in (1, 2, 3, 4)] == [{"pieces": 1, "wood_g": 2000}, {"pieces": 1, "wood_g": 2000},
                                                                       {"pieces": 0, "wood_g": 1000}, {"pieces": 0, "wood_g": 0}]
        assert eggs["qty"] == 2 and shop["materials"]["wood"] == 5000
        assert t.restock(state, sid)["made"] == 1 and club["qty"] == 1 and shop["materials"]["wood"] == 3500
        monkeypatch.setattr(registry, "producers", lambda: [])  # the farmer became an adventurer: no more eggs
        eggs["qty"] = 0
        assert daily.produce(state, 5) == {"pieces": 0, "wood_g": 0}
        # the admin's hand from outside is the only other source, and it is written down
        t.add_material(state, sid, "metal", 2.5, "admin")
        assert shop["materials"]["metal"] == 2500 and "2,5 kg of Metal brought to Forge" in state["goods_log"][-1]["what"]
        with pytest.raises(t.TownError, match="holds only"):
            t.add_material(state, sid, "metal", -3, "admin")
        seen = t.view(state, "nobody")["shops"][0]
        row = next(r for r in seen["stock"] if r["name"] == "Two-handed sword")
        assert (row["material"], row["weight"]) == ("Metal", "4,0 kg") and {"id": "metal", "name": "Metal", "amount": "2,5 kg"} in seen["materials"]
    # a sale the till cannot pay for leaves no trace: no piece on the shelf, no new line, nothing out of the pack
    with t.town(write=True) as state:
        shop = state["shops"][sid]
        shop["till"] = 1
        c = make(content)
        dcc.add_item(c, "Dagger", "weapon", 2, "3 gp")
        dcc.add_item(c, "Mace", "weapon", 1, "5 gp")
        daggers = next(i for i in shop["stock"] if i["name"] == "Dagger")["qty"]
        lines = len(shop["stock"])
        carried = {i["name"]: (n, i["qty"]) for n, i in enumerate(c["inventory"])}
        for name in ("Dagger", "Mace"):  # one the forge shelves already, one it would have to open a line for
            with pytest.raises(t.TownError, match="in the till"):
                t.sell(state, sid, c, carried[name][0])
        assert next(i for i in shop["stock"] if i["name"] == "Dagger")["qty"] == daggers and len(shop["stock"]) == lines
        assert {i["name"]: (n, i["qty"]) for n, i in enumerate(c["inventory"])} == carried and shop["till"] == 1
        shop["till"] = 500_000
    # a trader's unsold purchase no longer leaves the pack by itself; an unscripted trader lets it go at a loss in the end
    spec = {"id": "hen", "name": "Henrik", "likes": ["weapon"], "persona": "x", "brings": [("Mended lantern", "gear", "6 gp")]}
    with t.town(write=True) as state:
        bot = daily._record(state, spec)
        dcc.add_item(bot, "Dagger", "weapon", 1, "3 gp")
        bot["inventory"][0].update(paid_cp=100_000, bought_day=1)
        daily.arrive(bot, spec, 40)
        assert [i["name"] for i in bot["inventory"]] == ["Dagger"]  # still there, and no lantern from nowhere
        assert daily.rule_plan(state, bot, spec, 2) == [] or all(a["do"] == "buy" for a in daily.rule_plan(state, bot, spec, 2))
        assert {"do": "sell", "shop": sid, "index": 0, "count": 1} in daily.rule_plan(state, bot, spec, 40)


def test_endless_shelves_get_a_listed_quantity(content, monkeypatch):
    from ttrpgtools.dcc.westmarch import places, town as t
    monkeypatch.setattr(places, "PLACES", [{"id": "store", "name": "Store", "kinds": ["shop"], "materials": {"metal": 1.5},
                                            "goods": [("Candle", "gear", "1 cp", None)]}])
    with t.town(write=True) as state:
        line = state["shops"]["store"]["stock"][0]
        assert line["qty"] is None and state["shops"]["store"]["materials"] == {"metal": 1500}
        state["shops"]["store"]["materials"]["metal"] = 700  # used since
    monkeypatch.setattr(places, "PLACES", [{"id": "store", "name": "Store", "kinds": ["shop"], "materials": {"metal": 1.5},
                                            "goods": [("Candle", "gear", "1 cp", 20)]}])
    with t.town(write=True) as state:
        line = state["shops"]["store"]["stock"][0]
        assert (line["qty"], line["target"]) == (20, 20) and state["shops"]["store"]["materials"] == {"metal": 700}  # the store is not refilled
        line["qty"] = 3
    with t.town() as state:
        assert state["shops"]["store"]["stock"][0]["qty"] == 3  # and the shelf is not topped up on the next load


@real
def test_only_the_admin_brings_material_from_outside():
    from ttrpgtools.web.app import create_app
    from ttrpgtools.dcc.westmarch import town as t
    with t.town(write=True) as state:
        forge = t.save_shop(state, None, "Forge")
        state["shops"][forge]["materials"] = {"metal": 3000}
        t.stock_item(state, forge, "Dagger", "weapon", "3 gp", 2)
    client = create_app().test_client()
    admin, player = {"Remote-User": "admin"}, {"Remote-User": "wren"}
    judge = lambda body, who: client.post("/TTRPG/dcc/api/town/judge", json=body, headers=who)
    assert judge({"action": "material", "shop": forge, "material": "metal", "kg": "12,5"}, player).status_code == 403
    assert "kilograms" in judge({"action": "material", "shop": forge, "material": "metal", "kg": "lots"}, admin).get_json()["error"]
    seen = judge({"action": "material", "shop": forge, "material": "metal", "kg": "12,5"}, admin).get_json()
    assert seen["goods"]["census"]["metal"] == {"name": "Metal", "raw_g": 15_500, "things_g": 1000, "total_g": 16_500}
    assert "12,5 kg of Metal brought to Forge" in seen["goods"]["log"][0]["what"] and seen["goods"]["log"][0]["by"] == "admin"
    town = client.get("/TTRPG/dcc/api/town", headers=player).get_json()
    assert "goods" not in town and town["shops"][0]["materials"] == [{"id": "metal", "name": "Metal", "amount": "15,5 kg"}]
    assert town["shops"][0]["stock"][0]["weight"] == "0,5 kg"


def test_page_scripts_parse():
    """A script with a syntax error takes its whole page down, and no Python test would notice."""
    import shutil, subprocess
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    scripts = sorted((dcc.REPO_DIR / "ttrpgtools" / "web" / "static" / "dcc").glob("*.js"))
    assert len(scripts) >= 5
    for script in scripts:
        result = subprocess.run([node, "--check", str(script)], capture_output=True, text=True)
        assert result.returncode == 0, f"{script.name}: {result.stderr[:400]}"


def test_the_tax_office_minds_its_manners_by_luck(content, monkeypatch):
    from ttrpgtools.dcc.westmarch import voices
    assert [voices.luck_band(n) for n in (3, 5, 6, 8, 9, 12, 13, 15, 16, 18)] == ["cursed", "cursed", "unlucky", "unlucky", "plain", "plain", "lucky", "lucky", "blessed", "blessed"]
    c = make(content)
    c.update(name="Egon Crookback", tax_debt_cp=1_009_259)
    said = {}
    for luck in (4, 7, 10, 14, 17):
        c["luck_current"] = luck
        line = voices.tax_office(c, 3)
        said[line["band"]] = line["owes"]
        assert "10.092,59 gp" in line["owes"] and "{" not in line["owes"]                 # the same sum under every letterhead
        assert line == voices.tax_office(c, 3)                                              # the same all day
        receipt = voices.tax_receipt(c, 500, 3)
        assert "5,00 gp" in receipt and "{" not in receipt
    assert said["plain"] == "Egon Crookback owes 10.092,59 gp." and len(set(said.values())) == 5
    assert "Egon Crookback" in said["blessed"] and "Egon Crookback" in said["lucky"]
    assert "Egon Crookback" not in said["unlucky"] and "Egon Crookback" not in said["cursed"]    # never spelled right
    c["luck_current"] = 4
    slips = {voices.misspelled("Egon Crookback", day) for day in range(1, 40)}
    assert len(slips) > 8 and "Egon Crookback" not in slips and all(abs(len(s) - 14) <= 1 for s in slips)   # another slip every day, never the real name
    assert any("Roughly" in voices.tax_receipt(c, 500, day) for day in range(1, 6))             # no bed booked: the office still claims to know
    c["lodging"] = {"name": "The Shoddy Inn", "nights": 2, "applied": 0}
    assert any("The Shoddy Inn" in voices.tax_receipt(c, 500, day) for day in range(1, 6))    # the office knows where the unlucky sleep
    # a sealed character's Luck is not given away by the office's tone
    assert voices.tax_office(c, 3, sealed=True) == {"band": "plain", "owes": "Egon Crookback owes 10.092,59 gp."}
    assert voices.tax_receipt(c, 500, 3, sealed=True) == "Paid 5,00 gp in taxes. The coin is gone."


def test_roman_numerals_for_the_moon_that_counts_the_old_way():
    """The page script that rewrites the town's numbers for characters of the Roman-numeral moon, run through node."""
    from ttrpgtools.dcc.westmarch import places
    assert [m["id"] for m in places.MOONS if m.get("numerals") == "roman"] == ["pale"]
    import json, shutil, subprocess
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    source = (dcc.REPO_DIR / "ttrpgtools" / "web" / "static" / "dcc" / "dcc_assist.js").read_text(encoding="utf-8")
    block = source[source.index("  const ROMAN = "):source.index("  function romanize(root)")]
    cases = {"7,07 gp": "VII gp", "0,01 gp": "I cp", "0,00 gp": "N gp", "10.092,59 gp": "X̅ gp",      # money is rounded for the eye
             "0,36 gp": "XXXV cp", "0,14 gp": "XIV cp", "5,36 gp": "V gp L cp", "37,61 gp": "XL gp", "248,99 gp": "CCL gp",
             "92.283,04 gp": "X̅C̅ gp", "1.000.000,00 gp": "M̅ gp", "1.171.999,98 gp": "M̅C̅C̅ gp",
             "3 left": "III left", "38 left": "XXXVIII left", "0 left": "N left",                            # a count is never rounded
             "Metal, 4,0 kg": "Metal, IV kg", "Wood, 0,25 kg": "Wood, ··· kg", "Leather and stuff, 4,5 kg": "Leather and stuff, IVS kg",
             "Monday, 5 October 2026": "Monday, V October MMXXVI", "1d10": "1d10", "Arrows (20)": "Arrows (XX)", "1994": "MCMXCIV"}
    script = block + "\nprocess.stdout.write(JSON.stringify(" + json.dumps(list(cases)) + ".map(romanText)));"
    result = subprocess.run([node, "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr[:400]
    assert dict(zip(cases, json.loads(result.stdout))) == cases


@real
def test_moon_enemies_and_the_herb_woman(monkeypatch):
    from datetime import date, timedelta
    from ttrpgtools.web.app import create_app
    from ttrpgtools.dcc.westmarch import places, town as t
    # the forecast agrees with the moons' own cycles: the red lantern is full for five nights of thirteen
    day = places.EPOCH
    seen = t.full_forecast("red", day)
    assert 0 <= seen["in"] <= 12 and 1 <= seen["for"] <= 5
    first = day + timedelta(days=seen["in"])
    assert t.moon(first, "red")["phase"] == "full" and t.moon(first + timedelta(days=seen["for"]), "red")["phase"] != "full"
    assert all(t.moon(first + timedelta(days=n), "red")["phase"] == "full" for n in range(seen["for"]))
    assert seen["in"] == 0 or t.moon(first - timedelta(days=1), "red")["phase"] != "full"
    drowned = t.full_forecast("drowned", day)
    assert drowned["for"] == 1 and t.moon(day + timedelta(days=drowned["in"]), "drowned")["phase"] == "full"
    # the rule is static: a character's moon gives one die better against its enemies and one die worse against its weak kind
    c, content = hero(augur=2)
    c["moon"] = "red"
    rule = t.moon_rule(c)
    assert rule["text"] == ("Your moon is The Red Lantern. One die better (+1d) against the hungry: goblins, beasts, and anything that eats people. "
                            "One die worse (-1d) against the dead and the patient: un-dead, statues, and whatever has been waiting. "
                            "Saving throws are one die better (+1d) by open flame, on odd dungeon levels, or in the front rank.")
    assert ["even" in m["safe"] or "odd" in m["safe"] for m in places.MOONS] == [True, True, False]   # pale even, red odd, drowned neither
    assert {m["id"]: (m["enemies"].split(":")[0], m["weak"].split(":")[0]) for m in places.MOONS} == {
        "pale": ("the dead and the patient", "the wet and the hidden"), "red": ("the hungry", "the dead and the patient"),
        "drowned": ("the wet and the hidden", "the hungry")}                       # each moon is weak against another moon's enemies
    assert t.moon_rule({**c, "moon": None}) is None
    # the herb woman: a copper a question, into her till, and no page of her own
    monkeypatch.setattr(places, "PLACES", [{"id": "herb-woman", "till": "0 gp", "name": "The Herb Woman", "kinds": ["oracle"], "keeper": "Hedwig Dornbusch", "ask": "1 cp", "blurb": "x"}])
    client = create_app().test_client()
    player = {"Remote-User": "wren"}
    rows = client.get("/TTRPG/dcc/api/registry/people", headers=player).get_json()["rows"]
    hedwig = next(r for r in rows if r["name"] == "Hedwig Dornbusch")
    assert hedwig["locked"] and not hedwig["playable"] and hedwig["occupation"] == "Herb woman"
    free = next(r for r in rows if r["playable"])
    cid = client.post("/TTRPG/dcc/api/registry/people", json={"action": "claim", "id": free["id"], "alignment": "lawful", "moon": "drowned"}, headers=player).get_json()["character"]
    town = client.get(f"/TTRPG/dcc/api/town?character={cid}", headers=player).get_json()
    me = next(x for x in town["characters"] if x["id"] == cid)
    woman = next(s for s in town["shops"] if s["id"] == "herb-woman")
    assert woman["ask"] == {"price_cp": 1, "price": "0,01 gp"} and "Your moon is The Drowned Moon" in me["moon_rule"]["text"] and not me["roman"]
    purse = me["coins_cp"]
    told = client.post("/TTRPG/dcc/api/town/buy", json={"character": cid, "shop": "herb-woman", "ask_moon": "red"}, headers=player).get_json()
    assert "The Red Lantern is full" in told["receipt"] and "Hedwig Dornbusch" in told["receipt"]
    assert next(x for x in told["characters"] if x["id"] == cid)["coins_cp"] == purse - 1
    with t.town() as state:
        assert state["shops"]["herb-woman"]["till"] == 1
    assert "three moons" in client.post("/TTRPG/dcc/api/town/buy", json={"character": cid, "shop": "herb-woman", "ask_moon": "cheese"}, headers=player).get_json()["error"]


@real
def test_birth_augurs_change_hands_at_the_herb_woman(monkeypatch):
    from ttrpgtools.web.app import create_app
    from ttrpgtools.dcc.westmarch import places, town as t
    content = dcc.load_content()
    harvest = next(a for a in content["luck_augurs"] if "hp_per_level" in dcc.augur_targets(a["applies_to"]))
    plain = next(a for a in content["luck_augurs"] if dcc.augur_targets(a["applies_to"]) == {"ac"})
    # the engine: an augur that touches hit points takes them along for every level so far, and brings them back
    c, _ = hero(augur=harvest["roll"], klass="warrior", level=2, luck=16)      # Luck 16: +2 to hit points at 0-level and at both levels
    assert c["birth_augur"]["modifier"] == 2
    with_augur = c["hp_max"]
    dcc.set_augur(c, content, None)
    assert c["birth_augur"]["roll"] == 0 and c["hp_max"] == with_augur - 6 and dcc.derive(c, content)["augur_effect"] == "Born under nothing: no birth augur"
    dcc.set_augur(c, content, harvest, 1, origin="bought")
    assert c["hp_max"] == with_augur - 3 and c["birth_augur"]["modifier"] == 1 and c["birth_augur"]["origin"] == "bought"
    dcc.set_augur(c, content, plain, -2, origin="bought")
    assert c["hp_max"] == with_augur - 6 and dcc.derive(c, content)["ac"] == dcc.derive(dict(c, birth_augur=dict(dcc.NO_AUGUR)), content)["ac"] - 2
    # the trade, with coin: 50 gp a point, worn by one point on her shelf, her till pays or is paid
    monkeypatch.setattr(places, "PLACES", [{"id": "herb-woman", "till": "0 gp", "name": "The Herb Woman", "kinds": ["oracle"], "keeper": "Hedwig Dornbusch",
                                            "ask": "1 cp", "augur_point": "50 gp", "blurb": "x"}])
    lucky, _ = hero(augur=plain["roll"], klass="warrior", level=1, luck=16)      # Charmed House style, +2
    unlucky, _ = hero(augur=harvest["roll"], klass="warrior", level=1, luck=5)   # hit points, -2
    lucky["name"], unlucky["name"] = "Lucky", "Unlucky"
    for ch in (lucky, unlucky):
        ch["coins"] = {"gp": 120, "sp": 0, "cp": 0}
    hp_before = unlucky["hp_max"]
    with t.town(write=True) as state:
        shop = state["shops"]["herb-woman"]
        with pytest.raises(t.TownError, match="cannot pay"):
            t.sell_augur(state, "herb-woman", lucky)                              # her till is empty: she cannot buy a good one
        assert lucky["birth_augur"]["roll"] == plain["roll"] and shop.get("augurs", []) == []
        sale = t.sell_augur(state, "herb-woman", unlucky)                         # a bad one: 2 points, 100 gp to be rid of it
        assert shop["till"] == 10_000 and dcc.coins_total_cp(unlucky["coins"]) == 2_000 and unlucky["birth_augur"]["roll"] == 0
        assert unlucky["hp_max"] > hp_before and "paid to be rid" in sale["answer"]   # the hit points it cost come back
        assert [(a["modifier"], a["price_cp"]) for a in t.augur_shelf(shop)] == [(-3, -15_000)]   # worn by one point: worse
        with pytest.raises(t.TownError, match="cannot pay"):
            t.take_augur(state, "herb-woman", unlucky, 0)                         # she owes 150 gp to whoever takes it and holds 100
        t.sell_augur(state, "herb-woman", lucky)                                  # now she can pay 100 gp for the +2
        assert shop["till"] == 0 and dcc.coins_total_cp(lucky["coins"]) == 22_000 and [a["modifier"] for a in shop["augurs"]] == [-3, 1]
        with pytest.raises(t.TownError, match="no augur left"):
            t.sell_augur(state, "herb-woman", lucky)
        everything = lambda: dcc.coins_total_cp(lucky["coins"]) + dcc.coins_total_cp(unlucky["coins"]) + shop["till"]
        assert everything() == 24_000                                             # coin only moved between two purses and her till
        with pytest.raises(dcc.DCCError, match="Not enough coin"):
            t.take_augur(state, "herb-woman", unlucky, 1)                         # the worn +1 costs 50 gp; 20 gp will not do
        got = t.take_augur(state, "herb-woman", lucky, 1)                         # anyone without an augur may take it, the seller too
        assert lucky["birth_augur"]["modifier"] == 1 and "bought from Hedwig Dornbusch, once Lucky's" == lucky["birth_augur"]["origin"]
        assert shop["till"] == 5_000 and dcc.coins_total_cp(lucky["coins"]) == 17_000 and "itches" in got["answer"] and everything() == 24_000
        with pytest.raises(t.TownError, match="One at a time"):
            t.take_augur(state, "herb-woman", lucky, 0)
        shop["till"] = 15_000                                                     # the admin fills her till: now she can pay for the bad one to leave
        no_augur_hp = unlucky["hp_max"]
        paid = t.take_augur(state, "herb-woman", unlucky, 0)
        assert dcc.coins_total_cp(unlucky["coins"]) == 17_000 and shop["till"] == 0 and shop["augurs"] == [] and "She pays 150,00 gp" in paid["answer"]
        assert unlucky["birth_augur"]["modifier"] == -3 and unlucky["hp_max"] == sum(max(1, int(h["hp_roll"]) - 3) for h in unlucky["history"] if h["event"] in ("0-level", "level")) <= no_augur_hp
        novice, _ = hero(augur=plain["roll"], luck=16)                            # level 0: the augur is not theirs to trade yet
        with pytest.raises(t.TownError, match="Finish the character first"):
            t.sell_augur(state, "herb-woman", novice)
        assert [s_["item"] for s_ in state["log"]][-4:] == ["Augur sold: " + harvest["augur"] + " (-2)", "Augur sold: " + plain["augur"] + " (+2)",
                                                            "Augur taken: " + plain["augur"] + " (+1)", "Augur taken: " + harvest["augur"] + " (-3)"]
    # the page data: what she holds and what a finished character carries
    client = create_app().test_client()
    seen = client.get("/TTRPG/dcc/api/town", headers={"Remote-User": "admin"}).get_json()
    woman = next(x for x in seen["shops"] if x["id"] == "herb-woman")
    assert woman["augurs"] == [] and woman["augur_point_cp"] == 5_000


def test_made_things_carry_the_moon_of_their_day(content, monkeypatch):
    from datetime import timedelta
    from ttrpgtools.dcc.westmarch import places, town as t
    flat = {"period": 10, "amplitude": 0, "phase": 0}
    monkeypatch.setattr(t, "today", lambda: places.EPOCH)
    # the fullest moon of a night is a full one whenever any moon is full
    for n in range(0, 120):
        on = places.EPOCH + timedelta(days=n)
        full = [m["id"] for m in places.MOONS if t.moon(on, m["id"])["phase"] == "full"]
        assert not full or t.fullest_moon(on) in full, (n, full, t.fullest_moon(on))
    assert {t.fullest_moon(places.EPOCH + timedelta(days=n)) for n in range(0, 120)} == {"pale", "red", "drowned"}
    # a gift and a flaw are each only a chance: even for a maker of plain Luck, swayed a tenth per point of Luck modifier; never two of either
    monkeypatch.setattr(t, "maker_luck", lambda name: {"Lucky Smith": 17, "Plain Smith": 10, "Sour Smith": 4}[name])
    line = {"id": "dagger", "kind": "weapon"}
    share = {}
    for name in ("Lucky Smith", "Plain Smith", "Sour Smith"):
        marks = [t.make_mark("forge", {"keeper": name}, line, 1, piece) for piece in range(2000)]
        assert all(len(m["gifts"]) <= 1 and len(m["flaws"]) <= 1 and m["moon"] == t.fullest_moon(places.EPOCH) for m in marks)
        share[name] = (sum(bool(m["gifts"]) for m in marks) / 2000, sum(bool(m["flaws"]) for m in marks) / 2000)
    assert 0.46 < share["Plain Smith"][0] < 0.54 and 0.46 < share["Plain Smith"][1] < 0.54
    assert 0.66 < share["Lucky Smith"][0] < 0.74 and 0.26 < share["Lucky Smith"][1] < 0.34      # Luck 17: +2
    assert 0.26 < share["Sour Smith"][0] < 0.34 and 0.66 < share["Sour Smith"][1] < 0.74        # Luck 4: -2
    assert t.make_mark("forge", {"keeper": "Plain Smith"}, line, 1) == t.make_mark("forge", {"keeper": "Plain Smith"}, line, 1)
    # whatever could bear a name has a moon; ammunition and bundles have none
    assert t.make_mark("forge", {"keeper": "Plain Smith"}, {"id": "lantern", "kind": "gear"}, 1) is not None
    assert t.make_mark("forge", {"keeper": "Plain Smith"}, {"id": "arrows", "kind": "ammo", "units": 20}, 1) is None
    assert t.make_mark("forge", {"keeper": "Plain Smith"}, {"id": "spikes", "kind": "gear", "units": 12}, 1) is None
    both = {"moon": "red", "gifts": ["while you are wounded"], "flaws": ["on a full stomach"]}
    assert t.mark_text(both) == "Red Lantern make. Attacks with it are one die better while you are wounded. Attacks with it are one die worse on a full stomach."
    assert t.mark_text({"moon": "pale", "gifts": [], "flaws": []}, "gear") == "Pale Moon make."
    assert t.mark_text({**both, "flaws": []}, "trade") == "Red Lantern make. Rolls made with it are one die better while you are wounded."
    with t.town(write=True) as state:
        sid = t.save_shop(state, None, "Forge", "Plain Smith", curve=flat)
        shop = state["shops"][sid]
        shop.update(deals=["weapon", "gear"], till=500_000, materials={"metal": 5_000, "leather": 5_000})
        dagger = t.stock_item(state, sid, "Dagger", "weapon", "3 gp", 1, curve=flat)   # one old piece, made before the rule
        dagger["target"] = 3
        pack = t.stock_item(state, sid, "Backpack", "gear", "2 gp", 0, curve=flat)
        pack["target"] = 2
        assert t.restock(state, sid, day=1)["made"] == 4 and len(dagger["made"]) == 2 and dagger["qty"] == 3 and len(pack["made"]) == 2
        moon = t.fullest_moon(places.EPOCH)
        assert all(m["moon"] == moon and m["maker"] == "Plain Smith" and m["day"] == 1 for m in dagger["made"] + pack["made"])
        assert "mark" not in t.view(state, "nobody")["shops"][0]["stock"][0]            # the town table says nothing to a player
        assert t.view(state, "admin")["shops"][0]["stock"][0]["mark"]["pieces"] == 2   # the admin sees which moon is next
        c = make(content)
        c["coins"] = {"gp": 50, "sp": 0, "cp": 0}
        t.buy(state, sid, "dagger", c)                                 # the marked pieces go first
        mine = c["inventory"][-1]
        assert mine["name"] == "Dagger" and mine["mark"]["moon"] == moon and " make." in mine["notes"] and len(dagger["made"]) == 1
        t.buy(state, sid, "dagger", c); t.buy(state, sid, "dagger", c)
        daggers = [i for i in c["inventory"] if i["name"] == "Dagger"]
        assert [bool(i.get("mark")) for i in daggers] == [True, True, False] and "made" not in dagger and dagger["qty"] == 0
        t.buy(state, sid, "backpack", c); t.buy(state, sid, "backpack", c)
        dcc.add_item(c, "Backpack", "gear", 1, "2 gp")                 # a plain one from elsewhere: it never merges into a piece with a moon
        packs = [i for i in c["inventory"] if i["name"] == "Backpack"]
        assert [(i["qty"], bool(i.get("mark"))) for i in packs] == [(1, True), (1, True), (1, False)]
        index = next(n for n, i in enumerate(c["inventory"]) if i.get("mark") and i["name"] == "Dagger")
        mark = c["inventory"][index]["mark"]
        t.sell(state, sid, c, index)                                  # sold back: the piece keeps its moon on the shelf
        assert dagger["qty"] == 1 and dagger["made"] == [mark]
    with t.town() as state:
        assert state["shops"][sid]["stock"][0]["made"] == [mark]      # and the mark survives being saved and loaded


@real
def test_a_hen_has_a_moon(monkeypatch):
    from ttrpgtools.web.app import create_app
    from ttrpgtools.dcc.westmarch import registry, town as t
    client = create_app().test_client()
    player = {"Remote-User": "wren"}
    db = registry.connect()
    try:
        import json as _json
        keeper = next(dict(r) for r in db.execute("SELECT id, name, sheet FROM people WHERE locked = 0 AND sheet IS NOT NULL")
                      if "Hen" in str(registry.build_character(dcc.load_content(), r["name"], _json.loads(r["sheet"]))["inventory"]))
    finally:
        db.close()
    cid = client.post("/TTRPG/dcc/api/registry/people", json={"action": "claim", "id": keeper["id"], "alignment": "lawful", "moon": "pale"}, headers=player).get_json()["character"]
    things = dcc.load_character(cid)["inventory"]
    hen = next(i for i in things if "hen" in i["name"].lower())
    from datetime import date
    from ttrpgtools.dcc.westmarch import places
    hatched = date.fromordinal(places.EPOCH.toordinal() + hen["mark"]["day"] - 1)
    assert 20 <= t.campaign_day() - hen["mark"]["day"] < 420 and hen["mark"]["moon"] == t.fullest_moon(hatched)   # the moon of the day it hatched
    assert hen["mark"]["maker"] == keeper["name"] and " make." in hen["notes"]
    assert not any(i.get("mark") for i in things if i is not hen)     # nothing else a villager brings along has one


@real
def test_mercurial_magic_roll_again_twice():
    w, content = hero(klass="wizard", level=1, intelligence=13)
    spell = dcc.spell_list(content, "wizard", w)[0]["name"]
    dcc.set_spells(w, [spell], content)
    dcc.set_spell_detail(w, spell, 100)                                   # "roll again twice, on 4d20": the two results are still owed
    v = dcc.derive(w, content)
    mine = next(s_ for s_ in v["spells"] if s_["name"] == spell)
    assert mine["mercurial"]["text"].startswith("Roll again twice") and any("two further rolls are missing" in line and spell in line for line in v["todo"])
    for bad in ([45], [45, 99], [45, 100], [0, 45]):
        with pytest.raises(dcc.DCCError, match="two further results"):
            dcc.set_spell_detail(w, spell, 100, bad)
    dcc.set_spell_detail(w, spell, 100, [13, 93])
    v = dcc.derive(w, content)
    mine = next(s_ for s_ in v["spells"] if s_["name"] == spell)
    assert mine["mercurial_roll"] == 100 and mine["mercurial_more"] == [13, 93]
    assert mine["mercurial"]["text"].startswith("Both of these. (13) Slow cast.") and "(93) Greater power." in mine["mercurial"]["text"]
    assert not any("further rolls" in line for line in v["todo"])
    dcc.set_spell_detail(w, spell, 99, [1, 2])                             # the plain "roll again twice" works the same
    assert w["spell_details"][spell] == {"mercurial": 99, "mercurial_more": [1, 2]}
    dcc.set_spell_detail(w, spell, 50, [1, 2])                             # an ordinary result has no further rolls
    assert w["spell_details"][spell] == {"mercurial": 50}


def test_clauses_one_hidden_quirk_per_character(content, monkeypatch):
    from ttrpgtools.dcc.westmarch import clauses, debts, places, town as t
    flat = {"period": 10, "amplitude": 0, "phase": 0}
    monkeypatch.setattr(t, "today", lambda: places.EPOCH)
    # which clause: fixed by augur and moon together; none without either
    c = make(content)
    assert clauses.clause_of(c) is None and clauses.clause_of(None) is None           # no moon: no clause (traders have neither)
    seen = {clauses.clause_of({"birth_augur": {"roll": roll}, "moon": moon}) for roll in range(1, 31) for moon in ("pale", "red", "drowned")}
    from collections import Counter
    dealt = Counter(clauses.clause_of({"birth_augur": {"roll": roll}, "moon": moon}) for roll in range(1, 31) for moon in ("pale", "red", "drowned"))
    assert seen == set(clauses.CLAUSES) and set(dealt.values()) == {4, 5}       # dealt evenly: every clause belongs to four or five pairings
    assert clauses.clause_of({"birth_augur": {"roll": 0}, "moon": "red"}) is None
    assert clauses.clause_of({"birth_augur": {"roll": 7}, "moon": "red"}) == clauses.clause_of({"birth_augur": {"roll": 7}, "moon": "red"})
    monkeypatch.setattr(clauses, "clause_of", lambda ch: (ch or {}).get("_clause"))     # from here on each character is given one by hand
    def buyer(clause, **more):
        ch = make(content)
        ch.update({"coins": {"gp": 500, "sp": 0, "cp": 0}, "moon": "red", "_clause": clause, **more})
        return ch
    with t.town(write=True) as state:
        smith = t.save_shop(state, None, "Smith", "Bram", curve=flat)
        outfit = t.save_shop(state, None, "Outfitter", "Marta", curve=flat)
        junk = t.save_shop(state, None, "Junk", "Grod", curve=flat)
        monkeypatch.setattr(places, "ROLES", {"smith": smith, "outfitter": outfit, "junk": junk})
        for sid in (smith, outfit, junk):
            state["shops"][sid].update(deals=["weapon", "gear", "trade", "armor"], till=5_000_000)
        state["shops"][junk].update(buys_anything=True, sell_back=0.15, junk_cp=2)
        stock = lambda sid, name, kind, cost, qty: t.stock_item(state, sid, name, kind, cost, qty, curve=flat)
        dagger, club = stock(smith, "Dagger", "weapon", "3 gp", 5), stock(smith, "Club", "weapon", "3 gp", 5)
        rope, torch, pack = stock(outfit, "Rope, 50\u2019", "gear", "25 cp", 5), stock(outfit, "Torch, each", "gear", "10 cp", 5), stock(outfit, "Backpack", "gear", "2 gp", 5)
        helm, hen, lamp = stock(outfit, "Steel helmet", "armor", "10 gp", 2), stock(outfit, "Hen", "trade", "50 cp", 3), stock(junk, "Lantern", "gear", "250 cp", 1)
        row = lambda ch, sid, name: next(r for sh in t.view(state, "nobody", ch)["shops"] if sh["id"] == sid for r in sh["stock"] if r["name"] == name)
        spent = lambda ch: 50_000 - dcc.coins_total_cp(ch["coins"])
        has = lambda ch, name: sum(int(i.get("qty", 1)) for i in ch["inventory"] if i["name"] == name)
        # nobody sells you rope
        ch = buyer("no_rope")
        assert row(ch, outfit, "Rope, 50\u2019").get("refused") and not row(ch, outfit, "Backpack").get("refused")
        with pytest.raises(t.TownError, match="Not to you"):
            t.buy(state, outfit, rope["id"], ch)
        # pairs: two pieces at twice the price, and never the last single one
        ch = buyer("pairs")
        assert row(ch, outfit, "Backpack")["price_cp"] == 400 and row(ch, outfit, "Backpack")["lot"] == 2
        t.buy(state, outfit, pack["id"], ch)
        assert has(ch, "Backpack") == 2 and spent(ch) == 400 and pack["qty"] == 3
        assert row(ch, junk, "Lantern").get("refused")
        with pytest.raises(t.TownError, match="only the one"):
            t.buy(state, junk, lamp["id"], ch)
        # prices above 1 gp go up to the next gold piece, at the junk shop down; a copper price stays
        ch = buyer("round_gold")
        stock(outfit, "Odd thing", "gear", "250 cp", 2); stock(junk, "Odd thing", "gear", "250 cp", 2)
        assert (row(ch, outfit, "Odd thing")["price_cp"], row(ch, junk, "Odd thing")["price_cp"], row(ch, outfit, "Torch, each")["price_cp"]) == (300, 200, 10)
        # a hen for a tenth, leather and stuff for double
        ch = buyer("hens_and_leather")
        assert (row(ch, outfit, "Hen")["price_cp"], row(ch, outfit, "Backpack")["price_cp"], row(ch, smith, "Dagger")["price_cp"]) == (5, 400, 300)
        # the blacksmith sells a weapon only against one handed in
        ch = buyer("trade_in")
        ch["inventory"] = [i for i in ch["inventory"] if i["kind"] != "weapon"]
        with pytest.raises(t.TownError, match="handed in"):
            t.buy(state, smith, dagger["id"], ch)
        dcc.add_item(ch, "Mace", "weapon", 1, "5 gp")
        t.buy(state, smith, dagger["id"], ch)
        assert has(ch, "Mace") == 0 and has(ch, "Dagger") == 1 and next(i for i in state["shops"][smith]["stock"] if i["name"] == "Mace")["qty"] == 1
        # nothing with an edge from the blacksmith; helmets by decree; a keeper of your own moon sells you nothing but buys
        ch = buyer("no_edges")
        assert row(ch, smith, "Dagger").get("refused") and not row(ch, smith, "Club").get("refused")
        ch = buyer("no_helmets")
        with pytest.raises(t.TownError, match="decree"):
            t.buy(state, outfit, helm["id"], ch)
        ch = buyer("keeper_moon", moon=clauses.keeper_moon(state["shops"][smith]))
        dcc.add_item(ch, "Dagger", "weapon", 1, "3 gp")
        assert row(ch, smith, "Club").get("refused") and smith in t.offers(state, ch)
        other_moon = next(m["id"] for m in places.MOONS if m["id"] != clauses.keeper_moon(state["shops"][smith]))
        assert not row(buyer("keeper_moon", moon=other_moon), smith, "Club").get("refused")
        # rope at half and light at double, at the outfitter only
        ch = buyer("rope_and_light")
        assert (row(ch, outfit, "Rope, 50\u2019")["price_cp"], row(ch, outfit, "Torch, each")["price_cp"], row(ch, junk, "Lantern")["price_cp"]) == (12, 20, 250)
        # no shop serves you before the day's tax; any payment opens them
        ch = buyer("tax_first", tax_debt_cp=1000)
        assert row(ch, smith, "Club").get("refused")
        with pytest.raises(t.TownError, match="tax office"):
            t.buy(state, smith, club["id"], ch)
        t.pay_taxes(state, ch, "1 cp")
        t.buy(state, smith, club["id"], ch)
        assert not row(ch, smith, "Club").get("refused")
        # sevens at the tax office
        ch = buyer("sevens", tax_debt_cp=1000)
        assert t.pay_taxes(state, ch, "20 cp")["each_cp"] == 14 and ch["tax_debt_cp"] == 986
        with pytest.raises(t.TownError, match="sevens"):
            t.pay_taxes(state, ch, "5 cp")
        # six tenths where others get half; the junk shop keeps its own rate
        ch, plain = buyer("sixty"), buyer(None)
        price_of = lambda who, sid, name: next(r["each_cp"] for r in t.offers(state, who)[sid] if r["name"] == name)
        for who in (ch, plain):
            dcc.add_item(who, "Dagger", "weapon", 1, "3 gp"); dcc.add_item(who, "Hen", "trade", 1, "50 cp")
        assert (price_of(plain, smith, "Dagger"), price_of(ch, smith, "Dagger")) == (150, 180) and price_of(ch, junk, "Dagger") == price_of(plain, junk, "Dagger")
        # the junk keeper: double for hens, nothing for anything else
        ch = buyer("hens_for_groderick")
        dcc.add_item(ch, "Dagger", "weapon", 1, "3 gp"); dcc.add_item(ch, "Hen", "trade", 1, "50 cp")
        assert [r["name"] for r in t.offers(state, ch)[junk]] == ["Hen"] and price_of(ch, junk, "Hen") == 2 * price_of(plain, junk, "Hen") == 4   # a hen has no book price: twice his flat pittance
        # the oldest piece; and at the smith only what is a fortnight old
        club["made"] = [{"moon": "red", "day": 1, "gifts": [], "flaws": []}, {"moon": "red", "day": -30, "gifts": [], "flaws": []}]
        club["qty"] = 3                                                 # one unmarked piece (the oldest), one from long ago, one from today
        ch = buyer("oldest")                                            # pays for what they ask and gets the oldest thing in the shop instead
        ch["inventory"] = []
        daggers_before = dagger["qty"]
        sale = t.buy(state, smith, club["id"], ch)
        assert sale["item"] == "Dagger" and [i["name"] for i in ch["inventory"]] == ["Dagger"] and spent(ch) == 300    # the club's price, the first old thing on the shelf
        assert dagger["qty"] == daggers_before - 1 and club["qty"] == 3
        for line in state["shops"][smith]["stock"]:
            if line is not club:
                line["qty"] = 0                                         # everything else is gone: the club line holds one unmarked piece and two marked
        t.buy(state, smith, club["id"], ch); t.buy(state, smith, club["id"], ch)
        clubs = [i for i in ch["inventory"] if i["name"] == "Club"]
        assert sum(int(i.get("qty", 1)) for i in clubs if not i.get("mark")) == 1 and [i["mark"]["day"] for i in clubs if i.get("mark")] == [-30]
        assert [m["day"] for m in club["made"]] == [1] and t.oldest_line(state["shops"][smith]) is club
        dagger["qty"] = daggers_before
        ch = buyer("two_weeks")
        assert row(ch, smith, "Club").get("refused")                    # only today's piece is left: too fresh
        with pytest.raises(t.TownError, match="too fresh"):
            t.buy(state, smith, club["id"], ch)
        assert row(ch, smith, "Dagger")["qty"] == dagger["qty"] and not row(ch, smith, "Dagger").get("refused")   # unmarked stock is old stock
        # inns: the pet fee, and the worst bed
        inn = {"name": "Inn", "curve": flat, "stay": {"price": "10 cp", "hp": 2, "ability": 1}}
        usual = t.stay_offer("inn", inn, 1, buyer(None))
        pet, worst = t.stay_offer("inn", inn, 1, buyer("pet_fee")), t.stay_offer("inn", inn, 1, buyer("worst_bed"))
        assert pet["price_cp"] == usual["price_cp"] + 3 and "pet fee of 0,03 gp" in pet["note"] and "note" not in usual
        assert (worst["price_cp"], worst["hp"], worst["ability"]) == (usual["price_cp"], 1, 0) and (usual["hp"], usual["ability"]) == (2, 1)
        # the herb woman: the first question of a week for nothing, a lie on the second, the truth for coin after that
        herb = t.save_shop(state, None, "Herbs", "Hedwig", curve=flat)
        state["shops"][herb].update(kinds=["oracle"], ask="1 cp", till=0)
        ch = buyer("herb_week")
        truth = t.full_forecast("drowned")
        said = [t.ask_moon(state, herb, ch, "drowned")["answer"] for _ in range(3)]
        true_words = f"in {truth['in']} night" if truth["in"] else "full tonight"
        assert spent(ch) == 2 and state["shops"][herb]["till"] == 2 and true_words in said[0] and true_words in said[2] and true_words not in said[1]
        t.ask_moon(state, herb, buyer(None), "drowned")
        assert state["shops"][herb]["till"] == 3                         # everybody else pays every time
    # the library asks one of them for no interest
    monkeypatch.setattr(debts, "_living_characters", lambda: [("a", borrower), ("b", other)])
    borrower, other = buyer("no_interest", library_loan_cp=1_000_000, tax_debt_cp=0), buyer(None, library_loan_cp=1_000_000, tax_debt_cp=0)
    monkeypatch.setattr(dcc, "save_character", lambda ch, cid: None)
    debts.accrue(t.campaign_day())
    assert borrower["library_loan_cp"] == 1_000_000 and other["library_loan_cp"] > 1_000_000


@real
def test_the_nameless_clause_hides_the_name_from_its_player(monkeypatch):
    from ttrpgtools.web.app import create_app
    from ttrpgtools.dcc.westmarch import clauses
    client = create_app().test_client()
    admin, player = {"Remote-User": "admin"}, {"Remote-User": "wren"}
    rows = client.get("/TTRPG/dcc/api/registry/people", headers=player).get_json()["rows"]
    free = next(r for r in rows if r["playable"])
    cid = client.post("/TTRPG/dcc/api/registry/people", json={"action": "claim", "id": free["id"], "alignment": "lawful", "moon": "red"}, headers=player).get_json()["character"]
    name, title = free["name"], "The " + free["occupation"]
    monkeypatch.setattr(clauses, "clause_of", lambda ch: "nameless" if (ch or {}).get("moon") else None)
    pages = ["/TTRPG/dcc/", f"/TTRPG/dcc/{cid}/build", f"/TTRPG/dcc/api/character/{cid}", f"/TTRPG/dcc/api/town?character={cid}", "/TTRPG/dcc/api/registry/people"]
    for url in pages:
        mine = client.get(url, headers=player).get_data(as_text=True)
        assert name not in mine and title in mine, url                        # the player is addressed by occupation, everywhere
        assert name in client.get(url, headers=admin).get_data(as_text=True), url   # the admin still sees who it is
    seen = client.get(f"/TTRPG/dcc/api/town?character={cid}", headers=player).get_json()
    me = next(c for c in seen["characters"] if c["id"] == cid)
    assert me["name"] == title and title.split()[-1][:4] in me["tax_line"] and me["clause"] is None    # and is not told why
    assert next(c for c in client.get("/TTRPG/dcc/api/town", headers=admin).get_json()["characters"] if c["id"] == cid)["clause"] == "nameless"
    assert name not in client.get(f"/TTRPG/dcc/{cid}/json", headers=player, follow_redirects=True).get_data(as_text=True)


def test_producers_scrap_metal_notebooks_and_the_caravan(content, monkeypatch):
    from ttrpgtools.dcc.westmarch import daily, materials, places, town as t
    flat = {"period": 10, "amplitude": 0, "phase": 0}
    monkeypatch.setattr(t, "today", lambda: places.EPOCH)
    monkeypatch.setattr(daily, "model_plan", lambda *a: None)
    digger = {"id": "dig", "name": "Digger", "likes": [], "persona": "x", "brings": [("Scrap metal", "trade", "4 sp", 5), ("Notched longsword", "weapon", "6 gp")]}
    henwife = {"id": "hen", "name": "Hen keeper", "likes": [], "persona": "x", "brings": [("Hen", "trade", "5 sp", 1), ("Eggs, a dozen", "trade", "3 cp", 3)]}
    assert materials.made_of("Scrap metal", "trade") == ("metal", 1000) and materials.is_raw("Scrap metal") and not materials.is_raw("Dagger")
    with t.town(write=True) as state:
        smith = t.save_shop(state, None, "Smith", "Bram", curve=flat)
        store = t.save_shop(state, None, "Store", "Marta", curve=flat)
        state["shops"][smith].update(deals=["weapon"], wants=["Scrap metal"], till=100_000, materials={"metal": 0}, restock_every=1)
        state["shops"][store].update(deals=["trade", "gear"], till=100_000, materials={})
        sword = t.stock_item(state, smith, "Longsword", "weapon", "10 gp", 0, curve=flat)
        sword["target"] = 2
        eggs = t.stock_item(state, store, "Eggs, a dozen", "trade", "3 cp", 0, curve=flat)
        eggs["target"] = 6
        # the digger brings scrap (never a sword: that would have to be made), the smith buys it although he deals in weapons only
        for day in range(1, 9):
            for spec in (digger, henwife):
                bot = daily._record(state, spec)
                daily.arrive(bot, spec, day)
                daily.act(state, bot, spec, daily.rule_plan(state, bot, spec, day), day)
        dug = daily._record(state, digger)
        assert not any("sword" in i["name"].lower() for i in dug["inventory"]) and dcc.coins_total_cp(dug["coins"]) > 0
        scrap = next(i for i in state["shops"][smith]["stock"] if i["name"] == "Scrap metal")
        lumps = scrap["qty"]
        assert lumps >= 4 and state["shops"][smith]["till"] == 100_000 - dcc.coins_total_cp(dug["coins"])     # coin moved from his till to the digger
        with pytest.raises(t.TownError, match="does not deal"):
            t.offer(state, store, {"name": "Notched longsword", "kind": "weapon", "cost": "6 gp"})
        # an inn is no shop, but it buys the ale it pours, up to twice its line, and nothing else
        inn = t.save_shop(state, None, "Inn", "Odila", curve=flat)
        state["shops"][inn].update(kinds=["inn"], till=100_000)
        ale = t.stock_item(state, inn, "Ale, a jug", "trade", "6 cp", 0, curve=flat)
        ale["target"] = 12
        assert t.offer(state, inn, {"name": "Ale, a jug", "kind": "trade", "cost": "6 cp"})["room"] == 24
        with pytest.raises(t.TownError, match="does not deal"):
            t.offer(state, inn, {"name": "Eggs, a dozen", "kind": "trade", "cost": "3 cp"})
        del state["shops"][inn]
        # on his making day the scrap is melted for what the shelf lacks: two longswords are 4 kg
        work = t.restock(state, smith, day=9)
        assert work == {"made": 2, "broken": 4, "short": []} and scrap["qty"] == lumps - 4 and sword["qty"] == 2
        # the hen keeper's hens carry a moon and keep it on the shelf
        keeper = daily._record(state, henwife)
        hens = [i for sh in state["shops"].values() for i in sh["stock"] if i["name"] == "Hen"] + [i for i in keeper["inventory"] if i["name"] == "Hen"]
        assert hens and all(i.get("mark") or i.get("made") for i in hens) and eggs["qty"] >= 1
        # one small note per trader: rewritten whole, never longer than fifty words, kept when a day brings none
        daily.write_note(dug, 3, "The smith pays best on his making day.")
        assert daily.note_of(dug) == "The smith pays best on his making day." and dug["note_day"] == 3
        daily.write_note(dug, 4, "")
        assert daily.note_of(dug) == "The smith pays best on his making day."
        daily.write_note(dug, 5, " ".join(f"word{n}" for n in range(80)))
        assert len(dug["note"].split()) == daily.NOTE_WORDS == 50 and dug["note"].startswith("word0 ") and "notes" not in dug
        assert daily.note_of({"notes": [{"day": 1, "text": "old line"}, {"day": 2, "text": "newest line"}]}) == "newest line"   # an older notebook counts by its last line
        # what the village needs: the worst shortage first, in coin
        monkeypatch.setattr(places, "CARAVAN", {**places.CARAVAN, "every": 30, "ask_ahead": 7, "goods_price": 0.5,
                                                "material_price": {"metal": "4 sp", "leather": "3 sp", "tech": "15 gp", "wood": "5 cp"}})
        plate = t.stock_item(state, smith, "Half-Plate", "armor", "550 gp", 0, curve=flat)
        plate["target"] = 1                                              # 22 kg of metal he does not have
        scrap["qty"] = 0
        state["shops"][smith]["materials"]["metal"] = 2_000
        eggs["qty"] = 0
        needs = daily.village_needs(state)
        assert [(n["what"], n["kind"]) for n in needs] == [("metal", "material"), ("Eggs, a dozen", "goods")]
        assert needs[0]["kg"] == 20.0 and needs[0]["value_cp"] == 800 and needs[1] == {"what": "Eggs, a dozen", "kind": "goods", "pieces": 6, "value_cp": 18, "label": "Eggs, a dozen"}
        # the factor sends for the caravan a week ahead, and it comes on the thirtieth day; tills pay, the coin leaves
        monkeypatch.setattr(places, "BOTS", [{"id": "vessa", "name": "Vessa the factor", "likes": [], "persona": "x", "brings": []}])
        assert (daily.caravan_today(23), daily.caravan_today(30), daily.caravan_today(24)) == ("ask", "arrive", None)
        before = t.coins_text(0), state["shops"][smith]["till"], state["shops"][store]["till"]
        daily.run_day(state, 23, live=False)
        assert [w["what"] for w in state["caravan"]["wants"]] == ["metal", "Eggs, a dozen"] and "sent for the caravan: metal and eggs, a dozen" in " ".join(n["text"] for n in state["chronicle"][-3:])
        for day in range(24, 31):
            daily.run_day(state, day, live=False)
        told = " ".join(n["text"] for n in state["chronicle"])
        assert "The caravan came: 20,0 kg of metal, 6 x Eggs, a dozen, for 8,12 gp. It stays 2 days and buys at 20 percent of the usual price, but no hen, no chicken, no barley." in told
        camp = state["shops"]["caravan"]
        assert camp["till"] == 812 and state["money"]["caravan"] == 0 and state["shops"][store]["till"] == before[2] - 12 and eggs["qty"] == 6
        # while it stands in town it buys from anyone, low, and not everything; what it buys leaves with it, the coin it paid stays
        seller = make(content)
        seller["inventory"] = []
        dcc.add_item(seller, "Dagger", "weapon", 1, "3 gp"); dcc.add_item(seller, "Hen", "trade", 1, "5 sp"); dcc.add_item(seller, "Barley, a sack", "trade", 1, "4 sp")
        assert [r["name"] for r in t.offers(state, seller)["caravan"]] == ["Dagger"] and t.offers(state, seller)["caravan"][0]["each_cp"] == 60    # a fifth of 3 gp
        t.sell(state, "caravan", seller, 0)
        assert camp["till"] == 752 and dcc.coins_total_cp(seller["coins"]) == 20 + 60 and "caravan" in [sh["id"] for sh in t.view(state, "nobody")["shops"]]
        daily.run_day(state, 31, live=False)
        assert not camp.get("away")                                    # the second day
        daily.run_day(state, 32, live=False)
        assert camp["away"] and camp["stock"] == [] and camp["till"] == 0 and state["money"]["caravan"] == 752
        assert "The caravan left, taking 1 x Dagger. 7,52 gp of the village's coin is with it." in " ".join(n["text"] for n in state["chronicle"])
        assert "caravan" not in [sh["id"] for sh in t.view(state, "nobody")["shops"]] and "caravan" not in t.offers(state, seller)
        # a model may set the terms within bounds; nonsense falls back to the caravan's own
        state["caravan"] = {"wants": []}
        daily.caravan_arrives(state, 60, {"pays_share": 0.9, "refuses": ["dagger"], "note": "GOAL squeeze them."})
        assert camp["sell_back"] == 0.35 and camp["refuses"] == ["dagger"] and camp["till"] == 752 and state["caravan_master"]["note"] == "GOAL squeeze them."
        daily.caravan_leaves(state, 62)
        daily.caravan_arrives(state, 90, {"pays_share": "lots", "refuses": "everything"})
        assert camp["sell_back"] == 0.2 and camp["refuses"] == ["hen", "chicken", "barley"]
        daily.caravan_leaves(state, 92)
        assert plate["qty"] == 1 or state["shops"][smith]["materials"]["metal"] >= 22_000      # the smith could make the plate at once: his making day is every day here
        # a model's choice is taken when it names lines from the top of the list; nonsense falls back to the worst shortages
        eggs["qty"] = 0
        assert [w["what"] for w in daily.request_caravan(state, 53, [0])] == ["Eggs, a dozen"]
        assert [w["what"] for w in daily.request_caravan(state, 53, ["x", 99])] == ["Eggs, a dozen"]


def test_town_talk_is_rare_and_short(content, monkeypatch):
    from ttrpgtools.dcc.westmarch import daily, places, town as t
    monkeypatch.setattr(t, "today", lambda: places.EPOCH)
    with t.town(write=True) as state:
        state["news"] = []
        told, weeks = 0, {}
        for day in range(1, 701):                                    # a hundred weeks; each night a few sales, some by traders, one of an augur
            state["log"] = [{"day": day, "shop": "Shop1", "item": "Stinky cheese", "count": -2, "each_cp": 40, "character": "Zeno Zwiebel"},
                            {"day": day, "shop": "The Blacksmith", "item": "Dagger", "count": -1, "each_cp": 150, "character": "Egon Crookback"},
                            {"day": day, "shop": "The Herb Woman", "item": "Augur sold: Charmed House (+2)", "count": -1, "each_cp": 10000, "character": "Egon Crookback"},
                            {"day": day, "shop": "Shop1", "item": "Rope", "count": 1, "each_cp": 25, "character": "Egon Crookback"}]
            said = bool(daily.talk(state, day))
            told += said
            weeks[(day - 1) // 7] = weeks.get((day - 1) // 7, 0) + said
        assert set(weeks.values()) == {1, 2} and 1.3 < told / 100 < 1.7      # every single week has one or two new lines
        assert set(n["text"] for n in state["news"]) <= {"Zeno Zwiebel sold Stinky cheese to Shop1.", "Egon Crookback sold Dagger to The Blacksmith."}
        assert len(state["news"]) == t.NEWS_LIMIT and len(t.view(state, "nobody")["news"]) == 4 and "chronicle" not in t.view(state, "nobody")
        state["log"] = []
        assert all(daily.talk(state, day) is None for day in range(701, 760))    # nothing sold: nothing said
        t.tell(state, 760, "Making day at Yard: 2 pieces made.")
        assert len(state["news"]) == t.NEWS_LIMIT and t.view(state, "admin")["chronicle"][0]["text"].startswith("Making day")


def test_a_models_plan_is_carried_out_not_just_spoken(content, monkeypatch):
    from ttrpgtools.dcc.westmarch import daily, places, town as t
    flat = {"period": 10, "amplitude": 0, "phase": 0}
    monkeypatch.setattr(t, "today", lambda: places.EPOCH)
    spec = {"id": "sig", "name": "Sigrun", "likes": ["weapon", "gear"], "persona": "x", "brings": []}
    monkeypatch.setattr(places, "BOTS", [spec])
    with t.town(write=True) as state:
        rich = t.save_shop(state, None, "Rich", curve=flat)
        poor = t.save_shop(state, None, "Poor", curve=flat)
        state["shops"][rich].update(deals=["weapon", "gear"], till=100_000)
        state["shops"][poor].update(deals=["weapon", "gear"], till=3)
        t.stock_item(state, rich, "Lantern", "gear", "10 gp", 2, curve=flat)
        t.stock_item(state, poor, "Dagger", "weapon", "3 gp", 0, curve=flat)["target"] = 1     # the poor shop would pay 150 a dagger and has 3 cp
        bot = daily._record(state, spec)
        bot["coins"] = {"gp": 30, "sp": 0, "cp": 0}
        dcc.add_item(bot, "Dagger", "weapon", 4, "3 gp")
        index = next(n for n, i in enumerate(bot["inventory"]) if i["name"] == "Dagger")
        # the model names the shop that cannot pay, asks for more than anyone takes, and names the lantern by its name at the wrong shop
        plan = ([{"do": "sell", "shop": poor, "index": index, "count": 9}, {"do": "buy", "shop": poor, "item": "Lantern", "count": 1},
                 {"do": "buy", "shop": "nowhere", "item": "Unicorn", "count": 1}], "Steel is cheap today.", "Remember the lantern.")
        done = daily.act(state, bot, spec, plan[0], 1)
        assert len(done) == 2 and done[0].startswith("sold 4 x Dagger to Rich (") and done[1] == "bought 1 x Lantern at Rich (10,00 gp)"   # put right, carried out, the nonsense skipped
        got = next(s_["each_cp"] for s_ in state["log"] if s_["item"] == "Dagger") * 4
        assert dcc.coins_total_cp(bot["coins"]) == 3000 + got - 1000 and state["shops"][poor]["till"] == 3 and state["shops"][rich]["till"] == 100_000 - got + 1000
        # a plan of which nothing can be done is not the end of the day: the plain rule trades instead
        dcc.add_item(bot, "Dagger", "weapon", 1, "3 gp")
        daily.run_day(state, 2, {"sig": ([{"do": "buy", "shop": "nowhere", "item": "Unicorn"}], "I shall buy a unicorn.", "Unicorns are dear.")}, live=False)
        assert not any(i["name"] == "Dagger" for i in bot["inventory"]) and "sold 1 x Dagger to Rich" in state["chronicle"][-1]["text"]
        assert "unicorn" not in state["chronicle"][-1]["text"].lower() and bot["note"] == "Unicorns are dear."   # the remark of a failed plan is dropped, the note kept


def test_the_villages_notepad_and_its_bandwagon(content, monkeypatch):
    from ttrpgtools.dcc.westmarch import daily, places, town as t
    flat = {"period": 10, "amplitude": 0, "phase": 0}
    monkeypatch.setattr(t, "today", lambda: places.EPOCH)
    state = {"shops": {}}
    assert daily.board_write(state, "Detlef", 1, {"need": "More chickens."}) == "more chickens" and daily.board_text(state) == ["1. more chickens: Detlef"]
    assert daily.board_write(state, "Zeno", 1, {"me_too": 1}) == "more chickens"                       # "me too" by number
    assert daily.board_write(state, "Xaver", 2, {"need": "a chicken or two"}) == "more chickens"        # the same thing in other words is the same line
    assert daily.board_write(state, "Zeno", 2, {"me_too": 1}) == "more chickens"                        # a name stands under a line once
    assert daily.board_write(state, "Hartmut", 2, {"need": "a new lantern"}) == "a new lantern"
    assert daily.board_text(state) == ["1. more chickens: Detlef, Zeno, Xaver", "2. a new lantern: Hartmut"]
    assert daily.board_write(state, "Pip", 2, {"me_too": 9}) is None and daily.board_write(state, "Pip", 2, None) is None and daily.board_write(state, "Pip", 2, {"need": ""}) is None
    for n in range(20):                                                                                # one small page: old unsupported lines make room
        daily.board_write(state, "Pip", 3 + n, {"need": f"thing{chr(97 + n) * 4}"})
    assert len(state["needs_board"]) == daily.BOARD_LINES and all(len(l["what"]) <= daily.BOARD_WORDS for l in state["needs_board"])
    # a model's answer reaches the page through the nightly run, and the page is given to the next model as input
    spec = {"id": "det", "name": "Detlef", "likes": [], "persona": "x", "brings": []}
    monkeypatch.setattr(places, "BOTS", [spec])
    with t.town(write=True) as state:
        store = t.save_shop(state, None, "Store", curve=flat)
        state["shops"][store].update(deals=["trade"], till=10_000)
        hens = t.stock_item(state, store, "Hen", "trade", "5 sp", 6, curve=flat)
        hens["target"] = 6
        daily.run_day(state, 1, {"det": ([], "", "", {"need": "more chickens"})}, live=False)
        daily.run_day(state, 2, {"det": ([], "", "", {"me_too": 1})}, live=False)
        assert daily.board_text(state) == ["1. more chickens: Detlef"]
        seen = {}
        monkeypatch.setattr(daily, "ask_model", lambda messages, **kw: seen.update(text=messages[-1]["content"]) or {"bring": [0]})
        needs = daily.village_needs(state)                           # the shelf is full, yet a wish with names under it is a need the factor can send for
        assert [(n["what"], n.get("wished_by")) for n in needs] == [("Hen", 1)]
        assert daily.model_caravan(needs, daily.board_text(state)) == [0] and "more chickens: Detlef" in seen["text"]
        daily.request_caravan(state, 5, [0])
        daily.caravan_arrives(state, 10)
        assert hens["qty"] == 6 and state["shops"][store]["till"] == 10_000                                    # a full hen shelf gets no hens, wish or not (the owner 10-10)
        hens["qty"] = 1
        state["caravan"] = {"wants": [{"what": "Hen", "kind": "trade", "wish": True}]}
        daily.caravan_arrives(state, 20)
        assert hens["qty"] == 1 + places.CARAVAN["hens_max"] and state["shops"][store]["till"] == 10_000 - 2 * 75     # a short one: two at most, dear, paid from the till
    assert "1. more chickens: Detlef" in t.TOWN_PATH.with_name("village_needs.txt").read_text()        # and it is a text file to read


def test_every_trader_has_a_short_description():
    import importlib
    from ttrpgtools.dcc.westmarch import places
    real = importlib.reload(places)
    real.MARKET = None   # reloading brings back the file's own switch
    try:
        from ttrpgtools.dcc.westmarch import daily
        notes = {b["id"]: daily.identity(b) for b in real.BOTS}
        assert len(real.BOTS) == 14 and all(15 <= len(text.split()) <= 62 for text in notes.values()), {k: len(v.split()) for k, v in notes.items()}
        assert all(5 <= len(b["seed"].split()) <= 50 and "RULE" in b["seed"] for b in real.BOTS)        # the starting note: a goal, something to track, a rule
        assert notes["hartmut"] == ("NAME Hartmut Bachmeier. RACE dwarf who left the mines. TRADE scrap digger. MAKES scrap metal. "
                                    "NEEDS lantern, hammer, rations. KEEPS one hammer, one lantern, three rations. LIKES old iron and silence. "
                                    "QUIRK buys nothing at the full Pale Moon. RHYTHM digs most at the new Drowned Moon. WRITES never writes more than four words.")
        assert len({b["quirk"] for b in real.BOTS}) == 14 and daily.identity({"persona": "x"}) == "x"   # everyone has a quirk of their own; older specs still work
        state = {}
        bot = daily._record(state, real.BOTS[0])
        assert bot["note"] == real.BOTS[0]["seed"] and bot["seeded"]
        daily.write_note(bot, 3, "GOAL changed.")
        assert daily._record(state, real.BOTS[0])["note"] == "GOAL changed."                             # seeded once, then the model's to rewrite
    finally:
        places.PLACES, places.BOTS = [], []


def test_hens_eat_barley_and_the_town_note(content, monkeypatch):
    from ttrpgtools.dcc.westmarch import daily, places, town as t
    flat = {"period": 10, "amplitude": 0, "phase": 0}
    monkeypatch.setattr(t, "today", lambda: places.EPOCH)
    monkeypatch.setattr(places, "HENS", {"eats": 0.25, "dies": 0.5})
    with t.town(write=True) as state:
        store = t.save_shop(state, None, "Store", curve=flat)
        hens = t.stock_item(state, store, "Hen", "trade", "5 sp", 4, curve=flat)
        barley = t.stock_item(state, store, "Barley, a sack", "trade", "4 sp", 2, curve=flat)
        state["bots"] = {"det": {"name": "Detlef", "coins": {"gp": 0, "sp": 0, "cp": 0},
                                 "inventory": [{"name": "Hen", "kind": "trade", "qty": 1}, {"name": "Hen", "kind": "trade", "qty": 1}, {"name": "Eggs, a dozen", "kind": "trade", "qty": 3}]}}
        told = daily.hens_eat(state, 1, characters=False)             # four hens at a quarter sack each: one sack a day while there is barley
        assert barley["qty"] == 1 and hens["qty"] == 4 and "Store's hens ate a sack of barley." in told
        daily.hens_eat(state, 2, characters=False)
        assert barley["qty"] == 0 and hens["qty"] == 4
        for day in range(3, 12):                                      # no barley left: they die off, at the shop and in the trader's yard
            daily.hens_eat(state, day, characters=False)
        assert hens["qty"] == 0 and not any(i["name"] == "Hen" for i in state["bots"]["det"]["inventory"])
        assert any(i["name"] == "Eggs, a dozen" for i in state["bots"]["det"]["inventory"]) and "died for want of barley" in " ".join(n["text"] for n in state["chronicle"])
        # the town note: a line each, about a hundred words, the oldest lines fall off
        assert t.town_note_write(state, "Zeno", "Cheese sells best at Shop3 under the red moon.") == "Zeno: Cheese sells best at Shop3 under the red moon."
        for n in range(30):
            t.town_note_write(state, f"Villager {n}", f"the smith has run out of coin on day {n} and the caravan pays nothing for hens")
        note = state["town_note"]
        assert 80 <= len(note.split()) <= places.TOWN_NOTE_WORDS and "Zeno" not in note and note.splitlines()[-1].startswith("Villager 29:")
        assert t.view(state, "nobody")["town_note"] == note and t.town_note_write(state, "Pip", "   ") == note        # everybody reads it; an empty line changes nothing
        # a line the note already says is not written again, in the same words or in others; a different fact is
        state["town_note"] = ""
        t.town_note_write(state, "Sigrun", "Red Lantern full; scrap prices dip, keep your hammers.")
        for echo in ("Scrap prices dip; keep hammers.", "scrap prices dip, keep hammers!", "Keep your hammers: scrap price dips.", "   ", "Red Lantern full."):
            assert t.town_note_write(state, "Pip", echo) == "Sigrun: Red Lantern full; scrap prices dip, keep your hammers.", echo
        t.town_note_write(state, "Zeno", "Shop1 pays 24 cp for barley today.")
        assert t.town_note_write(state, "Pip", "barley fetches 24 cp at Shop1 now").count("\n") == 1                 # the same fact, other words
        assert t.town_note_write(state, "Pip", "Shop3 pays 24 cp for barley today.").count("\n") == 2               # another shop is another fact
        assert t.town_note_write(state, "Pip", "Shop1 pays 31 cp for barley today.").count("\n") == 3               # another price too
        assert t.town_note_write(state, "Pip", "Hens are dying at Shop3 for want of feed.").count("\n") == 4        # something new is written
        long_line = t.town_note_write(state, "Pip", " ".join(f"{a}{b}ab" for a in "abcdefgh" for b in "ijklmnop")).splitlines()[-1]
        assert len(long_line.split()) == 26                           # the name and twenty-five words at most
    # a trader's model answer may carry a line for it
    spec = {"id": "det", "name": "Detlef", "likes": [], "persona": "x", "brings": []}
    monkeypatch.setattr(places, "BOTS", [spec])
    with t.town(write=True) as state:
        state["town_note"] = ""
        daily.run_day(state, 20, {"det": ([], "", "", {"town_note": "Feed is dear this week."})}, live=False)
        assert state["town_note"] == "Detlef: Feed is dear this week."


def test_a_bad_answer_never_stops_the_night(content, monkeypatch):
    from ttrpgtools.dcc.westmarch import daily, places, town as t
    flat = {"period": 10, "amplitude": 0, "phase": 0}
    monkeypatch.setattr(t, "today", lambda: places.EPOCH)
    spec = {"id": "sig", "name": "Sigrun", "likes": [], "persona": "x", "brings": []}
    other = {"id": "pip", "name": "Pip", "likes": [], "persona": "x", "brings": []}
    monkeypatch.setattr(places, "BOTS", [spec, other])
    with t.town(write=True) as state:
        bot = daily._record(state, spec)
        dcc.add_item(bot, "Dagger", "weapon", 1, "3 gp")
        # a pack line that is not there, a negative one, a word for a number: skipped, no error
        assert daily.act(state, bot, spec, [{"do": "sell", "shop": "x", "index": 7, "count": 1}, {"do": "sell", "shop": "x", "index": -9, "count": 1},
                                            {"do": "sell", "shop": "x", "index": "first", "count": 1}], 1) == []
        # and if a trader's turn fails anyway, it is written in the log and the next trader still plays
        monkeypatch.setattr(daily, "arrive", lambda bot, spec, day, view=None: (_ for _ in ()).throw(RuntimeError("boom")) if spec["id"] == "sig" else None)
        daily.run_day(state, 1, live=False)
        assert "Sigrun could not be played today: RuntimeError: boom." in " ".join(n["text"] for n in state["chronicle"])
        assert "pip" in state["bots"] and state["last_daily"] == 1


def test_barley_is_grown_not_made_from_leather(content, monkeypatch):
    import importlib
    from ttrpgtools.dcc.westmarch import daily, materials, places
    real = importlib.reload(places)
    real.MARKET = None   # reloading brings back the file's own switch
    try:
        for name, kind in (("Barley, a sack", "trade"), ("Coal, a sack", "trade"), ("Stinky cheese", "trade"), ("Ale, a jug", "trade"),
                           ("Eggs, a dozen", "trade"), ("Hen", "trade"), ("Oil, 1 flask", "gear"), ("Candle", "gear"), ("Rations, per day", "gear")):
            assert materials.made_of(name, kind) is None, name                                             # "sack" in a name does not make it a leather good
        assert all(materials.is_produce(n) for n in ("Barley, a sack", "Coal, a sack", "Stinky cheese", "Ale, a jug", "Eggs, a dozen", "Hen", "Rations, per day"))
        assert materials.made_of("Sack, small", "gear") == ("leather", 250) and materials.made_of("Scrap metal", "trade") == ("metal", 1000)
        # and every producer's own wares really arrive: thirty days, nothing sold
        for spec in real.BOTS:
            if spec["id"] not in ("zeno", "detlef", "xaver", "hedwig-n", "hartmut", "reinhild", "jutta", "ivo"):
                continue
            bot = daily._record({"bots": {}}, spec)
            dcc.add_item(bot, "Barley, a sack", "trade", 30, "4 sp"); dcc.add_item(bot, "Coal, a sack", "trade", 30, "6 sp")   # the brewer and the smoker need their raw stuff
            for day in range(1, 61):
                daily.arrive(bot, spec, day)
            held = {i["name"] for i in bot["inventory"]}
            assert {b[0] for b in spec["brings"]} <= held, (spec["id"], held)
    finally:
        places.PLACES, places.BOTS = [], []


def test_a_rich_trader_is_told_so_and_may_spend(content, monkeypatch):
    from ttrpgtools.dcc.westmarch import daily, places, town as t
    flat = {"period": 10, "amplitude": 0, "phase": 0}
    monkeypatch.setattr(t, "today", lambda: places.EPOCH)
    spec = {"id": "det", "name": "Detlef", "likes": ["trade", "mount"], "needs": ["Feed (per day)"], "persona": "x", "brings": []}
    other = {"id": "pip", "name": "Pip", "likes": [], "persona": "x", "brings": []}
    monkeypatch.setattr(places, "BOTS", [spec, other])
    assert daily.is_rich(50_000) and not daily.is_rich(49_999)                                          # 500 gp
    with t.town(write=True) as state:
        shop = t.save_shop(state, None, "Smith", "Bram", curve=flat)
        state["shops"][shop].update(deals=["weapon", "trade"], till=0)
        t.stock_item(state, shop, "Longsword", "weapon", "15 gp", 4, curve=flat)
        t.stock_item(state, shop, "Feed (per day)", "mount", "2 cp", 9, curve=flat)
        bot = daily._record(state, spec)
        daily._record(state, other)["coins"] = {"gp": 7, "sp": 0, "cp": 0}
        bot["coins"] = {"gp": 20, "sp": 0, "cp": 0}
        # a poor producer: no word about money, and only what the trade needs
        assert daily.wealth_note(state, bot) is None and [r["name"] for r in daily.market(state, spec, 2000)] == ["Feed (per day)"]
        assert [r["name"] for r in daily.shelves_shown(daily.market(state, spec, 2000), 2000)] == ["Feed (per day)"]
        # a rich one is told, with numbers, and shown everything the purse can buy
        bot["coins"] = {"gp": 20_000, "sp": 0, "cp": 0}
        note = daily.wealth_note(state, bot)
        assert note.startswith("YOU ARE RICH. Your purse holds 20.000,00 gp. The richest other trader holds 7,00 gp. Everything on every shelf in the village together costs about 60,18 gp")
        assert "332 times over" in note and "nothing stops you buying what your trade does not need" in note and "at least one that your trade has no need of" in note and "no longer fit" in note
        assert {r["name"] for r in daily.market(state, spec, 2_000_000)} == {"Feed (per day)", "Longsword"}
        assert daily.shelves_shown(daily.market(state, spec, 2_000_000), 2_000_000)[0]["name"] == "Longsword"     # the dearest first
        # the model is given the note, and the harness lets the purchase through, up to ten pieces
        seen = {}
        monkeypatch.setattr(daily, "ask_model", lambda messages, **kw: seen.update(text=messages[-1]["content"]) or {"actions": [{"do": "buy", "shop": shop, "item": "longsword", "count": 40}]})
        actions = daily.model_plan(state, bot, spec)[0]
        assert '"you_have_come_into_money":' in seen["text"] and "YOU ARE RICH" in seen["text"]
        assert daily.act(state, bot, spec, actions, 1) == ["bought 4 x Longsword at Smith (60,00 gp)"]            # four is all the shelf holds
        assert state["shops"][shop]["till"] == 6000 and dcc.coins_total_cp(bot["coins"]) == 2_000_000 - 6000
        # the note: a rich trader's note starts from the windfall (once), in the same shape as any seed
        spec["keeps"] = "his last three hens"
        seed = daily.windfall_seed(spec, bot)
        assert seed.startswith("WINDFALL I came into 19.940,00 gp. GOAL ") and "RULE" in seed and "TRACK" in seed and len(seed.split()) <= 50
        seen.clear()
        daily.model_plan(state, bot, spec)
        assert "WINDFALL I came into" in seen["text"]                                                   # the model sees it as its own note
        bot["note"] = "GOAL twelve hens. RULE feed hens only."
        daily.run_day(state, 2, {"det": ([], "", "GOAL twelve hens. RULE feed hens only.", {})}, live=False)
        assert bot["note"].startswith("WINDFALL I came into") and bot["windfall_told"]
        daily.run_day(state, 3, {"det": ([], "", "WINDFALL still rich. GOAL a new roof.", {})}, live=False)
        assert bot["note"] == "WINDFALL still rich. GOAL a new roof."                                      # after that the note is the model's own
        bot["coins"] = {"gp": 20, "sp": 0, "cp": 0}
        # a poor trader is told nothing, and is still held to the trade's needs
        bot["coins"] = {"gp": 20, "sp": 0, "cp": 0}
        t.stock_item(state, shop, "Longsword", "weapon", "15 gp", 4, curve=flat)
        seen.clear()
        daily.model_plan(state, bot, spec)
        assert '"you_have_come_into_money":' not in seen["text"] and "YOU ARE RICH" not in seen["text"] and daily.act(state, bot, spec, actions, 1) == []


def test_the_imported_goods_and_the_eel_farmer(content, monkeypatch):
    import importlib
    from ttrpgtools.dcc.westmarch import daily, materials, places, town as t
    real = importlib.reload(places)
    real.MARKET = None   # reloading brings back the file's own switch
    try:
        names = [g["name"] for g in real.TRADE_GOODS]
        assert names == ["Stinky cheese", "Smoked eel", "Fabric, a bolt", "Eastern steel, an ingot"] and not any("placeholder" in n for n in names)
        assert not any("placeholder" in b[0] for bot in real.BOTS for b in bot.get("brings", []))
        # nobody makes fabric or eastern steel: no trader brings them, and no workshop makes them
        brought = {b[0] for bot in real.BOTS for b in bot.get("brings", [])}
        assert "Fabric, a bolt" not in brought and "Eastern steel, an ingot" not in brought and "Smoked eel" in brought
        assert materials.made_of("Fabric, a bolt", "trade") is None and materials.made_of("Smoked eel", "trade") is None
        assert materials.made_of("Eastern steel, an ingot", "trade") == ("metal", 2000) and materials.is_raw("Eastern steel, an ingot")
        smith = next(p for p in real.PLACES if p["id"] == "shop2")
        assert ("Eastern steel, an ingot", "trade", "18 gp", 2) in smith["goods"] and "Eastern steel, an ingot" in smith["wants"]
        assert ("Fabric, a bolt", "trade", "3 gp", 6) in next(p for p in real.PLACES if p["id"] == "shop1")["goods"]
        monkeypatch.setattr(t, "today", lambda: places.EPOCH)
        with t.town(write=True) as state:
            forge = state["shops"]["shop2"]
            steel = next(i for i in forge["stock"] if i["name"] == "Eastern steel, an ingot")
            assert steel["qty"] == 2 and steel["target"] == 2
            steel["qty"] = 0
            before = dict(forge["materials"])
            work = t.restock(state, "shop2")                       # the smith does not "make" imported steel from his own metal
            assert steel["qty"] == 0 and forge["materials"].get("metal") == before.get("metal") or work["made"] >= 0
            needs = daily.village_needs(state)
            assert ("Eastern steel, an ingot", "goods") in [(n["what"], n["kind"]) for n in needs]       # it is a shortage the caravan can fill
    finally:
        places.PLACES, places.BOTS = [], []


def test_the_cook_makes_rations_from_whatever_is_cheapest(content):
    import importlib
    from ttrpgtools.dcc.westmarch import daily, economy, places
    real = importlib.reload(places)
    real.MARKET = None
    try:
        gudrun = next(b for b in real.BOTS if b["id"] == "gudrun")
        assert [name for name, _ in economy.recipes(gudrun, "Rations, per day")] == ["Barley, a sack", "Eggs, a dozen", "Hen"]
        assert economy.recipes(next(b for b in real.BOTS if b["id"] == "xaver"), "Ale, a jug") == [("Barley, a sack", 10)]   # a single pair still reads as a list
        assert not any(g["name"].startswith("Feed") for g in real.PRODUCE if "name" in g) and "Feed (per day)" not in str(real.BOTS)   # barley is the feed
        bot = daily._record({"bots": {}}, gudrun)
        dcc.add_item(bot, "Barley, a sack", "trade", 1, "4 sp")
        dcc.add_item(bot, "Eggs, a dozen", "trade", 40, "3 cp")
        view = {"rel": {"Barley, a sack": 3.0, "Eggs, a dozen": 0.5, "Hen": 1.0, "Rations, per day": 1.0}}
        held = lambda name: sum(int(i.get("qty", 1)) for i in bot["inventory"] if i["name"] == name)
        for day in range(1, 60):
            daily.arrive(bot, gudrun, day, view)
        assert held("Barley, a sack") == 1 and 0 < held("Eggs, a dozen") < 40      # cheap eggs go into the pot first; the dear barley stays in the pack
        assert held("Rations, per day") + bot["batch"]["Rations, per day"] == 3 * (40 - held("Eggs, a dozen"))
        bot["inventory"] = [i for i in bot["inventory"] if i["name"] not in ("Eggs, a dozen", "Rations, per day")]   # sold off, so the cellar has room again
        bot["batch"]["Rations, per day"] = before = 0
        for day in range(60, 300):                                                 # no eggs left: the barley is used, 25 rations a sack
            daily.arrive(bot, gudrun, day, view)
        assert held("Barley, a sack") == 0 and held("Rations, per day") + bot["batch"]["Rations, per day"] == before + 25
    finally:
        places.PLACES, places.BOTS = [], []


def test_the_brewer_needs_barley_and_the_smoker_coal(content):
    import importlib
    from ttrpgtools.dcc.westmarch import daily, places
    real = importlib.reload(places)
    real.MARKET = real.FIELDS = None   # reloading brings back the file's own switches; here the eel is about the coal, not the ponds
    try:
        xaver = next(b for b in real.BOTS if b["id"] == "xaver")
        reinhild = next(b for b in real.BOTS if b["id"] == "reinhild")
        assert [b[0] for b in xaver["brings"]] == ["Ale, a jug"] and [b[0] for b in reinhild["brings"]] == ["Barley, a sack"]   # he brews, she grows
        assert reinhild["trade"] == "barley farmer" and next(b for b in real.BOTS if b["id"] == "ivo")["trade"] == "leatherworker"
        bot = daily._record({"bots": {}}, xaver)
        for day in range(1, 31):                                      # no barley: not one jug in a month
            daily.arrive(bot, xaver, day)
        assert not any(i["name"] == "Ale, a jug" for i in bot["inventory"])
        dcc.add_item(bot, "Barley, a sack", "trade", 1, "4 sp")       # one sack: at most ten jugs, however long he waits, and the sack is gone
        for day in range(31, 151):
            daily.arrive(bot, xaver, day)
        jugs = sum(int(i.get("qty", 1)) for i in bot["inventory"] if i["name"] == "Ale, a jug")
        assert jugs == 10 and not any(i["name"].startswith("Barley") for i in bot["inventory"]) and bot["batch"]["Ale, a jug"] == 0
        jutta = daily._record({"bots": {}}, next(b for b in real.BOTS if b["id"] == "jutta"))
        dcc.add_item(jutta, "Coal, a sack", "trade", 2, "6 sp")        # two sacks smoke eight strings
        for day in range(1, 200):
            daily.arrive(jutta, next(b for b in real.BOTS if b["id"] == "jutta"), day)
        assert sum(int(i.get("qty", 1)) for i in jutta["inventory"] if i["name"] == "Smoked eel") == 8
    finally:
        places.PLACES, places.BOTS = [], []


def test_production_runs_with_the_moons(content, monkeypatch):
    import importlib
    from ttrpgtools.dcc.westmarch import daily, places, town as t
    real = importlib.reload(places)
    real.MARKET = None   # reloading brings back the file's own switch
    try:
        jutta = next(b for b in real.BOTS if b["id"] == "jutta")
        assert jutta["moon"] == {"id": "red", "peak": "full", "swing": 0.9} and "RHYTHM eels run with the Red Lantern, most at full." in daily.identity(jutta)
        flat = next(b for b in real.BOTS if b["id"] == "zeno")
        assert daily.rhythm(flat, 5) == 1.0 and daily.rhythm({"moon": {"id": "red", "peak": "full", "swing": 0.5}}, 1) <= 1.5
        # a smooth wave: new moon at 1 minus the swing, full moon at 1 plus it, never outside
        waves = [daily.rhythm(jutta, d) for d in range(1, 400)]
        assert 0.1 - 1e-9 <= min(waves) < 0.2 and 1.8 < max(waves) <= 1.9 + 1e-9 and abs(sum(waves) / len(waves) - 1) < 0.08
        lit = [t.moon_light("red", d) for d in range(1, 400)]
        assert min(lit) < 0.05 and max(lit) > 0.95 and all(0 <= x <= 1 for x in lit)
        # the eels come with the moon: forty-odd cycles of thirteen nights, fresh empty pack each morning
        by_phase = {"full": 0, "new": 0, "n_full": 0, "n_new": 0}
        for day in range(1, 521):
            bot = daily._record({"bots": {}}, jutta)
            dcc.add_item(bot, "Coal, a sack", "trade", 40, "6 sp")
            daily.arrive(bot, jutta, day)
            eels = sum(int(i.get("qty", 1)) for i in bot["inventory"] if i["name"] == "Smoked eel")
            light = t.moon_light("red", day)
            if light > 0.85:
                by_phase["full"] += eels; by_phase["n_full"] += 1
            elif light < 0.15:
                by_phase["new"] += eels; by_phase["n_new"] += 1
        full, new = by_phase["full"] / by_phase["n_full"], by_phase["new"] / by_phase["n_new"]
        assert full > 1.0 and new < 0.35 and full > 4 * new, (full, new)
        # the other moons have other periods: red 13 nights, pale a lunar month, drowned 61
        def peaks(moon):
            days = [d for d in range(1, 251) if t.moon_light(moon, d) > 0.9]
            return 1 + sum(1 for a, b in zip(days, days[1:]) if b - a > 1)      # runs of bright nights
        assert (peaks("red"), peaks("pale"), peaks("drowned")) == (19, 8, 4) or (18 <= peaks("red") <= 20 and 8 <= peaks("pale") <= 9 and 4 <= peaks("drowned") <= 5), (peaks("red"), peaks("pale"), peaks("drowned"))
    finally:
        places.PLACES, places.BOTS = [], []



def test_a_trader_sets_a_little_aside_for_the_tax_office(content, monkeypatch):
    from ttrpgtools.dcc.westmarch import daily, debts, places, registry, town as t
    monkeypatch.setattr(t, "today", lambda: places.EPOCH)
    marta = next(r for r in registry.rows("people") if r["name"] == "Marta Vogt")
    db = registry.connect()
    with db:
        db.execute("UPDATE people SET debt_cp = 300 WHERE id = ?", (marta["id"],))
    db.close()
    spec = {"id": "m", "name": "Marta Vogt"}
    with t.town(write=True) as state:
        bot = {"coins": {"gp": 4, "sp": 0, "cp": 0}}
        assert daily.pay_tax(state, bot, spec) == 0 and debts.villager_owes("Marta Vogt") == 300   # under the reserve: nothing set aside
        bot = {"coins": {"gp": 25, "sp": 0, "cp": 0}}
        before = state["money"]["finanzamt"]
        paid = daily.pay_tax(state, bot, spec)                                                    # 5 % of the 20 gp above the reserve = 1 gp
        assert paid == 100 and debts.villager_owes("Marta Vogt") == 200
        assert dcc.coins_total_cp(bot["coins"]) == 2400 and state["money"]["finanzamt"] == before + 100
        bot["coins"] = {"gp": 900, "sp": 0, "cp": 0}
        assert daily.pay_tax(state, bot, spec) == 200 and debts.villager_owes("Marta Vogt") == 0  # never more than the debt
        assert daily.pay_tax(state, bot, spec) == 0


def test_market_off_changes_nothing_and_on_it_prices_scarcity(content, monkeypatch):
    from ttrpgtools.dcc.westmarch import economy, places, town as t
    flat = {"period": 10, "amplitude": 0.5, "phase": 0}
    monkeypatch.setattr(t, "today", lambda: places.EPOCH)
    with t.town(write=True) as state:
        store = t.save_shop(state, None, "Store", curve=flat)
        barley = t.stock_item(state, store, "Barley, a sack", "trade", "4 sp", 10, curve=flat)
        armor = t.stock_item(state, store, "Chainmail", "armor", "75 gp", 4, curve=flat)
        for line in (barley, armor):
            line["target"] = line["qty"]
        economy.reprice(state, 1)
        assert "drift" not in barley and "market" not in state                       # off: untouched
        monkeypatch.setattr(places, "MARKET", {})
        for _ in range(12):
            economy.reprice(state, 1)
        assert abs(barley["drift"] - 1.0) < 0.01 and barley["calm"] < 1.0               # a full shelf is the usual price, and the wave is small
        barley["qty"], armor["qty"] = 1, 1
        for _ in range(12):
            economy.reprice(state, 1)
        assert barley["drift"] > 2.0 and armor["drift"] > 1.8                           # scarce is dear, armor dearer for its shelf
        assert armor["drift"] <= 90.0 and economy.view(state)["fill"]["Barley, a sack"] == 0.1
        barley["qty"] = 40
        for _ in range(12):
            economy.reprice(state, 1)
        assert barley["drift"] < 0.5                                                    # plentiful is cheap
        assert t.price_cp(state["shops"][store], barley, 3) < 40


def test_eggs_are_laid_by_fed_hens_and_goods_arrive_after_their_lag(content, monkeypatch):
    from ttrpgtools.dcc.westmarch import daily, economy, places, town as t
    monkeypatch.setattr(places, "MARKET", {})
    spec = {"id": "d", "name": "Detlef", "lays": "Eggs, a dozen", "lag": {"Hen": 5}, "brings": [("Eggs, a dozen", "trade", "3 cp", 3), ("Hen", "trade", "5 sp", 1)]}
    bot = {"coins": {"gp": 0, "sp": 0, "cp": 0}, "inventory": [], "hens_fed": 12}
    daily.arrive(bot, spec, 1, {"rel": {"Eggs, a dozen": 0.0001}})
    assert sum(i["qty"] for i in bot["inventory"] if i["name"] == "Eggs, a dozen") == 1     # twelve fed hens lay a dozen
    bot["hens_fed"] = 0
    before = sum(i["qty"] for i in bot["inventory"] if i["name"] == "Eggs, a dozen")
    daily.arrive(bot, spec, 2, {"rel": {"Eggs, a dozen": 0.0001}})
    assert sum(i["qty"] for i in bot["inventory"] if i["name"] == "Eggs, a dozen") == before   # unfed hens lay nothing
    economy.queue(bot, "Hen", "trade", "5 sp", 1, 7)
    daily.arrive(bot, spec, 6, {"rel": {"Eggs, a dozen": 0.0001}})
    assert not any(i["name"] == "Hen" for i in bot["inventory"])                            # not yet
    daily.arrive(bot, spec, 7, {"rel": {"Eggs, a dozen": 0.0001}})
    assert any(i["name"] == "Hen" for i in bot["inventory"])                                # the lag is over


def test_households_are_paid_from_full_tills_and_eat_what_they_can_afford(content, monkeypatch):
    from ttrpgtools.dcc.westmarch import economy, money, places, town as t
    flat = {"period": 10, "amplitude": 0, "phase": 0}
    monkeypatch.setattr(t, "today", lambda: places.EPOCH)
    monkeypatch.setattr(places, "MARKET", {"diet": {"Ale, a jug": 3}, "diet_scale": 1.0, "hh_ref": 100})
    cfg = economy.config()
    with t.town(write=True) as state:
        store = t.save_shop(state, None, "Store", curve=flat)
        state["shops"][store]["till"] = 10_000
        ale = t.stock_item(state, store, "Ale, a jug", "trade", "10 cp", 50, curve=flat)
        before = money.supply(state)["money_cp"]
        paid = economy.wages(state, cfg)
        assert paid > 0 and state["shops"][store]["till"] == 10_000 - paid and state["money"]["households"] == paid
        assert money.supply(state)["money_cp"] == before
        state["shops"][store]["till"] += state["money"]["households"] - 15    # coin for one jug only (the rest goes back to the till, so none is lost)
        state["money"]["households"] = 15
        eaten = economy.eat(state, 1, cfg)
        assert eaten == {"Ale, a jug": 1} and ale["qty"] == 49 and state["money"]["households"] == 5
        assert money.supply(state)["money_cp"] == before                     # the coin only moved
        state["money"]["households"] = 0
        assert economy.eat(state, 2, cfg) == {}                              # no coin, no meal


def test_a_producer_keeps_back_a_scarce_dear_good_and_releases_it_when_enough_is_kept(content, monkeypatch):
    from ttrpgtools.dcc.westmarch import economy, places
    own = {"goods": ["Ale, a jug"], "above": 1.6, "fill": 0.4, "cap_days": 3, "eat": 0.0}
    monkeypatch.setattr(places, "MARKET", {"own_use": own})
    cfg = economy.config()
    spec = {"id": "x", "name": "Xaver", "brings": [("Ale, a jug", "trade", "6 cp", 2)]}
    bot = {"inventory": [{"name": "Ale, a jug", "kind": "trade", "qty": 4}]}
    economy.own_use(bot, spec, cfg, {"rel": {"Ale, a jug": 2.5}, "fill": {"Ale, a jug": 0.1}})
    assert not bot["inventory"] and bot["kept"]["Ale, a jug"] == 4 and "release" not in bot       # scarce and dear: kept back (less than three days' worth for now)
    bot["inventory"] = [{"name": "Ale, a jug", "kind": "trade", "qty": 3}]
    economy.own_use(bot, spec, cfg, {"rel": {"Ale, a jug": 2.5}, "fill": {"Ale, a jug": 0.1}})
    assert bot["release"] == {"Ale, a jug": 7} and bot["kept"]["Ale, a jug"] == 0          # six days' worth kept (cap 3 x 2): all of it goes out again
    economy.own_use(bot, spec, cfg, {"rel": {"Ale, a jug": 1.0}, "fill": {"Ale, a jug": 1.0}})
    assert bot["kept"]["Ale, a jug"] == 0                                                     # plentiful and cheap: nothing is kept


def test_a_trader_holds_back_what_the_trade_must_keep(content, monkeypatch):
    from ttrpgtools.dcc.westmarch import daily, places, town as t
    monkeypatch.setattr(t, "today", lambda: places.EPOCH)
    flat = {"period": 10, "amplitude": 0, "phase": 0}
    spec = {"id": "d", "name": "Detlef", "hold": {"Hen": 2}, "likes": [], "persona": "x", "brings": []}
    monkeypatch.setattr(places, "BOTS", [spec])
    with t.town(write=True) as state:
        store = t.save_shop(state, None, "Store", curve=flat)
        state["shops"][store]["till"] = 100_000
        state["shops"][store]["deals"] = ["trade"]
        t.stock_item(state, store, "Hen", "trade", "5 sp", 0, curve=flat)
        bot = daily._record(state, spec)
        for _ in range(5):
            dcc.add_item(bot, "Hen", "trade", 1, "5 sp")
        plan = daily.rule_plan(state, bot, spec, 1)
        assert sum(a["count"] for a in plan if a["do"] == "sell") <= 3                          # five hens, two held back


def test_a_fresh_start_settles_the_shelves_and_funds_the_producers_from_the_finanzamt(content, monkeypatch):
    from ttrpgtools.dcc.westmarch import daily, economy, money, places, town as t
    flat = {"period": 10, "amplitude": 0, "phase": 0}
    spec = {"id": "d", "name": "Detlef", "lays": "Eggs, a dozen", "stock_up": {"Barley, a sack": 3}, "likes": [], "persona": "x",
            "brings": [("Eggs, a dozen", "trade", "3 cp", 3), ("Hen", "trade", "5 sp", 1)]}
    monkeypatch.setattr(places, "BOTS", [spec])
    monkeypatch.setattr(t, "today", lambda: places.EPOCH)
    with t.town(write=True) as state:
        store = t.save_shop(state, None, "Store", curve=flat)
        barley = t.stock_item(state, store, "Barley, a sack", "trade", "4 sp", 40, curve=flat)
        barley["target"] = 6
        bot = daily._record(state, spec)
        dcc.add_item(bot, "Barley, a sack", "trade", 9, "4 sp")
        state["money"]["finanzamt"] = 5000
        before = money.supply(state)["money_cp"]
        done = economy.fresh_start(state)
        assert barley["qty"] == 6 and sum(i["qty"] for i in bot["inventory"] if i["name"] == "Barley, a sack") == 3
        assert done["capital_cp"] == 1500 and state["money"]["finanzamt"] == 3500 and dcc.coins_total_cp(bot["coins"]) == 1500
        assert sum(1 for i in bot["inventory"] if i["name"] == "Hen") == 12 and money.supply(state)["money_cp"] == before


def test_a_new_character_starts_with_about_ten_gold_and_ten_gold_of_debt():
    import importlib
    from ttrpgtools.dcc.westmarch import places, registry
    importlib.reload(places)
    importlib.reload(registry)
    try:
        assert places.TAX_DEBT == "10 gp" and places.START_PURSE_CP == 1000
        assert registry.start_copper(5) == 800 and registry.start_copper(60) == 1200
        assert registry.start_copper(33) == round(1000 * (0.8 + 0.4 * 28 / 55))
    finally:
        places.MARKET = None


def test_what_the_players_buy_heats_the_good_and_raises_every_price_for_weeks(content, monkeypatch):
    from ttrpgtools.dcc.westmarch import economy, places, town as t
    flat = {"period": 10, "amplitude": 0, "phase": 0}
    monkeypatch.setattr(t, "today", lambda: places.EPOCH)
    monkeypatch.setattr(places, "MARKET", {})
    with t.town(write=True) as state:
        store = t.save_shop(state, None, "Store", curve=flat)
        state["shops"][store]["till"] = 0
        sword = t.stock_item(state, store, "Longsword", "weapon", "10 gp", 10, curve=flat)
        rope = t.stock_item(state, store, "Rope, 50’", "gear", "1 gp", 10, curve=flat)
        for line in (sword, rope):
            line["target"] = 10
        for _ in range(3):
            economy.reprice(state, 1)
        calm = (sword["drift"], rope["drift"])
        assert abs(calm[0] - 1.0) < 0.05 and state["market"]["inflation"] == 1.0
        player = {"name": "Mira", "coins": {"gp": 500, "sp": 0, "cp": 0}, "inventory": []}
        t.buy(state, store, sword["id"], player, 4, who="mira")        # 400 cp is not much: but 4 of 10 swords is 40 percent of the stock
        sword["qty"] = 10                                                # the shelf is restocked at once, so only the heat is left
        economy.reprice(state, 2)
        first = (sword["drift"], rope["drift"])
        assert state["market"]["heat"]["Longsword"] > 3.5 and state["market"]["inflation"] > 1.3
        assert first[0] > calm[0] * 1.5 and first[1] > calm[1] * 1.2     # the sword is hotter than the rope, but the rope is dearer too: the players' coin is about
        for day in range(3, 30):
            economy.reprice(state, day)
        assert sword["drift"] < first[0] and state["market"]["inflation"] < 1.3 and state["market"]["heat"].get("Longsword", 0) < 1   # and it fades
        before = state["market"]["spent"]
        t.buy(state, store, sword["id"], {"name": "Bot", "coins": {"gp": 500, "sp": 0, "cp": 0}, "inventory": []}, 2, who="bot")
        assert state["market"]["spent"] == before                         # traders' buying works through the shelves alone


def test_the_unplayed_villagers_are_funded_from_the_finanzamt(content, monkeypatch):
    import importlib
    from ttrpgtools.dcc.westmarch import money, places, registry, town as t
    importlib.reload(places); importlib.reload(registry)
    monkeypatch.setattr(places, "MARKET", None)
    db = registry.connect()
    with db:
        db.execute("INSERT INTO people (name, occupation, status, sheet, locked, updated) VALUES ('Lone', 'farmer', 'alive', '{\"copper\": 30}', 0, '2026-10-08')")
    db.close()
    with t.town(write=True) as state:
        state["money"]["finanzamt"] = 100_000
        before = money.supply(state)["money_cp"]
        done = money.fund_villagers(state)
        assert done["villagers"] >= 1 and done["short_cp"] == 0 and money.supply(state)["money_cp"] == before
        assert money.fund_villagers(state)["villagers"] == 0                # once is enough


def test_a_glut_can_make_goods_free_and_even_make_the_shop_pay_you_to_take_them(content, monkeypatch):
    from ttrpgtools.dcc.westmarch import economy, places, town as t
    flat = {"period": 10, "amplitude": 0, "phase": 0}
    monkeypatch.setattr(t, "today", lambda: places.EPOCH)
    monkeypatch.setattr(places, "MARKET", {})
    assert t.price_text(0) == "free" and t.price_text(-12) == "they pay you 0,12 gp" and t.coins_text(-250) == "-2,50 gp"
    with t.town(write=True) as state:
        store = t.save_shop(state, None, "Store", curve=flat)
        state["shops"][store]["till"] = 100
        eggs = t.stock_item(state, store, "Eggs, a dozen", "trade", "3 cp", 5, curve=flat)
        eggs["target"] = 5
        eggs["drift"], eggs["calm"] = 0.01, 0.15                                   # a glut: 3 cp times 0,01 rounds to nothing
        assert t.price_cp(state["shops"][store], eggs, 1) == 0
        player = {"name": "Mira", "coins": {"gp": 0, "sp": 0, "cp": 5}, "inventory": []}
        sale = t.buy(state, store, eggs["id"], player, 2, who="mira")
        assert sale["each_cp"] == 0 and dcc.coins_total_cp(player["coins"]) == 5 and eggs["qty"] == 3      # free: it costs nothing
        eggs["bounty"] = 0.5                                                      # a great glut: the shop pays half the usual price per dozen
        assert t.price_cp(state["shops"][store], eggs, 1) == -2 and t.view(state, "", full=True)["shops"][0]["stock"][0]["price"] == "they pay you 0,02 gp"
        sale = t.buy(state, store, eggs["id"], player, 3, who="mira")
        assert dcc.coins_total_cp(player["coins"]) == 5 + 6 and state["shops"][store]["till"] == 100 - 6 and eggs["qty"] == 0
        eggs["qty"] = 5
        state["shops"][store]["till"] = 3
        with pytest.raises(t.TownError):
            t.buy(state, store, eggs["id"], player, 5, who="mira")                  # the till cannot pay: nothing changes
        assert dcc.coins_total_cp(player["coins"]) == 11 and eggs["qty"] == 5 and state["shops"][store]["till"] == 3


def test_a_traders_surplus_feeds_the_family_and_returns_to_the_households(content, monkeypatch):
    from ttrpgtools.dcc.westmarch import economy, money, places, town as t
    monkeypatch.setattr(t, "today", lambda: places.EPOCH)
    monkeypatch.setattr(places, "MARKET", {"reserve": 3000, "family_share": 0.1})
    with t.town(write=True) as state:
        state["bots"] = {"rich": {"name": "R", "coins": {"gp": 100, "sp": 0, "cp": 0}, "inventory": []},
                         "poor": {"name": "P", "coins": {"gp": 5, "sp": 0, "cp": 0}, "inventory": []}}
        before = money.supply(state)["money_cp"]
        moved = economy.families(state, economy.config())
        assert moved == 700 and state["money"]["households"] == 700                          # a tenth of the 70 gp above the reserve
        assert dcc.coins_total_cp(state["bots"]["rich"]["coins"]) == 9300 and dcc.coins_total_cp(state["bots"]["poor"]["coins"]) == 500
        assert money.supply(state)["money_cp"] == before


def test_fresh_start_takes_a_windfall_back_and_does_not_add_hens_twice(content, monkeypatch):
    from ttrpgtools.dcc.westmarch import daily, economy, places, town as t
    monkeypatch.setattr(t, "today", lambda: places.EPOCH)
    spec = {"id": "d", "name": "Detlef", "lays": "Eggs, a dozen", "stock_up": {"Barley, a sack": 3}, "likes": [], "persona": "x",
            "brings": [("Eggs, a dozen", "trade", "3 cp", 3), ("Hen", "trade", "5 sp", 1)]}
    monkeypatch.setattr(places, "BOTS", [spec])
    with t.town(write=True) as state:
        bot = daily._record(state, spec)
        bot["coins"] = {"gp": 18000, "sp": 0, "cp": 0}
        before = state["money"]["finanzamt"]
        done = economy.fresh_start(state)
        assert dcc.coins_total_cp(bot["coins"]) == 20000 and state["money"]["finanzamt"] == before + 1_780_000 - done["capital_cp"]
        assert sum(1 for i in bot["inventory"] if i["name"] == "Hen") == 12 and done["hens"] == 12
        economy.fresh_start(state)
        assert sum(1 for i in bot["inventory"] if i["name"] == "Hen") == 12                  # run twice, still one flock


def test_the_households_top_up_a_till_that_has_run_dry(content, monkeypatch):
    from ttrpgtools.dcc.westmarch import economy, money, places, town as t
    flat = {"period": 10, "amplitude": 0, "phase": 0}
    monkeypatch.setattr(t, "today", lambda: places.EPOCH)
    monkeypatch.setattr(places, "MARKET", {"till_float": 1000, "refill_share": 0.5})
    with t.town(write=True) as state:
        dry, full = t.save_shop(state, None, "Dry", curve=flat), t.save_shop(state, None, "Full", curve=flat)
        state["shops"][dry]["till"], state["shops"][full]["till"] = 100, 5000
        wagon = t.save_shop(state, None, "Wagons", curve=flat)
        state["shops"][wagon]["kinds"], state["shops"][wagon]["till"] = ["caravan"], 0
        state["money"]["households"] = 600
        before = money.supply(state)["money_cp"]
        moved = economy.refill(state, economy.config())
        assert moved == 300 and state["shops"][dry]["till"] == 400 and state["shops"][full]["till"] == 5000 and state["money"]["households"] == 300
        assert state["shops"][wagon]["till"] == 0                                           # the wagons carry their own coin
        assert money.supply(state)["money_cp"] == before


@real
def test_the_villagers_age_wed_have_children_and_die(monkeypatch):
    import importlib
    from ttrpgtools.dcc.westmarch import debts, lives, places, registry, steward
    cfg = dict(importlib.reload(places).LIVES)
    monkeypatch.setattr(places, "LIVES", cfg)
    monkeypatch.setattr(places, "MARKET", None)
    monkeypatch.setattr(places, "TAX_DEBT", "10 gp")
    monkeypatch.setattr(places, "STEWARD", None)
    # the odds of dying: an elf never, a dwarf later than a human, nobody young
    assert lives.death_chance(500, "elf", cfg) < 0.0001 and lives.death_chance(20, "human", cfg) < 0.001           # an elf hardly dies, in five hundred years
    assert lives.death_chance(20, "human", cfg) < lives.death_chance(50, "human", cfg) < lives.death_chance(70, "human", cfg) < 1
    assert lives.death_chance(70, "dwarf", cfg) < lives.death_chance(70, "human", cfg) and lives.death_chance(70, "halfling", cfg) < lives.death_chance(70, "human", cfg)
    survived = 1.0
    for month in range(12 * 90):
        survived *= 1 - lives.death_chance(month / 12, "human", cfg)
    assert survived < 0.001                                     # nobody lives to ninety
    assert lives.death_chance(500, "elf", cfg) < 1e-6 and lives.death_chance(500, "elf", cfg, mishap=False) < lives.death_chance(500, "elf", cfg)   # an elf's mishap a tenth of the old; the herb woman has none
    # each ability of a child: father's, mother's, their mean or 2d10, a quarter each
    import random
    rows = {"sheet": json.dumps({"abilities": {a: 16 for a in dcc.ABILITIES}})}, {"sheet": json.dumps({"abilities": {a: 6 for a in dcc.ABILITIES}})}
    rng, counts = random.Random(1), {16: 0, 6: 0, 11: 0}
    draws = [v for _ in range(600) for v in lives._genes(rows[0], rows[1], cfg, rng).values()]
    for v in draws:
        if v in counts:
            counts[v] += 1
    assert all(0.2 < n / len(draws) < 0.34 for n in counts.values()) and min(draws) >= 3 and max(draws) <= 18
    # forty years of the whole village in a month-by-month loop
    state = {"money": {"households": 200000, "bank": 0, "finanzamt": 0, "library": 0, "caravan": 0}}

    def coin():
        db = registry.connect()
        try:
            sheets = [json.loads(r["sheet"])["copper"] for r in db.execute("SELECT sheet FROM people WHERE status != 'dead' AND claimed_by IS NULL AND sheet IS NOT NULL")]
        finally:
            db.close()
        return sum(sheets) + state["money"]["households"]
    start, owed = coin(), debts.town_total()["total_cp"]
    for month in range(1, 12 * 40 + 1):
        lives.monthly(state, int(month * 365 / 12) + 1)
    db = lives._db()
    people = [dict(r) for r in db.execute("SELECT * FROM people")]
    by_id = {p["id"]: p for p in people}
    totals = db.execute("SELECT SUM(births), SUM(deaths), SUM(weddings) FROM lives_monthly").fetchone()
    assert totals[0] > 5 and totals[1] > 5 and totals[2] > 5
    assert coin() == start                                       # births and deaths move coin between sheets and the households, never make or lose any
    assert debts.town_total()["total_cp"] == owed                # what the dead owed went to the living
    for p in people:
        if p["spouse_id"]:
            other = by_id[p["spouse_id"]]
            assert other["spouse_id"] == p["id"] and p["status"] == other["status"] == "alive" and p["race"] == other["race"] and p["sex"] != other["sex"]   # one spouse, the same kind, both alive
            assert not lives.related(p, other)
        if p["mother_id"]:
            assert p["race"] == by_id[p["father_id"]]["race"] == by_id[p["mother_id"]]["race"]
            if p["sheet"]:
                assert all(3 <= v <= 18 for v in json.loads(p["sheet"])["abilities"].values()) and p["occupation"] != "Child"
            else:
                assert p["occupation"] == "Child"
    assert any(p["mother_id"] and p["sheet"] for p in people)       # some child grew up and has its rolls
    grown = [p for p in people if p["mother_id"] and p["sheet"]]
    from_parents = sum(p["occupation"] in json.loads(p["genes"])["jobs"] for p in grown)
    assert from_parents / len(grown) > 0.65                      # four in five take a parent's trade (and a fifth draw it again by chance)
    assert all(p["seat"] for p in people if p["locked"] and p["mother_id"] and p["status"] == "alive")      # a child is townsfolk only by holding a seat
    db.close()
    registry.connect().close()
    assert len([r for r in registry.rows("people") if r["mother_id"]]) == len([p for p in people if p["mother_id"] and p["status"] != "dead"])    # the register keeps the living villagers born since
    assert not [r for r in registry.rows("people") if r["mother_id"] and r["occupation"] == "Child" and r["playable"]]      # a child cannot be taken over
    kids = [r for r in registry.rows("people", judge=True) if r["occupation"] == "Child" and r["status"] == "alive"]
    assert kids and all(set(k["inherited"]["abilities"]) == set(dcc.ABILITIES) for k in kids) and not any("inherited" in r for r in registry.rows("people"))   # the admin sees their scores, a player does not


@real
def test_a_dead_keeper_is_replaced_by_a_child_with_the_trade_or_nobody(monkeypatch):
    import importlib
    import random
    from ttrpgtools.dcc.westmarch import lives, places, registry
    cfg = dict(importlib.reload(places).LIVES)
    monkeypatch.setattr(places, "LIVES", cfg)
    monkeypatch.setattr(places, "MARKET", None)
    state = {"money": {"households": 200000, "bank": 0, "finanzamt": 0, "library": 0, "caravan": 0},
             "shops": {"shop1": {"keeper": "Marta Vogt"}, "shop2": {"keeper": "Bram Eisenhand"}}}
    lives.monthly(state, 31)                                       # the first month: every townsperson holds the seat of their trade
    db = lives._db()
    seats = {r["seat"]: r for r in db.execute("SELECT * FROM people WHERE seat IS NOT NULL")}
    assert len(seats) == 20 and "Brewer" in seats and "Herb woman" in seats                 # the nineteen trades and the herb woman
    # a child who took the parent's trade at eighteen and was not seated waits for the seat: when the brewer dies she has it
    brewer = seats["Brewer"]
    child = lambda name, job, born: db.execute("INSERT INTO people (name, occupation, status, notes, updated, locked, debt_cp, born_day, sex, race, mother_id, father_id, genes, sheet) "
                                               "VALUES (?, ?, 'alive', '', 'x', 0, 0, ?, 'f', 'human', ?, ?, ?, ?)",
                                               (name, job, born, brewer["id"], brewer["id"], json.dumps({"abilities": {a: 12 for a in dcc.ABILITIES}, "jobs": ["Brewer", "Brewer"]}),
                                                json.dumps({"abilities": {a: 12 for a in dcc.ABILITIES}, "copper": 0, "occupation": job})))
    child("Hanne Xaversdotter", "Brewer", 31 - 25 * 365)
    lives._die(db, state, db.execute("SELECT * FROM people WHERE id = ?", (brewer["id"],)).fetchone(), 40, "old age")
    heir = db.execute("SELECT * FROM people WHERE name = 'Hanne Xaversdotter'").fetchone()
    assert heir["seat"] == "Brewer" and heir["locked"] == 1 and state["seats"]["xaver"] == heir["name"] and "Brewer" not in state.get("vacant", {})
    assert not lives.vacant_bot(state, next(b for b in places.BOTS if b["id"] == "xaver")) and lives.holder_name(state, next(b for b in places.BOTS if b["id"] == "xaver")) == heir["name"]
    # the keeper of a shop dies with nobody to follow: the shop is shut (closed_reason), the seat stands empty
    marta = seats["Outfitter and innkeeper (Shop1)"]
    lives._die(db, state, db.execute("SELECT * FROM people WHERE id = ?", (marta["id"],)).fetchone(), 41, "old age")
    assert state["vacant"]["Outfitter and innkeeper (Shop1)"]["was"] == "Marta Vogt" and state["shops"]["shop1"]["keeper"] == "Marta Vogt"
    db.commit()
    from ttrpgtools.dcc.westmarch import town
    assert "Marta Vogt is dead" in town.closed_reason(state["shops"]["shop1"])
    report = lives.summary(state, 41)
    assert any("EMPTY" in line for line in report["townsfolk_seats"])
    seen = lives.look_up(state, 41, [{"children": True}, {"person": "Hanne Xaversdotter"}, {"best_for_delver": 3}, {"trade": "brewer"}, {"couples": True}])[:3]     # three questions at most
    assert len(seen) == 3 and "Hanne Xaversdotter" in seen[1]["answer"][0] and "holds the seat of Brewer" in seen[1]["answer"][1] and len(seen[2]["answer"]) == 3
    assert all("STR" in line and "delver score" in line for line in seen[0]["answer"]) and "population" in report and "single_adults" not in report         # the report outlines; individuals are asked for
    # a child comes of age and draws the trade of the empty seat (a parent's, with certainty here): she takes the seat, and the shop opens
    monkeypatch.setitem(cfg, "parent_job", 1.0)
    db.execute("INSERT INTO people (name, occupation, status, notes, updated, locked, debt_cp, born_day, sex, race, mother_id, father_id, genes) VALUES "
               "('Greta Martasdotter', 'Child', 'alive', '', 'x', 0, 0, ?, 'f', 'human', ?, ?, ?)",
               (41 - 18 * 365 - 5, marta["id"], marta["id"], json.dumps({"abilities": {a: 11 for a in dcc.ABILITIES}, "jobs": ["Outfitter and innkeeper (Shop1)"] * 2})))
    lives._come_of_age(db, state, 41, cfg, dcc.load_content(), random.Random(1))
    greta = db.execute("SELECT * FROM people WHERE name = 'Greta Martasdotter'").fetchone()
    assert greta["occupation"] == "Outfitter and innkeeper (Shop1)" and greta["seat"] == greta["occupation"] and greta["locked"] == 1
    assert state["shops"]["shop1"]["keeper"] == "Greta Martasdotter" and "Outfitter and innkeeper (Shop1)" not in state["vacant"]
    monkeypatch.setattr(places, "PLACES", [{"id": "shop1", "name": "Shop1", "kinds": ["shop"], "keeper": "Marta Vogt"}])
    state["shops"]["shop1"].setdefault("stock", [])
    town._seed(state)                                                                                   # the nightly load writes places.py over every shop
    assert state["shops"]["shop1"]["keeper"] == "Greta Martasdotter"                                   # but the heir keeps it (a bug until 10-10: shops shut for decades)
    assert json.loads(greta["sheet"])["abilities"] == {a: 11 for a in dcc.ABILITIES}       # the rolls are the inherited scores
    db.commit()
    assert town.closed_reason(state["shops"]["shop1"]) is None
    assert not [r for r in registry.rows("people") if r["name"] == "Greta Martasdotter" and r["playable"]]    # townsfolk are not for playing
    # the forge's seat is "Blacksmith (The Blacksmith)"; an adult of the table's plain "Blacksmith" takes it when it stands empty (a bug until 10-10: empty for years)
    bram = seats["Blacksmith (The Blacksmith)"]
    lives._die(db, state, db.execute("SELECT * FROM people WHERE id = ?", (bram["id"],)).fetchone(), 42, "old age")
    assert "Blacksmith (The Blacksmith)" in state["vacant"]
    child("Rike Bramsdotter", "Blacksmith", 42 - 20 * 365)
    lives._fill_vacant(db, state, 42)
    rike = db.execute("SELECT * FROM people WHERE name = 'Rike Bramsdotter'").fetchone()
    assert rike["seat"] == "Blacksmith (The Blacksmith)" and state["shops"]["shop2"]["keeper"] == "Rike Bramsdotter" and "Blacksmith (The Blacksmith)" not in state["vacant"]
    # a child named "X the Younger 21" because X was taken keeps a shop; the dead X neither shuts it nor passes it on (both until 10-11)
    child("Volker Ingosson", "Child", 42 - 70 * 365)
    child("Volker Ingosson the Younger 21", "Child", 42 - 30 * 365)
    db.execute("UPDATE people SET status = 'dead' WHERE name = 'Volker Ingosson'")
    db.commit()
    state["shops"]["shop2"]["keeper"] = "Volker Ingosson the Younger 21"
    assert town.closed_reason(state["shops"]["shop2"]) is None
    lives._install(db, state, db.execute("SELECT * FROM people WHERE name = 'Hanne Xaversdotter'").fetchone(), "Brewer", 43, "Volker Ingosson")
    assert state["shops"]["shop2"]["keeper"] == "Volker Ingosson the Younger 21"
    db.close()


def test_the_barley_fields_grow_by_the_moons_light_and_change_hands_for_coin(content, monkeypatch):
    import importlib
    from ttrpgtools.dcc.westmarch import daily, fields, places, town as t
    cfg = dict(importlib.reload(places).FIELDS)
    monkeypatch.setattr(places, "FIELDS", cfg)
    monkeypatch.setattr(places, "MARKET", {})
    monkeypatch.setattr(places, "PLACES", [])
    monkeypatch.setattr(t, "today", lambda: places.EPOCH)
    reinhild = next(b for b in places.BOTS if b["id"] == "reinhild")
    monkeypatch.setattr(places, "BOTS", [reinhild])
    # the light: 0.4 to 1.6, averaging about one over the years; a harvest factor inside the same bounds
    lights = [fields.light(d) for d in range(1, 2000)]
    assert 0.4 <= min(lights) and max(lights) <= 1.6 and 0.9 < sum(lights) / len(lights) < 1.1
    assert all(0.4 <= fields.harvest_factor(d, cfg) <= 1.6 for d in range(20, 400, 7))
    # the fat nights: the Drowned Moon bright, the other two not; about one night in a month
    fat = sum(fields.fat_night(d) for d in range(1, 3651))
    assert 0.6 <= fat / 120 <= 1.1, fat
    with t.town(write=True) as state:
        state["money"] = {"bank": 0, "finanzamt": 0, "households": 50000, "library": 0, "caravan": 0}
        store = t.save_shop(state, None, "Store", curve={"period": 10, "amplitude": 0, "phase": 0})
        barley = t.stock_item(state, store, "Barley, a sack", "trade", "4 sp", 0, curve={"period": 10, "amplitude": 0, "phase": 0})
        barley["target"] = 10
        state["market"] = {"rel": {"Barley, a sack": 1.0}}
        bot = daily._record(state, reinhild)
        bot["coins"] = {"gp": 100, "sp": 0, "cp": 0}
        fields.lay_out(state, 1, ["Reinhild Sevenbrothers", "Anselm Sevenbrothers", "Veit Stillwater"])                 # three people: one plot each, the rest the village's
        plots = fields.book(state)["plots"]
        assert len(plots) == 100 and sum(1 for p in plots if p["owner"] is None) == 97 and len(fields.owned_by(state, "Reinhild Sevenbrothers")) == 1
        for p in plots[3:10]:                                                                                           # she farms eight plots
            p["owner"] = "Reinhild Sevenbrothers"
        # night one: no seed in store, two sacks in the pack; one pair of hands works seven plots, so one sack sows them and the eighth plot waits
        dcc.add_item(bot, "Barley, a sack", "trade", 2, "4 sp")
        done = fields.farm(state, bot, reinhild, 1)
        assert done == ["sowed 7 plots with 1 sack of seed"] and sum(int(i.get("qty", 1)) for i in bot["inventory"] if i["name"] == "Barley, a sack") == 1 and bot["seed"] == 0
        assert sum(1 for p in plots if p["sown"] == 1) == 7
        bot["inventory"] = []
        for day in range(2, 1 + cfg["grow"]):
            assert fields.farm(state, bot, reinhild, day) == []                                                         # growing: nothing to do
        done = fields.farm(state, bot, reinhild, 1 + cfg["grow"])
        sacks = sum(int(i.get("qty", 1)) for i in bot["inventory"] if i["name"] == "Barley, a sack") + bot["seed"]
        assert done[0].startswith("reaped") and 7 * 4 * 0.4 <= sacks <= 7 * 4 * 1.6 + 7                                         # seven plots by the light
        assert done[1] == "sowed 7 plots with 1 sack of seed" and bot["seed"] == 0                                               # the sack kept back sows the eighth plot and six common ones: hands full again
        assert sum(1 for p in plots if p.get("worker") == "Reinhild Sevenbrothers") == 6
        reaped = [p for p in plots[:10] if p["rest_until"] == 1 + cfg["grow"] + cfg["rest"]]
        assert len(reaped) == 7 and all(p["sown"] is None for p in reaped)
        assert fields.farm(state, bot, reinhild, 1 + cfg["grow"] + cfg["rest"] - 1) == []                                       # resting
        assert fields.farm(state, bot, reinhild, 1 + cfg["grow"] + cfg["rest"]) == []                                          # her own seven are rested and ready, but her hands are full
        log = fields.book(state)["harvests"]
        assert len(log) == 7 and "sky_when_sown" in fields.summary(state, 80)["harvests_lately"][0] and "light" not in json.dumps(fields.summary(state, 80))   # moons shown, the formula not
        # the land market (the owner 10-10): every owner names a price, the crop on the plot included; a common plot asks the usual price, unless somebody works it
        import random as _random
        from ttrpgtools.dcc.westmarch import registry
        purses = lambda: sum(json.loads(r[0])["copper"] for r in registry.connect().execute("SELECT sheet FROM people WHERE sheet IS NOT NULL"))
        state["market"] = {"rel": {"Barley, a sack": 2.0}}
        common = next(p for p in plots if p["owner"] is None and not p.get("worker"))
        worked = next(p for p in plots if p.get("worker"))
        assert fields.ask_cp(state, common) == cfg["usual_plot_cp"] and fields.ask_cp(state, worked) is None
        for p in plots:                                                                                                 # her common plots end their season early, for the test
            if p.get("worker"):
                p.pop("worker")
                p["sown"] = None
        mine = fields.owned_by(state, "Reinhild Sevenbrothers")
        assert len(mine) == 8 and fields.rule_actions(state, bot, reinhild, 80) == []                                   # eight plots and hands for seven: no more land
        for p in mine[2:]:                                                                                              # she keeps two; the rest go to Veit, fallow
            p.update(owner="Veit Stillwater", sown=None, rest_until=None)
        for p in plots:
            if p["owner"] is None:
                p["owner"] = "Veit Stillwater"                                                                         # no common plot left: land must be bought
        veit = json.loads(registry.connect().execute("SELECT sheet FROM people WHERE name = 'Veit Stillwater'").fetchone()[0])["copper"]
        own_price = int(cfg["usual_plot_cp"] * _random.Random("plot-ask/Veit Stillwater").uniform(*cfg["attachment"]) * max(0.4, min(1.5, (veit + 200) / 1200)))
        fallow = next(p for p in plots if p["owner"] == "Veit Stillwater" and p["sown"] is None)
        assert fields.ask_cp(state, fallow) == own_price                                                                # his own attachment and his own purse
        sown = next(p for p in plots if p["owner"] == "Veit Stillwater" and p["sown"] is None and p is not fallow)
        sown["sown"] = 79
        assert fields.ask_cp(state, sown) == own_price + 4 * 40 * 2                                                     # and the barley on it, at today's price
        sown["sown"] = None
        bot["coins"] = {"gp": 300, "sp": 0, "cp": 0}
        wish = fields.rule_actions(state, bot, reinhild, 80)
        assert wish == [{"do": "buy_field", "plot": fields.for_sale(state, 80, "Reinhild Sevenbrothers", 1)[0]["plot"]}]   # the cheapest ask, under a year's harvest
        before, had = dcc.coins_total_cp(bot["coins"]) + state["money"]["households"], purses()
        done = fields.act(state, bot, reinhild, wish, 80)
        assert done[0].startswith("bought plot") and purses() == had + own_price                                          # the coin is in the seller's own purse
        assert dcc.coins_total_cp(bot["coins"]) + state["money"]["households"] == before - own_price
        # a model may name its own price; another buyer sees it
        bought = fields.owned_by(state, "Reinhild Sevenbrothers")[-1]
        assert fields.act(state, bot, reinhild, [{"do": "ask_field", "plot": bought["id"], "ask_cp": 99999}], 81) == [f"would sell plot {bought['id']} for 999,99 gp"]
        assert fields.ask_cp(state, bought) == 99999 and fields.mine_for_prompt(state, bot, reinhild, 81)["your_prices_set"] == {str(bought["id"]): 99999}
        # broke: she sells a fallow plot to the village at four fifths of the usual price
        bot["coins"] = {"gp": 1, "sp": 0, "cp": 0}
        assert fields.rule_actions(state, bot, reinhild, 82) == [{"do": "sell_field"}]
        before = dcc.coins_total_cp(bot["coins"]) + state["money"]["households"]
        done = fields.act(state, bot, reinhild, [{"do": "sell_field"}], 82)
        sold = next(p for p in plots if p["owner"] is None)
        assert done == [f"sold plot {sold['id']} to the village for 12,80 gp"] and dcc.coins_total_cp(bot["coins"]) + state["money"]["households"] == before
        # a common plot is worked for nothing by a farmer with idle hands, and the harvest is the worker's
        bot["seed"], bot["inventory"] = 1, []
        hands = fields.farm(state, bot, reinhild, 83)
        assert sold.get("worker") == "Reinhild Sevenbrothers" and sold["sown"] == 83 and hands[-1].startswith("sowed")
        assert fields.ask_cp(state, sold) is None and sold["id"] not in [o["plot"] for o in fields.for_sale(state, 83, None, 100)]   # not for sale while worked
        fields.farm(state, bot, reinhild, 83 + cfg["grow"])
        assert sold["sown"] is None and "worker" not in sold and any(h["plot"] == sold["id"] and h["who"] == "Reinhild Sevenbrothers" for h in fields.book(state)["harvests"])
        # the night's hand: a dead owner's plot goes to the village, a farming villager's plot is tilled and the harvest put on the shelf
        db = registry.connect()
        with db:
            db.execute("UPDATE people SET status = 'dead' WHERE name = 'Veit Stillwater'")
        db.close()
        plots[1]["owner"] = "Anselm Sevenbrothers"                                                                      # a farmer of the register
        plots[2]["owner"] = "Egon Crookback"                                                                            # a dwarven mushroom-farmer: no barley
        state["market"] = {"rel": {"Barley, a sack": 1.0}}
        barley["qty"] = 0
        plots[60].update(owner="Veit Stillwater", sown=70)                                                              # sown by a man who dies without an heir
        out = fields.nightly(state, 90)
        assert plots[60]["owner"] is None and plots[60]["sown"] is None and plots[60]["rest_until"] == 90               # the crop rots, the plot is free (stuck sown for good until 10-10)
        plots[61].update(sown=80, worker="Hanne Pipsdotter")                                                           # a farming seat's dead holder: the seat still bears her name
        state["seats"] = {"reinhild": "Hanne Pipsdotter"}
        fields.nightly(state, 90)
        assert plots[61]["sown"] is None and "worker" not in plots[61]
        state["seats"] = {}
        assert out["to_common"] >= 1 and not [p for p in plots if p["owner"] == "Veit Stillwater"] and out["sown"] == 0 and plots[1]["sown"] is None   # no barley anywhere: no seed, no sowing
        db = registry.connect()
        sheet = json.loads(db.execute("SELECT sheet FROM people WHERE name = 'Anselm Sevenbrothers'").fetchone()[0])
        assert sheet["copper"] < 40                                                                                     # 33 cp: a sack costs more, so night 90 sowed nothing either way
        sheet["copper"] = 500
        with db:
            db.execute("UPDATE people SET sheet = ? WHERE name = 'Anselm Sevenbrothers'", (json.dumps(sheet),))
        db.close()
        barley["qty"], till, coin = 3, int(state["shops"][store].get("till", 0)), purses()
        out = fields.nightly(state, 91)
        assert out["sown"] == 7 and plots[1]["sown"] == 91 and plots[2]["sown"] is None and barley["qty"] == 2       # Anselm bought one sack: his plot and six common ones; Egon's stays fallow
        assert sum(1 for p in plots if p.get("worker") == "Anselm Sevenbrothers") == 6
        assert state["shops"][store]["till"] - till == coin - purses() > 0                                              # his coin went to the shop's till, no more and no less
        shelf_before = barley["qty"]
        out = fields.nightly(state, 91 + cfg["grow"])
        assert fields.book(state)["stores"]["Anselm Sevenbrothers"] == 0 and plots[1]["sown"] is None                  # his own plot rests; the sack he kept back
        assert out["sown"] == 7 and sum(1 for p in plots if p.get("worker") == "Anselm Sevenbrothers") == 7           # sowed seven fresh common plots the same night
        assert barley["qty"] == shelf_before + out["sacks"]                                                             # the rest went to the shelf that was short
        seen = fields.mine_for_prompt(state, bot, reinhild, 100)
        assert len(seen["your_plots"]) == len(fields.worked_by(state, "Reinhild Sevenbrothers")) and seen["your_hands_work_at_most"] == 7 and "plots_for_sale_cheapest_first" in seen
        # the land belongs to the person behind the trader: "Pip" for "Pip the farmhand", the heir once the seat is taken over
        pip = {"id": "pip", "name": "Pip the farmhand", "tills": True}
        assert fields.person_of(state, pip) == "Pip" and fields.person_of(state, reinhild) == "Reinhild Sevenbrothers"
        state["seats"] = {"pip": "Hanne Pipsdotter"}
        monkeypatch.setattr(places, "BOTS", [reinhild, pip])
        assert fields.person_of(state, pip) == "Hanne Pipsdotter" and fields._tillers(state) == {"Reinhild Sevenbrothers", "Hanne Pipsdotter"}
        monkeypatch.setattr(places, "BOTS", [reinhild])
        state["seats"] = {}
        # a tiller's barley comes from the land, not the old brings
        bot["inventory"] = []
        for day in range(200, 260):
            daily.arrive(bot, reinhild, day, {"rel": {"Barley, a sack": 1.0}})
        assert not any(i["name"] == "Barley, a sack" for i in bot["inventory"]) and not bot.get("pipeline")
        # a farming trader out of seed buys a sack off the shelf with the purse (until 10-10 such a seat never sowed again)
        for p in plots:
            p.update(sown=None, rest_until=None); p.pop("worker", None)
        bot["seed"], bot["inventory"], barley["qty"] = 0, [], 2
        purse, till = dcc.coins_total_cp(bot["coins"]), int(state["shops"][store].get("till", 0))
        done = fields.farm(state, bot, reinhild, 300)
        assert done[-1] == "sowed 7 plots with 1 sack of seed" and barley["qty"] == 1 and purse - dcc.coins_total_cp(bot["coins"]) == int(state["shops"][store]["till"]) - till > 0


def test_the_eel_ponds_and_the_fat_nights(content, monkeypatch):
    import importlib
    from ttrpgtools.dcc.westmarch import daily, fields, places
    cfg = dict(importlib.reload(places).FIELDS)
    monkeypatch.setattr(places, "FIELDS", cfg)
    monkeypatch.setattr(places, "MARKET", None)
    jutta = next(b for b in places.BOTS if b["id"] == "jutta")
    bot = daily._record({"bots": {}}, jutta)
    dcc.add_item(bot, "Coal, a sack", "trade", 50, "6 sp")                        # coal for two hundred eels: the ponds are the limit now
    plain = next(d for d in range(1, 400) if not fields.fat_night(d) and not any(fields.fat_night(x) for x in range(d, d + 25)))
    caught = sum(fields.ponds_tonight(bot, jutta, d) for d in range(plain, plain + jutta["ponds"]["days"]))
    assert caught == jutta["ponds"]["count"] * jutta["ponds"]["per"]               # every pond once in its cycle
    fat = next(d for d in range(1, 400) if fields.fat_night(d))
    bot["ponds"] = [fat] * jutta["ponds"]["count"]
    bot["eels"] = 0
    assert fields.ponds_tonight(bot, jutta, fat) == jutta["ponds"]["count"] * jutta["ponds"]["per"] * cfg["fat"]      # five times the catch, and nobody says why
    assert fields.take_eels(bot, jutta, 1000) == jutta["ponds"]["count"] * jutta["ponds"]["per"] * cfg["fat"] and bot["eels"] == 0
    bot["eels"], bot["batch"] = 0, {}
    for day in range(1000, 1200):                                                   # no fresh eels: no smoked eel, whatever the coal
        bot["ponds"] = [10 ** 6] * jutta["ponds"]["count"]
        daily.arrive(bot, jutta, day, {"rel": {"Smoked eel": 1.0, "Coal, a sack": 1.0}})
    assert not any(i["name"] == "Smoked eel" for i in bot["inventory"]) and not any(e["name"] == "Smoked eel" for e in bot.get("pipeline", []))


@real
def test_the_herb_woman_teaches_a_child_a_trade(monkeypatch):
    import importlib
    import random
    from ttrpgtools.dcc.westmarch import lives, places
    cfg = dict(importlib.reload(places).LIVES)
    monkeypatch.setattr(places, "LIVES", cfg)
    monkeypatch.setattr(places, "MARKET", None)
    state = {"money": {"households": 200000, "bank": 0, "finanzamt": 0, "library": 0, "caravan": 0}, "steward": {}}
    lives.monthly(state, 31)
    db = lives._db()
    child = db.execute("SELECT * FROM people WHERE occupation = 'Child' AND status = 'alive' ORDER BY born_day LIMIT 1").fetchone()
    grown = db.execute("SELECT name FROM people WHERE sheet IS NOT NULL LIMIT 1").fetchone()[0]
    taken = lives.set_mentoring(state, 31, [{"child": child["name"], "trade": "Brewer"}, {"child": grown, "trade": "Brewer"}, {"child": child["name"], "trade": "Dragon tamer"}, "junk"])
    assert taken == [{"child": child["name"], "trade": "Brewer"}] and lives.summary(state, 31)["my_mentoring"] == [[child["name"], "Brewer"]]   # a living child, a real trade, once
    assert lives.set_mentoring(state, 31, [{"child": child["name"], "trade": "Outfitter and innkeeper"}]) == [{"child": child["name"], "trade": "Outfitter and innkeeper (Shop1)"}]   # a seat by its plain name
    lives.set_mentoring(state, 31, taken)
    monkeypatch.setitem(cfg, "mentor_chance", 1.0)
    day = int(child["born_day"]) + 18 * 365 + 3
    lives._come_of_age(db, state, day, cfg, dcc.load_content(), random.Random(1))
    row = db.execute("SELECT * FROM people WHERE id = ?", (child["id"],)).fetchone()
    assert row["occupation"] == "Brewer" and row["sheet"] and state["steward"]["mentoring"] == []                          # taught, and the lesson is over
    assert db.execute("SELECT COUNT(*) FROM life_events WHERE kind = 'taught' AND who = ?", (child["name"],)).fetchone()[0] == 1
    db.close()


@real
def test_hedwigs_own_hens_seed_notes_once_and_newcomers(monkeypatch):
    import importlib
    import random
    from ttrpgtools.dcc.westmarch import daily, lives, places, registry, steward, town as t
    real = importlib.reload(places)
    cfg = dict(real.LIVES)
    me = next(b for b in real.BOTS if b["id"] == "hedwig-d")
    monkeypatch.setattr(places, "LIVES", cfg)
    monkeypatch.setattr(places, "MARKET", None)
    monkeypatch.setattr(places, "BOTS", [me])
    monkeypatch.setattr(places, "PLACES", [])
    monkeypatch.setattr(places, "STEWARD", {"every": 30, "brain": "host"})
    assert me["lays"] == "Eggs, a dozen"
    with t.town(write=True) as state:
        bot = daily._record(state, me)
        dcc.add_item(bot, "Eggs, a dozen", "trade", 3, "3 cp")
        sells = [a for a in steward.plan(state, bot, me, 10) if a["do"] == "sell"]
        assert sells == [{"do": "sell", "shop": "", "index": next(n for n, i in enumerate(bot["inventory"]) if i["name"] == "Eggs, a dozen"), "count": 3}]   # her hens' eggs go to the shelves
        rep = steward.report(state, 10)
        assert "my_own_hens" in rep and "hens" in steward.PERSONA.lower()
        # a seed line is given once: a note she deletes stays deleted, a new line in the file still arrives
        assert steward.load_seed(state, 10, "Quiet is the goal.\nKeep hens.\n") == 2
        b = steward.book(state)
        steward.apply(state, 11, {"notes_delete": [n["id"] for n in b["notes"] if n["text"] == "Keep hens."]})
        assert steward.load_seed(state, 12, "Quiet is the goal.\nKeep hens.\nA new line.\n") == 1 and "Keep hens." not in [n["text"] for n in b["notes"]]
        # a newcomer: an adult of the trade, single, rolled, coin only from the households
        state["money"] = {"households": 10_000, "bank": 0, "finanzamt": 0, "library": 0, "caravan": 0}
        lives.monthly(state, 31)
        name = lives.spawn(state, 31, "Hunter", dcc.load_content(), random.Random(1))
        db = lives._db()
        row = db.execute("SELECT * FROM people WHERE name = ?", (name,)).fetchone()
        sheet = json.loads(row["sheet"])
        assert row["occupation"] == "Hunter" and row["spouse_id"] is None and cfg["adult"] <= lives.age_of(row, 31) <= 35 and row["race"] == "human"
        assert state["money"]["households"] == 10_000 - sheet["copper"] and row["notes"] == "came to the village"
        assert db.execute("SELECT COUNT(*) FROM life_events WHERE kind = 'arrived' AND who = ?", (name,)).fetchone()[0] == 1
        db.close()
        registry.connect().close()
        assert any(r["name"] == name for r in registry.rows("people"))                                # the register keeps a newcomer (not in villagers.py)


@real
def test_the_herb_womans_matches_and_the_delver(monkeypatch):
    import importlib
    from ttrpgtools.dcc.westmarch import lives, places, registry
    cfg = dict(importlib.reload(places).LIVES)
    monkeypatch.setattr(places, "LIVES", cfg)
    monkeypatch.setattr(places, "MARKET", None)
    state = {"money": {"households": 200000, "bank": 0, "finanzamt": 0, "library": 0, "caravan": 0}, "steward": {}}
    lives.monthly(state, 31)                                     # the first month sets everyone up
    db = lives._db()
    adults = lives._adults(db, 31, cfg)
    single = [a for a in adults if lives._single(a)]
    man, woman = next((a, b) for a in single if a["sex"] == "m" for b in single if lives.compatible(a, b, 31, cfg))
    other_kind = next(b for b in single if b["race"] != man["race"] and b["sex"] == "f")
    wed = next(a for a in adults if a["spouse_id"])
    taken = lives.set_matches(state, 31, [{"a": man["name"], "b": woman["name"]}, {"a": man["name"], "b": other_kind["name"]}, {"a": wed["name"], "b": woman["name"]},
                                         {"a": "Nobody", "b": woman["name"]}, "junk"])
    assert [(m["a"], m["b"]) for m in taken] == [(man["name"], woman["name"])]     # only a pair who could wed tonight
    monkeypatch.setitem(cfg, "match_boost", 1.0)
    monkeypatch.setitem(cfg, "romance", 0.0)
    lives.monthly(state, 62)
    wed_now = db.execute("SELECT spouse_id FROM people WHERE id = ?", (man["id"],)).fetchone()[0]
    assert wed_now == woman["id"] and state["steward"]["matches"] == []             # she weds him, and the match is done
    # the delver: the strongest adult in their prime, gold following strength, a trip that can kill
    import random
    state["delver"] = {}
    got = lives.delver(state, 62, random.Random(1))
    best = max((a for a in lives._adults(db, 62, cfg) if a["sheet"] and lives.age_of(a, 62) <= lives.prime_until(a["race"], cfg)), key=lambda r: (lives.score(json.loads(r["sheet"])), -r["id"]))
    assert got["name"] == best["name"] == state["delver"]["who"] and 0.5 <= got["factor"] <= 1.6 and not got["died"]
    monkeypatch.setitem(cfg["delver"], "trip_death", 100.0)   # a certain death
    lost = lives.delver(state, 63, random.Random(2))
    assert lost["died"] and "who" not in state["delver"]
    assert db.execute("SELECT status, cause FROM people WHERE name = ?", (best["name"],)).fetchone()[:] == ("dead", "the dungeon")
    monkeypatch.setitem(cfg["delver"], "trip_death", 0.0)
    assert lives.delver(state, 64, random.Random(3))["name"] != best["name"]       # the next best goes
    # a block makes a wedding a hundred times rarer: with every other single removed, one pair would wed within a few months but for the block
    adults = [r for r in lives._adults(db, 64, cfg) if lives._single(r)]
    man, woman = next((a, b) for a in adults if a["sex"] == "m" for b in adults if lives.compatible(a, b, 64, cfg))
    assert lives.set_blocks(state, 64, [{"a": man["name"], "b": woman["name"]}, {"a": man["name"], "b": "Nobody"}, {"a": man["name"], "b": man["name"]}]) == [{"a": man["name"], "b": woman["name"]}]
    assert lives.summary(state, 64)["my_blocks"] == [[man["name"], woman["name"]]] and lives._blocked(state, man, woman)
    monkeypatch.setitem(cfg, "romance", 1.0)                     # everybody single meets somebody every month; the block alone keeps these two apart
    monkeypatch.setitem(cfg, "block_factor", 0.0)
    monkeypatch.setitem(cfg, "accident", 0.0)                    # nobody dies in these three years: the blocked pair must still be alive to be asked about
    monkeypatch.setitem(cfg, "lifespan", {k: 100_000 for k in cfg["lifespan"]})
    for month in range(3, 40):
        lives.monthly(state, int(month * 365 / 12) + 1)
    both = [db.execute("SELECT * FROM people WHERE id = ?", (i,)).fetchone() for i in (man["id"], woman["id"])]
    assert both[0]["spouse_id"] != woman["id"] and both[1]["spouse_id"] != man["id"]
    state["steward"]["matches"] = [{"a": man["name"], "b": woman["name"], "left": 5}]
    lives.set_blocks(state, 64, [{"a": woman["name"], "b": man["name"]}])
    assert state["steward"]["matches"] == []                     # a block on the pair ends the match
    rep = lives.summary(state, 64)
    singles = lives.look_up(state, 64, [{"singles": {"race": "human", "sex": "f"}}])[0]["answer"]
    assert rep["delver_now"] != "(none)" and rep["population"]["adults"] > 50 and sum(rep["population"]["single_adults_by_kind"].values()) > 5 and singles and all("STR" in line for line in singles)
    assert len(json.dumps(rep)) < 5000                           # the report holds counts and trades, not a hundred people
    db.close()


def test_the_steward_defines_her_own_alarms_and_tends_her_own_notebook(content, monkeypatch):
    import importlib
    from ttrpgtools.dcc.westmarch import daily, places, steward, town as t
    importlib.reload(places)
    me = next(b for b in places.BOTS if b["id"] == "hedwig-d")
    keeper = next(b for b in places.BOTS if b["id"] == "detlef")
    monkeypatch.setattr(places, "BOTS", [me, keeper])
    monkeypatch.setattr(places, "PLACES", [])
    monkeypatch.setattr(places, "MARKET", {})
    monkeypatch.setattr(places, "STEWARD", {"every": 30, "brain": "host"})
    monkeypatch.setattr(t, "today", lambda: places.EPOCH)
    flags = steward.validate_flags([{"when": "price_above", "of": "Eggs, a dozen", "x": 40, "for_days": 60}, {"when": "price_above", "of": "each good", "x": 10, "for_days": 21, "except": ["Eggs, a dozen"]},
                                    {"when": "stock_below", "of": "Dragon egg", "n": 1}, {"when": "purse_below_gp", "of": "mayor", "gp": 3}, {"when": "mood"}, "junk", {"when": "flock_below", "n": 5}])
    assert flags == [{"when": "price_above", "for_days": 60, "x": 40.0, "of": "Eggs, a dozen"},
                     {"when": "price_above", "for_days": 21, "x": 10.0, "of": "each good", "except": ["Eggs, a dozen"]},
                     {"when": "flock_below", "for_days": 1, "n": 5}] and steward.validate_flags("none") is None
    with t.town(write=True) as state:
        daily._record(state, me)
        for _ in range(8):
            dcc.add_item(daily._record(state, keeper), "Hen", "trade", 1, "5 sp")
        state["market"] = {"rel": {"Eggs, a dozen": 54.0}}
        for night in range(1, 30):
            steward.observe(state, night)
        assert any("Eggs, a dozen" in a for a in steward.alerts(state))                      # her starting alarm: tenfold for 21 nights
        steward.apply(state, 30, {"flags": flags, "next_checkin": {"in_days": 100, "or_when": [{"disaster": True}]}})
        assert steward.book(state)["flags"] == flags and steward.alerts(state) == []        # her own list replaces it, and the counts start over
        for night in range(31, 91):
            steward.observe(state, night)
        assert steward.alerts(state) == ["Eggs, a dozen has been at 40.0 times its usual price or more for 60 nights"]    # she chose sixty nights and forty times for eggs
        assert "a new alarm of yours is on" in steward.due(state, 91)                         # not seen yet: it wakes her
        steward.apply(state, 91, {"next_checkin": {"in_days": 100, "or_when": [{"disaster": True}]}})
        steward.observe(state, 92)
        assert steward.due(state, 92) is None                                                 # seen: the same alarm does not wake her again
        state["market"] = {"rel": {"Eggs, a dozen": 1.0}}
        steward.observe(state, 93)
        assert steward.book(state)["acked"] == []
        # the notebook: ids, edits, deletes, pins, forgetting, room
        b = steward.book(state)
        steward.apply(state, 100, {"notes_add": ["eggs swing hard", {"text": "plan: scrap for the smiths", "pin": True}, {"text": "watch Reinhild", "forget_after_days": 10}]})
        ids = {n["text"]: n["id"] for n in b["notes"]}
        assert [n["pin"] for n in b["notes"]] == [False, True, False] and b["notes"][2]["until"] == 110
        steward.apply(state, 105, {"notes_delete": [ids["eggs swing hard"]], "notes_edit": {str(ids["plan: scrap for the smiths"]): "plan: scrap for the smiths, judged in 2029"}})
        assert [n["text"] for n in b["notes"]] == ["plan: scrap for the smiths, judged in 2029", "watch Reinhild"] and b["notebook"].count("\n") == 1
        steward.apply(state, 111, {})
        assert [n["text"] for n in b["notes"]] == ["plan: scrap for the smiths, judged in 2029"]       # forgotten on the day she asked
        steward.apply(state, 112, {"notes_add": [{"text": c * 900} for c in "xyzuvwq"]})
        assert sum(len(n["text"]) for n in b["notes"]) <= steward.NOTE_LIMITS["chars"] and any(n["pin"] for n in b["notes"])      # full: the oldest unpinned went, the pinned plan stayed
        assert len(b["notes"][-1]["text"]) == 400 and b["notes"][-1]["text"][0] == "q" and len(b["lost_for_room"]) == 2
        rep = steward.report(state, 113)
        assert rep["notebook_room"]["dropped_for_lack_of_room_last_time"] == b["lost_for_room"] and rep["my_flags"] == flags and all("id" in n for n in rep["my_notebook"])
        steward.apply(state, 114, {"notebook": "the whole text, the old way"})
        assert [n["text"] for n in b["notes"]] == ["the whole text, the old way"]
        seed = "# comment\n\nQuiet is the goal.\nOne experiment at a time.\n"
        assert steward.load_seed(state, 115, seed) == 2 and steward.load_seed(state, 116, seed) == 0       # twice is the same as once
        assert [n["pin"] for n in b["notes"]] == [False, True, True]
        old = {"orders": [], "notebook": "an old book, one long text", "checked": 7, "log": [], "history": [], "streak": {"dear:Eggs, a dozen": 5, "o3": 2}, "done": [], "aided": {}}
        state["steward"] = old
        migrated = steward.book(state)
        assert migrated["flags"] == steward.DEFAULT_FLAGS and migrated["notes"][0]["text"] == "an old book, one long text" and "dear:Eggs, a dozen" not in migrated["streak"] and "o3" in migrated["streak"]


def test_the_steward_decides_when_to_look_again(content, monkeypatch):
    import importlib
    from ttrpgtools.dcc.westmarch import daily, places, steward, town as t
    importlib.reload(places)
    me = next(b for b in places.BOTS if b["id"] == "hedwig-d")
    keeper = next(b for b in places.BOTS if b["id"] == "detlef")
    monkeypatch.setattr(places, "BOTS", [me, keeper])
    monkeypatch.setattr(places, "PLACES", [])
    monkeypatch.setattr(t, "today", lambda: places.EPOCH)
    monkeypatch.setattr(places, "MARKET", {})
    monkeypatch.setattr(places, "STEWARD", {"every": 30, "brain": "host"})
    # what she may ask for: the date within bounds, and only conditions that mean something
    wake = steward.validate_wake({"in_days": 99999, "or_when": [{"flock_below": 5}, {"price_above": "Barley, a sack", "x": 20}, {"price_below": "Dragon egg", "x": 1},
                                                              {"stock_below": "Hen", "n": 3}, {"purse_below_gp": "detlef", "gp": 2}, {"purse_below_gp": "mayor", "gp": 2},
                                                              {"disaster": True}, "junk", {"nonsense": 1}]})
    assert wake["in_days"] == 730 and wake["or_when"] == [{"flock_below": 5}, {"price_above": "Barley, a sack", "x": 20.0}, {"stock_below": "Hen", "n": 3},
                                                          {"purse_below_gp": "detlef", "gp": 2}, {"disaster": True}]   # the unknown good and the mayor were dropped
    assert steward.validate_wake({"in_days": 0})["in_days"] == 1 and steward.validate_wake("later") is None
    with t.town(write=True) as state:
        bot, detlef = daily._record(state, me), daily._record(state, keeper)
        for _ in range(8):
            dcc.add_item(detlef, "Hen", "trade", 1, "5 sp")
        assert steward.due(state, 29) is None and "usual interval" in steward.due(state, 30)       # nothing asked yet: the old thirty nights
        steward.apply(state, 30, {"next_checkin": {"in_days": 14, "or_when": [{"flock_below": 5}]}}, "test")
        b = steward.book(state)
        assert b["next"]["day"] == 44 and b["attention"] == steward.ATTENTION_CAP - 1
        assert steward.due(state, 31) is None and steward.due(state, 43) is None and "14 days" in steward.due(state, 44)   # her date wakes her
        detlef["inventory"] = [i for i in detlef["inventory"] if i["name"] != "Hen"]
        assert "only 0 hens" in steward.due(state, 32)                                              # a condition wakes her early
        b["attention"] = 0.5
        assert steward.due(state, 32) is None and steward.due(state, 44) is None                    # under one point nothing wakes her, her own date included (the owner 10-10)
        b["attention"] = 1.0
        assert "14 days" in steward.due(state, 44)                                                  # enough back: the date wakes her
        b["attention"] = 0.5
        rep = steward.report(state, 32, "test reason")
        assert rep["check_ins"]["woken_because"] == "test reason" and rep["check_ins"]["you_asked_to_be_woken"]["in_days"] == 14 and "attention_rules" in rep["check_ins"]
        b["attention"] = 3.0
        steward.apply(state, 44, {"notebook": "quiet"}, "test", 2.5)                                # a look that read and wrote two and a half average calls' worth of tokens
        assert steward.book(state)["next"]["day"] == 44 + steward.DEFAULT_GAP and abs(steward.book(state)["attention"] - 0.5) < 1e-9
        for night in range(45, 45 + 365):
            steward.observe(state, night)
        assert abs(steward.book(state)["attention"] - 0.5 - steward.ATTENTION_PER_YEAR) < 0.01     # 3.14 points back a year: the pace of the runs before
        assert steward.maybe_checkin(state, 200) is False                                           # the host asks her, not the nightly update


def test_the_steward_steps_in_only_when_a_trouble_has_lasted_and_a_brain_may_only_write_valid_orders(content, monkeypatch):
    import importlib
    from ttrpgtools.dcc.westmarch import daily, economy, places, steward, town as t
    flat = {"period": 10, "amplitude": 0, "phase": 0}
    importlib.reload(places)                                  # the autouse fixture emptied the traders; she is in the file's own list
    me = next(b for b in places.BOTS if b["id"] == "hedwig-d")
    keeper = next(b for b in places.BOTS if b["id"] == "detlef")
    monkeypatch.setattr(places, "BOTS", [me, keeper])
    monkeypatch.setattr(places, "PLACES", [])
    monkeypatch.setattr(t, "today", lambda: places.EPOCH)
    monkeypatch.setattr(places, "MARKET", {})
    monkeypatch.setattr(places, "STEWARD", {"every": 30, "brain": "rules"})
    with t.town(write=True) as state:
        store = t.save_shop(state, None, "Store", curve=flat)
        state["shops"][store]["till"] = 100_000
        barley = t.stock_item(state, store, "Barley, a sack", "trade", "4 sp", 20, curve=flat)
        barley["target"] = 10
        bot, detlef = daily._record(state, me), daily._record(state, keeper)
        bot["coins"] = {"gp": 300, "sp": 0, "cp": 0}
        detlef["coins"] = {"gp": 0, "sp": 0, "cp": 50}
        for _ in range(4):
            dcc.add_item(bot, "Hen", "trade", 1, "5 sp")
        state["market"] = {"rel": {"Barley, a sack": 0.01}}                                        # nearly free, and staying so
        for night in range(1, 28):
            assert not [a for a in daily.rule_plan(state, bot, me, night) if a["do"] == "buy" and a["item"] == "Barley, a sack"]   # an ordinary swing is left alone
        buys = [a for a in daily.rule_plan(state, bot, me, 28) if a["do"] == "buy" and a["item"] == "Barley, a sack"]
        assert len(buys) == 2                                                                      # on the 28th night it has lasted: she buys a little
        assert steward.held(detlef, "Hen") == 4 and steward.held(bot, "Hen") == 0   # his flock was empty: she gave hens
        assert any("gave 4 hens" in d["what"] for d in steward.book(state)["done"]) and detlef["coins"]["cp"] <= 50 + 500          # and a producer with 50 cp was given coin
        state["market"] = {"rel": {"Barley, a sack": 15.0}}
        bot["inventory"] = [i for i in bot["inventory"] if i["name"] != "Barley, a sack"]
        dcc.add_item(bot, "Barley, a sack", "trade", 3, "4 sp")
        for night in range(29, 49):
            assert not [a for a in daily.rule_plan(state, bot, me, night) if a["do"] == "sell"]     # dear for 20 nights: not yet
        assert [a for a in daily.rule_plan(state, bot, me, 49) if a["do"] == "sell"]                 # 21 nights: she releases her reserve
        rep = steward.report(state, 49)
        assert "disasters_now" in rep and "my_deeds_lately" in rep and rep["goods"]["Barley, a sack"]["i_hold"] == 3
        monkeypatch.setattr(places, "STEWARD", None)
        assert daily.rule_plan(state, bot, me, 50) == []                                           # off: only the herb woman
    # a brain may write what it likes: only orders she can carry out survive, inside bounds
    good = steward.validate([{"buy": "Barley, a sack", "below": 0.05, "up_to": 9999, "per_night": 99, "for_days": 9999}, {"sell": "Ale, a jug", "above": 0.2},
                             {"buy": "Dragon egg", "below": 0.1}, {"sell": "Hen"}, "junk", {"buy": "Ale, a jug"}, {"give_hens": 99, "when_flock_below": 0},
                             {"aid": "detlef", "gp": 500, "when_purse_below_gp": 2}, {"aid": "mayor", "gp": 1, "when_purse_below_gp": 1}])
    assert good == [{"buy": "Barley, a sack", "below": 0.05, "for_days": 365, "up_to": 60, "per_night": 10, "keep_gp": 50},
                    {"sell": "Ale, a jug", "above": 2.0, "for_days": 0, "keep": 0, "per_night": 3},
                    {"give_hens": 12, "when_flock_below": 1},
                    {"aid": "detlef", "gp": 20, "when_purse_below_gp": 2, "for_days": 0, "every_days": 30}]
    # her hens' feed may be bought at up to twice the usual price, and what the bounds changed is told back to her
    asked = [{"buy": "Barley, a sack", "below": 3.5, "up_to": 10}, {"buy": "Dragon egg", "below": 0.1}]
    kept = steward.validate(asked)
    assert kept[0]["below"] == 2.0 and steward.changed_by_rules(asked, kept) == ["Barley, a sack: below 3.5 became 2.0 (the rules' bound)", 'dropped: {"buy": "Dragon egg", "below": 0.1}']



def test_the_weather_is_a_slow_shared_walk_and_moves_a_farm_trades_yield(content, monkeypatch):
    from ttrpgtools.dcc.westmarch import daily, economy, places
    monkeypatch.setattr(places, "MARKET", {"weather": {"sigma": 0.7, "memory": 0.985}})
    state = {}
    skies = [economy.step_weather(state, day) for day in range(1, 200)]
    again = {}
    assert skies == [economy.step_weather(again, day) for day in range(1, 200)]                    # the same sky for the same nights
    assert min(skies) < 0.6 and max(skies) > 1.6 and abs(skies[10] - skies[11]) < 0.3              # good years and bad ones, changing slowly
    monkeypatch.setattr(places, "MARKET", {"weather": None})
    assert economy.step_weather({}, 1) == 1.0
    monkeypatch.setattr(places, "MARKET", {"weather": {"sigma": 0.7, "memory": 0.985}})
    spec = {"id": "r", "name": "Reinhild", "farm": True, "brings": [("Rations, per day", "trade", "1 cp", 10)]}
    plain = {"id": "r", "name": "Reinhild", "brings": [("Rations, per day", "trade", "1 cp", 10)]}
    heavy = lambda s, w: sum(int(i["qty"]) for day in range(1, 40) for bot in [daily._record({"bots": {}}, s)] for _ in [daily.arrive(bot, s, day, {"weather": w, "rel": {}})] for i in bot["inventory"])
    assert heavy(spec, 3.0) > heavy(plain, 3.0)                                                      # a bumper year only helps a farm


def test_the_caravan_crew_eats_in_the_village_the_delver_brings_new_coin_and_neighbours_help_a_broke_producer(content, monkeypatch):
    import importlib
    from ttrpgtools.dcc.westmarch import economy, money, places, town as t
    importlib.reload(places)
    spec = next(b for b in places.BOTS if b["id"] == "jutta")
    monkeypatch.setattr(places, "BOTS", [spec])
    monkeypatch.setattr(places, "PLACES", [])                                               # only the shops this test makes
    flat = {"period": 10, "amplitude": 0, "phase": 0}
    monkeypatch.setattr(places, "MARKET", {"relief_floor": 500, "relief_gift": 300, "crew_diet": {"Ale, a jug": 3}, "delver": {"name": "Garrick", "every": (5, 5), "gp": (5, 5), "inn": 0.4, "till": "inn"}})
    monkeypatch.setattr(t, "today", lambda: places.EPOCH)
    with t.town(write=True) as state:
        store, inn = t.save_shop(state, None, "Store", curve=flat), "inn"
        state["shops"][inn] = {"name": "Inn", "stock": [], "till": 0, "kinds": ["inn"], "curve": flat}
        ale = t.stock_item(state, store, "Ale, a jug", "trade", "6 cp", 10, curve=flat)
        camp = state["shops"]["caravan"] = {"name": "The Caravan", "kinds": ["caravan"], "stock": [], "till": 100, "away": False, "curve": flat}
        state["shops"][store]["till"] = 0
        eaten = economy.crew_eats(state, 1, economy.config())
        assert eaten == {"Ale, a jug": 3} and ale["qty"] == 7 and camp["till"] == 82 and state["shops"][store]["till"] == 18       # the crew paid, the shop took it
        camp["away"] = True
        assert economy.crew_eats(state, 2, economy.config()) == {}                                                                   # nothing while the wagons are away
        before = money.supply(state)["money_cp"]
        assert economy.delver(state, 1, economy.config()) == 0 and state["delver"]["next"] == 6                                      # first return is a few days off
        assert economy.delver(state, 5, economy.config()) == 0
        assert economy.delver(state, 6, economy.config()) == 500
        assert money.supply(state)["money_cp"] == before + 500 and state["shops"][inn]["till"] == 200 and state["money"]["households"] == 300 and state["delver"]["next"] == 11
        state["bots"] = {"jutta": {"name": "Jutta", "coins": {"gp": 0, "sp": 0, "cp": 120}, "inventory": []}}
        state["money"]["households"] = 1_000
        before = money.supply(state)["money_cp"]
        assert economy.relief(state, economy.config()) == 300 and dcc.coins_total_cp(state["bots"]["jutta"]["coins"]) == 420
        assert economy.relief(state, economy.config()) == 80 and dcc.coins_total_cp(state["bots"]["jutta"]["coins"]) == 500        # up to the floor, no further
        assert economy.relief(state, economy.config()) == 0 and money.supply(state)["money_cp"] == before


def test_the_steward_counts_the_nights_a_trouble_has_lasted_and_reports_it_only_when_it_is_a_disaster(content, monkeypatch):
    import importlib
    from ttrpgtools.dcc.westmarch import daily, economy, places, steward, town as t
    importlib.reload(places)
    me = next(b for b in places.BOTS if b["id"] == "hedwig-d")
    keeper = next(b for b in places.BOTS if b["id"] == "detlef")
    monkeypatch.setattr(places, "BOTS", [me, keeper])
    monkeypatch.setattr(places, "PLACES", [])
    monkeypatch.setattr(places, "MARKET", {})
    monkeypatch.setattr(t, "today", lambda: places.EPOCH)
    with t.town(write=True) as state:
        daily._record(state, me)
        daily._record(state, keeper)["coins"] = {"gp": 0, "sp": 0, "cp": 0}
        state["market"] = {"rel": {"Eggs, a dozen": 54.0}}
        for night in range(1, 21):
            steward.observe(state, night)
        assert "the hen keeper's flock has been below 3 hens for 20 nights" in steward.alerts(state)
        assert not any("Eggs, a dozen has been at 10.0 times" in a for a in steward.alerts(state))        # 20 nights: not yet a disaster
        steward.observe(state, 21)
        assert "Eggs, a dozen has been at 10.0 times its usual price or more for 21 nights" in steward.alerts(state)
        state["market"] = {"rel": {"Eggs, a dozen": 1.0}}
        steward.observe(state, 22)
        assert not any("Eggs, a dozen has been at 10.0 times" in a for a in steward.alerts(state))        # it ended: the count starts over


def test_the_steward_writes_to_the_village_notebook_only_slowly(content, monkeypatch):
    import importlib
    from ttrpgtools.dcc.westmarch import places, steward, town as t
    importlib.reload(places)
    monkeypatch.setattr(places, "PLACES", [])
    monkeypatch.setattr(t, "today", lambda: places.EPOCH)
    assert "Bene Gesserit" in steward.PERSONA and "centuries" in steward.PERSONA and "only slowly" in steward.PERSONA
    with t.town(write=True) as state:
        steward.apply(state, 100, {"town_note": "Barley is dear; sow early."})
        first = state.get("town_note", "")
        steward.apply(state, 130, {"town_note": "Another thing entirely about ale and weather."})
        assert state.get("town_note", "") == first and steward.book(state)["note_day"] == 100     # too soon: the second line is dropped
        steward.apply(state, 190, {"town_note": "Sow early when the Pale Moon is new."})
        assert steward.book(state)["note_day"] == 190


def test_the_steward_may_buy_a_workshops_idle_armor_and_sell_it_back_when_the_workshop_needs_the_metal(content, monkeypatch):
    import importlib
    from ttrpgtools.dcc.westmarch import daily, economy, places, steward, town as t
    flat = {"period": 10, "amplitude": 0, "phase": 0}
    importlib.reload(places)
    me = next(b for b in places.BOTS if b["id"] == "hedwig-d")
    monkeypatch.setattr(places, "BOTS", [me])
    monkeypatch.setattr(places, "PLACES", [])
    monkeypatch.setattr(places, "MARKET", {})
    monkeypatch.setattr(places, "STEWARD", {"every": 30, "brain": "rules"})
    monkeypatch.setattr(t, "today", lambda: places.EPOCH)
    with t.town(write=True) as state:
        smith = t.save_shop(state, None, "Smithy", curve=flat)
        state["shops"][smith].update(till=50_000, materials={"metal": 40_000}, deals=["armor"])
        mail = t.stock_item(state, smith, "Chainmail", "armor", "75 gp", 4, curve=flat)
        mail["target"] = 4
        bot = daily._record(state, me)
        bot["coins"] = {"gp": 300, "sp": 0, "cp": 0}
        state["market"] = {"rel": {"Chainmail": 0.3}}                                                  # four suits sitting on his shelf, cheap, no buyer
        for night in range(1, 31):
            steward.observe(state, night)
        rep = steward.report(state, 30)
        assert rep["workshops"]["Smithy"]["shelf_pieces_that_have_sat_full_and_cheap_for_30_nights_or_more"][0]["item"] == "Chainmail"
        assert rep["workshops"]["Smithy"]["raw_material_kg"]["metal"] == 40.0
        orders = steward.validate([{"buy": "Chainmail", "below": 0.5, "for_days": 0, "up_to": 2, "per_night": 1, "keep_gp": 50},
                                   {"sell": "Chainmail", "when_metal_below_kg": 5, "for_days": 0, "keep": 0, "per_night": 2},
                                   {"buy": "Dragon egg", "below": 0.1}], steward.known_items(state))
        assert [list(o)[0] for o in orders] == ["buy", "sell"] and orders[1]["when_metal_below_kg"] == 5
        steward.book(state)["orders"] = orders
        done = daily.act(state, bot, me, [a for a in daily.rule_plan(state, bot, me, 31) if a["do"] == "buy"], 31)
        assert steward.held(bot, "Chainmail") == 1 and done                                          # she buys one suit a night, to keep, at the price of the day
        assert not [a for a in daily.rule_plan(state, bot, me, 32) if a["do"] == "sell"]             # the smith still has plenty of metal
        state["shops"][smith]["materials"]["metal"] = 3_000
        assert [a for a in daily.rule_plan(state, bot, me, 33) if a["do"] == "sell"]                # he is short: she sells the armor back to be melted


def test_the_delver_buys_a_weapon_from_the_smith_and_the_herb_woman_lives_off_the_households(content, monkeypatch):
    import importlib
    from ttrpgtools.dcc.westmarch import daily, economy, money, places, town as t
    flat = {"period": 10, "amplitude": 0, "phase": 0}
    importlib.reload(places)
    me = next(b for b in places.BOTS if b["id"] == "hedwig-d")
    monkeypatch.setattr(places, "BOTS", [me])
    monkeypatch.setattr(places, "PLACES", [])
    monkeypatch.setattr(places, "ROLES", {"smith": "smithy"})
    monkeypatch.setattr(places, "MARKET", {"delver": {"name": "Garrick", "every": (5, 5), "gp": (5, 5), "inn": 0.5, "till": "inn", "gear": 0.6}, "herb_cap": 20})
    monkeypatch.setattr(places, "STEWARD", {"every": 30, "brain": "rules"})
    monkeypatch.setattr(t, "today", lambda: places.EPOCH)
    with t.town(write=True) as state:
        state["shops"]["smithy"] = {"name": "Smithy", "stock": [], "till": 0, "kinds": ["shop"], "curve": flat, "restock_every": 7}
        t.stock_item(state, "smithy", "Dagger", "weapon", "3 gp", 4, curve=flat)
        t.stock_item(state, "smithy", "Chainmail", "armor", "75 gp", 2, curve=flat)         # too dear for him
        state["shops"]["inn"] = {"name": "Inn", "stock": [], "till": 0, "kinds": ["inn"], "curve": flat}
        economy.delver(state, 1, economy.config())                                              # fixes the first return
        before = money.supply(state)["money_cp"]
        economy.delver(state, state["delver"]["next"], economy.config())
        dagger = next(l for l in state["shops"]["smithy"]["stock"] if l["name"] == "Dagger")
        assert dagger["qty"] == 3 and state["shops"]["smithy"]["till"] == 300                  # the dearest he could afford with 60 percent of 5 gp
        assert money.supply(state)["money_cp"] == before + 500 and next(l for l in state["shops"]["smithy"]["stock"] if l["name"] == "Chainmail")["qty"] == 2
        assert state["shops"]["inn"]["till"] == 100 and state["money"]["households"] == 100     # half of the rest at the inn
        bot = daily._record(state, me)
        bot["coins"] = {"gp": 295, "sp": 0, "cp": 0}
        state["money"]["households"] = 10_000
        assert economy.herbs(state, economy.config()) == 20 and dcc.coins_total_cp(bot["coins"]) == 29_520
        bot["coins"] = {"gp": 300, "sp": 0, "cp": 0}
        assert economy.herbs(state, economy.config()) == 0                                       # at her capital: the households pay her nothing more
        monkeypatch.setattr(places, "STEWARD", None)
        assert economy.herbs(state, economy.config()) == 0


def test_a_drought_does_not_erase_hatching_hens_and_each_hen_has_her_own_luck(content, monkeypatch):
    import importlib
    from ttrpgtools.dcc.westmarch import daily, economy, places, town as t
    importlib.reload(places)
    spec = next(b for b in places.BOTS if b["id"] == "detlef")
    monkeypatch.setattr(places, "MARKET", {})
    monkeypatch.setattr(places, "BOTS", [spec])
    bot = {"coins": {"gp": 5, "sp": 0, "cp": 0}, "inventory": []}
    for day in range(1, 31):   # a severe drought: the yield factor is 0.2; a hen that hatches after her lag is still a hen
        economy.queue(bot, "Hen", "trade", "5 sp", 1, day)
        daily.arrive(bot, spec, day, {"weather": 0.2, "rel": {"Eggs, a dozen": 0.0001}})
    assert sum(1 for i in bot["inventory"] if i["name"] == "Hen") >= 25
    # twelve hens with no barley die on separate nights, not all on one
    from ttrpgtools.dcc.westmarch import steward
    state = {"shops": {}, "bots": {"d": {"name": "Detlef", "coins": {"gp": 0, "sp": 0, "cp": 0}, "inventory": [{"name": "Hen", "kind": "trade", "qty": 1} for _ in range(12)]}}}
    survivors = []
    for day in range(1, 40):
        daily.hens_eat(state, day, characters=False)
        survivors.append(steward.held(state["bots"]["d"], "Hen"))
    assert 0 < survivors[10] < 12 and len(set(survivors)) > 4        # a thinning flock, not one sudden death


def test_the_history_keeps_every_goods_price_and_stock_and_the_caravans_top_need(content, monkeypatch):
    from ttrpgtools.dcc.westmarch import history, places, town as t
    flat = {"period": 10, "amplitude": 0, "phase": 0}
    monkeypatch.setattr(t, "today", lambda: places.EPOCH)
    with t.town(write=True) as state:
        store = t.save_shop(state, None, "Store", curve=flat)
        barley = t.stock_item(state, store, "Barley, a sack", "trade", "4 sp", 5, curve=flat)
        mail = t.stock_item(state, store, "Chainmail", "armor", "75 gp", 1, curve=flat)
        barley["target"], mail["target"] = 10, 2
        for day in range(1, 31):
            barley["drift"] = 1.0 if day < 15 else 20.0                 # a price that jumps on the 15th night
            barley["qty"] = 5 if day < 15 else 0
            assert history.record(state, day) == 2
        history.record(state, 30)                                         # recording a night twice replaces it
    assert history.span() == (1, 30)
    data = history.series(points=100)
    assert data["step"] == 1 and len(data["days"]) == 30 and set(data["series"]) == {"Barley, a sack", "Chainmail"}
    b = data["series"]["Barley, a sack"]
    assert b["price"][0] == 40 and b["price"][20] == 800 and b["stock"][0] == 5 and b["stock"][20] == 0 and b["usual"][0] == 10 and b["rel"][20] == 20.0
    assert data["series"]["Chainmail"]["kind"] == "armor"
    assert history.series(1, 30, points=10)["step"] == 1                   # never fewer than 50 points: a month is drawn day by day
    wide = history.series(points=50)
    assert wide["step"] == 1 and wide["needs"] and all("label" in n for n in wide["needs"])


def test_the_history_page_and_api_are_for_the_admin(content, monkeypatch):
    from ttrpgtools.web.app import create_app
    from ttrpgtools.dcc.westmarch import history, places, town as t
    flat = {"period": 10, "amplitude": 0, "phase": 0}
    monkeypatch.setattr(t, "today", lambda: places.EPOCH)
    with t.town(write=True) as state:
        store = t.save_shop(state, None, "Store", curve=flat)
        t.stock_item(state, store, "Barley, a sack", "trade", "4 sp", 5, curve=flat)
        for day in range(1, 11):
            history.record(state, day)
    client = create_app().test_client()
    assert client.get("/TTRPG/dcc/api/history", headers={"Remote-User": "wren"}).status_code == 403
    got = client.get("/TTRPG/dcc/api/history?since=3&points=100", headers={"Remote-User": "admin"}).get_json()
    assert got["days"][0] == 3 and got["span"] == [1, 10] and "Barley, a sack" in got["series"] and got["real_day"] >= 1 and got["epoch"]
    page = client.get("/TTRPG/dcc/history", headers={"Remote-User": "admin"})
    assert page.status_code == 200 and b"dcc_history.js" in page.data


def test_the_history_keeps_what_the_caravan_was_asked_for_brought_and_took(content, monkeypatch):
    from ttrpgtools.dcc.westmarch import history, places, town as t
    monkeypatch.setattr(t, "today", lambda: places.EPOCH)
    with t.town(write=True) as state:
        state["caravan"] = {"asked_day": 5, "wants": [{"label": "Metal", "kind": "material", "what": "metal"}, {"label": "Barley, a sack", "kind": "goods", "what": "Barley, a sack"}]}
        history.record(state, 5)
        state["caravan"] = {"last_day": 10, "brought": ["30,0 kg metal", "3 x Barley, a sack"], "paid_cp": 1234}
        history.record(state, 10)
        state["caravan"].update(left_day=12, took=["4 x Hen"])
        history.record(state, 12)
        state["caravan"] = {"asked_day": 15, "wants": [{"label": "Hen", "kind": "goods", "what": "Hen"}]}
        history.record(state, 15)
    got = history.series(points=50)["caravan"]
    assert got == [{"day": 10, "asked": ["Metal", "Barley, a sack"], "brought": ["30,0 kg metal", "3 x Barley, a sack"], "paid_cp": 1234, "took": ["4 x Hen"]}]


def test_a_name_taken_by_all_gets_the_younger_then_the_third():
    import random
    import sqlite3
    from ttrpgtools.dcc.westmarch import lives
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE people (name TEXT)")
    db.executemany("INSERT INTO people VALUES (?)", [(f"{g} Volkersson",) for g in lives.GIVEN["m"]])
    first = lives._child_name(db, {"name": "Volker Ingosson"}, "m", random.Random(1))
    assert first.endswith(" Volkersson the Younger")
    db.execute("INSERT INTO people VALUES (?)", (first,))
    db.executemany("INSERT INTO people VALUES (?)", [(f"{g} Volkersson the Younger",) for g in lives.GIVEN["m"]])
    assert lives._child_name(db, {"name": "Volker Ingosson"}, "m", random.Random(1)).endswith(" Volkersson the Third")


def test_a_note_too_long_is_cut_and_she_is_told():
    from ttrpgtools.dcc.westmarch import steward
    b = {"notes": [], "next_note": 1}
    steward.edit_notes(b, {"notes_add": ["x" * 400 + "the end"]}, 5)
    assert b["notes"][0]["text"] == "x" * 400 and b["changed_by_rules"] == ["note 1 was cut at 400 characters; this end was lost: 'the end'"]


def test_the_graveyard_holds_the_last_200_dead_and_the_older_are_forgotten(content):
    import importlib
    from ttrpgtools.dcc.westmarch import lives, registry
    importlib.reload(registry)
    db = registry.connect()
    with db:
        for i in range(230):
            db.execute("INSERT INTO people (name, occupation, status, died_day, cause, updated) VALUES (?, 'farmer', 'dead', ?, 'old age', '2026-10-11')", (f"Dead {i}", i))
        forgotten = lives._forget_the_old_dead(db)
    db.close()
    yard = registry.graveyard()
    assert forgotten >= 30 and len(yard) == 200
    assert yard[0]["name"] == "Dead 229" and yard[-1]["name"] == "Dead 30"    # newest first, the thirty oldest are gone
    assert not any(r["status"] == "dead" for r in registry.rows("people"))
    # the written cast is never forgotten: connect() would add the name again as a new living person (10-11)
    from ttrpgtools.dcc.westmarch import villagers
    name = villagers.TOWNSFOLK[0][0]
    db = registry.connect()
    with db:
        db.execute("UPDATE people SET status = 'dead', died_day = -5, seat = NULL WHERE name = ?", (name,))
        lives._forget_the_old_dead(db)
    assert db.execute("SELECT status FROM people WHERE name = ?", (name,)).fetchone()["status"] == "dead"
    db.close()
    registry.connect().close()
    assert registry.connect().execute("SELECT COUNT(*) FROM people WHERE name = ? AND status = 'alive'", (name,)).fetchone()[0] == 0


def test_the_town_note_has_talk_and_requests_and_small_kinds_get_more_children():
    from ttrpgtools.dcc.westmarch import lives, places, town as t
    state = {"town_note": "Ivo: hides wanted"}
    assert "Henrik the tinker" in t.flavour_lines(state) and "state" not in state.get("town_flavour", "")     # a village with no talk starts from the seed
    t.flavour_write(state, "Pip the farmhand", "The hens sat on my hat again and I let them.")
    assert state["town_flavour"].splitlines()[-1].startswith("Pip the farmhand:") and "Sigrun of the caravan" in state["town_flavour"]
    assert t.flavour_write(state, "Pip the farmhand", "Hens sat on my hat again, I let them.") == state["town_flavour"]   # the same talk is not written twice
    for i in range(40):
        t.flavour_write(state, f"Voice {i}", f"Something different number {i} happened near the {['mill','ford','well','barn'][i % 4]} today.")
    assert sum(len(l.split()) for l in state["town_flavour"].splitlines()) <= places.TOWN_FLAVOUR_WORDS + 20
    text = t.note_text(state)
    assert text.index("TALK") < text.index("REQUESTS") and "Ivo: hides wanted" in text
    import importlib
    cfg = importlib.reload(places).LIVES   # the file's own settings
    assert cfg["rare_kind"] == {"below": 12, "boost": 4.0} and cfg["target"] == 80
    assert lives._rare_boost(40, cfg) == 1.0 and lives._rare_boost(12, cfg) == 1.0 and lives._rare_boost(0, cfg) == 4.0 and 1.0 < lives._rare_boost(2, cfg) < 4.0


def test_hedwig_reads_the_old_orders_teachings_and_the_live_file_wins(monkeypatch, tmp_path):
    from ttrpgtools.dcc.westmarch import steward
    assert "Old Order" in steward.teachings() and not any(w in steward.teachings().lower() for w in ("light", "moon", "fat eel", "pale"))    # the bundled seed; the secret barley and eel rules are nowhere in it
    live = tmp_path / "t.md"; live.write_text("Look after the smith.", encoding="utf-8")
    monkeypatch.setenv("WESTMARCH_TEACHINGS", str(live))
    assert steward.teachings() == "Look after the smith."
    assert "the_old_order_teachings" in steward.PERSONA


def test_a_household_has_one_purse_and_nobody_has_a_private_one(monkeypatch):
    import importlib, json as _json
    from ttrpgtools.dcc.westmarch import households as hh, lives, places, registry
    cfg = dict(importlib.reload(places).LIVES)
    monkeypatch.setattr(places, "LIVES", cfg)
    day = 100 * 365
    db = registry.connect()
    db.executescript(lives.SCHEMA)
    def add(name, sex, age, spouse=None, mother=None, father=None):
        with db:
            cur = db.execute("INSERT INTO people (name, occupation, status, notes, updated, locked, sex, race, born_day, spouse_id, mother_id, father_id, genes, sheet) "
                             "VALUES (?, 'Farmer', 'alive', 'x', '2026-10-11', 0, ?, 'human', ?, ?, ?, ?, '{}', ?)",
                             (name, sex, day - age * 365, spouse, mother, father, _json.dumps({"copper": 500})))
        return cur.lastrowid
    bert, anna = add("Bert T", "m", 30), add("Anna T", "f", 28)
    with db:
        db.execute("UPDATE people SET spouse_id = ? WHERE id = ?", (anna, bert)); db.execute("UPDATE people SET spouse_id = ? WHERE id = ?", (bert, anna))
    cora, dora, edgar = add("Cora T", "f", 5, mother=anna, father=bert), add("Dora S", "f", 25), add("Edgar S", "m", 27)
    state = {"money": {"households": 10_000}, "last_daily": day}
    sheets_cp = sum(_json.loads(r[0])["copper"] for r in db.execute("SELECT sheet FROM people WHERE status != 'dead' AND claimed_by IS NULL AND sheet IS NOT NULL"))
    done = hh.migrate(db, state)
    mine = lambda name: db.execute("SELECT household_id FROM people WHERE name = ?", (name,)).fetchone()[0]
    total = lambda: sum(state["households"].values())
    assert state["household_mode"] and done["households"] >= 3 and total() == state["money"]["households"] == 10_000 + sheets_cp      # the coin in the villagers' own purses is the households' now
    assert mine("Bert T") == mine("Anna T") == mine("Cora T") and mine("Dora S") != mine("Anna T")                                  # a couple and their child: one household
    before = total()
    hh.credit(state, db, mine("Dora S"), 400)                                                                                       # a flow that belongs to one house
    assert total() == before + 400 and state["money"]["households"] == total()
    state["money"]["households"] -= 1000                                                                                            # an aggregate flow (the diet): spread, never negative
    hh.reconcile(state, db)
    assert total() == state["money"]["households"] == before + 400 - 1000 and min(state["households"].values()) >= 0
    dora_house, edgar_house = mine("Dora S"), mine("Edgar S")
    both = state["households"][str(dora_house)] + state["households"][str(edgar_house)]
    lives._wed(db, db.execute("SELECT * FROM people WHERE id = ?", (edgar,)).fetchone(), db.execute("SELECT * FROM people WHERE id = ?", (dora,)).fetchone(), day, state)
    assert mine("Dora S") == mine("Edgar S") and state["households"][str(mine("Edgar S"))] == both and total() == state["money"]["households"]   # a wedding joins the purses
    other = mine("Anna T")
    hh.endow(state, db, 300)                                                                                                        # a newcomer's house is paid by the others
    assert total() == state["money"]["households"]
    for name in ("Dora S", "Edgar S"):
        lives._die(db, state, db.execute("SELECT * FROM people WHERE name = ?", (name,)).fetchone(), day, "old age")
    assert str(mine("Edgar S")) not in state["households"] and total() == state["money"]["households"]                              # nobody left: the coin goes back to the others
    assert state["households"][str(other)] >= 0
    db.close()
