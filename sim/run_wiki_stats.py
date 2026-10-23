"""Run the wiki-literal generator many times, check it reproduces the wiki's own numbers, and measure what it predicts.
Usage: python3 -I run_wiki_stats.py <out_dir> [maps_per_type]"""
import sys, os, json, random, collections, statistics as st
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "..", "verify"))
import wiki_mapgen as W
import analyze_map as A

out = sys.argv[1]; K = int(sys.argv[2]) if len(sys.argv) > 2 else 60
READING = sys.argv[3] if len(sys.argv) > 3 else "A"
os.makedirs(out, exist_ok=True)
TRIBES = list(W.TRIBE_MOD)                              # 15 tribes (Polaris has no biome of its own)
mapgen = json.load(open(os.path.join(HERE, "..", "data", "map_generation.json")))
rng = random.Random(1)
report = {"params_not_from_wiki": W.PARAMS, "by_type": {}, "capital_ring8_by_tribe": {}, "self_check": {}}
ring_full = collections.defaultdict(collections.Counter)
# self-check accumulators: terrain share per biome, P(res|terrain) per zone
terr_acc = collections.defaultdict(collections.Counter); res_acc = collections.defaultdict(collections.Counter)
for mt in ("lakes", "drylands", "continents", "pangea", "archipelago", "waterworld"):
    reps = []
    for k in range(K):
        tribes = rng.sample(TRIBES, 4)
        g = W.generate(mt, 16, tribes, seed=10_000 * len(mt) + k, village_reading=READING)
        r = A.analyse(g, mapgen); reps.append(r)
        if mt == "lakes":
            for c in r["capitals"]: ring_full[c["tribe"]][c["ring8_total"]] += 1
            n = g["size"]; T = g["tiles"]; settle = [i for i, t in T.items() if t["improvement"] == "Village"]
            inner = {j for s in settle for j in W.nbrs(s, n, 1)} - set(settle)
            outer = {j for s in settle for j in W.nbrs(s, n, 2)} - inner - set(settle)
            caprings = {j for i, t in T.items() if t["capital_of"] for j in W.nbrs(i, n, 1)}
            for i, t in T.items():
                if t["biome"] and not t["improvement"] and i not in caprings and t["terrain"] in ("Field", "Forest", "Mountain"): terr_acc[t["biome"]][t["terrain"]] += 1
                if i in caprings: continue                                    # guarantees distort capital rings on purpose
                z = "inner" if i in inner else "outer" if i in outer else None
                if z and t["terrain"] in ("Field", "Forest", "Mountain", "Water"):
                    res_acc[(t["biome"] or "water", z, t["terrain"])][t["resource"] or "none"] += 1
    report["by_type"][mt] = {
        "land_fraction": round(st.mean(r["land_fraction"] for r in reps), 3),
        "settlements_mean": round(st.mean(r["villages_and_cities"] for r in reps), 2), "grid_slots": reps[0]["village_grid_slots"],
        "ruins_mean": round(st.mean(r["ruins"] for r in reps), 2), "starfish_mean": round(st.mean(r["starfish"] for r in reps), 2),
        "capital_ring8_mean": round(st.mean(c["ring8_total"] for r in reps for c in r["capitals"]), 2),
        "fish_rate_shallow_near_settlement": round(st.mean(r["fish_rate_shallow_near_settlement"] or 0 for r in reps), 3)}
    print(mt, report["by_type"][mt])
report["capital_ring8_by_tribe"] = {t: {"mean": round(sum(k * v for k, v in c.items()) / sum(c.values()), 2), "n": sum(c.values()),
                                        "dist": {k: round(v / sum(c.values()), 3) for k, v in sorted(c.items())}} for t, c in sorted(ring_full.items())}
# self-check against the wiki numbers
chk = {}
for t, c in terr_acc.items():
    tot = sum(c.values()); want = W.biome_shares(t)
    chk[t] = {k: (round(c[k.capitalize()] / tot, 3), round(want[k], 3)) for k in ("mountain", "forest", "field")}
report["self_check"]["terrain_share_per_biome (measured, wiki target)"] = chk
rows = {}
for (t, z, ter), c in res_acc.items():
    if t == "water": continue
    tot = sum(c.values()); cp = W.cond_probs(t, z)[{"Field": "field", "Forest": "forest", "Mountain": "mountain", "Water": "water"}[ter]]
    rows[f"{t}/{z}/{ter}"] = {r: (round(c[{"fruit": "Fruit", "crop": "Spores" if t == "Cymanti" else "Crop", "animal": "Game", "metal": "Metal", "fish": "Fish"}[r]] / tot, 3), round(p, 3)) for r, p in cp.items()}
report["self_check"]["P(resource|terrain) per biome/zone (measured, wiki-derived target)"] = rows
report["village_reading"] = READING
json.dump(report, open(os.path.join(out, f"wiki_mapgen_report_{READING}.json"), "w"), indent=1)
worst = max(abs(a - b) for v in chk.values() for a, b in v.values())
worst_r = max(abs(a - b) for v in rows.values() for a, b in v.values())
print("self-check: worst terrain share error %.3f ; worst resource-rate error %.3f" % (worst, worst_r))
print("capital ring-8 means:", {t: v["mean"] for t, v in report["capital_ring8_by_tribe"].items()})
