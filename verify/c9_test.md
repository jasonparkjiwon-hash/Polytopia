# C9 village count: pre-registered held-out test

Written 2026-10-23, before the held-out saves' settlement counts were looked at.

## Question

How many settlements (capitals plus villages) does a map get, out of its (size // 3)² village slots?

## Models

- **PE** (PolyEnv): every slot is filled. p = 0.999 for every map type, since p = 1 would give a zero likelihood.
- **WK** (wiki, "attempt to assign 60%"): p = 0.60 for every map type.
- **MS** (measured): the per-map-type `settlements_per_slot` in `data/measured_mapgen.json`, built from the first 27 saves: drylands 0.668, lakes 0.646, archipelago 0.603, continents 0.52, pangea 0.48, waterworld 0.24.

## Data

Every turn-0 save in `saves/` that was not one of the 27 used to build the table. A save counts as one of the 27 if its map type, size, land share, water tiles and starfish match a row of the table. Settlement counts are not used for this matching.

## Likelihood

Each save is Binomial(slots, p). The Bayes factor for model A over model B is the product over held-out saves of the binomial likelihood ratios.

## Decision rule

- The model with the highest likelihood is chosen if its Bayes factor against each other model is above 10.
- Otherwise C9 stays open, and the result says which models are still in play.
- A model with no held-out save of a map type can't be tested on that type. The result lists the map types that were covered.

The script is `verify/c9_test.py`.

## Amendment, 23 Oct 2026

This was written after seeing that the new Drylands save (6eccceef) had been dropped. Its settlement count (67) had already been printed while its map type was checked. The amendment only decides which saves count as new; it uses no settlement counts.

The matching rule under Data can mistake a new save for one of the 27. Drylands maps are almost all land, so two of them can share size, land share, water tiles and starfish. Saves that are known to have arrived after the table was built (af181c8f, 09a5bf1e, 6eccceef, d71a6b1d) now always count as held out. Nothing else changes.
