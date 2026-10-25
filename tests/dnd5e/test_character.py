"""Sheet derivation against hand-computed builds and DDB's rendered sheets.

Needs the private builder data (builder_data.py) and, for the golden test, the
captures in content/dnd5e/private/golden/ (golden_capture.py); skips without them.
"""

import json
import re
from pathlib import Path

import pytest

from ttrpgtools.dnd5e import character as ch

DATA = ch.DATA_DIR
GOLDEN = Path(__file__).resolve().parents[2] / "content" / "dnd5e" / "private" / "golden"
pytestmark = pytest.mark.skipif(not (DATA / "classes.json").exists(), reason="builder data not built")


@pytest.fixture(scope="module")
def data():
    return ch.load_data()


def find(entries, name, source="PHB"):
    return next(e for e in entries.values() if e["name"] == name and e["source"] == source)


def sub_id(data, cls, name):
    return next(s["id"] for s in data.classes[cls]["subclasses"] if s["name"] == name)


def test_hill_dwarf_life_cleric_5(data):
    char = {
        "name": "Hand check",
        "abilities": {"method": "standard", "base": {"str": 14, "dex": 10, "con": 13, "int": 8, "wis": 15, "cha": 12}},
        "race": {"id": find(data.races, "Dwarf (Hill)")["id"]},
        "background": {"id": find(data.backgrounds, "Acolyte")["id"], "languages": ["elvish", "giant"]},
        "classes": [{"id": "cleric", "level": 5, "subclass": sub_id(data, "cleric", "Life Domain"),
                     "skills": ["medicine", "persuasion"], "asi": {"4": {"abilities": {"wis": 2}}}}],
        "inventory": [{"id": data.item_by_name["chain mail"]["id"], "equipped": True},
                      {"id": data.item_by_name["shield"]["id"], "equipped": True},
                      {"id": data.item_by_name["mace"]["id"], "equipped": True}],
    }
    s = ch.derive(char, data)
    assert s["abilities"]["wis"]["score"] == 18 and s["abilities"]["con"]["score"] == 15
    assert s["hp"]["max"] == 10 + 4 * 7 + 5  # d8 max + 4 averages, con +2, Dwarven Toughness
    assert s["armor_class"]["value"] == 18
    assert s["speed"]["walk"] == 25
    assert s["saving_throws"]["wis"]["modifier"] == 7
    assert s["passives"]["perception"] == 14 and s["passives"]["insight"] == 17
    caster = s["spellcasting"]["casters"][0]
    assert (caster["save_dc"], caster["attack"], caster["prepared_max"]) == (15, 7, 9)
    assert len(caster["always_prepared"]) == 6
    assert [x["max"] for x in s["spellcasting"]["slots"]] == [4, 3, 2]
    mace = next(a for a in s["attacks"] if a["name"] == "Mace")
    assert (mace["to_hit"], mace["damage"]) == (5, "1d6+2")
    assert "heavy" in s["proficiencies"]["armor"]
    assert not s["problems"]


def test_multiclass_slots_and_pact_magic(data):
    char = {"name": "Multi", "abilities": {"base": {a: 14 for a in ch.ABILITIES}},
            "classes": [{"id": "paladin", "level": 2}, {"id": "sorcerer", "level": 3}, {"id": "warlock", "level": 5}]}
    s = ch.derive(char, data)
    # caster level = 2 // 2 + 3 = 4 -> 4/3 slots; warlock slots stay separate.
    assert [x["max"] for x in s["spellcasting"]["slots"]] == [4, 3]
    assert s["spellcasting"]["pact"]["count"] == 2 and s["spellcasting"]["pact"]["level"] == 3
    assert s["proficiency_bonus"] == 4


def test_single_class_half_caster_uses_its_own_table(data):
    s = ch.derive({"name": "Pal", "classes": [{"id": "paladin", "level": 1}]}, data)
    assert s["spellcasting"]["slots"] == []
    s = ch.derive({"name": "Art", "classes": [{"id": "artificer", "level": 1}]}, data)
    assert [x["max"] for x in s["spellcasting"]["slots"]] == [2]


def test_point_buy_budget(data):
    base = {"str": 15, "dex": 15, "con": 15, "int": 8, "wis": 8, "cha": 8}
    s = ch.derive({"name": "PB", "abilities": {"method": "pointbuy", "base": base}}, data)
    assert s["point_buy"]["spent"] == 27 and not s["problems"]
    base["int"] = 9
    s = ch.derive({"name": "PB", "abilities": {"method": "pointbuy", "base": base}}, data)
    assert any("Point buy" in p for p in s["problems"])


def test_open_choices_ask_for_missing_picks(data):
    s = ch.derive({"name": "Empty", "classes": [{"id": "warlock", "level": 2}]}, data)
    whats = " ".join(c["what"] for c in s["choices_open"])
    assert "Choose a race" in whats and "Otherworldly Patron" in whats and "Eldritch Invocations" in whats


