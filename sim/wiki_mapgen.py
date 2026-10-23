"""Wiki-literal Polytopia map generator.

Every number that the fandom wiki's Map Generation page states is applied as written (marked WIKI below).
Where the wiki is silent, a parameter is still needed to draw a map; each of those is marked PARAM with
where its value came from, so they can be swapped or tested. Nothing here is taken from Polyfish's code
except the four land-ratio PARAMs the wiki gives no number for.

Wiki reading used for the resource table: each column (inner / outer) sums to 100% of LAND tiles in that
zone, so P(resource | terrain) = share / terrain share (e.g. inner fruit on field = 18/48 = 0.375).
Since update 2.0.58 the wiki says terrain follows these percentages "or as close as possible", so terrain
and resources are assigned as exact quotas per tribe biome per zone, not as independent coin flips.

Two modes (generate(..., mode=...)):
  "measured" (default): numbers counted from Jason's real game saves (data/measured_mapgen.json, built by
      verify/build_measured_tables.py) come first; the wiki fills in where the saves are thin. Each measured rate is
      blended with the wiki value as a prior worth PRIOR_N tiles, so a cell with 2,000 tiles follows the game and a
      cell with 10 tiles stays near the wiki. Every place the saves overrule the wiki is marked MEASURED.
  "wiki": the wiki-literal generator, kept so the two can still be compared.

Usage:  python3 -I wiki_mapgen.py --mode measured --type lakes --size 16 --tribes Imperius,Bardur,XinXi,Kickoo --seed 1 --out map.json
        (or import and call generate(...))"""
import math, random, json, argparse, os

MEASURED_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "measured_mapgen.json")
MEASURED = json.load(open(MEASURED_PATH)) if os.path.exists(MEASURED_PATH) else None
PRIOR_N = {"terrain": 50, "resource": 30}     # wiki prior strength, in tiles

# ---------------- WIKI numbers ----------------
BASE = {"mountain": 0.14, "forest": 0.38, "field": 0.48}                                          # WIKI
SHARE = {  # WIKI resource table: share of land tiles in the zone
    "inner": {"fruit": 0.18, "crop": 0.18, "field_empty": 0.12, "animal": 0.19, "forest_empty": 0.19, "metal": 0.11, "mountain_empty": 0.03},
    "outer": {"fruit": 0.06, "crop": 0.06, "field_empty": 0.36, "animal": 0.06, "forest_empty": 0.32, "metal": 0.03, "mountain_empty": 0.11}}
FISH_SHARE = 0.50                                                                                  # WIKI: 50% of shallow water tiles
TRIBE_MOD = {  # WIKI tribe modifier table (multipliers); water modifiers are listed but not applied in the game (WIKI)
    "XinXi": {"mountain": 1.5, "metal": 1.5}, "Imperius": {"animal": 0.5, "fruit": 2.0}, "Bardur": {"fruit": 1.5, "crop": 0.0},
    "Oumaji": {"forest": 0.2, "animal": 0.2, "mountain": 0.5}, "Kickoo": {"mountain": 0.5, "fish": 1.5}, "Hoodrick": {"mountain": 0.5, "forest": 1.5},
    "Luxidoor": {}, "Vengir": {"metal": 2.0, "animal": 0.1, "fruit": 0.1, "fish": 0.1}, "Zebasi": {"mountain": 0.5, "forest": 0.5, "fruit": 0.5},
    "AiMo": {"mountain": 1.5, "crop": 0.1}, "Quetzali": {"fruit": 2.0, "crop": 0.1}, "Yadakk": {"mountain": 0.5, "forest": 0.5, "fruit": 1.5},
    "Aquarion": {"forest": 0.5}, "Elyrion": {"mountain": 0.5, "crop": 1.5}, "Cymanti": {"mountain": 1.2}}      # Cymanti: spores replace crops (WIKI)
GUARANTEE = {"Bardur": "animal", "Imperius": "fruit", "Kickoo": "fish", "Zebasi": "crop", "Elyrion": "animal", "Cymanti": "crop",
             "XinXi": "metal", "Oumaji": "fruit", "Hoodrick": "animal"}                             # WIKI: >=2 identical; others random tier-1
