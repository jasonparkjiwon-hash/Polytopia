# Status

_Last updated 2026-10-26 (Jason's games 1-5 ingested, scored held-out, released)._

## Now

- **Phase 1 (data and verification) is done.** All six exit gates passed on
  2026-10-23 (`docs/polytopia_ai_phase_1_spec.md`).
- **Polish program is done** (four parallel sessions, 23 Oct):
  - **Units: 4728/4728, every unit in every save exact** (was 4709/4753).
  - **Stars: 802/819 player-turns exact** (was 762). All 17 misses left are
    explained; most need saves without gaps or an answer from Jason
    (`investigations/star-tail.md`).
  - Every engine rule has a ledger id (`tools/rule_levels.py`, run by `check.sh`):
    147 rules, 1 still unverified (embassy price step; Market and Clathrus income
    passed on games 1-5, 26 Oct).
- **Jason's games 1-5 (26 Oct, Hard, every turn):** held-out score before tuning units
  1724/1733, stars 512/523; released for tuning. With them `tools/miss.py` is units
  6452/6461, stars 1314/1342. Misses classified, five small rule fixes listed in
  `investigations/games-1-5.md` (unit 47 Mermaid Archer, Waterways tier, Sanctuary price,
  Clear Forest +1, siege case).
- **Jason's game 6 (26 Oct, Cymanti, every turn t2-t20):** held-out units 917/984, stars 173/198;
  released. Embassies x5, peace offers, Aquarion units 49-52, Living Island; see `investigations/game-6.md`.
  With games 1-6 `tools/miss.py` is units 7369/7445, stars 1487/1540 before rule fixes; after ref-fix (27 Oct, 14 kept fixes,
  table in `investigations/games-1-5.md`): **units 7389/7392, stars 1511/1540**; holdout ed6cb932 still 187/187, 64/64.
- **Phase 3 prep is running** (backlog item 0): Polyfish becomes the forward
  model (`docs/simulator_choice.md`).
- **Score baseline:** the expected `check.sh` output is under "Quick start" in
  `README.md`. That's the one copy. Update it there when scores change.
- **Saves:** the raw saves are committed in `saves_raw/`; `sh scripts/restore_saves.sh`
  rebuilds `saves/` for everyone, so both people's `check.sh` scores match.

## Who's on what

| Person | Working on |
|---|---|
| Jason | — |
| Minjae | — |
| Claude (orchestrator) | Phase 3 prep (backlog item 0): runs the sessions below |
| Claude: pf-loader | Load saves into Polyfish, score it, legality check |
| Claude: pf-port | Port v123 corrections into Polyfish (pf-port-3 handoff 26 Oct: units 6455/6456, stars 1320/1342, legal 99.3%) |
| Claude: sim-dist | First pass done (held-out check, `data/distributions.json`, `data/bot_turns.csv`); see `investigations/sim-dist.md` |
| Claude: fm-accept | Done 27 Oct: forward-model API (`sim/README.md`), `tools/pf_accept.py` (end of check.sh), gaps ranked in `investigations/fm-accept.md` |

## Waiting on Jason

- pf-port-4 (27 Oct): game 6 (9906f7da) t11, an Aquarion bot used Build 7 (normally Fishing) on two Ocean tiles with no fish, and each Ocean tile became shallow Water (n=2). What is this action? Check in an Aquarion game whether some tech (Aquaculture? Waterways?) lets you turn Ocean into Water, and its price.

- ref-fix (27 Oct), four in-game checks:
  1. **Sanctuary "nearby":** build a Sanctuary with a wild animal exactly 2 tiles away (none adjacent); note stars right before
     and after building and over the next 2 turns. Does the far animal pay +1? (SANCTUARY-V123: card price 5 and +1 per animal
     fit game 2 with adjacent animals; radius 1 vs 2 not separated.)
  2. **Mermaid Dagger card** (Aquarion unit 51): HP, attack, defence, skills. The engine uses Polyfish's Dagger stats.
  3. **Infiltration:** when an Aquarion Scuba (or a Cloak) infiltrates a city, how many Daggers appear, and does the unit in the
     city take normal attack damage? (Game 6: 6 damage, 3 Mermaid Daggers; Polyfish says a fixed 2 and up to the city's production.)
  4. **Jelly / Mermaid Defender / Shark prices** (Aquarion p9 game 6 star rows don't fit the card prices 8/8/8; the
     cards' train price for each would settle it).

- pf-port-3 (26 Oct), one in-game check for the Polaris Outpost network (OUTPOST-NETWORK, fits 80/83 save states):
  build two Outposts 5 tiles apart with ice between them, a city next to each. Does the far city get connected
  (+1 population to it and the capital)? Then break the ice between them (or let it melt): does it disconnect?
  Save each turn.

- pf-port (24 Oct), two in-game checks left for the Polyfish forward model:
  1. ~~Mermaid onto ocean~~ answered 26 Oct: innate for Aquarion, no tech (AMPHIBIOUS-WATER, L0).
  2. Aqua Farm (build 49) and Aquarion structure 51: Aquaculture unlocks Aqua Farm and Atoll (5 stars each). Jason 26 Oct: Atoll is like Fungi mycelium (connects cities, buildable anywhere, population grows with the number of cities connected); 51 = Atoll is likely, unconfirmed. Still open: the population formula. Test: build an Atoll linking 2 and then 3 cities, saving each turn. (pf-legal-2 26 Oct, from 18 builds: 51 = Atoll is consistent; Aqua Farm goes on AquaCrop and gives +2 population; Atoll goes on water, ocean or flooded land; both need Aquaculture; AQUARION-STRUCTURES.)
  3. Polaris skating: how far can a Mooni or Battle Sled move from a city (land) onto ice in one turn?
     (09a5bf1e t1: a Mooni went 2 tiles from its city onto ice.)
     pf-legal: the saves show Mooni at most 2 and Battle Sled at most 3, from a city or ice alike (SKATE-MOVE);
     only a Battle Sled 4 tiles over ice would change that.

- pf-legal-2 (26 Oct), Aquarion Jelly (unit 52): which tech unlocks it? Look at the tech tree card for the
  Jelly (or research Navigation alone first and see if the Jelly appears in the city's train list). The
  only bot that trained one held Navigation, Aquaculture, Marine Life, Organization and Strategy. Until
  then Polyfish never offers it.
- pf-legal (24 Oct), one in-game check: move a non-Cymanti land unit (e.g. a Warrior) onto a Cymanti
  algae tile with 2+ moves left. Does it stop there, or can it keep going? (Cymanti units and boats keep
  going, ALGAE-MOVE.)

- Round 3 (items 35-40) all answered 23-24 Oct.

- New saves as he plays, **every turn** (games 1-5 did this). Each new game goes into `data/holdout.json` first and is scored before any tuning. Still wanted: Oceanology research, peace, and a Sanctuary game played on for 10+ turns (games 1-5 gave 1 Sanctuary over 4 turns and 10 more water ruins).
- ~~Waterways save id~~: 48, tier 2 (game 1, AQUARION-WATERWAYS-ID).
- Round 2, items 26–34 on the test sheet
  (`docs/polytopia_open_questions_to_fill_in_while_playing.md`).

## Decided

- **Notebook:** only Jason rebuilds `notebook/polytopia_engine.ipynb` (about
  400 KB, conflicts on nearly every merge otherwise). Minjae's PRs leave it alone.
