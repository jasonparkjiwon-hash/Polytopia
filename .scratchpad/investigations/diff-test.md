# diff-test (28 Oct 2026)

_Owner: diff-test · state: in progress_

Order from Jason: chase the last engine misses with new methods (differential testing, residual clustering, hypothesis search, leave-one-game-out), not by tracing one by one.

## Tool: `python3 -I tools/engine_diff.py [--turns] [--game <id>] [--pickle f]`

Runs the referee and Polyfish on every checkpoint pair of all 18 games (held-out too, marked H) and sorts every unit row and every player's stars into:
both-right / ref-only (Polyfish wrong) / pf-only (referee wrong) / both-same (missing in both) / both-differ. 16 s.
Note: referee rows with an integer HP (`10` not `10.0`) are oracle-placed spawns (INFILTRATE-SPAWN reads the next save), so "ref-only" there is not a real referee win.

## Results

| Date | Finding | Class | Kept |
|---|---|---|---|
| 28 Oct | Quetzali Pirate/Raft (710ddb20 t18->19): a boarding Dagger becomes a Pirate | pf-only | already pushed by web-deep (PIRATE-BOARD); same cause found independently here |
| 28 Oct | Two Warrior HP rows (710ddb20 id439, 64795ee3 id1): a unit that captured / examined ruins is not idle | pf-only | already pushed by web-deep (CAPTURE-RUIN-ACT); same cause found independently here (Polyfish's `end_unit_turn` in the capture/ruins moves) |

Lesson: web-deep reads the same Polyfish source, so pf-only rows get fixed twice. Pull before starting a fix; the tool's value from here is the both-same / both-differ rows and the clustering below.
