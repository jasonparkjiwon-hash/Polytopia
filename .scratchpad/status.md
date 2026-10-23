# Status

_Last updated 2026-10-23._

## Now

- **Phase 1 (data and verification) is done.** All six exit gates passed on
  2026-10-23 (`docs/polytopia_ai_phase_1_spec.md`).
- **Phase 2 (advisor mode) is next**, and starts only when Jason says go.
- Before Phase 3, load real saves into Polyfish (`docs/simulator_choice.md`).
- **Score baseline:** the expected `check.sh` output is under "Quick start" in
  `README.md`. That's the one copy. Update it there when scores change.

## Who's on what

| Person | Working on |
|---|---|
| Jason | — |
| Minjae | Trying out this scratchpad layout on the `scratchpad-restructure` branch of the fork |

## Waiting on Jason

- Per-turn saves of a fight-heavy Crazy game.
- Round 2, items 26–34 on the test sheet
  (`docs/polytopia_open_questions_to_fill_in_while_playing.md`).
- A shared copy of `saves/` for Minjae.

## Needs a decision (two people now)

- **Who rebuilds the notebook?** `notebook/polytopia_engine.ipynb` is about
  400 KB and regenerated after every engine change, so if both people rebuild
  it, nearly every merge will conflict. Suggestion: only Jason rebuilds it,
  and Minjae's PRs leave it alone.
- **How saves are shared**, so both people's `check.sh` scores mean the same
  thing (for example, a shared Drive folder).
