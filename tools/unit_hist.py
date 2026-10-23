"""Bisect inside the action log: replay from one save to the next and print every action that changes the given units.
Usage: python3 -I tools/unit_hist.py <game id prefix> <turnA> id [id ...] [--all]
Each line: action index, turn, action, tribe, args -> changed units (id, type, x, y, hp, effects, alive).
Attack lines add the event (attacker id/type/hp, defender id/type/hp, bonus, dmg, ret, terrain); --all prints every attack."""
import sys, os, json, glob, struct
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "engine"))
import replay as R
from state import State, TRIBE
ALL = "--all" in sys.argv; args = [a for a in sys.argv[1:] if a != "--all"]
g, ta, ids = args[0], int(args[1]), [int(i) for i in args[2:]]
ds = sorted((json.load(open(f)) for f in glob.glob(os.path.join(ROOT, "saves", f"{g}*_t*.json"))), key=lambda d: len(d["actions"]))
acts = ds[-1]["actions"]
R.ORACLE.clear(); R.RUIN.clear(); R.RUIN_SEEN.clear()
for d in ds:
    R.add_ruin_oracle(d)
    for i, v in R.snapshot_units(d).items(): R.ORACLE.setdefault(i, (v[0], v[1], v[5]))
a = [d for d in ds if d["currentTurn"] == ta][0]; b = ds[ds.index(a) + 1]
tr = {p["PlayerId"]: TRIBE.get(p["Tribe"]) for p in b["currentPlayers"]}
st = State(a, "current"); R.PREV[0] = None; turn = ta
objs = {i: st.units.get(i) for i in ids}
look = lambda: {i: ((o.id, o.type, o.x, o.y, o.hp, tuple(o.effects), o.id in st.units) if o else None) for i, o in objs.items()}
s0 = look(); print("saves", [d["currentTurn"] for d in ds], "start", s0)
for k in range(len(a["actions"]), len(b["actions"])):
    x = acts[k]
    if x["type"] == 15 and bytes.fromhex(x["raw"])[0] == 255: turn += 1
    ne = len(R.EVENTS); R.apply(st, x, turn); ev = [e for e in R.EVENTS[ne:] if e[0] == "attack"]
    for i in ids:
        if st.units.get(i) is not None: objs[i] = st.units[i]   # follows a unit through temp ids, boarding and rekeys once the id is known
    s1 = look()
    if s1 != s0 or (ALL and ev):
        f = R.FMT.get(x["type"]); v = struct.unpack(f, bytes.fromhex(x["raw"])) if f else (bytes.fromhex(x["raw"])[0],)
        print(k, "t", turn, x["name"], tr.get(v[0]), v[1:], "->", {i: s1[i] for i in ids if s1[i] != s0.get(i)}, *(["ev", ev[0][2:]] if ev else []))
    s0 = s1
sv = R.snapshot_units(b); print("save", {i: sv.get(i) for i in ids})
