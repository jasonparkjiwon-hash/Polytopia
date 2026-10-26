"""Shared by tools/pf_miss.py and tools/pf_stars.py: checkpoint pairs -> pfreplay jobs, and running the bin.
Ruin rewards aren't in the log: like the Python replay's ruin oracle, read each one back from the next save
(a unit created that turn on the ruin tile = Swordsman; a tech not researched = FreeTech; else 10 stars if the
star check says so; else Explorer) and hand it to Polyfish as a hint."""
import os, sys, json, glob, re, collections, subprocess, tempfile, struct
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "engine"))
import economy as EC
BIN = os.path.join(ROOT, "sim", "pfcore", "target", "release", "pfreplay")
HELD = {h["game"]: h for h in json.load(open(os.path.join(ROOT, "data", "holdout.json")))["held"]}
SWORDSMAN, FREE_TECH, RESOURCES, EXPLORER = 8, 4, 1, 3   # Polyfish RuinsRewardType

def held(gid, turn): return gid in HELD and turn >= HELD[gid].get("from_turn", 0)

def checkpoints(prefix=""):
    games = collections.defaultdict(list)
    for f in glob.glob(os.path.join(ROOT, "saves", prefix + "*_t*.json")):
        if re.search(r"_t\d+\.json$", f): games[os.path.basename(f)[:36]].append(f)
    for gid, fs in sorted(games.items()):
        yield gid, sorted(((json.load(open(f)), f) for f in fs), key=lambda d: len(d[0]["actions"]))

def ruin_hints(a, b, acts):
    n0, n1 = len(a["actions"]), len(b["actions"]); turn = a["currentTurn"]
    tech = lambda d, pl: {t for p in d["currentPlayers"] if p["PlayerId"] == pl for t in p["AvailableTech"]}
    researched = collections.defaultdict(set); ruins = collections.defaultdict(list)
    for i in range(n0, n1):
        x = acts[i]; r = bytes.fromhex(x["raw"])
        if x["type"] == 15 and r[0] == 255: turn += 1
        if x["type"] == 8: researched[r[0]].add(struct.unpack("<BH", r)[1])
        if x["type"] == 14: ruins[r[0]].append((i, turn) + struct.unpack("<BII", r)[1:])
    units = [(t["Unit"], x, y) for y, row in enumerate(b["currentTiles"]) for x, t in enumerate(row) if t.get("Unit")]
    made = collections.defaultdict(set)              # (owner, created turn) -> unit ids in the next save
    for u, _, _ in units: made[(u["Owner"], u["CreatedTurn"])].add(u["Id"])
    first = {}                                       # each unit's first logged Move in the window: (pl, fx, fy, tx, ty, id, index)
    for i in range(n0, n1):
        if acts[i]["type"] == 6:
            m = struct.unpack("<BIIIII", bytes.fromhex(acts[i]["raw"])); first.setdefault(m[5], m + (i,))
    moves = list(first.values())
    rows = EC.check(a, b, acts) if ruins else {}
    hints = []
    for pl, rs in ruins.items():
        free = sorted(tech(b, pl) - tech(a, pl) - researched[pl]); stars = (rows.get(pl, {}).get("residual") or 0) + rows.get(pl, {}).get("ruin_stars", 0)
        for i, t, x, y in rs:
            on_tile = any(u["Owner"] == pl and u["CreatedTurn"] == t and (ux, uy) == (x, y) for u, ux, uy in units)
            # or it walked off before the next save: a unit created that turn whose first logged Move starts on the ruin
            # (af181c8f t16 #2211; the Python replay's RUIN oracle does the same)
            walked = any(m[0] == pl and m[1:3] == (x, y) and m[5] in made[(pl, t)] for m in moves if m[6] > i)
            if on_tile or walked: hints.append(dict(i=i, reward=SWORDSMAN))
            elif free: hints.append(dict(i=i, reward=FREE_TECH, tech=free.pop(0)))
            elif stars >= EC.RUIN_STARS: hints.append(dict(i=i, reward=RESOURCES)); stars -= EC.RUIN_STARS
            else: hints.append(dict(i=i, reward=EXPLORER))
    return hints

def meet_hints(a, b):
    """Tribes met between the saves (the log has no meet event; Polyfish's own rule misses meets after Explorer
    exploration): read them from the next save's Encountered, with the stars the economy model books (economy.check)."""
    pa = {p["PlayerId"]: p for p in a["currentPlayers"]}; pb = {p["PlayerId"]: p for p in b["currentPlayers"]}
    out = []
    for pl in pb:
        for o in sorted(set(pb[pl]["Encountered"]) - set(pa.get(pl, {}).get("Encountered", []))):
            score = (pa if o > pl and o in pa else pb).get(o, {}).get("Score", 0)
            out.append(dict(pl=pl, o=o, stars=EC.meet_stars(score)))
    return out

def jobs_for(prefix="", keep=lambda gid, turn: not held(gid, turn), first_turn=None):
    jobs, pairs = [], {}
    for gid, ds in checkpoints(prefix):
        acts = ds[-1][0]["actions"]
        for (a, fa), (b, fb) in zip(ds, ds[1:]):
            if not keep(gid, b["currentTurn"]) or (first_turn is not None and a["currentTurn"] != first_turn): continue
            tag = f"{gid}|{a['currentTurn']}|{b['currentTurn']}"; pairs[tag] = (a, b, acts)
            jobs.append(dict(tag=tag, start=fa, final=ds[-1][1], hints=ruin_hints(a, b, acts), meets=meet_hints(a, b), **{"from": len(a["actions"]), "to": len(b["actions"])}))
    return jobs, pairs

def run(jobs, trace=False):
    if not os.path.exists(BIN): sys.exit("build Polyfish first: cd sim/pfcore && cargo build --release")
    with tempfile.TemporaryDirectory() as tmp:
        jf = os.path.join(tmp, "jobs.json"); json.dump(jobs, open(jf, "w"))
        env = dict(os.environ, PF_TRACE="1") if trace else None
        out = subprocess.run([BIN, jf], capture_output=True, text=True, env=env).stdout
    return [json.loads(l[7:]) for l in out.splitlines() if l.startswith("PFJSON ")]
