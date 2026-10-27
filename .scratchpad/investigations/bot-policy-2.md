# bot-policy-2 (Phase 6 groundwork; needed now for win % in Phase 5)

_Owner: bot-policy-2 session · 2026-10-27 · state: v1 + v2 + distribution check done; v3 ideas at the bottom_
**Parallel work:** the first bot-policy session pushed its own version (d4faae2) while this one ran: `botpolicy.rs`, `tools/bot_policy.py`,
`data/bot_policy.json`, notes in `bot-policy.md`. It uses one softmax over all legal moves with forward-model outcome features and has
agreement numbers but no playout check. This session's files carry a `2` (`botpolicy2.rs`, `tools/bot_policy2.py`, bin `pfbot`,
`data/bot_policy_v1.json` / `v2.json`, env `PF_BOTDUMP`) so the two do not collide. The two agreement tables use different candidate sets
(this one is two-stage: group, then move) and are not directly comparable. Nobody has merged the two yet.

Goal: a policy that plays the built-in bots (Hard first) inside the forward model well enough that simulated futures look like
real ones. Win % will come from playouts where this policy plays the opponents.

## What exists (all new files; no rule code touched)

| Thing | File / command |
|---|---|
| Move features, policy, playout chooser | `sim/pfcore/src/botpolicy2.rs` (tests: `botpolicy2_tests.rs`) |
| Decision dump: every legal move's features at each logged action (hook in `pfreplay`, env `PF_BOTDUMP=file`, off by default) | `python3 -I tools/bot_dump.py OUT.jsonl [--game P] [--holdout]` (~40 s, 200 MB for all tuned games: keep it in scratchpad) |
| Fit / evaluate agreement | `python3 -I tools/bot_policy2.py eval\|fit TRAIN.jsonl HOLD.jsonl [--v1 F] [--v2 F] [--maxturn 5] [--nocv]`; `v1` rewrites the hand rules |
| Playout bin | `sim/pfcore/target/release/pfbot POLICY.json JOBS.json` (plays all tribes with the policy, `random` job flag = uniform random legal moves) |
| Distribution check | `python3 -I tools/bot_dist.py POLICY.json [--holdout] [--k 1,2,3] [--runs 8] [--max N] [--random] [--json OUT]` |
| Weights | `data/bot_policy_v1.json` (hand-set), `data/bot_policy_v2.json` (fitted + `rules.capture_first`) |

Policy = two softmax stages. **Stage 1** picks a move *group* (Step, Attack, Summon = train, Build, Research, Capture, Harvest, ...;
the group is `api::kind`) from features of the group: bias, by turn bucket, log count, context (fraction of own units that already
acted, foes near, stars, cities, ...), which other groups are playable now, and the max over its moves of each named move feature
(`Attack.kill`, `Step.village_gain`, ...). **Stage 2** picks the move inside the group from the move's own features. Move features
use only the forward model: `calculate_combat_preview` (kill, damage, return damage), distances to foes / free villages / enemy cities,
unexplored tiles around a step's destination, terrain and resource of a build or harvest tile, unit cost and stars left for a train, and
the 3x3 around the capital for the research opener. Weights are a sparse name -> number table; `sample` draws from the softmaxes,
else argmax. One extra rule: `capture_first` (see BOT-CAPTURE-FIRST).

Data: 13 248 logged actions in the 11 tuned games (12 849 bot decisions whose logged move Polyfish lists; 51 bot actions are
illegal in Polyfish and left out) and 354 in held-out ed6cb932 (342 bot decisions, turns 1-5 only). Held-out was never used to fit.

## Agreement with the bots' real moves (hit rate; chance = random legal move in the same set)

"Stage 1" = the bot's next group; "stage 2" = its move inside the right group. Chance is exact (ties split), not sampled. Note the
bots are noisy (decision rates are 60-75%, see sim-dist.md), so a hit rate of 100% is not the target.

All turns, tuned games (n=12 849; v2 is **in-sample**, 4-fold CV by game before the `has:` features: stage 1 0.684, stage 2 0.495, top-3 0.720, log-lik -2.35):

| | stage 1 top-1 | stage 2 top-1 | stage 2 top-3 | log-lik / decision |
|---|---|---|---|---|
| random legal | 0.248 | 0.363 | 0.585 | -3.46 |
| v1 hand rules | 0.415 | 0.397 | 0.627 | -3.38 |
| v2 fitted | 0.706 | 0.526 | 0.742 | -2.14 |

