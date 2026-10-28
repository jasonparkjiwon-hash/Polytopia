"""What-if advisor: the situation of one player in a save, and every legal move with the outcome the forward model predicts.
Plain-language text for someone who does not read code. Engine: sim/pfcore bin `whatif` (src/whatif.rs); docs: sim/README.md "What-if".

    python3 -I tools/whatif.py <save> [--player N] [--all] [--top N] [--no-lookahead] [--no-likely] [--json]
    <save> = the iPhone export (a text file: device path on line 1, base64 below), a raw .state file, a decoded saves/*.json,
             or - to read the pasted export from stdin.
Default player = the human (non-bot) player of the save. Default output = situation + shortlist; --all adds every legal move.
The best attacks and threats also get a "likely reply" line, an ESTIMATE from the bot model (tools/scenario.py; --no-likely skips it).
Compare whole plans with tools/scenario.py. Needs the binary: cd sim/pfcore && cargo build --release --bin whatif   (the script builds it when missing)."""
import base64, hashlib, json, os, re, subprocess, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BIN = os.path.join(ROOT, "sim", "pfcore", "target", "release", "whatif")


# ------------------------------------------------------------------ input
def decode_export(raw_bytes):
    """iPhone export text (path line + base64), or a raw .state, -> (decoded JSON dict, name)."""
    sys.path.insert(0, os.path.join(ROOT, "verify"))
    import state_v123 as S
    name = "pasted"
    try:
        txt = raw_bytes.decode("ascii")
        lines = [l for l in txt.strip().splitlines() if l.strip()]
        if lines and not re.fullmatch(r"[A-Za-z0-9+/=\s]+", lines[0]) or (lines and "/" in lines[0] and ".state" in lines[0]):
            name = lines[0].strip(); lines = lines[1:]
        raw = base64.b64decode("".join(l.strip() for l in lines))
    except (UnicodeDecodeError, ValueError):
        raw = raw_bytes                                  # a binary .state
    st = S.read_state(S.decompress(raw))
    h = st["initial"]["header"]; cur = st["current"]["header"]
    out = {"format": "polytopia-state-json/2", "gameVersion": st["version"], "mapWidth": h["MapWidth"], "mapHeight": h["MapHeight"],
           "currentTurn": cur["CurrentTurn"], "header": {"MapHeaderInput": h}, "currentHeader": cur, "initialTiles": st["initial"]["tiles"],
           "initialPlayers": [p for p in st["initial"]["players"] if p["PlayerId"] != 255],
           "currentTiles": st["current"]["tiles"] if cur["CurrentTurn"] > 0 else st["initial"]["tiles"],
           "currentPlayers": [p for p in st["current"]["players"] if p["PlayerId"] != 255],
           "actions": st["actions"], "actionsProblem": st["actions_problem"], "unparsedBytes": st["unparsed_bytes"]}
    return out, name


def load_input(arg):
    """-> path of a decoded save JSON (written to a cache dir when the input is an export)."""
    data = sys.stdin.buffer.read() if arg == "-" else open(arg, "rb").read()
    if arg != "-" and arg.endswith(".json"):
        return arg
    try:
        d, name = decode_export(data)
    except Exception as e:
        raise SystemExit("could not read this as a Polytopia save export (%s). Paste the whole text again: the first line is the device path, the rest is the base64 block." % str(e)[:120])
    cache = os.environ.get("WHATIF_CACHE") or os.path.join(os.environ.get("TMPDIR", "/tmp"), "whatif_cache")
    os.makedirs(cache, exist_ok=True)
    p = os.path.join(cache, hashlib.sha1(data).hexdigest()[:12] + ".json")
    json.dump(d, open(p, "w"))
    return p


