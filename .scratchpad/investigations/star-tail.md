# Star tail: 57 -> 17 star player-turns off (762 -> 802/819)

_Owner: polish-star session · started 2026-10-23_

Copy this file to `investigations/<short-name>.md` when starting a hunt. Update
it before clearing the chat, so a fresh chat can continue from here alone.
Delete it once the conclusion is in the ledger or `lessons.md`.

## Symptom

Which unit(s), at which checkpoint: expected vs what the engine gets.
The command that shows it:

```sh
python3 -I tools/miss.py --list
python3 -I tools/trace.py <game> <turnA> <turnB> x,y ...
```

## Tried

- `AQUARION_TIERS`: price tech ids 47 (tier 1), 39/46 (tier 2) by id (spend() now passes unknown ids through) → 762 -> 770. Kept.
- `ROUND_START_PAID`: a save right after the round-end EndTurn (player 255) already holds the round opener's income;
  a save b ending that way adds it → 770 -> 775 (af181c8f p1 -5/+5 pairs). Kept.
- `END_INCOME_FROM_B`: that opener income uses save b's cities (the log has CityReward without the level-up) → 778. Kept.
- `EMBASSY_ACTION30` + `TRACK_PEACE` + `EMBASSY_BUILDER_PAID=False`, cost 4 → 780. Kept (split with Jason's 5, see ledger EMBASSY-ACTION).
  Grid (before LEVEL_FROM_REWARD): cost 4/5/6 x builder paid yes/no: 779/780, 778/778, 779/778. Only 4/no fits both embassies.

- `LEVEL_FROM_REWARD`: city Level rises with each CityReward, not with action 21 (243/243 vs 0/201) → 780 -> 800. Kept.
  END_INCOME_FROM_B became redundant (800 either way) and was removed.
- `MARKET_BY_LEVEL`: a Market pays the level of each adjacent Windmill/Sawmill/Forge (af181c8f p14 t25) → 801. Kept.
- e15f392c t11->12 p5 -4: explained in part. p4 founded a city at (26,19); its border cut p5's water route
  (HasWaterRoute lost, ConnectedPlayerCapital 5 -> 0), so 3 p5 cities fell to -1 population before p5's turn
  (NEG_POP would take 3). The engine has no trade-route model; 1 star still unexplained. Left as is.
- Polarism (id 32) tier 3 → 802. Kept (ledger TRIBE-TECH-TIERS). Oceantology (id 49, 6e1bf8e0 p16 t11-15) left unpriced.
- `MEET_SCORE_AT_FIRSTMEET`: in 2+ turn gaps, interpolate the met tribe's score to Diplomacy FirstMeet → 803, but it
  only reshuffles misses (fixes bot-war rows, breaks 2 Cliff t2->4 rows and af t16->18); offsets -1/-0.5/+0.5/+1 give
  805/801/805/802. Reverted (noise, and it regresses the Cliff baseline).
- af181c8f t10->12: p9 +3 is a tribe destroyed mid-gap (no turns, stars irrelevant); p13 -2 is meet-score timing
  (p11's score crossed 3000 between the saves, and there is no t11 save).

## Ruled out

- Break Ice (action 18) paying stars: 77/78 single-turn rows with it are exact.

- Cost 5 for the embassy with any builder-income variant: leaves 09a5bf1e p1 and 6e1bf8e0 p12 both off by +-1.

- <idea> — <why>

## Current theory (802/819, 17 left, all accounted for but 4 stars)

- Bot war 6e1bf8e0 (13 rows): meet stars in 4-6 turn gaps. Every star row there without a meeting is exact, every
  miss is even, and each residual fits inside the range of meet stars the met tribes' scores allow between the two
  saves (checked row by row). Not fixable without saves in between (interpolating to FirstMeet only reshuffles).
- 6e1bf8e0 t11->15 p16 (-8): Oceantology (id 49, Cymanti) is unpriced; tier 1, 2 or 3 all fit with meet timing.
- af181c8f t10->12 p13 (-2): meet timing, 2-turn gap with no t11 save.
- af181c8f t10->12 p9 (+3): tribe destroyed by p5 at action 1082, no turns after; why its stars rose is unknown, and
  it doesn't matter for play.
- e15f392c t11->12 p5 (-4): trade route cut by p4's new city border (3 cities to -1 pop before p5's turn, -3);
  1 star unexplained. Would need a trade-route model (connections via roads/water routes inside own territory).

## Next step

- Ask Jason (in status.md): Oceantology's tier (in-game tech card, or a Cymanti game where it is researched with one
  city), and the embassy price check (5 per him and the card vs a net 4 in both saves).
- Optional: trade-route model (ConnectedPlayerCapital, HasWaterRoute) if more saves show connection losses.
- A new single-turn save series (no gaps) for any game would turn the bot-war meet rows into checks.

## Notes from the orchestrator (23 Oct)

- Kept: besieged capital loses the bot bonus (`BONUS_NEEDS_FREE_CAPITAL`), 754 -> 762.
- Ruled out: meet-star score timing. Variants max(before,after), after only,
  before-or-after, average all scored 726-730 vs 762 baseline.
- Five single-turn + misses left: 09a5bf1e t4->5 p1 (+2), t6->7 p1 (+1), t7->8 p7 (+2, met 3 tribes, a ruin);
  af181c8f t25->26 p14 (+2, Break Ice, city reward); e15f392c t4->5 p3 (+2, ruin, and tribes 11 and 13 newly met p3
  while p3's own Encountered list did not change). None has a new or negative-population city.
- City reward residual tally (single reward, one turn, no ruin): reward 1: 22 exact/1 off, 3: 51/1, 4: 26/1, 5: 10/1, 6: 5/0, 7: 13/0.
