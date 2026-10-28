# web-deep: deeper research on the last engine misses

_Owner: web-deep · started 2026-10-28. Hosts: WebSearch works but gives thin snippets (Quetzali pirate, Polaris spawn: nothing). ext/ sources (`sh scripts/fetch_third_party.sh`) were the useful ones._

| # | Question | Answer | Level | Result |
|---|---|---|---|---|
| 1 | Quetzali Pirate -> Raft (710ddb20 t18->19) | **Solved.** A Dagger boarding a port/boat becomes a **Pirate** (10 HP, atk 2, Surprise, Carry; the Dagger rides as passenger), not a Raft. Save: t18 Dagger 469 moves (19,21)->(20,20) port, t19 save shows Pirate 550 with Dagger 469 aboard, attacked a Warrior without retaliation. Polyfish `actions/units.rs` embark: Cloak->Dinghy, Dagger->Pirate, Giant->Juggernaut, else Raft. Search found nothing. | L3 (save) + L0 (Polyfish) | units 10183 -> 10185/10195, no game worse (`RULES.dagger_pirate`, ledger PIRATE-BOARD) |
