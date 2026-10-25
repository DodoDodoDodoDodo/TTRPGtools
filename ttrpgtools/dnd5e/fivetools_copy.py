"""5etools' variant monsters: an entry with `_copy` is another monster (its base) plus optional templates
(`_templates`, from template.json) and changes (`_mod`). This builds the full raw monster the importer can
convert. The change modes cover what the 2014 bestiaries use; an unknown mode is reported, never guessed."""

from __future__ import annotations

import copy
import json
import math
import re
from pathlib import Path
from typing import Any

#: entry arrays a "*" change applies to
TEXT_FIELDS = ("trait", "action", "bonus", "reaction", "legendary", "mythic", "lairActions", "regionalEffects", "variant", "spellcasting")
CR_PROF = {0: 2, 1: 2, 2: 2, 3: 2, 4: 2, 5: 3, 6: 3, 7: 3, 8: 3, 9: 4, 10: 4, 11: 4, 12: 4, 13: 5, 14: 5, 15: 5, 16: 5,
           17: 6, 18: 6, 19: 6, 20: 6, 21: 7, 22: 7, 23: 7, 24: 7, 25: 8, 26: 8, 27: 8, 28: 8, 29: 9, 30: 9}


class Library:
    """Every raw monster and template of the 2014 bestiaries, by (name, source)."""

    def __init__(self, bestiary_dir: Path, skip: set[str] = frozenset()):
        self.monsters: dict[tuple[str, str], dict] = {}
        index = json.loads((bestiary_dir / "index.json").read_text())
        for source, filename in index.items():
            if source in skip:
                continue
            for raw in json.loads((bestiary_dir / filename).read_text()).get("monster", []):
                self.monsters[(raw["name"].lower(), raw["source"].lower())] = raw
        templates = bestiary_dir / "template.json"
        self.templates = {(t["name"].lower(), t["source"].lower()): t
                          for t in (json.loads(templates.read_text()).get("monsterTemplate", []) if templates.exists() else [])}
        self.unknown: list[str] = []

    def resolve(self, raw: dict, depth: int = 0) -> dict:
        ref = raw.get("_copy")
        if not ref or depth > 8:
            return raw
        base = self.monsters.get((ref["name"].lower(), ref["source"].lower()))
        if base is None:
            self.unknown.append(f"{raw['name']}: base {ref['name']} ({ref['source']}) not found")
            return raw
        out = copy.deepcopy(self.resolve(base, depth + 1))
        out.pop("_copy", None)
        for key, value in raw.items():
            if key != "_copy":
                out[key] = copy.deepcopy(value)
        for t in ref.get("_templates") or []:
            template = self.templates.get((t["name"].lower(), t["source"].lower()))
            if template is None:
                self.unknown.append(f"{raw['name']}: template {t['name']} not found")
                continue
            apply = template.get("apply") or {}
            for key, value in (apply.get("_root") or {}).items():
                out[key] = copy.deepcopy(value)
            self._mods(out, apply.get("_mod") or {}, raw["name"])
        self._mods(out, ref.get("_mod") or {}, raw["name"])
        return _fill_placeholders(out)

    def _mods(self, monster: dict, mods: dict, who: str) -> None:
        for field, ops in mods.items():
            for op in ops if isinstance(ops, list) else [ops]:
                if op == "remove":
                    monster.pop(field, None)
                    continue
                mode = op.get("mode")
                if mode == "replaceTxt":
                    fields = TEXT_FIELDS if field == "*" else [field]
                    pattern = re.compile(op["replace"], re.I if "i" in (op.get("flags") or "") else 0)
                    for f in fields:
                        if f in monster:
                            monster[f] = _replace_text(monster[f], pattern, op.get("with", ""))
                elif mode == "setProp":
                    _set_path(monster, op["prop"], copy.deepcopy(op.get("value")))
                elif mode in ("appendArr", "prependArr", "insertArr"):
                    items = op["items"] if isinstance(op["items"], list) else [op["items"]]
                    arr = monster.setdefault(field, [])
                    if mode == "appendArr":
                        arr.extend(copy.deepcopy(items))
                    elif mode == "prependArr":
                        arr[:0] = copy.deepcopy(items)
                    else:
                        arr[op.get("index", 0):op.get("index", 0)] = copy.deepcopy(items)
                elif mode == "appendIfNotExistsArr":
                    items = op["items"] if isinstance(op["items"], list) else [op["items"]]
                    arr = monster.setdefault(field, [])
                    arr.extend(copy.deepcopy(i) for i in items if i not in arr)
                elif mode == "addSenses":
                    senses = op.get("senses") or []
                    current = monster.setdefault("senses", [])
                    for sense in senses if isinstance(senses, list) else [senses]:
                        text = f"{sense['type']} {sense['range']} ft."
                        if not any(str(c).startswith(sense["type"]) for c in current):
                            current.append(text)
                elif mode == "replaceArr":
                    items = op["items"] if isinstance(op["items"], list) else [op["items"]]
                    arr = monster.get(field, [])
                    target = op["replace"]
                    at = next((i for i, e in enumerate(arr) if _entry_name(e) == (target if isinstance(target, str) else None)
                               or (isinstance(target, dict) and target.get("index") == i)), None)
                    if at is None:
                        self.unknown.append(f"{who}: replaceArr {field} has no {target}")
                    else:
                        arr[at:at + 1] = copy.deepcopy(items)
                elif mode == "removeArr":
                    names = op.get("names") or op.get("items") or []
                    names = names if isinstance(names, list) else [names]
                    monster[field] = [e for e in monster.get(field, []) if _entry_name(e) not in names and e not in names]
                else:
                    self.unknown.append(f"{who}: change mode {mode} on {field} not supported")