@pytest.mark.skipif(not GOLDEN.exists() or not list(GOLDEN.glob("*.json")), reason="no golden captures")
@pytest.mark.parametrize("path", sorted(GOLDEN.glob("*.json")) if GOLDEN.exists() else [], ids=lambda p: p.stem)
def test_golden_against_ddb(data, path):
    from ttrpgtools.dnd5e.ddb_import import import_ddb

    golden = json.loads(path.read_text())
    rendered = golden["rendered"]
    s = ch.derive(import_ddb(golden["ddb"], data), data)
    num = lambda text: int(text.replace(" ", ""))
    assert s["armor_class"]["value"] == int(rendered["ac"])
    assert s["hp"]["max"] == int(re.search(r"MAX\D*?(\d+)", rendered["health"]).group(1))
    assert s["proficiency_bonus"] == num(rendered["proficiency"])
    assert s["speed"]["walk"] == int(re.match(r"\d+", rendered["speed"]).group(0))
    for abbr, box in rendered["abilities"].items():
        score = box["secondary"] if box["secondary"] and box["secondary"].lstrip("-").isdigit() else box["primary"]
        assert s["abilities"][abbr.lower()]["score"] == int(score), abbr
    for abbr, value in rendered["saves"].items():
        assert s["saving_throws"][abbr.lower()]["modifier"] == num(value), abbr
    for skill, value in rendered["skills"].items():
        if skill.lower() in s["skills"]:
            assert s["skills"][skill.lower()]["modifier"] == num(value), skill
    passives = [int(x) for x in re.findall(r"(\d+) PASSIVE", rendered["senses"])]
    assert passives == [s["passives"]["perception"], s["passives"]["investigation"], s["passives"]["insight"]]
    initiative = next(x for x in rendered["combat"] if x.startswith("INITIATIVE"))
    assert s["initiative"] == num(re.search(r"([+-] ?\d+)", initiative).group(1))


def test_magic_weapon_variant_adds_its_bonus(data):
    sword = next(i for i in data.items.values() if i["name"] == "+1 Longsword")
    char = {"name": "Knight", "abilities": {"base": {"str": 16, "dex": 10, "con": 14, "int": 8, "wis": 10, "cha": 12}},
            "classes": [{"id": "fighter", "level": 1}], "inventory": [{"id": sword["id"], "equipped": True}]}
    attack = next(a for a in ch.derive(char, data)["attacks"] if a["name"] == "+1 Longsword")
    assert (attack["to_hit"], attack["damage"], attack["versatile"]) == (6, "1d8+4", "1d10+4")


def test_tasha_optional_features_are_opt_in(data):
    char = {"name": "Ranger", "classes": [{"id": "ranger", "level": 1}]}
    names = lambda c: {f["name"] for f in ch.derive(c, data)["features"]}
    assert "Deft Explorer" not in names(char)
    char["classes"][0]["variant_features"] = ["Deft Explorer"]
    assert "Deft Explorer" in names(char)


def test_overrides_are_applied_last_and_marked(data):
    char = {"name": "O", "abilities": {"base": {a: 10 for a in ch.ABILITIES}}, "classes": [{"id": "wizard", "level": 1}],
            "overrides": {"ac_bonus": 1, "speed": 40, "skill_bonus": {"perception": 2}, "save_bonus": {"wis": 1}, "spell_dc_bonus": 1}}
    s = ch.derive(char, data)
    assert s["armor_class"]["value"] == 11 and s["armor_class"]["overridden"]
    assert s["speed"]["walk"] == 40
    assert s["skills"]["perception"]["modifier"] == 2 and s["passives"]["perception"] == 12
    assert s["saving_throws"]["wis"]["modifier"] == 3
    assert s["spellcasting"]["casters"][0]["save_dc"] == 8 + 2 + 0 + 1


def test_effects_and_conditions_move_the_numbers(data):
    axe = next(i for i in data.items.values() if i["name"] == "Greataxe" and i["source"] == "PHB")
    char = {"name": "B", "abilities": {"base": {"str": 16, "dex": 14, "con": 14, "int": 8, "wis": 10, "cha": 8}},
            "classes": [{"id": "barbarian", "level": 5}], "inventory": [{"id": axe["id"], "equipped": True}],
            "play": {"effects": ["Rage", "Shield of Faith"], "exhaustion": 2}}
    s = ch.derive(char, data)
    attack = next(a for a in s["attacks"] if a["name"] == "Greataxe")
    assert attack["damage"] == "1d12+3+2"  # Rage Damage +2 at level 5
    assert "slashing" in s["defenses"]["resist"]
    assert s["armor_class"]["value"] == 10 + 2 + 2 + 2  # Unarmored Defense + Shield of Faith
    assert s["speed"]["walk"] == (30 + 10) // 2  # Fast Movement, halved by exhaustion 2
    char["play"] = {"conditions": ["grappled"]}
    assert ch.derive(char, data)["speed"]["walk"] == 0


def test_mage_armor_only_without_armor(data):
    char = {"name": "W", "abilities": {"base": {"str": 8, "dex": 16, "con": 12, "int": 16, "wis": 10, "cha": 10}},
            "classes": [{"id": "wizard", "level": 1}], "play": {"effects": ["Mage Armor"]}}
    assert ch.derive(char, data)["armor_class"]["value"] == 16


