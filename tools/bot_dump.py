"""Dump every logged action's legal-move features (sim/pfcore src/botpolicy2.rs) for bot-policy fitting.
Usage: python3 -I tools/bot_dump.py OUT.jsonl [--game PREFIX] [--holdout]   (default: all tuning games; --holdout: ed6cb932 only)
One JSON line per logged action of any player: {tag, i, t, p, tr, bot, c, m: [[group, [[feature, value]...]]...]}. Needs the pfreplay build."""
import os, sys
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "tools"))
import pf_jobs as PJ
out = sys.argv[1]
want = sys.argv[sys.argv.index("--game") + 1] if "--game" in sys.argv else ""
hold = "--holdout" in sys.argv
if os.path.exists(out): os.remove(out)
os.environ["PF_BOTDUMP"] = out
jobs, _ = PJ.jobs_for(want, lambda gid, turn: PJ.held(gid, turn) == hold)
res = PJ.run(jobs)
print(len(jobs), "jobs,", sum(1 for r in res if "error" in r), "errors ->", out)
