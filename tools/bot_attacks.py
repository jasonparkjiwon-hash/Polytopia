"""Bot attack decisions vs the engine's predicted outcome (groundwork for Phase 6).
Usage: python3 -I tools/bot_attacks.py [--summary]   (writes data/bot_attacks.csv; --summary prints the rules and hit rates used in
.scratchpad/investigations/sim-dist.md, training games and the held-out games of data/holdout.json scored separately). Pure stdlib.

Each game's longest log is replayed with engine/replay.py (as tools/bot_turns.py does). For every bot unit, at its first action of
the turn (just before that action, since other units may already have killed or wounded its targets; at the end of the turn if
it never acted), the hostile units it could attack from where it stands are listed:
visible to the bot (replay.sees), not hidden, within the unit's range. For each target, replay.fight() on the current state gives
the predicted damage and return damage. At every bot attack the same list is taken from the attacker's square (after any move),
so target choice is known too. One row per decision point:
  kind      'first' (the unit's first action, or turn end: did it attack without moving first?) or 'attack' (an attack action: which target?)
  game difficulty turn player tribe uid utype uhp umax   (the unit)
  outcome   first: attack (attacked from here) / move_attack (moved, then attacked) / move / other / idle;  attack: index of the target hit
  cands     per target 'type|hp|maxhp|dmg|ret|kill|owner|human|attacked_us_turn|city|we_hit_turn|id|x|y' joined with ';'  (attacked_us_turn: last turn that
            owner attacked this player, -1 if never; city: the target stands on a city or village; we_hit_turn: last turn this
            player attacked that owner)   ucity: the unit stands in its own city"""
import sys, os, json, glob, collections, struct, csv, copy
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "engine")); sys.path.insert(0, os.path.join(ROOT, "tools"))
import replay as R
from state import State
from distributions import longest_logs
from economy import UNIT_COST

COLS = ["kind", "game", "difficulty", "turn", "player", "tribe", "uid", "utype", "ux", "uy", "uhp", "umax", "ucity", "outcome", "note", "cands"]
UNIT_AT = (3, 4, 13, 16, 18, 24, 38)          # actions that name their unit by square

def holdout_games():
    h = json.load(open(os.path.join(ROOT, "data", "holdout.json")))
    return {e["game"][:8] for e in h.get("held", [])}

def candidates(st, u, last_hit):
    out = []
    rng = R.stat(u).get("range", 1)
    for e in st.units.values():
        if e.owner == 255 or not R.hostile(st, u.owner, e.owner) or st.at.get((e.x, e.y)) != e.id: continue
        if R.dist((u.x, u.y), (e.x, e.y)) > rng or R.INVISIBLE in e.effects or not R.sees(st, u.owner, (e.x, e.y)): continue
        dmg, ret, _ = R.fight(st, u, e)
        p = st.players.get(e.owner)
        out.append(dict(type=e.type, hp=e.hp, maxhp=e.max_hp, dmg=dmg, ret=ret, kill=int(dmg >= e.hp), owner=e.owner,
                        human=int(bool(p and p.human)), atk_us=last_hit.get((e.owner, u.owner), -1), city=int((e.x, e.y) in st.city), id=e.id, x=e.x, y=e.y,
                        we_hit=last_hit.get((u.owner, e.owner), -1)))
    return out

def enc(cs):
    return ";".join("|".join(str(c[k]) for k in ("type", "hp", "maxhp", "dmg", "ret", "kill", "owner", "human", "atk_us", "city", "we_hit", "id", "x", "y")) for c in cs)

