"""Economy replay: check each player's stars between two saves of the same game.

stars(next save) = stars(this save) + income - spending + logged rewards, for every player, over the actions between the saves.
Usage: python3 -I economy.py <save json> <save json> [more saves of the same game...]"""
import sys, os, json, struct, math, collections
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, ".."); sys.path.insert(0, HERE)
from state import UNIT, TECH, TRIBE, State
import replay as R

_ui = json.load(open(os.path.join(ROOT, "data", "measured_ui.json")))
_units = json.load(open(os.path.join(ROOT, "data", "units.json")))["units"]
_tree = json.load(open(os.path.join(ROOT, "data", "tech_tree.json")))["techs"]

def _cost(v): return v["v"] if isinstance(v, dict) else v
UNIT_COST = {k: _cost(v.get("cost")) for k, v in _units.items()}
UNIT_COST.update({k: v["cost"] for k, v in _ui["units"].items()})              # v123 info cards win
UNIT_COST.update({"Scoutship": UNIT_COST["Scout"], "Rammership": UNIT_COST["Rammer"], "Amphibian": UNIT_COST["Amphibian"],
                  "Tridention": UNIT_COST["Tridention"], "Moth": UNIT_COST["MothC"]})
# Build action ids (StructureType, plus the tile actions the enum doesn't name; ids read from the tile changes in the saves)
BUILD = {3: ("Road", 3), 5: ("Farm", 5), 6: ("Windmill", 5), 7: ("Fishing", 2), 8: ("Port", 7), 9: ("Hunting", 2), 12: ("LumberHut", 3),
         13: ("Sawmill", 5), 15: ("HarvestFruit", 2), 17: ("Temple", 20), 21: ("Mine", 5), 22: ("Forge", 5), 33: ("Outpost", 5),
         37: ("Fungi", 5), 38: ("Algae", 5), 39: ("Mycelium", 5), 48: ("Bridge", 5), 50: ("Market", 5),
         23: ("AltarOfPeace", 0), 24: ("TowerOfWisdom", 0), 25: ("GrandBazaar", 0), 26: ("EmperorsTomb", 0), 27: ("GateOfPower", 0),
         28: ("ParkOfFortune", 0), 29: ("EyeOfGod", 0),                                   # monuments are free
         30: ("EnchantAnimal", 3), 46: ("Starfish", -8), 49: ("AquaFarm", 5), 51: ("Aquarion51", 5)}
# MEASURED (implied by the star check on turns where it was the only unknown): Enchant Animal 3 (5/5); harvesting Starfish
# GIVES 8 stars (18/22); AquaFarm 5 (n=1) and Aquarion structure 51 5 (n=2) are thin.
UPGRADE_COST = {"Scoutship": 5, "Rammership": 5, "Bomber": 15}
TIER = {k.replace(" ", ""): v["tier"] for k, v in _tree.items()}
TIER.update({"IceFishing": 2, "Sledding": 2, "PolarWarfare": 3, "Spearing": 3})   # MEASURED: tribe techs priced by the same formula (n=1-2 each)
REWARD_STARS = {7: 5}                       # CityReward Resources: +5 stars now
REWARD_INCOME = {3: 1, 2: 1}                # Workshop, Park: +1 star per turn

def meet_stars(score):
    """Stars for meeting a tribe, from the MET tribe's score (Polyfish get_star_exchange, v >= 83): 1 + 2*min(ceil(score/1000), 5).
    MEASURED: 129/141 one-turn meetings exact."""
    return 1 + 2 * min(math.ceil(score / 1000), 5) if score > 0 else 1

def tech_cost(tier, cities, literacy):
    base = tier * cities + 4
    return math.ceil(base * 2 / 3) if literacy else base

