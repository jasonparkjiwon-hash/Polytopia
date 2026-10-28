import sys,os,json,glob,collections
sys.path.insert(0,'/home/user/Polytopia/engine')
import economy as EC
games={}
for f in glob.glob('/home/user/Polytopia/saves/*_t*.json'):
    d=json.load(open(f)); games.setdefault(f.split('/')[-1][:8],[]).append(d)
rows=[]
for g,ds in sorted(games.items()):
    ds.sort(key=lambda d:d['currentTurn']); acts=max(ds,key=lambda d:len(d['actions']))['actions']
    for a,b in zip(ds,ds[1:]):
        if b['currentTurn']-a['currentTurn']!=1: continue
        res=EC.check(a,b,acts)
        pa={p['PlayerId']:p for p in a['currentPlayers']}; pb={p['PlayerId']:p for p in b['currentPlayers']}
        for pl,r in res.items():
            if r.get('met')!=1 or r['residual'] is None: continue
            o=list(set(pb[pl]['Encountered'])-set(pa[pl]['Encountered']))[0]
            fm={d['PlayerId']:d['FirstMeet'] for d in pb[pl].get('Diplomacy',())}.get(o)
            rows.append((g,a['currentTurn'],pl,o,pa.get(o,{}).get('Score'),pb[o]['Score'],fm,r['residual'],r['unknown'] and 1 or 0))
import collections; c=collections.Counter(min(5,-(-r[5]//1000)) for r in rows if r[7]==0); print(sorted(c.items()))
bad=[r for r in rows if r[7]!=0]
print(len(rows),'single-meet 1-turn rows;',len(bad),'off')
for r in bad: print(r)
