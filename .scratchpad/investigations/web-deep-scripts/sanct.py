import sys,os,json,glob,collections
sys.path.insert(0,'/home/user/Polytopia/engine')
from state import TERRAIN
games={}
for f in glob.glob('/home/user/Polytopia/saves/*_t*.json'):
    d=json.load(open(f)); games.setdefault(f.split('/')[-1][:8],[]).append(d)
for g,ds in sorted(games.items()):
    ds.sort(key=lambda d:d['currentTurn'])
    S={}
    for d in ds:
        for y,row in enumerate(d['currentTiles']):
            for x,t in enumerate(row):
                if t['ImprovementExists'] and t['ImprovementType']==32: S.setdefault((x,y),[]).append(d['currentTurn'])
    for (sx,sy),turns in S.items():
        if len(turns)<2: continue
        line=[]
        for d in ds:
            if d['currentTurn'] not in turns: continue
            T=d['currentTiles']; t0=T[sy][sx]
            games_=[(x,y) for y in range(sy-1,sy+2) for x in range(sx-1,sx+2) if (x,y)!=(sx,sy) and 0<=y<len(T) and 0<=x<len(T[0]) and T[y][x].get('ResourceExists') and T[y][x]['ResourceType']==1]
            forest=sum(1 for y in range(sy-1,sy+2) for x in range(sx-1,sx+2) if (x,y)!=(sx,sy) and 0<=y<len(T) and 0<=x<len(T[0]) and TERRAIN.get(T[y][x]['Terrain'])=='Forest' and not T[y][x]['ImprovementExists'] and not T[y][x].get('ResourceExists'))
            line.append((d['currentTurn'],len(games_),forest,t0['Owner'],(t0.get('ImprovementData') or {}).get('Level')))
        print(g,(sx,sy),line)
