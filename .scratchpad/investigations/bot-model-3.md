# bot-model-3: bot policy v3 (task 3 of the 27 Oct plan)

_Owner: bot-model-3 session · 2026-10-27 · state: v3 shipped (`data/bot_policy_v3.json`), v2 stays selectable_

## What was done

1. **Re-dump over all games** (`python3 -I tools/bot_dump.py DUMP.jsonl --all`, 3 min, 700 MB: keep in scratch). 14 games have bot
   decisions (17 538 bot decisions whose logged move Polyfish lists); Hard 9 games, Crazy 4 (`09a5bf1e`, `64795ee3` = game 8, `6e1bf8e0`,
   `ed6cb932`), one Easy-handicap game. Dump lines now also carry the stage-1 features per group (`gf`, so Python never mirrors Rust),
   the mover's handicap, stars and the cheapest affordable unit.
2. **Split (never fitted on test):** TEST = `ed6cb932` (all of it, Crazy, turns 1-4, n=342) + game 7 `710ddb20` turns 12-19 (Hard, n=1566).
   TRAIN = the other 15 630 decisions (3 624 Crazy), including game 7 turns 1-11 and all of game 8. I kept game 8 in training because
   Crazy has three more games; the Crazy test is thin (one game, 4 turns).
3. **Model** (same two-stage logit, weights in one sparse name table, interpretable): new features (`botpolicy2.rs`, `ext`):
   - **Bug found:** v2's "free village" set looked for unowned *city* tiles; free villages are tiles with the Village structure, so
     v2's `Step.village_gain` etc. were constant 0. Fixed for ext (v2 behaviour unchanged for v2 files).
   - Step (which tile): inverse distance to villages / enemy cities / foes / ruins, stepping onto a village / ruin / enemy city,
     **claiming** (gain toward the nearest village counts only if this is the closest own unit to it: BOT-VILLAGE-CLAIM), gains by unit
     role (melee, ranged, fast, tank), threat at the destination (attack x hp of foes within 2), stronger/weaker nearest foe,
     targets in range next turn, rough terrain x threat, crowding, empty-city-left, move length, hurt.
   - Attack: damage/return ratio, target hp and attack, target near own city, value (target cost - own cost), kill by role.
   - Train: cost/stars, same-type count, units count, city level, type x (foe near, stars, cities, Crazy). Build: cost, stars left,
     adjacent same structure. Research: cost, stars left, tier.
   - Context: Crazy flag, own units, population, income (city levels), city under threat, foes near, affordable unit,
     stars over the cheapest unit, enemy cities / villages known, turn^2. Spending: EndTurn x "what else is playable" x stars / acted.
   - **Hard vs Crazy:** `C:`-prefixed delta weights (Crazy = Hard fit + deltas, shrunk by a larger l2) are implemented in the fit and in
     `pfbot`/`choose`, but did not help on held-out Crazy (log-lik -1.34 pooled, -1.35 to -1.39 with deltas), so v3 ships **pooled**.
     Game 8 and the other Crazy games are thin; the data say move choice is the same, the handicap is in the economy (BOT-DIFFICULTY-SAME-POLICY).
   - Stage-1 ablation (honest negative result): the max-over-group of the new move features and the new context crossings fit TRAIN but
     made late-game stage 1 worse (log-lik -0.92 vs -0.83 for v2 on game 7 turns 12+). They are left out of the stage-1 fit
     (`S1_BAN` in `tools/bot_policy3.py`); only the EndTurn spending crossings stay. Stage 1 is at its ceiling with these inputs.
4. **Playout calibration:** `rules.group_bias` (stage-1 offset per group). A per-decision policy gives EndTurn a small chance at
   every decision, so turns get cut short (steps -7%, builds -45%, stars pile up). `EndTurn -0.4` fixes it; chosen on TRAIN windows
   (-0.5 / -1.0 / -0.4 tried; -1.0 makes stars go negative). Other offsets (Summon +0.3, Step +0.15, Attack +0.2) gave nothing clear.
   `capture_first` 0.94 re-checked on TRAIN (0.94: cities 104 vs real 109; 0.3: 94; 0: 84), kept.
