"""The DCC west marches campaign: one campaign, one town, real time.

Everything specific to this campaign lives in this package. Facts that are
simply true of the campaign (the start date, the places in town and what they
sell) are written down in ``places.py``. What changes through play (what is
left on the shelves, who bought what) is stored under ``data/westmarch/``.

Time runs 1:1 with the real calendar: campaign day 1 is ``places.EPOCH`` and a
new day starts at midnight in ``places.TIMEZONE``.
"""

from ttrpgtools.dcc import explain as dcc_explain

#: What "What is this?" should say about things the rulebook does not contain. Keep in step with the code.
dcc_explain.HOUSE_NOTES.extend([
    {"title": "This campaign: the tax office", "words": ["tax", "debt", "owes", "owed"],
     "body": "Every villager, played or not, starts out owing the tax office 10,000 gp, far more than a villager will ever earn. 'Pay "
             "taxes' takes an amount such as 5,00 gp: that coin is gone at once and the debt shrinks by it. The big counter on the "
             "character list is what the whole town owes. When someone dies, their debt is split evenly among everyone still alive, "
             "so the town owes as much as before. The debt also grows by itself over time. Only the admin can change a purse. Rolling a die a second time in the builder "
             "doubles the debt, and raising a rolled number by hand adds 6,000 gp; lowering it takes off a single copper."},
    {"title": "This campaign: money", "words": ["purse", "coin", "price", " gp", "copper", "afford"],
     "body": "Money is written as gold with two decimals, like cents: 10,02 gp is 10 gold and 2 copper, and 1 gp is 100 cp. Players "
             "cannot add money. No coin is ever made or lost by play: what a character pays lands in the shop's or inn's till, a "
             "shop can only buy what its till can pay for, taxes go to the Finanzamt, and a dead character's coins go into the "
             "library's cash pot. "
             "Only the bank issues new coin. Prices in town change every real day, and nobody is shown the trend."},
    {"title": "This campaign: shops", "words": ["shop", "buy", "sell", "stock", "shelf", "blacksmith", "groderick", "market", "left", "sold out"],
     "body": "The town has three shops with real shelves: when the last piece is bought it is gone for everyone until the keeper "
             "can make another. Each "
             "shop buys back the kinds of goods it deals in at half of its own price that day. Groderick at Shop3 buys anything at "
             "all, for very little. Shops have no pages of their own: the town page and each character's page list every item with its "
             "price at each shop, and a click on a price buys it there. Below it the town page lists what each shop pays for the "
             "things a character carries; a click on a price sells one."},
    {"title": "This campaign: what things are made of", "words": ["material", "metal", "wood", "leather", "weight", "kg", "workshop", "making day",
                                                                    "made of", "sold out", "break up", "melt", "produce"],
     "body": "Nothing in town appears or vanishes by itself. Every piece of equipment is made of one material (metal, wood, leather "
             "and stuff, or Oldwork) and has a weight. On its making day a keeper makes what the shelf is short of, but "
             "only while the workshop holds the piece's weight in that material: a 4 kg sword needs 4 kg of metal. When the material "
             "runs out, spare second-hand pieces on the shelf are broken up for it: metal and leather come back whole, "
             "Oldwork loses half each time, wood is never broken up. So selling old gear to a shop gives its keeper "
             "material to work with. Small goods such as rations, candles, eggs, barley and coal, and raw wood, are brought by "
             "the villagers of the fitting trades, a little every night."},
    {"title": "This campaign: the library", "words": ["library", "borrow", "loan", "lent", "bring back"],
     "body": "When a character dies, everything they carried goes to the library: the things onto its shelves, the coins into its "
             "cash pot. Any character may borrow a thing from the shelves free of charge; it still belongs to the library and cannot "
             "be sold, only brought back. Coin can be borrowed from the pot too: such a loan grows a little every night until it is "
             "paid back into the pot."},
    {"title": "This campaign: inns", "words": ["inn", "bed", "night", "stay", "lodging", "sleep"],
     "body": "Inns are listed on the town's front page. Set the number of nights and press Pay: the price of all those nights "
             "leaves the purse at once. Each real night that passes restores hit points and lost ability "
             "points: one of each at the Shoddy Inn and at Shop1, two of each at the Good Inn, which costs far more."},
    {"title": "This campaign: the three moons", "words": ["moon", "lantern", "drowned", "pale"],
     "body": "Three moons cross the sky: the Pale Moon (calm, familiar, patient), the Red Lantern (restless, hungry, quick to anger) "
             "and the Drowned Moon (secretive, slow, seldom seen). Every character is bound to one, chosen when the character is "
             "made, for life. Nobody is told how long their cycles are; the town page shows tonight's phase of each. "
             "A character's moon decides two things in a fight, always: one die better (+1d, one step up the dice chain) against "
             "that moon's enemies, one die worse (-1d) against the kind it is weak against. Pale Moon: better against the dead and "
             "the patient, worse against the wet and the hidden. Red Lantern: better against the hungry, worse against the dead and "
             "the patient. Drowned Moon: better against the wet and the hidden, worse against the hungry."},
    {"title": "This campaign: who makes what", "words": ["produce", "producer", "scrap", "scrap metal", "caravan", "brewer", "hen keeper", "cheesemaker", "digger", "factor"],
     "body": "A few villagers make the basic goods and sell them to the shops: Zeno Zwiebel cheese, Detlef of the Ford eggs and hens, "
             "Xaver Haberkorn ale and barley, Hedwig Nebelung lamp oil and candles, Reinhild Sevenbrothers rations and barley, and the "
             "dwarf Hartmut Bachmeier scrap metal, which only the smith buys and melts down for his work. A shop buys a thing only "
             "up to twice the quantity it usually keeps, and only what its till can pay. Once a month a caravan comes; Vessa the "
             "factor sends for it a week ahead with the one or two kinds the village is shortest of. The shops pay for what it "
             "brings, and that coin leaves the village."},
    {"title": "This campaign: the town note and the caravan", "words": ["town note", "write", "caravan", "wagons", "hens", "barley", "hen died"],
     "body": "The town note is a scrap of about a hundred words that everybody shares: any character may add a line on the town page, "
             "the traders read it and add theirs at night, and the oldest lines fall off. The caravan comes every ten days and stays "
             "two. It sells dear to the shops, and it buys from anyone, but low and not everything; what it buys leaves with it. "
             "Hens eat: whoever owns a hen uses up a little barley every day, and without barley a hen may die."},
    {"title": "This campaign: things with a moon", "words": ["make", "moon make", "one die better", "one die worse", "maker", "lantern make", "pale moon make", "drowned moon make"],
     "body": "Whatever a keeper makes that could bear a name (weapons, armor, shields, gear) belongs to the moon that stood "
             "fullest on the day it was made: 'Red Lantern make'. Ammunition and small goods such as chalk, candles and barley "
             "have no moon. A hen has one. A thing with a moon may carry a gift (rolls with it are one die better in one "
             "circumstance) and a flaw (one die worse in another); each is only a chance, and a lucky maker's pieces have gifts "
             "more often and flaws less. Nothing in town says which moon a piece on a shelf has: it shows once the piece is "
             "bought. Whoever knows the making days and asks the herb woman about the moons can work it out beforehand."},
    {"title": "This campaign: the herb woman", "words": ["herb", "hedwig", "which moon", "next full", "forecast", "copper a question"],
     "body": "The herb woman in town says, for one copper a question, when one of the three moons is next full and for how many "
             "nights. Every question costs again. It matters because a weapon or armor made on a day belongs to the moon that "
             "stands fullest then. "
             "She also deals in birth augurs. An augur changes hands together with its modifier, at 50 gp a point: she pays for a "
             "good one, if she has the coin; a bad one costs that much to be rid of, and she pays whoever takes it off her shelf. "
             "An augur on her shelf is worn by one point. Whoever sold theirs is born under nothing and may take one from the shelf; "
             "nobody carries two. Hit points follow where the augur touches them, for every level so far."},
    {"title": "This campaign: villagers and characters", "words": ["villager", "townsfolk", "play ", "take over", "graveyard", "record death", "birth augur"],
     "body": "A character is made by taking over one of the villagers who are free to play. Five ability scores and the hit points are shown beforehand; "
             "Luck and the birth augur stay sealed, also from the player who took the villager, until the character is finished: class "
             "chosen and 1st level reached. Then both are told. The new character has 10 XP, enough to choose a class. Shopkeepers, "
             "innkeepers, the mayor and the traders cannot be played. A dead character goes to the graveyard and the villager is "
             "marked dead; a shop whose keeper is dead, missing or away stays shut."},
])
