"""Compendium-to-pack converter, on a small invented compendium (no book text)."""

from ttrpgtools.dnd5e import content

FIXTURE = """<?xml version="1.0" encoding="UTF-8"?>
<compendium version="5">
  <class>
    <name>Warlock</name><hd>8</hd><proficiency>Wisdom, Charisma, Arcana</proficiency>
    <numSkills>2</numSkills><armor>Light Armor</armor><weapons>Simple Weapons</weapons>
    <spellAbility>Charisma</spellAbility><slotsReset>S</slotsReset><subclass>Otherworldly Patron</subclass>
    <autolevel level="1"><slots>2, 1</slots></autolevel>
    <autolevel level="1"><counter><name>Spells Known</name><value>2</value></counter></autolevel>
    <autolevel level="1"><feature><name>Pact Magic</name><text>Base text.</text>
      <text>Source:\tPlayer's Handbook (2014) p. 107</text></feature></autolevel>
    <autolevel level="1"><feature optional="YES"><name>Otherworldly Patron: The Fiend</name><text>Fiend text.</text>
      <text>Source:\tPlayer's Handbook (2014) p. 109</text></feature></autolevel>
    <autolevel level="6"><feature optional="YES"><name>The Fiend: Dark One's Own Luck</name><text>Luck.</text>
      <text>Source:\tPlayer's Handbook (2014) p. 109</text></feature>
      <counter><name>Dark One's Luck</name><value>1</value><reset>S</reset></counter></autolevel>
    <autolevel level="1"><feature optional="YES"><name>Otherworldly Patron: Goat (HB)</name><text>Goat.</text>
      <text>Source:\tPlayer's Handbook (2014) p. 1</text></feature></autolevel>
    <autolevel level="1"><feature optional="YES"><name>Otherworldly Patron: The Lurker</name><text>UA.</text>
      <text>Source:\tUnearthed Arcana: Sorcerer And Warlock p. 3</text></feature></autolevel>
    <autolevel level="3"><feature optional="YES"><name>Pact Boon: Pact of the Blade</name><text>Blade.</text>
      <text>Source:\tPlayer's Handbook (2014) p. 107</text></feature></autolevel>
    <autolevel level="10"><feature optional="YES"><name>Pact Boon: Pact of the Blade</name><text>Blade again.</text>
      <text>Source:\tPlayer's Handbook (2014) p. 107</text></feature></autolevel>
  </class>
  <class>
    <name>Tinkerer (Homebrew)</name><hd>8</hd>
    <autolevel level="1"><feature><name>Gadgets</name><text>Source:\tSome Homebrew Book p. 2</text></feature></autolevel>
  </class>
  <spell><name>Invocation: Agonizing Blast</name><level>0</level><classes>Eldritch Invocations</classes>
    <text>Prerequisite: eldritch blast cantrip</text><text>Effect.</text>
    <text>Source:\tPlayer's Handbook (2014) p. 110</text></spell>
  <spell><name>Infusion: Enhanced Defense</name><level>0</level><classes>Artificer Infusions</classes>
    <text>Effect.</text><text>Source:\tEberron: Rising from the Last War p. 62, Tasha's Cauldron of Everything</text></spell>
  <spell><name>Hex</name><level>1</level><school>EN</school>
    <classes>School: Enchantment, Warlock, Warlock (Fiend), Artificer (Effigist (HB))</classes>
    <text>Curse.</text><text>Source:\tPlayer's Handbook (2014) p. 251</text></spell>
  <spell><name>Goat Bleat</name><level>0</level><classes>Warlock (Goat (HB))</classes>
    <text>Source:\tPlayer's Handbook (2014) p. 1</text></spell>
  <race><name>Elf, Pallid</name><size>M</size><speed>30</speed><ability>Dex 2, Wis 1</ability>
    <trait><name>Description</name><text>Pale.</text>
      <text>Source:\tPlayer's Handbook (2014) p. 23,\n\tExplorer's Guide to Wildemount p. 163</text></trait></race>
  <race><name>Elf, Avariel</name><size>M</size><speed>30</speed>
    <trait><name>Description</name><text>Winged.</text><text>Source:\tPlayer's Handbook (2014) p. 23</text></trait>
    <trait><name>Flight</name><text>Fly.</text><text>Source:\tUnearthed Arcana: Elf Subraces p. 1</text></trait></race>
  <feat><name>Resilient (Wisdom)</name><prerequisite></prerequisite><text>Pick one.</text>
    <text>Source:\tPlayer's Handbook (2014) p. 168</text><modifier category="ability score">Wisdom +1</modifier></feat>
  <feat><name>Fighting Style: Archery</name><text>Source:\tPlayer's Handbook (2014) p. 72</text></feat>
  <feat><name>Gift of the Chromatic Dragon</name><text>Source:\tFizban's Treasury of Dragons p. 2024</text></feat>
  <item><name>Chain Mail</name><type>HA</type><weight>55</weight><value>75.0</value><ac>16</ac>
    <stealth>1</stealth><strength>13</strength><text>Rings.</text>
    <text>Source:\tPlayer's Handbook (2014) p. 145</text></item>
</compendium>
"""


