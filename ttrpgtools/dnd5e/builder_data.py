"""Builder data: 5etools-src to the files the 5e character builder reads.

    python -m ttrpgtools.dnd5e.builder_data /path/to/5etools-src [out_dir]

Writes `content/dnd5e/private/builder/<kind>.json` (classes, races, backgrounds,
feats, optionalfeatures, spells, items, languages) and `meta.json` with counts.

5etools carries the mechanics the compendium only has as prose: spells-known and
slot progressions, invocations known per level, skill and ability choices,
starting equipment, multiclass requirements, structured prerequisites. Only the
2014-era sources in SOURCES pass; any entry with `edition: "one"` (the 2024
rules) is refused even under an allowed source. Entries keep the 5etools entry
format; the frontend renders the {@tag} markup.
"""

from __future__ import annotations

import copy
import glob
import json
import re
import subprocess
import sys
from collections import Counter
from itertools import zip_longest
from pathlib import Path
from typing import Any

DEFAULT_OUT = Path(__file__).resolve().parents[2] / "content" / "dnd5e" / "private" / "builder"

#: 5etools source key -> our book key (same keys as content.BOOKS).
SOURCES = {
    "PHB": "phb", "DMG": "dmg", "MM": "mm", "XGE": "xge", "TCE": "tce", "SCAG": "scag", "VGM": "vgm",
    "MTF": "mtf", "MPMM": "mpmm", "EEPC": "eepc", "FTD": "ftd", "EGW": "egw", "ERLW": "erlw", "WGE": "wge",
    "GGR": "ggr", "MOT": "mot", "VRGR": "vrgr", "SCC": "scc", "AI": "ai", "BMT": "bmt", "BGG": "bgg",
    "DSotDQ": "dsotdq", "SatO": "psa", "AAG": "aag", "BAM": "aag", "LoX": "aag", "WBtW": "wbtw",
    "CRCotN": "cotn", "BGDIA": "bgdia", "LLK": "llk", "ToA": "toa", "WDH": "wdh", "WDMM": "wdmm",
    "PaBTSO": "pabtso", "TftYP": "tftyp", "IDRotF": "idrotf", "PotA": "pota", "SKT": "skt", "OotA": "oota",
    "CoS": "cos", "CM": "cm", "IMR": "imr", "QftIS": "qis", "GoS": "gos", "DitLCoT": "dsotdc",
    "HotDQ": "hotdq", "RoT": "rot", "RoTOS": "rot", "LMoP": "lmop", "JttRC": "jttrc", "KftGV": "kftgv",
    "VEoR": "vecna", "TTP": "ttp", "OGA": "oga", "LR": "lr", "DC": "ek", "SDW": "ek", "HftT": "htt",
    "AL": "al", "AitFR-AVT": "aitfr",
}

ABILITIES = ("str", "dex", "con", "int", "wis", "cha")


def allowed(entry: dict) -> bool:
    source = entry.get("source", "")
    return (source in SOURCES or source.startswith("TftYP")) and entry.get("edition") != "one"


def book(source: str) -> str:
    return "tftyp" if source.startswith("TftYP") else SOURCES.get(source, source.lower())


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


# --- _copy resolution -------------------------------------------------------

def _apply_mod(target: dict, prop: str, mod: Any) -> None:
    """The handful of 5etools _mod operations the 2014 data uses."""
    for op in mod if isinstance(mod, list) else [mod]:
        if op == "remove":
            target.pop(prop, None)
            continue
        if not isinstance(op, dict):
            continue
        mode = op.get("mode")
        items = op.get("items")
        items = items if isinstance(items, list) else [items] if items is not None else []
        arr = target.setdefault(prop, [])
        if mode == "appendArr":
            arr.extend(items)
        elif mode == "prependArr":
            arr[:0] = items
        elif mode == "insertArr":
            arr[op.get("index", 0):op.get("index", 0)] = items
        elif mode == "replaceArr":
            name = op.get("replace")
            name = name.get("index") if isinstance(name, dict) and "index" in name else name
            for i, old in enumerate(arr):
                if (isinstance(name, int) and i == name) or (isinstance(old, dict) and old.get("name") == name) or old == name:
                    arr[i:i + 1] = items
                    break
        elif mode == "removeArr":
            names = op.get("names") or []
            names = names if isinstance(names, list) else [names]
            target[prop] = [x for x in arr if not (isinstance(x, dict) and x.get("name") in names) and x not in names]
        elif mode == "replaceTxt":
            pattern, repl = op.get("replace", ""), op.get("with", "")
            target[prop] = json.loads(re.sub(re.escape(pattern), repl.replace("\\", "\\\\"), json.dumps(arr)))


