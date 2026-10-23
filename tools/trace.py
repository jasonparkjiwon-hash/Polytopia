"""Actions and tile contents around given tiles between two per-turn saves of one game.
Usage: python3 -I tools/trace.py <game id prefix> <turnA> <turnB> x,y [x,y ...]"""
import sys, os, json, glob, struct
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "engine"))
import replay as R
from state import UNIT, TERRAIN, TRIBE
g, ta, tb = sys.argv[1:4]; pts = [tuple(map(int, p.split(","))) for p in sys.argv[4:]]
L = lambda t: json.load(open(glob.glob(os.path.join(ROOT, "saves", f"{g}*_t{t}.json"))[0]))
a, b = L(ta), L(tb)
acts = max((json.load(open(f)) for f in glob.glob(os.path.join(ROOT, "saves", f"{g}*_t*.json"))), key=lambda d: len(d["actions"]))["actions"]
tr = {p["PlayerId"]: TRIBE.get(p["Tribe"]) for p in b["currentPlayers"]}
def tile(d, x, y):
    t = d["currentTiles"][y][x]; u = t.get("Unit"); p = t.get("PassengerUnit")
    return (TERRAIN.get(t["Terrain"]), f"flood{t.get('FloodedValue')}" if t.get("FloodedFlag") else "", f"imp{t['ImprovementType']}" if t["ImprovementExists"] else "",
            u and (u["Id"], tr.get(u["Owner"]), UNIT.get(u["UnitType"], u["UnitType"]), u["Health"] / 10), p and (p["Id"], UNIT.get(p["UnitType"])))
for x, y in pts: print((x, y), "before", tile(a, x, y), "| after", tile(b, x, y))
for i in range(len(a["actions"]), len(b["actions"])):
    x = acts[i]; f = R.FMT.get(x["type"]); v = struct.unpack(f, bytes.fromhex(x["raw"])) if f else ()
    n = list(v[1:])
    if any((n[j], n[j + 1]) in pts for j in range(len(n) - 1)): print(i, x["name"], tr.get(v[0]), v[1:])
