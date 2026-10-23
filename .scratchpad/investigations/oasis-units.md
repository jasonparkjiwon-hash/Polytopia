# Oasis Struggle (af181c8f): unit misses

_Owner: polish-oasis session · 2026-10-23 · **DONE: 0 unit misses** (was 21)_

```sh
python3 -I tools/miss.py --game af181c8f --list | grep unit      # prints nothing now
```

miss.py's "exact" counts HP-exact units; a position miss also adds to the denominator.
Misses = denominator - numerator. Combined total at the end: 4727/4729 units (2 bot-war
misses left), stars 802/819.

## Kept (each A/B'd on the combined total, units and stars held or improved)

| Switch (engine/replay.py) | Case | Ledger |
|---|---|---|
| `push_dir_persists`, `push_dir_round` (+ `prime_last_moves`) | t4 Warrior id18: pushed the way it walked the turn before | PUSH-DIRECTION |
| `polaris_capture_freezes` | t13 Warrior id105: Polaris took 9,16 and the water around froze | POLARIS-CAPTURE-FREEZE |
| `idle_auto_recover` (human only; `saved_acted` in state.py) | t15 Rider id260 healed with no action | IDLE-AUTO-RECOVER |
| `explode_poison_halves` | t15 Warrior id219, Defender id194: poisoned targets of a Boomchi | EXPLODE-POISON-DEFENCE |
| `push_saved_facing` (UnitDirection byte 2) | t15 Raychi id94 | SAVE-UNIT-FACING |
| `push_ccw_first` (+ `push_no_room_removes`), confirmed by Jason | t10 Warrior id169 | PUSH-TIEBREAK |

The botwar stream's fixes (ruin Swordsman, kill move-in rules, no-move push toward attacker,
Juggernaut follows a kill) cleared the other Oasis misses (t10 HP, t19, t24, t25 trio).

## Tried and reverted

- `push_unmoved_reverse` (never-moved unit pushed opposite to its owner's last move): 2/4.
- `explode_full_hp` (Boomchi explodes at full strength): +9 misses.
- `idle_auto_recover` for AI players too: +57 misses (bots' idle units don't heal).
- `push_saved_facing` for never-moved units too: t10 goes onto the port. Net hold.

## Open (weak evidence; in-game tests would settle them)

- IDLE-AUTO-RECOVER: confirmed by Jason (+4 friendly, +2 elsewhere, capped, not poisoned). Open:
  why AI idle units never heal in the saves; whether allied territory counts as friendly.
- PUSH-TIEBREAK: confirmed by Jason (counter-clockwise first; no room removes the unit).
- POLARIS-CAPTURE-FREEZE: does Polaris border growth freeze water too?
- What sets a new unit's facing (UnitDirection) before it first moves.
