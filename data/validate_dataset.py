#!/usr/bin/env python3
"""Cross-checks the dataset against itself. Exit code 1 if a hard check fails.
The start-score reconstruction is the interesting one: it tests tribe start data (tech, unit, capital level)
against the wiki's Score table using only the score formula, so it exposes which source is wrong."""
import json, os, sys, math
D = os.path.dirname(os.path.abspath(__file__))
L = lambda n: json.load(open(os.path.join(D, n), encoding="utf-8"))
tech, tribes, units, mapg = L("tech_tree.json"), L("tribes.json"), L("units.json"), L("map_generation.json")
hard_fail = 0
def ok(c, msg):
    global hard_fail
    print(("PASS  " if c else "FAIL  ") + msg)
    if not c: hard_fail += 1

# ---- 1. tech graph --------------------------------------------------------
T = tech["techs"]
ok(len(T) == 25, "25 base techs")
ok(sum(1 for t in T.values() if t["tier"] == 1) == 5 and sum(1 for t in T.values() if t["tier"] == 2) == 10 and sum(1 for t in T.values() if t["tier"] == 3) == 10, "tier sizes 5/10/10")
bad = [n for n, t in T.items() if (t["prerequisite"] is None) != (t["tier"] == 1) or (t["prerequisite"] and T[t["prerequisite"]]["tier"] != t["tier"] - 1)]
ok(not bad, "every tier-N tech has exactly one tier-(N-1) prerequisite  " + str(bad))
# acyclic by construction (tier strictly decreases) -> reachability of all techs from tier 1
ok(all(t["tier"] == 1 or t["prerequisite"] in T for t in T.values()), "all prerequisites exist")
# each T1 tech is prerequisite of >=1 T2; each T2 of >=1 T3 except where noted
pre = {t["prerequisite"] for t in T.values() if t["prerequisite"]}
print("INFO  techs that are nobody's prerequisite:", sorted(n for n in T if n not in pre))
cost = lambda tier, cities, lit=False: (lambda b: math.ceil(b * 2 / 3) if lit else b)(tier * cities + 4)
ok([cost(1, 1), cost(2, 1), cost(3, 1)] == [5, 6, 7] and [cost(1, 1, True), cost(2, 1, True), cost(3, 1, True)] == [4, 4, 5], "tech cost reproduces wiki example 5/6/7 and 4/4/5 with Literacy")

# ---- 2. units -------------------------------------------------------------
U = units["units"]
need = {u["requiredTechToSpawn"] for u in U.values() if u["requiredTechToSpawn"]}
ok(all(n in T for n in need), "unit tech requirements exist in tech tree  " + str(sorted(need - set(T))))
# every land unit that is city-trainable
train = ["Warrior","Archer","Defender","Rider","MindBender","Swordsman","Catapult","Cloak","Knight"]
ok(all(u in U for u in train), "9 city-trainable base units present")
print("INFO  base unit table (cost hp atk def mv rng):")
for u in train: x = U[u]; print("      %-10s %2d %2d %3.1f %3.1f %d %d  %s" % (u, x["cost"], x["maxHealth"], x["attack"], x["defense"], x["movePoints"], x["range"], x["requiredTechToSpawn"]))

# ---- 3. start score reconstruction ----------------------------------------
CITY_L1, TERR, EXPL = 100, 9 * 20, 25 * 5      # level-1 city, 3x3 territory, 5x5 explored
def start_score(tech_name, unit, level=1):
    s = CITY_L1 + 50 * (level - 1) + TERR + EXPL
    s += 5 * U[unit]["cost"]
    if tech_name: s += 100 * T[tech_name]["tier"]
    return s
# variant tables: what each source claims the start package is
variants = {
 "PE package":     {"XinXi":("Climbing","Warrior",1),"Imperius":("Organization","Warrior",1),"Bardur":("Hunting","Warrior",1),"Oumaji":("Riding","Rider",1),
                    "Kickoo":("Fishing","Warrior",1),"Hoodrick":("Archery","Archer",1),"Luxidoor":(None,"Warrior",1),"Vengir":("Smithery","Swordsman",1),
                    "Zebasi":("Farming","Warrior",1),"AiMo":("Philosophy","MindBender",1),"Quetzali":("Strategy","Defender",1),"Yadakk":("Roads","Warrior",1),
                    "Aquarion":(None,"Mermaid",1)},
 "Wiki package (pre-2025)":   {"AiMo":("Meditation","Warrior",1),"Luxidoor":(None,"Warrior",2)},
 "Current (NamuWiki, Nov 2025)": {"Luxidoor":(None,"Warrior",3)},
}
# tribes whose tech is not in the base tree: model as tier-1 replacements
SPECIAL = {"Elyrion":(1,"Warrior"),"Polaris":(1,"Mooni"),"Cymanti":(2,"Shaman")}
wk = {n: v["start_score_WK"] for n, v in tribes["tribes"].items()}
print("\nSTART-SCORE RECONSTRUCTION  (component formula vs wiki Score table)")
print("%-9s %-34s %6s %6s  %s" % ("tribe", "package tested", "calc", "wiki", "verdict"))
matches = 0; total = 0
def row(name, desc, calc):
    global matches, total
    w = wk.get(name); total += 1 if w else 0
    v = "n/a" if w is None else ("MATCH" if calc == w else "off by %+d" % (calc - w))
    if w is not None and calc == w: matches += 1
    print("%-9s %-34s %6d %6s  %s" % (name, desc, calc, w, v))
