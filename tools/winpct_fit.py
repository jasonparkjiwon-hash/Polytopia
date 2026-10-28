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

SETS = {"score only": ("score",), "old eval": (), "+share": ("share",), "+war": ("war",), "+turn": ("turn",), "+tribe": ("tribe",), "+water": ("water",),
        "share+war": ("share", "war"), "war+tribe": ("war", "tribe"), "share+war+tribe": ("share", "war", "tribe"), "share+war+turn": ("share", "war", "turn"), "all": ("share", "war", "turn", "tribe", "water")}

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

if __name__ == "__main__":
    c = sys.argv[1] if len(sys.argv) > 1 else ""
    G0 = load() if c else None
    TRIBES[:] = sorted({v["tribes"][i]["tribe"] for g in G0.values() for v in g.values() for i in v["tribes"]}) if c else []
    if c == "labels": cmd_labels()
    elif c == "sets": cmd_sets(sys.argv[2] if len(sys.argv) > 2 else "power", sys.argv[3].split(",") if len(sys.argv) > 3 else None)
    else: print(__doc__)
