# diff-test (28 Oct 2026)

_Owner: diff-test · state: handoff 28 Oct (see the end)_

Order from Jason: chase the last engine misses with new methods (differential testing, residual clustering, hypothesis search, leave-one-game-out), not by tracing one by one.

## Tool: `python3 -I tools/engine_diff.py [--turns] [--game <id>] [--pickle f]`

Runs the referee and Polyfish on every checkpoint pair of all 18 games (held-out too, marked H) and sorts every unit row and every player's stars into:
both-right / ref-only (Polyfish wrong) / pf-only (referee wrong) / both-same (missing in both) / both-differ. 16 s.
Note: referee rows with an integer HP (`10` not `10.0`) are oracle-placed spawns (INFILTRATE-SPAWN reads the next save), so "ref-only" there is not a real referee win.

## Results

| Date | Finding | Class | Kept |
|---|---|---|---|
| 28 Oct | Quetzali Pirate/Raft (710ddb20 t18->19): a boarding Dagger becomes a Pirate | pf-only | already pushed by web-deep (PIRATE-BOARD); same cause found independently here |
| 28 Oct | Two Warrior HP rows (710ddb20 id439, 64795ee3 id1): a unit that captured / examined ruins is not idle | pf-only | already pushed by web-deep (CAPTURE-RUIN-ACT); same cause found independently here (Polyfish's `end_unit_turn` in the capture/ruins moves) |

Lesson: web-deep reads the same Polyfish source, so pf-only rows get fixed twice. Pull before starting a fix; the tool's value from here is the both-same / both-differ rows and the clustering below.
| 28 Oct | Game 8 t9->10 Kiton 177 / Swordsman 161 ("predicted kill that doesn't happen"): the Kiton had +4 from its own Mycelium after its attack, so it had 10 HP, not 6. The fight arithmetic (dmg 7, retaliation 6, no defence bonus) fits exactly | both-differ (referee no heal, Polyfish healed at every player's turn end) | MYCELIUM-HEAL (`RULES.mycelium_heal`=4, radius 1): units 10187 -> 10189 (-3 rows -> 3 fewer misses incl. the denominator), no game worse, held-out unchanged; Polyfish fixed too (once per unit, owner's turn only): pf units 10179/10207 -> 10184/10205 |
| 28 Oct | Game 8 t7->8 IceArcher 70 ("Rider hit should kill a 5-HP archer"): the archer was never at 5 HP. Its own hit froze the adjacent Warrior, and a frozen unit does not hit back (no 5 retaliation). The Rider's later hit of 6 (no retaliation: Stiff, no bonus) leaves 4 = the save | both-same (nothing in either engine) | FREEZE-BEFORE-RETALIATION (`RULES.freeze_blocks_retaliation`): units 10189 -> 10190, no game worse; ported to Polyfish (pf 10184 -> 10185) |
| 28 Oct | 9906f7da t17->18 Jason p1 stars -2: the (1,9) embassy vanished with no attack or capture between 1 and 9; p9's Shark had just stepped onto Jason's city (2,27). The only entry-into-partner-city event in 18 games | star both-same | EMBASSY-DESTROYED-BY-ENTRY (`ECON_RULES.embassy_entry_destroys`, n=1): stars 1946 -> 1947, no game worse. Not ported to Polyfish (it has no embassy-destroyed-by-combat either; pf stars 1938) |
| 28 Oct | 710ddb20 Centipede chain rows (t16->17 extra Segment; t17->18 Segment position, missing 547, extra): (a) the chain stops at 3 segments; (b) the second displacement (kill move-in) shifts a 1-segment chain once more, no more growth | unit both-same / both-differ | CENTIPEDE-CHAIN extended (`RULES.cent_cap`=3, `cent_second`='shift_maxseg1'): units 10190 -> **10191/10191, every unit exact**, no game worse, held-out 187/187; a 15-variant grid, 'fresh promoted head' fits as well as 'chain of 1' (n=1+1). Not ported to Polyfish (its chain rows: see pf_miss --list) |

## Method notes (what paid off)

- **engine_diff** (differential): the pf-only rows were all fixable from Polyfish's code in minutes (Pirate, idle heal). Both-differ rows pointed to the Kiton fight; reading Polyfish's end-of-turn code found the missing Mycelium rule.
- **rule_search** (`tools/rule_search.py`, hypothesis search + per-game deltas = leave-one-game-out): 10 Mycelium variants in 18 s. Only amount 4 / radius 1 fixes all three rows (3 and 5 fix fewer, radius 0 and amount 2 none, radius 2 breaks 09a5bf1e). A peaked response like that is the sign the rule is real, not a fit to one fight.
- **residual** (`tools/residual.py`, clustering): units 10.4k rows, 8-13 misses: nothing to cluster. Stars one-turn gaps: 10 misses, only weak late-game / many-cities lift (round 15-19: 6 of 10, 6.5x). Not a single rule: the rows are in 4 games with different causes.
- Tried and rejected with rule_search: siege by ADJACENT enemy units (radius 1 or 2, all cities or capital only) to explain 9906f7da t18->19 p1 (-5): +188 to +519 star misses.
- 9906f7da t18->19 p1 -5 stays open: Jason's capital paid 0 at round 19 (nothing on the tile, enemy adjacent at (4,25), city 2 captured the same round), the embassy + peace offer he made that turn price as modelled (OfferPeace/embassy windows are exact 31/33).
- **Embassy income timing (open, 9906f7da p9 t14->15 and t15->16, -2 each):** Jason built an embassy at p9 in round 14 and round 15 (p1 acts first, p9 later in the same round); p9's income at its turn start is 2 lower than modelled both times. A variant "an embassy built this round pays its host only from the next round" (`embassy_fresh`) fixes those two rows but breaks four others where a same-round embassy DID pay the host (09a5bf1e t7->8 p7, 9906f7da t6->7 p9 and t18->19 p9, 6e1bf8e0 t11->15 p7): net -2 stars. Relation state (neutral/peace), rebuild-after-destruction and order in the round do not separate the two groups. Needs a controlled in-game test (see Waiting on Jason): build an embassy in a foreign capital at neutral, note the host's stars at the start of its turn in the same round. Switch removed again.
- **Infiltration spawn placement (open, 5 cases, 9 placements):** replayed to the action with the exact free tiles. What each simple ordering explains: smallest tile index first among allowed tiles: g8 t9 (Mountain with Climbing), 710ddb20 t19 (7,24),(8,24), 9906f7da Mermaid Daggers (mountain excluded, no Climbing) = 3 of 5; fails 710ddb20 t9 (second egg (9,25), not (8,24)) and t16 (the 4th Dagger (17,18) on the outer ring while (17,17) is free). "Within Chebyshev 1 of the infiltrator's own tile" explains t16 (all four) but not the others. PF's popped-largest-index order explains none for non-Aquarion tribes. n is too small to separate rules; random is not ruled out (same conclusion as pf-port). Placement stays read from the next save (INFILTRATE-SPAWN). A sixth case with the free tiles known would settle it.

## Open after this session (for the next rule session)

- **Referee units: none** (10191/10191 on the tuned games, held-out 187/187). **Polyfish units** 21 rows (`python3 -I tools/pf_miss.py --list`): Centipede chain (cap 3 and the one-segment second shift are not ported), egg/Dagger placement, game 8 t8->10 fights.
- **Referee stars: 25 of 1972.** 14 are 6e1bf8e0 (4-6 turn gaps, meeting stars; unsolvable without in-between saves). Single rows: 9906f7da p9 t14/t15 (-2, embassy income timing, above), 9906f7da p1 t18 (-5, capital paid 0), 710ddb20 p3 t16 (+2: a Cloak infiltrated a level-4 city the same window; the 9906f7da Scuba case pays the level exactly, the Cloak case pays 2 more) and t18 (-1: the captured city has population -1), p2 t17 (-7), p9 t9 (-2), 64795ee3 p12 (-1), af181c8f t10->12 (2-turn gap), e15f392c p5 (-4, trade route).
- **Polyfish stars 1938/1972** (referee 1947): it has no embassy-destroyed-by-combat / by-entry rule and no ruin-city; not ported.

## Needs Jason (one in-game test each, if he wants these rows closed)

1. Embassy income timing: build an embassy in a foreign capital at neutral; write down the host's stars at the start of its turn in the SAME round and the next one (9906f7da p9 t14/t15 say not paid the first round, other games say paid).
2. Infiltration: after any Cloak/Dagger infiltration, a screenshot of the free tiles around the city before the attack and where the Daggers/Eggs appear (placement rule), and the stars gained.

## Methods scoreboard

| Method | Result |
|---|---|
| 1 differential (`tools/engine_diff.py`) | Found 3 of the 6 kept rules' leads (Warrior idle heal, Pirate, Kiton/Mycelium); web-deep found the first two in parallel from the same Polyfish source. 10 min per lead. |
| 2 residual clustering (`tools/residual.py`) | Units: nothing to cluster (8-13 misses in 10.4k rows). Stars: late rounds / many cities, p<0.001 but not one rule; led to the embassy windows via the OfferPeace/Embassy lift. |
| 3 hypothesis search (`tools/rule_search.py`) | Settled MYCELIUM-HEAL (amount/radius grid), FREEZE order, CENTIPEDE cap and shift, EMBASSY entry; rejected siege-by-adjacency (+188..+519) and fresh-embassy timing (-2 net). 10-15 variants in under a minute. |
| 4 per-game deltas | Built into rule_search (any game worse = not KEEPABLE, held-out checked). |

## Jason's pasted Centipede text (28 Oct, source not given) tested against the saves

It says: no length cap; a segment is added only when the head makes a kill, on the tile it vacated; 0 segments = move 2, 1+ = move 1. Replayed as variants (`tools/rule_search.py`): growth only on kill = +2 unit misses (710ddb20), no cap = +1, so the saves disagree with both claims (segments appeared on plain moves, and a 3-segment chain did not get a 4th on t16->17). The movement part (2 then 1) is consistent with the saves but untested here. Kept: cap 3, growth on every head move. If the text comes from the game's own card, the cap row may be a different mechanism (e.g. the exploded tail on t16->17 consumed the new segment); the variant was not run with that reading.
