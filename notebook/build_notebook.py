"""Assemble polytopia_engine.ipynb: source modules as %%writefile cells, data + sample saves as one compressed blob, then demo cells."""
import json, os, base64, zlib
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = os.path.join(R, "notebook", "polytopia_engine.ipynb")

def md(s): return {"cell_type": "markdown", "metadata": {}, "source": s.strip("\n").splitlines(True)}
def code(s): return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": s.strip("\n").splitlines(True)}
def wf(path, src): return code(f"%%writefile {path}\n" + open(src).read())

data_files = {"verify/game_enums.json": "verify/game_enums.json", "data/measured_start.json": "data/measured_start.json",
              "data/measured_ui.json": "data/measured_ui.json", "data/measured_mapgen.json": "data/measured_mapgen.json",
              "data/units.json": "data/units.json", "data/tech_tree.json": "data/tech_tree.json"}
saves = {"saves/botwar_t5.state": "saves/6e1bf8e0-1271-4f48-95c0-0fef5e449a63_t5.state",
         "saves/botwar_t11.state": "saves/6e1bf8e0-1271-4f48-95c0-0fef5e449a63_t11.state",
         "saves/botwar_t15.state": "saves/6e1bf8e0-1271-4f48-95c0-0fef5e449a63_t15.state",
         "saves/giants_of_shaza_t6.state": "saves/9847d452-4605-4d46-8330-cf8c695d6f48.state",
         **{f"saves/ankiian_t{t}.state": f"saves/1bf60251-4e7a-4d43-9043-ffc90bf46c31_t{t}.state" for t in range(1, 8)}}
blob = {k: base64.b64encode(zlib.compress(open(os.path.join(R, v), "rb").read(), 9)).decode() for k, v in {**data_files, **saves}.items()}

