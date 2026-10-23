# CLAUDE.md: context for Claude Code

## The project

- **Goal:** a Polytopia AI "wartime general" that beats the built-in bots (Hard first, then Crazy).
- **Roles:** Jason is the president and gives orders; Claude is the general.
- **Priority:** winning, combat first. Score doesn't matter.
- **Phases:** 1 data and verification (done) → 2 advisor mode → 3 forward model → 4 fog inference → 5 search → 6 bot model and exploits → 7 directives. See `docs/polytopia_ai_roadmap.md`. Current state is in `.scratchpad/status.md`.

## Start here

1. Read `.scratchpad/status.md`, then the backlog item or investigation for the task.
2. Read other files only when `.scratchpad/README.md` says the task needs them.
   Before changing `engine/` or `verify/state_v123.py`, read `.scratchpad/lessons.md`
   (save format, combat formulas, engine gotchas).
3. One task per chat. On a long task, keep the investigation file up to date so
   the person can clear the chat and continue in a fresh one.

## Who you're working with

Two people work on this repo. Minjae's checkout has a `CLAUDE.local.md` (not
committed) saying so. **If that file is missing, you're working with Jason.**

- **Jason** owns the repo (`jasonparkjiwon-hash/Polytopia`) and makes the project calls.
  - Approved 23 Oct 2026: commit and push finished work straight to `main` without asking, but only after `sh scripts/check.sh` runs without regressing the README baseline.
  - Changes only to `.scratchpad/` (notes, investigation progress) can be pushed to `main` without running `check.sh`.
  - He uses **Claude Code on his iPhone**, so his sessions run in the cloud on a fresh copy of the repo. Anything not committed and pushed is gone when the session ends, so push scratchpad updates before the chat ends.
  - He plays on **iPhone** and exports saves as text (device path + base64). There are no PC-only tools on his side.
- **Minjae** contributes from a fork (`miinjaekim/Polytopia`, remote `upstream` is Jason's repo).
  - Run `git pull upstream main` before starting a task.
  - Work on a branch, push to the fork, and open a pull request to Jason's repo. Never push to Jason's repo directly.
  - `sh scripts/check.sh` must not regress the README baseline before a PR.

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

## Conventions

- Pure-stdlib Python 3 in `engine/` and `verify/`. Run scripts that read downloaded or third-party data with `python3 -I`.
- After changing engine code, rebuild the notebook (`python3 notebook/build_notebook.py`) and run `python3 scripts/run_notebook.py notebook/polytopia_engine.ipynb /tmp/nbwork`. Who does this now that there are two people is an open question in `.scratchpad/status.md`.
- `sh scripts/check.sh` must not regress the baseline in README.md.
- Don't read the notebook or whole save JSONs into the chat. Query them with small scripts that print only what's needed.
- `ext/` (third-party clones) and build outputs are gitignored. Fetch them with `scripts/fetch_third_party.sh`.
