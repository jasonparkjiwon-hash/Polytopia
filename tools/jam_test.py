"""Does 'settlements = random sequential packing until no spot is left' (Chebyshev >= 3, land, not on the map edge, capitals fixed)
predict the real settlement count per save? Compared with the C9 model (share x (n//3)^2). No fitted parameter in the packing model.
Usage: python3 -I tools/jam_test.py   (reads saves/*.json via verify/analyze_map.py; needs scripts/restore_saves.sh first)"""
import sys, os, glob, json, random, statistics, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "verify"))
import analyze_map as A
E = A.load_enums("verify/game_enums.json")
MT = {"1": "drylands", "2": "lakes", "3": "continents", "4": "archipelago", "5": "waterworld", "6": "pangea"}
meas = json.load(open("data/measured_mapgen.json"))["by_map_type"]
rng = random.Random(7)
def jam(n, land, caps, runs=40):
    base = [c for c in caps]
    cells = [i for i in range(n * n) if land[i] and 0 < i % n < n - 1 and 0 < i // n < n - 1]
    out = []
    for _ in range(runs):
        rng.shuffle(cells); S = list(base)
        for p in cells:
            if all(max(abs(p % n - q % n), abs(p // n - q // n)) >= 3 for q in S): S.append(p)
        out.append(len(S))
    return statistics.mean(out), statistics.pstdev(out)
rows = []
for f in sorted(glob.glob("saves/????????-????-????-????-????????????.json")):
    d = json.load(open(f)); mt = MT[str(d["header"]["MapHeaderInput"]["SettingsTail"][2])]
    g = A.normalise(f, E); n = g["size"]; T = g["tiles"]
    caps = [i for i, t in T.items() if t.get("capital_of")]
    sett = [i for i, t in T.items() if t["improvement"] in ("Village", "City") or t.get("capital_of")]
    land = {i: t["terrain"] not in ("Water", "Ocean") for i, t in T.items()}
    m, sd = jam(n, land, caps)
    rows.append((mt, n, len(caps), len(sett), m, sd, round(meas[mt]["settlements_per_slot"] * (n // 3) ** 2, 1)))
by = collections.defaultdict(list)
for r in rows: by[r[0]].append(r)
print("type      maps  actual-jam (mean, sd of diff)   actual-C9share (mean, sd)   [jam sd ~ run-to-run]")
for mt, rs in sorted(by.items()):
    dj = [r[3] - r[4] for r in rs]; dc = [r[3] - r[6] for r in rs]
    print("%-12s %3d  %+6.1f (%4.1f)   %+6.1f (%4.1f)   typical jam sd %.1f" % (mt, len(rs), statistics.mean(dj), statistics.pstdev(dj), statistics.mean(dc), statistics.pstdev(dc), statistics.mean(r[5] for r in rs)))
dj = [r[3] - r[4] for r in rows]; dc = [r[3] - r[6] for r in rows]
print("ALL %d maps: |actual-jam| mean %.2f   |actual-C9| mean %.2f" % (len(rows), statistics.mean(map(abs, dj)), statistics.mean(map(abs, dc))))
