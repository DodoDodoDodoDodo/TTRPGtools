"""Builder content: compendium XML to one JSON pack per allow-listed Wizards book.

    python -m ttrpgtools.dnd5e.content "/path/to/Complete_Compendium.xml" [out_dir]

Writes `content/dnd5e/private/packs/<book>.json` and prints a coverage table.
Only titles in BOOKS pass; everything else (homebrew, UA, Plane Shift, 2024)
is dropped and counted under "rejected". Classes carry no source of their own,
so a class goes into the pack of its base features and its subclasses and
options into the packs of their own rows.
"""

from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from .statblock import slugify

DEFAULT_OUT = Path(__file__).resolve().parents[2] / "content" / "dnd5e" / "private" / "packs"

#: book key -> (display title, every spelling the compendium uses, lower-cased).
BOOKS: dict[str, tuple[str, tuple[str, ...]]] = {
    "phb": ("Player's Handbook (2014)", ("player's handbook (2014)", "player's handbook")),
    "dmg": ("Dungeon Master's Guide (2014)", ("dungeon master's guide (2014)", "dungeon master's guide")),
    "mm": ("Monster Manual (2014)", ("monster manual (2014)",)),
    "xge": ("Xanathar's Guide to Everything", ("xanathar's guide to everything",)),
    "tce": ("Tasha's Cauldron of Everything", ("tasha's cauldron of everything",)),
    "scag": ("Sword Coast Adventurer's Guide", ("sword coast adventurer's guide",)),
    "vgm": ("Volo's Guide to Monsters", ("volo's guide to monsters",)),
    "mtf": ("Mordenkainen's Tome of Foes", ("mordenkainen's tome of foes",)),
    "mpmm": ("Mordenkainen Presents: Monsters of the Multiverse", ("mordenkainen presents: monsters of the multiverse",)),
    "eepc": ("Elemental Evil Player's Companion", ("elemental evil player's companion", "elemental evil: trinkets")),
    "ftd": ("Fizban's Treasury of Dragons", ("fizban's treasury of dragons",)),
    "egw": ("Explorer's Guide to Wildemount", ("explorer's guide to wildemount",)),
    "erlw": ("Eberron: Rising from the Last War", ("eberron: rising from the last war",)),
    "wge": ("Wayfinder's Guide to Eberron", ("wayfinder's guide to eberron", "wayfinder's guide to eberron chapter 5")),
    "ggr": ("Guildmasters' Guide to Ravnica", ("guildmasters' guide to ravnica",)),
    "mot": ("Mythic Odysseys of Theros", ("mythic odysseys of theros",)),
    "vrgr": ("Van Richten's Guide to Ravenloft", ("van richten's guide to ravenloft",)),
    "scc": ("Strixhaven: A Curriculum of Chaos", ("strixhaven: a curriculum of chaos",)),
    "ai": ("Acquisitions Incorporated", ("acquisitions incorporated",)),
    "bmt": ("The Book of Many Things", ("the book of many things",)),
    "bgg": ("Bigby Presents: Glory of the Giants", ("bigby presents: glory of the giants",)),
    "dsotdq": ("Dragonlance: Shadow of the Dragon Queen", ("dragonlance: shadow of the dragon queen",)),
    "psa": ("Planescape: Adventures in the Multiverse", ("planescape: adventures in the multiverse - sigil and the outlands",)),
    "aag": ("Spelljammer: Astral Adventurer's Guide", (
        "spelljammer: adventures in space - astral adventurer's guide",
        "spelljammer: adventures in space - light of xaryxis",
        "spelljammer: adventures in space - boo's astral menagerie",
    )),
    "wbtw": ("The Wild Beyond the Witchlight", ("the wild beyond the witchlight",)),
    "cotn": ("Critical Role: Call of the Netherdeep", ("critical role: call of the netherdeep",)),
    "bgdia": ("Baldur's Gate: Descent Into Avernus", ("baldur's gate: descent into avernus",)),
    "llk": ("Lost Laboratory of Kwalish", ("lost laboratory of kwalish",)),
    "toa": ("Tomb of Annihilation", ("tomb of annihilation",)),
    "wdh": ("Waterdeep: Dragon Heist", ("waterdeep: dragon heist",)),
    "wdmm": ("Waterdeep: Dungeon of the Mad Mage", ("waterdeep: dungeon of the mad mage",)),
    "pabtso": ("Phandelver and Below: The Shattered Obelisk", ("phandelver and below: the shattered obelisk",)),
    "tftyp": ("Tales from the Yawning Portal", ("tales from the yawning portal",)),
    "idrotf": ("Icewind Dale: Rime of the Frostmaiden", ("icewind dale: rime of the frostmaiden",)),
    "pota": ("Princes of the Apocalypse", ("princes of the apocalypse",)),
    "skt": ("Storm King's Thunder", ("storm king's thunder",)),
    "oota": ("Out of the Abyss", ("out of the abyss",)),
    "cos": ("Curse of Strahd", ("curse of strahd", "curse of strahd: optional backgrounds")),
    "cm": ("Candlekeep Mysteries", ("candlekeep mysteries",)),
    "imr": ("Infernal Machine Rebuild", ("infernal machine rebuild",)),
    "qis": ("Quests from the Infinite Staircase", ("quests from the infinite staircase",)),
    "gos": ("Ghosts of Saltmarsh", ("ghosts of saltmarsh",)),
    "dsotdc": ("Descent into the Lost Caverns of Tsojcanth", ("descent into the lost caverns of tsojcanth",)),
    "hotdq": ("Hoard of the Dragon Queen", ("hoard of the dragon queen",)),
    "rot": ("Rise of Tiamat", ("rise of tiamat", "the rise of tiamat online supplement")),
    "lmop": ("Lost Mine of Phandelver", ("lost mine of phandelver", "lost mines of phandelver")),
    "jttrc": ("Journeys through the Radiant Citadel", ("journeys through the radiant citadel",)),
    "kftgv": ("Keys from the Golden Vault", ("keys from the golden vault",)),
    "vecna": ("Vecna: Eve of Ruin", ("vecna: eve of ruin", "vecna dossier")),
    "ttp": ("The Tortle Package", ("the tortle package",)),
    "oga": ("One Grung Above", ("one grung above",)),
    "lr": ("Locathah Rising", ("locathah rising",)),
    "ek": ("Essentials Kit", ("essentials kit: divine contention", "essentials kit: sleeping dragon's wake")),
    "htt": ("Hunt for the Thessalhydra", ("hunt for the thessalhydra",)),
    "al": ("Adventurers League", ("adventurers league: rage of demons", "adventurers league: elemental evil", "mulmaster bonds and backgrounds")),
}