5. Found while checking builds: real log type 1 covers both Build and Harvest. v2's "builds -45%" in bot-policy-2.md compared sim Build
   only with real Build+Harvest; `tools/bot_dist.py` now compares like with like.

## Agreement with the bots' real moves (hit rate; chance in brackets)

TEST, all decisions (v2 and v3 both never saw these turns; v2 never saw games 7 and 8 at all):

| | n | stage 1 top-1 | stage 2 top-1 | stage 2 top-3 | log-lik / decision |
|---|---|---|---|---|---|
| random | 1908 | 0.203 | 0.292 | 0.503 | -3.86 |
| v2 | 1908 | 0.702 | 0.444 | 0.679 | -2.52 |
| **v3** | 1908 | 0.690 | **0.461** | **0.703** | **-2.44** |
| random Hard / v2 / v3 (game 7 t12-19) | 1566 | 0.169 / 0.685 / 0.672 | 0.248 / 0.407 / 0.411 | 0.457 / 0.639 / 0.660 | -4.18 / -2.74 / -2.69 |
| random Crazy / v2 / v3 (ed6cb932) | 342 | 0.361 / 0.784 / 0.772 | 0.492 / 0.617 / **0.687** | 0.715 / 0.864 / 0.895 | -2.38 / -1.47 / **-1.34** |

TRAIN (v3 is in-sample here; 4-fold CV by game for v3: stage 1 0.682, stage 2 0.516 / 0.743, log-lik -2.32; Hard 0.687 / 0.521, Crazy
0.665 / 0.498; in-sample 0.720 / 0.547 / 0.766, -2.02; v2 in-sample on the same 15 630: 0.711 / 0.518 / 0.737, -2.16, and v2 had not seen games 7-8).

Per move type on TEST (stage-2 top-1 given the right group, chance in brackets; v2 -> v3):

| group | n | stage-2 top-1 | stage-1 top-1 (group next) | log-lik |
|---|---|---|---|---|
| Step, which tile given the unit | 848 | 0.456 -> **0.491** (0.225) | 0.967 -> 0.844 (v2 collapses onto Step) | -3.15 -> -3.30 (more spread, honest) |
| Attack, target given the attacker | 310 | 0.902 -> 0.887 (0.714) | 0.148 -> **0.361** (0.134) | -2.69 -> **-2.06** |
| Summon, unit type given the city | 228 | 0.842 -> 0.846 (0.449) | 0.855 -> 0.890 (0.184) | -1.51 -> -1.48 |
| Research | 72 | 0.750 -> 0.736 (0.193) | 0.208 -> 0.278 | -2.53 -> -2.31 |
| Build | 64 | 0.305 -> 0.284 (0.145) | 0.531 -> 0.469 | -3.31 -> -3.18 |
| Capture | 40 | 0.975 = chance | 0.350 -> **0.525** | -1.53 -> -1.26 |
| Upgrade | 24 | 0.312 -> 0.562 (0.455) | 0.500 -> 0.542 | -2.28 -> -2.08 |
| Harvest | 42 | 0.436 -> 0.484 (0.395) | 0.167 -> 0.143 | no signal |

Reading: the move-choice agreement gains are modest (+0.017 stage 2, log-lik +0.08); the bots are noisy and "which unit goes next"
is not modelled (Step stage-2 over unit AND tile is 0.22 vs 0.07 chance). Attack/Capture/Upgrade group timing improved clearly.
Build and Harvest are still near chance: no feature explains them (tile-level resource/terrain only).

## Playout distribution check (the part that matters for win %)

`python3 -I tools/bot_dist.py POLICY --set test --game G --k 1,3 --runs 10`; the policy plays every tribe from save i for k rounds; bot-tribe
totals vs the real save i+k. Window starts of the test set only. Real | v2 | v3 | random.

**Game 7 (Hard) windows from turn 12** (105 bot-tribe windows at k=1, 75 at k=3):

