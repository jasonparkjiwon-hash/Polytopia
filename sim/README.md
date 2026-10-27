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

## Forward-model API (fm-accept; `src/api.rs`, `src/bin/pfapi.rs`, `tools/pf_api.py`)

For search and scenarios. It adds no rules: every call goes through Polyfish's own move generation and `play_move`.

- Rust (`polyfish::api`):
  - `load_save_file(path, "current", player)`: a decoded save (`saves/<id>_t<n>.json`) -> `Game`, `player` to move.
  - `legal(&game)`: every legal move as `{key, label, mv}`; label like `Step Warrior (3,4)->(4,5)`, `Build Farm (3,4)`, `Research Fishing`, `EndTurn`.
  - `find(&game, &key)`, `apply(&mut game, mv)` (returns the undo), `undo(&mut game, u)` (newest first), `end_turn(&mut game)`.
  - `clone(&game)`: direct struct copy (~16k/s on a 16-tribe mid-game state). `Game::clone_game` goes through JSON and is slower.
  - `fingerprint(&state)`: hash of everything Polyfish holds; equal fingerprints = same game. `fingerprint_with(.., true)` ignores tile reveals.
  - `kind(mv)`: the move's rule family, the key into `data/pf_rule_levels.json`.
  - `Dice::from_file("data/distributions.json", seed)` + `apply_with_dice(&mut game, mv, Some(&mut dice))`: an Examine Ruins gets its reward sampled from the measured table (land or water, Free Tech dropped when nothing is researchable) instead of Polyfish's seeded hash. `RANDOM_EVENTS` lists every random event and what covers it.
  - Undo is exact except tile reveals: `play_move` explores for good, its undo keeps the tiles explored. Clone when that matters.
