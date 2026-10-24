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

## Scores

| commit | legal | units | stars |
|---|---|---|---|
| 8d129e7 (start) | 8481/8972 94.5% | 4723/4734 | 750/819 |
| a0b9be3 | 8657/8972 96.5% | 4723/4734 | 750/819 |
| 46f9984 | 8818/8972 98.3% | 4723/4734 | 798/819 (pf-port's star work) |

## Next step

Left (pf_miss --illegal): Mermaid onto ocean (Waiting on Jason: which tech), Research / Build 21, 8, 27, 28
"not offered" with stars in hand, Aquarion 49/51 (no Polyfish type), a few odd moves. Downstream (not
generation): CityReward not pending, Train city full, stars short, Attack already attacked.
