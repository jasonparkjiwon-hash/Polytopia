"""
polymap.py - seedable Polytopia-style map generator.

Based on the community script (QuasiStellar's Polytopia-Map-Generator logic) with:
  * its own RNG (random.Random(seed)) so maps are reproducible
  * no dependency on the missing `utils` module
  * the script's bugs fixed (Kickoo `break`, undefined `territory`)
  * map types with the wiki's quadrant capital placement and suburbs

IMPORTANT: this is a reimplementation, NOT the game's code. Things marked
[WIKI] come from the Polytopia wiki's Map Generation page; things marked
[GUESS] are my own placeholders and have not been checked against the real game.
"""
import math
import random
from dataclasses import dataclass, field

# ---------------------------------------------------------------- tribes
TRIBE_ORDER = ['Xin-xi', 'Imperius', 'Bardur', 'Oumaji', 'Kickoo', 'Hoodrick',
               'Luxidoor', 'Vengir', 'Zebasi', 'Ai-mo', 'Quetzali', 'Yadakk',
               'Aquarion', 'Elyrion']
REGULAR_TRIBES = TRIBE_ORDER[:12]

# digit -> multiplier, transcribed from the community script's underscore names
_MULT = {1: 0.1, 2: 0.5, 3: 1.0, 4: 1.5, 5: 2.0}
# one digit per tribe, in TRIBE_ORDER
_DIGITS = {
    'forest':   [3, 3, 3, 1, 3, 4, 3, 3, 2, 3, 3, 2, 2, 3],
    'mountain': [4, 3, 3, 3, 2, 2, 3, 3, 2, 4, 3, 2, 3, 2],
    'metal':    [3, 3, 3, 3, 3, 3, 3, 5, 3, 3, 1, 3, 3, 3],
    'fruit':    [3, 3, 4, 3, 3, 3, 5, 1, 2, 3, 5, 4, 3, 3],
    'crop':     [3, 3, 1, 3, 3, 3, 3, 3, 3, 1, 1, 3, 3, 4],
    'game':     [3, 3, 5, 3, 3, 3, 2, 1, 3, 3, 3, 3, 3, 3],
    'fish':     [3, 3, 3, 3, 4, 3, 3, 1, 3, 3, 3, 3, 3, 3],
    'whale':    [3] * 14,
}
WATER_CHANCE = {'Kickoo': 0.4, 'Aquarion': 0.3}   # extra ocean tiles in own territory

GENERAL = {'mountain': 0.15, 'forest': 0.4, 'fruit': 0.5, 'crop': 0.5,
           'fish': 0.5, 'game': 0.5, 'whale': 0.4, 'metal': 0.5}
BORDER_EXPANSION = 1 / 3


def tw(kind, tribe):
    """tribe weight multiplier for a terrain/resource kind"""
    return _MULT[_DIGITS[kind][TRIBE_ORDER.index(tribe)]]


# ---------------------------------------------------------------- map types
# placement: 'quadrant' [WIKI: Drylands, Lakes, Archipelago, Waterworld]
#            'spread'   farthest-point (community script) for Continents
#            'coastal'  farthest-point preferring coast [WIKI: Pangea]
# suburbs:   up to N villages near each capital [WIKI: Lakes, Archipelago]
# land/density values are [GUESS]: the wiki only says each type has a "wetness".
# NOTE: `land` is the INITIAL random land fraction. The smoothing pass is a steep
# sigmoid (0.40 -> ~0.21 final, 0.50 -> ~0.50, 0.60 -> ~0.76), so these were tuned
# empirically to hit rough final land shares: drylands ~.85, lakes ~.70,
# continents ~.47, pangea ~.55, archipelago ~.33, waterworld ~.22  [all GUESS].
MAP_TYPES = {
    'drylands':    dict(land=0.64, placement='quadrant', suburbs=0, density=0.55),
    'lakes':       dict(land=0.55, placement='quadrant', suburbs=2, density=0.55),
    'continents':  dict(land=0.50, placement='spread',   suburbs=0, density=0.55, min_island=6),
    'pangea':      dict(land=0.55, placement='coastal',  suburbs=0, density=0.55, one_island=True),
    'archipelago': dict(land=0.44, placement='quadrant', suburbs=2, density=0.50),
    'waterworld':  dict(land=0.41, placement='quadrant', suburbs=0, density=0.45),
}


