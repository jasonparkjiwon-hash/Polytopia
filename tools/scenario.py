"""Scenario comparison for one player (what-if-2): play 2-5 candidate move sequences EXACTLY, then sample bot turns forward.

    python3 -I tools/scenario.py <save> --moves "Attack Polytaur (5,16)->(4,16)" "Summon Warrior (4,12)" ["A1; A2" ...] [options]
    python3 -I tools/scenario.py <save> --auto [--top 5]

  <save>     the iPhone export text (or - for stdin), a raw .state, or a decoded saves/*.json (as tools/whatif.py)
  --moves    2-5 options; each option is one move or several joined with ';' (played in that order). Moves are written like the
             lines of `tools/whatif.py --all` (e.g. "Step Warrior (4,9)->(3,8)", "Summon Warrior (4,12)"); a part of a label is
             enough when only one legal move contains it. "nothing" = end the turn without doing anything.
  --auto     builds the options itself from the what-if shortlist (best attacks, safest threats, a train, a build, research, the
             "do nothing" baseline), runs them all and shows the best --top (default 5) by the in-game score they reach.
  --hypo T   "what if" edits of the loaded position, repeatable. Supported: "enemy unit at 4,16 has 5 more HP" (also "less HP", "has
             7 HP", "my unit at ..."), "I have 5 more stars" (or fewer), "Cymanti has 3 more stars", "peace with Cymanti" / "peace with
             player 5", "war with ...". Everything else is refused.
  --k N      sampled futures per option (default 20; each is a full bot turn for every tribe)   --h H  rounds ahead, 1-3 (default 1)
  --player P (default: the human of the save)  --policy v3|v2  --no-win  --json  --seed S

What is exact and what is not: your own moves and their immediate result are the engine's exact numbers (`[exact]`; a ruin is a table
of chances). Everything after your turn is an ESTIMATE from the bot model (policy v3, data/bot_policy_v3.json): K enemy turns are
drawn from it and counted. From round 2 on the model also plays YOUR side. Agreement of the model with real bots:
.scratchpad/investigations/bot-model-3.md. The win-% is the chance to hold the MOST CITIES after H rounds (full information, 90% interval), not to win the game."""
import argparse, json, math, os, re, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import whatif as W

ROOT = W.ROOT
BIN = os.path.join(ROOT, "sim", "pfcore", "target", "release", "scen")
POLICIES = {"v3": "bot_policy_v3.json", "v2": "bot_policy_v2.json"}
HYPO_HELP = ("supported edits: unit HP (\"enemy unit at x,y has N more HP\", \"... N less HP\", \"... has N HP\", also \"my unit at x,y ...\"), "
             "stars (\"I have N more stars\", \"I have N fewer stars\", \"<tribe> has N more stars\"), peace (\"peace with <tribe>\") and war "
             "(\"war with <tribe>\"). Anything else (new units or cities, techs, terrain, other tribes' relations) is refused.")
LABEL = ("estimate from the bot model (policy v3; it picks the same move as a real bot 46% of the time against 29% for a random legal move, "
         "attack targets 89% when it knows the attacker; over one round its counts of attacks and kills are within about 10-20% of the real "
         "bots, over three rounds they run about 20% low)")


def ensure_bin():
    if not os.path.exists(BIN):
        print("building the scenario engine (once, about a minute)...", file=sys.stderr)
        subprocess.run(["cargo", "build", "--release", "--bin", "scen"], cwd=os.path.join(ROOT, "sim", "pfcore"), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["git", "checkout", "Cargo.lock"], cwd=os.path.join(ROOT, "sim", "pfcore"), stderr=subprocess.DEVNULL)


# ------------------------------------------------------------------ hypotheticals
def tribe_ref(txt, d):
    """'Cymanti' / 'player 5' / 'p5' / '5' -> player id (error text if unknown or ambiguous)."""
    t = txt.strip().lower().replace("tribe", "").replace("the", "").strip()
    m = re.fullmatch(r"(?:player|p)?\s*(\d+)", t)
    if m: return int(m.group(1))
    ids = {}
    for o in d["situation"]["others"]: ids.setdefault(o["tribe"].lower(), []).append(o["id"])
    if t in ids and len(ids[t]) == 1: return ids[t][0]
    if t in ids: raise SystemExit("--hypo: %s is ambiguous, players %s; write the player number (e.g. \"peace with player %d\")" % (txt, ids[t], ids[t][0]))
    raise SystemExit("--hypo: no tribe called \"%s\" in this save (tribes: %s)" % (txt, ", ".join(sorted({o["tribe"] for o in d["situation"]["others"]}))))


