# what-if (Phase 2, capability 1: "know possible moves and outcomes")

_Owner: what-if session · 27 Oct 2026 · state: done, first version (validation numbers below)_

Jason's first interface is advisor mode: he exports a save on the iPhone, pastes it into the cloud session, and gets the
situation, every legal move with the exact outcome the forward model predicts, a shortlist, and the worst-case reply.

## How Jason uses it (iPhone, cloud session)

1. In the game, export the save as text (the same export as for the data games: first line = device path, then the base64 block).
2. Paste the whole text into the chat and say "what-if" (optionally "for player N" or "show everything").
3. The session saves the paste to a file and runs (one command, 1-2 s; the first time it builds the engine, about a minute):
   ```sh
   cat > /tmp/export.txt   # the pasted text
   python3 -I tools/whatif.py /tmp/export.txt            # situation + shortlist (player = the human of the save)
   python3 -I tools/whatif.py /tmp/export.txt --all      # + every legal move, grouped
   python3 -I tools/whatif.py /tmp/export.txt --player 3 # advise another player (bots too)
   python3 -I tools/whatif.py - < /tmp/export.txt        # same, reading stdin
   ```
   Also accepted: a raw `.state` file or a decoded `saves/<id>_tN.json`. Options: `--top N` (shortlist length, default 5),
   `--no-lookahead` (skip the worst-case replies, faster), `--json` (the raw data).
4. The session answers from that output: Jason asks follow-ups ("what if I train a Rider instead?") and the session can look the move up with `--all`.
   For a custom question about a sequence of moves use `tools/pf_api.py` (Sim.play / undo / push / pop on the same save).

If the pasted text is cut off, the script says so ("could not read this as a Polytopia save export...").
The default player is the human (non-bot) player of the save: the save does not say whose turn it is, and Jason exports during his own turn.

## What it prints

1. **Your situation** (only what that player can see, `fog::player_view`): stars and income, techs and what can be researched (with cost),
   cities (level, growth, income, capital/besieged/not connected), units (HP, can act or already acted), visible enemies and cities,
   what is hidden (explored share, tribes met; enemy stars/techs/score and units on unexplored tiles are never shown),
   and the danger now (which of your units a visible enemy could hit, worst case).
2. **Shortlist**: best attacks (kill first, then damage dealt against damage taken, in unit-cost terms; each with exact damage dealt,
   damage taken back, kill or not, whether the attacker moves in, and the worst-case reply afterwards); cheapest threats (moves that put an
   enemy in attack reach this turn, safest first); moves that lose a unit or leave one exposed; then the economy (trains, builds, research with
   what it unlocks, harvests, ruins).
3. **`--all`**: every legal move by group (attacks, moves, trains, upgrades, builds, research, captures, harvests, abilities, diplomacy,
   recover/disband, city rewards), one line each with the state change, stars before/after and what it threatens.

Tags on a line: `[exact]` (combat has no dice), `RANDOM` (a table of measured chances; today only Examine Ruins, from
`data/distributions.json`), `target tile is in the fog` (the result may differ once you see the tile), and
`depends on an unverified rule: <ledger id>` for any move kind that touches a rule below L1 (`data/pf_rule_levels.json`, written by
`tools/pf_rule_levels.py`; at this commit no move kind does, so the tag is checked only by a test with a fake entry).

Coordinates are `(x,y)` of the save's grid, counted from 0: x = column, y = row. **Which screen corner is (0,0) in the game is not known**,
so every place also names its nearest city, and cities whose name decodes to symbols are called "your city 1/2" and "<tribe> city 1". Open question for Jason:
point at your capital on the screen and tell me its (x,y) from the report (for example whether it sits left/right/top/bottom of the map)
and the wording can be fixed once.

## How it works (so the numbers can be trusted)

