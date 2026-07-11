"""du_general.py -- THE unified single/multi-chunk dense scan generator.

(2026-07-10 M1/M2; intervals+overhangs 2026-07-11; seams+position laws 2026-07-11 M3)

One entry point replaces build_scan / build_scan_2d / build_scan_2surf(_2d) / build_scan_narrow:

    build_scan_general(cols, mc, bnd_op=None, lead=None, smooth_fn=None,
                       xseam_lo=False, xopen_hi=False, yseam_lo=None, yopen_hi=None)

cols: {(x_plane, y_col): (zlo, zhi)  OR  [(zlo, zhi), ...]} voxel occupancy in CHUNK-LOCAL
coords (may be negative for seam overlap). A list of z-intervals per column encodes
overhangs (multi-interval columns, OVH1/OVH2 donors 3361/3363).

POSITION LAWS (2026-07-11, exact across 3213/3215/3217/3219/3178/3187/3189/E1):
    bnd_op = (65 - 55*(x-8) + 35*(y-8) + (z-8)) % 256      [x=bnd plane, y=first col, z=its zlo]
    lead   = 99 + 48*(x0-8)//5 + 2*((y0-8)//9)             [x0/y0 = first marker plane/col]
    mat_off = 99 + markerspan + pad   (LEAD-INDEPENDENT); grp_off = mat_off + lead - 9;
    trailing = pre-mat pad = mat_off - lead - markerspan; scanlen = grp_off + gspan + trailing.
    gaps: pairwise-sum bands over adjacent plane ncs: marker <=12:8,<=28:6,<=42:4,else 2;
    group <=10:8,<=28:6,<=42:4,else 2 (refines the old max-nc bands; matches 3189 6/4/2).

MULTI-CHUNK SEAMS (M3, donors 3178 X-box / 3187 Y-box / 3189 X-sphere markers):
  split rule at boundary S (=32): low chunk carries planes/cols [lo..S] + phantom S+1 for
  groups, +X/+Y UNCAPPED; high chunk carries [S-2..hi] (+ phantom plane S-3 for group math),
  entry gets seam forms. Local coords in the high chunk are negative (global-32).
    xseam_lo: cols include phantom plane at index 0; markers skip it; group lines start at
      line 1 = interior form with opener = (seam_marker_opener - 36); seam marker opener =
      bnd_op law at (local x of first real plane, first col y, its zlo). [3178c2: 103/67 ✓,
      3189c2: 224 ✓]
    xopen_hi: cols include phantom last plane; markers skip it; last group line = interior
      form between last real plane and phantom; NO +X cap.
    yopen_hi=Yc: cols may include phantom col Yc+1 per plane (markers clip to y<=Yc); group
      walls extend through Yc+1; NO Y-hi cap on planes that continue.
    yseam_lo=Ylo: planes whose first col == Ylo replace the Y-lo opener with a B,T pair:
      B val = (234 - F_ylo) % 256 (= std opener + 35), T standard; boundary group planes
      merge opener+first transition into one token val+35.
  provisional layout hooks (1 donor each, flagged): xseam_lo -> grp_off += 10;
  yseam_lo -> grp_off += 2; pad -= 2 when nx==4 and maxnc in (5,6) (unpinned pad cell).

VAL LAWS (all byte-exact across the 16-donor regression, see test_du_general.py):
  markers:  opener F-law (235 - F), F = 35*(nc_prev+nc_own)/2 + T_prev[-1] - zlo_own[0]
            continuation = 34 - h_prev + zstep ; byte2 = interior-plateau rule.
            Multi-interval column: one extra marker per extra interval, val = igap-1
            (igap = empty voxels between intervals; CONFOUNDED with h_up-1, see OVH3 note),
            byte4 = h_up-1; continuation to the next column runs from the TOPMOST interval.
  groups:   Y-lo opener dispatch (_ylo_F); +X boundary = 199 - (35*mean + max(T) - zlo);
            Bottom family: 33 - max(t[a],t[a-1]) + pairmin-delta; Top: min(4 h-corners)-2.
            Multi-interval column: t := FULL span; extra tokens val = igap-2, run = h_up
            prepended at every wall whose max-window {a,a-1} contains the column.
  smoothing: vertex k of ANY run-R group at (x_g, y_g, zspan_min + k); smooth_fn(x,y,z) ->
            target point; 84 steps/vox; in-place run0, expanded otherwise.

UNPINNED (need probes): igap-vs-h_up extra-token val (OVH3: gap2/h3); adjacent doubled
columns (OVH4); the 3 layout hooks above; yopen_hi boundary-plane cap-vs-continuation
ambiguity (flat donors identical); curved y-seam B/T runs.
"""
import math

