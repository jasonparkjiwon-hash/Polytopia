"""Polyfish replay report, scored like tools/miss.py: load each checkpoint into Polyfish (sim/pfcore save_loader), run the
logged actions to the next checkpoint (bin pfreplay) and compare units (exact HP) and stars with the next save.
Also the legality check: is each logged action in Polyfish's legal-move list at that point?
Usage: python3 -I tools/pf_miss.py [--list] [--illegal] [--game <id prefix>] [--holdout | --all]
  --list     one line per unit/star miss        --illegal  illegal actions grouped by cause (3 examples each)
  --detail <text> [n]  what Polyfish saw at the first n (default 8) illegal actions whose type/cause contains <text>
  --accept   one acceptance line (units, stars, legal %) for the tuned saves and the held-out ones (implies --all)
Needs the bin: cd sim/pfcore && cargo build --release. Never prints save JSON."""
import sys, os, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pf_jobs as PJ
import economy as EC
want = sys.argv[sys.argv.index("--game") + 1] if "--game" in sys.argv else ""
def keep(gid, turn): return True if "--all" in sys.argv or "--accept" in sys.argv else PJ.held(gid, turn) == ("--holdout" in sys.argv)
BOATS = {39, 40, 41, 42, 43, 44, 45}   # Dinghy, Pirate, Bomber, Scoutship, Raft, Rammership, Juggernaut: boat types count as one (like miss.py)
jobs, pairs = PJ.jobs_for(want, keep)
results = PJ.run(jobs)

def snap(d):   # save id -> (owner, type id, x, y, hp)
    o = {}
    for y, row in enumerate(d["currentTiles"]):
        for x, t in enumerate(row):
            u = t.get("Unit")
            if u: o[u["Id"]] = (u["Owner"], u["UnitType"], x, y, u["Health"] / 10)
    return o

def compare(units, d):
    s = snap(d); mine = {u[0]: (u[1], u[2], u[3], u[4], u[5]) for u in units}
    for tid in sorted(i for i in mine if i < 0):          # temp ids: pair with the saved unit on the same tile (miss.py compare)
        m = mine[tid]
        for i, sv in s.items():
            if (sv[0], sv[2], sv[3]) == (m[0], m[2], m[3]) and i not in mine: mine[i] = mine.pop(tid); break
    res = collections.Counter(); bad = []
    for i, sv in s.items():
        m = mine.get(i)
        if m is None: res["missing"] += 1; bad.append(("missing", i, sv)); continue
        if m[1] != sv[1] and not (m[1] in BOATS and sv[1] in BOATS): res["type"] += 1; bad.append(("type", i, sv, m))
        if (m[2], m[3]) != (sv[2], sv[3]): res["pos"] += 1; bad.append(("pos", i, sv, m))
        if m[0] != sv[0]: res["owner"] += 1; bad.append(("owner", i, sv, m))
        if abs(m[4] - sv[4]) > 1e-4: res["hp"] += 1; bad.append(("hp", i, sv, m))
        else: res["HP exact"] += 1
    for i in mine:
        if i not in s: res["extra"] += 1; bad.append(("extra", i, mine[i]))
    return res, bad

