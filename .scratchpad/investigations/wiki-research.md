# wiki-research: answers to the open rule questions from wikis and sources

_Owner: wiki-research · 2026-10-27_

**Access:** polytopia.fandom.com, web.archive.org and other wiki hosts are refused by the container's egress proxy
(403 on CONNECT; WebFetch can't resolve them). Only WebSearch works, so wiki facts are search-engine summaries of the
fandom pages (undated, L0). Third-party sources in ext/ (Polyfish v105-era, PolyMod, calculator configs) have no
Atoll, Jelly unlock or Outpost-network info (Polyfish's Jelly is commented out).

| # | Question | Answer | Level | Accuracy |
|---|---|---|---|---|
| 1 | Sanctuary radius | wiki + Polyfish: adjacent animals in own territory; radius 1 vs 2 identical in miss.py (switch SANCTUARY_RADIUS) | L0/L1, saves can't separate | 0 |
| 2 | Atoll population | wiki infobox: 1 pop, 3 tiles through water/ocean/flooded; matches the +1 pop already in ATOLL-NETWORK | L3 (saves) + L0 | 0 (already modelled) |
| 3 | Outpost network | wiki: links Outposts within 5 ice tiles, +1 pop to capital and city, lost when disconnected; agrees with radius-2 fit | L3 + L0 | 0 (already modelled); ice-break disconnect still untested |
| 4 | Jelly tech | Navigation (wiki, replaces Bomber; saves hold Navigation but also other techs). Cymanti tech 49: wiki says Pescetism unlocks the Raychi; not applied | L1 | pf_miss Train legal +2 (1398 -> 1400) |
| 5 | Build 7 ocean -> water | not found. Waterways gives Flood (field/forest under the unit) and Bubbled; Puffer Drench floods a tile | open | - |
| 6 | Algae and land units | wiki: units without creep/fly stop on algae (even frozen) = current Polyfish | L0 | 0 |
| 7 | Infiltration tiles | no new source (unit-cards owns it) | - | - |
| 8 | Aquarion prices | wiki: Jelly 8, Shark 8, Mermaid Defender 3. Cards say 8/8/8. A/B: Defender 3 fits game 6 (stars 1512 -> 1514, Train legal +5); Jelly/Shark 3 or 5 worse | L0 conflict | stars +2, legal +5 |

Kept: Jelly unlock (pfcore technology.rs + test aquarion_navigation_trains_jelly), Mermaid Defender cost 3
(units.rs, flagged in ledger MERMAID-DEFENDER-COST as a conflict with Jason's card), SANCTUARY_RADIUS switch (1).
Still wanted from Jason: the Mermaid Defender train price on screen; the Build 7 ocean case.
