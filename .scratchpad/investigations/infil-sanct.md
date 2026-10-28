# Infiltration and Sanctuary test docs (ingested 2026-10-28)

_Owner: ingest session · state: ingested, held-out scored, released for tuning 28 Oct, rules below kept (ledger ids)_

Source: Jason's Google Docs 'Polytopia infiltrate' (196Ef4...) and 'Polytopia sanctuary game' (18ybfp...), fetched fresh 28 Oct.
No notes by Jason in either doc (device-path lines + base64 only). All 11 blobs decoded, 0 unparsed bytes. None were in `saves_raw/`.
The docs hold few saves, not every turn: **infiltrate** has 5 saves in 3 games: `5d15d70f` t6, t7; `5f3ffaea` t5 (single, no pair); `ac4b122a` t10, t11.
**sanctuary** has 6 saves of one game `9ac0b946` t6-t11 (the t8 blob was in the doc twice with different bytes; the first was kept).
All are 16-player 30x30 games with Jason as p1 Quetzali (infiltrate games) and p1 (sanctuary, 3 Sanctuaries built by p1). No t1 saves (docs start at t5/t6).

## Held-out score (before any change, rules commit 9d14312)

| game | units | stars | Polyfish units / stars |
|---|---|---|---|
| 5d15d70f | 65/65 | 15/16 | 65/65, 14/16 |
| 9ac0b946 | 518/518 | 79/80 | 518/518, 80/80 |
| ac4b122a | 129/129 | 15/16 | 127/131, 14/16 |
| 5f3ffaea | no pair | | |

Total 712/712 units, 109/112 stars (referee). With ed6cb932: 899/899, 173/176. Plain `tools/miss.py` stayed 10191/10191, 1947/1972; `check.sh` passed.
After the one rule below (SANCTUARY-BUILD-TURN) held-out stars were 174/176 and the games were released the same day.
**Released for tuning on 28 Oct, after the scores above were recorded.** Plain `tools/miss.py` with all 12 games: **units 10903/10903, stars 2057/2084**.

## (a) Infiltration (8 events in all 20+ games: scripts in the session scratchpad, rerun by replaying and catching attacks by Cloak/Scuba/Moth on enemy cities)

