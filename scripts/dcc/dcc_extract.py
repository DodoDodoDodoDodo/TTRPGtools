"""DCC core content extractor (docs/DESIGN.md section 5.3).

    python scripts/dcc/dcc_extract.py <DCC_Ref_Book.pdf> <DCC_core_rulebook.pdf> [out.json]

Tables come from the Reference Booklet (clean single-column layout), spell
entries and class prose from the core rulebook. Writes
content/dcc/private/core.json (gitignored) and prints counts against the known
totals. Arguments ending in .txt are treated as cached pdftotext dumps:
booklet dump, core `-layout` dump, core reading-order dump (three .txt args).

Seed for the real `build-pack --system dcc` converter; not wired into the
package yet.
"""
import json, re, subprocess, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEFAULT_OUT = REPO / "content" / "dcc" / "private" / "core.json"

DASH = ("-", "–", "—")


def pdftotext(pdf, layout):
    cmd = ["pdftotext"] + (["-layout"] if layout else []) + [str(pdf), "-"]
    out = subprocess.run(cmd, check=True, capture_output=True).stdout
    return out.decode("utf-8", errors="ignore").splitlines()


def load_inputs(args):
    if len(args) >= 3 and all(a.endswith(".txt") for a in args[:3]):
        rd = lambda a: Path(a).read_text(encoding="utf-8", errors="ignore").splitlines()
        return rd(args[0]), rd(args[1]), rd(args[2])
    if len(args) >= 2:
        return pdftotext(args[0], True), pdftotext(args[1], True), pdftotext(args[1], False)
    sys.exit(__doc__)


def find(lines, pattern, start=0, flags=0):
    rx = re.compile(pattern, flags)
    for i in range(start, len(lines)):
        if rx.search(lines[i]):
            return i
    raise KeyError(pattern)


SMALL_WORDS = {"of", "the", "and", "from", "to", "a", "in", "on", "or", "for"}


def smallcaps(s):
    """pdftotext renders the small-caps display font as e.g. 'Magic MiSSile' or
    'aniMal SuMMoning': capitals are unreliable, so title-case every word."""
    words = []
    for n, w in enumerate(s.strip().split()):
        low = w.lower()
        words.append(low if n and low.strip(",") in SMALL_WORDS else low[0].upper() + low[1:])
    return " ".join(words)


# ---------------------------------------------------------------- generic tables
ROLL = re.compile(r"^\s*(\d+(?:-\d+)?\+?|00)\s{2,}(\S.*?)\s*$|^\s*(\d+ or (?:less|lower|more)|\d+-\d+\+?)\s+(\S.*?)\s*$")
SPLIT_ROLL = re.compile(r"^\s*(\d+) or\s{2,}(\S.*?)\s*$")
HEADING = re.compile(r"^\s*(TABLE \d-\d+:|CRIT TABLE|[A-Z][A-Z &,'\-]{8,}$)")


def roll_table(lines, start_pat, max_rows=200, stop_pat=None):
    """Rows of 'roll  text' with indented continuation lines, from the line
    after `start_pat` to the next heading or `stop_pat`."""
    i = find(lines, start_pat)
    out, cur = [], None
    block = list(lines[i + 1 : i + 400])
    for n, line in enumerate(block):
        s = line.rstrip()
        sm = SPLIT_ROLL.match(s)
        if sm and n + 1 < len(block) and re.match(r"^\s*(less|lower|more)\s+", block[n + 1]):
            s = f"{sm.group(1)} or {block[n + 1].split()[0]}  {sm.group(2)}"
            block[n + 1] = re.sub(r"^\s*(less|lower|more)\s+", " " * 8, block[n + 1])
        if not s.strip():
            continue
        if re.match(r"^\s*\d+\s*$", s) and out:  # page number
            continue
        if out and (re.search(start_pat, s) or re.search(r"\(?continued\)?\s*$", s, re.IGNORECASE) and HEADING.match(s)):
            continue  # same table continues on the next page
        if (stop_pat and re.search(stop_pat, s)) or (out and HEADING.match(s) and not ROLL.match(s)):
            break
        m = ROLL.match(s)
        if m and (cur is None or len(s) - len(s.lstrip()) <= 6):
            cur = {"roll": m.group(1) or m.group(3), "text": m.group(2) or m.group(4)}
            out.append(cur)
            if len(out) >= max_rows:
                break
        elif cur is not None and not re.match(r"^\s*(Roll|d\d+|d%)\s", s):
            cur["text"] += " " + s.strip()
    for r in out:
        r["text"] = re.sub(r"\s+", " ", r["text"]).strip()
    return out


