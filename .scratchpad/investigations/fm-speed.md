# fm-speed(-2): make the forward model fast for search

State: gap 1 (speed) and gap 2 (search-mode apply) done and pushed; gap 5 (ledger) and the final numbers: see bottom.

## What changed (no rule change)

Check: `pf_accept.py --full` (13549 per-action checks) and `pf_miss.py` give identical output before and after
(only the speed line differs).

- `settings::units::get_unit_setting` / `settings::technology::get_technology_setting` return `&'static` from a table
  built once (OnceLock). `resolve_tech_for_tribe` is a table lookup. Skills are a `SkillSet` bitmask (was HashSet).
- `functions::UnitIndexGuard`: `generate_legal_moves` builds a tile -> first-unit table once; `get_unit_at` /
  `get_true_unit_at` use it while the guard lives (matched by the address of the borrowed state, so a cloned state
  falls back to the scan). Same answer as the scan (first unit in tribe order).
- `states::IndexMap` is now an alias with a fast integer hasher (iteration order is insertion order, so
  serialization and fingerprints are unchanged). `TileState.explorers` uses the same hasher.
- `get_adjacent_indices` pre-sizes its Vec; `is_adjacent_to_enemy` allocates nothing.
- Tried and dropped: fast hasher on unit/tile effect sets (no gain).

Callgrind on the bench state (100 movegens): 417M instructions -> 97M (4.3x).

## Search-mode apply

`Game::search_move` / `api::apply_search`: the simulate_move path (no reveals, no fog memory, no `_history`) but
EndTurn always goes to the next player. Undo is exact (fingerprint equal, reveals included, since nothing is revealed).
Tests in `api_tests.rs`: next player moves; undo exact and no explorer changes; 400-move game played with
`apply` and `apply_search` side by side gives identical states (minus explorers, history, fog memory) on every move
that reveals no tile. Moves that reveal tiles differ by design: score +5 a tile, Lighthouse +1 population.

Note for search: in search mode the Explorer reward / ruin explorer credits score without revealing, so a Lighthouse
population bonus is not seen. Small, and it is hidden information anyway.

## Bench

`pfapi bench <save> 0 [secs]` (existing), `PF_MOVEGEN_ONLY=n` for callgrind, and new
`pfapi playout <save|gen4> <player|0> [secs] [play]` (random policy, end turn with chance 1/8; `play` = play_move).
Wall-clock on this cloud box is noisy (+-30%); compare instruction counts.

## Gap 5 (done)

Ledger MOVE-BASE, TRAIN-BASE, UPGRADE-BASE (L2) added with `tools/ledger.py`; `KINDS` in `tools/pf_rule_levels.py` now
maps Step/Summon/Upgrade to them. (g) reports "kinds with unlabelled upstream logic touched:" (none). Decompose,
Destroy, Disband and Drain still say UPSTREAM; the saves never play them.

## Numbers (af181c8f t14, 16 tribes, 115 units; box is noisy, +-30%)

| | before | after |
|---|---|---|
| movegen/s | ~1100 (992 in the full run) | ~9100 (7300-9200 in single runs) |
| apply+undo/s (play_move) | 4700-5800 | ~14000-16000 |
| random playout, play_move | 11 rounds/s (177 player-turns/s) | 41-51 rounds/s |
| random playout, search_move | n/a | 50 rounds/s (796 player-turns/s) |
| 4-tribe generated state, search_move | n/a | 940 rounds/s (3760 player-turns/s) |
| 4-tribe generated state, play_move | n/a | 782 rounds/s |

Callgrind: 417M -> 97M instructions per 100 movegens (4.3x). 10k/s not quite reached on this box; what is left in
the profile: `generate_legal_moves` itself 18%, `is_steppable` 13%, `is_terminal` 10%, `get_enemy_at` 8%.
Next ideas: cache `is_adjacent_to_enemy` per tile per movegen (an enemy-zone bitmap built with the unit index), and
skip `Box<dyn Move>` allocation (a move enum). Fog memory is ~70% of play_move, which is why `search_move` matters.
