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
| Claude: fm-speed-2 | Done: movegen ~9k/s (was 1.1k), search_move, MOVE/TRAIN/UPGRADE-BASE; see investigations/fm-speed.md |
| Claude: pf-loader | Load saves into Polyfish, score it, legality check |
| Claude: pf-port | Port v123 corrections into Polyfish (pf-port-3 handoff 26 Oct: units 6455/6456, stars 1320/1342, legal 99.3%) |
| Claude: sim-dist | First pass done (held-out check, `data/distributions.json`, `data/bot_turns.csv`); see `investigations/sim-dist.md` |
| Claude: bot-policy | Handoff 27 Oct: one-softmax bot policy over all legal moves (`botpolicy.rs`, `data/bot_policy.json`, bin `botplay`, `tools/bot_policy.py`), all-moves top-1 held-out 0.53 (random 0.20), given the actor 0.69 (0.34); 2-round playouts match stars/cities/kills on held-out, units low; see `investigations/bot-policy.md` (and bot-policy-2 below, built in parallel) |
| Claude: bot-policy-2 | Done 27 Oct: bot move policy v1/v2 (`sim/pfcore/src/botpolicy.rs`, `data/bot_policy_v2.json`), playout bin `pfbot`, distribution check; held-out next-group 0.78 (random 0.36), move 0.62 (0.49); see `investigations/bot-policy-2.md` |
| Claude: fog-inference | Handoff 27 Oct: player view exact vs saves (1876 pairs), belief sampler v1 (`belief.rs`, `pffog`, `tools/pf_belief.py`); capitals good, terrain only near explored, villages biased low; see `investigations/fog-inference.md` |
| Claude: fm-accept | Done 27 Oct: forward-model API (`sim/README.md`), `tools/pf_accept.py` (end of check.sh), gaps ranked in `investigations/fm-accept.md` |

## Waiting on Jason

- **Jason (27 Oct): no more data collection for a while; work with games 7 and 8 (Google Docs 'Polytopia Game 7' id 18IWmxuWo7rbqXDuEwrrqhUV1x84tY5TwURr_59GXbYc, 'Polytopia Game 8' id 18VWmQLcOhgb8EmRLG7Jqo-p9Fcy0UW1tEA18mlr-LDg) plus the 12 we have. Resume work at ~8pm Juba (18:00 UTC) when usage resets: ingest 7 and 8 as held-out first, then (his go given 27 Oct) the win-% prototype, the what-if tool, and a better bot model, in that order.** New facts from his screenshots (Sanctuary level 1/8, Insect Egg card) are in the ledger.

- **Jason will send full-length bot games, every turn, on 28 Oct.** Then start, in this order, on his go: (1) win-% prototype (Phase 5: playouts from a state with bot-policy v2 opponents); (2) what-if tool (capability 1: moves with exact outcomes from a save); (3) better bot model from the new games. Aquarion Build 7 on ocean answered 27 Oct: it is the Lost City's fish (AQUARION-OCEAN).

- bot-policy-2 (27 Oct), optional, makes the bot model much better: full-length Hard bot games exported **every turn** (turn 1 to the end,
  like game 6), ideally 2-3 games, plus one Crazy game the same way. Right now Attack/Capture/Build rest on 400-1400 decisions and the
  held-out game covers turns 1-5 only. Also useful: one game where you note, for 3-4 bot turns, how many stars the bot held at the end of its
  turn (what stops a bot building).

- ref-fix (27 Oct), four in-game checks:
  1. **Sanctuary "nearby":** build a Sanctuary with a wild animal exactly 2 tiles away (none adjacent); note stars right before
     and after building and over the next 2 turns. Does the far animal pay +1? (SANCTUARY-V123: card price 5 and +1 per animal
     fit game 2 with adjacent animals; radius 1 vs 2 not separated.)
  2. ~~Mermaid Dagger card~~ answered 27 Oct: same as a Dagger but amphibious.
  3. ~~Infiltration~~ answered 27 Oct: Daggers = city level, cap 5, only empty tiles in its borders (INFILTRATE).
  4. Mermaid Defender price: card says 8, game 6 p9 rows fit 3 (4 rows; Jelly and Shark fit 8). Both engines use 3 (MERMAID-DEFENDER-PRICE). Re-check: train one Defender with stars before and after.

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

- ~~pf-legal-2 Jelly tech~~ answered 27 Oct (wiki-research): Navigation (wiki + 2 saves, L1); Polyfish now offers it. Old text: Aquarion Jelly (unit 52): which tech unlocks it? Look at the tech tree card for the
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
