"""Shadow replay: apply a save's action list to its turn-0 state and compare with saved checkpoints.

Usage: python3 -I replay.py <final save json> <checkpoint save json> [more checkpoints...]
Each checkpoint is an earlier export of the same game; its action count says where to stop and compare."""
import sys, os, json, struct, math, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from stats import STATS
from state import State, Unit, UNIT, TECH, TERRAIN, BOATS, max_hp

FMT = {1: "<BHII", 2: "<BIIIII", 3: "<BII", 4: "<BII", 5: "<BHII", 6: "<BIIIII", 7: "<BIII", 8: "<BH", 9: "<BII", 11: "<BIIH",
       13: "<BII", 14: "<BII", 15: "<B", 16: "<BHII", 17: "<BII", 18: "<BII", 20: "<B", 21: "<BII", 24: "<BII", 25: "<BII",
       27: "<BIIB", 28: "<BBB", 29: "<BIIB", 30: "<BIIB", 38: "<BII"}

LAND_UNITS = {"Warrior", "Rider", "Archer", "Defender", "MindBender", "Swordsman", "Catapult", "Knight", "Cloak", "Dagger", "Giant",
              "Polytaur", "Mooni", "IceArcher", "BattleSled", "IceFortress", "Gaami", "Hexapod", "Kiton", "Shaman", "Exida", "Doomux",
              "Centipede", "Segment", "Larva", "SteamWagon", "SteamFortress", "Pyro", "AshArcher"}   # Aquarion units are amphibious/water: never embark
WATER_UNITS = {"Shark", "Raychi", "Puffer", "Jelly", "Crab"}   # MEASURED: seen only on water, flooded tiles or cities (Mermaid walks on land)
RULES = {   # one switch per line; A/B each in tools/miss.py before keeping a change
    'retaliation_uses_bonus': True,
    'melee_moves_in_on_kill': True,
    't18_disband': False,
    't18_break_ice': True,
    't24_explode': True,
    't38_swarm': True,
    't38_attack_boost': False,
    'mooni_freezes_units': True,
    'retaliation_needs_sight': True,
    'frozen_no_retaliation': True,
    'freeze_on_hit': True,
    'tribe_super_unit': True,
    'bridge_is_land': True,
    'stomp': True,
    'summon_promotion': True,
    'peace_spares_area_damage': True,
    'stiff_moves_in': True,
    'explode_poison': True,
    't4_heal': True,
    'stomp_poison': True,
    'port_boards': True,
    't17_freeze_area': True,
    'explode_round': 'round_then_half',
    'explode_round_by_type': {},
    'hidden_attacker_no_retaliation': True,
    'algae_is_land': True,
    'flood_keeps_form': True,
    'resync_terrain': True,
    'kill_move_lands': True,
    'push_polyfish': True,
    'push_needs_climbing': True,
    'ruin_unit': True,
    'mooni_freeze': True,
    'water_units_stay': True,
    'shaman_convert': True,
    'shaman_damage': True,
    'poison': True,
    'attack_splash': True,
    'poison_recover_cures': True,
    'mooni_freezes': ('Water', 'Ocean'),
    'freezers': ('Mooni', 'Gaami'),
    'giant_juggernaut': True,
    'port_kill_embark': True,
    'algae_keeps_boats': True,
    'push_onto_port': True,
    'no_cities_no_units': True,
    'ruin_unseen_swordsman': True,
    'kill_move_needs_climbing': True,
    'stiff_boat_lands': True,
    'stomp_on_kill_move': True,
    'push_dir_persists': True,
    'push_dir_round': True,
    'peace_break_disbands': True,       # UNVERIFIED (L0): no save has a broken peace with units inside the ex-ally's borders
    'break_ice_after_move_needs_dash': True,   # UNVERIFIED legality check (L0 in-game text): only counts violations in LOG
    'polaris_capture_freezes': True,
}
LOG = collections.Counter(); EVENTS = []

def dist(a, b): return max(abs(a[0] - b[0]), abs(a[1] - b[1]))

def stat(u):
    return STATS.get(u.type, {"hp": 10, "atk": 2, "def": 2, "skills": set(), "range": 1})

def defence_bonus(st, u):
    """1 normally; 1.5 on forest/mountain/water with the owner's tech, or in own city with Fortify; 4 behind city walls."""
    p = st.players.get(u.owner); techs = p.techs if p else set(); pos = (u.x, u.y); ter = st.terrain.get(pos)
    sk = stat(u)["skills"]
    if pos in st.city and st.city[pos] == u.owner and "fortify" in sk:
        return 4.0 if pos in st.wall else 1.5
    if ter == "Forest" and "Archery" in techs: return 1.5
    if ter == "Mountain" and "Climbing" in techs: return 1.5
    if ter in ("Water", "Ocean") and "Aquatism" in techs: return 1.5
    return 1.0

def rnd(x): return math.floor(x + 0.5 + 1e-9)

def explore(st, owner, x, y, r=1):
    """Tiles a tribe has explored grow as its units move or appear (vision radius 1; the save's explored set is the start)."""
    s = st.explored.setdefault(owner, set())
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1): s.add((x + dx, y + dy))

