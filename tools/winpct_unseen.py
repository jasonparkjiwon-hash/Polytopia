"""Belief mode with unseen opponents (win-pct-2). Pure stdlib. Needs the pfwin build.

  python3 -I tools/winpct_unseen.py bank            tribe profiles of every saved checkpoint -> data/win_bank.json
  python3 -I tools/winpct_unseen.py run H N VARIANT [POLICY]   playouts for the held/tuned points with a lag-H point; VARIANT in
        full | belief | noscore | score | oracle_cities | oracle_all   -> $WINPCT_CACHE/pb_H_VARIANT_POLICY.json
  python3 -I tools/winpct_unseen.py report H [POLICY]  Brier / reliability of each variant against the real leader at t+H
Variants: full = full information (the save's hidden map and armies); belief = map sampled, opponents only what is visible (+ a lone
Warrior at sampled capitals; the old belief mode); noscore / score = unseen cities and armies drawn from the profile bank (score
also conditions on the scoreboard score of met tribes); oracle_* = the TRUE number of cities (and units) is given, placement and
unit types still drawn (diagnostic: how much a perfect count would buy). Games in HELD plus the game itself are never in the bank
for that state. See .scratchpad/investigations/win-pct.md (belief section)."""
import os, sys, json, collections, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import winpct_lib as W
import winpct_eval as E

CACHE = E.CACHE

def cmd_bank():
    jobs, meta = [], {}
    for gid, ts in E.saves().items():
        for t, f in ts.items():
            pl, _ = W.save_info(f)
            tag = f"{gid[:8]}|{t}"
            jobs.append({"tag": tag, "start": f, "player": pl, "state_only": True, "game": gid[:8]})
    profs = []
    for r in W.run(jobs):
        if "error" in r or not r.get("profiles"): continue
        profs += [p for p in r["profiles"] if p["bot"]]
    json.dump({"about": "tribe profiles (bot tribes) at every saved checkpoint; used by pfwin belief mode (unseen.rs); exclude test games at run time",
               "profiles": profs}, open(W.BANK, "w"), separators=(",", ":"))
    print(len(profs), "profiles ->", W.BANK, os.path.getsize(W.BANK) // 1024, "KB")

def pb_name(H, variant, policy): return os.path.join(CACHE, "pb_%d_%s_%s.json" % (H, variant, policy))

def policy_path(policy): return os.path.join(W.ROOT, "data", "bot_policy_%s.json" % policy)

def points_for(H):
    states = json.load(open(os.path.join(CACHE, "states.json")))
    return states, [(g, t) for g, t, f, y in E.points(states, H, "score")]

def cmd_run(H, n, variant, policy="v2", games=None):
    states, pts = points_for(H)
    jobs = []
    for g, t in pts:
        if games and g not in games: continue
        v = states["%s|%d" % (g, t)]
        j = {"tag": "%s|%d" % (g, t), "start": os.path.join(W.ROOT, "saves", "%s_t%d.json" % (E.full_id(g), t)), "player": v["player"], "playouts": n,
             "horizon": H, "snap_hs": [H], "seed": 1}
        if variant != "full":
            j["belief_pov"] = v["player"]
            if variant != "belief": j["unseen"] = variant; j["bank_exclude"] = list(E.HELD) + [g]
        jobs.append(j)
    name = pb_name(H, variant, policy)
    out = json.load(open(name)) if os.path.exists(name) else {}
    jobs = [j for j in jobs if j["tag"] not in out]
    ix = [E.FI[k] for k in E.KEEP]; secs = 0.0; k = 0
    import concurrent.futures as cf
    with cf.ThreadPoolExecutor(4) as ex:
        for r in ex.map(lambda j: W.run([j], 1, policy_path(policy))[0], jobs):
            k += 1
            if "error" in r: print("ERR", r["tag"], r["error"], flush=True); continue
            out[r["tag"]] = {str(H): {t: [[pl[0][t][i] for i in ix] for pl in r["playouts"]] for t in r["tribes"]}}
            secs += r["secs"]
            if k % 10 == 0: json.dump(out, open(name, "w")); print(variant, k, "of", len(jobs), "cpu-s %.0f" % secs, flush=True)
    json.dump(out, open(name, "w"))
    print(variant, len(out), "states, cpu-s %.0f" % secs, flush=True)

def brier_rows(play, states, H, policy_blend=None):
    """{(split): [(p, y)]} for the playout share of each variant file."""
    tuned = E.tuned_games(states)
    rows = {"tuned": [], "held": []}
    for g, t, f, y in E.points(states, H, "score"):
        tag = "%s|%d" % (g, t)
        if tag not in play: continue
        pp, _ = E.play_probs(play, tag, H, "score")
        rows["tuned" if g in tuned else "held"].append((g, t, f, y, pp))
    return rows

def cmd_report(H, policy="v2", variants=("full", "belief", "noscore", "score", "oracle_cities", "oracle_all")):
    states = json.load(open(os.path.join(CACHE, "states.json")))
    tuned = E.tuned_games(states)
    plays = {v: json.load(open(pb_name(H, v, policy))) for v in variants if os.path.exists(pb_name(H, v, policy))}
    common = None
    for v, pl in plays.items(): common = set(pl) if common is None else common & set(pl)
    print("H=%d policy=%s; states common to all variants: %d" % (H, policy, len(common or [])))
    cache = {}
    def static_w(g):
        if g not in cache: cache[g] = E.fit_softmax([p for p in E.points(states, H, "score") if p[0] in tuned and p[0] != g], E.PHI)
        return cache[g]
    res = collections.defaultdict(lambda: collections.defaultdict(list))   # name -> split -> [(p, y)]
    gamepairs = collections.defaultdict(lambda: collections.defaultdict(list))
    rowsets = {}
    for g, t, f, y in E.points(states, H, "score"):
        tag = "%s|%d" % (g, t)
        if common is not None and tag not in common: continue
        sp = "tuned" if g in tuned else "held"
        alive = [i for i in f if W.alive(f[i])]
        pr = {"uniform": E.uniform(f), "static": W.softmax_probs(static_w(g), f)}
        for v, pl in plays.items():
            pp, _ = E.play_probs(pl, tag, H, "score")
            pr[v] = pp
            pr[v + "+static"] = {i: 0.5 * pp[i] + 0.5 * pr["static"][i] for i in f}
        for name, p in pr.items():
            for i in alive: res[name][sp].append((p[i], y.get(i, 0.0)))
    names = ["uniform", "static"] + [x for v in plays for x in (v, v + "+static")]
    print("%-22s %-22s %-22s" % ("", "tuned Brier (n pairs)", "held Brier (n pairs)"))
    for nm in names:
        c = []
        for sp in ("tuned", "held"):
            r = res[nm][sp]
            c.append("%.4f (%d)" % (W.brier(r), len(r)) if r else "-")
        print("%-22s %-22s %-22s" % (nm, c[0], c[1]))
    for v in plays:
        r = res[v]["tuned"] + res[v]["held"]
        print("reliability %-14s" % v, "; ".join("[%.2f,%.2f) n=%d pred %.3f obs %.3f" % x for x in W.reliability(r)))

if __name__ == "__main__":
    c = sys.argv[1] if len(sys.argv) > 1 else ""
    if c == "bank": cmd_bank()
    elif c == "run": cmd_run(int(sys.argv[2]), int(sys.argv[3]), sys.argv[4], sys.argv[5] if len(sys.argv) > 5 else "v2")
    elif c == "report": cmd_report(int(sys.argv[2]), sys.argv[3] if len(sys.argv) > 3 else "v2")
    else: print(__doc__)
