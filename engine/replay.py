"""Shadow replay: apply a save's action list to its turn-0 state and compare with saved checkpoints.

Usage: python3 -I replay.py <final save json> <checkpoint save json> [more checkpoints...]
Each checkpoint is an earlier export of the same game; its action count says where to stop and compare."""
import sys, os, json, struct, math, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from stats import STATS
from state import State, Unit, UNIT, TECH, BOATS, max_hp

FMT = {1: "<BHII", 2: "<BIIIII", 3: "<BII", 4: "<BII", 5: "<BHII", 6: "<BIIIII", 7: "<BIII", 8: "<BH", 9: "<BII", 11: "<BIIH",
       13: "<BII", 14: "<BII", 15: "<B", 16: "<BHII", 17: "<BII", 18: "<BII", 20: "<B", 21: "<BII", 24: "<BII", 25: "<BII",
       27: "<BIIB", 28: "<BBB", 29: "<BIIB", 30: "<BIIB", 38: "<BII"}

LAND_UNITS = {"Warrior", "Rider", "Archer", "Defender", "MindBender", "Swordsman", "Catapult", "Knight", "Cloak", "Dagger", "Giant",
              "Polytaur", "Mooni", "IceArcher", "BattleSled", "IceFortress", "Gaami", "Hexapod", "Kiton", "Shaman", "Exida", "Doomux",
              "Centipede", "Segment", "Larva", "SteamWagon", "SteamFortress", "Pyro", "AshArcher"}   # Aquarion units are amphibious/water: never embark
RULES = {"retaliation_uses_bonus": True, "melee_moves_in_on_kill": True, "t18_disband": False, "t24_explode": True, "t38_boost": True}
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

def fight(st, a, d):
    sa, sd = stat(a), stat(d)
    atk, dfn = sa["atk"] + (0.5 if getattr(a, "boosted", False) else 0), sd["def"]
    bonus = defence_bonus(st, d)
    af = atk * a.hp / a.max_hp; df = dfn * d.hp / d.max_hp * bonus; tot = af + df
    dmg = rnd(af / tot * atk * 4.5) if tot > 0 else 0
    ret = 0
    d_hp = d.hp - dmg
    if d_hp > 0 and "stiff" not in sd["skills"] and "surprise" not in sa["skills"] and dist((a.x, a.y), (d.x, d.y)) <= sd.get("range", 1):
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

TEMP = [0]
def spawn(st, owner, name, x, y):
    """New unit whose real id the log doesn't give: temporary negative id until its first Move/Attack names it."""
    TEMP[0] -= 1; u = Unit(TEMP[0], owner, name, x, y, 0, 0); u.max_hp = max_hp(u); u.hp = u.max_hp
    old = unit_at(st, x, y)
    if old is not None:                          # forced spawn pushes the occupant to a free neighbouring tile
        LOG["spawn on occupied tile (push)"] += 1
        free = [(x + dx, y + dy) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if (dx or dy) and (x + dx, y + dy) in st.terrain and (x + dx, y + dy) not in st.at]
        land = [q for q in free if st.terrain[q] not in ("Water", "Ocean")]
        if land or free: place(st, old, *(land or free)[0])
        else: st.at.pop((x, y), None)
    st.units[u.id] = u; st.at[(x, y)] = u.id
    return u

ORACLE = {}   # unit id -> (owner, type, promotion) from any saved checkpoint, for units spawned by events the log doesn't spell out

def summon(st, uid, owner, x, y):
    o = ORACLE.get(uid); name = o[1] if o else "Warrior"
    u = Unit(uid, owner, name, x, y, 0, 0); u.max_hp = max_hp(u); u.hp = u.max_hp
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

