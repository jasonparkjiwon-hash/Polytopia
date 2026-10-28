"""win-pct-3 (28 Oct 2026): labels, refit of the evaluation function, fog features. Research harness; needs numpy (the shipped
tools/winpct.py stays stdlib and reads the fitted weights from data/winpct_eval.json).

  python3 -I tools/winpct_fit.py labels          which label is predictable at each horizon (LOGO, sample sizes)
  python3 -I tools/winpct_fit.py sets LABEL      feature-set comparison for one label (LOGO over 14 games + held-out three)
Cache: $WINPCT_CACHE (default /tmp/winpct_cache), made by `winpct_eval.py states` (needs the 17-feature pfwin: PFWIN_BIN) and `playouts`.
Notes and numbers: .scratchpad/investigations/win-pct.md."""
import os, sys, json, math, collections
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import winpct_lib as W

CACHE = os.environ.get("WINPCT_CACHE", "/tmp/winpct_cache")
FI = W.FI
HELD = ("ed6cb932", "710ddb20", "64795ee3")   # test-only: ed6cb932 (data/holdout.json) and games 7-8 (never fitted by the policy or the old eval)
LAGS = (1, 2, 3, 4, 6)

def load():
    S = json.load(open(os.path.join(CACHE, "states.json")))
    G = collections.defaultdict(dict)
    for v in S.values(): G[v["game"]][v["t"]] = v
    return G

def arr(v, ids): return np.array([v["feats"][i] for i in ids], float)

# ---- labels: share vector over the tribes alive at t (ties split) ---------------------------------------------------------------
def leader_vec(alive, key):
    y = np.zeros(len(key))
    if not alive.any(): return y
    k = np.where(alive, key, -1e18); lead = k >= k.max() - 1e-9
    y[lead] = 1.0 / lead.sum(); return y

def label_vec(name, F):
    """F: (k, nfeat) of the tribes at t+H. 'survive' is per tribe (not a share vector)."""
    a = F[:, FI["alive"]] > .5; c = F[:, FI["cities"]]; u = F[:, FI["unit_hp_cost"]]; s = F[:, FI["score"]]
    if name == "survive": return a.astype(float)
    if name == "score": return leader_vec(a, s)
    if name == "cities": return leader_vec(a, c * 1e4 + u)
    if name == "military": return leader_vec(a, u)
    if name == "power": return leader_vec(a, c * 1e6 + u * 1e2 + s * 1e-3)   # most cities; military breaks ties, then score
    raise KeyError(name)

def points(G, lag, games=None):
    """Every checkpoint (game, t) with a save at t+lag; tribes = those alive at t."""
    out = []
    for g, ts in sorted(G.items()):
        if games is not None and g not in games: continue
        for t, v in sorted(ts.items()):
            if t + lag not in ts: continue
            ids = [i for i in sorted(v["feats"], key=int) if v["feats"][i][0] > .5]
            if len(ids) < 2: continue
            out.append(dict(game=g, t=t, turn=v["turn"], ids=ids, F=arr(v, ids), Fn=arr(ts[t + lag], ids), v=v, tribes=[v["tribes"][i]["tribe"] for i in ids],
                            lag=lag, bot=[v["tribes"][i]["bot"] for i in ids]))
    return out

# ---- features -------------------------------------------------------------------------------------------------------------------
BASE = ["cities", "level", "unit_hp_cost", "stars", "income", "techs", "kills", "score"]
SC = {"cities": 1, "level": .5, "unit_hp_cost": .1, "stars": .1, "income": .2, "techs": .2, "kills": .5, "score": .001}
def col(F, n): return F[:, FI[n]]
def share(x): s = x.sum(); return x / s if s > 0 else np.zeros_like(x)
TRIBES = []

