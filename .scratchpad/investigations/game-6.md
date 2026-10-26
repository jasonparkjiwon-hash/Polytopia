# Jason's game 6 (ingested 2026-10-26)

_Owner: ingest session · state: ingested, held-out scored, released for tuning 2026-10-26_

Source: Jason's Google Doc "Polytopia game 6" (21 saves, path + base64, no notes). Save id 9906f7da,
"Butte Treaties", Hard, 30x30, 85% water, 11 players; Jason = p1 Cymanti; one save every turn.
Kept turns 2-20 (19 saves). Left out: t0 (pre-StartMatch) and t1, whose action list starts with
12 bytes the decoder doesn't know (`00 03000000 18000000 00` then the u16 action count 45; (3,24)
may be a selected tile); t2's log holds the same turn-1 actions, so nothing is lost.

**Decoder fix (verify/state_v123.py):** the tile byte after TileSkin is a count of TileEffect ids
(u32 each), not a flag. t13, t15-t17 have tiles with 2 effects: Flooded (1) + Tentacle (3), likely
Aquarion unit 52's effect. Every older save decodes byte-identical.

## Held-out score (before any change, rules commit 11018f7)

Units 917/984, stars 173/198.

## Misses, classified (for the rule-fixing sessions)

- **Unknown Aquarion units 49, 50, 51, 52** (Polyfish positional: MermaidDefender, MermaidCloak,
  MermaidDagger, Jelly; L0). 52 has 20 HP. Nearly all 67 unit misses: 42 type-name misses
  (`unit49` etc.), plus HP/kill/position misses from their missing stats. p9 (Aquarion) star misses
  -6, -5, -13, -2, -14, -1, -3 on turns 12-20 are their unpriced trainings (and builds).
- **Embassy income (contradicts ECON-EMBASSY / EMBASSY-ACTION):** Jason built an embassy (action 30)
  in the Aquarion capital (10,24) on turns 6, 13, 14, 15, 18. While it stood (p9's Diplomacy record
  for p1: EmbassyLevel 1 at t7-t13 and t16-t17), **both p1 (builder) and p9 (host) got +2 a turn more
  than the engine pays**, with no peace (all offers rejected). The engine pays the builder nothing
  while neutral (from 2 older cases). EmbassyLevel dropped to 0 at t14 and t18: the embassy was lost
  (how? asked Jason) and rebuilt. Price per rebuild not yet separated (residuals t6 +2, t13 0, t14 0,
  t15 +2, t18 -5 for p1 mix price and income).
- **p10 Zebasi -20 at t17->18 and t19->20:** something costing 20 the engine doesn't price. Not checked.
- **p1 t18->19 -5:** embassy rebuild price or income stop; with the embassy item above.

## What the game contains

- **Peace:** Jason offered peace to the Aquarion on turns 6, 7, 18 (all rejected); Imperius
  offered it on turns 18, 19 (rejected).
- **Embassies:** 5 builds by Jason, all on the Aquarion (above).
- **Ruins:** 16 examined, 15 on water.
- **Living Island:** Jason trained one on turn 11 with Organization, Strategy, Diplomacy, Fishing,
  Sailing, Navigation researched and no Oceanology (ledger TRIBE-TECH-TIERS says Oceanology unlocks
  it: check). Also a Moth (Diplomacy) and Raychi.
- **Water Temple** (build 19) x2, Grand Bazaar x1, Aqua Farm x14, Atoll x5, Enchant Animal x2.
- Not here: Sanctuary, Oceanology research, Giant.
