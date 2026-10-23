# Polytopia AI: roadmap

Oct 22, 2026 · @Jason Park

## Where things stand (22 Oct, night)

The goal: Claude as a wartime general for Polytopia, you as president, beating the built-in bots through search, a forward model, fog inference and exploit-finding. Step 1 (data) is essentially done. The first interface will be **advisor mode**: Claude advises while you play the real game.

**Done**

- **Rules dataset v0.3.** Map generation, fog, all 16 tribes, 54 units, the tech tree, combat, economy and bot settings. Every fact carries a source, a confidence level and a conflict ID. The self-check passes (14 of 15 wiki start scores rebuilt from first principles).
- **Wiki pass tonight.** It settled or moved 13 conflicts: retaliation, poison, fog retaliation, villages, capital guarantees, all tribe terrain modifiers, the explorer, and the special-tribe trees. It also added four new findings:
  - Bot “difficulty stars” are total capital income (Easy 1, Crazy 5), not a bonus on top.
  - Since 2025, techs can be researched backwards.
  - Burn Forest now costs 3 stars.
  - There is a new tribe, Solaris, that nothing covers yet.
- **Your test sheet.** “Polytopia: open questions to fill in while playing” lists 7 priority tests plus quick confirms.

**Biggest lesson so far:** every number has a patch date. Dated patch notes beat the PolyEnv engine, and the engine beats the undated wiki. The engine itself is stale on the 2025 changes.

**Still open (needs your games):** how many resources sit around a capital (the top test), whether fog shows old or live state, water tech gates, tile action costs, ruin odds, and the meeting reward. The wiki's Fog of War, Bots and Resources pages would not load from here.

**Where the files are** (my workspace, under `polytopia_ai/`)

- `data/*.json`: the dataset. `data/build_dataset.py` rebuilds it and `data/validate_dataset.py` checks it.
- `data/conflicts_and_gaps.md`: the full conflict table (C1–C26, G1–G12).
- `polymap.py` and `hidden_tiles.py`: the first map and hidden-tile models. Both are **out of date** and use the old weights.
- A copy of this roadmap is saved in the Polytopia project, so any session can pick it up.

## Tomorrow

### Decide first (5 minutes)

These shape the whole advisor build. Type your choice after each.

- **Tribe to start with.** I'd suggest one with no special mechanics and a simple start, such as Imperius, Bardur or Xin-xi, so the model only has to be right about the base rules. Choice:
- **Map and mode.** I'd suggest a normal-size Lakes map, Domination, against 2–3 bots. That is the best-documented map type, and Domination has a clear win condition. Choice:
- **Bot difficulty.** Start on Hard; Crazy once the advisor holds up. Choice:
- **How you send the game state.** Options: (a) a screenshot each turn plus a one-line note; (b) a typed short-hand; (c) both, with screenshots on turn 0 and whenever something new appears. I'd suggest (c). Choice:
- **How much advice per turn.** Options: (a) the single best move; (b) the top 3 with reasons; (c) a full turn plan. I'd suggest (b), with a one-line threat warning. Choice:

### Session plan

1. You answer the five choices above.
2. I build the advisor kit: a game-state file, a belief tracker for unseen tiles and enemy units, and a fixed per-turn reply format (rough guess: about an hour of my work).
3. You play turn 0 and send it. That one screen also answers Q1–Q3 on the test sheet.
4. We play the first 10 turns together. After each turn you say whether my advice made sense, and I log where my model of the game was wrong.
5. At the end, I fold every correction back into the dataset and the test sheet.

**If you only have 10 minutes:** play one game to turn 1 and fill Q1 and Q2 on the test sheet. That is the most valuable data per minute.

## Phases

Each phase has a clear exit test, so we know when to move on. The order matters: each one feeds the next.

### Phase 1. Data — almost done

- **Left to do:** your in-game answers; the wiki pages that would not load (paste them from your phone if you like); Solaris.
- **Exit:** the top 7 tests answered, and no conflict left that changes a turn-1 decision.

**Update 23 Oct:** Phase 1 is now governed by the stricter “Polytopia AI: Phase 1 spec” doc. It has six exit gates and an evidence ladder from L0 to L3, and it adds data paths beyond screenshots. The advisor stays on hold until every gate passes.

### Phase 2. Advisor mode v1 — next

- **Build:** a game-state file (turn, stars, techs, cities, units, explored tiles); a belief file for what is hidden (a likely-resources map, likely enemy positions); a rules lookup on the dataset; and a fixed reply each turn: top 3 moves, why, and the main threat.
- **No search yet:** I reason from the rules and the state, the way a strong human would.
- **Exit:** 3 full games won on Hard with the advice, and a written log of every place my rules model was wrong.

### Phase 3. Forward model

- **Build:** a simulator that predicts the result of a move exactly: fights, income, growth, techs. Choose between patching PolyEnv (C++, fast, many known stale rules) and a small Python engine built from our dataset (slower, but every rule is ours and sourced). My lean is the Python engine first, since the rules are now well documented.
- **Patch list if we use PolyEnv:** retaliation with the defence bonus, no retaliation from fog, backwards research, Burn Forest 3, temples 100 per level, all 16 capital guarantees, tribe terrain table, bot income.
- **Exit:** it predicts 95% of fight results and star totals in your logged games exactly.

### Phase 4. Fog inference

- **Build:** update `polymap.py` and `hidden_tiles.py` to the v0.3 rules, then a belief tracker: probable resources and villages in unseen tiles, and where enemy units probably are, based on what was last seen.
- **Exit:** before you scout a tile, I predict its terrain, villages and resources better than chance. Each prediction is scored against what you then see.

### Phase 5. Search

- **Build:** plan several turns ahead with the forward model and beliefs, using sampled hidden maps and a tree or beam search over each turn's moves. An evaluation function scores income, cities, military and score.
- **Exit:** the advisor's own plans beat my Phase 2 judgement in head-to-head replays.

### Phase 6. Bot model and exploits

- **Build:** a model of how bots choose moves, from your games (what they attack, when they expand, whether they react to unseen units). Then self-play inside the simulator to find repeatable exploits.
- **Exit:** a list of exploits that work reliably in the real game, each tested by you.

### Phase 7. President's directives

- **Build:** turn your orders (“take the eastern capital by turn 15”, “no losses before turn 8”, “max score”) into objective functions and limits for the search, and report back like a general: plan, risk, cost.
- **Exit:** you give orders only, and the general wins on Crazy.

### Later, optional

- **Automation:** read the game from screenshots without your note, or connect to a game client. Only after Phase 5 proves the advice is worth automating.

## Risks and open questions

- **Workspace files can vanish.** My working folder is wiped when a session ends. I saved the conflict table, the dataset and this plan into the Polytopia project tonight. If a future session can't find `polytopia_ai/`, it rebuilds from the project copies.
- **Version drift keeps happening.** The game patches several times a year. Every rule needs its patch date, and when you notice a balance update in game, tell me so I can recheck the affected rules.
- **Screenshots are the bottleneck.** Advisor mode is only as good as my reading of your screen. If reading fails often, we switch to typed short-hand for the parts that matter (stars, unit HP, enemy positions).
- **Bots may cheat on vision.** If they see through fog, the belief model of their behaviour changes. Your notes on odd bot moves are the cheapest evidence.
- **Special tribes are expensive.** Polaris, Cymanti, Aquarion, Elyrion and Solaris each add their own mechanics. I'd keep them out until Phase 5 works on base tribes.
- **Open for you:** is the goal to win reliably (Domination on Crazy), to score high (Perfection), or both? It changes what the evaluation function rewards in Phase 5.
