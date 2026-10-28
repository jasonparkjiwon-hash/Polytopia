"""Residual clustering (stdlib): which features over-represent the misses?
Unit rows (every unit in every checkpoint pair, from tools/engine_diff.py: referee and Polyfish both scored) and star rows (every
player-turn the economy check scores). For each feature value: rows, misses, miss rate, lift = rate / overall rate, and a one-sided
exact tail probability P(X >= misses) under the overall rate (binomial). Lists values with >= 2 misses, sorted by tail probability.
Usage: python3 -I tools/residual.py [units|stars] [--engine ref|pf|any] [--top N] [--maxgap N]   (--maxgap 1: one-turn pairs only; long gaps swamp everything)
Features (units): tribe, unit type, terrain, own territory, difficulty (bot handicap), human/bot actor, gap length, effects, adjacent enemy,
  in a city/village, boat/land, action types touching the unit in the window, round bucket, attacked/defended/moved in the window.
Features (stars): tribe, human, gap length, cities bucket, round bucket, event counts by type in the window (own/other), city changes."""
import sys, os, collections, math, struct, json
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "engine")); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine_diff as ED
import pf_jobs as PJ
import economy as EC, replay as R
from state import TRIBE

MODE = next((a for a in sys.argv[1:] if a in ("units", "stars")), "stars")
ENGINE = sys.argv[sys.argv.index("--engine") + 1] if "--engine" in sys.argv else "ref"
TOP = int(sys.argv[sys.argv.index("--top") + 1]) if "--top" in sys.argv else 25
ATYPE = {1: "Build", 2: "Attack", 3: "Recover", 4: "HealOthers", 5: "Train", 6: "Move", 7: "Capture", 8: "Research", 9: "Destroy", 11: "CityReward",
         13: "Promote", 14: "Ruins", 15: "EndTurn", 16: "Upgrade", 17: "FreezeArea", 18: "BreakIce", 24: "Explode", 27: "OfferPeace",
         28: "PeaceReply", 29: "BreakPeace", 30: "Enchant", 38: "Swarm"}

def binom_tail(k, n, p):                            # P(X >= k), X ~ Bin(n, p)
    if p <= 0: return 0.0 if k > 0 else 1.0
    if p >= 1: return 1.0
    s = 0.0
    for i in range(k, n + 1):
        s += math.exp(math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1) + i * math.log(p) + (n - i) * math.log(1 - p))
        if i > k + 400: break
    return min(s, 1.0)

def window(acts, a, b):
    out = []
    for i in range(len(a["actions"]), len(b["actions"])):
        x = acts[i]; out.append((x["type"], bytes.fromhex(x["raw"])[0], x["raw"]))
    return out

