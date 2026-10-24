# pf-loader (Phase 3 prep, see backlog item 0)

_Owner: pf-loader session · started 2026-10-24_

Real saves loaded into Polyfish, the logged actions replayed there, scored like
`tools/miss.py`, plus the legality check (is every logged action in Polyfish's
legal-move list?).

## How to run

```sh
sh scripts/restore_saves.sh
(cd sim/pfcore && cargo build --release && cd ../.. && git checkout sim/pfcore/Cargo.lock)
python3 -I tools/pf_miss.py                  # units / stars per game + LEGAL line
python3 -I tools/pf_miss.py --illegal        # illegal actions grouped by cause ([Aquarion] = Aquarion actor)
python3 -I tools/pf_miss.py --detail "<type or cause text>" [n]   # what Polyfish saw at those actions
python3 -I tools/pf_miss.py --list           # one line per unit/star miss, plus loader drops and notes
python3 -I tools/pf_stars.py                 # star drift split into income / spending causes
python3 -I tools/pf_stars.py <game> <turnA> [players]   # one checkpoint pair
```

Pieces:
- `sim/pfcore/src/save_loader.rs`: save JSON -> `GameState` (+ `LoadReport` of what was dropped).
- `sim/pfcore/src/bin/pfreplay.rs`: runs jobs (checkpoint, log range), legality check, unit ids, output JSON.
- `tools/pf_jobs.py`: builds jobs from `saves/`, ruin-reward hints, runs the bin.
- `tools/pf_miss.py`, `tools/pf_stars.py`: scoring and diagnosis.
- `scripts/check.sh` prints `pf_miss` TOTAL/LEGAL as an informational line (can't fail the baseline).
- One hook in Polyfish: `UnitState.uid` (save unit id; rules ignore it).

## Scores (2026-10-24, after pf-port's Aquarion units and Juggernaut commits)

Python referee: units 4728/4728, stars 802/819.

| game | units exact | stars exact |
|---|---|---|
| 09a5bf1e Cliff & Gods | 418/423 | 4/96 |
| 1bf60251 Ankiian | 291/291 | 82/96 |
| 6e1bf8e0 bot war | ~171/256 | 1/32 |
| af181c8f Oasis | ~2290/2440 | 40/355 |
| e15f392c Misty Fields | ~1400/1437 | 29/240 |
| **total** | **4645/4802** | **157/819** |

Units total differs from 4728 because extras (units Polyfish keeps alive) count as misses too.

Legality: **7758/8972 = 86.5%** of logged actions are in Polyfish's legal list.
ExamineRuins 56/56, Capture 172/175, EndTurn 972/979, Recover 152/155,
Attack 1150/1198, Move 3513/3765, Train 755/1028, Build 364/614, Research 236/369,
CityReward 210/264, Upgrade 94/127, BreakIce 30/92, OfferPeace 0/40, PeaceReply 0/37, Explode 11/24.

## Harness rules (how logged actions become Polyfish moves)

- Each logged action -> candidate Polyfish moves (`candidates()` in pfreplay). The first that is in
  `legal_moves()` (matched by `serialize()`) is played; if none, the first candidate is played anyway
  and the case is listed as illegal with a cause.
- Action map: 6 Move -> StepMove; 2 Attack -> AttackMove, else ConvertMove; 5 Train -> SummonMove;
  16 Upgrade -> UpgradeMove; 1 Build -> BuildMove, except 7/9/15 -> HarvestMove, 46 Starfish ->
  CaptureMove, 30 -> EnchantAnimalMove; 7 Capture / 14 Ruins -> CaptureMove; 8 -> ResearchMove;
  11 -> RewardMove; 13 Promote, 3 Recover, 4 HealOthers, 17 FreezeArea, 24 Explode, 38 Swarm (BoostMove),
  9 Destroy; 18 Break Ice -> BreakIceMove on every ice tile next to the unit (v123 breaks them all);
  27 -> PeaceTreatyMove(tile, other); 28 -> PeaceRequestResponse(offerer, flag); 29 -> BreakPeaceMove;
  30 -> EstablishEmbassyMove; 15 EndTurn -> EndTurnMove; 15 with player 255 (round end), 20, 21 skipped.
- **Stars short only:** if the action becomes legal with 1000 more stars, it is played on credit (the
  tribe's stars stay below the real count). Listed as "stars short in Polyfish (drift)".
- **Level-up rewards:** v123 lets a player pick the reward later in the turn; Polyfish offers only the
  reward until it's picked. When Polyfish has one pending, the player's next logged CityReward is played
  early (counted legal).
- **Ruin rewards** (not in the log): read from the next save like the Python replay's ruin oracle
  (unit created that turn on the tile = Swordsman, unexplained new tech = FreeTech, star check +10 =
  Resources, else Explorer) and passed as a CaptureMove hint.
- **Unit ids:** `uid` from the save; new units get temporary negative ids, renamed by the first logged
  Move/Attack and otherwise paired by tile (as `miss.py` does). Boarding gives the boat a new temp id and
  the passenger gets its id back on landing; an upgrade gives a new id.
- **Turn order:** EndTurn calls Polyfish's end_turn (next player's income and resets there). If the
  logged actor isn't Polyfish's current player, the current player is set (counted in notes).
- **Stars scoring:** same player-turns as `miss.py` (economy.py rows with cities); exact = Polyfish stars
  equal the next save, allowing +10 per ruin examined (ruin stars aren't logged).

## Field map (save JSON -> Polyfish)

Mapped: terrain, climate (= tribe id), owner, capital_of (`Capital`), ruling city (`CapitalCoordinates`),
road, water route, skin, explorers (`PlayerVisibility`), flood 1 -> Flooded, 4 -> Algae; resources;
improvements -> structures (level, founded turn); cities (owner, name, level, production = **level**,
TotalPopulation -> population, CurrentPopulation -> progress, border size, connected, rewards);
units (id, owner, type, HP/10, veteran from passenger record for boats, kills = Experience, home,
created turn, moved/attacked, flipped, effects, passenger type, direction = UnitDirection[2] + 1);
prev_coords from the log's last move (push direction); tribes (tribe, name, bot = AutoPlay, stars,
score, kills, losses, techs, met players, unique improvements, diplomacy: peace / last attack /
embassy level / first meet / ..., killed if DestroyedTurn); settings (size, turn, seed, version 115,
max turns 10000, current player = next actor in the log).

Not mapped (dropped or unknown):
- Save city `Production` (1 or 2 at every level; meaning unknown). Polyfish production = level.
- Improvements 49 (AquaFarm), 51 (Aquarion structure): no Polyfish type; dropped (load report).
- Techs 39, 45, 46, 47 (Aquarion v123): no Polyfish type; dropped. Research of them is unmapped.
- Tasks (player `Tasks`), DiplomacyMessages (pending peace offers -> `has_offered_peace` false),
  `DifficultyHandicap` (waiting for pf-port's `TribeState.handicap`), embassies list, `ever_moved`.
- Centipede leader/follower links (none in the saves so far).
- Fog memory (`memory_units`), pacifist turns, `attacked_this_turn`.

## Misses by cause (for pf-port)

Stars (`pf_stars.py`, 819 player-turns):
- 567 bot bonus missing (DifficultyHandicap - 1 a turn; needs `handicap` field + rule).
- 71 meeting stars differ (turns where a tribe was met).
- Prices: Enchant Animal (pf 1 vs 3), Outpost (pf 0 vs 5), Starfish (pf 0 vs +8), tech costs
  (e.g. pf 5 vs 6/7 for tier 2/3), Aquarion techs/structures unmapped.
- Ruin stars show as "spend ExamineRuins" in pf_stars (not a miss: pf_miss allows them).

Illegal actions (`pf_miss.py --illegal`):
- Stars short (drift from the above): Train 156, Build 145, Research 102, Upgrade 31.
- Aquarion movement (138 Moves): Mermaid/Shark/Swordsmaid on flooded land and water get few or no
  steps in Polyfish.
- Cymanti water units (Boomchi, Raychi, Living Island) between land and water; Polaris skating on ice
  (Mooni, Battle Sled 2-3 tiles onto ice): ~45 Moves.
- Train not unlocked: Boomchi 56 (35), Shark 53 (24), Raychi 35 (21), Moth 61, Living Island 57.
- Train "city full" (units > level): ~18, check v123's cap.
- Break Ice not offered (51): units that moved without Dash, or attacked; v123 allows it.
- City reward not pending (44): Polyfish's city hasn't levelled (pop from a failed harvest, or v123
  pop rules).
- OfferPeace 0/40, PeaceReply 0/37: not checked yet (translation or Polyfish's diplomacy conditions).
- Explode not offered (12), Attack: no defender / already attacked (~30), Move: no unit at source (~20):
  downstream of earlier divergence; check after the above.

Units (`pf_miss.py --list`, 157 misses): mostly downstream of the illegal actions above (units not
trained, Aquarion movement, ruin units).

## Next step

1. OfferPeace / PeaceReply: see why Polyfish never offers them (`--detail OfferPeace`).
2. Fill pf-port's new fields when they land: `TribeState.handicap`, `embassies`, `UnitState.ever_moved`.
3. Re-run after each pf-port batch; keep this table current.
