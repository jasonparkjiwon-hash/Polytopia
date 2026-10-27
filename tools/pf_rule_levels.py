"""Label the rules Polyfish (sim/pfcore) applies with ledger ids and levels, like tools/rule_levels.py does for engine/.
  python3 -I tools/pf_rule_levels.py           write data/pf_rule_levels.json
  python3 -I tools/pf_rule_levels.py --check   exit 1 if a v123 correction or move kind has an id missing from the ledger
Three parts:
  kinds   rule family of each move (src/api.rs kind(): move type, ability name, Upgrade) -> the ledger ids it applies.
          "UPSTREAM" in a list = Polyfish v115 logic no ledger entry covers yet (counted as unlabelled).
  v123    each bullet of sim/README.md "v123 corrections" -> its bracketed ledger ids (parsed, not hand-kept).
  flags   src/v123_flags.rs switches (below-L1 rules, off by default) -> ledger id.
A run's moves by kind (pfreplay output "kinds") then name the below-L1 rules it touched: tools/pf_accept.py."""
import sys, os, re, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rule_levels import level_rank
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT = os.path.join(ROOT, "data", "pf_rule_levels.json")

PUSH = ["PUSH-DIRECTION", "PUSH-TIEBREAK", "PUSH-NEVER-MOVED", "PUSH-PORT-FIRST", "PUSH-ONTO-PORT", "SAVE-UNIT-FACING"]
KINDS = {   # api::kind -> ledger ids (hand map: what each move's code path decides)
    "Step": ["MOVE-BASE", "ALGAE-MOVE", "SKATE-MOVE", "PORT-STEP", "PORT-BOARDS", "AMPHIBIOUS-WATER", "SWIFT-MOVE", "MOVE-BLOCKED-HIDDEN",
             "GIANT-JUGGERNAUT", "STOMP-ON-BOARDING", "BRIDGE-LAND", "WATER-UNITS-VILLAGE", "TENTACLES", "G9"],
    "Attack": ["COMBAT-FORMULA", "C6", "RET-RANGE", "DEF-BONUS", "C7", "SPLASH", "C20", "FROZEN-NO-RETALIATION", "CLOAK-DAGGER-RETALIATION",
               "JUGGERNAUT-NO-RETALIATION", "KILL-MOVE-IN", "JUGGERNAUT-KILL-MOVE", "KILL-MOVE-CLIMBING", "WATER-UNITS", "STOMP", "TENTACLES",
               "EMBASSY-DESTROYED-BY-COMBAT", "UNIT-STATS-UI", "PEACE-AREA-DAMAGE"] + PUSH,
    "Summon": ["UNIT-STATS-UI", "AQUARION-UNIT", "UNIT-ID-48", "UNIT-ID-53", "AQUARION-UNIT-47", "AQUARION-UNITS-49-52", "CYMANTI-TECHS",
               "SUPER-UNIT-BY-TRIBE", "NO-CITIES-NO-UNITS", "TRAIN-BASE"],
    "Upgrade": ["UNIT-STATS-UI", "ECON-PRICES-V123", "UPGRADE-BASE"],
    "Build": ["C19-COSTS", "ECON-PRICES-V123", "ECON-MARKET-CLATHRUS", "SANCTUARY-V123", "OUTPOST-NETWORK", "OUTPOST-ON-ICE", "AQUARION-STRUCTURES",
              "AQUARION-AQUA-FARM-WATER", "ATOLL-NETWORK", "MONUMENT-TERRAIN", "METAL-WITH-MINING", "PORT-FLOODED", "CLATHRUS-ON-LAND",
              "WATER-TEMPLE-PRICE", "ECON-INCOME"],
    "Harvest": ["C19-COSTS", "ECON-PRICES-V123", "ECON-INCOME"],
    "Research": ["TECH-TREE", "TECH-COST", "C25-BACKWARDS", "C27", "RESEARCH-BACKWARD", "AQUARION-TECH-TIERS", "AQUARION-TECH-SLOTS",
                 "TRIBE-TECH-TIERS", "CYMANTI-TECHS", "CYMANTI-OCEANOLOGY-ID", "AQUARION-WATERWAYS-ID"],
    "Capture": ["CAPTURE-TERRITORY", "ECON-INCOME", "ECON-BOT-BONUS", "POLARIS-CAPTURE-FREEZE", "MOONI-FREEZE", "RUIN-REWARD", "DIST-RUIN-REWARD",
                "RUIN-UNIT-CYMANTI", "RUIN-UNIT-SPAWN", "ECON-RUIN-STARS", "AQUARION-LOST-CITY", "INFILTRATE"],
    "Reward": ["CITY-REWARDS", "CITY-LEVEL-BY-REWARD", "DIST-CITY-REWARD", "ECON-INCOME"],
    "EndTurn": ["ECON-INCOME", "ROUND-START-INCOME", "ECON-BOT-BONUS", "ECON-SIEGE", "IDLE-AUTO-RECOVER", "ECON-EMBASSY", "EMBASSY-INCOME-NEUTRAL",
                "FUNGI-GROWTH", "SANCTUARY-V123", "ECON-MARKET-CLATHRUS", "OUTPOST-NETWORK", "ECON-MEET", "C7"],
    "Recover": ["HEAL-TERRITORY", "C7"],
    "HealOthers": ["ACTION-4-HEAL"],
    "FreezeArea": ["ACTION-17-FREEZE-AREA", "MOONI-FREEZE", "GAAMI-FREEZE", "MOONI-FREEZE-UNITS"],
    "BreakIce": ["ACTION-18-BREAK-ICE", "ACTION-18-AFTER-MOVE"],
    "Explode": ["EXPLODE-DAMAGE", "EXPLODE-POISON", "EXPLODE-POISON-DEFENCE", "EXPLODE-ANYTIME"],
    "Convert": ["SHAMAN", "CONVERT-ATTACK"],
    "Promote": ["PROMOTE-HP"],
    "Disband": ["UPSTREAM"],
    "Destroy": ["C19-COSTS", "UPSTREAM"],
    "BurnForest": ["C19-COSTS"], "GrowForest": ["C19-COSTS"], "ClearForest": ["C19-COSTS", "CLEAR-FOREST-V123"],
    "EnchantAnimal": ["ECON-PRICES-V123", "ENCHANT-REMOVES-GAME"],
    "PeaceTreaty": ["DIPLO-PEACE"], "PeaceRequestResponse": ["DIPLO-PEACE"], "BreakPeace": ["DIPLO-PEACE", "DIPLO-BREAK-DISBAND"],
    "EstablishEmbassy": ["EMBASSY-ACTION", "ECON-EMBASSY"], "DestroyEmbassy": ["EMBASSY-ACTION"],
    "Swarm": ["ACTION-TYPES-V123"], "Decompose": ["FUNGI-GROWTH", "UPSTREAM"], "Drain": ["UPSTREAM"],
}
FLAGS = {"amphibious_ocean_innate": "AMPHIBIOUS-WATER", "sanctuary_no_income": "SANCTUARY-NO-INCOME"}