def run_engine(path, player, lookahead):
    if not os.path.exists(BIN):
        print("building the what-if engine (once, about a minute)...", file=sys.stderr)
        subprocess.run(["cargo", "build", "--release", "--bin", "whatif"], cwd=os.path.join(ROOT, "sim", "pfcore"), check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["git", "checkout", "Cargo.lock"], cwd=os.path.join(ROOT, "sim", "pfcore"), stderr=subprocess.DEVNULL)
    cmd = [BIN, path, "--dist", os.path.join(ROOT, "data", "distributions.json")]
    if player is not None: cmd += ["--player", str(player)]
    if not lookahead: cmd.append("--no-lookahead")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode: raise SystemExit("what-if engine failed: " + r.stderr.strip()[:500])
    return json.loads(r.stdout)


# ------------------------------------------------------------------ rule levels
def unverified_map():
    """move kind -> [ledger ids whose rule is below L1] (data/pf_rule_levels.json, written by tools/pf_rule_levels.py)."""
    try:
        d = json.load(open(os.environ.get("WHATIF_RULE_LEVELS") or os.path.join(ROOT, "data", "pf_rule_levels.json")))
    except OSError:
        return {}
    return {k: [x["ledger"] for x in v if x.get("below_L1")] for k, v in d.get("kinds", {}).items()}


# ------------------------------------------------------------------ words
def nice(s):
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", s) if s else s

def n(x):
    if x is None: return "?"
    return str(int(x)) if abs(x - round(x)) < 1e-6 else ("%.1f" % x)

def xy(p):
    return "(%d,%d)" % (p[0], p[1])


def clean_name(nm):
    return bool(nm) and all(ch.isalpha() or ch in " '-." for ch in nm)