# ---------------------------------------------------------------- booklet tables
def parse_occupations(REF):
    out = []
    i = find(REF, r"TABLE 1-3: OCCUPATION")
    rx = re.compile(r"^\s*(\d{2,3})(?:-(\d{2,3}))?\s+(\S.*?)\s{2,}(.+?)\s*$")
    while i < len(REF) and (not out or out[-1]["roll"][1] < 100):
        m = rx.match(REF[i]); i += 1
        if not m:
            continue
        lo, hi, occ, items = m.groups()
        lo = int(lo); hi = int(hi) if hi else lo
        lo = 100 if lo == 0 else lo; hi = 100 if hi == 0 else hi
        if out and lo <= out[-1]["roll"][1]:
            break
        parts = [p.strip() for p in items.split(",")]
        out.append({"roll": [lo, hi], "occupation": occ.rstrip("*").strip(), "weapon": parts[0],
                    "trade_goods": ", ".join(parts[1:]), "notes": "*" * (len(occ) - len(occ.rstrip("*")))})
    return out


def parse_ability_mods(REF):
    i = find(REF, r"TABLE 1-1: ABILITY SCORE MODIFIERS")
    out = {}
    for line in REF[i + 1 : i + 25]:
        m = re.match(r"^\s*(\d+)\s+([+-]?\d|None|[–-])\s+(.+?)\s{2,}(.+?)\s*$", line)
        if m:
            score, mod, known, maxlvl = m.groups()
            out[int(score)] = {"mod": 0 if mod in ("None",) + DASH else int(mod),
                               "wizard_spells_known": known.strip(), "max_spell_level": maxlvl.strip()}
    return out


def parse_luck(REF):
    i = find(REF, r"TABLE 1-2: LUCK SCORE")
    out = []
    for line in REF[i + 1 : i + 40]:
        m = re.match(r"^\s*(\d+)\s{2,}(.+?)\s{2,}(.+?)\s*$", line)
        if m:
            out.append({"roll": int(m.group(1)), "augur": m.group(2).strip(), "applies_to": m.group(3).strip()})
    return out


def parse_xp(REF):
    i = find(REF, r"TABLE 1-4: XP LEVEL")
    out = {}
    for line in REF[i + 1 : i + 20]:
        m = re.match(r"^\s*(\d{1,2})\s{2,}(\d+)", line)
        if m:
            out[int(m.group(1))] = int(m.group(2))
    return out


CLASS_TABLES = {"cleric": r"TABLE 1-5: CLERIC", "thief": r"TABLE 1-7: THIEF", "warrior": r"TABLE 1-10: WARRIOR",
                "wizard": r"TABLE 1-12: WIZARD", "dwarf": r"TABLE 1-14: DWARF", "elf": r"TABLE 1-16: ELF",
                "halfling": r"TABLE 1-18: HALFLING"}
CLASS_COLUMNS = {
    "cleric": ["attack", "crit", "action_dice", "ref", "fort", "will", "spells_l1", "spells_l2", "spells_l3", "spells_l4", "spells_l5"],
    "thief": ["attack", "crit", "action_dice", "luck_die", "ref", "fort", "will"],
    "warrior": ["attack", "crit", "threat_range", "action_dice", "ref", "fort", "will"],
    "wizard": ["attack", "crit", "action_dice", "spells_known", "max_spell_level", "ref", "fort", "will"],
    "dwarf": ["attack", "crit", "action_dice", "ref", "fort", "will"],
    "elf": ["attack", "crit", "action_dice", "spells_known", "max_spell_level", "ref", "fort", "will"],
    "halfling": ["attack", "crit", "action_dice", "ref", "fort", "will", "sneak_hide"],
}


def parse_class_tables(REF):
    out, problems = {}, []
    for name, pat in CLASS_TABLES.items():
        i = find(REF, pat)
        levels = {}
        for line in REF[i + 1 : i + 40]:
            m = re.match(r"^\s*(\d{1,2})\s{2,}(.+?)\s*$", line)
            if not m:
                continue
            lvl = int(m.group(1))
            if not 1 <= lvl <= 10 or lvl in levels:
                continue
            cells = [c for c in re.split(r"\s{2,}", m.group(2).strip()) if c]
            cols = CLASS_COLUMNS[name]
            if len(cells) != len(cols):
                problems.append(f"{name} L{lvl}: {cells}")
                continue
            row = dict(zip(cols, cells))
            row["crit_die"], row["crit_table"] = row.pop("crit").split("/")
            row["attack"] = row["attack"].rstrip("*")
            levels[lvl] = row
        out[name] = levels
    return out, problems


