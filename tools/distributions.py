"""Measured distributions of the random parts the forward model needs, from every save in saves/.
Usage: python3 -I tools/distributions.py [--rows]   (writes data/distributions.json; --rows prints one line per ruin event)
Run sh scripts/restore_saves.sh first. Pure stdlib; reads saves programmatically only.

Ruin rewards: the log doesn't say what a ruin gave, so each examined ruin is classified from the two saves around it:
  unit     a unit created that turn standing on the ruin tile (engine RUIN oracle)
  tech     a tech the player gained without a Research action
  stars    the star check (engine/economy.py) is exactly +10 short
  explorer at least EXPLORER_TILES newly visible tiles the replayed units don't explain (baseline: 1 of 674
           player-turns without a ruin or a city Explorer reach that; 31 of 35 city-Explorer turns do)
  pop      the capital's TotalPopulation rose by at least 3 more than the player's builds explain
  (unit, tech and stars are hard evidence and win over explorer/pop, which can fire by chance: rates in "signal_false_positive")
  unresolved   none of these, or more than one, or more than one ruin by that player between the two saves
City rewards: the choice at each level-up, bots vs the human, from every game's longest action log."""
import sys, os, json, glob, re, collections, struct, math
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "engine"))
import replay as R, economy as EC
from state import State
EXPLORER_TILES = 30
BUILD_POP = {"Farm": 2, "Mine": 2, "LumberHut": 1, "Port": 1, "Fishing": 1, "Hunting": 1, "HarvestFruit": 1}   # data/economy.json; Windmill/Sawmill/Forge below
FEEDER = {"Windmill": "Farm", "Sawmill": "LumberHut", "Forge": "Mine"}; FEED_POP = {"Windmill": 1, "Sawmill": 1, "Forge": 2}
STRUCT_ID = {"Farm": 5, "LumberHut": 12, "Mine": 21}
REWARD = {1: "CityWall", 2: "Park", 3: "Workshop", 4: "Explorer", 5: "BorderGrowth", 6: "SuperUnit", 7: "Resources", 8: "PopGrowth"}

def wilson(k, n, z=1.96):
    if n == 0: return [0.0, 1.0]
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, c - h), 3), round(min(1.0, c + h), 3)]

def table(counter, keys=None):
    n = sum(counter.values()); keys = keys or sorted(counter)
    return {"n": n, "outcomes": {k: {"count": counter[k], "share": round(counter[k] / n, 3) if n else None, "ci95": wilson(counter[k], n)} for k in keys}}

def vis(d):
    v = collections.defaultdict(set)
    for y, row in enumerate(d["currentTiles"]):
        for x, t in enumerate(row):
            for p in t.get("PlayerVisibility", ()): v[p].add((x, y))
    return v

def capitals(d):
    out = {}
    for y, row in enumerate(d["currentTiles"]):
        for x, t in enumerate(row):
            if t["ImprovementExists"] and t["ImprovementType"] == 1 and t["Capital"]: out[t["Capital"]] = ((x, y), t["ImprovementData"]["TotalPopulation"])
    return out

def build_pop(d, x, y, name):
    if name in BUILD_POP: return BUILD_POP[name]
    if name in FEEDER:
        rows = d["currentTiles"]
        return FEED_POP[name] * sum(1 for dx in (-1, 0, 1) for dy in (-1, 0, 1) if (dx or dy) and 0 <= y + dy < len(rows) and 0 <= x + dx < len(rows[0])
                                    and rows[y + dy][x + dx]["ImprovementExists"] and rows[y + dy][x + dx]["ImprovementType"] == STRUCT_ID[FEEDER[name]])
    return 0

def per_turn_games():
    games = collections.defaultdict(list)
    for f in glob.glob(os.path.join(ROOT, "saves", "*_t*.json")):
        if re.search(r"_t\d+\.json$", f): games[os.path.basename(f)[:36]].append(f)
    return games

