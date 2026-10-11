"""How the town words things for one particular character. Same sums, different letterhead.

Hand-written lines: edit freely. A line may use {name} (as the office spells it), {first} (first name), {debt},
{paid} and {inn} (a sentence about where the character sleeps). Which of a band's lines is used changes from day
to day, and so does the misspelling, but stays the same within a day.

The tax office: its manner follows the debtor's Luck as it stands today, so burning Luck sours the office and
regaining it sweetens it. Nothing here changes a sum. Players are not told what drives it.
"""

from __future__ import annotations

import hashlib

from . import town

# highest Luck score of a band, and its name
LUCK_BANDS = [(5, "cursed"), (8, "unlucky"), (12, "plain"), (15, "lucky"), (18, "blessed")]

TAX_OFFICE = {
    "blessed": {
        "owes": ["Esteemed contributor {name}: a mere {debt} remains, entirely at your convenience.",
                 "The office thanks {name} for existing. Outstanding: {debt}. There is no hurry whatsoever.",
                 "{name}, friend of the ledger, carries {debt}. The office would not dream of mentioning it."],
        "receipt": ["Received with gratitude: {paid}. The office has framed one of the coins.",
                    "{paid} accepted from {name}. A clerk wept, a little.",
                    "The office is honoured by {paid}. Your file smells of lavender now."]},
    "lucky": {
        "owes": ["Valued contributor {name} owes {debt}. The office trusts you completely.",
                 "{name}: {debt} outstanding. We are sure it is an oversight.",
                 "{name} owes {debt}. The office remembers your name, and fondly."],
        "receipt": ["{paid} received. The office appreciates {name}.",
                    "Thank you, {name}. {paid} has been entered in the good ledger.",
                    "{paid} received in good order. Do come again."]},
    "plain": {
        "owes": ["{name} owes {debt}."],
        "receipt": ["Paid {paid} in taxes. The coin is gone."]},
    "unlucky": {
        "owes": ["The debtor {name} owes {debt}. This has been noted.",
                 "{name}, whose file was misplaced twice, owes {debt}. Probably more.",
                 "{name} owes {debt}. The office spelled that as it pleases."],
        "receipt": ["{paid} received from {name}. It was counted three times. {inn}",
                    "{paid} taken from {name}. One coin looked wrong; the office kept it anyway. {inn}",
                    "Receipt for {name}: {paid}. Do not lose this receipt. The office already has. {inn}"]},
    "cursed": {
        "owes": ["The debtor currently known as {first} owes {debt}. The office knows.",
                 "{name} (alias suspected) owes {debt}. A clerk has been assigned to watch.",
                 "{name} owes {debt}, and an apology, and the office is counting both."],
        "receipt": ["{paid} taken. It changes nothing. {inn}",
                    "The office accepts {paid} from the debtor currently known as {first} and remains disappointed. {inn}",
                    "{paid} received. The office felt nothing. {inn}"]},
}
INN_KNOWN = "We know you sleep at {inn}."
INN_UNKNOWN = "We know where you sleep. Roughly."
MISSPELL = {"cursed", "unlucky"}   # these bands never get their name right


def luck_band(luck: int) -> str:
    return next((name for top, name in LUCK_BANDS if luck <= top), LUCK_BANDS[-1][1])


def _pick(options: list[str], *seed) -> str:
    return options[int(hashlib.sha1("/".join(str(s) for s in seed).encode()).hexdigest(), 16) % len(options)]


def misspelled(name: str, day: int) -> str:
    """The name as a careless clerk writes it today: one small slip, another one tomorrow."""
    roll = int(hashlib.sha1(f"{name}/{day}/slip".encode()).hexdigest(), 16)
    letters = [n for n, ch in enumerate(name) if ch.isalpha() and 0 < n < len(name) - 1 and name[n - 1].isalpha() and name[n + 1].isalpha()]
    if not letters:
        return name + "?"
    at, how = letters[roll % len(letters)], (roll >> 8) % 4
    if how == 0 and name[at].lower() != name[at + 1].lower():   # two letters change places (two equal ones would leave it right)
        return name[:at] + name[at + 1].lower() + name[at].lower() + name[at + 2:]
    if how <= 1:   # a letter is written twice
        return name[:at] + name[at] + name[at].lower() + name[at + 1:]
    if how == 2:   # a letter is forgotten
        return name[:at] + name[at + 1:]
    swap = {"a": "e", "e": "i", "i": "y", "o": "u", "u": "o", "y": "i", "b": "p", "p": "b", "d": "t", "t": "d", "g": "k", "k": "g", "s": "z", "z": "s", "m": "n", "n": "m"}
    return name[:at] + swap.get(name[at].lower(), "h") + name[at + 1:]   # a letter is misheard


def _words(character: dict, day: int, sealed: bool) -> tuple[str, dict]:
    luck = int(character.get("luck_current", character["abilities"]["luck"]))
    band = "plain" if sealed else luck_band(luck)   # a sealed character's Luck is nobody's business yet, the office's included
    name = misspelled(character["name"], day) if band in MISSPELL else character["name"]
    lodging = character.get("lodging")
    return band, {"name": name, "first": name.split()[0], "debt": town.coins_text(int(character.get("tax_debt_cp") or 0)),
                  "inn": INN_KNOWN.format(inn=lodging["name"]) if lodging else INN_UNKNOWN}


def tax_office(character: dict, day: int, sealed: bool = False) -> dict:
    """What the office says about the debt today: {"band", "owes"}."""
    band, words = _words(character, day, sealed)
    return {"band": band, "owes": _pick(TAX_OFFICE[band]["owes"], character["name"], day, "owes").format(**words)}


def tax_receipt(character: dict, paid_cp: int, day: int, sealed: bool = False) -> str:
    band, words = _words(character, day, sealed)
    return _pick(TAX_OFFICE[band]["receipt"], character["name"], day, "receipt", paid_cp).format(paid=town.coins_text(paid_cp), **words).strip()
