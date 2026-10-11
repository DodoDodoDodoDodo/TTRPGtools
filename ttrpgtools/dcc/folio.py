"""DCC character folio: an 8-page A5 booklet drawn from character data.

Pages: 1 cover, 2 stats, 3 class, 4 crit and fumble tables plus remaining
inventory, 5 campaign (map, home, religion, relations, goals), 6-8 spells for
casters or journal, class tables and reference for the rest. The imposed
variant reorders pages for duplex A4 printing (8|1, 2|7, 6|3, 4|5).
"""

from __future__ import annotations

import io
import re

from reportlab.lib.pagesizes import A4, A5, landscape
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from ttrpgtools import dcc

W, H = A5
M = 20  # margin
INK = (0.1, 0.08, 0.06)
RULE = (0.55, 0.5, 0.42)
FAINT = (0.85, 0.82, 0.76)
FONT, BOLD, ITAL = "Helvetica", "Helvetica-Bold", "Helvetica-Oblique"


class Sheet:
    """Top-left coordinate drawing helpers over a reportlab canvas."""

    def __init__(self, c: canvas.Canvas):
        self.c = c

    def y(self, top: float) -> float:
        return H - top

    def text(self, x, top, s, size=8, font=FONT, align="left", color=INK, max_w=None):
        s = str(s)
        if max_w:
            while size > 4 and stringWidth(s, font, size) > max_w:
                size -= 0.5
        self.c.setFillColorRGB(*color); self.c.setFont(font, size)
        y = self.y(top)
        if align == "center":
            self.c.drawCentredString(x, y, s)
        elif align == "right":
            self.c.drawRightString(x, y, s)
        else:
            self.c.drawString(x, y, s)
        return size

    def rule(self, x1, top1, x2, top2, width=0.5, color=RULE):
        self.c.setStrokeColorRGB(*color); self.c.setLineWidth(width)
        self.c.line(x1, self.y(top1), x2, self.y(top2))

    def box(self, x, top, w, h, label=None, width=0.7, fill=None):
        self.c.setStrokeColorRGB(*RULE); self.c.setLineWidth(width)
        if fill:
            self.c.setFillColorRGB(*fill); self.c.rect(x, self.y(top + h), w, h, stroke=1, fill=1)
        else:
            self.c.rect(x, self.y(top + h), w, h, stroke=1, fill=0)
        if label:
            self.text(x + 3, top + 7, label.upper(), 5, BOLD, color=RULE)

    def heading(self, top, s, x=M, w=W - 2 * M, size=9):
        self.text(x, top, s.upper(), size, BOLD)
        self.rule(x, top + 3, x + w, top + 3, 0.8)
        return top + 10

    def wrap(self, s, w, size, font=FONT):
        lines = []
        for para in str(s).split("\n"):
            cur = ""
            for word in para.split():
                trial = (cur + " " + word).strip()
                if stringWidth(trial, font, size) <= w or not cur:
                    cur = trial
                else:
                    lines.append(cur); cur = word
            lines.append(cur)
        return lines

    def para(self, x, top, w, s, size=7, font=FONT, leading=None, max_lines=None):
        leading = leading or size * 1.25
        lines = self.wrap(s, w, size, font)
        if max_lines:
            lines = lines[:max_lines]
        for n, line in enumerate(lines):
            self.text(x, top + n * leading + size, line, size, font)
        return top + len(lines) * leading

    def lines(self, x, top, w, n, gap=11):
        for i in range(n):
            self.rule(x, top + (i + 1) * gap, x + w, top + (i + 1) * gap, 0.4, FAINT)
        return top + n * gap

    def table(self, x, top, widths, rows, size=6.5, header=None, leading=None, max_top=None):
        """Rows of cells with wrapping; stops before max_top and returns (top, rows_drawn)."""
        leading = leading or size * 1.2
        drawn = 0
        if header:
            for i, hcell in enumerate(header):
                self.text(x + sum(widths[:i]) + 2, top + size, hcell, size, BOLD)
            top += leading + 1
            self.rule(x, top, x + sum(widths), top, 0.4)
            top += 1
        for row in rows:
            cells = [self.wrap(str(cell), widths[i] - 4, size) for i, cell in enumerate(row)]
            height = max(len(c) for c in cells) * leading + 2
            if max_top and top + height > max_top:
                break
            for i, lines in enumerate(cells):
                for n, line in enumerate(lines):
                    self.text(x + sum(widths[:i]) + 2, top + size + n * leading, line, size, BOLD if i == 0 and len(widths) > 1 and len(row[0]) < 12 else FONT)
            top += height
            self.rule(x, top, x + sum(widths), top, 0.3, FAINT)
            drawn += 1
        return top, drawn

    def stat_box(self, x, top, w, h, label, value, sub=None, value_size=16):
        self.box(x, top, w, h, label)
        self.text(x + w / 2, top + h * 0.66, value, value_size, BOLD, "center", max_w=w - 6)
        if sub:
            self.text(x + w / 2, top + h - 4, sub, 5.5, FONT, "center", RULE, max_w=w - 4)

    def footer(self, page, name):
        self.text(W / 2, H - 9, f"{name}  ·  {page}", 6, FONT, "center", RULE)


