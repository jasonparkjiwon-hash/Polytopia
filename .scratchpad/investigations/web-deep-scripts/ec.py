import sys,os,json,glob
sys.path.insert(0,'/home/user/Polytopia/engine')
import economy as EC
g,ta,pl=sys.argv[1],int(sys.argv[2]),int(sys.argv[3])
fs=[json.load(open(f)) for f in glob.glob(f'/home/user/Polytopia/saves/{g}*_t*.json')]
acts=max(fs,key=lambda d:len(d['actions']))['actions']
a=[d for d in fs if d['currentTurn']==ta][0]; b=[d for d in fs if d['currentTurn']==ta+1][0]
r=EC.check(a,b,acts)[pl]
print({k:v for k,v in r.items() if not isinstance(v,(list,dict)) or len(str(v))<200})
