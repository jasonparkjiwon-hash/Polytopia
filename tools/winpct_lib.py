"""Shared by tools/winpct.py (the CLI) and tools/winpct_eval.py (calibration): run the pfwin playout bin, real-save states, standings.
Pure stdlib. pfwin plays bot policy v2 for every tribe from a save (Game::search_move, seeded) and returns per-tribe feature vectors
(order = FEATS) at the start of each round h = 1..H. See .scratchpad/investigations/win-pct.md."""
import os, sys, json, glob, re, subprocess, tempfile, math, concurrent.futures as cf

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
BIN = os.environ.get("PFWIN_BIN") or os.path.join(ROOT, "sim", "pfcore", "target", "release", "pfwin")
POLICY = os.path.join(ROOT, "data", "bot_policy_v2.json")
BANK = os.path.join(ROOT, "data", "win_bank.json")        # tribe profiles for belief mode (tools/winpct_unseen.py bank)
BELIEF = os.path.join(ROOT, "data", "belief_model.json")
FEATS = ["alive", "cities", "pop", "level", "units", "unit_cost", "unit_hp_cost", "stars", "income", "techs", "kills", "casualties", "score", "connected", "threat", "pressure", "water"]
FI = {n: i for i, n in enumerate(FEATS)}

def _run_chunk(jobs, policy):
    with tempfile.TemporaryDirectory() as tmp:
        jf = os.path.join(tmp, "jobs.json"); json.dump(jobs, open(jf, "w"))
        out = subprocess.run([BIN, policy, BELIEF, jf] + ([BANK] if os.path.exists(BANK) else []), capture_output=True, text=True, cwd=ROOT).stdout
    return [json.loads(l[6:]) for l in out.splitlines() if l.startswith("PFWIN ")]

def run(jobs, procs=4, policy=POLICY):
    """Run pfwin jobs (dicts, see sim/pfcore/src/bin/pfwin.rs) on `procs` processes; results in job order."""
    if not jobs: return []
    chunks = [jobs[i::procs] for i in range(min(procs, len(jobs)))]
    with cf.ThreadPoolExecutor(len(chunks)) as ex:
        res = list(ex.map(lambda c: _run_chunk(c, policy), chunks))
    by_tag = {r["tag"]: r for c in res for r in c}
    return [by_tag.get(j["tag"], {"tag": j["tag"], "error": "no output"}) for j in jobs]

def current_player(acts, i):
    """Player to move after the first i logged actions (as tools/bot_dist.py)."""
    for a in acts[i:]:
        raw = bytes.fromhex(a["raw"])
        if raw[0] != 255 and a["type"] != 20: return raw[0]
    return 1

def save_info(path):
    """(player to move, turn) of a decoded save. Reads the save (and, for the player, the log in the same file)."""
    d = json.load(open(path))
    return current_player(d["actions"], len(d["actions"])), d["currentTurn"]

def alive(f): return f[FI["alive"]] > 0.5

# ---- standings: who "wins" at a state --------------------------------------------------------------------------------------
LABELS = ("score", "cities", "survive")

def leader_share(feats, label):
    """feats: {id: vector}. Returns {id: share} summing to 1 over the alive tribes: 1/k for each of the k tied leaders.
    label 'score': the game's own score (what ends a score-limited game); 'cities': city count, then units' value as tie-break."""
    live = {t: f for t, f in feats.items() if alive(f)}
    if not live: return {t: 0.0 for t in feats}
    key = (lambda f: f[FI["score"]]) if label == "score" else (lambda f: (f[FI["cities"]], round(f[FI["unit_hp_cost"]], 3)))
    best = max(key(f) for f in live.values())
    lead = [t for t, f in live.items() if key(f) == best]
    return {t: (1.0 / len(lead) if t in lead else 0.0) for t in feats}

def brier(pairs):
    """pairs: (p, y); mean squared error."""
    return sum((p - y) ** 2 for p, y in pairs) / max(1, len(pairs))

def reliability(pairs, edges=(0, .02, .05, .1, .2, .35, .5, .75, 1.0001)):
    rows = []
    for lo, hi in zip(edges, edges[1:]):
        b = [(p, y) for p, y in pairs if lo <= p < hi]
        if b: rows.append((lo, min(hi, 1.0), len(b), sum(p for p, _ in b) / len(b), sum(y for _, y in b) / len(b)))
    return rows

def wilson(k, n, z=1.96):
    """Wilson interval for k successes in n (k may be fractional)."""
    if n <= 0: return 0.0, 1.0
    p = k / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)

# ---- static evaluation (conditional logit over the alive tribes) --------------------------------------------------------------
PHI = ["cities", "level", "unit_hp_cost", "stars", "income", "techs", "kills", "score"]
SCALE = {"cities": 1, "level": 0.5, "unit_hp_cost": 0.1, "stars": 0.1, "income": 0.2, "techs": 0.2, "kills": 0.5, "score": 0.001}

def phi(f, names=PHI): return [f[FI[n]] * SCALE[n] for n in names]

def softmax_probs(w, feats, names=PHI):
    """{tribe: probability}: softmax of w.phi over the alive tribes (dead ones get 0)."""
    live = [t for t, f in feats.items() if alive(f)]
    if not live: return {t: 0.0 for t in feats}
    z = {t: sum(a * b for a, b in zip(w, phi(feats[t], names))) for t in live}
    m = max(z.values()); e = {t: math.exp(v - m) for t, v in z.items()}; s = sum(e.values())
    return {t: (e[t] / s if t in e else 0.0) for t in feats}

