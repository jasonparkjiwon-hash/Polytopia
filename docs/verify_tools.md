# verify/: checking the dataset without screenshots

| File | What it does |
|---|---|
| `run_all.sh` | Rebuilds the dataset and runs every check below. |
| `parse_polyfish.py` | Turns the Polyfish engine's Rust rule tables into `polyfish_tables.json`. |
| `crosscheck.py` | Compares our dataset with Polyfish field by field and writes `crosscheck_polyfish.md`. |
| `extract_enums.py` | Extracts the game's numeric ids (terrain, resource, building, unit, tribe, tech) into `game_enums.json`. |
| `state2json/` | Go tool that converts a real `.state` save into JSON. It is built on samuelyuan/polytopiamapmodelgo (MIT). |
| `analyze_map.py` | Measures real maps (`state2json` exports or Polyfish JSON states) against each open conflict. |
| `c23_models.py` | Pre-registered test for C23. It simulates three generator models and scores observations by Bayes factor. |

## Real save to report

```
state2json/state2json game.state game.json
python3 -I analyze_map.py game_enums.json game.json more.json --out report.json
```

## Scoring capital counts from the test sheet

1. Write the counts as a JSON list:

   ```json
   [{"tribe": "Imperius", "visible_total": 3}, {"tribe": "Bardur", "full_total": 5}]
   ```

   Use `full_total` only when every resource is visible, either from a save or because the tribe already has the right techs.

2. Run the scorer on that file:

   ```
   python3 -I c23_models.py obs.json
   ```

## Build notes

- The cloud workspace cannot reach crates.io, pypi or proxy.golang.org.
- Go dependencies build with `GOPROXY=direct GOSUMDB=off GOFLAGS=-mod=mod`, which fetches them from GitHub.
- Polyfish's Rust engine cannot be built here until crates.io is allowed.

## The one sample tested

The analyser was tested on Polyfish's `saved_state.json` (game version 115, turn 11).

This file is a pipeline test only, not evidence: harvested resources are already gone by turn 11, and the file may be a simulator game.


## verify/run_all.sh

```
#!/bin/sh
# Rebuild the dataset, then run every check. Exit non-zero if a hard check fails.
set -e
D=$(cd "$(dirname "$0")/.." && pwd)
python3 -I "$D/data/build_dataset.py" > /dev/null
python3 -I "$D/data/validate_dataset.py" | tail -3
PF="$D/ext/HenBOMB_Polyfish/polyfish-rs/src"
if [ -d "$PF" ]; then
  python3 -I "$D/verify/parse_polyfish.py" "$PF" "$D/verify/polyfish_tables.json"
  python3 -I "$D/verify/crosscheck.py" "$D/data" "$D/verify/polyfish_tables.json" "$D/verify/crosscheck_polyfish.md" "$D/verify/crosscheck_polyfish.json" | head -1
fi
python3 -I "$D/verify/c23_models.py" | head -17 > "$D/verify/c23_summary.txt"
echo "all checks ran"

```


## verify/parse_polyfish.py

