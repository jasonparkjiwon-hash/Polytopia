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
  - Polyfish's push rule fits: same direction as its last move (opposite for an enemy), otherwise toward the map centre.
  - The log doesn't record ruin rewards; the replay reads a ruin unit from the next save.
- **Boats:** the boat record always shows promotion 0. The passenger record keeps the veteran level.
- **Terrain changes outside the log:**
  - Mooni and Gaami freeze the water (and ocean) around them after moving or capturing, and freeze adjacent enemy units. Ice goes back to water only through Break Ice (action 18).
  - Aquarion flood (flag value 1): boats stay boats and walkers stay walkers.
  - Cymanti algae (value 4): walkable water.
  - Terrain is re-synced at checkpoints.
- **Healing:** +4 in own territory, +2 elsewhere. Territory is re-synced at checkpoints.
- **Fog:** explored tiles show enemies live. Only unexplored clouds hide them.

- **Saves can be mid-turn:** Jason exports during his own turn, sometimes after acting (af181c8f t14 holds his Attack and Train but not his EndTurn). The unit `Moved`/`Attacked` flags in the save tell which of his units already acted (`saved_acted` in `state.py`).
- **Push direction is hidden state:** the game keeps a unit's last move direction across turns (not in the save); a replay starting at a checkpoint reads it back from the log (`prime_last_moves`). Units trained that turn have no logged move and their push direction isn't predictable yet.