def apply(st, a, turn):
    t = a["type"]; b = bytes.fromhex(a["raw"]); f = FMT.get(t)
    v = struct.unpack(f, b) if f else (b[0],)
    pl = v[0]
    if t == 6:                                   # Move
        _, x0, y0, x1, y1, uid = v
        u = locate(st, uid, x0, y0, pl)
        ter = st.terrain.get((x1, y1)); ter0 = st.terrain.get((x0, y0))
        water = ("Water", "Ocean")
        if ter in water and ter0 not in water and u.type in LAND_UNITS:
            u.passenger = u.type; u.type = "Raft"        # a land unit stepping into water becomes a Raft
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
        if at.type == "MindBender":                 # Convert
            df.owner = at.owner; LOG["convert"] += 1; EVENTS.append(("convert", turn, at.type, df.type)); return
        dmg, ret, bonus = fight(st, at, df); at.boosted = False
        EVENTS.append(("attack", turn, at.id, at.type, at.hp, df.id, df.type, df.hp, bonus, dmg, ret, st.terrain.get((tx, ty))))
        df.hp -= dmg
        if df.hp <= 0:
            remove(st, df); at.xp += 1
            if RULES["melee_moves_in_on_kill"] and dist((ox, oy), (tx, ty)) == 1 and "stiff" not in stat(at)["skills"] and stat(at).get("range", 1) == 1:
                place(st, at, tx, ty)
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
        if u: u.hp = min(u.max_hp, u.hp + (4 if st.owner.get((x, y)) == u.owner else 2))
    elif t == 1:                                 # Build (only unit-spawning builds matter for combat)
        _, imp, x, y = v
        if imp == 30: spawn(st, pl, "Polytaur", x, y); LOG["enchant animal"] += 1
    elif t == 7 and RULES.get("territory", True):  # Capture: the city's tile and the 8 around it become the captor's (unowned or owned by the old owner)
        _, uid, x, y = v; old = st.city.get((x, y))
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                q = (x + dx, y + dy)
                if q in st.terrain and st.owner.get(q) in (0, old, None): st.owner[q] = pl
        st.city[(x, y)] = pl
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
        if rw == 6:                              # Super unit (Giant), forced spawn
            spawn(st, pl, "Giant", x, y)
    elif t == 18 and RULES["t18_disband"]:       # Disband (inferred)
        _, x, y = v; u = unit_at(st, x, y)
        if u and u.owner == pl: remove(st, u); LOG["disband"] += 1
    elif t == 38 and RULES["t38_boost"]:         # Boost (Shaman): adjacent friendly units +0.5 attack until they attack
        _, x, y = v
        for u in list(st.units.values()):
            if u.owner == pl and dist((u.x, u.y), (x, y)) == 1: u.boosted = True
        LOG["boost"] += 1
    elif t == 24 and RULES["t24_explode"]:       # Explode: the unit dies; adjacent enemies take half damage (floored)
        _, x, y = v; u = unit_at(st, x, y)
        if u and u.owner == pl:
            sa = stat(u)
            for d in list(st.units.values()):
                if d.owner != pl and dist((d.x, d.y), (x, y)) == 1 and st.at.get((d.x, d.y)) == d.id:
                    af = sa["atk"] * u.hp / u.max_hp; df = stat(d)["def"] * d.hp / d.max_hp * defence_bonus(st, d); tot = af + df
                    dmg = math.floor(rnd(af / tot * sa["atk"] * 4.5) / 2) if tot > 0 else 0
                    d.hp -= dmg
                    if d.hp <= 0: remove(st, d)
            remove(st, u); LOG["explode"] += 1
    else:
        LOG[f"unhandled type {t}"] += 1

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
        if abs(m[4] - s[4]) > 1e-6: res["HP differs"] += 1; bad.append(("hp", i, s, m))
        else: res["HP exact"] += 1
    for i in mine:
        if i not in snap: res["extra in engine (should be dead)"] += 1; bad.append(("extra", i, mine[i]))
    return res, bad

def run(final, checkpoints):
    D = json.load(open(final)); st = State(D, "initial"); acts = D["actions"]
    for c in list(checkpoints) + [final]:
        for i, v in snapshot_units(json.load(open(c))).items(): ORACLE.setdefault(i, (v[0], v[1], v[5]))
    cps = sorted(((len(json.load(open(c))["actions"]), c) for c in checkpoints))
    turn = 0; k = 0; reports = []
    for i, a in enumerate(acts):
        while k < len(cps) and i == cps[k][0]:
            cd = json.load(open(cps[k][1])); res, bad = compare(st, cd); reports.append((cps[k][1], i, res, bad)); k += 1
            if RULES.get("resync_territory", True):     # borders are read back from each checkpoint (they are not under test here)
                for yy, row in enumerate(cd["currentTiles"]):
                    for xx, tt in enumerate(row): st.owner[(xx, yy)] = tt["Owner"]
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
