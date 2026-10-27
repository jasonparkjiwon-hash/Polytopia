"""Actions and tile contents around given tiles between two per-turn saves of one game.
Usage: python3 -I tools/trace.py <game id prefix> <turnA> <turnB> x,y [x,y ...] [--city]
--acts P lists every action of player P between the saves.
--players prints each player's tribe, stars and techs in both saves.
--city also prints the city record (owner, level, population, rewards taken) on improvement tiles."""
import sys, os, json, glob, struct
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "engine"))
import replay as R
from state import UNIT, TERRAIN, TRIBE
CITY, PLAYERS = "--city" in sys.argv, "--players" in sys.argv; sys.argv = [x for x in sys.argv if x not in ("--city", "--players")]
WHO = int(sys.argv.pop(sys.argv.index("--acts") + 1)) if "--acts" in sys.argv else None; sys.argv = [x for x in sys.argv if x != "--acts"]
g, ta, tb = sys.argv[1:4]; pts = [tuple(map(int, p.split(","))) for p in sys.argv[4:]]
L = lambda t: json.load(open(glob.glob(os.path.join(ROOT, "saves", f"{g}*_t{t}.json"))[0]))
a, b = L(ta), L(tb)
acts = max((json.load(open(f)) for f in glob.glob(os.path.join(ROOT, "saves", f"{g}*_t*.json"))), key=lambda d: len(d["actions"]))["actions"]
tr = {p["PlayerId"]: TRIBE.get(p["Tribe"]) for p in b["currentPlayers"]}
def tile(d, x, y):
    t = d["currentTiles"][y][x]; u = t.get("Unit"); p = t.get("PassengerUnit")
    return (TERRAIN.get(t["Terrain"]), f"flood{t.get('FloodedValue')}" if t.get("FloodedFlag") else "", f"imp{t['ImprovementType']}" if t["ImprovementExists"] else "", f"res{t['ResourceType']}" if t.get("ResourceExists") else "",
            u and (u["Id"], tr.get(u["Owner"]), UNIT.get(u["UnitType"], u["UnitType"]), u["Health"] / 10, "home", u.get("hx"), u.get("hy")), p and (p["Id"], UNIT.get(p["UnitType"])))
def city(d, x, y):
    t = d["currentTiles"][y][x]; c = t.get("ImprovementData") or {}
    return (t["Owner"], "city at", t.get("CapitalCoordinates")) + ((c and {k: c.get(k) for k in ("Level", "CurrentPopulation", "TotalPopulation", "Production", "BorderSize", "CityRewards", "FoundedTurn")}),)
if PLAYERS:
    for d, n in ((a, "before"), (b, "after")):
        for p in d["currentPlayers"]: print(n, "p%d" % p["PlayerId"], TRIBE.get(p["Tribe"]), "stars", p.get("Currency"), "techs", sorted(p["AvailableTech"]), "kills", p.get("Kills"), "tasks", p.get("Tasks"), "diplo (id, state, embassy)", [(r["PlayerId"], r["RelationState"], r["EmbassyLevel"]) for r in p.get("Diplomacy", [])])
for x, y in pts:
    print((x, y), "before", tile(a, x, y), "| after", tile(b, x, y))
    if CITY: print("   city before", city(a, x, y), "| after", city(b, x, y))
for i in range(len(a["actions"]), len(b["actions"])):
    x = acts[i]; f = R.FMT.get(x["type"]); v = struct.unpack(f, bytes.fromhex(x["raw"])) if f else ()
    n = list(v[1:])
    if any((n[j], n[j + 1]) in pts for j in range(len(n) - 1)) or (v and v[0] == WHO): print(i, x["name"], tr.get(v[0]), v[1:])
