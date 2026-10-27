# bot-policy (Phase 6 groundwork, for win % in Phase 5)

_Owner: bot-policy session · started 2026-10-27 · state: v1, v2 + playout check + calibration done (handoff)_

**Parallel work:** bot-policy-2 (86429b1) built a two-stage policy at the same time (`botpolicy2.rs`, `pfbot`,
`tools/bot_policy2.py`, `tools/bot_dist.py`, `data/bot_policy_v2.json`, notes `bot-policy-2.md`). This one is its
"v3 idea 3": one softmax over all legal moves, fitted in pure Python (fine: 1 s per iteration, 13k decisions, 64
moves on average). Its ledger id clashed: this session's model is **BOT-POLICY-LOGIT**, theirs BOT-POLICY-V2.
Not directly comparable numbers: theirs are totals over windows and two-stage agreement. Where they meet: both
take captures first; theirs piles up stars (held-out k=1 stars 48 vs real 29) and gets units closer (28 vs 32);
this one's EndTurn offset matches stars (k=2 mean +0.88 vs +0.62) but trains too little (units +0.68 vs +1.07).
Merging them (or one shared distribution tool) is for the orchestrator to decide.

Goal: a policy that plays the built-in bots inside the forward model (Polyfish, `sim/pfcore`) so simulated
futures look like real ones. Win % = playouts with this policy for the opponents.

## What exists

| Thing | Command | Notes |
|---|---|---|
| Features + policy | `sim/pfcore/src/botpolicy.rs` | per legal move: class, kind x turn bucket, attack preview (kill, damage, return), step geometry (toward villages/enemy cities/ruins, enemies, fog, capital), train/research/build/reward ids, forward-model outcome (simulate_move on a clone: enemy kills/HP, own HP, stars, pop, cities). `score_v1` (hand rules), `Weights` (v2), `pick` (softmax / argmax), `play_turn`. |
| Data | `PF_DECISIONS=1` in `pfreplay` (2-line hook) -> `python3 -I tools/bot_policy.py collect` | every legal logged bot action with all its legal alternatives -> `saves/bot_decisions.jsonl` (82 MB, gitignored, rebuild ~1 min) |
| Playouts | `target/release/botplay <policy> <save> <player> <rounds> <seeds> -- <later saves>`, `python3 -I tools/bot_policy.py play [--held] [--rounds 2] [--seeds 5] [--every 3] [--policy v2/v1/random] [--endbias x]` | every player plays the policy from a real save; per bot tribe deltas (units, cities, stars, techs, casualties, kills) vs the real later saves |
| Eval / fit | `python3 -I tools/bot_policy.py eval [v1/v2]`, `... fit` | fit = conditional logit (softmax over the legal moves), AdaGrad, L2 0.01, 300 iters on the tuned games -> `data/bot_policy.json` |

## Data (27 Oct)

13168 bot decisions from 12 games (tuned 12826 in 11 games, held-out ed6cb932 342 decisions, turns 1-5 only).
Mean 64 legal moves per decision. Bot logged actions the replay can't reproduce (0.6%) are left out.

## Agreement (top-1 / top-3; tie-aware), 27 Oct, after the turn-order features

v2 = the playout policy (fitted weights + captures first + offsets; numbers below with EndTurn -1.5, no Train offset;
with the final offsets (EndTurn -1.25, Train +1.0): all top-1 tuned 0.345, held 0.533; actor unchanged). 12849 tuned / 342 held-out decisions.

| | v1 rules tuned | v2 tuned | random tuned | v1 held | v2 held | random held |
|---|---|---|---|---|---|---|
| all, top-1 | 0.216 | **0.350** | 0.102 | 0.344 | **0.531** | 0.199 |
| all, top-3 | 0.392 | **0.602** | 0.200 | 0.646 | **0.829** | 0.361 |
| actor, top-1 | 0.479 | **0.587** | 0.328 | 0.616 | **0.691** | 0.340 |
| actor, top-3 | 0.772 | **0.855** | 0.653 | 0.841 | **0.936** | 0.652 |
| top move's class = bot's | 0.432 | **0.621** | | 0.490 | **0.731** | |

Per move type, given the actor, tuned (v1 -> v2, random): Step 0.389 -> 0.467 (0.219), Attack 0.786 -> 0.83
(0.553), Train 0.544 -> 0.74 (0.539), Research 0.155 -> 0.62 (0.174), village capture 1.00. Held-out, given the
actor: Step 0.61, Attack 0.94 (n=16), Train 0.83, Research 0.71 (n=31).
"all" = the bot's move among every legal move; "actor" = among the moves of the same unit/city (research: among
research moves), i.e. what given who. Random = 1/n, 3/n on the same sets.

