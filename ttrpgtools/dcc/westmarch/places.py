"""Campaign facts, written down by hand. Edit freely: new places and new goods
appear in town on the next page load; quantities already in play are kept.

Goods are either a key of the rulebook equipment tables with a starting
quantity, ``("weapon:Longsword", 2)``, or anything else as
``("Silvered dagger", "weapon", "25 gp", 1)``. Services (lodging, meals) are
``(name, usual price)`` and never run out; goods always do.
Price curves are derived from the names unless a place or item sets its own
``curve`` (see ``town.py``). ``deals`` lists the kinds of goods a shop buys
back; ``restock_every`` is the number of days between making days, on which
the keeper makes what is short of the quantities written here, as far as the
``materials`` (kilograms in the workshop) go; ``stay`` makes a place an inn
with a nightly price and what a night restores.

Goods are a closed system (see ``materials.py``): equipment is made from
material by weight, small goods are brought by the villagers (``PRODUCE``),
and nothing else fills a shelf.

NAMES, KEEPERS AND SHELVES BELOW ARE PLACEHOLDERS until the owner replaces them.
"""

from datetime import date

EPOCH = date(2026, 10, 4)       # campaign day 1
TIMEZONE = "Europe/Berlin"      # a new day starts at midnight here
UPDATE_HOUR = 2                 # produce, making days and traders happen at this hour, every night
TALK_PER_WEEK = (1, 2)          # town talk: every week has this many nights (at least, at most) with one line "who sold what"
JUDGES = [j for j in __import__("os").environ.get("TTRPG_JUDGES", "admin").split(",") if j]             # login names that run the town (admin and DM)
SELL_BACK = 0.5                 # a shop pays this share of today's price for goods it buys
# Nobody likes a birth augur that does nothing. Whoever was born with a Luck modifier of +0 (Luck 9 to 12) has this
# chance that fate nudged the score at birth, up or down with equal odds, to a 3d6 score outside that band.
LUCK_NUDGE_CHANCE = 0.8

# Money is a closed system: every coin sits in a purse, a till (``till`` on a place below is what it starts with),
# the bank or the Finanzamt. Only the bank issues or retires coin, on the admin's word. PLACEHOLDER amounts.
BANK_START = "0 gp"
TAX_SURCHARGE = "6,000 gp"      # added "for no reason in particular" when a rolled number is raised by hand; lowering it refunds 1 cp
# The debt grows by itself: about INTEREST_MONTHLY per month for everyone, but how much of it lands on a given night
# follows the debtor's own moon. The weights are averaged over each moon's cycle, so no moon is cheaper in the long run.
INTEREST_MONTHLY = 0.02
LIBRARY_INTEREST_MONTHLY = 0.06  # on coin borrowed from the library's pot, weighted by the borrower's moon in the same way (PLACEHOLDER rate)
INTEREST_BY_PHASE = {"new": 0.0, "waxing crescent": 0.5, "first quarter": 1.0, "waxing gibbous": 1.5, "full": 2.0,
                     "waning gibbous": 1.5, "last quarter": 1.0, "waning crescent": 0.5}
# None: fixed prices. A dict (see economy.DEFAULT) switches on scarcity prices, production lags, fed-hen eggs and the households.
# Chosen in scripts/westmarch_lab.py runs (docs/dcc/DESIGN.md section 24): sticky prices and producers' own use make the occasional stuck episode;
# momentum buying is left out, it made one of 19 episodes last 87 days.
# None: Hedwig Dornbusch is only the herb woman (steward off). A dict switches on the steward (westmarch/steward.py): ``every`` is the days between her check-ins,
# ``brain`` is "rules" (her standing orders stay as they are) or "claude" (a headless Claude instance rewrites them), ``capital_cp`` her purse.
# Ageing (lives.py): the playable villagers age, marry, have children and die; the locked townsfolk (keepers, producers, the herb woman) stay as they are. None: off.
LIVES = {"lifespan": {"human": 60, "dwarf": 250, "halfling": 110, "elf": 2000},   # expected years; an elf dies of age only in theory (and has as few children, in proportion)
         "adult": 18, "weibull": 7.0,       # at eighteen the child works; the steeper the curve, the more the deaths bunch up late, around the expected lifespan
         "accident": 0.0003,                # monthly chance of dying young for a human, less in proportion to a longer life
         "accident_kind": {"elf": 0.1, "dwarf": 0.1},   # and a tenth of that again (the owner 10-11): an elf lives 2000 years on average (1794 before), a dwarf 247 (224)
         "rare_kind": {"below": 12, "boost": 4.0},   # a kind with fewer than 12 living gets up to four times the chance of a child (the owner 10-11: the dwarves and halflings were dying out)
         "no_mishap": ["Hedwig Dornbusch"],  # dies of nothing but age (the owner 10-11: a mishap killed her at about 709 in year 203)
         "child_death": (0.006, 0.0008),    # monthly chance for a child under five, and for one from five to seventeen (about four in ten never see eighteen): couples may have many children and the village stays small
         "romance": 0.04,                   # monthly chance that a single adult finds someone single of the same kind
         "match_boost": 0.6, "match_max": 3, "match_months": 24, "block_factor": 0.01, "block_max": 6,   # what the herb woman's hand does: a matched pair weds in a month with this chance
         "age_gap": 15,                     # years between a couple, for a human (longer-lived kinds scale up)
         "birth": 0.04, "children_max": 6, "target": 80, "steer": 1.0, "steer_deaths": 2.0,   # monthly chance of a child per couple (scaled to lifespan; chosen so the village holds about 100 by itself), and the number of living people the death chance is nudged towards (at 110 living: ten percent more deaths and ten percent fewer births)
         "mutation": 0.08, "parent_job": 0.8, "vacant_weight": 100, "mentor_max": 4, "mentor_chance": 0.85,   # a child drawing a job at random counts the table once, the trades of the village once each, and a hundred times for one whose seat stands empty
        
         "delver": {"prime": 0.45, "trip_death": 0.01}}   # a delver is the best of the adults in their prime; a trip kills with this chance at average strength