def sees(st, owner, q):
    """Explored tiles show enemies live (G3), so a tribe sees an attacker unless it stands on a tile the tribe never explored.
    What its units and cities see right now also counts: radius 1, or 2 for a Scout-skill unit or a unit on a mountain."""
    if not st.explored or q in st.explored.get(owner, ()): return True
    for u in st.units.values():
        if u.owner == owner:
            r = 2 if ("scout" in stat(u)["skills"] or st.terrain.get((u.x, u.y)) == "Mountain") else 1
            if dist((u.x, u.y), q) <= r: return True
    return any(o == owner and dist(c, q) <= 1 for c, o in st.city.items())

def fight(st, a, d):
    sa, sd = stat(a), stat(d)
    atk, dfn = sa["atk"] + (0.5 if getattr(a, "boosted", False) else 0), sd["def"]
    bonus = defence_bonus(st, d)
    if RULES["poison"] and POISON in d.effects: bonus *= 0.5   # Polyfish (v115 notes): poison halves defence, bonuses included
    af = atk * a.hp / a.max_hp; df = dfn * d.hp / d.max_hp * bonus; tot = af + df
    dmg = rnd(af / tot * atk * 4.5) if tot > 0 else 0
    ret = 0
    d_hp = d.hp - dmg
    unseen = RULES["retaliation_needs_sight"] and not sees(st, d.owner, (a.x, a.y))      # Jason's in-game test: no return fire from fog
    hidden = RULES["hidden_attacker_no_retaliation"] and "hide" in sa["skills"]        # Jason: a Cloak never takes retaliation
    frozen = RULES["frozen_no_retaliation"] and FROZEN in d.effects                   # MEASURED 09a5bf1e t7: a Frozen Warrior did not hit back
    if d_hp > 0 and not unseen and not hidden and not frozen and "stiff" not in sd["skills"] and "surprise" not in sa["skills"] and dist((a.x, a.y), (d.x, d.y)) <= sd.get("range", 1):
        dfr = df if RULES["retaliation_uses_bonus"] else dfn * d.hp / d.max_hp
        ret = rnd(dfr / tot * dfn * 4.5) if tot > 0 else 0
    return dmg, ret, bonus

def remove(st, u):
    st.units.pop(u.id, None)
    if st.at.get((u.x, u.y)) == u.id: st.at.pop((u.x, u.y))

def place(st, u, x, y):
    if st.at.get((u.x, u.y)) == u.id: st.at.pop((u.x, u.y))
    u.x, u.y = x, y; st.at[(x, y)] = u.id

def unit_at(st, x, y):
    i = st.at.get((x, y)); return st.units.get(i) if i is not None else None

DIRS = [(0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1)]
def sgn(v): return (v > 0) - (v < 0)

def push_target(st, u, actor):
    """Polyfish's push rule (functions.rs calculate_pushable_position): keep going the way the unit last moved this turn (or
    toward its last ranged attack target), reversed for an enemy of the acting player; a unit that hasn't moved goes toward the
    map centre. A blocked tile is skipped for the next direction either side, nearer the centre first."""
    x, y = u.x, u.y; cx, cy = st.W // 2, st.H // 2
    atk, frm = getattr(u, "last_attack", None), getattr(u, "last_from", None)
    if atk is not None and stat(u).get("range", 1) > 1: d = (sgn(atk[0] - x), sgn(atk[1] - y))
    elif frm is not None and frm != (x, y):
        vx, vy = x - frm[0], y - frm[1]; m = max(abs(vx), abs(vy))
        if RULES["push_dir_round"]: d = (sgn(vx) * (2 * abs(vx) > m), sgn(vy) * (2 * abs(vy) > m))   # MEASURED (6e1bf8e0 t11, e15f392c t13): a 2-tile move (-2,-1) pushes on (-1,0)
        else: d = (sgn(vx), sgn(vy))
    else: d = None
    if d is not None and u.owner != actor: d = (-d[0], -d[1])
    if d is None or d == (0, 0):
        d = (sgn(cx - x), sgn(cy - y))
        if d == (0, 0): d = (0, 1)
    k = DIRS.index(d); order = [DIRS[k]]
    for i in range(1, 5):
        a, b = DIRS[(k - i) % 8], DIRS[(k + i) % 8]
        if a == b: order.append(a); continue
        da = (x + a[0] - cx) ** 2 + (y + a[1] - cy) ** 2; db = (x + b[0] - cx) ** 2 + (y + b[1] - cy) ** 2
        if db < da or (db == da and abs(x + b[0] - y - b[1]) < abs(x + a[0] - y - a[1])): order += [b, a]
        else: order += [a, b]
    for dx, dy in order:
        q = (x + dx, y + dy)
        if q not in st.terrain or q in st.at: continue
        if u.type in LAND_UNITS and is_water(st, *q) and not (RULES["push_onto_port"] and q in st.port and st.owner.get(q) == u.owner): continue   # MEASURED (af181c8f t15, t21): its own port takes it, and it boards
        if u.type not in LAND_UNITS and u.type in BOATS and not is_water(st, *q): continue
        if RULES["push_needs_climbing"] and st.terrain.get(q) == "Mountain" and "Climbing" not in st.players[u.owner].techs and "fly" not in stat(u)["skills"]:
            continue                             # Polyfish is_steppable_for_push; MEASURED 09a5bf1e t6 (Cymanti, no Climbing)
        return q
    return None