TIER1 = ["fish", "animal", "fruit"]                                                                # WIKI
PRE_TERRAIN = {"drylands": 0.0, "waterworld": 0.10}                                                # WIKI (others 0.30)
VILLAGE_TOTAL = {"drylands": 0.80}                                                                 # WIKI (others 0.60 "after terrain")
SUBURBS = (1, 2)                                                                                   # WIKI: 1-2 per capital, not drylands/waterworld

# ---------------- PARAMs (wiki gives no number) ----------------
PARAMS = {
    "land_ratio": {"drylands": 1.0, "lakes": 0.733, "continents": 0.468, "pangea": 0.513, "archipelago": 0.399, "waterworld": 0.151},
    "land_ratio_src": "MEASURED on Jason's 6 real Massive saves (one per type, 16 players, game v123); wiki gives no numbers. May differ by map size.",
    "village_total_reading": "A (default): 60% of max = TOTAL after terrain; B: 60% of the slots still free after terrain. C9 / Q4 decides",
    "max_villages": "(size//3)^2 grid slots with >=3 spacing, not on the edge (PolyEnv; wiki: 'not deterministic')",
    "capital_spot": "random tile inside the player's domain, >=2 from its border and the map edge (wiki: capitals never within 2 of a domain border)",
    "biome_owner": "each land tile takes the tribe of the nearest capital (Chebyshev; wiki: land is divided between tribes)",
    "shallow_rule": "water edge-adjacent to land = shallow, else ocean (PolyEnv)",
    "resource_area": "inner = distance 1 of any settlement, outer = distance 2; none farther (PolyEnv + wiki inner/outer wording)",
    "ruins_count": {121: 4, 196: 5, 256: 7, 324: 9, 400: 11, 900: 23},
    "ruins_count_src": "PolyEnv table (wiki gives no count); placement uses the wiki rules",
    "starfish_count": "water tiles // 25 (PolyEnv; wiki: any water tile, no count)",
    "noise_smoothing_passes": 2,
}

def dist(a, b, n): return max(abs(a % n - b % n), abs(a // n - b // n))
def nbrs(i, n, r=1):
    x, y = i % n, i // n
    return [(y + dy) * n + x + dx for dy in range(-r, r + 1) for dx in range(-r, r + 1)
            if (dx or dy) and 0 <= x + dx < n and 0 <= y + dy < n]
def orth(i, n):
    x, y = i % n, i // n
    return [(y + dy) * n + x + dx for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)) if 0 <= x + dx < n and 0 <= y + dy < n]

FOREST_RULE = "renormalised"   # "wiki_text" | "renormalised" (fitted to real saves, see ledger C12)

def biome_shares(tribe, rule=None):
    """Mountain first (WIKI). Forest: wiki text multiplies forest and gives the rest to field; real saves fit better when the
    forest multiplier re-weights forest against field instead: forest = fb*mod / (fb*mod + field_b) * (1 - mountain)."""
    rule = rule or FOREST_RULE
    m = TRIBE_MOD.get(tribe, {})
    mountain = BASE["mountain"] * m.get("mountain", 1.0)
    forest_before = BASE["forest"] + (BASE["mountain"] - mountain) * (BASE["forest"] / (1 - BASE["mountain"]))
    if rule == "wiki_text":
        forest = min(forest_before * m.get("forest", 1.0), 1 - mountain)
    else:
        fw = forest_before * m.get("forest", 1.0); field_b = 1 - mountain - forest_before
        forest = fw / (fw + field_b) * (1 - mountain)
    return {"mountain": mountain, "forest": forest, "field": 1 - mountain - forest}

def cond_probs(tribe, zone):
    """P(resource | terrain) from the wiki share table, times the tribe multiplier; field split capped at 100%."""
    s, m = SHARE[zone], TRIBE_MOD.get(tribe, {})
    fruit = s["fruit"] / BASE["field"] * m.get("fruit", 1.0)
    crop = s["crop"] / BASE["field"] * m.get("crop", 1.0)
    if fruit + crop > 1.0: fruit, crop = fruit / (fruit + crop), crop / (fruit + crop)          # PARAM: proportional cap
    return {"field": {"fruit": fruit, "crop": crop},
            "forest": {"animal": min(1.0, s["animal"] / BASE["forest"] * m.get("animal", 1.0))},
            "mountain": {"metal": min(1.0, s["metal"] / BASE["mountain"] * m.get("metal", 1.0))},
            "water": {"fish": min(1.0, FISH_SHARE * m.get("fish", 1.0))}}