class R:
    def __init__(self, d):
        self.d = d; self.s = d["situation"]; self.pov = self.s["player"]
        self.cities = {(c["x"], c["y"]): c for c in self.s["cities"]}
        # city names in the saves sometimes decode to symbols: such a city is called "your city 2" / "enemy city 3" instead
        self.alias = {}
        for i, c in enumerate(self.s["cities"], 1):
            self.alias[(c["x"], c["y"])] = c["name"] if clean_name(c["name"]) else "your city %d" % i
        for i, c in enumerate(self.s["enemy_cities"], 1):
            self.alias[(c["x"], c["y"])] = c["name"] if clean_name(c["name"]) else "%s city %d" % (c["tribe"], i)
        for c in self.s["cities"] + self.s["enemy_cities"]: c["name"] = self.alias[(c["x"], c["y"])]
        self.unv = unverified_map()
        self.cur_targets = {}
        for m in d["moves"]:
            if m["group"] == "attack" and m.get("attack") and m["attack"]["defender"]:
                self.cur_targets.setdefault(tuple(m["src"]), set()).add(tuple(m["target"]))
        self.base_die = {(u["x"], u["y"], u["type"]) for u in d["threats_now"]["units"] if u["can_die"]}

    def near_city(self, x, y):
        best = None
        for (cx, cy), c in self.cities.items():
            dist = max(abs(cx - x), abs(cy - y))
            if best is None or dist < best[0]: best = (dist, c["name"])
        if best is None: return ""
        return "in %s" % best[1] if best[0] == 0 else "%d tile%s from %s" % (best[0], "" if best[0] == 1 else "s", best[1])

    def who(self, owner, tribe, typ):
        return ("your " if owner == self.pov else "enemy %s " % tribe) + nice(typ)

    def events(self, evs, skip_actor_move=False):
        """clauses for the events of a move (own units: 'your X')."""
        out = []
        for e in evs:
            k = e["ev"]
            if k == "hp":
                out.append("%s at %s HP %s→%s" % (self.who(e["owner"], e["tribe"], e["type"]), xy((e["x"], e["y"])), n(e["from"]), n(e["to"])) + (" (heals)" if e["to"] > e["from"] else ""))
            elif k == "gone":
                out.append("%s at %s is destroyed" % (self.who(e["owner"], e["tribe"], e["type"]), xy((e["x"], e["y"]))) if e["owner"] != self.pov or True else "")
            elif k == "new":
                out.append("a new %s%s appears at %s" % ("" if e["owner"] == self.pov else e["tribe"] + " ", nice(e["type"]), xy((e["x"], e["y"]))))
            elif k == "moved":
                if not skip_actor_move or e["owner"] != self.pov:
                    out.append("%s moves %s→%s" % (self.who(e["owner"], e["tribe"], e["type"]), xy(e["from"]), xy(e["to"])))
                if e["hp_to"] != e["hp_from"]: out.append("its HP %s→%s" % (n(e["hp_from"]), n(e["hp_to"])))
            elif k == "became":
                out.append("%s at %s becomes %s%s" % (nice(e["type"]), xy((e["x"], e["y"])), nice(e["to_type"]), "" if e["owner"] == e["new_owner"] else " (changes side)"))
            elif k == "city_new":
                out.append("a new city (level %d) at %s" % (e["level"], xy((e["x"], e["y"]))))
            elif k == "city":
                bits = []
                if e["owner_from"] != e["owner_to"]: bits.append("the city changes owner")
                if e["level_from"] != e["level_to"]: bits.append("level %d→%d" % (e["level_from"], e["level_to"]))
                elif e["pop_from"] != e["pop_to"]: bits.append("population progress %d→%d" % (e["pop_from"], e["pop_to"]))
                if bits: out.append("%s %s: %s" % (self.alias.get((e["x"], e["y"]), "city"), xy((e["x"], e["y"])), ", ".join(bits)))
            elif k == "city_gone":
                out.append("city at %s is gone" % xy((e["x"], e["y"])))
            elif k == "structure":
                a = nice(e["to"]) if e["to"] else None; b = nice(e["from"]) if e["from"] else None
                out.append(("builds %s at %s" % (a, xy((e["x"], e["y"]))) if a and not b else "removes %s at %s" % (b, xy((e["x"], e["y"]))) if b and not a
                            else "%s at %s becomes %s" % (b, xy((e["x"], e["y"])), a)) if (a or b) else "")
            elif k == "resource":
                if e["from"] and not e["to"]: out.append("uses up the %s at %s" % (nice(e["from"]).lower(), xy((e["x"], e["y"]))))
            elif k == "terrain":
                out.append("terrain changes on %d tile%s (e.g. %s %s→%s)" % (e["n"], "" if e["n"] == 1 else "s", xy((e["x"], e["y"])), e["from"], e["to"]))
            elif k == "tech_any":
                out.append("you learn one free tech, picked at random among the %d you could research" % e["n"])
            elif k == "tribe_out":
                out.append("if this was their last city (you cannot see their others), %s is wiped out" % e["tribe"])
            elif k == "tech":
                out.append("you learn %s" % nice(e["tech"]))
            elif k == "relation":
                out.append("relation with %s changes (%s%s)" % (e["tribe"], "at peace" if e["state_to"] == 1 else "not at peace", ", embassy level %d" % e["embassy_to"] if e["embassy_to"] else ""))
        return [o for o in out if o]

    def flags(self, m):
        f = []
        ids = self.unv.get(m["kind"], [])
        if ids: f.append("depends on an unverified rule: " + ", ".join(ids))
        if m.get("random"): f.append("RANDOM")
        if m.get("fog"): f.append("target tile is in the fog: its contents are unknown")
        return f

    def stars_txt(self, m):
        if "stars" not in m: return ""
        b, a = m["stars"]
        if a == b: return ""
        return "stars %d→%d" % (b, a)

    def reply_txt(self, m):
        r = m.get("reply")
        if r is None: return None
        die = [u for u in r["units"] if u["can_die"] and (u["x"], u["y"], u["type"]) not in self.base_die]
        parts = []
        for u in die:
            tag = ""
            seen = []
            for h in u["hits"]:
                t = "%s from %s" % (nice(h["enemy"]), xy(h["from"]))
                if t not in seen: seen.append(t)
            who = ", ".join(seen[:3])
            parts.append("your %s at %s (HP %s) could be killed: %s can reach it, up to %s damage in total%s" % (nice(u["type"]), xy((u["x"], u["y"])), n(u["hp"]), who, n(u["total_dmg"]), tag))
        for c in r["captures"][:2]:
            parts.append("your city at %s could be walked into by an enemy %s" % (xy((c["x"], c["y"])), nice(c["by"])))
        if parts: return parts
        old = [u for u in r["units"] if u["can_die"]]
        return ["nothing new is exposed (worst case over every visible enemy)" + ("; %d of your units %s already at risk before" % (len(old), "was" if len(old) == 1 else "were") if old else "")]

    def line(self, m, brief=False):
        g = m["group"]; a = m.get("actor"); t = m.get("target"); s = m.get("src")
        pos = s or t
        head = ""; body = []
        if g == "attack":
            at = m["attack"]; A = at["attacker"]; D = at["defender"]
            if D is None:
                head = "%s %s attacks the city at %s" % (nice(A["type"]), xy((A["x"], A["y"])), xy(t))
            else:
                head = "%s %s (HP %s/%s) attacks %s %s %s (HP %s/%s)" % (nice(A["type"]), xy((A["x"], A["y"])), n(A["hp"]), n(A["max"]), D["tribe"], nice(D["type"]), xy((D["x"], D["y"])), n(D["hp"]), n(D["max"])) + (", inside a city (its defence bonus is counted)" if D.get("in_city") else "")
                body.append("deals %s damage → %s" % (n(at["dmg_dealt"]), "DESTROYS it" if D["killed"] else "its HP %s→%s" % (n(D["hp"]), n(D["hp_after"]))))
            body.append("YOUR UNIT DIES in the fight (takes %s back)" % n(at["dmg_taken"]) if A["died"] else "takes no damage back" if not at["dmg_taken"] else "takes %s back (HP %s→%s)" % (n(at["dmg_taken"]), n(A["hp"]), n(A["hp_after"])))
            if A["moved_in"]: body.append("then moves in to %s" % xy(t))
            rest = [e for e in m["events"] if not (e["ev"] in ("hp", "gone", "moved", "new") and ((e.get("x"), e.get("y")) in ((A["x"], A["y"]), tuple(t)) or e["ev"] == "moved"))]
            body += self.events(rest)
        elif g == "move":
            head = "%s %s → %s" % (nice(a["type"]), xy(s), xy(t))
            body.append("(%s)" % self.near_city(*t))
            if m.get("explored_new"): body.append("reveals %d new tile%s" % (m["explored_new"], "" if m["explored_new"] == 1 else "s"))
            ta = [x for x in (m.get("then_attack") or []) if (x["x"], x["y"]) not in self.cur_targets.get(tuple(s), set())]
            if ta: body.append("from there it could newly attack: " + "; ".join("%s %s (HP %s) → %s%s" % (nice(x["type"]), xy((x["x"], x["y"])), n(x["hp"]), "kills it" if x["kill"] else "%s damage" % n(x["dmg"]), "" if not x["taken"] else ", takes %s" % n(x["taken"])) for x in ta[:4]))
            if m.get("exposed_to"): body.append("%d enemy unit%s could reach that tile (rough)" % (m["exposed_to"], "" if m["exposed_to"] == 1 else "s"))
            extra = [e for e in m["events"] if e["ev"] != "moved"]
            body += self.events(extra)
        elif g == "train":
            c = self.cities.get(tuple(s)) if s else None
            head = "Train %s in %s" % (nice(m["named"]), c["name"] if c else xy(s))
            nw = next((e for e in m["events"] if e["ev"] == "new"), None)
            body.append("costs %d star%s (stars %d→%d)%s" % (m["cost"], "" if m["cost"] == 1 else "s", m["stars"][0], m["stars"][1], ", the new unit has HP %s and can act next turn" % n(nw["hp"]) if nw else ""))
            body += self.events([e for e in m["events"] if e["ev"] != "new"])
        elif g == "upgrade":
            head = "Upgrade %s %s → %s" % (nice(a["type"]) if a else "unit", xy(s), nice(m["named"]) if m["named"] else "?")
            body += self.events(m["events"])
        elif g == "build":
            head = "Build %s at %s (%s)" % (nice(m["named"]), xy(pos), self.near_city(*pos))
            body += self.events([e for e in m["events"] if not (e["ev"] == "structure" and e["to"] == m["named"])])
        elif g == "research":
            head = "Research %s" % nice(m["named"])
            body.append("costs %d" % m["cost"])
            un = m.get("unlocks") or []
            if un: body.append("unlocks: " + ", ".join(("%s ×%d" % (nice(u["name"]), u["n"]) if u["n"] > 1 else nice(u["name"])) for u in un[:8]))
        elif g == "capture":
            head = "Capture/examine at %s" % xy(pos)
            if m.get("random"):
                head = "Examine the ruins at %s" % xy(pos)
            body += self.events(m.get("events") or [])
        elif g == "harvest":
            res = next((e["from"] for e in m["events"] if e["ev"] == "resource" and e["from"]), None)
            head = "Harvest %sat %s (%s)" % (nice(res).lower() + " " if res else "", xy(pos), self.near_city(*pos))
            body += self.events([e for e in m["events"] if e["ev"] != "resource"])
        elif g == "reward":
            head = "City reward: %s" % nice(m["named"] or "")
            body += self.events(m["events"])
        elif g == "diplomacy":
            who = m["other"]["tribe"] if m.get("other") else "?"
            verb = {"PeaceTreaty": "Offer peace to", "EstablishEmbassy": "Build an embassy with", "BreakPeace": "Break the peace with", "PeaceRequestResponse": "Answer the peace offer from",
                    "DestroyEmbassy": "Destroy the embassy of"}.get(m["kind"], nice(m["kind"]) + " with")
            head = "%s %s" % (verb, who)
            if m["kind"] == "PeaceRequestResponse": head += (": accept" if m["key"].get("target") == 1 else ": decline")
            if m.get("cost"): body.append("costs %d" % m["cost"])
            body += self.events(m["events"])
        elif g == "unit_order":
            head = "%s %s %s" % (nice(m["kind"]), nice(a["type"]) if a else "", xy(s))
            body += self.events(m["events"])
        else:
            head = "%s %s %s" % (nice(m["kind"]), nice(a["type"]) if a else "", xy(s) if s else "")
            if m["named"] and m["named"] != m["kind"]: head += " " + nice(m["named"])
            if t: head += " → " + xy(t)
            body += self.events(m["events"])
        st = self.stars_txt(m)
        if st and g not in ("research", "train"): body.append(st)
        txt = head + (": " + "; ".join(b for b in body if b) if body else "")
        fl = self.flags(m)
        if g == "attack" and not fl: fl = []
        tag = (" [exact]" if g == "attack" and not m.get("fog") else "")
        out = txt + tag + ("".join(" [%s]" % f for f in fl))
        if m.get("random"):
            rows = sorted(m["random"]["outcomes"], key=lambda o: -o["p"])
            out += "\n        RANDOM (measured chance, %s):" % m["random"]["what"].split(" (")[0]
            for o in rows:
                evs = self.events([e for e in o["events"] if e["ev"] != "structure"]); out += "\n          %2d%%  %s: %s" % (round(o["p"] * 100), o["reward"], "; ".join(evs) if evs else "nothing you can see (e.g. an explorer revealing tiles)")
            out += "\n          (in our saves roughly 1 ruin in 12 also turns into a level-3 'Lost City' for you: not in the measured table above)"
        return out


