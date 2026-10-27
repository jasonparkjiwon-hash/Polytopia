"""Bot move model v3 (bot-model-3): fit and score the two-stage policy of sim/pfcore/src/botpolicy2.rs on decision dumps.
Pure stdlib (multiprocessing for the gradient). Same weights-file form as v2 ({"g": stage 1, "w": stage 2, "rules": {...}}),
plus "C:"-prefixed delta weights that apply only to Crazy bots (DifficultyHandicap >= 4); the Hard weights are the base.

  python3 -I tools/bot_dump.py DUMP.jsonl --all                    decision dump of every game (3 min, ~700 MB: keep it in scratch)
  python3 -I tools/bot_policy3.py prep DUMP.jsonl DATA.pkl          compact records (bot decisions whose logged move Polyfish lists)
  python3 -I tools/bot_policy3.py eval DATA.pkl --w v2.json[,v3.json] [--split]
  python3 -I tools/bot_policy3.py fit DATA.pkl --out OUT.json [--l2 0.02] [--l2c 1.0] [--iters 80] [--cv] [--nodiff]

Split (never fit on test data): TEST = ed6cb932 (all of it: Crazy, turns 1-4) + game 7 (710ddb20) turns 12-19 (Hard). Everything else is TRAIN.
Stage 1 = which move group next, stage 2 = which move inside it (see botpolicy2.rs). Chance is exact (ties split)."""
import sys, os, json, math, pickle, collections, multiprocessing as mp
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import bot_policy2 as B2
ROOT = os.path.join(HERE, "..")
dot, logsoft, rank_hit, fmt = B2.dot, B2.logsoft, B2.rank_hit, B2.fmt

def is_test(r): return r["game"] == "ed6cb932" or (r["game"] == "710ddb20" and r["turn"] >= 12)
def kind_of(r): return "Crazy" if r["crazy"] else "Hard"

def prep(dump, out):
    recs = []
    for line in open(dump):
        d = json.loads(line)
        if not d["bot"] or d["c"] < 0: continue
        crazy = d["h"] >= 4
        gf = {g: dict(f) for g, f in d["gf"].items()}
        by = collections.defaultdict(list); srcs = collections.defaultdict(list); tg = collections.defaultdict(list)
        for m in d["m"]: by[m[0]].append(dict(m[1])); srcs[m[0]].append(m[2]); tg[m[0]].append(m[3])
        cg = d["m"][d["c"]][0]; ci = sum(1 for m in d["m"][:d["c"]] if m[0] == cg)
        cands = by[cg]
        if crazy:
            gf = {g: {**f, **{"C:" + k: v for k, v in f.items()}} for g, f in gf.items()}
            cands = [{**f, **{"C:" + k: v for k, v in f.items()}} for f in cands]
        recs.append(dict(game=d["tag"].split("|")[0][:8], turn=d["t"], tribe=d["tr"], crazy=crazy, n=len(d["m"]), stars=d["st"], cheap=d["cheap"],
                         groups=gf, cg=cg, cands=cands, ci=ci, srcs=srcs[cg], tgts=tg[cg]))
    pickle.dump(recs, open(out, "wb"), protocol=4); print(len(recs), "records ->", out)

def load(path):
    recs = pickle.load(open(path, "rb"))
    return [r for r in recs if not is_test(r)], [r for r in recs if is_test(r)]

# ---------- parallel conditional logit (Adagrad), per-feature l2 ----------
_P = None
def _grad(args):
    lo, hi, w = args
    gr = collections.defaultdict(float); ll = 0.0
    for fs, c in _P[lo:hi]:
        sc = [sum(w[i] * v for i, v in f) for f in fs]; m = max(sc); e = [math.exp(s - m) for s in sc]; z = sum(e)
        ll += math.log(e[c] / z)
        for j, f in enumerate(fs):
            p = e[j] / z - (1.0 if j == c else 0.0)
            if p:
                for i, v in f: gr[i] -= p * v
    return dict(gr), ll

