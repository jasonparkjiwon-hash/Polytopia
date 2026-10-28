# Lessons

Engine and save-format knowledge already paid for. Read before changing
`engine/` or `verify/state_v123.py`, or when a replay mismatch looks familiar.
Add to it when a hunt turns up a gotcha worth remembering.

## Save format (v123), short version

- **Layout:** initial state | 7 bytes | current state | 2 bytes | action list | 9-byte trailer.
  - The trailer is 3 zero bytes, the hash and a u16 action count.
- **Player records:** the post-v114 layout plus one trailing tribe byte. Task types 1, 5 and 9 carry 6 bytes; the others 2.
- **Action sizes** (bytes after the u16 type) are in `ACTION_SIZES` in `verify/state_v123.py`.
- **Known action types:** 27 Offer Peace (needs Strategy); 28 peace reply (1 accept, 0 decline); 29 Break Peace (n=1); 38 Shaman Swarm (neighbours get extra movement, no attack bonus); 24 Boomchi Explode. Build type 30 is Enchant Animal. Type 18 is Break Ice (the ice around the acting unit becomes water again).
- **Start techs** appear only after StartMatch (see `data/measured_start.json`).

## Combat (confirmed by replay)

- aF = atk·hp/max; dF = def·hp/max·bonus.
- dmg = round_half_up(aF/(aF+dF)·atk·4.5).
- ret = round_half_up(dF/(aF+dF)·def·4.5). Retaliation counts the bonus.
- No retaliation if:
  - the attacker is out of the defender's range;
  - the defender's tribe can't see the attacker's tile (unexplored and out of current vision);
  - the attacker is a hidden Cloak;
  - Stiff (the defender) or Surprise (the attacker) applies.
- A Dagger still retaliates when attacked.
- A melee attacker moves in after a kill.
- **Defence bonus:**
  - 1.5 in its own city (Fortify units); 4 with walls.
  - 1.5 on forest with Archery, or on mountain with Climbing.
- Veteran +5 max HP; splash (Bomber) and explode hit each neighbour for half damage, floored.
- Poison halves defence, bonus included. Fungi poisons non-Cymanti units at end of turn.
- A Shaman converts like a Mind Bender (one sample: it also deals normal damage, with no retaliation).
- After a kill: a boat moving onto land drops its passenger. Land units don't follow into water. Sharks and Raychi don't follow onto dry land.

## Engine bookkeeping gotchas

- **Unit ids:**
  - Train doesn't record the new id. Temporary negative ids are rekeyed by position on the unit's first Move or Attack.
  - Boarding gives the boat a new id; the passenger gets its old id back on landing.
  - An upgrade gives a new id.
- **Forced spawns:** the Giant reward, Enchant and ruin units (spawned on the ruin tile) push the occupant to a neighbour.
  - Direction: the unit's facing, stored in the save (UnitDirection byte 2), which follows its last move. A unit with no move goes toward its attacker if it was attacked, otherwise toward the map centre (nearest of 8 by angle; new units face that way).
  - Blocked: try counter-clockwise first, then clockwise, widening. In the engine's grid order that's the *next* entry (the screen is mirrored). No open tile removes the unit.
  - Boarding an own port counts only as the first choice.
  - The log doesn't record ruin rewards; the replay reads a ruin unit from the next save. An unseen ruin unit is a veteran Swordsman.
- **Boats:** the boat record always shows promotion 0. The passenger record keeps the veteran level.
- **Terrain changes outside the log:**
  - Mooni and Gaami freeze the water (and ocean) around them after moving or capturing, and freeze adjacent enemy units. Ice goes back to water only through Break Ice (action 18).
  - Aquarion flood (flag value 1): boats stay boats and walkers stay walkers.
  - Cymanti algae (value 4): walkable water.
  - Terrain is re-synced at checkpoints.
- **Healing:** +4 in own territory, +2 elsewhere. Territory is re-synced at checkpoints.
- **Fog:** explored tiles show enemies live. Only unexplored clouds hide them.

- **Saves can be mid-turn:** Jason exports during his own turn, sometimes after acting (af181c8f t14 holds his Attack and Train but not his EndTurn). The unit `Moved`/`Attacked` flags in the save tell which of his units already acted (`saved_acted` in `state.py`).
- **Idle healing:** the human player's idle units (no move, no attack) heal at End Turn like Recover (not when poisoned). AI idle units don't in any save; turning it on for them adds 57 misses.
- **Polaris capture** freezes the water around the captured city at once (radius 1, not under units).
- **Moving onto a hidden Cloak** doesn't happen: the mover stays and the Cloak is revealed.
- **Giant/Juggernaut:** a Giant boarding its port becomes a Juggernaut and stomps; a Juggernaut follows a kill onto land (as a Giant, stomping), but not onto a mountain without Climbing.
- **`engine/stats.py`:** an inline `#` comment once swallowed the Exida, Larva and Moth rows. Check new rows actually load.

- **Boarding:** a Dagger that boards a port/boat becomes a Pirate (10 HP, atk 2, Surprise), the Dagger rides as passenger; Giant -> Juggernaut; others -> Raft (PIRATE-BOARD, L3).
- **Acting blocks the idle heal:** a city capture (type 7) and an examined ruin (type 14) count as the unit acting (CAPTURE-RUIN-ACT, L3).

## Economy gotchas

- Tech price = tier × cities + 4, tribe techs included.
- City level rises with each CityReward in the log, not with action 21.
- A save taken right after the round-end EndTurn (player 255) already holds the round opener's income.
- A besieged capital loses the bot star bonus.
- **Aquarion water ruin = new city:** examining an ocean ruin (improvement 2) turns it into the examiner's level-1 city; +1 star from the next income (RUIN-CITY, L3).
- **Prices from Jason (28 Oct):** Mermaid Defender 3 stars (the card's 8 is wrong); each embassy costs 2 stars more than the previous.
- **Meeting stars** 1+2*min(ceil(score/1000),5) is L3 (370/373 rows); don't re-tune it.
- **Settled, don't redo:** action 38 = Shaman Swarm; the g8 'Polaris IceArcher without a Train' is a fight miss, not a spawn; the web (devtrackers.gg, fandom) is unreachable except by WebSearch snippets: see investigations/web-deep.md before searching again.
- **Still open (see web-deep.md):** defender on a village/city tile survives a predicted kill (g8 t7->8, t9->10); infiltration tile order (Jason: city tile, forest/mountain by tech, plain, then water Pirates; direction loop from where the Cloak came, counter-clockwise first); Sanctuary spawn period.

## Tools worth knowing

- `tools/unit_hist.py <game> <turnA> id id ...`: every action touching those units between two saves, with attack numbers.
- `tools/rule_levels.py --check` (run by `check.sh`) fails if an engine rule has no ledger id. Add new switches to its MAP.