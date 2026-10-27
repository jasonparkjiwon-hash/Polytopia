"""Distribution check for the bot policy (bot-policy-2, step 4): play the policy forward from a real save for 1-3 rounds and
compare per-bot outcomes with what the real game did between the same two saves. Needs the Polyfish build (pfbot). Pure stdlib.

  python3 -I tools/bot_dist.py POLICY.json [--holdout] [--game PREFIX] [--k 1,2,3] [--runs 8] [--random] [--max N] [--json OUT]

Windows: every checkpoint save i to save i+k of the same game (k rounds later). The simulation starts at save i (the player to move
continues that turn), the policy plays EVERY tribe (the human too) until as many EndTurns have passed as the log shows, and the end
state is compared with save i+k, bot tribes only. --random plays uniform random legal moves instead (EndTurn with chance 1/8).
Measured per bot tribe over the window: change in units, cities, stars, population, techs, kills, casualties; move counts (steps,
attacks, trains, captures, builds, research) against the logged actions. Reported: totals real vs simulated (mean over runs),
and the mean absolute error of the simulated per-tribe change against the real one, next to the same for a 'no change' guess."""
import sys, os, json, glob, re, collections, subprocess, tempfile
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "tools"))
import pf_jobs as PJ

BIN = os.path.join(ROOT, "sim", "pfcore", "target", "release", "pfbot")
LOG_GROUP = {6: "Step", 2: "Attack", 5: "Summon", 7: "Capture", 14: "Capture", 1: "Build", 8: "Research", 3: "Recover", 11: "Reward"}
STATS = ["units", "cities", "stars", "pop", "techs", "kills", "casualties"]
MOVES = ["Step", "Attack", "Summon", "Capture", "Build", "Research"]

def current_player(acts, i):
    for a in acts[i:]:
        raw = bytes.fromhex(a["raw"])
        if raw[0] != 255 and a["type"] != 20: return raw[0]
    return 1

def windows(prefix, keep, ks):
    out = []
    for gid, ds in PJ.checkpoints(prefix):
        acts = ds[-1][0]["actions"]
        for i in range(len(ds)):
            for k in ks:
                if i + k >= len(ds): continue
                (a, fa), (b, fb) = ds[i], ds[i + k]
                if not keep(gid, b["currentTurn"]): continue
                n0, n1 = len(a["actions"]), len(b["actions"])
                seg = acts[n0:n1]
                ends = sum(1 for x in seg if x["type"] == 15 and bytes.fromhex(x["raw"])[0] != 255)
                real = collections.defaultdict(collections.Counter)
                for x in seg:
                    pl = bytes.fromhex(x["raw"])[0]
                    if pl != 255 and x["type"] in LOG_GROUP: real[pl][LOG_GROUP[x["type"]]] += 1
                out.append(dict(tag=f"{gid[:8]}|t{a['currentTurn']}|k{k}", game=gid[:8], k=k, start=fa, end=fb, player=current_player(acts, n0),
                                end_player=current_player(acts, n1), end_turns=ends, real_moves=real))
    return out

def run_bin(policy, jobs):
    with tempfile.TemporaryDirectory() as tmp:
        jf = os.path.join(tmp, "jobs.json"); json.dump(jobs, open(jf, "w"))
        out = subprocess.run([BIN, policy, jf], capture_output=True, text=True, cwd=ROOT).stdout
    return {j["tag"]: j["runs"] for j in (json.loads(l[6:]) for l in out.splitlines() if l.startswith("PFBOT "))}

def main():
    a = sys.argv[1:]
    opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    policy = a[0]; hold = "--holdout" in a; random_pol = "--random" in a
    ks = [int(x) for x in opt("--k", "1,2,3").split(",")]; runs = int(opt("--runs", 8)); cap = int(opt("--max", 10**9))
    ws = windows(opt("--game", ""), lambda gid, turn: PJ.held(gid, turn) == hold, ks)
    if len(ws) > cap:
        step = len(ws) / cap; ws = [ws[int(i * step)] for i in range(cap)]
    sim_jobs = [dict(tag=w["tag"], start=w["start"], player=w["player"], end_turns=w["end_turns"], runs=runs, seed=7, sample=True, random=random_pol) for w in ws]
    real_jobs = [dict(tag=w["tag"], start=w["end"], player=w["end_player"], state_only=True) for w in ws]
    sim = run_bin(policy, sim_jobs); real = run_bin(policy, real_jobs)
    tot = collections.defaultdict(lambda: collections.defaultdict(float))     # k -> metric -> sums
    err = collections.defaultdict(lambda: collections.defaultdict(float)); n_t = collections.Counter()
    bad = sum(1 for w in ws for r in sim.get(w["tag"], []) if "error" in r)
    # start summaries: the 'before' of the simulation runs (same save for every run)
    for w in ws:
        rs = [r for r in sim.get(w["tag"], []) if "error" not in r]
        if not rs or w["tag"] not in real: continue
        start = rs[0]["before"]; endr = real[w["tag"]][0]["before"]
        for pl, s0 in start.items():
            if not s0["bot"] or pl not in endr: continue
            k = w["k"]; n_t[k] += 1
            for m in STATS:
                real_d = endr[pl][m] - s0[m]
                sims = [r["after"][pl][m] - s0[m] for r in rs if pl in r["after"]]
                if not sims: continue
                mean = sum(sims) / len(sims)
                tot[k]["real " + m] += real_d; tot[k]["sim " + m] += mean
                err[k]["mae " + m] += abs(mean - real_d); err[k]["mae0 " + m] += abs(real_d)
            for g in MOVES:
                rm = w["real_moves"].get(int(pl), {}).get(g, 0)
                sm = [sum(v for kk, v in r["counts"].get(pl, {}).items() if kk == g or (g == "Summon" and kk.startswith("Train:"))) for r in rs]
                tot[k]["real mv:" + g] += rm; tot[k]["sim mv:" + g] += sum(sm) / len(sm)
                err[k]["mae mv:" + g] += abs(sum(sm) / len(sm) - rm); err[k]["mae0 mv:" + g] += rm
    res = {}
    print(f"policy {os.path.basename(policy)}{' (random legal)' if random_pol else ''}  {'held-out' if hold else 'tuned games'}  windows {len(ws)}  runs/window {runs}  bad runs {bad}")
    for k in sorted(tot):
        print(f"  k={k} rounds, {n_t[k]} bot-tribe windows:  total real | sim mean | per-tribe MAE sim (MAE of 'no change' / of zero)")
        res[k] = {}
        for key in [f"{p} {m}" for m in STATS for p in ("real",)] + [f"real mv:{g}" for g in MOVES]:
            m = key.split(" ", 1)[1]; r = tot[k]["real " + m]; s = tot[k]["sim " + m]; n = n_t[k]
            res[k][m] = dict(real=round(r, 1), sim=round(s, 1), mae=round(err[k]["mae " + m] / n, 3), mae_zero=round(err[k]["mae0 " + m] / n, 3), n=n)
            print(f"    {m:<14}{r:>9.0f} |{s:>9.1f} |  {err[k]['mae ' + m] / n:6.2f}  ({err[k]['mae0 ' + m] / n:5.2f})")
    if opt("--json"): json.dump(res, open(opt("--json"), "w"), indent=1)

if __name__ == "__main__": main()