_TITLE_TO_BOOK = {spelling: key for key, (_, spellings) in BOOKS.items() for spelling in spellings}

#: Classes in the compendium that are not player classes.
NON_PC_CLASSES = {"Expert Sidekick", "Spellcaster Sidekick", "Warrior Sidekick"}

#: Rows that cite a Wizards book but are not in it. "Mage of X" is the 2020 UA
#: "Mages of Strixhaven"; the printed Strixhaven has no subclasses.
MISATTRIBUTED = re.compile(r"^Mage of ")

#: Name tags the compendium puts on homebrew and playtest rows, whatever they cite.
_UNOFFICIAL_TAG = re.compile(r"\((?:[^()]*\b)?(?:HB|UA|Homebrew|Livestream|Twitter)\b[^()]*\)", re.I)

#: Option groups the compendium stores as spell rows named "<Group>: <Choice>".
#: group -> (class, subclass or None, level the group opens at).
SPELL_ROW_OPTIONS = {
    "Invocation": ("Warlock", None, 2),
    "Metamagic": ("Sorcerer", None, 3),
    "Infusion": ("Artificer", None, 2),
    "Maneuver": ("Fighter", "Battle Master", 3),
    "Arcane Shot": ("Fighter", "Arcane Archer", 3),
    "Rune": ("Fighter", "Rune Knight", 3),
    "Elemental Discipline": ("Monk", "Way of the Four Elements", 3),
}
_PREREQUISITE = re.compile(r"^\s*Prerequisites?:\s*(.+?)\s*(?:\n|$)")

_LAND_TERRAINS = {"arctic", "coast", "desert", "forest", "grassland", "mountain", "swamp", "underdark"}
_SUBCLASS_FILLER = re.compile(r"\b(?:the|of|domain|school|magic|circle|oath|college|path|way|patron|tradition)\b")


def unofficial_name(name: str) -> bool:
    return bool(_UNOFFICIAL_TAG.search(name) or MISATTRIBUTED.match(name))


