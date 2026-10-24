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
| 39 | Swarm (38): adjacent friends get extra move, no attack boost | ACTION-TYPES-V123 | L1 | Boost (+1 move; +0.5 atk only v<115) | check |
| 40 | Move onto a hidden enemy: stops, reveals it | MOVE-BLOCKED-HIDDEN | L3 | ? | todo |
| 41 | Tribe with no cities loses its units | NO-CITIES-NO-UNITS | L3 | ? | todo |
| 42 | Breaking peace disbands breaker's units in ex-ally territory | DIPLO-BREAK-DISBAND | L3 | no | todo |
| 43 | Super unit by tribe | SUPER-UNIT-BY-TRIBE | L3/L1 | pf ok | done (pf) |
| 44 | Income = level + capital + Workshop/Park + min(0,pop) | ECON-INCOME | L3 | production field + capital + rewards + progress<0 | check |
| 45 | Siege: city with enemy on centre earns 0 | ECON-SIEGE | L3 | pf ok | done (pf) |
| 46 | Bot bonus: handicap-1 a turn while holding own unbesieged capital | ECON-BOT-BONUS | L3 | missing | done (stars 155 -> 688/819) |
| 47 | Embassy: 5 +2 each further (engine 4, split), income 2 / 4 at peace for host (builder only at peace) | ECON-EMBASSY, EMBASSY-ACTION | L1/L3 | 5 flat, no income | done (engine's L3 version: cost 4 +2 each; host 2/4, builder 4 at peace only); stars 742 -> 744 |
| 48 | Market pays level of each adjacent Windmill/Sawmill/Forge | ECON-MARKET-CLATHRUS | L3 | +1 each | done |
| 49 | Clathrus +1 per adjacent Fungi (card) vs Algae (Polyfish) | ECON-MARKET-CLATHRUS | split, untested | Algae | flag |
| 50 | City level +1 per city reward | CITY-LEVEL-BY-REWARD | L3 | reward.rs | check |
| 51 | Meet stars from the met tribe's score | ECON-MEET | L3 | get_star_exchange | check |
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
| 57 | Bridge carries land units | BRIDGE-LAND | L3 | pf ok (is_steppable) | check |

## Flagged (below L1, off)

- Aquarion unit ids 47, 49-52, 54, 55 (L0): not added.
- Clathrus income source (split): left as Polyfish (Algae).
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

## Findings

- Meeting stars (the biggest star gap left, ~57 player-turns): Polyfish's rule (a tribe meets another at its turn
  start when an enemy unit stands on a tile it has explored) fits the saves; the misses come from exploration that
  Polyfish doesn't reproduce, mostly Explorer rewards (city reward 4, ruin Explorer: random path). Example 09a5bf1e
  t2->4: player 3's explored tiles go 28 -> 87 with only short moves and one Explorer reward. Fix belongs to the
  harness (read the explored set / Encountered from the next save, like the ruin oracle) or sim-dist (Explorer path
  distribution), not a rule port. A "meet after each own move" switch changed nothing (tried, removed).
- Saves: meets are one-way in 124 of 290 new meets (A knows B, B doesn't know A yet).

## Next step

Remaining todo rows: #35 heal others (check), #38 Shaman convert + damage, #39 Swarm, #40 move onto hidden
unit, #41 no cities no units, #42 break-peace disband, #47 embassy, #48 Market by level, #50 city level per
reward (check), #44 income (loader sets production = level; check).
