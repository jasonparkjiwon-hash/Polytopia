"""Hypothesis search: A/B many rule variants against the whole replay at once.
A variant is a label plus overrides of engine/replay.RULES and engine/economy.ECON_RULES (env POLY_RULES / POLY_ECON, read at import).
Each variant runs `tools/miss.py` (tuned games) and `tools/miss.py --holdout`, in parallel; the report shows units/stars exact per variant,
the change against the baseline, and PER GAME deltas (leave-one-game-out: a variant that helps one game and hurts another is flagged).
Usage: python3 -I tools/rule_search.py <variants file> [--jobs N]
Variants file, one per line (blank lines and # comments ignored):
    label | {"mycelium_heal": 4, "mycelium_radius": 1}                    RULES overrides
    label | {"mycelium_heal": 4} | {"some_econ_rule": true}               RULES and ECON_RULES overrides
A variant is KEEPABLE when units+stars improve (or hold with fewer misses), no game gets worse, and the held-out games hold.
Never prints save JSON."""
import sys, os, json, subprocess, re, concurrent.futures
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
MISS = os.path.join(ROOT, "tools", "miss.py")

def run(rules, econ, extra):
    env = dict(os.environ, POLY_RULES=json.dumps(rules), POLY_ECON=json.dumps(econ))
    out = subprocess.run([sys.executable, "-I", MISS] + extra, capture_output=True, text=True, env=env, cwd=ROOT).stdout
    res = {}
    for m in re.finditer(r"^(\S+) units exact (\d+)/(\d+) \| stars exact (\d+)/(\d+)", out, re.M):
        if m.group(1) != "TOTAL": res[m.group(1)] = (int(m.group(3)) - int(m.group(2)), int(m.group(5)) - int(m.group(4)))   # misses: units, stars
    return res

def score(label, rules, econ):
    return label, run(rules, econ, []), run(rules, econ, ["--holdout"])

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--") and not a.isdigit()]
    jobs = int(sys.argv[sys.argv.index("--jobs") + 1]) if "--jobs" in sys.argv else 4
    variants = [("baseline", {}, {})]
    for ln in open(args[0]):
        ln = ln.strip()
        if not ln or ln.startswith("#"): continue
        parts = [p.strip() for p in ln.split("|")]
        variants.append((parts[0], json.loads(parts[1]) if len(parts) > 1 and parts[1] else {}, json.loads(parts[2]) if len(parts) > 2 and parts[2] else {}))
    with concurrent.futures.ThreadPoolExecutor(jobs) as ex:
        results = list(ex.map(lambda v: score(*v), variants))
    base = results[0]
    tot = lambda r: (sum(v[0] for v in r.values()), sum(v[1] for v in r.values()))
    bu, bs = tot(base[1]); hu, hs = tot(base[2])
    print(f"baseline misses: units {bu}, stars {bs} (tuned); held-out units {hu}, stars {hs}")
    print(f"{'variant':<34}{'units':>6}{'stars':>6}   per-game change (misses; - is better)                 verdict")
    for label, tuned, held in results[1:]:
        du, ds = tot(tuned)[0] - bu, tot(tuned)[1] - bs
        pg = {g: (tuned[g][0] - base[1][g][0], tuned[g][1] - base[1][g][1]) for g in tuned if g in base[1] and tuned[g] != base[1][g]}
        hh = tot(held); worse = [g for g, (a, b) in pg.items() if a > 0 or b > 0]; hworse = hh[0] > hu or hh[1] > hs
        keep = (du + ds < 0 or (du + ds == 0 and False)) and not worse and not hworse
        mixed = [g for g, (a, b) in pg.items() if a < 0 or b < 0]
        verdict = "KEEPABLE" if keep else ("MIXED" if mixed and worse else ("held-out worse" if hworse else ("no change" if not pg else "worse")))
        print(f"{label:<34}{du:>+6}{ds:>+6}   {', '.join(f'{g[:8]} {a:+d}/{b:+d}' for g, (a, b) in pg.items())[:70]:<70} {verdict}")
    if not results[1:]: print("no variants")

main()