def feats(p, fs):
    """(k, d) feature matrix, names. fs: set of groups among share, war, turn, tribe, water."""
    if callable(fs): return fs(p)
    F, turn = p["F"], p["turn"]; cols, names = [], []
    def add(n, x): cols.append(np.asarray(x, float)); names.append(n)
    for n in BASE: add(n, col(F, n) * SC[n])
    if "share" in fs:
        for n in ("cities", "level", "unit_hp_cost", "income", "score", "stars"): add("sh_" + n, share(col(F, n)))
        for n in ("cities", "unit_hp_cost", "income", "score"): add("log_" + n, np.log1p(col(F, n)))
    if "war" in fs:
        add("threat_frac", col(F, "threat") / np.maximum(col(F, "cities"), 1)); add("pressure", col(F, "pressure") * .5)
        add("casualties", col(F, "casualties") * .5); add("kd", (col(F, "kills") - col(F, "casualties")) * .5)
        add("units", col(F, "units") * .2); add("connected_frac", col(F, "connected") / np.maximum(col(F, "cities"), 1))
    if "lead" in fs:                # where each tribe stands against the best OTHER tribe (the label is an argmax)
        def margin(x):
            o = np.array([np.max(np.delete(x, i)) for i in range(len(x))]); return x - o
        mc = margin(col(F, "cities")); mu_ = margin(col(F, "unit_hp_cost")); ms = margin(col(F, "score"))
        add("lead_cities", np.clip(mc, -3, 3)); add("top_cities", (mc > 0) * 1.0); add("tie_cities", (mc == 0) * 1.0)
        add("lead_mil", np.clip(mu_ / 20.0, -2, 2)); add("top_mil", (mu_ > 0) * 1.0); add("lead_score", np.clip(ms / 100.0, -2, 2)); add("top_score", (ms > 0) * 1.0)
    if "turn" in fs:
        z = (turn - 10) / 10.0
        for n in ("cities", "unit_hp_cost", "income", "score", "stars"): add("t_" + n, col(F, n) * SC[n] * z)
    if "tribe" in fs:
        for tb in TRIBES: add("tr_" + tb, [1.0 if x == tb else 0.0 for x in p["tribes"]])
    if "water" in fs:
        w = col(F, "water")[0] - .5
        add("water_x_military", col(F, "unit_hp_cost") * SC["unit_hp_cost"] * w); add("water_x_cities", col(F, "cities") * w)
    return np.stack(cols, 1), names

# ---- conditional logit (numpy) --------------------------------------------------------------------------------------------------
def pack(X, Y):
    P = len(X); K = max(len(x) for x in X); d = X[0].shape[1]
    A = np.zeros((P, K, d)); Yp = np.zeros((P, K)); M = np.zeros((P, K), bool)
    for i, (x, y) in enumerate(zip(X, Y)): A[i, :len(x)] = x; Yp[i, :len(x)] = y; M[i, :len(x)] = True
    return A, Yp, M

def softmax_masked(Z, M):
    Z = np.where(M, Z, -1e30); Z = Z - Z.max(1, keepdims=True); E = np.exp(Z) * M
    return E / E.sum(1, keepdims=True)

def fit(X, Y, l2=1.0, iters=300):
    """Standardised conditional logit, Adam. X list of (k,d); Y list of (k,) label shares (points with no mass are skipped). Returns (w, mu, sd)."""
    keep = [i for i, y in enumerate(Y) if y.sum() > 0.5]
    A, Yp, M = pack([X[i] for i in keep], [Y[i] for i in keep])
    Af = A[M]; mu = Af.mean(0); sd = Af.std(0) + 1e-9
    A = (A - mu) / sd * M[:, :, None]; d = A.shape[2]; w = np.zeros(d); m = np.zeros(d); v = np.zeros(d); n = len(keep)
    for it in range(1, iters + 1):
        Pm = softmax_masked(A @ w, M)
        g = (np.einsum("pk,pkd->d", Yp - Pm * Yp.sum(1, keepdims=True), A) - 2 * l2 * w) / n
        m = .9 * m + .1 * g; v = .999 * v + .001 * g * g
        w += 0.1 * (m / (1 - .9 ** it)) / (np.sqrt(v / (1 - .999 ** it)) + 1e-8)
    return w, mu, sd

