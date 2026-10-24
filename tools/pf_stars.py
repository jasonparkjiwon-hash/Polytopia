"""Where Polyfish's stars drift from the economy model (engine/economy.py), split into income and spending by action kind.
Usage: python3 -I tools/pf_stars.py                       totals over every checkpoint pair (held-out games excluded)
       python3 -I tools/pf_stars.py <game> <turnA> [pl..]  one pair, one line per player that misses (or the listed players)
Income differences are split into the bot bonus (DifficultyHandicap - 1, economy.py) and the rest."""
import sys, os, json, glob, re, collections, subprocess, tempfile, struct
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "engine"))
import economy as EC
BIN = os.path.join(ROOT, "sim", "pfcore", "target", "release", "pfreplay")
HELD = {h["game"] for h in json.load(open(os.path.join(ROOT, "data", "holdout.json")))["held"]}
one = len(sys.argv) > 2; only = {int(x) for x in sys.argv[3:]}
games = collections.defaultdict(list)
for f in glob.glob(os.path.join(ROOT, "saves", (sys.argv[1] if one else "") + "*_t*.json")):
    if re.search(r"_t\d+\.json$", f): games[os.path.basename(f)[:36]].append(f)
jobs, pairs = [], {}
for gid, fs in games.items():
    if gid in HELD and not one: continue
    ds = sorted(((json.load(open(f)), f) for f in fs), key=lambda d: len(d[0]["actions"]))
    for (a, fa), (b, fb) in zip(ds, ds[1:]):
        if one and a["currentTurn"] != int(sys.argv[2]): continue
        tag = f"{gid}|{a['currentTurn']}"; pairs[tag] = (a, b, ds[-1][0]["actions"])
        jobs.append(dict(tag=tag, start=fa, final=ds[-1][1], **{"from": len(a["actions"]), "to": len(b["actions"])}))
with tempfile.TemporaryDirectory() as tmp:
    jf = os.path.join(tmp, "j.json"); json.dump(jobs, open(jf, "w"))
    out = subprocess.run([BIN, jf], capture_output=True, text=True, env=dict(os.environ, PF_TRACE="1")).stdout
def kind(x):
    k = x["name"]
    if x["type"] in (1, 5, 16): k += " " + str(struct.unpack("<BHII", bytes.fromhex(x["raw"]))[1])
    if x["type"] == 8: k += " " + str(struct.unpack("<BH", bytes.fromhex(x["raw"]))[1])
    return k
tot = collections.Counter(); causes = collections.Counter(); ex = {}
for line in out.splitlines():
    if not line.startswith("PFJSON "): continue
    r = json.loads(line[7:]); a, b, acts = pairs[r["tag"]]
    if "error" in r: print("error", r["tag"], r["error"]); continue
    pf_inc = collections.Counter(); pf_sp = collections.defaultdict(collections.Counter)
    for i, t, actor, dd in r["trace"]:
        for p, v in dd.items():
            p = int(p)
            if t == 15 or p != actor: pf_inc[p] += v
            else: pf_sp[p][kind(acts[i])] -= v
    rows = EC.check(a, b, acts); bk = EC.Books(a); ec_sp = collections.defaultdict(collections.Counter)
    for x in acts[len(a["actions"]):len(b["actions"])]:
        pl = bytes.fromhex(x["raw"])[0]; c = EC.spend(bk, pl, x); EC.book(bk, x)
        if c: ec_sp[pl][kind(x)] += c
    after = {p["PlayerId"]: p["Currency"] for p in b["currentPlayers"]}; b0 = EC.Books(a)
    for pl, row in sorted(rows.items()):
        if row["residual"] is None or not b0.cities(pl) or (only and pl not in only): continue
        off = after[pl] - r["stars"][str(pl)]; tot["player-turns"] += 1
        if off == 0 and not only: tot["exact"] += 1; continue
        bonus = max(0, b0.handicap.get(pl, 1) - 1) * row["turns"]
        di = row["income"] - pf_inc[pl]
        found = []
        if di == bonus and bonus: found.append("income: bot bonus missing")
        elif di: found.append(f"income: other ({'+' if di > 0 else ''}{di} vs econ, bonus {bonus})")
        for kk in set(pf_sp[pl]) | set(ec_sp[pl]):
            if pf_sp[pl][kk] != ec_sp[pl][kk]: found.append(f"spend {kk}: pf {pf_sp[pl][kk]} econ {ec_sp[pl][kk]}")
        if row["residual"]: found.append(f"econ itself off {row['residual']:+d}")
        if one: print(f"{r['tag']} p{pl} {b0.tribe.get(pl)} off {off:+d}: " + "; ".join(found)); continue
        for c in found:
            c2 = re.sub(r": pf -?\d+ econ -?\d+", "", c); c2 = re.sub(r"\(.*\)", "(...)", c2) if c2.startswith("income: other") else c2
            causes[c2] += 1; ex.setdefault(c2, f"{r['tag'][:8]} t{r['tag'].split('|')[1]} p{pl}")
if not one:
    print(f"stars exact {tot['exact']}/{tot['player-turns']}; causes (a miss can have several):")
    for c, n in causes.most_common(40): print(f"{n:5d} {c} | e.g. {ex[c]}")
