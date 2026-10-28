import sys,os,json,glob,struct,collections
sys.path.insert(0,'/home/user/Polytopia/engine')
from state import TRIBE, TERRAIN, UNIT, TECH
games={}
for f in glob.glob('/home/user/Polytopia/saves/*_t*.json'):
    d=json.load(open(f)); games.setdefault(f.split('/')[-1][:8],[]).append(d)
for g,ds in sorted(games.items()):
    ds.sort(key=lambda d:d['currentTurn']); acts=max(ds,key=lambda d:len(d['actions']))['actions']
    for a,b in zip(ds,ds[1:]):
        T=b['currentTiles']
        for i in range(len(a['actions']),len(b['actions'])):
            x=acts[i]
            if x['type']!=2: continue
            _,uid,ox,oy,tx,ty=struct.unpack('<BIIIII',bytes.fromhex(x['raw'])); pl=x['raw'] and bytes.fromhex(x['raw'])[0]
            # attacker type in a
            ut=None
            for row in a['currentTiles']:
                for t in row:
                    u=t.get('Unit')
                    if u and u['Id']==uid: ut=UNIT.get(u['UnitType'])
            if ut not in('Cloak','Scuba','Moth'): continue
            t=a['currentTiles'][ty][tx]
            if not t.get('ImprovementExists') or t['ImprovementType']!=1 or t['Owner'] in (pl,0): continue
            # spawned units in b near city
            sp=[]
            for yy,row in enumerate(T):
                for xx,tt in enumerate(row):
                    u=tt.get('Unit')
                    if u and u['Owner']==pl and u['CreatedTurn'] in (a['currentTurn'],a['currentTurn']+1) and UNIT.get(u['UnitType']) in('Dagger','MermaidDagger','InsectEgg','Pirate') and abs(xx-tx)<=3 and abs(yy-ty)<=3: sp.append((xx,yy,TERRAIN.get(tt['Terrain'])))
            cd=T[ty][tx].get('ImprovementData') or {}
            lvl=cd.get('Level'); bs=cd.get('BorderSize')
            ter=collections.Counter(); 
            occ=[]
            for yy in range(max(0,ty-(bs or 1)),min(len(T),ty+(bs or 1)+1)):
                for xx in range(max(0,tx-(bs or 1)),min(len(T[0]),tx+(bs or 1)+1)):
                    tt=T[yy][xx]
                    if (xx,yy)==(tx,ty) or tt['Owner']!=t['Owner']: continue
                    ter[TERRAIN.get(tt['Terrain'])]+= 0 if tt.get('Unit') and (xx,yy) not in [(s[0],s[1]) for s in sp] else 1
            print(g,a['currentTurn'],ut,'lvl',lvl,'spawn',sp,'free terrain',dict(ter))