TEMP = [0]
def spawn(st, owner, name, x, y):
    """New unit whose real id the log doesn't give: temporary negative id until its first Move/Attack names it."""
    TEMP[0] -= 1; u = Unit(TEMP[0], owner, name, x, y, 0, 0); u.max_hp = max_hp(u); u.hp = u.max_hp
    old = unit_at(st, x, y)
    if old is not None:                          # forced spawn pushes the occupant to a neighbouring tile
        LOG["spawn on occupied tile (push)"] += 1
        q = push_target(st, old, owner) if RULES["push_polyfish"] else None
        if q is None and not RULES["push_polyfish"]:
            free = [(x + dx, y + dy) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if (dx or dy) and (x + dx, y + dy) in st.terrain and (x + dx, y + dy) not in st.at]
            land = [q for q in free if st.terrain[q] not in ("Water", "Ocean")]
            q = (land or free or [None])[0]
        if q is not None: enter(st, old, x, y, *q); EVENTS.append(("push", old.id, (x, y), q))
        else: st.at.pop((x, y), None)
    st.units[u.id] = u; st.at[(x, y)] = u.id; explore(st, owner, x, y)
    return u

RUIN = {}     # (owner, x, y) -> [(created turn, unit type, promotion)]: units a checkpoint shows standing where a ruin was examined
ORACLE = {}   # unit id -> (owner, type, promotion) from any saved checkpoint, for units spawned by events the log doesn't spell out
RUIN_SEEN = {}   # (owner, x, y) -> turn: ruins examined with no checkpoint showing the reward (it may be a unit that died before the next save)

def summon(st, uid, owner, x, y):
    o = ORACLE.get(uid); name = o[1] if o else "Warrior"
    if o is None and RULES["ruin_unseen_swordsman"] and (owner, x, y) in RUIN_SEEN:   # MEASURED 6e1bf8e0 t8-10: unit 165 first moved off a ruin
        o = (owner, "Swordsman", 1); LOG["ruin unit (inferred)"] += 1                  # XinXi examined; only a veteran Swordsman fits its fights
    u = Unit(uid, owner, name if o is None else o[1], x, y, 0, 0)
    if o and RULES["summon_promotion"]: u.promotion = o[2]   # e.g. a ruin's veteran Swordsman (MEASURED af181c8f t16: 20 max HP)
    u.max_hp = max_hp(u); u.hp = u.max_hp
    st.units[uid] = u; st.at[(x, y)] = uid; st.max_unit_id = max(st.max_unit_id, uid); LOG["spawned unseen unit"] += 1
    return u

def locate(st, uid, x, y, owner):
    """Return the unit with this id, standing at (x, y). Fixes pushes and spawns the log doesn't record."""
    u = st.units.get(uid)
    if u is not None and (u.x, u.y) == (x, y): return u
    here = unit_at(st, x, y)
    if u is not None and (here is None or here.id == uid):
        place(st, u, x, y); LOG["teleported (push/unlogged move)"] += 1; return u
    if here is not None and here.owner == owner and (here.id < 0 or uid not in ORACLE):
        return rekey(st, here, uid)
    if here is not None:
        # someone else stands where the save says uid is: the engine's occupant must have been pushed away; keep it, but off-map
        LOG["occupant displaced"] += 1; st.at.pop((x, y), None)
    if u is not None:
        place(st, u, x, y); return u
    return summon(st, uid, owner, x, y)

def rekey(st, u, uid):
    """The save names units by id; if the unit on the tile carries a different id in the engine, adopt the save's id."""
    if u.id == uid: return u
    other = st.units.pop(uid, None)
    if other is not None and st.at.get((other.x, other.y)) == uid: st.at.pop((other.x, other.y))
    st.units.pop(u.id, None); u.id = uid; st.units[uid] = u; st.at[(u.x, u.y)] = uid; LOG["rekeyed"] += 1
    return u

def is_water(st, x, y):
    if RULES["bridge_is_land"] and (x, y) in st.bridge: return False   # MEASURED af181c8f t22-23: land units cross a bridge on foot
    return st.terrain.get((x, y)) in ("Water", "Ocean") and not (RULES["algae_is_land"] and st.flood.get((x, y)) == 4)

