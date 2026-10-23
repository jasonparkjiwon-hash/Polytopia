# Bot war (6e1bf8e0) t5-15: unit misses, saves 4-6 turns apart

_Owner: polish-botwar session · started 2026-10-23_

## Symptom

Started at 23 unit misses (t5->11: 2, t11->15: 21). Saves exist only at t5, t11, t15.

```sh
python3 -I tools/miss.py --game 6e1bf8e0 --list | grep unit
```

Miss tuples are `(save, engine)`: `(owner, type, x, y, hp, promotion)`.

## Tools

`python3 -I tools/unit_hist.py <game> <turnA> id id ... [--all]`: replays from save turnA to the next
save, prints every action that changes those units, with the attack event (attacker hp, defender
hp, bonus, dmg, ret).
Save units near a tile: a 15-line scratch script (`near.py`: tile, id, tribe, type, hp, CreatedTurn).

## Tried

- `ruin_unseen_swordsman` + `kill_move_needs_climbing` (new switches) → units 4709/4753 → 4715/4745,
  stars 762/819 held. Each alone: 4714/4746 and 4709/4754. Kept. t5->11 now 0 misses.

## Ruled out

## Current theory

- t5->11 solved: XinXi unit 165 came from ruin (0,6) (action 777), died before t11, so no save named it
  and the engine summoned it as a Warrior. As a veteran Swordsman every fight fits exactly. Then
  the Luxidoor Giant's kill on mountain (1,8) at 1214 must not move in (no Climbing).

## Next step

- t11->15: 21 misses. Work them one by one with `hist.py 6e1bf8e0 11 <id>`.
