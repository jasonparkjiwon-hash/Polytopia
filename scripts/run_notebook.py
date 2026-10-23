"""Execute a notebook's code cells in order in one namespace (handles %%writefile), headless."""
import json, sys, os, io, contextlib, traceback
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
nb = json.load(open(sys.argv[1])); work = sys.argv[2]; os.makedirs(work, exist_ok=True); os.chdir(work)
ns = {"__name__": "__main__"}; figs = 0
plt.show = lambda *a, **k: None
for i, c in enumerate(nb["cells"]):
    if c["cell_type"] != "code": continue
    src = "".join(c["source"])
    if src.startswith("%%writefile"):
        path, body = src.split("\n", 1); path = path.split(None, 1)[1].strip()
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True); open(path, "w").write(body); print(f"[cell {i}] wrote {path}"); continue
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf): exec(compile(src, f"cell{i}", "exec"), ns)
        out = buf.getvalue()
        print(f"[cell {i}] OK\n" + "\n".join("   " + l for l in out.splitlines()[:14]))
        for fn in plt.get_fignums():
            figs += 1; plt.figure(fn).savefig(f"fig{figs}.png", dpi=70); plt.close(fn)
    except Exception:
        print(f"[cell {i}] ERROR\n", buf.getvalue()[-800:], traceback.format_exc()[-1500:]); sys.exit(1)
print("ALL CELLS RAN;", figs, "figures saved in", work)