# ------------------------------------------------------------------ pages
def page_cover(s: Sheet, c, v, campaign):
    s.box(M, M, W - 2 * M, H - 2 * M, width=1.2)
    s.text(W / 2, 70, "DUNGEON CRAWL CLASSICS", 9, BOLD, "center", RULE)
    s.text(W / 2, 110, c["name"], 24, BOLD, "center", max_w=W - 2 * M - 20)
    klass = f"Level {c['level']} {c['class'].capitalize()}" if c.get("class") else "0-level"
    if v["title"]:
        klass += f", {v['title']}"
    s.text(W / 2, 130, klass, 11, FONT, "center")
    s.text(W / 2, 146, f"{c['occupation']['occupation']}  ·  {c['alignment'].capitalize()}" + (f"  ·  {v['race'].capitalize()}" if v["race"] else ""), 9, FONT, "center", RULE)
    s.box(M + 40, 170, W - 2 * M - 80, 250, "portrait")
    s.text(M + 30, 450, "Player", 6, BOLD, color=RULE); s.rule(M + 60, 452, W - M - 30, 452)
    s.text(M + 62, 450, c.get("owner") or "", 8)
    s.text(M + 30, 470, "Campaign", 6, BOLD, color=RULE); s.rule(M + 66, 472, W - M - 30, 472)
    s.text(M + 68, 470, campaign.get("name", ""), 8)
    s.para(M + 30, 490, W - 2 * M - 60, "Birth augur: " + v["augur_effect"], 7.5, ITAL)


