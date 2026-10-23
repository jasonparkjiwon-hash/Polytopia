# Backlog

Open work only, highest priority first. Owner is whoever is working on it now.
Set it when you pick an item up so two people don't do the same work.

Score now: 4728/4728 units (100%) and 802/819 star player-turns exact
(`python3 -I tools/miss.py`).

The replay work is mostly finished; what's left waits on Jason (see
`status.md`). The next big step is Phase 2 (advisor mode), once Jason says go.

## 1. Aquarion names

_Owner: unassigned · waiting on test item 40_

- **Techs:** the engine prices 39, 46 and 47 by id (`AQUARION_TIERS` in
  `engine/economy.py`). Known: 46 is Marine Life (L2). Polyfish's names (L0):
  39 Aquaculture, 47 AquaFishing. Rename them in the engine only together with
  `AQUARION_TIERS`, or the prices break.
- **Units:** 46 Mermaid, 48 Swordsmaid, 53 Shark are measured. Polyfish names the
  rest (47, 49–52, 54, 55) in the ledger only (`AQUARION-UNIT-IDS`, L0); no save
  holds them yet.

## 2. Star misses left (17)

_Owner: unassigned · details in `investigations/star-tail.md`_

- Bot war (13 rows): stars for meeting a tribe, somewhere in a 4–6 turn gap.
  Needs a game with saves every turn.
- Bot war p16 (-8): Oceantology's price (waiting on Jason).
- Misty Fields t11→12 p5 (-4): a trade route cut by another tribe's new city
  border. Would need a trade-route model; worth it only if more saves show it.
- Oasis t10→12: p13 (-2) is meet timing with no t11 save; p9 (+3) is a tribe
  destroyed mid-gap. Ignore both.

## 3. Unverified rules (3)

_Owner: unassigned · waiting on test items 36–38_

Embassy price (`EMBASSY_STEP`, 4 in the saves vs 5 per the card), Market income
(one save case), Clathrus income (Fungi per the card, Algae per Polyfish).
Settle each in the ledger when Jason's test comes back.

## 4. Small open questions (no save tests them yet)

- Why AI players' idle units never heal in the saves, while the human player's
  do (`IDLE-AUTO-RECOVER`). Also: does allied territory count as friendly?
- Does Polaris border growth (not just a capture) freeze water too?
- A push with no open tile removes the unit (Jason); no save shows one yet.
- Second embassy price (+2?), part of test item 36.
