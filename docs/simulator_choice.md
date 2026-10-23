# Simulator base: comparison and decision (Phase 1, gate F)

Written 23 Oct 2026.

## Decision

**Use Polyfish as the simulator base**, patched with our v123 corrections. Keep our Python replay engine as the referee: every change to the simulator must still reproduce the real saves.

## Comparison

| | **Polyfish** (`sim/pfcore`) | **PolyEnv** | **Our Python engine** (`engine/`) |
|---|---|---|---|
| What it is | Full game re-implementation for an AlphaZero-style AI | Fan re-implementation, written against the wiki | Replay checker: re-applies a save's logged moves and compares with the next save |
| Language, licence | Rust, Apache-2.0 | C++, MIT | Python (stdlib), ours |
| Game version | v115 (Cymanti rework); last updated Sep 2026 | Not stated; source dated Jan–Feb 2026 | v123, measured from your saves |
| Can play a game itself | Yes: legal moves, play and undo, game copy for search, map generator, fog | Yes | No: no legal-move generator and no turn loop |
| Rule coverage | All base units and actions; fog; diplomacy; most special tribes. Lacks the v120+ units (Aquarion rework, Solaris/steam) | Base game; some stale prices (Burn Forest 5, Shaman 10) and stubs | Combat, movement, boats, ice, poison, splash, economy. Matches about 95% of units and 95% of player-turns in real v123 saves |
| Agreement with our dataset | 290 fields agree, 36 differ, all 36 explained (`verify/crosscheck_polyfish.md`) | Many dataset numbers came from it; independent only where the wiki disagrees | Is the dataset |
| Speed (this container) | 4,100–6,500 random legal moves/s, including move generation; game copy 2–7 ms | Not built here | About 90,000 logged moves/s replayed (no legality checks); state copy 16 ms |
| Builds here | Yes, `cargo build --release` in about 30 s | Not fetched | Yes |

Speed figures come from `sim/pfcore/src/bin/bench.rs`, which plays random legal moves on a generated Continents map (4 tribes on Normal, 16 on Massive).

## Why Polyfish

- **It is the only one that is a complete, fast forward model.** Search (Phase 5) needs legal moves, cheap copies and undo. Polyfish already has all three, plus a game copy designed for tree search.
- **It is the freshest independent source.** Its differences from our data are known and few, and the real saves settle each one.
- **Its licence is compatible.** Apache-2.0 allows modification; we keep its notice.
- **PolyEnv adds nothing Polyfish doesn't cover,** and its numbers are older.
- **Our engine is better used as the test oracle.** It is the only code checked against real v123 saves.

## What has to happen before Phase 3

1. **Load real saves into Polyfish.** Convert our save JSON into Polyfish's GameState and run its move code on a save's action log.
2. **Run the same comparison as our replay.** Do units, HP and stars match the next save? This becomes the acceptance test for the forward model.
3. **Port the v123 corrections.** These come from the ledger (every rule at L1 or above):
   - Swordsmaid (48) and the other Aquarion units.
   - Ocean ice.
   - Giants become Juggernauts at sea.
   - Own-port boarding.
   - Boats stay boats on algae.
   - Siege income.
   - Bot bonus.
   - Meeting stars.
   - Starfish +8.
   - Embassy 5.
   - C29 values.
4. **Leave the unknowns out until measured:** action 18, Swarm vs Boost (38), ruin weights, ice melting.
