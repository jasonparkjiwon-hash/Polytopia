# Flagged rules and rule labelling

_Owner: polish-rules session · started 2026-10-23_

Goal: every rule the engine uses carries a ledger id and level; unseen rules are
switches with a best guess, marked unverified, so later simulations can flag moves
that rely on them.

## Done

1. **Rule audit.** `tools/rule_levels.py` finds every RULES / ECON_RULES switch,
   upper-case constant and action handler in `engine/replay.py` and
   `engine/economy.py`, plus hand-listed formula functions, and maps each to a
   ledger id (MAP in the script). Writes `data/rule_levels.json` (rule -> ledger,
   level, file:line, unverified). `--check` runs first in `check.sh` and fails on a
   rule with no id or an id missing from the ledger; it also notes when the json is
   out of date. New ledger ids: CITY-REWARDS, CAPTURE-TERRITORY, PROMOTE-HP,
   WATER-UNITS, ENGINE-RESYNC, ACTION-18-AFTER-MOVE, AQUARION-UNIT-IDS.
2. **Flagged switches** (each on/off holds 4709/4753 units, 770/819 stars):
   - replay `peace_break_disbands` (L0; 0 disbands in any save)
   - replay `break_ice_after_move_needs_dash`: legality check, counts in LOG only.
     Saves: 128/130 move-then-break are Dash units, 2 are a Raft (test item).
   - economy `ECON_RULES`: embassy_income, market_income, clathrus_income (last two untested),
     aquarion51_price = 5 (the saves DO test it: 4 gives 766 stars). embassy_income is tested
     since the stars session found embassies (action 30): off gives 778 vs 780.
3. **Ids found (Polyfish types.rs comments, L0):** tech 39 Aquaculture, 46 MarineLife,
   47 AquaFishing; units 46-55 MermaidWarrior, MermaidArcher, MermaidSwordsman,
   MermaidDefender, MermaidCloak, MermaidDagger, Jelly, Shark, Siren, Aquapult
   (positional; agrees with measured 46, 48 and inferred 53). Ledger only; not put
   in engine/state.py (economy prices 39/46/47 by id; no save holds the other units).

4. **Wiki cross-check** (search snippets only: fandom, breezewiki, archive.org and
   miraheze are all blocked here). Recorded in the ledger: 46 = Marine Life (unlocks
   Shark; all 29 Shark trainings follow it) -> L2, 53 = Shark -> L2; 47 is the tier-1
   slot (always first); wiki embassy (builder earns 2) and price 5 conflict with the
   saves; wiki Break Ice open to all but Mooni/Gaami; peace-break text = Jason's.
5. **Test list:** Round 3 (items 35-40) in the open-questions doc; status.md updated.

## Left for the orchestrator

- Engine names for techs 39/46/47 are not set (economy prices them by id; renaming
  would break `AQUARION_TIERS`). Units 47, 49-52, 54, 55 named in the ledger only.
- Delete this file once merged; conclusions are in the ledger.
