# Bot war (6e1bf8e0) t5-15: unit misses, saves 4-6 turns apart

_Owner: polish-botwar session · started 2026-10-23 · **done 2026-10-23: 0 misses** (units 4728/4728 in all games)_

## Symptom

Started at 23 unit misses (t5->11: 2, t11->15: 21). Saves exist only at t5, t11, t15.
Now 2 left: t5->11 extra id -94 (a Luxidoor trainee pushed to the wrong tile; the temp id number
shifts between runs), t11->15 Giant 290 at 27 HP (save 29).

```sh
python3 -I tools/miss.py --game 6e1bf8e0 --list | grep unit
```

Miss tuples are `(save, engine)`: `(owner, type, x, y, hp, promotion)`.

## Tools

- `python3 -I tools/unit_hist.py <game> <turnA> id id ... [--all]`: replays from save turnA to the next
  save (earlier segments replayed silently, as miss.py does), prints every action that changes those
  units, with the attack event (attacker hp, defender hp, bonus, dmg, ret).
- Scratch scripts worth recreating (15-25 lines each, same loading code as unit_hist.py):
  `near.py <game> <turn> x,y r` (save units near a tile, with CreatedTurn and Flipped),
  `around.py <game> <action k> x,y r` (engine units near a tile just before action k, with defence bonus),
  `acts.py <game> <type>` (every action of one type with the engine's unit on its tile).

## Tried (all kept unless marked)

- `ruin_unseen_swordsman` + `kill_move_needs_climbing` → units 4709/4753 → 4715/4745. Each alone: 4714/4746
  and 4709/4754. Also closed 428, 309, 388, 177, 310 at t15 (they hung off unit 165's fights).
- Restored Exida, Larva and Moth in `engine/stats.py` (inline `#` comments had swallowed them) → neutral.
- Moth (v123) fitted: defence 2, no retaliation against its attack (`surprise` stand-in), stiff → 4715 → 4717
  (344, 237). Defence 3 scores the same; 0.1 (Polyfish) or with retaliation: no gain. Ledger MOTH-V123.
- `stiff_boat_lands` + Climbing check covers boats + `stomp_on_kill_move` → 4717/4743 → 4721/4741 (223, 326, 295).
- `move_blocked_by_hidden` → 4721/4741 → 4722/4738 (251, 272, 234, 215). Ledger MOVE-BLOCKED-HIDDEN.
- `push_toward_attacker` + `push_centre_round` → 4722/4737 → 4724/4733. Alone: 4721/4736 and 4722/4738.
- `push_port_first_only` → 4725/4733 → 4725/4732. `ruin_boat_passenger` → 4726/4732.
- Totals at pause (after other streams' merges): units 4727/4731, stars 802/819.

## Ruled out

- Moth dies and leaves an InsectEgg that explodes: a fresh egg's blast deals 2 to a full Swordsman, save says 1.
- For Giant 290: own-port defence bonus 1.5 (4721/4741 → 4697/4747); Juggernaut defence 5 or 6 (4719/4741);
  water bonus from Navigation / Sailing / Ramming / Fishing instead of Aquatism (all ~4670/4755).
  Attackers at 1743 (223), 1934 (365, fresh trainee) and 2149 (Scoutship 404, full HP at t15) all hit at full
  strength, so their hits are exact.
- Pushes skip forest (both remaining push cases avoided a free forest): 4727/4731 → 4727/4739 (round on),
  4725/4741 (round off).

## Resolution (after Jason's answers)

- Jason: pushes try the counter-clockwise side first (`push_ccw_first`, added by another stream); no port defence bonus.
- **Trainee -94:** new units face the map centre, nearest of 8 by angle (824/871 saved facings match; the axis
  rounding fitted 756). `push_centre_round = 'angle'`: the trainee at (2,9) faces (1,1), (3,10) is blocked,
  CCW next is (2,10) = save. 4727/4729 → 4727/4728.
- **Giant 290:** a Giant boarding its port as a Juggernaut stomps (`stomp_after_boarding`): Kickoo Warrior 36
  drops to 4 HP, its hit at 1562 does 2, Giant 38→35→32→29 = save. 4727/4728 → 4728/4728.
  Ledger PUSH-NEVER-MOVED (updated), STOMP-ON-BOARDING.
