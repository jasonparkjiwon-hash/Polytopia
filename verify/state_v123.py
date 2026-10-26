"""Python reader for Polytopia .state saves, written for game version 123 (iOS, Oct 2026).

The Go library polytopiamapmodelgo (MIT) documents the layout up to ~version 115; v123 adds/moves header bytes,
so the header is located by structure (map width/height followed by tile (0,0)) instead of fixed offsets.
Handles the double LZ4 wrapping seen in the iOS export (outer block whose content is another compressed save).

Usage: python3 -I state_v123.py <save.state | already-decompressed .decomp> <out.json>
Output schema = state2json's ("polytopia-state-json/1"), so analyze_map.py reads it unchanged."""
import struct, sys, json

def lz4_block_decompress(src, out_len):
    """Minimal LZ4 block decoder (no external lz4 module available here)."""
    dst = bytearray(); i = 0; n = len(src)
    while i < n:
        tok = src[i]; i += 1
        lit = tok >> 4
        if lit == 15:
            while True:
                b = src[i]; i += 1; lit += b
                if b != 255: break
        dst += src[i:i + lit]; i += lit
        if i >= n: break
        off = src[i] | (src[i + 1] << 8); i += 2
        ml = tok & 15
        if ml == 15:
            while True:
                b = src[i]; i += 1; ml += b
                if b != 255: break
        ml += 4; start = len(dst) - off
        for k in range(ml): dst.append(dst[start + k])
    return bytes(dst)

def unwrap(b):
    """Polytopia wrapper: 1 header byte (bits 6-7 = size of the length diff field: 2 or 4 bytes), diff, LZ4 block."""
    sz = (b[0] >> 6) & 3; sz = 4 if sz == 3 else sz
    if sz not in (2, 4): return None
    diff = int.from_bytes(b[1:1 + sz], "little")
    return lz4_block_decompress(b[1 + sz:], len(b) - 1 - sz + diff)

def decompress(raw):
    data = raw
    for _ in range(3):                      # unwrap until the payload starts with version (u32 == u32)
        v1, v2 = struct.unpack_from("<II", data, 0)
        if v1 == v2 and 90 <= v1 <= 200: return data
        data = unwrap(data)
    raise ValueError("could not find a decompressed save payload")

class R:
    def __init__(s, b, o=0): s.b, s.o = b, o
    def u8(s): v = s.b[s.o]; s.o += 1; return v
    def u16(s): v = struct.unpack_from("<H", s.b, s.o)[0]; s.o += 2; return v
    def i16(s): v = struct.unpack_from("<h", s.b, s.o)[0]; s.o += 2; return v
    def u32(s): v = struct.unpack_from("<I", s.b, s.o)[0]; s.o += 4; return v
    def i32(s): v = struct.unpack_from("<i", s.b, s.o)[0]; s.o += 4; return v
    def raw(s, n): v = s.b[s.o:s.o + n]; s.o += n; return v
    def vstr(s):
        n = s.u8()                          # 7-bit-encoded length (short names fit one byte)
        if n & 0x80: n = (n & 0x7f) | (s.u8() << 7)
        return s.raw(n).decode("utf-8", "replace")

UNIT_FMT = "<IBHIIiiiiHHHBBBH"                   # 42 bytes, per polytopiamapmodelgo docs
UNIT_KEYS = ["Id", "Owner", "UnitType", "FollowerUnitId", "LeaderUnitId", "cx", "cy", "hx", "hy", "Health", "PromotionLevel", "Experience", "Moved", "Attacked", "Flipped", "CreatedTurn"]

def read_unit(r):
    vals = struct.unpack_from(UNIT_FMT, r.b, r.o); r.o += struct.calcsize(UNIT_FMT)
    return dict(zip(UNIT_KEYS, vals))

def read_header(r):
    h = {"Version1": r.u32(), "Version2": r.u32(), "TotalActions": r.u16(), "CurrentTurn": r.u32(), "CurrentPlayerIndex": r.u8(),
         "MaxUnitId": r.u32(), "CurrentGameState": r.u8(), "Seed": r.i32(), "TurnLimit": r.u32(), "ScoreLimit": r.u32(),
         "WinByCapital": r.u8(), "Unknown6": list(r.raw(6)), "GameModeBase": r.u8(), "GameModeRules": r.u8()}
    h["MapName"] = r.vstr(); h["SquareSize"] = r.u32()
    h["Disabled"] = [r.u16() for _ in range(r.u16())]; h["Unlocked"] = [r.u16() for _ in range(r.u16())]
    h["Difficulty"] = r.u16(); h["Opponents"] = r.u32()
    # v123: the rest of the settings block changed size; locate width,height (= SquareSize) followed by tile (0,0)
    sq = h["SquareSize"]; pat = struct.pack("<HHII", sq, sq, 0, 0)
    k = r.b.find(pat, r.o)
    if k < 0 or k - r.o > 200: raise ValueError("map dimensions not found after header")
    h["SettingsTail"] = list(r.b[r.o:k]); r.o = k
    h["MapWidth"], h["MapHeight"] = r.u16(), r.u16()
    return h

