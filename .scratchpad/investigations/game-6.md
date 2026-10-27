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
  MermaidDagger, Jelly; L0). 52 = trainable 20-HP Jelly (AQUARION-UNIT-52, Jason: jellyfish). Nearly all 67 unit misses: 42 type-name misses
  (`unit49` etc.), plus HP/kill/position misses from their missing stats. p9 (Aquarion) star misses
  -6, -5, -13, -2, -14, -1, -3 on turns 12-20 are their unpriced trainings (and builds).
- **Embassy income (contradicts ECON-EMBASSY / EMBASSY-ACTION):** Jason built an embassy (action 30)
  in the Aquarion capital (10,24) on turns 6, 13, 14, 15, 18. While it stood (p9's Diplomacy record
  for p1: EmbassyLevel 1 at t7-t13 and t16-t17), **both p1 (builder) and p9 (host) got +2 a turn more
  than the engine pays**, with no peace (all offers rejected). The engine pays the builder nothing
  while neutral (from 2 older cases). EmbassyLevel dropped to 0 after each p1-p9 fight (t13, t14 attacks; t18 city capture) and was
  rebuilt: any combat or capture destroys it (Jason; EMBASSY-DESTROYED-BY-COMBAT). Price per rebuild not yet separated (residuals t6 +2, t13 0, t14 0,
  t15 +2, t18 -5 for p1 mix price and income).
- **p10 Zebasi -20 at t17->18 and t19->20:** Water Temple (build 19) costs 20 (WATER-TEMPLE-PRICE).
- **p1 t18->19 -5:** embassy rebuild price or income stop; with the embassy item above.

## What the game contains

- **Peace:** Jason offered peace to the Aquarion on turns 6, 7, 18 (all rejected); Imperius
  offered it on turns 18, 19 (rejected).
- **Embassies:** 5 builds by Jason, all on the Aquarion (above).
- **Ruins:** 16 examined, 15 on water.
- **Living Island:** Jason trained one on turn 11 with Organization, Strategy, Diplomacy, Fishing,
  Sailing, Navigation researched Jason: after Oceanology, so Cymanti Oceanology is saved as tech 14 (CYMANTI-OCEANOLOGY-ID;
  conflicts with TRIBE-TECH-TIERS 'Oceanology = 49'). Also a Moth (Diplomacy) and Raychi.
- **Water Temple** (build 19) x2, Grand Bazaar x1, Aqua Farm x14, Atoll x5, Enchant Animal x2.
- Not here: Sanctuary, Oceanology research, Giant.

## Embassy income: proposal for the rule session (A/B done, engine untouched)

Jason: an embassy pays unless the two tribes are actively fighting; he rebuilt it each time it broke.
Three changes to `engine/economy.py` (A/B with a scratch copy, star rows exact over every game):

| Variant | Stars exact |
|---|---|
| baseline | 1550/1604 |
| + standing embassies known across saves (read the host's Diplomacy EmbassyLevel in save a; `check()` only pre-books Build-70 embassies, not action 30) | 1554 |
| + `EMBASSY_BUILDER_PAID = True` (builder earns 2 while neutral) | 1561 (09a5bf1e -1) |
| + an attack or city capture between builder and host removes the embassy | **1562**, no game worse (09a5bf1e back; game 6 173 -> 185) |

Ledger: EMBASSY-INCOME-NEUTRAL, EMBASSY-DESTROYED-BY-COMBAT. The replay engine needs the same
destruction rule wherever it tracks embassies. Script: ask the ingest session (scratch `ab_embassy2.py`), or
rebuild it from the table: it monkeypatches `EC.Books` and `R.apply`.

## ref-fix results (27 Oct)

Kept (table in `games-1-5.md`): units 49-52 named, Mermaid Dagger stats, INFILTRATE, Water Temple 20, the three embassy
changes, embassy rebuild at the same host costs 4. Game 6 now units 934/937 (the 3 unit misses left over all games are all here),
stars 190/198. Left, classified:
- **Units (3 left, all games):** the 3 Mermaid Daggers from the t18 infiltration (placement random in Polyfish; the replay
  reads them from the next save). Fixed later the same day: the Super Unit push onto a fallback own port (PUSH-PORT-FIRST
  changed), and Jelly Tentacles (TENTACLES: a Jelly hits adjacent enemies after it moves and when an enemy moves next to it),
  which explained the Warrior HP rows t15->16, t16->17 and the t17->18 / t19->20 fight at (12,20).
- **Stars p9 (Aquarion):** +5 t13, +3 t14, -2 t15, +5 t17, +8 t18, +5 t19: train prices for 49/52/53 don't fit one set
  (D+J = 13 at t14; D+2S = 19 at t17 but 16 at t18). Mixed with embassy-host income; Waiting on Jason (prices).
- **Stars p1:** t17->18 -2 (engine pays the embassy at turn 18 start, the game doesn't; no p1-p9 fight in between),
  t18->19 -5 (Jason's income 0 at turn 19 start; the engine says 5; Jason lost (2,27) to p9 that round). Open.