```
"""Parse Polyfish (HenBOMB/Polyfish, targets game version 115 'Cymanti Rework') static tables into JSON.
Usage: python3 parse_polyfish.py <polyfish-rs/src> <out.json>"""
import re, sys, json, os
src, out = sys.argv[1], sys.argv[2]
norm = lambda s: re.sub(r'[^a-z0-9]', '', s.lower())

def blocks(text, pat):
    # yields (name, body) for `Name => Struct { ... }` handling nested braces
    for m in re.finditer(pat, text):
        i = text.index('{', m.end() - 1); depth = 0; j = i
        while True:
            if text[j] == '{': depth += 1
            elif text[j] == '}':
                depth -= 1
                if depth == 0: break
            j += 1
        yield m.group(1), text[i + 1:j]

def field(body, name, cast=str):
    m = re.search(r'\b' + name + r'\s*:\s*([^,\n]+)', body)
    if not m: return None
    v = m.group(1).strip()
    sm = re.match(r'Some\((.*)\)$', v)
    if sm: v = sm.group(1)
    if v == 'None': return None
    v = v.split('::')[-1]
    try: return cast(v)
    except Exception: return v

units = {}
t = open(os.path.join(src, 'settings/units.rs')).read()
for name, body in blocks(t, r'U::(\w+)\s*=>\s*UnitSetting\s*\{'):
    sk = re.search(r'skills!\[([^\]]*)\]', body)
    units[name] = {"cost": field(body, 'cost', int), "attack": field(body, 'attack', float),
                   "movement": field(body, 'movement', int), "defense": field(body, 'defense', float),
                   "range": field(body, 'range', int), "health": field(body, 'health', float),
                   "upgrade_from": field(body, 'upgrade_from'),
                   "skills": sorted(s.strip().split('::')[-1] for s in sk.group(1).split(',') if s.strip()) if sk else []}
techs = {}
t = open(os.path.join(src, 'settings/technology.rs')).read()
for name, body in blocks(t, r'^\s{8}(\w+)\s*=>\s*TechnologySetting\s*\{'.replace('^', '(?m)^')):
    techs[name] = {"tier": field(body, 'tier', int), "requires": field(body, 'requires'),
                   "replaces_tech": field(body, 'replaces_tech'), "tribe_type": field(body, 'tribe_type'),
                   "unlocks_unit": field(body, 'unlocks_unit'), "unlocks_structure": field(body, 'unlocks_structure'),
                   "unlocks_terrain": field(body, 'unlocks_terrain'), "explicit_cost": field(body, 'explicit_cost', int)}
res = {}
t = open(os.path.join(src, 'settings/resources.rs')).read()
for name, body in blocks(t, r'(?m)^\s{8}(\w+)\s*=>\s*ResourceSetting\s*\{'):
    vis = re.search(r'visible_required:\s*vec!\[([^\]]*)\]', body)
    res[name] = {"cost": field(body, 'cost', int), "tech_required": field(body, 'tech_required'),
                 "struct_required": field(body, 'struct_required'),
                 "visible_required": [v.strip() for v in vis.group(1).split(',') if v.strip()] if vis else [],
                 "reward_pop": field(body, 'reward_pop', int), "reward_stars": field(body, 'reward_stars', int)}
structs = {}
t = open(os.path.join(src, 'settings/structures.rs')).read()
for name, body in blocks(t, r'StructureType::(\w+)\s*=>\s*StructureSetting\s*\{'):
    structs[name] = {k: field(body, k, int) if k in ("cost","reward_pop","reward_stars","reward_score") else field(body, k) for k in ("cost", "reward_pop", "reward_stars", "reward_score", "tribe_type")}
json.dump({"source": "HenBOMB/Polyfish polyfish-rs/src/settings (game version 115, commit 2026-09-02)",
           "units": units, "techs": techs, "resources": res, "structures": structs}, open(out, 'w'), indent=1)
print(len(units), "units", len(techs), "techs", len(res), "resources", len(structs), "structures")

```


## verify/crosscheck.py