BASE = collections.Counter()   # soft signals on player-turns without a ruin (false-positive rates)
def ruin_events():
    """One row per (game, save pair, player) with at least one ruin examined between the two saves."""
    rows = []
    for gid, fs in sorted(per_turn_games().items()):
        ds = sorted((json.load(open(f)) for f in fs), key=lambda d: len(d["actions"])); acts = ds[-1]["actions"]
        R.ORACLE.clear(); R.RUIN.clear(); R.RUIN_SEEN.clear()
        for d in ds:
            R.add_ruin_oracle(d)
            for i, v in R.snapshot_units(d).items(): R.ORACLE.setdefault(i, (v[0], v[1], v[5]))
        for a, b in zip(ds, ds[1:]):
            st = State(a, "current"); R.PREV[0] = None; turn = a["currentTurn"]; R.prime_last_moves(st, acts, len(a["actions"]))
            ruins = []; research = collections.Counter(); city_explorer = collections.Counter(); pop_builds = collections.Counter()
            cap_a = capitals(a)
            for i in range(len(a["actions"]), len(b["actions"])):
                x = acts[i]; raw = bytes.fromhex(x["raw"]); pl = raw[0]
                if x["type"] == 15 and pl == 255: turn += 1
                if x["type"] == 14:
                    _, rx, ry = struct.unpack("<BII", raw); ruins.append((pl, rx, ry, turn, st.terrain.get((rx, ry))))
                if x["type"] == 8: research[pl] += 1
                if x["type"] == 11 and struct.unpack("<BIIH", raw)[3] == 4: city_explorer[pl] += 1
                if x["type"] == 1:
                    _, s, bx, by = struct.unpack("<BHII", raw); name = EC.BUILD.get(s, ("?",))[0]
                    owner_city = tuple(b["currentTiles"][by][bx]["CapitalCoordinates"])
                    if pl in cap_a and owner_city == cap_a[pl][0]: pop_builds[pl] += build_pop(b, bx, by, name)
                R.apply(st, x, turn)
            if b["currentTurn"] - a["currentTurn"] == 1:
                va, vb = vis(a), vis(b); cap_b = capitals(b); rp = {r[0] for r in ruins}
                for pl in st.players:
                    if pl in rp: continue
                    if not city_explorer[pl]: BASE["explorer n"] += 1; BASE["explorer fired"] += len(vb[pl] - st.explored.get(pl, set()) - va[pl]) >= EXPLORER_TILES
                    if pl in cap_a and pl in cap_b and cap_a[pl][0] == cap_b[pl][0]:
                        BASE["pop n"] += 1; BASE["pop fired"] += cap_b[pl][1] - cap_a[pl][1] - pop_builds[pl] >= 3
            if not ruins: continue
            econ = EC.check(a, b, acts); va, vb = vis(a), vis(b); cap_b = capitals(b)
            ta = {p["PlayerId"]: set(p["AvailableTech"]) for p in a["currentPlayers"]}
            tb = {p["PlayerId"]: set(p["AvailableTech"]) for p in b["currentPlayers"]}
            for pl in sorted({r[0] for r in ruins}):
                mine = [r for r in ruins if r[0] == pl]; e = econ.get(pl, {})
                sig = {"unit": [u[1] for (_, rx, ry, t, _) in mine for u in R.RUIN.get((pl, rx, ry), ()) if u[0] == t],
                       "tech": len(tb.get(pl, set()) - ta.get(pl, set())) - research[pl],
                       "stars": e.get("ruin_stars", 0) // EC.RUIN_STARS,
                       "explorer": len(vb[pl] - st.explored.get(pl, set()) - va[pl]) >= EXPLORER_TILES and not city_explorer[pl],
                       "pop": pl in cap_a and pl in cap_b and cap_a[pl][0] == cap_b[pl][0] and cap_b[pl][1] - cap_a[pl][1] - pop_builds[pl] >= 3}
                hard = [k for k in ("unit", "tech", "stars") if sig[k]]; soft = [k for k in ("explorer", "pop") if sig[k]]
                if len(mine) > 1: cls = "unresolved (several ruins)"
                elif len(hard) == 1: cls = hard[0]               # one reward per ruin: a hard signal wins over a soft one (soft ones have false positives)
                elif not hard and len(soft) == 1: cls = soft[0]
                elif not hard and not soft: cls = "unresolved (no signal)"
                else: cls = "unresolved (" + "+".join(hard + soft) + ")"
                if cls == "unit": cls = "unit:" + sig["unit"][0]
                _, rx, ry, t, ter = mine[0]
                rows.append(dict(game=gid[:8], saves=f"t{a['currentTurn']}->t{b['currentTurn']}", player=pl, human=st.players[pl].human,
                                 tile=[rx, ry], turn=t, terrain=ter, water=ter in ("Ocean", "Water"), ruins=len(mine), reward=cls,
                                 window=b["currentTurn"] - a["currentTurn"]))
    return rows

