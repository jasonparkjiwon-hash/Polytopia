"""Unit stats for the engine. Priority: v123 in-game info cards (data/measured_ui.json) > calculator v116 config > nothing.
Keys are the game's UnitType names (game_enums.json, Polyfish ids)."""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, "..")

# calculator v116 table (amigobrewbrew/polytopiacalculatorfirebase-public src/config/v116.json), copied as data
V116 = {
 "Warrior": (10, 2, 2, ["fortify"]), "Rider": (10, 2, 1, ["fortify"]), "Archer": (10, 2, 1, ["fortify"]), "Defender": (15, 1, 3, ["fortify"]),
 "MindBender": (10, 0, 1, ["stiff"]), "Swordsman": (15, 3, 3, []), "Catapult": (10, 4, 0, ["stiff"]), "Knight": (10, 3.5, 1, ["fortify"]),
 "Cloak": (5, 0, 0.5, ["stiff"]), "Dagger": (10, 2, 2, ["surprise", "static"]), "Giant": (40, 5, 4, ["static"]),
 "Raft": (10, 0, 1, ["static", "stiff", "variableHp"]), "Scoutship": (10, 2, 1, ["static", "variableHp"]), "Rammership": (10, 3, 3, ["static", "variableHp"]),
 "Bomber": (10, 3, 2, ["splash", "static", "stiff", "variableHp"]), "Juggernaut": (40, 4, 4, ["stiff", "stomp", "static"]),
 "Dinghy": (5, 0, 0.5, ["static", "stiff"]), "Pirate": (10, 2, 2, ["surprise", "static"]), "Amphibian": (10, 2, 1, []), "Tridention": (10, 2.5, 1, []),
 "Shark": (10, 3.5, 2, ["surprise"]), "Puffer": (10, 4, 0, ["stiff"]), "Jelly": (20, 2, 2, ["stiff", "tentacles", "static"]), "Crab": (40, 4, 4, ["static"]),
 "Polytaur": (15, 3, 1, ["fortify", "static"]), "DragonEgg": (10, 0, 2, ["fortify", "static", "stiff"]), "BabyDragon": (15, 3, 3, ["static"]),
 "FireDragon": (20, 4, 3, ["splash", "static"]), "Mooni": (10, 0, 1, ["stiff"]), "IceArcher": (10, 1, 1, ["freeze", "fortify", "stiff"]),
 "BattleSled": (15, 3, 2, []), "IceFortress": (20, 4, 3, ["static"]), "Gaami": (30, 4, 3, ["static"]), "Hexapod": (5, 3, 1, []), "Kiton": (15, 1, 3, ["poison"]),
 "Phychi": (5, 0.7, 1, ["poison", "surprise", "double attack"]), "Raychi": (10, 3, 2, []), "Boomchi": (10, 3, 3, ["onlyExplode", "static", "stiff"]),
 "LivingIsland": (20, 4, 4, ["stomp", "static", "poison"]), "Shaman": (10, 1, 1, ["static"]), "Exida": (10, 3, 1, ["poison", "poisonSplash"]),
 "Doomux": (20, 3.5, 2, ["explode", "static"]), "Centipede": (20, 4, 3, ["static"]), "Segment": (10, 2, 2, ["onlyExplode", "static", "stiff"]),
 "InsectEgg": (10, 2, 3, ["onlyExplode", "static", "stiff"]), "Larva": (10, 2, 2, ["surprise", "static"]), "Moth": (10, 2, 0.1, ["poison", "static", "stiff"]),
}
# ranges (not in the calculator): info cards + dataset; default 1
RANGE = {"Archer": 2, "Catapult": 3, "Bomber": 3, "Scoutship": 2, "IceArcher": 2, "FireDragon": 2, "AshArcher": 2, "SteamFortress": 2, "Pirate": 1}
UI_NAME = {"Scout": "Scoutship", "Rammer": "Rammership"}   # info-card name -> enum name

def load():
    S = {}
    for k, (hp, a, d, sk) in V116.items():
        S[k] = {"hp": hp, "atk": a, "def": d, "skills": set(sk), "range": RANGE.get(k, 1), "src": "calc-v116"}
    p = os.path.join(ROOT, "data", "measured_ui.json")
    if os.path.exists(p):
        for k, v in json.load(open(p))["units"].items():
            k = UI_NAME.get(k, k); old = S.get(k, {"skills": set()})
            sk = {s.lower().replace("_", "") for s in v["skills"].split()}
            if "variableHp" in old["skills"]: sk.add("variableHp")
            S[k] = {"hp": v["hp"], "atk": v["attack"], "def": v["defense"], "skills": sk, "range": v["range"], "move": v["movement"], "src": "v123-ui"}
    return S

STATS = load()
