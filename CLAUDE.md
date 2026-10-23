# CLAUDE.md: context for Claude Code

## The project

- **Goal:** a Polytopia AI "wartime general" that beats the built-in bots (Hard first, then Crazy).
- **Roles:** Jason is the president and gives orders; Claude is the general.
- **Priority:** winning, combat first. Score doesn't matter.
- **Phases:** 1 data and verification (done) → 2 advisor mode → 3 forward model → 4 fog inference → 5 search → 6 bot model and exploits → 7 directives. See `docs/polytopia_ai_roadmap.md`. Current state is in `.scratchpad/status.md`.

## Start here

1. Run `sh scripts/restore_saves.sh` (8 s; rebuilds `saves/` from the raw `saves_raw/*.state`). Then `python3 -I tools/miss.py` for the current score (units and stars per game).
2. Read `.scratchpad/status.md`, then the backlog item or investigation for the task.
3. Read other files only when `.scratchpad/README.md` says the task needs them.
   Before changing `engine/` or `verify/state_v123.py`, read `.scratchpad/lessons.md`
   (save format, combat formulas, engine gotchas).
4. One task per chat. On a long task, keep the investigation file up to date so
   the person can clear the chat and continue in a fresh one.

## Who you're working with

Two people work on this repo. Tell them apart by the git remote: run
`git remote get-url origin`. If it points at `miinjaekim/Polytopia`, you're
working with Minjae; otherwise with Jason.

- **Jason** owns the repo (`jasonparkjiwon-hash/Polytopia`) and makes the project calls.
  - Approved 23 Oct 2026: commit and push finished work straight to `main` without asking, but only after `sh scripts/check.sh` runs without regressing the README baseline. Don't use side branches or pull requests unless he asks for one.
  - Changes only to `.scratchpad/` (notes, investigation progress) can be pushed to `main` without running `check.sh`.
  - He uses **Claude Code on his iPhone**, so his sessions run in the cloud on a fresh copy of the repo. Anything not committed and pushed is gone when the session ends, so push scratchpad updates before the chat ends.
  - He plays on **iPhone** and exports saves as text (device path + base64). There are no PC-only tools on his side.
- **Minjae** contributes from a fork (`miinjaekim/Polytopia`, remote `upstream` is Jason's repo).
  - Run `git pull upstream main` before starting a task.
  - Work on a branch, push to the fork, and open a pull request to Jason's repo. Never push to Jason's repo directly.
  - `sh scripts/check.sh` must not regress the README baseline before a PR.
  - Leave `notebook/` alone; Jason rebuilds it.

For both:

- Run anything consequential by the person first (posting, deleting, messaging people, force-pushing, rewriting history).
- Verify rendered output (notebooks, plots, pages) before handing it over.
- Keep explanations plain; neither reads the code line by line.

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

## Working efficiently (the main cost is context, not code)

- **Never open** `saves/*.json`, `notebook/*.ipynb`, or `verify/ledger.json` / `data/conflicts_and_gaps.md` whole. `.claude/settings.json` blocks the first two.
  - One spot in a game: `python3 -I tools/trace.py <game> <turnA> <turnB> x,y ...`.
  - Ledger: `python3 -I tools/ledger.py ids | get ID | add ... | note "..."`. Edit the ledger and gaps file only through this tool.
  - Code: `python3 -I tools/outline.py engine/replay.py`, then Read only the lines you need (`offset`/`limit`).
- **One fix per loop, small output:** change one rule, A/B it with `RULES` in `tools/miss.py` (keep only if the total improves or holds), commit. Don't paste misses back into the chat: use `--list` and read only the lines about the case you're on.
- **Notebook:** rebuild and run it only when you finish a batch of work, not after each change.
- **Docs:** the repo copies in `docs/` are the source of truth. Update the live claude.ai spec only when Jason asks.
- Start a fresh session after about 15 replay-fix loops.

## Conventions

- Pure-stdlib Python 3 in `engine/` and `verify/`. Run scripts that read downloaded or third-party data with `python3 -I`.
- `sh scripts/check.sh` must not regress the baseline in README.md.
- Raw saves live in `saves_raw/` (committed, tiny). `saves/` (decoded JSON) and `ext/` are gitignored and rebuilt on demand (`scripts/restore_saves.sh`, `scripts/fetch_third_party.sh`).
