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
| Claude: sim-dist | First pass done (held-out check, `data/distributions.json`, `data/bot_turns.csv`); see `investigations/sim-dist.md` |

## Waiting on Jason

- Round 3: item 40 answered 24 Oct (Aquarion ids 45 start, 47 Fishing, 46 Marine Life, 39 Aquaculture); 36–38 answered 24 Oct by cards: embassy 4 +2 each, Market, Clathrus). Items 36–38 and 40 on the test sheet: embassy price/income, Market,
  Clathrus, Aquarion tech names 39/47 (35 and 39 answered 23 Oct).

- Waterworld and other new saves as he plays. **Export every turn** (one save per turn, like Misty Fields), not every 4-6 turns: single-turn gaps are what let ruin rewards and bot choices be read off. Each new game goes into `data/holdout.json` first and is scored before any tuning. Most wanted: a water-heavy map (only 10 water ruins so far) and a game where he builds a Sanctuary (no animal-spawn data at all).
- The Aquarion wiki page or tech list (backlog item 1).
- Round 2, items 26–34 on the test sheet
  (`docs/polytopia_open_questions_to_fill_in_while_playing.md`).

## Decided

- **Notebook:** only Jason rebuilds `notebook/polytopia_engine.ipynb` (about
  400 KB, conflicts on nearly every merge otherwise). Minjae's PRs leave it alone.
