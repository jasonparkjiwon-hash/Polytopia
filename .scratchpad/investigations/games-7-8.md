# Jason's games 7 and 8 (ingested 2026-10-27)

_Owner: ingest session · state: ingested, held-out scored, released for tuning 27 Oct, referee fixes kept (below)_

Source: Jason's Google Docs 'Polytopia Game 7' (18IWmx...) and 'Polytopia Game 8' (18VWmQ...), fetched fresh 27 Oct
(game 8 had 10 saves, game 7 had 20). One save per turn; the doc has one note from Jason (Moth makes Insect Eggs, see below).
All blobs decoded. Game 7's t10 blob had a note line glued under it (stripped before decoding). No duplicates in `saves_raw/`.

| | Game 7 `710ddb20` | Game 8 `64795ee3` |
|---|---|---|
| Map | "Lights of Shalosa", 30x30, 25% water | "Square of Daumpo", 30x30, 1% water (land map) |
| Players | 16 (Jason + 15 bots, all 16 tribes) | 16 (Jason + 15 bots, all 16 tribes) |
| Jason | p1 **Cymanti** | p1 **Elyrion** |
| Difficulty | header Difficulty 2, bots DifficultyHandicap 2 (Hard) | header Difficulty 3, bots DifficultyHandicap 4 (Crazy); Jason 1 |
| Turns | t1-t19 every turn (t0 pre-StartMatch left out) | t1-t10 every turn (doc starts at t1) |
| How far | t19: bots have 1-8 cities each, Giants (4), Juggernauts (3), Bombers (3), Mind Benders, Catapults, Centipede; Jason 4 cities, 11 kills | t10: early game only, bots 3-5 cities, Swordsmen/Warriors/Riders, Polytaurs, first Ice Archers; Jason 3 cities, 66 stars |

t1 check (like game 6): both t1 saves parse clean (0 unparsed bytes) and their action list is an exact prefix of t2's, so t1 is kept.

## Held-out score (before any rule change, rules commit 6c1a03a)

- Game 7: units 1950/1982, stars 284/288. Game 8: units 824/832, stars 139/144.
- Polyfish on the same pairs (`tools/pf_miss.py`, same commit): game 7 units 1956/1985, stars 283/288;
  game 8 units 822/833, stars 140/144. Legal: 4883/4894 logged actions legal (99.8%) over all held-out games.
- Plain `tools/miss.py` stayed 7389/7392, 1515/1540 with the two games held; `check.sh` passed. Released for tuning the same day
  (after the scores were recorded, `data/holdout.json`).

## What was new

- **Cymanti Moth = Cloak with Insect Eggs.** Jason's note, confirmed: a Moth attacking an enemy city is used up and Insect Eggs
  (10 HP) appear on free tiles of the city's border (2 for a level-2 city). 5 cases in 3 places (game 7 t8, t18; game 8 bot t9).
  It pays no stars. One counter-case (6e1bf8e0 t11): a Moth hitting a city its own side had lost just attacked. Ledger MOTH-INFILTRATE.
  Jason asked for the Moth's stat picture: not here yet.
- **Centipede + Segments.** Jason's Centipede drags a chain of 10-HP Segments (Leader/Follower ids are in the save). Ledger CENTIPEDE-CHAIN.
- **Quetzali Pirate/Raft:** a Quetzali unit 'Pirate' (10 HP) turns into a 1-HP 'Raft' record at (21,18) (t18->19, left open).
- **Embassies:** three built by bots in Jason's capital (p4 t7, p9 t12, p3 t13); peace actions (type 28) 8 in game 7, 3 in game 8.
- **Sanctuaries:** 12 on the game 8 map (3 built by players), no level readings needed yet; Forest Temple built once (price 15, new).
- Not seen: Lost City, Oceanology/Pescetism research by Jason, trained Jelly/Shark, new unit/structure/tech ids (every id is known:
  46/48 are the Aquarion Mermaid/Swordsmaid in `engine/state.py`; type 38 is the known Cymanti action).
