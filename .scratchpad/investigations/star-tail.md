# Star tail: 57 → 17 star player-turns off (762 → 802/819)

_Owner: none (paused 2026-10-23; the rest waits on Jason or new saves)_

```sh
python3 -I tools/miss.py --list | grep star
```

## Where it stands (17 left, all explained except about 4 stars)

- **Bot war 6e1bf8e0 (13 rows):** stars for meeting a tribe, in 4–6 turn gaps.
  Every bot-war star row without a meeting is exact, every miss is even, and each
  fits within the meet stars the met tribes' scores allow between the two saves
  (checked row by row). Can't be fixed without saves in between.
- **6e1bf8e0 t11→15 p16 (-1):** Oceanology (id 49, Cymanti) is now priced tier 3
  from Jason's card (was -8); the -1 left is likely meet timing in the gap.
- **af181c8f t10→12 p13 (-2):** meet timing; 2-turn gap, no t11 save.
- **af181c8f t10→12 p9 (+3):** a tribe destroyed by p5 at action 1082 with no turns
  after. Doesn't matter for play.
- **e15f392c t11→12 p5 (-4):** p4's new city at (26,19) cut p5's water route
  (HasWaterRoute lost, ConnectedPlayerCapital 5 → 0), so 3 p5 cities fell to -1
  population before p5's turn (-3). 1 star unexplained. Needs a trade-route model
  (connections by road or water route inside own territory).

## Kept (all in `engine/economy.py`)

| Change | Stars |
|---|---|
| `BONUS_NEEDS_FREE_CAPITAL`: a besieged capital loses the bot bonus | 754 → 762 |
| `AQUARION_TIERS`: techs 47 tier 1, 39 and 46 tier 2, priced by id | → 770 |
| `ROUND_START_PAID`: a save right after the round-end EndTurn (player 255) already holds the round opener's income | → 775 |
| Embassies (`EMBASSY_ACTION30`, `TRACK_PEACE`, builder not paid, net cost 4) | → 780 |
| `LEVEL_FROM_REWARD`: city level rises with each CityReward, not with action 21 (243/243 vs 0/201) | → 800 |
| `MARKET_BY_LEVEL`: a Market pays the level of each adjacent Windmill/Sawmill/Forge | → 801 |
| Polarism (id 32) tier 3 | → 802 |

## Tried and reverted, or ruled out

- Meet-star score timing (max of before/after, after only, average): 726–730 vs 762.
- `MEET_SCORE_AT_FIRSTMEET` (interpolate the met tribe's score to Diplomacy
  FirstMeet in gaps): 803, but it only reshuffles misses and breaks Cliff t2→4.
- Embassy cost 5 with any builder-income variant: leaves 09a5bf1e p1 and 6e1bf8e0
  p12 off by ±1. Grid of cost 4/5/6 × builder paid or not: only 4/not paid fits both.
- Break Ice (action 18) paying stars: 77/78 single-turn rows with it are exact.

## Next step

- A save every turn for any game would turn the meet rows into checks.
- Optional: trade-route model, if more saves show connection losses.

## 28 Oct (later): rebellion found, five rows left (Jason: gaps between saves are not counted)

**Fixed: REBELLION-NO-INCOME** (referee stars 2057 -> 2062/2084; Polyfish 2046 -> 2052). A city whose save record has RebellionFlag 1 (an enemy Cloak/Scuba/Moth infiltrated it) pays nothing at its owner's next
income, and a rebelling capital also loses the bot bonus. Rows: 5d15d70f t6->7 p13 -5, 710ddb20 t17->18 p2 -7 and t9->10 p9 -2, 9906f7da t18->19 p1 -5, ac4b122a t10->11 p4 -1. Polyfish: `CityState.rebelling`
(loaded from RebellionFlag, set by infiltration, cleared after the owner's income; `get_city_production`, `get_bot_bonus`), test `infiltrated_city_pays_nothing`.

**Still open (5 rows), what was tried:**
- **9906f7da p9 t14->15 and t15->16 (-2 each):** p9 hosts Jason's embassy, rebuilt in two rounds in a row (actions 925, 1029). A rule "a new embassy pays its host from the host's next turn" fixes both but breaks three exact
  cases where the first turn WAS paid (9906f7da t6->7, t18->19; 09a5bf1e t7->8), so it is not the rule. Only 5 host first-turn cases exist (3 paid, 2 unpaid). Not separated by: host's Diplomacy tech
  (p9 was paid at t6 without it; a rule "host needs Diplomacy" breaks 9906f7da t6-12 and 710ddb20, 2062 -> 2046), LastAttackTurn, EmbassyBuildTurn, relation (all neutral), starfish harvests (price -8 is fine, 62 other harvest windows exact).
- **710ddb20 t16->17 p3 (+2):** p3 (Quetzali) infiltrated p2's capital (level 4) with a Cloak, captured a village and bought Archery (modelled 16 = tier 2 x 6 cities + 4; 14 would fit with 5 cities).
  A rule "a village captured this turn does not count for tech prices" fits this row but breaks ~130 others (2062 -> 1938), so no. Open: infiltration pay for a capital (6 instead of 4?) or a tech discount.
- **710ddb20 t18->19 p3 (-1):** p3 captured p2's capital (level 4, population -1). 64795ee3 t9->10 p12 (-1): captured a village. Both involve a capture in the window; not traced further.
Needs: more rows (a save every turn) before another hypothesis is worth testing; each one above is a single row.
