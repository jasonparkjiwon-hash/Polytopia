"""Render wiki-generator sample maps (one per map type) to a PNG for a visual sanity check."""
import sys, os, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import wiki_mapgen as W
COL = {"Field": "#c9d98a", "Forest": "#4f8a3c", "Mountain": "#8c8c8c", "Water": "#7fb8e6", "Ocean": "#2f6fae"}
GLY = {"AquaCrop": ("d", "#2ec4b6"), "Fruit": ("o", "#d6336c"), "Crop": ("s", "#e8b923"), "Game": ("^", "#7a4a1f"), "Metal": ("D", "#e0e0e0"), "Fish": ("o", "#ffffff"), "Starfish": ("*", "#ffd43b"), "Spores": ("s", "#9b59b6")}
MODE = sys.argv[2] if len(sys.argv) > 2 else "measured"
out = sys.argv[1]; types = ["lakes", "drylands", "continents", "pangea", "archipelago", "waterworld"]
fig, axes = plt.subplots(3, 2, figsize=(8, 12.5))
for ax, mt in zip(axes.flat, types):
    g = W.generate(mt, 16, ["Imperius", "Bardur", "XinXi", "Kickoo"], seed=7, mode=MODE); n = g["size"]
    for i, t in g["tiles"].items():
        x, y = t["x"], n - 1 - t["y"]
        ax.add_patch(Rectangle((x, y), 1, 1, color=COL[t["terrain"]]))
        if t["resource"]:
            m, c = GLY[t["resource"]]; ax.plot(x + .5, y + .5, m, color=c, ms=4, mec="black", mew=0.4)
        if t["improvement"] == "Village":
            ax.add_patch(Rectangle((x + .15, y + .15), .7, .7, fill=False, ec="red" if t["capital_of"] else "black", lw=2 if t["capital_of"] else 1.2))
        elif t["improvement"] == "Ruin": ax.text(x + .5, y + .5, "R", ha="center", va="center", fontsize=7, weight="bold")
    ax.set_xlim(0, n); ax.set_ylim(0, n); ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([])
    ax.set_title(f"{mt}  (land {sum(t['terrain'] not in ('Water','Ocean') for t in g['tiles'].values())/n/n:.0%})", fontsize=11)
fig.suptitle(f"Generator ({MODE} mode), 16x16, seed 7\nred square = capital, black = village, R = ruin\no fruit, s crop, ^ animal, D metal, white o fish, teal diamond AquaCrop, * starfish", fontsize=10)
plt.tight_layout(); plt.savefig(out, dpi=110); print("saved", out)
