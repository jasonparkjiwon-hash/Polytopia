"""Parse Polyfish (HenBOMB/Polyfish, targets game version 115 'Cymanti Rework') static tables into JSON.
Usage: python3 parse_polyfish.py <polyfish-rs/src> <out.json>"""
import re, sys, json, os
src, out = sys.argv[1], sys.argv[2]
norm = lambda s: re.sub(r'[^a-z0-9]', '', s.lower())

def blocks(text, pat):
    # yields (name, body) for `Name => Struct { ... }` handling nested braces
    for m in re.finditer(pat, text):
        i = text.index('{', m.end() - 1); depth = 0; j = i
        while True:
            if text[j] == '{': depth += 1
            elif text[j] == '}':
                depth -= 1
                if depth == 0: break
            j += 1
        yield m.group(1), text[i + 1:j]

def field(body, name, cast=str):
    m = re.search(r'\b' + name + r'\s*:\s*([^,\n]+)', body)
    if not m: return None
    v = m.group(1).strip()
    sm = re.match(r'Some\((.*)\)$', v)
    if sm: v = sm.group(1)
    if v == 'None': return None
    v = v.split('::')[-1]
    try: return cast(v)
    except Exception: return v

units = {}
t = open(os.path.join(src, 'settings/units.rs')).read()
for name, body in blocks(t, r'U::(\w+)\s*=>\s*UnitSetting\s*\{'):
    sk = re.search(r'skills!\[([^\]]*)\]', body)
    units[name] = {"cost": field(body, 'cost', int), "attack": field(body, 'attack', float),
                   "movement": field(body, 'movement', int), "defense": field(body, 'defense', float),
                   "range": field(body, 'range', int), "health": field(body, 'health', float),
                   "upgrade_from": field(body, 'upgrade_from'),
                   "skills": sorted(s.strip().split('::')[-1] for s in sk.group(1).split(',') if s.strip()) if sk else []}
techs = {}
t = open(os.path.join(src, 'settings/technology.rs')).read()
for name, body in blocks(t, r'^\s{8}(\w+)\s*=>\s*TechnologySetting\s*\{'.replace('^', '(?m)^')):
    techs[name] = {"tier": field(body, 'tier', int), "requires": field(body, 'requires'),
                   "replaces_tech": field(body, 'replaces_tech'), "tribe_type": field(body, 'tribe_type'),
                   "unlocks_unit": field(body, 'unlocks_unit'), "unlocks_structure": field(body, 'unlocks_structure'),
                   "unlocks_terrain": field(body, 'unlocks_terrain'), "explicit_cost": field(body, 'explicit_cost', int)}
res = {}
t = open(os.path.join(src, 'settings/resources.rs')).read()
for name, body in blocks(t, r'(?m)^\s{8}(\w+)\s*=>\s*ResourceSetting\s*\{'):
    vis = re.search(r'visible_required:\s*vec!\[([^\]]*)\]', body)
    res[name] = {"cost": field(body, 'cost', int), "tech_required": field(body, 'tech_required'),
                 "struct_required": field(body, 'struct_required'),
                 "visible_required": [v.strip() for v in vis.group(1).split(',') if v.strip()] if vis else [],
                 "reward_pop": field(body, 'reward_pop', int), "reward_stars": field(body, 'reward_stars', int)}
structs = {}
t = open(os.path.join(src, 'settings/structures.rs')).read()
for name, body in blocks(t, r'StructureType::(\w+)\s*=>\s*StructureSetting\s*\{'):
    structs[name] = {k: field(body, k, int) if k in ("cost","reward_pop","reward_stars","reward_score") else field(body, k) for k in ("cost", "reward_pop", "reward_stars", "reward_score", "tribe_type")}
json.dump({"source": "HenBOMB/Polyfish polyfish-rs/src/settings (game version 115, commit 2026-09-02)",
           "units": units, "techs": techs, "resources": res, "structures": structs}, open(out, 'w'), indent=1)
print(len(units), "units", len(techs), "techs", len(res), "resources", len(structs), "structures")
