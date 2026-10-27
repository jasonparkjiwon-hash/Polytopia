"""Bot move model (Phase 6 groundwork, bot-policy-2): how well does a policy that ranks Polyfish's legal moves predict what the
built-in bots actually did? Input: decision dumps from tools/bot_dump.py (every legal move's features at each logged action,
written by sim/pfcore/src/botpolicy2.rs). Pure stdlib.

Two stages, same as sim/pfcore/src/botpolicy2.rs: (1) which GROUP of move comes next (Step, Attack, Summon = train, Research, ...;
softmax over the groups present, features = `group_feats`), (2) which move inside the group (softmax over its moves, features =
the move's own sparse features). Weights files: {"g": {...stage 1...}, "w": {...stage 2...}}.

  python3 -I tools/bot_policy2.py eval TRAIN.jsonl HOLD.jsonl [--v1 data/bot_policy_v1.json] [--v2 data/bot_policy_v2.json]
  python3 -I tools/bot_policy2.py fit TRAIN.jsonl HOLD.jsonl [--out data/bot_policy_v2.json] [--l2 0.02] [--iters 80]
  python3 -I tools/bot_policy2.py v1                      writes the hand-set rules to data/bot_policy_v1.json

Reported (bot decisions whose logged move Polyfish listed; chance = random legal move): stage-1 and stage-2 top-1/top-3 per
group, the policy's own deterministic hit rate (both stages right), and mean log-likelihood of the logged move."""
import sys, os, json, math, collections, random
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

def bucket(t): return 0 if t < 5 else 1 if t < 10 else 2 if t < 20 else 3

def group_feats(x, g, turn, members, present):
    """Mirror of botpolicy::group_feats; members = list of {name: value}."""
    f = {f"G:{g}": 1.0, f"G:{g}@b{bucket(turn)}": 1.0, f"G:{g}.n": math.log(1 + len(members))}
    for c, v in x.items(): f[f"G:{g}*{c}"] = v
    for h in present:
        if h != g: f[f"G:{g}*has:{h}"] = 1.0
    mx = {}
    for m in members:
        for k, v in m.items():
            if "." in k and ":" not in k and v > mx.get(k, -1e9): mx[k] = v
    for k, v in mx.items(): f["Gmax:" + k] = v
    return f

def load(path):
    """One record per bot decision with a matched logged move: game, turn, tribe, per-group stage-1 features, chosen group, that
    group's candidate move features, the chosen index in it, and the total number of legal moves."""
    out = []
    for line in open(path):
        d = json.loads(line)
        if not d["bot"] or d["c"] < 0: continue
        by = collections.defaultdict(list)
        srcs = collections.defaultdict(list)
        for m in d["m"]: by[m[0]].append(dict(m[1])); srcs[m[0]].append(m[2])
        cg = d["m"][d["c"]][0]
        ci = sum(1 for m in d["m"][:d["c"]] if m[0] == cg)
        x = dict(d["x"])
        out.append(dict(game=d["tag"].split("|")[0][:8], turn=d["t"], tribe=d["tr"], n=len(d["m"]),
                        groups={g: group_feats(x, g, d["t"], ms, list(by)) for g, ms in by.items()}, cg=cg, cands=by[cg], ci=ci, srcs=srcs[cg]))
    return out

# ---------- scoring ----------
def dot(w, f): return sum(w.get(k, 0.0) * v for k, v in f.items())

def logsoft(scores):
    m = max(scores); z = math.log(sum(math.exp(s - m) for s in scores)) + m
    return [s - z for s in scores]

def rank_hit(scores, i, k):
    """P(the logged item is in the top k) when ties are broken uniformly at random (so all-zero weights = random)."""
    s = scores[i]; better = sum(1 for v in scores if v > s + 1e-9); eq = sum(1 for v in scores if abs(v - s) <= 1e-9)
    return max(0.0, min(1.0, (k - better) / eq))