class Books:
    """Cities, techs and stars per player, kept up to date through the actions between two saves."""
    def __init__(self, d):
        self.city = {}; self.capital = {}
        for y, row in enumerate(d["currentTiles"]):
            for x, t in enumerate(row):
                if t["ImprovementExists"] and t["ImprovementType"] == 1:
                    self.city[(x, y)] = dict(owner=t["Owner"], **t["ImprovementData"])
                    if t["Capital"]: self.capital[(x, y)] = t["Capital"]
        self.techs = {p["PlayerId"]: {TECH.get(k, k) for k in p["AvailableTech"]} for p in d["currentPlayers"]}
        self.stars = {p["PlayerId"]: p["Currency"] for p in d["currentPlayers"]}
        self.tribe = {p["PlayerId"]: TRIBE.get(p["Tribe"]) for p in d["currentPlayers"]}
        self.handicap = {p["PlayerId"]: p["DifficultyHandicap"] for p in d["currentPlayers"]}

    def cities(self, pl): return [c for c in self.city.values() if c["owner"] == pl]

    def income(self, pl, model, units=None):
        cs = [(q, c) for q, c in self.city.items() if c["owner"] == pl]
        if units is not None:                           # a city with an enemy unit on it produces nothing (siege; Polyfish get_city_production)
            cs = [(q, c) for q, c in cs if not (units.get(q) is not None and units[q] != pl)]
        if model == "production": return sum(c["Production"] for _, c in cs)
        bonus = max(0, self.handicap.get(pl, 1) - 1)     # MEASURED: bot bonus = DifficultyHandicap - 1 stars a turn (Easy 1, Hard 2)
        if BONUS_NEEDS_CAPITAL and not any(self.capital.get(q) == pl and c["owner"] == pl for q, c in self.city.items()): bonus = 0
        tot = bonus if any(c["owner"] == pl for c in self.city.values()) else 0   # MEASURED: bot bonus = DifficultyHandicap - 1 stars a turn (Easy 1, Hard 2)
        for q, c in cs:
            tot += c["Level"] + (1 if self.capital.get(q) == pl else 0)
            tot += sum(REWARD_INCOME.get(r, 0) for r in c["CityRewards"])
            if NEG_POP: tot += min(0, c["CurrentPopulation"])   # a city with negative population (after a capture) pays that much less
        return tot

def spend(b, pl, a):
    """Stars this action costs (negative = gained). None = price not known."""
    t = a["type"]; r = bytes.fromhex(a["raw"])
    if t == 5:
        ut = UNIT.get(struct.unpack("<BHII", r)[1]); return UNIT_COST.get(ut)
    if t == 1:
        imp = struct.unpack("<BHII", r)[1]; return BUILD.get(imp, (None, None))[1]
    if t == 16:
        ut = UNIT.get(struct.unpack("<BHII", r)[1]); return UPGRADE_COST.get(ut)
    if t == 8:
        tech = TECH.get(struct.unpack("<BH", r)[1]); tier = TIER.get(tech)
        if tier is None: return None
        return tech_cost(tier, len(b.cities(pl)), "Philosophy" in b.techs.get(pl, ()))
    if t == 11:
        rw = struct.unpack("<BIIH", r)[3]; return -REWARD_STARS.get(rw, 0)
    return 0

def book(b, a):
    """Bookkeeping that changes later prices or income: captures, research, city rewards, level-ups."""
    t = a["type"]; r = bytes.fromhex(a["raw"]); pl = r[0]
    if t == 7:
        _, uid, x, y = struct.unpack("<BIII", r)
        if (x, y) in b.city: b.city[(x, y)]["owner"] = pl
    elif t == 8:
        b.techs.setdefault(pl, set()).add(TECH.get(struct.unpack("<BH", r)[1]))
    elif t == 11:
        _, x, y, rw = struct.unpack("<BIIH", r)
        if (x, y) in b.city: b.city[(x, y)]["CityRewards"] = b.city[(x, y)]["CityRewards"] + [rw]
    elif t == 21:
        _, x, y = struct.unpack("<BII", r)
        if (x, y) in b.city: b.city[(x, y)]["Level"] += 1

