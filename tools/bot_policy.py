"""bot-policy: how well a policy predicts the built-in bots' moves inside the forward model (Polyfish).

  python3 -I tools/bot_policy.py collect      # replay every game with PF_DECISIONS=1 -> saves/bot_decisions.jsonl
  python3 -I tools/bot_policy.py eval [v2]    # top-1 / top-3 agreement: v1 rules (or the fitted v2) vs random
  python3 -I tools/bot_policy.py fit          # conditional logit on the tuned games -> data/bot_policy.json
  python3 -I tools/bot_policy.py play [--held|--game ID] [--rounds 2] [--seeds 5] [--every 3] [--policy v2|v1|random]
                                              # playouts from real saves vs what happened (distribution check)

A decision = one legal logged action by a bot player: every legal Polyfish move at that point, with the features
from sim/pfcore/src/botpolicy.rs, and the move the bot played. Held-out games (data/holdout.json) are scored
separately and never used for fitting. Measures (tie-aware: a tie with k others counts 1/(k+1)):
  all    : the bot's move among every legal move;
  actor  : among the moves of the same unit / city (for Research: among research moves) -- "what" given "who";
  kind   : the top move's class equals the bot's (Step, Attack, Train, ...).
Random baseline = 1/n (3/n) on the same sets. Pure stdlib.
"""
import os, sys, json, math, collections, random, subprocess
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "tools"))
import pf_jobs as J

DATA = os.path.join(ROOT, "saves", "bot_decisions.jsonl")
OUT = os.path.join(ROOT, "data", "bot_policy.json")
KINDS = ["EndTurn", "Step", "Attack", "Train", "Upgrade", "Research", "Build", "Harvest", "CapVillage", "CapCity",
         "CapRuin", "CapOther", "Reward", "Convert", "Recover", "HealOthers", "Promote", "Diplomacy", "Forest", "Ability"]
HELD = set(J.HELD)


def collect():
    jobs, _ = J.jobs_for(keep=lambda g, t: True)
    os.environ["PF_DECISIONS"] = "1"
    by_game = collections.defaultdict(list)
    for j in jobs: by_game[j["tag"][:36]].append(j)
    # one process per game, in parallel
    import tempfile
    procs = []
    with tempfile.TemporaryDirectory() as tmp:
        for gid, js in by_game.items():
            jf = os.path.join(tmp, gid + ".json"); json.dump(js, open(jf, "w"))
            procs.append((gid, subprocess.Popen([J.BIN, jf], stdout=subprocess.PIPE, text=True)))
        n = 0
        with open(DATA, "w") as f:
            for gid, p in procs:
                for line in p.stdout:
                    if not line.startswith("PFJSON "): continue
                    r = json.loads(line[7:])
                    if r.get("error"): print("error", r["tag"], r["error"]); continue
                    cols = r["cols"]
                    for d in r["decisions"]:
                        d["game"] = gid; d["tag"] = r["tag"]
                        d["c"] = [c[:5] + [{cols[k]: v for k, v in zip(c[5][::2], c[5][1::2])}] for c in d["c"]]
                        f.write(json.dumps(d, separators=(",", ":")) + "\n"); n += 1
                p.wait()
    print(f"{n} bot decisions from {len(by_game)} games -> {os.path.relpath(DATA, ROOT)}")


def load():
    return [json.loads(l) for l in open(DATA)]


def hit(scores, i, k):
    s = scores[i]; better = sum(x > s for x in scores); eq = sum(x == s for x in scores)
    return min(1.0, max(0.0, (k - better) / eq))


def actor_set(d):
    ch = d["c"][d["chosen"]]
    if ch[0] == 0: return None
    if ch[0] == 5: return [j for j, c in enumerate(d["c"]) if c[0] == 5]
    if ch[1] < 0: return None
    return [j for j, c in enumerate(d["c"]) if c[1] == ch[1] and c[0] != 5]


def v2_scorer(pj):
    """The playout policy: fitted weights + endturn_bias + capture_first, as botpolicy.rs scores them."""
    w = dict(pj["weights"]); w["k:EndTurn"] = w.get("k:EndTurn", 0.0) + pj.get("endturn_bias", 0.0)
    cap = 50.0 if pj.get("capture_first") else 0.0
    return lambda d: [sum(w.get(k, 0.0) * v for k, v in c[5].items()) + (cap if c[0] in (8, 9) else 0.0) for c in d["c"]]


