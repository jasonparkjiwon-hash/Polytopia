# Jason's games 1-5 (ingested 2026-10-26)

_Owner: ingest session · state: ingested, held-out scored, released for tuning 2026-10-26_

Source: `.scratchpad/inbox/2026-10-26_games1-5.zip`, five PDFs ("Polytopia game 1-5"), each a list
of device path + base64 save. All 49 blobs decoded cleanly; **the PDFs hold no notes from Jason**
(no text besides paths and base64). The turn-0 saves (pre-StartMatch, games 2-5) were dropped:
the t1 save holds the same start. Kept: 46 per-turn saves, `saves_raw/<id>_t<N>.state`.

## The games (all v123, 30x30, Hard, Jason human as p1, one save every turn)

| Game | Save id | Map | Jason | Players | Turns | Water |
|---|---|---|---|---|---|---|
| 1 | 3edee0ec | Wrath of Fiasji | Aquarion | 16 (all tribes) | 1-10 | 84% (62% ocean): waterworld-like |
| 2 | b2448ead | Fields Adventure | Elyrion | 16 | 1-8 | 26% |
| 3 | 9be1198d | Cliff & Love | Cymanti | 10 | 1-9 | 49% |
| 4 | 05ade18c | Lyuhian Pond | Polaris | 11 | 1-7 | 62% (mostly shallow) |
| 5 | 028182a9 | Magnificent Songs | AiMo | 11 | 1-12 | 85% (69% ocean) |

## Held-out score (before any change, rules commit 62666fa)

| Game | Units | Stars |
|---|---|---|
| 1 3edee0ec | 409/409 | 141/144 |
| 2 b2448ead | 454/454 | 109/112 |
| 3 9be1198d | 272/272 | 80/80 |
| 4 05ade18c | 208/217 | 63/66 |
| 5 028182a9 | 381/381 | 119/121 |
| Total | 1724/1733 | 512/523 |

## Held-out misses, classified (for the rule-fixing sessions)

