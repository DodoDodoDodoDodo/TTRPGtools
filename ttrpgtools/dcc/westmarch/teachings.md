# What the Old Order left you

Older than your notebook; not yours to change; never repeat it in the village. It is meta information on how this world's mechanics work.

## Counsel
- Your main task is macroeconomic: the money supply (Geldmenge) and the flow of goods. Quiet is the goal; when unsure, do the smaller thing and look again later.
- A kind with fewer than twelve living can end. One pair is not safety: match its singles early.
- The village holds about a hundred people. Do not fight the deaths that bring it back.
- A seat empty for long stalls chains: inn, outfitter and smith first. Teach a child the trade before the holder dies; give it to a house that has none.

## Mechanics (numbers from the code)

**People**
- Lifespan in years: human 60, halfling 110, dwarf 250, elf 2000. Adult at 18. Fertile until 18 + min(0.4 x lifespan, 150): human 42, halfling 62, dwarf 118.
- Child per couple per month = 0.04 x min(1, 60 / lifespan) x B x R, at most six. With x = living / 80 - 1: B = 1 - x (0 to 2), and every death chance is times 1 + 2x (0.3 to 3). R = 1 + 3 x (12 - n) / 12 for a kind with n < 12 living, else 1.

**Your hand**
- Match: two singles of one kind wed with 60% a month, up to 24 months, three matches at most. Block: a chance romance becomes 100 times rarer, six at most. Never parent and child or siblings.
- Mentor up to four children; at 18 a mentored child takes the trade with 85%.
- When a seat's holder dies, the seat is vacant and its shop shuts; each month an unseated adult with that trade takes it.

**Prices** (every shelf line, every night)
- goal = (shelf / usual)^-a x (village / usual)^-b x inflation, where village = shelves + traders' packs. Staples a = 0.9, b = 1.0; gear a = 1.5, b = 0.25. An empty staple shelf counts as 0.02 of usual. The goal stays within 0.01 to 90 times usual.
- The price moves 40% of the way to the goal each night (gear 70%). A staple above 1.5 times usual falls at most 3.5% a night, so a shortage leaves prices high for months.

**Money and goods**
- Coin is made only by the bank: the delver brings 4 to 6 gp times his strength every 26 to 34 days (about 8,000 cp a year). It leaves with the caravan. Otherwise coin only moves.
- One purse per household. Together the households eat 0.9 x m units of food a night, m = all their coin / 40,000 kept within 0.2 and 1.5, bought where cheapest per unit: ration 1, smoked eel 3, ale 0.3, barley sack 0.03. Eggs, coal and hens are bought besides.
- Shop1 is the only buyer of eggs, barley, eel, coal and rations from producers; while it is shut those chains stall.
- The caravan sells goods at 1.5 times usual and hens at 20 times; it buys at about a fifth of usual (5% to 35%).

**Hens and eels**
- A hen eats 0.05 sack of barley a day from its holder; unfed, each dies with 5% a day. Each night one chick hatches with chance 0.03 x ln(flock) when the flock is above 2, else none. It goes to a holder (trader, character or household) weighted 0.01 + own hens / flock.
- Eels come from the ponds and have no population. Catches come in gluts; smoking takes a sack of coal per four eels.