def evaluate(ds, scorer, name):
    rows = collections.defaultdict(lambda: [0, 0.0, 0.0, 0.0, 0.0])  # n, top1, top3, rand1, rand3
    def add(key, sc, i, n):
        r = rows[key]; r[0] += 1; r[1] += hit(sc, i, 1); r[2] += hit(sc, i, 3); r[3] += 1 / n; r[4] += min(3, n) / n
    for d in ds:
        sc = scorer(d); i = d["chosen"]; k = KINDS[d["c"][i][0]]; n = len(sc)
        add(("all", "ALL"), sc, i, n); add(("all", k), sc, i, n)
        a = actor_set(d)
        if a and len(a) > 0:
            sub = [sc[j] for j in a]; ai = a.index(i)
            add(("actor", "ALL"), sub, ai, len(a)); add(("actor", k), sub, ai, len(a))
        # kind of the top move
        best = max(sc); tops = [j for j, x in enumerate(sc) if x == best]
        r = rows[("kind", "ALL")]; r[0] += 1; r[1] += sum(d["c"][j][0] == d["c"][i][0] for j in tops) / len(tops)
    return {f"{m}|{k}": dict(n=v[0], top1=round(v[1] / v[0], 3), top3=round(v[2] / v[0], 3),
                              rand1=round(v[3] / v[0], 3), rand3=round(v[4] / v[0], 3)) for (m, k), v in sorted(rows.items())}


def show(res, title, kinds=("ALL", "Step", "Attack", "Train", "Research", "EndTurn", "Build", "Harvest", "CapVillage", "CapCity", "Reward")):
    print(title)
    for m in ("all", "actor"):
        for k in kinds:
            r = res.get(f"{m}|{k}")
            if r: print(f"  {m:5} {k:10} n={r['n']:5}  top1 {r['top1']:.3f} top3 {r['top3']:.3f}   random {r['rand1']:.3f} / {r['rand3']:.3f}")
    r = res["kind|ALL"]; print(f"  kind of top move = bot's kind: {r['top1']:.3f} (n={r['n']})")


def fit(ds, l2=0.01, iters=300, lr=0.1, seed=1):
    """Conditional logit (softmax over each decision's legal moves), AdaGrad, L2."""
    feats = sorted({k for d in ds for c in d["c"] for k in c[5]})
    w = {k: 0.0 for k in feats}; g2 = {k: 1e-8 for k in feats}
    for it in range(iters):
        grad = collections.defaultdict(float); ll = 0.0
        for d in ds:
            sc = [sum(w[k] * v for k, v in c[5].items()) for c in d["c"]]
            m = max(sc); e = [math.exp(x - m) for x in sc]; z = sum(e)
            ll += sc[d["chosen"]] - m - math.log(z)
            for c, x in zip(d["c"], e):
                p = x / z
                if p > 1e-6:
                    for k, v in c[5].items(): grad[k] -= p * v
            for k, v in d["c"][d["chosen"]][5].items(): grad[k] += v
        for k in feats:
            gk = grad[k] / len(ds) - l2 * w[k]
            g2[k] += gk * gk; w[k] += lr * gk / math.sqrt(g2[k])
        if it % 25 == 0 or it == iters - 1: print(f"  iter {it}: mean log-lik {ll / len(ds):.4f}", flush=True)
    return {k: round(v, 4) for k, v in w.items() if abs(v) > 1e-4}


PLAY = os.path.join(ROOT, "sim", "pfcore", "target", "release", "botplay")
STATS = ("units", "cities", "stars", "techs", "casualties", "kills")


def first_actor(acts, i):
    for a in acts[i:]:
        p = int(a["raw"][:2], 16)
        if p != 255 and a["type"] != 20: return p
    return 1


