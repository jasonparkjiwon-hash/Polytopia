# pf-port (Phase 3 prep, see backlog item 0)

_Owner: pf-port session · started 2026-10-24_

Goal: Polyfish (`sim/pfcore`, written for v115) gets every v123 correction the
Python referee relies on. One rule per commit, each with a Rust unit test
(`src/v123_tests.rs`, built from a real save case where one exists).
Rules at L1+ go in as default behaviour; below L1 behind a flag in
`GameSettings` (off) and listed under "Flagged".

Build: `cd sim/pfcore && cargo build --release` (online works). `cargo test --release`.
`Cargo.lock` gets rewritten by an online build: `git checkout sim/pfcore/Cargo.lock` before committing.

## Fields the loader (pf-loader) must fill for these ports

- `UnitState.direction`: the save's UnitDirection byte 2 **plus 1** (0 = no facing known / never moved).
  Byte 2: 0 NW, 1 W, 2 SW, 3 S, 4 SE, 5 E, 6 NE, 7 N (SAVE-UNIT-FACING).
- `UnitState.ever_moved` (new): true if the log shows the unit moved before the save (push rule; see `prime_last_moves` in engine/replay.py).
- `TribeState.handicap` (new): the save's DifficultyHandicap (1 human/Easy, 2 Hard, 4 Crazy).
- `TribeState.bot`: false for the human (AutoPlay == 0).
- `TribeState.embassies` (new): host player ids this tribe has an embassy with.

## To-do table

Status: **done** = ported with a test; **pf ok** = Polyfish already does it;
**todo**; **flag** = below L1, behind a switch, off.

