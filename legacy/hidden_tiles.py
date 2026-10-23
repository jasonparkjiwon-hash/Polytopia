"""
hidden_tiles.py - Bayesian hidden-tile estimator for Polytopia-style fog of war.

Idea: the generator (polymap.py) is a known stochastic process. We simulate many
maps, simulate what a player would have revealed, and learn P(tile contents | what
the player can see). Prediction = hierarchical Dirichlet smoothing over count tables
(global -> coarse features -> finer features), so rare feature combinations back off
to broader ones instead of overfitting. On top of that we apply EXACT rule
constraints (village spacing, border rule) and a capital-count constraint.

Caveat: this learns the *reimplementation's* statistics. Against the real game it is
only as good as polymap's match to it. To adapt it, swap the training maps for real
revealed-map logs; the estimator itself does not care where maps come from.
"""
import math
import random
from collections import defaultdict

import polymap
from polymap import cheb, ring

LAND = ('ground', 'forest', 'mountain')


# ------------------------------------------------------------------ labels
def label(m, c):
    return f"{m.terrain[c]}|{m.above[c] or '-'}"


def base_terrain(lab):
    return lab.split('|')[0]


# ------------------------------------------------------------------ fog
def simulate_reveal(m, viewer, rng, explore=6):
    """Cells a player controlling capital #viewer has seen.
    Radius-2 around own capital, then `explore` random-walk scouting trips
    that reveal radius-1 around each step."""
    n = m.size
    cap = m.capitals[viewer][0]
    seen = {cap} | set(ring(cap, 2, n))
    frontier = list(seen)
    for _ in range(explore):
        cur = rng.choice(frontier)
        for _step in range(rng.randint(2, 5)):
            cur = rng.choice(ring(cur, 1, n))
            new = {cur} | set(ring(cur, 1, n))
            seen |= new
            frontier.extend(new)
    return seen


# ------------------------------------------------------------------ features
def _bucket_lf(land, known):
    if known == 0:
        return 'none'
    f = land / known
    return 'lo' if f < 1 / 3 else ('mid' if f < 2 / 3 else 'hi')