def game_rows(gid, d):
    R.ORACLE.clear(); R.RUIN.clear(); R.RUIN_SEEN.clear(); R.PREV[0] = None
    for f in glob.glob(os.path.join(ROOT, "saves", gid + "*.json")):
        c = json.load(open(f))
        if not isinstance(c.get("currentTiles"), list): continue
        R.add_ruin_oracle(c)
        for i, v in R.snapshot_units(c).items(): R.ORACLE.setdefault(i, (v[0], v[1], v[5]))
    st = State(d, "initial"); turn = 0; diff = d["currentHeader"].get("Difficulty")
    rows = []; last_hit = {}            # (attacker owner, victim owner) -> last turn
    cur = None; seen = {}; pending = {}; elig = []  # cur player; uids that acted; uid -> row awaiting 'move_attack'; units able to attack

    def base(u, kind):
        p = st.players.get(u.owner)
        return dict(kind=kind, game=gid[:8], difficulty=diff, turn=turn, player=u.owner, tribe=p.tribe if p else "?", uid=u.id,
                    utype=u.type, ux=u.x, uy=u.y, uhp=u.hp, umax=u.max_hp, ucity=int(st.city.get((u.x, u.y)) == u.owner))

    def start_turn(pl):
        nonlocal seen, pending, elig
        seen = {}; pending = {}; elig = []
        p = st.players.get(pl)
        if not p or p.human: return
        for u in list(st.units.values()):
            if u.owner != pl or st.at.get((u.x, u.y)) != u.id: continue
            if R.stat(u)["atk"] <= 0 or "onlyExplode" in R.stat(u)["skills"]: continue   # Raft, Mooni, Boomchi cannot attack
            elig.append(u.id)

    def end_turn():                           # units that never acted: targets as the turn ends
        for uid, r in pending.items(): rows.append(r)
        for uid in elig:
            u = st.units.get(uid)
            if uid in seen or u is None or st.at.get((u.x, u.y)) != uid: continue
            cs = candidates(st, u, last_hit)
            if cs: rows.append(dict(base(u, "first"), outcome="idle", note="", cands=enc(cs)))

    for a in d["actions"]:
        t = a["type"]; raw = bytes.fromhex(a["raw"]); pl = raw[0]
        v = struct.unpack(R.FMT[t], raw) if t in R.FMT else (pl,)
        if t == 15 and pl == 255: turn += 1
        if pl != 255 and t != 20 and pl != cur:
            if cur is not None: end_turn()
            cur = pl; start_turn(pl)
        bot = pl != 255 and st.players.get(pl) and not st.players[pl].human
        if bot and t in (6, 2) or (bot and t in UNIT_AT and len(v) >= 3):
            if t == 6: uid = v[5]
            elif t == 2: uid = v[1]
            else:
                u0 = R.unit_at(st, v[1], v[2]); uid = u0.id if u0 else None
            if uid in elig and uid not in seen:   # the unit's first action: what could it attack from where it stands right now?
                seen[uid] = 1; u = st.units.get(uid)
                cs = candidates(st, u, last_hit) if u is not None and st.at.get((u.x, u.y)) == uid else []
                if cs:
                    r = dict(base(u, "first"), outcome={6: "move", 2: "attack"}.get(t, "other"), note="", cands=enc(cs))
                    if t == 6:                     # a move onto an enemy or neutral city or village
                        q = (v[3], v[4]); o = (v[1], v[2])
                        tg = [(e.x, e.y) for e in st.units.values() if e.owner != pl and e.owner != 255 and R.hostile(st, pl, e.owner)
                              and R.dist(o, (e.x, e.y)) <= R.stat(u).get("range", 1)]
                        cit = [c for c, ow in st.city.items() if ow != pl and (ow in (0, -1, 255) or R.hostile(st, pl, ow))]
                        def step(ps):
                            if not ps: return "="
                            a0, a1 = min(R.dist(o, c) for c in ps), min(R.dist(q, c) for c in ps)
                            return "<" if a1 < a0 else ">" if a1 > a0 else "="
                        r["note"] = ("to_city " if q in st.city and st.city[q] != pl else "") + "target" + step(tg) + " city" + step(cit)
                        pending[uid] = r
                    else:
                        if t != 2: r["note"] = a["name"]
                        rows.append(r)
            elif uid in pending and t == 2:
                pending[uid]["outcome"] = "move_attack"; rows.append(pending.pop(uid))
            if t == 2:
                at = R.locate(st, v[1], v[2], v[3], pl)
                df = R.unit_at(st, v[4], v[5])
                if at is not None and df is not None and at.type not in ("MindBender", "Shaman"):
                    cs = candidates(st, at, last_hit)
                    idx = next((i for i, c in enumerate(cs) if c["id"] == df.id), -1)
                    if idx < 0:                    # the target was not on our list (fog/peace/range model miss): keep it, flagged
                        dmg, ret, _ = R.fight(st, at, df); p = st.players.get(df.owner)
                        cs.append(dict(type=df.type, hp=df.hp, maxhp=df.max_hp, dmg=dmg, ret=ret, kill=int(dmg >= df.hp), owner=df.owner,
                                       human=int(bool(p and p.human)), atk_us=last_hit.get((df.owner, pl), -1), city=int((df.x, df.y) in st.city), id=df.id, x=df.x, y=df.y,
                                       we_hit=last_hit.get((pl, df.owner), -1)))
                        idx = -(len(cs))           # negative: off-list target, index -idx-1
                    rows.append(dict(base(at, "attack"), outcome=idx, note="moved" if getattr(at, "moved_now", False) else "", cands=enc(cs)))
        if t == 2 and pl != 255:
            df = R.unit_at(st, v[4], v[5])
            if df is not None and df.owner != pl: last_hit[(pl, df.owner)] = turn
        if t == 15 and pl != 255 and pl == cur:
            end_turn(); pending = {}; cur = None
        R.apply(st, a, turn)
    end_turn()
    return rows