| # | Rule | Ledger id | Level | Polyfish v115 | Status |
|---|---|---|---|---|---|
| 1 | Poison halves defence, bonus included (no extra x0.7 on defence) | C7 | L3 | def x0.7 AND bonus x0.5 | done |
| 2 | Recover cures poison instead of healing | C7 | L1 | pf ok (heal_unit) | done (pf) |
| 3 | Frozen defender doesn't retaliate | FROZEN-NO-RETALIATION | L3 | retaliates | done |
| 4 | Hidden (Hide) attacker takes no retaliation | CLOAK-DAGGER-RETALIATION | L3 | retaliates | done |
| 5 | No retaliation if defender's tribe can't see the attacker's tile | C20 | L3 | not checked | done |
| 6 | City defence bonus only in own city (not ally's) | DEF-BONUS | L2 | any non-enemy city | done |
| 7 | Splash: half damage floored | SPLASH | L2 | half, not floored | done |
| 8 | Unit stats from v123 cards (Cloak atk 2, Moth def 2, ...) | UNIT-STATS-UI, MOTH-V123 | L3 | v115 values | done (Cloak, Moth; Crab def 5 vs engine 4 open: engine's 4 is calc v116, no card) |
| 9 | Shaman and Mooni have no Static | C29b | L3 | Static | done |
| 10 | Aquarion units 46 Mermaid, 48 Swordsmaid, 53 Shark | AQUARION-UNIT, UNIT-ID-48, UNIT-ID-53 | L3/L3/L2 | missing | done (Shark's unlock waits on #54); pf_miss units 4356/4898 -> 4424/4873 |
| 11 | Aquarion ids 47, 49-52, 54, 55 | AQUARION-UNIT-IDS | L0 | missing | flag (not added) |
| 12 | Giant boards as Juggernaut carrying the Giant; lands as Giant | GIANT-JUGGERNAUT | L3 | Juggernaut with no passenger, never lands | done |
| 13 | Giant boarding as Juggernaut stomps | STOMP-ON-BOARDING | L3 | uses old type (no stomp) | done |
| 14 | Only own port boards | PORT-BOARDS | L3 | any port | done |
| 15 | Boat on Aquarion-flooded land stays a boat; walker stays walker | FLOOD-ALGAE | L3 | boat lands | done |
| 16 | Boat on algae stays a boat | ALGAE-KEEPS-BOATS | L3 | pf ok (algae is water terrain) | done (pf: algae tiles keep water terrain) |
| 17 | Stiff units don't move in after a kill (boats do, and land) | KILL-MOVE-IN, JUGGERNAUT-KILL-MOVE | L3 | every range-1 unit moves in | done |
| 18 | Kill move-in onto mountain needs Climbing | KILL-MOVE-CLIMBING | L3 | pf ok (is_steppable_for_push) | done (pf: is_steppable_for_push / step_unit) |
| 19 | Land unit follows a kill into water only onto own port | PORT-KILL-EMBARK | L3 | pf ok via is_steppable_for_push | done (pf: is_steppable_for_push / step_unit) |
| 20 | Water units don't follow a kill onto dry land | WATER-UNITS | L2 | Water skill only | done |
| 21 | Stomp on kill move-in | JUGGERNAUT-KILL-MOVE | L3 | step_unit stomps | done (pf: is_steppable_for_push / step_unit) |
| 22 | Push direction: saved facing / last move ever, rounded to 8 dirs | PUSH-DIRECTION, SAVE-UNIT-FACING | L3 | prev_coords sign | done (misses 98 -> 81) |
| 23 | Never-moved unit: toward attacker if attacked, else centre by angle | PUSH-NEVER-MOVED | L3 | centre by sign | done (misses 98 -> 81) |
| 24 | Blocked: counter-clockwise side first; no room removes the unit | PUSH-TIEBREAK | L3 | nearer-centre first; removes | done (misses 98 -> 81) |
| 25 | Push onto own port only as first choice; boats not onto land | PUSH-PORT-FIRST, PUSH-ONTO-PORT | L3 | any order; boats onto land allowed | done (misses 98 -> 81) |
| 26 | Push onto mountain needs Climbing | PUSH-TERRAIN | L3 | pf ok | done (pf) |
| 27 | Freeze (Mooni/Gaami move, action 17): water+ocean around, not under units; adjacent enemies frozen | MOONI-FREEZE, GAAMI-FREEZE, MOONI-FREEZE-UNITS, ACTION-17-FREEZE-AREA | L3/L1 | freezes under units too | done |
| 28 | Mooni/Gaami freeze after capturing too | MOONI-FREEZE | L3 | ? | done |
| 29 | Polaris capture freezes own water around the city | POLARIS-CAPTURE-FREEZE | L3 | no | done |
| 30 | Ice Archer hit freezes the target | FROZEN-NO-RETALIATION | L3 | pf ok | done (pf) |
| 31 | Frozen unit sits its next turn out, thaws | FROZEN-NO-RETALIATION | L3 | pf ok (unfreeze + end turn) | done (pf) |
| 32 | Break Ice (action 18) | ACTION-18-BREAK-ICE | L3 | break_ice.rs | done (actor = first eligible own unit next to the target ice; may differ from the logged unit) |
| 33 | Idle auto-recover for the human only | IDLE-AUTO-RECOVER | L3 | every active player | done |
| 34 | Heal 4 own territory / 2 elsewhere | HEAL-TERRITORY | L2 | pf ok | done (pf) |
| 35 | Heal Others (action 4) +4 to adjacent friends | ACTION-4-HEAL | L3 | heal_others.rs | done (pf: heal_others +4 to adjacent friends) |
| 36 | Explode: round then half, poison halves defence, targets poisoned | EXPLODE-DAMAGE, EXPLODE-POISON(-DEFENCE) | L3 | explode.rs | done |
| 37 | Area damage (stomp/splash/explode) spares tribes at peace | PEACE-AREA-DAMAGE | L3 | get_true_enemy_at | done (pf: is_enemy excludes peace) |
| 38 | Shaman converts and also deals damage | SHAMAN | L3 | convert only? | done (+3 units) |
| 39 | Swarm (38): adjacent friends get extra move, no attack boost | ACTION-TYPES-V123 | L1 | Boost (+1 move; +0.5 atk only v<115) | done (pf: Boost = +1 move, no attack bonus at v115+) |
| 40 | Move onto a hidden enemy: stops, reveals it | MOVE-BLOCKED-HIDDEN | L3 | ? | done |
| 41 | Tribe with no cities loses its units | NO-CITIES-NO-UNITS | L3 | ? | done (pf: capture_city removes an eliminated tribe's units) |
| 42 | Breaking peace disbands breaker's units in ex-ally territory | DIPLO-BREAK-DISBAND | L3 | no | done |
| 43 | Super unit by tribe | SUPER-UNIT-BY-TRIBE | L3/L1 | pf ok | done (pf) |
| 44 | Income = level + capital + Workshop/Park + min(0,pop) | ECON-INCOME | L3 | production field + capital + rewards + progress<0 | done: Workshop/Park counted once (stars 744 -> 750); production = level from the loader |
| 45 | Siege: city with enemy on centre earns 0 | ECON-SIEGE | L3 | pf ok | done (pf) |
| 46 | Bot bonus: handicap-1 a turn while holding own unbesieged capital | ECON-BOT-BONUS | L3 | missing | done (stars 155 -> 688/819) |
| 47 | Embassy: 5 +2 each further (engine 4, split), income 2 / 4 at peace for host (builder only at peace) | ECON-EMBASSY, EMBASSY-ACTION | L1/L3 | 5 flat, no income | done (engine's L3 version: cost 4 +2 each; host 2/4, builder 4 at peace only); stars 742 -> 744 |
| 48 | Market pays level of each adjacent Windmill/Sawmill/Forge | ECON-MARKET-CLATHRUS | L3 | +1 each | done |
| 49 | Clathrus +1 per adjacent Fungi (card) vs Algae (Polyfish) | ECON-MARKET-CLATHRUS | split, untested | Algae | done: L3 from 9be1198d (held-out pre-registered test); switch removed, stars 1313 -> 1316/1342 |
| 50 | City level +1 per city reward | CITY-LEVEL-BY-REWARD | L3 | reward.rs | pf: level rises from population, reward follows; harness plays logged rewards (pf-loader) |
| 51 | Meet stars from the met tribe's score | ECON-MEET | L3 | get_star_exchange | pf ok (formula); trigger: see Findings (exploration gap) |
| 52 | Tech cost tier x cities + 4; Literacy 2/3 ceil | TECH-COST | L2 | x0.66 ceil | done |
| 53 | Tribe techs priced at the replaced tech's tier (Polarism, Oceantology 3, ...) | TRIBE-TECH-TIERS | L3 | tier missing -> 1 for most | done (stars 700 -> 719) |
| 54 | Aquarion techs 39, 46, 47 by tier | AQUARION-TECH-TIERS | L3 (tiers) | missing | done (stars 688 -> 700, legal 91.4 -> 91.8%) |
| 55 | Unit/structure/upgrade costs v123 (Enchant 3, Starfish +8, AquaFarm 5, ...) | C19-COSTS, ECON-PRICES-V123 | L3 | Starfish 8 pf ok | Enchant 3 done (stars 720 -> 730); Starfish done (#60); Outpost: see What's left |
| 56 | Ruin stars 10 | ECON-RUIN-STARS | L3 | pf ok | done (pf) |
| 58 | Navigation requires Sailing (base tree) | TECH-TREE | L3 | requires Ramming | done |
| 58 | Navigation requires Sailing (base tree) | TECH-TREE | L3 | requires Ramming | done |
| 59 | Amphibious units onto shallow water / flooded land with no tech | AMPHIBIOUS-WATER (new) | L3 | needs a water tech | done (legal Moves +127) |
| 60 | Starfish: Navigation or the tribe's version (Polar Warfare) | ECON-PRICES-V123 + save count 32/32 | L3 | plain Navigation only | done |
| 61 | Break Ice after a Dash move | ACTION-18-AFTER-MOVE | L3 | not offered | done by pf-loader (d4e40af) |
| 62 | Outpost buildable for 5 (effect still missing) | engine BUILD (star check) | L3 price, effect unknown | refused as unimplemented | done (stars 730 -> 740) |
| 63 | Capture takes the 3x3 (unowned / old owner's), not radius-2 same-owner tiles | CAPTURE-TERRITORY | L2 | city._territory (radius 2, any same-owner tile) | done (+2 units, pf-loader item 9) |
| 64 | A captured capital isn't the captor's capital (+1 income, bot bonus) | ECON-INCOME, ECON-BOT-BONUS | L3 | capital_of moves to the captor | done (stars 740 -> 742) |
| 65 | A city's building income counts only tiles it rules (post_load territories overlap) | ECON-MARKET-CLATHRUS | L3 | counted in every overlapping city | done (Market port 741 -> 742) |
| 66 | Water and amphibious units follow a kill onto water | WATER-UNITS, KILL-MOVE-IN | L2/L3 | only Float units | done (unit misses 29 -> 12) |
| 67 | Cymanti water ruin gives a veteran Boomchi | RUIN-UNIT-CYMANTI | L3 | Rammership + Warrior | done (+1 unit) |
| 68 | Fish harvest with the tribe's Fishing (Aquarion 47, Polaris Frostwork) | save count 14/14, 13/13 | L3 | base Fishing only | done (legal Build 518 -> 545) |
| 69 | Cymanti use base Sailing/Ramming/Navigation/Diplomacy; Raychi via Sailing, Boomchi via Ramming, Algae via Fishing | CYMANTI-TECHS (new) | L3 | Hydrology/Synergy/Oceantology replacements | done (legal 94.8 -> 95.7%) |
| 70 | Peace offers (Strategy, met, one pending per pair) and replies generated; breaker's side RelationState 3 | DIPLO-PEACE | L3 | generation switched off upstream | done (legal 95.7 -> 96.3%; replies to offers pending at a checkpoint need the loader) |
| 71 | Turn income before start-of-turn effects (Fungi growth's level counts next turn) | CITY-LEVEL-BY-REWARD | L3 | income after Fungi growth | done (stars 798 -> 801) |
| 72 | Persist (Knight, Tridention) attacks again after a kill; the kill move-in doesn't exhaust | PERSIST-KILL-MOVE (new) | L3 | step_unit exhausted first | done (legal Attack +8) |
| 73 | Clathrus +1 per adjacent Fungi | ECON-MARKET-CLATHRUS | L3 (9be1198d) | Algae | done, switch removed (stars +3) |
| 74 | Sanctuary costs 3, no star income | SANCTUARY-NO-INCOME (new) | L3 n=1 | 5, +1 per adjacent animal | flag `sanctuary_no_income` (off) 26 Oct: Jason's v123 card says 5 stars, +1 per nearby animal (split; ref-fix settles SANCTUARY-V123, then re-port). A/B 1320 both ways |
| 75 | A convert ends the converter's turn (no idle heal, no second action) | CONVERT-ATTACK, IDLE-AUTO-RECOVER | L3 | converter left idle | done (+1 unit) |
| 76 | Amphibious + Marine Life follow a kill onto ocean | WATER-UNITS, AMPHIBIOUS-WATER | L3 | shallow water only | done (+1 unit) |
| 77 | Fungi save level 0/1 = Polyfish 1/2 (grows once, +1 pop) | FUNGI-GROWTH (new) | L3 | loaded as is: new Fungi never grew | done (CityReward legal +9) |
| 78 | Polaris Outpost network: roads, cities, ports, Outposts, ice within 2 of an Outpost | OUTPOST-NETWORK (new) | L3 (80/83 states) | no Polaris network at all | done (legal +8); ice formed later doesn't re-run the connection update |
| 79 | Aquarion Atoll links own cities/Atolls within 3 | ATOLL-NETWORK (new) | L3 (49/50 states) | none | done (CityReward +5) |
| 57 | Bridge carries land units | BRIDGE-LAND | L3 | pf ok (is_steppable) | done (pf: is_steppable allows bridges for walkers; boats pass under) |

## Flagged (below L1, off)

- `sanctuary_no_income`: Sanctuary costs 3, no income (b2448ead, n=1) vs the v123 card (5, +1 per nearby animal, default). A/B equal (1320/1342). Re-port once ref-fix records the result in games-1-5.md.

- Aquarion unit ids 47, 49-52, 54, 55 (L0): not added.
- ~~`clathrus_fungi`~~ promoted 26 Oct (L3, 9be1198d), switch removed.
- `aquarion_tech_slots` (src/v123_flags.rs; conflicts_and_gaps AQUARION-TECHS, inferred): 47 replaces Fishing
  (opens water), 39 Ramming, 46 Sailing (opens ocean). A/B at d0a5d85: off legal 91.8%, on 92.0% (Move +19,
  Research +7), units/stars equal. Supports the inference; promoting it needs a second source.
- Switches: `PF_FLAGS=name,name` in the environment of pfreplay (tools/pf_miss.py passes the environment).

## Log

A/B = tools/pf_miss.py units exact with the port vs the same tree with only that port reverted
(`ab.sh` in the session scratchpad: `git diff C^ C -- sim/pfcore/src | git apply -R`, rebuild, rerun).
Misses = compared - exact.

- poison (#1): misses 545 -> 542 (+3 exact). Frozen (#3), hidden (#4): not separable (stacked edits), tiny.
- sight (#5), own-city bonus (#6): 0. Splash floor (#7): +1. Cloak/Moth cards (#8): +1 (and 3 fewer missing).
- Aquarion units (#10): 4552/4860 -> 4651/4829 (misses 308 -> 178 at 43a8af1).
- Juggernaut carries Giant (#12): 187 -> 178. Own port boards (#14): 210 -> 178. Stomp on boarding (#13): 0.
- Flooded land keeps boats (#15): 178 -> 170. Stiff stays after kill (#17): 0.
- Water units into a city (#20): 117 -> 98 misses, stars 157 -> 155 (sieges by those units; check when stars are worked on).
- Push rule (#22-25): 70 -> 53 (at 032c9fd, after pf-loader's fixes).
- Freeze (#27), captures freeze (#28-29): units 0, legal +5. Break Ice all around (#32): legal +34. Idle recover human-only (#33): +3.
- Explode (#36): misses 50 -> 36. Bot bonus (#46): stars 155 -> 688. Aquarion techs (#54): stars 688 -> 700, legal 91.4 -> 91.8%.
- Amphibious water (#59): legal Moves +127. Tribe tech tiers (#53): stars 700 -> 719. Starfish (#60): +1 star.
- Enchant 3 (#55): stars 720 -> 730. Outpost (#62): 730 -> 740. Capture 3x3 (#63): +2 units. Captured capital (#64): +2 stars.
- Market by level (#48): -1 star until the ruling-city fix (#65) made the row exact (742). Embassy (#47): +2 stars.
- Shaman damage (#38): +3 units. Hidden bump (#40): +1 legal. Workshop/Park once (#44): stars 744 -> 750.
- pf-port-2 (24 Oct, harness only, `bin/pfreplay.rs` + `tools/pf_jobs.py`; no Polyfish rule changed):
  - Meeting oracle (6c3eb7b): tribes met between the saves come from the next save's Encountered, at the
    economy model's price (`pf_jobs.meet_hints`, ECON-MEET). Stars 750 -> 781, legal 96.5 -> 97.3%.
  - Meetings only from the oracle (423f5ed): while a logged action plays, every tribe "knows" every other, so
    Polyfish's own discovery (turn start, random Explorer path) books none. Stars 781 -> 792.
  - Unmapped Aquarion builds 49/51 charged 5 stars (ECON-PRICES-V123), and a logged CityReward that Polyfish
    didn't have pending levels the city by adding just enough population (LEVEL_FROM_REWARD) (f65efe4).
    Stars 792 -> 798, Train "city full" 1006 -> 1018.

## Findings

- Meeting stars (the biggest star gap left, ~57 player-turns): Polyfish's rule (a tribe meets another at its turn
  start when an enemy unit stands on a tile it has explored) fits the saves; the misses come from exploration that
  Polyfish doesn't reproduce, mostly Explorer rewards (city reward 4, ruin Explorer: random path). Example 09a5bf1e
  t2->4: player 3's explored tiles go 28 -> 87 with only short moves and one Explorer reward. Fix belongs to the
  harness (read the explored set / Encountered from the next save, like the ruin oracle) or sim-dist (Explorer path
  distribution), not a rule port. A "meet after each own move" switch changed nothing (tried, removed).
- Saves: meets are one-way in 124 of 290 new meets (A knows B, B doesn't know A yet).

## Scores (pf_miss)

26 Oct (pf-port-3), at f42844c, games 1-5 released into the tuned set: tuned units 6455/6456, stars 1320/1342,
legal 99.2% (referee on the same set, tools/miss.py: units 6452/6461, stars 1314/1342). Held-out (ed6cb932 only
now) 187/187, 64/64, legal 99.7%.

26 Oct (pf-port-3), at 28ac99e: tuned units 4723/4734, stars 801/819, legal 8846/8972 = 98.6%.
Jason's 5 new held-out games (535a6d8, `pf_miss --holdout`, scored once, not tuned on), Polyfish vs referee
(holdout.json `scored`, at 62666fa):

| game | Polyfish units | stars | referee units | stars |
|---|---|---|---|---|
| 3edee0ec | 409/409 | 142/144 | 409/409 | 141/144 |
| b2448ead | 454/454 | 110/112 | 454/454 | 109/112 |
| 9be1198d | 272/272 | 77/80 | 272/272 | 80/80 |
| 05ade18c | 203/211 | 63/66 | 208/217 | 63/66 |
| 028182a9 | 380/382 | 120/121 | 381/381 | 119/121 |
| total | 1718/1728 | 512/523 | 1724/1733 | 512/523 |

Legal on the held-out set (ed6cb932 included): 3130/3163 = 99.0%. ed6cb932 still 187/187, 64/64.

24 Oct, at f65efe4 incl. pf-legal's moves:

Units exact 4723/4734 (11 misses), stars exact 798/819 (referee 802/819), legal 8801/8972 = 98.1%.
Held-out ed6cb932 (data/holdout.json, scored once by check.sh at f65efe4): units 187/187, stars 64/64, legal 98.9%.
Earlier: at ec8f6da units 4723/4734, stars 750/819, legal 96.3%.
Start of this session (pf-loader's first run): units 4349/4906, stars 162/819, legal 81.8%.

## Split with pf-legal (orchestrator, 24 Oct)

pf-legal owns move generation: peace generation, tribe water/ice/algae movement, tribe train unlocks, fish /
replacement-tech resource gates, Outpost and Aquarion structures 49/51, Explode and ConvertMove generation.
Already done here before the split (don't redo): peace offers/replies (#70, ec8f6da), Cymanti train unlocks
(#69, ec40fcf), fish gate (#68, 4c13187), Outpost buildable (#62, 46a6115), amphibious water (#59), Starfish (#60).
pf-port keeps: economy / star drift, unit HP and position misses, the rest of the table.

## What's left (rule gaps, biggest first)

1. Stars (21 misses). 18 are rows the referee's economy misses too (`pf_stars` "econ itself off": almost all
   6e1bf8e0 t5->11 / t11->15, saves 4-6 turns apart, so the met tribe's score at the meeting is unknown).
   3 rows Polyfish misses but the referee doesn't, each 1 star of income:
   - 09a5bf1e t2->4 p15 Cymanti: a city's population runs 1 ahead in Polyfish, so its CityReward is offered
     before the Fishing that really levels it (income +1 a turn early). CaptureCity/CityReward lines in
     pf_stars are the same 5 stars swapped, not a bug.
   - e15f392c t4->5 and t15->? p14: Polyfish pays 6 a turn, the economy model 5 (level 2 capital + 1 capital
     + 1 Workshop + bonus 1). Was being looked at: dump Polyfish's per-city get_city_production for p14 after
     load (an eprintln behind an env var in run_job, not committed) to see which term is +1.
2. Movement legality (~85 Moves): Cymanti water units leaving a city 2-3 tiles onto water/algae; Polaris
   skating 2-3 tiles from a city onto ice; Mermaid onto ocean (ocean is innate for Aquarion, Jason 26 Oct (no tech); was open:
   AMPHIBIOUS-WATER); a few boats into a port.
3. Explode not offered (13), Attack "already attacked" (Knights, HP drift), Train "city full" (downstream).
4. Peace replies to offers pending at a checkpoint (11): the loader needs the save's DiplomacyMessages.
5. ~~Outpost effect~~ done (#78, OUTPOST-NETWORK); ~~Clathrus~~ done (#73).
6. Unit misses (11): af181c8f t16 ruin Swordsman hint (harness, noted in pf-loader.md), 6e1bf8e0 HP drift.

## pf-port-3 notes (26 Oct)

- Harness (tools/pf_jobs.py ruin_hints): a ruin Swordsman that walked off or died before the next save is found
  from its first logged Move starting on the ruin tile (new unit; boat passengers count as old). Fixed the
  af181c8f t16 chain (5 misses) and 6e1bf8e0 t7 (Giant 231 HP).
- Last unit miss: 6e1bf8e0 t11->15 Swordsman 198 (#1623-1624: two attacks on (7,3) where neither Polyfish nor
  the referee has a defender; the referee is exact only because it moves units by id). Drift in the 4-turn gap.
- Stars: all 22 misses are rows economy.py misses too ("econ itself off"; 6e1bf8e0 gaps, meetings, b2448ead
  t7->8 siege: the game paid a city with a Hoodrick unit on it, ECON-SIEGE test item).
- CityReward "not pending" (42 left) by cause, from saves' ConnectedPlayerCapital: cities newly connected to
  the capital via Polaris Outposts (09a5bf1e t5, af181c8f t8/t13), Aquarion Atoll 51 (3edee0ec t9, 6e1bf8e0 t11,
  e15f392c t4) and ports (09a5bf1e t7, e15f392c t5/t8, af181c8f t21); 3 lighthouse discoveries (af181c8f t8,
  6e1bf8e0 t11); the rest unexplained so far.

## Next step (pf-port-3 handoff, 26 Oct)

Scores at 8bbd5bc: tuned units 6455/6456, stars 1320/1342, legal 11704/11781 = 99.3% (CityReward 332/366);
held-out ed6cb932 187/187, 64/64, 99.7%. The referee on the tuned set: 6452/6461, 1314/1342.

1. CityReward "not pending" (34 left): Polaris capitals that need 2 population after an Outpost connection
   (09a5bf1e t5 #533/#537, af181c8f t8 #795: maybe the Outpost itself gives population); cities connected by
   ports (Build 8: e15f392c t5 Yadakk, 09a5bf1e t7 Hoodrick, af181c8f t21 Quetzali; Polyfish's standard branch
   only follows roads); captures (e15f392c t8 Vengir); Kickoo/Zebasi/others unexplained. Recipe: the scratchpad
   scripts in this session were throwaway; `ConnectedPlayerCapital` per city in consecutive saves tells
   connection events apart from other population sources.
2. Jason 26 Oct: an Outpost can only be built on ice (OUTPOST-ON-ICE; the saves agree, 23/25 on ice when first
   seen, the 2 on water had their ice broken or thawed afterwards; Polyfish already ice-only). Open: does the
   network still run through an Outpost whose ice is gone (af181c8f t14 says yes, t15-18 (9,16) disconnected)?
   Polaris connection update when ice forms (freeze moves) and when it breaks (af181c8f t14->16 (9,16)
   disconnected again); OUTPOST-NETWORK misfits listed in the ledger.
3. Stars: nothing Polyfish-only left (all 22 misses are economy.py misses too).
4. Last unit miss 6e1bf8e0 t11->15 Swordsman 198 (gap drift, see pf-port-3 notes).

## Next step (older)

(pf-port-2, 24 Oct) Next session: the e15f392c p14 +1 income (above), then the 11 unit misses (6e1bf8e0 HP
drift; Knights "already attacked" 9 = HP drift; af181c8f t16 is the harness ruin hint), then item 5 (Outpost
effect). Note: the meeting oracle reads the next save, so it's for replay scoring only; a forward model
running without a next save keeps Polyfish's own meeting rule (sim-dist: Explorer path distribution).

Older:

Movement, Explode, Convert, Outpost and 49/51 belong to pf-legal (pf-legal.md). pf-port next: star drift
(`tools/pf_stars.py`: city rewards Polyfish doesn't offer, "econ itself off" rows in 6e1bf8e0) and the 11 unit
misses (6e1bf8e0 HP drift; af181c8f t16 is the harness ruin hint).