def enter(st, u, x0, y0, x1, y1):
    """Step u from (x0, y0) onto (x1, y1): a land unit entering water boards a Raft, a boat reaching land drops its passenger."""
    ter = st.terrain.get((x1, y1)); ter0 = st.terrain.get((x0, y0))
    water = ("Water", "Ocean")
    if RULES["algae_is_land"]:                     # MEASURED (e15f392c): land units stand on Cymanti algae (flood value 4) unboarded
        if st.flood.get((x1, y1)) == 4: ter = "Field"
        if st.flood.get((x0, y0)) == 4: ter0 = "Field"
    if RULES["bridge_is_land"] and u.type not in BOATS:  # a bridge carries land units; boats still pass under it as water
        if (x1, y1) in st.bridge: ter = "Field"
        if (x0, y0) in st.bridge: ter0 = "Field"
    if RULES["algae_keeps_boats"] and st.flood.get((x1, y1)) == 4 and u.type in BOATS:
        pass                                     # MEASURED (af181c8f t22, t25): a boat moving onto Cymanti algae stays a boat, passenger aboard
    elif RULES["flood_keeps_form"] and st.flood.get((x1, y1)) == 1 and ter not in water and (x1, y1) not in st.city and not (RULES["port_boards"] and (x1, y1) in st.port and st.owner.get((x1, y1)) == u.owner and u.type in LAND_UNITS):
        pass                                     # MEASURED: on Aquarion-flooded land a boat stays a boat and a land unit stays on foot (a city is plain land)
    elif (ter in water or (RULES["port_boards"] and (x1, y1) in st.port and st.owner.get((x1, y1)) == u.owner and ter != "Ice")) and ter0 not in water and u.type in LAND_UNITS and u.type not in BOATS:
        u.passenger = u.type                         # a land unit stepping into water becomes a Raft; MEASURED (af181c8f): a Giant becomes a Juggernaut
        u.type = "Juggernaut" if RULES["giant_juggernaut"] and u.type == "Giant" else "Raft"
        if RULES.get("boat_new_id", True):            # MEASURED: the boat is a new unit id; the passenger keeps its own id
            u.passenger_id = u.id; TEMP[0] -= 1; st.units.pop(u.id, None)
            if st.at.get((u.x, u.y)) == u.id: st.at[(u.x, u.y)] = TEMP[0]
            u.id = TEMP[0]; st.units[u.id] = u
    elif ter not in water and u.type in BOATS and u.passenger:
        u.type = u.passenger; u.passenger = None    # disembark
        pid = getattr(u, "passenger_id", None)
        if pid is not None and RULES.get("boat_new_id", True) and pid not in st.units:   # MEASURED: the unit gets its old id back
            st.units.pop(u.id, None)
            if st.at.get((u.x, u.y)) == u.id: st.at[(u.x, u.y)] = pid
            u.id = pid; st.units[pid] = u; u.passenger_id = None
    place(st, u, x1, y1)

PREV = [None]
POISON = 1   # UnitEffect enum
FROZEN, SWIFT = 0, 6
_sk = {k: " ".join(v.get("skills") or ()).lower() for k, v in json.load(open(os.path.join(HERE, "..", "data", "units.json")))["units"].items()}
_sk.update({k: str(v.get("skills", "")).lower() for k, v in json.load(open(os.path.join(HERE, "..", "data", "measured_ui.json")))["units"].items()})   # v123 cards win
_sk.update({"Rammership": _sk.get("Rammer", ""), "Scoutship": _sk.get("Scout", "")})
DASH = {k for k, v in _sk.items() if "dash" in v}   # legality checks only (break_ice_after_move_needs_dash)
SUPER_UNIT = {"Polaris": "Gaami", "Aquarion": "Crab", "Elyrion": "DragonEgg", "Cymanti": "Centipede"}

def add_effect(u, e):
    if e not in u.effects: u.effects = list(u.effects) + [e]

def hostile(st, a, b):
    """Different tribes not at peace (Polyfish get_true_enemy_at). MEASURED af181c8f t25: an Ai-Mo Stomp left an Imperius Defender
    (at peace) untouched."""
    return a != b and not (RULES["peace_spares_area_damage"] and frozenset((a, b)) in st.peace)

def stomp(st, u, old):
    """Polyfish move_unit Stomp: after moving, every adjacent enemy takes half the normal attack damage, floored (MEASURED af181c8f t25:
    an Ai-Mo Juggernaut landing next to three wounded Oumaji units killed them with no logged attack)."""
    sa = STATS[old]
    for d in [e for e in st.units.values() if hostile(st, e.owner, u.owner) and dist((e.x, e.y), (u.x, u.y)) == 1 and st.at.get((e.x, e.y)) == e.id]:
        af = sa["atk"] * u.hp / u.max_hp; df = stat(d)["def"] * d.hp / d.max_hp * defence_bonus(st, d); tot = af + df
        d.hp -= math.floor(rnd(af / tot * sa["atk"] * 4.5) / 2) if tot > 0 else 0
        if d.hp <= 0: remove(st, d)
        elif RULES["stomp_poison"] and "poison" in sa["skills"]: add_effect(d, POISON)   # Polyfish: a Poison stomper (Living Island) poisons too
        LOG["stomp"] += 1

def mooni_freeze(st, x, y, owner=None):
    """MEASURED (e15f392c, 4/4 cases): right after a Mooni moves or captures, the water around it is ice, so land units walk on it.
    MEASURED (af181c8f): ocean freezes too (45 of 70 new ice tiles were ocean; 61 of the 70 were next to a Mooni or Gaami)."""
    if not RULES["mooni_freeze"]: return
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            q = (x + dx, y + dy)
            if st.terrain.get(q) in RULES["mooni_freezes"] and q not in st.at:
                st.ice_from[q] = st.terrain[q]; st.terrain[q] = "Ice"
            e = unit_at(st, *q)                  # Jason in game + Polyfish freeze_area: adjacent enemy units are Frozen (saves: 3 of 4 frozen units sit next to an enemy Mooni)
            if RULES["mooni_freezes_units"] and e is not None and owner is not None and e.owner != owner and q != (x, y): add_effect(e, FROZEN)

