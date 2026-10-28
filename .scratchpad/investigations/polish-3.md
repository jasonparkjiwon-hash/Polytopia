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
