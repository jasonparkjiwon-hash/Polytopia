"""Win-% estimator (win-pct-3): the shipped model from data/winpct_eval.json (fitted by tools/winpct_fit.py write). Needs numpy.

LABEL ('power'): the tribe holds the MOST CITIES H rounds later (ties: strongest military, then in-game score). Not the chance to win the game
(no saved game ran to a finish) and not the in-game score lead. Modes:
  full : the state is fully known (a save with the hidden map). Static eval, plus playouts when given (stacked). CHEATING for a fogged real game.
  fog  : only what the mover can know (own tribe in full; for the others public score, cities seen on explored tiles, tribes met, tribe). No playouts.
Every estimate carries a 90% interval (bootstrap over the games used to fit the model; plus playout resampling when playouts are given) and a
trust note: how often the label came true in leave-one-game-out predictions that said about the same."""
import os, sys, json, math
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import winpct_lib as W
import winpct_fit as FIT

PATH = os.path.join(W.ROOT, "data", "winpct_eval.json")
_M = None
FI = W.FI

def model():
    global _M
    if _M is None:
        _M = json.load(open(PATH)); FIT.TRIBES[:] = _M["tribes"]
    return _M

def lag_for(H):
    lags = sorted(int(k) for k in model()["lags"]); return min(lags, key=lambda k: abs(k - H))

def _pred(m, x):
    z = ((x - np.array(m["mu"])) / np.maximum(np.array(m["sd"]), 1e-6)) @ np.array(m["w"]); z = z - z.max(); e = np.exp(z); return e / e.sum()

def _point(feats, tribes, ids, player=None, fog=None, turn=0):
    return dict(ids=ids, F=np.array([feats[i] for i in ids], float), tribes=[tribes[i]["tribe"] for i in ids], turn=turn,
                v={"player": player, "fog": fog or {}}, bot=[tribes[i]["bot"] for i in ids])

def trust_note(bins, p):
    """How often the label came true when the model predicted about p (out-of-fold, pooled tribe-points)."""
    for b in bins:
        if b["lo"] <= p < b["hi"] or (p >= 1 and b["hi"] >= 1):
            flag = "" if b["n"] >= 40 else " (few cases: treat as rough)"
            return "when the model said %d-%d%%, the label came true %.0f%% of the time (%d tribe-cases, leave-one-game-out)%s" % (round(100 * b["lo"]), round(100 * b["hi"]), 100 * b["obs"], b["n"], flag)
    return "no calibration data at this level"

def estimate(feats, tribes, H, mode="fog", player=None, fog=None, ends=None, turn=0, draws=300, seed=1):
    """feats {id: 17-vector}; tribes {id: {tribe, bot}}; ends: list of {id: vector} at round H (playouts, mode 'full' only).
    Returns {id: dict(est, lo, hi, model_sd, playout_sd, trust, basis)} for the alive tribes (dead: est 0)."""
    M = model(); lag = lag_for(H); L = M["lags"][str(lag)]; rng = np.random.default_rng(seed)
    ids = [i for i in sorted(feats, key=int) if feats[i][0] > .5]
    p = _point(feats, tribes, ids, player, fog, turn)
    use_play = mode == "full" and ends
    if mode == "fog":
        x = FIT.fog_feats(p)[0]; base = _pred(L["fog"], x); boots = [_pred(b, x) for b in L["boot_fog"]]; key = "fog_distilled"; basis = "fog model (own state + public score, cities seen, tribes met)"
    else:
        x = FIT.feats(p, {"share", "war", "tribe"})[0]; base = _pred(L["full"], x); boots = [_pred(b, x) for b in L["boot_full"]]; key = "static_full"; basis = "static eval on the full state"
    k = len(ids); sw = np.array(L["stack_w"])
    if use_play:
        def lead(sample):
            acc = np.zeros(k)
            for e in sample:
                F = np.zeros((k, len(W.FEATS)))
                for a, i in enumerate(ids): F[a] = e[i]
                acc += FIT.label_vec(M["label"], F)
            return acc / len(sample)
        pp = lead(ends); n = len(ends)
        stack = lambda ppv, s: _norm(np.exp(sw[0] * np.log(ppv * .94 + .06 / k + .02) + sw[1] * np.log(s + .01)))
        est = stack(pp, base); key = "playout+static learned"; basis = "%d playouts of %d rounds stacked with the static eval" % (n, H)
        draws_p = []
        for d in range(draws):
            s_b = boots[rng.integers(len(boots))]
            pb = rng.dirichlet(pp * n + .5); draws_p.append(stack(pb, s_b))
        D = np.array(draws_p)
        model_sd = np.std([stack(pp, b) for b in boots], 0); play_sd = np.std([stack(rng.dirichlet(pp * n + .5), base) for _ in range(120)], 0)
    else:
        est = base; D = np.array(boots); model_sd = D.std(0); play_sd = np.zeros(k)
    lo, hi = np.percentile(D, 5, 0), np.percentile(D, 95, 0)
    out = {}
    for a, i in enumerate(ids):
        out[i] = dict(est=float(est[a]), lo=float(min(lo[a], est[a])), hi=float(max(hi[a], est[a])), model_sd=float(model_sd[a]), playout_sd=float(play_sd[a]),
                      trust=trust_note(L["calib"].get(key, []), float(est[a])), basis=basis, lag=lag)
    for i in feats:
        if i not in out: out[i] = dict(est=0.0, lo=0.0, hi=0.0, model_sd=0.0, playout_sd=0.0, trust="dead", basis=basis, lag=lag)
    return out

def _norm(v): return v / v.sum()

def metrics(H, mode="fog"):
    """Leave-one-game-out Brier of the shipped model for this horizon (and uniform), for the header line."""
    L = model()["lags"][str(lag_for(H))]["metrics"]
    key = {"fog": "fog_distilled", "full": "static_full", "play": "playout+static learned"}[mode]
    return L[key], L["uniform"]

LABEL_TEXT = "holds the MOST CITIES %d rounds later (ties: strongest army, then score)"