def _subclass_key(name: str) -> str:
    key = re.sub(r"[^a-z]", "", _SUBCLASS_FILLER.sub("", name.lower()))
    return "land" if key in _LAND_TERRAINS else key

ITEM_TYPES = {
    "LA": "light armor", "MA": "medium armor", "HA": "heavy armor", "S": "shield",
    "M": "melee weapon", "R": "ranged weapon", "A": "ammunition", "RD": "rod", "ST": "staff",
    "WD": "wand", "RG": "ring", "P": "potion", "SC": "scroll", "W": "wondrous item",
    "G": "adventuring gear", "$": "money",
}
SCHOOLS = {"A": "Abjuration", "C": "Conjuration", "D": "Divination", "EN": "Enchantment",
           "EV": "Evocation", "I": "Illusion", "N": "Necromancy", "T": "Transmutation"}
ABILITIES = {"str": "Str", "dex": "Dex", "con": "Con", "int": "Int", "wis": "Wis", "cha": "Cha"}

_SOURCE_LINE = re.compile(r"^(?P<title>.*?)(?:,)?(?:\s+p\.?\s*(?P<page>\d+))?\s*,?$")


def book_of(title: str) -> str | None:
    return _TITLE_TO_BOOK.get(title.strip().rstrip(",").strip().lower())


def split_source(text: str) -> tuple[str, list[tuple[str, int | None]]]:
    """Prose without the trailing "Source:" block, plus (title, page) pairs."""
    at = text.rfind("Source:")
    if at < 0:
        return text.strip(), []
    pairs = []
    # One title per line, or several on one line after page numbers: "ERLW p. 62, Tasha's ...".
    for line in re.split(r",\s*\n|\n|(?<=\d)\s*,\s*", text[at + 7:]):
        line = line.strip().rstrip(",").strip()
        if not line:
            continue
        m = _SOURCE_LINE.match(line)
        pairs.append((m.group("title").strip(), int(m.group("page")) if m.group("page") else None))
    return text[:at].strip(), pairs


def _text(el: ET.Element) -> str:
    return "\n".join((t.text or "") for t in el.findall("text"))


def _sourced(el: ET.Element) -> tuple[str, str | None, int | None, str | None]:
    """(prose, book key, page, raw first title) for an element with <text> children."""
    prose, pairs = split_source(_text(el))
    for title, page in pairs:
        key = book_of(title)
        if key:
            return prose, key, page, title
    return prose, None, None, pairs[0][0] if pairs else None


def _modifiers(el: ET.Element) -> list[dict]:
    return [{"category": (m.get("category") or "").lower(), "value": (m.text or "").strip()}
            for m in el.iter("modifier")]


def _split_top(text: str) -> list[str]:
    """Split on commas outside parentheses: "Artificer (Effigist (HB)), Warlock"."""
    parts, depth, cur = [], 0, []
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if "".join(cur).strip():
        parts.append("".join(cur).strip())
    return parts


def _csv(text: str | None) -> list[str]:
    return [p.strip() for p in (text or "").split(",") if p.strip()]


def _num(text: str | None) -> float | int | None:
    try:
        value = float(text)
    except (TypeError, ValueError):
        return None
    return int(value) if value.is_integer() else value


def _traits(el: ET.Element) -> list[dict]:
    out = []
    for t in el.findall("trait"):
        prose, _, _, _ = _sourced(t)
        entry = {"name": t.findtext("name") or "", "text": prose}
        mods = _modifiers(t)
        if mods:
            entry["modifiers"] = mods
        out.append(entry)
    return out


class Report:
    def __init__(self) -> None:
        self.kept: dict[str, Counter] = defaultdict(Counter)
        self.rejected: Counter = Counter()
        self.unsourced: Counter = Counter()
        self.notes: list[str] = []

    def keep(self, book: str, kind: str) -> None:
        self.kept[book][kind] += 1

    def reject(self, kind: str, raw_title: str | None) -> None:
        self.rejected[kind] += 1
        if raw_title is None:
            self.unsourced[kind] += 1


# --- entry converters -------------------------------------------------------

