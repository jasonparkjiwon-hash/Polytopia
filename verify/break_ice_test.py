"""How well does the engine's terrain match the next save on tiles that were ever ice, with and without Break Ice?"""
import sys, json, collections, glob, os, re
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, "..", "engine"))
import replay as R
from state import State, TERRAIN
games = collections.defaultdict(list)
for f in glob.glob(os.path.join(HERE, "..", "saves", "*_t*.json")):
    if re.search(r"_t\d+\.json$", f): games[os.path.basename(f)[:36]].append(f)
for rule in (False, True):
    R.RULES["t18_break_ice"] = rule; c = collections.Counter(); units = collections.Counter()
    for gid, fs in games.items():
        ds = sorted((json.load(open(f)) for f in fs), key=lambda d: len(d["actions"])); acts = ds[-1]["actions"]
        for a, b in zip(ds, ds[1:]):
            st = State(a, "current"); R.PREV[0] = None; turn = a["currentTurn"]
            for i in range(len(a["actions"]), len(b["actions"])):
                x = acts[i]
                if x["type"] == 15 and bytes.fromhex(x["raw"])[0] == 255: turn += 1
                R.apply(st, x, turn)
            for y, row in enumerate(b["currentTiles"]):
                for xx, t in enumerate(row):
                    eng, real = st.terrain.get((xx, y)), TERRAIN.get(t["Terrain"])
                    if "Ice" in (eng, real) or TERRAIN.get(a["currentTiles"][y][xx]["Terrain"]) == "Ice":
                        c["match" if eng == real or {eng, real} <= {"Water", "Ocean"} else f"engine {eng} / save {real}"] += 1
            res, _ = R.compare(st, b); units.update(res)
    print(f"break ice {'ON ' if rule else 'OFF'}: ice-related tiles {dict(c.most_common(4))} | units exact {units['HP exact']}")