def _marker(v,h,b2=2): return bytes([v&0xff,1,b2,(h-1)&0xff,0])
def _tok(v,r): return bytes([v&0xff,1,r&0xff,0x7e,0x7e,0x7e,r&0xff,0])
def _enc(d): return (int(round(d))+126)&0xff

def bnd_op_law(x,y,z): return (65 - 55*(x-8) + 35*(y-8) + (z-8)) % 256
def lead_law(x,y): return 99 + (48*(x-8))//5 + 2*((y-8)//9)
def _mkband(s): return 8 if s<=12 else (6 if s<=28 else (4 if s<=42 else 2))
def _gband(s):  return 8 if s<=10 else (6 if s<=28 else (4 if s<=42 else 2))

def _planes_of(cols):
    xs=sorted({x for x,_ in cols})
    out=[]
    for x in xs:
        ys=sorted(y for (xx,y) in cols if xx==x)
        out.append((x,ys))
    return xs,out

def _norm(cols):
    """normalize values to sorted tuple of (zlo,zhi) intervals."""
    out={}
    for c,v in cols.items():
        if isinstance(v,tuple) and len(v)==2 and isinstance(v[0],int):
            out[c]=((v[0],v[1]),)
        else:
            out[c]=tuple(sorted(tuple(iv) for iv in v))
    return out

