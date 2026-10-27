"""Thin Python wrapper over the Polyfish forward model (sim/pfcore bin pfapi serve; docs in sim/README.md).
    from pf_api import Sim
    s = Sim("saves/<id>_t12.json", player=3)       # load the end-of-save state, player 3 to move
    ms = s.moves()                                  # [{"key": {...}, "label": "Step Warrior (3,4)->(4,5)"}, ...]
    st = s.play(ms[1]["key"]); s.undo(); s.end_turn(); s.state()
    s.push(); ...; s.pop()                          # explore a copy, then go back to the position before push
    s.dice()                                        # from now on ruin rewards are sampled from data/distributions.json
Each call returns the state summary: turn, player, fingerprint, per tribe stars, cities and units [type, x, y, hp].
Search itself should run in Rust (src/api.rs); this is for scripts, scenarios and checks.
    python3 -I tools/pf_api.py <save> <player>     prints the legal moves, plays the first non-EndTurn one, undoes it"""
import json, os, subprocess, sys
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
BIN = os.path.join(ROOT, "sim", "pfcore", "target", "release", "pfapi")

class Sim:
    def __init__(self, save, player=1, which="current"):
        if not os.path.exists(BIN): raise SystemExit("build Polyfish first: cd sim/pfcore && cargo build --release")
        self.p = subprocess.Popen([BIN, "serve"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        self.summary = self._call(cmd="load", path=save, player=player, which=which)

    def _call(self, **c):
        self.p.stdin.write(json.dumps(c) + "\n"); self.p.stdin.flush()
        r = json.loads(self.p.stdout.readline())
        if "error" in r: raise ValueError(r["error"])
        return r["ok"]

    def moves(self): return self._call(cmd="moves")
    def play(self, key): return self._call(cmd="play", key=key)
    def end_turn(self): return self._call(cmd="end")
    def undo(self): return self._call(cmd="undo")
    def state(self): return self._call(cmd="state")
    def push(self): return self._call(cmd="push")
    def pop(self): return self._call(cmd="pop")
    def dice(self, seed=1): return self._call(cmd="dice", path=os.path.join(ROOT, "data", "distributions.json"), seed=seed)
    def close(self): self.p.stdin.close(); self.p.wait()

if __name__ == "__main__":
    s = Sim(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 1)
    ms = s.moves(); print(len(ms), "legal moves:", ", ".join(m["label"] for m in ms[:12]), "..." if len(ms) > 12 else "")
    first = next((m for m in ms if m["label"] != "EndTurn"), None)
    if first:
        f0 = s.state()["fingerprint"]; s.play(first["key"]); print("played", first["label"])
        print("undo restores the state:", s.undo()["fingerprint"] == f0)
    s.close()