def parse_thief_skills(REF):
    i = find(REF, r"TABLE 1-9: THIEF SKILLS")
    out, align = {}, None
    for line in REF[i + 1 : i + 60]:
        m = re.search(r"Bonus for (\w+) Thieves", line)
        if m:
            align = m.group(1).lower(); out[align] = {}; continue
        m = re.match(r"^\s*([A-Za-z /]+?)[*†‡]*\s{2,}(.+?)\s*$", line)
        if m and align and not line.strip().startswith(("Skill", "Level")):
            vals = re.split(r"\s+", m.group(2).strip())
            if len(vals) == 10:
                out[align][m.group(1).strip()] = vals
    return out


def parse_titles(CORE):
    """Table 1-6 etc.: class titles by level and alignment (core rulebook only).
    The alignment column order differs per class (wizard: Chaotic, Lawful,
    Neutral), so it is read from each table's own header line."""
    heads = (("lawful", r"\bLaw"), ("chaotic", r"\bChao"), ("neutral", r"\bNeutral"))
    out = {}
    for name in CLASS_TABLES:
        try:
            i = find(CORE, rf"Table 1-\d+: {name} TiTleS", flags=re.IGNORECASE)
        except KeyError:
            continue
        rows, order = {}, None
        for line in CORE[i + 1 : i + 12]:
            found = sorted((m.start(), key) for key, pat in heads for m in [re.search(pat, line)] if m)
            if len(found) == 3 and not re.match(r"^\s*\d", line):
                order = [key for _, key in found]
                continue
            m = re.match(r"^\s*(\d)\s{2,}(\S.*?)\s{2,}(\S.*?)\s{2,}(\S.*?)\s*$", line)
            m1 = re.match(r"^\s*(\d)\s{2,}(\S.*?)\s*$", line)
            if m and order:
                rows[int(m.group(1))] = dict(zip(order, m.groups()[1:]))
            elif m1:
                rows[int(m1.group(1))] = {"all": m1.group(2)}
        out[name] = rows
    return out


def parse_weapons(REF):
    i = find(REF, r"TABLE 3-1: WEAPONS")
    out = []
    for line in REF[i + 1 : i + 40]:
        m = re.match(r"^\s*([A-Z][A-Za-z\- ]+?)([*†‡#]*)\s{2,}(\S+)\s{2,}(\S+)\s{2,}(.+?)\s*$", line)
        if m and m.group(1).strip() != "Weapon":
            name, marks, dmg, rng, cost = m.groups()
            out.append({"name": name.strip(), "damage": dmg, "range": None if rng in DASH else rng.rstrip("*"),
                        "strength_at_close_range_only": rng.endswith("**"), "cost": cost,
                        "two_handed": "*" in marks, "backstab_weapon": "†" in marks, "mounted_charge": "#" in marks})
    return out


def parse_armor(REF):
    i = find(REF, r"TABLE 3-3: ARMOR")
    out = []
    for line in REF[i + 1 : i + 20]:
        m = re.match(r"^\s*(\(?[A-Za-z\- ]+\)?)\*?\s{2,}([+-]\d)\s{2,}(\S+)\s{2,}(\S+)\s{2,}(d\d+|[–-])\s{2,}(.+?)\s*$", line)
        if m:
            name, ac, check, speed, fumble, cost = m.groups()
            out.append({"name": name.strip("() "), "ac": int(ac), "check_penalty": 0 if check in DASH else int(check),
                        "speed_penalty": 0 if speed in DASH else int(re.sub(r"[^\d-]", "", speed)),
                        "fumble_die": None if fumble in DASH else fumble, "cost": cost})
    for row in out:  # the booklet prints a dash here; the core rulebook (p. 72 and p. 478) prints d8
        if row["name"] == "Shield" and not row["fumble_die"]:
            row["fumble_die"] = "d8"
    return out


def parse_equipment(REF):
    i = find(REF, r"TABLE 3-4: EQUIPMENT")
    out = []
    for line in REF[i + 1 : i + 30]:
        m = re.match(r"^\s*(\d+)\s{2,}(.+?)\s{2,}(\S+ [cgs]p)\s*$", line)
        if m:
            out.append({"roll": int(m.group(1)), "item": m.group(2).rstrip("*").strip(), "cost": m.group(3)})
    return out


