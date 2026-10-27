# pf-legal (Phase 3 prep, see backlog item 0): Polyfish move generation to 100%

_Owner: pf-legal session · started 2026-10-24_

The forward model and search only consider moves Polyfish generates, so every logged action must be in
Polyfish's legal list. Owns pf-loader.md's list items 2 (peace), 3 (water/ice movement), 4 (train
unlocks), 5 (resource gates via the tribe's tech), 7 (Outpost 33, Aquarion 49/51), 8 (Explode,
ConvertMove). pf-port owns stars drift (1, 6) and unit HP/position misses (9).
Tests: `sim/pfcore/src/v123_legal_tests.rs` (helpers from v123_tests). README section "Legal-move generation".

## How to run

```sh
sh scripts/restore_saves.sh
(cd sim/pfcore && cargo build --release && cargo test --release; git checkout Cargo.lock)
python3 -I tools/pf_miss.py --illegal | head -40
python3 -I tools/pf_miss.py --detail "<type: cause>" 50
```

## Done

- Peace (DIPLO-PEACE): pf-port shipped the generator at the same time (ec8f6da); pf-legal added the
  fallback target for an opponent without a capital (540b4cc) and the loader's pending offers from
  DiplomacyMessages `[1, sender]` (a0b9be3). OfferPeace 38/40, PeaceReply 37/37. The 2 offers left
  (6e1bf8e0 t5 #1045/#1201, player 5 -> 3) fail the "met" gate: 5 met 3 at turn 7 in the save, Polyfish
  doesn't meet them (meeting drift, pf-port Findings).
- Fishing via tribe tech and Cymanti train unlocks: pf-port did these too (4c13187, ec40fcf).
- ALGAE-MOVE (865f82c): Cymanti units and boats move on through algae (+26 Moves).
- SKATE-MOVE (5c38f0f): skaters +1 movement from anywhere; saves: Mooni max 2, Sled max 3 (+10).
- PORT-STEP (8ac629e): frozen / flooded-land ports and amphibious units step onto enemy ports (+13).
- WATER-UNITS-VILLAGE (cd0174a): Raychi/Shark into villages and cities, stop there (+10).
- EXPLODE-ANYTIME (4388fed): no adjacent enemy needed (+12); Moth explodes (925d276, MOTH-V123) -> 24/24.
- CONVERT-ATTACK (46f9984): converters get ConvertMove, not AttackMove; a boat carrying a Mind Bender
  attacks normally (passenger skills must not count: e15f392c t9 #1007).
- Research (58e699f, TRIBE-TECH-TIERS + RESEARCH-BACKWARD): the generator uses pf-port's
  get_researchable_techs (tribe techs never inherited `next`) plus each known tech's prerequisite (Vengir
  Mining from Smithery). Research 351 -> 361.
- METAL-WITH-MINING: Metal visible with Mining too (Vengir have no Climbing): Build 577 -> 585.
- pf-legal-2 (26 Oct): AMPHIBIOUS-WATER ocean (Mermaid onto ocean with Marine Life 46; innate = switch
  `amphibious_ocean_innate`, off, Jason's L0 answer) +10 Moves; AQUARION-STRUCTURES (Aqua Farm 49 on AquaCrop,
  +2 pop; Atoll 51 on water/ocean/flooded land, pop not modelled; both need Aquaculture 39) +14; PORT-FLOODED
  (Ports on flooded land) +6; AQUARION-UNIT-47 (Mermaid Archer replaces Archer) +7, units +8; MONUMENT-TERRAIN
  (monuments on ice; ocean for Aquarion) +3; SWIFT-MOVE (save effect 6 from Swarm = +1 movement) +4.
- pf-legal-3 (27 Oct): CYMANTI-OCEANOLOGY-ID (Navigation unlocks the Living Island for Cymanti) +2;
  AQUARION-LOST-CITY (ocean ruin -> level-3 city, both rewards pending; pf_jobs reads the city from the next save
  as the ruin hint) +8, stars +2; AQUARION-AQUA-FARM-WATER (Aqua Farm on empty water/ocean, makes the AquaCrop;
  the old "on AquaCrop" was read from after-build saves) +4; CLATHRUS-ON-LAND (Field/Forest next to own Fungi)
  +2. EXPLODE-WATER-SPORES (explode on water: algae + Spores, Fungi follows) +1; AQUARION-FREE-SPIRIT (Aquarion
  research base Free Spirit; 25 Free Diving never seen) +1; FLOOD-ALGAE (land units walk onto flooded land, no
  water tech) +2; WATER-UNIT-PORT-PASS (Sharks sail on through an own port) +2; MOONI-CAPTURE-NO-UNIT-FREEZE
  (Mooni capture freezes tiles, not adjacent enemy units; e15f392c t5) +4; CITY-UNITS-OWN-ONLY (city unit limit
  counts only the owner's units) +4; Lost City finder rehomed there +1.
  `tools/trace.py`: `--city` (owning city + city record), `--players` (tribe, stars, techs, kills, tasks,
  diplomacy), `--acts P` (every action of player P).

- pf-tail-2 (28 Oct): CAPTURE-DISCONNECT (a captured connected city loses 1 pop, the captor's capital keeps its
  population; af181c8f t8 #755) CityReward legal 403 -> 404; WATER-ROUTE (ports link over water in up to 5 steps,
  diagonals count, not through enemy tiles, to own ports and to own cities with an own port beside them; a
  port-side city is also a route source; the saves mark the route in the tile flag HasWaterRoute, which `tools/trace.py`
  does not print: see the grid script idea below) 404 -> 413, Train +1; EMBASSY-AT-PEACE (embassies can be built at a
  tribe at peace, 6e1bf8e0 t11 #1839) Embassy 5/7 -> 6/7. Referee: RULES mooni_capture_freezes_units (off), scores
  unchanged (units 7389/7392, stars 1511/1540, held-out 187/187, 64/64). `tools/trace.py --city` now also prints
  ConnectedPlayerCapital.

## Scores

| commit | legal | units | stars |
|---|---|---|---|
| 8d129e7 (start) | 8481/8972 94.5% | 4723/4734 | 750/819 |
| a0b9be3 | 8657/8972 96.5% | 4723/4734 | 750/819 |
| 46f9984 | 8818/8972 98.3% | 4723/4734 | 798/819 (pf-port's star work) |
| METAL-WITH-MINING | 8836/8972 98.5% (held-out 99.4%) | 4723/4734 | 798/819 |
| AQUARION-STRUCTURES (old set) | 8860/8972 98.8%; games 1-5 held-out 3135/3163 99.1% (new 5: 2778/2809 98.9% before) | 4723/4734 | 798/819 |
| SWIFT-MOVE (games 1-5 now tuned) | 11682/11781 99.2% | 6455/6457 | 1320/1342 |
| pf-legal-3 start (12 games) | 13145/13257 99.2% | 7386/7398 | 1500/1540 |
| a2176ce CLATHRUS-ON-LAND | 13165/13257 99.3% | 7389/7397 | 1512/1540 |
| Lost City finder rehomed | 13181/13257 99.4% | 7391/7394 | 1512/1540 |
| pf-tail-2: CAPTURE-DISCONNECT, WATER-ROUTE, EMBASSY-AT-PEACE | 13216/13257 99.7% (held-out 354/354) | 7391/7394 | 1512/1540 |

## Next step (pf-legal-3 handoff, 27 Oct)

Legal 13181/13257 (99.4%), held-out 354/354; units 7391/7394, stars 1512/1540. Illegal left: 76. Almost all are
not move generation:
- **pf-port (drift):** CityReward not pending 39 (population drift, e.g. Polaris capitals levelling with no logged
  build: Outpost network), stars short ~20 (incl. ATOLL-ON-ALGAE #1494, now offered), Gate of Power x2 (6e1bf8e0 t11:
  Polyfish misses kills because #1623/#1624 find no defender at (7,3): an enemy got there unlogged, push/spawn),
  Move no unit at source x2 (same tile), city full e15f392c t10 #1093 (save city level 3, Polyfish 2), af181c8f t24
  #4071 Defender 488 "already moved" (mid-turn save flags?), 9906f7da t17 #1252 target unexplored (exploration),
  af181c8f t22 #3456 Rammership onto mountain (needs Cymanti units at (24,11)/(24,12) gone by then).
- **pf-port (embassy convention):** Embassy x2. 9906f7da t13 #818: p1 builds at p9, but the t12 save has p9's record
  (1, state 0, EmbassyLevel 1), which embassies_to_builder_side reads as "p1 already has one at p9"; no p1-p9 combat
  before #818. Either the record side is reversed or something unlogged destroyed it. 6e1bf8e0 t11 #1839 likewise?
- **Jason:** Jelly (52) tech (2 Trains); Cymanti bot p16 researched tech 49 (6e1bf8e0 t11 #1678) holding
  [0,1,6,7,8,10,13,20,38,44] (no Navigation): what is it and what does it need? (Jason's Oceanology is 14.)
- **Random, not modelled:** Lost City spawns resources (fish) around itself: Build 7 x2 (9906f7da t11 #693/#697).
  Its terrain change (orthogonal ocean -> water) is also unmodelled; the next checkpoint re-syncs it.

Legal by type: Move 5608/5614, Attack 1442/1444, Train 1397/1407, Build 1015/1029, Research 631/634, CityReward
380/419, Embassy 5/7; all others 100% (EndTurn, Capture, Upgrade, Recover, BreakIce, ExamineRuins, OfferPeace,
PeaceReply, Promote, Explode, Swarm, HealOthers, BreakPeace, FreezeArea).

## Next step (pf-tail-2 handoff, 28 Oct)

Legal 13216/13257 (99.7%), held-out 354/354; units 7391/7394, stars 1512/1540. Illegal left: 41.
- **CityReward not pending 6** (413/419): 09a5bf1e t7 #820 (p13 (27,2) gains +2 with no logged cause; its capital
  +2 is the Mine), af181c8f t8 #795 (Polaris capital, Outposts: real total is 1 above Polyfish's, Outposts' own pop
  not modelled?), af181c8f t12 #1479 (Cymanti Mycelium), e15f392c t5 #417, 9906f7da t12 #808 (after ExamineRuins),
  6e1bf8e0 t11 #2003. Each is 1 short. `HasWaterRoute` (tile flag, also set on ice for Polaris routes) is the real
  network record: print it with a small script over the save (grid of terrain digit, `*` for HasWaterRoute, `P` port,
  `C` city) before touching connection rules; Cymanti Mycelium and Polaris ice routes may deserve the same check.
- **Stars short ~20 are economy itself** (`tools/pf_stars.py`: "econ itself off", the Python economy misses the same
  player-turns): the Aquarion bot p9 of 9906f7da is off +3, +3, -2, +5, +8, +5 over t13-t19 (no link found to
  Train 49/53 counts or Build 46); 6e1bf8e0 t5->11 has 9 players off by 2-6 over six turns (too coarse to tell).
- **Kill/position drift (unchanged):** 6e1bf8e0 t11 #1623/#1624 find no defender at (7,3) (XinXi's Swordsman 199 left it
  at #1437, so who stood there is unlogged); #1805/#2014 no unit at source are the same tile; Gate of Power x2 follow
  from the missing kills. af181c8f t24 #4071 already moved, 9906f7da t17 #1252 / af181c8f t22 #3456 targets unchanged.
- **Embassy #818** (9906f7da t13): p1 rebuilds an embassy at p9 while the save shows level 1 (cost 4): a level-2
  rebuild or a stale record; not modelled (EMBASSY-AT-PEACE ledger text).
- **Jason:** Jelly (52) tech, Cymanti bot tech 49, as before.
