# fm-accept (Phase 3: Polyfish as the forward model, see backlog item 0)

_Owner: fm-accept session · 2026-10-27 · state: done (API, suite, gaps below)_

Goal: prove Polyfish (`sim/pfcore`) is usable as the forward model Jason asked for (possible moves and
outcomes, win % from a state, scenarios) and give search a stable API.

## How to run

```sh
sh scripts/restore_saves.sh
(cd sim/pfcore && cargo build --release && cargo test --release; cd ../.. && git checkout sim/pfcore/Cargo.lock)
python3 -I tools/pf_accept.py            # FM ACCEPT lines (also at the end of check.sh, informational), ~40 s
python3 -I tools/pf_accept.py --full     # forward-model checks at every logged legal action (~8 min)
python3 -I tools/pf_accept.py --fails    # + first failing checks and tile-miss examples
python3 -I tools/pf_api.py <save> <player>   # wrapper demo: list moves, play one, undo
sim/pfcore/target/release/pfapi bench <save> 0 4   # speed on one state (0 = tribe with most units)
python3 -I tools/pf_rule_levels.py [--check]       # data/pf_rule_levels.json
```

API docs: `sim/README.md` "Forward-model API". Pieces: `src/api.rs` (library), `src/bin/pfapi.rs`
(moves / serve / bench / dice), `tools/pf_api.py` (Python `Sim`), `src/api_tests.rs` (4 cargo tests on a
generated map), per-action checks inside `pfreplay` (`PF_ACCEPT=n`), tile check `tiles_vs` in pfreplay.

## Acceptance numbers (2026-10-27, after pf-legal-3's commits up to 946395a)

| test | result |
|---|---|
| (a) logged move in the generated list | tuned 13176/13257 = 99.4%, held-out 354/354 = 100% |
| (b) API move on a clone = replay state (whole state) | **13510/13510** (full run); listed with a label 13510/13510 |
| (b) referee at checkpoints: units / stars | 7391/7394, 1512/1540 (held-out 187/187, 64/64) = `PF ACCEPT` |
| (b) tiles vs the next save | owner 103487/103500, terrain 103397/103500, structure 103470/103500, structure level 11065/11113, road 103500/103500, flood 103461/103500, city owner 3233/3233, city level 3217/3233, city pop 3126/3233 |
| (c) determinism (two clones, same move) | **13510/13510** |
| (d) clone independence | **13510/13510** |
| undo exact | 11410/13510; **exact up to tile reveals 13510/13510** |
| (e) speed, af181c8f t14, 16 tribes, 115 units, 272 moves | movegen ~1150/s (~310k moves listed/s), play_move+undo ~5900/s, simulate_move+undo ~18700/s, clone ~16000/s, random playout ~210 player-turns/s = ~13 rounds/s |
| (f) random events | 4 rolled; 1 sampled from distributions.json (ruin reward type, TVD 0.006 land / 0.003 water, every reward executes 5/5, 4/4); not covered: free tech pick, explorer path, Sanctuary spawn tile |
| (g) rules | 13521 moves in 24 kinds, all mapped to ledger ids; below-L1 touched: none (no switch on); kinds with unlabelled upstream logic touched: Step 5739, Summon 1428, Upgrade 185; 2 README v123 bullets without a ledger id |

(The default run checks every 25th legal action: 489/489 on each of (b), (c), (d).)

## Gaps that block search, ranked

1. **Speed (move generation).** Search time is ~90% `generate_legal_moves` (callgrind on the bench).
   Hot spots: `settings::units::get_unit_setting` builds a whole `UnitSetting` with a fresh `HashSet` of
   skills on every call (17% of all instructions; `has_skill` calls it), `technology::resolve_tech_for_tribe`
   walks every tech and rebuilds its settings per call (14%), `is_steppable`/`is_terminal` (15%).
   A static table for unit and tech settings (built once, `OnceLock`) should roughly halve move generation,
   with no rule change. **Request to pf-legal-3 / whoever owns `settings/`** (not done here: those files are
   being edited by the rule sessions). Target for MCTS: 10k+ movegens/s on this state.
2. **Fog memory in `play_move`.** `memory::observe_all` is ~100 µs of the ~160 µs `play_move`
   (O(tribes x units) with SipHash lookups on `explorers`). Search should use `Game::simulate_move`
   (3x faster, no reveals) or skip memory; but `simulate_move`'s EndTurn skips back to the mover unless
   `adversarial_search()` is on. Needed: an API call "apply for search" = no reveals, no fog memory, real
   EndTurn to the next player. Small, in `game.rs`; ask before adding (it touches the turn flow).
3. **Hidden information.** `load_save_file` loads the full map (the save holds it). Search on a real
   game must not see through fog: `Game::clone_for_mcts(pov)` (obscure_fog) exists but is untested against
   saves. Phase 4 (fog inference) item; needs a belief-state loader before search plays live games.
4. **Win % needs an opponent model and an evaluation.** Playouts now use a random policy (end turn with
   chance 1/8). At ~13 rounds/s on a 16-tribe map, a 30-round playout costs ~2 s: too slow for MCTS without
   gap 1 and a cut-off evaluation. `data/bot_rules.json` (attack decision/target, research opener) is the
   start of a bot policy (Phase 6).
5. **Unlabelled upstream rules.** Movement (move points, terrain cost, zone of control), training limits and
   Upgrade come from Polyfish v115 with no ledger entry (`UPSTREAM` in `data/pf_rule_levels.json`).
   They pass the legality test (99.4%) but have no level. Proposal: ledger entries MOVE-BASE, TRAIN-BASE,
   UPGRADE-BASE at L2 (Polyfish + 13k replayed actions). Also two sim/README v123 bullets carry no ledger id
   (city building income counts only the city's tiles; harvests accept the tribe's tech version).
6. **Undo keeps tiles explored.** Exact otherwise (13510/13510). Fine for search (clone at the root, or
   `simulate_move`), but a tree that undoes `play_move` will slowly reveal the map to the mover.
7. **Tile misses at checkpoints (for pf-port, not search-blocking):** city population 107 misses and city
   level 16 (population sources Polyfish doesn't model, e.g. Aqua Farm/Atoll); terrain 103 (028182a9 t4-10
   around (26-28,13-15): ice/flooding?), structure levels 48 (Lighthouse 47, Forge 22, Windmill 6, Village 1:
   Polyfish doesn't keep these levels up to date), flood/algae 39, tile owner 13 (af181c8f (23-24,12)).
   `python3 -I tools/pf_accept.py --fails` lists examples.
8. **Random events not sampled from data:** ruin free-tech pick, explorer path, Sanctuary spawn tile keep
   Polyfish's seeded hash (no measured distribution exists). Low impact.

## Requests to other sessions

- pf-legal-3 / settings owner: gap 1 (cache unit and tech settings). The suite's (e) line measures it.
- Orchestrator: gap 2 needs a decision on adding a search-mode apply to `game.rs`.
- Ledger: gap 5 entries (MOVE-BASE, TRAIN-BASE, UPGRADE-BASE), then add them to KINDS in `tools/pf_rule_levels.py`.

## Notes

- Fingerprint = hash of the whole serialized `GameState` minus `_messages` (IndexMaps keep order, so clones
  serialize identically). It includes `_history`, so equal fingerprints also mean the same move history.
- (b) is checked inside the replay itself: two clones play the logged move through the API before the replay
  plays it; the replay's state must then equal the clone's. Ruins use the save's reward (hint), as the replay.
- Checkpoint tile check loads the next save with the same loader and compares part by part; a save's level 0
  and Polyfish's level 1 for a fresh building count as equal.