def convert_race(el: ET.Element) -> dict:
    name = el.findtext("name") or ""
    base, _, sub = name.partition(", ")
    abilities = {}
    for part in _csv(el.findtext("ability")):
        m = re.match(r"(\w+)\s+([+-]?\d+)", part)
        if m:
            abilities[m.group(1).capitalize()] = int(m.group(2))
    race = {
        "id": slugify(name), "name": name, "race": base, "subrace": sub or None,
        "size": el.findtext("size") or "", "speed": _num(el.findtext("speed")),
        "abilities": abilities, "proficiencies": _csv(el.findtext("proficiency")),
        "spell_ability": el.findtext("spellAbility") or None, "traits": _traits(el),
    }
    for tag in ("resistance", "immunity", "ancestry", "spells"):
        if el.findtext(tag):
            race[tag] = el.findtext(tag).strip()
    return race


def convert_background(el: ET.Element) -> dict:
    name = el.findtext("name") or ""
    bg = {"id": slugify(name), "name": name, "proficiencies": _csv(el.findtext("proficiency")),
          "traits": _traits(el)}
    for tag in ("tools", "languages", "ancestry"):
        if el.findtext(tag):
            bg[tag] = el.findtext(tag).strip()
    return bg


def convert_feat(el: ET.Element, prose: str) -> dict:
    name = el.findtext("name") or ""
    # The compendium splits a feat per choice: "Resilient (Wisdom)", "Magic Initiate (Bard)",
    # "Squat Nimbleness (Dexterity + Acrobatics (Proficient))". The builder shows one feat, then the variant.
    m = re.match(r"^(.*?)\s*\(((?:[^()]|\([^()]*\))*)\)$", name)
    base, variant = (m.group(1), m.group(2)) if m else (name, None)
    category = base.partition(": ")[0] if ": " in base else "Feat"  # "Dark Gift", "Draconic Gift"
    feat = {"id": slugify(name), "name": name, "feat": base, "variant": variant, "category": category,
            "prerequisite": (el.findtext("prerequisite") or "").strip() or None,
            "text": prose, "modifiers": _modifiers(el)}
    for tag in ("proficiency", "special"):
        if el.findtext(tag):
            feat[tag] = el.findtext(tag).strip()
    return feat


def convert_spell(el: ET.Element, prose: str) -> dict:
    name = el.findtext("name") or ""
    classes, subclass_lists = [], []
    for part in _split_top(el.findtext("classes") or ""):
        if part.startswith("School:"):
            continue
        m = re.match(r"^(.*?)\s*\((.*)\)$", part)
        if m:
            subclass_lists.append({"class": m.group(1).strip(), "subclass": m.group(2).strip()})
        else:
            classes.append(part)
    return {
        "id": slugify(name), "name": name, "level": int(el.findtext("level") or 0),
        "school": SCHOOLS.get(el.findtext("school") or "", el.findtext("school") or ""),
        "ritual": (el.findtext("ritual") or "").upper() == "YES",
        "time": el.findtext("time") or "", "range": el.findtext("range") or "",
        "components": el.findtext("components") or "", "duration": el.findtext("duration") or "",
        "classes": classes, "subclass_lists": subclass_lists, "text": prose,
        "rolls": [r.text for r in el.findall("roll") if r.text],
    }


def convert_item(el: ET.Element, prose: str) -> dict:
    name = el.findtext("name") or ""
    code = el.findtext("type") or ""
    item: dict[str, Any] = {
        "id": slugify(name), "name": name, "type": ITEM_TYPES.get(code, code), "type_code": code,
        "magic": (el.findtext("magic") or "").upper() == "YES",
        "detail": (el.findtext("detail") or "").strip(),
        "weight": _num(el.findtext("weight")), "value_gp": _num(el.findtext("value")),
        "properties": _csv(el.findtext("property")), "text": prose,
    }
    for tag, key in (("ac", "ac"), ("strength", "strength"), ("dmg1", "damage"),
                     ("dmg2", "damage_versatile"), ("dmgType", "damage_type"), ("range", "range"),
                     ("charges", "charges")):
        if (el.findtext(tag) or "").strip():
            value = el.findtext(tag).strip()
            item[key] = _num(value) if key in ("ac", "strength", "charges") else value
    if (el.findtext("stealth") or "").strip() in ("1", "YES"):
        item["stealth_disadvantage"] = True
    mods = _modifiers(el)
    if mods:
        item["modifiers"] = mods
    return item


# --- classes ----------------------------------------------------------------

