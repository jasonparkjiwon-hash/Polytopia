# Backlog

Open work only, highest priority first. Owner is whoever is working on it now.
Set it when you pick an item up so two people don't do the same work.

Score now: 4709/4753 units (99.1%) and 762/819 star player-turns exact
(`python3 -I tools/miss.py`).

## 0. Polish program (Jason, 23 Oct): deterministic parts exact

Goal: every deterministic rule (combat, movement, income, tech cost) matches every
save; random parts (ruins, bot choices) become measured distributions; every rule
the engine uses has a ledger id and level. Four parallel Claude sessions, one
investigation file each in `investigations/`:

| Stream | File | Owns (edit freely) |
|---|---|---|
| polish-oasis | `investigations/oasis-units.md` | Oasis unit misses; combat/move code in `engine/replay.py` |
| polish-botwar | `investigations/botwar-units.md` | Bot war unit misses; same file, so rebase often |
| polish-stars | `investigations/star-tail.md` | `engine/economy.py`; items 1 and 3 below |
| polish-rules | `investigations/flagged-rules.md` | New `RULES` switches for unseen rules, rule labelling, "Not yet in any save", item 4 |

Shared-file rules: small commits; `git pull --rebase origin main` before every
push, then re-run `tools/miss.py` and `check.sh` on the rebased tree; the A/B gate
is the combined total. Ledger edits only through `tools/ledger.py` (on a rebase
conflict in the ledger, take upstream and re-run your ledger command). Don't edit
`CLAUDE.md`.

## 1. Aquarion research (star misses)

_Owner: unassigned_

Tech ids 39, 46, 47 are missing from `TECH`. The saves imply 47 is tier 1 and
39 and 46 are tier 2 (price tier x cities + 4). Name them and add to `TIER` in
`engine/economy.py`. The Aquarion wiki page is blocked from the cloud container
(proxy 403); Jason can paste it or the tech names.

## 2. Unit misses left (44)

_Owner: unassigned_

- Bot war turn 11-15 (23): mostly 1-5 HP off, and units the engine keeps alive.
  Saves are 4 turns apart, so the cause is hard to isolate.
- Oasis Struggle (21): one spot each; trace with `tools/trace.py`. One explosion
  (Oasis t25, three targets 1 HP less) fits no variant.

Start a file in `investigations/` when you pick this up (see
`investigations/_template.md`).

## 3. Other star misses

_Owner: unassigned_

- Single-turn misses of -1 on a bot that attacked (about 10): probably a kill or
  capture reward not modelled.
- Multi-turn gaps (bot war): small errors add up; ignore until the single-turn
  ones are fixed.

## 4. Aquarion unit ids

_Owner: unassigned_

Only 46 Mermaid, 48 Swordsmaid, 53 Shark are named; the other Aquarion ids are
still unknown.

## Not yet in any save

Embassy, Market, Clathrus income; structure 51 price; Dash units breaking ice the
same turn; peace-break disbanding. Nothing to do until a save shows them.
