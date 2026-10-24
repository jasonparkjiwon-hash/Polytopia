# sim/: the Polyfish engine, built offline

- `pfcore/` contains the Polyfish engine modules copied from HenBOMB/Polyfish `polyfish-rs/src` (Apache-2.0, commit of 2026-09-02).
  - Left out: `ai/`, `bin/`, `main.rs`, `training_api.rs`, `recorder.rs` and `replay/`.
  - Changed from upstream (Apache-2.0 section 4b: modified files carry these changes):
    - the Sanctuary spawn in `actions/mod.rs` uses DotNetRandom instead of StdRng;
    - v123 rule corrections, listed below.
- `vendor/` holds 25 dependency crates, copied from their GitHub release tags (`vendor_list.txt`).
  - Offline only: a `.cargo/config.toml` made `vendor/` stand in for crates.io (not in the repo; online `cargo build` fetches crates normally).
  - The `serde_derive` manifest is de-workspaced (inherited dependency versions written in).
- Build: `cd pfcore && cargo build --release --offline`.
- Generate maps: `target/release/genmaps <out> <n> <map_type 1-6> <size 0-5> <seed0> <tribe ids> [players]`.
  - Then analyse them with `../verify/analyze_map.py`.

## v123 corrections (pf-port; ledger ids in brackets, tests in `src/v123_tests.rs`)

- Poison halves only the defence bonus; the v115 extra -30% on defence is removed (`functions.rs`) [C7].
- A Frozen defender doesn't retaliate (`actions/units.rs` attack_unit) [FROZEN-NO-RETALIATION].
- A hidden attacker (Hide skill: Cloak) takes no retaliation [CLOAK-DAGGER-RETALIATION].
- No retaliation when the defender's tribe can't see the attacker's tile (explored, or current vision) (`functions.rs` tribe_sees_tile) [C20].
- City defence bonus (1.5, walls 4) only in the unit's own city, not an ally's [DEF-BONUS].
- Splash damage is half the direct damage, floored [SPLASH].
- Unit stats from the v123 cards: Cloak attack 2 and Stiff; Moth defence 2 and Surprise (`settings/units.rs`) [UNIT-STATS-UI, MOTH-V123].
- Mooni and Shaman lose Static [C29b].
- Aquarion unit types 46 Mermaid, 48 Swordsmaid, 53 Shark with v123 card stats; Mermaid/Swordsmaid replace Aquarion's Warrior/Swordsman (`types.rs`, `settings/units.rs`, `settings/technology.rs`) [AQUARION-UNIT, UNIT-ID-48, UNIT-ID-53].
- A Giant boarding becomes a Juggernaut carrying the Giant, and lands as a Giant [GIANT-JUGGERNAUT].
- Only the unit's own port boards it; a frozen-over port is walked on foot [PORT-BOARDS].
