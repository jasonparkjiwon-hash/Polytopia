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

## Scores (2026-10-24, with pf-port through WATER-UNITS)

Python referee: units 4728/4728, stars 802/819.

| game | units exact | stars exact |
|---|---|---|
| 09a5bf1e Cliff & Gods | 420/421 | 4/96 |
| 1bf60251 Ankiian | 291/291 | 84/96 |
| 6e1bf8e0 bot war | 204/230 | 1/32 |
| af181c8f Oasis | 2362/2393 | 38/355 |
| e15f392c Misty Fields | 1413/1425 | 28/240 |
| **total** | **4690/4760** | **155/819** |

Totals differ from 4728 because units Polyfish keeps alive (extras) count as misses too.
Unit misses by kind: hp 29, missing 17, pos 17, extra 13, type 1.

Legality: **7813/8972 = 87.1%** of logged actions are in Polyfish's legal list.
Capture 175/175, ExamineRuins 56/56, Recover 154/155, EndTurn 979/979, Attack 1160/1198,
Move 3524/3765, Promote 35/38, CityReward 215/264, Train 750/1028, Research 233/369, Build 361/614,
Upgrade 94/127, BreakIce 30/92, Explode 11/24, OfferPeace 0/40, PeaceReply 0/37.

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

Stars (`pf_stars.py`, 819 player-turns; most misses have the first cause):
- 571 bot bonus missing (DifficultyHandicap - 1 a turn while the capital is held; needs
  `TribeState.handicap`, which the loader will fill as soon as the field exists).
- 78 meeting stars differ (turns where a tribe was met).
- Prices: Enchant Animal (pf 1 vs 3), Outpost (unimplemented in Polyfish: it refuses the build),
  Starfish (needs Navigation in Polyfish and gives 0; v123 +8), tech costs (e.g. pf 5 vs 6/7),
  Aquarion techs 39/45/46/47 and structures 49/51 unmapped.
- "spend ExamineRuins" lines in pf_stars are ruin stars (not misses; pf_miss allows them).

Illegal actions (`pf_miss.py --illegal`), by cause:
- Stars short after drift (follows from the star causes): Train 172, Build 151, Research 104, Upgrade 32.
- Aquarion movement, 142 Moves: Mermaid/Shark/Swordsmaid on flooded land and water get few or no steps.
  Cause found: Polyfish lets a unit onto water or flooded land only with a tech whose `unlocks_terrain`
  is Water (Fishing); Aquarion's v123 start tech 45 (AquaBase, ledger AQUARION-TECH-TIERS) has no Polyfish
  id and is dropped. Test (not committed): loading 45 as Fishing cuts these 142 to 84 (legal 87.1% ->
  87.8%). For pf-port: add tech 45 (and 39, 46, 47) with what they unlock; the rest is likely Ocean.
- Other movement, 69 Moves: Cymanti water units (Boomchi, Raychi, Living Island) between land and
  water; Polaris skating on ice (Mooni, Battle Sled 2-3 tiles onto ice).
- Train, unit not unlocked by the tribe's techs: Boomchi 56 (35), Shark 53 (27), Raychi 35 (21),
  Moth 61, Living Island 57. City full (units > level): ~15, check v123's cap.
- Break Ice not offered (59): units that moved without Dash or attacked. Also v123 clears all ice next
  to the unit in one action; Polyfish clears one tile and ends the unit's turn (44 extra tiles refused).
- Peace: Polyfish's generator has OfferPeace and PeaceReply switched off ("to prevent loops"): 0/40, 0/37.
- Convert: Polyfish's move list never offers ConvertMove; a converter's attack converts in v123 (4,
  played as ConvertMove; the Shaman's damage is then missing).
- City reward not pending (49): Polyfish's city hasn't levelled. 36 have a logged harvest/build near the
  city that Polyfish refuses or values differently (Starfish needs Navigation in Polyfish; Outpost is
  unimplemented; Fishing); 13 have no logged source near the city (unknown pop gain).
- The reverse, a reward Polyfish wants that the log never picks: hidden by the harness for the rest of
  that turn (noted "reward Polyfish wants but the log never picks"), so it no longer makes every later
  action illegal.
- Explode not offered (13), Attack "already attacked" (10).
- Downstream of earlier divergence: no unit at source / no defender (~25).

Units (70 misses): HP 1-2 off after fights (af181c8f), pushes/move-ins to another tile, boats not
boarded (PORT-BOARDS), Cymanti/Aquarion units not trained; the Shaman's convert damage.

## Next step

1. OfferPeace / PeaceReply: see why Polyfish never offers them (`--detail OfferPeace`).
2. Fill pf-port's new fields when they land: `TribeState.handicap`, `embassies`, `UnitState.ever_moved`.
3. Re-run after each pf-port batch; keep this table current.