def predict(model, x):
    w, mu, sd = model; z = ((x - mu) / sd) @ w; z = z - z.max(); e = np.exp(z); return e / e.sum()

def run_logo(pts, label, fs, l2, test_games, fit_games):
    """Each test game is predicted by a model fitted on fit_games minus itself. Returns rows (game, t, ids, pred, y) with y the label share."""
    rows = []
    for g in test_games:
        tr = [p for p in pts if p["game"] in fit_games and p["game"] != g]; te = [p for p in pts if p["game"] == g]
        if not tr or not te: continue
        mdl = fit([feats(p, fs)[0] for p in tr], [label_vec(label, p["Fn"]) for p in tr], l2)
        for p in te:
            y = label_vec(label, p["Fn"])
            if y.sum() > .5: rows.append((g, p["t"], p["ids"], predict(mdl, feats(p, fs)[0]), y))
    return rows

def sq(rows, pick=None):
    return [float(v) for (g, t, ids, pr, y) in rows if pick is None or pick(g) for v in (pr - y) ** 2]
def uni(rows, pick=None):
    return [float(v) for (g, t, ids, pr, y) in rows if pick is None or pick(g) for v in (np.ones(len(y)) / len(y) - y) ** 2]
def mean(x): return sum(x) / max(1, len(x))

def boot_ci(rows, game_stat, n=300, seed=1):
    """Bootstrap over games: 90% interval of game_stat(rows resampled by game)."""
    rng = np.random.default_rng(seed); by = collections.defaultdict(list)
    for r in rows: by[r[0]].append(r)
    gs = sorted(by); vals = []
    for _ in range(n):
        pick = [by[gs[i]] for i in rng.integers(0, len(gs), len(gs))]
        vals.append(game_stat([r for b in pick for r in b]))
    return float(np.percentile(vals, 5)), float(np.percentile(vals, 95))

def skill(rows):
    """1 - Brier(model)/Brier(uniform) over (point, tribe)."""
    return 1 - mean(sq(rows)) / max(mean(uni(rows)), 1e-12)

# ---- commands -------------------------------------------------------------------------------------------------------------------
def games_split(G):
    allg = sorted(G)
    pool = [g for g in allg if g != "ed6cb932"]            # LOGO pool: every game but the holdout
    tuned = [g for g in allg if g not in HELD]             # old protocol fit set
    return allg, pool, tuned

def cmd_labels():
    G = load(); allg, pool, tuned = games_split(G)
    print("games with saves:", len(allg), "| LOGO pool", len(pool), "(all but ed6cb932) | max turn", max(t for g in G.values() for t in g))
    dead = sum(1 for g in G.values() for t, v in g.items() for f in v["feats"].values() if f[0] < .5)
    print("dead tribe-states in all saves:", dead, "of", sum(len(v["feats"]) for g in G.values() for v in g.values()), "| a finished game (a winner): none (max 26 rounds, nobody eliminated to a last tribe)")
    for lab in ("score", "cities", "military", "power", "survive"):
        print("\nlabel", lab)
        for lag in LAGS:
            pts = points(G, lag)
            if lab == "survive":
                n = sum(len(p["ids"]) for p in pts); d = sum(int((label_vec(lab, p["Fn"]) < .5).sum()) for p in pts)
                print(f"  H={lag}: {len(pts)} points, {n} tribe-points, {d} tribes dead at t+H -> nothing to predict"); continue
            # persistence: does the current leader keep the lead? mean share of the lead at t+H held by the leader at t
            keep = []; ties = 0
            for p in pts:
                y = label_vec(lab, p["Fn"]); y0 = label_vec(lab, p["F"]); ties += (y.max() < 1)
                if y.sum() > .5: keep.append(float((y * (y0 > 0) * y0).sum() / max(y0.sum(), 1e-9) if y0.sum() else 0))
            rows = run_logo(pts, lab, {"share", "war"}, 4.0, pool, pool)
            rows0 = run_logo(pts, lab, set(), 1.0, pool, pool)
            lo, hi = boot_ci(rows, skill)
            print(f"  H={lag}: points {len(pts)} (games {len({p['game'] for p in pts})}), leader-persistence {mean(keep):.2f}, ties at t+H {ties/len(pts):.2f} | "
                  f"Brier uniform {mean(uni(rows)):.4f} old-eval {mean(sq(rows0)):.4f} full-eval {mean(sq(rows)):.4f} | skill {skill(rows):.3f} [{lo:.3f},{hi:.3f}]")