def whole_game_techs():
    """Free techs (gained without a Research action) per examined ruin, over each game's longest log: a cross-check on the tech share."""
    out = collections.Counter()
    for gid, d in longest_logs().items():
        st0 = State(d, "initial"); stf = State(d, "current")
        res = collections.Counter(); ruins = collections.Counter()
        for x in d["actions"]:
            raw = bytes.fromhex(x["raw"])
            if x["type"] == 8: res[raw[0]] += 1
            if x["type"] == 14: ruins[raw[0]] += 1
        for pl, p in stf.players.items():
            if pl not in st0.players or not ruins[pl]: continue
            free = len(p.techs - st0.players[pl].techs) - res[pl]
            if free < 0 or free > ruins[pl]: out["players skipped (count doesn't fit)"] += 1; continue
            out["ruins"] += ruins[pl]; out["tech"] += free; out["games"] += 0
        out["games"] += 1
    return out

PAIR = {3: "level 2: Workshop|Explorer", 4: "level 2: Workshop|Explorer", 1: "level 3: CityWall|Resources", 7: "level 3: CityWall|Resources",
        8: "level 4: PopGrowth|BorderGrowth", 5: "level 4: PopGrowth|BorderGrowth", 2: "level 5+: Park|SuperUnit", 6: "level 5+: Park|SuperUnit"}
PAIR_LEVEL = {"level 2": 2, "level 3": 3, "level 4": 4, "level 5+": 5}
def longest_logs():
    best = {}
    for f in glob.glob(os.path.join(ROOT, "saves", "*.json")):
        gid = os.path.basename(f)[:36]; d = json.load(open(f))
        if not isinstance(d, dict) or not isinstance(d.get("currentTiles"), list) or not d.get("actions"): continue   # turn-0 map saves have no log
        if gid not in best or len(d["actions"]) > len(best[gid]["actions"]): best[gid] = d
    return best

def city_rewards():
    """City reward choices (bots vs the human), grouped by the pair offered (the reward id fixes the pair), from each game's longest log.
    Also counts how often the city's reward count (initial rewards + earlier CityReward actions) disagrees with the pair's level."""
    out = collections.defaultdict(collections.Counter); check = collections.Counter()
    for gid, d in longest_logs().items():
        st = State(d, "initial"); prior = collections.Counter()
        for y, row in enumerate(d["initialTiles"]):
            for x, t in enumerate(row):
                if t["ImprovementExists"] and t["ImprovementType"] == 1 and t["ImprovementData"]: prior[(x, y)] = len(t["ImprovementData"].get("CityRewards", []))
        for a in d["actions"]:
            if a["type"] != 11: continue
            pl, x, y, r = struct.unpack("<BIIH", bytes.fromhex(a["raw"]))
            prior[(x, y)] += 1; lvl = min(prior[(x, y)] + 1, 5); pair = PAIR.get(r, "other")
            check["agree" if PAIR_LEVEL.get(pair.split(":")[0]) == lvl else "disagree"] += 1
            who = "human" if st.players.get(pl) and st.players[pl].human else "bot"
            out[f"{who} {pair}"][REWARD.get(r, str(r))] += 1
    return out, check