def apply(st, a, turn):
    t = a["type"]; b = bytes.fromhex(a["raw"]); f = FMT.get(t)
    v = struct.unpack(f, b) if f else (b[0],)
    pl = v[0]
    if PREV[0] == 15 and pl != 255:              # a new player's turn: their units' moved/attacked marks reset
        for u in st.units.values():
            if u.owner == pl:
                if not RULES["push_dir_persists"]: u.last_from = None; u.last_attack = None
                u.thaw = FROZEN in u.effects     # frozen before this turn: it sits this turn out, then thaws at its end
    if t == 15 and RULES["frozen_no_retaliation"]:
        for u in st.units.values():
            if u.owner == pl and getattr(u, "thaw", False): u.effects = [e for e in u.effects if e != FROZEN]; u.thaw = False
    PREV[0] = t
    if t == 15 and RULES["poison"]:              # Polyfish process_end_turn_effects: Fungi poisons non-Cymanti units of other owners on it
        for q, owner in st.fungi.items():
            u = unit_at(st, *q)
            if u and u.owner != owner and st.players.get(u.owner) and st.players[u.owner].tribe != "Cymanti": add_effect(u, POISON)
    if t == 6:                                   # Move
        _, x0, y0, x1, y1, uid = v
        u = locate(st, uid, x0, y0, pl)
        old = u.type                             # Stomp uses the type before the move (a Juggernaut that lands as a Giant still stomps)
        enter(st, u, x0, y0, x1, y1); u.last_from = (x0, y0); explore(st, u.owner, x1, y1)
        if RULES["stomp"] and "stomp" in STATS.get(old, {}).get("skills", ()): stomp(st, u, old)
        if u.type in RULES["freezers"]: mooni_freeze(st, x1, y1, u.owner)
    elif t == 2:                                 # Attack
        _, uid, ox, oy, tx, ty = v
        at = locate(st, uid, ox, oy, pl)
        df = unit_at(st, tx, ty)
        if df is None and RULES.get("recover_lost_defender", False):
            near = [u for u in st.units.values() if u.owner != pl and dist((u.x, u.y), (tx, ty)) <= 3 and st.at.get((u.x, u.y)) == u.id]
            if near:
                df = min(near, key=lambda u: dist((u.x, u.y), (tx, ty))); place(st, df, tx, ty); LOG["defender recovered by proximity"] += 1
        if at is None or df is None:
            LOG["attack: missing " + ("attacker" if at is None else "defender")] += 1; return
        if at.type == "MindBender" or (RULES["shaman_convert"] and at.type == "Shaman"):   # Convert (Shaman: Polyfish + e15f392c t9)
            if at.type == "Shaman" and RULES["shaman_damage"]:   # MEASURED (n=1, e15f392c t9): the Shaman also deals its normal damage, no retaliation
                dmg, _, _ = fight(st, at, df); df.hp -= dmg
                if df.hp <= 0: remove(st, df); return
            df.owner = at.owner; LOG["convert"] += 1; EVENTS.append(("convert", turn, at.type, df.type)); return
        dmg, ret, bonus = fight(st, at, df); at.boosted = False; at.last_attack = (tx, ty)
        if RULES["attack_splash"] and "splash" in stat(at)["skills"]:   # Polyfish: enemies next to the target take half their own damage, floored
            for e in [u for u in st.units.values() if hostile(st, u.owner, at.owner) and u is not df and dist((u.x, u.y), (tx, ty)) == 1 and st.at.get((u.x, u.y)) == u.id]:
                sd = math.floor(fight(st, at, e)[0] / 2); e.hp -= sd
                if RULES["poison"] and "poison" in stat(at)["skills"]: add_effect(e, POISON)
                if e.hp <= 0: remove(st, e)
                LOG["splash"] += 1
        EVENTS.append(("attack", turn, at.id, at.type, at.hp, df.id, df.type, df.hp, bonus, dmg, ret, st.terrain.get((tx, ty))))
        df.hp -= dmg
        if RULES["poison"]:                      # Polyfish: a poison attacker poisons its target; a poison defender poisons a contact attacker
            if df.hp > 0 and "poison" in stat(at)["skills"]: add_effect(df, POISON)
            if df.hp > 0 and ret > 0 and "poison" in stat(df)["skills"] and dist((ox, oy), (tx, ty)) <= 1: add_effect(at, POISON)
        if RULES["freeze_on_hit"] and df.hp > 0 and "freeze" in stat(at)["skills"]: add_effect(df, FROZEN)   # Ice Archer (Freeze skill)
        if df.hp <= 0:
            remove(st, df); at.xp += 1
            if RULES["melee_moves_in_on_kill"] and dist((ox, oy), (tx, ty)) == 1 and ("stiff" not in stat(at)["skills"] or (RULES["stiff_moves_in"] and at.type in BOATS and (is_water(st, tx, ty) or RULES["stiff_boat_lands"]))) and stat(at).get("range", 1) == 1:
                if not RULES["kill_move_lands"]: place(st, at, tx, ty)
                elif RULES["kill_move_needs_climbing"] and st.terrain.get((tx, ty)) == "Mountain" and (at.type in LAND_UNITS or at.type in BOATS) and "Climbing" not in st.players[at.owner].techs and "fly" not in stat(at)["skills"]:
                    pass                                 # MEASURED 6e1bf8e0 t10: a Luxidoor Giant (no Climbing) killed a unit on a mountain and stayed put
                elif at.type in LAND_UNITS and is_water(st, tx, ty) and not (RULES["port_kill_embark"] and (tx, ty) in st.port and st.owner.get((tx, ty)) == at.owner):
                    pass                                 # a land unit doesn't follow a kill into water, except onto its own port, where it boards (MEASURED: 4/4 own port, 0/2 enemy port)
                elif RULES["water_units_stay"] and at.type in WATER_UNITS and not (is_water(st, tx, ty) or (tx, ty) in st.flood or (tx, ty) in st.city):
                    pass                                 # MEASURED (e15f392c t9): a Shark doesn't follow a kill onto dry land
                else:
                    old_type = at.type
                    enter(st, at, at.x, at.y, tx, ty)    # MEASURED (e15f392c t15): a boat moving in onto land drops its passenger
                    if RULES["stomp_on_kill_move"] and "stomp" in STATS.get(old_type, {}).get("skills", ()): stomp(st, at, old_type)   # MEASURED 6e1bf8e0 t13
        else:
            at.hp -= ret
            if at.hp <= 0: remove(st, at)
    elif t == 5:                                 # Train
        _, ut, x, y = v
        spawn(st, pl, UNIT.get(ut, f"unit{ut}"), x, y)
    elif t == 16:                                # Upgrade (boat)
        _, ut, x, y = v
        u = unit_at(st, x, y)
        if u:                                    # an upgraded boat gets a new id in the save: give it a temp id until named
            TEMP[0] -= 1; st.units.pop(u.id, None); u.id = TEMP[0]; st.units[u.id] = u; st.at[(x, y)] = u.id
            u.type = UNIT.get(ut, f"unit{ut}")
    elif t == 13:                                # Promote: +5 max HP, full heal
        _, x, y = v; u = unit_at(st, x, y)
        if u: u.promotion += 1; u.max_hp = max_hp(u); u.hp = u.max_hp
    elif t == 3:                                 # Recover: +4 in own territory, +2 elsewhere
        _, x, y = v; u = unit_at(st, x, y)
        if u and RULES["poison_recover_cures"] and POISON in u.effects: u.effects = [e for e in u.effects if e != POISON]
        elif u: u.hp = min(u.max_hp, u.hp + (4 if st.owner.get((x, y)) == u.owner else 2))
    elif t == 1:                                 # Build (only unit-spawning builds matter for combat)
        _, imp, x, y = v
        if imp == 30: spawn(st, pl, "Polytaur", x, y); LOG["enchant animal"] += 1
        if imp == 8: st.port.add((x, y))
        if imp == 48: st.bridge.add((x, y))
    elif t == 4 and RULES["t4_heal"]:            # Heal Others (Mind Bender): friendly units next to it +4 HP, capped
        _, x, y = v                              # MEASURED af181c8f t7: an Ai-Mo Warrior at 7 HP next to (25,18) was at 10 next turn
        for u in list(st.units.values()):
            if u.owner == pl and dist((u.x, u.y), (x, y)) == 1: u.hp = min(u.max_hp, u.hp + 4)
        LOG["heal others"] += 1
    elif t == 17 and RULES["t17_freeze_area"]:   # Freeze Area (Polaris; Polyfish freeze_area): water around turns to ice, enemies frozen
        _, x, y = v; mooni_freeze(st, x, y, pl); LOG["freeze area"] += 1
    elif t == 28:                                # peace reply: 1 = accepted
        p1, p2, flag = v
        if flag == 1: st.peace.add(frozenset((p1, p2)))
    elif t == 29:                                # break peace
        _, x, y, other = v; st.peace.discard(frozenset((pl, other)))
        if RULES["peace_break_disbands"]:        # Jason's pasted summary (L0): the breaker's units inside the ex-ally's borders are disbanded
            for u in [u for u in st.units.values() if u.owner == pl and st.owner.get((u.x, u.y)) == other]: remove(st, u); LOG["peace-break disband"] += 1
    elif t == 7 and RULES.get("territory", True):  # Capture: the city's tile and the 8 around it become the captor's (unowned or owned by the old owner)
        _, uid, x, y = v; old = st.city.get((x, y))
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                q = (x + dx, y + dy)
                if q in st.terrain and st.owner.get(q) in (0, old, None): st.owner[q] = pl
        st.city[(x, y)] = pl
        if RULES["no_cities_no_units"] and old and old != pl and old not in st.city.values():   # MEASURED (af181c8f t10): Kickoo lost its last city
            for u in [u for u in st.units.values() if u.owner == old]: remove(st, u)          # and its remaining units were gone by the next save
            LOG["tribe destroyed"] += 1
        cu = st.units.get(uid)
        if cu is not None and cu.type in RULES["freezers"]: mooni_freeze(st, x, y, pl)
        if RULES["polaris_capture_freezes"] and st.players.get(pl) and st.players[pl].tribe == "Polaris":
            for dy in (-1, 0, 1):                # MEASURED af181c8f t13: a Battle Sled took a city and the water around it was ice
                for dx in (-1, 0, 1):            # the same turn (a Warrior then walked onto it on foot)
                    q = (x + dx, y + dy)
                    if st.terrain.get(q) in RULES["mooni_freezes"] and st.owner.get(q) == pl and q not in st.at:
                        st.ice_from[q] = st.terrain[q]; st.terrain[q] = "Ice"
    elif t == 7:                                 # Capture village/city
        _, uid, x, y = v; st.city[(x, y)] = pl
    elif t == 8:                                 # Research
        _, tech = v
        if pl in st.players: st.players[pl].techs.add(TECH.get(tech, tech))
    elif t == 11:                                # City reward
        _, x, y, rw = v
        if rw == 1: st.wall.add((x, y))
        if rw == 5 and RULES.get("territory", True):   # Border growth: radius 2 around the city
            for dy in range(-2, 3):
                for dx in range(-2, 3):
                    q = (x + dx, y + dy)
                    if q in st.terrain and st.owner.get(q) in (0, None): st.owner[q] = pl
        if rw == 6:                              # Super unit, forced spawn: the tribe's own (Polyfish get_super_unit; Polaris Gaami MEASURED af181c8f t24)
            tribe = st.players[pl].tribe if pl in st.players else None
            spawn(st, pl, SUPER_UNIT.get(tribe, "Giant") if RULES["tribe_super_unit"] else "Giant", x, y)
    elif t == 14 and RULES["ruin_unit"]:         # Examine ruins: the reward isn't logged; a unit reward (veteran Swordsman seen twice)
        _, x, y = v                              # spawns on the ruin tile and pushes the explorer. Read it back from the checkpoints.
        hit = [r for r in RUIN.get((pl, x, y), ()) if r[0] == turn]
        if hit:
            _, name, promo = hit[0]; u = spawn(st, pl, name, x, y)
            if promo: u.promotion = promo; u.max_hp = max_hp(u); u.hp = u.max_hp
            LOG["ruin unit"] += 1
        else: LOG["ruin (no unit)"] += 1; RUIN_SEEN[(pl, x, y)] = turn
    elif t == 18 and RULES["t18_break_ice"]:     # Break Ice (Jason's in-game text; 91/92 uses had ice next to the unit): the ice around
        _, x, y = v                              # the acting unit turns back to water or ocean, except under a unit
        u = unit_at(st, x, y)                    # Jason's in-game text: breaking ice uses the unit's action, so only a Dash unit can move first
        if RULES["break_ice_after_move_needs_dash"] and u is not None and getattr(u, "last_from", None) is not None and u.type not in DASH:
            LOG["moved, then broke ice, no Dash"] += 1; LOG["no-dash ice breaker " + u.type] += 1
        elif u is not None and getattr(u, "last_from", None) is not None: LOG["moved, then broke ice (Dash)"] += 1
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                q = (x + dx, y + dy)
                if st.terrain.get(q) == "Ice" and q not in st.at:
                    st.terrain[q] = getattr(st, "ice_from", {}).get(q, "Water"); LOG["ice broken"] += 1
    elif t == 18 and RULES["t18_disband"]:       # Disband (inferred)
        _, x, y = v; u = unit_at(st, x, y)
        if u and u.owner == pl: remove(st, u); LOG["disband"] += 1
    elif t == 38 and RULES["t38_swarm"]:         # Swarm (Shaman): adjacent friendly units get extra movement (Swift), no attack bonus
        _, x, y = v                              # Jason in game; the save shows Swift (UnitEffect 6); Polyfish v115 notes: Boost became Swarm
        for u in list(st.units.values()):
            if u.owner == pl and dist((u.x, u.y), (x, y)) == 1:
                add_effect(u, SWIFT)
                if RULES["t38_attack_boost"]: u.boosted = True   # the old +0.5 attack reading, kept as a switch for A/B
        LOG["swarm"] += 1
    elif t == 24 and RULES["t24_explode"]:       # Explode: the unit dies; adjacent enemies take half damage (floored)
        _, x, y = v; u = unit_at(st, x, y)
        if u and u.owner == pl:
            sa = stat(u)
            for d in list(st.units.values()):
                if hostile(st, d.owner, pl) and dist((d.x, d.y), (x, y)) == 1 and st.at.get((d.x, d.y)) == d.id:
                    af = sa["atk"] * u.hp / u.max_hp; df = stat(d)["def"] * d.hp / d.max_hp * defence_bonus(st, d); tot = af + df
                    raw = af / tot * sa["atk"] * 4.5 if tot > 0 else 0
                    dmg = {"round_then_half": lambda: math.floor(rnd(raw) / 2), "half_then_round": lambda: rnd(raw / 2),
                           "floor_half": lambda: math.floor(raw / 2), "floor_third": lambda: math.floor(raw / 3)}[
                              RULES["explode_round_by_type"].get(u.type, RULES["explode_round"])]()
                    d.hp -= dmg
                    if RULES["explode_poison"] and d.hp > 0: add_effect(d, POISON)   # Polyfish explode + af181c8f t25 (every target poisoned)
                    if d.hp <= 0: remove(st, d)
            remove(st, u); LOG["explode"] += 1
    else:
        LOG[f"unhandled type {t}"] += 1

