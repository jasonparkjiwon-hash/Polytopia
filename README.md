# Polytopia AI

Claude as a wartime general for The Battle of Polytopia: an advisor (later a
planner) that beats the built-in bots using a sourced rules dataset, a forward
model, fog inference and search.

## Docs

- [`docs/roadmap.md`](docs/roadmap.md) — the seven phases and their exit tests.
- [`docs/phase1-spec.md`](docs/phase1-spec.md) — Phase 1 (data) exit gates,
  evidence ladder (L0–L3), data paths and status board.
- [`docs/open-questions.md`](docs/open-questions.md) — the in-game test sheet
  and save-file checklist.

Live versions: [roadmap](https://claude.ai/artifact/BRUwionha6Zkjd7fY5WaQz) ·
[Phase 1 spec](https://claude.ai/artifact/K9wQ2L9xnNqnaxfckBGcwp) ·
[open questions](https://claude.ai/artifact/VdTo8Kw8UGqYRQfygEVS2s)

## Intended layout

The code lives in the claude.ai "Polytopia" project and has not been added
here yet. Expected paths, per the docs:

```
polytopia_ai/
  data/
    *.json                  rules dataset (v0.3)
    build_dataset.py        rebuilds the dataset
    validate_dataset.py     self-check
    conflicts_and_gaps.md   conflict table (C1–C29, G1–G12)
  polymap.py                map model (out of date: old weights)
  hidden_tiles.py           hidden-tile model (out of date)
  verify/
    run_all.sh              rebuild dataset + run every check
    state2json              .state save file -> JSON
    analyze_map.py          measure a real map against open conflicts
    c23_models.py           pre-registered capital-resource test
    crosscheck.py           field-by-field comparison with Polyfish
    parse_polyfish.py
```

External engines referenced: Polyfish (game version 115 re-implementation,
used for cross-checks and map generation) and PolyEnv (C++).

## Data

Real `.state` saves stay out of git (see `.gitignore`); keep them in `saves/`
locally.