def convert_class(el: ET.Element, report: Report) -> dict[str, Any] | None:
    """Return {"class": shell, "book": key, "subclasses": [...], "options": [...]}.

    Rows inside a class: non-optional features are the base class. Optional rows
    are named "<Prefix>: <Choice>". The prefix equal to the class's <subclass>
    text picks a subclass; a prefix equal to a subclass name is that subclass's
    later feature; any other prefix is an option group (Invocation, Maneuver...).
    """
    name = el.findtext("name") or ""
    subclass_group = (el.findtext("subclass") or "").strip()
    base_features: list[dict] = []
    optional_rows: list[dict] = []
    table_counters: dict[str, dict[int, Any]] = defaultdict(dict)
    slots: dict[int, list[int]] = {}
    asi_levels: list[int] = []

    for al in el.iter("autolevel"):
        level = int(al.get("level") or 0)
        if al.get("scoreImprovement", "").upper() == "YES":
            asi_levels.append(level)
        if al.find("slots") is not None and (al.findtext("slots") or "").strip():
            slots[level] = [int(x) for x in _csv(al.findtext("slots"))]
        features = al.findall("feature")
        counters = [{"name": c.findtext("name") or "", "value": _num(c.findtext("value")),
                     "reset": c.findtext("reset") or None, "level": level} for c in al.findall("counter")]
        if not features:
            for c in counters:
                table_counters[c["name"]][level] = c["value"]
            continue
        for i, f in enumerate(features):
            prose, book, page, raw = _sourced(f)
            row = {"name": f.findtext("name") or "", "level": level, "text": prose,
                   "book": book, "page": page, "raw_source": raw}
            mods = _modifiers(f)
            if mods:
                row["modifiers"] = mods
            if i == 0 and counters:
                row["counters"] = counters
            if f.get("optional", "").upper() == "YES":
                optional_rows.append(row)
            else:
                base_features.append(row)

    base_books = Counter(f["book"] for f in base_features if f["book"])
    if not base_books:
        report.reject("class", None)
        return None
    book = base_books.most_common(1)[0][0]
    for f in base_features:
        f["book"] = f["book"] or book

    by_prefix: dict[str, list[dict]] = defaultdict(list)
    loose: list[dict] = []
    for row in optional_rows:
        prefix, sep, choice = row["name"].partition(": ")
        if sep:
            by_prefix[prefix].append({**row, "choice": choice})
        else:
            loose.append(row)

    subclasses = []
    for row in by_prefix.pop(subclass_group, []):
        if not row["book"]:
            report.reject("subclass", row["raw_source"])
            continue
        sub_name = row["choice"]
        features = [{**r, "name": r["choice"]} for r in by_prefix.pop(sub_name, [])]
        subclasses.append({
            "id": slugify(f"{name}-{sub_name}"), "class": name, "name": sub_name, "book": row["book"],
            "page": row["page"], "level": row["level"], "text": row["text"],
            "counters": row.get("counters", []),
            "features": [f for f in features if f["book"]],
        })

    options = []
    for prefix, rows in by_prefix.items():
        for row in rows:
            if not row["book"]:
                report.reject("option", row["raw_source"])
                continue
            options.append({"id": slugify(f"{name}-{prefix}-{row['choice']}"), "class": name,
                            "group": prefix, **{k: v for k, v in row.items() if k != "raw_source"}})
    for row in loose:
        if row["book"]:
            options.append({"id": slugify(f"{name}-{row['name']}"), "class": name, "group": "Optional",
                            "choice": row["name"], **{k: v for k, v in row.items() if k != "raw_source"}})
        else:
            report.reject("option", row["raw_source"])

    shell = {
        "id": slugify(name), "name": name, "book": book, "hit_die": int(el.findtext("hd") or 0),
        "proficiency": _csv(el.findtext("proficiency")), "num_skills": int(el.findtext("numSkills") or 0),
        "armor": _csv(el.findtext("armor")), "weapons": _csv(el.findtext("weapons")),
        "tools": _csv(el.findtext("tools")), "wealth": el.findtext("wealth") or "",
        "spell_ability": el.findtext("spellAbility") or None,
        "slots_reset": el.findtext("slotsReset") or None, "subclass_group": subclass_group,
        "asi_levels": sorted(set(asi_levels)), "slots": {str(k): v for k, v in sorted(slots.items())},
        "table": {n: {str(k): v for k, v in sorted(lv.items())} for n, lv in table_counters.items()},
        "traits": _traits(el),
        "features": [{k: v for k, v in f.items() if k != "raw_source"} for f in base_features],
    }
    return {"class": shell, "book": book, "subclasses": subclasses, "options": options}


