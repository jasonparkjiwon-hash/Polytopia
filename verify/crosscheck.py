"""Cross-check our dataset (PolyEnv+wiki based) against Polyfish tables (game version 115).
Two independent reimplementations agreeing = strong evidence; disagreeing = a conflict to resolve.
Usage: python3 -I crosscheck.py <data_dir> <polyfish_tables.json> <out.md> <out.json>"""
import json, sys, re, os
data, pf_path, out_md, out_json = sys.argv[1:5]
L = lambda n: json.load(open(os.path.join(data, n), encoding="utf-8"))
ours_u, ours_t, ours_e = L("units.json")["units"], L("tech_tree.json")["techs"], L("economy.json")
pf = json.load(open(pf_path))
norm = lambda s: re.sub(r"[^a-z0-9]", "", str(s).lower())
SKILL_ALIAS = {"staticskill": "static", "air": "fly", "heal": "healothers", "wateronly": "float", "water": "float"}
snorm = lambda s: SKILL_ALIAS.get(norm(s), norm(s))
ALIAS = {"mindbender": "mindbender", "scout": "scoutship", "rammer": "rammership", "bomber": "bomber",
         "game": "animal", "hunting": "hunting"}
rows = []
def cmp(area, item, fld, a, b):
    if isinstance(a, dict) and "v" in a: a = a["v"]          # v123 card values are stored as {"v": value, "src": ...}
    if a is None and b is None: return
    try: same = abs(float(a) - float(b)) < 1e-9
    except Exception: same = norm(a) == norm(b)
    rows.append({"area": area, "item": item, "field": fld, "ours": a, "polyfish": b, "agree": same})

pfu = {norm(k): (k, v) for k, v in pf["units"].items()}
for name, u in ours_u.items():
    key = norm(name); key = ALIAS.get(key, key)
    if key not in pfu:
        rows.append({"area": "unit", "item": name, "field": "(exists)", "ours": "yes", "polyfish": "missing", "agree": False}); continue
    _, p = pfu[key]
    for a, b in (("cost", "cost"), ("attack", "attack"), ("defense", "defense"), ("movePoints", "movement"), ("range", "range"), ("maxHealth", "health")):
        if a in ("cost", "maxHealth") and not u.get(a): continue   # PE stores 0 for untrainable / inherited values
        cmp("unit", name, a, u.get(a), p.get(b))
    cmp("unit", name, "skills", ",".join(sorted(set(map(snorm, u.get("skills", []))))), ",".join(sorted(set(map(snorm, p.get("skills", []))))))

pft = {norm(k): v for k, v in pf["techs"].items()}
for name, t in ours_t.items():
    p = pft.get(norm(name))
    if not p:
        rows.append({"area": "tech", "item": name, "field": "(exists)", "ours": "yes", "polyfish": "missing", "agree": False}); continue
    cmp("tech", name, "tier", t["tier"], p["tier"])
    cmp("tech", name, "prerequisite", t["prerequisite"], p["requires"])
for name, p in pf["techs"].items():
    if norm(name) not in {norm(k) for k in ours_t} and not p.get("tribe_type") and not p.get("replaces_tech") and name not in ("Basic", "BeyondComprehension"):
        rows.append({"area": "tech", "item": name, "field": "(exists)", "ours": "missing", "polyfish": "base tech", "agree": False})

pfs = {norm(k): v for k, v in pf["structures"].items()}
for name, b in ours_e["buildings"].items():
    if not isinstance(b, dict) or "cost" not in b: continue
    p = pfs.get(norm(name))
    if p: cmp("building", name, "cost", b["cost"], p["cost"])
for name, a in ours_e["tile_actions"].items():
    if isinstance(a, dict) and "cost" in a:
        rows.append({"area": "tile_action", "item": name, "field": "cost", "ours": a["cost"], "polyfish": "see version_sync.rs", "agree": None})

agree = sum(1 for r in rows if r["agree"] is True); dis = [r for r in rows if r["agree"] is False]
_ex = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "crosscheck_explained.json")))["explained"]
for r in dis: r["why"] = _ex.get(f"{r['area']}|{r['item']}|{r['field']}")
unexplained = [r for r in dis if not r["why"]]
json.dump({"agree": agree, "disagree": len(dis), "unexplained": len(unexplained), "rows": rows}, open(out_json, "w"), indent=1)
with open(out_md, "w") as f:
    f.write("# Cross-check: our dataset vs Polyfish (game v115)\n\n")
    f.write(f"{agree} fields agree, {len(dis)} disagree or are missing on one side.\n\n## Disagreements\n\n")
    f.write("| Area | Item | Field | Ours (PE/wiki) | Polyfish v115 | Why |\n|---|---|---|---|---|---|\n")
    for r in dis: f.write(f"| {r['area']} | {r['item']} | {r['field']} | {r['ours']} | {r['polyfish']} | {r['why'] or '**UNEXPLAINED**'} |\n")
print(agree, "agree;", len(dis), "disagree;", len(unexplained), "unexplained")
for r in unexplained: print("  UNEXPLAINED", r["area"], r["item"], r["field"], r["ours"], "|", r["polyfish"])
