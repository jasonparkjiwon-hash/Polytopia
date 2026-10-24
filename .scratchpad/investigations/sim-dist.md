# sim-dist (Phase 3 prep, see backlog item 0)

_Owner: sim-dist session · started 2026-10-24 · state: first pass done_

## What exists now

| Thing | Command | Notes |
|---|---|---|
| Held-out check | `python3 -I tools/miss.py --holdout` | `data/holdout.json` (empty so far). Plain `miss.py` leaves held checkpoints out; `--all` scores everything. Protocol in README under the baseline. |
| Distributions | `python3 -I tools/distributions.py [--rows]` | Writes `data/distributions.json` (counts, n, Wilson 95%). Ledger: DIST-RUIN-REWARD, DIST-CITY-REWARD, RUIN-UNIT-CYMANTI. |
| Bot turns | `python3 -I tools/bot_turns.py [--summary]` | Writes `data/bot_turns.csv`, 1163 player-turns (1084 bot) from 6 games. |

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

## Not measurable from current saves

- Sanctuary / animal spawns: no Sanctuary built and no wild units in any save.
- Starfish: only map-gen counts (STARFISH, already in data/); no respawn data.
- Bot war saves are 4-6 turns apart, so its ruins are only resolvable when one ruin per
  player per window.

## Next step

1. Bot research opener vs resources around the capital (initialTiles).
2. Attack decision vs predicted outcome (kill / damage ratio) using engine fight on a copy.
3. When Jason sends a new save: put it in holdout first, score, record.
