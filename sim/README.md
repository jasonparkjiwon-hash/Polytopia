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
- A Giant boarding at its own port stomps with Juggernaut attack [STOMP-ON-BOARDING].
- A boat on Aquarion-flooded land (not a city) stays a boat [FLOOD-ALGAE].
- A Stiff unit doesn't move in after a kill; a Stiff boat (Juggernaut) does, and lands [KILL-MOVE-IN, JUGGERNAUT-KILL-MOVE].
- A water unit may enter a city (it follows a kill into one) (`functions.rs` is_steppable_for_push) [WATER-UNITS].
- Push rule from engine/replay.py push_target: ranged attack target, else saved/kept facing (`UnitState.direction` = save byte + 1, `ever_moved`), else away from the last move's start or toward the last attacker (`push_from`); reversed for other players' units; centre by angle; counter-clockwise first; own port only as first choice; boats only onto water; no open tile removes (`functions.rs` calculate_pushable_position, `actions/units.rs`, `bin/pfreplay.rs` primes ever_moved) [PUSH-DIRECTION, SAVE-UNIT-FACING, PUSH-NEVER-MOVED, PUSH-TIEBREAK, PUSH-PORT-FIRST, PUSH-ONTO-PORT].
- Freeze area (Mooni/Gaami moves, action 17) doesn't freeze a tile under a unit, and records the frozen terrain (`TileState.frozen_from`) [MOONI-FREEZE].
- Break Ice turns all ice around the acting unit back to its water/ocean, except under a unit (`moves/abilities/break_ice.rs`) [ACTION-18-BREAK-ICE].
- On a village/city capture a Mooni/Gaami freezes the area, and any Polaris capture turns its own water around the city to ice (`moves/capture.rs`) [MOONI-FREEZE, POLARIS-CAPTURE-FREEZE].
- Idle units heal at the end of the turn only for the human (`TribeState.bot` false), and not when poisoned [IDLE-AUTO-RECOVER].
- Explode hits each adjacent enemy (hidden too, not at peace) for half the exploder's direct damage, rounded then halved and floored, and poisons survivors (was a flat 2) (`moves/abilities/explode.rs`) [EXPLODE-DAMAGE, EXPLODE-POISON, EXPLODE-POISON-DEFENCE].
- Bot bonus: DifficultyHandicap - 1 stars a turn while holding the own unbesieged capital (`TribeState.handicap`, filled by save_loader; `functions.rs` get_bot_bonus, `game.rs`) [ECON-BOT-BONUS].
- Navigation requires Sailing as in the verified tree (upstream: Ramming) [TECH-TREE].
