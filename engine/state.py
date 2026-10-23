"""Game state for the engine, loaded from an ingested save JSON (verify/ingest_saves.py output)."""
import json, os, struct
from dataclasses import dataclass, field
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, "..")
E = json.load(open(os.path.join(ROOT, "verify", "game_enums.json")))
UNIT = {int(k): v for k, v in E["UnitType"].items()}
UNIT.update({46: "Mermaid",   # v123 id, measured: Aquarion's start unit (22/22 saves), 10 HP, trainable with no tech
             53: "Shark",   # v123 id, inferred: best replay fit (96 exact HP at turn 15 vs 90 for the others), 10 HP
             48: "Swordsmaid"})   # v123 id, measured (af181c8f): Aquarion only (45/45), first trained right after Smithery, 15 HP fresh
UNIT_ID = {v: k for k, v in UNIT.items()}
TERRAIN = {int(k): v for k, v in E["TerrainType"].items()}
TECH = {int(k): v for k, v in E["TechnologyType"].items()}
TRIBE = {int(k): v for k, v in E["TribeType"].items()}
START = json.load(open(os.path.join(ROOT, "data", "measured_start.json")))
BOATS = {"Raft", "Scoutship", "Rammership", "Bomber", "Juggernaut"}   # Juggernaut: a Giant at sea (af181c8f, 19/19 Juggernauts carry a Giant)

@dataclass
class Unit:
    id: int; owner: int; type: str; x: int; y: int; hp: float; max_hp: float
    promotion: int = 0; xp: int = 0; passenger: str = None; effects: list = field(default_factory=list)

@dataclass
class Player:
    id: int; tribe: str; techs: set; stars: int = 0

class State:
    def __init__(self, d, which="initial"):
        tiles = d["initialTiles"] if which == "initial" else d["currentTiles"]
        players = d["initialPlayers"] if which == "initial" else d["currentPlayers"]
        self.H = len(tiles); self.W = len(tiles[0]); self.tiles = tiles
        self.terrain = {}; self.owner = {}; self.city = {}; self.wall = set(); self.units = {}; self.at = {}; self.flood = {}; self.fungi = {}; self.port = set()
        for y, row in enumerate(tiles):
            for x, t in enumerate(row):
                self.terrain[(x, y)] = TERRAIN.get(t["Terrain"], t["Terrain"]); self.owner[(x, y)] = t["Owner"]
                if t.get("FloodedFlag"): self.flood[(x, y)] = t.get("FloodedValue", 1)   # 1 = Aquarion flood (land), 4 = Cymanti algae (water)
                if t.get("ImprovementExists") and t["ImprovementType"] == 37: self.fungi[(x, y)] = t["Owner"]   # Cymanti Fungi (poisons)
                if t.get("ImprovementExists") and t["ImprovementType"] == 8: self.port.add((x, y))
                if t.get("ImprovementExists") and t["ImprovementType"] == 1:            # village / city
                    self.city[(x, y)] = t["Owner"]
                    if 1 in (t.get("ImprovementData") or {}).get("CityRewards", []): self.wall.add((x, y))
                if t.get("Unit"):
                    self.add_unit_record(t["Unit"], t.get("PassengerUnit"), t.get("UnitEffects"))
        self.players = {}
        for p in players:
            tr = TRIBE.get(p["Tribe"], str(p["Tribe"]))
            techs = {TECH.get(t, t) for t in p["AvailableTech"]}
            if which == "initial":       # start techs are granted by StartMatch (measured_start.json)
                techs |= set(START.get(tr, {}).get("after_match_start", {}).get("techs", []))
            self.players[p["PlayerId"]] = Player(p["PlayerId"], tr, techs, p["Currency"])
        self.max_unit_id = max(self.units) if self.units else 0

    def add_unit_record(self, u, passenger=None, effects=None):
        from stats import STATS
        name = UNIT.get(u["UnitType"], f"unit{u['UnitType']}")
        un = Unit(u["Id"], u["Owner"], name, u["cx"], u["cy"], u["Health"] / 10, 0, u["PromotionLevel"], u["Experience"])
        if passenger:
            un.passenger = UNIT.get(passenger["UnitType"], str(passenger["UnitType"])); un.passenger_id = passenger["Id"]
            un.promotion = passenger["PromotionLevel"]   # MEASURED: the boat record's level is always 0; the passenger keeps veteran status (HP is the boat's)
        un.max_hp = max_hp(un); un.effects = effects or []
        self.units[un.id] = un; self.at[(un.x, un.y)] = un.id

def max_hp(u):
    from stats import STATS
    base = STATS.get(u.passenger if (u.type in BOATS and u.passenger) else u.type, {}).get("hp", 10)
    return base + (5 if u.promotion > 0 else 0)
