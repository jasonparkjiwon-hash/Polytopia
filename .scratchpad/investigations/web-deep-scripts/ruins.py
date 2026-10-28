import sys,os,json,glob,struct,collections
sys.path.insert(0,'/home/user/Polytopia/engine')
import economy as EC
from state import TRIBE, TERRAIN
games={}
for f in glob.glob('/home/user/Polytopia/saves/*_t*.json'):
    d=json.load(open(f)); games.setdefault(f.split('/')[-1][:8],[]).append(d)
for g,ds in sorted(games.items()):
    ds.sort(key=lambda d:d['currentTurn']); acts=max(ds,key=lambda d:len(d['actions']))['actions']
    for a,b in zip(ds,ds[1:]):
        tr={p['PlayerId']:TRIBE.get(p['Tribe']) for p in b['currentPlayers']}
        ru=[(x,acts[i]) for i in range(len(a['actions']),len(b['actions'])) for x in [acts[i]] if x['type']==14]
        if not ru: continue
        res=EC.check(a,b,acts)
        for x in {x['player'] if 'player' in x else None for _,x in ru}: pass
        byp=collections.defaultdict(list)
        for _,x in ru:
            raw=bytes.fromhex(x['raw']); byp[x.get('player',raw[0])].append(raw.hex())
        for pl,l in byp.items():
            r=res.get(pl)
            if r: print(g,a['currentTurn'],pl,tr.get(pl),len(l),'resid',r['residual'],'rs',r.get('ruin_stars'),l[:2])