RUIN_STARS = 10
BONUS_NEEDS_CAPITAL = True
NEG_POP = True
PAID_AT_TURN_START = False  # MEASURED: a save taken right at a turn start does not hold that turn's income yet; a mid-turn save does (596 vs 562 exact)

def check(a, b, acts, model="levels", siege=True):
    """One row per player: stars before/after, income, known spending, unknown-price actions, residual (after - predicted)."""
    bk = Books(a); after = {p["PlayerId"]: p["Currency"] for p in b["currentPlayers"]}
    rows = {pl: dict(before=s, income=0, spent=0, unknown=collections.Counter(), turns=0) for pl, s in bk.stars.items()}
    st = State(a, "current") if siege else None; R.PREV[0] = None; turn = a["currentTurn"]
    n0 = len(a["actions"])
    prev_end = PAID_AT_TURN_START is False and n0 > 0 and acts[n0 - 1]["type"] == 15   # see PAID_AT_TURN_START
    for i in range(len(a["actions"]), len(b["actions"])):
        x = acts[i]; pl = bytes.fromhex(x["raw"])[0]
        if pl in rows and prev_end and pl != 255:       # the first action of a player's turn: income arrives first
            occ = {q: st.units[i].owner for q, i in st.at.items() if i in st.units} if st else None
            rows[pl]["income"] += bk.income(pl, model, occ); rows[pl]["turns"] += 1
        prev_end = x["type"] == 15
        if st is not None:
            if x["type"] == 15 and pl == 255: turn += 1
            R.apply(st, x, turn)
        if pl not in rows: continue
        if x["type"] == 14: rows[pl]["ruins"] = rows[pl].get("ruins", 0) + 1
        c = spend(bk, pl, x)
        if c is None: rows[pl]["unknown"][(x["name"], x["raw"][2:6])] += 1
        else: rows[pl]["spent"] += c
        book(bk, x)
    pa = {p["PlayerId"]: p for p in a["currentPlayers"]}; pb = {p["PlayerId"]: p for p in b["currentPlayers"]}
    for pl, r in rows.items():                          # tribes met between the saves (the log has no meet event)
        if pl not in pb: continue
        for o in set(pb[pl]["Encountered"]) - set(pa[pl]["Encountered"]):
            score = (pa if o > pl and o in pa else pb).get(o, {}).get("Score", 0)   # the met tribe's score when met: before its own turn if it plays later
            r["income"] += meet_stars(score); r["met"] = r.get("met", 0) + 1
    for pl, r in rows.items():
        r["after"] = after.get(pl); r["predicted"] = r["before"] + r["income"] - r["spent"]
        r["residual"] = None if r["after"] is None else r["after"] - r["predicted"]
        # the log doesn't say what a ruin gave: MEASURED it is either no stars or exactly 10 (27 and 10 of 37 ruin turns),
        # so read the star rewards back from the next save, like the replay does for ruin units
        if r["residual"] and r.get("ruins") and r["residual"] % RUIN_STARS == 0 and 0 < r["residual"] // RUIN_STARS <= r["ruins"]:
            r["ruin_stars"] = r["residual"]; r["predicted"] += r["residual"]; r["residual"] = 0
    return rows

if __name__ == "__main__":
    ds = sorted((json.load(open(f)) for f in sys.argv[1:]), key=lambda d: len(d["actions"])); acts = ds[-1]["actions"]
    tot = collections.Counter()
    for a, b in zip(ds, ds[1:]):
        rows = {pl: r for pl, r in check(a, b, acts).items() if r["residual"] is not None and Books(a).cities(pl)}
        ok = sum(1 for r in rows.values() if r["residual"] == 0 and not r["unknown"])
        off = sorted((r["residual"] for r in rows.values() if r["residual"]), key=abs)
        tot["exact"] += ok; tot["players"] += len(rows)
        print(f"t{a['currentTurn']}->t{b['currentTurn']}: stars exact for {ok}/{len(rows)} players" + (f"  (off by {off})" if off else ""))
    print(f"total: {tot['exact']}/{tot['players']} player-turns exact")