def parse_attack_modifiers(REF):
    i = find(REF, r"TABLE 4-1: ATTACK ROLL MODIFIERS")
    out, group = [], None
    for line in REF[i + 1 : i + 30]:
        s = line.rstrip()
        if not s.strip() or s.strip().startswith("*"):
            if out and not s.strip():
                continue
            if s.strip().startswith("*"):
                break
        if s.strip().endswith("…"):
            group = s.strip().rstrip("…").strip(); continue
        m = re.match(r"^\s+(\S.*?)\s{2,}([+-]?\d*d?|-)\s+([+-]?\d*d?|-)\s*$", s)
        if m and group:
            cond, melee, missile = m.groups()
            out.append({"group": group, "condition": cond.rstrip("*"), "melee": None if melee == "-" else melee,
                        "missile": None if missile == "-" else missile})
    return out


def parse_ammunition(REF):
    i = find(REF, r"TABLE 3-2: AMMUNITION")
    out = []
    for line in REF[i + 1 : i + 10]:
        m = re.match(r"^\s*([A-Z][A-Za-z ,\-]+?)\s{2,}(\d+)\s{2,}(\d+)\s*$", line)
        if m:
            out.append({"name": m.group(1).strip(), "quantity": int(m.group(2)), "cost": f"{m.group(3)} gp"})
    return out


def parse_mounts(REF):
    i = find(REF, r"TABLE 3-5: MOUNTS")
    out = []
    for line in REF[i + 1 : i + 16]:
        m = re.match(r"^\s*([A-Z][A-Za-z ,()\-]+?)\s{2,}(\S+(?: lbs?\.)?|-|x\d\*)\s{2,}(\d+ [cgs]p|x\d\*)\s*$", line)
        if m:
            out.append({"name": m.group(1).strip(), "weight": None if m.group(2) in ("-",) else m.group(2), "cost": m.group(3)})
    return out


def parse_two_weapon(REF):
    i = find(REF, r"TABLE 4-3: TWO-WEAPON ATTACKS")
    out, cur = [], None
    for line in REF[i + 1 : i + 20]:
        st = line.strip()
        if st.startswith("*"):
            break
        m = re.match(r"^\s*(\d+(?:-\d+)?\+?)\s{2,}(\S+(?: \S+)?)\s{2,}(\S+(?: \S+)?)\s{2,}(.+?)\s*$", line)
        if m:
            lo, hi = (m.group(1).rstrip("+").split("-") + [None])[:2]
            cur = {"agility": [int(lo), int(hi) if hi else 24], "primary": m.group(2), "off_hand": m.group(3), "crits": m.group(4)}
            out.append(cur)
        elif cur and st and st != "die":
            cur["crits"] += " " + st
        elif cur and st == "die":
            cur["primary"] += " die"
    return out


def parse_turn_unholy(REF):
    i = find(REF, r"TABLE 4-4: TURN UNHOLY")
    out = []
    hd = ["1", "2", "3-4", "5-6", "7-8", "9-10", "11-12"]
    for line in REF[i + 1 : i + 60]:
        m = re.match(r"^\s*(\d+(?:-\d+)?\+?)\s+(\S+)\s+(\S+(?: \S+)?)\s+(.+?)\s*$", line)
        if m and (m.group(2).endswith("'") or m.group(2) in DASH):
            cells = re.split(r"\s+", m.group(4).strip())
            if len(cells) >= 7 and m.group(1) not in [r["check"] for r in out]:
                out.append({"check": m.group(1), "range": m.group(2), "holy_smite": m.group(3),
                            "by_hd": dict(zip(hd, cells[:7]))})
        if line.strip().startswith("NE = "):
            break
    return out


def parse_lay_on_hands(REF):
    i = find(REF, r"^\s*LAY ON HANDS\s*$")
    out = []
    for line in REF[i + 1 : i + 12]:
        m = re.match(r"^\s*(\d+(?:-\d+)?\+?)\s{2,}(\S+(?: \S+)?)\s{2,}(\S+(?: \S+)?)\s{2,}(\S+(?: \S+)?)", line)
        if m:
            out.append({"check": m.group(1), "same_alignment": m.group(2), "adjacent": m.group(3), "opposed": m.group(4)})
    return out


CRIT_TABLES = {"I": r"CRIT TABLE I:", "II": r"CRIT TABLE II:", "III": r"CRIT TABLE III:",
               "IV": r"CRIT TABLE IV:", "V": r"CRIT TABLE V:"}