| | k=1 real | v2 | v3 | random | k=3 real | v2 | v3 |
|---|---|---|---|---|---|---|---|
| units change | 29 | 74.4 | **28.6** | -20 | 67 | 126 | 79 |
| cities change | 5 | 4.9 | 5.0 | 0.2 | 9 | 7.6 | 8.6 |
| kills | 160 | 96 | **135** | 30 | 347 | 204 | 264 |
| attacks | 294 | 176 | **259** | 62 | 638 | 399 | 516 |
| trains | 192 | 168 | 163 | 16 | 418 | 327 | 337 |
| builds+harvests | 79 | 82 | 81 | 178 | 178 | 178 | 172 |
| captures | 18 | 25.5 | 25.1 | 1.5 | 37 | 42 | 47 |
| stars change | 35 | 44 | -5 | 500 | 26 | 75 | 22 |

Per-tribe MAE v3 beats v2 and "no change" on units, cities, kills, attacks at both horizons; stars are no better than "no change" at k=3.
**ed6cb932 (Crazy, turns 1-4):** k=1 units 32 | 28 | 29.5, kills 7 | 5.8 | 6.7, attacks 16 | 17.6 | 20.6, trains 36 | 31 | 34, builds 37 | 35 | 35,
captures 16 | 16.8 | 16.9, stars 29 | 52 | 15; k=3 (30 windows) units 48 | 28 | 36, cities taken 17 | 4.6 | 11.8 (v2 far too low), captures 25 | 7 | 16.
**TRAIN windows (80 per k, 4 runs; in-sample for v3):** k=1 units 213 | 206, kills 225 | 206, attacks 424 | 399, trains 434 | 402,
builds 240 | 281, captures 104 | 124, cities 67 | 66, stars -143 | -129; k=3: units 438 | 375, kills 442 | 393, attacks 902 | 798,
trains 861 | 745, builds 604 | 580, cities 150 | 118. End-of-turn stars: sim mean 1.9-3.2, could still train 6-10% (real 2-3 and 8-14%).

## Where it is still weak (honest list)

1. **Stars**: after the EndTurn offset, game 7 late stars are under by ~0.4 per tribe-window at 1 round (-5 vs +35); the other direction
   (+120 vs -33) without the offset. One scalar cannot fit both; income vs spend on the Hard late game needs a per-turn spending model.
2. **Drift at 3 rounds**: attacks, trains, kills ~ -20% (persistent targets are still missing: each decision is memoryless), cities
   taken -20..-25%. Use 1-2 round horizons or accept a low-biased aggression.
3. **Which unit moves next** and Build/Harvest choice are near chance; best-action-first order untested.
4. **Crazy** has 3 tuning games and a 4-turn test; Crazy-specific behaviour could still exist late game (no late Crazy data).
5. Speed: v3 playouts are ~35% slower than v2 (pfwin 1317 vs 2080 moves/s on game 7 t12) because of the extra features.

## Interface (for win-pct) and reproduce

- File `data/bot_policy_v3.json` has the **same form** as v2 (`{"g":{..},"w":{..},"rules":{..}}`) plus `"ext": true` and `rules.group_bias`.
  `Policy::from_file` reads both; `botpolicy2::choose(&game, &legal, &pol, &mut rng, true)` is unchanged, so `pfwin`, `pfbot` and
  `tools/winpct*.py` switch by pointing at the v3 file: set `POLICY` in `tools/winpct_lib.py` (not edited here). v2 stays: `data/bot_policy_v2.json`.
- `pfbot data/bot_policy_v3.json jobs.json` / `tools/bot_dist.py data/bot_policy_v3.json --set test|train [--game G]`. `pfbot` also prints
  `EndStars` / `EndCanTrain` counters per tribe.
- Refit: `bot_dump.py D.jsonl --all`; `bot_policy3.py prep D.jsonl D.pkl`; `bot_policy3.py fit D.pkl --out X.json --iters 150 --nodiff --l2 0.05 [--cv]`;
  `bot_policy3.py eval D.pkl --w data/bot_policy_v2.json,X.json [--full]`; then add `"ext": true`, `rules` by hand. Fit ~2 min, CV ~8 min.
- Ledger: BOT-POLICY-V3, BOT-VILLAGE-CLAIM, BOT-SPEND, BOT-DIFFICULTY-SAME-POLICY.

## Ideas next

Persistent per-unit targets in the playout loop; a per-turn spending model (stars at end of turn by turn/difficulty); path-distance
(BFS) instead of Chebyshev for Step features; best-action-first one-stage softmax fitted in Rust; more late-game Crazy data.
