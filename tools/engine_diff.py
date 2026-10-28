"""Differential test of the two engines: the Python referee (engine/replay.py) and Polyfish (sim/pfcore, bin pfreplay) are
run on the same checkpoint pair (same start save, same logged actions) and compared with each other AND with the next real save.
Every unit row and every player's stars lands in one of five classes:
  both-right     both engines equal the save
  ref-only       the referee is right, Polyfish wrong  -> bug in Polyfish
  pf-only        Polyfish is right, the referee wrong  -> bug in the referee
  both-same      both wrong in the same way            -> a rule missing from both
  both-differ    both wrong, differently               -> missing rule plus a bug
Usage: python3 -I tools/engine_diff.py [--game <prefix>] [--turns] [--pickle <file>]   (every game, held-out ones included, marked)
  --turns   list each non-both-right row (one line each)     --pickle  also write the rows (for tools/residual.py)
Stars: ref/pf are "off" values (0 = exact). Needs the Polyfish bin: cd sim/pfcore && cargo build --release. Never prints save JSON."""
import sys, os, json, collections
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "engine")); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import replay as R, economy as EC
from state import State
import pf_jobs as PJ
BOATS = {39, 40, 41, 42, 43, 44, 45}
want = sys.argv[sys.argv.index("--game") + 1] if "--game" in sys.argv else ""

def snap(d):
    o = {}
    for y, row in enumerate(d["currentTiles"]):
        for x, t in enumerate(row):
            u = t.get("Unit")
            if u: o[u["Id"]] = (u["Owner"], u["UnitType"], x, y, round(u["Health"] / 10, 3))
    return o

def pair_temp(mine, truth):                      # temp (negative) ids pair with the saved unit on the same tile, like both scorers
    for tid in [i for i in mine if i < 0]:
        m = mine[tid]
        for i, sv in truth.items():
            if (sv[0], sv[2], sv[3]) == (m[0], m[2], m[3]) and i not in mine: mine[i] = mine.pop(tid); break
    return mine

def same(m, s):
    return m is not None and s is not None and (m[1] == s[1] or (m[1] in BOATS and s[1] in BOATS)) and m[2:4] == s[2:4] and m[0] == s[0] and abs(m[4] - s[4]) < 1e-4

def ref_run(ds):
    """Referee predictions for every pair of one game: {(ta,tb): (units, stars_off)}"""
    acts = ds[-1]["actions"]; out = {}
    R.ORACLE.clear(); R.RUIN.clear(); R.RUIN_SEEN.clear()
    for d in ds:
        R.add_ruin_oracle(d)
        for i, v in R.snapshot_units(d).items(): R.ORACLE.setdefault(i, (v[0], v[1], v[5]))
    for a, b in zip(ds, ds[1:]):
        st = State(a, "current"); R.PREV[0] = None; turn = a["currentTurn"]; R.prime_last_moves(st, acts, len(a["actions"]))
        for i in range(len(a["actions"]), len(b["actions"])):
            x = acts[i]
            if x["type"] == 15 and bytes.fromhex(x["raw"])[0] == 255: turn += 1
            R.apply(st, x, turn)
        INV = {v: k for k, v in R.UNIT.items()}
        units = {u.id: (u.owner, INV.get(u.type, u.type), u.x, u.y, round(u.hp, 3)) for u in st.units.values()}
        stars = {}
        for pl, r in EC.check(a, b, acts).items():
            if r["residual"] is None or not EC.Books(a).cities(pl): continue
            stars[pl] = 0 if r["residual"] == 0 and not r["unknown"] else (r["residual"] or 1)
        out[(a["currentTurn"], b["currentTurn"])] = (pair_temp(units, snap(b)), stars)
    return out

def rows():
    """Yield dicts: game, gid, ta, tb, kind('unit'|'star'), key, truth, ref, pf, cls, a, b"""
    jobs, pairs = PJ.jobs_for(want, lambda gid, turn: True)
    pf = {r["tag"]: r for r in PJ.run(jobs)}
    games = collections.defaultdict(list)
    for tag in pairs: games[tag.split("|")[0]].append(tag)
    for gid in sorted(games):
        ds = sorted((d for g, l in PJ.checkpoints(gid[:8]) if g == gid for d, _ in l), key=lambda d: len(d["actions"]))
        refs = ref_run(ds)
        for tag in games[gid]:
            _, ta, tb = tag.split("|"); ta, tb = int(ta), int(tb); a, b, acts = pairs[tag]
            if tag not in pf or "error" in pf[tag]: continue
            truth = snap(b); rr, rstars = refs[(ta, tb)]
            pu = pair_temp({u[0]: (u[1], u[2], u[3], u[4], round(u[5], 3)) for u in pf[tag]["units"]}, truth)
            for i in sorted(set(truth) | set(rr) | set(pu)):
                t, m1, m2 = truth.get(i), rr.get(i), pu.get(i)
                ok1 = same(m1, t) if t else m1 is None; ok2 = same(m2, t) if t else m2 is None
                eq = (m1 is None and m2 is None) or same(m1, m2)
                cls = "both-right" if ok1 and ok2 else "ref-only" if ok1 else "pf-only" if ok2 else "both-same" if eq else "both-differ"
                yield dict(game=gid[:8], gid=gid, ta=ta, tb=tb, kind="unit", key=i, truth=t, ref=m1, pf=m2, cls=cls, a=a, b=b)
            after = {p["PlayerId"]: p["Currency"] for p in b["currentPlayers"]}
            ruins = collections.Counter(bytes.fromhex(x["raw"])[0] for x in acts[len(a["actions"]):len(b["actions"])] if x["type"] == 14)
            for pl, ro in rstars.items():
                po = after[pl] - pf[tag]["stars"].get(str(pl), 0)
                if po and po % EC.RUIN_STARS == 0 and 0 < po // EC.RUIN_STARS <= ruins[pl]: po = 0
                cls = "both-right" if ro == 0 and po == 0 else "ref-only" if ro == 0 else "pf-only" if po == 0 else "both-same" if ro == po else "both-differ"
                yield dict(game=gid[:8], gid=gid, ta=ta, tb=tb, kind="star", key=pl, truth=None, ref=ro, pf=po, cls=cls, a=a, b=b)

if __name__ == "__main__":
    cnt = collections.Counter(); lines = []; allrows = []
    for r in rows():
        cnt[(r["kind"], r["cls"])] += 1; allrows.append(r)
        if r["cls"] != "both-right":
            f = lambda v: "-" if v is None else v
            h = "H" if PJ.held(r["gid"], r["tb"]) else " "
            lines.append(f"{r['cls']:<11}{h} {r['game']} t{r['ta']}->{r['tb']} {r['kind']} {r['key']}: save {f(r['truth'])} ref {f(r['ref'])} pf {f(r['pf'])}")
    for k in ("unit", "star"):
        print(k, {c: cnt[(k, c)] for c in ("both-right", "ref-only", "pf-only", "both-same", "both-differ")})
    if "--turns" in sys.argv: print("\n".join(sorted(lines)))
    if "--pickle" in sys.argv:
        import pickle; pickle.dump([{k: v for k, v in r.items() if k not in ("a", "b")} for r in allrows], open(sys.argv[sys.argv.index("--pickle") + 1], "wb"))
