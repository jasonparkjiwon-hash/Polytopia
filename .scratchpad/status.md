# Status

_Last updated 2026-10-23._

## Now

- **Phase 1 (data and verification) is done.** All six exit gates passed on
  2026-10-23 (`docs/polytopia_ai_phase_1_spec.md`).
- **Phase 2 (advisor mode) is next**, and starts only when Jason says go.
- Before Phase 3, load real saves into Polyfish (`docs/simulator_choice.md`).
- **Score baseline:** the expected `check.sh` output is under "Quick start" in
  `README.md`. That's the one copy. Update it there when scores change.
- **Saves:** the raw saves are committed in `saves_raw/`; `sh scripts/restore_saves.sh`
  rebuilds `saves/` for everyone, so both people's `check.sh` scores match.

## Who's on what

| Person | Working on |
|---|---|
| Jason | — |
| Minjae | — |
| Claude (orchestrator) | Polish program (backlog "Polish"): runs the four sessions below and merges their results |
| Claude: polish-oasis | Unit misses, Oasis Struggle (`af181c8f`) |
| Claude: polish-botwar | Unit misses, bot war (`6e1bf8e0`) |
| Claude: polish-stars | Star tail (`engine/economy.py`) |
| Claude: polish-rules | Unverified rules as flagged switches, rule labelling, wiki cross-check |

## Waiting on Jason

- Embassy price check: note your stars right before building one embassy, right after, and at your next turn start (saves say a net 4, you and the card say 5).

- Round 3, items 35–40 on the test sheet: controlled tests for the rules the engine
  marks unverified (peace-break disband, embassy price/income, Market, Clathrus, Raft
  Break Ice, Aquarion tech names 39/47; 46 is now known: Marine Life).

- Waterworld and other new saves as he plays.
- The Aquarion wiki page or tech list (backlog item 1).
- Round 2, items 26–34 on the test sheet
  (`docs/polytopia_open_questions_to_fill_in_while_playing.md`).

## Decided

- **Notebook:** only Jason rebuilds `notebook/polytopia_engine.ipynb` (about
  400 KB, conflicts on nearly every merge otherwise). Minjae's PRs leave it alone.
