"""Calibration harness for the win-percentage prototype (win-pct, Phase 5). Needs the pfwin build. Pure stdlib.

  python3 -I tools/winpct_eval.py states            real feature vectors of every saved checkpoint -> CACHE/states.json
  python3 -I tools/winpct_eval.py fit               static-eval fit + leave-one-game-out CV (needs states)
  python3 -I tools/winpct_eval.py playouts H N      N playouts of H rounds from every eval point -> CACHE/play_H.json
  python3 -I tools/winpct_eval.py report H          calibration tables (needs states, fit, playouts)
CACHE = $WINPCT_CACHE or /tmp/winpct_cache. Notes and numbers: .scratchpad/investigations/win-pct.md."""
import os, sys, json, glob, re, math, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import winpct_lib as W
import pf_jobs as PJ

CACHE = os.environ.get("WINPCT_CACHE", "/tmp/winpct_cache")
FI = W.FI

def saves():
    """{game id: {turn: path}} of the decoded saves (one per turn per game; the last file wins if a turn repeats)."""
    g = collections.defaultdict(dict)
    for f in sorted(glob.glob(os.path.join(W.ROOT, "saves", "*_t*.json"))):
        m = re.search(r"([0-9a-f-]{36})_t(\d+)\.json$", f)
        if m: g[m.group(1)][int(m.group(2))] = f
    return g

def cmd_states():
    os.makedirs(CACHE, exist_ok=True)
    jobs, meta = [], {}
    for gid, ts in saves().items():
        for t, f in ts.items():
            pl, turn = W.save_info(f)
            tag = f"{gid[:8]}|{t}"
            jobs.append({"tag": tag, "start": f, "player": pl, "state_only": True}); meta[tag] = (gid[:8], t, pl, turn)
    out = {}
    for r in W.run(jobs):
        if "error" in r: print("ERR", r["tag"], r["error"]); continue
        g, t, pl, turn = meta[r["tag"]]
        out[r["tag"]] = {"game": g, "t": t, "player": pl, "turn": turn, "tribes": r["tribes"], "feats": r["start"], "fog": r.get("fog"), "explored": r.get("explored")}
    json.dump(out, open(os.path.join(CACHE, "states.json"), "w"))
    print(len(out), "states ->", CACHE)

KEEP = ["alive"] + [n for n in ("cities", "level", "unit_hp_cost", "stars", "income", "techs", "kills", "score")]
HS = [1, 2, 3, 4, 6, 8]

def cmd_playouts(hmax, n, belief=False):
    """Playouts from every saved state (full information unless belief): CACHE/play_{hmax}{_b}.json, tag -> {h: {tribe: [[KEEP feats] per playout]}}."""
    states = json.load(open(os.path.join(CACHE, "states.json")))
    hs = [h for h in HS if h <= hmax]
    jobs = []
    only = os.environ.get("WINPCT_GAMES", "").split(",")
    for tag, v in states.items():
        if only != [""] and v["game"] not in only: continue
        j = {"tag": tag, "start": os.path.join(W.ROOT, "saves", "%s_t%d.json" % (full_id(v["game"]), v["t"])), "player": v["player"], "playouts": n, "horizon": max(hs), "snap_hs": hs, "seed": 1}
        if belief: j["belief_pov"] = v["player"]
        jobs.append(j)
    name = os.path.join(CACHE, "play_%d%s.json" % (hmax, "_b" if belief else ""))
    out = json.load(open(name)) if os.path.exists(name) else {}      # resumable: states already done are skipped
    jobs = [j for j in jobs if j["tag"] not in out]
    ix = [FI[k] for k in KEEP]; stats = [0.0, 0.0]
    import concurrent.futures as cf
    with cf.ThreadPoolExecutor(4) as ex:
        for k, r in enumerate(ex.map(lambda j: W.run([j], 1)[0], jobs)):
            if "error" in r: print("ERR", r["tag"], r["error"], flush=True); continue
            out[r["tag"]] = {str(h): {t: [[pl[j][t][i] for i in ix] for pl in r["playouts"]] for t in r["tribes"]} for j, h in enumerate(r["hs"])}
            stats[0] += r["secs"]; stats[1] += r["rounds_per_s"] * r["secs"]
            if k % 10 == 9: json.dump(out, open(name, "w")); print(k + 1, "of", len(jobs), "cpu-s %.0f rounds %.0f" % tuple(stats), flush=True)
    json.dump(out, open(name, "w"))
    print(len(out), "states; cpu-seconds %.0f; rounds %.0f" % tuple(stats), flush=True)

