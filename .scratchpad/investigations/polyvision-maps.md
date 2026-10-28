# PolyVision maps (28 Oct 2026, session polyvision-maps)

**Source:** github.com/NeoLorenzo/PolyVision, `pol_env/Tribes/levels/phase1_pool_bardur_real/` (5,517 listed; no licence, so
nothing from it is committed). 11x11, one player (Bardur, capital `c:2`), map type Drylands, game v122, initial map only.
**Fetched:** 5,267 CSVs = train 5000 + validation 250 + human_benchmark 17, all SHA-256 verified.
The 250 `test/` files return 404 (not published). Every cell code parsed (11 distinct codes, nothing unknown):
`.:` `f:` `m:` plain; `.:f` fruit; `f:a` animal; `m:o` metal; `.:r` `f:r` `m:r` ruin (hides any resource); `v:` village; `c:2` capital.
No crop, fish, whale, water or lighthouse appears. Villages and capital lose their terrain in the CSV.

**Tools (committed, aggregates only):** `tools/polyvision_fetch.py <dir> [workers]` (fetch + verify, 4 workers),
`tools/polyvision_stats.py <pv_dir> <pf_dir> out.json` (stats and chi-square/KS vs three generators),
`tools/jam_test.py` (settlement-count test on our saves). Aggregates: `data/polyvision_stats.json`.
Fetch into an empty dir outside the repo; run with `python3 -I`.

## Main finding: village count is a packing jam, not a share of slots (ledger C9-JAM)
- Real: 3-8 villages per map (mean 7.16; 8.16 settlements incl. capital, 0.907 of the 9 slots). Our C9 rule (0.668 x 9) says 6.0.
- Random sequential packing, no fitted parameter: place settlements on interior tiles (not on the edge, x,y in 1..9), Chebyshev >= 3 from every
  settlement, in random order, until no spot is left, with the real capital kept: mean 8.167 vs 8.160; distribution
  4/5/6/7/8/9 = .001/.006/.033/.151/.404/.405 vs .001/.005/.032/.154/.414/.395.
- Out of sample on our 37 turn-0 saves (all six map types, real land masks): mean |actual - jam| 1.13 settlements vs 1.81 for the fitted
  C9 share model (`tools/jam_test.py`). So the "share" is an effect of land shape and size, not a rule: 0.89 at 11x11, 0.65 at 30x30.
- In `sim/wiki_mapgen.py` jam is not better than share for 14+ maps (the generator's land layout is more compact than the real one:
  sum |gen - real| over 15 rows 35.7 vs 16.8; Continents/Pangea overshoot by 8-12). So the default stays "share", jam only for measured Drylands <= 12
  (`village_fill`). `check.sh` output identical before and after.

## Rules: confirmed / contradicted / untestable (all "v122, Bardur Drylands 11x11 only")
- SPACING (>= 3 Chebyshev, never on the edge): confirmed, min nearest-settlement distance 3 in 42k settlements, 0 on the edge.
- RES-AREA (no resource beyond distance 2): confirmed, 0 resources on 37.4k land tiles at distance >= 3 from any settlement.
- RUINS-900: size 11 -> 4 ruins, 5267/5267 maps (table row 121 from PolyEnv was L1; now measured).
- RUIN-PLACE: confirmed on 21,068 ruins: nearest village exactly 2 for 84.5% and never 1; >= 3 from the capital; >= 3 from other ruins;
  edges allowed (59.8% of ruins sit on the edge ring, 33% of tiles do; follows from the crowded interior). Hidden resource under ruin: not testable (CSV drops it).
- C10 (Bardur capital guarantee = animal): >= 2 animals in the capital's ring in 5267/5267 maps, exactly 2 in 86.7%, mean 2.17.
- C23b (ring resources): Bardur ring mean 5.10 (n=5267) vs 5.57 (n=21 saves, z about 1.7), the all-tribe 5.75 is higher; a Bardur-only value of about 5.1 fits better.
- C23 / TERRAIN-MEASURED (Bardur): terrain 0.532/0.317/0.152 field/forest/mountain (rings excluded) vs saves 0.511/0.333/0.156 (|z| < 1);
  inner P(animal|forest) .504, P(fruit|field) .486, P(metal|mountain) .805; outer .167/.155/.267. Saves: .531/.450/.943 inner (metal z -2.1, n=35), .149/.197/.325 outer: all |z| < 1.3 except inner metal.
  Outer metal .267 is above the wiki's .214 and so are inner fruit (.486 vs .375) and outer fruit (.155 vs .125): wiki baseline is low for Bardur.