def test_bag_of_holding_contents_weigh_nothing_and_coins_can(data):
    item = lambda name: next(i for i in data.items.values() if i["name"] == name)["id"]
    char = {"name": "C", "abilities": {"base": {"str": 10}}, "description": {"coin_weight": True, "encumbrance": "variant"},
            "currency": {"gp": 500},
            "inventory": [{"id": item("Bag of Holding"), "uid": "bag"}, {"id": item("Backpack"), "uid": "pack"},
                          {"id": item("Chain Mail"), "inside": "bag"}, {"id": item("Crowbar"), "inside": "pack"}]}
    s = ch.derive(char, data)
    assert s["encumbrance"]["weight"] == 15 + 5 + 5 + 10  # bag, backpack, crowbar, 500 coins; chain mail in the bag is weightless
    assert s["encumbrance"]["status"] is None
    char["inventory"][2].pop("inside")
    s = ch.derive(char, data)
    assert s["encumbrance"]["status"] == "encumbered" and s["speed"]["walk"] == 30 - 10  # 90 lb. > 5 x Str 10
    char["description"]["encumbrance"] = "none"  # DDB's "No Encumbrance" preference
    s = ch.derive(char, data)
    assert s["encumbrance"]["status"] is None and s["encumbrance"]["disabled"] and s["speed"]["walk"] == 30


def test_feat_choices_skilled_linguist_prodigy(data):
    feat = lambda name: next(f for f in data.feats.values() if f["name"] == name and f["source"] in ("PHB", "XGE"))["id"]
    char = {"name": "F", "abilities": {"base": {a: 10 for a in ch.ABILITIES}}, "classes": [{"id": "fighter", "level": 8, "asi": {
        "4": {"feat": {"id": feat("Skilled"), "skill_tool": ["skill:arcana", "tool:lute", "skill:history", "skill:nature"]}},
        "6": {"feat": {"id": feat("Linguist"), "languages": ["elvish", "dwarvish", "giant"]}},
        "8": {"feat": {"id": feat("Prodigy"), "skills": ["stealth"], "tools": ["thieves' tools"], "languages": ["orc"], "expertise": ["stealth"]}}}}]}
    s = ch.derive(char, data)
    assert s["skills"]["arcana"]["proficiency"] == "proficient" and s["skills"]["history"]["proficiency"] == "proficient"
    assert s["skills"]["nature"]["proficiency"] != "proficient"  # Skilled gives three picks, the fourth is ignored
    assert s["skills"]["stealth"]["proficiency"] == "expertise"
    profs = s["proficiencies"]
    assert "lute" in profs["tools"] and "thieves' tools" in profs["tools"]
    assert {"elvish", "dwarvish", "giant", "orc"} <= set(map(str.lower, profs["languages"]))


def test_feat_optional_features(data):
    feat = lambda name: next(f for f in data.feats.values() if f["name"] == name)["id"]
    option = lambda name: next(o for o in data.optionalfeatures.values() if o["name"] == name)["id"]
    char = {"name": "F", "abilities": {"base": {a: 10 for a in ch.ABILITIES}}, "classes": [{"id": "wizard", "level": 8, "asi": {
        "4": {"feat": {"id": feat("Fighting Initiate"), "optionalfeatures": [option("Defense")]}},
        "8": {"feat": {"id": feat("Eldritch Adept"), "optionalfeatures": [option("Devil's Sight"), option("Mask of Many Faces")]}}}}],
        "inventory": [{"id": next(i for i in data.items.values() if i["name"] == "Leather Armor")["id"], "equipped": True}]}
    s = ch.derive(char, data)
    names = [f["name"] for f in s["features"]]
    assert "Defense" in names and "Devil's Sight" in names
    assert "Mask of Many Faces" not in names  # Eldritch Adept grants one invocation
    assert s["armor_class"]["value"] == 11 + 1  # leather 11 + Dex 0 + Defense 1 from the feat


def test_granted_spells_race_and_feat(data):
    race = next(r for r in data.races.values() if r["name"] == "Tiefling" and r["source"] == "PHB")["id"]
    feat = lambda name: next(f for f in data.feats.values() if f["name"] == name)["id"]
    spell = lambda name: data.spell_by_name[name.lower()]["id"]
    char = {"name": "T", "abilities": {"base": {"str": 10, "dex": 10, "con": 10, "int": 14, "wis": 10, "cha": 15}},
            "race": {"id": race}, "classes": [{"id": "fighter", "level": 4, "asi": {"4": {"feat": {
                "id": feat("Magic Initiate"), "spell_block": 5, "spell_picks": {
                    "known|_|_|known|0": [spell("Fire Bolt"), spell("Light")], "innate|_|daily|1/long rest|0": [spell("Magic Missile")]}}}}}]}
    granted = ch.derive(char, data)["spellcasting"]["granted"]
    by_name = {g["name"]: g for g in granted}
    assert {"Thaumaturgy", "Hellish Rebuke", "Fire Bolt", "Light", "Magic Missile"} <= set(by_name)
    assert "Darkness" not in by_name  # Tiefling darkness comes at 5th level
    assert by_name["Hellish Rebuke"]["usage"] == "1/long rest" and by_name["Hellish Rebuke"]["save_dc"] == 8 + 2 + 3
    assert by_name["Fire Bolt"]["ability"] == "int" and by_name["Fire Bolt"]["attack"] and by_name["Fire Bolt"]["attack_bonus"] == 2 + 2


