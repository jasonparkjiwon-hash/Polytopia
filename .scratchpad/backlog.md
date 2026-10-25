# Backlog

Open work only, highest priority first. Owner is whoever is working on it now.
Set it when you pick an item up so two people don't do the same work.

Score now: 4728/4728 units (100%) and 802/819 star player-turns exact
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

## 1. Aquarion unit ids

_Owner: unassigned · waiting on a save_

46 Mermaid, 48 Swordsmaid, 53 Shark are measured. Polyfish names the rest
(47, 49–52, 54, 55) in the ledger only (`AQUARION-UNIT-IDS`, L0); no save holds
them yet. Tech ids are settled (`AQUARION-TECH-TIERS`).

## 2. Star misses left (17)

_Owner: unassigned · details in `investigations/star-tail.md`_

- Bot war (13 rows): stars for meeting a tribe, somewhere in a 4–6 turn gap.
  Needs a game with saves every turn.
- Bot war t11→15 p16 (-1): was -8 before Oceanology was priced tier 3 (Jason's card).
- Misty Fields t11→12 p5 (-4): a trade route cut by another tribe's new city
  border. Would need a trade-route model; worth it only if more saves show it.
- Oasis t10→12: p13 (-2) is meet timing with no t11 save; p9 (+3) is a tribe
  destroyed mid-gap. Ignore both.

## 3. Unverified rules (3)

_Owner: unassigned · waiting on a save that shows them_

Embassy price step (`EMBASSY_STEP`; 4, +2 each, settled from Jason's test but
not yet seen in a save), Market income (one save case), Clathrus income (Fungi
per the card, Algae per Polyfish; untested). Jason answered tests 36–38.

## 4. Small open questions (no save tests them yet)

- Why AI players' idle units never heal in the saves, while the human player's
  do (`IDLE-AUTO-RECOVER`). Also: does allied territory count as friendly?
- Does Polaris border growth (not just a capture) freeze water too?
- A push with no open tile removes the unit (Jason); no save shows one yet.