def evaluate(recs, W):
    """W = (stage-1 weights, stage-2 weights). Returns per-group tallies and totals."""
    g1, w2 = W
    S = collections.defaultdict(lambda: collections.Counter())
    for r in recs:
        gs = list(r["groups"]); sc = [dot(g1, r["groups"][g]) for g in gs]; gi = gs.index(r["cg"])
        ls = logsoft(sc)[gi]
        cs = [dot(w2, f) for f in r["cands"]]; ci = r["ci"]
        lm = logsoft(cs)[ci]
        for key in (r["cg"], "ALL"):
            s = S[key]; s["n"] += 1
            s["s1_top1"] += rank_hit(sc, gi, 1); s["s1_top3"] += rank_hit(sc, gi, 3); s["s1_chance1"] += 1 / len(gs); s["s1_chance3"] += min(3, len(gs)) / len(gs)
            s["s2_top1"] += rank_hit(cs, ci, 1); s["s2_top3"] += rank_hit(cs, ci, 3); s["s2_chance1"] += 1 / len(cs); s["s2_chance3"] += min(3, len(cs)) / len(cs)
            s["joint_top1"] += rank_hit(sc, gi, 1) * rank_hit(cs, ci, 1)
            s["ll"] += ls + lm; s["ll_chance"] += -math.log(r["n"])
            s["s2_n_multi"] += len(cs) > 1
        if r["cg"] in ("Step", "Attack", "Summon"):   # same unit (city for Summon) as the logged move: which destination / target / unit type
            same = [j for j, sr in enumerate(r["srcs"]) if sr == r["srcs"][ci]]
            sub = [cs[j] for j in same]; k = same.index(ci); s = S[r["cg"] + "|unit"]
            s["n"] += 1; s["s2_top1"] += rank_hit(sub, k, 1); s["s2_top3"] += rank_hit(sub, k, 3)
            s["s2_chance1"] += 1 / len(sub); s["s2_chance3"] += min(3, len(sub)) / len(sub)
    return S

def fmt(S, title, min_n=15):
    rows = [f"{title}", f"  {'group':<14}{'n':>6}  {'stage1 top1 (chance)':>22}  {'stage2 top1 (chance)':>22}  {'stage2 top3 (chance)':>22}  {'both':>6}  {'ll/dec (random)':>16}"]
    keys = ["ALL"] + [k for k, _ in sorted(((k, v["n"]) for k, v in S.items() if k != "ALL"), key=lambda kv: (("|" in kv[0]), -kv[1])) if S[k]["n"] >= min_n]
    for k in keys:
        s = S[k]; n = s["n"]
        if "|" in k:
            rows.append(f"  {k:<14}{n:>6.0f}  {'-':>22}  {s['s2_top1']/n:>10.3f} ({s['s2_chance1']/n:.3f})    {s['s2_top3']/n:>10.3f} ({s['s2_chance3']/n:.3f})"); continue
        rows.append(f"  {k:<14}{n:>6.0f}  {s['s1_top1']/n:>10.3f} ({s['s1_chance1']/n:.3f})    {s['s2_top1']/n:>10.3f} ({s['s2_chance1']/n:.3f})    {s['s2_top3']/n:>10.3f} ({s['s2_chance3']/n:.3f})  {s['joint_top1']/n:>6.3f}  {s['ll']/n:>8.2f} ({s['ll_chance']/n:.2f})")
    return "\n".join(rows)

# ---------- fitting: conditional logit by Adagrad ----------
def fit_logit(problems, l2=0.02, iters=80, lr=0.5, init=None):
    """problems: list of (list of feature-dicts, chosen index). Maximises the sum of log-softmax at the chosen item - l2*|w|^2/2."""
    names = sorted({k for cs, _ in problems for f in cs for k in f}); ix = {k: i for i, k in enumerate(names)}
    P = [([[(ix[k], v) for k, v in f.items()] for f in cs], c) for cs, c in problems if len(cs) > 1]
    w = [0.0] * len(names); G = [1e-8] * len(names)
    if init:
        for k, v in init.items():
            if k in ix: w[ix[k]] = v
    for it in range(iters):
        grad = [-l2 * x for x in w]
        for fs, c in P:
            sc = [sum(w[i] * v for i, v in f) for f in fs]; m = max(sc); e = [math.exp(s - m) for s in sc]; z = sum(e)
            for j, f in enumerate(fs):
                p = e[j] / z - (1.0 if j == c else 0.0)
                if p:
                    for i, v in f: grad[i] -= p * v
        for i, g in enumerate(grad):
            G[i] += g * g; w[i] += lr * g / math.sqrt(G[i])
    return {names[i]: round(w[i], 4) for i in range(len(names)) if abs(w[i]) > 1e-4}

def fit(recs, l2, iters):
    gp = [([r["groups"][g] for g in r["groups"]], list(r["groups"]).index(r["cg"])) for r in recs]
    mp = [(r["cands"], r["ci"]) for r in recs]
    return fit_logit(gp, l2, iters), fit_logit(mp, l2, iters)

