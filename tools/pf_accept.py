"""Forward-model acceptance suite for Polyfish (fm-accept; .scratchpad/investigations/fm-accept.md).
  python3 -I tools/pf_accept.py            all tests, forward-model checks at every 25th logged legal action
  python3 -I tools/pf_accept.py --full     the checks at every logged legal action (~5 min)
  python3 -I tools/pf_accept.py --fails    also print the first failing checks (state parts that differ)
Tests: (a) the logged move is in the generated list (legality, as pf_miss); (b) the state after playing it through the
API on a clone equals the replay's state (units/HP/stars/tiles/everything Polyfish holds; the referee comparison at
checkpoints is pf_miss --accept); (c) determinism: two clones playing the same move agree; (d) clone independence;
undo exact (and exact up to tile reveals); (e) speed on a mid-game save; (f) random events and Dice coverage;
(g) rule labels: moves played by kind -> ledger ids, below-L1 and unlabelled ones touched (data/pf_rule_levels.json).
Prints one 'FM ACCEPT' line per test (check.sh shows them; informational, never part of the baseline)."""
import sys, os, json, glob, re, collections, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pf_jobs as PJ
import pf_rule_levels as PR
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
API = os.path.join(ROOT, "sim", "pfcore", "target", "release", "pfapi")
if not os.path.exists(API): sys.exit("build Polyfish first: cd sim/pfcore && cargo build --release")
os.environ["PF_ACCEPT"] = "1" if "--full" in sys.argv else "25"

jobs, _ = PJ.jobs_for("", lambda g, t: True)
R = PJ.run(jobs)
A = {True: collections.Counter(), False: collections.Counter()}   # held-out? -> counts
legal = {True: [0, 0], False: [0, 0]}
kinds, fails, errs = collections.Counter(), [], 0
for r in R:
    if "error" in r: errs += 1; continue
    gid, _, b = r["tag"].split("|"); h = PJ.held(gid, int(b))
    for k, (p, n) in r["accept"].items(): A[h][k, 0] += p; A[h][k, 1] += n
    for p, n in r["legal"].values(): legal[h][0] += p; legal[h][1] += n
    kinds.update(r["kinds"]); fails += [dict(f, tag=r["tag"]) for f in r["accept_fail"]]

def frac(k):
    t = A[False] + A[True]; return f"{t[k, 0]}/{t[k, 1]}"
pct = lambda x: f"{100 * x[0] / max(x[1], 1):.1f}%"
print(f"FM ACCEPT (a) logged move in the generated list: tuned {legal[False][0]}/{legal[False][1]} = {pct(legal[False])}, "
      f"held-out {legal[True][0]}/{legal[True][1]} = {pct(legal[True])}" + (f"; {errs} jobs failed to load" if errs else ""))
print(f"FM ACCEPT (b) API move on a clone = replay state: {frac('same_as_replay')}; listed with a label: {frac('listed')}; "
      f"applies: {frac('applies')} (checks at every {os.environ['PF_ACCEPT']}th legal action; referee checkpoints: PF ACCEPT line)")
print(f"FM ACCEPT (c) deterministic: {frac('deterministic')} | (d) clone independent: {frac('clone_independent')} | "
      f"undo exact: {frac('undo_exact')}, exact but tile reveals: {frac('undo_exact_but_reveals')}")

# (e) speed: the middle checkpoint of the game with the most checkpoints, the tribe with the most units to move
by = collections.defaultdict(list)
for p in glob.glob(os.path.join(ROOT, "saves", "*_t*.json")):
    m = re.match(r"(.+)_t(\d+)\.json$", os.path.basename(p)); by[m.group(1)].append((int(m.group(2)), p))
g = max(by, key=lambda k: len(by[k])); turns = sorted(by[g]); save = turns[len(turns) // 2][1]
b = json.loads(subprocess.run([API, "bench", save, "0", "4"], capture_output=True, text=True).stdout or "{}")
if b:
    print(f"FM ACCEPT (e) speed ({g[:8]} t{b['turn']}, {b['tribes']} tribes, {b['units']} units, player {b['player']} with {b['legal_now']} moves): "
          f"movegen {b['movegen_per_s']:.0f}/s ({b['moves_listed_per_s']:.0f} moves listed/s), apply+undo {b['apply_undo_per_s']:.0f}/s, "
          f"clone {b['clone_per_s']:.0f}/s, random playout {b['playout_player_turns_per_s']} player-turns/s = {b['playout_rounds_per_s']} rounds/s")

# (f) random events
d = json.loads(subprocess.run([API, "dice", os.path.join(ROOT, "data", "distributions.json"), save, "1", "20000"], capture_output=True, text=True).stdout or "{}")
if d:
    ev = d["events"]; dice = [e for e in ev if e["covered"].startswith("Dice")]; rolled = [e for e in ev if e["covered"] not in ("-",) and "choice" not in e["where"]]
    rr = d["ruin"]
    print(f"FM ACCEPT (f) random events Polyfish rolls: {len(rolled)}; sampled from distributions.json: {len(dice)} ({', '.join(e['event'] for e in dice)}); "
          f"not covered: {', '.join(e['event'] for e in rolled if e not in dice)}; ruin sampling vs table TVD land {rr['land']['tvd']} "
          f"water {rr['water']['tvd']}; each reward executes: land {rr['land']['rewards_executed']}/{rr['land']['rewards']}, water {rr['water']['rewards_executed']}/{rr['water']['rewards']}")

# (g) rule labels touched by the replayed moves
L, errors = PR.build()
touched = {k: L["kinds"].get(k) for k in kinds}
unknown = sorted(k for k, v in touched.items() if v is None)
below = sorted({r["ledger"] for v in touched.values() if v for r in v if r["below_L1"]})
up = sorted(k for k, v in touched.items() if v and any(r["ledger"] == "UPSTREAM" for r in v))
flags = [k for k in os.environ.get("PF_FLAGS", "").split(",") if k]
print(f"FM ACCEPT (g) rules: {sum(kinds.values())} moves in {len(kinds)} kinds, all mapped: {'yes' if not unknown else 'no, ' + ', '.join(unknown)}; "
      f"below-L1 rules touched: {', '.join(below + [f'{k} (switch)' for k in flags]) or 'none'}; kinds with unlabelled upstream logic touched: "
      f"{', '.join(f'{k} {kinds[k]}' for k in up)}; label errors: {len(errors)}")
if "--fails" in sys.argv:
    for f in fails[:20]: print("  fail", f)