# ------------------------------------------------------------------ report
def likely_map(args, moves):
    """label -> the sampled bot-model reply (ESTIMATE) of each shortlisted move, from the scenario engine; {} when switched off or unavailable."""
    if not moves or getattr(args, "no_likely", False) or not getattr(args, "path", None): return {}
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import scenario as SC
        opts = [{"name": "o%d" % i, "moves": [m["label"]]} for i, m in enumerate(moves)]
        res = SC.run_engine(args.path, args.player, opts, args.likely_k, 1, 1, "v3", [], False)
        return {m["label"]: (o["estimate"]["reply"], o["estimate"]["k"]) for m, o in zip(moves, res["options"]) if "error" not in o}
    except (SystemExit, Exception) as e:
        print("(likely replies not available: %s)" % str(e)[:120], file=sys.stderr)
        return {}


def likely_txt(lk, m):
    got = lk.get(m["label"])
    if not got: return None
    rp, k = got
    att = sorted([u for u in rp["units"] if u["p_attacked"] > 0], key=lambda u: -u["p_attacked"])
    parts = ["your %s at %s attacked %d%% / killed %d%%" % (nice(u["type"]), xy((u["x"], u["y"])), round(100 * u["p_attacked"]), round(100 * u["p_killed"])) for u in att[:3]]
    if not parts: parts = ["none of your units was attacked in any sample"]
    top = rp["top_attacks"][0] if rp["top_attacks"] else None
    tail = "; most likely attack: %s → %s (%d%%)" % (nice(top["enemy"]), nice(top["target"]), round(100 * top["chance"])) if top else ""
    caps = "; chance of losing a city %d%%" % round(100 * rp["p_any_city_lost"]) if rp["p_any_city_lost"] else ""
    return "likely reply (ESTIMATE from the bot model, %d sampled enemy turns; model agreement: bot-model-3.md): %s%s; chance of losing a unit in that reply %d%%, expected %.2f%s" % (
        k, "; ".join(parts), tail, round(100 * rp["p_any_unit_lost"]), rp["lost_units"][0], caps)


