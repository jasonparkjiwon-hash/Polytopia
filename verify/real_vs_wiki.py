"""Compare a real turn-0 map tile by tile with the wiki rules: terrain share per tribe biome, and P(resource|terrain)
in the inner (adjacent to a settlement) and outer (distance 2) zones, against both readings of the wiki table.
Usage: python3 -I real_vs_wiki.py <game_enums.json> <state json>"""
import sys, os, json, collections, math
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "..", "sim"))
import analyze_map as A, wiki_mapgen as W
E = A.load_enums(sys.argv[1]); g = A.normalise(sys.argv[2], E); n = g["size"]; T = g["tiles"]
settle = [i for i, t in T.items() if t["improvement"] == "Village"]
caps = {i for i, t in T.items() if t["capital_of"]}
inner = {j for s in settle for j in W.nbrs(s, n, 1)} - set(settle)
outer = {j for s in settle for j in W.nbrs(s, n, 2)} - inner - set(settle)
far = set(T) - inner - outer - set(settle)
caprings = {j for c in caps for j in W.nbrs(c, n, 1)}
TER = {"Field": "field", "Forest": "forest", "Mountain": "mountain"}
RES = {"Field": ["Fruit", "Crop", "Spores"], "Forest": ["Game"], "Mountain": ["Metal"]}
out = {"map": {"size": n, "settlements": len(settle), "capitals": len(caps), "land": round(sum(t["terrain"] not in ("Water", "Ocean") for t in T.values()) / n / n, 3)}}
# terrain shares per biome (non-settlement land)
tb = collections.defaultdict(collections.Counter)
for i, t in T.items():
    if t["terrain"] in TER and not t["improvement"]: tb[t["biome"]][t["terrain"]] += 1
rows = []
for b, c in sorted(tb.items()):
    tot = sum(c.values())
    if b not in W.TRIBE_MOD: rows.append((b, tot, {k: round(c[k] / tot, 3) for k in TER}, None)); continue
    want = W.biome_shares(b); rows.append((b, tot, {k: round(c[k] / tot, 3) for k in TER}, {k.capitalize(): round(v, 3) for k, v in want.items()}))
out["terrain_by_biome"] = rows
# resource rates by zone, pooled over biomes after dividing out tribe multipliers is messy -> report per zone pooled, and per biome
def rate(zone, ter, resname, excl_caprings=True, biome=None):
    tiles = [i for i in zone if T[i]["terrain"] == ter and (not excl_caprings or i not in caprings) and (biome is None or T[i]["biome"] == biome)]
    k = sum(1 for i in tiles if T[i]["resource"] == resname); return k, len(tiles)
pooled = {}
for zname, zone in (("inner", inner), ("outer", outer), ("beyond_2", far)):
    for ter, names in RES.items():
        for rn in names:
            k, m = rate(zone, ter, rn)
            if m: pooled[f"{zname} {rn}|{ter}"] = (k, m, round(k / m, 3))
out["pooled_rates"] = pooled
# expected pooled rates under the two readings, weighting each biome by its tile count in that cell
def expected(zname, ter, rn, reading):
    if zname == "beyond_2": return 0.0
    num = 0; den = 0
    for b in tb:
        if b not in W.TRIBE_MOD: continue
        k, m = rate(inner if zname == "inner" else outer, ter, rn, biome=b)
        if not m: continue
        key = {"Fruit": "fruit", "Crop": "crop", "Spores": "crop", "Game": "animal", "Metal": "metal"}[rn]
        if (rn == "Spores") != (b == "Cymanti"): continue
        base = W.SHARE[zname][key]; mult = W.TRIBE_MOD[b].get(key, 1.0)
        p = base * mult / {"field": 0.48, "forest": 0.38, "mountain": 0.14}[TER[ter]] if reading == "WIKI" else base * mult
        num += min(p, 1.0) * m; den += m
    return round(num / den, 3) if den else None
cmp_rows = []
for key, (k, m, r) in pooled.items():
    z, rest = key.split(" "); rn, ter = rest.split("|")
    ew, ep = expected(z, ter, rn, "WIKI"), expected(z, ter, rn, "PE")
    def zsc(e): return round((r - e) / math.sqrt(max(e * (1 - e), 1e-6) / m), 1) if e is not None else None
    cmp_rows.append({"cell": key, "n": m, "real": r, "wiki_reading": ew, "z_vs_wiki": zsc(ew), "PE_reading": ep, "z_vs_PE": zsc(ep)})
out["rates_vs_readings"] = cmp_rows
# fish & water
water = [i for i, t in T.items() if t["terrain"] in ("Water", "Ocean")]
out["water_tiles"] = {i: (T[i]["terrain"], T[i]["resource"]) for i in water}
json.dump(out, open(sys.argv[2].replace(".json", "_vs_wiki.json"), "w"), indent=1, default=str)
print(json.dumps(out["map"]))
print("TERRAIN SHARE PER BIOME (real vs wiki target)")
for b, tot, real, want in rows: print(f"  {b:9s} n={tot:3d} real {real}  wiki {want}")
print("RESOURCE RATES (capital rings excluded)")
for c in cmp_rows: print(f"  {c['cell']:24s} n={c['n']:3d} real {c['real']:.3f} | wiki {c['wiki_reading']} (z {c['z_vs_wiki']}) | PE {c['PE_reading']} (z {c['z_vs_PE']})")
print("water:", out["water_tiles"])