DEEDS = ["BLINDING ATTACKS", "DISARMING ATTACKS", "PUSHBACK ATTACKS", "TRIPS AND THROWS",
         "RALLYING MANEUVERS", "DEFENSIVE MANEUVERS", "PRECISION SHOTS"]


# ---------------------------------------------------------------- core rulebook
HEADER_START = re.compile(r"^Level:\s*(\d)(?:\s*\(([^)]+)\))?\s+Range:")
HEADER = re.compile(r"Level:\s*(\d)(?:\s*\(([^)]+)\))?\s+Range:\s*(.+?)\s+Duration:\s*(.+?)\s+Casting [Tt]ime:\s*(.+?)(?:\s+Save:\s*(.+))?$")
SECTION = re.compile(r"^\s*LEVEL \d (WIZARD|CLERIC) SPELLS\s*$")


def parse_spells(CORE):
    spells = []
    idx = [i for i, l in enumerate(CORE) if HEADER_START.match(l)]
    for n, i in enumerate(idx):
        end = idx[n + 1] - 1 if n + 1 < len(idx) else min(len(CORE), i + 400)
        name = smallcaps(CORE[i - 1])
        head, j = CORE[i].strip(), 0
        while j < 3 and (not re.search(r"Casting [Tt]ime:", head)
                         or (not re.search(r"Save:", head) and CORE[i + 1 + j].strip().startswith("Save:"))):
            head += " " + CORE[i + 1 + j].strip(); j += 1
        m = HEADER.search(re.sub(r"\s+", " ", head))
        if not m:
            print("  unparsed spell header:", name); continue
        patron = m.group(2)
        klass = "patron" if patron else next(
            (SECTION.match(CORE[k]).group(1).lower() for k in range(i, 0, -1) if SECTION.match(CORE[k])), "unknown")
        sp = {"name": name, "class": klass, "patron": patron, "level": int(m.group(1)), "range": m.group(3),
              "duration": m.group(4), "casting_time": m.group(5), "save": m.group(6), "general": "",
              "manifestation": "", "corruption": "", "misfire": "", "results": []}
        field = None
        for line in CORE[i + 1 + j : end]:
            s = line.strip()
            if not s or re.match(r"^Page \d+$", s) or s.endswith("(continued)"):
                continue
            m2 = re.match(r"^(General|Manifestation|Corruption|Misfire)\s{2,}(.*)$", s)
            if m2:
                field = m2.group(1).lower(); sp[field] = m2.group(2); continue
            m3 = re.match(r"^(\d+(?:-\d+)?\+?)\s{2,}(.*)$", s)
            if m3 and (field or sp["results"]):
                field = "results"; sp["results"].append({"band": m3.group(1), "text": m3.group(2)}); continue
            if field == "results" and sp["results"]:
                sp["results"][-1]["text"] += " " + s
            elif field:
                sp[field] += " " + s
        spells.append(sp)
    return spells


CLASS_START = {"cleric": r"^Hit points: A cleric gains", "thief": r"^Hit points: A thief gains",
               "warrior": r"^Hit points: A warrior gains", "wizard": r"^Hit points: A wizard gains",
               "dwarf": r"^Hit points: A dwarf gains", "elf": r"^Hit points: An elf gains",
               "halfling": r"^Hit points: A halfling gains"}
FIELD = re.compile(r"^([A-Z][A-Za-z’'\- ]{2,30}):\s+(\S.*)$")


def parse_class_prose(RAW):
    """'Field: text' paragraphs per class from the reading-order dump. Each class
    runs from its 'Hit points:' line to its 'Action dice:' paragraph."""
    out = {}
    for name, pat in CLASS_START.items():
        i = find(RAW, pat)
        # class description: the paragraph(s) before the field block, back to the previous blank-separated heading
        fields, cur = {}, None
        k = i
        while k < len(RAW):
            s = RAW[k].strip()
            k += 1
            if s == "\f" or not s:
                if cur == "Action dice" and fields.get(cur):
                    break
                continue
            m = FIELD.match(s)
            if m and len(m.group(1).split()) <= 3:
                cur = m.group(1).strip(); fields[cur] = m.group(2).strip()
            elif cur:
                fields[cur] += " " + s
            if cur == "Action dice" and k - i > 400:
                break
        out[name] = {k2: re.sub(r"\s+", " ", v) for k2, v in fields.items()}
    return out


