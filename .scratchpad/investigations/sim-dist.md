# sim-dist (Phase 3 prep, see backlog item 0)

_Owner: sim-dist session · started 2026-10-24 · state: second pass done (bot rules)_

## What exists now

| Thing | Command | Notes |
|---|---|---|
| Held-out check | `python3 -I tools/miss.py --holdout` | `data/holdout.json` (empty so far). Plain `miss.py` leaves held checkpoints out; `--all` scores everything. Protocol in README under the baseline. |
| Distributions | `python3 -I tools/distributions.py [--rows]` | Writes `data/distributions.json` (counts, n, Wilson 95%). Ledger: DIST-RUIN-REWARD, DIST-CITY-REWARD, RUIN-UNIT-CYMANTI. |
| Bot turns | `python3 -I tools/bot_turns.py [--summary]` | Writes `data/bot_turns.csv`, 1163 player-turns (1084 bot) from 6 games. (Committed csv predates ed6cb932; rerunning adds it: filter `game` when tuning.) |
| Bot attacks | `python3 -I tools/bot_attacks.py [--summary]` | Writes `data/bot_attacks.csv`: every bot unit's first action with a target in range (engine `fight()` per target on the live state) and every bot attack's target list. 2431 rows. |
| Bot rules | `python3 -I tools/bot_rules.py` (after bot_attacks) | Writes `data/bot_rules.json`: BOT-RESEARCH-OPENER, BOT-ATTACK-DECISION, BOT-ATTACK-TARGET, each scored on training and held-out separately, with baselines and Wilson 95%. |

## Held-out protocol

1. A new save goes into `data/holdout.json` `held` (full save id; optional `from_turn` when
   an old game is continued) before anyone looks at its misses.
2. Score once with `--holdout`; record date, units, stars and the commit in `scored`, and in README.
3. Tuning loops use plain `miss.py`, which skips held checkpoints.
4. Move to `released` (dated) to start fixing its misses; never back.
All current saves are training data (every rule was tuned on them), so `held` starts empty.

## Ruin rewards (n=56 examined in per-turn windows, 54 classified)

How a ruin is classified: unit on the ruin tile that turn / tech without Research / star check
+10 (hard signals), or 30+ unexplained newly visible tiles (explorer; false positive 1/674)
/ capital TotalPopulation +3 beyond builds (pop; false positive 8/709) (soft signals; a hard
one wins). Result: stars 14, pop 16, tech 11, unit 7, explorer 6. Uniform 1/5 fits
(chi-square 6.95, df 4, p=0.14). Whole-game cross-check: free techs per ruin 14/57.
- Water ruins (n=10): explorer 0/10, pop 5/10. Thin.
- Cymanti: land unit = Mantis, water unit = Boomchi (n=1 each). Other tribes: Swordsman,
  Rammership + veteran Warrior.
- Polyfish (`sim/pfcore`) has the RuinsRewardType enum but no reward logic or weights: no
  conflict, it simply lacks it. pf-port should implement: uniform over eligible
  {stars 10, tech, pop +3 capital, explorer, tribe unit}.
- Explorer eligibility (RUIN-REWARD open point) not settled: needs ruins where the 5x5 is
  fully explored. Turns > 7 show more pop (11/25), as expected if explorer/tech drop out.

## Bot city rewards (n=300 bot choices)

Level 4: Border Growth 36/36. Level 5+: Super Unit 14/14 (treat both as deterministic).
Level 2: Workshop 94 / Explorer 65. Level 3: Wall 48 / Resources 43. No dependence found on
tribe, difficulty, capital or turn (scratch split; small cells). Next: try local features
(enemy units near the city for Wall; fog near the city for Explorer).

## Bot behaviour (first look, `--summary`)

- Research opener: most tribes start Fishing then Sailing; tribe tech first for Polaris
  (IceFishing/Sledding) and Aquarion (47, 39); Mining first for XinXi and Vengir; Hoodrick
  Fishing/Hunting. Likely driven by resources near the capital: test that next.