```
"""Cross-check our dataset (PolyEnv+wiki based) against Polyfish tables (game version 115).
Two independent reimplementations agreeing = strong evidence; disagreeing = a conflict to resolve.
Usage: python3 -I crosscheck.py <data_dir> <polyfish_tables.json> <out.md> <out.json>"""
import json, sys, re, os
data, pf_path, out_md, out_json = sys.argv[1:5]
L = lambda n: json.load(open(os.path.join(data, n), encoding="utf-8"))
ours_u, ours_t, ours_e = L("units.json")["units"], L("tech_tree.json")["techs"], L("economy.json")
pf = json.load(open(pf_path))
norm = lambda s: re.sub(r"[^a-z0-9]", "", str(s).lower())
SKILL_ALIAS = {"staticskill": "static", "air": "fly", "heal": "healothers", "wateronly": "float", "water": "float"}
snorm = lambda s: SKILL_ALIAS.get(norm(s), norm(s))
ALIAS = {"mindbender": "mindbender", "scout": "scoutship", "rammer": "rammership", "bomber": "bomber",
         "game": "animal", "hunting": "hunting"}
rows = []
def cmp(area, item, fld, a, b):
    if a is None and b is None: return
    try: same = abs(float(a) - float(b)) < 1e-9
    except Exception: same = norm(a) == norm(b)
    rows.append({"area": area, "item": item, "field": fld, "ours": a, "polyfish": b, "agree": same})

pfu = {norm(k): (k, v) for k, v in pf["units"].items()}
for name, u in ours_u.items():
    key = norm(name); key = ALIAS.get(key, key)
    if key not in pfu:
        rows.append({"area": "unit", "item": name, "field": "(exists)", "ours": "yes", "polyfish": "missing", "agree": False}); continue
    _, p = pfu[key]
    for a, b in (("cost", "cost"), ("attack", "attack"), ("defense", "defense"), ("movePoints", "movement"), ("range", "range"), ("maxHealth", "health")):
        if a in ("cost", "maxHealth") and not u.get(a): continue   # PE stores 0 for untrainable / inherited values
        cmp("unit", name, a, u.get(a), p.get(b))
    cmp("unit", name, "skills", ",".join(sorted(set(map(snorm, u.get("skills", []))))), ",".join(sorted(set(map(snorm, p.get("skills", []))))))

pft = {norm(k): v for k, v in pf["techs"].items()}
for name, t in ours_t.items():
    p = pft.get(norm(name))
    if not p:
        rows.append({"area": "tech", "item": name, "field": "(exists)", "ours": "yes", "polyfish": "missing", "agree": False}); continue
    cmp("tech", name, "tier", t["tier"], p["tier"])
    cmp("tech", name, "prerequisite", t["prerequisite"], p["requires"])
for name, p in pf["techs"].items():
    if norm(name) not in {norm(k) for k in ours_t} and not p.get("tribe_type") and not p.get("replaces_tech") and name not in ("Basic", "BeyondComprehension"):
        rows.append({"area": "tech", "item": name, "field": "(exists)", "ours": "missing", "polyfish": "base tech", "agree": False})

pfs = {norm(k): v for k, v in pf["structures"].items()}
for name, b in ours_e["buildings"].items():
    if not isinstance(b, dict) or "cost" not in b: continue
    p = pfs.get(norm(name))
    if p: cmp("building", name, "cost", b["cost"], p["cost"])
for name, a in ours_e["tile_actions"].items():
    if isinstance(a, dict) and "cost" in a:
        rows.append({"area": "tile_action", "item": name, "field": "cost", "ours": a["cost"], "polyfish": "see version_sync.rs", "agree": None})

agree = sum(1 for r in rows if r["agree"] is True); dis = [r for r in rows if r["agree"] is False]
json.dump({"agree": agree, "disagree": len(dis), "rows": rows}, open(out_json, "w"), indent=1)
with open(out_md, "w") as f:
    f.write("# Cross-check: our dataset vs Polyfish (game v115)\n\n")
    f.write(f"{agree} fields agree, {len(dis)} disagree or are missing on one side.\n\n## Disagreements\n\n")
    f.write("| Area | Item | Field | Ours (PE/wiki) | Polyfish v115 |\n|---|---|---|---|---|\n")
    for r in dis: f.write(f"| {r['area']} | {r['item']} | {r['field']} | {r['ours']} | {r['polyfish']} |\n")
print(agree, "agree;", len(dis), "disagree")
for r in dis: print(" ", r["area"], r["item"], r["field"], r["ours"], "|", r["polyfish"])

```


## verify/extract_enums.py

```
"""Extract Rust enums (name = int) from Polyfish types.rs -> JSON id maps. These mirror the real game's enum ids
because Polyfish loads JSON states captured from the real game. Usage: extract_enums.py <types.rs> <out.json>"""
import re, sys, json
t = open(sys.argv[1]).read()
out = {}
for m in re.finditer(r'pub enum (\w+)\s*\{(.*?)\n\}', t, re.S):
    vals = {}; nxt = 0
    for line in m.group(2).split('\n'):
        line = line.split('//')[0].strip().rstrip(',')
        if not line or line.startswith('#'): continue
        mm = re.match(r'^(\w+)\s*(?:=\s*(-?\d+))?$', line)
        if not mm: continue
        v = int(mm.group(2)) if mm.group(2) is not None else nxt
        vals[str(v)] = mm.group(1); nxt = v + 1
    if vals: out[m.group(1)] = vals
json.dump(out, open(sys.argv[2], 'w'), indent=1)
print({k: len(v) for k, v in out.items()})

```