cells = [
md("""
# Polytopia engine (v123)

This notebook holds everything built so far, running in one place:

1. **Save decoder**: reads iPhone `.state` saves (map, players, every action).
2. **Engine replay**: replays a game action by action and checks it against the saved checkpoints.
3. **Combat calculator**: the damage formula the replay confirmed.
4. **Map generator**: uses the numbers measured from real saves, with the wiki filling gaps.

**How to use:** *Runtime → Run all*. It works straight away with a bundled bot-war game (Massive, 16 players, turns 5, 11 and 15). To use your own saves, run the **Upload** cell; it accepts the iPhone text exports or raw `.state` files.

Everything is plain Python with no installs needed. The setup cells write the code to `/content/polytopia/`, so you can open and edit the files there.
"""),
md("## 1. Setup: write the code and data"),
code("""
import os, sys, base64, zlib, json
ROOT = "/content/polytopia" if os.path.isdir("/content") else os.path.abspath("polytopia")
for d in ("verify", "engine", "sim", "data", "saves"): os.makedirs(os.path.join(ROOT, d), exist_ok=True)
os.chdir(ROOT)
for p in (os.path.join(ROOT, "engine"), os.path.join(ROOT, "verify"), os.path.join(ROOT, "sim")):
    if p not in sys.path: sys.path.insert(0, p)
print("working in", ROOT)
"""),
md("### Save-file decoder (`verify/state_v123.py`)"),
wf("verify/state_v123.py", os.path.join(R, "verify/state_v123.py")),
md("### Engine: unit stats, game state, replay (`engine/`)"),
wf("engine/stats.py", os.path.join(R, "engine/stats.py")),
wf("engine/state.py", os.path.join(R, "engine/state.py")),
wf("engine/replay.py", os.path.join(R, "engine/replay.py")),
wf("engine/economy.py", os.path.join(R, "engine/economy.py")),
md("### Map generator (`sim/wiki_mapgen.py`)"),
wf("sim/wiki_mapgen.py", os.path.join(R, "sim/wiki_mapgen.py")),
md("### Data tables and sample saves (compressed)"),
code("BLOB = " + json.dumps(blob) + "\n" + """
for path, b64 in BLOB.items():
    with open(os.path.join(ROOT, path), "wb") as f: f.write(zlib.decompress(base64.b64decode(b64)))
print("wrote", len(BLOB), "files:", ", ".join(sorted(BLOB)))
"""),
md("## 2. Loading saves"),
code("""
import importlib, re, glob, collections
import state_v123 as S

def load_save(raw):
    \"\"\"Decode a .state file (bytes) into the JSON layout the engine reads.\"\"\"
    st = S.read_state(S.decompress(raw)); h = st["initial"]["header"]; cur = st["current"]["header"]
    return {"gameVersion": st["version"], "mapWidth": h["MapWidth"], "mapHeight": h["MapHeight"], "currentTurn": cur["CurrentTurn"],
            "header": {"MapHeaderInput": h}, "currentHeader": cur,
            "initialTiles": st["initial"]["tiles"], "initialPlayers": [p for p in st["initial"]["players"] if p["PlayerId"] != 255],
            "currentTiles": st["current"]["tiles"], "currentPlayers": [p for p in st["current"]["players"] if p["PlayerId"] != 255],
            "actions": st["actions"], "actionsProblem": st["actions_problem"], "unparsedBytes": st["unparsed_bytes"]}

def read_any(path):
    \"\"\"Raw .state, or the iPhone text export (first line = device path, then base64).\"\"\"
    b = open(path, "rb").read()
    try:
        lines = b.decode().strip().splitlines()
        if lines and lines[0].strip().endswith(".state"): return base64.b64decode("".join(l.strip() for l in lines[1:]))
    except UnicodeDecodeError: pass
    return b

GAMES = {}
def add(path):
    d = load_save(read_any(path)); name = os.path.splitext(os.path.basename(path))[0]
    jp = os.path.join(ROOT, "saves", name + ".json"); json.dump(d, open(jp, "w")); GAMES[name] = jp
    ok = d["actionsProblem"] is None and d["unparsedBytes"] == 0
    print(f"{name:28s} '{d['header']['MapHeaderInput']['MapName']}' {d['mapWidth']}x{d['mapHeight']} turn {d['currentTurn']:3d} "
          f"actions {len(d['actions']):5d}  decoded {'fully' if ok else 'PARTLY: ' + str(d['actionsProblem'])}")

for p in sorted(glob.glob(os.path.join(ROOT, "saves", "*.state"))): add(p)
"""),
md("### Upload your own saves (optional)\nRun this cell and pick one or more files: the iPhone text exports or `.state` files. Each one is decoded and added to `GAMES`."),
code("""
try:
    from google.colab import files
    up = files.upload()
    for name, data in up.items():
        p = os.path.join(ROOT, "saves", name); open(p, "wb").write(data); add(p)
except ImportError:
    print("Not running in Colab: copy files into", os.path.join(ROOT, "saves"), "and call add(path)")
"""),
md("## 3. Inspect a game\nPlayers (tribe, stars, score, cities, kills and losses) and what happened in the move history."),
code("""
E = json.load(open(os.path.join(ROOT, "verify", "game_enums.json")))
def summary(name):
    d = json.load(open(GAMES[name])); T = E["TribeType"]
    print(d["header"]["MapHeaderInput"]["MapName"], "| turn", d["currentTurn"], "| difficulty", d["header"]["MapHeaderInput"]["Difficulty"])
    print(f"{'player':>6} {'tribe':10s} {'you?':5s} {'stars':>5} {'score':>6} {'cities':>6} {'kills':>5} {'losses':>6}")
    for p in d["currentPlayers"]:
        print(f"{p['PlayerId']:>6} {T.get(str(p['Tribe']), str(p['Tribe'])):10s} {'YOU' if p['AutoPlay'] == 0 else '':5s} {p['Currency']:>5} {p['Score']:>6} {p['NumCities']:>6} {p['Kills']:>5} {p['Losses']:>6}")
    print("actions:", dict(collections.Counter(a["name"] for a in d["actions"]).most_common()))
summary("botwar_t15")
"""),
md("## 4. Engine replay vs checkpoints\nThe engine replays the turn-15 save's full move history from turn 0, stopping at each earlier export (turns 5 and 11) to compare every unit's HP, type, position and owner with what the game saved."),
code("""
import replay as RP; importlib.reload(RP)
st, reps = RP.run(GAMES["botwar_t15"], [GAMES["botwar_t5"], GAMES["botwar_t11"]])
for path, n, res, bad in reps:
    tot = sum(v for k, v in res.items() if k in ("HP exact", "HP differs"))
    print(f"{os.path.basename(path):18s} after {n:5d} actions: exact HP {res.get('HP exact', 0)}/{tot} units  | {dict(res)}")
"""),
md("### Turn-by-turn replay: Ankiian Mountain (Bardur, Massive, 16 players, exported every turn 1–7)\nWith a checkpoint every turn, any mismatch points to one turn's actions."),
code("""
importlib.reload(RP)
st2, reps2 = RP.run(GAMES["ankiian_t7"], [GAMES[f"ankiian_t{t}"] for t in range(1, 7)])
for path, n, res, bad in reps2:
    tot = sum(v for k, v in res.items() if k in ("HP exact", "HP differs"))
    print(f"turn {os.path.basename(path).split('_t')[-1][:-5]:>2}: exact HP {res.get('HP exact', 0)}/{tot}  | {dict(res)}" + (f"  <- {bad}" if bad else ""))
"""),
md("### Stars check: Ankiian turn by turn\nFor every player between two saves: stars before + income − spending (units, buildings, techs, upgrades) + rewards (city Resources, meeting a tribe, ruins read back from the next save) must equal the stars in the next save."),
code("""
import economy as EC; importlib.reload(EC)
ds = [json.load(open(GAMES[f"ankiian_t{t}"])) for t in range(1, 8)]
for a, b in zip(ds, ds[1:]):
    rows = {pl: r for pl, r in EC.check(a, b, ds[-1]["actions"]).items() if r["residual"] is not None and EC.Books(a).cities(pl)}
    ok = sum(1 for r in rows.values() if r["residual"] == 0 and not r["unknown"])
    off = sorted(r["residual"] for r in rows.values() if r["residual"])
    print(f"turn {a['currentTurn']} -> {b['currentTurn']}: stars exact for {ok}/{len(rows)} players" + (f"  (off by {off})" if off else ""))
"""),
md("### Rule A/B tests\nFlip one rule and rerun. The version that reproduces more of the saved HP is the real game rule. This is how the counter-attack question was settled."),
code("""
def score(**rules):
    importlib.reload(RP); RP.RULES.update(rules)
    _, reps = RP.run(GAMES["botwar_t15"], [GAMES["botwar_t5"], GAMES["botwar_t11"]])
    return [r[2].get("HP exact", 0) for r in reps]
print("current rules                     ", score())
print("counter-attack WITHOUT def. bonus ", score(retaliation_uses_bonus=False))
print("no move-in after a melee kill     ", score(melee_moves_in_on_kill=False))
importlib.reload(RP);
"""),
md("## 5. Combat calculator\nThe confirmed formula: damage = round(aF/(aF+dF) × attack × 4.5), with aF = attack × hp/max and dF = defense × hp/max × bonus (1.5 for a city with Fortify, forest + Archery or mountain + Climbing; 4 behind walls). The counter-attack uses the same dF."),
code("""
from stats import STATS
def battle(attacker, defender, a_hp=None, d_hp=None, bonus=1.0, a_vet=False, d_vet=False, distance=1):
    a, d = STATS[attacker], STATS[defender]
    amax, dmax = a["hp"] + 5 * a_vet, d["hp"] + 5 * d_vet; ah, dh = a_hp or amax, d_hp or dmax
    af = a["atk"] * ah / amax; df = d["def"] * dh / dmax * bonus; tot = af + df
    dmg = RP.rnd(af / tot * a["atk"] * 4.5); left = dh - dmg; ret = 0
    if left > 0 and "stiff" not in d["skills"] and "surprise" not in a["skills"] and distance <= d.get("range", 1):
        ret = RP.rnd(df / tot * d["def"] * 4.5)
    print(f"{attacker} ({ah}/{amax}) -> {defender} ({dh}/{dmax}, bonus {bonus}): deals {dmg}, defender left {max(left, 0)}"
          + (f", hits back {ret}, attacker left {ah - ret}" if left > 0 else " (killed)"))

battle("Warrior", "Warrior")
battle("Knight", "Archer", bonus=1.5)
battle("Swordsman", "Defender", bonus=4)          # defender behind city walls
battle("Catapult", "Warrior", distance=3)         # out of range: no counter-attack
battle("Shark", "Mermaid")
print("\\nunits known:", ", ".join(sorted(STATS)))
"""),
md("## 6. Map generator\nThe save-first generator: AquaCrop, fixed capital pairs, real capital rings, per-tribe terrain and per-type village counts, all measured from 27 real saves. Set `MODE = 'wiki'` for the wiki-only version."),
code("""
import wiki_mapgen as W; importlib.reload(W)
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
COL = {"Field": "#c9d98a", "Forest": "#4f8a3c", "Mountain": "#8c8c8c", "Water": "#7fb8e6", "Ocean": "#2f6fae"}
GLY = {"AquaCrop": ("d", "#2ec4b6"), "Fruit": ("o", "#d6336c"), "Crop": ("s", "#e8b923"), "Game": ("^", "#7a4a1f"), "Metal": ("D", "#e0e0e0"),
       "Fish": ("o", "#ffffff"), "Starfish": ("*", "#ffd43b"), "Spores": ("s", "#9b59b6")}
def draw(g, ax, title=""):
    n = g["size"]
    for t in g["tiles"].values():
        x, y = t["x"], n - 1 - t["y"]; ax.add_patch(Rectangle((x, y), 1, 1, color=COL.get(t["terrain"], "#cccccc")))
        if t["resource"] in GLY: m, c = GLY[t["resource"]]; ax.plot(x + .5, y + .5, m, color=c, ms=4, mec="black", mew=0.4)
        if t["improvement"] == "Village": ax.add_patch(Rectangle((x + .15, y + .15), .7, .7, fill=False, ec="red" if t["capital_of"] else "black", lw=1.5))
        elif t["improvement"] == "Ruin": ax.text(x + .5, y + .5, "R", ha="center", va="center", fontsize=6, weight="bold")
    ax.set_xlim(0, n); ax.set_ylim(0, n); ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([]); ax.set_title(title, fontsize=10)

MODE, SIZE, SEED = "measured", 16, 7
TRIBES = ["Imperius", "Bardur", "XinXi", "Kickoo"]
fig, axes = plt.subplots(2, 3, figsize=(13, 9))
for ax, mt in zip(axes.flat, ["lakes", "drylands", "continents", "pangea", "archipelago", "waterworld"]):
    g = W.generate(mt, SIZE, TRIBES, seed=SEED, mode=MODE)
    land = sum(t["terrain"] not in ("Water", "Ocean") for t in g["tiles"].values()) / SIZE ** 2
    draw(g, ax, f"{mt} (land {land:.0%})")
fig.suptitle(f"Generated maps ({MODE} mode), {SIZE}x{SIZE}, seed {SEED}. Red = capital, black = village, R = ruin, teal = AquaCrop")
plt.tight_layout(); plt.show()
"""),
md("### Compare with a real map\nThe real turn-0 map from a save, drawn the same way."),
code("""
def real_map(name):
    d = json.load(open(GAMES[name])); ter = {int(k): v for k, v in E["TerrainType"].items()}; res = {int(k): v for k, v in E["ResourceType"].items()}
    n = d["mapWidth"]; tiles = {}
    for y, row in enumerate(d["initialTiles"]):
        for x, t in enumerate(row):
            imp = t["ImprovementType"] if t["ImprovementExists"] else None
            tiles[y * n + x] = {"x": x, "y": y, "terrain": ter.get(t["Terrain"]), "resource": res.get(t["ResourceType"]) if t["ResourceExists"] else None,
                                "improvement": {1: "Village", 2: "Ruin"}.get(imp), "capital_of": t["Capital"]}
    return {"size": n, "tiles": tiles}
fig, axes = plt.subplots(1, 2, figsize=(13, 6.5))
draw(real_map("giants_of_shaza_t6"), axes[0], "REAL: Giants of Shaza (Normal Lakes)")
draw(W.generate("lakes", 16, ["Imperius", "Bardur", "Luxidoor", "Aquarion"], seed=3), axes[1], "GENERATED: Lakes, same tribes")
plt.tight_layout(); plt.show()
"""),
md("""
## Notes
- **Not done yet:** this is a checker, not a playable engine. It doesn't generate legal moves or simulate bots.
- **Where the replay stands:** turn 5 matches almost exactly; later turns drift, because of rare mechanics not modelled yet (ruin spawns, boats, healing, poison, action type 18).
- **Where things live:** every confirmed rule, with its evidence, is in the project ledger (`claude/ledger.json`).
"""),
]
nb = {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
      "language_info": {"name": "python"}, "colab": {"provenance": []}}, "nbformat": 4, "nbformat_minor": 5}
json.dump(nb, open(OUT, "w"), indent=1)
print("wrote", OUT, os.path.getsize(OUT) // 1024, "KB,", len(cells), "cells")