# ---------------------------------------------------------------- data
@dataclass
class GameMap:
    size: int
    map_type: str
    seed: int
    tribes: list
    terrain: list            # 'ocean' 'water' 'ground' 'forest' 'mountain'
    above: list              # None 'capital' 'village' 'fruit' 'crop' 'game' 'fish' 'whale' 'metal' 'ruin'
    owner: list              # tribe whose territory the tile fell in (internal, hidden from players)
    capitals: list = field(default_factory=list)   # [(cell, tribe)]
    suburbs: list = field(default_factory=list)

    def rc(self, cell):
        return divmod(cell, self.size)

    def ascii(self):
        sym = {'ocean': 'o', 'water': '~', 'ground': '.', 'forest': 'f', 'mountain': 'm'}
        ab = {'capital': '@', 'village': 'v', 'ruin': 'r', 'fruit': 'F', 'crop': 'C',
              'game': 'G', 'fish': 'S', 'whale': 'W', 'metal': 'M'}
        rows = []
        for r in range(self.size):
            line = ''
            for c in range(self.size):
                i = r * self.size + c
                line += ab.get(self.above[i]) or sym[self.terrain[i]]
            rows.append(line)
        return '\n'.join(rows)


# ---------------------------------------------------------------- grid helpers
def cheb(a, b, n):
    return max(abs(a // n - b // n), abs(a % n - b % n))


def ring(cell, r, n):
    """all cells within Chebyshev distance r (excluding the cell itself)"""
    row, col = divmod(cell, n)
    out = []
    for dr in range(-r, r + 1):
        for dc in range(-r, r + 1):
            if dr == 0 and dc == 0:
                continue
            rr, cc = row + dr, col + dc
            if 0 <= rr < n and 0 <= cc < n:
                out.append(rr * n + cc)
    return out


def plus(cell, n):
    row, col = divmod(cell, n)
    out = []
    for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        rr, cc = row + dr, col + dc
        if 0 <= rr < n and 0 <= cc < n:
            out.append(rr * n + cc)
    return out


def components(land, n):
    """connected components of land cells (8-connectivity)"""
    seen, comps = set(), []
    for start in land:
        if start in seen:
            continue
        comp, stack = [], [start]
        seen.add(start)
        while stack:
            c = stack.pop()
            comp.append(c)
            for nb in ring(c, 1, n):
                if nb in land and nb not in seen:
                    seen.add(nb)
                    stack.append(nb)
        comps.append(comp)
    return comps


# ---------------------------------------------------------------- generator
def generate(seed, size=16, map_type='lakes', tribes=None, smoothing=3, relief=4):
    if map_type not in MAP_TYPES:
        raise ValueError(f'map_type must be one of {list(MAP_TYPES)}')
    cfg = MAP_TYPES[map_type]
    rng = random.Random(seed)
    n = size
    N = n * n
    if tribes is None:
        tribes = rng.sample(REGULAR_TRIBES, 3)
    assert all(t in TRIBE_ORDER for t in tribes)

    # ---- 1. land: random seed cells then neighbour-majority smoothing
    land = [False] * N
    target = int(N * cfg['land'])
    for c in rng.sample(range(N), target):
        land[c] = True
    land_coeff = (0.5 + relief) / 9
    for _ in range(smoothing):
        new = [False] * N
        for c in range(N):
            nb = ring(c, 1, n) + [c]          # 3x3 block incl. self (assumption)
            water = sum(1 for x in nb if not land[x])
            new[c] = (water / len(nb)) <= land_coeff
        land = new

    # ---- 1b. island shaping [GUESS]
    comps = components({c for c in range(N) if land[c]}, n)
    if cfg.get('one_island') and comps:
        keep = set(max(comps, key=len))
        land = [c in keep for c in range(N)]
    elif cfg.get('min_island'):
        keep = set()
        for comp in comps:
            if len(comp) >= cfg['min_island']:
                keep.update(comp)
        land = [c in keep for c in range(N)]

    terrain = ['ground' if land[c] else 'ocean' for c in range(N)]
    above = [None] * N

    # ---- 2. capitals
    interior = lambda c: 2 <= c // n < n - 2 and 2 <= c % n < n - 2
    cand = [c for c in range(N) if terrain[c] == 'ground' and interior(c)]
    if len(cand) < len(tribes) * 4:           # degenerate map: fall back to any land
        cand = [c for c in range(N) if terrain[c] == 'ground']
    if len(cand) < len(tribes):
        return generate(seed + 7919, size, map_type, tribes, smoothing, relief)

    capitals = []
    if cfg['placement'] == 'quadrant':
        g = max(2, math.ceil(math.sqrt(len(tribes))))
        qsize = n / g
        quad = lambda c: (int((c // n) / qsize), int((c % n) / qsize))
        occupied = set()
        for _t in tribes:
            by_q = {}
            for c in cand:
                if c in capitals:              # never reuse a capital cell
                    continue
                by_q.setdefault(quad(c), []).append(c)
            free = {q: cs for q, cs in by_q.items() if q not in occupied}
            if not free:
                free = by_q                    # more tribes than usable quadrants
            qs = list(free)
            q = rng.choices(qs, weights=[len(free[x]) for x in qs])[0]   # weighted randomness [WIKI]
            cx, cy = (q[0] + 0.5) * qsize, (q[1] + 0.5) * qsize
            cs = free[q]
            w = [1.0 / (1 + math.hypot(c // n - cx, c % n - cy)) for c in cs]   # prefer quadrant centre [GUESS]
            pick = rng.choices(cs, weights=w)[0]
            capitals.append(pick)
            occupied.add(q)
    else:
        pool = cand
        if cfg['placement'] == 'coastal':      # [WIKI: Pangea prefers capitals next to water]
            coastal = [c for c in cand if any(terrain[x] == 'ocean' for x in ring(c, 1, n))]
            if len(coastal) >= len(tribes):
                pool = coastal
        capitals.append(rng.choice(pool))
        while len(capitals) < len(tribes):     # farthest-point, random tie-break
            best, best_d = [], -1
            for c in pool:
                d = min(cheb(c, k, n) for k in capitals)
                if d > best_d:
                    best, best_d = [c], d
                elif d == best_d:
                    best.append(c)
            capitals.append(rng.choice(best))
    for c, t in zip(capitals, tribes):
        above[c] = 'capital'

    # ---- 3. territories: random flood fill, one tile per tribe per round
    owner = [None] * N
    active = []
    for c, t in zip(capitals, tribes):
        owner[c] = t
        active.append([c])
    unowned = N - len(capitals)
    while unowned > 0:
        progressed = False
        for i, t in enumerate(tribes):
            while active[i]:
                src = rng.choice(active[i])
                free = [x for x in ring(src, 1, n) if owner[x] is None]
                if free:
                    pick = rng.choice(free)
                    owner[pick] = t
                    active[i].append(pick)
                    unowned -= 1
                    progressed = True
                    break
                active[i].remove(src)
        if not progressed:
            break

    # ---- 4. forest / mountain / extra ocean by tribe weights
    for c in range(N):
        if terrain[c] == 'ground' and above[c] is None:
            t = owner[c]
            r = rng.random()
            if r < GENERAL['forest'] * tw('forest', t):
                terrain[c] = 'forest'
            elif r > 1 - GENERAL['mountain'] * tw('mountain', t):
                terrain[c] = 'mountain'
            if rng.random() < WATER_CHANCE.get(t, 0):
                terrain[c] = 'ocean'
    # shallow water: ocean orthogonally touching land
    for c in range(N):
        if terrain[c] == 'ocean' and any(terrain[x] in ('ground', 'forest', 'mountain')
                                         for x in plus(c, n)):
            terrain[c] = 'water'

    # ---- 5. villages
    vmap = []
    for c in range(N):
        r, col = divmod(c, n)
        if terrain[c] in ('ocean', 'water', 'mountain') or r in (0, n - 1) or col in (0, n - 1):
            vmap.append(-1)
        else:
            vmap.append(0)

    def claim(c):                              # city blocks radius 2: spacing >= 3 [COMMUNITY SCRIPT]
        vmap[c] = 3
        for x in ring(c, 1, n):
            vmap[x] = max(vmap[x], 2)
        for x in ring(c, 2, n):
            vmap[x] = max(vmap[x], 1)

    for c in capitals:
        claim(c)
    villages, suburbs = [], []
    for c in capitals:                         # suburbs [WIKI: Lakes, Archipelago; up to two]
        for _ in range(cfg['suburbs']):
            opts = [x for x in range(N) if vmap[x] == 0 and 3 <= cheb(x, c, n) <= 4]
            if opts:
                v = rng.choice(opts)
                claim(v)
                suburbs.append(v)
                villages.append(v)
    # village count formula [WIKI]
    n_villages = round(((n / 3) ** 2 - len(capitals) - len(suburbs)) * cfg['density'])
    for _ in range(max(0, n_villages)):
        opts = [x for x in range(N) if vmap[x] == 0]
        if not opts:
            break
        v = rng.choice(opts)
        claim(v)
        villages.append(v)
    for v in villages:
        terrain[v] = 'ground'                  # villages sit on cleared ground
        above[v] = 'village'

    # ---- 6. resources (full chance next to cities, 1/3 two tiles out)
    def proc(c, p):
        return (vmap[c] == 2 and rng.random() < p) or \
               (vmap[c] == 1 and rng.random() < p * BORDER_EXPANSION)

    for c in range(N):
        t = owner[c]
        if above[c] is not None:
            continue
        ty = terrain[c]
        if ty == 'ground':
            fruit = GENERAL['fruit'] * tw('fruit', t)
            crop = GENERAL['crop'] * tw('crop', t)
            if proc(c, fruit * (1 - crop / 2)):
                above[c] = 'fruit'
            elif proc(c, crop * (1 - fruit / 2)):
                above[c] = 'crop'
        elif ty == 'forest':
            if proc(c, GENERAL['game'] * tw('game', t)):
                above[c] = 'game'
        elif ty == 'water':
            if proc(c, GENERAL['fish'] * tw('fish', t)):
                above[c] = 'fish'
        elif ty == 'ocean':
            if proc(c, GENERAL['whale'] * tw('whale', t)):
                above[c] = 'whale'
        elif ty == 'mountain':
            if proc(c, GENERAL['metal'] * tw('metal', t)):
                above[c] = 'metal'

    # ---- 7. ruins: ~1 per 40 tiles, at most a third at sea, never near cities
    n_ruins = round(N / 40)
    max_sea = round(n_ruins / 3)
    ruins, sea = 0, 0
    for _ in range(n_ruins * 50):
        if ruins >= n_ruins:
            break
        opts = [x for x in range(N) if vmap[x] in (-1, 0, 1) and above[x] is None
                and terrain[x] != 'water']
        if not opts:
            break
        r = rng.choice(opts)
        if terrain[r] == 'ocean':
            if sea >= max_sea:
                continue
            sea += 1
        above[r] = 'ruin'
        for x in ring(r, 1, n):
            vmap[x] = max(vmap[x], 2)
        ruins += 1

    # ---- 8. tribe starting guarantees near the capital
    def need(resource, base, count, cap):
        have = sum(1 for x in ring(cap, 1, n) if above[x] == resource)
        spots = [x for x in ring(cap, 1, n) if above[x] not in (resource, 'capital', 'village')]
        rng.shuffle(spots)
        while have < count and spots:
            x = spots.pop()
            terrain[x] = base
            above[x] = resource
            have += 1
            for nb in plus(x, n):
                if terrain[nb] == 'ocean':
                    terrain[nb] = 'water'

    for cap, t in zip(capitals, tribes):
        if t == 'Imperius':
            need('fruit', 'ground', 2, cap)
        elif t in ('Bardur', 'Elyrion'):
            need('game', 'forest', 2, cap)
        elif t == 'Zebasi':
            need('crop', 'ground', 1, cap)
        elif t == 'Kickoo':
            have = sum(1 for x in ring(cap, 1, n) if above[x] == 'fish')
            spots = [x for x in plus(cap, n) if above[x] is None]
            rng.shuffle(spots)
            while have < 2 and spots:
                x = spots.pop()
                terrain[x] = 'water'
                above[x] = 'fish'
                have += 1

    return GameMap(size=n, map_type=map_type, seed=seed, tribes=list(tribes),
                   terrain=terrain, above=above, owner=owner,
                   capitals=list(zip(capitals, tribes)), suburbs=suburbs)


if __name__ == '__main__':
    import sys
    mt = sys.argv[1] if len(sys.argv) > 1 else 'lakes'
    m = generate(seed=int(sys.argv[2]) if len(sys.argv) > 2 else 1, map_type=mt,
                 tribes=['Bardur', 'Imperius', 'Kickoo'])
    print(m.ascii())
