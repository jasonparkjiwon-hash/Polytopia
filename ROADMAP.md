# Polytopia AI: roadmap (saved 2026-10-22)

Live versions are kept as Claude Docs:

- Roadmap: https://claude.ai/artifact/BRUwionha6Zkjd7fY5WaQz
- Test sheet: https://claude.ai/artifact/VdTo8Kw8UGqYRQfygEVS2s

This file is the plain copy for future sessions.

## Goal

Claude acts as a wartime general for Polytopia. Jason is the president. The general beats the built-in bots through search, a forward model, fog inference and exploit-finding. The first interface is advisor mode: Claude advises while Jason plays the real game.

## Status

- **Phase 1 (data):** dataset v0.3 is done.
  - The project copies are `claude/polytopia_dataset_v0.3.json`, `claude/conflicts_and_gaps.md` and `claude/build_dataset_v0.3.py.txt`.
  - Source priority: dated patch notes (NamuWiki, 2025 balance pass) beat the PolyEnv engine, and the engine beats the undated fandom wiki.
  - Still open, and needing Jason's games:
    - C23: resources around a capital (the top test)
    - G3: stale or live fog
    - C8: water tech gates
    - C19: tile action costs
    - C14: ruin odds
    - C18: meeting reward
  - The fandom Fog of War, Bots, Resources, Starfish, Whale, Vision and AI pages return client errors from the cloud.
  - Solaris (G12) is a new tribe that nothing covers yet.
- `polymap.py` and `hidden_tiles.py` are OUT OF DATE (old weights, radius-2 reveal).

## Decisions Jason still has to make (asked in the roadmap doc)

- **Tribe:** suggest Imperius, Bardur or Xin-xi.
- **Map and mode:** suggest normal-size Lakes, Domination, 2-3 bots.
- **Difficulty:** suggest Hard first.
- **How he sends the state:** suggest a screenshot plus a note on turn 0 and whenever something new appears, typed otherwise.
- **Advice format:** suggest the top 3 moves with reasons, plus a threat line.
- **Goal:** Domination on Crazy, a high Perfection score, or both.

## Phase 1 spec (added 2026-10-23)

Phase 1 is now governed by the Phase 1 spec doc: https://claude.ai/artifact/K9wQ2L9xnNqnaxfckBGcwp

The advisor stays on hold until all six gates pass:

- **A.** Core rules at L1 or above.
- **B.** C23, C10 and C9 decided by pre-registered tests.
- **C.** A real `.state` file analysed (or 10 or more capitals logged).
- **D.** Fog measured at L3.
- **E.** The dataset rebuilds and every check passes, with version stamps.
- **F.** The simulator base chosen.

The tools are in `claude/verify_tools.md` (state2json, analyze_map, c23_models, the Polyfish cross-check).

Polyfish (HenBOMB/Polyfish, Apache-2.0 engine, game version 115) is the strongest reference engine found so far.

2026-10-23 07:00 update:

- **Device:** Jason plays on an iPhone and has no save files, so Gate C becomes 15 or more test-sheet capitals.
- **Polyfish engine:** it now builds offline from GitHub-vendored crates (`sim/`). crates.io is no longer needed.
- **Polyfish map generator:** its maps are treated as a model, not ground truth, because its Drylands maps come out about half water.

Earlier asks (now answered):

- His device (to find .state files).
- Allow index.crates.io and static.crates.io in Settings > Capabilities (needed to build Polyfish).
- Q1 and Q2 data.

## Phases (each with an exit test)

1. **Data.** Exit: the top 7 tests are answered.
2. **Advisor v1.** Build a state file, a belief file, a rules lookup and a fixed per-turn reply. Exit: 3 wins on Hard, plus a log of model errors.
3. **Forward model.** Lean: a Python engine built from the dataset. The alternative is patching PolyEnv; these are the patches it would need:
   - retaliation keeps the defence bonus
   - no retaliation from fog
   - backwards research
   - Burn Forest costs 3
   - temples score 100 per level
   - all 16 capital guarantees
   - the tribe terrain table
   - bot income is the TOTAL capital income

   Exit: 95% of logged fights and star totals predicted exactly.
4. **Fog inference.** Update `polymap.py` and `hidden_tiles.py`, then track beliefs about unseen tiles and enemy units. Exit: predictions beat chance on tiles Jason later scouts.
5. **Search.** Plan several turns ahead over sampled hidden maps, with an evaluation function. Exit: beats Phase 2 judgement in replays.
6. **Bot model and self-play exploits.** Exit: exploits that hold up in the real game.
7. **Directives to objectives.** Jason gives orders only. Exit: wins on Crazy.

## Next session

1. Jason answers the decisions.
2. Claude builds the advisor kit.
3. Turn 0 screenshot (it also answers Q1-Q3).
4. The first 10 turns together, logging every model error.
5. Fold the corrections back into the dataset.
