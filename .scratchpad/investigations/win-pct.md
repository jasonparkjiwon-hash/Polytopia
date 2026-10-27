# win-pct: win percentage from a saved state (Phase 5, capability 2)

_Owner: win-pct session · 27 Oct 2026 · state: prototype done and calibrated; weak spots listed below_

## What it does

`python3 -I tools/winpct.py <save> [--player P] [--playouts N] [--horizon H] [--seed S] [--top K]` plays bot policy v2 for EVERY tribe
(the human too) from the save, N seeded playouts of H rounds with `Game::search_move`, and prints per tribe: **est** (recommended: half
playout lead share, half static estimate), the playout lead share with a 95% Wilson interval, the static estimate, alive %, and start ->
mean end of cities, unit value, stars, score; plus "drivers" for `--player` (its gap to the field median at the horizon).
Files: bin `sim/pfcore/src/bin/pfwin.rs`; `tools/winpct.py` (CLI), `tools/winpct_lib.py` (run, labels, static softmax),
`tools/winpct_eval.py` (states / playouts / report / write / smoke), weights `data/winpct_static.json`.

## What "winning" means here (read this first)

- **No saved game ran to a finish** (max 26 rounds; 2 tribes ever died, in 2 games). So there is no final-win label and survival is
  uninformative (99.8% alive). Everything below is **definition (a): P(tribe has the highest in-game score H rounds later)**, ties split.
  A city-count leader label was also scored (static fit only; same picture). "Score" is the game's own score, which is what ends a
  score-limited game; Jason's combat priority is not in the label: kills/units enter only as inputs.
- Final-win (b) is not computed. Do not read the percentages as "chance to win the game".
- 16 tribes in most games (1 human + bots), so a uniform guess is ~6%. Numbers for the human are for Jason's tribe played BY THE BOT POLICY.

## Playout engine