# ---------- v1: hand-set rules ----------
def v1():
    """Interpretable rules from data/bot_rules.json (BOT-ATTACK-DECISION/-TARGET, BOT-RESEARCH-OPENER) and the observed turn
    shape (units move and fight first, then economy, then EndTurn). Hand-set, not fitted."""
    g = {
        # which kind of move next: units first, economy after most units have acted, EndTurn last
        "G:Capture": 4.0, "G:Reward": 6.0,
        "G:Attack": 1.5, "Gmax:Attack.kill": 2.0, "G:Attack*frac_acted": 1.0,
        "G:Step": 2.0, "G:Step*frac_acted": -3.0,
        "G:Summon": -1.0, "G:Summon*frac_acted": 3.0, "G:Build": -1.0, "G:Build*frac_acted": 2.5,
        "G:Harvest": -0.5, "G:Harvest*frac_acted": 2.0, "G:Research": -1.0, "G:Research*frac_acted": 2.5,
        "G:Upgrade": -1.0, "G:Upgrade*frac_acted": 2.5, "G:Recover": 0.0, "G:Recover*frac_acted": 0.5,
        "G:EndTurn": -2.0, "G:EndTurn*frac_acted": 4.0, "Gmax:EndTurn.units_left": -0.4,
    }
    w = {
        # attack target order: a kill, then least return damage, then most expensive; Defenders and units in a city hold back
        "Attack.kill": 3.0, "Attack.nokill_ret": -2.0, "Attack.tgt_cost": 0.5, "Attack.self_dies": -2.0,
        # expansion: toward free villages, then enemy cities and foes; wounded units do not close in
        "Step.village_gain": 0.8, "Step.enemycity_gain": 0.3, "Step.foe_gain": 0.3, "Step.hurt_x_foe_gain": -1.5, "Step.leaves_city": 0.0,
        # training: Warrior-heavy early, mixed later (counts from data/bot_turns.csv)
        "Summon:Warrior": 1.0, "Summon:Warrior@b0": 1.0, "Summon:Warrior@b1": 0.6, "Summon:Defender": -0.3, "Summon:Rider": -0.5,
        "Summon:Swordsman": -0.3, "Summon:Archer": -0.3, "Summon:Warrior@b3": -0.7, "Summon:Defender@b3": 0.4, "Summon:Swordsman@b3": 0.4,
        # research opener (BOT-RESEARCH-OPENER): water by the capital -> Fishing; metal -> Mining; fruit -> Organization; game -> Hunting
        "Rs:Fishing*water": 3.0, "Rs:Mining*metal": 3.0, "Rs:Organization*fruit": 2.0, "Rs:Hunting*game": 2.0, "Rs:Climbing*metal": 1.0,
        "Rs:Riding*early": 0.5,
    }
    return {"about": v1.__doc__.replace("\n", " "), "g": g, "w": w}

def main():
    a = sys.argv[1:]
    opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    if a[0] == "v1":
        json.dump(v1(), open(os.path.join(ROOT, "data", "bot_policy_v1.json"), "w"), indent=1); print("wrote data/bot_policy_v1.json"); return
    train, hold = load(a[1]), load(a[2])
    if "--maxturn" in a:
        mt = int(opt("--maxturn")); train = [r for r in train if r["turn"] <= mt]; hold = [r for r in hold if r["turn"] <= mt]
    print(f"bot decisions with the logged move in Polyfish's list: tuned games {len(train)}, held-out {len(hold)}")
    if a[0] == "eval":
        for name, path in (("v1", opt("--v1")), ("v2", opt("--v2"))):
            if not path: continue
            p = json.load(open(path)); W = (p["g"], p["w"])
            print(fmt(evaluate(train, W), f"== {name} tuned games")); print(fmt(evaluate(hold, W), f"== {name} held-out"))
        print(fmt(evaluate(train, ({}, {})), "== random baseline (all-zero weights) tuned games")); print(fmt(evaluate(hold, ({}, {})), "== random baseline held-out"))
    elif a[0] == "fit":
        l2 = float(opt("--l2", 0.02)); iters = int(opt("--iters", 80))
        games = sorted({r["game"] for r in train}); folds = [games[i::4] for i in range(4)]   # 4-fold CV by game
        cv = collections.defaultdict(collections.Counter)
        for fo in ([] if "--nocv" in a else folds):
            tr = [r for r in train if r["game"] not in fo]; te = [r for r in train if r["game"] in fo]
            W = fit(tr, l2, iters)
            for k, s in evaluate(te, W).items(): cv[k].update(s)
        if cv: print(fmt(cv, "== v2 tuned games, 4-fold cross-validation by game (honest in-distribution estimate)"))
        W = fit(train, l2, iters)
        print(fmt(evaluate(train, W), "== v2 tuned games (in-sample)")); print(fmt(evaluate(hold, W), "== v2 held-out"))
        out = opt("--out")
        if out: json.dump({"about": f"bot_policy.py fit on tuned games (l2={l2}, iters={iters})", "g": W[0], "w": W[1]}, open(out, "w"), indent=0); print("wrote", out)

if __name__ == "__main__": main()