def report(d, args):
    r = R(d); s = r.s
    L = []
    L.append("WHAT-IF · %s (player %d)%s · turn %d · stars %d (+%d a turn)" % (s["tribe"], s["player"], " [bot]" if s["is_bot"] else "", s["turn"], s["stars"], s["income"]))
    L.append("Tiles are written (x,y): x = column counted from the left, y = row counted from the top; (0,0) is the top-left corner (map %dx%d, counting from 0). Places also name their nearest city." % (s["map_size"], s["map_size"]))
    if os.environ.get("PF_FLAGS"): L.append("WARNING: rule switches are on (PF_FLAGS=%s): results depend on unverified rules." % os.environ["PF_FLAGS"])
    L.append("")
    L.append("== 1. YOUR SITUATION ==")
    L.append("Techs: " + (", ".join(nice(t) for t in s["techs"]) or "none"))
    L.append("Can research now: " + (", ".join("%s (%d)" % (nice(t["tech"]), t["cost"]) for t in s["researchable"]) or "nothing"))
    L.append("Cities (%d):" % len(s["cities"]))
    for c in s["cities"]:
        fl = [x for x, v in (("capital", c["capital"]), ("walls", c["walls"]), ("workshop", c["workshop"]), ("park", c["park"]), ("BESIEGED", c["besieged"]), ("not connected to the capital", not c["connected"] and not c["capital"])) if v]
        L.append("  %s %s: level %d, growth %d/%d, +%d stars a turn%s" % (c["name"], xy((c["x"], c["y"])), c["level"], c["pop"], c["pop_needed"], c["income"], " (" + ", ".join(fl) + ")" if fl else ""))
    L.append("Units (%d):" % len(s["units"]))
    for u in s["units"]:
        state = "can act" if u["can_act"] else ("already acted" if (u["moved"] or u["attacked"]) else "cannot act now")
        ef = (" " + "/".join(u["effects"])) if u["effects"] else ""
        L.append("  %s%s %s, HP %s/%s, %s%s - %s" % (nice(u["type"]), " (veteran)" if u["vet"] else "", xy((u["x"], u["y"])), n(u["hp"]), n(u["max"]), state, ef, r.near_city(u["x"], u["y"])))
    eu = s["enemy_units"]; ec = s["enemy_cities"]
    L.append("Enemies you can see: %d unit%s, %d city/cities" % (len(eu), "" if len(eu) == 1 else "s", len(ec)))
    byt = {}
    for u in eu: byt.setdefault(u["tribe"] + " (p%d)" % u["owner"], []).append(u)
    for t, us in byt.items():
        peace = next((o["at_peace"] for o in s["others"] if o["id"] == us[0]["owner"]), False)
        L.append("  %s%s: " % (t, " [at peace]" if peace else "") + "; ".join("%s %s HP %s/%s" % (nice(u["type"]), xy((u["x"], u["y"])), n(u["hp"]), n(u["max"])) for u in us[:8]) + (" ..." if len(us) > 8 else ""))
    for c in ec[:8]: L.append("  enemy city %s %s (%s, level %d%s)" % (c["name"], xy((c["x"], c["y"])), c["tribe"], c["level"], ", capital" if c["capital"] else ""))
    ex = s["explored"]
    L.append("Hidden from you: you have explored %d of %d tiles (%d%%). You have met %d of the other %d tribes. Units and cities on tiles you have not explored, and every other tribe's stars, techs and score, are not shown (the advice uses only what you can see)." % (ex[0], ex[1], round(100 * ex[0] / ex[1]), s["tribes_met"], s["tribes_total"] - 1))
    tn = r.d["threats_now"]
    risky = [u for u in tn["units"] if u["can_die"]]
    if tn["units"]:
        L.append("Danger right now (worst case: each visible enemy attacks once, as far as it can reach):")
        for u in tn["units"][:6]:
            L.append("  your %s at %s (HP %s): %d enemy unit%s can hit it for up to %s%s" % (nice(u["type"]), xy((u["x"], u["y"])), n(u["hp"]), u["attackers"], "" if u["attackers"] == 1 else "s", n(u["total_dmg"]), " - COULD BE KILLED" if u["can_die"] else ""))
    else:
        L.append("Danger right now: no visible enemy can attack any of your units next turn.")
    for c in tn["captures"][:3]: L.append("  your city at %s could be entered by an enemy %s" % (xy((c["x"], c["y"])), nice(c["by"])))
    if s["pending_reward"]: L.append("\nA city level-up reward is waiting: pick one first (only these moves are legal).")

    mv = d["moves"]
    top = args.top
    L.append("")
    L.append("== 2. SHORTLIST ==")
    atk = sorted([m for m in mv if m["group"] == "attack" and m.get("attack") and m["attack"]["defender"]], key=lambda m: -m["score"])
    if atk:
        L.append("Best attacks (a kill first, then damage dealt against damage taken). Combat results are EXACT unless a line says otherwise:")
        lk = likely_map(args, atk[:top])
        for i, m in enumerate(atk[:top], 1):
            L.append("  %d. %s" % (i, r.line(m)))
            rp = r.reply_txt(m)
            if rp: L.append("       afterwards, worst case: " + "; ".join(rp))
            lt = likely_txt(lk, m)
            if lt: L.append("       " + lt)
    else:
        L.append("Attacks: none available right now.")
    def newt(m): return [x for x in (m.get("then_attack") or []) if (x["x"], x["y"]) not in r.cur_targets.get(tuple(m["src"]), set())]
    thr = [m for m in mv if m["group"] == "move" and newt(m)]
    def thr_key(m):
        rp = m.get("reply"); risk = bool(rp and any(u["can_die"] and (u["x"], u["y"], u["type"]) not in r.base_die for u in rp["units"])) if rp else False
        return (risk, -sum(1 for x in newt(m) if x["kill"]), -len(newt(m)))
    thr.sort(key=thr_key)
    if thr:
        L.append("Cheapest threats (a move that puts an enemy in reach to attack this turn, safest first):")
        lk = likely_map(args, thr[:top])
        for i, m in enumerate(thr[:top], 1):
            L.append("  %d. %s" % (i, r.line(m)))
            rp = r.reply_txt(m)
            if rp: L.append("       afterwards, worst case: " + "; ".join(rp))
            lt = likely_txt(lk, m)
            if lt: L.append("       " + lt)
    lose = []
    for m in mv:
        if m["group"] == "attack" and m.get("attack") and m["attack"]["attacker"]["died"]:
            lose.append((m, ["the attacking unit dies in the fight itself (exact)"])); continue
        rp = m.get("reply")
        if rp:
            newdie = [u for u in rp["units"] if u["can_die"] and (u["x"], u["y"], u["type"]) not in r.base_die]
            if newdie: lose.append((m, ["%s at %s (HP %s) could be killed afterwards (worst case)" % (nice(u["type"]), xy((u["x"], u["y"])), n(u["hp"])) for u in newdie]))
    L.append("Moves that lose a unit (or leave one exposed), %d found%s:" % (len(lose), "" if len(lose) <= top else ", first %d" % top))
    for m, why in lose[:top]: L.append("  - %s  → %s" % (nice(m["label"]), "; ".join(why)))
    if not lose: L.append("  (none among the moves examined)")

    L.append("")
    L.append("Economy and setup (what you can spend stars on):")
    if not any(m["group"] in ("train", "build", "research", "capture", "harvest") for m in mv): L.append("  nothing available right now (stars %d)." % s["stars"])
    for g, title in (("train", "Train"), ("build", "Build"), ("research", "Research"), ("capture", "Capture / ruins"), ("harvest", "Harvest")):
        ms = [m for m in mv if m["group"] == g]
        if not ms: continue
        L.append("  %s (%d option%s%s):" % (title, len(ms), "" if len(ms) == 1 else "s", "" if args.all or len(ms) <= top else ", showing %d, --all lists all" % top))
        for m in ms[: (len(ms) if args.all else top)]: L.append("    - " + r.line(m))

    if args.all:
        L.append("")
        L.append("== 3. EVERY LEGAL MOVE, by group ==")
        names = {"attack": "Attacks", "move": "Moves", "train": "Trains", "upgrade": "Upgrades", "build": "Builds", "research": "Research", "capture": "Captures", "harvest": "Harvests",
                 "ability": "Special abilities", "diplomacy": "Diplomacy", "unit_order": "Recover / disband", "reward": "City rewards", "other": "Other"}
        for g, title in names.items():
            ms = [m for m in mv if m["group"] == g]
            if not ms: continue
            L.append("%s (%d):" % (title, len(ms)))
            for m in ms: L.append("  - " + r.line(m))
    L.append("")
    L.append("Reading the labels: [exact] = the forward model's number, no dice in combat; RANDOM = a table of measured chances; \"worst case\" = the best the enemies could do against you with the units you can see, not a prediction of what they will do; a rough \"could reach\" ignores terrain.")
    return "\n".join(L)


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("save"); ap.add_argument("--player", type=int); ap.add_argument("--all", action="store_true")
    ap.add_argument("--top", type=int, default=5); ap.add_argument("--no-lookahead", action="store_true"); ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-likely", action="store_true", help="skip the sampled (bot model) likely replies of the shortlist")
    ap.add_argument("--likely-k", type=int, default=12, help="sampled enemy turns per shortlisted move (default 12)")
    args = ap.parse_args(argv)
    path = load_input(args.save)
    args.path = path
    d = run_engine(path, args.player, not args.no_lookahead)
    print(json.dumps(d) if args.json else report(d, args))


if __name__ == "__main__":
    main(sys.argv[1:])
