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
- **6e1bf8e0 t11→15 p16 (-8):** Oceantology (id 49, Cymanti) is unpriced; tier
  1, 2 or 3 all fit once meet timing is allowed for. Asked Jason.
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

- When Jason answers: price Oceantology (TRIBE-TECH-TIERS) and settle the embassy
  price (EMBASSY-ACTION vs ECON-EMBASSY).
- A save every turn for any game would turn the meet rows into checks.
- Optional: trade-route model, if more saves show connection losses.