def full_id(g): return next(k for k in saves() if k.startswith(g))

# ---- static evaluation: conditional logit over the alive tribes of a state -> P(leader at t+L) --------------------------------
PHI, SCALE, phi, softmax_probs = W.PHI, W.SCALE, W.phi, W.softmax_probs

# Held-out for win-pct: ed6cb932 (data/holdout.json) and games 7 and 8 (710ddb20, 64795ee3). Games 7 and 8 were released for rule tuning
# on 27 Oct, but neither the bot policy v2 nor anything here was fitted on them, so they stay held-out for this work.
HELD = ("ed6cb932", "710ddb20", "64795ee3")

def held_game(g): return g if g in HELD else None

def tuned_games(states): return {v["game"] for v in states.values() if not held_game(v["game"])}

def points(states, lag, label="score", games=None):
    """[(game, t, feats_t, share_at_t+lag)] for every checkpoint t whose t+lag exists (same game)."""
    by = collections.defaultdict(dict)
    for v in states.values(): by[v["game"]][v["t"]] = v
    out = []
    for g, ts in sorted(by.items()):
        if games is not None and g not in games: continue
        for t, v in sorted(ts.items()):
            if t + lag in ts and any(W.alive(f) for f in v["feats"].values()):
                out.append((g, t, v["feats"], W.leader_share(ts[t + lag]["feats"], label)))
    return out

def fit_softmax(pts, names=PHI, l2=0.5, iters=150):
    """Maximise sum_points sum_p y_p log pi_p - l2 |w|^2 by gradient ascent (Adam). Returns w."""
    k = len(names); w = [0.0] * k; m = [0.0] * k; v = [0.0] * k
    X = []
    for g, t, f, y in pts:
        live = [i for i, x in f.items() if W.alive(x)]
        if len(live) < 2: continue
        X.append(([phi(f[i], names) for i in live], [y.get(i, 0.0) for i in live]))
    for it in range(1, iters + 1):
        gr = [-2 * l2 * a for a in w]
        for xs, ys in X:
            z = [sum(a * b for a, b in zip(w, x)) for x in xs]; mx = max(z); e = [math.exp(a - mx) for a in z]; s = sum(e)
            pi = [a / s for a in e]; ysum = sum(ys)
            for j in range(k):
                ex = sum(p * x[j] for p, x in zip(pi, xs))
                gr[j] += sum(y * (x[j] - ex) for y, x in zip(ys, xs))
        for j in range(k):
            m[j] = .9 * m[j] + .1 * gr[j]; v[j] = .999 * v[j] + .001 * gr[j] ** 2
            w[j] += 0.05 * (m[j] / (1 - .9 ** it)) / (math.sqrt(v[j] / (1 - .999 ** it)) + 1e-8)
    return w

def eval_pairs(pts, predict):
    """[(p, y)] over every (point, alive tribe), and the log-loss of the leader share."""
    pairs, ll, n = [], 0.0, 0
    for g, t, f, y in pts:
        pr = predict(f)
        for i in f:
            if W.alive(f[i]): pairs.append((pr[i], y.get(i, 0.0)))
        ll -= sum(yy * math.log(max(pr[i], 1e-6)) for i, yy in y.items() if yy > 0); n += 1
    return pairs, ll / max(1, n)

def uniform(f):
    live = [i for i, x in f.items() if W.alive(x)]
    return {i: (1.0 / len(live) if i in live else 0.0) for i in f}

