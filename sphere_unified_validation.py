import sys, math; sys.path.insert(0,'/home/du')
import du_shape_parse as sp

B = list(sp.chunks('/home/du/exports/archive/3191_export.blueprint').values())[0]
def is_marker(i):
    return i+5<=len(B) and B[i+1]==1 and B[i+2]==2 and B[i+4]==0 and B[i+3]<32
i=64; mplanes=[]; cur=[]
while i<2400:
    if is_marker(i): cur.append((B[i],B[i+3]+1)); i+=5
    else:
        if cur: mplanes.append(cur); cur=[]
        i+=1
if cur: mplanes.append(cur)
NX=len(mplanes); WIDE=max(len(p) for p in mplanes)
y0=[(WIDE-len(p))//2 for p in mplanes]
Hh={}; 
for p,pl in enumerate(mplanes):
    for c,(v,h) in enumerate(pl): Hh[(p,y0[p]+c)]=h
def hcol(p,y): return Hh.get((p,y),0)
def zlo(p,y):  return -Hh[(p,y)]//2 if (p,y) in Hh else None
def zhiT(p,y): return Hh[(p,y)]//2 if (p,y) in Hh else None   # top gridline

BND_OP=100  # position CV for this donor

# ---------- generate CONTENT: markers ----------
def gen_marker_plane(p):
    pl=mplanes[p]; nc=len(pl); o=y0[p]
    hs=[h for _,h in pl]
    zl=[zlo(p,o+c) for c in range(nc)]
    if p==0:
        opener=BND_OP
    else:
        ncp=len(mplanes[p-1]); op_=y0[p-1]
        K2=(ncp+nc)              # 2*K
        zd=(zl[0]-zl[-1]) + (zlo(p-1,op_+ncp-1)-zl[-1])
        opener=(235 - (35*K2)//2 - hs[-1] + zd) % 256
    out=bytearray([opener,1,2,hs[0]-1,0])
    for c in range(1,nc):
        v=(34-hs[c-1]+(zl[c]-zl[c-1]))%256
        out+=bytes([v,1,2,hs[c]-1,0])
    return bytes(out)

mk_ok=0
for p in range(NX):
    gen=gen_marker_plane(p)
    # find observed plane bytes
    # reconstruct from mplanes? compare against raw: locate plane p extent
    # walk raw again
    # (we have extents from earlier: recompute)
    pass
# recompute extents
i=64; exts=[]; cur=None
while i<2400:
    if is_marker(i):
        if cur is None: cur=[i,i+5]
        else: cur[1]=i+5
        i+=5
    else:
        if cur: exts.append(tuple(cur)); cur=None
        i+=1
if cur: exts.append(tuple(cur))
for p in range(NX):
    a,b=exts[p]
    obs=B[a:b]; gen=gen_marker_plane(p)
    if obs==gen: mk_ok+=1
    else:
        d=[k for k in range(min(len(obs),len(gen))) if obs[k]!=gen[k]]
        print(f'  marker p{p} DIFF at {d[:4]} obs={list(obs[:10])} gen={list(gen[:10])}')
print(f'marker planes byte-exact: {mk_ok}/{NX}')

# ---------- generate CONTENT: group planes (skeleton with 7e placeholders NOT possible --
# donor has real displacements; so compare val/run/LENGTH per token, and splice donor verts) ----------
regs=sp.group_regions(B)

def mk_F_opener(p):
    """marker-opener value of plane p per the F-law (own=p, prev=p-1)."""
    pl=mplanes[p]; nc=len(pl); o=y0[p]
    hs=[h for _,h in pl]; zl=[zlo(p,o+c) for c in range(nc)]
    ncp=len(mplanes[p-1]); op_=y0[p-1]
    zd=(zl[0]-zl[-1])+(zlo(p-1,op_+ncp-1)-zl[-1])
    return (235-(35*(ncp+nc))//2-hs[-1]+zd)%256

def gen_group_plane(g):
    """Return list of (val,run) predicted tokens for vertex plane g."""
    toks=[]
    if g==0 or g==NX:
        p=0 if g==0 else NX-1
        nc=len(mplanes[p]); o=y0[p]
        hs=[hcol(p,o+j) for j in range(nc)]
        zl=[zlo(p,o+j) for j in range(nc)]
        if g==0: opener=(BND_OP+19)%256
        else:
            opener=(mk_F_opener(NX-1)-36)%256   # +X boundary: last plane's F-form - 36
        toks.append((opener, hs[0]))
        # boundary tokens: two-surface boundary law with pairwise-min bottom family
        zc={j:zl[j] for j in range(nc)}
        def pmin(u,v):
            vs=[zc.get(x) for x in (u,v) if zc.get(x) is not None]
            return min(vs) if vs else 0
        for c in range(1,nc):
            hp2=hs[c-2] if c>=2 else 0
            bs=pmin(c-1,c)-pmin(c-2,c-1) if c>=2 else pmin(c-1,c)-zc[c-1]
            toks.append(((33-max(hs[c-1],hp2)+bs)%256, max(hs[c],hs[c-1])))
        c=nc-1
        toks.append(((33-max(hs[-1],hs[-2])+max(0,zc.get(nc-1,0)-zc.get(nc-2,0)))%256, hs[-1]))
        return toks
    L,R=g-1,g
    y0n=max(y0[L],y0[R]); y1n=min(y0[L]+len(mplanes[L])-1,y0[R]+len(mplanes[R])-1)
    u0=min(y0[L],y0[R]); u1=max(y0[L]+len(mplanes[L])-1,y0[R]+len(mplanes[R])-1)
    rng=range(u0-3,u1+4)
    t={y:max(hcol(L,y),hcol(R,y)) for y in rng}
    zc={}
    for y in rng:
        vs=[v for v in (zlo(L,y),zlo(R,y)) if v is not None]
        zc[y]=min(vs) if vs else None
    def pmin(u,v):
        vs=[zc.get(x) for x in (u,v)]
        vs=[x for x in vs if x is not None]
        return min(vs) if vs else 0
    # Y-lo opener = marker-opener F of the DOMINANT adjacent plane (larger occupancy) - 36
    volL=sum(h for _,h in mplanes[L]); volR=sum(h for _,h in mplanes[R])
    own = R if volR>=volL and not (volL>volR) else L
    own = R if volR>volL else (L if volL>volR else (R if g<=NX//2 else L))
    opener=(mk_F_opener(own)-36)%256
    # run of Y-lo wall: t at first union col
    toks.append((opener, t[u0]))
    # walk transitions at gridlines u0+1 .. u1
    for yw in range(u0+1,u1+1):
        a,b=yw-1,yw
        inL_a=(L,a) in Hh; inR_a=(R,a) in Hh; inL_b=(L,b) in Hh; inR_b=(R,b) in Hh
        exposed_a=(inL_a!=inR_a); exposed_b=(inL_b!=inR_b)
        hp2=t.get(a-1,0)
        bs=pmin(a,b)-pmin(a-1,a)
        bval=(33-max(t[a],hp2)+bs)%256
        if exposed_a or exposed_b:
            toks.append((bval, max(t[a],t[b])))          # collapsed cliff
        else:
            # flush pair: Bottom run = 4-corner zlo span, Top = corner law
            zloc=[zlo(L,a),zlo(L,b),zlo(R,a),zlo(R,b)]
            zhic=[zhiT(L,a),zhiT(L,b),zhiT(R,a),zhiT(R,b)]
            hcorn=[hcol(L,a),hcol(L,b),hcol(R,a),hcol(R,b)]
            toks.append((bval, max(zloc)-min(zloc)))
            toks.append(((min(hcorn)-2)%256, max(zhic)-min(zhic)))
    # Y-hi wall at gridline u1+1
    a,b=u1,u1+1
    toks.append(((33-max(t[a],t.get(a-1,0))+(pmin(a,b)-pmin(a-1,a)))%256, t[u1]))
    return toks

gp=[sp.groups(B,a,b) for a,b in regs]
ok=0; tot=0; diffs=[]
for g in range(NX+1):
    pred=gen_group_plane(g)
    obs=[(t['val'],t['run']) for t in gp[g]]
    tot+=1
    if pred==obs: ok+=1
    else:
        diffs.append(g)
        for k,(p_,o_) in enumerate(zip(pred,obs)):
            if p_!=o_: print(f'  g{g} tok{k}: pred{p_} obs{o_}')
        if len(pred)!=len(obs): print(f'  g{g} LEN pred{len(pred)} obs{len(obs)}')
print(f'group planes (val,run) exact: {ok}/{tot}; diff planes: {diffs}')
