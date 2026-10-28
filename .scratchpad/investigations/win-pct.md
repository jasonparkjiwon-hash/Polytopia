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

## 28 Oct 2026 (win-pct-2): belief with unseen opponents, v2 vs v3, speed

**Belief mode with unseen opponents (task 1) — negative result.** `sim/pfcore/src/unseen.rs` + `data/win_bank.json` (2099 real bot-tribe
profiles: cities with levels, units with hp, stars) + `tools/winpct_unseen.py`. After `sample_belief`, each opposing tribe gets cities/units
drawn from a profile (same bot level, Gaussian turn kernel sigma 1.5, tribe bonus, score kernel); new cities prefer sampled villages within 6 of
its cities, new units sit on unexplored tiles within 4; observed cities/units untouched; stars replaced by the profile's; techs left as saved.
Bank never contains the test game or the held-out games (ed6cb932, 710ddb20, 64795ee3). Opponent cities/units at H=1 move from 1.0/1.3 (old
belief) to ~2.4/5.5 (full information 3.3/8.3). H=4, 16 playouts, 100 points, raw playout lead share, Brier tuned / held:

| uniform | static | full info | belief old | unseen noscore | unseen score (met tribes) | unseen scoreall | oracle cities | oracle cities+units |
|---|---|---|---|---|---|---|---|---|
| .0660/.0586 | .0567/.0559 | **.0552/.0446** | .0705/.0626 | .0762/.0622 | .0772/.0640 | .0760/.0643 | .0754/.0665 | .0783/.0696 |

With 50% static blended in: full .0519/.0468, belief old .0588/.0544, noscore .0611/.0547, scoreall .0612/.0553. **Belief mode cannot beat the
static eval** (tuned .0567/.0559); filling in unseen units did NOT help, even with the true city and unit counts (oracle_*): drawing profiles
at random per tribe removes WHICH tribes are strong, which is most of the signal, and conditioning on the saved score (all tribes) did not recover it.
Advice: for a fogged game use the static eval (or full-information playouts only as an upper bound). Reproduce:
`python3 -I tools/winpct_unseen.py bank; ... run 4 16 VARIANT [v2|v3]; ... report 4 v2` (variants full belief noscore score scoreall oracle_cities oracle_all).

**Policy v3 vs v2 for the opponents (task 2):** full information, H=4, 16 playouts, same 100 points, Brier tuned/held: v2 .0552/.0446, v3 .0584/.0456.
v3 is not better and ~2x slower on late states: **keep v2** (POLICY unchanged).

**Speed (task 3, partly done).** Profile: ~70% of a playout was `botpolicy2::choose` (feature strings, `format!`, malloc, repeated nearest-distance scans,
failing accessors building error Strings). Changes in `botpolicy2.rs` (feature names are `Cow<'static,str>`, interned/memoised names,
fast hasher, per-decision distance maps, caches for threat/unexplored): **playouts with the same seed are bit-identical** (md5 of the playout
features checked for v2 and v3 on 5 states). One process, 16 tribes, 4 rounds, v2: t15 2.04 -> 4.11 playouts/s, t24 1.36 -> 3.13 (2.0-2.3x; choose
2.16 s -> 0.72 s); v3 about 2x. Not done: 3x target missed (engine `legal_moves`/`apply` are now ~35% and out of my scope), threads inside pfwin,
early stop. Brier before/after identical (same playouts). pfwin prints `prof_legal_choose_apply_nlegal` timings.

**Not done (tasks 4-5):** second label (survival/city count/military), refit on all 18 games, tools/winpct.py help, ledger entries (no new
settled game rule came out of this). Next: that refit, and a cheaper per-tribe playout (skip distant tribes) if more speed is wanted.

## 28 Oct 2026 (win-pct-3): honest label, refit eval, fog, intervals, speed

