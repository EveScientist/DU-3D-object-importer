"""Fit the mc law: m8 = mc-512 (mod 256) over shape-known donors."""
import sys; sys.path.insert(0,'/home/du'); sys.path.insert(0,'.')
import test_smooth_roundtrip as T

def m8(name,key=(8,8,8)):
    return T.chunks(name)[key][1]-512

def feat(cols):
    """(nx, nc_first_plane?, ..., T_last, x0, y0) from a cols dict (single-interval)."""
    xs=sorted({x for x,_ in cols})
    nx=len(xs)
    lastx=xs[-1]
    ysl=sorted(y for (x,y) in cols if x==lastx)
    iv=cols[(lastx,ysl[-1])]
    Tlast=(iv[1] if isinstance(iv,tuple) else iv[-1][1])+1
    ys0=sorted(y for (x,y) in cols if x==xs[0])
    # nc: max cols per plane
    nc=max(len([1 for (x,y) in cols if x==xx]) for xx in xs)
    z0=min((iv[0] if isinstance(iv,tuple) else iv[0][0]) for iv in cols.values())
    return dict(nx=nx,nc=nc,Tl=Tlast,x0=xs[0],y0=min(y for _,y in cols),z0=z0)

def pred(f):
    v = 112 + 55*(f['nx']-4) - 35*(f['nc']-4) - (f['Tl']-12)
    v += (19*(f['x0']-8))//5
    v += -(47*(f['y0']-8))//5
    return v%256

def flat(hp,z0=8,x0=8,y0=8):
    return {(x0+x,y0+y):(z0,z0+h-1) for x,row in enumerate(hp) for y,h in enumerate(row) if h>0}
def surf(zlo,zhi,x0=8,y0=8):
    return {(x0+x,y0+y):(zlo[x][y],zhi[x][y]) for x in range(len(zlo)) for y in range(len(zlo[0]))}
def narrow(sets,H,z0=8):
    return {(8+x,8+y):(z0,z0+H-1) for x,s in enumerate(sets) for y in s}

E1zlo=[[11]*5,[11,10,10,10,11],[11,10,9,10,11],[11,10,10,10,11],[11]*5]
E1zhi=[[12]*5,[12,13,13,13,12],[12,13,14,13,12],[12,13,13,13,12],[12]*5]
tests=[
 ('3162', flat([[4]*4]*4)),
 ('3197', flat([[4]*6]*6)),
 ('3199', flat([[2,4,6,8,10]]*3)),
 ('3201', flat([[10,8,6,4,2]]*3)),
 ('3203', flat([[2,10,4,8,6]]*2)),
 ('3205', flat([[6]*4]*4)),
 ('3207', flat([[6,8,10,12]]*2)),
 ('3209', flat([[4]*7]*3)),
 ('3211', flat([[4]*8]*3)),
 ('3213', flat([[4]*4]*4,z0=18,x0=18,y0=18)),
 ('3215', flat([[4]*4]*4,x0=18)),
 ('3217', flat([[4]*4]*4,y0=18)),
 ('3219', flat([[4]*4]*4,z0=18)),
 ('3230', flat([[4]*4,[6]*4,[8]*4])),
 ('3236', flat([[8]*5]*3)),
 ('3238', flat([[4]*4,[4,6,8,6],[4]*4])),
 ('3252', flat([[2,4,6,8],[4,6,8,6],[6,8,6,4]])),
 ('3265', surf([[11,10,9,10,11]]*3,[[12,13,14,13,12]]*3)),
 ('3273', surf([[12,10,8,6,4]]*3,[[13]*5]*3)),
 ('3307', surf(E1zlo,E1zhi)),
 ('3318', narrow([{1,2,3},{0,1,2,3,4},{1,2,3}],4)),
 ('3320', narrow([{2},{1,2,3},{0,1,2,3,4},{1,2,3},{2}],4)),
 ('3325', narrow([{1,2,3},{0,1,2,3,4},{0,1,2,3,4},{0,1,2,3,4},{1,2,3}],4)),
 ('3353', flat([[4]*12]*8)),
 ('3355', flat([[4]*16]*12)),
 ('3357', flat([[2,4,6,8],[8]*4,[6]*4])),
 ('3359', flat([[2,4,6,4],[8]*4,[6]*4])),
 ('3367', flat([[h]*4 for h in (2,2,3,3,3,4,4,4)],x0=27)),   # full shape; chunk1 view below
 ('3396', flat([[3]*4]*8,x0=27)),
]
print(f'{"donor":6s} {"m8":>4s} {"pred":>4s} {"res":>5s}   nx nc Tl x0 y0')
for name,cols in tests:
    try: m=m8(name)
    except Exception as e: print(name,'ERR',e); continue
    f=feat(cols)
    # chunk1 view for multichunk shapes: clip to carried region (x<=32+1 phantom excl markers)
    p=pred(f)
    r=(m-p)%256
    r=r-256 if r>128 else r
    print(f'{name:6s} {m:4d} {p:4d} {r:+5d}   {f["nx"]:2d} {f["nc"]:2d} {f["Tl"]:2d} {f["x0"]:2d} {f["y0"]:2d}')