def main():
    ev = ruin_events()
    if "--rows" in sys.argv:
        for r in ev: print(r["game"], r["saves"], "p%d" % r["player"], r["tile"], "turn", r["turn"], r["terrain"], "->", r["reward"])
    res = collections.Counter(r["reward"].split(":")[0] for r in ev)
    clean = collections.Counter(r["reward"].split(":")[0] for r in ev if not r["reward"].startswith("unresolved"))
    land = collections.Counter(r["reward"].split(":")[0] for r in ev if not r["reward"].startswith("unresolved") and not r["water"])
    water = collections.Counter(r["reward"].split(":")[0] for r in ev if not r["reward"].startswith("unresolved") and r["water"])
    early = collections.Counter(r["reward"].split(":")[0] for r in ev if not r["reward"].startswith("unresolved") and r["turn"] <= 7)
    late = collections.Counter(r["reward"].split(":")[0] for r in ev if not r["reward"].startswith("unresolved") and r["turn"] > 7)
    units = collections.Counter(r["reward"].split(":")[1] for r in ev if r["reward"].startswith("unit"))
    keys = ["stars", "tech", "pop", "explorer", "unit"]
    wg = whole_game_techs(); cr, crc = city_rewards()
    out = {
        "about": "Generated by tools/distributions.py from saves/ (do not edit by hand). Counts, sample size n and Wilson 95% intervals. "
                 "Ruin rewards are classified from the saves around each examined ruin (method in the tool's docstring). Ledger: DIST-RUIN-REWARD, DIST-CITY-REWARD.",
        "ruin_reward": {
            "all_events": table(res),
            "resolved": table(clean, keys),
            "resolved_land": table(land, keys),
            "resolved_water": table(water, keys),
            "resolved_turn_le7": table(early, keys),
            "resolved_turn_gt7": table(late, keys),
            "unit_types": dict(units),
            "signal_false_positive": {k: {"fired": BASE[k + " fired"], "n": BASE[k + " n"], "ci95": wilson(BASE[k + " fired"], BASE[k + " n"])} for k in ("explorer", "pop")},
            "uniform_check": "wiki/PolyEnv: uniform over the eligible rewards (5 on land: stars, tech, pop, explorer, unit), 0.2 each",
            "tech_whole_games": {"ruins": wg["ruins"], "free_techs": wg["tech"], "share": round(wg["tech"] / wg["ruins"], 3) if wg["ruins"] else None,
                                 "ci95": wilson(wg["tech"], wg["ruins"]), "players_skipped": wg["players skipped (count doesn't fit)"],
                                 "note": "every game's longest log (single saves included): techs gained without Research per examined ruin"},
        },
        "city_reward_choice": {k: table(v, k.split(": ")[1].split("|")) for k, v in sorted(cr.items())},
        "city_reward_level_check": dict(crc),
    }
    json.dump(out, open(os.path.join(ROOT, "data", "distributions.json"), "w"), indent=1)
    print(f"ruin events {len(ev)}: resolved {sum(clean.values())} {dict(clean)}; unresolved {sum(res.values()) - sum(clean.values())}")
    print("soft-signal false positives:", {k: f"{BASE[k + ' fired']}/{BASE[k + ' n']}" for k in ("explorer", "pop")})
    print(f"whole-game tech share: {wg['tech']}/{wg['ruins']}")
    print("city rewards:", {k: dict(v) for k, v in sorted(cr.items())}, "level check", dict(crc))

if __name__ == "__main__":
    main()