# ---- fog features: what the mover (the human) can know ------------------------------------------------------------------------------
OWN = ["cities", "level", "unit_hp_cost", "stars", "income", "techs", "kills", "casualties", "units"]
def fog_feats(p, lite=False):
    """Mover's view: for every tribe the public score, cities seen on explored tiles (its own: all), met flag, tribe; full features only for the mover itself."""
    v = p["v"]; F = p["F"]; me = np.array([1.0 if i == str(v["player"]) else 0.0 for i in p["ids"]])
    vc = np.array([float(v["fog"][i][0]) for i in p["ids"]]); met = np.array([float(v["fog"][i][1]) for i in p["ids"]])
    vc = np.where(me > 0, col(F, "cities"), vc); sc = col(F, "score"); cols, names = [], []
    def add(n, x): cols.append(np.asarray(x, float)); names.append(n)
    add("score", sc * .001); add("vis_cities", vc); add("met", met); add("me", me)
    add("sh_score", share(sc)); add("sh_vis_cities", share(vc)); add("log_score", np.log1p(sc))
    if not lite:
        for n in OWN: add("me_" + n, me * col(F, n) * SC.get(n, .2))
        add("me_threat_frac", me * col(F, "threat") / max(col(F, "cities")[me > 0].sum(), 1)); add("me_pressure", me * col(F, "pressure") * .5)
        for tb in TRIBES: add("tr_" + tb, [1.0 if x == tb else 0.0 for x in p["tribes"]])
    return np.stack(cols, 1), names

SETS = {"score only": ("score",), "old eval": (), "+share": ("share",), "+war": ("war",), "+turn": ("turn",), "+tribe": ("tribe",), "+water": ("water",),
        "share+war": ("share", "war"), "lead": ("lead",), "share+war+lead": ("share", "war", "lead"), "share+war+lead+tribe": ("share", "war", "lead", "tribe"), "war+tribe": ("war", "tribe"), "share+war+tribe": ("share", "war", "tribe"), "share+war+turn": ("share", "war", "turn"), "all": ("share", "war", "turn", "tribe", "water")}

def cmd_sets(label, only=None):
    G = load(); allg, pool, tuned = games_split(G)
    for lag in LAGS:
        pts = points(G, lag); print(f"\nlabel {label} H={lag}: {len(pts)} points; LOGO pool {len({p['game'] for p in pts if p['game'] in pool})} games; held = ed6cb932+7+8 fitted on the 11 tuned")
        base = None
        for name, fs in SETS.items():
            if only and name not in only: continue
            best = None
            for l2 in (0.5, 2.0, 8.0, 30.0):
                if name == "score only":
                    global BASE
                    save = BASE; BASE = ["score"]
                    rows = run_logo(pts, label, set(), l2, pool, pool); BASE = save
                else: rows = run_logo(pts, label, set(fs), l2, pool, pool)
                b = mean(sq(rows))
                if best is None or b < best[0]: best = (b, l2, rows)
            b, l2, rows = best
            held_rows = run_logo(pts, label, set(fs), l2, [g for g in HELD if g in G], tuned) if name != "score only" else []
            lo, hi = boot_ci(rows, skill)
            hb = mean(sq(held_rows)); hu = mean(uni(held_rows))
            print(f"  {name:15s} l2 {l2:5.1f}  LOGO Brier {b:.4f} (uniform {mean(uni(rows)):.4f}) skill {skill(rows):.3f} [{lo:.3f},{hi:.3f}] | held Brier {hb:.4f} (uniform {hu:.4f}, n={len(held_rows)}) " + (f"skill {1-hb/hu:.3f}" if held_rows else ""))

