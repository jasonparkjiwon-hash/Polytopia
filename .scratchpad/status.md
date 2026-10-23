# Status

_Last updated 2026-10-23 (after the polish program)._

## Now

- **Phase 1 (data and verification) is done.** All six exit gates passed on
  2026-10-23 (`docs/polytopia_ai_phase_1_spec.md`).
- **Polish program is done** (four parallel sessions, 23 Oct):
  - **Units: 4728/4728, every unit in every save exact** (was 4709/4753).
  - **Stars: 802/819 player-turns exact** (was 762). All 17 misses left are
    explained; most need saves without gaps or an answer from Jason
    (`investigations/star-tail.md`).
  - Every engine rule has a ledger id (`tools/rule_levels.py`, run by `check.sh`):
    140 rules, 3 still unverified (embassy price, Market, Clathrus), all waiting
    on Jason's tests 36–38.
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

## Waiting on Jason

In-game tests are on the test sheet
(`docs/polytopia_open_questions_to_fill_in_while_playing.md`).

- **Round 3, item 40: Aquarion tech names.** Which id is Aquaculture, and what
  the tier-1 tech before Marine Life is called (backlog item 1).
- **Round 3, item 36: embassy price.** Note stars right before building one,
  right after, and at your next turn start. The saves say a net 4; Jason and the
  card say 5.
- **Round 3, items 37–38:** Market and Clathrus income.
- **Oceantology (Cymanti tech, save id 49):** its tier, from the tech card or a
  game where a one-city Cymanti researches it.
- **Round 2, items 26–34:** played games (calibration, Crazy-bot war, Easy and
  Normal bots, Solaris, special tribes).
- **New saves as he plays**, especially a game exported every turn: the bot war's
  4–6 turn gaps are what's left in the star misses.

## Decided

- **Notebook:** only Jason rebuilds `notebook/polytopia_engine.ipynb` (about
  400 KB, conflicts on nearly every merge otherwise). Minjae's PRs leave it alone.
