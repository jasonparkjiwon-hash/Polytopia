# Backlog

Open work only, highest priority first. Owner is whoever is working on it now.
Set it when you pick an item up so two people don't do the same work.

Score now: 4709/4753 units (99.1%) and 762/819 star player-turns exact
(`python3 -I tools/miss.py`).

## 0. Phase 3 prep: Polyfish as the forward model (Jason, 24 Oct)

Polish is done for now (units 4728/4728, stars 802/819); it continues over time as
sims run. Plan: `docs/simulator_choice.md` "What has to happen before Phase 3".
Polyfish (`sim/pfcore`, Rust) becomes the forward model; `engine/` stays the
referee. Three parallel Claude sessions, one investigation file each:

| Stream | File | Owns |
|---|---|---|
| pf-loader | `investigations/pf-loader.md` | Save JSON -> Polyfish GameState; run logged actions in Polyfish; `tools/pf_miss.py` scored like `tools/miss.py`; then a legality check (every logged action is in Polyfish's legal-move list) |
| pf-port | `investigations/pf-port.md` | Port the v123 corrections (every ledger rule at L1+) into `sim/pfcore`, one rule per commit, each with a Rust unit test; list of what Polyfish still lacks |
| sim-dist | `investigations/sim-dist.md` | Random parts as measured distributions (ruin rewards, bot choices that matter to the sim) in `data/`; held-out check (`tools/miss.py --holdout`) |

Shared rules: small commits, `git pull --rebase origin main` before every push,
`sh scripts/check.sh` must hold the README baseline; don't edit `CLAUDE.md`.
pf-loader and pf-port both touch `sim/pfcore`: pf-loader adds new files (a loader
module, a bin), pf-port edits rule code; rebase often.

## 1. Aquarion research (star misses)

_Owner: unassigned_

Priced by id since 23 Oct (`AQUARION_TIERS` in `engine/economy.py`: 47 tier 1, 39 and 46
tier 2; 8 star rows went exact). Still open: the in-game names, to replace the ids. The Aquarion wiki page is blocked from the cloud container
(proxy 403); Jason can paste it or the tech names.

## 2. Unit misses left (44)

_Owner: unassigned_

- Bot war turn 11-15 (23): mostly 1-5 HP off, and units the engine keeps alive.
  Saves are 4 turns apart, so the cause is hard to isolate.
- Oasis Struggle (21): one spot each; trace with `tools/trace.py`. One explosion
  (Oasis t25, three targets 1 HP less) fits no variant.

Start a file in `investigations/` when you pick this up (see
`investigations/_template.md`).

## 3. Other star misses

_Owner: unassigned_

- Single-turn misses of -1 on a bot that attacked (about 10): probably a kill or
  capture reward not modelled.
- Multi-turn gaps (bot war): small errors add up; ignore until the single-turn
  ones are fixed.

## 4. Aquarion unit ids

_Owner: unassigned_

Only 46 Mermaid, 48 Swordsmaid, 53 Shark are named; the other Aquarion ids are
still unknown.

## Not yet in any save

Embassy, Market, Clathrus income; structure 51 price; Dash units breaking ice the
same turn; peace-break disbanding. Nothing to do until a save shows them.
