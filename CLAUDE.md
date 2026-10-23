# CLAUDE.md: context for Claude Code

## The project

- **Goal:** a Polytopia AI "wartime general" that beats the built-in bots (Hard first, then Crazy).
- **Roles:** Jason is the president and gives orders; Claude is the general.
- **Priority:** winning, combat first. Score doesn't matter.
- **Phases:** 1 data and verification (done, 23 Oct 2026) → 2 advisor mode (next, on Jason's go) → 3 forward model → 4 fog inference → 5 search → 6 bot model and exploits → 7 directives. See `docs/polytopia_ai_roadmap.md`.
- **Phase 1 exit gates:** see `docs/polytopia_ai_phase_1_spec.md`. All six passed on 23 Oct 2026. Before Phase 3, load real saves into Polyfish (`docs/simulator_choice.md`).

## Working with Jason

- Run anything consequential by him before doing it (posting, deleting, messaging people, force-pushing, rewriting history).
- **Exception, approved by Jason on 23 Oct 2026:** commit and push finished work straight to `main` without asking, but only after `sh scripts/check.sh` runs without regressing the README baseline. Don't use side branches or pull requests unless he asks for one.
- He plays on **iPhone** and exports saves as text (device path + base64). There are no PC-only tools on his side.
- Verify rendered output (notebooks, plots, pages) before handing it over.
- Keep explanations plain; he's not reading the code line by line.

## Evidence rules

- Every rule has a level in `verify/ledger.json`:
  - **L0:** one source.
  - **L1:** two independent sources agree, at least one dated 2025 or later.
  - **L2:** three sources agree, or a pre-registered test passes.
  - **L3:** measured in the real game (a save or a controlled test).
- The simulator may rely only on L1 or above.
- **Tie-break:** dated patch notes > Polyfish (game v115) > PolyEnv > the undated fandom wiki. Real saves (L3) beat everything.
- When a rule changes, update `verify/ledger.json` and `data/conflicts_and_gaps.md` in the same change. Don't pick a side on a split rule; make it a test item.
- **A/B test rule changes against the replay:** a change is kept only if the bot-war match score improves or stays the same. The `RULES` dict in `engine/replay.py` holds the switches.

## Save format (v123), short version

- **Layout:** initial state | 7 bytes | current state | 2 bytes | action list | 9-byte trailer.
  - The trailer is 3 zero bytes, the hash and a u16 action count.
- **Player records:** the post-v114 layout plus one trailing tribe byte. Task types 1, 5 and 9 carry 6 bytes; the others 2.
- **Action sizes** (bytes after the u16 type) are in `ACTION_SIZES` in `verify/state_v123.py`.
- **Known action types:** 27 Offer Peace (needs Strategy); 28 peace reply (1 accept, 0 decline); 29 Break Peace (n=1); 38 Shaman Swarm (neighbours get extra movement, no attack bonus); 24 Boomchi Explode. Build type 30 is Enchant Animal. Type 18 is Break Ice (the ice around the acting unit becomes water again).
- **Start techs** appear only after StartMatch (see `data/measured_start.json`).

## Combat (confirmed by replay)

- aF = atk·hp/max; dF = def·hp/max·bonus.
- dmg = round_half_up(aF/(aF+dF)·atk·4.5).
- ret = round_half_up(dF/(aF+dF)·def·4.5). Retaliation counts the bonus.
- No retaliation if:
  - the attacker is out of the defender's range;
  - the defender's tribe can't see the attacker's tile (unexplored and out of current vision);
  - the attacker is a hidden Cloak;
  - Stiff (the defender) or Surprise (the attacker) applies.
- A Dagger still retaliates when attacked.
- A melee attacker moves in after a kill.
- **Defence bonus:**
  - 1.5 in its own city (Fortify units); 4 with walls.
  - 1.5 on forest with Archery, or on mountain with Climbing.
- Veteran +5 max HP; splash (Bomber) and explode hit each neighbour for half damage, floored.
- Poison halves defence, bonus included. Fungi poisons non-Cymanti units at end of turn.
- A Shaman converts like a Mind Bender (one sample: it also deals normal damage, with no retaliation).
- After a kill: a boat moving onto land drops its passenger. Land units don't follow into water. Sharks and Raychi don't follow onto dry land.

## Engine bookkeeping gotchas

- **Unit ids:**
  - Train doesn't record the new id. Temporary negative ids are rekeyed by position on the unit's first Move or Attack.
  - Boarding gives the boat a new id; the passenger gets its old id back on landing.
  - An upgrade gives a new id.
- **Forced spawns:** the Giant reward, Enchant and ruin units (spawned on the ruin tile) push the occupant to a neighbour.
  - Polyfish's push rule fits: same direction as its last move (opposite for an enemy), otherwise toward the map centre.
  - The log doesn't record ruin rewards; the replay reads a ruin unit from the next save.
- **Boats:** the boat record always shows promotion 0. The passenger record keeps the veteran level.
- **Terrain changes outside the log:**
  - Mooni and Gaami freeze the water (and ocean) around them after moving or capturing, and freeze adjacent enemy units. Ice goes back to water only through Break Ice (action 18).
  - Aquarion flood (flag value 1): boats stay boats and walkers stay walkers.
  - Cymanti algae (value 4): walkable water.
  - Terrain is re-synced at checkpoints.
- **Healing:** +4 in own territory, +2 elsewhere. Territory is re-synced at checkpoints.
- **Fog:** explored tiles show enemies live. Only unexplored clouds hide them.

## Working efficiently (read this first: the main cost is context, not code)

- **Start of a session:** run `sh scripts/restore_saves.sh` (8 s; rebuilds `saves/` from the raw `saves_raw/*.state`). Then `python3 -I tools/miss.py` for the current score (units and stars per game).
- **Never open** `saves/*.json`, `notebook/*.ipynb`, or `verify/ledger.json` / `data/conflicts_and_gaps.md` whole. `.claude/settings.json` blocks the first two.
  - One spot in a game: `python3 -I tools/trace.py <game> <turnA> <turnB> x,y ...`.
  - Ledger: `python3 -I tools/ledger.py ids | get ID | add ... | note "..."`. Edit the ledger and gaps file only through this tool.
  - Code: `python3 -I tools/outline.py engine/replay.py`, then Read only the lines you need (`offset`/`limit`).
- **One fix per loop, small output:** change one rule, A/B it with `RULES` in `tools/miss.py` (keep only if the total improves or holds), commit. Don't paste misses back into the chat: use `--list` and read only the lines about the case you're on.
- **Notebook:** rebuild and run it only when you finish a batch of work, not after each change.
- **Docs:** the repo copies in `docs/` are the source of truth. Update the live claude.ai spec only when Jason asks.
- Start a fresh session after about 15 replay-fix loops.

## Open work (hand-off, 23 Oct 2026)

Phase 1 is done. Replay is at 4709/4753 units (99.1%) and 762/819 star player-turns exact (`tools/miss.py`).

1. **Unit misses left (44):** bot war turn 11-15 (23, mostly 1-5 HP off and units the engine keeps alive; saves 4 turns apart, so cause is hard to isolate) and Oasis Struggle (21, one spot each; trace with `tools/trace.py`). One explosion (Oasis t25, three targets 1 HP less) fits no variant.
2. **Star misses left (65):**
   - Aquarion research: tech ids 39, 46, 47 are missing from `TECH`. The saves imply 47 is tier 1 and 39 and 46 are tier 2 (price tier x cities + 4). Name them and add to `TIER` in `engine/economy.py`. The Aquarion wiki page (https://polytopia.fandom.com/wiki/Aquarion) is blocked from the cloud container (proxy 403); Jason can paste it or the tech names.
   - Single-turn misses of -1 on a bot that attacked (about 10): probably a kill or capture reward not modelled.
   - Multi-turn gaps (bot war): small errors add up; ignore until single-turn ones are fixed.
3. **Not yet in any save:** Embassy, Market, Clathrus income; structure 51 price; Dash units breaking ice the same turn; peace-break disbanding.
4. **Aquarion unknown unit ids:** only 46 Mermaid, 48 Swordsmaid, 53 Shark are named; the other Aquarion ids are still unknown.
5. **Next phase:** Phase 2 (advisor) waits for Jason's go. Before Phase 3, load saves into Polyfish (`docs/simulator_choice.md`).
6. **Waiting on Jason:** Waterworld/other new saves as he plays; the Aquarion page or tech list.

## Conventions

- Pure-stdlib Python 3 in `engine/` and `verify/`. Run scripts that read downloaded or third-party data with `python3 -I`.
- `sh scripts/check.sh` must not regress the baseline in README.md (run it before pushing; push straight to `main`).
- Raw saves live in `saves_raw/` (committed, tiny). `saves/` (decoded JSON) and `ext/` are gitignored and rebuilt on demand (`scripts/restore_saves.sh`, `scripts/fetch_third_party.sh`).
