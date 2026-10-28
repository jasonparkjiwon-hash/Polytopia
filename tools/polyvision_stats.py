"""Aggregate statistics of PolyVision 11x11 Bardur Drylands maps vs Polyfish `genmaps` maps.
Usage: python3 -I tools/polyvision_stats.py <pv_dir> <pf_dir> [out.json]
  pv_dir: output of tools/polyvision_fetch.py (third-party data, never committed)
  pf_dir: output of sim/pfcore genmaps (`genmaps <dir> 5000 1 0 1000 4 1`: Drylands, Tiny=11, Bardur, 1 player)
Only aggregates are written. Legend (PolyVision tools/polytopia_map_converter/README.md): cell 'T:R', T = . field, f forest,
m mountain; R = a animal, o metal, f fruit, r ruin (hides any resource), c:2 = capital, v: = village (terrain not kept)."""
import json, glob, sys, math, collections
N = 11
def neigh8(x, y):
    return [(x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if (dx or dy) and 0 <= x + dx < N and 0 <= y + dy < N]
def cheb(a, b): return max(abs(a[0] - b[0]), abs(a[1] - b[1]))

def load_pv(d):
    out, codes = [], collections.Counter()
    for f in sorted(glob.glob(d + "/*/*.csv")):
        rows = [l.split(",") for l in open(f).read().split("\n") if l.strip()]
        g = {}
        for y, r in enumerate(rows):
            for x, c in enumerate(r):
                codes[c] += 1
                t, s = c.split(":")
                if t == "v": g[(x, y)] = ("?", None, "v")
                elif t == "c": g[(x, y)] = ("?", None, "c")
                elif s == "r": g[(x, y)] = (t, None, "r")
                else: g[(x, y)] = (t, s or None, None)
        out.append(g)
    return out, codes

def load_pf(d):
    T = {3: ".", 4: "m", 5: "f"}; R = {1: "a", 5: "o", 6: "f", 2: "c"}
    out = []
    for f in sorted(glob.glob(d + "/*.json")):
        j = json.load(open(f)); g = {}
        for k, t in j["tiles"].items():
            x, y = t["coords"]["x"], t["coords"]["y"]
            g[(x, y)] = [T.get(t["type"], "w%d" % t["type"]), None, None, t.get("capitalOf", 0)]
        for k, s in j["structures"].items():
            x, y = int(k) % N, int(k) // N
            if s["type"] == 1: g[(x, y)][2] = "c" if g[(x, y)][3] else "v"
            elif s["type"] == 2: g[(x, y)][2] = "r"
        for k, r in j["resources"].items():
            g[(int(k) % N, int(k) // N)][1] = R.get(r["type"], "x%d" % r["type"])
        for p, v in g.items():
            t, r, s, _ = v
            if s in ("v", "c"): g[p] = ("?", None, s)
            elif s == "r": g[p] = (t, None, "r")
            else: g[p] = (t, r, None)
        out.append(g)
    return out

def load_py(mode, n, seed0=1000):
    """Maps from sim/wiki_mapgen.py (our wiki-literal / measured generator), 11x11 Drylands, one Bardur."""
    import importlib.util, os
    sp = importlib.util.spec_from_file_location("wiki_mapgen", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sim", "wiki_mapgen.py"))
    wm = importlib.util.module_from_spec(sp); sp.loader.exec_module(wm)
    T = {"Field": ".", "Forest": "f", "Mountain": "m"}; R = {"Game": "a", "Metal": "o", "Fruit": "f", "Crop": "c"}
    out = []
    for i in range(n):
        m = wm.generate(map_type="drylands", size=N, tribes=("Bardur",), seed=seed0 + i, mode=mode)
        g = {}
        for t in m["tiles"].values():
            p = (t["x"], t["y"]); im = t["improvement"]
            terr = T.get(t["terrain"], "w")
            if t["capital_of"]: g[p] = ("?", None, "c")
            elif im == "Village": g[p] = ("?", None, "v")
            elif im == "Ruin": g[p] = (terr, None, "r")
            else: g[p] = (terr, R.get(t["resource"]), None)
        out.append(g)
    return out

def feats(g, agg):
    cap = [p for p, v in g.items() if v[2] == "c"]
    vil = [p for p, v in g.items() if v[2] == "v"]
    rui = [p for p, v in g.items() if v[2] == "r"]
    if len(cap) != 1: agg["bad_capital_count"] += 1; return
    c = cap[0]; sett = cap + vil
    agg["n"] += 1
    agg["hist_villages"][len(vil)] += 1; agg["hist_ruins"][len(rui)] += 1
    agg["cap_x"][c[0]] += 1; agg["cap_y"][c[1]] += 1
    agg["cap_pos"]["%d,%d" % (min(c[0], N - 1 - c[0]), min(c[1], N - 1 - c[1]))] += 1
    for v in vil:
        agg["vil_cheb_from_cap"][cheb(v, c)] += 1
        if min(v) == 0 or max(v) == N - 1: agg["settlement_on_edge"] += 1
    if min(c) == 0 or max(c) == N - 1: agg["settlement_on_edge"] += 1
    for s in sett:
        agg["nearest_other_settlement"][min([cheb(s, o) for o in sett if o != s] or [99])] += 1
    for r in rui:
        agg["ruin_nearest_village"][min([cheb(r, v) for v in vil] or [99])] += 1
        agg["ruin_cap_dist"][cheb(r, c)] += 1
        agg["ruin_nearest_ruin"][min([cheb(r, o) for o in rui if o != r] or [99])] += 1
        if min(r) == 0 or max(r) == N - 1: agg["ruin_on_edge"] += 1
    # terrain / resources by distance to nearest settlement (capital ring r<=1 reported separately)
    for p, (t, r, s) in g.items():
        if s is not None and t == "?": continue
        d = min(cheb(p, o) for o in sett)
        if s == "r": agg["ruin_by_dist"][min(d, 4)] += 1; agg["terrain_by_dist_ruin"]["%s|%d" % (t, min(d, 4))] += 1
        if p == c or t == "?": continue
        ring = cheb(p, c) <= 1
        zone = "capring" if ring else "d%d" % min(d, 4)
        agg["terrain_zone"][zone + "|" + t] += 1
        if s is None: agg["res_zone"][zone + "|" + t + "|" + (r or "-")] += 1
    # capital ring 1 and 2 resource counts (non-ruin tiles)
    ring1 = [p for p in neigh8(*c)]
    agg["cap_ring1_nres"][sum(1 for p in ring1 if g[p][1])] += 1
    agg["cap_ring1_animal"][sum(1 for p in ring1 if g[p][1] == "a")] += 1
    agg["cap_ring1_has_animal"][int(any(g[p][1] == "a" for p in ring1))] += 1
    ring2 = [p for p in g if cheb(p, c) == 2]
    agg["cap_ring2_nres"][sum(1 for p in ring2 if g[p][1])] += 1
    agg["cap_ring1_terrain"]["".join(sorted(g[p][0] for p in ring1))] += 0
    for p in ring1: agg["cap_ring1_tile"][g[p][0] + "|" + (g[p][1] or "-") + "|" + (g[p][2] or "-")] += 1
    agg["cap_ring1_ruins"][sum(1 for p in ring1 if g[p][2] == "r")] += 1
    agg["cap_ring1_village"][sum(1 for p in ring1 if g[p][2] == "v")] += 1
    # clustering: same-terrain share of 4-neighbour pairs among known land tiles
    for (x, y), (t, r, s) in g.items():
        if t == "?": continue
        for q in ((x + 1, y), (x, y + 1)):
            if q in g and g[q][0] != "?":
                u = g[q][0]; agg["pairs"]["".join(sorted((t, u)))] += 1
    # nearest-neighbour terrain for mountains / forests: number of 8-neighbours of same type
    for (x, y), (t, r, s) in g.items():
        if t in ("m", "f"):
            k = sum(1 for q in neigh8(x, y) if g[q][0] == t)
            agg["same8_" + t][k] += 1
    nt = collections.Counter(v[0] for v in g.values())
    agg["maps_mountains_hist"][nt["m"] // 3 * 3] += 1
    agg["maps_forest_hist"][nt["f"] // 5 * 5] += 1

def run(maps):
    class Ag(dict):
        def __missing__(self, k):
            self[k] = collections.Counter(); return self[k]
    ag = Ag(); ag["n"] = 0; ag["bad_capital_count"] = 0; ag["settlement_on_edge"] = 0; ag["ruin_on_edge"] = 0
    for g in maps: feats(g, ag)
    return ag

def gammaq(a, x):  # upper regularised incomplete gamma Q(a,x)
    if x <= 0: return 1.0
    if x < a + 1:
        s, t, n = 1.0 / a, 1.0 / a, a
        for _ in range(2000):
            n += 1; t *= x / n; s += t
            if abs(t) < abs(s) * 1e-14: break
        return 1 - s * math.exp(-x + a * math.log(x) - math.lgamma(a))
    b = x + 1 - a; c = 1e300; d = 1 / b; h = d
    for i in range(1, 2000):
        an = -i * (i - a); b += 2; d = an * d + b; d = 1e-300 if abs(d) < 1e-300 else d
        c = b + an / c; c = 1e-300 if abs(c) < 1e-300 else c
        d = 1 / d; de = d * c; h *= de
        if abs(de - 1) < 1e-14: break
    return math.exp(-x + a * math.log(x) - math.lgamma(a)) * h

def chi2(ca, cb, minexp=5):
    """Two-sample homogeneity chi-square over categories (cells with small expected pooled into 'rest')."""
    na, nb = sum(ca.values()), sum(cb.values())
    keys = sorted(set(ca) | set(cb), key=str); rest = [0, 0]; rows = []
    for k in keys:
        a, b = ca.get(k, 0), cb.get(k, 0); e = (a + b) / (na + nb)
        if min(e * na, e * nb) < minexp: rest[0] += a; rest[1] += b
        else: rows.append((a, b))
    if rest[0] + rest[1]: rows.append(tuple(rest))
    stat = 0.0
    for a, b in rows:
        e = (a + b) / (na + nb)
        for o, n in ((a, na), (b, nb)):
            if e * n > 0: stat += (o - e * n) ** 2 / (e * n)
    df = max(len(rows) - 1, 1)
    return {"chi2": round(stat, 1), "df": df, "p": gammaq(df / 2, stat / 2), "chi2_per_df": round(stat / df, 2)}

def ks(ca, cb):
    """Two-sample KS on integer-valued histograms (D, asymptotic p)."""
    na, nb = sum(ca.values()), sum(cb.values()); fa = fb = D = 0.0
    for k in sorted(set(ca) | set(cb)):
        fa += ca.get(k, 0) / na; fb += cb.get(k, 0) / nb; D = max(D, abs(fa - fb))
    en = math.sqrt(na * nb / (na + nb)); lam = (en + 0.12 + 0.11 / en) * D
    p = 2 * sum((-1) ** (j - 1) * math.exp(-2 * j * j * lam * lam) for j in range(1, 100))
    return {"D": round(D, 4), "p": min(max(p, 0.0), 1.0)}

def mean(c):
    n = sum(c.values()); return sum(k * v for k, v in c.items()) / n if n else float("nan")

def compare(A, B, name):
    R = {"n_real": A["n"], "n_gen": B["n"], "real_bad_capital": A["bad_capital_count"], "gen_bad_capital": B["bad_capital_count"]}
    for k in ("hist_villages", "hist_ruins", "vil_cheb_from_cap", "nearest_other_settlement", "ruin_nearest_village", "ruin_cap_dist",
              "ruin_nearest_ruin", "cap_ring1_nres", "cap_ring1_animal", "cap_ring2_nres", "same8_m", "same8_f", "cap_pos", "cap_x", "cap_y"):
        a, b = A[k], B[k]
        R[k] = {"real": {str(x): a[x] for x in sorted(a, key=str)}, "gen": {str(x): b[x] for x in sorted(b, key=str)},
                "real_mean": round(mean(a), 3) if k != "cap_pos" else None, "gen_mean": round(mean(b), 3) if k != "cap_pos" else None,
                "chi2": chi2(a, b), "ks": ks(a, b) if k != "cap_pos" else None}
    for k in ("settlement_on_edge", "ruin_on_edge"):
        R[k] = {"real": A[k], "gen": B[k]}
    for k in ("terrain_zone", "res_zone", "cap_ring1_tile", "pairs", "ruin_by_dist"):
        R[k] = {"real": dict(A[k]), "gen": dict(B[k]), "chi2": chi2(A[k], B[k])}
    P = {}; sh = {}
    for src, X in (("real", A), ("gen", B)):
        for zone in ("capring", "d1", "d2", "d3", "d4"):
            tt = sum(v for k, v in X["terrain_zone"].items() if k.startswith(zone + "|"))
            if tt: sh["%s %s" % (src, zone)] = {t: round(X["terrain_zone"].get("%s|%s" % (zone, t), 0) / tt, 4) for t in (".", "f", "m")}
            for t, rs in (("f", ("a",)), (".", ("f", "c")), ("m", ("o",))):
                tot = sum(v for k, v in X["res_zone"].items() if k.startswith("%s|%s|" % (zone, t)))
                if not tot: continue
                for r in rs: P["%s %s P(%s|%s)" % (src, zone, r, t)] = round(X["res_zone"].get("%s|%s|%s" % (zone, t, r), 0) / tot, 4)
    R["p_resource"] = P; R["terrain_share"] = sh
    return R

def main():
    pv_dir, pf_dir = sys.argv[1], sys.argv[2]
    out = sys.argv[3] if len(sys.argv) > 3 else None
    pv, codes = load_pv(pv_dir); A = run(pv)
    R = {"pv_cell_codes": dict(codes)}
    gens = {"polyfish_genmaps": run(load_pf(pf_dir))}
    for mode in ("measured", "wiki"): gens["wiki_mapgen_" + mode] = run(load_py(mode, 5000))
    for name, B in gens.items(): R[name] = compare(A, B, name)
    s = json.dumps(R, indent=1, default=str)
    if out: open(out, "w").write(s)
    else: print(s)

if __name__ == "__main__":
    main()