def build(tmp_path):
    xml = tmp_path / "compendium.xml"
    xml.write_text(FIXTURE)
    return content.build(xml)


def merged(packs):
    return {kind: [e for p in packs.values() for e in p[kind]] for kind in content.KINDS}


def test_split_source_handles_one_line_and_many_lines():
    _, pairs = content.split_source("x\nSource:\tEberron: Rising from the Last War p. 62, Tasha's Cauldron of Everything")
    assert pairs == [("Eberron: Rising from the Last War", 62), ("Tasha's Cauldron of Everything", None)]
    _, pairs = content.split_source("x\nSource:\tPlayer's Handbook (2014) p. 23,\n\tExplorer's Guide to Wildemount p. 163")
    assert [content.book_of(t) for t, _ in pairs] == ["phb", "egw"]


def test_class_subclass_and_options(tmp_path):
    packs, _ = build(tmp_path)
    m = merged(packs)
    assert [c["name"] for c in m["classes"]] == ["Warlock"]
    warlock = m["classes"][0]
    assert warlock["slots"] == {"1": [2, 1]}
    assert warlock["table"] == {"Spells Known": {"1": 2}}
    assert [s["name"] for s in m["subclasses"]] == ["The Fiend"]
    fiend = m["subclasses"][0]
    assert [f["name"] for f in fiend["features"]] == ["Dark One's Own Luck"]
    assert fiend["features"][0]["counters"][0]["reset"] == "S"


def test_options_from_spell_rows_and_dedupe(tmp_path):
    packs, _ = build(tmp_path)
    opts = {(o["group"], o["choice"]): o for o in merged(packs)["options"]}
    assert opts[("Invocation", "Agonizing Blast")]["prerequisite"] == "eldritch blast cantrip"
    assert opts[("Invocation", "Agonizing Blast")]["class"] == "Warlock"
    assert opts[("Infusion", "Enhanced Defense")]["book"] == "erlw"
    blade = [o for o in merged(packs)["options"] if o["choice"] == "Pact of the Blade"]
    assert len(blade) == 1 and blade[0]["level"] == 3


def test_spell_lists_use_short_subclass_names_and_drop_homebrew(tmp_path):
    packs, report = build(tmp_path)
    spells = {s["name"]: s for s in merged(packs)["spells"]}
    assert spells["Hex"]["classes"] == ["Warlock"]
    assert [t["subclass_id"] for t in spells["Hex"]["subclass_lists"]] == ["warlock-the-fiend"]
    assert "Goat Bleat" not in spells
    assert "Invocation: Agonizing Blast" not in spells


def test_races_take_the_last_title_and_reject_playtest_traits(tmp_path):
    packs, _ = build(tmp_path)
    races = merged(packs)["races"]
    assert [(r["name"], r["book"]) for r in races] == [("Elf, Pallid", "egw")]
    assert races[0]["abilities"] == {"Dex": 2, "Wis": 1}


def test_feats_group_variants_and_skip_fighting_style_copies(tmp_path):
    packs, _ = build(tmp_path)
    feats = merged(packs)["feats"]
    assert {(f["feat"], f["variant"]) for f in feats} == {("Resilient", "Wisdom"), ("Gift of the Chromatic Dragon", None)}


def test_homebrew_and_playtest_never_pass(tmp_path):
    packs, report = build(tmp_path)
    names = [e["name"] for kind in content.KINDS for e in merged(packs)[kind]]
    assert not any("(HB)" in n or "Homebrew" in n or "Lurker" in n or "Tinkerer" in n for n in names)
    assert report.rejected["class"] == 1


def test_item_fields(tmp_path):
    packs, _ = build(tmp_path)
    mail = merged(packs)["items"][0]
    assert (mail["type"], mail["ac"], mail["strength"], mail["stealth_disadvantage"]) == ("heavy armor", 16, 13, True)


def test_no_2024_titles_on_the_allow_list():
    for key, (title, spellings) in content.BOOKS.items():
        assert "2024" not in title and not any("2024" in s for s in spellings), key
