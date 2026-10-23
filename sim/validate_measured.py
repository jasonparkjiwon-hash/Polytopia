"""Check the generator against the real saves: for every (map type, size) in the save library, generate K maps in each
mode and compare settlements, land share, capital-ring totals per tribe, and pooled resource rates.

Usage: python3 -I validate_measured.py <out.json> [K]"""
import sys, os, json, random, collections, statistics as st
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "..", "verify"))
import wiki_mapgen as W, analyze_map as A
K = int(sys.argv[2]) if len(sys.argv) > 2 else 20
M = W.MEASURED; mg = json.load(open(os.path.join(HERE, "..", "data", "map_generation.json")))
TR = list(W.TRIBE_MOD) + ["Polaris"]; rng = random.Random(3)
real_ring = {t: v["mean_total"] for t, v in M["capital_ring"].items()}
out = {"K": K, "by_type_size": {}, "ring_by_tribe": {}, "rates": {}}
ring = {m: collections.defaultdict(list) for m in ("measured", "wiki")}
rates = {m: collections.defaultdict(collections.Counter) for m in ("measured", "wiki")}
RES = {"Fruit": "fruit", "Crop": "crop", "Spores": "crop", "Game": "animal", "Metal": "metal", "Fish": "fish", "AquaCrop": "aquacrop"}
for mt, v in M["by_map_type"].items():
    for n in sorted({r["size"] for r in v["rows"]}):
        real = [r for r in v["rows"] if r["size"] == n]; row = {"real_settlements": [r["settlements"] for r in real], "real_land": round(st.mean(r["land"] for r in real), 3)}
        for mode in ("measured", "wiki"):
            S = []; L = []
            for k in range(K):
                tribes = rng.sample(TR, 16 if n >= 30 else 4)
                g = W.generate(mt, n, tribes, seed=rng.randrange(10 ** 9), mode=mode); r = A.analyse(g, mg)
                S.append(r["villages_and_cities"]); L.append(r["land_fraction"])
                for c in r["capitals"]: ring[mode][c["tribe"]].append(c["ring8_total"])
                T = g["tiles"]; settle = {i for i, t in T.items() if t["improvement"] == "Village"}
                capring = {j for i, t in T.items() if t["capital_of"] for j in W.nbrs(i, n, 1)}
                inner = {j for s in settle for j in W.nbrs(s, n, 1)} - settle
                for i in inner - capring:
                    ter = T[i]["terrain"].lower(); ter = "water" if ter in ("water", "ocean") else ter
                    rates[mode][ter][RES.get(T[i]["resource"], "none")] += 1
            row[mode] = {"settlements": round(st.mean(S), 1), "land": round(st.mean(L), 3)}
        out["by_type_size"][f"{mt}/{n}"] = row
        print(f"{mt:11s} {n:2d} settle real {row['real_settlements']} measured {row['measured']['settlements']} wiki {row['wiki']['settlements']} | land real {row['real_land']} measured {row['measured']['land']} wiki {row['wiki']['land']}")
print("\ncapital ring-8 mean by tribe: real / measured / wiki")
for t in sorted(real_ring):
    m = st.mean(ring["measured"][t]) if ring["measured"][t] else None; w = st.mean(ring["wiki"][t]) if ring["wiki"][t] else None
    out["ring_by_tribe"][t] = {"real": real_ring[t], "measured": m and round(m, 2), "wiki": w and round(w, 2)}
    print(f"  {t:9s} {real_ring[t]:.2f} / {m:.2f} / {w:.2f}")
real_rates = collections.defaultdict(collections.Counter)
for k, c in M["resource_counts"].items():
    t, z, ter = k.split("|")
    if z == "inner": real_rates["water" if ter in ("water", "ocean") else ter].update({r: x for r, x in c.items() if r != "starfish"})
print("\ninner-zone resource rates: real | measured | wiki")
for ter in ("field", "forest", "mountain", "water"):
    def fmt(c): s = sum(c.values()); return {r: round(x / s, 3) for r, x in sorted(c.items())}
    out["rates"][ter] = {"real": fmt(real_rates[ter]), "measured": fmt(rates["measured"][ter]), "wiki": fmt(rates["wiki"][ter])}
    print(f"  {ter:8s}", out["rates"][ter])
json.dump(out, open(sys.argv[1], "w"), indent=1)
