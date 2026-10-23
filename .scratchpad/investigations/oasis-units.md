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
- (botwar's ruin-Swordsman and kill-move-in fixes cleared t10 HP, t15 Defender and several others.)
- `push_unmoved_reverse` (a never-moved unit is pushed opposite to its owner's latest Move) →
  fits af18 t10 and t24, fails t19 (fits only the move before the latest) and breaks t15
  (CityReward at 20,22, which plain toward-centre gets right). Misses 28 → 30. Reverted.
- `polaris_capture_freezes`: a Polaris city capture freezes water around the city
  (af18 t13, Battle Sled takes 9,16; Warrior id105 walks onto 9,15 on foot) → misses 28 → 27. Kept.
  Ledger POLARIS-CAPTURE-FREEZE.
- (botwar's Juggernaut kill-move-in fix cleared the t25 trio.)
- `idle_auto_recover`: the human player's idle wounded units heal at his End Turn (t15 Rider
  id260, 6 -> 10). For all players it adds 57 misses, so human only (AutoPlay 0). Needs the
  save's Moved/Attacked flags because Jason's t14 save is mid-turn. Misses 19 -> 18. Kept.
  Ledger IDLE-AUTO-RECOVER; in-game test request in the gaps file.
- `explode_full_hp` (Boomchi explodes at full strength) → misses 14 → 23. Reverted.
- `explode_poison_halves`: poison halves the target's defence in an explosion too (t15
  Warrior id219, Defender id194; the save's UnitEffects showed both poisoned) → 13 → 12. Kept.
  Ledger EXPLODE-POISON-DEFENCE.

## Push cases (all saves)

| Case | Last move | Result |
|---|---|---|
| 09a5 t6, 1bf6 t2, 6e1b t5, af18 t24, e15 t4 | this turn | fit Polyfish |
| af18 t4 (26,24) | previous turn, north | pushed north: needs persistence |
| e15 t13 sled (8,10) | previous turn, (-1,-2) | fits only with persistence + rounding |
| 6e1b t11 Scoutship | (-2,-1) | (-1,0): rounding |
| af18 t10 (2,17) CityReward Giant | never moved (trained there) | pushed (-1,+1), AWAY from centre. Open |
| af18 t19 (2,17) CityReward Giant | Defender trained there this turn | pushed (+1,0) onto own port; centre rule says (3,16). Open |
| af18 t24 (6,12) CityReward Gaami | Swordsman trained there this turn | pushed (+1,-1) to (7,11); centre rule says (6,13) Ice+Outpost. Open |
| af18 t15/t21 (20,22) CityReward | never moved | toward-centre fits |
| af18 t15 Raychi (14,7) | unclear (its last logged move ended on 13,7) | save (15,7), engine (15,8). Open |

## Ruled out

- Toward-centre for a unit that moved on an earlier turn (af18 t4 contradicts it).

## Current theory

- City-reward pushes of a unit trained that turn (af18 t10, t19, t24): 3 of 5 never-moved
  cases miss the toward-centre rule. Same city (2,17) chose differently at t10 and t19 with the
  same free tiles, so no rule from the map alone fits: the game must hold hidden per-unit state
  (Polyfish's prev_coords is not saved). Ideas tried: reverse of the owner's last move (2/4),
  `Flipped` facing (new units mostly face right, doesn't give a y component). Likely not
  deterministic from save data; 5 miss lines (t10 id169, t19 id489 + temp, t24 id661 + temp).
  An Outpost (imp 33) on Ice/Water blocking pushes would make t24 fit the move-direction story;
  untested.

## Next step

- t15 Raychi id94 ruin push (its last logged move ended on 13,7, but it stood on 14,7);
  t25 Juggernaut id664 + Warrior id723 + Scoutship id721, each 1 HP high in the save
  (off by one: rounding or a heal?).
