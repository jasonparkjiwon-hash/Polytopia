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

def sample(d, model, tribe, rng):
    ks, ps = zip(*d[model][tribe]["full"].items()); return rng.choices(ks, ps)[0]

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

def with_engine(d, path="pf_engine_ring8.json"):
    """Replace the hand-built POLYFISH model with the real Polyfish engine's measured distribution (if generated)."""
    import os
    if os.path.exists(path):
        e = json.load(open(path))["tribes"]
        d["PF_ENGINE"] = {t: {"full": {int(k): v for k, v in x["full"].items()}, "visible": {int(k): v for k, v in x["visible"].items()},
                              "mean_full": x["mean_full"], "mean_visible": x["mean_visible"]} for t, x in e.items()}
        d.pop("POLYFISH", None)
    return d

def with_wiki_generator(d, path="wiki_gen_ring8.json"):
    """WIKI model = the wiki-literal map generator (sim/wiki_mapgen.py), measured by wiki_ring8.py. Replaces the rough hand model."""
    import os
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
    if os.path.exists(p):
        e = json.load(open(p))["tribes"]
        d["WIKI"] = {t: {"full": {int(k): v for k, v in x["full"].items()}, "visible": {int(k): v for k, v in x["visible"].items()},
                         "mean_full": x["mean_full"], "mean_visible": x["mean_visible"]} for t, x in e.items()}
    d.pop("POLYFISH", None)
    return d

def score(dist, obs):
    ll = {m: 0.0 for m in dist}
    for o in obs:
        key, val = ("full", o["full_total"]) if o.get("full_total") is not None else ("visible", o["visible_total"])
        for m in dist: ll[m] += math.log(max(dist[m][o["tribe"]][key].get(val, 0.0), 1e-4))
    best = max(ll, key=ll.get)
    # absolute fit of the leader: z-score of observed vs predicted totals (|z| > 3 = neither model describes the game)
    zs = 0.0; var = 0.0
    for o in obs:
        key, val = ("full", o["full_total"]) if o.get("full_total") is not None else ("visible", o["visible_total"])
        dd = dist[best][o["tribe"]][key]; mu = sum(k * p for k, p in dd.items()); v = sum((k - mu) ** 2 * p for k, p in dd.items())
        zs += val - mu; var += v
    fit_z = round(zs / math.sqrt(var), 2) if var else 0.0
    bf = {m: round(math.exp(ll[best] - ll[m]), 1) for m in ll if m != best}
    return {"log_likelihood": {m: round(v, 2) for m, v in ll.items()}, "leader": best, "bayes_factor_vs_others": bf,
            "decided": all(v > 10 for v in bf.values()) and abs(fit_z) <= 3, "leader_fit_z": fit_z,
            "warning": "leader fits poorly: the real generator may be neither model" if abs(fit_z) > 3 else None, "n_capitals": len(obs)}

if __name__ == "__main__":
    d = with_wiki_generator(distributions())
    if "--with-polyfish" in sys.argv: d = with_engine(d); sys.argv.remove("--with-polyfish")
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
                tribe = rng.choice([t for t in MOD if t in d[truth]]); f = sample(d, truth, tribe, rng); obs.append({"tribe": tribe, "full_total": f})
                s = score(d, obs)
                if s["decided"]: need.append((k, s["leader"] == truth)); break
            else: need.append((61, False))
        ks = sorted(k for k, _ in need); acc = sum(ok for _, ok in need) / len(need)
        print(f"if {truth} is true: median {ks[len(ks)//2]} capitals (90th pct {ks[int(len(ks)*0.9)]}) to decide from full counts; correct verdict {acc:.0%}")
