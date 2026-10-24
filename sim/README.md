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
- Aquarion techs 45 AquaBase (start), 47 AquaFishing (tier 1), 39 Aquaculture and 46 Marine Life (tier 2, need 47; Marine Life unlocks the Shark); another tribe's own tech is never researchable; prerequisites accept the tribe's version. Which base tech each replaces is behind the off switch `aquarion_tech_slots` (new `src/v123_flags.rs`, `PF_FLAGS` in pfreplay) [AQUARION-TECH-TIERS, UNIT-ID-53].
- Amphibious units step onto shallow water and flooded land without a tech (`moves/mod.rs`) [AMPHIBIOUS-WATER, new ledger entry].
- Tribe techs take the tier and prerequisite of the base tech they replace (most had tier 1 and could not be researched); the researchable list has no duplicates (`settings/technology.rs`) [TRIBE-TECH-TIERS].
- Philosophy discount is ceil(cost x 2/3) (`settings/technology.rs`) [TECH-COST].
- Starfish can be gathered with Navigation or the tribe's version of it (Polar Warfare) (`moves/mod.rs`, `moves/capture.rs`) [ECON-PRICES-V123].
- Enchant Animal costs 3 (`version_sync.rs`) [ECON-PRICES-V123].
- Enchant Animal costs 3 (`version_sync.rs`) [ECON-PRICES-V123].
- The Polaris Outpost is buildable for 5 stars; its effect (ice network) is not modelled yet (`settings/structures.rs`).
- Capturing a city claims the 3x3 around it (unowned or the old owner's tiles), not every same-owner tile within 2 (`actions/city.rs` capture_city) [CAPTURE-TERRITORY].
- A captured capital stays the old owner's capital (no +1, no bot bonus for the captor) (`actions/city.rs`) [ECON-INCOME, ECON-BOT-BONUS].
- Market earns the level of each adjacent Windmill/Sawmill/Forge (its adjacent Farms/Lumber Huts/Mines) (`functions.rs` get_city_production) [ECON-MARKET-CLATHRUS].
- A city's building income (Market, Clathrus, ...) counts only tiles that city rules; post_load's territories overlap (`functions.rs` get_city_production).
- Embassy: costs 4 plus 2 per embassy the tribe has; the host earns 2 a turn (4 at peace, 0 at war), the builder 4 only at peace; the loader keeps RelationState 3 (war) (`functions.rs` get_embassy_income/get_embassy_cost, `game.rs`, `moves/abilities/diplomacy.rs`, `save_loader.rs`) [EMBASSY-ACTION, ECON-EMBASSY].
- A Shaman's convert also deals its normal damage, with no retaliation; a target it kills isn't converted (`moves/abilities/convert.rs`) [SHAMAN].
- A move onto a hidden enemy reveals it and uses the move but not the attack (`moves/step.rs`) [MOVE-BLOCKED-HIDDEN].
- Breaking peace disbands the breaker's units inside the ex-ally's territory (`moves/abilities/diplomacy.rs`) [DIPLO-BREAK-DISBAND].
- A Workshop or Park adds +1 income once (Polyfish raised production and also counted the reward) (`moves/reward.rs`) [ECON-INCOME].
- Water-skill units (and amphibious units on shallow water) follow a kill onto water (`functions.rs` is_steppable_for_push) [WATER-UNITS].
- A Cymanti water ruin's unit is a veteran Boomchi (`actions/structure.rs`) [RUIN-UNIT-CYMANTI].
- Resource harvests accept the tribe's version of the tech, and Aquarion's 47 counts as Fishing (`settings/technology.rs` has_tech_for_tribe, `moves/mod.rs`, `functions.rs`).
- Cymanti use the base Sailing, Ramming, Navigation and Diplomacy; Raychi unlock with Sailing, Boomchi with Ramming, Algae with Fishing, Moth with Diplomacy; Oceantology tier 3 (`settings/technology.rs`) [CYMANTI-TECHS, new ledger entry].
- Peace offers (need Strategy, a met tribe, no offer pending) and replies are generated again; breaking peace leaves RelationState 3 on the breaker's side (`moves/abilities/diplomacy.rs`) [DIPLO-PEACE].
- Clathrus income source behind the off switch `clathrus_fungi` (Fungi per the v123 card; default Algae as upstream) [ECON-MARKET-CLATHRUS, split].

## Legal-move generation (pf-legal; tests in `src/v123_legal_tests.rs`)

- A peace offer to a tribe without a capital is named by its first city (v123 logs one of its cities) (`moves/abilities/diplomacy.rs` peace_offer_target); the loader reads pending offers from DiplomacyMessages `[1, sender]` (`save_loader.rs`) [DIPLO-PEACE].