Turns 1-5 only (so tuned and held-out are comparable): tuned n=3 147 / held-out n=342.

| | stage 1 top-1 | stage 2 top-1 | stage 2 top-3 | log-lik |
|---|---|---|---|---|
| random, tuned / held-out | 0.385 / 0.361 | 0.490 / 0.492 | 0.717 / 0.715 | -2.32 / -2.38 |
| v1, tuned / held-out | 0.576 / 0.554 | 0.522 / 0.542 | 0.751 / 0.758 | -2.16 / -2.15 |
| **v2, tuned / held-out** | **0.772 / 0.784** | **0.639 / 0.617** | **0.850 / 0.864** | **-1.46 / -1.47** |

Held-out is as good as tuned, so v2 is not overfitted at this size. Per group, v2 all turns tuned (chance in brackets; stage 2 only):

| group | n | stage 2 top-1 | top-3 | note |
|---|---|---|---|---|
| Step (which unit and tile) | 5513 | 0.248 (0.099) | 0.487 (0.279) | |
| **Step given the unit** (which tile) | 5513 | **0.464 (0.240)** | 0.803 (0.594) | held-out 0.406 (0.197) / 0.879 (0.578), n=128 |
| Attack (which unit and target) | 1420 | 0.684 (0.434) | 0.927 (0.787) | |
| **Attack given the attacker** (target) | 1420 | 0.898 (0.762) | 0.998 | kill > least return damage > cost; held-out 16/16 |
| Summon (which city and type) | 1383 | 0.665 (0.433) | 0.955 (0.779) | |
| Summon given the city (type) | 1383 | 0.817 (0.539) | 0.999 | |
| Research | 599 | 0.833 (0.174) | 0.985 (0.518) | in-sample; CV 0.626 / 0.881; held-out 0.710 (0.169), n=31 |
| Build | 527 | 0.362 (0.205) | 0.678 (0.415) | resource/terrain of the tile helps; weak |
| Harvest | 374 | 0.494 (0.478) | 0.843 | no signal found |
| Capture | 410 | 0.930 = chance | | almost always one option |

Stage 1 is the weak spot for the rare groups: argmax collapses to Step (0.98 of Step decisions, 0.15 of Attack, 0.32 of Capture), so
use the stochastic policy; the log-likelihood (-2.14 vs -3.46 random, -1.47 vs -2.37 on held-out) is the honest summary. The agreement
tables score the weights only; `capture_first` is not in them.

## Facts about the bots found on the way (ledger BOT-*)

- **Turn shape** (BOT-TURN-SHAPE): units first (Capture mean position 0.23 of the turn, Attack 0.35, Step 0.29), then economy
  (Harvest 0.65, Build/Reward 0.70, Summon/Research 0.74, Upgrade 0.78), then EndTurn. Which unit goes next is not unit id order
  (af181c8f: 8 of 255 turns ascending, 8 descending): probably a best-action-first loop; not modelled.
- **Capture** (BOT-CAPTURE-FIRST): in 385 bot turns where a capture (village, city, ruin) was possible at some decision, the bot made
  one in 94%. Per decision only 29% (other units go first), so a per-decision softmax under-captures: on a 30-window k=1 check v2 without the rule made 29 captures (real 49);
  with `capture_first` 0.94, 60 windows, it makes 56 (real 42), and cities taken at k=1 go from 17 to 24 (real 25).
- When available at a decision the bot played: Step 64%, Capture 29%, Attack 23%, Summon 22%, EndTurn 13%, Build 6%, Research 6%.
  Per turn, if available at some decision: Summon used 78%, Attack 74%, Upgrade 59%, Research 38%, Build 36%, Harvest 31%, Recover 24%.
  So bots do **not** spend everything; the sim's star surplus (below) is partly bot behaviour we do not model (what stops a bot building).
- Step destinations: toward free villages and enemy cities help (`Step.village_gain`), unexplored tiles around the destination help
  (scouting), wounded units close in less. Details are in the fitted weights.

## Distribution check (step 4): the policy plays all tribes from a real save, k = 1-3 rounds, vs what happened

`tools/bot_dist.py`, bot tribes only, totals over bot-tribe windows (sim = mean of runs). The simulation starts from save i (the
player to move continues that turn), plays until as many EndTurns as the log shows, and is compared with save i+k. The human is played
by the policy too, so effects of the human's real moves on bots are missing. Held-out: 9 windows, 20 runs each; tuned: 60 windows, 6 runs.