def read_tile(r, version, ex, ey):
    t = {"WorldCoordinates": [r.u32(), r.u32()]}
    if t["WorldCoordinates"] != [ex, ey]: raise ValueError(f"tile ({ex},{ey}) misaligned at offset {r.o}: got {t['WorldCoordinates']}")
    t["Terrain"] = r.u16(); t["Climate"] = r.u16(); t["Altitude"] = r.i16(); t["Owner"] = r.u8(); t["Capital"] = r.u8()
    t["CapitalCoordinates"] = [r.i32(), r.i32()]
    t["ResourceExists"] = r.u8() == 1; t["ResourceType"] = r.u16() if t["ResourceExists"] else -1
    t["ImprovementExists"] = r.u8() == 1; t["ImprovementType"] = r.u16() if t["ImprovementExists"] else -1
    if t["ImprovementExists"]:
        d = {"Level": r.u16(), "FoundedTurn": r.u16(), "CurrentPopulation": r.i16(), "TotalPopulation": r.u16(), "Production": r.i16(),
             "BaseScore": r.i16(), "BorderSize": r.i16(), "UpgradeCount": r.i16(), "ConnectedPlayerCapital": r.u8()}
        if r.u8() == 1: d["CityName"] = r.vstr()
        d["FoundedTribe"] = r.u8(); d["CityRewards"] = [r.u16() for _ in range(r.u16())]
        d["RebellionFlag"] = r.u16()
        if d["RebellionFlag"]: d["RebellionBuffer"] = list(r.raw(2))
        t["ImprovementData"] = d
    t["Unit"] = None
    if r.u8() == 1:
        t["Unit"] = read_unit(r)
        if r.u8() == 1:
            t["PassengerUnit"] = read_unit(r); assert r.u8() == 0
            t["PassengerEffects"] = [r.u16() for _ in range(r.u16())]; r.raw(5)
        t["UnitEffects"] = [r.u16() for _ in range(r.u16())]; t["UnitDirection"] = list(r.raw(5))
    t["PlayerVisibility"] = list(r.raw(r.u8()))
    t["HasRoad"] = r.u8() == 1; t["HasWaterRoute"] = r.u8() == 1; t["TileSkin"] = r.u16(); t["Unknown"] = list(r.raw(2))
    if version >= 105:
        t["FloodedFlag"] = r.u8()   # MEASURED (9906f7da t13): a count of TileEffect ids (u32 each), not a flag; 2 = Flooded + Tentacle
        effects = [r.u32() for _ in range(t["FloodedFlag"])]
        if effects: t["FloodedValue"] = effects[0]
        if len(effects) > 1: t["TileEffects"] = effects
    return t

def read_map(r, version):
    h = read_header(r); W, H = h["MapWidth"], h["MapHeight"]
    tiles = [[read_tile(r, version, x, y) for x in range(W)] for y in range(H)]
    return h, tiles

def read_player(r, version=123):
    """Player record (polytopiamapmodelgo layout, aggressions array dropped since v114) + one trailing byte in v123
    (equal to the tribe id in every save seen so far)."""
    p = {"PlayerId": r.u8(), "Name": r.vstr(), "AccountId": r.vstr(), "AutoPlay": r.u8(), "StartTile": [r.i32(), r.i32()], "Tribe": r.u16(),
         "UnknownByte1": r.u8(), "DifficultyHandicap": r.u32()}
    if version < 114:
        p["Aggressions"] = [(r.u8(), r.i32()) for _ in range(r.u16())]
    p.update({"Currency": r.u32(), "Score": r.u32(), "UnknownInt2": r.u32(), "NumCities": r.u16()})
    p["AvailableTech"] = [r.u16() for _ in range(r.u16())]
    p["Encountered"] = [r.u8() for _ in range(r.u16())]
    p["Tasks"] = []
    for _ in range(r.i16()):
        tt = r.i16(); p["Tasks"].append([tt, list(r.raw(6 if tt in (1, 5, 9) else 2))])   # v123: task type 9 also carries a uint32
    p["Kills"], p["Losses"], p["TribesDestroyed"] = r.i32(), r.i32(), r.i32()
    p["OverrideColor"] = list(r.raw(4)); p["OverrideTribe"] = r.u8()
    p["UniqueImprovements"] = [r.u16() for _ in range(r.u16())]
    p["Diplomacy"] = []
    for _ in range(r.u16()):
        d = struct.unpack_from("<BBiBiiii", r.b, r.o); r.o += 23
        p["Diplomacy"].append(dict(zip(["PlayerId", "RelationState", "LastAttackTurn", "EmbassyLevel", "LastPeaceBrokenTurn", "FirstMeet", "EmbassyBuildTurn", "PreviousAttackTurn"], d)))
    p["DiplomacyMessages"] = [list(r.raw(2)) for _ in range(r.u16())]
    p["DestroyedByTribe"] = r.u8(); p["DestroyedTurn"] = r.u32(); p["UnknownBuffer2"] = list(r.raw(4))
    p["EndScore"] = r.i32(); p["PlayerSkin"] = r.u16(); p["UnknownBuffer3"] = list(r.raw(4))
    if version >= 123: p["V123TrailingByte"] = r.u8()
    return p