Code: `tools/winpct_fit.py` (research harness, numpy: `labels`, `sets`, `fog`, `write`), `tools/winpct_est.py` (estimator), `tools/winpct.py` (CLI, rewritten),
weights `data/winpct_eval.json`. pfwin/scenario features grew by `threat` (own cities with an armed foreign unit within 3), `pressure` (foreign cities with an
own armed unit within 3), `water` (map water share); `pfwin state_only` also returns `fog` (per tribe: cities on the mover's explored tiles, met) and `explored`.
Data: **15 games have saves** (CLAUDE.md says 18; the other 3 have no decoded checkpoints here), 157 checkpoints. Protocol: leave-one-game-out (LOGO) over the 14 games
other than ed6cb932 (n per cell below = points x alive tribes; points are serially correlated inside a game, so intervals are bootstrap over games, 90%);
"held" = ed6cb932 + games 7-8 predicted by models fitted on the 11 tuned games only (17-31 points per cell: noisy). Playouts 16 per state, policy v2.

### 1. Labels (LOGO, same features; skill = 1 - Brier/uniform Brier; points / games)
| label | H=1 | H=2 | H=3 | H=4 | H=6 |
|---|---|---|---|---|---|
| score leader (old) | .27 | .18 | .20 | .15 | .08 [-.05,.22] |
| most cities (tie: army) | .34 | .23 | .23 | .20 | .11 [-.01,.21] |
| strongest army | **.51** | .25 | .13 | .07 | .06 |
| **power** = most cities, tie: army, then score | .33 | .22 | .23 | .20 | .10 [-.01,.20] |
| survival to t+H | 0 dead of 1957 | 1 of 1771 | 2 of 1601 | 4 of 1431 | 5 of 1106 |
points: 137 / 124 / 112 / 100 / 77 (13-14 games). **No saved game finished** (max 26 rounds, 15 dead tribe-states in 2256): no final-winner label, survival is noise.
Army lead is predictable one round out (persistence) and is gone by H=4 (units die and are rebuilt). Score lead is the least predictable and does not encode combat.
**Primary label = "power": the tribe holds the most cities at t+H (ties: strongest army, then score)**. Why: cities are what combat takes and loses, it is the land-based
win condition, it moves slowly enough to be predictable 2-6 rounds out (unlike army), it has no ties in practice (tie-breaks), and it is nearly as predictable as the best label at each H.

### 2. Evaluation function refit (label power, conditional logit over alive tribes, standardised, ridge l2 by LOGO, per-H weights)
Feature groups tried (LOGO skill / held skill, H=2,4,6): old 8-feature eval .21/.16/.08 (held .25/.16/.13); +relative shares and logs .21/.17/.10; **+war
(threat share, pressure, casualties, kills-casualties, units, connected share) .24/.19/.10 (held .31/.20/.12)**; +turn x features .20/.15/.08 (no gain); +water x features
.20/.15/.07 (no gain: 15 distinct water values); +tribe one-hots helps at H=6 (.14 vs .08); lead-margin features (cities / army margin to the best other tribe): no gain.
Shipped: **share+war+tribe** (l2 8; 30 at H=6). Table (Brier per (point, tribe), LOGO / held, n = 133,121,110,99,77 points LOGO and 31,28,25,22,17 held):

| H | uniform | score only | old eval | **new static (full info)** | playouts alone | **playouts+static stacked (full info)** | **fog (shipped)** | fog static on fog features | fog_lite |
|---|---|---|---|---|---|---|---|---|---|
| 1 | .0652/.0586 | .0568 | .0464/.0409 | .0451/.0383 | .0166/.0097 | **.0164/.0099** | .0541/.0499 | .0560/.0517 | .0571/.0560 |
| 2 | .0651/.0586 | .0580 | .0516/.0442 | .0503/.0427 | .0440/.0365 | **.0422/.0340** | .0561/.0516 | .0588/.0529 | .0579/.0563 |
| 3 | .0650/.0586 | .0583 | .0535/.0468 | .0500/.0435 | .0591/.0472 | **.0484/.0402** | .0566/.0523 | .0591/.0528 | .0585/.0568 |
| 4 | .0649/.0586 | .0590 | .0549/.0491 | .0519/.0444 | .0642/.0542 | **.0512/.0433** | .0563/.0487 | .0613/.0547 | .0600/.0580 |
| 6 | .0646/.0586 | .0629 | .0594/.0508 | .0546/.0436 | .0658/.0618 | **.0549/.0465** | .0563/.0515 | .0699/.0659 | .0678/.0691 |

Skill (LOGO, 90% bootstrap over games): new static .31 / .23 / .23 / .20 / .16 (H=1,2,3,4,6; H=6 [.02,.28]); stacked playouts .75 [.65,.85] / .35 [.23,.44] / .26 / .21 / .15;
fog .17 [.07,.27] / .14 [.03,.26] / .13 / .13 / .13 [-.01,.25]. Reading:
- **Playouts matter only at H<=2** (H=1: Brier .0166 vs static .0451, the next round almost decides who holds the most cities) and add a little at H=3; from H=4 the
  stacked estimate equals the new static eval (.0512 vs .0519; .0549 vs .0546): raw playouts are worse than uniform-ish at H=6 (.0658). The 50/50 blend of win-pct-1 is replaced by a learned stack
  (log-linear weights per H, fitted on out-of-fold static predictions: playout weight 1.38/.88/.48/.38/.37, static .55/.60/.92/.91/.81).
- The new static eval beats the old one at every H (e.g. H=4 .0519 vs .0549, held .0444 vs .0491) and beats score-only everywhere.
- Reliability (LOGO, pred% -> obs%, n tribe-cases), H=4 new static: 1->1 (562), 3->5 (301), 7->7 (283), 13->11 (162), 25->27 (63), 39->44 (16), 64->47 (15), 89->92 (13);
  fog: 1->1 (237), 3->4 (532), 7->6 (389), 14->12 (184), 25->25 (53), 41->56 (9). Calibrated where there are data (<=30%); above 40% each bin has <20 cases (rough). H=6 static:
  25->16 (43), 41->88 (8), 87->44 (9): the top is not trustworthy at H=6. Tables per mode and H are in `data/winpct_eval.json` (`calib`) and are what the "trust" line prints.

### 3. Fog (what the mover can know: own tribe in full; others: public score [assumption: the scoreboard shows every tribe's score], cities on explored tiles, tribes met, tribe)
Tested (LOGO / held Brier at H=4; uniform .0649/.0586): (c) static eval on the fog features .0613/.0547 (H=6: .0699, WORSE than uniform); fog_lite (score, cities seen, met, me) .0600/.0580;
(a) **distillation: fit the fog model to the soft target 0.5 x full-information playout share + 0.5 x full static prediction (no outcomes), ridge 3** .0563/.0487 (H=6 .0563/.0515);
(b) Platt/stack on the fog prediction .0615/.0539 (no gain), fog+fog_lite stack no gain; imputation (ridge-impute the other tribes' true features from score and visible cities, then the full eval) .0576/.0524 (H=6 .0657: bad).
**Winner = (a) distilled fog model**: it uses 2-3x the training signal (every tribe's smooth full-information prediction, not one 0/1 outcome) and is the only fog variant that beats uniform at H=6.
It beats the plain static eval in fog at every H (the gap grows with H) and recovers ~55-85% of the full-information static skill (.13 vs .20 at H=4; .13 vs .16 at H=6; .17 vs .31 at H=1). What is
lost is exactly the hidden state (units, cities not yet seen). Caveats: stage-1 soft targets for the training games use out-of-fold static predictions (no label leak), but the distilled model was
chosen among ~8 variants on the same LOGO folds (mild optimism; held-out agrees: .0487 vs uniform .0586). Playouts from the player's view (belief + unseen sampling, 28 Oct earlier) stay a negative result.

### 4. Intervals and trust (tools/winpct_est.py)
Every printed percentage has: label name and horizon; a 90% interval = 5-95 percentile over 20 bootstrap fits of the model (games resampled; plus Dirichlet-resampled playout lead shares in full mode, prior 0.5 per tribe so
unanimous playouts keep an interval); `model +-` and `playouts +-` standard deviations separately; a trust line from the out-of-fold calibration bin of the prediction; the mode flag (**FULL INFORMATION is printed as CHEATING for a fogged real game**).
Not in the interval: bot-policy drift after 2-3 rounds, a human who plays unlike policy v2, and the "scores are public" assumption. `tools/scenario.py` now prints the same label, interval and trust per option (full-information futures, flagged).

### 5. Speed
Found and fixed a tail bug: when a save's first (starting) player is eliminated inside a playout the forward model's turn counter stops and the others cycle forever until the 40,000-move guard (e.g. 9847d452 t6, seed 1065: 11.9M legal moves, 18 s for 2 playouts; the
state's other seeds take 0.05 s). pfwin now declares a round after 2 x tribes tribe-turns without a counter change (and forces EndTurn after 400 moves in one tribe turn). Normal playouts are bit-identical.
CLI uses all cores and stops early once every plausible tribe has a 90% Wilson half-width below 7 points (at least 16 playouts).
Before -> after, 48 playouts x 4 rounds, 4 cores, wall seconds: 9847d452 t6 (4 tribes) 18.6 -> 0.3; af181c8f t5 1.1 -> 1.1; t15 51 -> 2.5 (early stop: 24 playouts, 1.1 s, top tribe .780 -> .795); t24 114 -> 3.3.
The full calibration run (157 states x 16 playouts x 6 rounds) fell from >40 CPU-minutes to 6 CPU-minutes. Brier of playouts identical before/after (H=4 .0642 -> .0642, H=2 .0441 -> .0440; the stuck playouts were a few).

### Reproduce
```sh
cd sim/pfcore && cargo build --release; git restore Cargo.lock          # pfwin with the 17 features
python3 -I tools/winpct_eval.py states; python3 -I tools/winpct_eval.py playouts 6 16      # ~6 CPU-minutes now
python3 -I tools/winpct_fit.py labels; python3 -I tools/winpct_fit.py sets power; python3 -I tools/winpct_fit.py fog; python3 -I tools/winpct_fit.py write
python3 -I tools/winpct.py <save> --mode both --horizon 4
```
### Weak spots / next
Few games (14 in LOGO), no finished game (a final-win label needs one); top-probability bins are sparse; the new weights were chosen on the same folds that report them (held agrees, 17-31 points);
the fog model assumes other tribes' scores are visible (if Jason's iPhone view hides unmet tribes' scores, drop `score` for them: refit with `met * score`); the human is modelled as policy v2 only in full mode.