def features(m_size, obs, viewer_cap, c):
    """obs: dict cell -> (terrain, above). Returns (k1, k2, k3) hierarchical keys."""
    n = m_size
    nb = ring(c, 1, n)
    known1 = [obs[x] for x in nb if x in obs]
    nk = 0 if not known1 else (1 if len(known1) <= 2 else (2 if len(known1) <= 5 else 3))
    # land fraction among revealed tiles within radius 2 (wider context than radius 1:
    # smoothing makes land/ocean spatially correlated over a few tiles)
    known = [obs[x] for x in ring(c, 2, n) if x in obs]
    land = sum(1 for t, _a in known if t in LAND)
    lf = _bucket_lf(land, len(known))

    dc = 6
    hint = 'none'
    best_cap = 99
    for x, (t, a) in obs.items():
        if a in ('capital', 'village'):
            d = cheb(c, x, n)
            dc = min(dc, min(d, 5)) if d < 6 else dc
        if a == 'capital':
            d = cheb(c, x, n)
            if d < best_cap:
                best_cap = d
    edge = min(min(c // n, n - 1 - c // n, c % n, n - 1 - c % n), 2)
    dv = min(cheb(c, viewer_cap, n) // 3, 5)
    k1 = (lf, edge)
    k2 = (dc, lf, edge, dv)
    k3 = (dc, lf, edge, dv, nk)
    return k1, k2, k3


# ------------------------------------------------------------------ model
class HiddenTileModel:
    def __init__(self, k=15.0):
        self.k = k
        self.glob = defaultdict(float)
        self.t1 = defaultdict(lambda: defaultdict(float))
        self.t2 = defaultdict(lambda: defaultdict(float))
        self.t3 = defaultdict(lambda: defaultdict(float))
        self.labels = set()

    def add(self, lab, k1, k2, k3):
        self.labels.add(lab)
        self.glob[lab] += 1
        self.t1[k1][lab] += 1
        self.t2[k2][lab] += 1
        self.t3[k3][lab] += 1

    def _smooth(self, counts, prior):
        tot = sum(counts.values())
        return {l: (counts.get(l, 0.0) + self.k * prior[l]) / (tot + self.k) for l in self.labels}

    def predict(self, k1, k2, k3):
        gt = sum(self.glob.values())
        p0 = {l: (self.glob[l] + 0.01) / (gt + 0.01 * len(self.labels)) for l in self.labels}
        p1 = self._smooth(self.t1[k1], p0) if k1 in self.t1 else p0
        p2 = self._smooth(self.t2[k2], p1) if k2 in self.t2 else p1
        p3 = self._smooth(self.t3[k3], p2) if k3 in self.t3 else p2
        return p3

    def prior_only(self):
        gt = sum(self.glob.values())
        return {l: (self.glob[l] + 0.01) / (gt + 0.01 * len(self.labels)) for l in self.labels}


def observation(m, seen):
    return {c: (m.terrain[c], m.above[c]) for c in seen}


def make_example(seed, size, map_type, n_tribes=3, explore=6):
    rng = random.Random(seed * 7 + 1)
    tribes = rng.sample(polymap.REGULAR_TRIBES, n_tribes)
    m = polymap.generate(seed, size, map_type, tribes)
    viewer = rng.randrange(len(m.capitals))
    seen = simulate_reveal(m, viewer, rng, explore)
    return m, viewer, seen


def train(map_type, seeds, size=16, explore=6):
    model = HiddenTileModel()
    for s in seeds:
        m, viewer, seen = make_example(s, size, map_type, explore=explore)
        obs = observation(m, seen)
        vcap = m.capitals[viewer][0]
        for c in range(m.size ** 2):
            if c in seen:
                continue
            k1, k2, k3 = features(m.size, obs, vcap, c)
            model.add(label(m, c), k1, k2, k3)
    return model


# ------------------------------------------------------------------ inference
def apply_rules(probs, size, obs, n_capitals_total, c):
    """Exact constraints from the generator's rules. Mutates and renormalises."""
    row, col = divmod(c, size)
    if row in (0, size - 1) or col in (0, size - 1):
        probs['ground|village'] = 0.0                     # villages never spawn on the border
    for x, (t, a) in obs.items():
        if a in ('capital', 'village') and cheb(c, x, size) <= 2:
            probs['ground|village'] = 0.0                 # min city spacing of 3
    s = sum(probs.values())
    return {l: p / s for l, p in probs.items()}


def infer(model, size, obs, viewer_cap, n_capitals_total=3, use_rules=True, use_capital_count=True):
    """Posterior over labels for every hidden tile. Returns {cell: {label: p}}."""
    post = {}
    for c in range(size * size):
        if c in obs:
            continue
        k1, k2, k3 = features(size, obs, viewer_cap, c)
        p = model.predict(k1, k2, k3)
        if use_rules:
            p = apply_rules(p, size, obs, n_capitals_total, c)
        post[c] = p
    if use_capital_count:
        known_caps = sum(1 for _t, a in obs.values() if a == 'capital')
        remaining = n_capitals_total - known_caps
        cap_labels = [l for l in model.labels if l.endswith('|capital')]
        mass = sum(post[c].get(l, 0.0) for c in post for l in cap_labels)
        if remaining <= 0:
            scale = 0.0                       # every capital is already visible: none can hide
        elif mass > 0:
            scale = remaining / mass
        else:
            scale = None
        if scale is not None:
            for c, p in post.items():
                for l in cap_labels:
                    p[l] = min(0.95, p.get(l, 0.0) * scale)
                s = sum(p.values())
                post[c] = {l: v / s for l, v in p.items()}
    return post


# ------------------------------------------------------------------ evaluation
def evaluate(model, map_type, seeds, size=16, explore=6):
    res = {k: dict(ll=0.0, n=0, hit=0, bhit=0, tll=0.0, near_n=0, near_hit=0, far_n=0, far_hit=0,
                   ls_hit=0, ls_near_n=0, ls_near_hit=0, ls_far_n=0, ls_far_hit=0)
           for k in ('prior (no fog info)', 'model', 'model + rules')}
    cap_ranks = {k: [] for k in res}
    for s in seeds:
        m, viewer, seen = make_example(s, size, map_type, explore=explore)
        obs = observation(m, seen)
        vcap = m.capitals[viewer][0]
        variants = {
            'prior (no fog info)': None,
            'model': infer(model, size, obs, vcap, len(m.capitals), use_rules=False, use_capital_count=False),
            'model + rules': infer(model, size, obs, vcap, len(m.capitals), use_rules=True, use_capital_count=True),
        }
        prior = model.prior_only()
        hidden = [c for c in range(size * size) if c not in seen]
        hidden_caps = [c for c, _t in m.capitals if c not in seen]
        for name, post in variants.items():
            for c in hidden:
                p = prior if post is None else post[c]
                truth = label(m, c)
                R = res[name]
                R['ll'] += -math.log(max(p.get(truth, 0.0), 1e-4))
                R['n'] += 1
                R['hit'] += max(p, key=p.get) == truth
                # base-terrain accuracy (marginalise over overlays)
                bt = defaultdict(float)
                for l, v in p.items():
                    bt[base_terrain(l)] += v
                ok = max(bt, key=bt.get) == base_terrain(truth)
                R['bhit'] += ok
                R['tll'] += -math.log(max(bt.get(base_terrain(truth), 0.0), 1e-4))
                near = any(x in seen for x in ring(c, 1, size))
                R['near_n' if near else 'far_n'] += 1
                R['near_hit' if near else 'far_hit'] += ok
                # land vs sea (forest/mountain are per-tile noise, so this isolates spatial structure)
                pl = sum(v for l, v in p.items() if base_terrain(l) in LAND)
                is_land = base_terrain(truth) in LAND
                R['ls_hit'] += (pl >= 0.5) == is_land
                R['ls_near_n' if near else 'ls_far_n'] += 1
                R['ls_near_hit' if near else 'ls_far_hit'] += (pl >= 0.5) == is_land
            # capital recovery: rank of each hidden capital among hidden tiles by P(capital)
            for cc in hidden_caps:
                def pc(c):
                    p = prior if post is None else post[c]
                    return sum(v for l, v in p.items() if l.endswith('|capital'))
                order = sorted(hidden, key=pc, reverse=True)
                cap_ranks[name].append(order.index(cc) / len(hidden))
    out = {}
    for name, R in res.items():
        ranks = cap_ranks[name]
        out[name] = dict(
            logloss=R['ll'] / R['n'],
            label_acc=R['hit'] / R['n'],
            terrain_acc=R['bhit'] / R['n'],
            terrain_ll=R['tll'] / R['n'],
            near_acc=R['near_hit'] / max(1, R['near_n']),
            far_acc=R['far_hit'] / max(1, R['far_n']),
            near_share=R['near_n'] / R['n'],
            ls_acc=R['ls_hit'] / R['n'],
            ls_near=R['ls_near_hit'] / max(1, R['ls_near_n']),
            ls_far=R['ls_far_hit'] / max(1, R['ls_far_n']),
            capital_top10pct=sum(1 for r in ranks if r < 0.10) / max(1, len(ranks)),
            capital_median_rank_pct=100 * sorted(ranks)[len(ranks) // 2] if ranks else float('nan'),
        )
    return out


if __name__ == '__main__':
    import argparse
    import time
    ap = argparse.ArgumentParser()
    ap.add_argument('--types', default='lakes')
    ap.add_argument('--train', type=int, default=1500)
    ap.add_argument('--test', type=int, default=300)
    ap.add_argument('--size', type=int, default=16)
    ap.add_argument('--explore', type=int, default=6)
    a = ap.parse_args()
    for mt in a.types.split(','):
        t0 = time.time()
        model = train(mt, range(a.train), a.size, a.explore)
        r = evaluate(model, mt, range(100000, 100000 + a.test), a.size, a.explore)
        print(f'\n== {mt}  (train {a.train} maps, test {a.test}, {time.time() - t0:.0f}s) ==')
        print(f"{'':22s}{'full LL':>8s}{'terr LL':>8s}{'terr acc':>9s}{'land/sea':>9s}{'ls near':>8s}{'ls far':>7s}{'cap top10%':>11s}{'cap med':>9s}")
        for name, v in r.items():
            print(f"{name:22s}{v['logloss']:8.3f}{v['terrain_ll']:8.3f}{v['terrain_acc']:9.3f}"
                  f"{v['ls_acc']:9.3f}{v['ls_near']:8.2f}{v['ls_far']:7.2f}"
                  f"{v['capital_top10pct']:11.2f}{v['capital_median_rank_pct']:8.0f}%")
        print(f"(near = hidden tile touching a revealed tile: {r['model']['near_share']:.0%} of hidden tiles; "
              f"LL = mean log-loss in nats, lower is better; cap med = median rank of true capital, lower is better)")