def resolve_copies(entries: list[dict]) -> list[dict]:
    by_key = {(e.get("name"), e.get("source")): e for e in entries}

    def resolve(e: dict, depth: int = 0) -> dict:
        if "_copy" not in e or depth > 5:
            return e
        ref = e["_copy"]
        base = by_key.get((ref.get("name"), ref.get("source")))
        if base is None:
            return {k: v for k, v in e.items() if k != "_copy"}
        out = copy.deepcopy(resolve(base, depth + 1))
        for key in ("reprintedAs", "srd", "basicRules", "otherSources", "hasFluff", "hasFluffImages"):
            out.pop(key, None)
        for prop, mod in (ref.get("_mod") or {}).items():
            if prop == "*":
                continue
            _apply_mod(out, prop, mod)
        out.update({k: v for k, v in e.items() if k != "_copy"})
        return out

    return [resolve(e) for e in entries]


# --- classes ----------------------------------------------------------------

def _class_ref(ref: str) -> tuple:
    """"Name|Class|ClassSource|Level|Source" with PHB defaults."""
    parts = (ref.split("|") + [""] * 5)[:5]
    name, cls, cls_src, level, src = parts
    cls_src = cls_src or "PHB"
    return name, cls, cls_src, int(level or 0), src or cls_src


def _subclass_ref(ref: str) -> tuple:
    """"Name|Class|ClassSource|SubShort|SubSource|Level|Source" with PHB defaults."""
    parts = (ref.split("|") + [""] * 7)[:7]
    name, cls, cls_src, short, sub_src, level, src = parts
    cls_src, sub_src = cls_src or "PHB", sub_src or "PHB"
    return name, cls, cls_src, short, sub_src, int(level or 0), src or sub_src


def _inline_refs(entries: Any, class_features: dict, subclass_features: dict) -> Any:
    """Replace refClassFeature / refSubclassFeature objects with the feature they point at."""
    if isinstance(entries, list):
        return [_inline_refs(e, class_features, subclass_features) for e in entries]
    if not isinstance(entries, dict):
        return entries
    if entries.get("type") == "refSubclassFeature":
        target = subclass_features.get(_subclass_ref(entries["subclassFeature"]))
        if target is None:
            return {"type": "entries", "entries": []}
        return {"type": "entries", "name": target["name"],
                "entries": _inline_refs(target.get("entries", []), class_features, subclass_features)}
    if entries.get("type") == "refClassFeature":
        target = class_features.get(_class_ref(entries["classFeature"]))
        if target is None:
            return {"type": "entries", "entries": []}
        return {"type": "entries", "name": target["name"],
                "entries": _inline_refs(target.get("entries", []), class_features, subclass_features)}
    return {k: _inline_refs(v, class_features, subclass_features) for k, v in entries.items()}


CLASS_KEYS = (
    "hd", "proficiency", "spellcastingAbility", "casterProgression", "cantripProgression",
    "spellsKnownProgression", "spellsKnownProgressionFixed", "spellsKnownProgressionFixedAllowLowerLevel",
    "spellsKnownProgressionFixedByLevel", "preparedSpells", "preparedSpellsProgression", "optionalfeatureProgression",
    "featProgression", "startingProficiencies", "startingEquipment", "multiclassing", "classTableGroups", "subclassTitle",
)
SUBCLASS_KEYS = ("shortName", "additionalSpells", "spellcastingAbility", "casterProgression", "cantripProgression",
                 "spellsKnownProgression", "optionalfeatureProgression", "subclassTableGroups")