def convert_option_row(group: str, choice: str, prose: str, book: str, page: int | None) -> dict:
    cls, subclass, level = SPELL_ROW_OPTIONS[group]
    m = _PREREQUISITE.match(prose)
    option = {"id": slugify(f"{cls}-{group}-{choice}"), "class": cls, "group": group, "choice": choice,
              "name": choice, "level": level, "text": prose, "book": book, "page": page,
              "prerequisite": m.group(1) if m else None}
    if subclass:
        option["subclass"] = subclass
    return option


def _dedupe_options(packs: dict[str, dict], report: Report) -> None:
    """One option per (class, group, choice): class rows repeat an option at every
    level it can be taken (Metamagic at 3, 10, 17); keep the lowest level, and the
    prerequisite from whichever copy has one."""
    best: dict[tuple, dict] = {}
    for p in packs.values():
        for opt in p["options"]:
            key = (opt["class"], opt["group"], opt["choice"])
            seen = best.get(key)
            if seen is None:
                best[key] = opt
                continue
            if opt["level"] < seen["level"]:
                opt.setdefault("prerequisite", seen.get("prerequisite"))
                best[key] = opt
            elif not seen.get("prerequisite") and opt.get("prerequisite"):
                seen["prerequisite"] = opt["prerequisite"]
    keep = {id(o) for o in best.values()}
    removed = 0
    for p in packs.values():
        before = len(p["options"])
        p["options"] = [o for o in p["options"] if id(o) in keep]
        report.kept[p["book"]]["options"] -= before - len(p["options"])
        removed += before - len(p["options"])
    if removed:
        report.notes.append(f"duplicate option rows merged: {removed}")


# --- driver -----------------------------------------------------------------

KINDS = ("classes", "subclasses", "options", "races", "backgrounds", "feats", "spells", "items")


def build(xml_path: str | Path) -> tuple[dict[str, dict], Report]:
    root = ET.parse(str(xml_path)).getroot()
    report = Report()
    packs: dict[str, dict] = {key: {"book": key, "title": title, **{k: [] for k in KINDS}}
                              for key, (title, _) in BOOKS.items()}

    def add(book: str, kind: str, entry: dict) -> None:
        if unofficial_name(entry["name"]):
            report.reject({"classes": "class", "subclasses": "subclass"}.get(kind, kind.rstrip("s")), "name tag")
            return
        packs[book][kind].append(entry)
        report.keep(book, kind)

    for el in root:
        if el.tag == "class":
            if (el.findtext("name") or "") in NON_PC_CLASSES:
                continue
            converted = convert_class(el, report)
            if not converted:
                continue
            add(converted["book"], "classes", converted["class"])
            for sub in converted["subclasses"]:
                add(sub["book"], "subclasses", sub)
            for opt in converted["options"]:
                add(opt["book"], "options", opt)
            continue
        if el.tag == "monster":
            continue
        if el.tag in ("race", "background"):
            # Sources sit on the traits. A subrace lists its parent race's book
            # first and its own last, and a UA variant cites UA on a later trait.
            titles = [pair for t in el.findall("trait") for pair in split_source(_text(t))[1]]
            if not titles or not all(book_of(title) for title, _ in titles):
                report.reject(el.tag, titles[0][0] if titles else None)
                continue
            first_trait_titles = next(split_source(_text(t))[1] for t in el.findall("trait")
                                      if split_source(_text(t))[1])
            title, page = first_trait_titles[-1]
            entry = convert_race(el) if el.tag == "race" else convert_background(el)
            entry.update(book=book_of(title), page=page)
            add(entry["book"], el.tag + "s", entry)
            continue
        prose, book, page, raw = _sourced(el)
        if not book:
            report.reject(el.tag, raw)
            continue
        group, sep, choice = (el.findtext("name") or "").partition(": ")
        if el.tag == "feat" and group == "Fighting Style":
            continue  # copies of the class option rows
        if el.tag == "spell" and sep and group in SPELL_ROW_OPTIONS:
            add(book, "options", convert_option_row(group, choice, prose, book, page))
            continue
        entry = {"feat": convert_feat, "spell": convert_spell, "item": convert_item}[el.tag](el, prose)
        entry.update(book=book, page=page)
        add(book, el.tag + "s", entry)

    _prune_spell_lists(packs, report)
    _dedupe_options(packs, report)
    return {k: p for k, p in packs.items() if any(p[kind] for kind in KINDS)}, report