- C21 (5x5 reveal), handicaps, units, tech: not testable (initial map only).
- Not testable: other map types and sizes, 2+ players (all maps have one player, so no symmetry or player-number check; capital sector rules untested), water, crop/fish/whale, lighthouse.
- Capital position (1 player): x and y roughly bell-shaped around the centre (x=2..8: 4.3/12.2/20.8/25.8/19.8/12.2/4.9 %), not uniform; the generator draws uniform (chi-square rejects; effect: cap-to-village distances 4.51 vs 4.12). Not known whether this is a 1-player effect.

## Generator comparison (5,000 maps each; effect size matters, chi2/df is huge at n ~ 1e5)
| stat (mean) | real | Polyfish `genmaps` | wiki_mapgen measured | wiki_mapgen wiki |
|---|---|---|---|---|
| villages / map | 7.16 | 2.45 | 7.06 | 5.94 |
| ruins / map | 4.00 | 3.73 (2-4) | 4.00 | 4.00 |
| nearest other settlement | 3.08 | 3.10 | 3.08 (chi2/df .2) | 3.14 |
| village distance from capital | 4.12 | 3.90 | 4.51 | 4.51 |
| ruin to nearest village | 2.19 | 3.06 | 2.21 | 2.46 |
| capital ring-1 resources | 5.10 | 4.59 | 4.99 | 5.26 |
| capital ring-1 animals | 2.17 | 4.10 | 2.00 | 2.21 |
| capital ring-2 resources | 5.43 | 5.03 | 5.18 | 4.68 |
| terrain field/forest/mountain (d1) | .52/.32/.16 | 0/.56/.23 | .50/.33/.15 | .48/.38/.14 |
| P(animal/fruit/metal) d1 | .50/.49/.81 | .72/-/.30 | .52/.47/.87 | .50/.56/.78 |
| P(animal/fruit/metal) d2 | .17/.15/.27 | .30/-/.08 | .15/.20/.28 | .17/.20/.23 |
| forest same-type neighbours (of 8) | 2.06 | 4.33 | 2.01 | 2.40 |
- **Polyfish `genmaps` (11x11, Bardur, Drylands) is not usable as a Drylands generator:** about 40% ocean and 10% shallow water (the real maps are all land),
  no Fields except under settlements, forests 55%, wildly clustered; ruins 2-4 (placement can fail); animals in the ring 4.1. Upstream's own diagnostic test
  (`report_drylands_seat_imbalance`) already says Tiny/Drylands strands seat 2 on an island. Same pattern at 14, 16 and 30 (about 45% ocean). Cause not traced
  (the code has land ratio 0.95 for Drylands but the output is half water); the forward model loads real saves, so nothing in the check suite depends on it. Not changed.
- `wiki_mapgen.py` measured mode (after the jam change for Tiny Drylands) matches in everything but capital position (uniform vs bell), ring-1 animals (exactly 2 vs real mean 2.17: real has random extra animals), and slightly high outer fruit (.195 vs .155) and inner metal (.87 vs .805).
- Possible tuning, not done (Bardur n is small in the saves; PolyVision cells are v122 and one tribe): outer fruit 0.155, inner metal 0.805.

## For the fog belief sampler (tools/pf_belief.py, `belief.rs`; village counts biased low, bias -11 and -19)
Draw hidden settlements by random sequential packing (hidden interior land, Chebyshev >= 3 from every known settlement and each other, until no spot is left),
instead of a gamma-prior rate. All spots are taken at turn 0, so a hidden spot is a village or an enemy city, never empty (only destroyed/razed settlements free one);
subtract the hidden enemy cities the sampler already places. Expected count on hidden land is about 0.65-0.9 per (n//3)^2 slot-equivalent, depending on the land shape. Not yet implemented or scored;
test with the games' ground truth (`pffog eval`). Ruins overcount (+0.8/+7): real rule is a fixed count by size (4/5/7/9/11/23 for 11/14/16/18/20/30) minus those already used; a per-size constant is better than a rate by turn.

## Limits
One tribe, one map type, one size, one player, v122 (ours are v123), Creative-mode games (are bot/starting settings the same? unknown); the CSV drops village/capital terrain, resources under ruins, lighthouses.
The harvester's maps are not independent draws of one seed stream: 5,517 distinct maps were checked for duplicates by them only.
