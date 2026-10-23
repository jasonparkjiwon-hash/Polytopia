# Backlog

Open work only, highest priority first. Owner is whoever is working on it now.
Set it when you pick an item up so two people don't do the same work.

## 1. Economy replay

_Owner: unassigned_

`engine/economy.py` gets about 95% of player-turns exact on the per-turn games.
The Crazy bonus is settled (3 a turn). Still open: structure 51, and Embassy,
Market and Clathrus income, which are coded but not yet seen in a save.

## 2. Coverage report

_Owner: unassigned_

Which rules each replay actually exercises, so we know which rules are
untested.

## 3. Remaining replay mismatches

_Owner: unassigned_

Bot war turn 15 is off by 12 HP, and Misty Fields has a few leftover units.
Known suspect: ruin reward weights. Start a file in `investigations/` when
you pick this up (see `investigations/_template.md`).