Held-out ed6cb932 (turns 1-5), real | v2 | v1 | random-legal, totals for 60 / 45 / 30 bot-tribe windows (k=1 / 2 / 3):

| k=1 | real | v2 | v1 | random |
|---|---|---|---|---|
| units change | 32 | 28 | 13 | 9 |
| cities change | 12 | 13 | 12 | 1 |
| casualties | 7 | 6 | 6 | 2 |
| attacks | 16 | 17 | 17 | 9 |
| trains | 36 | 32 | 17 | 11 |
| captures | 16 | 17 | 16 | 2 |
| builds | 37 | 23 | 17 | 14 |
| research | 31 | 28 | 28 | 39 |
| stars change | 29 | 48 | 106 | 81 |

Tuned games (60 windows, 259-264 bot-tribe windows, v2 | real): k=1 units 120|135, cities 24|25, casualties 63|82, attacks 118|160,
trains 173|209, captures 56|42, builds 75|142, stars 134|79. k=2: units 305|288, cities 62|91, casualties 245|361, attacks 485|722,
trains 533|632, captures 138|157, builds 260|410. k=3: units 302|344, cities 56|127, casualties 232|311, attacks 456|609, trains 512|643,
captures 122|184, builds 277|519. Per-tribe mean absolute error of the simulated change vs the real one: tuned, v2 beats both the "no change" guess and random-legal
playouts on every measure at every k, except builds at k=1 (no change is better) and stars at k=2-3 (no change is better; stars pile
up in the sim). Held-out, the same except kills and casualties at k=3 (10 events; random is as good).

Reading: **v2 playouts are the right shape at 1 round** (units, cities, kills, attacks, trains, captures within ~10-20% on held-out
and tuned) and **drift low at 2-3 rounds**: attacks -25%, trains -20%, builds -45%, cities taken -55% at k=3, and stars pile up
(unspent). The cause is structural: bots seem to keep a plan across turns (units walk to a target over several turns, the economy is
spent against a build order), while the policy re-decides each action with no memory. Random-legal playouts are far off on everything
(captures 2 vs 16, units 9 vs 32, stars 81 vs 29), v1 under-trains (17 vs 36) and over-attacks.
For win %: use the stochastic v2, 1-3 round horizons; do not read cities taken or economy beyond ~2 rounds from it yet.

## Not done / ideas for v3 (ordered by expected gain)

1. **Build/economy gap** (builds 55% of real at k=3, star surplus): find what makes a bot build or hold stars. Needs a per-turn view:
   stars before/after, what was affordable. Try features: stars >= cost of the cheapest build, structure value of the tile.
2. **Persistent targets**: give each unit a target (nearest free village / enemy city at the turn it was first seen) and keep it across
   turns; expected to fix captures and attacks at k=3. Needs a small state in the playout loop (per-unit target), not in the save.
3. **Best-action-first order**: test whether the bot's next action is the max of a score across all units (explains the turn shape and
   the unit-order result) with a one-stage softmax over all moves; the fit in pure Python is slow (270 moves x 13k decisions), so
   sample negatives or fit in Rust.
4. Hard vs Crazy: only Hard has full-turn games (Crazy appears in the bot-war saves only); fit per difficulty once there is data.
5. Bots' fog use: features use all enemy units (no fog filter); whether bots see through fog is untested (Phase 6 question).
6. More data helps most for Attack, Capture, Build (n=410-1420 tuned; 16-20 held-out): ask Jason for full-length Hard games exported
   every turn (see status.md).

## Reproduce

```sh
sh scripts/restore_saves.sh; (cd sim/pfcore && cargo build --release); git checkout sim/pfcore/Cargo.lock
S=$TMPDIR/bp; mkdir -p $S
python3 -I tools/bot_dump.py $S/d_train.jsonl; python3 -I tools/bot_dump.py $S/d_hold.jsonl --holdout
python3 -I tools/bot_policy2.py eval $S/d_train.jsonl $S/d_hold.jsonl --v1 data/bot_policy_v1.json --v2 data/bot_policy_v2.json
python3 -I tools/bot_policy2.py fit  $S/d_train.jsonl $S/d_hold.jsonl --out $S/v2_new.json --iters 60   # ~6 min with CV; --nocv ~1.5 min
python3 -I tools/bot_dist.py data/bot_policy_v2.json --holdout --runs 20; python3 -I tools/bot_dist.py data/bot_policy_v2.json --runs 6 --max 60
```