def read_players(r, version=123):
    return [read_player(r, version) for _ in range(r.u16())]

# Action payload sizes after the uint16 type (polytopiamapmodelgo, older versions). v123 differs: type 20 is 10 bytes
# (seen in every turn-0 save). Types not confirmed for v123 are flagged; parsing stops at the first unknown type and the
# rest is kept raw, so a played save tells us which sizes changed.
ACTION_SIZES = {1: 11, 2: 21, 3: 9, 4: 9, 5: 11, 6: 21, 7: 13, 8: 3, 9: 9, 11: 11, 13: 9, 14: 9, 15: 1, 16: 11, 17: 9, 18: 9,
                20: 1, 21: 9, 24: 9, 25: 9, 27: 10, 28: 3, 29: 10, 30: 10,
                38: 9}   # 38: player + tile, seen from Cymanti (v123; meaning TBD)
ACTION_CONFIRMED_V123 = {1, 2, 3, 5, 6, 7, 8, 11, 13, 14, 15, 16, 18, 20, 21, 24, 27, 28, 30, 38}   # confirmed by exact-end parses of saves 9847d452 and 6e1bf8e0
ACTION_NAMES = {1: "Build", 2: "Attack", 3: "Recover", 5: "Train", 6: "Move", 7: "CaptureCity", 8: "Research", 9: "DestroyImprovement",
                11: "CityReward", 13: "Promote", 14: "ExamineRuins", 15: "EndTurn", 16: "Upgrade", 20: "StartMatch?", 21: "CityLevelUp"}

def read_actions(r):
    n = r.u16(); out = []
    for i in range(n):
        if r.o + 2 > len(r.b): return out, {"stopped_at": i, "reason": "end of data"}
        t = r.u16()
        if t not in ACTION_SIZES: return out, {"stopped_at": i, "reason": f"unknown action type {t}", "raw_tail": r.b[r.o - 2:].hex()}
        out.append({"type": t, "name": ACTION_NAMES.get(t, f"type{t}"), "raw": r.raw(ACTION_SIZES[t]).hex(), "confirmed_v123": t in ACTION_CONFIRMED_V123})
    return out, None

def read_state(data):
    """Full v123 save: initial state, 7 bytes, current state, 2 bytes, actions. The current state's first header field is a
    32-bit hash (also stored in the StartMatch action) rather than the version."""
    r = R(data); version = struct.unpack_from("<I", data, 0)[0]
    h0, t0 = read_map(r, version); p0 = read_players(r, version)
    gap = r.raw(7).hex()
    h1, t1 = read_map(r, version); p1 = read_players(r, version)
    pad = r.raw(2).hex()
    actions, problem = read_actions(r)
    trailer = None
    if problem is None and len(data) - r.o == 9:   # v123 trailer: 3 zero bytes, the state hash, the action count
        z, hsh, cnt = r.raw(3), r.u32(), r.u16(); trailer = {"hash": hsh, "action_count": cnt, "matches_list": cnt == len(actions)}
    return {"trailer": trailer,"version": version, "initial": {"header": h0, "tiles": t0, "players": p0}, "current": {"header": h1, "tiles": t1, "players": p1},
            "actions": actions, "actions_problem": problem, "gap_bytes": gap, "pad_bytes": pad, "unparsed_bytes": len(data) - r.o}

if __name__ == "__main__":
    raw = open(sys.argv[1], "rb").read(); data = decompress(raw); st = read_state(data)
    h = st["initial"]["header"]; cur = st["current"]["header"]
    out = {"format": "polytopia-state-json/2", "gameVersion": st["version"], "mapWidth": h["MapWidth"], "mapHeight": h["MapHeight"],
           "currentTurn": cur["CurrentTurn"], "header": {"MapHeaderInput": h}, "currentHeader": cur,
           "initialTiles": st["initial"]["tiles"], "initialPlayers": st["initial"]["players"],
           "currentTiles": st["current"]["tiles"], "currentPlayers": st["current"]["players"],
           "actions": st["actions"], "actionsProblem": st["actions_problem"], "unparsedBytes": st["unparsed_bytes"]}
    json.dump(out, open(sys.argv[2], "w"))
    print(f"OK v{st['version']} '{h['MapName']}' {h['MapWidth']}x{h['MapHeight']} turn {cur['CurrentTurn']} players {len(st['current']['players'])} "
          f"actions {len(st['actions'])} unparsed {st['unparsed_bytes']}")
