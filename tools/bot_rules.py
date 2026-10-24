"""Predictive rules for built-in bot behaviour, each scored on the training games and on the held-out games (data/holdout.json)
separately. Writes data/bot_rules.json (rule text, n, hits, baseline, Wilson 95%). Groundwork for Phase 6; pure stdlib.
Usage: python3 -I tools/bot_attacks.py && python3 -I tools/bot_rules.py   (reads data/bot_attacks.csv; run restore_saves.sh first)

Rules (ledger ids BOT-*):
  BOT-RESEARCH-OPENER  first tech a bot researches, from its start techs and the 3x3 around its capital (initialTiles)
  BOT-ATTACK-DECISION  whether a unit that has a target in range attacks (in place or after a move) at its first action
  BOT-ATTACK-TARGET    which target an attacking unit hits, among 2+ on our list"""
import sys, os, json, glob, collections, struct, csv
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "engine")); sys.path.insert(0, os.path.join(ROOT, "tools"))
import replay as R
from state import State, TECH, TERRAIN
from economy import UNIT_COST
from distributions import longest_logs, wilson
from bot_attacks import parse, holdout_games

RES = {int(k): v for k, v in json.load(open(os.path.join(ROOT, "verify", "game_enums.json")))["ResourceType"].items()}

def around_capital(tiles, x0, y0):
    c = collections.Counter()
    for y in range(y0 - 1, y0 + 2):
        for x in range(x0 - 1, x0 + 2):
            if not (0 <= y < len(tiles) and 0 <= x < len(tiles[0])): continue
            t = tiles[y][x]; ter = TERRAIN.get(t["Terrain"], t["Terrain"])
            if t.get("ResourceExists"): c[RES.get(t["ResourceType"])] += 1
            if ter in ("Forest", "Mountain", "Water", "Ocean"): c[ter] += 1
    return c

def opener(tribe, c, techs):
    """BOT-RESEARCH-OPENER. Returns the predicted first tech (or a tuple of accepted ones)."""
    if tribe == "Aquarion": return ("47",)                       # its tribe tech (id 47, name not in our enum)
    if tribe == "Polaris": return ("IceFishing", "Sledding")
    water = c["Water"] + c["Ocean"]; metal = c["Metal"]
    mine = "Climbing" in techs or "Smithery" in techs           # XinXi / Vengir start techs open Mining
    if mine and (metal >= 2 or metal >= 1 and not water): return ("Mining",)
    if water and "Fishing" not in techs: return ("Fishing",)
    if c["Fruit"] >= 2 and "Organization" not in techs: return ("Organization",)
    if c["Game"] >= 2 and "Hunting" not in techs: return ("Hunting",)
    if metal and not mine: return ("Climbing",)
    return ("Riding",)

def opener_rows():
    out = []
    for gid, d in sorted(longest_logs().items()):
        st = State(d, "initial"); first = {}
        for a in d["actions"]:
            if a["type"] == 8:
                v = struct.unpack(R.FMT[8], bytes.fromhex(a["raw"])); first.setdefault(v[0], str(TECH.get(v[1], v[1])))
        for pl, p in st.players.items():
            caps = [q for q, o in st.city.items() if o == pl]
            if p.human or pl not in first or not caps: continue
            c = around_capital(d["initialTiles"], *caps[0])
            out.append(dict(game=gid[:8], tribe=p.tribe, first=first[pl], pred=opener(p.tribe, c, p.techs)))
    return out

def attack_feats(r):
    cs = parse(r)
    return dict(kill=any(c["kill"] for c in cs), best=max(c["dmg"] - c["ret"] for c in cs), city=r["ucity"] == "1", dfd=r["utype"] == "Defender")

def attack_decision(f):
    """BOT-ATTACK-DECISION: attacks unless it stands in its own city or is a Defender."""
    return not f["city"] and not f["dfd"]

def target_key(c):
    """BOT-ATTACK-TARGET: a kill first, then the least return damage, then the most expensive target."""
    return (c["kill"], -c["ret"], UNIT_COST.get(c["type"]) or 0)

def score(hits, n, base):
    return dict(n=n, hits=round(hits, 1), rate=round(hits / n, 3) if n else None, wilson95=wilson(round(hits), n), baseline=round(base / n, 3) if n else None)

def main():
    held = holdout_games(); out = {"about": __doc__.split("\n")[0] + " See .scratchpad/investigations/sim-dist.md.", "rules": {}}
    att = list(csv.DictReader(open(os.path.join(ROOT, "data", "bot_attacks.csv"))))
    ops = opener_rows()
    for split, sel in (("training", lambda g: g not in held), ("held_out", lambda g: g in held)):
        o = [r for r in ops if sel(r["game"])]
        fish = sum(r["first"] == "Fishing" for r in o)
        out["rules"].setdefault("BOT-RESEARCH-OPENER", {"rule": opener.__doc__.split(". ")[0], "baseline": "always Fishing"})[split] = \
            score(sum(r["first"] in r["pred"] for r in o), len(o), fish)
        first = [r for r in att if sel(r["game"]) and r["kind"] == "first"]
        ys = [r["outcome"] in ("attack", "move_attack") for r in first]; fs = [attack_feats(r) for r in first]
        hit = sum(attack_decision(f) == y for f, y in zip(fs, ys))
        rec = out["rules"].setdefault("BOT-ATTACK-DECISION", {"rule": attack_decision.__doc__.split(": ")[1], "baseline": "majority class"})
        rec[split] = score(hit, len(ys), max(sum(ys), len(ys) - sum(ys)))
        tab = collections.defaultdict(lambda: [0, 0])
        for f, y in zip(fs, ys):
            k = ("own city" if f["city"] else "Defender" if f["dfd"] else "field") + (", kill available" if f["kill"] else ", no kill")
            tab[k][0] += y; tab[k][1] += 1
        rec[split]["attack_rate_by_case"] = {k: dict(attacked=v[0], n=v[1], wilson95=wilson(*v)) for k, v in sorted(tab.items())}
        multi = [r for r in att if sel(r["game"]) and r["kind"] == "attack" and int(r["outcome"]) >= 0 and len(parse(r)) >= 2]
        hit = rnd = 0
        for r in multi:
            cs = parse(r); m = max(target_key(c) for c in cs); top = [i for i, c in enumerate(cs) if target_key(c) == m]
            hit += (int(r["outcome"]) in top) / len(top); rnd += 1 / len(cs)
        rec = out["rules"].setdefault("BOT-ATTACK-TARGET", {"rule": target_key.__doc__.split(": ")[1], "baseline": "uniform random among targets"})
        rec[split] = score(hit, len(multi), rnd)
        for mv, lab in (("", "in_place"), ("moved", "after_move")):
            sub = [r for r in multi if r["note"] == mv]; h = b = 0
            for r in sub:
                cs = parse(r); m = max(target_key(c) for c in cs); top = [i for i, c in enumerate(cs) if target_key(c) == m]
                h += (int(r["outcome"]) in top) / len(top); b += 1 / len(cs)
            rec[split][lab] = score(h, len(sub), b)
    json.dump(out, open(os.path.join(ROOT, "data", "bot_rules.json"), "w"), indent=1)
    for k, v in out["rules"].items():
        print(k, "|", " | ".join(f"{s}: {v[s]['hits']}/{v[s]['n']} (baseline {v[s]['baseline']})" for s in ("training", "held_out")))
    print("-> data/bot_rules.json")

if __name__ == "__main__":
    main()
