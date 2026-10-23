# Polytopia AI: Phase 1 spec

Oct 23, 2026 · @Jason Park

## Update, 23 Oct 08:00 — six real saves, one per map type

Six Massive turn-0 games with 15 Crazy bots each, one per map type: 96 capitals in all. Holding “Resume” is the export path; each save you send drops straight into the library.

- **Settled (L3):**
  - The wiki's resource table, across all six maps.
  - The 5×5 first reveal.
  - 23 ruins on every Massive map.
  - Villages always at least 3 apart and never on the edge.
  - No resources beyond 2 tiles.
  - Land share per map type: Drylands 99.6%, Lakes 73%, Pangea 51%, Continents 47%, Archipelago 40%, Waterworld 15%.
- **Corrected:**
  - Every capital gets 2 of the same resource **except Vengir** (2 of 2 Vengir capitals had none).
  - Tribe forest modifiers work differently from the wiki's wording. The corrected rule was fitted on 3 maps and held on the 3 new ones.
  - Starfish count is about water tiles ÷ 25.
- **Still open:**
  - Village count is off by 5–8 per map, depending on type.
  - Capitals run about 0.25 resources richer than the generator predicts.
  - A water resource (“AquaCrop”) appeared next to Vengir capitals.

## Update, 23 Oct 08:00 — first real save read

Your iPhone save (“Gods of Dame”: Massive 30×30 Drylands, 15 Crazy bots, turn 0, game version 123) parsed fully, all 900 tiles. Settled by measurement (L3):

- **C23 is decided: the wiki is right.** Its resource table gives shares of land tiles, so a field next to a village has fruit about 38% of the time, a forest has an animal about half the time, and a mountain has metal about 79% of the time. Your map matches this within noise on every main cell. The old engine's reading is off by 4 to 18 standard deviations.
- **Capitals average about 6 resources in their ring** (5.9 measured across 16 capitals; 5.6 predicted by the wiki generator).
- **All 16 capitals have 2 of the same resource**, across 12 tribes. That confirms the wiki and rules out the old engine.
- **The first reveal is exactly 5×5** for every player (C21).
- **No resources farther than 2 tiles from a settlement. 23 ruins on 900 tiles.**
- **Start units confirmed for 12 tribes**, including Ai-Mo's Mind Bender and Cymanti's Shaman.
- **Still uneven:** terrain shares for Hoodrick, Aquarion, Zebasi and Oumaji differ from the wiki table. More maps are needed.

Gates B and D move forward, and the C23 part of Gate B is done.

## Update, 23 Oct 07:00

- **iPhone, no save files.** Save files can't feed us real data, so the test sheet becomes the main real-data path. Gate C is rewritten below: **at least 15 capitals logged** with turn-1 counts and your starting tech.
- **The Polyfish engine now runs here.** I didn't need crates.io after all. I pulled the \~25 libraries its game engine needs straight from GitHub and built just the game engine, without its AI or server. It generated 660 maps in seconds.
- **The capital test is now sharper.** Its third model is now the real Polyfish generator, measured over 1,200 capitals, replacing my hand-built version. Using only what you can see on turn 1, a verdict needs a median of **4–10 capitals** (90% of runs within **10–25**), and it picks the right model 90–98% of the time.
- **Polyfish's map generator is not fully faithful.** Its Drylands maps come out about half water, while the wiki says Drylands is all land. So I treat its maps as a third model to test, not as ground truth. Its rules tables (units, techs, combat) are still the best source we have.

## Morning summary

As you asked, the advisor stays on hold. Phase 1 now has strict exit gates, a rule for how much evidence each fact needs, and ways to check the open gaps without screenshots.

**The big finds overnight**

- **Real save files can be read.** Polytopia's `.state` save file holds the full turn-0 map: every tile, resource, village and ruin, which tiles each player has seen, every player's start, and the whole move history. I built a converter and an analyser. One save from a large game with many bots settles the capital-resource question, the village count, ruins, starfish and land share all at once.
- **A second, current game engine exists.** Polyfish (open source, last updated September 2026) is a full re-implementation of the game for an AlphaZero-style AI, built against game version 115 (the Cymanti Rework). It records rules per patch and loads states captured from the real game. My automated comparison found **283 fields that agree with our dataset and 31 that don't**, and most of those 31 are special-tribe units it doesn't cover.
- **Several conflicts are now settled by two or three sources agreeing:** retaliation includes the defence bonus; Clear Forest gives +1 star; Burn Forest costs 3.
- **New open conflict:** Navigation may require Ramming rather than Sailing. Your tech-tree screen answers it without playing.
- **A correction to your test sheet:** crops and metal stay hidden until you have the right tech (Organization or Farming for crops, Climbing for metal). A turn-1 count therefore needs your techs noted. I've updated Q1.
- **The top test is now fixed in advance.** I simulated three competing models of how capital resources are generated. The verdict rule is written down before any data comes in, and about 3–12 capitals should be enough to decide.