def test_multiclass_fighter_needs_str_or_dex(data):
    char = lambda dex: {"name": "M", "abilities": {"base": {"str": 10, "dex": dex, "con": 10, "int": 10, "wis": 13, "cha": 10}},
                        "classes": [{"id": "cleric", "level": 1}, {"id": "fighter", "level": 1}]}
    fighter_problems = lambda s: [p for p in s["problems"] if "Fighter" in p]
    assert not fighter_problems(ch.derive(char(13), data))  # Dex 13 alone is enough
    assert fighter_problems(ch.derive(char(12), data))


def test_dragonmark_expands_class_spell_list(data):
    race = next(r for r in data.races.values() if r["name"] == "Halfling (Mark of Healing)")["id"]
    char = {"name": "H", "abilities": {"base": {a: 12 for a in ch.ABILITIES}}, "race": {"id": race},
            "classes": [{"id": "wizard", "level": 3}]}
    caster = ch.derive(char, data)["spellcasting"]["casters"][0]
    assert data.spell_by_name["cure wounds"]["id"] in caster["expanded"]  # a wizard could not learn it otherwise


def test_ddb_import_keeps_description_and_notes():
    from ttrpgtools.dnd5e.ddb_import import _import_description
    looks, char = {}, {}
    _import_description({"age": 30, "eyes": "Green", "weight": None, "alignmentId": 3,
                         "traits": {"personalityTraits": "Helpful.\n", "ideals": "", "flaws": None},
                         "notes": {"organizations": "Baker's Guild\n\n", "backstory": "Born at sea.",
                                   "otherNotes": "1st session", "personalPossessions": "A locket"}}, looks, char)
    assert looks == {"age": "30", "eyes": "Green", "alignment": "Chaotic Good", "traits": "Helpful.",
                     "organizations": "Baker's Guild", "backstory": "Born at sea."}
    assert char["notes"] == "1st session\n\nPersonal Possessions:\nA locket"


def test_features_carry_kind_and_page(data):
    s = ch.derive({"name": "F", "classes": [{"id": "fighter", "level": 1}], "race": {"id": "human-phb"}}, data)
    kinds = {f["name"]: f["kind"] for f in s["features"]}
    assert kinds["Second Wind"] == "class" and kinds["Languages"] == "race"
    assert next(f for f in s["features"] if f["name"] == "Second Wind")["page"] == 72


def test_armor_class_parts_add_up(data):
    chain = next(i for i in data.items.values() if i["name"] == "Chain Mail")["id"]
    shield = next(i for i in data.items.values() if i["name"] == "Shield")["id"]
    base = {"name": "AC", "abilities": {"base": {"str": 15, "dex": 14, "con": 14, "int": 10, "wis": 16, "cha": 8}}}
    for char in ({**base, "classes": [{"id": "monk", "level": 3}]},
                 {**base, "classes": [{"id": "fighter", "level": 1}], "inventory": [{"id": chain, "equipped": True}, {"id": shield, "equipped": True}]}):
        ac = ch.derive(char, data)["armor_class"]
        assert sum(v for _, v, _ in ac["parts"]) == ac["value"], ac


def test_custom_proficiencies_count(data):
    longsword = next(i for i in data.items.values() if i["name"] == "Longsword")["id"]
    char = {"name": "W", "abilities": {"base": {"str": 14, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}},
            "classes": [{"id": "wizard", "level": 1}], "inventory": [{"id": longsword, "equipped": True}]}
    plain_hit = next(a for a in ch.derive(char, data)["attacks"] if a["name"] == "Longsword")["to_hit"]
    s = ch.derive({**char, "custom_proficiencies": [{"type": "weapons", "name": "Longsword"}, {"type": "languages", "name": "Thieves' Cant"}]}, data)
    assert "longsword" in s["proficiencies"]["weapons"] and "thieves' cant" in s["proficiencies"]["languages"]
    assert next(a for a in s["attacks"] if a["name"] == "Longsword")["to_hit"] == plain_hit + 2


def test_custom_skills_and_ddb_import(data):
    from ttrpgtools.dnd5e.ddb_import import _import_custom_skills
    imported = _import_custom_skills({"customProficiencies": [
        {"name": "Navigation", "type": 1, "statId": None, "proficiencyLevel": 3, "miscBonus": None, "magicBonus": None, "override": None},
        {"name": "Piraterie", "type": 1, "statId": 1, "proficiencyLevel": 4, "miscBonus": 2, "magicBonus": None, "override": None},
        {"name": "Tinker", "type": 2, "statId": None, "proficiencyLevel": 3}]})
    assert [c["name"] for c in imported] == ["Navigation", "Piraterie"] and imported[0]["ability"] is None
    s = ch.derive({"name": "P", "abilities": {"base": {"str": 16, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}},
                   "classes": [{"id": "fighter", "level": 1}], "custom_skills": imported}, data)
    by = {c["name"]: c["modifier"] for c in s["custom_skills"]}
    assert by == {"Navigation": 2, "Piraterie": 3 + 4 + 2}