## verify/analyze_map.py

```
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
                              "seen_by": [i for i, v in enumerate(t.get("PlayerVisibility") or []) if v] if False else list(t.get("PlayerVisibility") or [])}
        players = [{"id": p.get("PlayerId"), "tribe": E["TribeType"].get(p.get("Tribe"), p.get("Tribe")), "stars": p.get("Currency"),
                    "score": p.get("Score"), "techs": [E["TechnologyType"].get(x, x) for x in (p.get("AvailableTech") or [])]}
                   for p in d["initialPlayers"]]
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

```


## verify/c23_models.py

```
"""Pre-registered test for conflict C23 (how many resources sit in a capital's 8-tile ring).

Three candidate generator models are simulated; each gives a probability distribution over the ring count.
Real observations (from .state files or the test sheet) are then scored by likelihood, so the verdict rule is
fixed BEFORE data arrives:  a model wins when its Bayes factor over every rival exceeds 10.

Models (all use the wiki tribe terrain modifiers and the inner-ring rates 18/18/19/11, fish 50%):
  PE      : rates are P(resource | terrain); guarantee only Bardur/Imperius/Kickoo/Zebasi (PolyEnv)
  WIKI    : table rows are shares of all tiles -> P(resource | terrain) = share / terrain share; every capital forced to >=2 identical
  POLYFISH: rates are P(resource | terrain); primary resource capped at 3; every tribe with a primary forced to 2 (Polyfish v115)
Visibility: crops need Organization/Farming/Construction, metal needs Climbing/Mining/Smithery (Polyfish resources.rs),
so a turn-1 screenshot only shows fruit, animals and fish unless the tribe starts with those techs.

Usage: python3 -I c23_models.py [observations.json]   (observations: [{"tribe":"Imperius","visible_total":3,"full_total":null}, ...])"""
import random, json, sys, math, collections

MOD = {  # wiki Map Generation table (mountain, forest multipliers; resource multipliers)
 "XinXi": ({"mountain": 1.5}, {"metal": 1.5}), "Imperius": ({}, {"animal": 0.5, "fruit": 2.0}), "Bardur": ({}, {"fruit": 1.5, "crop": 0.0}),
 "Oumaji": ({"forest": 0.2, "mountain": 0.5}, {"animal": 0.2}), "Kickoo": ({"mountain": 0.5}, {"fish": 1.5}), "Hoodrick": ({"mountain": 0.5, "forest": 1.5}, {}),
 "Luxidoor": ({}, {}), "Vengir": ({}, {"metal": 2.0, "animal": 0.1, "fruit": 0.1, "fish": 0.1}), "Zebasi": ({"mountain": 0.5, "forest": 0.5}, {"fruit": 0.5}),
 "AiMo": ({"mountain": 1.5}, {"crop": 0.1}), "Quetzali": ({}, {"fruit": 2.0, "crop": 0.1}), "Yadakk": ({"mountain": 0.5, "forest": 0.5}, {"fruit": 1.5}),
 "Elyrion": ({"mountain": 0.5}, {"crop": 1.5}), "Aquarion": ({"forest": 0.5}, {}), "Cymanti": ({"mountain": 1.2}, {}),
}
START_TECH = {"XinXi": "Climbing", "Imperius": "Organization", "Bardur": "Hunting", "Oumaji": "Riding", "Kickoo": "Fishing", "Hoodrick": "Archery",
              "Luxidoor": None, "Vengir": "Smithery", "Zebasi": "Farming", "AiMo": "Philosophy", "Quetzali": "Strategy", "Yadakk": "Roads",
              "Elyrion": "ForestMagic", "Aquarion": None, "Cymanti": "Farming"}
WIKI_GUARANTEE = {"Bardur": "animal", "Imperius": "fruit", "Kickoo": "fish", "Zebasi": "crop", "Elyrion": "animal", "Cymanti": "crop",
                  "XinXi": "metal", "Oumaji": "fruit", "Hoodrick": "animal"}          # others: random tier-1 (fish/animal/fruit)
PE_GUARANTEE = {"Bardur": "animal", "Imperius": "fruit", "Kickoo": "fish", "Zebasi": "crop"}
PF_PRIMARY = {"Imperius": "fruit", "Quetzali": "fruit", "Yadakk": "fruit", "Bardur": "animal", "Elyrion": "animal", "Hoodrick": "animal",
              "Kickoo": "fish", "Aquarion": "fish", "Zebasi": "crop", "Cymanti": "crop"}
INNER = {"fruit": 0.18, "crop": 0.18, "animal": 0.19, "metal": 0.11, "fish": 0.50}
WATER_SHARE_LAKES = 0.28   # Polyfish land ratio 0.72 for Lakes; capital tiles are land but neighbours may be water

def biome(tribe):
    m, _ = MOD[tribe]; mt = 0.14 * m.get("mountain", 1); rest = 1 - mt
    fo = 0.38 / 0.86 * rest * m.get("forest", 1); fi = 1 - mt - fo
    return {"Mountain": mt, "Forest": fo, "Field": fi}

def rate(tribe, res, model):
    r = INNER[res] * MOD[tribe][1].get(res, 1.0)
    if model == "WIKI" and res != "fish":
        r = r / {"fruit": 0.48, "crop": 0.48, "animal": 0.38, "metal": 0.14}[res]   # share -> conditional
    return min(r, 1.0)

def visible(tribe, res):
    t = START_TECH[tribe]
    if res == "crop": return t in ("Organization", "Farming", "Construction")
    if res == "metal": return t in ("Climbing", "Mining", "Smithery")
    return True

def ring(tribe, model, rng):
    b = biome(tribe); tiles = []
    for _ in range(8):
        if rng.random() < WATER_SHARE_LAKES:
            tiles.append(("Water", "fish" if rng.random() < rate(tribe, "fish", model) else None)); continue
        x = rng.random(); t = "Mountain" if x < b["Mountain"] else "Forest" if x < b["Mountain"] + b["Forest"] else "Field"
        if t == "Field":
            f, c = rate(tribe, "fruit", model), rate(tribe, "crop", model); y = rng.random()
            tot = f + c
            if tot > 1: f, c = f / tot, c / tot
            res = "fruit" if y < f else "crop" if y < f + c else None
        elif t == "Forest": res = "animal" if rng.random() < rate(tribe, "animal", model) else None
        else: res = "metal" if rng.random() < rate(tribe, "metal", model) else None
        tiles.append((t, res))
    cnt = collections.Counter(r for _, r in tiles if r)
    if model == "POLYFISH" and tribe in PF_PRIMARY:
        p = PF_PRIMARY[tribe]
        while cnt[p] > 3: cnt[p] -= 1
        if cnt[p] < 2: cnt[p] = 2                     # force-spawn by replacing tiles (approximation: adds without removing)
    guarantee = WIKI_GUARANTEE if model == "WIKI" else PE_GUARANTEE if model == "PE" else {}
    if model == "WIKI" and not any(v >= 2 for v in cnt.values()):
        g = guarantee.get(tribe) or rng.choice(["fish", "animal", "fruit"]); cnt[g] = max(cnt[g], 2)
    elif model == "PE" and tribe in guarantee and cnt[guarantee[tribe]] < 2:
        cnt[guarantee[tribe]] = 2
    full = sum(cnt.values()); vis = sum(v for k, v in cnt.items() if visible(tribe, k))
    return full, vis

def distributions(n=20000, seed=7):
    rng = random.Random(seed); out = {}
    for model in ("PE", "WIKI", "POLYFISH"):
        out[model] = {}
        for tribe in MOD:
            full = collections.Counter(); vis = collections.Counter()
            for _ in range(n):
                f, v = ring(tribe, model, rng); full[f] += 1; vis[v] += 1
            out[model][tribe] = {"full": {k: c / n for k, c in sorted(full.items())}, "visible": {k: c / n for k, c in sorted(vis.items())},
                                 "mean_full": round(sum(k * c for k, c in full.items()) / n, 2), "mean_visible": round(sum(k * c for k, c in vis.items()) / n, 2)}
    return out

def score(dist, obs):
    ll = {m: 0.0 for m in dist}
    for o in obs:
        key, val = ("full", o["full_total"]) if o.get("full_total") is not None else ("visible", o["visible_total"])
        for m in dist: ll[m] += math.log(max(dist[m][o["tribe"]][key].get(val, 0.0), 1e-4))
    best = max(ll, key=ll.get)
    bf = {m: round(math.exp(ll[best] - ll[m]), 1) for m in ll if m != best}
    return {"log_likelihood": {m: round(v, 2) for m, v in ll.items()}, "leader": best, "bayes_factor_vs_others": bf,
            "decided": all(v > 10 for v in bf.values()), "n_capitals": len(obs)}

if __name__ == "__main__":
    d = distributions()
    json.dump(d, open("c23_model_distributions.json", "w"), indent=1)
    print("%-9s" % "tribe" + "".join("%18s" % m for m in d) + "   (mean full ring / mean visible on turn 1)")
    for t in MOD: print("%-9s" % t + "".join("%11.2f /%5.2f" % (d[m][t]["mean_full"], d[m][t]["mean_visible"]) for m in d))
    if len(sys.argv) > 1:
        print(json.dumps(score(d, json.load(open(sys.argv[1]))), indent=1))
    # power analysis: how many capitals until a decision, if each model were true?
    rng = random.Random(11)
    for truth in d:
        need = []
        for trial in range(200):
            obs = []
            for k in range(1, 61):
                tribe = rng.choice(list(MOD)); f, v = ring(tribe, truth, rng); obs.append({"tribe": tribe, "full_total": f})
                s = score(d, obs)
                if s["decided"]: need.append((k, s["leader"] == truth)); break
            else: need.append((61, False))
        ks = sorted(k for k, _ in need); acc = sum(ok for _, ok in need) / len(need)
        print(f"if {truth} is true: median {ks[len(ks)//2]} capitals (90th pct {ks[int(len(ks)*0.9)]}) to decide from full counts; correct verdict {acc:.0%}")

```


