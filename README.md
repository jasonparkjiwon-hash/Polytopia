# polytopia-ai

A long-term build of an AI "wartime general" for The Battle of Polytopia. Claude is the general and Jason is the president. The goal is to **win, with combat first**; score doesn't matter.

**Current phase: Phase 1, data and verification.** No advisor or search work starts until the Phase 1 exit gates pass (`docs/polytopia_ai_phase_1_spec.md`).

## What's here

| Folder | What it is |
|---|---|
| `.scratchpad/` | Working notes for Claude Code sessions: current status, open work with owners, engine lessons, and one file per open mismatch hunt. Start with `.scratchpad/README.md`. |
| `engine/` | Replay engine: a Python copy of the game rules that replays a real save's action log and checks every unit's HP and position against the game's own end state. `replay.py` (rules and replay), `economy.py` (stars and income check), `state.py` (game state from a save), `stats.py` (unit stats). |
| `verify/` | Save decoder for game v123 (`state_v123.py`), save ingest (`ingest_saves.py`), the evidence **ledger** (`ledger.json`: every rule with its source and evidence level), and the Polyfish cross-check plus map analysis tools. `state2json/` and `statedebug/` are Go tools (binaries not committed; `go build` them). |
| `data/` | Rules dataset (units, tech tree, combat, economy, map generation, fog, tribes), measured tables from real saves (`measured_*.json`), and `conflicts_and_gaps.md` (every open conflict C1–C29 and gap G1–G12). |
| `saves_raw/` | The raw iPhone `.state` saves (95 files, 2.4 MB), committed. `sh scripts/restore_saves.sh` rebuilds `saves/` from them in about 8 seconds. |
| `tools/` | Small debug tools: `miss.py` (replay score), `trace.py` (one spot), `ledger.py` (edit the ledger without reading it), `outline.py` (find lines in big files). |
| `saves/` | **Local only, not committed** (gitignored); `scripts/check.sh` needs it. Real iPhone `.state` saves from 32 games (plus per-turn copies), their decoded JSON and `index.json`. Includes the bot war (`6e1bf8e0…` at turns 5/11/15), Ankiian turn by turn (`1bf60251…_t1`–`_t7`) and The Misty Fields turn by turn (`e15f392c…_t1`–`_t16`). `public_game_links.tsv` is Polyfish's list of ~11.7k public share links. |
| `sim/` | Map generator from the wiki rules (`wiki_mapgen.py`, with measured mode) and `pfcore/`, the Polyfish Rust engine core (Apache-2.0). |
| `notebook/` | `polytopia_engine.ipynb`, a self-contained Google Colab notebook (built by `build_notebook.py`). |
| `docs/` | Markdown exports of the Claude Docs: Phase 1 spec, roadmap, the in-game test sheet, plus `verify_tools.md`. |
| `legacy/` | Dataset v0.3 snapshot and the first map models (`polymap.py`, `hidden_tiles.py`, out of date). |
| `scripts/` | `check.sh` (smoke test), `fetch_third_party.sh` (re-clone reference repos into `ext/`), `run_notebook.py` (run the notebook headless). |

## Quick start

```sh
python3 -m pip install matplotlib        # only the notebook/map plots need it; the engine is pure stdlib
sh scripts/check.sh                      # replays both games and prints match scores
```

Expected from `check.sh` (the current baseline):

- Ankiian turn by turn: 27/27, 33/33, 39/39, 43/43, 51/51, 59/59, 66/66 units with exact HP.
- Bot war: turn 5 66/66, turn 11 92/92, turn 15 123/123: every unit exact.
- Misty Fields turn by turn (turns 1-16): exact through turn 12 (24, 29, 34, 37, 48, 69, 80, 94, 100, 103, 119, 123); then 133, 144, 149, 157: every unit exact.
- Oasis Struggle turn by turn (`af181c8f…_t1`–`_t26`, no t11/t17): see `data/conflicts_and_gaps.md` (full replay 2252 exact over 24 checkpoints).
- Cliff & Gods turn by turn (`09a5bf1e…_t1`–`_t8`, Crazy, 16 players): 26, 33, 47, 63, 78, 91, 109: every unit exact.
- Stars (`engine/economy.py`, last block of `check.sh`): Ankiian 96/96, bot war 18/32 (saves 4-6 turns apart), Misty Fields 239/240, Cliff & Gods 96/96 player-turns exact. Oasis Struggle 353/355 (scored by `tools/miss.py` only, not `check.sh`).
- Held-out check (`python3 -I tools/miss.py --holdout`, `data/holdout.json`): scored 26 Oct at rules commit 62666fa, before any tuning on them: Jason's games 1-5 (Hard, every turn) units 1724/1733, stars 512/523 (per game in `holdout.json`), released for tuning the same day; still held: `ed6cb932` (t1-t5) 187/187, 64/64. Plain `tools/miss.py` with games 1-5 released: units 6452/6461, stars 1314/1342.

**Held-out protocol.** Every rule so far was tuned on the saves above, so their scores
say how well the engine fits, not how well it predicts. To measure prediction:

1. A new save (or a new run of turns in an old game) goes into `data/holdout.json`
   `held` **before anyone looks at its misses or tunes a rule on it**.
2. Score it once: `python3 -I tools/miss.py --holdout`. Write the result (date, units,
   stars, the commit it was scored at) into that entry's `scored` field and the line above.
3. Plain `tools/miss.py` leaves held checkpoints out, so tuning loops never see them.
   `--all` scores everything.
4. To start fixing its misses, move the entry to `released` (with the date). Never move a
   game back: once tuned on, it is training data.

Replay one game by hand:

```sh
cd engine
python3 replay.py ../saves/<id>_t15.json ../saves/<id>_t5.json ../saves/<id>_t11.json   # final save, then checkpoints
```

Add a new save from the iPhone (the text export: first line is the device path, then base64):

```sh
python3 -I verify/ingest_saves.py saves export.txt
```

Rebuild all save JSONs from the raw `.state` files: `python3 -I verify/ingest_saves.py saves saves/*.state`.

## Third-party code

Reference repos (Polyfish, PolyEnv/Tribes, save editors and others) are **not committed**. `scripts/fetch_third_party.sh` re-clones them into `ext/` at the commits used. See `THIRD_PARTY.md`.

## Live docs (claude.ai)

- Phase 1 spec: https://claude.ai/artifact/K9wQ2L9xnNqnaxfckBGcwp
- Roadmap: https://claude.ai/artifact/BRUwionha6Zkjd7fY5WaQz
- Test sheet: https://claude.ai/artifact/VdTo8Kw8UGqYRQfygEVS2s

The copies in `docs/` were exported on 23 Oct 2026.
