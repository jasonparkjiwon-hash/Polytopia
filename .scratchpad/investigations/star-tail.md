# Star tail: 57 star player-turns off

_Owner: polish-star session · started 2026-10-23_

Copy this file to `investigations/<short-name>.md` when starting a hunt. Update
it before clearing the chat, so a fresh chat can continue from here alone.
Delete it once the conclusion is in the ledger or `lessons.md`.

## Symptom

Which unit(s), at which checkpoint: expected vs what the engine gets.
The command that shows it:

```sh
python3 -I tools/miss.py --list
python3 -I tools/trace.py <game> <turnA> <turnB> x,y ...
```

## Tried

- <change or `RULES` switch> → <scores before → after>. Kept / reverted.

## Ruled out

- <idea> — <why>

## Current theory

## Next step

## Notes from the orchestrator (23 Oct)

- Kept: besieged capital loses the bot bonus (`BONUS_NEEDS_FREE_CAPITAL`), 754 -> 762.
- Ruled out: meet-star score timing. Variants max(before,after), after only,
  before-or-after, average all scored 726-730 vs 762 baseline.
- Five single-turn + misses left: 09a5bf1e t4->5 p1 (+2), t6->7 p1 (+1), t7->8 p7 (+2, met 3 tribes, a ruin);
  af181c8f t25->26 p14 (+2, Break Ice, city reward); e15f392c t4->5 p3 (+2, ruin, and tribes 11 and 13 newly met p3
  while p3's own Encountered list did not change). None has a new or negative-population city.
- City reward residual tally (single reward, one turn, no ruin): reward 1: 22 exact/1 off, 3: 51/1, 4: 26/1, 5: 10/1, 6: 5/0, 7: 13/0.