def page_stats(s: Sheet, c, v, top0=M):
    s.text(M, top0 + 8, c["name"], 12, BOLD, max_w=W - 2 * M - 120)
    s.text(W - M, top0 + 8, f"Level {c['level']} {(c.get('class') or '0-level').capitalize()}", 8, FONT, "right")
    top = top0 + 16
    # abilities column
    col_w, bh = 74, 38
    for i, a in enumerate(dcc.ABILITIES):
        t = top + i * (bh + 4)
        s.box(M, t, col_w, bh, dcc.ABILITY_LABELS[a].upper())
        s.text(M + 26, t + 26, v["effective"][a], 17, BOLD, "center")
        s.text(M + 58, t + 26, v["mods_text"][a], 11, BOLD, "center")
        if v["ability_damage"][a]:
            s.text(M + col_w - 3, t + bh - 3, f"nat {c['abilities'][a]}", 5, FONT, "right", RULE)
        if a == "luck":
            s.text(M + 26, t + bh - 3, f"start {c['abilities']['luck']}", 5, FONT, "center", RULE)
    # right block
    x = M + col_w + 8; rw = W - M - x
    dice = v["action"]["dice"] + [""] * (2 - len(v["action"]["dice"]))
    s.stat_box(x, top, 46, 34, "action die 1", dice[0], value_size=11)
    s.stat_box(x + 50, top, 46, 34, "action die 2", dice[1], value_size=11)
    s.stat_box(x + 100, top, rw - 100, 34, "hp  current / max", "", f"max {c['hp_max']}")
    s.text(x + 100 + (rw - 100) * 0.72, top + 24, c["hp_max"], 14, BOLD, "center")
    s.rule(x + 100 + (rw - 100) * 0.5, top + 8, x + 100 + (rw - 100) * 0.5, top + 32, 0.4, FAINT)
    t2 = top + 38
    s.stat_box(x, t2, 46, 34, "ac", v["ac"], (c.get("armor") or "no armor") + (" +shield" if c.get("shield") else ""))
    s.stat_box(x + 50, t2, 46, 34, "init", v["initiative"], "d16 if 2h")
    s.stat_box(x + 100, t2, 46, 34, "speed", f"{v['speed']}'", None)
    t3 = t2 + 38
    s.stat_box(x, t3, 46, 34, "ref", v["saves_text"]["reflex"])
    s.stat_box(x + 50, t3, 46, 34, "fort", v["saves_text"]["fortitude"])
    s.stat_box(x + 100, t3, 46, 34, "will", v["saves_text"]["willpower"])
    t4 = t3 + 38
    s.stat_box(x, t4, 70, 34, "crit die / table", f"{v['crit_die']} / {v['crit_table']}", f"threat {v['threat_range'] or '20'}", 10)
    s.stat_box(x + 74, t4, 72, 34, "fumble die", v["fumble_die"], f"attack {v['attack']}", 10)
    # weapons
    t5 = t4 + 42
    t5 = s.heading(t5, "Weapons", x, rw, 7)
    widths = [rw * 0.36, rw * 0.16, rw * 0.2, rw * 0.28]
    wrows = [[w["name"] + (" (untrained)" if not w["trained"] else ""), w["missile_bonus"] if w["range"] else w["melee_bonus"], w["damage"] + (f" / {w['backstab_damage']}" if w["backstab_damage"] else ""), (w["range"] or "melee") + (f", {w['ammo']} {w['ammo_kind'].lower()}" if w["ammo"] is not None else "")] for w in v["weapons"][:2]]
    while len(wrows) < 2:
        wrows.append(["", "", "", ""])
    t5, _ = s.table(x, t5, widths, wrows, 6.5, ["main / secondary", "to hit", "dmg", "range, ammo"])
    # equipment list
    t6 = s.heading(t5 + 8, "Primary equipment", x, rw, 7)
    items = [i for i in v["inventory"] if i["kind"] not in ("weapon",) or not i["equipped"]]
    names = [f"{i['name']}" + (f" x{i['qty']}" if int(i.get("qty", 1)) != 1 else "") + (" (worn)" if i["equipped"] and i["kind"] in ("armor", "shield") else "") for i in items]
    bottom = H - M - 30
    line_h = 10
    n_lines = int((bottom - t6 - 4) // line_h)
    for i in range(n_lines):
        s.rule(x, t6 + (i + 1) * line_h, x + rw, t6 + (i + 1) * line_h, 0.4, FAINT)
        if i < len(names):
            s.text(x + 2, t6 + (i + 1) * line_h - 2, names[i], 6.5, max_w=rw - 4)
    shown = min(len(names), n_lines)
    for j, (k, label) in enumerate([("cp", "CP"), ("sp", "SP"), ("gp", "GP")]):
        bx = x + j * (rw / 3)
        s.box(bx, bottom, rw / 3 - 2, 26, label)
        s.text(bx + rw / 6, bottom + 20, c["coins"][k], 11, BOLD, "center")
    s.text(M, H - M + 2, "Luck: " + v["augur_effect"], 6, ITAL, color=RULE, max_w=W - 2 * M)
    return names[shown:]


def page_class(s: Sheet, c, v, x_extras):
    klass = c.get("class")
    top = s.heading(M + 8, f"{(klass or '0-level').capitalize()}" + (f"  ·  {v['title']}" if v["title"] else ""), size=10)
    # level / xp row
    s.stat_box(M, top, 60, 30, "level", c["level"], value_size=14)
    s.stat_box(M + 64, top, 80, 30, "xp", c["xp"], f"next {v['next_level_xp']}" if v["next_level_xp"] else "max", 12)
    s.stat_box(M + 148, top, 70, 30, "luck", c["luck_current"], f"start {c['abilities']['luck']}", 12)
    s.stat_box(M + 222, top, W - M - (M + 222), 30, "action dice", v["action_dice"], None, 10)
    top += 38
    # class-specific rows from the rolls table
    keys = {"warrior": ["melee_attack", "missile_attack", "melee_damage", "initiative", "crit"],
            "dwarf": ["melee_attack", "missile_attack", "shield_bash", "underground", "crit"],
            "thief": ["backstab", "melee_attack", "missile_attack", "two_weapon", "crit"],
            "halfling": ["two_weapon", "melee_attack", "missile_attack", "crit"],
            "elf": ["spell_check", "mercurial", "corruption", "secret_doors", "melee_attack"],
            "wizard": ["spell_check", "mercurial", "corruption", "melee_attack", "missile_attack"],
            "cleric": ["spell_check", "turn_unholy", "lay_on_hands", "melee_attack", "missile_attack"]}.get(klass, ["melee_attack", "missile_attack", "skill_checks"])
    rolls = {r["key"]: r for r in v["rolls"]}
    rows = [[rolls[k]["label"], rolls[k]["total"], ", ".join(f"{n} {val}" for n, val in rolls[k]["parts"]) + (f". {rolls[k]['note']}" if rolls[k]["note"] else "")] for k in keys if k in rolls]
    top = s.heading(top, "Rolls", size=7)
    top, _ = s.table(M, top, [95, 75, W - 2 * M - 170], rows, 6.2)
    # rules in play
    top = s.heading(top + 8, "Rules in play", size=7)
    x = x_extras
    lines = []
    if x.get("lucky_weapon"):
        lw = x["lucky_weapon"]; lines.append(("Lucky weapon", f"{lw['chosen'] or 'not chosen'} ({lw['modifier']:+d} to attack, fixed at level 1)"))
    if x.get("shield_bash"): lines.append(("Shield bash", x["shield_bash"]))
    if x.get("lucky_spell"):
        ls = x["lucky_spell"]; lines.append(("Lucky spell", f"{ls['chosen'] or 'not chosen'} ({ls['modifier']:+d} to its spell checks)"))
    if x.get("free_spells"): lines.append(("Always known", ", ".join(x["free_spells"])))
    if x.get("heightened_senses"): lines.append(("Heightened senses", x["heightened_senses"])); lines.append(("Immunities", x["immunities"])); lines.append(("Iron", x["iron"] + (" Carrying: " + ", ".join(x["iron_items"]) if x.get("iron_items") else "")))
    if x.get("disapproval"): lines.append(("Deity", x["deity"] or "")); lines.append(("Disapproval", f"natural 1 to {x['disapproval']['range']}. {x['disapproval']['rule']}"))
    if x.get("spellburn"): lines.append(("Spellburn", x["spellburn"]))
    if x.get("corruptions") is not None: lines.append(("Corruption", "; ".join(x["corruptions"]) or "none"))
    if x.get("luck_die"): lines.append(("Luck die", f"{x['luck_die']['die']}. {x['luck_die']['rule']}"))
    if x.get("backstab"): lines.append(("Backstab", x["backstab"]))
    if x.get("good_luck_charm"): lines.append(("Good luck charm", x["good_luck_charm"])); lines.append(("Two weapons", x.get("two_weapon_rule", ""))); lines.append(("Stealth", x.get("stealth", "")))
    if x.get("sword_and_board"): lines.append(("Sword and board", x["sword_and_board"])); lines.append(("Underground", x["underground"]))
    lines.append(("Luck recovery", x.get("luck_recovery", "")))
    tw = x.get("trained_weapons")
    lines.append(("Weapon training", "all weapons" if tw is None else ", ".join(sorted(tw))))
    # spellcasting summary
    sc = v["spellcasting"]
    if sc.get("caster"):
        known = f"{len(c['spells'])}/{sc['total']} known" if sc["kind"] == "wizard" else "per level " + " ".join(f"L{l}:{n}" for l, n in sc["per_level"].items() if n)
        lines.insert(0, ("Spellcasting", f"spell check {sc['check_bonus']:+d}, max spell level {sc['max_level']}, {known}. Spells on pages 6-8."))
    bottom = H - M - 8
    if v["thief_skills"]:
        bottom -= 14 * min(len(v["thief_skills"]), 13) // 2 + 20
    top, drawn = s.table(M, top, [78, W - 2 * M - 78], lines, 6.2, max_top=bottom)
    if v["thief_skills"]:
        top = s.heading(top + 6, "Stealth" if klass == "halfling" else f"Thief skills ({c['alignment']})", size=7)
        skills = v["thief_skills"]; half = (len(skills) + 1) // 2
        colw = (W - 2 * M) / 2
        ends = []
        for col, chunk in enumerate((skills[:half], skills[half:])):
            e, _ = s.table(M + col * colw, top, [colw * 0.62, colw * 0.36], [[sk["skill"], sk["value"]] for sk in chunk], 6.2)
            ends.append(e)
        top = max(ends)
    # titles by level, then the class abilities condensed, until the page is full
    if klass:
        titles = content_titles(v, c)
        if titles:
            top = s.heading(top + 6, "Titles", size=7)
            top, _ = s.table(M, top, [(W - 2 * M) / 5] * 5, [[f"{lvl}: {t}" for lvl, t in titles]], 5.5)
        top = s.heading(top + 6, f"{klass.capitalize()} abilities", size=7)
        skip = {"Hit points", "Weapon training", "Alignment", "Action dice", "Languages", "Caster level"}
        for name, text in v["prose"].items():
            if name in skip:
                continue
            short = " ".join(re.split(r"(?<=[.!?])\s+", text)[:3])
            lines_ = s.wrap(f"{name}. {short}", W - 2 * M, 6)
            need = len(lines_) * 7.2 + 3
            if top + need > H - M - 10:
                break
            s.text(M, top + 6, name.upper(), 5.5, BOLD, color=RULE)
            top = s.para(M, top + 8, W - 2 * M, short, 6) + 3


def content_titles(v, c):
    ct = v.get("_titles") or {}
    return [(lvl, t) for lvl, t in ct.items()]


def page_tables(s: Sheet, c, v, content, remaining):
    top = s.heading(M + 8, f"Crit table {v['crit_table']}  ·  roll {v['crit_die']} + Luck", size=8)
    rows = content["crit_tables"].get(v["crit_table"], [])
    colw = (W - 2 * M) / 2 - 3
    half = (len(rows) + 1) // 2
    end_left, _ = s.table(M, top, [22, colw - 22], [[r["roll"], r["text"]] for r in rows[:half]], 5.2, leading=6)
    end_right, _ = s.table(M + colw + 6, top, [22, colw - 22], [[r["roll"], r["text"]] for r in rows[half:]], 5.2, leading=6)
    top = max(end_left, end_right) + 6
    top = s.heading(top, f"Fumbles  ·  roll {v['fumble_die']} - Luck", size=8)
    frows = content.get("fumbles", [])
    half = (len(frows) + 1) // 2
    el, _ = s.table(M, top, [22, colw - 22], [[r["roll"], r["text"]] for r in frows[:half]], 5, leading=5.8, max_top=H - M - 80)
    er, _ = s.table(M + colw + 6, top, [22, colw - 22], [[r["roll"], r["text"]] for r in frows[half:]], 5, leading=5.8, max_top=H - M - 80)
    top = max(el, er) + 6
    top = s.heading(top, "Remaining inventory", size=7)
    n = int((H - M - top) // 9)
    for i in range(n):
        s.rule(M, top + (i + 1) * 9, W - M, top + (i + 1) * 9, 0.4, FAINT)
        if i < len(remaining):
            s.text(M + 2, top + (i + 1) * 9 - 2, remaining[i], 6, max_w=W - 2 * M - 4)


def page_campaign(s: Sheet, c, campaign):
    top = s.heading(M + 8, "Campaign", size=9)
    s.box(M, top, W - 2 * M, 150, "map")
    top += 156
    colw = (W - 2 * M) / 2 - 4
    s.text(M, top + 6, "IN MY HOME I OWN", 6, BOLD, color=RULE)
    t = s.para(M, top + 9, colw, campaign.get("home", ""), 6.5, max_lines=8)
    s.lines(M, max(t, top + 9), colw, max(0, 8 - int((t - top - 9) / 8)), 9)
    s.text(M + colw + 8, top + 6, "RELIGION", 6, BOLD, color=RULE)
    t2 = s.para(M + colw + 8, top + 9, colw, campaign.get("religion", ""), 6.5, max_lines=3)
    s.lines(M + colw + 8, max(t2, top + 9), colw, max(0, 3 - int((t2 - top - 9) / 8)), 9)
    top += 90
    s.text(M, top + 6, "RELATIONS: EVERYONE IN THE VALLEY", 6, BOLD, color=RULE)
    rel = campaign.get("relations", [])
    top += 9
    for i in range(10):
        s.rule(M, top + (i + 1) * 10, W - M, top + (i + 1) * 10, 0.4, FAINT)
        if i < len(rel):
            s.text(M + 2, top + (i + 1) * 10 - 2.5, rel[i], 6.5, max_w=W - 2 * M - 4)
    top += 108
    s.text(M, top + 6, "GOALS  ·  small and weird count double", 6, BOLD, color=RULE)
    goals = campaign.get("goals", [])
    top += 9
    n = int((H - M - top) // 12)
    for i in range(n):
        y = top + (i + 1) * 12
        s.box(M, y - 8, 7, 7, width=0.5)
        if i < len(goals):
            g = goals[i]
            if g.get("done"):
                s.text(M + 3.5, y - 2, "x", 7, BOLD, "center")
            s.text(M + 11, y - 2, g["text"], 6.5, max_w=W - 2 * M - 12)
        s.rule(M + 10, y, W - M, y, 0.4, FAINT)


def page_journal(s: Sheet, c):
    top = s.heading(M + 8, "Hirelings and allies", size=8)
    for i in range(2):
        x = M + i * ((W - 2 * M) / 2 + 2); w = (W - 2 * M) / 2 - 2
        s.box(x, top, w, 78)
        s.text(x + 3, top + 8, "NAME AND TITLE", 5, BOLD, color=RULE); s.rule(x + 3, top + 18, x + w - 3, top + 18, 0.4, FAINT)
        s.text(x + 3, top + 27, "HP", 5, BOLD, color=RULE); s.text(x + w / 2, top + 27, "AC", 5, BOLD, color=RULE); s.rule(x + 3, top + 36, x + w - 3, top + 36, 0.4, FAINT)
        s.text(x + 3, top + 45, "WEAPON / TO HIT / DMG", 5, BOLD, color=RULE); s.rule(x + 3, top + 54, x + w - 3, top + 54, 0.4, FAINT)
        s.text(x + 3, top + 63, "NOTES", 5, BOLD, color=RULE); s.rule(x + 3, top + 72, x + w - 3, top + 72, 0.4, FAINT)
    top += 88
    top = s.heading(top, "Adventure journal", size=8)
    for n in range(3):
        s.box(M, top, W - 2 * M, 118)
        for j, lab in enumerate(["ADVENTURE", "LOCATION", "FOES DEFEATED", "TREASURE GAINED", "NOTES"]):
            y = top + 10 + j * 21
            s.text(M + 3, y, lab, 5, BOLD, color=RULE); s.rule(M + 60, y + 2, W - M - 3, y + 2, 0.4, FAINT)
            if lab == "NOTES":
                s.rule(M + 3, y + 12, W - M - 3, y + 12, 0.4, FAINT)
        top += 124


def page_class_tables(s: Sheet, c, v, content):
    klass = c.get("class")
    top = M + 8
    if klass in ("warrior", "dwarf"):
        top = s.heading(top, "Mighty Deeds of Arms  ·  deed die 3+ and a hit", size=8)
        colw = (W - 2 * M) / 2 - 3
        deeds = list(content["mighty_deeds"].items())
        col_tops = [top, top]
        for n, (kind, rows) in enumerate(deeds):
            col = n % 2
            x = M + col * (colw + 6)
            s.text(x, col_tops[col] + 6, kind.upper(), 5.5, BOLD, color=RULE)
            end, _ = s.table(x, col_tops[col] + 8, [16, colw - 16], [[r["roll"], r["text"]] for r in rows], 4.8, leading=5.4)
            col_tops[col] = end + 5
        top = max(col_tops) + 4
    elif klass == "thief":
        top = s.heading(top, f"Thief skills by level ({c['alignment']})", size=8)
        table = content["thief_skills"][c["alignment"]]
        rows = [[skill] + list(vals) for skill, vals in table.items()]
        top, _ = s.table(M, top, [78] + [(W - 2 * M - 78) / 10] * 10, rows, 5.5, ["skill"] + [str(i) for i in range(1, 11)])
        top += 6
    elif klass == "halfling":
        top = s.heading(top, "Halfling", size=8)
        for k in ("Two-weapon Fighting", "Good luck charm", "Stealth", "Small size", "Infravision", "Slow"):
            if k in v["prose"]:
                s.text(M, top + 6, k.upper(), 5.5, BOLD, color=RULE); top = s.para(M, top + 8, W - 2 * M, v["prose"][k], 6) + 4
    top = s.heading(min(top + 4, H - M - 30), "Dice chain", size=7)
    s.text(M, top + 6, "  ".join(dcc.DICE_CHAIN) + "     -1d steps down, +1d steps up", 6.5)


def page_reference(s: Sheet, c, content):
    top = s.heading(M + 8, "Weapons", size=7)
    rows = [[w["name"] + ("*" if w["two_handed"] else ""), w["damage"], w["range"] or "-", str(w["cost"])] for w in content["weapons"]]
    colw = (W - 2 * M) / 2 - 3
    half = (len(rows) + 1) // 2
    el, _ = s.table(M, top, [colw * 0.44, colw * 0.2, colw * 0.24, colw * 0.12], rows[:half], 5, leading=5.8)
    er, _ = s.table(M + colw + 6, top, [colw * 0.44, colw * 0.2, colw * 0.24, colw * 0.12], rows[half:], 5, leading=5.8)
    top = max(el, er) + 4
    top = s.heading(top, "Armor", size=7)
    rows = [[a["name"], f"+{a['ac']}", str(a["check_penalty"]), f"{a['speed_penalty']}'" if a["speed_penalty"] else "-", a["fumble_die"] or "-", a["cost"]] for a in content["armor"]]
    top, _ = s.table(M, top, [80, 30, 40, 40, 50, W - 2 * M - 240], rows, 5, ["armor", "AC", "check", "speed", "fumble", "cost"], leading=5.8)
    top = s.heading(top + 4, "Ammunition and mounts", size=7)
    rows = [[a["name"], f"x{a['quantity']}", a["cost"]] for a in content.get("ammunition", [])] + [[m["name"], m["weight"] or "", m["cost"]] for m in content.get("mounts", [])]
    half = (len(rows) + 1) // 2
    el, _ = s.table(M, top, [colw * 0.6, colw * 0.2, colw * 0.2], rows[:half], 5, leading=5.8)
    er, _ = s.table(M + colw + 6, top, [colw * 0.6, colw * 0.2, colw * 0.2], rows[half:], 5, leading=5.8)
    top = max(el, er) + 6
    top = s.heading(top, "Attack roll modifiers", size=7)
    rows = [[f"{r['group']}: {r['condition']}", r["melee"] or "-", r["missile"] or "-"] for r in content.get("attack_modifiers", [])]
    half = (len(rows) + 1) // 2
    el, _ = s.table(M, top, [colw - 50, 25, 25], rows[:half], 5, leading=5.8)
    er, _ = s.table(M + colw + 6, top, [colw - 50, 25, 25], rows[half:], 5, leading=5.8)
    top = max(el, er) + 6
    top = s.heading(top, "Last will and testament", size=7)
    s.text(M, top + 12, "I,", 7); s.rule(M + 12, top + 14, M + 150, top + 14, 0.4); s.text(M + 154, top + 12, "do hereby", 7); s.rule(M + 190, top + 14, W - M, top + 14, 0.4)
    s.lines(M, top + 16, W - 2 * M, max(2, int((H - M - top - 30) // 12)), 12)


DENSITIES = [  # (band font, band leading, general max lines, band text: sentences kept)
    (5.5, 6.3, 99, 99), (5.0, 5.6, 2, 99), (4.8, 5.3, 1, 2), (4.6, 5.0, 1, 1)]


def spell_rows(sp, sentences):
    rows = []
    for r in sp.get("results", []):
        t = r["text"] if sentences >= 99 else " ".join(re.split(r"(?<=[.!?])\s+", r["text"])[:sentences])
        rows.append([r["band"], t])
    return rows


def spell_height(s: Sheet, sp, w, density):
    size, leading, gmax, sentences = density
    head = spell_head(sp)
    h = len(s.wrap(head, w, 6.5, BOLD)) * 8 + 2
    if sp.get("mercurial"):
        h += len(s.wrap(f"({sp['mercurial_roll']}) {sp['mercurial']['text']}", w - 24, size)) * (size * 1.2) + 2
    h += min(gmax, len(s.wrap(sp.get("general", ""), w, size))) * (size * 1.2) + 2
    for band, text in spell_rows(sp, sentences):
        h += max(len(s.wrap(text, w - 30, size)), 1) * leading + 2
    return h + 8


def spell_head(sp):
    return f"{sp['name']}   L{sp.get('level', '?')}  ·  {sp.get('range', '')}  ·  {sp.get('duration', '')}  ·  cast {sp.get('casting_time', '')}" + (f"  ·  save {sp['save']}" if sp.get("save") else "")


def spell_block(s: Sheet, sp, x, top, w, max_top, density=DENSITIES[0]):
    """Draw one spell; returns new top or None when it does not fit."""
    size, leading, gmax, sentences = density
    if top + spell_height(s, sp, w, density) > max_top:
        return None
    lines = s.wrap(spell_head(sp), w, 6.5, BOLD)
    for n, line in enumerate(lines):
        s.text(x, top + 6.5 + n * 8, line, 6.5, BOLD)
    top += len(lines) * 8 + 2
    if sp.get("mercurial"):
        s.text(x, top + size, "MERCURIAL", 4.5, BOLD, color=RULE)
        top = s.para(x + 24, top, w - 24, f"({sp['mercurial_roll']}) {sp['mercurial']['text']}", size) + 2
    top = s.para(x, top, w, sp.get("general", ""), size, max_lines=gmax) + 2
    top, drawn = s.table(x, top, [26, w - 26], spell_rows(sp, sentences), size, leading=leading)
    s.rule(x, top + 3, x + w, top + 3, 0.6)
    return top + 7


def pick_density(s: Sheet, spells, pages, w):
    """The first density at which all spells fit the spell pages (greedy, in order)."""
    for density in DENSITIES:
        usable = H - 2 * M - 20
        used, page = 0.0, 1
        heading_h = 12
        used = heading_h
        ok = True
        for sp in spells:
            h = spell_height(s, sp, w, density)
            if h > usable:
                ok = False; break
            if used + h > usable:
                page += 1; used = 0
                if page > pages:
                    ok = False; break
            used += h
        if ok:
            return density
    return DENSITIES[-1]


def render(character: dict, content: dict | None = None, imposed: bool = False) -> bytes:
    content = content or dcc.load_content()
    c = character
    v = dcc.derive(c, content)
    if c.get("class"):
        tt = content["class_titles"].get(c["class"], {})
        v["_titles"] = {lvl: (row.get(c.get("alignment", "neutral")) or row.get("all") or "") for lvl, row in sorted(tt.items(), key=lambda kv: int(kv[0]))}
    campaign = c.get("campaign") or {}
    buf = io.BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A5)
    s = Sheet(pdf)
    pages = []

    def new_page(fn, *args):
        pages.append((fn, args))

    remaining_holder = {}
    new_page(page_cover, c, v, campaign)
    new_page("stats", None)
    new_page(page_class, c, v, v["class_extras"])
    new_page("tables", None)
    new_page(page_campaign, c, campaign)
    if v["spellcasting"].get("caster"):
        new_page("spells", None); new_page("spells", None); new_page("spells", None)
    else:
        new_page(page_journal, c)
        new_page(page_class_tables, c, v, content)
        new_page(page_reference, c, content)
    spells = list(v["spells"])
    density = pick_density(s, spells, 3, W - 2 * M) if spells else DENSITIES[0]
    for n, (fn, args) in enumerate(pages, start=1):
        if fn == "stats":
            remaining_holder["rest"] = page_stats(s, c, v)
        elif fn == "tables":
            page_tables(s, c, v, content, remaining_holder.get("rest", []))
        elif fn == "spells":
            top = s.heading(M + 8, "Spells", size=8) if n == 6 else M + 8
            while spells:
                nt = spell_block(s, spells[0], M, top, W - 2 * M, H - M - 12, density)
                if nt is None:
                    if top <= M + 30:  # too tall even for an empty page: tightest tier, then clip
                        nt = spell_block(s, spells[0], M, top, W - 2 * M, H - M - 12, DENSITIES[-1])
                        if nt is None:
                            spell_block(s, spells[0], M, top, W - 2 * M, 10_000, DENSITIES[-1])
                        spells.pop(0)
                    break
                spells.pop(0); top = nt
        else:
            fn(s, *args)
        s.footer(n, c["name"])
        pdf.showPage()
    if spells:  # overflow: extra pages, in multiples of 4 for booklet printing
        guard = 0
        while (spells or len(pages) % 4) and guard < 40:
            guard += 1
            top = M + 8
            while spells:
                nt = spell_block(s, spells[0], M, top, W - 2 * M, H - M - 12, density)
                if nt is None:
                    if top <= M + 8:  # too big for any page: draw it anyway, clipped
                        spell_block(s, spells[0], M, top, W - 2 * M, 10_000, density); spells.pop(0)
                    break
                spells.pop(0); top = nt
            pages.append(("extra", None)); s.footer(len(pages), c["name"]); pdf.showPage()
    pdf.save()
    data = buf.getvalue()
    return impose(data) if imposed else data


def impose(pdf_bytes: bytes) -> bytes:
    """Booklet imposition: A5 pages onto landscape A4 sides for duplex, short-edge flip."""
    from pypdf import PdfReader, PdfWriter, Transformation

    reader = PdfReader(io.BytesIO(pdf_bytes))
    n = len(reader.pages)
    while n % 4:
        n += 1
    order = []
    lo, hi = 1, n
    side = 0
    while lo < hi:
        order.append((hi, lo) if side % 2 == 0 else (lo, hi))
        lo += 1; hi -= 1; side += 1
    writer = PdfWriter()
    aw, ah = landscape(A4)
    for left, right in order:
        page = writer.add_blank_page(width=aw, height=ah)
        for idx, x_off in ((left, 0), (right, aw / 2)):
            if idx <= len(reader.pages):
                src = reader.pages[idx - 1]
                page.merge_transformed_page(src, Transformation().translate(x_off, 0))
    out = io.BytesIO(); writer.write(out)
    return out.getvalue()