def test_campaigns_join_and_leave(tmp_path):
    from ttrpgtools.dnd5e import campaigns
    path = tmp_path / "c.sqlite"
    camp = campaigns.create("Curse of Strahd", "takahe", path=path)
    assert camp["dm"] == "takahe" and camp["characters"] == []
    other = campaigns.create("West Marches", "dodo", path=path)
    campaigns.join(camp["id"], "nila-1234", "dodo", path=path)
    campaigns.join(camp["id"], "nila-1234", "dodo", path=path)  # joining twice changes nothing
    campaigns.join(other["id"], "nila-1234", "dodo", path=path)
    assert [c["name"] for c in campaigns.of_character("nila-1234", path=path)] == ["Curse of Strahd", "West Marches"]
    assert campaigns.get(camp["id"], path=path)["characters"] == ["nila-1234"]
    campaigns.leave(camp["id"], "nila-1234", path=path)
    assert campaigns.by_character(path=path) == {"nila-1234": ["West Marches"]}
    campaigns.delete(other["id"], path=path)
    assert campaigns.by_character(path=path) == {} and campaigns.get(other["id"], path=path) is None


def test_lineage_race_gets_floating_increases(data):
    # MPMM races carry no ability data in 5etools; the renderer adds +2/+1 or +1/+1/+1 (builder_data.expand_lineage)
    aasimar = find(data.races, "Aasimar", "MPMM")
    base = {"name": "Lineage", "abilities": {"base": {a: 10 for a in ch.ABILITIES}}, "classes": [{"id": "fighter", "level": 1}]}
    s = ch.derive({**base, "race": {"id": aasimar["id"], "ability_block": 0, "ability_choices": ["cha", "wis"]}}, data)
    assert (s["abilities"]["cha"]["score"], s["abilities"]["wis"]["score"]) == (12, 11)
    s = ch.derive({**base, "race": {"id": aasimar["id"], "ability_block": 1, "ability_choices": ["str", "dex", "con"]}}, data)
    assert [s["abilities"][a]["score"] for a in ("str", "dex", "con", "int")] == [11, 11, 11, 10]


def test_extra_attack_and_channel_divinity_do_not_stack(data):
    s = ch.derive({"name": "Multi", "abilities": {"base": {a: 14 for a in ch.ABILITIES}},
                   "classes": [{"id": "fighter", "level": 5}, {"id": "paladin", "level": 5}]}, data)
    assert s["attacks_per_action"] == 2
    s = ch.derive({"name": "Multi", "abilities": {"base": {a: 14 for a in ch.ABILITIES}},
                   "classes": [{"id": "fighter", "level": 11}]}, data)
    assert s["attacks_per_action"] == 3
    s = ch.derive({"name": "Multi", "abilities": {"base": {a: 14 for a in ch.ABILITIES}},
                   "classes": [{"id": "cleric", "level": 6}, {"id": "paladin", "level": 3}]}, data)
    divinity = [c for c in s["counters"] if c["name"] == "Channel Divinity"]
    assert len(divinity) == 1 and divinity[0]["max"] == 2


def test_xp_advancement(data):
    char = {"name": "XP", "preferences": {"advancement": "xp"}, "xp": 7000, "classes": [{"id": "fighter", "level": 4}]}
    assert ch.derive(char, data)["xp"] == {"total": 7000, "level_by_xp": 5, "current": 2700, "next": 6500}
    assert "xp" not in ch.derive({**char, "preferences": {}}, data)


def test_magical_secrets_and_mystic_arcanum(data):
    fireball, counterspell = find(data.spells, "Fireball")["id"], find(data.spells, "Counterspell")["id"]
    lore = sub_id(data, "bard", "College of Lore")
    bard = {"name": "Bard", "abilities": {"base": {a: 14 for a in ch.ABILITIES}},
            "classes": [{"id": "bard", "level": 10, "subclass": lore, "spells": {"secrets": [fireball, counterspell]}}]}
    caster = ch.derive(bard, data)["spellcasting"]["casters"][0]
    assert (caster["secrets_max"], caster["secrets_extra"]) == (2, 2)
    assert {c["name"] for c in caster["list"]} >= {"Fireball", "Counterspell"}
    eyebite = find(data.spells, "Eyebite")["id"]
    warlock = {"name": "Lock", "abilities": {"base": {a: 14 for a in ch.ABILITIES}},
               "classes": [{"id": "warlock", "level": 12, "spells": {"arcanum": {"6": eyebite}}}]}
    s = ch.derive(warlock, data)
    caster = s["spellcasting"]["casters"][0]
    assert caster["arcanum_levels"] == [6] and caster["arcanum"][0]["name"] == "Eyebite"
    assert any(c["name"] == "Mystic Arcanum (6th level)" for c in s["counters"])