Units (9, all game 4): **unit id 47 unknown to the engine** (AQUARION-UNIT-47). 6 "type" misses are
bookkeeping (a trained 47 is stored as `47`, the save snapshot as `unit47`); the rest need its stats:
- t5->6 Warrior id7 8.0 (engine) vs 5.0 (save): unit 47's attack; t6->7 Warrior id7 missing (killed by a 47).
- t6->7 unit 47 id54 6.0 vs 7.0: its defence (or the attacker's damage against it).
- Fix: name 47 (Mermaid Archer) in `engine/state.py`, price 3, stats from Jason's card (atk 2, def 1, mov 1, range 2, Dash, Fortify), then A/B.

Stars (11):
| Miss | Cause |
|---|---|
| 4 05ade18c t4->5, t5->6, t6->7 p5 -3 | unit 47 price 3, not in the engine (AQUARION-UNIT-47) |
| 1 3edee0ec t8->9 p1 -8 | Waterways (tech 48) has no tier; tier 2 x 2 cities + 4 = 8 (AQUARION-WATERWAYS-ID) |
| 2 b2448ead t4->5 p1 -3 | Sanctuary (build 32) unpriced; costs 3 (SANCTUARY-V123) |
| 5 028182a9 t8->9 p1 +1 | Clear Forest (build 10) unknown; gives +1 (CLEAR-FOREST-V123) |
| 5 028182a9 t3->4 p1 +2 | met a tribe: meeting stars one band (2) short; the known ECON-MEET score-timing miss |
| 2 b2448ead t7->8 p1 +1 | siege: a Hoodrick unit stands on Jason's non-capital city (4,9) when his income is paid; engine drops the city (ECON-SIEGE), the game paid it. n=1; maybe siege needs war/meeting, or the unit arrived after payment. Test item |
| 2 b2448ead t6->7 p1 +3 | meeting turn (met 1, engine pays 5); +3 is not a band step: open (second meeting? Sanctuary?) |
| 1 3edee0ec t5->6 p1 +1, t9->10 p1 +1 | both turns Jason (Aquarion) examined a water ruin with no reward signal (distributions: "unresolved"); +1 unexplained. Candidates: ruin pop to a non-capital city, Atoll (51) built twice at t9 |

## What the games contain (wanted list in status.md)

- **Every-turn exports:** yes, all five.
- **Water ruins:** 10 new (game 1: 6, game 5: 4). Classified by `tools/distributions.py --rows`:
  pop 4, tech 2, unit 1 (Rammership), unresolved 3 (two are Jason's, above), explorer 0.
  Note: 3 of them were frozen by Polaris first and are logged as terrain "Ice", which the tool
  does not count as water. Land ruins: 14 (tech 4, explorer 4, unit 3: Mantis, Swordsman x2, pop 1, stars 1, unresolved 1).
- **Sanctuary:** yes, game 2 (Jason's Elyrion, (4,11), turn 4). See SANCTUARY-V123: cost 3, a
  Level counter on the tile (2, 1, 1, 2 for t5-t8), one animal (Game) respawned next to it at t7->8
  where an enchanted one had been taken. Spawn rule still open: needs more turns.
- **Waterways id:** 48 (game 1, Jason, turn 8), tier 2.
- **Atoll (structure 51) and Aqua Farm (49):** game 1 Jason built Aqua Farm (17,21) t6 and Atolls
  (18,20), (16,20) t9 (last save t10, so one turn after); game 3 bot p6 Aquarion built Aqua Farm (9,3)
  t5 and an Atoll (10,5) t6. Raw data for status.md item 2 (Atoll population); not analysed yet.
- **Market and Clathrus income:** tested and pass (ECON-MARKET-CLATHRUS); `tools/rule_levels.py`
  now lists only the embassy step as untested.
- **New ids:** unit 47 (Mermaid Archer), build 10 (Clear Forest), build 32 (Sanctuary), tech 48
  (Waterways). Seen before: techs 39/45/46/47, builds 46 (Starfish), 49, 51.
- **Not in these games:** embassies
  (Diplomacy researched by bots in games 1 and 5, none built), peace offers, Oceanology (id 49) research.

## Next

- Rule sessions: the five fixes in the table (unit 47 name/price/stats, Waterways tier, Sanctuary
  price, Clear Forest +1), each A/B'd with `tools/miss.py` (these games are now training data).
- sim-dist: re-run `tools/distributions.py` (adds 24 ruin events, 10 on water) and count Polaris-frozen ruins as water.
- Still wanted from Jason: an embassy (two in one game for the price step), Oceanology research,
  peace, a Sanctuary game played on for more turns. (Giant on a port: answered by Jason, GIANT-ON-PORT.)

## Kept rule fixes (ref-fix, 26 Oct), for the Polyfish port

| # | Ledger id | Change | miss.py total after (units, stars) |
|---|---|---|---|
| 1 | AQUARION-UNIT-47 | `engine/state.py` names unit 47 `MermaidArcher`; stats and price 3 from the v123 card in `data/measured_ui.json` | 7372/7439, 1490/1540 |
| 2 | AQUARION-WATERWAYS-ID | `engine/economy.py` `TIER["Waterways"] = 2` (tech 48) | 7372/7439, 1491/1540 |
| 3 | SANCTUARY-V123 | `engine/economy.py` `BUILD[32] = ("Sanctuary", 3)` | 7372/7439, 1492/1540 |
| 4 | CLEAR-FOREST-V123 | `engine/economy.py` `BUILD[10] = ("ClearForest", -1)` (gives 1 star) | 7372/7439, 1493/1540 |
| 5 | EMBASSY-INCOME-NEUTRAL, EMBASSY-DESTROYED-BY-COMBAT | `engine/economy.py`: `EMBASSY_FROM_SAVE` (host Diplomacy EmbassyLevel > 0 = standing embassy in save a), `EMBASSY_BUILDER_PAID = True` (builder +2 while neutral), `EMBASSY_COMBAT_DESTROYS` (an Attack on, or capture of, the other side ends it) | 7372/7439, 1505/1540 |
| 6 | SANCTUARY-V123 | `engine/economy.py` `SANCTUARY_INCOME`: price 5 (v123 card) and +1 a turn per adjacent Game tile present in both saves and not hunted/enchanted between; spawn every 2 turns not simulated | 7372/7439, 1506/1540 |
| 7 | AQUARION-UNITS-49-52 | `engine/state.py` names 49 MermaidDefender, 50 Scuba, 51 MermaidDagger, 52 Jelly (card stats/prices from `data/measured_ui.json`) | 7385/7397, 1508/1540 |
| 8 | INFILTRATE | `engine/replay.py` RULES `infiltrate`: Cloak/Scuba attacking an enemy city deals normal damage, no retaliation, and is removed (Polyfish uses a fixed 2: split) | 7385/7396, 1508/1540 |
| 9 | WATER-TEMPLE-PRICE | `engine/economy.py` `BUILD[19] = ("WaterTemple", 20)` | 7385/7396, 1510/1540 |
| 10 | ECON-EMBASSY | `engine/economy.py` `EMBASSY_STEP_OTHER_HOSTS`: a rebuild at the same host pays the base price (the +2 step counts other hosts only) | 7385/7396, 1511/1540 |
| 11 | AQUARION-UNITS-49-52 | `engine/stats.py` `MermaidDagger`: 10 HP, 2/2, Surprise Static Dash (Polyfish; no card) | 7386/7396, 1511/1540 |
