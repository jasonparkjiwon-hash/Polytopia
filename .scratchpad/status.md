# Status

_Last updated 2026-10-23._

## Now

- **Phase 1 (data and verification) is done.** All six exit gates passed on
  2026-10-23 (`docs/polytopia_ai_phase_1_spec.md`).
- **Phase 2 (advisor mode) is next**, and starts only when Jason says go.
- Before Phase 3, load real saves into Polyfish (`docs/simulator_choice.md`).
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
| Claude: pf-port | Port v123 corrections into Polyfish |
| Claude: sim-dist | First pass done (held-out check, `data/distributions.json`, `data/bot_turns.csv`); see `investigations/sim-dist.md` |

## Waiting on Jason

- pf-port (24 Oct), three in-game checks for the Polyfish forward model:
  1. Which tech lets Aquarion units (Mermaid) onto ocean? (saves: only seen with Navigation + Marine Life)
  2. Aqua Farm (build 49) and Aquarion structure 51: which tech unlocks each, and what does each do?
  3. Polaris skating: how far can a Mooni or Battle Sled move from a city (land) onto ice in one turn?
     (09a5bf1e t1: a Mooni went 2 tiles from its city onto ice.)
     pf-legal: the saves show Mooni at most 2 and Battle Sled at most 3, from a city or ice alike (SKATE-MOVE);
     only a Battle Sled 4 tiles over ice would change that.

- pf-legal (24 Oct), one in-game check: move a non-Cymanti land unit (e.g. a Warrior) onto a Cymanti
  algae tile with 2+ moves left. Does it stop there, or can it keep going? (Cymanti units and boats keep
  going, ALGAE-MOVE.)

- Round 3 (items 35-40) all answered 23-24 Oct.

- Waterworld and other new saves as he plays. **Export every turn** (one save per turn, like Misty Fields), not every 4-6 turns: single-turn gaps are what let ruin rewards and bot choices be read off. Each new game goes into `data/holdout.json` first and is scored before any tuning. Most wanted: a water-heavy map (only 10 water ruins so far) and a game where he builds a Sanctuary (no animal-spawn data at all).
- Waterways: its save id (only Aquarion tech id not yet seen).
- Round 2, items 26–34 on the test sheet
  (`docs/polytopia_open_questions_to_fill_in_while_playing.md`).

## Decided

- **Notebook:** only Jason rebuilds `notebook/polytopia_engine.ipynb` (about
  400 KB, conflicts on nearly every merge otherwise). Minjae's PRs leave it alone.