def build_scan_general(cols, mc, bnd_op=None, lead=None, smooth_fn=None,
                       xseam_lo=False, xopen_hi=False, yseam_lo=None, yopen_hi=None):
    IV=_norm(cols)
    xs,planes=_planes_of(IV)
    nP=len(planes)
    def ivs(x,y): return IV.get((x,y))
    def h(x,y):
        iv=ivs(x,y); return 0 if iv is None else iv[0][1]-iv[0][0]+1
    def zl(x,y):
        iv=ivs(x,y); return None if iv is None else iv[0][0]
    def zt(x,y):
        iv=ivs(x,y); return None if iv is None else iv[0][1]+1
    def span(x,y):
        iv=ivs(x,y); return 0 if iv is None else iv[-1][1]-iv[0][0]+1
    def Tlast_iv(x,y):
        iv=ivs(x,y); return iv[-1][1]+1
    def extras(x,y):
        """[(igap, h_up, zlo_up, ztop_up)] per extra interval, ascending z.
        igap = empty voxels between it and the interval below."""
        iv=ivs(x,y)
        if iv is None or len(iv)==1: return []
        return [(iv[k][0]-(iv[k-1][1]+1), iv[k][1]-iv[k][0]+1, iv[k][0], iv[k][1]+1)
                for k in range(1,len(iv))]

    # ---- marker-plane / group-line index ranges ----
    # xseam_lo: cols start at S-2 (all real, markers emit all); group lines skip g=0
    #   (no -X cap) and g=1 (line S-1) takes the seam opener override.
    # xopen_hi: cols include phantom plane S+1 (markers skip it); lines run to S+1, no +X cap.
    m1 = nP-1 if xopen_hi else nP          # markers = planes[0:m1]
    g0 = 1 if xseam_lo else 0
    g1 = nP-1 if xopen_hi else nP          # group lines g0..g1 inclusive
    def mycols(p):
        return [y for y in planes[p][1] if yopen_hi is None or y<=yopen_hi]
    maxnc=max(len(mycols(p)) for p in range(m1))
    z00=zl(planes[0][0],mycols(0)[0])
    flat = all(iv[0][0]==z00 for iv in IV.values())

    # ---- plateau byte2 (over emitted marker planes) ----
    # b2 counts an identical-COLUMN-SET run only when bounded on BOTH sides by strictly
    # NARROWER planes (isolated widest section, OCC3 [3,(5,5,5),3] -> 3). Heights are
    # irrelevant (ramp 3367 b2=2 despite h-plateaus; killed Deployments 11a-c), and
    # edge-touching or wider-bounded runs don't count (3189/3191 spheres: nc24 run at
    # chunk edge, nc22 run bounded by 24 -> both b2=2).
    csets=[frozenset(mycols(p)) for p in range(m1)]
    b2=2; s=0
    for e in range(1,m1+1):
        if e==m1 or csets[e]!=csets[s]:
            if (e-s)>=2 and s>0 and e<m1 and \
               len(csets[s-1])<len(csets[s]) and len(csets[e])<len(csets[s]):
                b2=max(b2,e-s)
            s=e

    # ---- markers ----
    def _F(p):
        """marker-opener F of plane index p (interior; p-1 may be a phantom plane)."""
        x=planes[p][0]; ys=mycols(p); xp=planes[p-1][0]; ysp=mycols(p-1)
        return (35*(len(ysp)+len(ys)))//2 + Tlast_iv(xp,ysp[-1]) - zl(x,ys[0])
    def _seam_marker_op():
        x=planes[0][0]; ys=mycols(0)
        return bnd_op_law(x, ys[0], zl(x,ys[0]))
    mplanes=[]
    for p in range(m1):
        x=planes[p][0]; ys=mycols(p)
        if p==0:
            # xseam_lo: plane S-2 opener = the same bnd_op law at its local position
            op = bnd_op if (bnd_op is not None and not xseam_lo) else bnd_op_law(x,ys[0],zl(x,ys[0]))
        else:
            op=(235-_F(p))%256
        out=_marker(op,h(x,ys[0]),b2)
        for ig,hu,_,_ in extras(x,ys[0]): out+=_marker((ig-1)%256,hu,b2)
        for c in range(1,len(ys)):
            pv=ivs(x,ys[c-1])[-1]      # continuation runs from prev col's TOPMOST interval
            hp=pv[1]-pv[0]+1
            out+=_marker((34-hp+(zl(x,ys[c])-pv[0]))%256, h(x,ys[c]), b2)
            for ig,hu,_,_ in extras(x,ys[c]): out+=_marker((ig-1)%256,hu,b2)
        mplanes.append(out)

    # ---- groups ----
    def vol(p): return sum(iv[1]-iv[0]+1 for y in mycols(p) for iv in ivs(planes[p][0],y))
    def Tlast(p):
        ysm=mycols(p); return Tlast_iv(planes[p][0],ysm[-1])
    def zfirst(p):
        ysm=mycols(p); return zl(planes[p][0],ysm[0])
    def ncp(p): return len(mycols(p))
    def _ylo_F(g):
        # Y-lo opener F-forms (each byte-exact in its donor class):
        #  flat, ncR>=ncL:      own-pair form  F=35*mean(ncL,ncR)+Tlast(L)-zfirst(R)
        #  flat, ncR<ncL:       max-K variant  F=35*max(ncL,ncR) +Tlast(L)-zfirst(R)
        #  two-surface (curved): marker-F of the DOMINANT (larger-vol) adjacent plane
        L,R=g-1,g
        nx=m1    # emitted marker plane count (owner-half tiebreak scale)
        if flat:
            if ncp(R)<ncp(L):
                if ncp(L)==maxnc:   # descending off the full-width plane: max-K variant
                    F=35*ncp(L) + Tlast(L) - zfirst(R)
                else:               # deeper descent: shifted pair = marker-F(L)
                    F=_F(L)
            elif vol(L)==vol(R):    # vol tie, equal nc: T := MAX column top of the pair.
                # Pinned jointly by 3252 g2 (non-identical mirrored planes: X=16=maxT,
                # NOT Tlast(L)=14, NOT the old owner-by-half _F(L) whose agreement at 16
                # was coincidental) and PLT-MC 3367's identical-plane ties (X=12=maxT;
                # _F(L)=11 rejected in-game: Deployments 11a-c invalid-vertex).
                # max over BOTTOM-interval tops: OVH1/2 pin that a multi-interval column's
                # upper intervals do NOT enter the tie max (donor 92 = base top 10).
                mT=max(zt(planes[q][0],y) for q in (L,R) for y in mycols(q))
                F=(35*(ncp(L)+ncp(R)))//2 + mT - zfirst(R)
            else:                   # ascending/descending equal-nc: own-pair form
                F=(35*(ncp(L)+ncp(R)))//2 + Tlast(L) - zfirst(R)
        else:
            own = R if vol(R)>vol(L) else (L if vol(L)>vol(R) else (R if g<=nP//2 else L))
            F=_F(own)
        return F
    def _upwall(toks,smooth,ua,ub,g,yw):
        """Upper-deck tokens of wall yw between cols a,b (ua/ub = extras lists, layer-
        aligned). One side only -> single wall token (igap-2, h_up). BOTH sides -> the
        uppers PAIR into their own (B_up, T_up) with spread runs (OVH4 3374: second
        two-surface deck). Vals for the pair: (min igap - 2, min h_up - 2) -- igap==h_up
        in OVH4, so the family split mirrors the lower deck (B_up igap-family/T_up
        Top-family); discriminating probe would need a slab with gap != h."""
        for k in range(max(len(ua),len(ub))):
            A=ua[k] if k<len(ua) else None
            B=ub[k] if k<len(ub) else None
            if A and B:
                toks.append(((min(A[0],B[0])-2)%256, abs(A[2]-B[2]))); smooth.append((g,yw,min(A[2],B[2])))
                toks.append(((min(A[1],B[1])-2)%256, abs(A[3]-B[3]))); smooth.append((g,yw,min(A[3],B[3])))
            else:
                C=A or B
                toks.append(((C[0]-2)%256, C[1])); smooth.append((g,yw,C[2]))
    def _upwall_bnd(toks,smooth,ua,ub,g,yw):
        """Boundary-plane upper tokens: single all-wall token per layer even when both
        cols have uppers (OVH4 boundary): val = min(igap)-2, run = max(h_up)."""
        for k in range(max(len(ua),len(ub))):
            A=ua[k] if k<len(ua) else None
            B=ub[k] if k<len(ub) else None
            ig=min(x[0] for x in (A,B) if x); hu=max(x[1] for x in (A,B) if x)
            zu=min(x[2] for x in (A,B) if x)
            toks.append(((ig-2)%256,hu)); smooth.append((g,yw,zu))
    def group_plane(g):
        toks=[]
        smooth=[]  # per token: (x_g, y_g, zbase) or (.., None) for upper-interval tokens
        if (g==0 and not xseam_lo) or (g==nP and not xopen_hi):
            p=0 if g==0 else nP-1
            x,ys=planes[p]; nc=len(ys)
            sm = yseam_lo is not None and ys[0]==yseam_lo
            ph = yopen_hi is not None and ys[-1]>yopen_hi
            hs=[h(x,y) for y in ys]; ss=[span(x,y) for y in ys]
            ex=[extras(x,y) for y in ys]; zc={j:zl(x,ys[j]) for j in range(nc)}
            def pm(u,v):
                vs=[zc.get(k) for k in (u,v) if zc.get(k) is not None]; return min(vs) if vs else 0
            if g==0:
                b=bnd_op if bnd_op is not None else bnd_op_law(x,ys[0],zl(x,ys[0]))
                op=(b+19)%256
            else:
                # +X boundary: F = 35*mean(nc_prev,nc_last) + max(Tlast(last),Tlast(prev))
                #              - zlo_first(last)   (reduces to all flat/curved donor forms)
                ysm=mycols(p); ysm2=mycols(p-1)
                Tl=Tlast_iv(x,ysm[-1]); Tp=Tlast_iv(planes[p-1][0],ysm2[-1])
                F=(35*(len(ysm2)+len(ysm)))//2 + max(Tl,Tp) - zl(x,ysm[0])
                op=(199-F)%256
            cstart=1
            if sm:  # y-seam: merge opener + first transition into one wall token, val+35
                toks.append(((op+35)%256, max(hs[0],hs[1]))); smooth.append((g,ys[1],min(zc[0],zc[1])))
                cstart=2
            else:
                toks.append((op,hs[0])); smooth.append((g,ys[0],zc[0]))
                _upwall_bnd(toks,smooth,ex[0],[],g,ys[0])     # Y-lo edge wall uppers
            for c in range(cstart,nc):
                sp2=ss[c-2] if c>=2 else 0
                bs=pm(c-1,c)-pm(c-2,c-1) if c>=2 else pm(c-1,c)-zc[c-1]
                r=max(hs[c],hs[c-1])
                toks.append(((33-max(ss[c-1],sp2)+bs)%256, r)); smooth.append((g,ys[c],min(zc[c-1],zc[c])))
                _upwall_bnd(toks,smooth,ex[c-1],ex[c],g,ys[c])
            if not ph:
                ss2=ss[-2] if nc>=2 else 0
                z2=zc[nc-2] if nc>=2 else zc[nc-1]
                toks.append(((33-max(ss[-1],ss2)+max(0,zc[nc-1]-z2))%256, hs[-1]))
                smooth.append((g,ys[-1]+1,zc[nc-1]))
                _upwall_bnd(toks,smooth,ex[-1],[],g,ys[-1]+1) # Y-hi edge wall uppers
            return toks,smooth
        L,R=g-1,g
        xL,ysL=planes[L]; xR,ysR=planes[R]
        u0=min(ysL[0],ysR[0]); u1=max(ysL[-1],ysR[-1])
        sm = yseam_lo is not None and u0==yseam_lo
        ph = yopen_hi is not None and u1>yopen_hi
        t={y:max(span(xL,y),span(xR,y)) for y in range(u0-3,u1+4)}
        def colex(y):
            eL,eR=extras(xL,y),extras(xR,y)
            return eL if len(eL)>=len(eR) else eR
        zc={}
        for y in range(u0-3,u1+4):
            vs=[v for v in (zl(xL,y),zl(xR,y)) if v is not None]
            zc[y]=min(vs) if vs else None
        def pm(u,v):
            vs=[zc.get(k) for k in (u,v)]; vs=[k for k in vs if k is not None]
            return min(vs) if vs else 0
        wstart=u0+1
        if sm:  # y-seam entry: std pair at wall S-1 (=u0+1) with B val := 234 - F_ylo
            a,b=u0,u0+1
            zloc=[z for z in (zl(xL,a),zl(xL,b),zl(xR,a),zl(xR,b)) if z is not None]
            ztc =[z for z in (zt(xL,a),zt(xL,b),zt(xR,a),zt(xR,b)) if z is not None]
            hc  =[v for v in (h(xL,a),h(xL,b),h(xR,a),h(xR,b)) if v>0]
            toks=[((234-_ylo_F(g))%256, max(zloc)-min(zloc))]; smooth=[(g,b,min(zloc))]
            toks.append(((min(hc)-2)%256, max(ztc)-min(ztc))); smooth.append((g,b,min(ztc)))
            wstart=u0+2
        elif g==g0 and xseam_lo:  # x-seam entry line (S-1): interior form, opener = seam - 36
            # opener run: BOTTOM-interval height of col u0 (OVH4: 2 not span 6)
            toks=[((_seam_marker_op()-36)%256, max(h(xL,u0) or 0,h(xR,u0) or 0))]; smooth=[(g,u0,zc[u0])]
            _upwall(toks,smooth,[],colex(u0),g,u0)            # Y-lo edge wall uppers
        else:
            toks=[((199-_ylo_F(g))%256, max(h(xL,u0) or 0,h(xR,u0) or 0))]; smooth=[(g,u0,zc[u0])]
            _upwall(toks,smooth,[],colex(u0),g,u0)            # Y-lo edge wall uppers
        for yw in range(wstart,u1+1):
            a,b=yw-1,yw
            ea=((xL,a) in IV)!=((xR,a) in IV); eb=((xL,b) in IV)!=((xR,b) in IV)
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
            _upwall(toks,smooth,colex(a),colex(b),g,yw)       # this wall's upper deck(s)
        if not ph:
            a,b=u1,u1+1
            toks.append(((33-max(t[a],t.get(a-1,0))+(pm(a,b)-pm(a-1,a)))%256,
                         max(h(xL,u1) or 0,h(xR,u1) or 0)))
            smooth.append((g,u1+1,zc[u1]))
            _upwall(toks,smooth,colex(u1),[],g,b)             # Y-hi edge wall uppers
        return toks,smooth

    glines=list(range(g0,g1+1))
    gdata=[group_plane(g) for g in glines]
    gregs=[]
    for toks,sm in gdata:
        out=bytearray()
        for (v,r),nom in zip(toks,sm):
            if smooth_fn is None or nom[2] is None:
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

    # ---- layout ----
    nx=m1
    # per-pair gap bands (sum of adjacent plane col counts)
    mncs=[len(mycols(p)) for p in range(m1)]
    mkgaps=[_mkband(mncs[i]+mncs[i+1]) for i in range(nx-1)]
    def ncg(g):
        if (g==0 and not xseam_lo) or (g==nP and not xopen_hi):
            p=0 if g==0 else nP-1
            return len(mycols(p))
        cl={y for y in mycols(g-1)} if 0<=g-1<m1 else set()
        cr={y for y in mycols(g)} if 0<=g<m1 else set()
        u=cl|cr
        return len(u) if u else max(len(mycols(p)) for p in range(m1))
    gncs=[ncg(g) for g in glines]
    ggaps=[_gband(gncs[i]+gncs[i+1]) for i in range(len(glines)-1)]
    # pads
    if maxnc==5: pad=240-8*nx if nx<=3 else 246-10*nx
    elif 7<=maxnc<=8: pad=241-9*nx
    else: pad=246-10*nx        # nc4,6,12,16 (B12/B16) all on this line
    if nx==4 and maxnc in (5,6): pad-=2   # provisional kink (3187 both chunks)
    if lead is None:
        lead=lead_law(planes[0][0], mycols(0)[0])
    markerspan=sum(len(m) for m in mplanes)+sum(mkgaps)
    mat_off=99+markerspan+pad              # lead-independent (3213/3215/3217 mat@409)
    grp_off=mat_off+lead-9
    if xseam_lo: grp_off+=10               # provisional hook (3178c2)
    if yseam_lo is not None: grp_off+=2    # provisional hook (3187c2)
    grpspan=sum(len(g) for g in gregs)+sum(ggaps)
    trailing=mat_off-lead-markerspan
    scanlen=grp_off+grpspan+trailing
    S=bytearray(scanlen); pl=[(mat_off,bytes([mc&0xff]),False)]; off=lead
    for i,m in enumerate(mplanes):
        pl.append((off,m,True)); off+=len(m)+(mkgaps[i] if i<len(mkgaps) else 0)
    off=grp_off
    for i,gr in enumerate(gregs):
        pl.append((off,gr,True)); off+=len(gr)+(ggaps[i] if i<len(ggaps) else 0)
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

def build_multichunk(cols, mc=606, chunk0=(8,8,8), smooth_fn=None):
    """Split GLOBAL cols (construct-local voxel coords, chunk0 covers 0..31 per axis) at
    32-voxel chunk boundaries in X and Y -> {(cx,cy,cz): scan}. mc: int, or dict keyed by
    chunk. Z-splits not yet implemented (single z-chunk shapes only).
    Split rule (byte-exact vs 3178/3187): a chunk carries planes/cols up to S=next boundary
    (one past its own range) plus a phantom plane/col S+1 for group math (open/uncapped
    high side); a chunk whose shape continues below carries from S-2 (negative local
    coords) with seam entry forms."""
    IV=_norm(cols)
    xs=[x for x,_ in IV]; ys=[y for _,y in IV]
    sx0,sx1=min(xs),max(xs); sy0,sy1=min(ys),max(ys)
    cx0,cy0,cz0=chunk0
    out={}
    for ci in range(sx0//32, sx1//32+1):
        for cj in range(sy0//32, sy1//32+1):
            lox,hix=32*ci,32*ci+31
            loy,hiy=32*cj,32*cj+31
            if not any(lox<=x<=hix and loy<=y<=hiy for x,y in IV): continue
            xs_lo = sx0<lox; xs_hi = sx1>hix
            ys_lo = sy0<loy; ys_hi = sy1>hiy
            xf = lox-2 if xs_lo else sx0
            xt = hix+2 if xs_hi else sx1       # hix+1 carried + hix+2 phantom
            yf = loy-2 if ys_lo else sy0
            yt = hiy+2 if ys_hi else sy1       # hiy+1 carried + hiy+2 phantom
            sub={(x-lox,y-loy):iv for (x,y),iv in IV.items() if xf<=x<=xt and yf<=y<=yt}
            key=(cx0+ci,cy0+cj,cz0)
            m = mc[key] if isinstance(mc,dict) else mc
            out[key]=build_scan_general(sub, m, smooth_fn=smooth_fn,
                xseam_lo=xs_lo, xopen_hi=xs_hi,
                yseam_lo=(yf-loy) if ys_lo else None,
                yopen_hi=(hiy+1-loy) if ys_hi else None)
    return out
