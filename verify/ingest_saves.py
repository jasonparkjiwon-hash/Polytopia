"""Ingest saves into the save library. Accepts iPhone exports (text files: first line = original path, then base64 of
the .state) or raw .state files (to rebuild the JSONs: python3 -I verify/ingest_saves.py saves saves/*.state).
Each save is decoded, parsed (state_v123), stored as <library>/<save-id>.state + .json, and listed in <library>/index.json.
Usage: python3 -I ingest_saves.py <library_dir> <attachment.txt> [more...]"""
import sys, os, re, json, base64, hashlib
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import state_v123 as S

lib = sys.argv[1]; os.makedirs(lib, exist_ok=True)
idx_path = os.path.join(lib, "index.json")
index = json.load(open(idx_path)) if os.path.exists(idx_path) else {}

def to_json(st):
    h = st["initial"]["header"]; cur = st["current"]["header"]; tiles = st["initial"]["tiles"]
    return {"format": "polytopia-state-json/2", "gameVersion": st["version"], "mapWidth": h["MapWidth"], "mapHeight": h["MapHeight"],
           "currentTurn": cur["CurrentTurn"], "header": {"MapHeaderInput": h}, "currentHeader": cur,
           "initialTiles": tiles, "initialPlayers": [p for p in st["initial"]["players"] if p["PlayerId"] != 255],
           "currentTiles": st["current"]["tiles"] if cur["CurrentTurn"] > 0 else "same as initialTiles (turn 0)",
           "currentPlayers": [p for p in st["current"]["players"] if p["PlayerId"] != 255],
           "actions": st["actions"], "actionsProblem": st["actions_problem"], "unparsedBytes": st["unparsed_bytes"]}

for f in sys.argv[2:]:
    if f.endswith(".state"):
        raw = open(f, "rb").read(); path = os.path.basename(f)
        m = re.match(r"(.+)_t(\d+)\.state$", path)
        if m:                                                   # per-turn copy: rebuild only its own JSON
            data = S.decompress(raw); st = S.read_state(data)
            out = to_json(st); tid = m.group(1) + "_t" + m.group(2)
            json.dump(out, open(os.path.join(lib, tid + ".json"), "w")); print(tid, "rebuilt"); continue
    else:
        lines = open(f).read().strip().splitlines()
        path = lines[0].strip(); b64 = "".join(l.strip() for l in lines[1:])
        raw = base64.b64decode(b64)
    sid = re.search(r"([0-9a-f-]{36})\.state", path).group(1) if re.search(r"([0-9a-f-]{36})\.state", path) else hashlib.sha1(raw).hexdigest()[:12]
    open(os.path.join(lib, sid + ".state"), "wb").write(raw)
    data = S.decompress(raw); st = S.read_state(data); ver = st["version"]
    h = st["initial"]["header"]; cur = st["current"]["header"]
    out = to_json(st)
    json.dump(out, open(os.path.join(lib, sid + ".json"), "w"))
    if cur["CurrentTurn"] > 0:   # the same game exported again later reuses its id: keep a copy per turn as well
        tid = f"{sid}_t{cur['CurrentTurn']}"
        open(os.path.join(lib, tid + ".state"), "wb").write(raw); json.dump(out, open(os.path.join(lib, tid + ".json"), "w"))
        index[tid] = dict(path=index.get(tid, {}).get("path", path), turn=cur["CurrentTurn"], actions=len(st["actions"]), map_name=h["MapName"], snapshot_of=sid)
    index[sid] = {"device_path": index.get(sid, {}).get("device_path", path), "map_name": h["MapName"], "size": h["MapWidth"], "version": ver, "turn": cur["CurrentTurn"], "actions": len(st["actions"]), "actions_ok": st["actions_problem"] is None and st["unparsed_bytes"] == 0,
                  "you": next((p["Tribe"] for p in st["initial"]["players"] if p["AutoPlay"] == 0 and p["PlayerId"] != 255), None),
                  "difficulty": h["Difficulty"], "opponents": h["Opponents"], "seed": h["Seed"], "game_mode": h["GameModeBase"]}
    print(sid, index[sid])
json.dump(index, open(idx_path, "w"), indent=1)
