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
python3 -I tools/pf_miss.py --accept         # one line: tuned and held-out (data/holdout.json) units, stars, legal %
python3 -I tools/pf_miss.py --holdout        # held-out games only
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
- `scripts/check.sh` prints `pf_miss --accept` (units, stars, legal % for tuned and held-out saves) as an informational line.
- One hook in Polyfish: `UnitState.uid` (save unit id; rules ignore it).

## Scores (2026-10-24, c0235c8, pf-port through TECH-COST)

`python3 -I tools/pf_miss.py --accept` (also the last line of `check.sh`, informational):
`PF ACCEPT tuned: units 4713/4749, stars 719/819, legal 94.0% | held-out: units 187/187, stars 53/64, legal 96.0%`

Python referee: units 4728/4728, stars 802/819; held-out ed6cb932 187/187, 64/64.

| game | units exact | stars exact |
|---|---|---|
| 09a5bf1e Cliff & Gods | 420/421 | (see pf_miss) |
| 1bf60251 Ankiian | 291/291 | |
| 6e1bf8e0 bot war | 211/224 | |
| af181c8f Oasis | 2377/2389 | |
| e15f392c Misty Fields | 1414/1424 | |
| **total** | **4713/4749** | **719/819** |
| held-out ed6cb932 | 187/187 | 53/64 |

Unit misses by kind: hp 11, pos 13, extra 7, missing 4, type 1.

Legality: **8431/8972 = 94.0%** (held-out 96.0%). Capture, Recover, EndTurn, ExamineRuins all legal;
BreakIce 91/92, Attack 1170/1198, Move 3673/3765, Promote 36/38, Upgrade 120/127, Research 322/369,
Train 924/1028, CityReward 215/264, Build 494/614, Explode 11/24, OfferPeace 0/40, PeaceReply 0/37.

History: 87.2% (032c9fd) -> 91.4% (bot bonus) -> 93.2% (Aquarion techs, AMPHIBIOUS-WATER) -> 93.8% (Break Ice
after a Dash move, d4e40af) -> 94.0% (harness plays one Break Ice, c0235c8).

## For pf-port, biggest first (541 illegal left; all below are rule gaps, not loader/harness)

1. **Stars drift** (80: Train 29, Research 23, Build 22, Upgrade 6): follows the 100 star misses; `pf_stars.py`.
2. **Peace** (77, DIPLO-PEACE L3): Polyfish's generator has OfferPeace (27) and PeaceReply (28) switched off
   ("to prevent loops"). The loader can fill pending offers from DiplomacyMessages once replies are generated.
3. **Water/ice movement** (79 Moves): Cymanti Boomchi/Raychi/Living Island leaving a city 2-3 tiles onto
   water or algae (~25); Polaris Mooni/Battle Sled skating 2-3 tiles from a city onto ice (~11); Mermaid
   ocean->ocean or onto ocean (~10: which tech opens ocean for Aquarion?); a few boats into a port.
4. **Train unlocks** (57): Boomchi 56 (35), Raychi 35 (21), Moth 61 (1): tribe techs don't unlock them.
5. **Fish harvest** (build 7, ~22, and downstream city rewards): `functions.rs` resource gate checks
   `Fishing` itself; v123 also accepts the tribe's replacement (Aquarion 47 AquaFishing, Polaris fish under ice).
   Suggest `resolve_tech_for_tribe(Fishing, tribe)` in the gate.
6. **City reward not pending** (49): downstream; the city's pop gain came from a build Polyfish refused
   (Fishing above, Outpost 33 ~17, Starfish 46 ~6, Mine 21 ~6, 38 ~6).
7. **Outpost** (build 33, ~17): unimplemented in Polyfish. **Aquarion structures 49/51** (11): no Polyfish type
   (the loader drops 29 of them at load).
8. Explode not offered (13), Attack "already attacked" (13: mostly Knights whose earlier attack killed in
   v123 but not in Polyfish: HP drift), Train "city full" (15: checked, not a loader bug: homes load right (`trace.py` shows
   them); the real city had levelled from a build Polyfish refused, e.g. 09a5bf1e t5 Outpost -> 3 Polaris units), monuments 27/28 (8: Polyfish recomputes tasks heuristically; the save's Tasks aren't loaded),
   ConvertMove never generated (4, SHAMAN).

## Harness rules (how logged actions become Polyfish moves)

- Each logged action -> candidate Polyfish moves (`candidates()` in pfreplay). The first that is in
  `legal_moves()` (matched by `serialize()`) is played; if none, the first candidate is played anyway
  and the case is listed as illegal with a cause.
- Action map: 6 Move -> StepMove; 2 Attack -> AttackMove, else ConvertMove; 5 Train -> SummonMove;
  16 Upgrade -> UpgradeMove; 1 Build -> BuildMove, except 7/9/15 -> HarvestMove, 46 Starfish ->
  CaptureMove, 30 -> EnchantAnimalMove; 7 Capture / 14 Ruins -> CaptureMove; 8 -> ResearchMove;
  11 -> RewardMove; 13 Promote, 3 Recover, 4 HealOthers, 17 FreezeArea, 24 Explode, 38 Swarm (BoostMove),
  9 Destroy; 18 Break Ice -> one BreakIceMove on an ice tile next to the unit (Polyfish clears them all);
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
- Tasks (player `Tasks`: Polyfish has no task state; it recomputes them), DiplomacyMessages (pending peace
  offers -> `has_offered_peace` false; moot while Polyfish generates no PeaceReply), embassies list.
- Now mapped: `DifficultyHandicap` -> `TribeState.handicap` (pf-port), Aquarion techs 39/45/46/47 (pf-port's enum).
- Centipede leader/follower links (none in the saves so far).
- Fog memory (`memory_units`), pacifist turns, `attacked_this_turn`.

## Misses by cause

Current, ranked: "For pf-port" above. Older notes (stars by cause): `pf_stars.py` splits star drift into
income/spending causes; "spend ExamineRuins" lines there are ruin stars (pf_miss allows them).
Diagnosis helpers: `--detail "<cause text>"` (matches "<type>: <cause>"; the [Aquarion] tag is not part of it),
`tools/trace.py` now shows tile resources too (`res3` = fish).

## Next step

1. Re-run `pf_miss.py --accept` after each pf-port batch; update the scores table.
2. Loader: once Polyfish generates PeaceReply, fill pending offers from the save's DiplomacyMessages.
3. Harness: once stars are close, drop the "on credit" crutch from the legality score (report both).