def convert_classes(data_dir: Path) -> list[dict]:
    out = []
    for path in sorted(glob.glob(str(data_dir / "class" / "class-*.json"))):
        if path.endswith(("class-sidekick.json", "class-mystic.json")):
            continue
        data = _load(Path(path))
        class_features = {(f["name"], f["className"], f["classSource"], f["level"], f["source"]): f
                          for f in data.get("classFeature", [])}
        subclass_features = {(f["name"], f["className"], f["classSource"], f["subclassShortName"],
                              f["subclassSource"], f["level"], f["source"]): f
                             for f in data.get("subclassFeature", [])}
        for cls in data.get("class", []):
            if not allowed(cls):
                continue
            features = []
            for item in cls.get("classFeatures", []):
                ref = item["classFeature"] if isinstance(item, dict) else item
                key = _class_ref(ref)
                feature = class_features.get(key)
                if feature is None or not allowed(feature):
                    continue
                features.append({
                    "name": feature["name"], "level": feature["level"], "source": feature["source"],
                    "book": book(feature["source"]), "page": feature.get("page"), "variant": bool(feature.get("isClassFeatureVariant")),
                    "gainSubclassFeature": bool(isinstance(item, dict) and item.get("gainSubclassFeature")),
                    "entries": _inline_refs(feature.get("entries", []), class_features, subclass_features),
                })
            subclasses = []
            for sub in data.get("subclass", []):
                if sub.get("className") != cls["name"] or sub.get("classSource") != cls["source"] or not allowed(sub):
                    continue
                sub_features = []
                for ref in sub.get("subclassFeatures", []):
                    feature = subclass_features.get(_subclass_ref(ref))
                    if feature is None:
                        continue
                    sub_features.append({
                        "name": feature["name"], "level": feature["level"], "source": feature["source"],
                        "book": book(feature["source"]), "page": feature.get("page"),
                        "entries": _inline_refs(feature.get("entries", []), class_features, subclass_features),
                    })
                subclasses.append({
                    "id": slug(f"{cls['name']}-{sub['name']}-{sub['source']}"), "name": sub["name"],
                    "source": sub["source"], "book": book(sub["source"]), "page": sub.get("page"),
                    **{k: sub[k] for k in SUBCLASS_KEYS if k in sub},
                    "features": sub_features,
                })
            out.append({
                "id": slug(cls["name"]), "name": cls["name"], "source": cls["source"], "book": book(cls["source"]),
                **{k: cls[k] for k in CLASS_KEYS if k in cls},
                "features": features,
                "subclasses": sorted(subclasses, key=lambda s: s["name"]),
            })
    return sorted(out, key=lambda c: c["name"])


# --- races ------------------------------------------------------------------

_RACE_SKIP = {"name", "source", "page", "raceName", "raceSource", "entries", "overwrite", "srd", "basicRules",
              "reprintedAs", "otherSources", "hasFluff", "hasFluffImages", "_versions", "soundClip"}


def _merge_list_of_dicts(base: list | None, extra: list | None) -> list | None:
    if not base or not extra:
        return copy.deepcopy(extra if extra is not None else base)
    return [{**(a or {}), **(b or {})} for a, b in zip_longest(base, extra)]