def unit_features(row, pairs, cache):
    tag = f"{row['gid']}|{row['ta']}|{row['tb']}"; a, b, acts = pairs[tag]
    if tag not in cache:
        w = window(acts, a, b); cache[tag] = (w, {p["PlayerId"]: p for p in a["currentPlayers"]}, a["currentTiles"])
    w, players, tiles = cache[tag]
    u = row["truth"] or row["ref"] or row["pf"]
    if u is None: return None
    owner, ty, x, y = u[0], u[1], u[2], u[3]
    tr = tiles[y][x]
    f = {"tribe": TRIBE.get(players.get(owner, {}).get("Tribe"), "?"), "type": R.UNIT.get(ty, ty), "terrain": str(tr.get("TerrainType", "?")),
         "territory": "own" if tr.get("Owner") == owner else "other", "gap": min(row["tb"] - row["ta"], 6),
         "round": min(row["ta"] // 5, 5), "boat": R.UNIT.get(ty, ty) in ("Raft", "Pirate", "Dinghy", "Scoutship", "Bomber", "Rammership", "Juggernaut"),
         "city_tile": bool(tr.get("ImprovementExists") and tr.get("ImprovementType") == 1)}
    pl = players.get(owner, {}); f["handicap"] = pl.get("DifficultyHandicap", "?"); f["human"] = pl.get("AutoPlay", 0) == 0
    kinds = collections.Counter(); hit = False
    for t, actor, raw in w:
        r = bytes.fromhex(raw)
        if t == 2 and len(r) >= 21:
            _, _, ax, ay, tx, ty2 = struct.unpack("<BIIIII", r)[:6]
            if (ax, ay) == (x, y) or (tx, ty2) == (x, y): kinds["fight_here"] += 1
    f["fight_here"] = kinds["fight_here"] > 0
    f["actor_types"] = tuple(sorted({ATYPE.get(t, str(t)) for t, a_, r_ in w if a_ == owner}))
    return f

def star_features(row, pairs, cache):
    tag = f"{row['gid']}|{row['ta']}|{row['tb']}"; a, b, acts = pairs[tag]; pl = row["key"]
    w = window(acts, a, b); players = {p["PlayerId"]: p for p in a["currentPlayers"]}
    own = collections.Counter(ATYPE.get(t, str(t)) for t, actor, r in w if actor == pl)
    oth = collections.Counter(ATYPE.get(t, str(t)) for t, actor, r in w if actor != pl)
    f = {"tribe": TRIBE.get(players[pl]["Tribe"], "?"), "human": players[pl].get("AutoPlay", 0) == 0, "gap": min(row["tb"] - row["ta"], 8),
         "round": min(row["ta"] // 5, 5), "handicap": players[pl].get("DifficultyHandicap", "?"),
         "cities": min(len(EC.Books(a).cities(pl)), 8), "stars0": min(players[pl]["Currency"] // 10, 8)}
    for k in ("Build", "Attack", "Capture", "Ruins", "Upgrade", "Research", "Train", "OfferPeace", "PeaceReply", "BreakPeace", "Promote", "CityReward", "Swarm", "Enchant"):
        f["own_" + k] = min(own[k], 3); f["other_" + k] = min(oth[k], 3)
    f["any_capture_in_window"] = (own["Capture"] + oth["Capture"]) > 0
    f["lost_city"] = len(EC.Books(b).cities(pl)) < len(EC.Books(a).cities(pl)); f["gained_city"] = len(EC.Books(b).cities(pl)) > len(EC.Books(a).cities(pl))
    f["encountered_new"] = len(set(players[pl].get("Encountered", [])) ^ set(next(p for p in b["currentPlayers"] if p["PlayerId"] == pl).get("Encountered", []))) > 0
    return f

def main():
    jobs, pairs = PJ.jobs_for("", lambda gid, turn: True)
    maxgap = int(sys.argv[sys.argv.index("--maxgap") + 1]) if "--maxgap" in sys.argv else 99
    rows = [r for r in ED.rows() if r["kind"] == ("unit" if MODE == "units" else "star") and r["tb"] - r["ta"] <= maxgap]
    cache = {}; table = []
    for r in rows:
        miss = (r["cls"] != "both-right") if ENGINE == "any" else ({"ref": r["cls"] in ("pf-only", "both-same", "both-differ"), "pf": r["cls"] in ("ref-only", "both-same", "both-differ")}[ENGINE])
        f = (unit_features if MODE == "units" else star_features)(r, pairs, cache)
        if f is None: continue
        table.append((f, miss, r))
    n = len(table); m = sum(1 for _, x, _ in table if x); p0 = m / n
    print(f"{MODE} rows {n}, misses {m} ({100 * p0:.2f}%) for engine={ENGINE}")
    cnt = collections.defaultdict(lambda: [0, 0])
    for f, miss, _ in table:
        for k, v in f.items():
            if k == "actor_types":
                for t in v: cnt[(k, t)][0] += 1; cnt[(k, t)][1] += miss
            else: cnt[(k, v)][0] += 1; cnt[(k, v)][1] += miss
    res = []
    for (k, v), (nn, mm) in cnt.items():
        if mm >= 2 and nn > mm: res.append((binom_tail(mm, nn, p0), k, v, nn, mm))
    res.sort()
    print(f"{'feature':<26}{'value':<18}{'rows':>6}{'miss':>5}{'rate':>7}{'lift':>6}{'p(tail)':>9}")
    for pt, k, v, nn, mm in res[:TOP]: print(f"{k:<26}{str(v):<18}{nn:>6}{mm:>5}{100 * mm / nn:>6.1f}%{(mm / nn) / p0:>6.1f}{pt:>9.4f}")

main()
