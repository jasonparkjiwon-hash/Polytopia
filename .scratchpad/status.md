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
| Claude (orchestrator) | Phase 3 prep (backlog item 0): runs the sessions below |
| Claude: pf-loader | Load saves into Polyfish, score it, legality check |
| Claude: pf-port | Port v123 corrections into Polyfish |
| Claude: sim-dist | Measured distributions for random parts; held-out check |

## Waiting on Jason

- Round 3, item 40 (Aquarion tech names 39/47; 36–38 answered 24 Oct by cards: embassy 4 +2 each, Market, Clathrus). Items 36–38 and 40 on the test sheet: embassy price/income, Market,
  Clathrus, Aquarion tech names 39/47 (35 and 39 answered 23 Oct).

- Waterworld and other new saves as he plays.
- The Aquarion wiki page or tech list (backlog item 1).
- Round 2, items 26–34 on the test sheet
  (`docs/polytopia_open_questions_to_fill_in_while_playing.md`).

## Decided

- **Notebook:** only Jason rebuilds `notebook/polytopia_engine.ipynb` (about
  400 KB, conflicts on nearly every merge otherwise). Minjae's PRs leave it alone.
