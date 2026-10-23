# CLAUDE.md: context for Claude Code

## The project

- **Goal:** a Polytopia AI "wartime general" that beats the built-in bots (Hard first, then Crazy).
- **Roles:** Jason is the president and gives orders; Claude is the general.
- **Priority:** winning, combat first. Score doesn't matter.
- **Phases:** 1 data and verification (now) → 2 advisor mode → 3 forward model → 4 fog inference → 5 search → 6 bot model and exploits → 7 directives. See `docs/polytopia_ai_roadmap.md`.
- **Phase 1 exit gates:** see `docs/polytopia_ai_phase_1_spec.md`. The advisor stays on hold until they pass.

## Working with Jason

- Run anything consequential by him before doing it (pushing, posting, deleting, messaging people).
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
- **Known action types:** 27 Establish Embassy; 28 diplomacy reply; 38 Shaman Boost; 24 Boomchi Explode. Build type 30 is Enchant Animal. Type 18 is unknown and is not Disband.
- **Start techs** appear only after StartMatch (see `data/measured_start.json`).

## Combat (confirmed by replay)

- aF = atk·hp/max; dF = def·hp/max·bonus.
- dmg = round_half_up(aF/(aF+dF)·atk·4.5).
- ret = round_half_up(dF/(aF+dF)·def·4.5). Retaliation counts the bonus.
- No retaliation if the attacker is out of the defender's range, or with Stiff or Surprise.
- A melee attacker moves in after a kill.
- **Defence bonus:**
  - 1.5 in its own city (Fortify units); 4 with walls.
  - 1.5 on forest with Archery, or on mountain with Climbing.
- Veteran +5 max HP; splash does half damage, floored.

## Engine bookkeeping gotchas

- **Unit ids:**
  - Train doesn't record the new id. Temporary negative ids are rekeyed by position on the unit's first Move or Attack.
  - Boarding gives the boat a new id; the passenger gets its old id back on landing.
  - An upgrade gives a new id.
- **Forced spawns:** the Giant reward and Enchant push the occupant to a neighbour. The push rule is unknown.
- **Healing:** +4 in own territory, +2 elsewhere. Territory is re-synced at checkpoints.
- **Fog:** explored tiles show enemies live. Only unexplored clouds hide them.

## Open work (next up)

1. **Economy replay:** check stars and income against the saves.
2. **Coverage report:** which rules each replay exercises.
3. **Bot-war mismatches at turns 11 and 15:**
   - The push direction rule.
   - Action type 18.
   - Ruin rewards and spawns.
   - Poison.
   - Boat HP details.
4. **Waiting on Jason:** per-turn saves of a fight-heavy Crazy game; Round 2 items 26–34 on the test sheet (`docs/polytopia_open_questions_to_fill_in_while_playing.md`).

## Conventions

- Pure-stdlib Python 3 in `engine/` and `verify/`. Run scripts that read downloaded or third-party data with `python3 -I`.
- After changing engine code, rebuild the notebook (`python3 notebook/build_notebook.py`) and run `python3 scripts/run_notebook.py notebook/polytopia_engine.ipynb /tmp/nbwork`.
- `sh scripts/check.sh` must not regress the baseline in README.md.
- `ext/` (third-party clones) and build outputs are gitignored. Fetch them with `scripts/fetch_third_party.sh`.