def parse_hypo(text, d):
    t = " ".join(text.strip().lower().split())
    m = re.fullmatch(r"(enemy|my|your) unit at \(?(\d+)\s*,\s*(\d+)\)? (?:has|with) (?:(\d+) (more|less|fewer|extra) hp|(\d+) hp)", t)
    if m:
        who, x, y = m.group(1), int(m.group(2)), int(m.group(3))
        h = {"op": "unit_hp", "x": x, "y": y, "mine": who != "enemy"}
        if m.group(6): h["set"] = int(m.group(6))
        else: h["delta"] = int(m.group(4)) * (1 if m.group(5) in ("more", "extra") else -1)
        return h
    m = re.fullmatch(r"(?:i|we) have (\d+) (more|extra|less|fewer) stars?", t)
    if m: return {"op": "stars", "tribe": "me", "delta": int(m.group(1)) * (1 if m.group(2) in ("more", "extra") else -1)}
    m = re.fullmatch(r"(?:i|we) have (\d+) stars?", t)
    if m: return {"op": "stars", "tribe": "me", "delta": int(m.group(1)) - d["situation"]["stars"]}
    m = re.fullmatch(r"(.+?) has (\d+) (more|extra|less|fewer) stars?", t)
    if m: return {"op": "stars", "tribe": tribe_ref(m.group(1), d), "delta": int(m.group(2)) * (1 if m.group(3) in ("more", "extra") else -1)}
    m = re.fullmatch(r"(peace|war) with (.+)", t)
    if m: return {"op": m.group(1), "tribe": tribe_ref(m.group(2), d)}
    raise SystemExit("--hypo: cannot do \"%s\". %s" % (text, HYPO_HELP))


# ------------------------------------------------------------------ options
def norm(s): return " ".join(s.lower().split())


def resolve_part(part, labels):
    """Exact label, else the unique legal label containing the text; otherwise the text is passed on and the engine checks it."""
    p = norm(part)
    if p in ("nothing", "do nothing", "pass", "end turn", "endturn"): return None
    ex = [l for l in labels if norm(l) == p]
    if ex: return ex[0]
    sub = [l for l in dict.fromkeys(labels) if p in norm(l)]
    if len(sub) == 1: return sub[0]
    if len(sub) > 1: raise SystemExit("\"%s\" matches %d legal moves (%s%s); write more of the label (see tools/whatif.py --all)" % (part, len(sub), " | ".join(sub[:5]), " ..." if len(sub) > 5 else ""))
    return part


def build_options(specs, d):
    labels = [m["label"] for m in d["moves"]]
    out = []
    for i, spec in enumerate(specs):
        parts = [resolve_part(p, labels) for p in spec.split(";") if p.strip()]
        mv = [p for p in parts if p]
        out.append({"name": "ABCDEFGH"[i], "moves": mv, "text": " + ".join(mv) or "do nothing (end the turn)"})
    return out


def attack_rank(m):
    a = m["attack"]; dfd = a["defender"]
    return ((2 if dfd["killed"] else 0) - (2 if a["attacker"]["died"] else 0), a["dmg_dealt"] * dfd["cost"] / max(dfd["max"], 1) - a["dmg_taken"] * a["attacker"]["cost"] / max(a["attacker"]["max"], 1))