def prime_last_moves(st, acts, upto):
    """push_dir_persists: a unit's last move direction carries over turns (MEASURED af181c8f t4: a ruin Swordsman pushed a Warrior
    on in the direction it had walked the turn before). A replay that starts at a checkpoint reads it back from the action log."""
    if not RULES["push_dir_persists"]: return
    last = {}
    for a in acts[:upto]:
        if a["type"] == 6:
            _, x0, y0, x1, y1, uid = struct.unpack(FMT[6], bytes.fromhex(a["raw"])); last[uid] = ((x0, y0), (x1, y1))
    for u in st.units.values():
        m = last.get(u.id)
        if m and m[1] == (u.x, u.y): u.last_from = m[0]

def snapshot_units(d):
    out = {}
    for y, row in enumerate(d["currentTiles"]):
        for x, t in enumerate(row):
            u = t.get("Unit")
            if u: out[u["Id"]] = (u["Owner"], UNIT.get(u["UnitType"], u["UnitType"]), x, y, u["Health"] / 10, u["PromotionLevel"])
    return out

def compare(st, d):
    snap = snapshot_units(d); mine = {u.id: (u.owner, u.type, u.x, u.y, u.hp, u.promotion) for u in st.units.values()}
    for tid in [i for i in mine if i < 0]:          # temp ids: pair with the saved unit on the same tile
        m = mine[tid]
        for i, sv in snap.items():
            if (sv[0], sv[2], sv[3]) == (m[0], m[2], m[3]) and i not in mine:
                mine[i] = mine.pop(tid); break
    res = collections.Counter(); bad = []
    for i, s in snap.items():
        m = mine.get(i)
        if m is None: res["missing in engine"] += 1; bad.append(("missing", i, s)); continue
        if m[1] != s[1] and not (m[1] in BOATS and s[1] in BOATS): res["type differs"] += 1; bad.append(("type", i, s, m))
        if (m[2], m[3]) != (s[2], s[3]): res["position differs"] += 1; bad.append(("pos", i, s, m))
        if m[0] != s[0]: res["owner differs"] += 1; bad.append(("owner", i, s, m))
        if abs(m[4] - s[4]) > 1e-6: res["HP differs"] += 1; bad.append(("hp", i, s, m))
        else: res["HP exact"] += 1
    for i in mine:
        if i not in snap: res["extra in engine (should be dead)"] += 1; bad.append(("extra", i, mine[i]))
    return res, bad