# The barley fields and the eel ponds (fields.py). None: barley and eel come from the traders' ``brings`` as before.
FIELDS = {"plots": 100, "grow": 41, "rest": 29, "per_seed": 7, "yield": 4.0, "light_nights": 12, "harvest_log": 60,
          "usual_plot_cp": 1600, "attachment": (0.5, 2.0), "farmer_ask": 3,   # owners name their price (the owner 10-10): about forty sacks at the usual price, times their own attachment, less when poor, thrice for a farmer, plus the crop
          "work": 7,   # plots one person keeps under barley at once: what one pair of hands can sow and reap (the owner 10-10)
          "keep_cp": 2000, "sell_below_cp": 300, "sell_share": 0.8,   # when a farming trader buys a plot, and when they sell one to the village
          "fat": 5}   # the eels on a fat night
STEWARD = {"every": 30, "brain": "host"}   # ON (2026-10-09): her standing orders act every night; her Claude check-in is run by the host (westmarch-steward.timer, nightly) on the nights she is due: she sets the next date and wake conditions herself
STEWARD_CAPITAL_CP = 30000
MARKET = {"ratchet": {"down": 0.035, "above": 1.5},
          "own_use": {"goods": ["Ale, a jug", "Eggs, a dozen", "Smoked eel", "Barley, a sack"], "above": 1.6, "fill": 0.4, "cap_days": 2.0, "eat": 0.03, "rest": 10}}
TAX_PAY_SHARE = 0.05             # a trader who owes the tax office pays this share of the coin above TAX_PAY_RESERVE each night (a small wish to be square)
TAX_PAY_RESERVE = "5 gp"
TAX_DEBT = "10 gp"              # what every character owes the tax office at the start (the owner 2026-10-08; it was 10,000 gp, hopeless on a peasant's income)
START_PURSE_CP = 1000           # house rule: a new character starts with about this much coin (10 gp); the 5d12 roll only sways it by a fifth either way

# The three moons. Every character is bound to one, chosen at creation. A moon's cycle is a list of
# (phase, nights), starting at new; the nights need not be equal, or even whole for the real one.
# ``offset`` shifts where in its cycle a moon stood on campaign day 1. Names and blurbs are PLACEHOLDERS.
# Players are told a moon's name and vibe, nothing about its cycle (the owner, 2026-10-04): they learn it by watching.
MOONS = [
    # "numerals": "roman" = for a character bound to this moon every number in town is written in Roman numerals
    # A character bound to a moon rolls one die better (+1d) against its "enemies" and one die worse (-1d) against its
    # "weak" kind, always. "safe": where their saving throws are one die better. Nothing changes with the phase.
    # PLACEHOLDER kinds: each moon is weak against another moon's enemies.
    {"id": "pale", "name": "The Pale Moon", "real": True, "numerals": "roman",
     "enemies": "the dead and the patient: un-dead, statues, and whatever has been waiting",
     "weak": "the wet and the hidden: fish-men, oozes, and things from below",
     "safe": "in lantern light, on even dungeon levels, or next to an ally",   # saving throws are one die better there
     # A thing made while this moon stood fullest may carry one of the "gifts" (rolls with it are one die better then)
     # and one of the "flaws" (one die worse then): each only a chance, see town.roll_mark. PLACEHOLDER lists.
     "gifts": ["against the un-dead", "in any round in which you did not move", "against anything older than you", "while you hold a lit lantern",
               "after a full night of sleep", "while somebody nearby is reading aloud"],
     "flaws": ["in the first round of a fight", "while running or charging", "against anything faster than you", "when you are in a hurry",
               "if you have told a lie today", "while it rains on you"],
     "blurb": "Calm, familiar, patient."},
    {"id": "red", "name": "The Red Lantern", "offset": 4,
     "enemies": "the hungry: goblins, beasts, and anything that eats people",
     "weak": "the dead and the patient: un-dead, statues, and whatever has been waiting",
     "safe": "by open flame, on odd dungeon levels, or in the front rank",   # saving throws are one die better there
     "gifts": ["while you are wounded", "against cold-blooded creatures", "while you are outnumbered", "while you are shouting",
               "against anything bigger than you", "by firelight"],
     "flaws": ["on a full stomach", "against the un-dead", "against plants and fungi", "against anything made of stone",
               "while you sit or lie down", "against anything smaller than a cat"],
     "blurb": "Restless, hungry, quick to anger.",
     "cycle": [("new", 1), ("waxing crescent", 1), ("first quarter", 1), ("waxing gibbous", 2), ("full", 5),
               ("waning gibbous", 1), ("last quarter", 1), ("waning crescent", 1)]},
    {"id": "drowned", "name": "The Drowned Moon", "offset": 17,
     "enemies": "the wet and the hidden: fish-men, oozes, and things from below",
     "weak": "the hungry: goblins, beasts, and anything that eats people",
     "safe": "in darkness, or last in the marching order",   # saving throws are one die better there
     "gifts": ["in darkness", "against creatures of water or slime", "while you are wet", "below the first level of a dungeon",
               "against anything with scales", "while you stand in water"],
     "flaws": ["in bright light", "within sight of the sky", "while you carry a lit torch", "against anything that is on fire",
               "against birds and whatever flies", "in a place that is bone dry"],
     "blurb": "Secretive, slow, seldom seen.",
     "cycle": [("new", 28), ("waxing crescent", 13), ("first quarter", 8), ("waxing gibbous", 5), ("full", 1),
               ("waning gibbous", 1), ("last quarter", 2), ("waning crescent", 3)]},
]