- Bin: `target/release/pfapi moves <save> <player>` (one JSON line per legal move), `pfapi serve` (JSON lines on stdin: `load`, `moves`, `play {key}`, `end`, `undo`, `push`, `pop`, `state`, `dice`), `pfapi bench <save> <player|0> [secs]`, `pfapi dice <distributions.json> <save> <player>`.
- Python: `tools/pf_api.py` (`Sim(save, player)`, `.moves() .play(key) .undo() .end_turn() .push() .pop() .dice() .state()`).
- Acceptance: `python3 -I tools/pf_accept.py [--full] [--fails]` prints the `FM ACCEPT` lines (end of `scripts/check.sh`, informational). The per-action checks run inside `pfreplay` when `PF_ACCEPT=n` is set (every n-th legal logged action). Rust tests: `src/api_tests.rs`.
- Rule labels: `python3 -I tools/pf_rule_levels.py [--check]` writes `data/pf_rule_levels.json` (move kinds, the v123 bullets below and the `v123_flags` switches -> ledger id and level).

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
- Push rule from engine/replay.py push_target: ranged attack target, else saved/kept facing (`UnitState.direction` = save byte + 1, `ever_moved`), else away from the last move's start or toward the last attacker (`push_from`); reversed for other players' units; centre by angle; counter-clockwise first; own port as first choice or fallback (27 Oct); boats only onto water; no open tile removes (`functions.rs` calculate_pushable_position, `actions/units.rs`, `bin/pfreplay.rs` primes ever_moved) [PUSH-DIRECTION, SAVE-UNIT-FACING, PUSH-NEVER-MOVED, PUSH-TIEBREAK, PUSH-PORT-FIRST, PUSH-ONTO-PORT].
- Freeze area (Mooni/Gaami moves, action 17) doesn't freeze a tile under a unit, and records the frozen terrain (`TileState.frozen_from`) [MOONI-FREEZE].
- Break Ice turns all ice around the acting unit back to its water/ocean, except under a unit (`moves/abilities/break_ice.rs`) [ACTION-18-BREAK-ICE].
- On a village/city capture a Mooni/Gaami freezes the area, and any Polaris capture turns its own water around the city to ice (`moves/capture.rs`) [MOONI-FREEZE, POLARIS-CAPTURE-FREEZE].
- Idle units heal at the end of the turn only for the human (`TribeState.bot` false), and not when poisoned [IDLE-AUTO-RECOVER].
- Explode hits each adjacent enemy (hidden too, not at peace) for half the exploder's direct damage, rounded then halved and floored, and poisons survivors (was a flat 2) (`moves/abilities/explode.rs`) [EXPLODE-DAMAGE, EXPLODE-POISON, EXPLODE-POISON-DEFENCE].
- Bot bonus: DifficultyHandicap - 1 stars a turn while holding the own unbesieged capital (`TribeState.handicap`, filled by save_loader; `functions.rs` get_bot_bonus, `game.rs`) [ECON-BOT-BONUS].
- Navigation requires Sailing as in the verified tree (upstream: Ramming) [TECH-TREE].
- Aquarion techs 45 AquaBase (start), 47 AquaFishing (tier 1), 39 Aquaculture and 46 Marine Life (tier 2, need 47; Marine Life unlocks the Shark); another tribe's own tech is never researchable; prerequisites accept the tribe's version. Each fills a base tech's slot: 47 Fishing (opens water), 39 Ramming (then Aquatism), 46 Sailing (then Navigation; opens ocean) [AQUARION-TECH-TIERS, UNIT-ID-53, AQUARION-TECH-SLOTS]. Below-L1 switches live in `src/v123_flags.rs` (`PF_FLAGS` in pfreplay).
- Amphibious units step onto shallow water and flooded land without a tech (`moves/mod.rs`) [AMPHIBIOUS-WATER, new ledger entry].
- Tribe techs take the tier and prerequisite of the base tech they replace (most had tier 1 and could not be researched); the researchable list has no duplicates (`settings/technology.rs`) [TRIBE-TECH-TIERS].
- Philosophy discount is ceil(cost x 2/3) (`settings/technology.rs`) [TECH-COST].
- Starfish can be gathered with Navigation or the tribe's version of it (Polar Warfare) (`moves/mod.rs`, `moves/capture.rs`) [ECON-PRICES-V123].
- Enchant Animal costs 3 (`version_sync.rs`) [ECON-PRICES-V123].
- The Polaris Outpost is buildable for 5 stars (`settings/structures.rs`); Polaris cities connect through roads, cities, ports, Outposts and ice within 2 of an Outpost, updated when an Outpost is built (`actions/connection.rs`, `actions/structure.rs`) [OUTPOST-NETWORK, new ledger entry; ice formed later doesn't trigger an update yet].
- Capturing a city claims the 3x3 around it (unowned or the old owner's tiles), not every same-owner tile within 2 (`actions/city.rs` capture_city) [CAPTURE-TERRITORY].
- A captured capital stays the old owner's capital (no +1, no bot bonus for the captor) (`actions/city.rs`) [ECON-INCOME, ECON-BOT-BONUS].
- Market earns the level of each adjacent Windmill/Sawmill/Forge (its adjacent Farms/Lumber Huts/Mines) (`functions.rs` get_city_production) [ECON-MARKET-CLATHRUS].
- A city's building income (Market, Clathrus, ...) counts only tiles that city rules; post_load's territories overlap (`functions.rs` get_city_production) [ECON-MARKET-CLATHRUS].
- Embassy: costs 4 plus 2 per embassy the tribe has at another host (a rebuild at the same host pays 4); while it stands the builder and the host each earn 2 a turn (4 at peace, 0 at war); the loader keeps RelationState 3 (war) and moves the save's EmbassyLevel from the host's record to the builder's (`functions.rs` get_embassy_income/get_embassy_cost, `game.rs`, `moves/abilities/diplomacy.rs`, `save_loader.rs` embassies_to_builder_side); an attack or city capture between the two tribes destroys it (`actions/units.rs` destroy_embassies_between, called by attack_unit and capture_city) [EMBASSY-ACTION, ECON-EMBASSY, EMBASSY-INCOME-NEUTRAL, EMBASSY-DESTROYED-BY-COMBAT].
- A Shaman's convert also deals its normal damage, with no retaliation; a target it kills isn't converted (`moves/abilities/convert.rs`) [SHAMAN].
- A move onto a hidden enemy reveals it and uses the move but not the attack (`moves/step.rs`) [MOVE-BLOCKED-HIDDEN].
- Breaking peace disbands the breaker's units inside the ex-ally's territory (`moves/abilities/diplomacy.rs`) [DIPLO-BREAK-DISBAND].
- A Workshop or Park adds +1 income once (Polyfish raised production and also counted the reward) (`moves/reward.rs`) [ECON-INCOME].
- Water-skill units, and amphibious units on shallow water (on ocean with Marine Life, as in move generation), follow a kill onto water (`functions.rs` is_steppable_for_push) [WATER-UNITS, AMPHIBIOUS-WATER].
- A Cymanti water ruin's unit is a veteran Boomchi (`actions/structure.rs`) [RUIN-UNIT-CYMANTI].
- Resource harvests accept the tribe's version of the tech, and Aquarion's 47 counts as Fishing (`settings/technology.rs` has_tech_for_tribe, `moves/mod.rs`, `functions.rs`) [AQUARION-TECH-SLOTS, CYMANTI-TECHS].
- Cymanti use the base Sailing, Ramming, Navigation and Diplomacy; Raychi unlock with Sailing, Boomchi with Ramming, Algae with Fishing, Moth with Diplomacy; Oceantology tier 3 (`settings/technology.rs`) [CYMANTI-TECHS, new ledger entry].
- Peace offers (need Strategy, a met tribe, no offer pending) and replies are generated again; breaking peace leaves RelationState 3 on the breaker's side (`moves/abilities/diplomacy.rs`) [DIPLO-PEACE].
- Turn income is paid before the start-of-turn effects, so a level from Fungi growth counts from the next turn (`game.rs` end_turn) [CITY-LEVEL-BY-REWARD].
- A Persist unit (Knight, Tridention) that kills moves in and may attack again; the kill move-in no longer ends its turn (`actions/units.rs` attack_unit) [PERSIST-KILL-MOVE, new ledger entry].
- A convert ends the converter's turn (it attacked), so it doesn't act again or idle-heal (`moves/abilities/convert.rs`) [CONVERT-ATTACK, IDLE-AUTO-RECOVER].
- An Aquarion Atoll links own cities and Atolls within 3 tiles into the capital network (as Mycelium at 4), updated when one is built (`actions/connection.rs`, `actions/structure.rs`) [ATOLL-NETWORK, new ledger entry].
- The loader reads a Fungi's save level 0/1 as Polyfish's 1/2, so a new Fungi grows once at its owner's next turn (+1 population) and an old one doesn't again (`save_loader.rs` structure_level) [FUNGI-GROWTH, new ledger entry].
- The Elyrion Sanctuary: 5 stars and +1 a turn per adjacent wild animal (v123 card, as upstream) by default; cost 3 and no income behind the off switch `sanctuary_no_income` (b2448ead, one game) until SANCTUARY-V123 settles the split (`settings/structures.rs`, `functions.rs`, `v123_flags.rs`) [SANCTUARY-V123, SANCTUARY-NO-INCOME, split]. A/B: stars 1320/1342 both ways.
- Enchant Animal removes the wild animal from its tile (v115 put the Game back, so it kept paying a Sanctuary) (`moves/abilities/enchant_animal.rs`) [ENCHANT-REMOVES-GAME].
- A Cloak or Scuba attacking a unit in an enemy city deals its normal damage (no retaliation), then infiltrates as into an empty city (Daggers) and is used up (`actions/units.rs` attack_unit) [INFILTRATE].
- Aquarion Jelly Tentacles: after a Jelly moves it hits every adjacent enemy, and an enemy that moves (or follows a kill) next to a Jelly is hit by it; normal damage, defender bonus, no retaliation (`actions/units.rs` tentacles_after_step, called from `moves/step.rs` and the kill move-in) [TENTACLES].
- Clathrus earns +1 per adjacent Fungi (v123 card; upstream counted Algae) (`functions.rs` get_city_production) [ECON-MARKET-CLATHRUS].

## Legal-move generation (pf-legal; tests in `src/v123_legal_tests.rs`)

- A peace offer to a tribe without a capital is named by its first city (v123 logs one of its cities) (`moves/abilities/diplomacy.rs` peace_offer_target); the loader reads pending offers from DiplomacyMessages `[1, sender]` (`save_loader.rs`) [DIPLO-PEACE].
- Cymanti algae doesn't stop Cymanti units or boats, which move on through it (`moves/mod.rs` is_terminal) [ALGAE-MOVE, new ledger entry].
- Skate units get +1 movement wherever the move starts, not only on ice (`functions.rs` get_unit_movement) [SKATE-MOVE, new ledger entry].
- Another tribe's port stops only a unit that would board; frozen ports, ports on flooded land and amphibious units step onto it (`moves/mod.rs` is_steppable) [PORT-STEP, new ledger entry].
- Water-only units (Raychi, Shark) move from water into a village or city and stop there (`moves/mod.rs`) [WATER-UNITS-VILLAGE, new ledger entry].
- Explode is offered with no enemy next to the exploder (`moves/abilities/unit_actions.rs`) [EXPLODE-ANYTIME, new ledger entry].
- The Atoll can be built on algae-covered water (`moves/build.rs`) [ATOLL-ON-ALGAE, new ledger entry].
- The Moth has Explode (`settings/units.rs`) [MOTH-V123].
- A converter's (Mind Bender, Shaman) attack is generated as ConvertMove; a boat carrying one attacks normally (`moves/mod.rs` generate_attack_moves) [CONVERT-ATTACK, new ledger entry].
- Research moves come from the v123 researchable list (tribe techs included) plus each known tech's prerequisite (`moves/research.rs`) [TRIBE-TECH-TIERS, RESEARCH-BACKWARD, new ledger entry].
- Metal is visible with Mining as well as Climbing (`functions.rs` is_resource_visible_to_tribe) [METAL-WITH-MINING, new ledger entry].
- Amphibious units step onto ocean with Marine Life (46); with no tech behind the switch `amphibious_ocean_innate` (`moves/mod.rs` is_navigationable_terrain, `v123_flags.rs`) [AMPHIBIOUS-WATER].
- New structures Aqua Farm (49, on AquaCrop, +2 population) and Atoll (51, on water, ocean or flooded land; no population effect yet), unlocked by Aquaculture; AquaCrop visible with Aquaculture (`types.rs`, `settings/structures.rs`, `settings/resources.rs`, `settings/technology.rs`, `moves/build.rs`, `functions.rs`) [AQUARION-STRUCTURES, new ledger entry].
- A Port can be built on flooded land (`moves/build.rs`) [PORT-FLOODED, new ledger entry].
- New unit Mermaid Archer (47), Aquarion's Archer, unlocked by Archery (`types.rs`, `settings/units.rs`, `settings/technology.rs`) [AQUARION-UNIT-47].
- Monuments can be built on ice, and on ocean by Aquarion (`moves/build.rs`) [MONUMENT-TERRAIN, new ledger entry].
- Swift (Swarm's effect, save effect 6) gives +1 movement like Boosted (`functions.rs` get_unit_movement) [SWIFT-MOVE, new ledger entry].
- New Aquarion units Mermaid Defender (49, Strategy), Scuba (50, Diplomacy), Mermaid Dagger (51, from a Scuba's infiltration) and Jelly (52, no unlocking tech known yet) with the v123 card stats (`types.rs`, `settings/units.rs`, `settings/technology.rs`, `actions/units.rs`) [AQUARION-UNITS-49-52, new ledger entry].
- Cymanti train the Living Island (57) with Navigation, which their save stores in place of Oceanology (`settings/technology.rs`) [CYMANTI-OCEANOLOGY-ID].
- An Aquarion Lost City (ocean ruin) starts at level 3 with both level-up rewards to choose and production 1, and its finder is rehomed there; the harness reads it from the next save (`actions/structure.rs`, `tools/pf_jobs.py`) [AQUARION-LOST-CITY, new ledger entry].
- Aquarion research the base Free Spirit; Free Diving (25) no longer replaces it (`settings/technology.rs`) [AQUARION-FREE-SPIRIT, new ledger entry].
- Land units walk onto flooded land without a water tech (`moves/mod.rs` is_navigationable_terrain) [FLOOD-ALGAE].
- Water units (Shark) sail on through an own port; only land units stop there (`moves/mod.rs`) [WATER-UNIT-PORT-PASS, new ledger entry].
- A Mooni capture freezes the water around it but not the adjacent enemy units (`actions/mod.rs` freeze_area_with, `moves/capture.rs`) [MOONI-CAPTURE-NO-UNIT-FREEZE, new ledger entry].
- A city's unit limit counts only its owner's units (`functions.rs` get_city_unit_count) [CITY-UNITS-OWN-ONLY, new ledger entry].
- Exploding on water leaves Spores with the algae, not Fruit (`moves/abilities/explode.rs`) [EXPLODE-WATER-SPORES, new ledger entry].
- The Clathrus (41) is built on land (Field, Forest) next to an own Fungi, not on water next to Algae (`settings/structures.rs`, `moves/build.rs`) [CLATHRUS-ON-LAND, new ledger entry].
- The Aqua Farm (49) also goes on empty water or ocean (`settings/structures.rs`, `moves/build.rs`) [AQUARION-AQUA-FARM-WATER, new ledger entry].
- The harness hints a ruin's +3 population (to the capital) when the next save's capital grew 3+ more than builds explain; such ruins used to fall to Explorer (`tools/pf_jobs.py`) [RUIN-POP-HINT, new ledger entry].
- A captured city that was connected to its old owner's capital loses 1 population and its link; the captor's capital keeps its population (`actions/city.rs` capture_city) [CAPTURE-DISCONNECT, new ledger entry].
- Ports link over water in up to 5 steps (diagonals count, not through enemy tiles) to own ports and to own cities with a port beside them, instead of a 4-tile box between ports (`actions/connection.rs` water_route_targets) [WATER-ROUTE, new ledger entry].