IMP = ["cities", "level", "unit_hp_cost", "stars", "income", "techs", "kills", "casualties", "units", "connected", "threat", "pressure"]
def imp_X(p):
    v = p["v"]; F = p["F"]; sc = col(F, "score")
    vc = np.array([float(v["fog"][i][0]) for i in p["ids"]]); met = np.array([float(v["fog"][i][1]) for i in p["ids"]])
    z = (p["turn"] - 10) / 10.0
    return np.stack([np.ones(len(sc)), sc * .01, np.log1p(sc), vc, met, vc * z, sc * .01 * z, np.full(len(sc), z), share(sc)], 1)

def impute_fit(tr, lam=3.0):
    """Ridge of every true feature of the OTHER tribes on public/visible ones. Returns coefficient matrix (d_imp x len(IMP))."""
    X = np.concatenate([imp_X(p)[[i for i, t in enumerate(p["ids"]) if t != str(p["v"]["player"])]] for p in tr])
    Y = np.concatenate([p["F"][[i for i, t in enumerate(p["ids"]) if t != str(p["v"]["player"])]][:, [FI[n] for n in IMP]] for p in tr])
    return np.linalg.solve(X.T @ X + lam * np.eye(X.shape[1]), X.T @ Y)

def impute_point(p, B):
    q = dict(p); F = p["F"].copy(); X = imp_X(p); H = X @ B
    for i, t in enumerate(p["ids"]):
        if t != str(p["v"]["player"]):
            for j, n in enumerate(IMP): F[i, FI[n]] = max(H[i, j], 0.0)
            F[i, FI["cities"]] = max(F[i, FI["cities"]], p["fogv"][i] if "fogv" in p else 0.0)
    q["F"] = F; return q

KEEP = ["alive", "cities", "level", "unit_hp_cost", "stars", "income", "techs", "kills", "score"]       # winpct_eval.KEEP

def play_share(play, p, H, label):
    """Playout lead share per tribe (order p['ids']) for the label, or None. Full information."""
    P = play.get("%s|%d" % (p["game"], p["t"]))
    if not P or str(H) not in P: return None
    D = P[str(H)]; n = len(D[p["ids"][0]]); acc = np.zeros(len(p["ids"]))
    for j in range(n):
        F = np.zeros((len(p["ids"]), len(W.FEATS)))
        for a, i in enumerate(p["ids"]): F[a, [FI[k] for k in KEEP]] = D[i][j]
        acc += label_vec(label, F)
    return acc / n, n

def fit_pred(tr, te, ff, ytr, l2):
    """Fit on points tr with label shares ytr (list), predict for te. Returns list of pred vectors."""
    mdl = fit([ff(p)[0] for p in tr], ytr, l2)
    return [predict(mdl, ff(p)[0]) for p in te]

def stack_X(parts): return np.stack([np.log(np.asarray(a) + e) for a, e in parts], 1)