MONSTER_LINE = re.compile(
    r"([A-Z][A-Za-z’' ,\-\(\)0-9]{2,60}?): Init ([+-]?\d+)[^;]*; Atk (.+?); AC (\d+)[^;]*; HD ([^;]+); (?:hp [^;]+; )?MV ([^;]+); "
    r"Act ([^;]+); (?:SP (.+?); )?SV ([^;]+?); AL ([LNC](?:[^.]{0,25})?)\.")
#: Names the heading debris cannot be stripped from by rule.
MONSTER_NAMES = {"W one Hollow man": "Hollow man", "Result 1 Elemental, Earth": "Elemental, Earth",
                 "Stamina loss (temporary) cycloPS Cyclops": "Cyclops",
                 "MonS of bobugbubilz Devil frog (type I demon, Bobugbubilz)": "Devil frog (type I demon, Bobugbubilz)"}


def _monster_name(raw):
    """The stat line follows a small-caps heading that pdftotext glues in front as debris ('Tle, gianT Beetle, giant')."""
    if raw in MONSTER_NAMES:
        return MONSTER_NAMES[raw]
    tokens = re.sub(r"^Page \d+ ", "", raw).split()
    debris = [n for n, tok in enumerate(tokens) if re.search(r"[a-z][A-Z]|[A-Z]{2}", tok.split("(")[0])]
    in_parens = raw.find("(")
    if debris and (in_parens < 0 or len(" ".join(tokens[:debris[-1] + 1])) < in_parens):
        tokens = tokens[debris[-1] + 1:]
    for cut in range(len(tokens) - 1, 0, -1):  # 'Taur Centaur', 'Pe-Man Jungle ape-man': the tail of the heading repeats the name's end
        head, rest = " ".join(tokens[:cut]).lower(), " ".join(tokens[cut:]).lower()
        first = re.split(r"[ ,]", rest)[0]
        if tokens[cut][0].isupper() and (rest.endswith(head) or first.endswith(head) or rest.split(" (")[0].endswith(head)):
            tokens = tokens[cut:]
            break
    return " ".join(tokens)


def parse_monsters(RAW):
    """Monster stat lines of the core rulebook: name, Init, Atk, AC, HD, MV, Act, SP, SV, AL, and the printed page."""
    out, seen = [], set()
    # the dump has lost its page breaks; the printed "Page N" footers split it well enough to cite a page
    chunks = re.split(r"\n(Page \d+)\n", "\n".join(RAW))
    for n in range(0, len(chunks) - 1, 2):
        page = int(chunks[n + 1].split()[1])
        flat = re.sub(r"\s*\n\s*", " ", re.sub(r"-\n", "", chunks[n]))
        for hit in MONSTER_LINE.findall(flat):
            name = _monster_name(hit[0].strip())
            if name in seen:
                continue
            seen.add(name)
            out.append({"name": name, "init": hit[1], "attack": hit[2], "ac": int(hit[3]), "hd": hit[4], "move": hit[5], "act": hit[6],
                        "special": hit[7], "saves": hit[8], "alignment": hit[9].strip(), "page": page})
    return out


LANGUAGE_COLUMNS = ["zero", "warrior", "cleric", "thief", "wizard", "halfling", "elf", "dwarf"]


def parse_languages(CORE):
    """Appendix L: d% range per class for each language (None where the class cannot roll it)."""
    i = find(CORE, r"% Chance to Know Language, by Class")
    cell = r"(\d+(?:-\d+)?|[–-])"
    rx = re.compile(r"^\s*(\S.*?)\*{0,2}\s{2,}" + r"\s+".join([cell] * 8) + r"\s*$")
    out = []
    for line in CORE[i + 1 : i + 60]:
        if line.strip().startswith("†"):
            break
        m = rx.match(line)
        if not m:
            continue
        ranges = {}
        for col, tok in zip(LANGUAGE_COLUMNS, m.groups()[1:]):
            lo, _, hi = tok.partition("-")
            ranges[col] = None if tok in DASH else [int(lo), int(hi or lo)]
        out.append({"language": m.group(1).split(" (")[0].strip(), "ranges": ranges})
    return out