# ---------------- MEASURED overrides (27 saves, game v123; ledger C10, AQUACROP, C9) ----------------
GUARANTEE_MEASURED = dict(GUARANTEE, AiMo="animal", Polaris="animal", Aquarion="fish", Quetzali="fruit", Yadakk="fruit")
# MEASURED: every non-Vengir tribe's pair is fixed (e.g. Ai-Mo 20/20 animal, Aquarion 22/22 fish); the wiki says "random tier-1".
LUXIDOOR_RING = [("field", "fruit"), ("field", "fruit"), ("field", "crop"), ("forest", "animal"), ("forest", "animal"),
                 ("mountain", "metal"), ("water", "fish"), ("water", "fish")]
# MEASURED: all 18 Luxidoor capitals had exactly this 8-tile ring (Field 3, Forest 2, Mountain 1, Water 2).
def village_share(map_type, mode):
    if mode == "measured" and MEASURED and map_type in MEASURED["by_map_type"]:
        return MEASURED["by_map_type"][map_type]["settlements_per_slot"]       # MEASURED: settlements (incl. capitals) / (n//3)^2
    return VILLAGE_TOTAL.get(map_type, 0.60)

def _blend(counts, prior, k):
    """Posterior mean: measured counts plus the wiki distribution as k pseudo-tiles. Labels not in prior get prior 0."""
    tot = sum(counts.values()); labels = set(prior) | set(counts)
    return {l: (counts.get(l, 0) + k * prior.get(l, 0.0)) / (tot + k) for l in labels}

def shares_for(tribe, mode="measured"):
    w = biome_shares(tribe)
    if mode != "measured" or not MEASURED or tribe not in MEASURED["terrain_counts"]: return w
    b = _blend(MEASURED["terrain_counts"][tribe], w, PRIOR_N["terrain"])
    return {k: b.get(k, 0.0) for k in ("mountain", "forest", "field")}

def probs_for(tribe, zone, mode="measured"):
    """P(resource | terrain) per zone. Measured mode: counted from the saves (water now includes AquaCrop, which the wiki
    never mentions, and covers deep ocean in the zone too), blended with the wiki prior."""
    w = cond_probs(tribe, zone)
    if mode != "measured" or not MEASURED: return w
    out = {}
    for ter, wter in (("field", "field"), ("forest", "forest"), ("mountain", "mountain"), ("water", "water")):
        prior = dict(w[wter]); prior["none"] = max(0.0, 1 - sum(prior.values()))
        if ter == "water": prior.setdefault("aquacrop", 0.0)
        cnt = dict(MEASURED["resource_counts"].get(f"{tribe}|{zone}|{ter}", {}))
        if ter == "water":                                                      # shallow + ocean pooled
            for k, v in MEASURED["resource_counts"].get(f"{tribe}|{zone}|ocean", {}).items(): cnt[k] = cnt.get(k, 0) + v
        cnt.pop("starfish", None)                                               # starfish placed separately
        if ter == "water":   # the wiki has no AquaCrop at all, so water shrinks toward the all-tribe measured rate instead
            pool = {}
            for key, v in MEASURED["resource_counts"].items():
                _, z, tt = key.split("|")
                if z == zone and tt in ("water", "ocean"):
                    for r, x in v.items():
                        if r != "starfish": pool[r] = pool.get(r, 0) + x
            tot = sum(pool.values()); prior = {r: x / tot for r, x in pool.items()}
            if "fish" in TRIBE_MOD.get(tribe, {}):                              # keep the wiki's fish multiplier as a prior
                f = min(prior["fish"] * TRIBE_MOD[tribe]["fish"], 0.95); scale = (1 - f) / (1 - prior["fish"])
                prior = {r: (f if r == "fish" else x * scale) for r, x in prior.items()}
        b = _blend(cnt, prior, PRIOR_N["resource"]); b.pop("none", None)
        out[ter] = {k: v for k, v in b.items() if v > 0}
    return out

