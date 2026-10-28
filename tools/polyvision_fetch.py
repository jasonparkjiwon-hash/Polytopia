"""Fetch the PolyVision phase1_pool_bardur_real maps (third-party data, no licence: never commit them).
Usage: python3 -I tools/polyvision_fetch.py <empty-outdir> [workers=4]
Downloads split_manifest.json, then every CSV, verifies SHA-256, skips files already cached."""
import json, hashlib, os, sys, urllib.request, concurrent.futures as cf
BASE = "https://raw.githubusercontent.com/NeoLorenzo/PolyVision/main/pol_env/Tribes/levels/phase1_pool_bardur_real/"
def get(url):
    for k in range(4):
        try:
            return urllib.request.urlopen(url, timeout=60).read()
        except Exception:
            if k == 3: raise
def main(out, workers=4):
    os.makedirs(out, exist_ok=True)
    mp = os.path.join(out, "split_manifest.json")
    if not os.path.exists(mp): open(mp, "wb").write(get(BASE + "split_manifest.json"))
    man = json.load(open(mp))["maps"]
    def one(e):
        p = os.path.join(out, e["relative_path"])
        if os.path.exists(p) and hashlib.sha256(open(p, "rb").read()).hexdigest() == e["csv_sha256"]: return "cached"
        os.makedirs(os.path.dirname(p), exist_ok=True)
        try: b = get(BASE + e["relative_path"])
        except Exception as ex: return "MISSING " + str(getattr(ex, "code", ex))
        if hashlib.sha256(b).hexdigest() != e["csv_sha256"]: return "BAD"
        open(p, "wb").write(b); return "ok"
    with cf.ThreadPoolExecutor(workers) as ex:
        res = list(ex.map(one, man))
    print({k: res.count(k) for k in set(res)})
    bad = [e["relative_path"] for e, r in zip(man, res) if r.startswith("MISSING") or r == "BAD"]
    print("first problems:", bad[:5])
if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 4)
