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

Coordinates are `(x,y)` of the save's grid, counted from 0: x = column, y = row. **(0,0) is the top-left corner of the screen (Jason, 28 Oct): x counts columns from the left, y rows from the top.**
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


---

# Part 2 (what-if-2, 28 Oct 2026): likely replies, scenario comparison, hypotheticals

_Owner: what-if-2 session · state: done (first version). Code: `sim/pfcore/src/scenario.rs`, bin `scen`, `tools/scenario.py`, `tools/scenario_validate.py`, `PF_REPLY` hook in `pfreplay.rs`; `tools/whatif.py` got the "likely reply" lines._

## How Jason uses it (iPhone export -> cloud session)

1. In the game, export the save as text (device path line + base64), paste it into the chat and say what you want.
2. The session saves the paste to a file (`cat > /tmp/export.txt`) and runs, e.g.:
   ```sh
   python3 -I tools/whatif.py /tmp/export.txt                       # situation + shortlist, now with a "likely reply" line per best attack / threat
   python3 -I tools/scenario.py /tmp/export.txt --auto               # it builds 5 options itself and ranks them
   python3 -I tools/scenario.py /tmp/export.txt --moves "Attack Polytaur (5,16)->(4,16)" "Summon Warrior (4,12); Step Warrior (4,9)->(3,8)" "nothing" --h 2 --k 30
   python3 -I tools/scenario.py /tmp/export.txt --moves "A" "B" --hypo "enemy unit at 4,16 has 5 more HP" --hypo "peace with Cymanti"
   ```
   Moves are written like the lines of `whatif.py --all` (the engine's own labels); one unique part of a label is enough. `a; b` = two moves in a row. `nothing` = end the turn.
   `--h` 1-3 rounds ahead (default 1), `--k` sampled futures (default 20; 20 takes 0.4 s early, 3-7 s late with 16 tribes), `--player`, `--no-win`, `--json`.
3. Jason can ask follow-ups in plain words ("what if I had 5 more stars", "what if the Warrior had 5 more HP") and the session turns them into `--hypo`.

Supported `--hypo` edits (applied to the loaded true state, the report says so in a "HYPOTHETICAL position" line): unit HP of a visible unit ("enemy unit at 4,16 has 5 more HP", "less HP", "has 7 HP", "my unit at ...", capped at 1..max),
stars ("I have 5 more stars", "I have 5 fewer stars", "I have 12 stars", "Cymanti has 3 more stars"), "peace with <tribe | player N>", "war with ...". Everything else (new units or cities, techs, terrain, a relation between two other tribes) is refused with that list.
The tile of a unit edit must be explored by the player.

## What is exact and what is an estimate

- Exact: the player's own moves and what they do now (engine `play_move`; a ruin is a table), the worst-case danger after them (`[exact]`).
- ESTIMATE (every such line says so): K enemy turns drawn from bot policy v3 (`data/bot_policy_v3.json`) for all other tribes, then H rounds; from round 2 the model plays the player's side too. Shown: chance each unit is attacked / killed, expected losses, most likely attack,
  per tribe units / cities / stars / score after H rounds (mean and 10th-90th percentile of the samples), and the chance to LEAD the in-game score (half playouts, half `data/winpct_static.json`, interval from the playouts only; calibration in win-pct.md). The saved score is not comparable with the later ones, so only options are compared.
- Agreement quoted in the output (bot-model-3.md): same move as the real bot 46% (random 29%), attack target 89% given the attacker, one-round counts of attacks/kills within 10-20% of real, 3 rounds about 20% low. `--auto` ranks by mean score after H rounds; with K=20 differences are often inside the noise and the verdict says "no clear difference".

## Validation of the likely reply (`python3 -I tools/scenario_validate.py --k 20`, 1.5 min)

At every real end of the human's turn in the saves the reply is sampled from the position, then the real bot actions that follow are read (replay, `PF_REPLY`). 147 windows, 310 human units; tuned games (the policy was FITTED on most of them: in-sample):

| check | result |
|---|---|
| really attacked units (56) given chance >=50% / >=20% / >0 | 46% / 89% / 95% |
| really killed units (16) given chance >=50% / >=20% / >0 | 62% / 88% / 94% |
| Brier, attacked (model vs always the base rate) | 0.087 vs 0.148 |
| Brier, killed | 0.023 vs 0.049 |
| calibration, attacked: predicted bin -> real rate | 0%->2%, 12%->15%, 35%->48%, 65%->65%, 84%->79% |
| real units lost in the central 80% of the samples | 145/147 windows |
| real attacks (tribe, tile) with predicted chance >0 / >=10% / >=30% | 55/58, 54/58, 39/58 |
| predicted most likely attack really happened / one of the top 3 | 33/69 (48%) / 41/69 (59%) windows |

Out-of-sample parts: game 7 (710ddb20) turns 12-19, which v3 never saw (8 windows, 68 units, 12 attacked): attacked units with chance >=20%: 9/12, >0: 10/12; Brier 0.109 vs 0.145 base; real attacks with chance >0: 11/13, >=30%: 9/13.
The held-out game ed6cb932 has only 4 windows with a human turn end and no attack on the human: nothing to score (4/4 windows inside the central 80%). So the honest reading: well calibrated and better than the base rate in-sample, the same direction out-of-sample but on 12 attacked units only. More human games with attacks would settle it.
Not covered by the reply sampler: abilities (Explode, Freeze), multi-turn plans of the bots, and any bot knowledge of what the player cannot see (the model plays on the true map; the real bots play on their own fog).

## Three end-to-end runs (trimmed: first lines of each section; exports in the iPhone format work the same, see Part 1)

### Run 1, early game: b2448ead t4 (Elyrion), `--moves "Attack Polytaur (5,16)->(4,16)" "Summon Warrior (4,12)" "nothing" --k 30`
```
[A] Attack Polytaur (5,16)->(4,16)
   exactly: Attack Polytaur (5,16)->(4,16) → your Polytaur moves (5,16)→(4,16); enemy Cymanti Warrior at (4,16) is destroyed [exact]
   you then hold 8 stars; units: Warrior (4,9) HP 10, Polytaur (4,16) HP 6
   danger, worst case [exact, what visible enemies could do to you if they all go for it]: Polytaur at (4,16) (HP 6) could be killed by 1 unit (up to 6 damage)
   ESTIMATE - 30 sampled enemy turns:
     chance each unit is attacked next turn: Polytaur (4,16) 67% (killed 67%)
     expected losses in the enemy reply: 0.67 (0-1) units (1.3 (0-2) unit-cost), chance of losing at least one 67%
     most likely attack: enemy Cymanti Warrior hits your Polytaur at (4,16) (67% of samples)

== COMPARISON (H=1 round, K=30; 'now' is exact, every other column is an ESTIMATE) ==
     now (exact)       lose unit  units lost  H=1 units  cities  stars  score  near enemy units  lead %
  A  1 kill, 8 stars   67%        0.67        1.3        2.0     11.0   1088   3.0→4.1           1%    
  B  no kill, 6 stars  27%        0.27        2.7        2.0     9.0    1087   4.0→4.5           1%    
  C  no kill, 8 stars  27%        0.27        1.7        2.0     11.0   1077   4.0→4.5           1%    
lead % = chance to lead the in-game score after 1 round (half sampled playouts, half the static model fitted on real games; see .scratchpad/investigations/win-pct.md for its calibration). It is NOT the chance to win the game.
(0.6 s; seed 1)
```
Reading: the attack kills the 1-HP Warrior now (exact) but the Polytaur (HP 6) is then exposed: the model has it attacked and killed in about two thirds of the samples; doing nothing risks it less (27%), because the enemy has two units that can reach it either way.

### Run 2, late game, 16 tribes, with a hypothetical: af181c8f t14 (Bardur), `--auto --top 3 --h 2 --hypo "I have 10 more stars"` (2.4 s)
```
HYPOTHETICAL position (edited, not the real game): you have 21 stars instead of 11
[A] do nothing (end the turn)
   exactly: nothing changes now; the turn ends with the units where they are.
   you then hold 21 stars; units: Rider (23,7) HP 6, Defender (23,8) HP 15
   danger, worst case [exact]: no visible enemy can kill any of your units next turn.
   ESTIMATE - 20 sampled enemy turns:
     chance each unit is attacked next turn: Defender (23,8) 20% (killed 0%); Rider (23,7) 15% (killed 5%)
     your city at (23,8): unit in it attacked 20%, city captured 0%
     expected losses in the enemy reply: 0.05 (0-0) units (0.1 (0-0) unit-cost), chance of losing at least one 5%
     most likely attack: enemy Yadakk Raft hits your Rider at (23,7) (10% of samples); next: Cymanti Raychi → Defender at (23,8) (5%); Yadakk Bomber → Rider at (23,7) (5%)
     you after 2 rounds (mean, 10th-90th percentile of the samples): units 2.2 (1.9-3) (now 2), cities 1 (1-1) (now 1), stars 10.8 (5-18.1) (now 21), score 2529 (2193-2900) (the saved score is not comparable with the later ones, s
     Yadakk (p13, near you) after 2: units 15.8 (14.9-17) (now 15), cities 6.2 (5-7) (now 7), score 4754 (4530-4992)
     chance you lead the in-game score after 2 rounds: 0% (playouts 0%, 95% interval 0%-16%, static model 0%) [ESTIMATE; not the chance to win the game]
   verdict: 5% chance to lose a unit next turn

[B] Research Fishing
== COMPARISON (H=2 rounds, K=20; 'now' is exact, every other column is an ESTIMATE) ==
     now (exact)        lose unit  units lost  H=2 units  cities  stars  score  near enemy units  lead %
  A  no kill, 21 stars  5%         0.05        2.2        1.0     10.8   2529   15.0→15.8         0%    
  B  no kill, 16 stars  5%         0.05        2.2        1.0     10.5   2492   15.0→15.8         0%    
lead % = chance to lead the in-game score after 2 rounds (half sampled playouts, half the static model fitted on real games; see .scratchpad/investigations/win-pct.md for its calibration). It is NOT the chance to win the game.
(2.4 s; seed 1)
```

### Run 3, held-out game: ed6cb932 t4 (Aquarion, Crazy), `--auto --top 3 --h 2` (1.6 s)
```

[C] Summon Mermaid (19,22)
   exactly: Summon Mermaid (19,22) → a new Mermaid appears at (19,22) [exact]
   you then hold 6 stars; units: Mermaid (15,21) HP 10, Mermaid (19,22) HP 10
   danger, worst case [exact]: no visible enemy can kill any of your units next turn.
   ESTIMATE - 20 sampled enemy turns:
     none of your units was attacked in any sample.
     expected losses in the enemy reply: 0 (0-0) units (-0 (0-0) unit-cost), chance of losing at least one 0%
     you after 2 rounds (mean, 10th-90th percentile of the samples): units 2.8 (2-3) (now 2), cities 1 (1-1) (now 1), stars 5.5 (4-8) (now 6), score 860 (854-870) (now 640)

== COMPARISON (H=2 rounds, K=20; 'now' is exact, every other column is an ESTIMATE) ==
     now (exact)       lose unit  units lost  H=2 units  cities  stars  score  near enemy units  lead %
  C  no kill, 6 stars  0%         0.00        2.8        1.0     5.5    860    -                 0%    
  B  no kill, 6 stars  0%         0.00        2.7        1.0     5.5    860    -                 0%    
  D  no kill, 3 stars  0%         0.00        1.6        1.0     5.6    857    -                 0%    
  A  no kill, 8 stars  0%         0.00        1.9        1.0     6.6    852    -                 0%    
lead % = chance to lead the in-game score after 2 rounds (half sampled playouts, half the static model fitted on real games; see .scratchpad/investigations/win-pct.md for its calibration). It is NOT the chance to win the game.
(1.6 s; seed 1)
```
(Only a few real options exist this early; the differences between them are inside the noise, which the tool prints.)

## Open items
1. (0,0) corner: ANSWERED by Jason 28 Oct: top left. Both tools now say so; places still also name the nearest city.
2. The win-% is "lead the in-game score after H rounds", with the weak calibration of win-pct.md; it is near 0% for everyone when the player is far behind, so it does not rank options there.
3. Later rounds use one policy for everybody including the player: it is a drift check, not a plan. `--auto` only builds single moves (plus best attack + best train); sequences of 3+ moves must be written by hand.
4. Validation needs more human turns with enemy contact (ask Jason for games where he is at war).