def auto_options(d, top=5):
    """Candidate list for --auto from the what-if data (single moves; economy moves are paired with the best attack)."""
    mv = d["moves"]; r = W.R(d)
    atk = sorted([m for m in mv if m["group"] == "attack" and m.get("attack") and m["attack"]["defender"] and not m["attack"]["attacker"]["died"]], key=attack_rank, reverse=True)
    thr = [m for m in mv if m["group"] == "move" and m.get("then_attack")]
    thr.sort(key=lambda m: (m.get("exposed_to", 0), -len(m["then_attack"])))
    trains = sorted([m for m in mv if m["group"] == "train" and m["kind"] == "Summon"], key=lambda m: -m["cost"])
    builds = [m for m in mv if m["group"] == "build"]
    research = sorted([m for m in mv if m["group"] == "research"], key=lambda m: m["cost"])
    caps = [m for m in mv if m["group"] == "capture"]
    cand = [[]]                                         # baseline: do nothing
    cand += [[m["label"]] for m in caps[:2]]
    cand += [[m["label"]] for m in atk[:3]]
    cand += [[m["label"]] for m in thr[:2]]
    if trains: cand += [[trains[0]["label"]]] + ([[trains[-1]["label"]]] if trains[-1]["label"] != trains[0]["label"] else [])
    if atk and trains: cand.append([atk[0]["label"], trains[0]["label"]])
    if builds: cand.append([builds[0]["label"]])
    if research: cand.append([research[0]["label"]])
    seen, out = set(), []
    for c in cand:
        k = tuple(c)
        if k in seen: continue
        seen.add(k); out.append(c)
    return [{"name": "ABCDEFGHIJKL"[i], "moves": c, "text": " + ".join(c) or "do nothing (end the turn)"} for i, c in enumerate(out[:10])]


# ------------------------------------------------------------------ engine
def run_engine(path, player, opts, k, h, seed, policy, hypos, want_feats):
    ensure_bin()
    job = {"k": k, "h": h, "seed": seed, "policy": os.path.join(ROOT, "data", POLICIES[policy]), "dist": os.path.join(ROOT, "data", "distributions.json"),
           "threads": os.cpu_count() or 4, "hypos": hypos, "feats": want_feats, "options": [{"name": o["name"], "moves": o["moves"]} for o in opts]}
    if player is not None: job["player"] = player
    with tempfile.TemporaryDirectory() as tmp:
        jf = os.path.join(tmp, "job.json"); json.dump(job, open(jf, "w"))
        r = subprocess.run([BIN, path, jf], capture_output=True, text=True, cwd=ROOT)
    if r.returncode: raise SystemExit("scenario engine failed: " + r.stderr.strip()[:600])
    return json.loads(r.stdout)


# ------------------------------------------------------------------ win-%
def win_estimates(res, H, pov):
    """Per option, for the subject: chance of holding the MOST CITIES H rounds later (win-pct-3 label 'power'): the sampled futures (full
    information, from the save: CHEATING for a fogged game) stacked with the static eval; 90% interval, trust note. tools/winpct_est.py."""
    try:
        import winpct_est as WE
    except Exception:
        return None
    out = {}
    for o in res["options"]:
        if "error" in o or not o.get("feats_h") or not o.get("tribe_names"): continue
        names = {i: {"tribe": n, "bot": True} for i, n in o["tribe_names"].items()}
        e = WE.estimate(o["start_feats"], names, H, "full", player=pov, ends=o["feats_h"], seed=1)
        r = e[str(pov)]; N = len(o["feats_h"])
        out[o["name"]] = {"est": r["est"], "lo": r["lo"], "hi": r["hi"], "n": N, "trust": r["trust"], "model_sd": r["model_sd"], "playout_sd": r["playout_sd"], "lag": r["lag"]}
    return out


# ------------------------------------------------------------------ words
def pc(x): return "%d%%" % round(100 * x)

def rng(a, nd=1):
    """[mean, p10, p90, se] -> '3.2 (2-5)'"""
    f = lambda v: (("%.*f" % (nd, v)).rstrip("0").rstrip(".") if nd else "%d" % round(v)).replace("-0", "0") if abs(v) < 0.005 else (("%.*f" % (nd, v)).rstrip("0").rstrip(".") if nd else "%d" % round(v))
    return "%s (%s-%s)" % (f(a[0]), f(a[1]), f(a[2]))


