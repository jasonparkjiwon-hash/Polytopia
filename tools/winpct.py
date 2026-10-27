"""Win percentage from a saved state (win-pct, Phase 5). Needs the pfwin build (cd sim/pfcore && cargo build --release).

  python3 -I tools/winpct.py <save.json | id_tN> [--player P] [--playouts N] [--horizon H] [--seed S] [--belief] [--top K]

Plays the bot policy v2 (data/bot_policy_v2.json) for EVERY tribe (the human too) from the save for H rounds, N times, and reports
per tribe the chance that it LEADS the in-game score after H rounds (ties split), with a 95% Wilson interval, plus the chance it is
still alive, and what moved (mean start -> end of cities, unit value, stars, score). A static estimate (data/winpct_static.json,
a conditional logit on the state's features, fitted on the real games) is printed beside it.
What the number is: P(leads the score after H rounds), NOT P(wins the game): no saved game ran to a finish, and the bots' own play
drifts after 2-3 rounds (bot-policy-2.md). The interval is playout noise only; model error is in the calibration tables of
.scratchpad/investigations/win-pct.md. Default is FULL INFORMATION (the save's hidden map is used: fine for calibration on saves,
cheating when advising a fogged game); --belief draws the hidden map from the subject's view (tools/pf_belief.py's sampler) per playout."""
import sys, os, json, math, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import winpct_lib as W

FI = W.FI

def resolve(arg):
    if os.path.exists(arg): return arg
    p = os.path.join(W.ROOT, "saves", arg if arg.endswith(".json") else arg + ".json")
    if os.path.exists(p): return p
    sys.exit("no such save: " + arg)

def main():
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"): print(__doc__); return
    opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    path = resolve(a[0]); n = int(opt("--playouts", 48)); H = int(opt("--horizon", 4)); seed = int(opt("--seed", 1)); top = int(opt("--top", 6))
    mover, turn = W.save_info(path)
    subject = int(opt("--player", 0)) or None
    procs = 4
    jobs = [{"tag": "w%d" % i, "start": path, "player": mover, "playouts": len(range(i, n, procs)), "horizon": H, "snap_hs": [H], "seed": seed * 100 + i,
             **({"belief_pov": subject or mover} if "--belief" in a else {})} for i in range(procs) if len(range(i, n, procs))]
    res = W.run(jobs, procs)
    bad = [r for r in res if "error" in r]
    if bad: sys.exit("pfwin: " + str(bad[0]["error"]))
    tribes, start = res[0]["tribes"], res[0]["start"]
    ends = [pl[0] for r in res for pl in r["playouts"]]
    N = len(ends)
    lead = collections.Counter(); alive = collections.Counter(); mean = collections.defaultdict(lambda: [0.0] * len(W.FEATS))
    for e in ends:
        for t, x in W.leader_share(e, "score").items(): lead[t] += x
        for t, f in e.items():
            alive[t] += W.alive(f)
            for i, v in enumerate(f): mean[t][i] += v / N
    static = None
    sp = os.path.join(W.ROOT, "data", "winpct_static.json")
    if os.path.exists(sp):
        m = json.load(open(sp)); lag = str(min((int(k) for k in m["lags"]), key=lambda k: abs(k - H)))
        static = W.softmax_probs(m["lags"][lag]["w"], start, m["names"])
    print("%s  turn %d, player %d to move, %d tribes, %d playouts x %d rounds, %s" % (os.path.basename(path), turn, mover, len(tribes), N, H,
          "BELIEF-sampled hidden map" if "--belief" in a else "FULL INFORMATION (hidden map known: calibration use only)"))
    print("lead% = P(highest in-game score after %d rounds), 95%% interval; alive%% after %d rounds; start -> mean end" % (H, H))
    order = sorted(tribes, key=lambda t: -lead[t])
    shown = order[:top] + ([str(subject)] if subject and str(subject) not in order[:top] else [])
    for t in shown:
        lo, hi = W.wilson(lead[t], N)
        s, e = start[t], mean[t]
        tag = "%s%s%s" % (tribes[t]["tribe"], " (human)" if not tribes[t]["bot"] else "", " <- subject" if subject and int(t) == subject else "")
        print("  p%-3s %-26s lead %5.1f%% [%4.1f-%4.1f]  static %s  alive %5.1f%%  cities %.0f->%.1f  units %.0f->%.1f  stars %.0f->%.1f  score %.0f->%.0f" % (
            t, tag, 100 * lead[t] / N, 100 * lo, 100 * hi, ("%5.1f%%" % (100 * static[t])) if static else "  n/a ", 100 * alive[t] / N,
            s[FI["cities"]], e[FI["cities"]], s[FI["unit_hp_cost"]], e[FI["unit_hp_cost"]], s[FI["stars"]], e[FI["stars"]], s[FI["score"]], e[FI["score"]]))
    if subject and str(subject) in tribes:
        t = str(subject); rank = sorted(((sum(1 for u in tribes if mean[u][FI["score"]] > mean[t][FI["score"]]) + 1)),)[0]
        gap = mean[t][FI["score"]] - mean[order[0]][FI["score"]]
        print("drivers (subject p%s vs field median at the horizon): " % t + ", ".join(
            "%s %+.1f" % (nm, mean[t][FI[nm]] - sorted(mean[u][FI[nm]] for u in tribes)[len(tribes) // 2]) for nm in ("cities", "unit_hp_cost", "stars", "income", "techs", "kills", "score"))
            + "; mean score rank %d of %d" % (rank, len(tribes)))

if __name__ == "__main__": main()