`sim/pfcore/src/whatif.rs` (bin `whatif`, JSON out) + `tools/whatif.py` (text). Adds no rules.
- Moves: `Game::legal_moves` on the **player's view** (`fog::player_view`: the true state minus everything the player has not explored).
- Outcome of a move: play it on a clone with `Game::play_move` (the replay's own path) and diff the two states: unit HP/kills/moves/new units,
  cities, structures, resources, techs, relations, stars, territory, newly explored tiles. So "exact" means exactly what the engine does.
- Random: a ruin is played once per possible reward with the table's chances (`Dice::ruin_weights`); a free tech is "one of N" (the engine's pick is a hash).
- Reply (worst case): for every visible enemy tribe, flip the mover to that tribe with fresh units, take its Attack moves on my units, and
  each enemy unit's Step then Attack; each attack played exactly. Per target: sum of the best hit of each enemy unit (a unit's damage does not
  depend on how hurt its target is, so the sum is a correct kill test), single-attack kills, and enemies that can walk into an empty city.
  Computed for the attacks, the steps that threaten something or can be reached, and trains/builds/captures (top 40 candidates).
  It is the worst case over what is visible, not a prediction of the bot's choice (bot policy v2 exists in `botpolicy2.rs`; using it for a "likely reply" is the next step).
- Hidden-information care: peace offers and embassies aim at the other tribe's capital, which the view hides. They are generated on the true state
  for tribes the player has met and shown with the tribe only (no tile).

## Validation (`python3 -I tools/whatif_validate.py [--fails]`, also in `check.sh`, informational)

For every logged legal move in all real saves (replayed by `pfreplay` with `PF_WHATIF=1`, `src/whatif.rs validate_move`):
the tool's prediction made from the mover's own fog view is compared with the engine's result on the true state, and for attacks with the
next real save. Numbers after games 7 and 8 were released (27 Oct):

| check | tuned games | held-out |
|---|---|---|
| logged moves / in the tool's move list | 17735 / 17734 | 354 / 354 |
| predicted outcome = engine result (view vs truth) | **17694 / 17734 (99.8%)** | 352 / 354 |
| of those, all tiles visible | 17586 / 17613 (99.8%) | 347 / 348 |
| of those, move into the fog / Explorer reward | 108 / 121 | 5 / 6 |
| Attacks: prediction = engine result | 1442 / 1442 at the first run (100%) | 16 / 16 |
| Attack kills predicted -> unit gone in the next real save | 769 / 770 | 5 / 5 |
| Attacker deaths predicted -> gone in the next save | 264 / 264 | 2 / 2 |
| Survivors nobody touched later: predicted HP = HP in the save | 1790 / 1799 | 17 / 17 |

(Survivor check: a unit counts only if the replay still holds the HP right after the attack at the end of the window, so later hits/heals are not blamed;
another 966 tuned and 8 held-out attacks were changed again later in their window and are not checked.) Per move type (first run, 13206 tuned moves;
EndTurn, Attack, Research, Upgrade, Recover, BreakIce, Promote, Explode: 100%): Move 99.9%, Train 99.9%, Build 99.8%, Capture 99.6%, CityReward 98.0%, ExamineRuins 90.6% (random: result is one of the predicted rewards).
Run it for the current table.

What the misses are (all listed as limits, none touches combat):
- **Fog effects on city growth** (about 25 of 17.7k): a Train, Build, Move or CityReward adds +1 city growth in the true state that the view cannot see (road/port
  connections through unexplored tiles; the Explorer reward reveals tiles). Moves into unexplored tiles and the Explorer reward carry the "fog" tag.
- **Ruin "Lost City"**: about 8 in 100 examined ruins in our saves turn into a level-3 city (a `city_new` event); `data/distributions.json` has no such outcome, so the table
  does not sum to the real thing (the report says so under the table).
- **Game 64795ee3 (new in 7/8)**: 4 attackers show more HP in the save than predicted (3 vs 4, 15 vs 20, 3 vs 5) and 1 kill is predicted but the unit lives on: engine-side rule
  gaps for the rules sessions to look at (`python3 -I tools/whatif_validate.py --fails | grep '"real": true'`).

## Runs on real saves (end to end, from the iPhone export format)

`af181c8f` t14 (Bardur, Jason, export text with a device-path line): 0.15 s. `9906f7da` t20 (Cymanti, 14 visible enemies): 0.95 s. `b2448ead` t4 (Elyrion): shown below.
Heaviest case seen: 16 tribes, player 4 of af181c8f t14 with 69 moves: 0.4 s with replies.

