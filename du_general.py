"""du_general.py -- M1: THE unified single-chunk dense scan generator (2026-07-10).

One entry point replaces build_scan / build_scan_2d / build_scan_2surf(_2d) / build_scan_narrow:

    build_scan_general(cols, mc, bnd_op=65, lead=99, smooth_fn=None)

cols: {(x_plane, y_col): (zlo, zhi)} voxel occupancy (single z-interval per column;
overhangs = future probe). All laws validated byte-exact across the donor corpus and the
3191 smoothed sphere (see closed_shapes_kickoff memory 2026-07-10):

  markers:  opener F-law (235 - F), F = 35*(nc_prev+nc_own)/2 + T_prev[-1] - zlo_own[0]
            continuation = 34 - h_prev + zstep ; byte2 = interior-plateau rule
  groups:   Y-lo opener: TWO validated family forms (dispatch, see _ylo_opener):
              flat single-surface narrowing -> 20 + 35*(2^lvl(left)-1)   [OCC1/2/3]
              z-varying two-surface        -> marker-F(dominant plane) - 36 [3191]
            +X boundary = marker-F(last plane) - 36 (curved) / flat boundary law
            Bottom family (pairs+cliffs+Y-hi): 33 - max(t[a],t[a-1]) + pairmin-delta
            Top: min(4 h-corners) - 2 ; runs = z-spans / max heights
  smoothing: vertex k of ANY run-R group at (x_g, y_g, zspan_min + k);
            smooth_fn(x,y,z) -> target point; displacement 84 steps/vox, in-place run0,
            expanded [val,01,run]+(dx,dy,dz,00)*(run+1)+[00] otherwise.
  layout:   small-regime rules (validated nc<=8, nx<=5); large scans need M2 (port
            h3_generator phase-alignment engine). See _layout.
"""
import math

def _marker(v,h,b2=2): return bytes([v&0xff,1,b2,(h-1)&0xff,0])
def _tok(v,r): return bytes([v&0xff,1,r&0xff,0x7e,0x7e,0x7e,r&0xff,0])
def _enc(d): return (int(round(d))+126)&0xff

def _planes_of(cols):
    xs=sorted({x for x,_ in cols})
    out=[]
    for x in xs:
        ys=sorted(y for (xx,y) in cols if xx==x)
        out.append((x,ys))
    return xs,out

def _F(cols, planes, p):
    """marker-opener F of plane index p (interior)."""
    x,ys=planes[p]; xp,ysp=planes[p-1]
    zlo0=cols[(x,ys[0])][0]
    Tprev=cols[(xp,ysp[-1])][1]+1
    return (35*(len(ysp)+len(ys)))//2 + Tprev - zlo0