def merge_subrace(race: dict, sub: dict) -> dict:
    out = copy.deepcopy(race)
    overwrite = sub.get("overwrite") or {}
    for key, value in sub.items():
        if key in _RACE_SKIP:
            continue
        if key in ("ability", "skillProficiencies", "languageProficiencies", "toolProficiencies",
                   "weaponProficiencies", "armorProficiencies") and key in out and not overwrite.get(key):
            out[key] = _merge_list_of_dicts(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    entries = list(out.get("entries", []))
    for entry in sub.get("entries", []):
        target = isinstance(entry, dict) and (entry.get("data") or {}).get("overwrite")
        if target:
            entries = [entry if isinstance(e, dict) and e.get("name") == target else e for e in entries]
        else:
            entries.append(entry)
    out["entries"] = entries
    if sub.get("name"):
        out["subrace"] = sub["name"]
        out["name"] = f"{race['name']} ({sub['name']})"
    out["source"] = sub.get("source", race["source"])
    out["page"] = sub.get("page", race.get("page"))
    return out


ALL_ABILITIES = ["str", "dex", "con", "int", "wis", "cha"]
#: what 5etools' Renderer.race.mergeSubraces adds at render time to "lineage" races (MPMM, VRGR, AAG...):
#: +2/+1 or +1/+1/+1 to abilities of choice, and Common plus one language
LINEAGE_ABILITY = {
    "VRGR": [{"choose": {"weighted": {"from": ALL_ABILITIES, "weights": [2, 1]}}},
             {"choose": {"weighted": {"from": ALL_ABILITIES, "weights": [1, 1, 1]}}}],
    "UA1": [{"choose": {"weighted": {"from": ALL_ABILITIES, "weights": [2, 1]}}}],
}


def expand_lineage(race: dict) -> dict:
    lineage = race.get("lineage")
    if lineage not in LINEAGE_ABILITY:
        return race
    race = dict(race)
    race.setdefault("ability", LINEAGE_ABILITY[lineage])
    if not race.get("languageProficiencies"):
        race["languageProficiencies"] = [{"common": True, "anyStandard": 1}]
        race["entries"] = [*race.get("entries", []), {"type": "entries", "name": "Languages", "entries": [
            "You can speak, read, and write Common and one other language that you and your DM agree is appropriate for your character."]}]
    return race


def convert_races(data_dir: Path) -> list[dict]:
    data = _load(data_dir / "races.json")
    races = [expand_lineage(r) for r in resolve_copies(data["race"])]
    subs_by_race: dict[tuple, list] = {}
    for sub in data["subrace"]:
        subs_by_race.setdefault((sub.get("raceName"), sub.get("raceSource")), []).append(sub)
    out = []
    for race in races:
        if not allowed(race) or race.get("traitTags") and "NPC Race" in race.get("traitTags", []):
            continue
        subs = [s for s in subs_by_race.get((race["name"], race["source"]), [])
                if allowed({"source": s.get("source", race["source"]), "edition": s.get("edition")})]
        concrete = [merge_subrace(race, s) for s in subs] or [race]
        for r in concrete:
            r = {k: v for k, v in r.items() if k not in ("_versions", "soundClip", "hasFluff", "hasFluffImages")}
            r["race"] = race["name"]
            r["id"] = slug(f"{r['name']}-{r['source']}")
            r["book"] = book(r["source"])
            out.append(r)
    return sorted(out, key=lambda r: r["name"])


# --- spells -----------------------------------------------------------------

def convert_spells(data_dir: Path) -> list[dict]:
    index = _load(data_dir / "spells" / "index.json")
    lookup = _load(data_dir / "generated" / "gendata-spell-source-lookup.json")
    out = []
    for source, filename in index.items():
        if not allowed({"source": source}):
            continue
        for spell in _load(data_dir / "spells" / filename)["spell"]:
            if not allowed(spell):
                continue
            info = (lookup.get(spell["source"].lower()) or {}).get(spell["name"].lower()) or {}
            classes = sorted({c for src, cs in (info.get("class") or {}).items() if allowed({"source": src}) for c in cs})
            variant = sorted({c for src, cs in (info.get("classVariant") or {}).items() if allowed({"source": src})
                              for c, v in cs.items()
                              if all(allowed({"source": d}) for d in (v.get("definedInSources") or [src]))})
            subclasses = []
            for cls_src, by_class in (info.get("subclass") or {}).items():
                if not allowed({"source": cls_src}):
                    continue
                for cls, by_src in by_class.items():
                    for sub_src, by_short in by_src.items():
                        if not allowed({"source": sub_src}):
                            continue
                        for short, meta in by_short.items():
                            subclasses.append({"class": cls, "subclass": short, "source": sub_src,
                                               "name": (meta or {}).get("name", short)})
            spell = {k: v for k, v in spell.items() if k not in ("hasFluff", "hasFluffImages", "srd", "basicRules")}
            spell.update(id=slug(f"{spell['name']}-{spell['source']}"), book=book(spell["source"]), classes=classes,
                         classesVariant=[c for c in variant if c not in classes], subclasses=subclasses)
            out.append(spell)
    return sorted(out, key=lambda s: (s["level"], s["name"]))


# --- the rest ---------------------------------------------------------------

def _simple(entries: list[dict], drop: tuple = ()) -> list[dict]:
    out = []
    for e in resolve_copies(entries):
        if not allowed(e):
            continue
        e = {k: v for k, v in e.items() if k not in ("hasFluff", "hasFluffImages", "srd", "basicRules", *drop)}
        e["id"] = slug(f"{e['name']}-{e['source']}")
        e["book"] = book(e["source"])
        out.append(e)
    return sorted(out, key=lambda e: e["name"])


_VARIANT_SKIP = {"namePrefix", "nameSuffix", "nameRemove", "source", "page", "entries", "lootTables", "reprintedAs",
                 "referenceSources", "srd", "basicRules", "tier", "otherSources", "hasFluffImages"}


def _matches(base: dict, cond: dict) -> bool:
    return all(base.get(k) == v or (k == "type" and str(base.get("type", "")).split("|")[0] == str(v).split("|")[0])
               for k, v in cond.items())


def expand_variants(bases: list[dict], variants: list[dict]) -> list[dict]:
    """DMG-style generic items ("+1 Weapon", "Armor of Resistance") as one item per matching base item."""
    out = []
    for v in variants:
        inherits = v.get("inherits") or {}
        if not allowed({"source": inherits.get("source", ""), "edition": v.get("edition")}):
            continue
        for base in bases:
            if not any(_matches(base, cond) for cond in v.get("requires", [])):
                continue
            excludes = v.get("excludes") or {}
            if any(base.get(k) == val or (k == "name" and base["name"] in (val if isinstance(val, list) else [val]))
                   for k, val in excludes.items()):
                continue
            name = base["name"]
            if inherits.get("nameRemove"):
                name = name.replace(inherits["nameRemove"], "")
            item = {k: val for k, val in base.items() if k not in ("id", "book", "entries", "value", "srd", "basicRules")}
            item.update({k: val for k, val in inherits.items() if k not in _VARIANT_SKIP})
            item["name"] = f"{inherits.get('namePrefix', '')}{name}{inherits.get('nameSuffix', '')}".strip()
            item["source"], item["page"] = inherits["source"], inherits.get("page")
            item["baseItem"] = base["id"]
            item["variant"] = v["name"]
            text = json.dumps(inherits.get("entries", []))
            fills = {"baseName": base["name"], "dmgType": base.get("dmgType", ""), "bonusAc": inherits.get("bonusAc", ""),
                     "bonusWeapon": inherits.get("bonusWeapon", "")}
            text = re.sub(r"\{=(\w+)(?:/(\w))?\}",
                          lambda m: (lambda val: val.lower() if m.group(2) == "l" else val.title() if m.group(2) == "u" else val)(str(fills.get(m.group(1), ""))),
                          text)
            item["entries"] = json.loads(text)
            item["id"] = slug(f"{item['name']}-{item['source']}")
            item["book"] = book(item["source"])
            out.append(item)
    return out


def convert_items(data_dir: Path) -> list[dict]:
    base = _load(data_dir / "items-base.json")
    bases = _simple(base["baseitem"], drop=("mastery",))
    named = _simple(_load(data_dir / "items.json")["item"], drop=("mastery",))
    variants = expand_variants(bases, _load(data_dir / "magicvariants.json")["magicvariant"])
    taken = {i["id"] for i in named}
    items = bases + named + [v for v in variants if v["id"] not in taken]
    # DDB's own item tags (Utility, Combat, Social...), collected by private/ddb/build_item_tags.py.
    tag_file = Path(__file__).resolve().parents[2] / "content" / "dnd5e" / "private" / "ddb" / "item-tags.json"
    if tag_file.exists():
        ddb_tags = json.loads(tag_file.read_text())
        for item in items:
            found = ddb_tags.get(item["name"].lower()) or ddb_tags.get(re.sub(r"s? \(\d+\)$", "", item["name"].lower()))
            if found:
                item["ddbTags"] = found
    # DDB magic-item pictures (private/ddb/import_magic_item_art.py). DDB writes templates as
    # "Ammunition, +1" where 5etools says "+1 Ammunition"; expanded variants share their template's picture.
    art_file = tag_file.parent / "magic-item-art.json"
    if art_file.exists():
        art = {}
        for name, file in json.loads(art_file.read_text()).items():
            art[name] = file
            m = re.match(r"^(.+?), (\+\d)$", name)
            if m:
                art[f"{m.group(2)} {m.group(1)}"] = file
        words = lambda text: set(re.findall(r"[a-z+0-9']+", text.lower()))
        families = sorted(((words(k), f) for k, f in art.items()), key=lambda kv: -len(kv[0]))
        for item in items:
            for key in (item["name"].lower(), (item.get("variant") or "").lower()):
                if key and key in art:
                    item["ddbImage"] = art[key]
                    break
            else:
                # Family pictures: "Bag of Tricks" covers Gray/Rust/Tan Bag of Tricks.
                if item.get("rarity") not in (None, "none"):
                    have = words(item["name"])
                    item_art = next((f for w, f in families if len(w) > 1 and w <= have), None)
                    if item_art:
                        item["ddbImage"] = item_art
    for item in items:
        # 2024 property keys look like "2H|XPHB"; the classic ones have no suffix.
        item["property"] = [p.split("|")[0] for p in item.get("property", []) if not p.endswith(("|XPHB", "|XDMG"))]
        if isinstance(item.get("type"), str):
            item["type"] = item["type"].split("|")[0]
    return items


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def convert_names(data_dir: Path) -> list[dict]:
    """Name tables (XGE, MTF, GoS) flattened to lists, for the builder's "Show Suggestions"."""
    out = []
    for e in _simple(_load(data_dir / "names.json")["name"]):
        e["tables"] = [{"option": t["option"], "names": [row["result"] for row in t["table"]]} for t in e["tables"]]
        out.append(e)
    return out


def _find_named(entry, name):
    if isinstance(entry, dict):
        if entry.get("name") == name:
            return entry
        entry = list(entry.values())
    if isinstance(entry, list):
        for child in entry:
            found = _find_named(child, name)
            if found:
                return found
    return None


def convert_details(data_dir: Path) -> dict[str, list[dict]]:
    """Alignment summaries (PHB p. 122) and lifestyles with their daily cost (PHB p. 157) for the
    Background step's Character Details, taken from the PHB book text."""
    phb = _load(data_dir / "book" / "book-phb.json")
    alignments = []
    for text in _find_named(phb, "Alignment")["entries"]:
        m = re.match(r"\{@b ([^}]+)\} \((\w+)\) ", text) if isinstance(text, str) else None
        if m:
            name = " ".join(w.capitalize() for w in m.group(1).split())
            alignments.append({"id": m.group(2).lower(), "name": name, "entries": [text], "book": "phb", "page": 122})
    expenses = _find_named(phb, "Lifestyle Expenses")
    costs = dict(next(e for e in expenses["entries"] if isinstance(e, dict) and e.get("type") == "table")["rows"])
    lifestyles = [{"id": slug(name), "name": name, "cost": costs[name], "entries": _find_named(expenses, name)["entries"], "book": "phb", "page": 158}
                  for name in costs]
    # PHB ch. 7 "Using Each Ability": the text DDB shows under an ability's score table
    using = _find_named(phb, "Using Each Ability")
    abilitytexts = [{"id": name[:3].lower(), "name": name, "entries": _find_named(using, name)["entries"], "book": "phb", "page": using.get("page")}
                    for name in ("Strength", "Dexterity", "Constitution", "Intelligence", "Wisdom", "Charisma")]
    # rules text DDB prints under the Speed and Senses panes: PHB movement, PHB passive checks, MM special senses
    mm = _load(data_dir / "book" / "book-mm.json")
    speed = _find_named(_find_named(phb, "Adventuring"), "Speed")
    senses = _find_named(_find_named(mm, "Statistics"), "Senses")
    ruletexts = [
        {"id": "speed", "name": "Speed", "book": "phb", "page": speed.get("page"),
         "entries": [speed["entries"][0], _find_named(phb, "Special Types of Movement")]},
        {"id": "senses", "name": "Senses", "book": "phb", "page": None,
         "entries": [_find_named(phb, "Passive Checks"), *[e for e in senses["entries"] if isinstance(e, dict)]]},
        {"id": "inspiration", "name": "Inspiration", "book": "phb", "page": 125,
         "entries": _find_named(_find_named(phb, "Personality and Background"), "Inspiration")["entries"]},
        {"id": "ac", "name": "Armor Class", "book": "phb", "page": 14,
         "entries": _find_named(_find_named(phb, "5. Choose Equipment"), "Armor Class")["entries"]},
    ]
    return {"alignments": sorted(alignments, key=lambda a: a["name"]), "lifestyles": lifestyles, "abilitytexts": abilitytexts, "ruletexts": ruletexts}


def race_group(name: str) -> str:
    """The base race a race entry belongs to in the builder's chooser: "Elf (Drow)" -> "Elf"; the two
    MTF gith are filed under Githyanki and Githzerai, VGM's Yuan-ti Pureblood under Yuan-Ti."""
    base, _, inner = name.partition(" (")
    if base == "Gith":
        return inner.rstrip(")")
    if base.lower() == "yuan-ti pureblood":
        return "Yuan-Ti"
    return base


def _first_sentence(entries) -> str | None:
    if isinstance(entries, dict):  # a single entry where a list is usual
        entries = [entries]
    for entry in entries or []:
        if isinstance(entry, dict) and entry.get("type") in ("quote", "image", "gallery", "insetReadaloud"):
            continue  # epigraphs and pictures, not a description
        text = entry if isinstance(entry, str) else _first_sentence(entry.get("entries")) if isinstance(entry, dict) else None
        if text and len(re.sub(r"\{@[^}]*\}", "", text).strip()) < 3:
            continue  # a drop-cap letter split off the paragraph
        if text:
            text = re.sub(r"\{@\w+ ([^|}]+)[^}]*\}", r"\1", text)
            return re.match(r"(.+?[.!?])(\s|$)", text).group(1) if re.match(r"(.+?[.!?])(\s|$)", text) else text
    return None


def add_race_extras(races: list[dict], data_dir: Path) -> list[dict]:
    """Chooser data per race: its base-race `group`, DDB's species-card picture for that group
    (private/ddb/species-art.json) and a one-sentence `blurb` from the 5etools race fluff."""
    art_file = Path(__file__).resolve().parents[2] / "content" / "dnd5e" / "private" / "ddb" / "species-art.json"
    art = json.loads(art_file.read_text()) if art_file.exists() else {}
    fluff = {(f["name"], f["source"]): f for f in _load(data_dir / "fluff-races.json")["raceFluff"]}
    by_name: dict[str, list[dict]] = {}
    for f in fluff.values():
        by_name.setdefault(f["name"], []).append(f)

    def picture(group: str) -> str | None:
        g = group.lower()
        for test in (lambda t: t == g, lambda t: t.endswith(" " + g), lambda t: t.startswith(g + " ")):
            for title, file in art.items():
                if test(title.lower().replace("\u2019", "'")):
                    return file
        return None

    def group_blurb(group: str, source: str) -> str | None:
        for f in [fluff.get((group, source))] + [f for f in by_name.get(group, []) if book(f["source"])]:
            mod = ((f or {}).get("_copy") or {}).get("_mod", {}).get("entries") or {} if f else {}
            text = f and _first_sentence(f.get("entries") or (mod.get("items") if isinstance(mod, dict) else None))
            if text:
                return text
        return None

    for race in races:
        race["group"] = race_group(race["name"])
        found_group = group_blurb(race["group"], race["source"])
        if found_group:
            race["groupBlurb"] = found_group
        found = picture(race["group"])
        if found:
            race["ddbArt"] = found
        base = race["name"].split(" (")[0]
        candidates = [fluff.get((race["name"], race["source"])), fluff.get((base, race["source"]))]
        candidates += [f for f in by_name.get(base, []) if book(f["source"])]
        for f in filter(None, candidates):
            # copies of a shared chapter ("Uncommon Races") keep their own text in _copy._mod.entries.items
            mod = ((f.get("_copy") or {}).get("_mod") or {}).get("entries") or {}
            blurb = _first_sentence(f.get("entries") or (mod.get("items") if isinstance(mod, dict) else None))
            if blurb:
                race["blurb"] = blurb
                break
    return races


def convert_actions(data_dir: Path) -> list[dict]:
    """Combat actions (5etools actions.json) plus "Interact with an Object", which the PHB describes in a
    section of its own (p. 190) rather than as an action entry; the sheet's Actions tab links them."""
    actions = _simple(_load(data_dir / "actions.json")["action"])
    section = _find_named(_load(data_dir / "book" / "book-phb.json"), "Interacting with Objects Around You")
    if section:
        actions.append({"name": "Interact with an Object", "source": "PHB", "page": section.get("page", 190),
                        "entries": section["entries"], "id": "interact-with-an-object-phb", "book": "phb"})
    return actions


def add_class_art(classes: list[dict]) -> list[dict]:
    """DDB's small class picture (img1-*.png, 128 px) from private/ddb/img/class-art/<class>/, as a
    path under the /ddb/ asset route; the builder's class header shows it."""
    art_dir = Path(__file__).resolve().parents[2] / "content" / "dnd5e" / "private" / "ddb" / "img" / "class-art"
    for cls in classes:
        found = sorted((art_dir / cls["id"]).glob("img1-*.png")) if (art_dir / cls["id"]).is_dir() else []
        if found:
            cls["ddbArt"] = f"img/class-art/{cls['id']}/{found[0].name}"
        if (art_dir / cls["id"] / "card.webp").exists():  # card-sized cut of DDB's class illustration
            cls["ddbCard"] = f"img/class-art/{cls['id']}/card.webp"
        heroes = sorted((art_dir / cls["id"]).glob("img2-*.png")) if (art_dir / cls["id"]).is_dir() else []
        if heroes:  # DDB's detailsBackgroundAvatar: the class page's backdrop
            cls["ddbHero"] = f"img/class-art/{cls['id']}/{heroes[0].name}"
        figures = sorted((art_dir / cls["id"]).glob("img3-*.png")) if (art_dir / cls["id"]).is_dir() else []
        if figures:  # detailsForegroundAvatar: the class figure in front of it
            cls["ddbFigure"] = f"img/class-art/{cls['id']}/{figures[0].name}"
        gear = sorted((art_dir / cls["id"]).glob("iconic-gear-*.png")) if (art_dir / cls["id"]).is_dir() else []
        if gear:
            cls["ddbGear"] = f"img/class-art/{cls['id']}/{gear[0].name}"
    # the newer builder's class page texts (extract_class_details.py): tagline, highlights, iconic gear
    details_path = art_dir.parents[1] / "class-details.json"
    details = json.loads(details_path.read_text()) if details_path.exists() else {}
    taglines = details.get("_subclasses", {})
    for cls in classes:
        if cls["id"] in details:
            cls["ddbDetail"] = details[cls["id"]]
        for sub in cls.get("subclasses", []):
            if taglines.get(sub["name"]):
                sub["ddbTagline"] = taglines[sub["name"]]
    return classes


RULES_GROUPS = {"core", "supplement", "setting", "screen"}


def convert_books(data_dir: Path) -> list[dict]:
    """The builder's books (by our short id) with name and the group the Home step switches them by:
    rules (core, supplements, setting books), adventures, other (Dodo, 2026-10-25)."""
    meta = {b["id"]: (b["name"], "rules" if b.get("group") in RULES_GROUPS else "other") for b in _load(data_dir / "books.json")["book"]}
    meta.update({a["id"]: (a["name"], "adventures") for a in _load(data_dir / "adventures.json")["adventure"]})
    out = {}
    for source, key in SOURCES.items():
        if key in out:
            continue
        name, group = meta.get(source, (source, "other"))
        out[key] = {"id": key, "book": key, "name": name, "group": group, "source": source}
    return sorted(out.values(), key=lambda b: (b["group"], b["name"]))


def build(src: str | Path) -> dict[str, list[dict]]:
    data_dir = Path(src) / "data"
    return {
        "classes": add_class_art(convert_classes(data_dir)),
        "races": add_race_extras(convert_races(data_dir), data_dir),
        "backgrounds": _simple(_load(data_dir / "backgrounds.json")["background"]),
        "feats": _simple(_load(data_dir / "feats.json")["feat"]),
        "optionalfeatures": _simple(_load(data_dir / "optionalfeatures.json")["optionalfeature"]),
        "spells": convert_spells(data_dir),
        "items": convert_items(data_dir),
        "languages": _simple(_load(data_dir / "languages.json")["language"]),
        "conditions": _simple(_load(data_dir / "conditionsdiseases.json")["condition"]),
        "names": convert_names(data_dir),
        **convert_details(data_dir),
        "actions": convert_actions(data_dir),
        "books": convert_books(data_dir),
    }


def write(kinds: dict[str, list[dict]], out_dir: Path, src: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    for kind, entries in kinds.items():
        (out_dir / f"{kind}.json").write_text(json.dumps(entries, ensure_ascii=False, separators=(",", ":")))
    try:
        commit = subprocess.run(["git", "-C", str(src), "rev-parse", "--short", "HEAD"],
                                capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        commit = None
    meta = {"fivetools_commit": commit, "counts": {k: len(v) for k, v in kinds.items()},
            "by_book": {k: dict(Counter(e["book"] for e in v)) for k, v in kinds.items()}}
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=1))
    return meta


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    src = Path(argv[0])
    kinds = build(src)
    meta = write(kinds, Path(argv[1]) if len(argv) > 1 else DEFAULT_OUT, src)
    print(json.dumps(meta["counts"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
