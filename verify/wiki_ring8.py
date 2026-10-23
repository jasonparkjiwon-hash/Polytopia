"""Measure the capital 8-tile ring distribution per tribe from the wiki-literal generator (normal Lakes, 4 players).
Writes wiki_gen_ring8.json in the same format as pf_engine_ring8.json. Usage: python3 -I wiki_ring8.py [maps]"""
import sys, os, json, random, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, "..", "sim")); sys.path.insert(0, HERE)
import wiki_mapgen as W
from c23_models import START_TECH
K = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
def vis(t, r):
    s = START_TECH[t]
    if r == "crop": return s in ("Organization", "Farming", "Construction")
    if r == "metal": return s in ("Climbing", "Mining", "Smithery")
    if r == "starfish": return False
    return True
full = collections.defaultdict(collections.Counter); seen = collections.defaultdict(collections.Counter)
rng = random.Random(42); T = list(W.TRIBE_MOD)
inv = {"Fruit": "fruit", "Crop": "crop", "Spores": "crop", "Game": "animal", "Metal": "metal", "Fish": "fish", "Starfish": "starfish"}
for k in range(K):
    tribes = rng.sample(T, 4); g = W.generate("lakes", 16, tribes, seed=500_000 + k); n = g["size"]
    for i, t in g["tiles"].items():
        if t["capital_of"]:
            tr = tribes[t["capital_of"] - 1]
            rs = [inv[g["tiles"][j]["resource"]] for j in W.nbrs(i, n, 1) if g["tiles"][j]["resource"]]
            full[tr][len(rs)] += 1; seen[tr][sum(vis(tr, r) for r in rs)] += 1
norm = lambda c: {k: v / sum(c.values()) for k, v in sorted(c.items())}
mean = lambda c: round(sum(k * v for k, v in c.items()) / sum(c.values()), 2)
out = {t: {"full": norm(full[t]), "visible": norm(seen[t]), "mean_full": mean(full[t]), "mean_visible": mean(seen[t]), "n": sum(full[t].values())} for t in full}
json.dump({"source": f"wiki_mapgen (wiki-literal), {K} normal Lakes maps, 4 players", "tribes": out}, open(os.path.join(HERE, "wiki_gen_ring8.json"), "w"), indent=1)
print({t: (o["mean_full"], o["mean_visible"], o["n"]) for t, o in sorted(out.items())})