- Action 38 (Cymanti, meaning TBD) appears twice in game 8 (p6).

## Held-out misses, classified (before fixes)

Game 8 units (8): Moth extra (Moth consumed by infiltration), Insect Egg missing (egg spawn), Warrior pos (follows the Moth case),
IceArcher id70 missing (Polaris spawn, t7->8; not a trained unit in the log), Warrior HP 5 vs 7 (t8->9), Swordsman 161 position+HP
and Kiton 177 missing (a Kiton vs Swordsman fight at (10-11,15), t9->10).
Game 8 stars (5): p15 -15 (**Forest Temple price**), p1 +4 and +2 (**meeting stars scored with the wrong save's score**), p6 +4
(**Cymanti tech 49 priced tier 3, really tier 2**), p12 -1 (open).
Game 7 units (32): 2 Moth extra + 4 Insect Eggs missing (**Moth infiltration**), 4 Quetzali Daggers missing (**infiltration spawn**,
same as game 6), ~16 Segment/Centipede rows (**chain**), Pirate/Raft (2), Warrior HP x2 and Polytaur HP (fight rows, open).
Game 7 stars (4): p9 -2 (an Upgrade, open), p3 +2 and -1 (Quetzali: Port/Research mix, open), p2 -7 (Zebasi, income vs siege/capture timing, open).

## Referee fixes kept (each A/B against the full `tools/miss.py`; older games never worse)

| Fix (ledger id, switch) | Units | Stars |
|---|---|---|
| MOTH-INFILTRATE (`replay.RULES.moth_infiltrate`, `ECON_RULES.moth_infiltrate=False`) | held-out extras gone, 1-6 unchanged | hold (paying the city level made game 7 worse by 2 twice) |
| INFILTRATE-SPAWN (`RULES.infiltrate_spawn`): Daggers/Eggs placed where the next save shows them | 10163 -> 10171 -> 10175 (game 6 all 937 exact) | hold |
| CENTIPEDE-CHAIN (`RULES.centipede_chain`) | 10175 -> 10183 | hold |
| FOREST-TEMPLE-PRICE (`economy.BUILD[18]` = 15) | | 1938 -> 1939 |
| MEET-SCORE-TURN (`ECON_RULES.meet_score_by_turn`; one-turn gaps only, all gaps made 6e1bf8e0 and af181c8f worse) | | 1939 -> 1943 |
| CYMANTI-TECH-49 (`economy.TIER['Oceantology']` 3 -> 2) | | 1943 -> 1944 |

**Totals now (games 1-8, plain `tools/miss.py`): units 10183/10196, stars 1944/1972.** Game 7 units 1966/1974, stars 284/288;
game 8 units 825/830, stars 143/144; games 1-6 unchanged (units 7389/7392).

## Left open (for the next rule session)

- Centipede: a 3-segment chain lost its tail the next turn (t16->17); a newly promoted head laid its trail differently (t17).
  Cap on segments? Needs a second Centipede game.
- Game 8 t9->10 Kiton/Swordsman fight, t8->9 Warrior HP 5 vs 7, IceArcher id70 (Polaris spawn).
- Game 7 t18->19: Pirate/Raft, two Warrior HP rows. Stars: Zebasi p2 -7 (t17->18), Quetzali p3 (t16->17 +2, t18->19 -1), AiMo p9 -2 (Upgrade), p12 -1.

## For the Polyfish side (not edited here; `sim/pfcore` rule code untouched)

- MOTH-INFILTRATE: Cymanti Moth attacking an enemy city = Cloak infiltrate; units used up, Insect Eggs (not Daggers) on free border tiles, no stars.
- CENTIPEDE-CHAIN: head moves -> segments shift into the tile their leader left, new Segment on the old tail tile; head dies -> first
  segment becomes the Centipede with 20 HP.
- FOREST-TEMPLE-PRICE: 15. CYMANTI-TECH-49: tier 2 price. MEET-SCORE-TURN: meeting stars use the met tribe's score in the later save
  when the meeting falls in the later save's own turn (one-turn gaps).
