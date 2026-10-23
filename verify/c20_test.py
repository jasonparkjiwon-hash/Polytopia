"""C20 test: does a defender retaliate against an attacker on a tile its tribe has never explored?
Per-turn replay over every game with consecutive saves, with and without 'no retaliation when unseen'.
'Unseen' = the attacker's tile is unexplored by the defender's tribe in the LATER save (exploration only grows)."""
import sys, json, collections, glob, os, re
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, "..", "engine"))
import replay as R
from state import State
games = collections.defaultdict(list)
for f in glob.glob(os.path.join(HERE, "..", "saves", "*_t*.json")):
    if re.search(r"_t\d+\.json$", f): games[os.path.basename(f)[:36]].append(f)
orig_fight = R.fight
def run(rule):
    tot = collections.Counter(); cases = []
    for gid, fs in sorted(games.items()):
        ds = sorted((json.load(open(f)) for f in fs), key=lambda d: len(d["actions"])); acts = ds[-1]["actions"]
        for a, b in zip(ds, ds[1:]):
            vis = {}
            for y, row in enumerate(b["currentTiles"]):
                for x, t in enumerate(row):
                    for p in t["PlayerVisibility"]: vis.setdefault(p, set()).add((x, y))
            def fight(st, at, df):
                dmg, ret, bonus = orig_fight(st, at, df)
                unseen = (at.x, at.y) not in vis.get(df.owner, set())
                if unseen and ret: cases.append((gid[:8], a["currentTurn"], at.id, at.type, df.type))
                return dmg, (0 if rule and unseen else ret), bonus
            R.fight = fight
            st = State(a, "current"); R.PREV[0] = None; turn = a["currentTurn"]
            for i in range(len(a["actions"]), len(b["actions"])):
                x = acts[i]
                if x["type"] == 15 and bytes.fromhex(x["raw"])[0] == 255: turn += 1
                R.apply(st, x, turn)
            res, bad = R.compare(st, b); tot.update(res)
    R.fight = orig_fight
    return tot, cases
for rule in (False, True):
    tot, cases = run(rule)
    print(f"{'no retaliation when unseen' if rule else 'always retaliate (current)':30s} exact {tot['HP exact']}  HP differs {tot['HP differs']}  | attacks from unexplored tiles that would get retaliation: {len(cases)}")
print("examples:", cases[:8])