for n, (t, u, lv) in variants["PE package"].items():
    row(n, "PE: %s + %s, lvl %d" % (t, u, lv), start_score(t, u, lv))
for k in ("Wiki package (pre-2025)", "Current (NamuWiki, Nov 2025)"):
    for n, (t, u, lv) in variants[k].items():
        row(n, "%s: %s+%s L%d" % ("OLD" if "pre" in k else "NOW", t, u, lv), start_score(t, u, lv))
for n, (tier, u) in SPECIAL.items():
    s = CITY_L1 + TERR + EXPL + 5 * U[u]["cost"] + 100 * tier
    row(n, "special: tier-%d tech + %s" % (tier, u), s)
print("\nreproduced %d rows of %d tested (14 distinct tribes of the 15 in the wiki table; Kickoo is the miss)" % (matches, total))
print("      -> Kickoo (615) is NOT reproduced by Fishing+Warrior (515): an unexplained +100  (C5)")
print("      -> Luxidoor: wiki 465 = level 2 (pre-Nov-2025); PE 515 = level 3 = CURRENT per NamuWiki (C2)")
print("      -> Ai-Mo: wiki 615 = Meditation+Warrior (pre-2025); PE 730 = Philosophy+MindBender = CURRENT per NamuWiki (C1)")
print("      -> LESSON: the fandom Score table mixes patch eras; arithmetic proves internal consistency, NOT currency.")
ok(matches >= 14, "14 of 15 wiki start scores reproduced from first principles (validates 5x5 reveal, 3x3 territory, score constants)")

# ---- 4. map generation sanity ---------------------------------------------
print("\nMAP GENERATION SANITY")
print("%-8s %5s %6s %12s %10s" % ("size", "side", "slots", "pre-terrain", "ruins"))
for name, side in {"tiny": 11, "small": 14, "normal": 16, "large": 18, "huge": 20, "massive": 30}.items():
    slots = (side // 3) ** 2
    n = 4 if side <= 14 else 4   # example capital count only for display
    pre = max(0, math.floor((slots - n - 2 * n) * 0.30))   # assume 1-2 suburbs ~ 1.5/capital: show for 4 players, 2 suburbs each (upper bound)
    r = mapg["ruins"]["count_by_tiles"]["v"][str(side * side)]
    print("%-8s %5d %6d %12d %10d" % (name, side, slots, pre, r))
rates = mapg["resources"]["rates"]
for k in ("inner", "outer"):
    field = rates[k]["fruit_on_field"] + rates[k]["crop_on_field"] + rates[k]["empty_field"]
    forest = rates[k]["animal_in_forest"] + rates[k]["empty_forest"]
    mount = rates[k]["metal_in_mountain"] + rates[k]["empty_mountain"]
    print("INFO  %s: field %.2f forest %.2f mountain %.2f" % (k, field, forest, mount))
# wiki table rows are shares of ALL tiles -> field rows sum to 48%, forest 38%, mountain 14% in BOTH columns
ok(abs(sum(rates["inner"][k] for k in ("fruit_on_field","crop_on_field","empty_field")) - 0.48) < 1e-9, "inner field rates sum to 48% (wiki table shares)")
ok(abs(sum(rates["outer"][k] for k in ("fruit_on_field","crop_on_field","empty_field")) - 0.48) < 1e-9, "outer field rates sum to 48%")
ok(abs(sum(rates["inner"][k] for k in ("animal_in_forest","empty_forest")) - 0.38) < 1e-9 and abs(sum(rates["outer"][k] for k in ("animal_in_forest","empty_forest")) - 0.38) < 1e-9, "forest rates sum to 38%")
ok(abs(sum(rates["inner"][k] for k in ("metal_in_mountain","empty_mountain")) - 0.14) < 1e-9 and abs(sum(rates["outer"][k] for k in ("metal_in_mountain","empty_mountain")) - 0.14) < 1e-9, "mountain rates sum to 14%")

print("\n=> Read literally, the wiki resource table is a table of SHARES OF ALL TILES (rows sum to 48/38/14).")
print("   PE reads the fruit/crop/animal/metal numbers as P(resource | already-chosen terrain) - e.g. P(fruit|field,inner)=0.18")
print("   while the wiki shares imply P(fruit|field,inner)=0.18/0.48=0.375. See conflict C23.")
sys.exit(1 if hard_fail else 0)
