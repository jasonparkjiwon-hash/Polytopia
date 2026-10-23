"""Extract Rust enums (name = int) from Polyfish types.rs -> JSON id maps. These mirror the real game's enum ids
because Polyfish loads JSON states captured from the real game. Usage: extract_enums.py <types.rs> <out.json>"""
import re, sys, json
t = open(sys.argv[1]).read()
out = {}
for m in re.finditer(r'pub enum (\w+)\s*\{(.*?)\n\}', t, re.S):
    vals = {}; nxt = 0
    for line in m.group(2).split('\n'):
        line = line.split('//')[0].strip().rstrip(',')
        if not line or line.startswith('#'): continue
        mm = re.match(r'^(\w+)\s*(?:=\s*(-?\d+))?$', line)
        if not mm: continue
        v = int(mm.group(2)) if mm.group(2) is not None else nxt
        vals[str(v)] = mm.group(1); nxt = v + 1
    if vals: out[m.group(1)] = vals
json.dump(out, open(sys.argv[2], 'w'), indent=1)
print({k: len(v) for k, v in out.items()})