def option_text(o, r, d, H, win, base):
    L = []
    nm = o["name"]
    L.append("[%s] %s" % (nm, o["text"]))
    if "error" in o:
        L.append("   cannot be played: " + o["error"]); return L
    ex, es = o["exact"], o["estimate"]
    # exact part
    for st in ex["steps"]:
        ev = r.events(st["events"])
        L.append("   exactly: %s → %s [exact]" % (W.nice(st["label"]), "; ".join(e for e in ev if e) or "no visible change"))
    if not ex["steps"]: L.append("   exactly: nothing changes now; the turn ends with the units where they are.")
    L.append("   you then hold %d stars; units: %s" % (ex["stars"], ", ".join("%s %s HP %s" % (W.nice(u["type"]), W.xy((u["x"], u["y"])), W.n(u["hp"])) for u in ex["my_units"][:8]) + (" ..." if len(ex["my_units"]) > 8 else "")))
    dg = ex["danger"]
    risky = [u for u in dg["units"] if u["can_die"]]
    if risky:
        L.append("   danger, worst case [exact, what visible enemies could do to you if they all go for it]: " + "; ".join(
            "%s at %s (HP %s) could be killed by %d unit%s (up to %s damage)" % (W.nice(u["type"]), W.xy((u["x"], u["y"])), W.n(u["hp"]), u["attackers"], "" if u["attackers"] == 1 else "s", W.n(u["total_dmg"])) for u in risky[:4]))
    else:
        L.append("   danger, worst case [exact]: no visible enemy can kill any of your units next turn.")
    for c in dg["captures"][:2]: L.append("   danger [exact]: an enemy %s could walk into your city at %s." % (W.nice(c["by"]), W.xy((c["x"], c["y"]))))
    # estimate part
    rp = es["reply"]
    L.append("   %s - %d sampled enemy turns:" % ("ESTIMATE", es["k"]))
    att = [u for u in rp["units"] if u["p_attacked"] > 0]
    att.sort(key=lambda u: -u["p_attacked"])
    if att:
        L.append("     chance each unit is attacked next turn: " + "; ".join(
            "%s %s %s (killed %s)" % (W.nice(u["type"]), W.xy((u["x"], u["y"])), pc(u["p_attacked"]), pc(u["p_killed"])) for u in att[:5]) + (" ..." if len(att) > 5 else ""))
    else:
        L.append("     none of your units was attacked in any sample.")
    cs = [c for c in rp["cities"] if c["p_unit_in_it_attacked"] > 0 or c["p_captured"] > 0]
    for c in cs[:3]:
        L.append("     your city at %s: unit in it attacked %s, city captured %s" % (W.xy((c["x"], c["y"])), pc(c["p_unit_in_it_attacked"]), pc(c["p_captured"])))
    L.append("     expected losses in the enemy reply: %s unit%s (%s unit-cost), chance of losing at least one %s%s" % (
        rng(rp["lost_units"], 2), "" if rp["lost_units"][0] == 1 else "s", rng(rp["lost_value"]), pc(rp["p_any_unit_lost"]),
        ", chance of losing a city %s" % pc(rp["p_any_city_lost"]) if rp["p_any_city_lost"] else ""))
    if rp["top_attacks"]:
        t = rp["top_attacks"][0]
        L.append("     most likely attack: enemy %s hits your %s (%s of samples)%s" % (W.nice(t["enemy"]), W.nice(t["target"]), pc(t["chance"]),
                 "; next: " + "; ".join("%s → %s (%s)" % (W.nice(x["enemy"]), W.nice(x["target"]), pc(x["chance"])) for x in rp["top_attacks"][1:3]) if len(rp["top_attacks"]) > 1 else ""))
    # tribes after H rounds
    mine = es["tribes"][str(r.pov)]
    last = mine["rounds"][H - 1]
    s0 = mine["start"]
    L.append("     you after %d round%s (mean, 10th-90th percentile of the samples): units %s (now %s), cities %s (now %s), stars %s (now %s), score %s (the saved score is not comparable with the later ones, so compare the options)" % (
        H, "" if H == 1 else "s", rng(last["units"]), W.n(s0["units"]), rng(last["cities"]), W.n(s0["cities"]), rng(last["stars"]), W.n(s0["stars"]), rng(last["score"], 0)))
    for tid, t in es["tribes"].items():
        if int(tid) == r.pov: continue
        l2 = t["rounds"][H - 1]
        L.append("     %s (p%s, near you) after %d: units %s (now %s), cities %s (now %s), score %s" % (t["tribe"], tid, H, rng(l2["units"]), W.n(t["start"]["units"]), rng(l2["cities"]), W.n(t["start"]["cities"]), rng(l2["score"], 0)))
    if win and nm in win:
        w = win[nm]
        L.append("     chance you hold the most cities after %d round%s: %s (90%% interval %s-%s; %d sampled futures) [ESTIMATE, full information; not the chance to win the game]" % (
            H, "" if H == 1 else "s", pc(w["est"]), pc(w["lo"]), pc(w["hi"]), w["n"]))
        L.append("       trust: " + w["trust"])
    return L


