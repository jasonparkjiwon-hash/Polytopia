"""Belief sampler from Python (fog-inference; Rust in sim/pfcore/src/belief.rs, bin pffog).
    from pf_belief import sample_belief
    s = sample_belief("saves/<id>_t5.json", pov=1, n=50, seed=1, outdir="/tmp/beliefs")
    s[0] -> {"sample": 0, "path": ".../belief_0.json", "hidden_tiles": 800, "hidden_villages": .., "hidden_ruins": .., "hidden_capitals": [[x, y], ...]}
Each sample file is a polyfish Game JSON (Game::from_json): pov's view kept exactly, hidden terrain/resources/villages/ruins/capitals drawn.
Model: data/belief_model.json (python3 -I tools/pf_belief.py train: fits on every save in saves/ and rewrites it)."""
import glob, json, os, subprocess, sys
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
BIN = os.path.join(ROOT, "sim", "pfcore", "target", "release", "pffog")
MODEL = os.path.join(ROOT, "data", "belief_model.json")

def sample_belief(save, pov, n=50, seed=1, outdir="beliefs", model=MODEL):
    os.makedirs(outdir, exist_ok=True)
    r = subprocess.run([BIN, "sample", save, str(pov), str(n), str(seed), model, outdir], capture_output=True, text=True, check=True)
    return [json.loads(l) for l in r.stdout.splitlines() if l.startswith("{")]

if __name__ == "__main__":
    if sys.argv[1:2] == ["train"]:
        saves = sorted(glob.glob(os.path.join(ROOT, "saves", "*_t1.json")) + glob.glob(os.path.join(ROOT, "saves", "*_t5.json")) + glob.glob(os.path.join(ROOT, "saves", "*_t8.json")) + glob.glob(os.path.join(ROOT, "saves", "*_t11.json")) + glob.glob(os.path.join(ROOT, "saves", "*_t12.json")))
        print(subprocess.run([BIN, "train", MODEL] + saves, capture_output=True, text=True, check=True).stdout)
    else:
        for s in sample_belief(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]) if len(sys.argv) > 3 else 3, 1, "/tmp/beliefs"): print(s)