def cmd_fog(label="power", l2=8.0, l2fog=3.0):
    G = load(); allg, pool, tuned = games_split(G)
    play = json.load(open(os.path.join(CACHE, "play_6.json")))
    full_ff = lambda p: feats(p, {"share", "war", "tribe"})
    fog_full = lambda p: fog_feats(p); fog_lite = lambda p: fog_feats(p, True)
    for H in (1, 2, 3, 4, 6):
        pts = [p for p in points(G, H) if play_share(play, p, H, label)]
        for p in pts:
            p["y"] = label_vec(label, p["Fn"]); p["pp"], p["n"] = play_share(play, p, H, label)
        pts = [p for p in pts if p["y"].sum() > .5]
        print(f"\nH={H} label {label}: {len(pts)} points, {len({p['game'] for p in pts})} games, {pts[0]['n']} playouts each")
        results = {}                     # name -> {(g,t): pred}  OUT-OF-FOLD (test game never in the fit); split by game group below
        def oof(name, ff, ytrain=None, l2_=l2, test=None, fitg=None):
            for split, (testg, fitg_) in {"logo": (pool, pool), "held": ([g for g in HELD if g in G], tuned)}.items():
                for g in testg:
                    tr = [p for p in pts if p["game"] in fitg_ and p["game"] != g]; te = [p for p in pts if p["game"] == g]
                    if not tr or not te: continue
                    ys = [(ytrain(p) if ytrain else p["y"]) for p in tr]
                    for p, pr in zip(te, fit_pred(tr, te, ff, ys, l2_)): results.setdefault(name, {})[(split, p["game"], p["t"])] = pr
        oof("static_full", full_ff); oof("fog_lite", fog_lite, l2_=l2fog); oof("fog", fog_full, l2_=l2fog)
        for p in pts: p["soft"] = 0.5 * p["pp"] + 0.5 * p["y"] * 0           # placeholder, replaced after static_full exists
        sf = results["static_full"]
        # distillation target: half full-information playouts, half the full static eval (no outcome): train the fog model on it
        for p in pts: p["soft"] = {sp: 0.5 * p["pp"] + 0.5 * sf.get((sp, p["game"], p["t"]), np.ones(len(p["ids"])) / len(p["ids"])) for sp in ("logo", "held")}
        for split, (testg, fitg_) in {"logo": (pool, pool), "held": ([g for g in HELD if g in G], tuned)}.items():
            for g in testg:
                tr = [p for p in pts if p["game"] in fitg_ and p["game"] != g]; te = [p for p in pts if p["game"] == g]
                if not tr or not te: continue
                for p, pr in zip(te, fit_pred(tr, te, fog_full, [p["soft"]["logo"] for p in tr], l2fog)): results.setdefault("fog_distilled", {})[(split, p["game"], p["t"])] = pr
        for split, (testg, fitg_) in {"logo": (pool, pool), "held": ([g for g in HELD if g in G], tuned)}.items():
            for g in testg:
                tr = [p for p in pts if p["game"] in fitg_ and p["game"] != g]; te = [p for p in pts if p["game"] == g]
                if not tr or not te: continue
                for l2d, nm in ((30.0, "fog_distilled l2=30"),):
                    for p, pr in zip(te, fit_pred(tr, te, fog_full, [p["soft"]["logo"] for p in tr], l2d)): results.setdefault(nm, {})[(split, p["game"], p["t"])] = pr
                for p, pr in zip(te, fit_pred(tr, te, fog_lite, [p["soft"]["logo"] for p in tr], l2)): results.setdefault("fog_lite_distilled", {})[(split, p["game"], p["t"])] = pr
                # imputation: ridge true-features-of-others from public/visible ones, then the full static eval (fitted on true features) on the imputed state
                B = impute_fit(tr); mdl = fit([full_ff(p)[0] for p in tr], [p["y"] for p in tr], l2)
                for p in te: results.setdefault("imputed static", {})[(split, p["game"], p["t"])] = predict(mdl, full_ff(impute_point(p, B))[0])
        for split in ("logo", "held"):
            for p in pts:
                k = (split, p["game"], p["t"])
                if k in sf:
                    results.setdefault("playout", {})[k] = p["pp"] * .94 + .06 / len(p["ids"])
                    results.setdefault("playout+static", {})[k] = 0.5 * p["pp"] + 0.5 * sf[k]
        # learned corrections (stage 2): conditional logit on log components, fitted on the other games' out-of-fold stage-1 predictions
        def stage2(name, comps, l2_=0.01):
            for split, (testg, fitg_) in {"logo": (pool, pool), "held": ([g for g in HELD if g in G], tuned)}.items():
                for g in testg:
                    key = lambda p: (("logo", p["game"], p["t"]))
                    trp = [p for p in pts if p["game"] in fitg_ and p["game"] != g and all(key(p) in results[c] for c, _ in comps)]
                    te = [p for p in pts if p["game"] == g and all((split, p["game"], p["t"]) in results[c] for c, _ in comps)]
                    if not trp or not te: continue
                    mk = lambda p, sp: (stack_X([(results[c][(sp, p["game"], p["t"])], e) for c, e in comps]), None)
                    mdl = fit([mk(p, "logo")[0] for p in trp], [p["y"] for p in trp], l2_)
                    for p in te: results.setdefault(name, {})[(split, p["game"], p["t"])] = predict(mdl, mk(p, split)[0])
        stage2("playout+static learned", [("playout", .02), ("static_full", .01)])
        stage2("fog_distilled Platt", [("fog_distilled", .01)])
        stage2("fog Platt", [("fog", .01)])
        stage2("fog+fog_lite learned", [("fog", .01), ("fog_lite", .01)])
        rows_out = {}
        for name in ["uniform", "static_full", "playout", "playout+static", "playout+static learned", "fog_lite", "fog", "fog_distilled", "fog_distilled l2=30", "fog_lite_distilled", "imputed static", "fog Platt", "fog_distilled Platt", "fog+fog_lite learned"]:
            line = []
            for split in ("logo", "held"):
                rows = []
                for p in pts:
                    k = (split, p["game"], p["t"])
                    if name == "uniform":
                        if k in sf: rows.append((p["game"], p["t"], p["ids"], np.ones(len(p["y"])) / len(p["y"]), p["y"]))
                    elif k in results.get(name, {}): rows.append((p["game"], p["t"], p["ids"], results[name][k], p["y"]))
                rows_out[(name, split)] = rows
                line.append(f"{split} n={len(rows)} Brier {mean(sq(rows)):.4f}")
            print(f"  {name:24s} " + " | ".join(line))
        # skill relative to uniform and bootstrap interval for the key models (LOGO)
        for name in ("static_full", "playout+static learned", "fog", "fog_distilled", "fog Platt"):
            r = rows_out[(name, "logo")]
            if r:
                lo, hi = boot_ci(r, skill); print(f"    {name}: LOGO skill {skill(r):.3f} [{lo:.3f},{hi:.3f}]")
        json.dump({f"{n}|{sp}": [[g, t, list(map(float, pr)), list(map(float, y))] for g, t, ids, pr, y in r] for (n, sp), r in rows_out.items()}, open(os.path.join(CACHE, f"fog_rows_{H}.json"), "w"))

