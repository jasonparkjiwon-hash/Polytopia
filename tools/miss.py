"""Compact replay report over every game with consecutive per-turn saves.
Usage: python3 -I tools/miss.py [--list] [--game <id prefix>]
Prints exact/missed unit and star counts per game. --list adds one line per miss. Never print save JSON; use tools/trace.py for one spot."""
import sys, os, json, glob, re, collections
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "engine"))
import replay as R, economy as EC
from state import State
want = sys.argv[sys.argv.index("--game") + 1] if "--game" in sys.argv else ""
games = collections.defaultdict(list)
for f in glob.glob(os.path.join(ROOT, "saves", want + "*_t*.json")):
    if re.search(r"_t\d+\.json$", f): games[os.path.basename(f)[:36]].append(f)
tu = collections.Counter(); ts = collections.Counter(); lines = []
for gid, fs in sorted(games.items()):
    ds = sorted((json.load(open(f)) for f in fs), key=lambda d: len(d["actions"])); acts = ds[-1]["actions"]
    R.ORACLE.clear(); R.RUIN.clear()
    for d in ds:
        R.add_ruin_oracle(d)
        for i, v in R.snapshot_units(d).items(): R.ORACLE.setdefault(i, (v[0], v[1], v[5]))
    u = collections.Counter(); s = collections.Counter()
    for a, b in zip(ds, ds[1:]):
        st = State(a, "current"); R.PREV[0] = None; turn = a["currentTurn"]
        for i in range(len(a["actions"]), len(b["actions"])):
            x = acts[i]
            if x["type"] == 15 and bytes.fromhex(x["raw"])[0] == 255: turn += 1
            R.apply(st, x, turn)
        res, bad = R.compare(st, b); u.update(res)
        lines += [f"{gid[:8]} t{a['currentTurn']}->{b['currentTurn']} unit {z[0]} id{z[1]} {z[2:]}" for z in bad]
        for pl, r in EC.check(a, b, acts).items():
            if r["residual"] is None or not EC.Books(a).cities(pl): continue
            s["players"] += 1
            if r["residual"] == 0 and not r["unknown"]: s["exact"] += 1
            else: lines.append(f"{gid[:8]} t{a['currentTurn']}->{b['currentTurn']} stars p{pl} off {r['residual']:+d}")
    miss = sum(v for k, v in u.items() if k != "HP exact")
    print(f"{gid[:8]} units exact {u['HP exact']}/{u['HP exact'] + miss} | stars exact {s['exact']}/{s['players']}")
    tu.update(u); ts.update(s)
miss = sum(v for k, v in tu.items() if k != "HP exact")
print(f"TOTAL units exact {tu['HP exact']}/{tu['HP exact'] + miss} | stars exact {ts['exact']}/{ts['players']}")
if "--list" in sys.argv: print("\n".join(lines))