## verify/state2json/main.go

```
// state2json: convert a Battle of Polytopia .state save file to JSON (initial map + current map + players + header).
// Built on github.com/samuelyuan/polytopiamapmodelgo. Usage: state2json <in.state> <out.json>
package main

import (
	"encoding/json"
	"fmt"
	"os"

	pm "github.com/samuelyuan/polytopiamapmodelgo"
)

func main() {
	if len(os.Args) < 3 {
		fmt.Println("usage: state2json <in.state> <out.json>")
		os.Exit(2)
	}
	s, err := pm.ReadPolytopiaCompressedFile(os.Args[1])
	if err != nil {
		fmt.Println("FAILED:", err)
		os.Exit(1)
	}
	out := map[string]interface{}{
		"format": "polytopia-state-json/1", "gameVersion": s.GameVersion,
		"mapWidth": s.MapWidth, "mapHeight": s.MapHeight, "currentTurn": s.MaxTurn,
		"header": s.MapHeaderOutput, "initialTiles": s.InitialTileData, "initialPlayers": s.InitialPlayerData,
		"tiles": s.TileData, "players": s.PlayerData, "captures": s.TurnCaptureMap,
	}
	b, _ := json.Marshal(out)
	if err := os.WriteFile(os.Args[2], b, 0644); err != nil {
		fmt.Println("FAILED:", err)
		os.Exit(1)
	}
	fmt.Printf("OK version=%d size=%dx%d turn=%d players=%d\n", s.GameVersion, s.MapWidth, s.MapHeight, s.MaxTurn, len(s.PlayerData))
}

```


## verify/state2json/go.mod

```
module state2json

go 1.24

require github.com/samuelyuan/polytopiamapmodelgo v0.0.0

require github.com/pierrec/lz4/v4 v4.1.22 // indirect

replace github.com/samuelyuan/polytopiamapmodelgo => ../../ext/polytopiamapmodelgo

```
