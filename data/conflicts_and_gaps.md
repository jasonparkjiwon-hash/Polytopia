# Conflicts and gaps (v0.3, wiki recheck 2026-10-22)

Where sources disagree, both claims are kept. "Lean" is my best current belief, not a decision.
Impact tags: **MAP** = map prior / hidden-tile model, **FOG** = vision/inference, **SIM** = forward model, **BOT** = opponent modelling.
Sources: PE = PolyEnv engine (Jan-Feb 2026), WK = fandom wiki (undated, mixed eras), NM = NamuWiki (dated), BP25 = 2025 balance pass dev post (devtrackers.gg, dated 2025), DEV = staff comment ~2019.

## Biggest lesson: version drift (updated)

The fandom pages mix patch eras. NamuWiki and the 2025 balance-pass post are dated. **New this round: PE is not fully current either.** BP25 puts Burn Forest at 3 stars (PE: 5) and allows "backwards" research, which PE likely lacks. Rule now: dated patch source > PE > undated wiki, and anything only one source states stays a test.

## Status at a glance

- **Settled or strongly leaned (no test needed):** C1, C2, C4, C13, C16, C17, C22, plus C3 (low priority).
- **Wiki recheck moved the lean (still worth a quick in-game check):** C6, C7, C9, C10, C11, C12, C20, C24, C25, C26.
- **Still genuinely open:** C5, C8, C14, C15, C18, C19, C21, C23.

## Conflicts

| ID | Topic | Claims | Lean after 2026-10-22 | Settle by | Impact |
|---|---|---|---|---|---|
| C1 | Ai-Mo start | PE, NM, BP25: Philosophy + Mind Bender. Old fandom: Meditation. | **Settled**: Philosophy + Mind Bender, 730. | - | SIM |
| C2 | Luxidoor start | PE/NM: level-3 capital, 2 stars, 515. WK Luxidoor page: level 3 **with city wall**, 4 stars/turn. | **Settled** level 3 + 2 stars (BP25). Wall: WK says yes (medium). | Turn 0 as Luxidoor (wall only) | SIM |
| C3 | Polaris start score | PE 630, WK 530. | 530 (medium-high). | Turn 0 | SIM |
| C4 | Cymanti start | WK Cymanti page: Farming (Fungi) + Shaman. BP25: zero Cymanti changes. | **Settled**: Farming + Shaman, 630. | - | SIM |
| C5 | Kickoo start score | PE 515, fandom Score 615. | 515 lean (low-medium). | Turn 0 as Kickoo | SIM |
| C6 | Retaliation uses defence bonus? | WK Combat: bonus is applied to defenceForce, so it **raises** retaliation. PE excludes it. | **WK (medium-high)**: the Combat page states it explicitly. PE deviates. | Q5 in the doc | SIM |
| C7 | Poison | WK Combat: -30% defence, -50% healing, no defence bonus, drops spores/algae on death; cured by self-heal once, Mind Bender, Mycelium. PE: different bonus table, no healing cut. Polyfish (v115 notes): defence halved, bonuses intact. | **Defence halved (L3, e15f392c turn 11)**; Polyfish right, old wiki stale. Cure by Recover still untested. | Watch a poisoned unit Recover | SIM (Cymanti) |
| C8 | Water tech gates | WK Sailing: "Scout and movement on ocean". WK Fishing (post Patch-the-Ocean): Port, Fishing action, "movement on ocean tiles" (likely means shallow water). WK Navigation: Battleship, all naval units on ocean. WK Explorer: shallow needs Sailing, ocean needs Navigation (pre-ocean-update wording). Aquarion page: base Fishing = starfish sight; Navigation = starfish harvesting. | Fishing = shallow-water boats + port + starfish visible; Sailing = deep ocean; Navigation = Battleship, starfish harvest (medium). Explorer page and PE Explorer are stale. | Q7 | FOG, SIM |
| C9 | Villages after terrain | WK Map Generation: ~30% before terrain, then "attempt to assign 60%" after; Drylands 0% before, ~80% after; Waterworld ~10% before. PE fills every slot. | **WK (medium)**: target ~60% of max total. | Q4 | MAP |
| C10 | Capital guarantees | WK Map Generation: **every** capital gets ≥2 identical resources, force-spawned if missing. Starting-tech resource for Bardur, Imperius, Kickoo, Zebasi, Elyrion, Cymanti; Xin-xi 2 metal; Oumaji 2 fruit; Hoodrick 2 animals; others 2 of a random tier-1 resource (fish, animal or fruit). Kickoo gets 2 fish water tiles even on Drylands. PE implements only 4 tribes. | **WK (medium-high)**: most detailed and internally consistent. | Q1 counts | MAP, FOG |
| C11 | Bardur terrain | WK: 1.5× fruit, 0× crop. PE: 0.8× forest, 0× crop. | WK (medium). | Optional | MAP |
| C12 | All tribe terrain modifiers | WK now gives a full table (below). PE has fewer. | **WK table (medium)**. Order: mountain mod first, then forest, field = rest. | Optional | MAP |
| C13 | Water modifiers | Listed but not applied in code (WK says so). | Settled: ignore. | - | MAP |
| C14 | Ruin rewards | WK: Battleship, Explorer, Navalon, Population, Stars, Super Unit, Technology (no weights). Ocean ruin always gives an Aquarion "Lost City" when Aquarion is in game. PE: uniform pool. | Pool settled (Ruin page, 2026-10-23). Log so far (13 ruins): tech 7, veteran Swordsman 2, other 4. Weights still unknown. | More ruin logs | SIM, BOT |
| C15 | Explorer | WK Explorer: 15 moves, random walk, steers toward fog only when exactly 1 tile from it; no ruin Explorer if ruin is >2 tiles from fog. PE: 15 steps. | **15 settled**; random-walk rule new. | - | FOG |
| C16 | Ruin placement | WK: any terrain except shallow water, not next to city/village/ruin. | Settled: WK. | - | MAP |
| C17 | Starting stars | PE, NM, BP25 agree. | **Settled**. | - | SIM |
| C18 | Meeting reward | PE only formula. WK Stars page gives none. | Unverified. | Meet a tribe | SIM |
| C19 | Tile action costs | PE: clear forest 0 cost +1 star; road 3. WK (undated): clear forest +2 stars; road 2. | **Open**; read the buttons. | Q in doc | SIM |
| C20 | Retaliation vs fog | WK Combat: no retaliation if defender cannot see attacker, or attacker kills. | **WK (medium-high)**. | Optional | SIM, FOG |
| C21 | Initial reveal | Derived 5×5. | 5×5 (medium-high). | Q3 | FOG |
| C22 | Domains vs sectors | Same mapping. | Settled. | - | MAP |
| C23 | Resource table: shares or conditionals? | WK table columns sum to 100% and the page says "48% of their biome" (share wording). Since 2.0.58 terrain "always follows these percentages or as close as possible". Fish 50% of shallow tiles. | Leans **shares** (wiki reading, ~5 resources in a capital ring before guarantees). Still the top test. | Q1 | **MAP (highest)** |
| C24 | Bot income | DEV: "how many stars the AI get from their capital". WK Game Modes: starting income Easy 1, Normal 2 (same as humans), Hard 3, Crazy 5. | **NEW, medium-high**: these are TOTAL capital income, not a bonus on top. Easy bots earn less than you. Older dataset read it as a bonus. | Watch a bot's score/stars if visible | BOT |
| C25 | Backwards research | BP25: techs can be researched backwards (Vengir Smithery → Mining without Climbing). PE: prerequisite only. | **NEW, medium-high**. Matters for Vengir and Ai-Mo. | Turn 0 tech screen as Vengir or Ai-Mo | SIM |
| C26 | Other 2025 changes | BP25: Burn Forest 3 stars (PE 5), Forges allowed on forests, Temples +100 points per level (was 50), Polytaur 3 stars, embassies cheaper and scale with count, Polaris unit tweaks. | **NEW, medium-high** (dated). PE stale on these. | - | SIM |