- Trains: Warrior 597 of ~1150, then Defender 114, Swordsman 97, Rider 47.
- Attacks: 528 of 1084 bot turns had an attack. Of units with a hostile unit in range at the
  turn's first action, 612/1709 (36%) attacked; Crazy 39%, Hard 35%. So "attack whenever
  possible" is wrong; next feature to test: would the attack kill / win the exchange
  (R.fight on a copy), and relation (war vs neutral).
- Peace: 37 offers, 12 accepted, 25 rejected, 1 break.
- City captures by bots: 33 turns with a city capture.

## Bot rules (second pass, 2026-10-24; ledger BOT-*, all L3 statistical)

Held-out = ed6cb932 (turns 1-5 only, so tiny for combat). Training = the other 6 games.

| Rule | Training | Held-out | Baseline (train / held) |
|---|---|---|---|
| BOT-RESEARCH-OPENER | 62/77 (81%) | 14/15 | always Fishing 55% / 67% |
| BOT-ATTACK-DECISION | 791/1195 (66%) | 10/10 | majority 51% / 90% |
| BOT-ATTACK-TARGET | 313/524 (60%) | 2/3 | random 44% / 50% |

- **Opener:** water next to the capital -> Fishing dominates; tribe techs first for Aquarion and
  Polaris; XinXi/Vengir go Mining with 2+ metal. Misses: Kickoo (starts with Fishing, then varies),
  Oumaji (FreeSpirit 2/2). Full list in `opener()` in `tools/bot_rules.py`.
- **Attack decision** (targets taken just before the unit's first action; at turn start the
  rate looked like 36% because other units had already killed the targets): field unit with a
  predicted kill 72% (n=302), field no kill 54% (n=541), unit in its own city 24% (n=202),
  Defender without a kill 11% (n=131). HP, provocation (who hit whom last), human vs bot
  target, tribe barely move it (provoked 58% vs never 39%, confounded). Moving away instead of
  attacking: 22% when no kill, 8% with a kill. So bots are kill-seeking but noisy: model as
  probabilities, not a rule.
- **Target choice:** kill first, then least return damage, then most expensive type. 65% for
  in-place attacks (random 42%), 58% after a move (random 44%): after a move the bot likely
  picked its target before moving, from squares we don't enumerate (needs movement range).
- **Training vs research / unit mix** (bot_turns.csv, descriptive): share of bot turns with a
  train rises with time (49% turns 0-4, 70% 5-9, 82% 10-19, 93% 20+). Warrior is 72% of
  trains before turn 10, 41% turns 10-19, 24% turn 20+ (Defender 20%, Swordsman 13%,
  Rider 10%, Boomchi 10%). Hard vs Crazy at the same turns: units/turn 1.51 vs 1.39 and
  attacks/turn 2.15 vs 2.09 (turns 10-19), 0.74 vs 0.85 units/turn before turn 10: no clear
  difference beyond the star bonus. Not put in data/ yet (confounded with game and turn).

## Not measurable from current saves

- Sanctuary / animal spawns: no Sanctuary built and no wild units in any save.
- Starfish: only map-gen counts (STARFISH, already in data/); no respawn data.
- Bot war saves are 4-6 turns apart, so its ruins are only resolvable when one ruin per
  player per window.

## Next step

1. Target choice after a move: enumerate reachable squares (movement points, terrain, ZOC) so
   the bot's choice can be scored over everything it could reach; same for "move away" moves.
2. Expansion: for each bot village/city capture, was it the nearest unclaimed village to the
   capturing unit? Needs path distance; straight-line is a first cut.
3. Attack decision: try per-player aggression (af181c8f players range 25%-83%) and a
   logistic fit on (kill, dmg-ret, in city, Defender) to give a probability for a forward model.
4. When Jason sends a new save: put it in holdout first, score `tools/bot_rules.py` on it, record.