# Trade goods: bought and sold for profit, not for use. Prices swing like everything else, and nobody sees the
# curve, except a character whose occupation is listed under ``knows`` (at most INSIGHT_MAX goods per character).
INSIGHT_MAX = 2
TRADE_GOODS = [
    {"name": "Stinky cheese", "price": "8 sp", "knows": ["cheesemaker", "herder", "farmer"]},
    # the owner, 2026-10-07: smoked eel (an eel farmer makes it), fabric and eastern steel (imported: no villager makes them,
    # only the caravan brings them). ``shop`` says whose shelf; the default is Shop1's.
    {"name": "Smoked eel", "price": "2 sp", "knows": ["eel farmer", "mariner", "fisher", "cook"]},
    {"name": "Fabric, a bolt", "price": "3 gp", "knows": ["haberdasher", "dyer", "glovemaker", "merchant", "trader"], "imported": True},
    {"name": "Eastern steel, an ingot", "price": "18 gp", "knows": ["blacksmith", "armorer", "locksmith", "mercenary"], "imported": True, "shop": "shop2"},
]

# Which place plays which part in the clauses (westmarch/clauses.py), and what an inn's pet fee is per night.
ROLES = {"smith": "shop2", "outfitter": "shop1", "junk": "shop3"}
PET_FEE = "3 cp"

# Plain small goods beside the weird ones above: (name, usual price). PLACEHOLDERS.
SMALL_GOODS = [("Eggs, a dozen", "3 cp"), ("Barley, a sack", "4 sp"), ("Coal, a sack", "6 sp"), ("Ale, a jug", "6 cp"), ("Hen", "5 sp")]

# Small goods come from the villagers. Every night each living villager nobody plays, whose occupation contains one of
# the ``by`` words, brings one piece with a chance of PRODUCE_CHANCE, but only while a shelf that lists the good is
# below its listed quantity. ``wood_kg`` instead of ``good`` is raw wood for the workshops that work wood, which take
# no more than WOOD_STORE_KG. A villager a player takes over stops producing. PLACEHOLDERS.
# Eggs, hens, ale, oil, candles, cheese, barley and scrap metal are not in this list: named producers make those and
# SELL them to the shops for coin (BOTS below), so a shelf of them fills only as far as a till can pay.
PRODUCE_CHANCE = 0.5
WOOD_STORE_KG = 60
PRODUCE = [
    {"wood_kg": 2, "by": ["forester", "woodcutter", "hunter", "trapper", "wainwright"]},
    {"good": "Rations, per day", "by": ["hunter", "trapper"]},   # hunting; the cook makes the rest from barley, eggs and hens
    {"good": "Torch, each", "by": ["forester", "trapper", "rope maker"]},
    {"good": "Chalk, 1 piece", "by": ["stonemason", "miner"]},
    {"good": "Holy water, 1 vial", "by": ["shaman", "healer"]},
    {"good": "Sling stones", "by": ["stonemason", "ditch digger"]},
    {"good": "Coal, a sack", "by": ["miner", "forester"]},
]