### Tribe terrain modifiers (WK Map Generation, undated, post-2.0.58 likely)

Xin-xi 1.5× mountain, 1.5× metal · Imperius 0.5× animal, 2× fruit · Bardur 1.5× fruit, 0× crop · Oumaji 0.2× forest, 0.2× animal, 0.5× mountain · Kickoo 0.5× mountain, 1.5× fish · Hoodrick 0.5× mountain, 1.5× forest · Luxidoor base · Vengir 2× metal, 0.1× animal, 0.1× fruit, 0.1× fish · Zebasi 0.5× mountain, 0.5× forest, 0.5× fruit · Ai-Mo 1.5× mountain, 0.1× crop · Quetzali 2× fruit, 0.1× crop · Yădakk 0.5× mountain, 0.5× forest, 1.5× fruit · Aquarion 0.5× forest · Elyrion 0.5× mountain, 1.5× crop · Cymanti 1.2× mountain, spores replace crops · Polaris none (takes over neighbours' land, freezes it).

## Gaps

| ID | Missing | Status after 2026-10-22 |
|---|---|---|
| G1 | Continents / pangea / archipelago pipelines | **Partly filled (qualitative)**: Lakes has a land-bridge border and every player has land links to ≥2 villages; Continents = large discrete landmasses (same guarantee); Pangea = one central mass, ocean rim; Archipelago = broken landmasses, almost every city coastal; Waterworld = small islands with 1-2 villages. Process: capitals, then 1-2 suburbs each (not Drylands/Waterworld), then ~1/3 of remaining villages, then smoothed-noise terrain. No numbers for land fraction per type. |
| G2 | Whales, sharks, starfish counts | Open. Resources/Starfish/Whale pages would not load. Starfish can spawn on any water tile. Whaling tech removed. |
| G3 | Stale vs live fog | Open. Fog of War and Vision pages would not load (fandom and API). In-game test Q6. |
| G4 | Ruin reward weights | Open. Needs a ruin log. |
| G5 | Bot vision and policy | **Partly filled**: income (C24); Easy bots stay peaceful unless provoked, Crazy may attack immediately. Bots page would not load. Vision cheating still unknown. |
| G6 | Skill semantics | **Mostly filled** from WK Unit Skills: Carry, Convert, Dash, Escape, Fortify, Heal (adjacent, up to 4), Persist, Scout (5×5 vs 3×3 reveal), Auto Freeze, Boost, Creep, Eat, Explode, Fly, Freeze, Freeze Area, Grow, Navigate, Poison, Skate, Sneak-type (ignore enemy ZoC), Splash-type, no-retaliation (Phychi), Independent-type (no pop slot). Not covered: Tentacles, Drench, Swarm, Static, Stiff, Stomp, Surprise, Autoflood. PE source still unread. |
| G7 | Special-tribe trees | **Partly filled**: Cymanti full replacement table; Aquarion table (Fishing/Aquaculture/Marine Life/Navigation/Riding/Waterways/Spearing/Mathematics); Elyrion (Forest Magic replaces Hunting, Forestry → Sanctuary, Water Magic). Polaris tree is an image only. Unit stats still missing. |
| G8 | Extra buildings | **Partly filled** (WK Buildings, some rows pre-ocean-update): Customs House 5 (2★/turn per adjacent port), Sawmill/Windmill/Forge, Library, temples (Temple 20, Forest 15, Mountain 20, Water 20, Ice 20), Sanctuary 5, Ice Bank 20 (3★/turn per 20 frozen tiles), Outpost 5, Algae 5, Clathrus 5, Fungi 5, Mycelium 5. Embassy: only "cheaper, scales with count" (BP25). Port listed as 10 under Sailing is the old pre-ocean value. |
| G9 | City vision radius | **Settled (L3):** 3x3. Jason in game; saves agree (ring 1 always explored, ring 2 not). |
| G10 | GAIG terrainProbs.json | Not retried; low value now that WK gives the full modifier table. |
| G11 | Fog of War, Bots, Resources, Starfish, Whale, Vision, AI pages | **Still blocked** on fandom (client error, also via api.php). Wayback is blocked from here. You can open them on your phone and paste text, or I can try another mirror. |
| G12 | **New: Solaris** | BP25 mentions "Solaris Crater" and "Solaris Lava Bank": a newer special tribe not in any dataset. Unknown. |

## Second-engine cross-check (2026-10-23, overnight)

New source **PF = Polyfish** (github HenBOMB/Polyfish, Rust engine, Apache-2.0, last commit 2026-09-02, targets game version 115 "Cymanti Rework" with dated per-version rules in `version_sync.rs`). It loads states captured from the real Steam game, so its enum ids and many rules are tied to real data. Automated diff (`verify/crosscheck.py`): **283 fields agree, 31 differ**, most of which are Aquarion/Cymanti units PF lacks.

| ID | Effect of PF evidence |
|---|---|
| C6 | PF uses defenseForce (with bonus) for retaliation: **wiki + PF vs PE → settled wiki (L1)**. |
| C7 | PF v115 notes: poison defence debuff now **50%**, defence bonuses kept, poison slows units (Cymanti Rework). Wiki's 30% is pre-v115. |
| C8 | PF: Fishing → water (shallow) movement + Port; Sailing → ocean; **Navigation requires Ramming** (not Sailing). Starfish visible with Fishing/Sailing/Navigation, harvest needs Navigation, +8 stars. New conflict **C27** (Navigation prerequisite). |
| C19 | PF `version_sync`: after v105 clear forest **+1 star**, burn forest **3**. Matches PE (+1) and BP25 (3). **Settled**. Road still open. |
| C20 | PF retaliates unless Stiff / Surprise / out of range; no fog check (same as PE). Wiki is alone: stays open, test needed. |
| G1 | PF land ratios per map type: Drylands 0.95, Lakes 0.72, Continents 0.45, Pangea 0.78, Archipelago 0.38, Waterworld 0.15 (single source, L0). |
| G2 | PF: starfish +8 stars on capture. |
| NEW C28 | **Visibility of resources**: PF says crops are hidden until Organization/Farming/Construction, metal until Climbing/Mining/Smithery. So turn-1 screenshots undercount; the test sheet must log techs. |
| NEW C29 | Unit stat differences PE vs PF: Raft range 1 vs 2, Pirate move 1 vs 2, Mooni defence 2 vs 1, Shaman cost 5 vs 10, Exida move 2 vs 1, Boomchi move 1 vs 2 (+amphibious), Polytaur cost 3 (BP25) vs 2. Cymanti rows: PF is v115-current, prefer PF. |

C23 now has a pre-registered test (`verify/c23_models.py`): three generator models simulated per tribe; a verdict needs a Bayes factor > 10. Power analysis: WIKI is decided in ~3 capitals if true; PE vs PF needs ~8-30 capitals. Best tribes to separate PE from PF: Hoodrick, Quetzali, Elyrion, Yadakk, Cymanti, Aquarion.

## Engine inconsistencies to remember when using PolyEnv as the simulator

- `ScoreSystem::startingScore()` is stubbed to return 0. Starting score comes from `Tribe.cpp`, which is wrong for several tribes.
- Ocean gate: movement uses Sailing, Explorer uses Navigation (C8).
- Retaliation excludes defence bonus (C6) and ignores fog (C20): both contradict the wiki.
- Burn Forest 5 (now 3), no backwards research, temples 50 per level: pre-2025 values (C25, C26).
- Only 4 capital guarantees (wiki says all tribes, C10).
- `TurnSystem.refreshUnitsForCurrentPlayer` is flagged as a placeholder in its own comments.
- Special tribes have unit stats but not their techs, buildings or mechanics.

## Polyfish engine runs (2026-10-23 morning)

The slim Polyfish engine (no AI, server or replay modules) builds offline. Its dependencies are vendored from GitHub tags; see `sim/`.

- **Test set:** 660 generated maps. They are 300 normal-size Lakes maps with 4 players (15 tribes cycled), plus 60 maps of each type.
- **Capital ring (8 tiles):** mean 4.4 resources, close to the wiki reading. 93% of capitals have 2 or more identical resources. Per-tribe values are in `verify/pf_engine_ring8.json`.
- **Lakes, normal size:** land 0.72, 13.8 settlements out of 25 grid slots (55%, near the wiki's 60%), 7 ruins in most maps (matches the ruin table), starfish about 4 (vs water/25 = 2).
- **Drylands (Polyfish mapgen issue):** only 0.51 land. The wiki says Drylands is all land, so Polyfish's mapgen is NOT fully faithful.
- **How it is used:** it is treated as a third model in the C23 test, not as ground truth.
- **C23 power on turn-1 visible counts:** 4-10 capitals median (90th percentile 10-25) to reach a verdict, 90-98% correct.
- **Jason plays on iPhone, and there are no save files.** Gate C therefore moves to 15 or more test-sheet capitals.

## First real save (2026-10-23, iPhone, game version 123)

Jason's turn-0 save is a Massive 30x30 Drylands map with 15 Crazy bots (16 capitals). It was read with the new `verify/state_v123.py`: the iOS file is double LZ4-wrapped, and the v123 header differs from the Go library's layout. Full rows are in `verify/ledger.json`.

**Settled at L3 (measured in the real game):**

- **C23:** the wiki table is SHARES of land tiles. Measured P(resource | terrain) matches the wiki reading (|z| <= 1.5); the PolyEnv reading is rejected (z 4 to 18). Capital rings average 5.9 resources.
- **C10:** every capital (16 of 16, 12 tribes) has 2 or more identical resources.
- **C21:** the turn-0 reveal is exactly 5x5 for every player.
- **Resources:** none beyond distance 2 of a settlement.
- **Ruins:** 23 on a 900-tile map.
- **Start units** are confirmed for 12 tribes.
- **Drylands:** Aquarion capitals also get 2 fish water tiles.

**Consistent but still L2:** C9 (70 settlements vs 66 predicted by the wiki-literal generator).

**Partly off:** C12. Hoodrick, Aquarion, Zebasi and Oumaji terrain shares deviate from the wiki table; more maps are needed.

**New tool:** `sim/wiki_mapgen.py` is a wiki-literal generator (wiki numbers applied as written; its PARAMs are flagged). Its self-check reproduces the wiki shares to within 0.7% (terrain) and sampling noise (resources).

## Six real saves, one per map type (2026-10-23 07:45)

All six are Massive maps, game v123, turn 0, each with 15 Crazy bots, giving 96 capitals in total. See `verify/ledger.json` and `saves/real_vs_generator_by_type.json`.

**Map type codes and land share:**

- The header map-type codes run 1 to 6: Drylands, Lakes, Continents, Archipelago, Waterworld, Pangea.
- Measured land share by type:

| Type | Land share |
|---|---|
| Drylands | 0.996 |
| Lakes | 0.733 |
| Continents | 0.468 |
| Archipelago | 0.399 |
| Waterworld | 0.151 |
| Pangea | 0.513 |

**Settled or narrowed:**

- **C23 (resource table):** settled by all six maps.
- **C10 (2 identical resources at the capital):** holds for every tribe except Vengir. Vengir has no guarantee.
- **C12 (terrain modifiers):** a corrected forest rule fits better. The forest multiplier re-weights forest against field; it is not simply applied as written. This was fitted on 3 maps and confirmed on 3 new maps.
- **Starfish:** the count is about water tiles / 25.

**Still open:**

- **C9 (village count):** the generator places 5 too few on Lakes and Drylands and 8 too many on Continents and Pangea.
- **Capital rings:** these run about 0.25 resources richer than the generator predicts.
- **AquaCrop (resource 9):** found next to Vengir capitals. Unexplained.

## 27 saves (adds 4 Massive, 6 Normal 16x16, 3 Lakes at 14/18/20), 2026-10-23
- **AquaCrop is a general water resource (L3).** 831 tiles on Water/Ocean across 27 saves, next to capitals of every tribe except Luxidoor. Shallow water within 1 tile of a settlement: Fish 0.44, AquaCrop 0.22, none 0.34. At distance 2: 0.13 / 0.08. The wiki's "Fish 0.5" ignores it; the generator never makes it.
- **The capital-ring gap is AquaCrop.** Real ring-8 mean is 5.79, or 5.34 without AquaCrop; the generator gives 5.47. The "+0.25 richer" gap is closed.
- **Ruins match the wiki size table exactly**: 14->5, 16->7, 18->9, 20->11, 30->23.
- **Land share does not depend on size.** Lakes runs 0.74-0.78 at every size; the other types at Normal match Massive. Continents is the noisiest, 0.47-0.63.
- **C9 village counts are still open.** Normal totals: Drylands 16, Lakes 16, Continents 14, Archipelago 15, Pangea 12, Waterworld 7. The generator is close at Normal size, except Pangea (14.8) and Huge Lakes (22 vs real 28). A fit on area alone misses Archipelago and Waterworld badly, so placement likely depends on islands or landmasses.
- **C10 holds at all sizes.** All 305 non-Vengir capitals have a pair; 11 of 19 Vengir capitals do.
- **C21 5x5 reveal holds at all sizes.**

## Generator now uses the saves first (measured mode), 2026-10-23
- `sim/wiki_mapgen.py generate(..., mode="measured")` is the default. Tables come from `data/measured_mapgen.json`, built by `verify/build_measured_tables.py` from all saves. Rebuild after adding saves.
- **The wiki is overruled on:** AquaCrop (missing from the wiki); fixed capital pairs for every tribe (the wiki says random for six of them); Luxidoor's fixed ring; per-tribe mountain/forest/field shares; village totals per map type (Drylands 0.67, Lakes 0.65, Archipelago 0.60, Continents 0.52, Pangea 0.48, Waterworld 0.24 of the (n//3)^2 slots); land share.
- **The wiki still supplies:** placement order, spacing, resource zones, the tribe multipliers as a prior, ruins, starfish and lighthouses.
- **Check** (`sim/validate_measured.py`): capital rings are within 0.2 of real for all 16 tribes (the wiki mode is off by up to 2.6 for Luxidoor and 0.9 for Zebasi). Water resources and land share match. Village counts are within the real spread, except Huge Lakes, where there is only 1 save.

## Full save decoding and start table, 2026-10-23
- `verify/state_v123.py read_state()` now decodes whole files: the initial state, the current state, players (stars, score, techs, kills/losses, diplomacy) and the action list. All 27 saves decode with 0 bytes left over.
- **Actions record what was done, not the result.** Combat damage is checked by replaying a game from its turn-0 state and comparing with the saved current state. One played save therefore tests the whole combat model.
- **Start table (L3, 324 players):** stars 7/6/2/5 as the wiki says, starting units confirmed, Luxidoor capital at level 3. Aquarion's unit is id 46, which Polyfish lacks. Turn-0 scores are in `data/measured_start.json`. Adding 100 × the start tech's tier gives every wiki start score, which settles C3 = 530 and C5 = 515.
- **Starting techs are granted at turn 1**, so turn-0 saves list none.
- **The tech tree is confirmed from a screenshot:** all 25 links. Costs are 5 at tier 1 and 6 at tier 2 with 1 city.
- **Solaris exists in v123** (Jason). It needs a turn-0 save.
- **Goal set by Jason:** winning and combat. Score is not a target.

## Ruin page and real ruin placement, 2026-10-23
- **C14 / G4:** the wiki Ruin page now says rewards are a uniform pick among the eligible options, which agrees with PolyEnv. The reward list is updated: Veteran Swordsman on land (not a Super Unit), Veteran Rammer with a Warrior on water (not a Battleship), Lost City for Aquarion on deep ocean. The frequencies still need a ruin log, and the exact Explorer fog condition is unclear.
- **Placement (L3, 481 ruins):** the wiki is wrong that ruins can touch villages since 2.0.58. In v123 they are ≥2 from villages, ≥3 from capitals and ≥3 from other ruins, never on shallow water, sometimes on deep ocean, and sometimes on top of a hidden resource. The generator's measured mode uses these spacings.

## Starting techs and scores settled (L3), 2026-10-23
- The save's current state (after the StartMatch action) holds starting techs and start scores. I misread this earlier as "granted at turn 1".
- **Settled:** C1 Ai-Mo Philosophy 730; C3 Polaris Frostwork 530; C4 Cymanti Farming 630; C5 Kickoo 515 (PolyEnv was right, the old fandom figure wrong). Aquarion's start tech has id 45, which Polyfish lacks. Full table in `data/measured_start.json`.
- **G3 fog:** Jason sees enemy units stay drawn after he walks away. Still to check: stale image or live view of explored tiles.

## Game info cards (40 screenshots), 2026-10-23
- **The unit stats in the dataset are correct** for 10 standard units, apart from two fixes: Cloak attack is 2, not 0; boats show 10 HP.
- **C19 mostly settled:** Road costs 3 (PolyEnv right), Burn Forest 3 (as in the 2025 patch), Port 7. Every building price read is listed in `data/measured_ui.json`. Not yet seen: Clear Forest, Sawmill, Customs House, Sanctuary.
- **C25 settled:** backwards research is allowed.
- **Literacy:** −33%, rounded up; 4/4/5 at 1 city.
- **G8:** Embassy costs 5 and pays both sides while you are not at war, double with a peace treaty.
- **G12 Solaris:** its tech tree, 4 units and 2 buildings are recorded. It still needs a save for its ids.

## G3 fog settled, 2026-10-23
- **No stale fog:** an explored tile stays visible, and units on it are shown live. Only unexplored cloud tiles hide units. The explored set in the save is therefore the player's exact vision. Hidden information means units in unexplored tiles plus unexplored terrain.

## Engine v0: combat checked by replay, 2026-10-23
- `engine/` (stats.py, state.py, replay.py) replays a save's actions from turn 0 and compares unit HP, type, position and owner at each exported checkpoint.
- **Bot war 6e1bf8e0 (16 players, 468 attacks by turn 15):** at turn 5, 63 of 66 units have exact HP. Matches drop later: 77 at turn 11 and 93 at turn 15, against 14 and 20 HP mismatches, because of the open items below.
- **Settled by A/B replay (L2):** C6, the counter-attack does include the defence bonus. Also settled: the city bonus applies only to Fortify units (4 with walls), the terrain bonus needs its tech, rounding is half-up, there is no counter-attack from out of range, and melee attackers move in after a kill.
- **Still to model:** Aquarion v123 units (ids 46, 48 and 53 are not in any enum: 46 Mermaid, 48 Swordsmaid, 53 Shark; the other Aquarion ids are still unknown), boat HP, healing (passive or reward?), unknown action types 18/24/27/38 (abilities), splash, poison, explode (Cymanti), and Polaris freezing.

## The Misty Fields (e15f392c), 16 turns in a row, 2026-10-23
Jason (Imperius) vs 15 Hard bots on a 30x30 map, exported every turn from 1 to 16 (2254 actions, all decoded). This game has Aquarion, Polaris and Cymanti, so it exercises most of the special rules. A per-turn tool (restart from each save, replay one turn) pinned each mismatch to its turn. Every change below was A/B tested on all three replay games and kept only if no score dropped.
- **Push direction (was L0, now L2):** Polyfish's rule. The unit keeps going the way it last moved, enemies go the opposite way, and a unit that hasn't moved goes toward the map centre. 2/2 ruin pushes land on the saved tile. Ankiian turn 3 is now exact.
- **Ruins (C14, G4):** a unit reward spawns on the ruin tile and pushes the explorer. The log grows to 13 ruins (above). The weights are still open.
- **Polaris ice:** a Mooni freezes the water and ocean around it straight after it moves or captures (4/4 cases). Ice also melts again, which is not modelled; the replay re-reads terrain at each checkpoint.
- **Oasis Struggle (af181c8f, turns 1-26, 16 tribes):**
  - Unit id 48 is the Aquarion Swordsmaid.
  - A Giant at sea is a Juggernaut.
  - A land unit can board at a port after a kill there or when pushed there.
  - A boat on Cymanti algae stays a boat.
  - A tribe with no cities left loses its units.
  - Per-turn replay: 2310 → 2356 exact. Full replay: 2157 → 2252 exact over 24 checkpoints.
  - Boarding at a port (after a kill or a push) needs the tribe's own port: 4/4 boarded at their own port, 0/2 at an enemy port.
  - A/B check: bot war 66, 90, 110 → 66, 90, 111. Misty Fields turns 13-16: 132, 144, 148, 157 → 133, 144, 149, 157, every unit exact. Ankiian unchanged.
- **Action type 18 (open, test item):** bots only, a tile holding one of their own units, usually right after it moved and next to an enemy. Nothing visible changes and the unit does nothing more that turn. It is not a poison cure (0/79 poisoned) and not a promotion (0/79 veteran afterwards).
- **Flood and algae:** the save's flood flag is the TileEffect enum (1 Flooded, 4 Algae). On Aquarion-flooded land, boats stay boats and walkers stay walkers (a city is plain land). On Cymanti algae, land units walk on water.
- **Moving in after a kill:** a boat landing after a kill drops its passenger. A land unit doesn't follow a kill into water. Sharks and Raychi (water-only) don't follow onto dry land.
- **Boat records:** a boat's own record always shows promotion 0. The passenger record keeps veteran status, and the boat's HP is the live value.
- **Splash** (Bomber): neighbours take half damage, floored. **Poison** (C7): defence halved. Fungi poisons non-Cymanti units at end of turn.
- **Shaman:** converts like a Mind Bender. In one sample it also dealt normal damage and took no retaliation (L3, n=1).
- **Test items, not decided:**
  - Action 38: Polyfish says the Shaman's Boost became Swarm, which adds movement only. The +0.5 attack makes no difference in any replay.
  - Action 18: still unknown (36 more samples).
  - Whether Recover cures poison.
  - Shaman damage plus conversion needs a second sample.
- **Result:**
  - Misty Fields is exact through turn 12, with 157 exact at turn 16 and no HP mismatch at any checkpoint.
  - Bot war: 66/66, 90/92, 110/122 (was 85/92, 106/118).

## Economy (stars) check, 23 Oct 2026

- `engine/economy.py` checks every player's stars between two saves: stars + income − spending + rewards.
- **Result:** 657/691 player-turns exact on the per-turn games (Ankiian 94/96, Misty Fields 234/240, Oasis Struggle 329/355). The bot war, with saves 4–6 turns apart, is 11/32.
- **New rules:** bot bonus (handicap − 1 a turn, needs own capital); siege; meeting stars; negative population; starfish +8; ruin stars read back from the next save; save timing (see the ledger, ECON-*).
- **Settled:** the tech formula tier × cities + 4 (Literacy ⅔) holds. The old residuals came from meeting stars, not from tech prices.
- **Open:**
  - Structure 51 price (n = 2). Aqua Farm 5 is confirmed in game.
  - Polarism and Oceantology tiers.
  - Embassy (5 stars, then +2 for each further one; 2 a turn to both sides, 4 with peace), Market and Clathrus income are coded from the in-game text but not yet seen in a save.
  - Clathrus counts Fungi (v123 card) vs Algae (Polyfish): test item.
- **Diplomacy actions:**
  - 27 is Offer Peace: all 37 actors had Strategy.
  - 28 is the reply: 1 led to peace 5/5 times; 0 did not 16/18 times.
  - 29 is Break Peace (n=1).
  - Test items: units disbanded inside the ex-ally's borders when peace is broken; no attacks between tribes at peace. Neither is in the engine yet.
  - About 15 player-turns still 1 star short.
- **C27 settled (L3):** Navigation needs Sailing, not Ramming. 24 of 36 research actions had Sailing without Ramming; 2 had neither (backwards research).
- **C9 decided for lakes, continents and archipelago (L2):** the pre-registered held-out test (`verify/c9_test.md`) uses the per-map-type shares. They beat PolyEnv by 10^530 and the wiki's 60% by 10^2.3 on 6 new saves. Drylands, pangea and waterworld still need a held-out save each.
- **Gate E, 23 Oct 2026:**
  - The dataset rebuilds from `build_dataset.py`. Hand-entered game facts now live in `data/game_ui_overlay.json` instead of edits to the generated JSON, and a rebuild reproduces every committed file.
  - `validate_dataset.py` passes, including a new check that every sourced fact carries a game_version stamp (141 facts and 58 units).
  - The Polyfish cross-check gives 290 agree and 36 disagree, all 36 explained (`verify/crosscheck_explained.json`).
  - Every ledger rule has a game_version.
  - New test item C29b: Polyfish gives Mooni and Shaman the Static skill, but our cards don't list it.
- **Cliff & Gods (09a5bf1e, Crazy, 16 tribes, turns 1–8):**
  - Crazy bot bonus confirmed at 3 a turn (L3): 83/90 bot player-turns exact, against 0/90 with 2 or 4.
  - Combat replay turn by turn: 419/422 exact.
  - Stars: 85/96 player-turns exact.
- **Settled from Jason's play, 23 Oct:**
  - Action 38 is the Shaman's Swarm: neighbours get extra movement (Swift), not +0.5 attack.
  - A Mooni freezes adjacent enemy units when it moves (3 of 4 frozen units in the saves stand next to an enemy Mooni).
  - Both are in the engine. Neither changes the HP or position scores.
- **C9 extended (L2):** Drylands (67/100, table 0.668) and Pangea (48/100, table 0.48) held-out saves match exactly. 9 held-out saves: the table beats the wiki by 10^4.0. Only Waterworld is still untested out of sample.
- **C20 (retaliation vs fog) can't be tested from the saves.**
  - In 1198 attacks replayed turn by turn, the two readings never differ (`verify/c20_test.py`).
  - A melee attacker is always seen. A ranged attacker in fog is usually out of the defender's range anyway.
  - Still a split: the wiki says no retaliation; Polyfish and PolyEnv say yes.
  - Test item: an enemy Archer attacked by a hidden Cloak, or shot at from 2 tiles away out of its sight.
- **Action 18 is Break Ice (L3).**
  - 91/92 uses had ice next to the unit.
  - With the rule, ice-vs-water mismatches drop from 148 to 0. The open "ice melting" item was this.
  - Still open: 12 tiles where the save has ice the engine didn't freeze.
- **C9 decided for all six map types (L2).** Waterworld held-out save: 24/100, and the table says 0.24. Over 10 held-out saves the table beats the wiki by 10^15.6. Gate B passes.
- **C20 settled (L3), from Jason's in-game test:**
  - An Archer or Catapult shot from a tile it can't see doesn't shoot back.
  - A Cloak never takes or gives retaliation.
  - A Dagger takes none when it attacks but retaliates when attacked.
  - The Gaami freezes like the Mooni.
  - In the engine, sight counts explored tiles plus current vision. With explored tiles alone it wrongly blocked 4 real retaliations.
- **C29b settled (L3):** neither the Mooni nor the Shaman has Static (Jason; Polyfish is wrong). The Mooni never retaliates (Stiff). The Shaman retaliates with plain damage, and retaliation never converts. The engine's Shaman skills are fixed; scores are unchanged.
- **Clathrus counts Fungi:** the in-game card wins over Polyfish's Algae (tie-break: real game first).
- **Gate A passes, 23 Oct.** Two L0 items stay as test items outside its scope (ruins and diplomacy):
  - Elyrion ruin rewards.
  - Units disbanded when peace breaks.
- ECON-BOT-BONUS: bonus is also not paid while the capital is besieged (enemy unit on it). A/B: stars exact 754->762/819, units unchanged.
- AQUARION-TECHS (Jason screenshots, 2026-10-23, 1 city, turn 0): Waterways costs 6 (tier 2; unlocks Flood, Bubbled), Aquaculture costs 6 (tier 2; Atoll 5 stars, Aqua Farm 5 stars), Tridention 8 stars, Mermaid Archer 3 stars (atk 2 def 1 mov 1 range 2, Dash+Fortify), Tridention (hp10 atk2.5 def1 mov2 range2, Dash+Persist). Marine Life, Spearing, Free Diving exist in the tree. Which save ids 39/46/47 are which is NOT settled: only tiers are known (47 tier 1; 39, 46 tier 2). Ids not named.
- 2026-10-23 AQUARION-TECH-TIERS: Aquarion tech ids 47 (tier 1), 39 and 46 (tier 2) priced by the star check (engine/economy.py AQUARION_TIERS); names still unknown.
- 2026-10-23 ROUND-START-INCOME: saves ending with the round-end EndTurn hold the round opener's income (refines PAID_AT_TURN_START, which held for ordinary EndTurns).
- Bot war 6e1bf8e0 t5-11 unit misses closed (polish-botwar): unseen ruin reward = veteran Swordsman (RUIN-UNIT-UNSEEN), no kill move-in onto a mountain without Climbing (KILL-MOVE-CLIMBING). Both n=1.
- PUSH-DIRECTION: open case af181c8f t10 (CityReward Giant at 2,17): the pushed Warrior was trained there and never moved, Polyfish's toward-centre rule says (3,16), the save has (1,18), the opposite way. Test item, not settled.
- 2026-10-23 SPLIT ECON-EMBASSY vs EMBASSY-ACTION: Jason and the v123 card say an embassy costs 5; both embassies in saves (09a5bf1e p1 t7, 6e1bf8e0 p12 t13) cost the builder a net 4, and the builder got no embassy income while neutral. Engine uses the measured 4 (EMBASSY_COST). Test: count stars right before and after building one embassy, and again at the next turn start.
- Moth stats split: Polyfish v115 defence 0.1, v123 replay fit >= 1.6 with no retaliation against its attack (MOTH-V123, n=1). Test item: in game, read a Moth's info card (attack, defence, skills).
- engine/stats.py: inline comments had swallowed Exida, Larva and Moth (they fell back to 10/2/2); fixed 2026-10-23 by polish-botwar.
- ACTION-18-AFTER-MOVE (2026-10-23): 128 of 130 move-then-break-ice uses are Dash units, 2 are a Raft (no Dash on any source). Test item: does a Raft (or its passenger's Dash) allow moving then breaking ice?
- AQUARION-TECH-TIERS / AQUARION-UNIT-IDS (2026-10-23): names for tech ids 39, 46, 47 and unit ids 47, 49-52, 54, 55 come from one source (Polyfish types.rs comments, positional for units): L0. Test item: Jason's per-turn Aquarion research save names them.
- Unverified engine switches (2026-10-23, data/rule_levels.json marks them): peace_break_disbands, break_ice_after_move_needs_dash, market_income, clathrus_income, and the embassy +2 price step. No save tests them; each is on at the best guess and changes no replay score.
- 2026-10-23 CITY-LEVEL-BY-REWARD: action 21 is not a level-up (Level changes track CityReward 243/243); its meaning is open. engine/economy.py LEVEL_FROM_REWARD.
- Wiki cross-check 2026-10-23 (search snippets only; fandom, breezewiki, archive.org, miraheze are blocked from this container): Embassy builder income (wiki 2/turn vs saves 0 while neutral) and price (wiki 5 vs saves net 4) conflict; Break Ice open to all units but Mooni/Gaami (wiki) vs 'Dash to move first' (Jason's text) vs 2 Raft cases; 46 = Marine Life (unlocks Shark) now L2.
- Bot war 6e1bf8e0 t13: Juggernaut kill move-in onto land (lands as Giant, stomps) replaces the old 'not onto land' reading of JUGGERNAUT-KILL-MOVE; the af181c8f t21 case was a mountain without Climbing.
- POLARIS-CAPTURE-FREEZE (new, L3 n=1): a Polaris city capture freezes the water around the city. Open: does border growth (city level-up) freeze new Polaris water too? 4 of 16 newly Polaris water tiles stayed water; not checked which.
- 2026-10-23 ECON-MARKET-CLATHRUS: Market pays the adjacent Windmill/Sawmill/Forge levels, not +1 each (af181c8f p14 t25, n=1; MARKET_BY_LEVEL).
- IDLE-AUTO-RECOVER (new, L3 n=1): a human player's idle wounded units heal at End Turn. In-game test for Jason: leave a wounded unit idle in own territory for one turn and check it gains 4 HP; also whether a unit that only moved (no attack) heals.
- SAVE-UNIT-FACING: UnitDirection byte 2 is the unit's facing (0 NW, anticlockwise: W, SW, S, SE, E, NE, N). Open: what sets a new unit's facing, and why a never-moved Warrior facing E was pushed SW (af181c8f t10, CityReward Giant at 2,17). The other ~15% of moved units whose facing differs from the last move may be turned by attacks; not checked.
- PUSH-TIEBREAK (new, L3 n=1): the clockwise side is tried first when a push's first choice is blocked, not the side nearer the centre (Polyfish). One deciding case (af181c8f t10); more pushes with both sides free would settle it.
- Settled 2026-10-23 (Jason in game + re-test): breaking peace disbands the breaker's units inside the ex-ally's territory (DIPLO-BREAK-DISBAND, L3 for the disband); moving then breaking ice needs Dash, 130/130 in the saves, the 2 'Raft' exceptions were engine bookkeeping (a Raft upgraded to a Scoutship has Dash).
- IDLE-AUTO-RECOVER confirmed by Jason in game (23 Oct): idle units heal +4 in friendly territory, +2 neutral/enemy, capped at max HP, poisoned units don't heal. Matches the engine. Open: the saves show AI players' idle units not healing (57 replay misses if applied); 'friendly' may include allied (peace) territory, engine uses own territory only.
- PUSH-TIEBREAK confirmed by Jason in game (23 Oct): counter-clockwise first, then clockwise, alternating outward; no open tile removes the pushed unit. Matches the engine (switch renamed push_ccw_first; push_no_room_removes added, not yet exercised by any save).
- Bot war 6e1bf8e0 unit misses 23 -> 0 (polish-botwar). Last two: push centre direction is nearest-by-angle (new units' saved facing, 824/871), and a Giant boarding as a Juggernaut stomps (STOMP-ON-BOARDING).
- Bot war 6e1bf8e0 unit misses 23 -> 0 (polish-botwar). Last two: push centre direction is nearest-by-angle (new units' saved facing, 824/871), and a Giant boarding as a Juggernaut stomps (STOMP-ON-BOARDING).
- ECON-EMBASSY (24 Oct): price settled at 4 for the first embassy, +2 for each further one (web summary Jason sent, 'following balance updates': 4, 6, 8...), agreeing with both saves (net 4). The earlier 5 (Jason's memory, v123 card reading) is superseded. +2 a turn each side, doubled at peace; reveals the 3x3 around the host capital. Step +2 still unseen in a save.
- TRIBE-TECH-TIERS (24 Oct): Oceanology (save id 49, Cymanti, needs Pescetism) costs 7 at 1 city on Jason's v123 card -> tier 3. Unlocks Living Island (20 stars; 20 HP, atk 4, def 4, move 2, range 1; Stomp, Algae, Static, Poison; water) and Gather Stars. Added to TIER: bot war p16 t11->15 residual -8 -> -1. Trade costs 7 at 1 city (tier 3, matches base tree).
- ECON-MARKET-CLATHRUS (24 Oct, v123 cards from Jason): Market 5 stars, 'Produces 1 star for each nearby Windmill, Forge, Sawmill each turn', one per city. Clathrus 5 stars, '1 star for each nearby Fungi each turn', poisons units that step on it, one per city (card says Fungi, so Polyfish's Algae is wrong for v123). SPLIT kept as a test item: the card reads 1 per building, but the one save case (af181c8f p14 t25) fits the building's level (+3 for a Windmill with 3 Farms); MARKET_BY_LEVEL stays on as measured.
- Ruin reward frequencies measured (DIST-RUIN-REWARD, n=54): consistent with uniform over the eligible pool (p=0.14). Cymanti ruin unit = Mantis (land) / Boomchi (water) (RUIN-UNIT-CYMANTI, n=2). Bot city rewards: level 4 always Border Growth (36/36), level 5+ always Super Unit (14/14), level 2 Workshop 59%, level 3 about even (DIST-CITY-REWARD). Polyfish has no ruin weights. Explorer condition (RUIN-REWARD open point) still open: water ruins gave 0/10 explorers.
- AQUARION-TECHS (24 Oct, inferred from prerequisites in all 6 Aquarion saves): Aquarion players own base Navigation (14, needs Sailing) and Aquatism (12, needs Ramming) but never base Fishing (10), Sailing (13) or Ramming (44), so their tribe versions fill those slots. 46 is always bought before Navigation -> Marine Life replaces Sailing (agrees with the wiki cross-check). 39 is bought before Aquatism (e15f392c) and in 1bf60251 without Organization (so not Waterways, which replaces Roads) -> 39 = Aquaculture (Ramming slot, tier 2, 6 at 1 city on Jason's card). 47 is tier 1 and always bought before 39 and 46 -> 47 = Aquarion Fishing (Jason's card shows Fishing buyable for 5 at turn 0, so it isn't the start tech). 45 = the Aquarion start tech, not Sailing (Sailing's slot is 46, bought later). Inference, one source type: confirm with one research-and-export test.
- AQUARION-TECHS (24 Oct, L3): game ed6cb932 (Jason's Drive doc, turns 0-4): the only Aquarion player (p1) owns exactly [Basic, 45] on turn 0 and researches Fishing on turn 1 (Jason) -> the save records tech 47. Every other tribe's Fishing is id 10 (11 tribes in the same game). So 47 = Aquarion Fishing, 45 = Aquarion start tech. Confirms the prerequisite inference; 39 = Aquaculture and 46 = Marine Life stay inferred (46 also wiki-backed).
- AQUARION-TECHS (24 Oct, L3): game ed6cb932 turn 5 (Jason: researched Aquaculture and Marine Life that turn): p1 researched 46 then 39, techs go [Basic,45,47] -> [Basic,45,47,46,39]. So {39,46} = {Aquaculture, Marine Life}, measured; 39 is not Waterways. Which is which comes from the earlier evidence: 46 always precedes Navigation (Sailing slot) and is wiki-backed as Marine Life; 39 precedes Aquatism (Ramming slot) -> 39 Aquaculture. All four Aquarion ids now settled: 45 start tech, 47 Fishing, 46 Marine Life, 39 Aquaculture. Waterways id not yet seen.
- AMPHIBIOUS-WATER (24 Oct, pf-port): Aquarion Mermaids/Swordsmaids stand on shallow water with only the start tech (11 save records); ocean seen only with Navigation + Marine Life (open: which one opens ocean).
- CYMANTI-TECHS (24 Oct, pf-port): v123 Cymanti use the base Sailing/Ramming/Navigation/Diplomacy; Raychi via Sailing (21/21), Boomchi via Ramming (35/35), Algae via Fishing (12/12), Moth via Diplomacy (n=1). Polyfish's Hydrology/Synergy/Oceantology replacements removed in sim/pfcore.
- ALGAE-MOVE (L3, pf-legal): Cymanti units and boats move through Cymanti algae; whether another tribe's land unit stops on algae is untested (in-game test in status.md).
- SKATE-MOVE (L3, pf-legal): skaters get +1 movement wherever they start; Mooni max 2, Battle Sled max 3 in the saves (answers pf-port's skating-range question from the saves).
- PORT-STEP (L3, pf-legal): only boarding needs the own port; frozen ports, ports on flooded land and amphibious units walk onto any port.