def verdict(o, base, H, r):
    """One plain line: what this option does compared with 'do nothing' (the first option if it is the baseline, else the first option)."""
    if "error" in o: return "cannot be played"
    es, rp = o["estimate"], o["estimate"]["reply"]
    me = es["tribes"][str(r.pov)]["rounds"][H - 1]
    bits = []
    ex = o["exact"]["steps"]
    kills = sum(1 for st in ex for e in st["events"] if e["ev"] == "gone" and e["owner"] != r.pov)
    mine_lost = sum(1 for st in ex for e in st["events"] if e["ev"] == "gone" and e["owner"] == r.pov)
    if kills: bits.append("kills %d enemy unit%s now" % (kills, "" if kills == 1 else "s"))
    if mine_lost: bits.append("LOSES %d of your own unit%s in the fight" % (mine_lost, "" if mine_lost == 1 else "s"))
    bits.append("%s chance to lose a unit next turn" % pc(rp["p_any_unit_lost"]))
    if base and base is not o and "error" not in base:
        b = base["estimate"]["tribes"][str(r.pov)]["rounds"][H - 1]
        d = me["score"][0] - b["score"][0]
        se = math.hypot(me["score"][3], b["score"][3])
        bits.append("score after %d round%s %+.1f vs %s (±%.1f)%s" % (H, "" if H == 1 else "s", d, "option " + base["name"], 1.96 * se, " - no clear difference" if abs(d) <= 1.96 * se else ""))
    return ", ".join(bits)


def score_key(o, H, r):
    if "error" in o: return -1e9
    return o["estimate"]["tribes"][str(r.pov)]["rounds"][H - 1]["score"][0]