def ring_template(rng, tribe, c, n, map_type=None):
    """MEASURED: one real capital ring of this tribe, rotated/reflected at random -> {tile: (terrain, resource)}.
    Rings from the same map type are used when there are any (a Drylands capital rarely touches water)."""
    tpls = (MEASURED or {}).get("capital_ring_templates", {}).get(tribe)
    if not tpls: return None
    same = [t for t in tpls if t["map_type"] == map_type]
    tpl = rng.choice(same or tpls)["tiles"]; sym = rng.randrange(8); out = {}
    for dx, dy, ter, r in tpl:
        if sym & 1: dx = -dx
        if sym & 2: dy = -dy
        if sym & 4: dx, dy = dy, dx
        out[(c // n + dy) * n + c % n + dx] = ("water" if ter in ("water", "ocean") else ter, r)
    return out

def smooth(field, n, passes, outside):
    for _ in range(passes):
        new = []
        for i in range(n * n):
            x, y = i % n, i // n; tot = 0; c = 0
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    xx, yy = x + dx, y + dy
                    tot += field[yy * n + xx] if 0 <= xx < n and 0 <= yy < n else outside; c += 1
            new.append(tot / c)
        field = new
    return field

def quota_assign(rng, tiles, probs):
    """Exact-quota assignment: round(p * len) tiles get each label ('as close as possible', WIKI 2.0.58)."""
    tiles = list(tiles); rng.shuffle(tiles); out = {}; k = 0
    for label, p in probs.items():
        x = p * len(tiles); c = int(x) + (1 if rng.random() < x - int(x) else 0)   # unbiased rounding (small zones)
        for t in tiles[k:k + c]: out[t] = label
        k += c
    return out

def generate(map_type="lakes", size=16, tribes=("Imperius", "Bardur"), seed=0, village_reading="A", mode="measured"):
    """village_reading A: 60% (80% drylands) of the max is the TOTAL after terrain; B: 60% of the slots still free after terrain."""
    rng = random.Random(seed); n = size; N = n * n; P = len(tribes)
    terrain = ["field"] * N; res = [None] * N; imp = [None] * N; cap_of = [0] * N
    # 1. capitals in domains
    g = math.ceil(math.sqrt(P)); span = n // g
    cells = list(range(g * g)); rng.shuffle(cells); caps = []
    for p, cell in enumerate(cells[:P]):
        cx, cy = cell % g, cell // g
        cand = [y * n + x for y in range(cy * span + 2, (cy + 1) * span - 2) for x in range(cx * span + 2, (cx + 1) * span - 2)
                if 2 <= x < n - 2 and 2 <= y < n - 2]
        c = rng.choice(cand); caps.append(c); imp[c] = "Village"; cap_of[c] = p + 1
    settle = list(caps)
    rings = {c: ring_template(rng, tribes[p], c, n, map_type) for p, c in enumerate(caps)} if mode == "measured" else {}
    rings = {c: r for c, r in rings.items() if r}
    def ok_spot(i): x, y = i % n, i // n; return 0 < x < n - 1 and 0 < y < n - 1 and all(dist(i, s, n) >= 3 for s in settle)
    max_v = (n // 3) ** 2
    share = village_share(map_type, mode)
    total = round(share * max_v) if village_reading == "A" else None
    cap_total = total if (mode == "measured" and total) else 10 ** 9      # MEASURED: earlier steps may not overshoot the total
    # 2. suburbs
    if map_type not in ("drylands", "waterworld"):
        for c in caps:
            want = rng.randint(*SUBURBS)
            cand = [i for i in nbrs(c, n, 4) if ok_spot(i)]; rng.shuffle(cand)
            for i in cand:
                if want and ok_spot(i) and len(settle) < cap_total: imp[i] = "Village"; settle.append(i); want -= 1
    # 3. pre-terrain villages up to 30% (10% waterworld, 0 drylands) of max
    pre = min(cap_total, len(settle) + round(PRE_TERRAIN.get(map_type, 0.30) * (max_v - len(settle))))   # 'a third of the REMAINING villages' (WIKI)
    cand = list(range(N)); rng.shuffle(cand)
    for i in cand:
        if len(settle) >= pre: break
        if ok_spot(i): imp[i] = "Village"; settle.append(i)
    # 4. land / water from smoothed noise (PARAM land ratio), settlement tiles forced land
    land = [True] * N
    ratio = PARAMS["land_ratio"][map_type]
    if mode == "measured" and MEASURED: ratio = MEASURED["by_map_type"].get(map_type, {}).get("land_ratio", ratio)   # MEASURED
    if ratio < 1.0:
        f = [rng.random() for _ in range(N)]
        for i in range(N):
            x, y = i % n, i // n
            if map_type == "pangea": f[i] -= 1.2 * max(abs(x - n / 2 + 0.5), abs(y - n / 2 + 0.5)) / n          # PARAM: central mass
        locked = set(settle) | {j for c in caps for j in orth(c, n)}
        ring_water = {j for r in rings.values() for j, (ter, _) in r.items() if ter == "water"}
        locked = (locked | {j for r in rings.values() for j in r}) - ring_water
        if map_type == "lakes": locked |= {i for i in range(N) if i % n in (0, n - 1) or i // n in (0, n - 1)}   # WIKI: land border on map edges
        for i in locked: f[i] = 2.0
        passes = 1 if map_type == "archipelago" else PARAMS["noise_smoothing_passes"] + (1 if map_type == "continents" else 0)
        f = smooth(f, n, passes, 0.5)
        for i in locked: f[i] = 9.0
        for i in ring_water: f[i] = -9.0                                  # MEASURED ring water counts toward the water quota
        order = sorted(range(N), key=lambda i: f[i])
        for i in order[:N - int(round(ratio * N))]: land[i] = False
    # 5. post-terrain villages up to the wiki total (60%, drylands 80%)
    if total is None: total = len(settle) + round(share * (max_v - len(settle)))
    cand = [i for i in range(N) if land[i]]; rng.shuffle(cand)
    for i in cand:
        if len(settle) >= total: break
        if ok_spot(i): imp[i] = "Village"; settle.append(i)
    # 6. biome owner = nearest capital
    owner = [None] * N
    for i in range(N):
        if land[i]:
            d = min(dist(i, c, n) for c in caps); best = [k for k, c in enumerate(caps) if dist(i, c, n) == d]
            owner[i] = tribes[rng.choice(best)]
    # 7. terrain per biome, exact quotas; settlements are fields (WIKI: city tiles forced to land)
    for t in set(tribes):
        tiles = [i for i in range(N) if land[i] and owner[i] == t and imp[i] is None]
        sh = shares_for(t, mode)
        labels = quota_assign(rng, tiles, {"mountain": sh["mountain"], "forest": sh["forest"]})
        for i in tiles: terrain[i] = labels.get(i, "field")
    for i in range(N):
        if not land[i]: terrain[i] = "water"
    # 8. resources: inner / outer zones, exact quotas per biome x terrain
    inner = {j for s in settle for j in nbrs(s, n, 1)} - set(settle)
    outer = {j for s in settle for j in nbrs(s, n, 2)} - inner - set(settle)
    shallow = {i for i in range(N) if not land[i] and any(land[j] for j in orth(i, n))}
    for zone_name, zone in (("inner", inner), ("outer", outer)):
        for t in set(tribes):
            cp = probs_for(t, zone_name, mode)
            for ter in ("field", "forest", "mountain"):
                tiles = [i for i in zone if owner[i] == t and terrain[i] == ter]
                for i, lab in quota_assign(rng, tiles, cp[ter]).items():
                    res[i] = "spores" if (lab == "crop" and t == "Cymanti") else lab
        # water: wiki = fish on shallow water only; measured = fish + aquacrop on all water in the zone (MEASURED)
        wz = zone & shallow if mode == "wiki" else {i for i in zone if not land[i]}
        for t in set(tribes):
            tiles = [i for i in wz if tribes[min(range(P), key=lambda k: dist(i, caps[k], n))] == t]
            for i, lab in quota_assign(rng, tiles, probs_for(t, zone_name, mode)["water"]).items(): res[i] = lab
    # 9. capital guarantee: >=2 identical resources in the 8-tile ring, force-spawned by replacing tiles (WIKI)
    TER_FOR = {"fruit": "field", "crop": "field", "spores": "field", "animal": "forest", "metal": "mountain", "fish": "water"}
    for p, c in enumerate(caps):
        t = tribes[p]; ring = [j for j in nbrs(c, n, 1) if imp[j] is None]
        cnt = {}
        for j in ring:
            if res[j]: cnt[res[j]] = cnt.get(res[j], 0) + 1
        if c in rings:   # MEASURED: the 8-tile ring is copied from one of this tribe's real capitals (rotated/reflected)
            for j, (ter, r) in rings[c].items():
                terrain[j] = ter; land[j] = ter != "water"; res[j] = "spores" if (r == "crop" and t == "Cymanti") else r
            continue
        if t == "Vengir": continue                     # MEASURED: 8 of 19 Vengir capitals had no identical pair (wiki silent)
        want = (GUARANTEE_MEASURED if mode == "measured" else GUARANTEE).get(t)
        if want == "crop" and t == "Cymanti": want = "spores"
        if want is None:
            if any(cnt.get(r, 0) >= 2 for r in TIER1): continue
            want = rng.choice(TIER1)
        need = 2 - cnt.get(want, 0)
        spots = [j for j in ring if res[j] != want and terrain[j] == TER_FOR[want]] + [j for j in ring if res[j] is None]
        spots += [j for j in ring if res[j] not in (want, None)]
        for j in spots:
            if need <= 0: break
            if res[j] == want: continue
            if TER_FOR[want] == "water" and land[j] and map_type != "drylands" and j in orth(c, n): continue   # keep capital's orth land
            terrain[j] = TER_FOR[want]; land[j] = terrain[j] != "water"; res[j] = want; need -= 1
    # 10. ruins (PARAM count, WIKI placement: not shallow water, not next to settlement or ruin)
    nr = PARAMS["ruins_count"].get(N, round(N * 23 / 900)); ruins = []
    cand = list(range(N)); rng.shuffle(cand)
    corners = {0, n - 1, N - n, N - 1}
    for i in cand:
        if len(ruins) >= nr: break
        if i in corners or imp[i] or i in shallow: continue
        if mode == "measured":   # MEASURED (481 real ruins): >=2 from any village, >=3 from capitals and other ruins; resources may sit hidden under a ruin
            if any(dist(i, s, n) < (3 if cap_of[s] else 2) for s in settle) or any(dist(i, j, n) < 3 for j in ruins): continue
        else:
            if res[i] or any(imp[j] == "Village" or j in ruins for j in nbrs(i, n, 1)): continue
        imp[i] = "Ruin"; ruins.append(i)
    # 11. starfish (PARAM count), lighthouses on corners
    water = [i for i in range(N) if not land[i] and res[i] is None and imp[i] is None and i not in corners]
    rng.shuffle(water)
    for i in water[:sum(1 for k in range(N) if not land[k]) // 25]: res[i] = "starfish"
    for i in corners: imp[i] = imp[i] or "Lighthouse"
    ter_out = {"field": "Field", "forest": "Forest", "mountain": "Mountain", "water": None}
    res_out = {"aquacrop": "AquaCrop", "fruit": "Fruit", "crop": "Crop", "animal": "Game", "metal": "Metal", "fish": "Fish", "spores": "Spores", "starfish": "Starfish"}
    tiles = {i: {"x": i % n, "y": i // n, "terrain": ter_out[terrain[i]] or ("Water" if i in shallow else "Ocean"),
                 "resource": res_out.get(res[i]), "improvement": imp[i], "owner": 0, "capital_of": cap_of[i], "seen_by": [],
                 "biome": owner[i]} for i in range(N)}
    return {"source": f"wiki_mapgen seed {seed}", "kind": f"generator ({mode})", "version": "wiki", "size": n, "map_type": map_type,
            "turn_of_map": 0, "tiles": tiles, "players": [{"id": k + 1, "tribe": t} for k, t in enumerate(tribes)], "params": PARAMS}

if __name__ == "__main__":
    a = argparse.ArgumentParser(); a.add_argument("--type", default="lakes"); a.add_argument("--size", type=int, default=16)
    a.add_argument("--tribes", default="Imperius,Bardur"); a.add_argument("--seed", type=int, default=0); a.add_argument("--out")
    a.add_argument("--mode", default="measured", choices=["measured", "wiki"])
    o = a.parse_args(); m = generate(o.type, o.size, o.tribes.split(","), o.seed, mode=o.mode)
    if o.out: json.dump(m, open(o.out, "w"), default=str)
    print("generated", o.type, o.size, "x", o.size, "tribes", o.tribes)