#: Gods of the Eternal Struggle (core rulebook p. 32): a cleric's god must match
#: the cleric's alignment, and the alignment fixes the weapon training.
DEITIES = {
    "lawful": {"weapons": ["Club", "Mace", "Sling", "Staff", "Warhammer"], "weapons_text": "club, mace, sling, staff, warhammer",
               "gods": ["Shul, god of the moon", "Klazath, god of war", "Ulesh, god of peace",
                        "Choranus, the Seer Father, lord of creation",
                        "Daenthar, the Mountain Lord, greater god of earth and industry",
                        "Gorhan, the Helmed Vengeance, god of valor and chivalry",
                        "Justicia, goddess of justice and mercy",
                        "Aristemis, the Insightful One, demigoddess of true seeing and strategy"],
               "unholy": "Un-dead, demons, devils, chaotic extraplanar creatures, monsters (e.g., basilisk or medusa), "
                         "Chaos Primes, chaotic humanoids (e.g., orcs), chaotic dragons"},
    "neutral": {"weapons": ["Dagger", "Mace", "Sling", "Staff", "Longsword", "Short sword", "Two-handed sword"],
                "weapons_text": "dagger, mace, sling, staff, sword (any)",
                "gods": ["Amun Tor, god of mysteries and riddles", "Ildavir, goddess of nature", "Pelagia, goddess of the sea",
                         "Cthulhu, priest of the Old Ones"],
                "unholy": "Mundane animals, un-dead, demons, devils, monsters (e.g., basilisk or medusa), lycanthropes, "
                          "perversions of nature (e.g., otyughs and slimes)"},
    "chaotic": {"weapons": ["Battleaxe", "Handaxe", "Longbow", "Shortbow", "Crossbow", "Dagger", "Dart", "Flail"],
                "weapons_text": "axe (any), bow (any), dagger, dart, flail",
                "gods": ["Ahriman, god of death and disease", "Hidden Lord, god of secrets",
                         "Azi Dahaka, demon prince of storms and waste", "Bobugbubilz, demon lord of evil amphibians",
                         "Cadixtat, chaos titan", "Nimlurun, the unclean one, lord of filth and pollution",
                         "Malotoch, the carrion crow god"],
                "unholy": "Angels, paladins, lawful dragons, Lords of Law, Lawful Primes, and Law-aligned humanoids (e.g., goblins)"},
}

#: Starting gold in gp when a campaign begins above level 0 (core rulebook p. 70).
STARTING_GOLD = {
    "warrior": ["5d12", "5d12+500", "5d12+1500"], "wizard": ["3d10", "3d10+(2d4x100)", "3d10+(5d4x100)"],
    "cleric": ["4d20", "4d20+400", "4d20+1300"], "thief": ["3d10", "3d10+(1d6x100)", "3d10+(3d6x100)"],
    "elf": ["3d12", "3d12+500", "3d12+2000"], "halfling": ["3d20", "3d20+250", "3d20+1500"],
    "dwarf": ["5d12", "5d12+700", "5d12+2000"],
}

ZERO_LEVEL_RULES = {
    "abilities": "3d6 in order for Strength, Agility, Stamina, Personality, Intelligence, Luck",
    "hit_points": "1d4 (Stamina modifier applies, minimum 1)",
    "starting_funds": "5d12 cp",
    "occupation": "d100 on table 1-3; grants the listed starting weapon and trade goods, and the demi-human occupations fix the race",
    "birth_augur": "d30 on table 1-2; the Luck modifier at creation applies to that roll for the rest of the character's life",
    "equipment": "one d24 roll on table 3-4",
    "alignment": "player's choice of Lawful, Neutral, Chaotic",
    "languages": "Common plus one per point of Intelligence modifier (Appendix L); dwarves, elves, halflings know their racial tongue",
    "attack_and_saves": "+0 attack, +0 to all saves before ability modifiers, 1d20 action die, crit 1d4 on table I",
    "speed": "30 feet; 20 feet for dwarves and halflings",
}