def cv_static(states, lag, label="score", names=PHI, l2=0.5):
    """Leave-one-game-out over the tuned games (held-out games never fit). Returns dict name -> (brier, logloss, n_points)."""
    tuned = tuned_games(states)
    allp = points(states, lag, label)
    res = collections.defaultdict(list)
    for g in sorted(tuned):
        tr = [p for p in allp if p[0] in tuned and p[0] != g]; te = [p for p in allp if p[0] == g]
        if not te or not tr: continue
        w = fit_softmax(tr, names, l2)
        sc = fit_softmax(tr, ["score"], l2)
        res["static"] += [(g, t, f, y, softmax_probs(w, f, names)) for g, t, f, y in te]
        res["score_only"] += [(g, t, f, y, softmax_probs(sc, f, ["score"])) for g, t, f, y in te]
        res["uniform"] += [(g, t, f, y, uniform(f)) for g, t, f, y in te]
    out = {}
    for k, rows in res.items():
        pairs = [(p[i], y.get(i, 0.0)) for g, t, f, y, p in rows for i in f if W.alive(f[i])]
        ll = -sum(sum(yy * math.log(max(p[i], 1e-6)) for i, yy in y.items() if yy > 0) for g, t, f, y, p in rows) / len(rows)
        out[k] = (W.brier(pairs), ll, len(rows))
    return out

def cmd_write():
    """Fit the static eval on the tuned games for each lag and write data/winpct_static.json (used by tools/winpct.py)."""
    states = json.load(open(os.path.join(CACHE, "states.json"))); tuned = tuned_games(states)
    out = {"about": "conditional-logit weights over alive tribes: P(leads in-game score at t+lag) = softmax(w . phi(state)); fitted by tools/winpct_eval.py write on the tuned games only", "names": PHI, "scale": SCALE, "tuned": sorted(tuned), "lags": {}}
    for lag in (1, 2, 3, 4, 6):
        pts = [p for p in points(states, lag, "score") if p[0] in tuned]
        out["lags"][str(lag)] = {"w": [round(x, 4) for x in fit_softmax(pts, PHI)], "points": len(pts)}
    json.dump(out, open(os.path.join(W.ROOT, "data", "winpct_static.json"), "w"), indent=1)
    print({k: v["w"] for k, v in out["lags"].items()})

def cmd_fit():
    states = json.load(open(os.path.join(CACHE, "states.json")))
    for label in ("score", "cities"):
        print("label", label, "(leader at t+lag), leave-one-game-out over tuned games: Brier per (point, tribe) / log-loss per point / points")
        for lag in (1, 2, 3, 4, 6, 8):
            r = cv_static(states, lag, label)
            print(f"  lag {lag}: " + "  ".join(f"{k} {b:.4f}/{l:.3f}/{n}" for k, (b, l, n) in r.items()))

# ---- calibration report ---------------------------------------------------------------------------------------------------
def play_probs(play, tag, h, label="score"):
    """{tribe: share of playouts in which it leads at round h}, and the per-playout end feature dicts {tribe: feats(KEEP order)}."""
    P = play[tag][str(h)]
    n = len(next(iter(P.values())))
    full = lambda v: [v[0]] + [0.0] * 0 + v[1:]
    sh = collections.defaultdict(float); ends = []
    for k in range(n):
        st = {t: P[t][k] for t in P}
        ends.append(st)
        # leader by label from KEEP vectors: build a FEATS-shaped dict for leader_share
        fe = {t: _to_feats(v) for t, v in st.items()}
        for t, x in W.leader_share(fe, label).items(): sh[t] += x / n
    return {t: sh.get(t, 0.0) for t in P}, ends

def _to_feats(v):
    f = [0.0] * len(W.FEATS)
    for name, x in zip(KEEP, v): f[FI[name]] = x
    return f

def cut_probs(ends, w, names=PHI):
    """Mean over playouts of the static softmax applied to each end state."""
    acc = collections.defaultdict(float)
    for st in ends:
        for t, x in softmax_probs(w, {t: _to_feats(v) for t, v in st.items()}, names).items(): acc[t] += x / len(ends)
    return acc