PLACES = [
    {"id": "shop1", "till": "60 gp", "materials": {"metal": 15, "leather": 30, "wood": 20, "tech": 3}, "wants": ["Tanned hide"], "name": "Shop1", "kinds": ["shop", "inn"], "keeper": "Marta Vogt",
     "blurb": "Outfitter with a few plain beds upstairs. Rope, lamp oil and a roof.",
     "deals": ["gear", "trade", "mount", "other"], "restock_every": 7,
     "stay": {"price": "3 sp", "hp": 1, "ability": 1},
     "goods": [("gear:Backpack", 4), ("gear:Candle", 20), ("gear:Chain, 10’", 2), ("gear:Chalk, 1 piece", 12), ("gear:Chest, empty", 2),
               ("gear:Crowbar", 3), ("gear:Flask, empty", 6), ("gear:Flint & steel", 5), ("gear:Grappling hook", 2), ("gear:Hammer, small", 3),
               ("gear:Iron spikes, each", 24), ("gear:Lantern", 2), ("gear:Mirror, hand-sized", 1), ("gear:Oil, 1 flask", 10),
               ("gear:Pole, 10-foot", 4), ("gear:Rations, per day", 30), ("gear:Rope, 50’", 5), ("gear:Sack, large", 6),
               ("gear:Sack, small", 8), ("gear:Torch, each", 24), ("gear:Waterskin", 5)]
              + [(good["name"], "trade", good["price"], 6) for good in TRADE_GOODS if good.get("shop", "shop1") == "shop1"]
              + [(name, "trade", price, 6) for name, price in SMALL_GOODS],
     "services": [("Hot meal and ale", "4 cp")]},
    # ``wants``: things a shop buys although they are not of the kinds it deals in. The smith buys scrap metal and melts it.
    {"id": "shop2", "till": "150 gp", "materials": {"metal": 20, "leather": 40, "wood": 30}, "wants": ["Scrap metal", "Eastern steel, an ingot", "Tanned hide"], "name": "The Blacksmith", "kinds": ["shop"], "keeper": "Bram Eisenhand",
     "blurb": "Smithy by the river gate. Blades, mail and whatever the last caravan left behind.",
     "deals": ["weapon", "armor", "shield", "ammo"], "restock_every": 10,
     "goods": [("weapon:Battleaxe", 1), ("weapon:Club", 3), ("weapon:Crossbow", 1), ("weapon:Dagger", 4), ("weapon:Dart", 12),
               ("weapon:Flail", 1), ("weapon:Handaxe", 3), ("weapon:Javelin", 4), ("weapon:Lance", 1), ("weapon:Longbow", 1),
               ("weapon:Longsword", 2), ("weapon:Mace", 2), ("weapon:Polearm", 1), ("weapon:Shortbow", 2), ("weapon:Short sword", 3),
               ("weapon:Sling", 3), ("weapon:Spear", 4), ("weapon:Staff", 3), ("weapon:Two-handed sword", 1), ("weapon:Warhammer", 1),
               ("armor:Padded", 3), ("armor:Leather", 2), ("armor:Studded Leather", 1), ("armor:Hide", 2), ("armor:Scale Mail", 1),
               ("armor:Chainmail", 1), ("shield:Shield", 3),
               ("ammo:Arrows", 6), ("ammo:Quarrels", 3), ("ammo:Sling stones", 5), ("ammo:Arrows, silver-tipped", 4)]
              + [(good["name"], "trade", good["price"], 2) for good in TRADE_GOODS if good.get("shop") == "shop2"]},
    # Groderick buys anything at all, for very little: `sell_back` of today's value, or `junk_cp` flat for things nobody can price.
    {"id": "shop3", "till": "25 gp", "materials": {"metal": 20, "leather": 5, "tech": 4}, "name": "Shop3", "kinds": ["shop"], "keeper": "Groderick the item merchant",
     "blurb": "Buys anything. Pays almost nothing. Sells what others gave up.",
     "buys_anything": True, "sell_back": 0.15, "junk_cp": 2, "restock_every": 13,
     "goods": [("weapon:Blackjack", 2), ("weapon:Blowgun", 1), ("weapon:Garrote", 2), ("weapon:Dagger", 2),
               ("gear:Thieves’ tools", 1), ("gear:Holy symbol", 2), ("gear:Holy water, 1 vial", 3), ("gear:Mirror, hand-sized", 1),
               ("gear:Lantern", 1), ("gear:Chest, empty", 1), ("armor:Banded Mail", 1), ("armor:Half-Plate", 1)]},
    # The library sells nothing. It lends: whatever the dead leave behind ends up here, and anyone may borrow it.
    {"id": "library", "name": "The Library", "kinds": ["library"], "keeper": "",
     "blurb": "What the dead leave behind is kept here and lent to the living. Bring it back."},
    # The herb woman reads the sky: for ``ask`` she says when one moon is next full, and for how long. Every question costs again.
    # She also deals in birth augurs (``augur_point``: coin per point of modifier). A good augur she buys, a bad one she takes
    # off you for a fee, and what she has she passes on, each worn by one point: see town.sell_augur and town.take_augur.
    {"id": "herb-woman", "till": "0 gp", "name": "The Herb Woman", "kinds": ["oracle"], "keeper": "Hedwig Dornbusch", "ask": "1 cp", "augur_point": "50 gp",
     "blurb": "Dried things hang from every beam. She knows what the sky will do, and says so for a copper."},
    # Inns: a night is paid up front, each real night that passes restores `hp` hit points and `ability` lost ability points.
    # The shoddy rate is the rulebook's night of rest, the good one its day of bed rest (p. 94).
    {"id": "shoddy-inn", "till": "5 gp", "name": "The Shoddy Inn", "kinds": ["inn"], "keeper": "One-Ear Jost",
     "blurb": "Cheap, loud, and close to the docks. Nobody asks your name.",
     "stay": {"price": "5 cp", "hp": 1, "ability": 1},
     "goods": [("Ale, a jug", "trade", "6 cp", 12)],   # the inns sell the brewer's ale (the owner 10-10: the village should drink more of it)
     "services": [("Bowl of stew and small beer", "2 cp")]},
    {"id": "good-inn", "till": "80 gp", "name": "The Good Inn", "kinds": ["inn"], "keeper": "Lady Odila",
     "blurb": "Clean sheets, a bath, a healer on call, and stabling behind the house. Coin first.",
     "stay": {"price": "2 gp", "hp": 2, "ability": 2},
     "goods": [("Ale, a jug", "trade", "6 cp", 12)],
     "services": [("Three-course supper with wine", "8 sp"), ("Stabling, one mount, one day", "5 sp")]},
]