def main():
    args = sys.argv[1:]
    out_path = Path(args[3]) if len(args) > 3 and args[3].endswith(".json") else (
        Path(args[2]) if len(args) > 2 and args[2].endswith(".json") else DEFAULT_OUT)
    REF, CORE, RAW = load_inputs(args)
    classes, problems = parse_class_tables(REF)
    data = {
        "source": {"tables": "DCC RPG Reference Booklet v1.09", "spells_and_prose": "DCC RPG core rulebook, 10th printing"},
        "zero_level_rules": ZERO_LEVEL_RULES,
        "occupations": parse_occupations(REF),
        "ability_mods": parse_ability_mods(REF),
        "luck_augurs": parse_luck(REF),
        "xp_thresholds": parse_xp(REF),
        "classes": classes,
        "class_titles": parse_titles(CORE),
        "class_prose": parse_class_prose(RAW),
        "thief_skills": parse_thief_skills(REF),
        "weapons": parse_weapons(REF),
        "armor": parse_armor(REF),
        "equipment": parse_equipment(REF),
        "attack_modifiers": parse_attack_modifiers(REF),
        "fumbles": roll_table(REF, r"TABLE 4-2: FUMBLES"),
        "crit_tables": {k: roll_table(REF, v) for k, v in CRIT_TABLES.items()},
        "mighty_deeds": {d.title(): roll_table(REF, rf"^\s*{d}\s*$") for d in DEEDS},
        "turn_unholy": parse_turn_unholy(REF),
        "two_weapon": parse_two_weapon(REF),
        "ammunition": parse_ammunition(REF),
        "mounts": parse_mounts(REF),
        "lay_on_hands": parse_lay_on_hands(REF),
        "spellburn": roll_table(REF, r"TABLE 5-1: SPELLBURN"),
        "mercurial_magic": roll_table(REF, r"TABLE 5-2: MERCURIAL MAGIC"),
        "corruption": {"minor": roll_table(REF, r"TABLE 5-3: MINOR CORRUPTION"),
                       "major": roll_table(REF, r"TABLE 5-4: MAJOR CORRUPTION"),
                       "greater": roll_table(REF, r"TABLE 5-5: GREATER CORRUPTION")},
        "generic_misfire": roll_table(REF, r"TABLE 5-6: GENERIC SPELL MISFIRE"),
        "disapproval": roll_table(REF, r"TABLE 5-7: DISAPPROVAL"),
        "spells": parse_spells(CORE),
        "languages": parse_languages(CORE),
        "monsters": parse_monsters(RAW),
        "deities": DEITIES,
        "starting_gold": STARTING_GOLD,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, indent=1, ensure_ascii=False))

    d = data
    covered = sum(hi - lo + 1 for lo, hi in (o["roll"] for o in d["occupations"]))
    print(f"occupations {len(d['occupations'])} rows covering {covered}/100 | ability_mods {len(d['ability_mods'])}/16 | "
          f"luck {len(d['luck_augurs'])}/30 | xp {len(d['xp_thresholds'])}/11")
    print("classes:", {k: len(v) for k, v in classes.items()}, "(10 each)", problems or "")
    print("titles:", {k: len(v) for k, v in d["class_titles"].items()}, "(5 each)")
    print("prose fields:", {k: len(v) for k, v in d["class_prose"].items()})
    print("thief skills:", {k: len(v) for k, v in d["thief_skills"].items()}, "(13 each)")
    print(f"weapons {len(d['weapons'])}/23 | armor {len(d['armor'])}/11 | equipment {len(d['equipment'])}/24 | "
          f"attack mods {len(d['attack_modifiers'])}/14 | fumbles {len(d['fumbles'])}/17")
    print("crit tables:", {k: len(v) for k, v in d["crit_tables"].items()})
    print("mighty deeds:", {k: len(v) for k, v in d["mighty_deeds"].items()})
    mercurial_cov = 0
    import re as _re
    for r in d["mercurial_magic"]:
        m = _re.match(r"^(\d+)(?:-(\d+))?", r["roll"]); lo = int(m.group(1)); hi = int(m.group(2) or lo)
        mercurial_cov += (100 if hi == 0 else hi) - (100 if lo == 0 else lo) + 1
    by = {}
    for s in d["spells"]:
        by[s["class"]] = by.get(s["class"], 0) + 1
    print(f"two-weapon rows {len(d['two_weapon'])}/5 | ammunition {len(d['ammunition'])}/4 | mounts {len(d['mounts'])}/11")
    print(f"turn unholy {len(d['turn_unholy'])}/9 | lay on hands {len(d['lay_on_hands'])}/5 | spellburn {len(d['spellburn'])}/24 | "
          f"mercurial {len(d['mercurial_magic'])} rows covering {mercurial_cov}/100 | corruption {[len(v) for v in d['corruption'].values()]} | "
          f"misfire {len(d['generic_misfire'])}/8 | disapproval {len(d['disapproval'])}/20")
    print(f"spells {len(d['spells'])}/130 {by}; spells with <3 result bands: {sum(1 for s in d['spells'] if len(s['results']) < 3)}")
    print(f"monsters {len(d['monsters'])} stat lines")
    print(f"languages {len(d['languages'])}/36 | deities {sum(len(v['gods']) for v in d['deities'].values())}/19")
    print("wrote", out_path)


if __name__ == "__main__":
    main()