def table(opts, res_by, win, H, r):
    hdr = ["", "now (exact)", "lose unit", "units lost", "H=%d units" % H, "cities", "stars", "score", "near enemy units", "lead %"]
    rows = [hdr]
    for o in opts:
        x = res_by[o["name"]]
        if "error" in x: rows.append([o["name"], "cannot be played"] + [""] * 8); continue
        es = x["estimate"]; me = es["tribes"][str(r.pov)]["rounds"][H - 1]
        near = [t for k, t in es["tribes"].items() if int(k) != r.pov]
        nu = sum(t["rounds"][H - 1]["units"][0] for t in near)
        n0 = sum(t["start"]["units"] for t in near)
        ex = x["exact"]["steps"]
        kills = sum(1 for st in ex for e in st["events"] if e["ev"] == "gone" and e["owner"] != r.pov)
        now = ("%d kill%s" % (kills, "" if kills == 1 else "s") if kills else "no kill") + ", %d stars" % x["exact"]["stars"]
        rows.append([x["name"], now, pc(es["reply"]["p_any_unit_lost"]), "%.2f" % es["reply"]["lost_units"][0], "%.1f" % me["units"][0], "%.1f" % me["cities"][0], "%.1f" % me["stars"][0], "%.0f" % me["score"][0],
                     "%.1f→%.1f" % (n0, nu) if near else "-", (pc(win[o["name"]]["est"]) if win and o["name"] in win else "-")])
    w = [max(len(row[i]) for row in rows) for i in range(len(hdr))]
    return ["  " + "  ".join(c.ljust(w[i]) for i, c in enumerate(row)) for row in rows]


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("save"); ap.add_argument("--player", type=int); ap.add_argument("--moves", nargs="+"); ap.add_argument("--auto", action="store_true")
    ap.add_argument("--hypo", action="append", default=[]); ap.add_argument("--k", type=int, default=20); ap.add_argument("--h", type=int, default=1)
    ap.add_argument("--top", type=int, default=5); ap.add_argument("--policy", default="v3", choices=sorted(POLICIES)); ap.add_argument("--no-win", action="store_true")
    ap.add_argument("--json", action="store_true"); ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args(argv)
    if bool(a.moves) == bool(a.auto): ap.error("give either --moves ... or --auto")
    if not 1 <= a.h <= 3: ap.error("--h must be 1, 2 or 3 (the bot model drifts after about 3 rounds)")
    if a.moves and not 2 <= len(a.moves) <= 5: ap.error("--moves takes 2 to 5 options")
    path = W.load_input(a.save)
    d = W.run_engine(path, a.player, False)                    # position + exact outcome of every legal move (no replies: fast)
    r = W.R(d)
    hypos = [parse_hypo(t, d) for t in a.hypo]
    if hypos and a.auto:                                       # shortlist must come from the edited position: the legal moves are the same, the numbers are re-run below
        pass
    opts = auto_options(d, a.top) if a.auto else build_options(a.moves, d)
    res = run_engine(path, a.player or r.pov, opts, a.k, a.h, a.seed, a.policy, hypos, not a.no_win)
    by = {o["name"]: o for o in res["options"]}
    win = None if a.no_win else win_estimates(res, a.h, r.pov)
    if a.auto:                                                  # rank by the mean in-game score they reach, show the best --top (the baseline stays for comparison)
        ranked = sorted(opts, key=lambda o: -score_key(by[o["name"]], a.h, r))
        keep = ranked[:a.top]
        base = next((o for o in opts if not o["moves"]), None)
        if base and base not in keep: keep.append(base)
        opts = keep
    if a.json:
        print(json.dumps({"options": opts, "result": res, "win": win})); return
    s = d["situation"]
    base = next((by[o["name"]] for o in opts if not o["moves"]), by[opts[0]["name"]])
    L = ["SCENARIOS · %s (player %d) · turn %d · stars %d (+%d a turn) · %d options%s" % (s["tribe"], s["player"], s["turn"], s["stars"], s["income"], len(opts), " (picked by --auto, best first)" if a.auto else ""),
         "Tiles are written (x,y): x = column from the left, y = row from the top; (0,0) is the top-left corner. Places also name the nearest city."]
    if res["hypos"]:
        L.append("HYPOTHETICAL position (edited, not the real game): " + "; ".join(res["hypos"]))
    L += ["How to read it: lines marked [exact] are the engine's own numbers for your moves (combat has no dice).",
          "Lines under ESTIMATE are drawn from the bot model: %d sampled enemy turns for each of the other %d tribes, %d round%s ahead (from round 2 the model also plays your side)." % (res["k"], len(s["others"]), a.h, "" if a.h == 1 else "s"),
          "Everything under ESTIMATE is an " + LABEL + ". Ranges are the 10th-90th percentile of the samples; they show how much the futures differ, not model error.", ""]
    for o in opts:
        x = by[o["name"]]
        x["text"] = o["text"]
        L += option_text(x, r, d, a.h, win, base)
        L.append("   verdict: " + verdict(x, base if base is not x else None, a.h, r))
        L.append("")
    L.append("== COMPARISON (H=%d round%s, K=%d; 'now' is exact, every other column is an ESTIMATE) ==" % (a.h, "" if a.h == 1 else "s", res["k"]))
    L += table(opts, by, win, a.h, r)
    if not a.no_win: L.append("lead %% = chance to hold the MOST CITIES after %d round%s (ties: strongest army, then score): sampled futures stacked with the static model fitted on the real games, 90%% interval and calibration in .scratchpad/investigations/win-pct.md. FULL INFORMATION (reads the save's hidden state): an upper bound for a fogged game, and NOT the chance to win the game." % (a.h, "" if a.h == 1 else "s"))
    L.append("(%.1f s; seed %d)" % (res["secs"], a.seed))
    print("\n".join(L))


if __name__ == "__main__":
    main(sys.argv[1:])