def v123_bullets():
    txt = open(os.path.join(ROOT, "sim", "README.md")).read()
    sec = txt.split("## v123 corrections", 1)[1].split("\n## ", 1)[0]
    out = []
    for b in re.findall(r"^- (.+)$", sec, re.M):
        ids = [i.strip() for grp in re.findall(r"\[([^\]]+)\]", b) for i in grp.split(",")]
        ids = [i.split(" ")[0] for i in ids if re.match(r"^[A-Z][A-Za-z0-9-]+$", i.split(" ")[0]) and not i.startswith("new")]
        out.append({"rule": b[:140], "ledger": ids, "files": sorted(set(re.findall(r"`([\w/]+\.rs)`", b)))})
    return out

def build():
    ledger = {r["id"]: r for r in json.load(open(os.path.join(ROOT, "verify", "ledger.json")))["rules"]}
    def lv(i): return ledger[i]["level"] if i in ledger else None
    errors = []
    def label(ids, where):
        rows = []
        for i in ids:
            if i == "UPSTREAM": rows.append({"ledger": i, "level": None, "below_L1": None}); continue
            if i not in ledger: errors.append(f"{where}: {i} not in verify/ledger.json")
            l = lv(i); rows.append({"ledger": i, "level": (l or "")[:60], "below_L1": l is not None and not l.startswith("tool") and level_rank(l) < 1})
        return rows
    kinds = {k: label(v, f"kind {k}") for k, v in KINDS.items()}
    v123 = [dict(b, labels=label(b["ledger"], "sim/README.md: " + b["rule"][:50])) for b in v123_bullets()]
    for b in v123:
        if not b["ledger"]: errors.append(f"sim/README.md bullet has no ledger id: {b['rule'][:60]}")
    # a switch is below L1 by definition (v123_flags.rs): the rule it turns on is the one-source side of a split
    flags = {k: dict(label([v], f"flag {k}")[0], below_L1=True) for k, v in FLAGS.items()}
    src = open(os.path.join(ROOT, "sim", "pfcore", "src", "v123_flags.rs")).read()
    for name in re.findall(r'\("(\w+)", &', src):
        if name not in FLAGS: errors.append(f"v123_flags.rs switch {name} has no ledger id: add it to FLAGS in tools/pf_rule_levels.py")
    return {"kinds": kinds, "v123": v123, "flags": flags}, errors

def summary(d):
    ids = {r["ledger"] for rows in d["kinds"].values() for r in rows} | {r["ledger"] for b in d["v123"] for r in b["labels"]}
    up = sorted(k for k, rows in d["kinds"].items() if any(r["ledger"] == "UPSTREAM" for r in rows))
    below = sorted({r["ledger"] for rows in d["kinds"].values() for r in rows if r["below_L1"]} | {r["ledger"] for b in d["v123"] for r in b["labels"] if r["below_L1"]})
    return f"{len(d['kinds'])} move kinds, {len(d['v123'])} v123 corrections, {len(ids - {'UPSTREAM'})} ledger ids; below L1: {', '.join(below) or 'none'}; kinds with unlabelled upstream logic: {', '.join(up)}"

if __name__ == "__main__":
    d, errors = build()
    for e in errors: print("MISSING", e)
    if "--check" in sys.argv:
        print("pf rule labels: " + summary(d) + f"; {len(errors)} missing"); sys.exit(1 if errors else 0)
    d = {"_about": "Generated by tools/pf_rule_levels.py: Polyfish move kinds, v123 corrections and switches -> ledger id and level. "
                   "below_L1 = the simulator should flag results that depend on it; UPSTREAM = Polyfish v115 logic without a ledger entry.", **d}
    json.dump(d, open(OUT, "w"), indent=1); print("wrote data/pf_rule_levels.json: " + summary(d))
