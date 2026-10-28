# diff-test (28 Oct 2026)

_Owner: diff-test · state: in progress_

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

## Method notes (what paid off)

- **engine_diff** (differential): the pf-only rows were all fixable from Polyfish's code in minutes (Pirate, idle heal). Both-differ rows pointed to the Kiton fight; reading Polyfish's end-of-turn code found the missing Mycelium rule.
- **rule_search** (`tools/rule_search.py`, hypothesis search + per-game deltas = leave-one-game-out): 10 Mycelium variants in 18 s. Only amount 4 / radius 1 fixes all three rows (3 and 5 fix fewer, radius 0 and amount 2 none, radius 2 breaks 09a5bf1e). A peaked response like that is the sign the rule is real, not a fit to one fight.
- **residual** (`tools/residual.py`, clustering): units 10.4k rows, 8-13 misses: nothing to cluster. Stars one-turn gaps: 10 misses, only weak late-game / many-cities lift (round 15-19: 6 of 10, 6.5x). Not a single rule: the rows are in 4 games with different causes.
