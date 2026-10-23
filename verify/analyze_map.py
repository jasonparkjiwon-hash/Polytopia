"""Measure real Polytopia maps to settle dataset conflicts without screenshots.

Input: either a state2json export of a real .state save (preferred: it contains the TURN-0 map, every tile,
fog per player) or a Polyfish JSON state (live_game.json / saved_state.json from the PolyMod capture mod).
Output: a JSON report + printed summary of every metric tied to an open conflict ID.

Usage: python3 -I analyze_map.py <game_enums.json> <state.json> [more states...] --out report.json
Pool many games: pass many files; per-game rows plus pooled stats are written."""
import json, sys, math, collections, os

def load_enums(p):
    e = json.load(open(p))
    return {k: {int(i): n for i, n in v.items()} for k, v in e.items()}

def normalise(path, E):
    """Return a common schema: size, version, map_type, tiles[idx] = dict(x,y,terrain,resource,improvement,owner,capital_of,seen_by), players."""
    d = json.load(open(path))
    T, R, S = E["TerrainType"], E["ResourceType"], E["StructureType"]
    if d.get("format", "").startswith("polytopia-state-json"):           # state2json export of a real .state file
        rows = d["initialTiles"]; W, H = d["mapWidth"], d["mapHeight"]
        tiles = {}
        for row in rows:
            for t in row:
                x, y = t["WorldCoordinates"]; idx = y * W + x
                tiles[idx] = {"x": x, "y": y, "terrain": T.get(t["Terrain"], str(t["Terrain"])),
                              "resource": R.get(t["ResourceType"]) if t.get("ResourceExists") else None,
                              "improvement": S.get(t["ImprovementType"], str(t["ImprovementType"])) if t.get("ImprovementExists") else None,
                              "owner": t["Owner"], "capital_of": t["Capital"] or 0,
                              "seen_by": list(t.get("PlayerVisibility") or []),
                              "biome": E["TribeType"].get(t.get("Climate"), t.get("Climate"))}
        players = [{"id": p.get("PlayerId"), "tribe": E["TribeType"].get(p.get("Tribe"), p.get("Tribe")), "stars": p.get("Currency"),
                    "score": p.get("Score"), "techs": [E["TechnologyType"].get(x, x) for x in (p.get("AvailableTech") or [])]}
                   for p in d["initialPlayers"]]
        if not players:   # newer saves: derive each player's tribe from its capital tile's climate
            players = [{"id": t["capital_of"], "tribe": t["biome"]} for t in tiles.values() if t["capital_of"]]
        hdr = d.get("header", {}).get("MapHeaderInput", {})
        return {"source": os.path.basename(path), "kind": "real .state (turn-0 map)", "version": d["gameVersion"], "size": W,
                "map_type": E["MapType"].get(hdr.get("MapPreset"), hdr.get("MapPreset")), "turn_of_map": 0, "tiles": tiles, "players": players}
    # Polyfish JSON (current map only, so harvested resources are already gone)
    s = d["settings"]; size = s["size"]; tiles = {}
    for k, t in d["tiles"].items():
        idx = int(k); r = (d["resources"].get(k) or {}); st = (d["structures"].get(k) or {})
        tiles[idx] = {"x": t["coords"]["x"], "y": t["coords"]["y"], "terrain": T.get(t["type"], t["type"]),
                      "resource": R.get(r.get("type")) if r else None, "improvement": S.get(st.get("type")) if st else None,
                      "owner": t.get("owner", 0), "capital_of": t.get("capitalOf", 0), "seen_by": t.get("explorers", [])}
    players = [{"id": p["id"], "tribe": E["TribeType"].get(p["type"], p["type"]), "stars": p["stars"], "score": p["score"]} for p in d["tribes"].values()]
    return {"source": os.path.basename(path), "kind": "Polyfish JSON (current map, turn %d)" % s["turn"], "version": s["version"], "size": size,
            "map_type": E["MapType"].get(s["mapType"], s["mapType"]), "turn_of_map": s["turn"], "tiles": tiles, "players": players}

def ring(g, cx, cy, r):
    out = []
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if (dx or dy) and 0 <= cx + dx < g["size"] and 0 <= cy + dy < g["size"]:
                out.append(g["tiles"][(cy + dy) * g["size"] + cx + dx])
    return out

