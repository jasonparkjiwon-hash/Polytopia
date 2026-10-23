"""C9 village count: the pre-registered held-out test in c9_test.md.

Usage: python3 -I c9_test.py <game_enums.json> <saves_dir> <measured_mapgen.json>"""
import sys, os, json, glob, math

E = json.load(open(sys.argv[1])); MT = E["MapType"]
M = json.load(open(sys.argv[3]))["by_map_type"]
P = {"PE": lambda mt: 0.999, "WK": lambda mt: 0.60, "MS": lambda mt: M[mt]["settlements_per_slot"]}

def binom_logpmf(k, n, p):
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1) + k * math.log(p) + (n - k) * math.log(1 - p)

def describe(d):
    """Map type, size, land share, water tiles, starfish, slots and settlements of a turn-0 map (initial state)."""
    h = d["header"]["MapHeaderInput"]; mt = MT[str(h["SettingsTail"][2])].lower(); n = h["MapWidth"]
    tiles = [t for row in d["initialTiles"] for t in row]
    terr = E["TerrainType"]
    water = sum(1 for t in tiles if terr.get(str(t["Terrain"])) in ("Water", "Ocean"))
    starfish = sum(1 for t in tiles if t["ResourceExists"] and E["ResourceType"].get(str(t["ResourceType"])) == "Starfish")
    settlements = sum(1 for t in tiles if t["ImprovementExists"] and t["ImprovementType"] == 1)
    return mt, n, 1 - water / len(tiles), water, starfish, (n // 3) ** 2, settlements

def in_table(mt, n, land, water, starfish):
    return any(r["size"] == n and abs(r["land"] - land) < 1e-9 and r["water"] == water and r["starfish"] == starfish
               for r in M.get(mt, {}).get("rows", []))

# Amendment (23 Oct, before scoring the Drylands save): saves known to have arrived after the table was built.
# Drylands maps are nearly all land, so a new one can share size, water and starfish with a table row.
KNOWN_NEW = {"af181c8f", "09a5bf1e", "6eccceef", "d71a6b1d"}
held = []
for f in sorted(glob.glob(os.path.join(sys.argv[2], "????????-????-????-????-????????????.json"))):
    d = json.load(open(f))
    if "initialTiles" not in d: continue
    mt, n, land, water, starfish, slots, settle = describe(d)
    if mt in M and (os.path.basename(f)[:8] in KNOWN_NEW or not in_table(mt, n, land, water, starfish)):
        held.append((os.path.basename(f)[:8], mt, n, slots, settle))

ll = {m: 0.0 for m in P}
for g, mt, n, slots, k in held:
    for m, p in P.items(): ll[m] += binom_logpmf(k, slots, p(mt))
    print(f"{g} {mt:12s} size {n:2d}: {k:3d} of {slots:3d} slots ({k / slots:.2f})  MS expects {M[mt]['settlements_per_slot']:.2f}")
print("held-out saves:", len(held), "| map types covered:", sorted({h[1] for h in held}))
best = max(ll, key=ll.get)
for m in P:
    if m != best: print(f"Bayes factor {best} over {m}: 10^{(ll[best] - ll[m]) / math.log(10):.1f}")
decided = all(ll[best] - ll[m] > math.log(10) for m in P if m != best)
print("verdict:", f"{best} decided (BF > 10 against both others)" if decided else "open")
