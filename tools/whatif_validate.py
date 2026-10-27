"""Validation of the what-if tool (Phase 2): for every logged legal move in the real saves, the prediction the tool makes from
the mover's own view (fog-correct, src/whatif.rs) is compared with what the engine then does, and attack results are checked
against the next real save (kills: the unit is gone; survivors nobody touched afterwards: the HP in the save).
    python3 -I tools/whatif_validate.py [--fails] [--summary]
Prints WHATIF lines per move type for the tuned games and the held-out games (data/holdout.json). Takes about a minute."""
import collections, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pf_jobs as PJ
os.environ["PF_WHATIF"] = "1"

jobs, _ = PJ.jobs_for("", lambda g, t: True)
R = PJ.run(jobs)
S = {True: collections.defaultdict(lambda: [0] * 6), False: collections.defaultdict(lambda: [0] * 6)}
A = {True: collections.Counter(), False: collections.Counter()}
fails, errs = [], 0
for r in R:
    if "error" in r or not r.get("whatif"): errs += 1; continue
    gid, _, b = r["tag"].split("|"); h = PJ.held(gid, int(b)); w = r["whatif"]
    for k, v in w["stats"].items():
        for i in range(6): S[h][k][i] += v[i]
    A[h]["attacks"] += w["attacks"]
    for k, (n, ok) in (("kills", w["kills"]), ("attacker_deaths", w["attacker_deaths"]), ("survivor_hp", w["survivor_hp"])):
        A[h][k, 0] += n; A[h][k, 1] += ok
    A[h]["touched_later"] += w["touched_later"]
    fails += [dict(f, tag=r["tag"][:8] + "|" + r["tag"].split("|", 1)[1]) for f in w["fail"]] + [dict(b, tag=r["tag"][:8], real=True) for b in w["bad"]]

def table(h):
    rows = S[h]
    tot = [sum(v[i] for v in rows.values()) for i in range(6)]
    out = [f"{'held-out' if h else 'tuned'}: {tot[0]} logged moves; in the player's view list {tot[1]}; prediction = engine result {tot[2]}/{tot[1]}; "
           f"of those, moves into/over the fog {tot[5]}/{tot[4]}, moves with all tiles visible {tot[2] - tot[5]}/{tot[1] - tot[4]} (random-outcome moves {tot[3]}, checked as 'result is one of the predicted outcomes')"]
    for k in sorted(rows, key=lambda k: -rows[k][0]):
        v = rows[k]
        if v[0]: out.append(f"    {k:<14} moves {v[0]:>5}  in view {v[1]:>5}  exact {v[2]:>5}  ({100 * v[2] / max(v[1], 1):.1f}%); fog {v[5]}/{v[4]}; all visible {v[2] - v[5]}/{v[1] - v[4]}")
    return out

summary = "--summary" in sys.argv
for h in (False, True):
    for l in (table(h)[:1] if summary else table(h)): print("WHATIF", l)
    a = A[h]
    print(f"WHATIF   attacks vs the next real save ({'held-out' if h else 'tuned'}): {a['attacks']} predicted; kills confirmed (unit gone from the save) {a['kills', 1]}/{a['kills', 0]}; "
          f"attacker deaths confirmed {a['attacker_deaths', 1]}/{a['attacker_deaths', 0]}; surviving units nobody touched afterwards show the predicted HP {a['survivor_hp', 1]}/{a['survivor_hp', 0]} "
          f"({a['touched_later']} more were changed again later in the window: not checked)")
if errs: print("WHATIF jobs failed:", errs)
if "--fails" in sys.argv:
    for f in fails[:25]: print("  FAIL", json.dumps(f)[:600])