# Every trader has an identity note and a note of their own, each at most 50 words, both given to the local model
# every time it plays them.
#   The identity note is fixed and built by daily.identity from labelled fields: NAME, RACE (with ``who``, a line of
#   their own story), TRADE, MAKES (from ``brings``), NEEDS (from ``needs``), KEEPS, LIKES (``fond``) and QUIRK. Name,
#   trade, wares and needs come from the data; ``who``, ``keeps``, ``fond`` and ``quirk`` are written by hand. It steers,
#   it does not forbid: a digger is very unlikely to sell his own hammer, and now and then one will. A quirk may
#   name a moon; the model is told tonight's sky. (``persona`` is the older prose description, kept as a fallback.)
#   The trader's own note starts as ``seed`` and the model rewrites it. A seed gives a GOAL, something to TRACK from
#   day to day, and a RULE that depends on what was tracked, so that keeping the note is worth the model's while.
# A trader may follow a script: a text file in westmarch/bots/ that tells the local model how to choose, plus hard
# ``limits`` that the code enforces whatever the model answers:
#   buys_per_day, sells_per_day   how many shelf lines it may buy from and pack lines it may sell, one piece each
#   pack_limit                    how many pieces it may hold
#   buy_below                     buys only at or below this share of the usual price (0.6 = 40% off or more)
#   min_profit                    sells only when the shop pays at least this much more than it paid (1.1 = +10%)
# The model only ever picks from lines that already satisfy the limits, so a bad answer cannot lose money.
# Traders who visit the shops once a day. Each has a purse and a pack of their own (``start`` is the coin they begin
# with; nobody earns coin from nowhere), brings what they produce themselves (``brings``: small goods only, never
# equipment, which has to be made from material), and decides what to sell and buy: the local model plays them when it is
# running, a plain rule does otherwise. PLACEHOLDERS like the places above.
BOTS = [
    {"id": "hedwig-d", "steward": True, "name": "Hedwig Dornbusch", "race": "elf", "trade": "herb woman and keeper of the village's balance", "who": "has watched this village for three hundred years",
     "keeps": "her herbs and her ledger", "fond": "balance", "quirk": "never sells at the top and never buys at the bottom", "likes": [],
     "persona": "An elf, the herb woman. Buys what is nearly free and stores it, sells what is dear, and never spends her whole purse. Keeps a few laying hens of her own and sells their eggs. Thinks in years.",
     "seed": "GOAL no good gone for months, no producer ruined. RULE buy when a good is nearly free, sell when it is dear. NEXT read the village each season.",
     "lays": "Eggs, a dozen", "brings": [("Eggs, a dozen", "trade", "3 cp")]},   # her own hens (the owner 10-10): fed from her barley, their eggs sold every night
    {"id": "henrik", "name": "Henrik the tinker", "race": "human", "trade": "tinker", "who": "walked in with a cart and never left", "keeps": "his hammer, his awl, one lantern", "fond": "broken things", "quirk": "never pays above the usual price", "likes": ["gear", "trade"],
     "persona": "A wandering tinker. Mends lamps and tools and resells them. Keeps his own hammer, awl and one lantern: without them he cannot work. Buys cheap gear worth mending, never above the usual price.",
     "seed": "GOAL mend and resell at double. LEDGER each thing bought: paid, then fetched: (empty). RULE buy only what the ledger says sold at a gain before, or what I have never tried. NEXT when ten things made a gain, raise my prices.",
     "brings": []},
    {"id": "sigrun", "name": "Sigrun of the caravan", "race": "human", "trade": "caravan guard captain", "who": "has buried three employers", "keeps": "her sword and her bow", "fond": "good steel", "quirk": "spends at most a third of her purse in a day", "likes": ["weapon", "armor", "trade"],
     "persona": "A caravan guard captain between journeys. Sells what she salvaged, buys good steel only when it is clearly cheap. Keeps her own sword and bow: she does not sell the tools of her trade. Careful with coin; never spends more than a third of her purse at once.",
     "seed": "GOAL a mail shirt before the next journey. TRACK my purse, and the smith's price for chainmail by day: (none yet). RULE buy it on the cheapest day I have seen, not before I have seen five. AFTER find the next journey.",
     "brings": []},
    {"id": "vessa", "name": "Vessa the factor", "race": "human", "trade": "factor", "who": "came with one ledger and no luggage", "keeps": "nothing: goods are coin that has not arrived yet", "fond": "a price that is wrong", "quirk": "sends for the caravan and speaks for what the village lacks", "start": "40 gp", "brings": [],
     "likes": ["weapon", "armor", "shield", "gear", "trade", "mount"],
     "persona": "A factor who lives on price differences alone. Uses nothing she buys and holds it only until it pays. Speaks for what the village lacks and sends for the caravan.",
     "seed": "I do arbitrage. LEDGER what things cost where, and on which day: (none yet). RULE buy only what the ledger has shown dearer elsewhere. NEXT learn on which days each shop's prices dip, and write the days here.",
     "script": "arbitrage.txt",
     "limits": {"buys_per_day": 2, "sells_per_day": 2, "pack_limit": 6, "buy_below": 0.6, "min_profit": 1.1}},
    {"id": "gudrun", "name": "Gudrun Kellermann", "race": "human", "trade": "cook", "who": "fed the mayor's wedding once and has never forgotten it", "keeps": "her pot and her best knife", "fond": "a full larder", "quirk": "tastes everything twice",
     "likes": ["trade", "gear"], "needs": ["Barley, a sack", "Eggs, a dozen", "Hen"],
     "stock_up": {"Barley, a sack": 2, "Eggs, a dozen": 2}, "stock_up_cheap": {"Hen": (2, 0.4)},
     "persona": "A cook. Makes rations from barley, eggs or hens, whichever is cheapest that day, and sells them to the shops and the travellers. Keeps her pot and her best knife. Buys hens only when they are cheap.",
     "seed": "GOAL a pot that never needs mending. TRACK which of barley, eggs and hens made the cheapest ration each day: (none yet). RULE buy hens only below half the usual price. NEXT a second pot.",
     "brings": [("Rations, per day", "gear", "2 cp", 8)], "makes_from": {"Rations, per day": [("Barley, a sack", 25), ("Eggs, a dozen", 3), ("Hen", 6)]}},
    {"id": "pip", "tills": True, "name": "Pip the farmhand", "race": "human", "trade": "farmhand", "who": "was promised the farm one day", "keeps": "one sack and one rope", "fond": "a full plate", "quirk": "sells on a whim, then regrets it", "likes": ["gear", "trade"],
     "persona": "A farmhand with little coin. Sells barley, which is also the mounts' feed, and whatever else the farm can spare. Buys only what the farm needs: rope, sacks, a tool now and then. Keeps one sack and one rope for the work.",
     "seed": "GOAL a rope of my own that is not frayed. TRACK what barley fetched each day: (none yet). RULE sell on a day that beats the best I have written down; else hold, three days at most.",
     "brings": [("Barley, a sack", "trade", "4 sp", 2)]},
    # Producers: they make basic goods (``brings``: name, kind, usual price, and optionally the most pieces in a day) and
    # sell them to the shops. ``needs`` names the only things they ever buy, and never more than three of one.
    # The local model plays them and keeps a notebook for each; a plain rule plays them otherwise.
    {"id": "zeno", "farm": True, "name": "Zeno Zwiebel", "race": "human", "trade": "cheesemaker", "who": "inherited the cellar and the smell", "keeps": "his cheese cloths and one knife", "fond": "ale with his own cheese", "quirk": "grumbles at every price and pays it anyway", "likes": ["trade"], "needs": ["Barley, a sack", "Ale, a jug"],
     "persona": "A cheesemaker. Makes stinky cheese and sells it where it pays best. Needs barley and ale now and then. Keeps his cheese cloths and one knife. Grumbles about every price.",
     "seed": "GOAL find out which shop loves cheese. TRACK what Shop1 and Shop3 paid, by day: (none yet). RULE sell where it paid more last time. SUSPICION the price follows a moon. Write down the sky when cheese is dear.",
     "brings": [("Stinky cheese", "trade", "8 sp")]},
    {"id": "detlef", "farm": True, "stock_up": {"Barley, a sack": 3, "Hen": 12}, "stock_up_cheap": {"Barley, a sack": (20, 1.0)}, "lays": "Eggs, a dozen", "hold": {"Hen": 12, "Barley, a sack": 20}, "lag": {"Hen": 14}, "watch": {"Hen": "Eggs, a dozen"}, "name": "Detlef of the Ford", "race": "human", "trade": "hen keeper", "who": "knows every hen by name", "keeps": "his last three hens", "fond": "a quiet yard", "quirk": "buys nothing while the Red Lantern is full", "likes": ["trade", "mount"], "needs": ["Barley, a sack"],
     "moon": {"id": "pale", "peak": "new", "swing": 0.5}, "rhythm": "hens lay best at the new Pale Moon",
     "persona": "A hen keeper. Sells eggs daily and a hen when the yard is full. Needs feed and barley for the birds, nothing else. Never sells his last three hens: no hens, no eggs.",
     "seed": "GOAL twelve hens in the yard. TRACK hens I hold: 3. Egg price by shop: (none yet). RULE sell a hen only when I hold more than twelve. AFTER decide whether geese were the better idea all along.",
     "brings": [("Eggs, a dozen", "trade", "3 cp", 3), ("Hen", "trade", "5 sp", 1)]},
    {"id": "xaver", "stock_up": {"Barley, a sack": 3}, "lag": {"Ale, a jug": 3}, "name": "Xaver Haberkorn", "race": "human", "trade": "brewer", "who": "lost a field to the tax office", "keeps": "his kettle and one jug of his own ale", "fond": "cheap barley", "quirk": "calls every price robbery", "likes": ["trade"], "needs": ["Barley, a sack"],
     "persona": "A brewer. Makes ale and sells it by the jug, with spare barley. Needs barley, the cheaper the better. Keeps a jug for himself and never sells his brewing kettle.",
     "seed": "GOAL never again pay more than 30 cp for barley. TRACK barley price by day, lowest seen: (none yet). RULE buy only within 5 cp of the lowest seen. AFTER a full cellar: brew something stronger and name it.",
     "brings": [("Ale, a jug", "trade", "6 cp", 10)], "makes_from": {"Ale, a jug": ("Barley, a sack", 10)}},   # up to a sack a night (the owner 10-10: was 4 jugs)   # one sack of barley makes ten jugs
    {"id": "hedwig-n", "name": "Hedwig Nebelung", "race": "human", "trade": "oil presser and chandler", "who": "has not let her lamp go out in nine years", "keeps": "her press and one lit lamp", "fond": "order", "quirk": "counts her flasks twice", "likes": ["gear", "trade"], "needs": ["Flask, empty"],
     "persona": "An oil presser and chandler. Makes lamp oil and candles and sells them. Needs empty flasks for the oil. Keeps her press and one lit lamp. Buys little else.",
     "seed": "GOAL six empty flasks in reserve. TRACK flask price, lowest seen: (none yet). Flasks held: 0. RULE buy a flask only at or below the lowest seen. WATCH who buys candles, and under which moon.",
     "brings": [("Oil, 1 flask", "gear", "2 sp", 2), ("Candle", "gear", "1 cp", 4)]},
    {"id": "hartmut", "name": "Hartmut Bachmeier", "race": "dwarf", "trade": "scrap digger", "who": "left the mines", "keeps": "one hammer, one lantern, three rations", "fond": "old iron and silence", "quirk": "buys nothing at the full Pale Moon", "likes": ["gear"], "needs": ["Lantern", "Hammer, small", "Rations, per day"],
     "moon": {"id": "drowned", "peak": "new", "swing": 0.6}, "rhythm": "digs most at the new Drowned Moon",
     "persona": "A dwarf who digs old iron out of the hill and sells it to the smith as scrap. Needs rations, a lantern and a hammer for the work, and keeps one of each always: a digger without a hammer is a beggar.",
     "seed": "GOAL a second lantern. TRACK what the smith paid per lump, by day: (none yet). RULE sell scrap only on a day that matches or beats the best written here; else wait one day. AFTER the lantern: find the next thing worth digging for.",
     "brings": [("Scrap metal", "trade", "4 sp", 5)]},
    {"id": "reinhild", "farm": True, "tills": True, "lag": {"Barley, a sack": 7}, "name": "Reinhild Sevenbrothers", "race": "human", "trade": "barley farmer", "who": "feeds seven brothers who do not farm", "keeps": "one sack, one rope, a week of rations", "fond": "a full barn", "quirk": "watches every copper leave", "likes": ["gear", "trade"], "needs": ["Sack, large", "Sack, small", "Rope, 50\u2019"],
     "moon": {"id": "pale", "peak": "full", "swing": 0.5}, "rhythm": "barley ripens by the Pale Moon, best at full",
     "persona": "A farmer. Grows barley and sells it. Needs sacks and rope. Keeps one sack, one rope and a week of her own rations. Watches every copper.",
     "seed": "GOAL 5 gp saved before winter. TRACK my purse at each day's end: (none yet). RULE buy rope or sacks only on a day my purse is above yesterday's. AFTER 5 gp: a second field, or one brother fewer.",
     "brings": [("Barley, a sack", "trade", "4 sp", 4)]},
    {"id": "jutta", "ponds": {"count": 6, "days": 20, "per": 2}, "stock_up": {"Coal, a sack": 3}, "lag": {"Smoked eel": 4}, "name": "Jutta of the Mill", "likes": ["trade", "gear"], "needs": ["Coal, a sack", "Sack, small"],
     "race": "human", "trade": "eel farmer", "who": "keeps eels in the old millpond", "keeps": "her smokehouse and ten breeding eels",
     "fond": "still water", "quirk": "talks to the eels",
     "moon": {"id": "red", "peak": "full", "swing": 0.9}, "rhythm": "eels run with the Red Lantern, most at full",
     "persona": "An eel farmer at the old mill. Raises eels in the millpond and smokes them. Needs coal for the smokehouse and sacks to carry them. Never sells her breeding eels.",
     "seed": "GOAL a second smokehouse. TRACK coal sacks used and eel strings sold, by day: (none yet). RULE smoke only as many eels as coal allows; sell where the price beats yesterday's. NEXT teach somebody the smoking, for a fee.",
     "brings": [("Smoked eel", "trade", "2 sp", 3)], "makes_from": {"Smoked eel": ("Coal, a sack", 4)}},   # one sack of coal smokes four strings
    {"id": "ivo", "lag": {"Tanned hide": 5}, "name": "Ivo Zwiebel", "likes": ["gear", "trade"], "needs": ["Hammer, small", "Rations, per day"],
     "race": "human", "trade": "leatherworker", "who": "tans hides in the creek below the mill", "keeps": "his awl, his knife and one stretching frame",
     "fond": "the smell of oak bark", "quirk": "never sells a hide he has not named",
     "persona": "A leatherworker who tans the hides of the village's beasts and sells them to the shops. Needs a hammer and food, nothing else. Keeps his own tools.",
     "seed": "GOAL a hide press of my own. TRACK what the outfitter and the smith each paid for a hide, by day: (none yet). RULE sell to whoever paid more last time; keep one hide for my own work. NEXT find out which of them can pay for three at once.",
     "brings": [("Tanned hide", "trade", "8 sp", 2)]},
]