What the fit says (weights, data/bot_policy.json): units act roughly in unit-list order (ord:first +1.2,
BOT-UNIT-ORDER 74% vs 43% random), trains after all units acted (+0.85, BOT-TRAIN-LAST 77%), stepping onto a
village/city/ruin +1.16 and -0.36 per tile farther from one, leaving the own city -0.64, attacks: target price
+0.57/5 stars, return damage -0.41/5 HP, kill +0.29 plus forward-model enemy kill/HP.

## Distribution check (playouts, 27 Oct)

Every player (the human too) plays the policy from a real save for 2 rounds; per bot tribe, the change in the
counts vs the real later save. Tuned games, every 4th checkpoint, 3 seeds (n=358 bot tribes); held-out ed6cb932
t1-t3 starts, 5 seeds (n=45). "inside" = real value within the simulated min-max over seeds.

| after 2 rounds, mean per bot tribe | real | v2 sim | v2 inside | v1 sim (argmax) | random sim |
|---|---|---|---|---|---|
| held: units | +1.07 | +0.68 | 0.87 | +0.87 | +0.28 |
| held: cities | +0.38 | +0.25 | 1.00 | +0.38 | +0.03 |
| held: stars | +0.62 | +0.88 | 0.82 | -0.56 | +0.64 |
| held: techs | +1.13 | +1.44 | 0.82 | +1.82 | +1.68 |
| held: casualties / kills | +0.22 / +0.22 | +0.21 / +0.22 | 0.96 / 0.98 | +0.42 / +0.42 | +0.07 / +0.06 |
| tuned: units | +1.02 | +0.69 | 0.70 | +0.74 | +0.08 |
| tuned: cities | +0.24 | +0.18 | 0.96 | +0.24 | +0.03 |
| tuned: stars | +0.51 | +0.25 | 0.62 | -0.79 | +0.01 |
| tuned: casualties / kills | +0.67 / +0.68 | +0.86 / +0.76 | 0.86 / 0.90 | | |

Calibration (chosen on tuned playouts only): the raw fit ends turns too early when sampled (stars +3.5 vs +0.5);
EndTurn offset -1 / -1.5 / -2 / -3 gave stars +1.01 / +0.25 / -0.25 / -0.67, so -1.5. Captures first raised
cities from +0.10 to +0.18 (real +0.24).

### Final calibration: Train +1.0, EndTurn -1.25 (chosen on tuned playouts)

Tuned, 2 rounds (n=358): base (End -1.5) units +0.70 / stars +0.33 / techs +0.79, MAE units 0.84 stars 2.43;
Train +0.5: +0.83 / +0.22; Train +1.0: +0.90 / +0.16; **Train +1.0 End -1.25: units +0.89 (real +1.02), stars
+0.48 (+0.51), techs +0.74 (+0.73), cities +0.17 (+0.24); MAE units 0.77, stars 2.39, techs 0.51.**
Held-out with it, 5 seeds, mean per bot tribe real / sim (inside range):

| | 1 round | 2 rounds |
|---|---|---|
| units | +0.56 / +0.54 (0.96) | +1.07 / +0.80 (0.87) |
| cities | +0.11 / +0.12 (1.00) | +0.38 / +0.24 (0.98) |
| stars | +0.20 / +0.60 (0.93) | +0.62 / +1.12 (0.80) |
| techs | +0.60 / +0.63 (0.87) | +1.13 / +1.36 (0.73) |
| casualties / kills | +0.07 / +0.08 | +0.22 / +0.27 |

Mixed on held-out against the End -1.5 version: units closer (MAE 0.45 vs 0.51), stars further (2.40 vs 1.97).
Kept because it was chosen on tuned data only; held-out is 45 tribe-rounds of an early Crazy game.

## Gaps / next

1. Units still a bit low and cities taken low at 2 rounds (cities +0.17-0.24 vs +0.24-0.38): bot-policy-2 sees
   the same drift and blames missing multi-turn plans (units walking to a target). A per-unit persistent target
   in the playout loop is the next thing to try.
2. Research/Build never top-1 among all moves: order inside the turn. Fine for sampling.
3. Held-out is small (turns 1-5, 342 decisions, 16 attacks). A long held-out Hard and a Crazy game exported every
   turn would test combat and late game (request in status.md).
4. Hard vs Crazy: DifficultyHandicap is 2 for Hard, 4 for Crazy (09a5bf1e, 6e1bf8e0 and the held-out ed6cb932 are
   Crazy; 1bf60251 has 1). Kind x crazy crossings changed held-out top-1 0.534 -> 0.531: no visible difference in
   move choice (as sim-dist found). So held-out = Crazy, tuned = mostly Hard; the policy transfers.
   (Tuned playout rows were run before this fix; held rows after.)
5. The human player is played by the same policy in playouts; for win % the user side is our own search.
6. Speed: a feature pass clones once and simulates every non-step move; early-game playouts run ~1 s for 16
   tribes x 2 rounds; mid-game unmeasured. fm-speed's movegen cache will help.
