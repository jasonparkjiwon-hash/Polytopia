# CLAUDE.md: context for Claude Code

## The project

- **Goal:** a Polytopia AI "wartime general" that beats the built-in bots (Hard first, then Crazy).
- **Roles:** Jason is the president and gives orders; Claude is the general.
- **Priority:** winning, combat first. Score doesn't matter.
- **Phases:** 1 data and verification (now) → 2 advisor mode → 3 forward model → 4 fog inference → 5 search → 6 bot model and exploits → 7 directives. See `docs/polytopia_ai_roadmap.md`.
- **Phase 1 exit gates:** see `docs/polytopia_ai_phase_1_spec.md`. The advisor stays on hold until they pass.

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

## Open work (next up)

1. **Economy replay:** `engine/economy.py`, 95% of player-turns exact on the per-turn games. Crazy bonus settled (3 a turn). Open: structure 51, and Embassy, Market and Clathrus income (coded, not yet seen in a save).
2. **Coverage report:** which rules each replay exercises.
3. **Remaining replay mismatches** (bot war turn 15: 12 HP; Misty Fields: a few leftover units):
   - Ruin reward weights.
4. **Waiting on Jason:** per-turn saves of a fight-heavy Crazy game; Round 2 items 26–34 on the test sheet (`docs/polytopia_open_questions_to_fill_in_while_playing.md`).

## Conventions

- Pure-stdlib Python 3 in `engine/` and `verify/`. Run scripts that read downloaded or third-party data with `python3 -I`.
- After changing engine code, rebuild the notebook (`python3 notebook/build_notebook.py`) and run `python3 scripts/run_notebook.py notebook/polytopia_engine.ipynb /tmp/nbwork`.
- `sh scripts/check.sh` must not regress the baseline in README.md.
- `ext/` (third-party clones) and build outputs are gitignored. Fetch them with `scripts/fetch_third_party.sh`.