def play(args):
    opt = dict(rounds=2, seeds=5, every=3, policy="v2", game=None, held=False, endbias=None)
    i = 0
    while i < len(args):
        k = args[i].lstrip("-")
        if k == "held": opt["held"] = True; i += 1; continue
        opt[k] = args[i + 1] if k in ("policy", "game") else float(args[i + 1]) if k in ("endbias",) else int(args[i + 1]); i += 2
    pol = OUT if opt["policy"] == "v2" else opt["policy"]
    if opt["endbias"] is not None:   # try an EndTurn offset without touching data/bot_policy.json
        import tempfile
        pj = json.load(open(OUT)); pj["endturn_bias"] = opt["endbias"]; pj["capture_first"] = bool(opt.get("capfirst", 1))
        pol = os.path.join(tempfile.mkdtemp(), "policy.json"); json.dump(pj, open(pol, "w"))
    runs = []
    for gid, ds in J.checkpoints(opt["game"] or ""):
        if opt["held"] != (gid in HELD): continue
        turns = [d["currentTurn"] for d, _ in ds]
        acts = ds[-1][0]["actions"]
        for j in range(0, len(ds), opt["every"]):
            a, fa = ds[j]
            later = []
            for r in range(1, opt["rounds"] + 1):
                if a["currentTurn"] + r not in turns: break
                later.append(ds[turns.index(a["currentTurn"] + r)][1])
            if len(later) < opt["rounds"] or len(a["actions"]) >= len(acts): continue
            runs.append((gid, a["currentTurn"], [PLAY, pol, fa, str(first_actor(acts, len(a["actions"]))), str(opt["rounds"]), str(opt["seeds"]), "--"] + later))
    procs = [(g, t, subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)) for g, t, cmd in runs]
    # per (bot tribe, start, round): simulated deltas per seed and the real delta
    rows = []
    for gid, t, p in procs:
        out = [json.loads(l) for l in p.stdout if l.startswith("{")]; p.wait()
        if not out or "real" not in out[-1]: print("failed", gid[:8], t); continue
        start, real = out[-1]["start"], out[-1]["real"]
        for r in range(opt["rounds"]):
            for tr, s0 in start.items():
                if not s0["bot"] or not real[r] or tr not in real[r]: continue
                sims = [o["rounds"][r][tr] for o in out[:-1] if len(o["rounds"]) > r and tr in o["rounds"][r]]
                if not sims: continue
                rows.append(dict(game=gid[:8], t=t, r=r + 1, real={k: real[r][tr][k] - s0[k] for k in STATS},
                                 sim=[{k: s[k] - s0[k] for k in STATS} for s in sims]))
    print(f"policy {opt['policy']}: {len(runs)} starts, {len(rows)} bot-tribe x round rows, {opt['seeds']} seeds each")
    for r in range(1, opt["rounds"] + 1):
        rr = [x for x in rows if x["r"] == r]
        if not rr: continue
        print(f"  after {r} round(s), n={len(rr)} bot tribes:")
        for k in STATS:
            real = sum(x["real"][k] for x in rr) / len(rr)
            sim = sum(sum(s[k] for s in x["sim"]) / len(x["sim"]) for x in rr) / len(rr)
            mae = sum(abs(x["real"][k] - sum(s[k] for s in x["sim"]) / len(x["sim"])) for x in rr) / len(rr)
            inside = sum(min(s[k] for s in x["sim"]) <= x["real"][k] <= max(s[k] for s in x["sim"]) for x in rr) / len(rr)
            print(f"    d{k:7} real mean {real:+6.2f}  sim mean {sim:+6.2f}  mean |real - sim| {mae:5.2f}  real inside sim range {inside:.2f}")
    return rows


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "eval"
    if cmd == "collect": return collect()
    if cmd == "play": return play(sys.argv[2:])
    ds = load()
    tuned = [d for d in ds if d["game"] not in HELD]; held = [d for d in ds if d["game"] in HELD]
    print(f"decisions: tuned {len(tuned)} ({len({d['game'] for d in tuned})} games), held-out {len(held)}")
    if cmd == "fit":
        w = fit(tuned)
        prev = json.load(open(OUT)) if os.path.exists(OUT) else {}
        json.dump(dict(endturn_bias=prev.get("endturn_bias", 0.0), capture_first=prev.get("capture_first", False),
                       calibration="endturn_bias and capture_first are set by hand from playouts on the tuned games "
                       "(tools/bot_policy.py play --endbias; .scratchpad/investigations/bot-policy.md); fit keeps them.",
                       about="bot-policy v2: conditional-logit weights over sim/pfcore/src/botpolicy.rs features, fitted on the "
                       "tuned games by tools/bot_policy.py fit (held-out games excluded). temperature 1 = the fitted probabilities.",
                       temperature=1.0, n_decisions=len(tuned), weights=w), open(OUT, "w"), indent=1, sort_keys=True)
        print(f"{len(w)} weights -> {os.path.relpath(OUT, ROOT)}")
        cmd = "eval"; sys.argv[2:] = ["v2"]
    if cmd == "eval":
        which = sys.argv[2] if len(sys.argv) > 2 else "v1"
        sc = (lambda d: [c[4] for c in d["c"]]) if which == "v1" else v2_scorer(json.load(open(OUT)))
        show(evaluate(tuned, sc, which), f"{which} on tuned games")
        show(evaluate(held, sc, which), f"{which} on held-out (ed6cb932)")


if __name__ == "__main__":
    main()