def fit_logit(problems, l2=0.02, l2c=None, iters=80, lr=0.5, procs=4):
    global _P
    names = sorted({k for cs, _ in problems for f in cs for k in f}); ix = {k: i for i, k in enumerate(names)}
    _P = [([[(ix[k], v) for k, v in f.items()] for f in cs], c) for cs, c in problems if len(cs) > 1]
    reg = [(l2c if (l2c is not None and k.startswith("C:")) else l2) for k in names]
    w = [0.0] * len(names); G = [1e-8] * len(names)
    n = len(_P); step = max(1, (n + procs * 4 - 1) // (procs * 4)); spans = [(a, min(n, a + step)) for a in range(0, n, step)]
    with mp.get_context("fork").Pool(procs) as pool:
        for it in range(iters):
            grad = [-r * x for r, x in zip(reg, w)]
            for gr, _ in pool.map(_grad, [(a, b, w) for a, b in spans]):
                for i, v in gr.items(): grad[i] += v
            for i, g in enumerate(grad):
                G[i] += g * g; w[i] += lr * g / math.sqrt(G[i])
    _P = None
    return {names[i]: round(w[i], 4) for i in range(len(names)) if abs(w[i]) > 1e-4}

STAGES = (1, 2)
# Stage-1 features left out of the fit: the max over a group's moves of the v3 move features (Gmax:Step.vil_inv, ...) and the
# v3 context crossings. They fit the tuning games but made the late-game test worse (stage-1 ll -0.92 vs -0.83); only the
# EndTurn spending crossings (G:EndTurn*has:X*stars / *acted) are kept from the v3 stage-1 additions.
import re
S1_BAN = re.compile(r"Gmax:(Step|Attack|Train|Build|Rs)\.(vil_inv|ecity_inv|foe_inv|on_|ruin_inv|vil_gain|ecity_gain|foe_gain|unexplored@|threat|targets|rough|dist|crowd|city_left|hurt|ratio|tgt_|value|kill@|n_same|n_units|cheapest|cost|city_lvl|capital|adj|stars_left|tier)"
                    r"|\*(crazy|n_units|pop|income|city_threat|n_foe_near|afford_unit|stars_over_cheap|n_enemy_cities|n_villages|turn2)$")
def fit(recs, l2, l2c, iters):
    recs = [dict(r, groups={g: {k: v for k, v in f.items() if not S1_BAN.search(k)} for g, f in r["groups"].items()}) for r in recs]
    if STAGES == (1,):
        gp = [([r["groups"][g] for g in r["groups"]], list(r["groups"]).index(r["cg"])) for r in recs]
        return fit_logit(gp, l2, l2c, iters), {}
    gp = [([r["groups"][g] for g in r["groups"]], list(r["groups"]).index(r["cg"])) for r in recs]
    mp_ = [(r["cands"], r["ci"]) for r in recs]
    return fit_logit(gp, l2, l2c, iters), fit_logit(mp_, l2, l2c, iters)

# ---------- evaluation ----------
def evaluate(recs, W):
    """Like bot_policy2.evaluate, plus the per-kind (Hard/Crazy) split and stars/steps keys."""
    S = collections.defaultdict(collections.Counter)
    g1, w2 = W
    for r in recs:
        gs = list(r["groups"]); sc = [dot(g1, r["groups"][g]) for g in gs]; gi = gs.index(r["cg"])
        ls = logsoft(sc)[gi]; cs = [dot(w2, f) for f in r["cands"]]; ci = r["ci"]; lm = logsoft(cs)[ci]
        keys = [r["cg"], "ALL", "ALL:" + kind_of(r)]
        for key in keys:
            s = S[key]; s["n"] += 1
            s["s1_top1"] += rank_hit(sc, gi, 1); s["s1_top3"] += rank_hit(sc, gi, 3); s["s1_chance1"] += 1 / len(gs); s["s1_chance3"] += min(3, len(gs)) / len(gs)
            s["s2_top1"] += rank_hit(cs, ci, 1); s["s2_top3"] += rank_hit(cs, ci, 3); s["s2_chance1"] += 1 / len(cs); s["s2_chance3"] += min(3, len(cs)) / len(cs)
            s["joint_top1"] += rank_hit(sc, gi, 1) * rank_hit(cs, ci, 1)
            s["ll"] += ls + lm; s["ll1"] += ls; s["ll2"] += lm; s["ll_chance"] += -math.log(r["n"])
        if r["cg"] in ("Step", "Attack", "Summon"):
            same = [j for j, sr in enumerate(r["srcs"]) if sr == r["srcs"][ci]]
            sub = [cs[j] for j in same]; k = same.index(ci)
            for key in (r["cg"] + "|unit", r["cg"] + "|unit:" + kind_of(r)):
                s = S[key]; s["n"] += 1; s["s2_top1"] += rank_hit(sub, k, 1); s["s2_top3"] += rank_hit(sub, k, 3)
                s["s2_chance1"] += 1 / len(sub); s["s2_chance3"] += min(3, len(sub)) / len(sub)
    return S

def summary(S, title):
    rows = [title]
    for k in ["ALL", "ALL:Hard", "ALL:Crazy"]:
        s = S[k]; n = s["n"]
        if n: rows.append(f"  {k:<10} n={n:<6.0f} stage1 top1 {s['s1_top1']/n:.3f} ({s['s1_chance1']/n:.3f}) | stage2 top1 {s['s2_top1']/n:.3f} ({s['s2_chance1']/n:.3f}) top3 {s['s2_top3']/n:.3f} ({s['s2_chance3']/n:.3f}) | joint {s['joint_top1']/n:.3f} | ll {s['ll']/n:.2f} = s1 {s['ll1']/n:.2f} + s2 {s['ll2']/n:.2f} (rand {s['ll_chance']/n:.2f})")
    return "\n".join(rows)

def main():
    a = sys.argv[1:]; opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    if a[0] == "prep": prep(a[1], a[2]); return
    train, test = load(a[1])
    print(f"train {len(train)} decisions ({sum(r['crazy'] for r in train)} Crazy), test {len(test)} ({sum(r['crazy'] for r in test)} Crazy)")
    if a[0] == "eval":
        for p in opt("--w").split(","):
            pol = json.load(open(p)); W = (pol["g"], pol["w"])
            print(fmt(evaluate(train, W), f"== {p} TRAIN") if "--full" in a else summary(evaluate(train, W), f"== {p} TRAIN"))
            print(fmt(evaluate(test, W), f"== {p} TEST") if "--full" in a else summary(evaluate(test, W), f"== {p} TEST"))
        W0 = ({}, {}); print(summary(evaluate(train, W0), "== random TRAIN")); print(summary(evaluate(test, W0), "== random TEST"))
    elif a[0] == "fit":
        l2 = float(opt("--l2", 0.02)); l2c = None if "--nodiff" in a else float(opt("--l2c", 1.0)); iters = int(opt("--iters", 80))
        global STAGES
        if "--stage1" in a: STAGES = (1,)
        if "--ban" in a:   # drop features whose name matches the regex (ablation)
            import re
            rx = re.compile(opt("--ban"))
            for r in train:
                r["groups"] = {g: {k: v for k, v in f.items() if not rx.search(k)} for g, f in r["groups"].items()}
                r["cands"] = [{k: v for k, v in f.items() if not rx.search(k)} for f in r["cands"]]
        if "--nodiff" in a:   # pooled fit: drop the Crazy delta features
            for r in train:
                r["groups"] = {g: {k: v for k, v in f.items() if not k.startswith("C:")} for g, f in r["groups"].items()}
                r["cands"] = [{k: v for k, v in f.items() if not k.startswith("C:")} for f in r["cands"]]
        if "--cv" in a:
            games = sorted({r["game"] for r in train}); folds = [games[i::4] for i in range(4)]; cv = collections.defaultdict(collections.Counter)
            for fo in folds:
                W = fit([r for r in train if r["game"] not in fo], l2, l2c, iters)
                for k, s in evaluate([r for r in train if r["game"] in fo], W).items(): cv[k].update(s)
            print(summary(cv, f"== 4-fold CV by game (l2={l2}, l2c={l2c})"))
        W = fit(train, l2, l2c, iters)
        print(summary(evaluate(train, W), "== TRAIN in-sample")); print(summary(evaluate(test, W), "== TEST"))
        if opt("--out"):
            json.dump({"about": f"bot_policy3.py fit (l2={l2}, l2c={l2c}, iters={iters}); test = ed6cb932 + game 7 turns 12+", "g": W[0], "w": W[1]}, open(opt("--out"), "w"), indent=0); print("wrote", opt("--out"))

if __name__ == "__main__": main()