tu, ts, lg = collections.Counter(), collections.Counter(), collections.defaultdict(lambda: [0, 0])
causes = collections.defaultdict(list); lines = []; per = collections.defaultdict(lambda: [collections.Counter(), collections.Counter()])
details = []; errors = []; notes = collections.Counter(); load = collections.Counter()
acc = collections.defaultdict(lambda: [0] * 6)   # tuned / held-out -> units ok, n, stars ok, n, legal ok, n
for r in results:
    gid, ta, tb = r["tag"].split("|"); g = per[gid[:8]]
    if "error" in r: errors.append(f"{gid[:8]} t{ta}->{tb}: {r['error']}"); continue
    a, b, acts = pairs[r["tag"]]
    res, bad = compare(r["units"], b); g[0].update(res)
    A = acc["held-out" if PJ.held(gid, int(tb)) else "tuned"]; A[0] += res["HP exact"]; A[1] += sum(res.values())
    for k, (ok, n) in r["legal"].items(): A[4] += ok; A[5] += n
    s0 = dict(g[1])
    lines += [f"{gid[:8]} t{ta}->{tb} unit {z[0]} id{z[1]} {z[2:]}" for z in bad]
    ruins = collections.Counter(bytes.fromhex(x["raw"])[0] for x in acts[len(a["actions"]):len(b["actions"])] if x["type"] == 14)
    after = {p["PlayerId"]: p["Currency"] for p in b["currentPlayers"]}
    for pl, row in EC.check(a, b, acts).items():          # the same player-turns miss.py scores
        if row["residual"] is None or not EC.Books(a).cities(pl): continue
        g[1]["players"] += 1; off = after[pl] - r["stars"].get(str(pl), 0)
        if off == 0 or (off % EC.RUIN_STARS == 0 and 0 < off // EC.RUIN_STARS <= ruins[pl]): g[1]["exact"] += 1   # ruin stars aren't logged
        else: lines.append(f"{gid[:8]} t{ta}->{tb} stars p{pl} off {off:+d} (start {r['stars0'].get(str(pl))})")
    A[2] += g[1]["exact"] - s0.get("exact", 0); A[3] += g[1]["players"] - s0.get("players", 0)
    for k, (ok, n) in r["legal"].items(): lg[k][0] += ok; lg[k][1] += n
    for c in r["illegal"]:
        if "--detail" in sys.argv and sys.argv[sys.argv.index("--detail") + 1] in f"{c['type']}: {c.get('cause')} {c.get('why', '')}": details.append(f"{gid[:8]} t{ta} #{c['i']} {c['type']} {c['raw']}: {c.get('cause')} {json.dumps(c.get('detail'))}")
    tribe = {p["PlayerId"]: p["Tribe"] for p in a["currentPlayers"]}
    for c in r["illegal"]: causes[(c["type"] + (" [Aquarion]" if tribe.get(int(c["raw"][:2], 16)) == 3 else ""), c.get("cause"), c.get("why", ""))].append(f"{gid[:8]} t{ta} #{c['i']} {c['raw']}")
    notes.update(r["notes"]); load.update({"drop " + k: v for k, v in r["load"]["dropped"].items()}); load.update({"sub " + k: v for k, v in r["load"]["substituted"].items()})
if "--accept" in sys.argv:
    print("PF ACCEPT " + " | ".join(f"{k}: units {A[0]}/{A[1]}, stars {A[2]}/{A[3]}, legal {100 * A[4] / max(A[5], 1):.1f}%"
                                   for k, A in sorted(acc.items(), key=lambda kv: kv[0] != "tuned")))
    sys.exit(0)
for gid, (u, s) in sorted(per.items()):
    miss = sum(v for k, v in u.items() if k != "HP exact")
    print(f"{gid} units exact {u['HP exact']}/{u['HP exact'] + miss} | stars exact {s['exact']}/{s['players']}")
    tu.update(u); ts.update(s)
miss = sum(v for k, v in tu.items() if k != "HP exact")
print(f"TOTAL units exact {tu['HP exact']}/{tu['HP exact'] + miss} | stars exact {ts['exact']}/{ts['players']}")
ok, n = sum(v[0] for v in lg.values()), sum(v[1] for v in lg.values())
print(f"LEGAL {ok}/{n} logged actions in Polyfish's legal list ({100 * ok / max(n, 1):.1f}%): " +
      ", ".join(f"{k} {v[0]}/{v[1]}" for k, v in sorted(lg.items(), key=lambda kv: -kv[1][1])))
if errors: print("ERRORS", len(errors), *errors[:5], sep="\n  ")
if "--list" in sys.argv:
    print("unit misses by kind:", dict(tu - collections.Counter({"HP exact": tu["HP exact"]})))
    print("notes:", dict(notes)); print("load:", dict(load)); print("\n".join(lines))
if "--illegal" in sys.argv:
    for (t, c, w), ex in sorted(causes.items(), key=lambda kv: -len(kv[1])):
        print(f"{len(ex):5d} {t}: {c} {w}".rstrip(), "|", "; ".join(ex[:3]))
if "--detail" in sys.argv:
    k = sys.argv.index("--detail"); n = int(sys.argv[k + 2]) if len(sys.argv) > k + 2 and sys.argv[k + 2].isdigit() else 8
    print(len(details), "matching"); print("\n".join(details[:n]))