def analyse(g, mapgen):
    size, tiles = g["size"], g["tiles"]; n = size * size
    rep = {"source": g["source"], "kind": g["kind"], "version": g["version"], "size": size, "map_type": g["map_type"]}
    terr = collections.Counter(t["terrain"] for t in tiles.values())
    land = sum(v for k, v in terr.items() if k not in ("Water", "Ocean"))
    rep["land_fraction"] = round(land / n, 3)                                        # G1 per map type
    rep["terrain_counts"] = dict(terr)
    caps = [t for t in tiles.values() if t["capital_of"]]
    rep["capitals"] = []
    for c in caps:                                                                    # C23, C10
        r1, r2 = ring(g, c["x"], c["y"], 1), ring(g, c["x"], c["y"], 2)
        res1 = collections.Counter(t["resource"] for t in r1 if t["resource"])
        owner_tribe = next((p["tribe"] for p in g["players"] if p["id"] == c["capital_of"]), None)
        rep["capitals"].append({"player": c["capital_of"], "tribe": owner_tribe,
            "ring8_resources": dict(res1), "ring8_total": sum(res1.values()),
            "ring24_total": sum(1 for t in r2 if t["resource"]),
            "has_2_identical": any(v >= 2 for v in res1.values()),
            "ring8_terrain": dict(collections.Counter(t["terrain"] for t in r1))})
    imp = collections.Counter(t["improvement"] for t in tiles.values() if t["improvement"])
    rep["villages_and_cities"] = imp.get("Village", 0)                                # C9 (cities are Village with owner)
    rep["non_capital_settlements"] = imp.get("Village", 0) - len(caps)
    rep["village_grid_slots"] = (size // 3) ** 2
    rep["ruins"] = imp.get("Ruin", 0)                                                  # ruin table check
    rep["ruins_expected_table"] = mapgen["ruins"]["count_by_tiles"]["v"].get(str(n))
    water = terr.get("Water", 0) + terr.get("Ocean", 0)
    rep["starfish"] = sum(1 for t in tiles.values() if t["resource"] == "Starfish")    # G2
    rep["starfish_expected_water_div_25"] = water // 25
    rep["lighthouses"] = imp.get("Lighthouse", 0)
    # fish rate on shallow water within 2 of any settlement (wiki 50%, PE guess)
    settle = [t for t in tiles.values() if t["improvement"] == "Village"]
    near = {id(x): x for s in settle for x in ring(g, s["x"], s["y"], 2) if x["terrain"] == "Water"}
    rep["fish_rate_shallow_near_settlement"] = round(sum(1 for x in near.values() if x["resource"] == "Fish") / len(near), 3) if near else None
    # field/forest/mountain resource rates near settlements, both readings of C23
    for k, terrain, resn in (("fruit", "Field", "Fruit"), ("crop", "Field", "Crop"), ("animal", "Forest", "Game"), ("metal", "Mountain", "Metal")):
        inner = [x for s in settle for x in ring(g, s["x"], s["y"], 1)]
        same = [x for x in inner if x["terrain"] == terrain]
        rep[f"P({k}|{terrain},inner)"] = round(sum(1 for x in same if x["resource"] == resn) / len(same), 3) if same else None
        rep[f"share({k},inner_all_land)"] = round(sum(1 for x in inner if x["resource"] == resn) / max(1, sum(1 for x in inner if x['terrain'] not in ('Water', 'Ocean'))), 3)
    rep["explored_tiles_per_player"] = dict(collections.Counter(p for t in tiles.values() for p in t["seen_by"]))   # C21 at turn 0
    rep["players"] = g["players"]                                                      # C1-C5, C17 start packages
    return rep

def pooled(reps):
    caps = [c for r in reps for c in r["capitals"]]
    out = {"games": len(reps), "capitals": len(caps)}
    if caps:
        tot = [c["ring8_total"] for c in caps]
        out["ring8_total_mean"] = round(sum(tot) / len(tot), 2)
        out["share_with_2_identical"] = round(sum(c["has_2_identical"] for c in caps) / len(caps), 2)
        out["verdict_C23"] = ("wiki-shares reading (~5)" if out["ring8_total_mean"] >= 4 else
                              "PE conditional reading (~2-3)" if out["ring8_total_mean"] <= 3.2 else "between: need more games")
    by_type = collections.defaultdict(list)
    for r in reps: by_type[r["map_type"]].append(r["land_fraction"])
    out["land_fraction_by_map_type"] = {k: round(sum(v) / len(v), 3) for k, v in by_type.items()}
    return out

if __name__ == "__main__":
    args = sys.argv[1:]; out = "report.json"
    if "--out" in args: i = args.index("--out"); out = args[i + 1]; args = args[:i] + args[i + 2:]
    E = load_enums(args[0]); mapgen = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "map_generation.json")))
    reps = [analyse(normalise(p, E), mapgen) for p in args[1:]]
    res = {"per_game": reps, "pooled": pooled(reps)}
    json.dump(res, open(out, "w"), indent=1)
    for r in reps:
        print(f"== {r['source']}  [{r['kind']}]  v{r['version']} {r['size']}x{r['size']} {r['map_type']}")
        print(f"   land {r['land_fraction']}  settlements {r['villages_and_cities']} (grid slots {r['village_grid_slots']})  ruins {r['ruins']} (table {r['ruins_expected_table']})  starfish {r['starfish']} (water/25 = {r['starfish_expected_water_div_25']})")
        for c in r["capitals"]: print(f"   capital p{c['player']} {c['tribe']}: ring-8 {c['ring8_resources']} total {c['ring8_total']}  2-identical={c['has_2_identical']}")
    print("POOLED", json.dumps(res["pooled"]))