### Example 1: b2448ead t4 (an attack and a train), the first two sections (the Build/Research/Harvest lists after Train are cut)
```
WHAT-IF · Elyrion (player 1) · turn 4 · stars 8 (+3 a turn)

== 1. YOUR SITUATION ==
Techs: Basic, Forest Magic, Forestry
Can research now: Riding (6), Organization (6), Fishing (6), Mathematics (10), Archery (8), Climbing (6)
Cities (2):
  your city 1 (4,9): level 1, growth 0/2, +1 stars a turn (not connected to the capital)
  your city 2 (4,12): level 1, growth 0/2, +2 stars a turn (capital)
Units (2):
  Warrior (4,9), HP 10/10, can act - in your city 1
  Polytaur (5,16), HP 6/15, can act - 4 tiles from your city 2
Enemies you can see: 2 units, 1 city/cities
  Cymanti (p5): Warrior (4,16) HP 1/10; Warrior (5,17) HP 10/10
  enemy city Bioaph (5,17) (Cymanti, level 3, capital)
Hidden from you: you have explored 40 of 900 tiles (4%). You have met 1 of the other 15 tribes. Units and cities on tiles you have not explored, and every other tribe's stars, techs and score, are not shown (the advice uses only what you can see).
Danger right now (worst case: each visible enemy attacks once, as far as it can reach):
  your Polytaur at (5,16) (HP 6): 2 enemy units can hit it for up to 9 - COULD BE KILLED

== 2. SHORTLIST ==
Best attacks (a kill first, then damage dealt against damage taken). Combat results are EXACT unless a line says otherwise:
  1. Polytaur (5,16) (HP 6/15) attacks Cymanti Warrior (4,16) (HP 1/10): deals 1 damage → DESTROYS it; takes no damage back; then moves in to (4,16) [exact]
       afterwards, worst case: your Polytaur at (4,16) (HP 6) could be killed: Warrior from (5,17) can reach it, up to 6 damage in total
  2. Polytaur (5,16) (HP 6/15) attacks Cymanti Warrior (5,17) (HP 10/10), inside a city (its defence bonus is counted): deals 4 damage → its HP 10→6; YOUR UNIT DIES in the fight (takes 6 back) [exact]
       afterwards, worst case: nothing new is exposed (worst case over every visible enemy)
Moves that lose a unit (or leave one exposed), 6 found, first 5:
  - Attack Polytaur (5,16)->(4,16)  → Polytaur at (4,16) (HP 6) could be killed afterwards (worst case)
  - Attack Polytaur (5,16)->(5,17)  → the attacking unit dies in the fight itself (exact)
  - Step Polytaur (5,16)->(4,15)  → Polytaur at (4,15) (HP 6) could be killed afterwards (worst case)
  - Step Polytaur (5,16)->(5,15)  → Polytaur at (5,15) (HP 6) could be killed afterwards (worst case)
  - Step Polytaur (5,16)->(6,16)  → Polytaur at (6,16) (HP 6) could be killed afterwards (worst case)

Economy and setup (what you can spend stars on):
  Train (1 option):
    - Train Warrior in your city 2: costs 2 stars (stars 8→6), the new unit has HP 10 and can act next turn
```

