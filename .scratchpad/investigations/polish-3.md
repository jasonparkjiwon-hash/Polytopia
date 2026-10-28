# polish-3 (28 Oct 2026)

_Owner: polish-3 · state: in progress_

## Polyfish before / after (tools/pf_miss.py)

| | units | stars | legal |
|---|---|---|---|
| before | 10169/10212 | 1937/1972 | 17753/17797 (99.8%) |
| after | 10179/10207 | 1938/1972 | 17755/17797 (99.8%) |

Held-out ed6cb932 unchanged: 187/187, 64/64. Referee unchanged: units 10183/10196, stars 1944/1972.

## Ported to sim/pfcore (each with a Rust test in v123_tests.rs, line in sim/README.md)

- MOTH-INFILTRATE: Moth treated like a Cloak (normal damage, used up, eggs = min(5, level)); not for a city its side lost (`ex_owners`).
- CENTIPEDE-CHAIN: loader links, grow on move, no re-shift on a second displacement. Rows left: 710ddb20 t13->14, t15->16, t17->18, t18->19 (segment ids/positions).
- CYMANTI-TECH-49: tier 2.
- FOREST-TEMPLE-PRICE and MEET-SCORE-TURN: not needed in Polyfish (no star miss there).

## Open

- Egg placement: real eggs (7,24),(9,25) around city (8,25), (10,6) around (11,7); Polyfish takes neighbours in list order. Unknown rule (random?).
- Referee misses not touched: game 8 IceArcher id70 (t7->8: a Rider hit that should kill a 5-HP IceArcher; the real unit lives with 4 HP, Rider has no retaliation damage), the rest of the list in `tools/miss.py --list`.

## Audit (28 Oct, `tools/rule_levels.py`)

158 engine rules labelled, 0 missing a ledger id. By level: L3 130, L2 14, L1 11, the rest are the three ENGINE-RESYNC tool entries.
Nothing is below L1. One entry is unverified by a save: ECON-EMBASSY (L1; price 5 stars, embassy price step). Test items for
"Waiting on Jason": none new (nothing here only Jason can settle that is not already listed there).
Many L3 rules rest on n=1 (egg/Dagger count and placement, Centipede chain growth, Moth exception); a second sample would
move them to L2 but changes no score today.

## Not done this session

Referee misses (13 units, 28 stars) were not reduced: the game 8 IceArcher (t7->8) is a Rider hit of 7 on a 5-HP archer that
the save shows alive with 4 HP, and no rule that fits was found in one sample. Other rows are the same open items listed in
`games-7-8.md` and `star-tail.md`.
