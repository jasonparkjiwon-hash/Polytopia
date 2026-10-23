"""Measure the map-generation numbers from real turn-0 saves, for the generator's 'measured' mode.

Usage: python3 -I build_measured_tables.py <game_enums.json> <saves_dir> <out.json>

Everything here is counted from the saves; nothing is taken from the wiki. The generator blends each measured
rate with the wiki value using a pseudo-count prior (see sim/wiki_mapgen.py: PRIOR_N), so thin cells lean on the
wiki and well-sampled cells follow the game.
Capital rings (distance 1 of a capital) are excluded from terrain and resource rates, because the capital
guarantee rewrites them on purpose; they are measured separately under capital_ring."""
import sys, os, json, glob, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import analyze_map as A

E = A.load_enums(sys.argv[1]); saves = sorted(glob.glob(os.path.join(sys.argv[2], "????????-????-????-????-????????????.json")))
MT = json.load(open(sys.argv[1]))["MapType"]
def nbrs(i, n, r=1):
    x, y = i % n, i // n
    return [(y + dy) * n + x + dx for dy in range(-r, r + 1) for dx in range(-r, r + 1) if (dx or dy) and 0 <= x + dx < n and 0 <= y + dy < n]
def dist(a, b, n): return max(abs(a % n - b % n), abs(a // n - b // n))
RES = {"Fruit": "fruit", "Crop": "crop", "Spores": "crop", "Game": "animal", "Metal": "metal", "Fish": "fish", "AquaCrop": "aquacrop", "Starfish": "starfish"}
TER = {"Field": "field", "Forest": "forest", "Mountain": "mountain", "Water": "water", "Ocean": "ocean"}

terrain = collections.defaultdict(collections.Counter)                 # tribe -> terrain counts (land, no settlements, no capital rings)
resource = collections.defaultdict(collections.Counter)                # (tribe, zone, terrain) -> resource counts
ring_pairs = collections.defaultdict(collections.Counter)               # tribe -> which resource forms the identical pair
ring_tot = collections.defaultdict(list)
ring_tpl = collections.defaultdict(list)                                 # tribe -> list of rings, each 8 (dx, dy, terrain, resource)
by_type = collections.defaultdict(list)
for f in saves:
    d = json.load(open(f)); mt = MT[str(d["header"]["MapHeaderInput"]["SettingsTail"][2])].lower()
    g = A.normalise(f, E); n = g["size"]; N = n * n; T = g["tiles"]
    caps = [i for i, t in T.items() if t.get("capital_of")]
    settle = [i for i, t in T.items() if t["improvement"] in ("Village", "City") or t.get("capital_of")]
    sset = set(settle); capring = {j for c in caps for j in nbrs(c, n, 1)}
    inner = {j for s in settle for j in nbrs(s, n, 1)} - sset; outer = {j for s in settle for j in nbrs(s, n, 2)} - inner - sset
    def tribe_of(i):
        b = T[i].get("biome")
        return b if b else T[min(caps, key=lambda c: dist(i, c, n))]["biome"]
    land = sum(1 for t in T.values() if t["terrain"] not in ("Water", "Ocean"))
    water = N - land
    by_type[mt].append({"size": n, "settlements": len(settle), "slots": (n // 3) ** 2, "land": land / N,
                        "starfish": sum(1 for t in T.values() if t["resource"] == "Starfish"), "water": water})
    for i, t in T.items():
        ter = TER.get(t["terrain"])
        if ter is None or i in sset or i in capring: continue
        tr = tribe_of(i)
        if ter in ("field", "forest", "mountain"): terrain[tr][ter] += 1
        z = "inner" if i in inner else "outer" if i in outer else "far"
        resource[(tr, z, ter)][RES.get(t["resource"], "none") if t["resource"] else "none"] += 1
    for c in caps:
        tr = T[c]["biome"]; cnt = collections.Counter(RES.get(T[j]["resource"]) for j in nbrs(c, n, 1) if T[j]["resource"] and not T[j]["improvement"])
        ring_tot[tr].append(sum(cnt.values()))
        ring_tpl[tr].append({"map_type": mt, "tiles": [[j % n - c % n, j // n - c // n, TER.get(T[j]["terrain"], "field"), RES.get(T[j]["resource"]) if T[j]["resource"] else None]
                             for j in nbrs(c, n, 1)]})
        pairs = [r for r, k in cnt.items() if k >= 2]
        ring_pairs[tr][",".join(sorted(pairs)) or "none"] += 1

out = {"_about": "Counted from %d real turn-0 saves (game v123). Capital rings excluded from terrain/resource rates." % len(saves),
       "terrain_counts": {t: dict(c) for t, c in sorted(terrain.items())},
       "resource_counts": {"|".join(k): dict(v) for k, v in sorted(resource.items())},
       "capital_ring": {t: {"n": len(v), "mean_total": round(sum(v) / len(v), 2), "pairs": dict(ring_pairs[t])} for t, v in sorted(ring_tot.items())},
       "capital_ring_templates": {t: v for t, v in sorted(ring_tpl.items())},
       "by_map_type": {}}
for mt, rows in by_type.items():
    out["by_map_type"][mt] = {"games": len(rows), "settlements_per_slot": round(sum(r["settlements"] for r in rows) / sum(r["slots"] for r in rows), 3),
                              "land_ratio": round(sum(r["land"] for r in rows) / len(rows), 3),
                              "starfish_per_water": round(sum(r["starfish"] for r in rows) / max(1, sum(r["water"] for r in rows)), 4),
                              "rows": rows}
json.dump(out, open(sys.argv[3], "w"), indent=1)
print("saves", len(saves))
for mt, v in out["by_map_type"].items(): print(mt, {k: v[k] for k in ("games", "settlements_per_slot", "land_ratio", "starfish_per_water")})
for t, v in out["capital_ring"].items(): print(t, v)
