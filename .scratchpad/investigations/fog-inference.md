# fog-inference (Phase 4), 27 Oct 2026

Code: `sim/pfcore/src/fog.rs` (player view), `src/belief.rs` (sampler), bin `pffog` (`info|view|explore|sweep|maps|train|eval|sample`),
`tools/pf_belief.py` (`sample_belief(save, pov, n, seed, outdir)`), model `data/belief_model.json` (`python3 -I tools/pf_belief.py train`).

## 1. Player view: agrees with the saves
`pffog sweep saves/*.json`, 1876 (save, player) pairs, 144,490 explored tiles:
- The save's `PlayerVisibility` (= what a player sees, FOG-STALE) equals the loaded explorers only after `fog::load_exact`.
  `Game::post_load` re-runs the engine vision rule and had added 26 tiles in 11 pairs. Cause: a **captured capital** was given the
  radius-2 capital reveal. Fixed in `actions/mod.rs` (`capital_of == tribe`), ledger FOG-CAPTURED-CAPITAL (L3). Now the rule adds 0 in all 1876; pf_miss unchanged (units 7391/7394, stars 1512/1540).
- `clone_for_mcts(pov)`/`obscure_fog` keeps every enemy unit and city on explored tiles (9,827 units, 3,659 cities: 0 lost, 0 leaked) and
  changes no explored tile. It **leaks** on hidden tiles: `capital_of` and `ruling_city_coords` (every capital's position!), and `climate`, skin.
  `fog::player_view(g, pov)` scrubs these (0 leaks in 1876 pairs). Use it, not `clone_for_mcts`, for any live game.
- Still in the view (a search must treat as unknown): other tribes' stars, techs, scores, relations, `known_players`.

## 2. Sampler v1 (`belief::sample_belief(g, pov, model, mode, seed)`)
Keeps pov's view exactly (test: 0 changed observed tiles). Draws: hidden capitals (free sector of the k x k grid, offset from the measured
fractions, 3x3 hidden, >= 4 apart; capital city, 3x3 border and a Warrior added), terrain (softmax on neighbour counts / observed-region
kernel / edge / capital distance, Gibbs 15 sweeps, neighbour coupling scaled by tau = 0.3), resources P(res | terrain, near capital),
free villages (Poisson-disc >= 3 apart, rate from the cross-game gamma prior) and ruins (rate by turn).

## 3. Scores (50 samples per pair, every player of the save as pov, model trained WITHOUT the test game, `pffog eval`)
Mean ln p(truth) of the empirical sample frequencies (+0.5 smoothing) over the hidden tiles; baselines: global class frequency, uniform.
| test | pairs / hidden tiles | metric | sampler | global freq | uniform |
|---|---|---|---|---|---|
| ed6cb932 t5 | 16 / 13,237 | terrain ln p | -1.748 | -1.688 | -1.731 |
| | | terrain ln p, 1-2 tiles from explored (n 1,153) | -1.608 | -1.626 | -1.713 |
| | | resource ln p | -1.520 | -1.526 | -1.939 |
| | | hidden capitals within 4 tiles (n 229) | 0.94 | 0.83 | 0.83 |
| af181c8f t12 + e15f392c t11 | 32 / 25,282 | terrain ln p | -1.660 | -1.717 | -1.754 |
| | | terrain ln p, 1-2 tiles (n 3,045) | -1.524 | -1.692 | -1.768 |
| | | hidden capitals within 4 tiles (n 434) | 0.94 | 0.84 | 0.84 |
Honest reading: **capitals** are clearly better than uniform (within 2 tiles 0.45-0.57 vs 0.43-0.44; within 4 tiles 0.94 vs 0.83). **Terrain** helps next to the
explored region (+0.02 to +0.17 nats) but far away it is no better than the global prior; overall it wins on 2 of 3 held-out games and loses on ed6cb932 (a game with
a different land/water mix). Only ~10 distinct games exist to learn game-level traits (global water share), so game-level features were dropped (they memorised the game).
**Villages are broken:** the hidden free-village count is under-estimated (bias -11 and -19, 90% interval covers 0/32 pairs) and the observed-region update made it worse
(explored area sits around capitals). Ruins: count over-estimated by +0.8 (ed6cb932) / +7 (the other two games, which are later: ruins get used up; the turn bucket is too coarse). Village probability is not calibrated (calibration table printed by `pffog eval`).

## 4. Limits and what Phase 5 should assume
- Not inferred: enemy stars, techs, scores, hidden cities beyond the capital (expansion), units beyond one start Warrior, buildings, roads, who owns which hidden tile beyond a capital 3x3. Hidden
  tribes keep their TRUE stars/techs in the sample's tribe records: **overwrite or ignore them in search**.
- Which hidden tribe sits at which sampled capital is arbitrary (only the set is meaningful); met tribes' positions are not used.
- Phase 5: treat hidden terrain beyond ~3 tiles from explored as nearly the global prior; use the sampler for capital/threat directions, not for expansion targets. Do not rely on village counts until fixed.
- Next steps: village model (suburbs within 4 of capitals, calibrate count vs map type), ruin decay by turn, hidden enemy expansion (cities per tribe per turn from bot_turns), infer water share from the first explored ring, use `known_players` to tie tribes to places.
- Update: `check.sh` baseline untouched; `cargo test` 129 pass (new: fog view test, belief keeps-the-view test).

## 5. Village count fixed (28 Oct, VILLAGE-PACK)
Same test as section 3 (3 held-out games, 48 pairs, 50 samples, model trained without them; `pffog eval`). Hidden free-village count, truth about 34-40 per pair:

| sampler version | MAE | bias | 90% interval covers |
|---|---|---|---|
| before (Poisson rate by eligible tile, terrain-weighted) | 12.6 | -12.6 | 0.21 |
| + villages allowed from the second ring in (was third) | 8.5 | -8.3 | 0.52 |
| random sequential packing, spots >= 3 apart, taken with probability drawn per sample from [0.9, 1] | **5.7** | **-2.8** | 0.42 |

What was wrong: (1) `eligible_land` kept villages two tiles off the border, but 22% of the real hidden villages stand on the second ring (x = 0 never; ring 1: 405 of 1,759). (2) A Poisson count on top of that under-fills: at turn 0 every packing spot is taken
(PolyVision, polyvision-maps.md), so the sampler now packs the hidden interior land (Chebyshev >= 3 from every known or sampled settlement) instead of drawing a rate. Env switches for A/B: `VIL_PACK=0` (old count), `VIL_LO` (fill floor).
Limits: the interval is still too narrow (0.42 of 0.90): game-to-game spread is real (a game with 40 hidden villages because enemies had captured some), and the packing has little variance of its own. Ruins unchanged (bias +0.8, covers 0.96).
Terrain and capital scores unchanged. The win-% fog model (`data/winpct_eval.json`) was not refitted on the new samples. `cargo test` 138 pass; no model retrain needed (`vil_fill` defaults to 0.9 for old model files).