# ---- shipped weights: data/winpct_eval.json ---------------------------------------------------------------------------------------
EDGES = [0, .02, .05, .1, .2, .35, .5, .75, 1.0001]
def calib_bins(rows):
    pairs = [(float(a), float(b)) for g, t, pr, y in rows for a, b in zip(pr, y)]
    out = []
    for lo, hi in zip(EDGES, EDGES[1:]):
        b = [(a, c) for a, c in pairs if lo <= a < hi]
        if b: out.append({"lo": lo, "hi": min(hi, 1.0), "n": len(b), "games": len({g for g, t, pr, y in rows}), "pred": round(sum(a for a, _ in b) / len(b), 4), "obs": round(sum(c for _, c in b) / len(b), 4)})
    return out

def pack_model(m, names): return {"w": [round(float(x), 5) for x in m[0]], "mu": [round(float(x), 5) for x in m[1]], "sd": [round(max(float(x), 1e-6), 8) for x in m[2]]}

def cmd_write(label="power", B=20):
    G = load(); allg, pool, tuned = games_split(G); play = json.load(open(os.path.join(CACHE, "play_6.json")))
    full_ff = lambda p: feats(p, {"share", "war", "tribe"}); fog_ff = lambda p: fog_feats(p)
    names_full = feats(points(G, 2)[0], {"share", "war", "tribe"})[1]; names_fog = fog_feats(points(G, 2)[0])[1]
    out = {"about": "win-pct-3 evaluation function, label '%s' (tribe holds the most cities at t+H; ties: strongest military, then in-game score). Fitted by tools/winpct_fit.py write on %d games (all but ed6cb932); calibration = leave-one-game-out out-of-fold predictions. Conditional logit over the tribes alive at t: P = softmax(((x - mu)/sd) . w)." % (label, len(pool)),
           "label": label, "pool": pool, "tribes": TRIBES, "names_full": names_full, "names_fog": names_fog, "lags": {}}
    rng = np.random.default_rng(7)
    for H in LAGS:
        pts = [p for p in points(G, H) if p["game"] in pool and play_share(play, p, H, label)]
        for p in pts: p["y"] = label_vec(label, p["Fn"]); p["pp"] = play_share(play, p, H, label)[0]
        pts = [p for p in pts if p["y"].sum() > .5]
        rows = json.load(open(os.path.join(CACHE, f"fog_rows_{H}.json")))
        oof = {(g, t): np.array(pr) for g, t, pr, y in rows["static_full|logo"]}
        pts = [p for p in pts if (p["game"], p["t"]) in oof]
        # stack of playouts + static: weights on log components, fitted on out-of-fold static predictions
        mk = lambda p, st: stack_X([(p["pp"] * .94 + .06 / len(p["ids"]), .02), (st, .01)])
        sw = fit([mk(p, oof[(p["game"], p["t"])]) for p in pts], [p["y"] for p in pts], 0.01)
        soft = lambda p: 0.5 * p["pp"] + 0.5 * oof[(p["game"], p["t"])]
        def fit_all(sel):
            return (fit([full_ff(p)[0] for p in sel], [p["y"] for p in sel], 8.0), fit([fog_ff(p)[0] for p in sel], [soft(p) for p in sel], 3.0))
        mf, mg = fit_all(pts); boots = []
        gl = sorted({p["game"] for p in pts})
        for b in range(B):
            pick = [gl[i] for i in rng.integers(0, len(gl), len(gl))]
            sel = [p for g in pick for p in pts if p["game"] == g]
            boots.append(fit_all(sel))
        calib = {k: calib_bins(rows[k + "|logo"]) for k in ("static_full", "playout+static learned", "fog_distilled", "uniform") if k + "|logo" in rows}
        met = {}
        for k in ("uniform", "static_full", "playout", "playout+static learned", "fog_distilled", "fog", "fog_lite"):
            r3 = [(g, t, None, np.array(pr), np.array(y)) for g, t, pr, y in rows[k + "|logo"]]
            met[k] = {"brier_logo": round(mean(sq(r3)), 5), "n_points": len(r3)}
            rh = rows.get(k + "|held", []); met[k]["brier_held"] = round(mean([float(v) for g, t, pr, y in rh for v in (np.array(pr) - np.array(y)) ** 2]), 5) if rh else None; met[k]["n_held"] = len(rh)
        out["lags"][str(H)] = {"n_points": len(pts), "full": pack_model(mf, names_full), "fog": pack_model(mg, names_fog), "stack_w": [round(float(x), 4) for x in sw[0] / sw[2]],
                               "boot_full": [pack_model(b[0], names_full) for b in boots], "boot_fog": [pack_model(b[1], names_fog) for b in boots], "calib": calib, "metrics": met}
        print("lag", H, "points", len(pts), "stack w", out["lags"][str(H)]["stack_w"], {k: v["brier_logo"] for k, v in met.items()})
    json.dump(out, open(os.path.join(W.ROOT, "data", "winpct_eval.json"), "w"))

if __name__ == "__main__":
    c = sys.argv[1] if len(sys.argv) > 1 else ""
    G0 = load() if c else None
    TRIBES[:] = sorted({v["tribes"][i]["tribe"] for g in G0.values() for v in g.values() for i in v["tribes"]}) if c else []
    if c == "labels": cmd_labels()
    elif c == "fog": cmd_fog("power")
    elif c == "write": cmd_write()
    elif c == "sets": cmd_sets(sys.argv[2] if len(sys.argv) > 2 else "power", sys.argv[3].split(",") if len(sys.argv) > 3 else None)
    else: print(__doc__)
