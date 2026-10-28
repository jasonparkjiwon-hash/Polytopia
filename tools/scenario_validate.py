"""Validation of the LIKELY-reply estimate (what-if-2): after a real human move (the real end of the human's turn in the saves), does the
real enemy reply fall inside what the bot model (policy v3, K sampled enemy turns) predicted?
    python3 -I tools/scenario_validate.py [--k 20] [--game PREFIX] [--policy PATH] [--rows]
pfreplay (PF_REPLY=k, src/scenario.rs ReplyProbe) replays every window between two consecutive saves; at the human's real EndTurn it
samples K enemy rounds from the position, then watches the real bot actions that follow and records which of the human's units were
attacked / killed and which (tribe, tile) attacks happened. Printed (tuned games and held-out games, data/holdout.json, apart):
  - per unit: how often a really attacked / killed unit had been given a chance >= 50%, >= 20%, > 0; the calibration table
    (predicted chance bin -> real rate) and the Brier score against always saying the base rate
  - per window: the real number of units lost lies in the central 80% of the sampled numbers; the real number was seen at all
  - per attack: a real (tribe, tile) attack had predicted chance > 0 / >= 10% / >= 30%; the predicted top attack really happened
Notes: windows are the real human turns in the saves with a logged EndTurn of the human; units are keyed by tile when the turn ended
(a push or a disband would show as a kill; rare); the model plays every tribe, the real bots played on their own fog."""
import argparse, collections, json, os, sys, concurrent.futures as cf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pf_jobs as PJ

