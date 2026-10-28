"""Win percentage from a saved state (win-pct, Phase 5; rebuilt 28 Oct by win-pct-3). Needs the pfwin build (cd sim/pfcore && cargo build --release) and numpy.

  python3 -I tools/winpct.py <save.json | id_tN> [--player P] [--horizon H] [--mode fog|full|both] [--playouts N] [--seed S] [--top K] [--json]

What the number is. LABEL "power": the chance that a tribe HOLDS THE MOST CITIES H rounds later (ties: strongest army, then in-game score).
It is not the chance to win the game (no saved game ran to a finish), and not the score lead. Every line carries a 90% interval, the horizon and
a trust note (how often this label came true when the model said about the same, leave-one-game-out over the real games).
Modes:
  fog   (default) what the player P can know: P's own tribe in full, for the others the public score, the cities P has seen, tribes met, tribe.
        No playouts: the unseen-unit sampling did not beat this (win-pct.md). Instant.
  full  FULL INFORMATION: plays bot policy v2 for every tribe from the save, N times (early stop when the leaders' interval is tight), and stacks the
        lead share with the static eval. This reads the save's hidden map: CHEATING for a fogged real game, fine as an upper bound / for a state you
        simulated. Playouts help only up to ~3 rounds; from 4 on the static eval alone is as good.
  both  prints fog and full side by side.
The interval covers model uncertainty (bootstrap over games) and, in full mode, playout noise. It does NOT cover the bots' drift from policy v2 after
2-3 rounds or that the human plays differently from the policy. Details and calibration tables: .scratchpad/investigations/win-pct.md."""
import sys, os, json, math, collections, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import winpct_lib as W
import winpct_est as E

FI = W.FI

def resolve(arg):
    if os.path.exists(arg): return arg
    p = os.path.join(W.ROOT, "saves", arg if arg.endswith(".json") else arg + ".json")
    if os.path.exists(p): return p
    sys.exit("no such save: " + arg)

def state(path, mover):
    r = W.run([{"tag": "s", "start": path, "player": mover, "state_only": True}], 1)[0]
    if "error" in r: sys.exit("pfwin: " + str(r["error"]))
    return r

def playouts(path, mover, H, N, seed, procs, tol=0.07, batch=None):
    """Up to N playouts of H rounds, `procs` processes at a time, in batches; stops early once every tribe that is plausible (>3%) has a 90% Wilson
    half-width below `tol` (and at least 16 playouts are in). Returns (end states, used)."""
    ends = []; batch = batch or max(8, 2 * procs); k = 0
    while len(ends) < N:
        m = min(batch, N - len(ends))
        jobs = [{"tag": "w%d" % i, "start": path, "player": mover, "playouts": len(range(i, m, procs)), "horizon": H, "snap_hs": [H], "seed": seed * 1000 + k * 64 + i}
                for i in range(procs) if len(range(i, m, procs))]
        k += 1
        res = W.run(jobs, procs)
        bad = [r for r in res if "error" in r]
        if bad: sys.exit("pfwin: " + str(bad[0]["error"]))
        ends += [pl[0] for r in res for pl in r["playouts"]]
        if tol and len(ends) >= 16 and len(ends) < N:
            lead = collections.Counter()
            for e in ends:
                for t, x in W.leader_share(e, "cities").items(): lead[t] += x
            n = len(ends)
            if all((W.wilson(c, n, 1.645)[1] - W.wilson(c, n, 1.645)[0]) / 2 < tol for c in lead.values() if c / n > .03): break
    return ends, len(ends)

def fmt(r):
    return "%4.1f%% [%4.1f-%4.1f]" % (100 * r["est"], 100 * r["lo"], 100 * r["hi"])

def main():
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"): print(__doc__); return
    opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    path = resolve(a[0]); N = int(opt("--playouts", 48)); H = int(opt("--horizon", 4)); seed = int(opt("--seed", 1)); top = int(opt("--top", 6))
    mode = opt("--mode", "fog"); procs = os.cpu_count() or 4
    mover, turn = W.save_info(path)
    subject = int(opt("--player", 0)) or mover
    st = state(path, subject); tribes = st["tribes"]; feats = st["start"]; fog = st.get("fog")
    results = {}
    if mode in ("fog", "both"): results["fog"] = E.estimate(feats, tribes, H, "fog", player=subject, fog=fog, turn=st["turn"], seed=seed)
    if mode in ("full", "both"):
        t0 = time.time(); ends, used = playouts(path, mover, H, N, seed, procs); results["full"] = E.estimate(feats, tribes, H, "full", player=subject, ends=ends, turn=st["turn"], seed=seed)
        results["full_info"] = (used, time.time() - t0)
    if "--json" in a:
        print(json.dumps({"label": "most cities at t+H", "horizon": H, "subject": subject, "estimates": {k: v for k, v in results.items() if k != "full_info"}})); return
    lag = E.lag_for(H)
    print("%s  turn %d, player %d to move, subject p%d (%s), %d tribes alive" % (os.path.basename(path), st["turn"], mover, subject, tribes[str(subject)]["tribe"], sum(1 for f in feats.values() if f[0] > .5)))
    print("label: chance a tribe %s | horizon H=%d (model fitted for H=%d)" % (E.LABEL_TEXT % H, H, lag))
    for m in ("fog", "full"):
        if m not in results: continue
        R = results[m]; order = sorted(R, key=lambda t: -R[t]["est"])
        shown = order[:top] + ([str(subject)] if str(subject) not in order[:top] else [])
        if m == "fog":
            b, u = E.metrics(H, "fog")
            print("\nFOG VIEW of p%d (no hidden information used%s). Leave-one-game-out Brier %.4f vs uniform %.4f." % (subject, "; other tribes' scores are read as public", b["brier_logo"], u["brier_logo"]))
        else:
            b, u = E.metrics(H, "play" if results["full_info"][0] else "full")
            print("\nFULL INFORMATION: CHEATING for a fogged real game (hidden map and every tribe's units used). %d playouts, %.0f s. LOGO Brier %.4f vs uniform %.4f." % (results["full_info"][0], results["full_info"][1], b["brier_logo"], u["brier_logo"]))
        print("  basis: " + R[order[0]]["basis"])
        for t in shown:
            r = R[t]; tag = "%s%s%s" % (tribes[t]["tribe"], " (human)" if not tribes[t]["bot"] else "", " <- subject" if int(t) == subject else "")
            print("  p%-3s %-24s %s  (model +-%.1f%s)" % (t, tag, fmt(r), 100 * r["model_sd"], (", playouts +-%.1f" % (100 * r["playout_sd"])) if r["playout_sd"] else ""))
        s = R[str(subject)]; print("  trust for p%d: %s" % (subject, s["trust"]))
    if "fog" in results and "full" in results:
        print("\nfog vs full-info gap for p%d: %+.1f points (the cost of not seeing the hidden state)" % (subject, 100 * (results["full"][str(subject)]["est"] - results["fog"][str(subject)]["est"])))

if __name__ == "__main__": main()
