# Oasis Struggle (af181c8f): unit misses

_Owner: polish-oasis session · started 2026-10-23_

## Symptom

21 unit misses at start (one spot each). List them with:

```sh
python3 -I tools/miss.py --game af181c8f --list | grep unit
python3 -I tools/trace.py af181c8f <turnA> <turnB> x,y ...
```

Note: miss.py's "exact" counts HP-exact units, so fixing a position miss shrinks the
denominator rather than raising the numerator. Count misses = denominator - numerator.

Helper scripts (scratchpad, not committed; easy to rewrite): one lists every Move/Attack
of a unit id in a turn range; another prints every engine push (ruin, city reward, build
spawn) with the unit's last move, the 8 neighbours and where the next save shows it.

## Tried

- `push_dir_persists` + `push_dir_round` (engine/replay.py, `prime_last_moves` reads the
  last move back from the log when miss.py starts at a checkpoint) → misses 44 → 42
  (af181c8f t4 id18, 6e1bf8e0 t11 id347), stars 762 hold. Kept. Ledger PUSH-DIRECTION.

## Push cases (all saves)

| Case | Last move | Result |
|---|---|---|
| 09a5 t6, 1bf6 t2, 6e1b t5, af18 t24, e15 t4 | this turn | fit Polyfish |
| af18 t4 (26,24) | previous turn, north | pushed north: needs persistence |
| e15 t13 sled (8,10) | previous turn, (-1,-2) | fits only with persistence + rounding |
| 6e1b t11 Scoutship | (-2,-1) | (-1,0): rounding |
| af18 t10 (2,17) CityReward Giant | never moved (trained there) | pushed (-1,+1), AWAY from centre. Open |
| af18 t15 Raychi (14,7) | unclear (its last logged move ended on 13,7) | save (15,7), engine (15,8). Open |

## Ruled out

- Toward-centre for a unit that moved on an earlier turn (af18 t4 contradicts it).

## Current theory

- af18 t10: for a never-moved unit the direction may come from something else (sprite
  `Flipped` field? the spawner?). Only one sample.

## Next step

- af18 t10 (id169) and t15 (id94) pushes; then t24 Swordsman id661 / Giant id491
  (also a CityReward push); then HP misses t10 (id76, id72, Mermaid id110, Warrior id134),
  t15 (id260, id219, id194), t25 (Juggernaut id664 and neighbours, off by 1).