ROOT = PJ.ROOT


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0]); ap.add_argument("--k", type=int, default=20); ap.add_argument("--game", default="")
    ap.add_argument("--policy", default=os.path.join(ROOT, "data", "bot_policy_v3.json")); ap.add_argument("--rows", action="store_true"); ap.add_argument("--json")
    a = ap.parse_args()
    os.environ["PF_REPLY"] = str(a.k); os.environ["PF_REPLY_POLICY"] = a.policy
    jobs, _ = PJ.jobs_for(a.game, lambda g, t: True)
    chunks = [jobs[i::4] for i in range(4)]
    with cf.ThreadPoolExecutor(4) as ex: R = [r for part in ex.map(PJ.run, chunks) for r in part]
    S = {True: collections.defaultdict(float), False: collections.defaultdict(float)}
    bins = {True: collections.defaultdict(lambda: [0, 0.0, 0]), False: collections.defaultdict(lambda: [0, 0.0, 0])}
    kbins = {True: collections.defaultdict(lambda: [0, 0.0, 0]), False: collections.defaultdict(lambda: [0, 0.0, 0])}
    rows, errs = [], 0
    edges = [0.0, 0.0001, 0.25, 0.5, 0.75, 1.0001]
    def put(tab, p, y):
        b = next(i for i in range(len(edges) - 1) if edges[i] <= p < edges[i + 1]); t = tab[b]; t[0] += 1; t[1] += p; t[2] += y
    for r in R:
        if "error" in r or not isinstance(r.get("reply"), list): errs += 1; continue
        gid, _, b = r["tag"].split("|"); h = PJ.held(gid, int(b)); s = S[h]
        for w in r["reply"]:
            if not w["units"]: continue
            s["windows"] += 1
            for u in w["units"]:
                s["units"] += 1; ya, yk = int(u["real_att"]), int(u["real_kill"])
                s["att"] += ya; s["kill"] += yk
                s["brier_att"] += (u["p_att"] - ya) ** 2; s["brier_kill"] += (u["p_kill"] - yk) ** 2
                put(bins[h], u["p_att"], ya); put(kbins[h], u["p_kill"], yk)
                if ya:
                    s["att_ge50"] += u["p_att"] >= 0.5; s["att_ge20"] += u["p_att"] >= 0.2; s["att_gt0"] += u["p_att"] > 0
                if yk:
                    s["kill_ge50"] += u["p_kill"] >= 0.5; s["kill_ge20"] += u["p_kill"] >= 0.2; s["kill_gt0"] += u["p_kill"] > 0
                s["pred_att_sum"] += u["p_att"]; s["pred_kill_sum"] += u["p_kill"]
            le, eq = w["pred_lost_le"], w["pred_lost_eq"]
            s["lost_seen"] += eq > 0; s["lost_central"] += (le - eq) <= 0.9 and le >= 0.1
            s["real_lost"] += w["real_lost"]; s["pred_lost"] += w["pred_lost_mean"]
            rp = w["real_pairs"]; s["pairs"] += len(rp)
            for q in rp: s["pair_gt0"] += q["p"] > 0; s["pair_ge10"] += q["p"] >= 0.1; s["pair_ge30"] += q["p"] >= 0.3
            if w["pairs"]:
                s["top_windows"] += 1
                realset = {(q["who"], q["tile"]) for q in rp}
                s["top1_real"] += (w["pairs"][0]["who"], w["pairs"][0]["tile"]) in realset
                s["top3_real"] += any((q["who"], q["tile"]) in realset for q in w["pairs"][:3])
            s["windows_real_attack"] += bool(rp)
            s["city_cap_real"] += len(w["cities"]["real_capture"])
            capp = {c[0]: c[1] for c in w["cities"]["pred_capture"]}
            for c in w["cities"]["real_capture"]: s["city_cap_pred_gt0"] += capp.get(c, 0) > 0
            rows.append((r["tag"], w))
    def pr(h, name):
        s = S[h]
        if not s["units"]: print("%s: no windows" % name); return
        u, A, K = s["units"], s["att"], s["kill"]
        base_a, base_k = A / u, K / u
        print("== %s: %d windows, %d of the human's units at turn end, %d really attacked, %d really killed" % (name, s["windows"], u, A, K))
        f = lambda x, n: "%d/%d (%.0f%%)" % (x, n, 100 * x / n) if n else "-"
        print("  really attacked units: predicted chance >=50%%: %s, >=20%%: %s, >0: %s" % (f(s["att_ge50"], A), f(s["att_ge20"], A), f(s["att_gt0"], A)))
        print("  really killed units:   predicted chance >=50%%: %s, >=20%%: %s, >0: %s" % (f(s["kill_ge50"], K), f(s["kill_ge20"], K), f(s["kill_gt0"], K)))
        print("  Brier, attacked: model %.3f vs base rate %.3f (%.3f)   killed: model %.3f vs %.3f (%.3f)   [lower is better]" % (
            s["brier_att"] / u, base_a * (1 - base_a), base_a, s["brier_kill"] / u, base_k * (1 - base_k), base_k))
        for lab, tab in (("attacked", bins[h]), ("killed", kbins[h])):
            names = ["0", "0-25%", "25-50%", "50-75%", "75-100%"]
            print("  calibration %s (predicted bin: n, mean predicted, real rate): " % lab + "; ".join("%s: %d, %.0f%%, %.0f%%" % (names[i], tab[i][0], 100 * tab[i][1] / tab[i][0], 100 * tab[i][2] / tab[i][0]) for i in range(5) if tab[i][0]))
        print("  units lost per window: real %.2f, model mean %.2f; real count inside the central 80%% of the samples in %s; count seen in the samples at all in %s" % (
            s["real_lost"] / s["windows"], s["pred_lost"] / s["windows"], f(s["lost_central"], s["windows"]), f(s["lost_seen"], s["windows"])))
        p = s["pairs"]
        print("  real attacks on the human's units (tribe, tile): %d; predicted chance >0: %s, >=10%%: %s, >=30%%: %s" % (p, f(s["pair_gt0"], p), f(s["pair_ge10"], p), f(s["pair_ge30"], p)))
        print("  predicted most-likely attack really happened: %s windows; one of the top 3: %s (windows with a predicted attack; real attacks in %s of %d windows)" % (
            f(s["top1_real"], s["top_windows"]), f(s["top3_real"], s["top_windows"]), s["windows_real_attack"], s["windows"]))
        if s["city_cap_real"]: print("  real captures of the human's cities: %d, predicted chance >0 for %d" % (s["city_cap_real"], s["city_cap_pred_gt0"]))
    print("SCENARIO REPLY VALIDATION (K=%d sampled enemy rounds per real human turn; policy %s; %d jobs, %d errors)" % (a.k, os.path.basename(a.policy), len(jobs), errs))
    pr(False, "tuned games"); pr(True, "held-out games")
    if a.json: json.dump([{"tag": t, **w} for t, w in rows], open(a.json, "w"))
    if a.rows:
        for t, w in rows[:40]: print(t, w["real_lost"], [(u["type"], round(u["p_att"], 2), u["real_att"]) for u in w["units"]][:6])


if __name__ == "__main__":
    main()