def cmd_report(hmax, belief=False):
    states = json.load(open(os.path.join(CACHE, "states.json")))
    play = json.load(open(os.path.join(CACHE, "play_%d%s.json" % (hmax, "_b" if belief else ""))))
    tuned = tuned_games(states); label = "score"
    nplay = len(next(iter(next(iter(next(iter(play.values())).values())).values())))
    print("playouts per state:", nplay, "| label: leader by in-game score at t+H (ties split) | belief" if belief else "| label: leader by in-game score at t+H (ties split) | full information")
    for H in [h for h in HS if h <= hmax and h >= 2]:
        pts = points(states, H, label)
        cut = H // 2 if H > 2 else 1
        rows = collections.defaultdict(list)    # name -> [(split, game, t, f, y, probs)]
        fits = {}
        def W_(g, lag, names=PHI):
            key = (g, lag, tuple(names))
            if key not in fits: fits[key] = fit_softmax([p for p in points(states, lag, label) if p[0] in tuned and p[0] != g], names)
            return fits[key]
        for g, t, f, y in pts:
            split = "tuned" if g in tuned else "held"
            tag = "%s|%d" % (g, t)
            if tag not in play: continue
            pp, _ = play_probs(play, tag, H, label)
            _, ends_c = play_probs(play, tag, cut, label)
            wl = W_(g, H); wsc = W_(g, H, ["score"])
            lg = H - cut
            cp = cut_probs(ends_c, W_(g, lg)) if lg > 0 else None
            rows["uniform"].append((split, g, t, f, y, uniform(f)))
            rows["score_only"].append((split, g, t, f, y, softmax_probs(wsc, f, ["score"])))
            rows["static"].append((split, g, t, f, y, softmax_probs(wl, f)))
            rows["playout"].append((split, g, t, f, y, pp))
            st = softmax_probs(wl, f)
            rows["playout+static"].append((split, g, t, f, y, {i: 0.5 * pp[i] + 0.5 * st[i] for i in f}))
            if cp: rows["cut@%d+static" % cut].append((split, g, t, f, y, cp))
        print(f"\nH={H}")
        for name, rs in rows.items():
            cells = []
            for sp in ("tuned", "held"):
                r = [x for x in rs if x[0] == sp]
                if not r: continue
                pairs = [(p[i], y.get(i, 0.0)) for _, g, t, f, y, p in r for i in f if W.alive(f[i])]
                ll = -sum(sum(yy * math.log(max(0.5 * p[i] + 0.5 / len(f), 1e-6)) for i, yy in y.items() if yy > 0) for _, g, t, f, y, p in r) / len(r)
                cells.append(f"{sp}: Brier {W.brier(pairs):.4f} logloss* {ll:.3f} (n={len(r)})")
            print(f"  {name:16s} " + " | ".join(cells))
        for name in ("playout", "playout+static", "static"):
            r = [x for x in rows[name] if x[0] == "tuned"]
            pairs = [(p[i], y.get(i, 0.0)) for _, g, t, f, y, p in r for i in f if W.alive(f[i])]
            print(f"  reliability {name} (tuned):", "; ".join(f"[{lo:.2f},{hi:.2f}) n={n} pred {mp:.3f} obs {my:.3f}" for lo, hi, n, mp, my in W.reliability(pairs)))

def cmd_smoke():
    """check.sh informational line: 8 playouts of 2 rounds from a small real state; leader shares must sum to 1."""
    f = sorted(glob.glob(os.path.join(W.ROOT, "saves", "9be1198d-*_t5.json")))[0]
    pl, _ = W.save_info(f)
    r = W.run([{"tag": "s", "start": f, "player": pl, "playouts": 8, "horizon": 2, "snap_hs": [2], "seed": 1}], 1)[0]
    tot = sum(sum(W.leader_share(pl_[0], "score").values()) for pl_ in r["playouts"]) / 8
    print("WINPCT SMOKE ok=%s playouts=%d lead_share_sum=%.2f rounds_per_s=%.0f" % (abs(tot - 1) < 1e-9 and not r["panics"], len(r["playouts"]), tot, r["rounds_per_s"]))

if __name__ == "__main__":
    c = sys.argv[1] if len(sys.argv) > 1 else ""
    if c == "states": cmd_states()
    elif c == "fit": cmd_fit()
    elif c == "write": cmd_write()
    elif c == "smoke": cmd_smoke()
    elif c == "report": cmd_report(int(sys.argv[2]), "--belief" in sys.argv)
    elif c == "playouts": cmd_playouts(int(sys.argv[2]), int(sys.argv[3]), "--belief" in sys.argv)
    else: print(__doc__)