### Example 2: 9906f7da t20 (Cymanti, besieged capital), the shortlist
```
== 2. SHORTLIST ==
Best attacks (a kill first, then damage dealt against damage taken). Combat results are EXACT unless a line says otherwise:
  1. Mermaid Dagger (2,24) (HP 2/10) attacks Aquarion Shark (2,25) (HP 4/10): deals 4 damage → DESTROYS it; takes no damage back; then moves in to (2,25) [exact]
       afterwards, worst case: your Mermaid Dagger at (2,25) (HP 2) could be killed: Mermaid Dagger from (3,24), Mermaid Defender from (3,25), Mermaid Dagger from (2,23) can reach it, up to 10 damage in total
  2. Mermaid Dagger (2,24) (HP 2/10) attacks Aquarion Mermaid Dagger (3,24) (HP 2/10), inside a city (its defence bonus is counted): deals 2 damage → DESTROYS it; takes no damage back; then moves in to (3,24) [exact]
       afterwards, worst case: your Mermaid Dagger at (3,24) (HP 2) could be killed: Mermaid Dagger from (2,23), Shark from (2,25), Mermaid Defender from (3,25) can reach it, up to 8 damage in total
  3. Mermaid Dagger (2,24) (HP 2/10) attacks Aquarion Mermaid Defender (3,25) (HP 15/15): deals 2 damage → its HP 15→13; takes no damage back [exact]
       afterwards, worst case: nothing new is exposed (worst case over every visible enemy); 2 of your units were already at risk before
  4. Mermaid Dagger (2,24) (HP 2/10) attacks Aquarion Mermaid Dagger (2,23) (HP 10/10): deals 1 damage → its HP 10→9; takes no damage back [exact]
       afterwards, worst case: nothing new is exposed (worst case over every visible enemy); 2 of your units were already at risk before
  5. Living Island (1,22) (HP 3/20) attacks Aquarion Mermaid Dagger (2,23) (HP 10/10): deals 3 damage → its HP 10→7; YOUR UNIT DIES in the fight (takes 3 back) [exact]
       afterwards, worst case: nothing new is exposed (worst case over every visible enemy); 1 of your units was already at risk before
Cheapest threats (a move that puts an enemy in reach to attack this turn, safest first):
  1. Raychi (7,16) → (6,18): (6 tiles from Exoly); reveals 2 new tiles; from there it could newly attack: Mermaid Defender (5,17) (HP 15) → 3 damage, takes 10; Mermaid (5,19) (HP 10) → 7 damage, takes 5; 3 enemy units could reach that tile (rough)
       afterwards, worst case: nothing new is exposed (worst case over every visible enemy); 2 of your units were already at risk before
  2. Raychi (2,15) → (4,16): (8 tiles from Exoly); from there it could newly attack: Mermaid Defender (5,17) (HP 15) → 3 damage, takes 10; 2 enemy units could reach that tile (rough)
       afterwards, worst case: nothing new is exposed (worst case over every visible enemy); 2 of your units were already at risk before
  3. Raychi (2,15) → (5,16): (8 tiles from Exoly); from there it could newly attack: Mermaid Defender (5,17) (HP 15) → 3 damage, takes 10; 2 enemy units could reach that tile (rough)
       afterwards, worst case: nothing new is exposed (worst case over every visible enemy); 2 of your units were already at risk before
  4. Raychi (2,15) → (4,17): (7 tiles from Exoly); from there it could newly attack: Mermaid Defender (5,17) (HP 15) → 3 damage, takes 10; 3 enemy units could reach that tile (rough)
       afterwards, worst case: nothing new is exposed (worst case over every visible enemy); 2 of your units were already at risk before
  5. Moth (4,15) → (4,16): (8 tiles from Exoly); from there it could newly attack: Mermaid Defender (5,17) (HP 15) → 1 damage; 2 enemy units could reach that tile (rough)
       afterwards, worst case: nothing new is exposed (worst case over every visible enemy); 2 of your units were already at risk before
Moves that lose a unit (or leave one exposed), 22 found, first 5:
  - Step Raychi (2,15)->(2,18)  → Raychi at (2,18) (HP 10) could be killed afterwards (worst case)
  - Step Raychi (2,15)->(3,18)  → Raychi at (3,18) (HP 10) could be killed afterwards (worst case)
  - Step Raychi (2,15)->(4,18)  → Raychi at (4,18) (HP 10) could be killed afterwards (worst case)
  - Attack Living Island (1,22)->(2,23)  → the attacking unit dies in the fight itself (exact)
  - Step Living Island (1,22)->(3,20)  → Living Island at (3,20) (HP 3) could be killed afterwards (worst case)

```

## Rule gaps and quirks found (not fixed here)

1. `data/distributions.json` ruin_reward: no "city" outcome (Lost City), see above (sim-dist owner).
2. The move generator lists some moves twice with the same key (Harvest on one tile); the tool drops the duplicates.
3. Diplomacy generation needs the other tribe's capital to be on an explored tile (`generate_diplomacy_moves` via `peace_offer_target` / `get_capital_city`); in the player's view that hides legal peace offers and embassies. The tool adds them from the true state for met tribes. A human can do these without having seen the capital (unconfirmed in the game; logged OfferPeace/Embassy moves of the bots prove only that they are legal for the bot).
4. The three "fog effects" above and the game 64795ee3 attack HP misses.
5. The screen orientation of (x,y) (see above).
6. Worst-case replies cover Attack and Step+Attack only: no enemy abilities (Explode, Convert, Freeze) and no multi-turn plans.

## Files
`sim/pfcore/src/whatif.rs`, `src/bin/whatif.rs`, `src/bin/pfreplay.rs` (PF_WHATIF hook), `tools/whatif.py`, `tools/whatif_validate.py`, `scripts/check.sh` (one informational block), 2 cargo tests (`whatif::tests`).