- `pfwin`: policy v2 (stochastic, `capture_first` on) for all tribes, `search_move` (no reveals, no fog memory, no dice table: a ruin reward
  uses Polyfish's seeded hash, not `data/distributions.json`), seed = f(job seed, playout index): same args give the same numbers.
  Snapshots at the start of rounds h = 1..H (turn counter reaches start+h with the starting player to move). 14 features per tribe.
- **Full information by default** (the save's hidden map): cheating for a real fogged game, fine for calibration on saves.
  `--belief` draws the map from `belief.rs`, **but it is NOT usable yet**: the sampler draws terrain/villages/capitals only, so other tribes'
  unseen cities and units are missing; belief playouts end with 1.2 cities and 5.5 unit value per tribe against 3.0 and 24.5 with full
  information (games 7-8, H=4) and their Brier is worse than the static guess (0.0645 vs 0.0558 at H=4, n=21). Fix = sample opposing
  cities/units too (fog-inference follow-up).
- **Playouts per second** (one process, 8 playouts, H=4, release build; the CLI runs 4 processes):

| state | tribes | rounds/s | moves/s | playouts/s (4 rounds) |
|---|---|---|---|---|
| 9847d452 t6 | 4 | 187 | 6400 | 46.7 |
| af181c8f t5 | 16 | 50 | 5800 | 12.6 |
| af181c8f t15 | 16 | 18 | 3500 | 4.5 |
| af181c8f t25 | 16 | 10 | 2350 | 2.5 |

  The full-run average over all 157 states (16 playouts, up to 6 rounds, 4 processes busy) was 2.75 rounds/s per process.
  Late 16-tribe states are slow: 48 playouts x 8 rounds from every state needed more than 100 CPU-minutes per process before I stopped it.

## Static evaluation

Conditional logit over the alive tribes: P(p leads at t+lag) = softmax_p(w . phi), phi = cities, city levels, unit value x hp, stars,
income, techs, kills, score (scaled), one weight vector per lag (1, 2, 3, 4, 6), L2 0.5, fitted on the 11 tuned games (`winpct_eval.py write`).
Weights shift from kills/score (lag 1: score 3.3) toward income/techs/units (lag 6: income 1.8, score 0.8). 11 games is little:
treat the weights as a sketch.

## Calibration

Label: leader by in-game score at t+H (ties split); a point = (game, turn t) with a save at t+H; Brier is per (point, alive tribe), so
lower than the uniform guess (about 0.059-0.066, depending on how many tribes are alive) means signal. Tuned = leave-one-game-out over 11 games (the static eval never saw its own game;
playouts use policy v2, fitted on those 11 games, so tuned playouts are in-sample for the policy). Held-out = ed6cb932 (turns 1-5), game 7
(710ddb20, t1-19) and game 8 (64795ee3, t1-10): never used by the policy or the eval. 16 playouts per state.

| H | n tuned / held | uniform | score only | static | playouts | **playouts+static** | cut@H/2 + static |
|---|---|---|---|---|---|---|---|
| 2 | 96 / 28 | .0664 / .0586 | .0550 / .0470 | .0542 / .0513 | .0567 / .0439 | **.0500 / .0440** | .0549 / .0448 |
| 3 | 87 / 25 | .0662 / .0586 | .0547 / .0480 | .0514 / .0472 | .0591 / .0422 | **.0514 / .0411** | .0541 / .0470 |
| 4 | 78 / 22 | .0660 / .0586 | .0580 / .0546 | .0567 / .0559 | .0552 / .0446 | **.0519 / .0468** | .0535 / .0509 |
| 6 | 60 / 17 | .0660 / .0586 | .0643 / .0551 | .0634 / .0583 | .0581 / .0559 | **.0560 / .0529** | .0570 / .0584 |

(each cell tuned / held-out Brier). Reading:
- Everything beats uniform. At 2-3 rounds the current score alone is nearly as good as anything (score only .055 vs .050-.054).
- **Playouts add information from H=4 on** (tuned .0552 vs static .0567 at H=4, .0581 vs .0634 at H=6; held-out .0446 vs .0559 at H=4),
  and the blend is best or near-best at every H on tuned. On held-out the raw playouts are as good as or better than the blend for H<=4
  and the blend wins at H=6; with 17-28 points per cell the held-out differences between the two are within noise.
- **Cutting playouts early and finishing with the static eval (cut@H/2) does not pay**: it is about as good as the static eval alone,
  worse than full playouts. Use full-horizon playouts.
- Even at H=6 the gain over uniform is only ~15% in Brier (.056 vs .066): who leads the score 6 rounds out is mostly not predictable
  from this model.
- **Reliability** (tuned, pooled bins of predicted lead share; pred -> observed). Raw playouts are overconfident at the top and have a
  floor: H=4 pred 0.00 -> obs 0.02, pred 0.58 -> 0.40, pred 0.92 -> 0.75; H=6 pred 0.55 -> 0.27, 0.89 -> 0.85. The blend: H=4
  0.01 -> 0.003, 0.03 -> 0.03, 0.07 -> 0.11, 0.14 -> 0.16, 0.27 -> 0.20, 0.40 -> 0.31, 0.64 -> 0.67, 0.91 -> 0.92; slightly low at 5-10%,
  slightly high at 20-50%. So report the blend, not the raw playout share.
- The Wilson interval is playout noise only (about +-15 points at 50% with 32 playouts); model error (bot policy drift, below) is
  not in it and is the larger part beyond ~3 rounds.

## Weak spots (honest)

1. Horizon drift: policy v2 under-plays attacks/builds/captures from round 2-3 on (bot-policy-2.md); playouts of 6 rounds carry that bias.
   The raw playout share is overconfident (above) because 16-48 samples of a drifting model are sharper than reality.
2. Few games, one human, no final result: no finish label; the 11 tuned games give 60-96 points per H, so Brier differences of 0.002-0.004
   between methods are not significant. Need games 7-8-style full-length games (Jason's 28 Oct data) for more.
3. Belief mode unusable (see above); full-information numbers are an upper bound on what a fogged advisor could know.
4. The human is modelled as policy v2; its real play (usually better at combat) is not.
5. Mid-round alignment: a snapshot is when the turn counter reaches t+H with the starting player to move; real saves are taken at the
   player's turn, so this matches for the human's checkpoints.
6. 16 playouts per state in the calibration, 48 default in the CLI. Speed on late 16-tribe states is 2-4 playouts/s (4 rounds) per process.

## Next steps

- Sample unseen opposing cities/units in the belief model (fog-inference), then re-run `playouts 6 16 --belief` and compare.
- Fit the blend weight and a probability floor on more games (Jason's full-length games), shrink raw playout shares.
- Label with a combat standing (kills, units lost, cities taken) once there are games with real fights to the end.
- Rebuild for speed (move enum instead of Box<dyn Move>, features cache in `botpolicy2::choose`) if more playouts are needed.

## Reproduce

```sh
cd sim/pfcore && cargo build --release            # then: git restore sim/pfcore/Cargo.lock if it changed
python3 -I tools/winpct_eval.py states            # real feature vectors of every save -> /tmp/winpct_cache
python3 -I tools/winpct_eval.py playouts 6 16     # ~1.5 h on 4 cores; resumable
python3 -I tools/winpct_eval.py report 6          # the table above
python3 -I tools/winpct_eval.py write             # data/winpct_static.json
```