def add_ruin_oracle(d):
    for row in d["currentTiles"]:
        for t in row:
            u = t.get("Unit")
            if u and u["CreatedTurn"] == d["currentTurn"] - 1:   # still on its spawn tile: units can't move the turn they appear
                RUIN.setdefault((u["Owner"], u["cx"], u["cy"]), set()).add((u["CreatedTurn"], UNIT.get(u["UnitType"], u["UnitType"]), u["PromotionLevel"]))

def run(final, checkpoints):
    D = json.load(open(final)); st = State(D, "initial"); acts = D["actions"]
    for c in list(checkpoints) + [final]:
        cd = json.load(open(c))
        for i, v in snapshot_units(cd).items(): ORACLE.setdefault(i, (v[0], v[1], v[5]))
        add_ruin_oracle(cd)
    cps = sorted(((len(json.load(open(c))["actions"]), c) for c in checkpoints))
    turn = 0; k = 0; reports = []
    for i, a in enumerate(acts):
        while k < len(cps) and i == cps[k][0]:
            cd = json.load(open(cps[k][1])); res, bad = compare(st, cd); reports.append((cps[k][1], i, res, bad)); k += 1
            if RULES.get("resync_territory", True):     # borders are read back from each checkpoint (they are not under test here)
                for yy, row in enumerate(cd["currentTiles"]):
                    for xx, tt in enumerate(row): st.owner[(xx, yy)] = tt["Owner"]
            if RULES["resync_terrain"]:                  # ice (Mooni freeze, melts again), Aquarion flood and Cymanti algae change outside the log
                st.flood = {}; st.fungi = {}; st.port = set(); st.bridge = set()
                for yy, row in enumerate(cd["currentTiles"]):
                    for xx, tt in enumerate(row):
                        if tt.get("ImprovementExists") and tt["ImprovementType"] == 37: st.fungi[(xx, yy)] = tt["Owner"]
                        if tt.get("ImprovementExists") and tt["ImprovementType"] == 8: st.port.add((xx, yy))
                        if tt.get("ImprovementExists") and tt["ImprovementType"] == 48: st.bridge.add((xx, yy))
                        st.terrain[(xx, yy)] = TERRAIN.get(tt["Terrain"], tt["Terrain"])
                        if tt.get("FloodedFlag"): st.flood[(xx, yy)] = tt.get("FloodedValue", 1)
        if a["type"] == 15 and bytes.fromhex(a["raw"])[0] == 255: turn += 1
        apply(st, a, turn)
    if k < len(cps) or True:
        res, bad = compare(st, D); reports.append((final, len(acts), res, bad))
    return st, reports

if __name__ == "__main__":
    st, reps = run(sys.argv[1], sys.argv[2:])
    for path, i, res, bad in reps:
        print(os.path.basename(path), "after", i, "actions:", dict(res))
    print("log:", dict(LOG))