# The caravan, every ``every`` campaign days (the owner, 2026-10-06: every 10 days, sent for 5 days ahead). Vessa the factor works out what the village is shortest of (daily.village_needs), sends for a
# caravan ``ask_ahead`` days before it is due, and it brings the ``kinds`` most needed kinds: raw material for the
# workshops, or small goods for the shelves. The shops that receive pay from their tills (materials at these prices a
# kilogram, goods at half their usual price); that coin leaves the village with the caravan. PLACEHOLDER numbers.
# The caravan is dear: materials at these prices a kilogram, goods at ``goods_price`` times their usual price.
# It stays ``stays`` days and buys as well, from anyone, but low: ``pays_share`` of a thing's usual price, and it
# ``refuses`` what spoils on the road. What it buys leaves with it. It pays out of the coin caravans took before, so
# selling to it is how that coin comes back. A model plays the caravan master on arrival (identity and note below,
# like a trader's) and may set the share within ``share_range`` and what is refused.
CARAVAN = {"every": 10, "ask_ahead": 5, "by": "vessa", "kinds": 2, "most_kg": 60, "stays": 2, "goods_price": 1.5,
           "material_price": {"metal": "12 sp", "leather": "9 sp", "tech": "45 gp", "wood": "15 cp"},
           "pays_share": 0.2, "share_range": (0.05, 0.35), "refuses": ["hen", "chicken", "barley"],
           "hens_max": 2,   # hens a visit brings at most, and only while the hen shelves hold under half their usual (the owner 10-10: it brought 4 to 6 nearly every visit)
           "identity": "NAME the caravan master. RACE human who has heard every sad story twice. TRADE long-road trader. SELLS dear what a village cannot make. "
                       "BUYS only what sells three towns on, and low. KEEPS the wagons moving. QUIRK lowballs everyone; really does not want anyone's chicken or barley.",
           "seed": "GOAL leave with more coin than we came with. TRACK what this village sold us and for what share of the usual price: (none yet). "
                   "RULE offer a fifth; a tenth where they took the last offer without complaint. Livestock and grain spoil: refuse them."}