def test_save_and_spell_bonuses_attunement_and_athlete(data):
    base = {a: 10 for a in ch.ABILITIES} | {"cha": 16, "str": 16}
    cloak, ring = data.item_by_name["cloak of protection"]["id"], data.item_by_name["ring of protection"]["id"]
    rod = data.item_by_name["+2 rod of the pact keeper"]["id"]
    char = {"name": "Bonus", "abilities": {"base": base},
            "classes": [{"id": "paladin", "level": 6}, {"id": "warlock", "level": 1}],
            "inventory": [{"id": cloak, "equipped": True, "attuned": True}, {"id": ring, "equipped": True, "attuned": False},
                          {"id": rod, "equipped": True, "attuned": True}]}
    s = ch.derive(char, data)
    # Aura of Protection +3 (Cha 16), cloak +1; the ring is not attuned and gives nothing
    assert s["saving_throws"]["dex"]["modifier"] == 0 + 3 + 1
    lock = next(c for c in s["spellcasting"]["casters"] if c["class"] == "Warlock")
    assert (lock["save_dc"], lock["attack"]) == (8 + 3 + 3 + 2, 3 + 3 + 2)
    assert s["attunement"] == {"used": 2, "max": 3}
    champion = sub_id(data, "fighter", "Champion")
    s = ch.derive({"name": "Champ", "abilities": {"base": base}, "classes": [{"id": "fighter", "level": 7, "subclass": champion}]}, data)
    assert s["skills"]["acrobatics"]["proficiency"] == "half" and s["skills"]["acrobatics"]["modifier"] == 2
    assert s["initiative"] == 2
    assert s["encumbrance"]["capacity"] == 240


def test_powerful_build_doubles_capacity(data):
    goliath = find(data.races, "Goliath", "MPMM")
    s = ch.derive({"name": "Big", "abilities": {"base": {a: 10 for a in ch.ABILITIES}}, "race": {"id": goliath["id"]},
                   "classes": [{"id": "fighter", "level": 1}]}, data)
    assert s["encumbrance"]["capacity"] == 300


def test_race_and_feat_uses_read_from_their_text(data):
    base = {"abilities": {"base": {a: 10 for a in ch.ABILITIES}}, "classes": [{"id": "fighter", "level": 5}]}
    s = ch.derive({**base, "name": "Dragon", "race": {"id": find(data.races, "Dragonborn")["id"]}}, data)
    assert {"name": "Breath Weapon", "max": 1, "reset": "short"}.items() <= next(c for c in s["counters"] if c["name"] == "Breath Weapon").items()
    s = ch.derive({**base, "name": "Goliath", "race": {"id": find(data.races, "Goliath", "MPMM")["id"]}}, data)
    assert next(c for c in s["counters"] if c["name"] == "Stone's Endurance")["max"] == 3  # proficiency bonus at level 5
    s = ch.derive({**base, "name": "Tiefling", "race": {"id": find(data.races, "Tiefling")["id"]}}, data)
    assert not any(c["name"] == "Infernal Legacy" for c in s["counters"])  # its spells carry the uses


def test_class_values_at_level(data):
    s = ch.derive({"name": "V", "classes": [{"id": "rogue", "level": 7}, {"id": "monk", "level": 5}, {"id": "bard", "level": 5}]}, data)
    assert s["class_values"] == {"Sneak Attack": "4d6", "Martial Arts": "1d6", "Bardic Inspiration": "d8"}


def test_monk_weapons_and_off_hand(data):
    dex = {"name": "W", "abilities": {"base": {a: 10 for a in ch.ABILITIES} | {"dex": 16}}}
    staff, sword, dagger = (data.item_by_name[n]["id"] for n in ("quarterstaff", "shortsword", "dagger"))
    s = ch.derive({**dex, "classes": [{"id": "monk", "level": 5}], "inventory": [{"id": staff, "equipped": True}]}, data)
    attacks = {a["name"]: a for a in s["attacks"]}
    assert (attacks["Quarterstaff"]["damage"], attacks["Quarterstaff"]["ability"]) == ("1d6+3", "dex")
    assert attacks["Unarmed Strike"]["damage"] == "1d6+3"
    s = ch.derive({**dex, "classes": [{"id": "rogue", "level": 3}],
                   "inventory": [{"id": sword, "equipped": True}, {"id": dagger, "equipped": True}]}, data)
    assert next(a for a in s["attacks"] if a["name"] == "Dagger (off-hand)")["damage"] == "1d4"


def test_defenses_from_items_and_class(data):
    ring = data.item_by_name["ring of fire resistance"]
    s = ch.derive({"name": "D", "classes": [{"id": "monk", "level": 10}],
                   "inventory": [{"id": ring["id"], "equipped": True, "attuned": True}]}, data)
    assert "fire" in s["defenses"]["resist"] and "poison" in s["defenses"]["immune"]
    assert "poisoned" in s["defenses"]["condition_immune"]