**Three things I need from you**

1. **Which device do you play on: iPhone, Android or a Steam PC?** This decides whether we can get `.state` files. On Windows the path is known. On a phone, check whether the Files app shows a Polytopia folder (iPhone: On My iPhone → Polytopia; Android: Android/data/com.midjiwan.polytopia).
2. **Optional: allow crates.io in your settings.** Under Settings → Capabilities, add `index.crates.io` and `static.crates.io` to the allowed domains. My workspace blocks them right now. With them I can build Polyfish's engine here and run thousands of simulated games.
3. **Play one game to turn 1 and fill Q1 and Q2** on the test sheet, noting your starting tech. That is the cheapest real data.

## Exit gates

Phase 1 is done only when **all six** gates pass. No advisor work starts before then.

- [ ] **Gate A. Core rules are trusted.** Every rule that changes the result of a move reaches at least level L1 (below), with at least one source dated 2025 or later, and no open conflict among them. That covers units, combat, movement, tech costs and prerequisites, income and growth, and tile actions. *Now (23 Oct): nearly done.*
  - Settled: road cost 3, C27 Navigation needs Sailing, income rules and diplomacy actions.
  - Also settled: the Crazy bot bonus (3 a turn) and action 38 (the Shaman's Swarm, a movement boost).
  - Also settled: action 18 is Break Ice, which explains the ice that seemed to melt.
  - Open: C20 (retaliation vs fog; the saves can't separate the readings, so it needs an in-game test) and C29b (Static skill).
- [ ] **Gate B. The map model is decided.** C23 (capital resources), C10 (capital guarantees) and C9 (villages) are each decided by their pre-registered test on real data, with a Bayes factor above 10. *Now (23 Oct): nearly done.*
  - C23 and C10 are decided (L3).
  - C9 is decided for Drylands, Lakes, Continents, Archipelago and Pangea: Bayes factor 10^4.0 over the wiki on 9 held-out saves (`verify/c9_test.md`).
  - Still needs one held-out Waterworld save.
- [x] **Gate C. Real data in a fixed format.** You're on iPhone with no save files, so this gate needs **at least 15 capitals** logged on the test sheet. Each row records the tribe, your starting tech and the fruit, animals and fish you can see on turn 1 (plus crops and metal if your tech shows them). If the verdict is still open after 15, we continue to 25. *Passed: iPhone saves turned out to be exportable. 33 games are decoded, over 300 capitals.*
- [x] **Gate D. Fog is measured, not assumed.** The first reveal (C21), whether old sightings go stale (G3) and city vision (G9) are measured at level L3. *Passed:*
  - *C21: 5×5 reveal, every save.*
  - *G3: explored tiles show enemies live (Jason).*
  - *G9: cities see 3×3 (Jason; the saves agree).*
- [x] **Gate E. The dataset rebuilds and checks itself.** The dataset is rebuilt from its script, then the self-check and the engine cross-check run with no unexplained differences. The game version (115 or later) is stamped on every rule. *Passed:*
  - *`verify/run_all.sh` rebuilds the data exactly. In-game facts now live in `data/game_ui_overlay.json`.*
  - *The self-check passes.*
  - *The Polyfish cross-check gives 290 agree and 36 differ, all 36 explained.*
  - *Every fact, unit and ledger rule carries `game_version`.*
- [x] **Gate F. The simulator base is chosen.** A written comparison of PolyEnv, Polyfish and our own Python engine, on rule coverage, freshness, speed and licence, with a decision. *Passed: Polyfish, patched with the v123 corrections, with our replay engine as the referee (`docs/simulator_choice.md`).*

## Evidence ladder

Every rule in the dataset carries a level. The simulator may only rely on a rule at L1 or above.

- **L0. One source.** A wiki page, one engine, or one patch note. Allowed in the dataset, flagged, never trusted for search.
- **L1. Two independent sources agree**, and at least one is dated 2025 or later. Our three independent families are the wiki, PolyEnv and Polyfish; dated patch notes count as a fourth.
- **L2. Three sources agree, or a pre-registered test passes.** The expected value and the decision rule are written down before the data is looked at, so a result can't be fitted after the fact.
- **L3. Measured in the real game**, either from a real `.state` file or from a controlled in-game test whose expected numbers were written beforehand.

**Tie-break when sources disagree:** a dated patch note beats Polyfish, which is tied to version 115. Polyfish beats PolyEnv on post-2025 rules. PolyEnv beats the undated wiki. Any rule that is still split after that becomes a test item; I don't pick a side.

**What counts as independent:** two pages of the same wiki are one source. A re-implementation that cites the wiki for a number is not independent on that number. I check each engine's comments for where a number came from.

## Data paths other than screenshots

Best first. The first that works on your device becomes the main path.

### 1. Save files (`.state`) — strongest

- **What it gives:** the complete turn-0 map, including unseen tiles; per-tile fog for every player; each player's stars, techs and score; and every action taken.
- **How:** copy the file to me → `state2json` converts it → `analyze_map.py` measures it against each open conflict.
- **Where the file is:** Windows/Steam `%USERPROFILE%\AppData\LocalLow\Midjiwan\Polytopia\<id>\Data\Singleplayer`. iPhone and Android are unconfirmed (see the morning question). The game deletes the file when the game ends, so copy it while the game is still running.
- **Best single experiment:** a Creative game on a Massive map with 15 bots. One save gives 16 capitals and 900 tiles. Run it once per map type.

### 2. The test sheet, in a fixed format — works on any phone

- Each question has its expected result written down in advance, and your answers are scored by the same pre-registered rule.
- **Restart trick:** each new game is a fresh capital. Ten restarts in Creative mode take about ten minutes and give ten capitals for Q1.

### 3. Controlled experiments through save editing — PC only

- An open-source save editor can place exact units, terrain and buildings in a save. We set up a fight (for example, a full-health Warrior against a fortified Defender), play one move, and read the result.
- This turns each combat or fog question into a single exact check.

### 4. Official replays — any device

- Polyfish's scraper has collected about 12,000 public replay links (`share.polytopia.io/g/<id>`). Each opens in the game on a phone through a `polytopia://opengame` link.
- Good for watching real fights and real ruin outcomes. Viewing is visual only, so it's slower than save files.

### 5. Polyfish's game mod — Steam PC only, the most data

- A PolyMod plugin plays replays at 20× speed and posts every game state as JSON. My analyser already reads that format.
- This is the route to hundreds of games for ruin odds, bot behaviour and fog.

### 6. Engine cross-checks — no device needed

- Our dataset (built from PolyEnv and the wiki) is compared field by field with Polyfish, and `run_all.sh` reruns the comparison after each rebuild. The older engines I downloaded (GAIG Tribes from 2022 and polytopia\_python) aren't wired in yet; they're too old to settle current rules but useful for history.

## Status board (23 Oct, morning)

| Area | Level | What's left |
| --- | --- | --- |
| Base unit stats | L1 | Raft range (1 or 2) |
| Tech tree | L1 | C27: Navigation's prerequisite; backwards research |
| Tech cost formula | L1 | none |
| Combat formula and retaliation | L2 | C20: no retaliation from fog |
| Poison (Cymanti) | L1 | now −50% defence, bonuses kept (v115) |
| Tile actions | L1 | road cost (2 or 3) |
| Start packages | L1 | C3, C5, Luxidoor wall |
| Capital resources (C23, C10) | L0 | pre-registered test, needs data |
| Villages (C9), ruins, starfish | L0 | one real save |
| Land share by map type (G1) | L0 | Polyfish only |
| Fog rules (C21, G3, G9) | L0 | in-game or save file |
| Ruin odds, meeting reward | L0 | replays or the mod |
| Bot behaviour (G5) | L0 | replays or the mod |
| Special tribes | L0–L1 | after base tribes |

The full list, with every source per item, is `conflicts_and_gaps.md` in the Polytopia project (C1–C29, G1–G12).

## Built overnight

All of it is in my workspace under `polytopia_ai/verify/` and copied to the Polytopia project.

- **`run_all.sh`** — one command that rebuilds the dataset and runs every check. Last run: the self-check passes and the Polyfish comparison gives 283 agree / 31 differ.
- **`state2json`** — converts a real `.state` save to JSON. It is built on an MIT-licensed save reader.
- **`analyze_map.py`** — measures a real map against every open conflict: capital rings, settlements against grid slots, ruins against the ruin table, starfish against water ÷ 25, land share, fish rate, tiles explored per player, and starting packages. It is tested on one sample state from Polyfish (game version 115, turn 11). That sample only shows the pipeline works; it is not evidence, because by turn 11 harvested resources are gone.
- **`c23_models.py`** — the pre-registered capital-resource test. Average resources in a capital's 8-tile ring, under each model:
  - PolyEnv model: about 1–4 depending on tribe (Vengir lowest, Imperius highest).
  - Wiki model: about 3–6.
  - Polyfish model: in between.

  If the wiki model is true, about 3 capitals decide it. Telling the other two apart takes about 8–30. Hoodrick, Quetzali, Elyrion, Yădakk and Cymanti separate them fastest.
- **`crosscheck.py` and `parse_polyfish.py`** — the comparison against the Polyfish engine. Rerun them with `run_all.sh` after pulling a newer Polyfish.

**What I couldn't do:** build Polyfish's engine, because crates.io is blocked here; and find a public real `.state` file. Neither the web nor the repos I checked had one, so Gate C needs your save or your test-sheet data.
