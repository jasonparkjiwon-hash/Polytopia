# bot-policy (Phase 6 groundwork, for win % in Phase 5)

_Owner: bot-policy session · started 2026-10-27 · state: v1 + v2 measured; playouts next_

Goal: a policy that plays the built-in bots inside the forward model (Polyfish, `sim/pfcore`) so simulated
futures look like real ones. Win % = playouts with this policy for the opponents.

## What exists

| Thing | Command | Notes |
|---|---|---|
| Features + policy | `sim/pfcore/src/botpolicy.rs` | per legal move: class, kind x turn bucket, attack preview (kill, damage, return), step geometry (toward villages/enemy cities/ruins, enemies, fog, capital), train/research/build/reward ids, forward-model outcome (simulate_move on a clone: enemy kills/HP, own HP, stars, pop, cities). `score_v1` (hand rules), `Weights` (v2), `pick` (softmax / argmax), `play_turn`. |
| Data | `PF_DECISIONS=1` in `pfreplay` (2-line hook) -> `python3 -I tools/bot_policy.py collect` | every legal logged bot action with all its legal alternatives -> `saves/bot_decisions.jsonl` (82 MB, gitignored, rebuild ~1 min) |
| Eval / fit | `python3 -I tools/bot_policy.py eval [v1/v2]`, `... fit` | fit = conditional logit (softmax over the legal moves), AdaGrad, L2 0.01, 300 iters on the tuned games -> `data/bot_policy.json` |

## Data (27 Oct)

13168 bot decisions from 12 games (tuned 12826 in 11 games, held-out ed6cb932 342 decisions, turns 1-5 only).
Mean 64 legal moves per decision. Bot logged actions the replay can't reproduce (0.6%) are left out.

## Agreement (top-1 / top-3; tie-aware), 27 Oct

"all" = the bot's move among every legal move; "actor" = among the moves of the same unit/city (research: among
research moves), i.e. what the bot did given who acted. Random = 1/n, 3/n on the same sets.

| | v1 rules tuned | v2 fitted tuned | random tuned | v1 held | v2 held | random held |
|---|---|---|---|---|---|---|
| all, top-1 | 0.216 | **0.297** | 0.101 | 0.344 | **0.463** | 0.199 |
| all, top-3 | 0.392 | **0.529** | 0.199 | 0.646 | **0.800** | 0.361 |
| actor, top-1 | 0.479 | **0.587** | 0.328 | 0.616 | **0.691** | 0.340 |
| actor, top-3 | 0.772 | **0.859** | 0.653 | 0.841 | **0.932** | 0.652 |
| top move's class = bot's | 0.432 | **0.579** | | 0.490 | **0.684** | |

Per move type (actor top-1, tuned v1 -> v2, random): Step 0.389 -> 0.476 (0.219), Attack 0.786 -> 0.828 (0.553),
Train 0.544 -> 0.740 (0.539), Research 0.155 -> 0.623 (0.174), village capture 1.000 -> 0.968.
All-moves top-1: captures 0.97/0.99 (v1), attacks 0.45/0.48, EndTurn 0.34 -> 0.63.
v2 never ranks Research/Build first among all moves (top-1 0.00): the bot does them at a point in the turn the
features don't see (order). Fine for sampling (probabilities), a gap for argmax.