def test_level_down_drops_extra_invocations(data):
    names = ["Agonizing Blast", "Armor of Shadows", "Devil's Sight"]
    ids = [next(o["id"] for o in data.optionalfeatures.values() if o["name"] == n and "EI" in o.get("featureType", [])) for n in names]
    s = ch.derive({"name": "Lock", "classes": [{"id": "warlock", "level": 2, "optionalfeatures": ids}]}, data)
    assert [f["name"] for f in s["features"] if f.get("optionalfeature")] == names[:2]  # two invocations at level 2


def test_granted_spell_uses_are_counters(data):
    s = ch.derive({"name": "T", "race": {"id": find(data.races, "Tiefling")["id"]}, "classes": [{"id": "fighter", "level": 5}]}, data)
    rebuke = next(g for g in s["spellcasting"]["granted"] if g["name"] == "Hellish Rebuke")
    counter = next(c for c in s["counters"] if c["name"] == rebuke["counter"])
    assert (counter["max"], counter["reset"]) == (1, "long")


def test_customize_your_origin_moves_racial_increases(data):
    dwarf = find(data.races, "Dwarf (Hill)")["id"]
    char = {"name": "O", "abilities": {"base": {a: 10 for a in ch.ABILITIES}}, "classes": [{"id": "wizard", "level": 1}],
            "preferences": {"customize_origin": True}, "race": {"id": dwarf, "ability_choices": ["int", "dex"]}}
    s = ch.derive(char, data)
    assert [s["abilities"][a]["score"] for a in ("int", "dex", "con", "wis")] == [12, 11, 10, 10]
    s = ch.derive({**char, "preferences": {}}, data)
    assert [s["abilities"][a]["score"] for a in ("int", "con", "wis")] == [10, 12, 11]


def test_custom_lineage_variable_trait(data):
    lineage = find(data.races, "Custom Lineage", "TCE")["id"]
    base = {"name": "L", "classes": [{"id": "fighter", "level": 1}]}
    s = ch.derive({**base, "race": {"id": lineage, "variable_trait": "skill", "skills": ["stealth"]}}, data)
    assert not s["senses"].get("darkvision") and s["skills"]["stealth"]["proficiency"] == "proficient"
    s = ch.derive({**base, "race": {"id": lineage, "variable_trait": "darkvision", "skills": ["stealth"]}}, data)
    assert s["senses"]["darkvision"] == 60 and s["skills"]["stealth"]["proficiency"] is None


def test_wild_shape_limits(data):
    assert ch.derive({"name": "D", "classes": [{"id": "druid", "level": 4}]}, data)["wild_shape"] == {"max_cr": 0.5, "swim": True, "fly": False}
    moon = sub_id(data, "druid", "Circle of the Moon")
    assert ch.derive({"name": "D", "classes": [{"id": "druid", "level": 9, "subclass": moon}]}, data)["wild_shape"]["max_cr"] == 3


def test_item_charges_are_counters(data):
    wand = data.item_by_name["wand of magic missiles"]["id"]
    s = ch.derive({"name": "W", "classes": [{"id": "wizard", "level": 3}], "inventory": [{"id": wand}, {"id": wand}]}, data)
    names = [c["name"] for c in s["counters"] if c["origin"] == "Item"]
    assert names == ["Wand of Magic Missiles", "Wand of Magic Missiles #2"]
    assert s["counters"][-1]["reset"] == "dawn" and s["counters"][-1]["max"] == 7


def test_background_skill_overlap_gets_a_replacement(data):
    acolyte = find(data.backgrounds, "Acolyte")["id"]  # Insight, Religion
    char = {"name": "O", "classes": [{"id": "cleric", "level": 1, "skills": ["insight", "medicine"]}],
            "background": {"id": acolyte, "replacement_skills": ["history"]}}
    s = ch.derive(char, data)
    assert s["background_overlap"] == ["insight"] and s["skills"]["history"]["proficiency"] == "proficient"
    s = ch.derive({**char, "background": {"id": acolyte}}, data)
    assert any("replacement" in c["what"] for c in s["choices_open"])


def test_eldritch_knight_school_limit(data):
    ek = sub_id(data, "fighter", "Eldritch Knight")
    shield, sleep, charm = (find(data.spells, n)["id"] for n in ("Shield", "Sleep", "Charm Person"))
    s = ch.derive({"name": "EK", "classes": [{"id": "fighter", "level": 3, "subclass": ek, "spells": {"known": [shield, sleep, charm]}}]}, data)
    caster = s["spellcasting"]["casters"][0]
    assert caster["school_limit"] == {"schools": ["A", "V"], "free": 1, "outside": 2}
    assert any("other schools" in p for p in s["problems"])


def test_spell_mastery_and_signature_spells(data):
    shield, invis, fireball, counter = (find(data.spells, n)["id"] for n in ("Shield", "Invisibility", "Fireball", "Counterspell"))
    s = ch.derive({"name": "Wiz", "classes": [{"id": "wizard", "level": 20, "spells": {
        "mastery": {"1": shield, "2": invis}, "signature": [fireball, counter]}}]}, data)
    caster = s["spellcasting"]["casters"][0]
    listed = {c["name"]: c for c in caster["list"]}
    assert listed["Shield"]["usage"] == "at will" and listed["Fireball"]["note"] == "Signature Spell"
    assert next(c for c in s["counters"] if c["name"] == "Signature Spell: Fireball")["reset"] == "short"