def _prune_spell_lists(packs: dict[str, dict], report: Report) -> None:
    """Keep only class and subclass spell-list tags that point at kept content.

    Spell tags use short subclass names ("Wizard (Graviturgy)", "Druid (Arctic)",
    "Warlock (Genie Dao)"); they match a subclass by a normalised key or prefix.
    """
    class_names = {c["name"] for p in packs.values() for c in p["classes"]}
    subclasses: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for p in packs.values():
        for sub in p["subclasses"]:
            subclasses[sub["class"]].append((_subclass_key(sub["name"]), sub["id"]))

    def match(cls: str, tag: str) -> str | None:
        key = _subclass_key(tag)
        for sub_key, sub_id in subclasses.get(cls, []):
            if key and (key == sub_key or key.startswith(sub_key) or sub_key.startswith(key)):
                return sub_id
        return None

    dropped = 0
    orphans = []
    for p in packs.values():
        kept_spells = []
        for spell in p["spells"]:
            spell["classes"] = [c for c in spell["classes"] if c in class_names]
            kept = []
            for tag in spell["subclass_lists"]:
                sub_id = match(tag["class"], tag["subclass"])
                if sub_id and not unofficial_name(tag["subclass"]):
                    kept.append({**tag, "subclass_id": sub_id})
                else:
                    dropped += 1
            spell["subclass_lists"] = kept
            # Invocations, maneuvers and the like are also modelled as spells; they are options here.
            if spell["classes"] or kept:
                kept_spells.append(spell)
            else:
                orphans.append(spell["name"])
                report.kept[p["book"]]["spells"] -= 1
        p["spells"] = kept_spells
    report.orphan_spells = orphans
    if orphans:
        report.notes.append(f"spells on no kept class list, dropped: {len(orphans)}")
    if dropped:
        report.notes.append(f"spell subclass-list tags dropped (homebrew or unmatched): {dropped}")


def write(packs: dict[str, dict], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.json"):
        old.unlink()
    for key, pack in packs.items():
        (out_dir / f"{key}.json").write_text(json.dumps(pack, ensure_ascii=False, indent=1))


def coverage_table(packs: dict[str, dict], report: Report) -> str:
    head = ["book"] + list(KINDS)
    rows = [head]
    for key in sorted(packs, key=lambda k: -sum(len(packs[k][x]) for x in KINDS)):
        rows.append([key] + [str(len(packs[key][kind]) or "") for kind in KINDS])
    rows.append(["TOTAL"] + [str(sum(len(p[kind]) for p in packs.values())) for kind in KINDS])
    widths = [max(len(r[i]) for r in rows) for i in range(len(head))]
    lines = ["  ".join(c.rjust(w) if i else c.ljust(w) for i, (c, w) in enumerate(zip(r, widths))) for r in rows]
    lines.append("rejected (not on the allow-list): " + ", ".join(f"{k} {v}" for k, v in sorted(report.rejected.items())))
    lines.append("of which without any Source line: " + ", ".join(f"{k} {v}" for k, v in sorted(report.unsourced.items())))
    lines.extend(report.notes)
    return "\n".join(lines)


def load_packs(books: Iterable[str] | None = None, pack_dir: Path = DEFAULT_OUT) -> dict[str, list[dict]]:
    """Merge packs into one content dict; `books` limits which packs load."""
    wanted = set(books) if books else None
    merged: dict[str, list[dict]] = {kind: [] for kind in KINDS}
    for path in sorted(pack_dir.glob("*.json")):
        if wanted is not None and path.stem not in wanted:
            continue
        pack = json.loads(path.read_text())
        for kind in KINDS:
            merged[kind].extend(pack.get(kind, []))
    return merged


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    packs, report = build(argv[0])
    out_dir = Path(argv[1]) if len(argv) > 1 else DEFAULT_OUT
    write(packs, out_dir)
    print(coverage_table(packs, report))
    print(f"wrote {len(packs)} packs to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
