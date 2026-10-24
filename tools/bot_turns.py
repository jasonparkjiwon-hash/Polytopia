"""Bot behaviour dataset (groundwork for Phase 6): one row per player turn, from each game's longest action log.
Usage: python3 -I tools/bot_turns.py [--summary]   (writes data/bot_turns.csv; --summary prints the regularities used in
.scratchpad/investigations/sim-dist.md). Run sh scripts/restore_saves.sh first. Pure stdlib.

The log is replayed from the game's start with engine/replay.py (unit ids from every checkpoint, as tools/miss.py does),
so kills and what a capture took are known. Columns:
  game difficulty turn player tribe human cities units   (cities and units at the start of the turn)
  trains (Type:n;...) attacks kills captures_village captures_city (old owner ids) research (tech names in order)
  builds (Name:n;...) moves ruins rewards (CityReward names) peace (offer>p / accept<p / reject<p / break>p) other (action names)
  in_range in_range_attacked   (own units with a hostile unit within their attack range at the turn's first action, and how many of them attacked)"""
import sys, os, json, glob, collections, struct, csv
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "engine")); sys.path.insert(0, os.path.join(ROOT, "tools"))
import replay as R, economy as EC
from state import State, TECH
from distributions import longest_logs, REWARD

COLS = ["game", "difficulty", "turn", "player", "tribe", "human", "cities", "units", "trains", "attacks", "kills", "captures_village",
        "captures_city", "research", "builds", "moves", "ruins", "rewards", "peace", "other", "in_range", "in_range_attacked"]

def fmt(counter): return ";".join(f"{k}:{v}" for k, v in sorted(counter.items()))

def game_rows(gid, d):
    R.ORACLE.clear(); R.RUIN.clear(); R.RUIN_SEEN.clear(); R.PREV[0] = None
    for f in glob.glob(os.path.join(ROOT, "saves", gid + "*.json")):
        c = json.load(open(f))
        if not isinstance(c.get("currentTiles"), list): continue
        R.add_ruin_oracle(c)
        for i, v in R.snapshot_units(c).items(): R.ORACLE.setdefault(i, (v[0], v[1], v[5]))
    st = State(d, "initial"); turn = 0; rows = {}; diff = d["currentHeader"].get("Difficulty")
    def row(pl):
        k = (turn, pl)
        if k not in rows:
            p = st.players.get(pl)
            rows[k] = dict(game=gid[:8], difficulty=diff, turn=turn, player=pl, tribe=p.tribe if p else "?", human=int(bool(p and p.human)),
                           cities=sum(1 for o in st.city.values() if o == pl), units=sum(1 for u in st.units.values() if u.owner == pl),
                           trains=collections.Counter(), attacks=0, kills=0, captures_village=0, captures_city=[], research=[],
                           builds=collections.Counter(), moves=0, ruins=0, rewards=[], peace=[], other=collections.Counter(),
                           _in_range={u.id for u in st.units.values() if u.owner == pl and any(R.hostile(st, pl, e.owner) and e.owner != 255
                                      and R.dist((u.x, u.y), (e.x, e.y)) <= R.stat(u).get("range", 1) for e in st.units.values())}, _attackers=set())
        return rows[k]
    for a in d["actions"]:
        t = a["type"]; raw = bytes.fromhex(a["raw"]); pl = raw[0]
        if t == 15 and pl == 255: turn += 1
        if pl != 255 and t != 20:
            r = row(pl); v = struct.unpack(R.FMT[t], raw) if t in R.FMT else (pl,)
            if t == 5: r["trains"][R.UNIT.get(v[1], str(v[1]))] += 1
            elif t == 2: r["attacks"] += 1; r["_attackers"].add(v[1])
            elif t == 7:
                old = st.city.get((v[2], v[3]))
                if old: r["captures_city"].append(str(old))
                else: r["captures_village"] += 1
            elif t == 8: r["research"].append(str(TECH.get(v[1], v[1])))
            elif t == 1: r["builds"][EC.BUILD.get(v[1], (str(v[1]),))[0]] += 1
            elif t == 6: r["moves"] += 1
            elif t == 14: r["ruins"] += 1
            elif t == 11: r["rewards"].append(REWARD.get(v[3], str(v[3])))
            elif t == 27: r["peace"].append(f"offer>{v[3]}")
            elif t == 28: r["peace"].append(("accept<" if v[2] == 1 else "reject<") + str(v[1]))   # replier, offerer, 1 = accepted
            elif t == 29: r["peace"].append(f"break>{v[3]}")
            elif t not in (15, 21): r["other"][a["name"]] += 1
            before = {i: u.owner for i, u in st.units.items()}
        else: before = None
        R.apply(st, a, turn)
        if before is not None and t in (2, 24):
            r["kills"] += sum(1 for i, o in before.items() if o != pl and i not in st.units)
    out = []
    for k in sorted(rows):
        r = rows[k]; r["in_range"] = len(r["_in_range"]); r["in_range_attacked"] = len(r["_in_range"] & r.pop("_attackers")); del r["_in_range"]
        for c in ("trains", "builds", "other"): r[c] = fmt(r[c])
        for c in ("captures_city", "research", "rewards", "peace"): r[c] = ";".join(r[c])
        out.append(r)
    return out

def summary(rows):
    bots = [r for r in rows if not int(r["human"])]
    first = collections.defaultdict(list)                     # research order per tribe: the first three techs
    for r in bots:
        if r["research"]: first[(r["game"], r["player"], r["tribe"])].extend(r["research"].split(";"))
    by_tribe = collections.defaultdict(collections.Counter)
    for (g, p, tr), techs in first.items(): by_tribe[tr]["-".join(techs[:2])] += 1
    print("first two researched techs by tribe (bots; one count per player):")
    for tr in sorted(by_tribe): print(" ", tr, dict(by_tribe[tr].most_common(4)))
    tr_mix = collections.Counter(); atk = collections.Counter(); peace = collections.Counter()
    for r in bots:
        for kv in filter(None, r["trains"].split(";")): k, v = kv.split(":"); tr_mix[k] += int(v)
        atk["turns"] += 1; atk["attacked"] += int(r["attacks"]) > 0; atk["captured city"] += bool(r["captures_city"])
        for p in filter(None, r["peace"].split(";")): peace[p.split(">")[0].split("<")[0]] += 1
    print("bot trains:", dict(tr_mix.most_common(12)))
    print("bot turns:", dict(atk), "peace actions:", dict(peace))
    ir = collections.Counter()
    for r in bots:
        ir["in range"] += int(r["in_range"]); ir["attacked"] += int(r["in_range_attacked"])
        ir["diff%s in range" % r["difficulty"]] += int(r["in_range"]); ir["diff%s attacked" % r["difficulty"]] += int(r["in_range_attacked"])
    print("bot units with a hostile unit in range at turn start, and how many attacked:", dict(ir))

def main():
    rows = []
    for gid, d in sorted(longest_logs().items()): rows += game_rows(gid, d)
    with open(os.path.join(ROOT, "data", "bot_turns.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, COLS); w.writeheader(); w.writerows(rows)
    print(f"{len(rows)} player-turns ({sum(1 for r in rows if not r['human'])} bot) -> data/bot_turns.csv")
    if "--summary" in sys.argv: summary([{k: str(v) for k, v in r.items()} for r in rows])

if __name__ == "__main__":
    main()