def parse(r):
    cs = []
    for s in filter(None, r["cands"].split(";")):
        f = s.split("|")
        cs.append(dict(type=f[0], hp=float(f[1]), maxhp=float(f[2]), dmg=int(f[3]), ret=int(f[4]), kill=int(f[5]), owner=int(f[6]),
                       human=int(f[7]), atk_us=int(f[8]), city=int(f[9]), we_hit=int(f[10]), id=int(f[11]), x=int(f[12]), y=int(f[13])))
    return cs

def summary(rows):
    held = holdout_games()
    for label, sel in (("training", lambda r: r["game"] not in held), ("held-out", lambda r: r["game"] in held)):
        rs = [r for r in rows if sel(r)]
        print(f"== {label}: {len(rs)} rows ==")
        report(rs)

def report(rs):
    first = [r for r in rs if r["kind"] == "first"]
    oc = collections.Counter(r["outcome"] for r in first)
    print(" first action of a bot unit with a target in range:", dict(oc))
    # feature split: attacked (in place or after a move) vs not, by best predicted outcome
    tab = collections.defaultdict(collections.Counter)
    for r in first:
        cs = parse(r); a = r["outcome"] in ("attack", "move_attack")
        kill = any(c["kill"] for c in cs); safe = any(c["ret"] < float(r["uhp"]) for c in cs)
        tab["kill" if kill else "no kill"][a] += 1
        tab["diff" + str(r["difficulty"])][a] += 1
        tab["target human" if any(c["human"] for c in cs) else "bots only"][a] += 1
        tab["provoked" if any(c["atk_us"] >= 0 for c in cs) else "never attacked by them"][a] += 1
        ratio = max(c["dmg"] - c["ret"] for c in cs)
        tab["dmg-ret>=%d" % (2 * (ratio >= 2) + 1 * (ratio >= 0))][a] += 1
    for k in sorted(tab): print(f"  {k:24s} attacked {tab[k][True]}/{tab[k][True] + tab[k][False]}")
    att = [r for r in rs if r["kind"] == "attack"]
    multi = [r for r in att if len(parse(r)) >= 2 and int(r["outcome"]) >= 0]
    print(f" attacks: {len(att)}, target off our list: {sum(1 for r in att if int(r['outcome']) < 0)}, with 2+ targets on list: {len(multi)}")
    for name, key in RULES_T.items():
        hit = 0
        for r in multi:
            cs = parse(r); best = max(range(len(cs)), key=lambda i: key(cs[i], r))
            top = [i for i in range(len(cs)) if key(cs[i], r) == key(cs[best], r)]
            hit += (int(r["outcome"]) in top) / len(top)          # ties split
        print(f"  target rule {name:28s} {hit:.1f}/{len(multi)} = {hit / max(1, len(multi)):.0%}")

RULES_T = {   # target-priority candidates; higher key wins, ties split evenly
    "random": lambda c, r: 0,
    "max damage": lambda c, r: c["dmg"],
    "kill, then max damage": lambda c, r: (c["kill"], c["dmg"]),
    "kill, then min return": lambda c, r: (c["kill"], -c["ret"]),
    "max dmg - return": lambda c, r: c["dmg"] - c["ret"],
    "kill, then dmg - return": lambda c, r: (c["kill"], c["dmg"] - c["ret"]),
    "lowest hp": lambda c, r: -c["hp"],
    "lowest hp after hit": lambda c, r: -(c["hp"] - c["dmg"]),
    "kill, then lowest hp": lambda c, r: (c["kill"], -c["hp"]),
    "human first, then kill/dmg": lambda c, r: (c["human"], c["kill"], c["dmg"]),
    "kill, min return, then cost": lambda c, r: (c["kill"], -c["ret"], UNIT_COST.get(c["type"]) or 0),   # BOT-ATTACK-TARGET (tools/bot_rules.py)
}

def main():
    rows = []
    for gid, d in sorted(longest_logs().items()): rows += game_rows(gid, d)
    with open(os.path.join(ROOT, "data", "bot_attacks.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, COLS); w.writeheader(); w.writerows(rows)
    print(f"{len(rows)} decision rows -> data/bot_attacks.csv")
    if "--summary" in sys.argv: summary([{k: str(v) for k, v in r.items()} for r in rows])

if __name__ == "__main__":
    main()