def test_item_speeds(data):
    boots = data.item_by_name["winged boots"]["id"]
    s = ch.derive({"name": "B", "classes": [{"id": "fighter", "level": 1}], "inventory": [{"id": boots, "equipped": True, "attuned": True}]}, data)
    assert s["speed"]["fly"] == s["speed"]["walk"] == 30


def test_custom_senses_speeds_defenses(data):
    s = ch.derive({"name": "C", "classes": [{"id": "fighter", "level": 1}], "custom_senses": {"blindsight": 10},
                   "custom_speeds": {"fly": 40}, "custom_defenses": [{"type": "resist", "name": "Fire"}]}, data)
    assert s["senses"]["blindsight"] == 10 and s["speed"]["fly"] == 40 and "fire" in s["defenses"]["resist"]


def test_save_notes_from_traits_and_features(data):
    dwarf = find(data.races, "Dwarf (Hill)")["id"]
    notes = ch.derive({"name": "N", "race": {"id": dwarf}, "classes": [{"id": "barbarian", "level": 2}]}, data)["save_notes"]
    texts = {n["source"]: n["text"] for n in notes}
    assert texts["Dwarven Resilience"] == "saving throws against poison"
    assert texts["Rage"].endswith("(while raging)")


def test_elemental_adept_type_in_name(data):
    adept = find(data.feats, "Elemental Adept")["id"]
    s = ch.derive({"name": "E", "classes": [{"id": "wizard", "level": 1}], "bonus_feats": [{"id": adept, "damage_type": "fire"}]}, data)
    assert any(f["name"] == "Elemental Adept (Fire)" for f in s["features"])


def test_wizard_book_rituals_listed(data):
    detect = find(data.spells, "Detect Magic")["id"]
    s = ch.derive({"name": "W", "classes": [{"id": "wizard", "level": 1, "spells": {"known": [detect], "prepared": []}}]}, data)
    card = next(c for c in s["spellcasting"]["casters"][0]["list"] if c["name"] == "Detect Magic")
    assert card["ritual_only"] and not card["prepared"]


def test_custom_background_takes_another_feature(data):
    acolyte, criminal = find(data.backgrounds, "Acolyte")["id"], find(data.backgrounds, "Criminal")["id"]
    s = ch.derive({"name": "B", "classes": [{"id": "fighter", "level": 1}],
                   "background": {"id": acolyte, "custom": {"skills": ["stealth", "arcana"], "tools": [], "languages": [], "name": "Temple Thief", "feature_from": criminal}}}, data)
    feature = next(f for f in s["features"] if f["kind"] == "background")
    assert feature["origin"] == "Criminal" and s["background"] == "Temple Thief"


def test_artificer_infusions(data):
    weapon = next(o["id"] for o in data.optionalfeatures.values() if o["name"] == "Enhanced Weapon")
    defense = next(o["id"] for o in data.optionalfeatures.values() if o["name"] == "Enhanced Defense")
    char = {"name": "A", "abilities": {"base": {a: 10 for a in ch.ABILITIES}},
            "classes": [{"id": "artificer", "level": 2, "optionalfeatures": [weapon, defense]}],
            "inventory": [{"id": data.item_by_name["mace"]["id"], "equipped": True, "infusion": weapon},
                          {"id": data.item_by_name["shield"]["id"], "equipped": True, "infusion": defense}]}
    s = ch.derive(char, data)
    mace = next(a for a in s["attacks"] if a["name"].startswith("Mace"))
    assert mace["to_hit"] == 0 + 2 + 1 and s["armor_class"]["value"] == 10 + 3
    assert s["infusions"] == {"used": 2, "max": 2}


def test_passives_drop_with_disadvantage(data):
    base = {"name": "P", "classes": [{"id": "fighter", "level": 1}]}
    normal = ch.derive(base, data)["passives"]["perception"]
    assert ch.derive({**base, "play": {"conditions": ["poisoned"]}}, data)["passives"]["perception"] == normal - 5


def test_coins_in_containers(data):
    bag, pack = data.item_by_name["bag of holding"]["id"], data.item_by_name["backpack"]["id"]
    base = {"name": "C", "classes": [{"id": "fighter", "level": 1}]}
    s = ch.derive({**base, "inventory": [{"id": pack, "uid": "p", "coins": {"gp": 100}}, {"id": bag, "uid": "b", "coins": {"gp": 500}}]}, data)
    plain = ch.derive({**base, "inventory": [{"id": pack, "uid": "p"}, {"id": bag, "uid": "b"}]}, data)
    assert s["encumbrance"]["weight"] - plain["encumbrance"]["weight"] == 2  # 100 gp in the backpack; the bag's 500 weigh nothing
    assert [b["coins"]["gp"] for b in s["container_coins"]] == [100, 500]
