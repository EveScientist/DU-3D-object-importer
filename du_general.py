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
    zopen_hi / zseam_lo (ZC1 3376 / ZC2 3378): z carries to S (no phantom) / from S-2;
      a zseam chunk's GROUP region clips intervals at S-1 (= local -1; columns entirely
      below become ABSENT: zero heights, edge collapse, F/bnd anchors at -1). B/T are
      SURFACE tokens: B exists unless both wall cols are bottom-cut, T exists unless both
      are top-cut; B (and Y-hi) vals blank to 33 when the lag-window {a-1,a} is entirely
      present-and-top-cut; T val blanks to 33 when both wall cols are bottom-cut.
      Markers/boundary planes/openers: fully standard over the carried/clipped intervals.
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
_LEAD_XBASE=[0,10,19,28,38,48,57,67,76]   # cells 2,5,6,7 interpolated (~9.56/vox), rest donor-pinned
def lead_law(x,y):
    xp=x-8
    xt=86*(xp//9)+_LEAD_XBASE[xp%9]
    yp=y-8
    yt=2*((yp+4)//9) if yp>=0 else 2*(yp//9)   # +4 shift for positives (3189c1/3420)
    if x<8 and yt!=0: yt+=2                    # xseam chunks (3380 corner/9-chunk)
    return 99 + xt + yt
def mc_law(carry_cols, xopen_owner=None, yopen_owner=None):
    """mc for a chunk from its CARRY view (markers view, local coords, NO phantoms;
    z carried to S / from S-2). mc = 512 + m8,
      m8 = (112 + 55*(nx-4) - 35*(mean(min_nc,max_nc)-4) - (T_last-12)
            + 55*(x0-8) - 35*(y0-8)) mod 256
    T_last = top gridline of the last column (absorbs z-position). Integer slopes pinned
    by the P5-P11 sweep (3408-3420); the earlier 19//5 / -47//5 fractional slopes and
    ownership bonuses were aliasing from multiple-of-5 sampling. Same 55/35 family as
    bnd_op_law. (owner args kept for signature compat; unused.)"""
    IV=_norm(carry_cols)
    xs=sorted({x for x,_ in IV}); nx=len(xs)
    ncs=[len([1 for (x,y) in IV if x==xx]) for xx in xs]
    ncm=(min(ncs)+max(ncs))/2
    lastx=xs[-1]; ylast=max(y for (x,y) in IV if x==lastx)
    Tl=IV[(lastx,ylast)][-1][1]+1
    x0=xs[0]; y0=min(y for _,y in IV)
    m8=int(112 + 55*(nx-4) - 35*(ncm-4) - (Tl-12) + 55*(x0-8) - 35*(y0-8))%256
    return 512+m8

def _mkband(s): return 8 if s<=12 else (6 if s<=28 else (4 if s<=42 else 2))
def _gband(s):  return 8 if s<=10 else (6 if s<=24 else (4 if s<=40 else 2))  # group bands sit LOWER than marker bands (3189/3191 groups: 26->4, 42->2, 40->4)

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
                       xseam_lo=False, xopen_hi=False, yseam_lo=None, yopen_hi=None,
                       zseam_lo=False, zopen_hi=False,
                       yopen_cap=True, yseam_merge=True):
    IV=_norm(cols)
    xs,planes=_planes_of(IV)
    nP=len(planes)
    # Z-SPLIT (ZC1 3376 / ZC2 3378): markers use the carried intervals as passed
    # (high chunk carries from S-2 = local -2; low chunk to S = local 32); the GROUP
    # region of a zseam chunk clips at S-1 = local -1, columns entirely below become
    # ABSENT (zero heights / edge collapse / F anchors at -1). AV switches from IV
    # (marker phase) to GIV (group phase).
    if zseam_lo:
        GIV={}
        for c,iv in IV.items():
            cl=tuple((max(a,-1),b) for a,b in iv if b>=-1)
            if cl: GIV[c]=cl
    else:
        GIV=IV
    AV=IV
    def ivs(x,y): return AV.get((x,y))
    def h(x,y):
        iv=ivs(x,y); return 0 if iv is None else iv[0][1]-iv[0][0]+1
    def zl(x,y):
        iv=ivs(x,y); return None if iv is None else iv[0][0]
    def zt(x,y):
        iv=ivs(x,y); return None if iv is None else iv[0][1]+1
    def span(x,y):
        iv=ivs(x,y); return 0 if iv is None else iv[-1][1]-iv[0][0]+1
    def Tlast_iv(x,y):
        iv=ivs(x,y); return -1 if iv is None else iv[-1][1]+1
    def cut_top(x,y):
        iv=ivs(x,y); return zopen_hi and iv is not None and iv[-1][1]>=32
    def cut_bot(x,y):
        return zseam_lo and (x,y) in GIV and IV[(x,y)][0][0]<=-2
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
    # b2 counts a run of FULLY IDENTICAL planes (col-sets AND intervals) bounded on BOTH
    # sides by planes with strictly NARROWER col-sets (OCC3 [3,(5,5,5),3] -> 3). Height
    # plateaus with equal-width bounds don't count (ramp 3367 b2=2, killed Deployments
    # 11a-c); widest runs with differing heights don't either (3191's six nc-20 planes,
    # b2=2); edge-touching runs don't (3189c1).
    pdat=[tuple((y,IV[(planes[p][0],y)]) for y in mycols(p)) for p in range(m1)]
    csets=[frozenset(mycols(p)) for p in range(m1)]
    b2=2; s=0
    for e in range(1,m1+1):
        if e==m1 or pdat[e]!=pdat[s]:
            if (e-s)>=2 and s>0 and e<m1 and \
               len(csets[s-1])<len(csets[s]) and len(csets[e])<len(csets[s]):
                b2=max(b2,e-s)
            s=e

    # ---- markers ----
    def _F(p):
        """marker-opener F of plane index p (interior; p-1 may be a phantom plane)."""
        x=planes[p][0]; ys=mycols(p); xp=planes[p-1][0]; ysp=mycols(p-1)
        z0=zl(x,ys[0]); z0=-1 if z0 is None else z0
        return (35*(len(ysp)+len(ys)))//2 + Tlast_iv(xp,ysp[-1]) - z0
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
    AV=GIV   # group phase reads group intervals

    # ---- groups ----
    def vol(p): return sum(iv[1]-iv[0]+1 for y in mycols(p) for iv in (ivs(planes[p][0],y) or ()))
    def Tlast(p):
        ysm=mycols(p); return Tlast_iv(planes[p][0],ysm[-1])
    def zfirst(p):
        ysm=mycols(p); z=zl(planes[p][0],ysm[0]); return -1 if z is None else z
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
            elif vol(L)==vol(R):
                # vol tie, equal nc. IDENTICAL planes -> own-pair form (= marker-F(R);
                # 3367 h4/h4 ties + ZC1/ZC2 z-cut chunks, where maxT over carried tops
                # would be wrong). NON-identical vol tie -> T := MAX bottom-interval
                # column top of the pair (3252 g2 mirrored planes: X=16=maxT, NOT
                # Tlast(L)=14; OVH1/2 pin that upper intervals stay OUT of the max).
                if [ (y,ivs(planes[L][0],y)) for y in mycols(L) ] == \
                   [ (y,ivs(planes[R][0],y)) for y in mycols(R) ]:
                    F=(35*(ncp(L)+ncp(R)))//2 + Tlast(L) - zfirst(R)
                else:
                    mT=max((zt(planes[q][0],y) for q in (L,R) for y in mycols(q)
                            if ivs(planes[q][0],y) is not None), default=-1)
                    F=(35*(ncp(L)+ncp(R)))//2 + mT - zfirst(R)
            else:                   # ascending/descending equal-nc: own-pair form
                F=(35*(ncp(L)+ncp(R)))//2 + Tlast(L) - zfirst(R)
        else:
            if vol(R)!=vol(L):
                own = R if vol(R)>vol(L) else L
            else:
                # tie: owner is on the ASCENDING side -- compare outer neighbors' volumes
                # (3191 g9 right / g12 left; 3189c1 plateau-edge line pins that the old
                # "chunk-half" proxy fails in seam chunks, where the shape's peak is not
                # at the chunk's middle). Equal/absent neighbors: identical planes make
                # _F(L)==_F(R), so the pick is immaterial.
                vL1 = vol(L-1) if L-1>=0 else -1
                vR1 = vol(R+1) if R+1<nP else -1
                own = R if vR1>=vL1 else L
            F=_F(own)
        return F
    def _upwall(toks,smooth,ua,ub,gx,yw):
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
                toks.append(((min(A[0],B[0])-2)%256, abs(A[2]-B[2]))); smooth.append((gx,yw,min(A[2],B[2])))
                toks.append(((min(A[1],B[1])-2)%256, abs(A[3]-B[3]))); smooth.append((gx,yw,min(A[3],B[3])))
            else:
                C=A or B
                toks.append(((C[0]-2)%256, C[1])); smooth.append((gx,yw,C[2]))
    def _upwall_bnd(toks,smooth,ua,ub,gx,yw):
        """Boundary-plane upper tokens: single all-wall token per layer even when both
        cols have uppers (OVH4 boundary): val = min(igap)-2, run = max(h_up)."""
        for k in range(max(len(ua),len(ub))):
            A=ua[k] if k<len(ua) else None
            B=ub[k] if k<len(ub) else None
            ig=min(x[0] for x in (A,B) if x); hu=max(x[1] for x in (A,B) if x)
            zu=min(x[2] for x in (A,B) if x)
            toks.append(((ig-2)%256,hu)); smooth.append((gx,yw,zu))
    def group_plane(g):
        gx=planes[0][0]+g   # ACTUAL x grid line (line g between voxel planes g-1,g);
                            # smooth nominals must use real coords, not the index
                            # (Deployment 12 bug: dome field evaluated at x=0..8)
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
                z0g=zl(x,ys[0]); z0g=-1 if z0g is None else z0g
                # zseam chunks: the group -X opener = bnd law at the GROUP z (S-1 = -1),
                # NOT the marker bnd_op (which anchors at S-2) -- ZC1/ZC2: 75 = law(z=-1)+19
                b=bnd_op if (bnd_op is not None and not zseam_lo) else bnd_op_law(x,ys[0],z0g)
                op=(b+19)%256
            else:
                # +X boundary: F = 35*mean(nc_prev,nc_last) + max(Tlast(last),Tlast(prev))
                #              - zlo_first(last)   (reduces to all flat/curved donor forms)
                ysm=mycols(p); ysm2=mycols(p-1)
                Tl=Tlast_iv(x,ysm[-1]); Tp=Tlast_iv(planes[p-1][0],ysm2[-1])
                z0g=zl(x,ysm[0]); z0g=-1 if z0g is None else z0g
                F=(35*(len(ysm2)+len(ysm)))//2 + max(Tl,Tp) - z0g
                op=(199-F)%256
            cstart=1
            if sm:  # y-seam: FLAT seam -> merged opener+first-transition token (val+35,
                    # 3187c2); CURVED seam -> nothing, std walls from c=2 (3400 high chunk)
                if yseam_merge:
                    toks.append(((op+35)%256, max(hs[0],hs[1]))); smooth.append((gx,ys[1],min(zc[0],zc[1])))
                cstart=2
            else:
                toks.append((op,hs[0])); smooth.append((gx,ys[0],zc[0]))
                _upwall_bnd(toks,smooth,ex[0],[],gx,ys[0])     # Y-lo edge wall uppers
            # yopen boundary: walls run through the seam col (y=yopen_hi); the +Y-open
            # edge is a TAIL token (curved-Y-seam decode 2026-07-12, 9 donors). Non-yopen
            # keeps the original walls+Y-hi-closing.
            seam_idx = ys.index(yopen_hi) if ph else None
            cend = (seam_idx+1) if ph else nc
            for c in range(cstart,cend):
                sp2=ss[c-2] if c>=2 else 0
                zc1=zc[c-1] if zc[c-1] is not None else pm(c-1,c)
                bs=pm(c-1,c)-pm(c-2,c-1) if c>=2 else pm(c-1,c)-zc1
                r=max(hs[c],hs[c-1])
                zmin=[v for v in (zc[c-1],zc[c]) if v is not None]
                toks.append(((33-max(ss[c-1],sp2)+bs)%256, r)); smooth.append((gx,ys[c],min(zmin) if zmin else None))
                _upwall_bnd(toks,smooth,ex[c-1],ex[c],gx,ys[c])
            if ph:
                hprev=hs[seam_idx-1]; hseam=hs[seam_idx]
                # TAIL = (33 - max(hseam,hprev), hseam); +X always, -X iff ascending or
                # flat-continues. "flat-continues" = the REAL next col (y=S+1) equals the
                # seam (yopen_cap; the carried phantom is a COPY so hs can't tell us).
                if g==nP or hseam>hprev or (hseam==hprev and yopen_cap):
                    toks.append(((33-max(hseam,hprev))%256, hseam))
                    smooth.append((gx,yopen_hi+1,zc.get(seam_idx)))
            else:
                ss2=ss[-2] if nc>=2 else 0
                z2=zc[nc-2] if nc>=2 else zc[nc-1]
                zn=zc[nc-1]
                dz=(zn-z2) if (zn is not None and z2 is not None) else 0
                toks.append(((33-max(ss[-1],ss2)+max(0,dz))%256, hs[-1]))
                smooth.append((gx,ys[-1]+1,zn))
                _upwall_bnd(toks,smooth,ex[-1],[],gx,ys[-1]+1) # Y-hi edge wall uppers
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
        def pmv(u,v):
            vs=[zc.get(k) for k in (u,v)]; vs=[k for k in vs if k is not None]
            return min(vs) if vs else None
        def pm(u,v):
            r=pmv(u,v); return 0 if r is None else r
        def bsf(u,v,p,q):
            """pairwise-min delta pm(u,v)-pm(p,q); a window with NO data contributes
            nothing (bs=0) -- ZC2c2: group-absent cols must not anchor at 0."""
            A=pmv(u,v); B=pmv(p,q)
            return 0 if (A is None or B is None) else A-B
        wstart=u0+1
        if sm:  # y-seam entry: std pair at wall S-1 (=u0+1) with B val := 234 - F_ylo;
                # on an X-seam entry line the adjustments COMPOSE: B := seam_op - 36 + 35
                # (3380 corner chunk: 0x08 = 9 - 1)
            a,b=u0,u0+1
            zloc=[z for z in (zl(xL,a),zl(xL,b),zl(xR,a),zl(xR,b)) if z is not None]
            ztc =[z for z in (zt(xL,a),zt(xL,b),zt(xR,a),zt(xR,b)) if z is not None]
            hc  =[v for v in (h(xL,a),h(xL,b),h(xR,a),h(xR,b)) if v>0]
            bsm=(_seam_marker_op()-1)%256 if (g==g0 and xseam_lo) else (234-_ylo_F(g))%256
            toks=[(bsm, max(zloc)-min(zloc))]; smooth=[(gx,b,min(zloc))]
            toks.append(((min(hc)-2)%256, max(ztc)-min(ztc))); smooth.append((gx,b,min(ztc)))
            wstart=u0+2
        elif g==g0 and xseam_lo:  # x-seam entry line (S-1): interior form, opener = seam - 36
            # opener run: BOTTOM-interval height of col u0 (OVH4: 2 not span 6)
            toks=[((_seam_marker_op()-36)%256, max(h(xL,u0) or 0,h(xR,u0) or 0))]; smooth=[(gx,u0,zc[u0])]
            _upwall(toks,smooth,[],colex(u0),gx,u0)            # Y-lo edge wall uppers
        else:
            toks=[((199-_ylo_F(g))%256, max(h(xL,u0) or 0,h(xR,u0) or 0))]; smooth=[(gx,u0,zc[u0])]
            _upwall(toks,smooth,[],colex(u0),gx,u0)            # Y-lo edge wall uppers
        def pres(y): return ivs(xL,y) is not None or ivs(xR,y) is not None
        def ctop(y): return cut_top(xL,y) or cut_top(xR,y)
        def cbot(y): return cut_bot(xL,y) or cut_bot(xR,y)
        for yw in range(wstart,u1+1):
            a,b=yw-1,yw
            ea=(ivs(xL,a) is not None)!=(ivs(xR,a) is not None)
            eb=(ivs(xL,b) is not None)!=(ivs(xR,b) is not None)
            hp2=t.get(a-1,0); bs=bsf(a,b,a-1,a)
            bval=(33-max(t[a],hp2)+bs)%256
            if ea or eb or not pres(a) or not pres(b):
                # edge wall incl group-absent columns (z-clipped away: ZC2c2 (33,3));
                # RUN = max BOTTOM-interval height (P3 3404: val keeps full span 33-8,
                # run stays 3), not the span
                rr=max(h(xL,a),h(xR,a),h(xL,b),h(xR,b))
                toks.append((bval,rr)); smooth.append((gx,yw,min(x for x in (zc[a],zc[b]) if x is not None)))
            else:
                # B/T are SURFACE tokens (ZC1/ZC2): B exists unless both cols lack a real
                # bottom (cut_bot); T exists unless both lack a real top (cut_top).
                # B val blanks to 33 when its lag-window {a-1,a} is entirely
                # present-and-top-cut; T val blanks to 33 when both cols are bottom-cut.
                if not (cbot(a) and cbot(b)):
                    zloc=[z for z in (zl(xL,a),zl(xL,b),zl(xR,a),zl(xR,b)) if z is not None]
                    bv = 33 if (ctop(a) and pres(a-1) and ctop(a-1)) else bval
                    toks.append((bv,max(zloc)-min(zloc))); smooth.append((gx,yw,min(zloc)))
                if not (ctop(a) and ctop(b)):
                    ztc=[z for z in (zt(xL,a),zt(xL,b),zt(xR,a),zt(xR,b)) if z is not None]
                    hc =[v for v in (h(xL,a),h(xL,b),h(xR,a),h(xR,b)) if v>0]
                    tv = 33 if (cbot(a) and cbot(b)) else (min(hc)-2)%256
                    toks.append((tv,max(ztc)-min(ztc))); smooth.append((gx,yw,min(ztc)))
            _upwall(toks,smooth,colex(a),colex(b),gx,yw)       # this wall's upper deck(s)
        if not ph:
            a,b=u1,u1+1
            if ctop(u1) and pres(u1-1) and ctop(u1-1):
                val=33          # Y-hi lag-window entirely top-cut (ZC1c1: (33,6))
            else:
                val=(33-max(t[a],t.get(a-1,0))+bsf(a,b,a-1,a))%256
            toks.append((val, max(h(xL,u1) or 0,h(xR,u1) or 0)))
            smooth.append((gx,u1+1,zc[u1]))
            _upwall(toks,smooth,colex(u1),[],gx,b)             # Y-hi edge wall uppers
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
    if nx>=20: pad+=6                     # provisional kink (3191 nx20: pad 52; 3189 nx13/14 classic; nx15-19 unseen)
    # measured pad cells (P12/P13 3422/3424); lines beyond these unseen
    if (nx,maxnc)==(4,9): pad-=2
    if (nx,maxnc)==(3,15): pad-=4
    # nx4 y-band: pad -2 at y0' in {4,19,-10} i.e. (y0-8)%15 in (4,5) (3418/3187c1/3187c2;
    # y' 0/9/10 unaffected (3162/3420/3217), nx6 at y27 unaffected (3380c1)). Empirical;
    # smells like phase alignment -- revisit with more y-cells.
    if nx<=4 and (mycols(0)[0]-8)%15 in (4,5): pad-=2   # 3400c1 extends to nx3; nx6 exempt (3380c1)
    if lead is None:
        lead=lead_law(planes[0][0], mycols(0)[0])
    markerspan=sum(len(m) for m in mplanes)+sum(mkgaps)
    # premat = pad - (lead-99), exact on every donor incl 3380c1's 0; when the formula
    # goes NEGATIVE it lands at 4 (X3 3382 mid: -8 -> 4; single point, provisional --
    # could be +12 wrap or const 4)
    premat=pad-(lead-99)
    if premat<0: premat=4
    mat_off=lead+markerspan+premat
    grp_off=mat_off+lead-9
    if xseam_lo: grp_off+=10               # hook (3178c2); NOT stacked with yseam (3380 corner)
    elif yseam_lo is not None: grp_off+=2  # hook (3187c2)
    if xseam_lo and yopen_hi is not None: grp_off-=2   # hook (3380 chunk (9,8,8))
    grpspan=sum(len(g) for g in gregs)+sum(ggaps)
    trailing=premat
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

def build_multichunk(cols, mc=None, chunk0=(8,8,8), smooth_fn=None):
    """Split GLOBAL cols (construct-local voxel coords, chunk0 covers 0..31 per axis) at
    32-voxel chunk boundaries in X, Y and Z -> {(cx,cy,cz): scan}. mc: int, or dict keyed
    by chunk.
    Split rule (byte-exact vs 3178/3187/3367 X/Y, 3376/3378 Z): a chunk carries
    planes/cols/z up to S=next boundary (one past its own range) plus, for X/Y, a phantom
    plane/col at S+1 for group math (open/uncapped high side); a chunk whose shape
    continues below carries from S-2 (negative local coords) with seam entry forms
    (Z: markers from S-2, group region clips at S-1 inside build_scan_general)."""
    IV=_norm(cols)
    xs=[x for x,_ in IV]; ys=[y for _,y in IV]
    zs=[v for iv in IV.values() for ab in iv for v in ab]
    sx0,sx1=min(xs),max(xs); sy0,sy1=min(ys),max(ys); sz0,sz1=min(zs),max(zs)
    cx0,cy0,cz0=chunk0
    out={}
    for ci in range(sx0//32, sx1//32+1):
      for cj in range(sy0//32, sy1//32+1):
        for ck in range(sz0//32, sz1//32+1):
            lox,hix=32*ci,32*ci+31
            loy,hiy=32*cj,32*cj+31
            loz,hiz=32*ck,32*ck+31
            xs_lo = sx0<lox; xs_hi = sx1>hix
            ys_lo = sy0<loy; ys_hi = sy1>hiy
            zs_lo = sz0<loz; zs_hi = sz1>hiz
            xf = lox-2 if xs_lo else sx0
            xt = hix+2 if xs_hi else sx1       # hix+1 carried + hix+2 phantom
            yf = loy-2 if ys_lo else sy0
            yt = hiy+2 if ys_hi else sy1       # hiy+1 carried + hiy+2 phantom
            zf = loz-2 if zs_lo else sz0
            zt_ = hiz+1 if zs_hi else sz1      # z carries to S, no phantom
            # chunk must OWN some voxels (not just overlap carry)
            if not any(lox<=x<=hix and loy<=y<=hiy and
                       any(b>=loz and a<=hiz for a,b in iv)
                       for (x,y),iv in IV.items()): continue
            sub={}
            for (x,y),iv in IV.items():
                if not (xf<=x<=xt and yf<=y<=yt): continue
                cl=tuple((max(a,zf)-loz, min(b,zt_)-loz) for a,b in iv
                         if b>=zf and a<=zt_)
                if cl: sub[(x-lox,y-loy)]=cl
            if not sub: continue
            # Y PHANTOM COL := COPY of the S col (3400: donor T=(4,0) = copy-h; true
            # col only used for the flatness flags). X phantom plane likewise (copy ==
            # true on every existing donor; 3189's seam-adjacent planes are identical).
            ycap=True; ymerge=True
            if ys_hi:
                Sy=hiy+1-loy
                for (x,y) in [k for k in sub if k[1]==Sy+1]: del sub[(x,y)]
                for (x,y) in [k for k in sub if k[1]==Sy]:
                    sub[(x,Sy+1)]=sub[(x,Sy)]
                ycap=all(IV.get((x+lox,hiy+2))==IV.get((x+lox,hiy+1))
                         for x in {k[0] for k in sub} if (x+lox,hiy+1) in IV)
            if ys_lo:
                ymerge=all(IV.get((x,loy-2))==IV.get((x,loy-1))
                           for x in {k[0]+lox for k in sub} if (x,loy-1) in IV)
            if xs_hi:
                Sx=hix+1-lox
                for k in [k for k in sub if k[0]==Sx+1]: del sub[k]
                for (x,y) in [k for k in sub if k[0]==Sx]:
                    sub[(Sx+1,y)]=sub[(Sx,y)]
            key=(cx0+ci,cy0+cj,cz0+ck)
            if mc is None:
                # carry view for the mc law = sub WITHOUT phantoms (marker range)
                mcv={c:iv for c,iv in sub.items()
                     if (not xs_hi or c[0]<=hix+1-lox) and (not ys_hi or c[1]<=hiy+1-loy)}
                m = mc_law(mcv, xopen_owner=(xs_hi and not xs_lo),
                                yopen_owner=(ys_hi and not ys_lo))
            else:
                m = mc[key] if isinstance(mc,dict) else mc
            # smooth_fn is defined over GLOBAL coords; chunks work in local coords, so
            # wrap with the chunk offset (field stays continuous across seams)
            sf=None
            if smooth_fn is not None:
                def sf(x,y,z,_ox=lox,_oy=loy,_oz=loz):
                    X,Y,Z=smooth_fn(x+_ox,y+_oy,z+_oz)
                    return (X-_ox,Y-_oy,Z-_oz)
            out[key]=build_scan_general(sub, m, smooth_fn=sf,
                xseam_lo=xs_lo, xopen_hi=xs_hi,
                yseam_lo=(yf-loy) if ys_lo else None,
                yopen_hi=(hiy+1-loy) if ys_hi else None,
                zseam_lo=zs_lo, zopen_hi=zs_hi,
                yopen_cap=ycap, yseam_merge=ymerge)
    return out