def _entry_name(entry: Any) -> str | None:
    return entry.get("name") if isinstance(entry, dict) else entry if isinstance(entry, str) else None


def _replace_text(value: Any, pattern: re.Pattern, replacement: str) -> Any:
    if isinstance(value, str):
        return pattern.sub(replacement, value)
    if isinstance(value, list):
        return [_replace_text(v, pattern, replacement) for v in value]
    if isinstance(value, dict):
        return {k: (v if k in ("name", "type") else _replace_text(v, pattern, replacement)) for k, v in value.items()}
    return value


def _set_path(obj: dict, path: str, value: Any) -> None:
    keys = path.split(".")
    for key in keys[:-1]:
        obj = obj.setdefault(key, {})
    if value is None:
        obj.pop(keys[-1], None)
    else:
        obj[keys[-1]] = value


def _fill_placeholders(monster: dict) -> dict:
    """<$name$>, <$short_name$>, <$spell_dc__cha$>, <$to_hit__str$>, <$damage_mod__dex$> as 5etools fills them."""
    cr = monster.get("cr")
    cr = cr.get("cr") if isinstance(cr, dict) else cr
    try:
        cr_num = math.floor(eval(str(cr), {"__builtins__": {}})) if cr not in (None, "Unknown", "—") else 0  # "1/4" -> 0
    except Exception:  # noqa: BLE001 - odd CR text: no proficiency bump
        cr_num = 0
    prof = CR_PROF.get(cr_num, 2)
    mod = lambda ability: (int(monster.get(ability, 10)) - 10) // 2
    name = monster.get("name", "")
    short = (monster.get("shortName") if isinstance(monster.get("shortName"), str) else None) or name.lower()

    def fill(match: re.Match) -> str:
        key = match.group(1)
        if key == "name":
            return name
        if key == "short_name":
            return short
        if key == "title_short_name":
            return short.title()
        kind, _, ability = key.partition("__")
        if ability in ("str", "dex", "con", "int", "wis", "cha"):
            return {"spell_dc": str(8 + prof + mod(ability)), "to_hit": f"{prof + mod(ability):+d}",
                    "damage_mod": f"{mod(ability):+d}".replace("+0", "")}.get(kind, match.group(0))
        return match.group(0)

    return json.loads(re.sub(r"<\$(\w+)\$>", lambda m: fill(m).replace('"', '\\"'), json.dumps(monster)))