def build_scan_general(cols, mc, bnd_op=65, lead=99, smooth_fn=None):
    xs,planes=_planes_of(cols)
    nx=len(planes); maxnc=max(len(ys) for _,ys in planes)
    flat = all(cols[c][0]==cols[(planes[0][0],planes[0][1][0])][0] for c in cols)
    def h(x,y):
        iv=cols.get((x,y)); return 0 if iv is None else iv[1]-iv[0]+1
    def zl(x,y):
        iv=cols.get((x,y)); return None if iv is None else iv[0]
    def zt(x,y):
        iv=cols.get((x,y)); return None if iv is None else iv[1]+1

    # ---- plateau byte2 ----
    def colset(p): return frozenset((y,cols[(planes[p][0],y)]) for y in planes[p][1])
    best=cur=1
    for p in range(1,nx):
        if colset(p)==colset(p-1): cur+=1; best=max(best,cur)
        else: cur=1
    b2 = 2 if best==nx else max(2,best)

    # ---- markers ----
    mplanes=[]
    for p,(x,ys) in enumerate(planes):
        op = bnd_op if p==0 else (235-_F(cols,planes,p))%256
        out=_marker(op,h(x,ys[0]),b2)
        for c in range(1,len(ys)):
            out+=_marker((34-h(x,ys[c-1])+(zl(x,ys[c])-zl(x,ys[c-1])))%256, h(x,ys[c]), b2)
        mplanes.append(out)

    # ---- groups ----
    def vol(p): return sum(h(planes[p][0],y) for y in planes[p][1])
    def Tlast(p):
        x,ys=planes[p]; return cols[(x,ys[-1])][1]+1
    def zfirst(p):
        x,ys=planes[p]; return cols[(x,ys[0])][0]
    def ncp(p): return len(planes[p][1])
    def _ylo_opener(g):
        # Y-lo opener F-forms (each byte-exact in its donor class; full unification
        # needs one discriminating donor -- see closed_shapes_kickoff 2026-07-10):
        #  flat, ncR>=ncL:      own-pair form  F=35*mean(ncL,ncR)+Tlast(L)-zfirst(R)
        #  flat, ncR<ncL:       max-K variant  F=35*max(ncL,ncR) +Tlast(L)-zfirst(R)
        #  two-surface (curved): marker-F of the DOMINANT (larger-vol) adjacent plane
        L,R=g-1,g
        if flat:
            if ncp(R)<ncp(L):
                if ncp(L)==maxnc:   # descending off the full-width plane: max-K variant
                    F=35*ncp(L) + Tlast(L) - zfirst(R)
                else:               # deeper descent: shifted pair = marker-F(L)
                    F=_F(cols,planes,L)
            elif vol(L)==vol(R) and ncp(L)==ncp(R) and L>0:
                own = L if g>nx//2 else R          # tie: owner by shape half
                F=_F(cols,planes,own)
            else:                   # ascending/equal: own-pair form = marker-F(R)
                F=(35*(ncp(L)+ncp(R)))//2 + Tlast(L) - zfirst(R)
        else:
            own = R if vol(R)>vol(L) else (L if vol(L)>vol(R) else (R if g<=nx//2 else L))
            F=_F(cols,planes,own)
        return (199-F)%256
    def group_plane(g):
        toks=[]
        smooth=[]  # per token: (x_g, y_g, zbase) or None
        if g==0 or g==nx:
            p=0 if g==0 else nx-1
            x,ys=planes[p]; nc=len(ys)
            hs=[h(x,y) for y in ys]; zc={j:zl(x,ys[j]) for j in range(nc)}
            def pm(u,v):
                vs=[zc.get(k) for k in (u,v) if zc.get(k) is not None]; return min(vs) if vs else 0
            if g==0: op=(bnd_op+19)%256
            else:
                # +X boundary: F = 35*mean(nc_prev,nc_last) + max(Tlast(last),Tlast(prev))
                #              - zlo_first(last)   (reduces to all flat/curved donor forms)
                x2,ys2=planes[nx-2]
                Tl=cols[(x,ys[-1])][1]+1; Tp=cols[(x2,ys2[-1])][1]+1
                F=(35*(len(ys2)+nc))//2 + max(Tl,Tp) - cols[(x,ys[0])][0]
                op=(199-F)%256
            toks.append((op,hs[0])); smooth.append((g,ys[0],-0))
            smooth[-1]=(g,ys[0],zc[0])
            for c in range(1,nc):
                hp2=hs[c-2] if c>=2 else 0
                bs=pm(c-1,c)-pm(c-2,c-1) if c>=2 else pm(c-1,c)-zc[c-1]
                r=max(hs[c],hs[c-1])
                toks.append(((33-max(hs[c-1],hp2)+bs)%256, r)); smooth.append((g,ys[c],min(zc[c-1],zc[c])))
            hs2=hs[-2] if nc>=2 else 0
            z2=zc[nc-2] if nc>=2 else zc[nc-1]
            toks.append(((33-max(hs[-1],hs2)+max(0,zc[nc-1]-z2))%256, hs[-1]))
            smooth.append((g,ys[-1]+1,zc[nc-1]))
            return toks,smooth
        L,R=g-1,g
        xL,ysL=planes[L]; xR,ysR=planes[R]
        u0=min(ysL[0],ysR[0]); u1=max(ysL[-1],ysR[-1])
        t={y:max(h(xL,y),h(xR,y)) for y in range(u0-3,u1+4)}
        zc={}
        for y in range(u0-3,u1+4):
            vs=[v for v in (zl(xL,y),zl(xR,y)) if v is not None]
            zc[y]=min(vs) if vs else None
        def pm(u,v):
            vs=[zc.get(k) for k in (u,v)]; vs=[k for k in vs if k is not None]
            return min(vs) if vs else 0
        toks=[(_ylo_opener(g), t[u0])]; smooth=[(g,u0,zc[u0])]
        for yw in range(u0+1,u1+1):
            a,b=yw-1,yw
            ea=((xL,a) in cols)!=((xR,a) in cols); eb=((xL,b) in cols)!=((xR,b) in cols)
            hp2=t.get(a-1,0); bs=pm(a,b)-pm(a-1,a)
            bval=(33-max(t[a],hp2)+bs)%256
            if ea or eb:
                toks.append((bval,max(t[a],t[b]))); smooth.append((g,yw,min(x for x in (zc[a],zc[b]) if x is not None)))
            else:
                zloc=[z for z in (zl(xL,a),zl(xL,b),zl(xR,a),zl(xR,b))]
                ztc =[z for z in (zt(xL,a),zt(xL,b),zt(xR,a),zt(xR,b))]
                hc  =[h(xL,a),h(xL,b),h(xR,a),h(xR,b)]
                toks.append((bval,max(zloc)-min(zloc))); smooth.append((g,yw,min(zloc)))
                toks.append(((min(hc)-2)%256,max(ztc)-min(ztc))); smooth.append((g,yw,min(ztc)))
        a,b=u1,u1+1
        toks.append(((33-max(t[a],t.get(a-1,0))+(pm(a,b)-pm(a-1,a)))%256, t[u1]))
        smooth.append((g,u1+1,zc[u1]))
        return toks,smooth

    gdata=[group_plane(g) for g in range(nx+1)]
    gregs=[]
    for toks,sm in gdata:
        out=bytearray()
        for (v,r),nom in zip(toks,sm):
            if smooth_fn is None:
                out+=_tok(v,r)
            else:
                xg,yg,zb=nom
                ds=[]
                allz=True
                for k in range(r+1):
                    P=(xg,yg,zb+k); T=smooth_fn(*P)
                    d=[max(-100,min(100,round(84*(T[j]-P[j])))) for j in range(3)]
                    ds.append(d); allz=allz and d==[0,0,0]
                if allz: out+=_tok(v,r)
                elif r==0:
                    out+=bytes([v,1,0,_enc(ds[0][0]),_enc(ds[0][1]),_enc(ds[0][2]),0,0])
                else:
                    out+=bytes([v,1,r])
                    for d in ds: out+=bytes([_enc(d[0]),_enc(d[1]),_enc(d[2]),0])
                    out+=bytes([0])
        gregs.append(bytes(out))

    # ---- layout (small-regime; M2 = general engine) ----
    mkgap=8 if maxnc<=6 else 6
    ggap=8 if maxnc<=5 else 6
    if maxnc==4: pad=246-10*nx
    elif maxnc==5: pad=240-8*nx if nx<=3 else 246-10*nx
    elif maxnc==6: pad=246-10*nx
    else: pad=241-9*nx
    markerspan=sum(len(m) for m in mplanes)+mkgap*(nx-1)
    mat_off=lead+markerspan+pad if lead!=99 else (99+markerspan)+pad
    grp_off=mat_off+90+(lead-99)
    grpspan=sum(len(g) for g in gregs)+ggap*(len(gregs)-1)
    scanlen=(mat_off+90)+grpspan+pad
    S=bytearray(scanlen); pl=[(mat_off,bytes([mc&0xff]),False)]; off=lead
    for m in mplanes: pl.append((off,m,True)); off+=len(m)+mkgap
    off=grp_off
    for gr in gregs: pl.append((off,gr,True)); off+=len(gr)+ggap
    pl.sort(); last=None; prev=0
    def fill(a,b,flip):
        for j in range(a,b): S[j]=(0xff if j%2==0 else 0) if flip else (0 if j%2==0 else 0xff)
    for o,d,tk in pl:
        if o>prev: fill(prev,o,last is not None and last%2==0)
        S[o:o+len(d)]=d
        if tk: last=o+len(d)
        prev=o+len(d)
    if prev<scanlen: fill(prev,scanlen,last is not None and last%2==0)
    return bytes(S)