# A trader whose purse reaches this is rich by the village's standards (the others hold a few gold pieces). Such a trader is
# told so in plain words, is no longer held to the things their trade needs, and may buy up to ten pieces of a thing.
# Everyone else stays as they were. (the owner, 2026-10-06: "Detlef does not know he's rich".)
RICH_PURSE = "500 gp"

# Hens eat. Whoever holds hens (a shop, a trader, a character) uses up this much of a sack of barley per hen and day;
# a holder without barley loses each hen with this chance per day. A simple approximation, on purpose.
HENS = {"eats": 0.05, "dies": 0.05}

TOWN_NOTE_WORDS = 160   # the town note, section REQUESTS: one shared scrap of about this many words that every trader reads and anyone may add a line to
TOWN_FLAVOUR_WORDS = 160   # and section TALK: what the villagers scribble for each other (the owner 10-11: more diverse talk), the oldest lines falling off the top
FLAVOUR_SEED = [   # invented (the owner 10-11): what the board might have held in the recent past; a village that has never had a line of talk starts from these
    ("Henrik the tinker", "Mended the same bucket twice this week. It leaks out of spite, I think."),
    ("Gudrun Kellermann", "Cold morning. Barley soup tastes of the field it grew in, and that is the best praise I have."),
    ("Pip the farmhand", "Somebody said I could have the south plot if I stop singing at the hens. Not yet decided."),
    ("Xaver Haberkorn", "Another year, another tax. They count my barrels, I count their sins. We are even."),
    ("Jutta of the Mill", "The eels are quiet. They know something about the weather and will not say."),
    ("Detlef of the Ford", "Hen number nine has taken to sitting on the well. Nobody has asked her to."),
    ("Zeno Zwiebel", "The cellar smells better than it has in years. Please do not tell the tanner."),
    ("Reinhild Sevenbrothers", "Seven brothers, one pot. I have started counting spoons."),
    ("Ivo Zwiebel", "Rain on oak bark: that is the smell of money, if you can wait a year for it."),
    ("Sigrun of the caravan", "Road was dull. Dull is good. Nobody died. Wrote it down anyway."),
]
TIDBITS = {   # one habit of the pen each, so that the small model writes eleven different voices and not one (the owner 10-11)
    "hedwig-d": "signs with a small leaf and writes slowly, as one who has time",
    "henrik": "writes short rhymes about whatever he mends, and they are bad",
    "sigrun": "writes the way she talks: short, flat, no adjectives",
    "vessa": "ends every note with a figure in the margin",
    "gudrun": "describes everything as if it were food",
    "pip": "spells badly and hopes loudly",
    "zeno": "complains about the smell of every other trade",
    "detlef": "reports the hens' news as if it were the village's",
    "xaver": "writes sour little verses against the tax office",
    "hedwig-n": "tells what the lamp saw in the night",
    "hartmut": "never writes more than four words",
    "reinhild": "mentions what her seven brothers have eaten",
    "jutta": "reports what the eels said",
    "ivo": "judges the weather by what it does to his hides",
}
for _bot in BOTS:
    _bot["tidbit"] = TIDBITS.get(_bot["id"], "")