Events (level = the city's level at the moment of the attack; count = units left):

| game, turn | unit, tribe | city level | units left | border facts |
|---|---|---|---|---|
| 5d15d70f t7 | Cloak, Quetzali (Jason) | 1 | 1 Dagger | 8 free land tiles in ring 1; took the first in row-major |
| 64795ee3 t9 | Moth, Cymanti (Crazy bot) | 1 | 1 Egg | 8 free; first row-major (mountain) |
| 710ddb20 t9 | Moth, Cymanti (Jason) | 2 | 2 Eggs | 5 free land in ring 1; took (7,24) and (9,25), not (8,24) |
| 710ddb20 t16 | Cloak, Quetzali (bot p3) | 4 (grew 3 -> 4 earlier that round) | 4 Daggers | only 3 free land tiles in ring 1: all three used, the 4th on ring 2 |
| 710ddb20 t19 | Moth, Cymanti (Jason) | 2 | 2 Eggs | free (7,24),(8,24),(9,24),(9,26): took the first two row-major |
| 9906f7da t18 | Scuba, Aquarion (bot) | 3 | 3 Mermaid Daggers | 4 free water tiles; took the first three row-major, left (2,25) |
| ac4b122a t11 | Cloak, Quetzali (Jason) | 2 (grew 1 -> 2 earlier in the pair) | 2 Daggers | exactly 2 free land tiles: both used, one is the Cloak's own tile |
| 6e1bf8e0 t11 | Moth, Cymanti | 2 | none | counter-case: the city had belonged to the Moth's side (MOTH-INFILTRATE) |

- **Count = the city's level at the moment of the attack: 7 of 7** (ledger INFILTRATE-COUNT). Careful: the level has to be read after any level-up
  earlier in the same pair (710ddb20 t16 and ac4b122a t11 looked like 3 -> 4 and 1 -> 2 Daggers "extra" until the CityReward action before the attack was noticed).
  The cap of 5 is untested (levels 1-4 seen). Polyfish's `min(5, level)` is right. Stars paid by the infiltrator: unchanged (INFILTRATE-STARS).
- **The unit in the city takes the normal attack damage** (5d15d70f: Warrior 10 -> 6 from a 5-HP Cloak, atk 2, def 2 with no city bonus, so 4 = the usual formula).
  The infiltrator disappears; the unit stays. The city gets `RebellionFlag` 1 for the next save (pairs: 5d15d70f, 710ddb20 t9/t17/t19, 9906f7da t19, ac4b122a).
- **Placement** (INFILTRATE-SPAWN, evidence added): units go on valid free tiles of the city's own territory: land for Daggers and Eggs, water for Mermaid Daggers;
  ring 1 before ring 2 (710ddb20 t16). Within a ring, sorting by row-major (y, then x) predicts the exact tile set in **5 of 7**; column-major 4/7, Euclid from the city
  3/7, nearest to the attacker 4/7, terrain-first (forest/mountain, then plain, then water) **no**: the spawned tiles are fields, mountains and forests with no pattern
  (resources do not matter either). The two misses are one tile off (710ddb20 t9, t16). Unit ids are not in row-major order, so the game places them in some other
  order, probably a shuffle with a first-N cut. Treat placement as random with a NW bias until more cases come in; the referee keeps reading the tiles from the next save.
- Not tested yet: fewer free tiles than the level (a case where some Daggers do not appear); a city with a wall; a level-5 city.

**For Polyfish (`sim/pfcore`, not edited here):** spawn `min(5, level at attack time)` units, Mermaid Daggers only on water, Eggs for Moths; candidates = free tiles
of the city owner's territory of the right kind including the infiltrator's own tile (it is removed first), ring 1 before ring 2, then row-major (5/7 exact). Keep it random-safe.

## (b) Sanctuary (9ac0b946, three Sanctuaries built by Jason: (6,20) turn 6, (11,18) turn 7, (13,19) turn 9)

- **Level = number of wild animals (Game) on the 8 tiles next to it, same save: 13 of 13 readings** (ledger SANCTUARY-LEVEL). It starts at 1 here because an animal stood next to each when built.
- **Income:** the engine's +1 per adjacent animal each turn (radius 1, price 5) fits every pair but one; the one miss was a build-turn effect: a Sanctuary built as the
  first action of a turn pays nothing that turn (the income arrives before the build). Fixed (`sanctuary_build_no_income`, SANCTUARY-BUILD-TURN): held-out stars 173/176 -> 174/176,
  all older games unchanged. The cost 5 is right in this game (no extra residual on the build turns). Radius 2 is not needed.
- **Animal spawn:** one new animal every 2 turns (turn T with (T - FoundedTurn) even, T > FoundedTurn), at the start of the owner's turn, on a free forest tile next to the
  Sanctuary **inside its owner's territory**: (6,20) got (5,20) at t8, (7,19) at t10; (11,18) got (10,18) at t9, (12,19) at t11; (13,19), also wanting (12,19) at t11, got nothing
  (one animal only). Neutral forests next to the Sanctuaries ((6,21), (11,17)) were never chosen. Order among free own forests: western first both times (n=2) (ledger SANCTUARY-SPAWN).
  Polyfish's "every 3 turns" does not fit; the card text "every 2 turns" does.
- **Fog:** all three Sanctuaries and their forests were in Jason's territory and visible. Fog effects not tested.
- Not tested: more than 3 animals (max level 8), a Sanctuary with no free forest left for several turns, Sanctuary near a border with another tribe.

**For Polyfish:** `api.rs` still lists "Sanctuary animal spawn tile: none: not measured" and the rate; set the rate to 2 turns, candidates = empty forest tiles next to the Sanctuary owned by the Sanctuary's owner, take the westmost (random tie-break), skip if none. Income: +1 per adjacent animal from the first income after the build.

## (5) Jason's attack-preview screenshot (defender in a grey-walled city)

I cannot see the image (no pixels came with the task), only Jason's description: attacker 10 HP, defender 10 HP shield in a city, red numbers 4 (above the enemy) and 5 (near the attacker).
In our formula dmg = round(aF/(aF+dF) x atk x 4.5), retaliation = round(dF/(aF+dF) x def x 4.5) with the defender's city bonus 1.5 (what `retaliation_uses_bonus` does):
**an attacker with attack 2 and a defender with defence 2, both 10/10 HP, with the 1.5 bonus gives exactly 4 and 5.** So the preview fits the model for two attack-2/defence-2 units
(Warrior-class, or any pair with those numbers); it does not show a defender taking "too little". It is one data point and the other candidates (other unit stats, a wall's 4x) do not give 4 and 5.
To use it for the open item (web-deep.md), Jason should send: the attacker's and defender's unit types and tribes, the defender's HP, the veteran stars, and whether a shield icon showed x1.5 or x4.

## Open

- Two star misses on defenders after an infiltration: 5d15d70f t6->7 p13 (Zebasi) 5 stars less than predicted (income 5 predicted, none came); ac4b122a t10->11 p4 1 less (a 40-star turn). Not Sanctuary, not found. Infiltrated defenders in the other six cases are exact, so the infiltration itself probably costs nothing.
- Placement of the extra tile and the order among tied tiles: needs more infiltrations (ask Jason for 3-4 more Daggers/Eggs cases with a note of which tiles were free).
