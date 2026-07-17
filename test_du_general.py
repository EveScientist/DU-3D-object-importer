import sys, json, base64, lz4.block, os; sys.path.insert(0,'/home/du')
import importlib, du_general as dg; importlib.reload(dg)
def body(name):
    for d in ('exports','exports/archive'):
        p=f'/home/du/{d}/{name}_export.blueprint'
        if os.path.exists(p): break
    bp=json.load(open(p))
    for e in bp['VoxelData']:
        if e['h']!=3: continue
        raw=base64.b64decode(e['records']['voxel']['data']['$binary']); size=int.from_bytes(raw[4:8],'little')
        dec=bytes(lz4.block.decompress(raw[12:],uncompressed_size=size))
        if len(dec)>700: return dec[64:-40], int.from_bytes(dec[-40:-36],'little'), dec[64+99]
def flatcols(hplanes, z0=8):
    return {(x+8,y+8):(z0,z0+h-1) for x,row in enumerate(hplanes) for y,h in enumerate(row) if h>0}
def surfcols(zlo,zhi):
    return {(x+8,y+8):(zlo[x][y],zhi[x][y]) for x in range(len(zlo)) for y in range(len(zlo[0]))}
def narrowcols(sets,H,z0=8):
    return {(x+8,y+8):(z0,z0+H-1) for x,s in enumerate(sets) for y in s}
E1zlo=[[11]*5,[11,10,10,10,11],[11,10,9,10,11],[11,10,10,10,11],[11]*5]
E1zhi=[[12]*5,[12,13,13,13,12],[12,13,13,13,12],[12,13,13,13,12],[12]*5]
E1zhi[1][2]=13; E1zhi[2][2]=14; E1zhi[3][2]=13
tests=[
 ('3230 X1 ramp',    flatcols([[4]*4,[6]*4,[8]*4])),
 ('3238 pyramid',    flatcols([[4]*4,[4,6,8,6],[4]*4])),
 ('3252 PY2 flip',   flatcols([[2,4,6,8],[4,6,8,6],[6,8,6,4]])),
 ('3236 nc5 box',    flatcols([[8]*5]*3)),
 ('3318 OCC1',       narrowcols([{1,2,3},{0,1,2,3,4},{1,2,3}],4)),
 ('3320 OCC2',       narrowcols([{2},{1,2,3},{0,1,2,3,4},{1,2,3},{2}],4)),
 ('3325 OCC3',       narrowcols([{1,2,3},{0,1,2,3,4},{0,1,2,3,4},{0,1,2,3,4},{1,2,3}],4)),
 ('3307 E1',         surfcols(E1zlo,E1zhi)),
 ('3265 L1 lens',    surfcols([[11,10,9,10,11]]*3,[[12,13,14,13,12]]*3)),
 ('3273 M1 stairs',  surfcols([[12,10,8,6,4]]*3,[[13]*5]*3)),
 ('3353 B12',        flatcols([[4]*12]*8)),
 ('3355 B16',        flatcols([[4]*16]*12)),
 ('3357 OPD',        flatcols([[2,4,6,8],[8]*4,[6]*4])),
 ('3359 OPD2',       flatcols([[2,4,6,4],[8]*4,[6]*4])),
 ('3361 OVH1',       {**{(x,y):(8,9) for x in range(8,11) for y in range(8,11)},
                      **{(x,9):[(8,9),(12,13)] for x in range(8,11)}}),
 ('3363 OVH2',       {**{(x,y):(8,9) for x in range(8,11) for y in range(8,11)},
                      **{(x,9):[(8,9),(13,15)] for x in range(8,11)}}),
 ('3372 OVH3',       {**{(x,y):(8,9) for x in range(8,11) for y in range(8,11)},
                      **{(x,9):[(8,9),(12,14)] for x in range(8,11)}}),
 ('3374 OVH4',       {**{(x,y):(8,9) for x in range(8,11) for y in range(8,11)},
                      **{(x,y):[(8,9),(12,13)] for x in range(8,11) for y in (8,9)}}),
]
def mchunks(name):
    for d in ('exports','exports/archive'):
        p=f'/home/du/{d}/{name}_export.blueprint'
        if os.path.exists(p): break
    bp=json.load(open(p)); out={}
    for e in bp['VoxelData']:
        if e['h']!=3: continue
        raw=base64.b64decode(e['records']['voxel']['data']['$binary']); size=int.from_bytes(raw[4:8],'little')
        dec=bytes(lz4.block.decompress(raw[12:],uncompressed_size=size))
        if len(dec)<=700: continue
        key=tuple(int(e[k]['$numberLong']) for k in ('x','y','z'))
        out[key]=(dec[64:-40], int.from_bytes(dec[-40:-36],'little'))
    return out
H367={27:2,28:2,29:3,30:3,31:3,32:4,33:4,34:4}
mctests=[
 ('3178 X-seam box', {(x,y):(8,11) for x in range(27,35) for y in range(8,12)},
  {(8,8,8):755,(9,8,8):641}),
 ('3367 X-seam ramp', {(x,y):(8,8+H367[x]-1) for x in H367 for y in range(8,12)},
  {(8,8,8):755,(9,8,8):641}),
 ('3187 Y-seam box', {(x,y):(8,11) for x in range(8,12) for y in range(27,35)},
  {(8,8,8):657,(8,9,8):683}),
 ('3376 Z-seam box', {(x,y):(27,34) for x in range(8,12) for y in range(8,12)},
  {(8,8,8):603,(8,8,9):633}),
 ('3378 Z-seam steps', {(x,y):(27,[30,33,35,30][y-8]) for x in range(8,11) for y in range(8,12)},
  {(8,8,8):550,(8,8,9):582}),
 ('3404 cut+overhang', {**{(x,y):(28,30) for x in range(8,11) for y in (8,10)},
  **{(x,9):[(28,33),(36,38)] for x in range(8,11)}}, None),
 ('3406 OVH5 slab', {**{(x,y):(8,9) for x in range(8,11) for y in range(8,11)},
  **{(x,y):[(8,9),(12,14)] for x in range(8,11) for y in (8,9)}}, None),
 ('3380 XY-corner box', {(x,y):(8,11) for x in range(27,35) for y in range(27,35)},
  None),
 ('3382 X3 triple span', {(x,y):(8,11) for x in range(27,67) for y in range(8,12)},
  None),
 ('3493 X-seam nc8 box', {(x,y):(8,11) for x in range(28,40) for y in range(10,18)},
  None),
 # 3497 (single nx6 nc4, y8 z20) needs grp_off +2 -- UNDER INVESTIGATION (nx6 vs z20 confound,
 # isolation donors E/F pending); NOT a passing regression donor until the cause is isolated.
 ('3500 single nx8 nc8 flat', {(12+i,13+j):(8,11) for i in range(8) for j in range(8)}, None),
 ('3502 lead-sweep x16', {(16+i,8+j):(8,11) for i in range(4) for j in range(4)}, None),
 ('3504 lead-sweep x17', {(17+i,8+j):(8,11) for i in range(4) for j in range(4)}, None),
 ('3506 lead-sweep x18', {(18+i,8+j):(8,11) for i in range(4) for j in range(4)}, None),
 ('3508 single nx8 nc4 (resid0)', {(20+i,24+j):(12,15) for i in range(8) for j in range(4)}, None),
 ('3510 single nx5 nc4 (resid0)', {(9+i,18+j):(24,27) for i in range(5) for j in range(4)}, None),
 # nx6 pocket sweep 2026-07-16 (P6A-F): x0 11/24 CLEAN both z (locked here); x0 14 = grp+2@z8,
 # lead+2&pad+2@z20 (NEW: lead z-dependence!); x0 19 = grp+2@z20 only. Hooks live at the lead
 # short-step cells xp%5==1, attenuating with x0. P6C/P6D NOT regression donors (law unmapped).
 ('3734 P6A nx6 x11 z8',  {(11+i,8+j):(8,11)  for i in range(6) for j in range(4)}, None),
 ('3736 P6B nx6 x11 z20', {(11+i,8+j):(20,23) for i in range(6) for j in range(4)}, None),
 ('3742 P6E nx6 x24 z8',  {(24+i,8+j):(8,11)  for i in range(6) for j in range(4)}, None),
 ('3744 P6F nx6 x24 z20', {(24+i,8+j):(20,23) for i in range(6) for j in range(4)}, None),
 # small-nx y-laws (2026-07-16, items 6+7): lead y-term 7-PERIOD at nx<=4 (2*((yp+1)//7)),
 # grp_off = mat + max(lead7,lead9) - 9, pad y-band %7 in (4,5). Donors: fresh Y12-Y23 nx4
 # sweep + the RECLAIMED nx3 sweep 3520-3534 (was "contaminated" -- it was the 7-period law).
 ('3746 Y12 nx4', {(8+i,12+j):(8,11) for i in range(4) for j in range(4)}, None),
 ('3748 Y13 nx4', {(8+i,13+j):(8,11) for i in range(4) for j in range(4)}, None),
 ('3750 Y14 nx4', {(8+i,14+j):(8,11) for i in range(4) for j in range(4)}, None),
 ('3752 Y21 nx4', {(8+i,21+j):(8,11) for i in range(4) for j in range(4)}, None),
 ('3754 Y22 nx4', {(8+i,22+j):(8,11) for i in range(4) for j in range(4)}, None),
 ('3756 Y23 nx4', {(8+i,23+j):(8,11) for i in range(4) for j in range(4)}, None),
 ('3520 nx3 y13', {(8+i,13+j):(8,11) for i in range(3) for j in range(4)}, None),
 ('3522 nx3 y21', {(8+i,21+j):(8,11) for i in range(3) for j in range(4)}, None),
 ('3524 nx3 y22', {(8+i,22+j):(8,11) for i in range(3) for j in range(4)}, None),
 ('3526 nx3 y14', {(8+i,14+j):(8,11) for i in range(3) for j in range(4)}, None),
 ('3528 nx3 y15', {(8+i,15+j):(8,11) for i in range(3) for j in range(4)}, None),
 ('3530 nx3 y16', {(8+i,16+j):(8,11) for i in range(3) for j in range(4)}, None),
 ('3532 nx3 y19', {(8+i,19+j):(8,11) for i in range(3) for j in range(4)}, None),
 ('3534 nx3 y20', {(8+i,20+j):(8,11) for i in range(3) for j in range(4)}, None),
 # Item 9 cell fluke-guards (2026-07-16): (4,9)+1 far coords, nx20+6 plain box, (3,15)-4 1-var
 # probes. C315 full-interaction (3766: x20*y10*z18 -> grp+2 & pad-2) + C315XY (3776: grp+2)
 # NOT in reg (positional hook pocket, unmapped -- guarded).
 ('3764 C49 far', {(18+i,16+j):(14,17) for i in range(4) for j in range(9)}, None),
 ('3768 C20 nx20 flat', {(8+i,12+j):(8,11) for i in range(20) for j in range(6)}, None),
 ('3770 C315X', {(20+i,8+j):(8,10) for i in range(3) for j in range(15)}, None),
 ('3772 C315Y', {(8+i,10+j):(8,10) for i in range(3) for j in range(15)}, None),
 ('3774 C315Z', {(8+i,8+j):(18,20) for i in range(3) for j in range(15)}, None),
 ('3778 C315XZ', {(20+i,8+j):(18,20) for i in range(3) for j in range(15)}, None),
 ('3780 C315YZ', {(8+i,10+j):(18,20) for i in range(3) for j in range(15)}, None),
]

# --- CAVITY (Z-through) + WINDOW (capped-void) donors, 2026-07-14 (voxel sets) ---
def _tube(x0,y0,n,hole,z0=8,h=4):
    return {(x,y,z) for x in range(x0,x0+n) for y in range(y0,y0+n)
            for z in range(z0,z0+h) if (x,y) not in hole}
def _wall(xr,yr,zr,win):
    return {(x,y,z) for x in xr for y in yr for z in zr if (x,z) not in win}
_ve1={(x,y,z) for x in range(8,12) for y in range(8,14) for z in range(8,12)
      if not (x in(9,10) and y in(9,10,11))}
_ve2={(x,y,z) for x in range(8,12) for y in range(8,12) for z in range(8,13)
      if not (x in(9,10) and y in(9,10))}
cavwin_tests=[
 ('3536 tube 1x1 hole',   _tube(8,8,5,{(10,10)})),
 ('3538 tube 2x2 hole',   _tube(8,8,4,{(9,9),(9,10),(10,9),(10,10)})),
 ('3540 tube off-center', _tube(8,8,5,{(9,9)})),
 ('3542 tube 1x2 slot',   _tube(8,8,5,{(10,9),(10,10)})),
 ('3544 VE1 2x3 hole',    _ve1),
 ('3546 VE2 2x2 h5',      _ve2),
 ('3550 PW1 window 1x2',  _wall(range(8,13),(8,9),range(8,14),{(10,10),(10,11)})),
 ('3552 W2 window 1x3',   _wall(range(8,13),(8,9),range(8,15),{(10,10),(10,11),(10,12)})),
 ('3554 W4 window 2wide', _wall(range(8,13),(8,9),range(8,14),{(9,10),(9,11),(10,10),(10,11)})),
 ('3556 W5 window 3deep', _wall(range(8,13),range(8,11),range(8,14),{(10,10),(10,11)})),
 ('3559 MW1 two windows', _wall(range(8,13),(8,9),range(8,14),{(9,10),(9,11),(11,10),(11,11)})),
 ('3561 MW2 stacked',     _wall(range(8,13),(8,9),range(8,18),{(10,10),(10,11),(10,14),(10,15)})),
 ('3563 MW3 3-wide',      _wall(range(8,13),(8,9),range(8,14),{(x,z) for x in (9,10,11) for z in (10,11)})),
 ('3565 MW4 diff-z',      _wall(range(8,13),(8,9),range(8,16),{(9,10),(9,11),(11,12),(11,13)})),
 ('3567 SC1 solid 5^3',   {(x,y,z) for x in range(8,13) for y in range(8,13) for z in range(8,13)}),
 ('3569 SC2 sealed 7^3 shell', {(x,y,z) for x in range(8,15) for y in range(8,15) for z in range(8,15)
                                if not (10<=x<=12 and 10<=y<=12 and 10<=z<=12)}),
 ('3571 SC3 non-cubic cavity', {(x,y,z) for x in range(8,16) for y in range(8,15) for z in range(8,14)
                                if not (10<=x<=13 and 10<=y<=11 and 10<=z<=11)}),
 ('3573 SC4 two cavities', {(x,y,z) for x in range(8,18) for y in range(8,14) for z in range(8,14)
                            if not ((10<=x<=11 or 14<=x<=15) and 10<=y<=11 and 10<=z<=11)}),
 ('3575 SC5 solid nx10 (pad kink)', {(x,y,z) for x in range(8,18) for y in range(8,14) for z in range(8,14)}),
 ('3577 SC6 one cavity nx10', {(x,y,z) for x in range(8,18) for y in range(8,14) for z in range(8,14)
                               if not (10<=x<=11 and 10<=y<=11 and 10<=z<=11)}),
]

# --- h=1 donors (2026-07-14): built at min_thickness=1 (raw shape) ---
h1_tests=[
 ('3579 H1 plate 4x4 h=1', {(x,y,8) for x in range(8,12) for y in range(8,12)}),
 ('3581 H2 x-step h2|h1', {(x,y,z) for x in range(8,10) for y in range(8,12) for z in (8,9)}
                         | {(x,y,8) for x in range(10,12) for y in range(8,12)}),
 ('3583 H3 y-step h2|h1', {(x,y,z) for x in range(8,12) for y in range(8,10) for z in (8,9)}
                         | {(x,y,8) for x in range(8,12) for y in range(10,12)}),
 ('3585 H4 wedge h3|h2|h1', {(x,y,z) for x in (8,9) for y in range(8,12) for z in (8,9,10)}
                           | {(x,y,z) for x in (10,11) for y in range(8,12) for z in (8,9)}
                           | {(x,y,8) for x in (12,13) for y in range(8,12)}),
 ('3588 H6 1-tall gap (val-0 marker)', {(x,y,z) for x in range(8,13) for y in (8,9) for z in range(8,14)
                                        if not ((x,z)==(10,11))}),
 ('3548 SB 1-thick sealed shell', {(x,y,z) for x in range(8,13) for y in range(8,13) for z in range(8,13)
                                   if x in(8,12) or y in(8,12) or z in(8,12)}),
]
def _mkh(H):
    return {(x,y,z) for x,row in H.items() for y,h in row.items() for z in range(8,8+h)}
def _mkr(rows):
    return {(x,y0+i,z) for x,(y0,hs) in rows.items() for i,h in enumerate(hs) for z in range(8,8+h)}
h1_tests += [
 ('3646 NC15 diamond (cyclic pad band)', _mkr({8:(10,[2,3,3,4,4,4,4,4,3,3,2]),
    9:(8,[2,3,3,4,4,5,5,5,5,5,4,4,3,3,2]), 10:(10,[2,3,3,4,4,4,4,4,3,3,2])})),
 ('3648 NC17 diamond (cyclic pad band)', _mkr({8:(10,[2,3,3,4,4,4,4,4,4,4,3,3,2]),
    9:(8,[2,3,3,4,4,5,5,5,5,5,5,5,4,4,3,3,2]), 10:(10,[2,3,3,4,4,4,4,4,4,4,3,3,2])})),
 ('3590 C1 diamond dome h1-rim', _mkh({8:{9:1,10:2,11:1}, 9:{8:1,9:2,10:3,11:2,12:1}, 10:{9:1,10:2,11:1}})),
 ('3592 C2 round dome h1-rim', _mkh({13:{16:1},14:{14:1,15:2,16:2,17:2,18:1},15:{14:2,15:3,16:3,17:3,18:2},
                                     16:{13:1,14:2,15:3,16:3,17:3,18:2,19:1},17:{14:2,15:3,16:3,17:3,18:2},
                                     18:{14:1,15:2,16:2,17:2,18:1},19:{16:1}})),
 # H1-RIM donor 3718 (= 3712 with 20 rim cols lowered to h1): pinned the marker-gap band law
 # = _mkband(effnc(LEFT, h1 cols excluded) + nc(RIGHT)).
 ('3718 H1RIM17', _mkh({9:{16:1,17:1,18:1},10:{13:1,14:2,15:3,16:3,17:3,18:3,19:3,20:2,21:1},
   11:{12:2,13:3,14:3,15:4,16:4,17:4,18:4,19:4,20:3,21:3,22:2},
   12:{11:2,12:3,13:4,14:4,15:5,16:5,17:5,18:5,19:5,20:4,21:4,22:3,23:2},
   13:{10:1,11:3,12:4,13:4,14:5,15:5,16:5,17:5,18:5,19:5,20:5,21:4,22:4,23:3,24:1},
   14:{10:2,11:3,12:4,13:5,14:5,15:5,16:6,17:6,18:6,19:5,20:5,21:5,22:4,23:3,24:2},
   15:{10:3,11:4,12:5,13:5,14:5,15:6,16:6,17:6,18:6,19:6,20:5,21:5,22:5,23:4,24:3},
   16:{9:1,10:3,11:4,12:5,13:5,14:6,15:6,16:6,17:6,18:6,19:6,20:6,21:5,22:5,23:4,24:3,25:1},
   17:{9:1,10:3,11:4,12:5,13:5,14:6,15:6,16:6,17:6,18:6,19:6,20:6,21:5,22:5,23:4,24:3,25:1},
   18:{9:1,10:3,11:4,12:5,13:5,14:6,15:6,16:6,17:6,18:6,19:6,20:6,21:5,22:5,23:4,24:3,25:1},
   19:{10:3,11:4,12:5,13:5,14:5,15:6,16:6,17:6,18:6,19:6,20:5,21:5,22:5,23:4,24:3},
   20:{10:2,11:3,12:4,13:5,14:5,15:5,16:6,17:6,18:6,19:5,20:5,21:5,22:4,23:3,24:2},
   21:{10:1,11:3,12:4,13:4,14:5,15:5,16:5,17:5,18:5,19:5,20:5,21:4,22:4,23:3,24:1},
   22:{11:2,12:3,13:4,14:4,15:5,16:5,17:5,18:5,19:5,20:4,21:4,22:3,23:2},
   23:{12:2,13:3,14:3,15:4,16:4,17:4,18:4,19:4,20:3,21:3,22:2},
   24:{13:1,14:2,15:3,16:3,17:3,18:3,19:3,20:2,21:1},25:{16:1,17:1,18:1}})),
]
allok=True
for name,cols in tests:
    n=name.split()[0]
    D,mc,bop=body(n)
    S=dg.build_scan_general(cols,mc,bnd_op=bop)
    ok = S==D
    allok&=ok
    if ok: print(f'{name}: BYTE-EXACT')
    else:
        dif=[i for i in range(min(len(S),len(D))) if S[i]!=D[i]]
        print(f'{name}: {len(dif)} diffs len {len(S)}/{len(D)} @{dif[:5]}' + ''.join(f' [{i}]{S[i]:02x}!={D[i]:02x}' for i in dif[:5]))
for x0,y0,nx,nc,bp in [(9,8,4,4,'3408'),(11,8,4,4,'3410'),(12,8,4,4,'3412'),(20,8,4,4,'3414'),
        (21,8,4,4,'3416'),(8,12,4,4,'3418'),(8,17,4,4,'3420'),(8,8,4,9,'3422'),(8,8,3,15,'3424'),(8,8,4,5,'3426')]:
    mctests.append((f'{bp} sweep x{x0}y{y0} {nx}x{nc}',
                    {(x0+i,y0+j):(8,11) for i in range(nx) for j in range(nc)}, None))
for name,cols,mcs in mctests:
    n=name.split()[0]
    don=mchunks(n)
    if mcs is None: mcs={k:v[1] for k,v in don.items()}
    got=dg.build_multichunk(cols,mcs)
    for k in sorted(don):
        S=got.get(k); D=don[k][0]
        ok = S==D
        allok&=ok
        if ok: print(f'{name} chunk{k}: BYTE-EXACT')
        else:
            dif=[i for i in range(min(len(S or b''),len(D))) if S[i]!=D[i]]
            print(f'{name} chunk{k}: {len(dif)} diffs len {len(S or b"")}/{len(D)} @{dif[:5]}')

# --- ARC #13 pipeline donors (voxel occupancy -> build_multichunk, mc from law) ---
def _mk(H):
    v=set()
    for x,row in H.items():
        for y,h in row.items():
            for z in range(8,8+h): v.add((x,y,z))
    return v
import obj_pipeline as _P
pipe_tests=[
 ('3466 NCV1', _mk({8:{9:2,10:3,11:2},9:{8:2,9:3,10:4,11:3,12:2},10:{9:2,10:3,11:2}})),
 ('3468 NCV2', _mk({8:{10:2},9:{8:2,9:3,10:4,11:3,12:2},10:{10:2}})),
 ('3470 NCV3', _mk({8:{10:2,11:3,12:4,13:3,14:2},9:{9:2,10:3,11:4,12:5,13:4,14:3,15:2},10:{10:2,11:3,12:4,13:3,14:2}})),
 ('3473 NCV4', _mk({8:{11:2,12:3,13:2},9:{10:2,11:3,12:4,13:3,14:2},10:{10:3,11:4,12:5,13:4,14:3},11:{11:2,12:3,13:2}})),
 ('3478 NCV5', _mk({8:{9:2,10:3,11:4,12:3,13:2},9:{10:5,11:6,12:5},10:{10:4,11:5,12:4},11:{10:3,11:4,12:3},12:{11:2}})),
 ('3483 DOMER4', _mk({12:{16:2},13:{14:3,15:3,16:4,17:3,18:3},14:{13:3,14:4,15:4,16:4,17:4,18:4,19:3},15:{13:3,14:4,15:5,16:5,17:5,18:4,19:3},16:{12:2,13:4,14:4,15:5,16:5,17:5,18:4,19:4,20:2},17:{13:3,14:4,15:5,16:5,17:5,18:4,19:3},18:{13:3,14:4,15:4,16:4,17:4,18:4,19:3},19:{14:3,15:3,16:4,17:3,18:3},20:{16:2}})),
 ('3475 DOMER3', _mk({13:{16:2},14:{14:2,15:3,16:3,17:3,18:2},15:{14:3,15:4,16:4,17:4,18:3},16:{13:2,14:3,15:4,16:4,17:4,18:3,19:2},17:{14:3,15:4,16:4,17:4,18:3},18:{14:2,15:3,16:3,17:3,18:2},19:{16:2}})),
 # WNC15 3653: nc15 equal-nc RUN [13,13,15,15,15,13,13] -> pins curved nc15 pad = 244-10nx
 # (slope -10; killed the cyclic-band misfit). Run/opener/b2 grammar at width>=13 CONFIRMED.
 ('3653 WNC15run', _mk({8:{9:2,10:3,11:4,12:4,13:4,14:4,15:5,16:4,17:4,18:4,19:4,20:3,21:2},
   9:{9:2,10:3,11:4,12:4,13:5,14:5,15:5,16:5,17:5,18:4,19:4,20:3,21:2},
   10:{8:2,9:3,10:4,11:4,12:4,13:5,14:5,15:5,16:5,17:5,18:4,19:4,20:4,21:3,22:2},
   11:{8:2,9:3,10:4,11:4,12:5,13:5,14:5,15:5,16:5,17:5,18:5,19:4,20:4,21:3,22:2},
   12:{8:2,9:3,10:4,11:4,12:4,13:5,14:5,15:5,16:5,17:5,18:4,19:4,20:4,21:3,22:2},
   13:{9:2,10:3,11:4,12:4,13:5,14:5,15:5,16:5,17:5,18:4,19:4,20:3,21:2},
   14:{9:2,10:3,11:4,12:4,13:4,14:4,15:5,16:4,17:4,18:4,19:4,20:3,21:2}})),
 # WNC15B 3657 (as-built): nc15 shoulders [11,11,13,13,15,15,15,13,13,11,11] nx11 -> pins the
 # CURVED-band pad KINK (+2 at nx>=10 even when nx<maxnc; slope-10 244-110+2=136). 11<->13
 # transition content CONFIRMED byte-exact.
 ('3657 WNC15B', _mk({8:{10:2,11:2,12:3,13:3,14:4,15:4,16:4,17:3,18:3,19:2,20:2},
   9:{10:2,11:3,12:4,13:4,14:4,15:4,16:4,17:3,18:3,19:3,20:2},
   10:{9:2,10:3,11:4,12:4,13:4,14:4,15:5,16:4,17:4,18:4,19:4,20:3,21:2},
   11:{9:2,10:3,11:4,12:4,13:5,14:5,15:5,16:5,17:5,18:4,19:4,20:3,21:2},
   12:{8:2,9:3,10:4,11:4,12:4,13:5,14:5,15:5,16:5,17:5,18:4,19:4,20:4,21:3,22:2},
   13:{8:2,9:3,10:4,11:4,12:5,13:5,14:5,15:5,16:5,17:5,18:5,19:4,20:4,21:3,22:2},
   14:{8:2,9:3,10:4,11:4,12:4,13:5,14:5,15:5,16:5,17:5,18:4,19:4,20:4,21:3,22:2},
   15:{9:2,10:3,11:4,12:4,13:5,14:5,15:5,16:5,17:5,18:4,19:4,20:3,21:2},
   16:{9:2,10:3,11:4,12:4,13:4,14:4,15:5,16:4,17:4,18:4,19:4,20:3,21:2},
   17:{10:2,11:3,12:4,13:4,14:4,15:4,16:4,17:3,18:3,19:3,20:2},
   18:{10:2,11:2,12:3,13:3,14:4,15:4,16:4,17:3,18:3,19:2,20:2}})), # FULL-DOME donor 3696 (as-built: x20 cols y14-16 at h3 build variance): nx15 maxnc15 dome ->
 # pins curved pad kink = 2*q^2 QUADRATIC (q=(nx-5)//5): pad 102 @ nx15. mc/lead/gaps confirmed.
 ('3696 FULLDOME15', _mk({8:{14:2,15:2,16:2},9:{12:2,13:2,14:3,15:3,16:3,17:2,18:2},
   10:{10:2,11:2,12:3,13:3,14:4,15:4,16:4,17:3,18:3,19:2,20:2},
   11:{10:2,11:3,12:4,13:4,14:4,15:4,16:4,17:4,18:4,19:3,20:2},
   12:{9:2,10:3,11:4,12:4,13:4,14:4,15:5,16:4,17:4,18:4,19:4,20:3,21:2},
   13:{9:2,10:3,11:4,12:4,13:5,14:5,15:5,16:5,17:5,18:4,19:4,20:3,21:2},
   14:{8:2,9:3,10:4,11:4,12:4,13:5,14:5,15:5,16:5,17:5,18:4,19:4,20:4,21:3,22:2},
   15:{8:2,9:3,10:4,11:4,12:5,13:5,14:5,15:5,16:5,17:5,18:5,19:4,20:4,21:3,22:2},
   16:{8:2,9:3,10:4,11:4,12:4,13:5,14:5,15:5,16:5,17:5,18:4,19:4,20:4,21:3,22:2},
   17:{9:2,10:3,11:4,12:4,13:5,14:5,15:5,16:5,17:5,18:4,19:4,20:3,21:2},
   18:{9:2,10:3,11:4,12:4,13:4,14:4,15:5,16:4,17:4,18:4,19:4,20:3,21:2},
   19:{10:2,11:3,12:4,13:4,14:4,15:4,16:4,17:4,18:4,19:3,20:2},
   20:{10:2,11:2,12:3,13:3,14:3,15:3,16:3,17:3,18:3,19:2,20:2},
   21:{12:2,13:2,14:3,15:3,16:3,17:2,18:2},22:{14:2,15:2,16:2}})), # WNC17 3707: [15,15,17,17,17,15,15] run -> pins nc17 base242+2(idrun) slope-10 AND the b2
 # flat-top gate (identical CURVED planes keep b2=2; backlog item 13).
 # ITEMS 11+17 (2026-07-16): G11/G24 asymmetric +1-col widenings + NCV6 (reclaimed) ->
 # FIVE laws: 35*INTEGER-mean F (all sites); ncg(interior)=span of LOWER-ylo plane (tie:left);
 # +X boundary wider-last = FULLY own-pair (35*span_own + Tlast_OWN, byte 740!); pad nx2 -2.
 ('3786 G11', _mk({8:{8:2,9:3,10:4,11:3,12:2},9:{8:2,9:3,10:4,11:4,12:3,13:2}})),
 ('3784 G24', _mk({8:{8:2,9:3,10:4,11:4,12:5,13:5,14:5,15:5,16:4,17:4,18:3,19:2},
   9:{8:2,9:3,10:4,11:4,12:5,13:5,14:5,15:5,16:4,17:4,18:3,19:2,20:2}})),
 ('3481 NCV6', _mk({8:{11:2},9:{10:3,11:4,12:3},10:{10:4,11:5,12:4},11:{10:5,11:6,12:5},
   12:{9:2,10:3,11:4,12:3,13:2}})),
 # ITEM 8 (2026-07-16): NC9/NC10 diamonds + WNC10 run -> curved nc9/10 = 244-10nx +2@nx>=5
 # + 2*((nx-5)//4)^2 (old 239-9nx was the nx7/nx9 degeneracy). WNC10 as-built (x14=x13 profile
 # variance) also pinned the shadow WIDER-previous clause (ncp(L-1)>ncp(L) -> shifted _F(L)).
 ('3758 NC9diamond', _mk({8:{10:2,11:3,12:3,13:4,14:3,15:3,16:2},
   9:{9:2,10:3,11:3,12:4,13:4,14:4,15:3,16:3,17:2},10:{10:2,11:3,12:3,13:4,14:3,15:3,16:2}})),
 ('3760 NC10diamond', _mk({8:{10:2,11:3,12:3,13:4,14:4,15:3,16:3,17:2},
   9:{9:2,10:3,11:3,12:4,13:4,14:4,15:4,16:3,17:3,18:2},
   10:{10:2,11:3,12:3,13:4,14:4,15:3,16:3,17:2}})),
 ('3762 WNC10run', _mk({8:{10:2,11:3,12:4,13:4,14:4,15:4,16:3,17:2},
   9:{10:2,11:3,12:4,13:5,14:5,15:4,16:3,17:2},
   10:{9:2,10:3,11:4,12:4,13:5,14:5,15:4,16:4,17:3,18:2},
   11:{9:2,10:3,11:4,12:5,13:5,14:5,15:5,16:4,17:3,18:2},
   12:{9:2,10:3,11:4,12:4,13:5,14:5,15:4,16:4,17:3,18:2},
   13:{10:2,11:3,12:4,13:5,14:5,15:4,16:3,17:2},
   14:{10:2,11:3,12:4,13:5,14:5,15:4,16:3,17:2}})),
 # NC13 3728 + WNC13 3730 (nx3 diamond + nx7 run): VERIFY nc12-14 slope-9 branch (235-9nx)
 # -- holds at both nx points (208/172). Also: WNC13 mc=767 (mat 0xff hidden) end-to-end.
 ('3728 NC13diamond', _mk({8:{10:2,11:3,12:3,13:4,14:4,15:4,16:3,17:3,18:2},
   9:{8:2,9:3,10:3,11:4,12:4,13:5,14:5,15:5,16:4,17:4,18:3,19:3,20:2},
   10:{10:2,11:3,12:3,13:4,14:4,15:4,16:3,17:3,18:2}})),
 ('3730 WNC13run', _mk({8:{9:2,10:3,11:4,12:4,13:4,14:4,15:4,16:4,17:4,18:3,19:2},
   9:{9:2,10:3,11:4,12:4,13:5,14:5,15:5,16:4,17:4,18:3,19:2},
   10:{8:2,9:3,10:4,11:4,12:4,13:5,14:5,15:5,16:4,17:4,18:4,19:3,20:2},
   11:{8:2,9:3,10:4,11:4,12:5,13:5,14:5,15:5,16:5,17:4,18:4,19:3,20:2},
   12:{8:2,9:3,10:4,11:4,12:4,13:5,14:5,15:5,16:4,17:4,18:4,19:3,20:2},
   13:{9:2,10:3,11:4,12:4,13:5,14:5,15:5,16:4,17:4,18:3,19:2},
   14:{9:2,10:3,11:4,12:4,13:4,14:4,15:4,16:4,17:4,18:3,19:2}})),
 # NC16 3723 (nx3 diamond) + WNC16 3725 (nx7 run, NO identical planes): pin nc16 = 242-10nx
 # +2 step at nx>=5 -- same cell as nc17, KILLING the idrun reading (3725 has no id-runs).
 ('3723 NC16diamond', _mk({8:{10:2,11:3,12:3,13:4,14:4,15:4,16:4,17:4,18:4,19:3,20:3,21:2},
   9:{8:2,9:3,10:3,11:4,12:4,13:5,14:5,15:5,16:5,17:5,18:5,19:4,20:4,21:3,22:3,23:2},
   10:{10:2,11:3,12:3,13:4,14:4,15:4,16:4,17:4,18:4,19:3,20:3,21:2}})),
 ('3725 WNC16run', _mk({8:{9:2,10:3,11:4,12:4,13:4,14:4,15:5,16:5,17:4,18:4,19:4,20:4,21:3,22:2},
   9:{9:2,10:3,11:4,12:4,13:5,14:5,15:5,16:5,17:5,18:5,19:4,20:4,21:3,22:2},
   10:{8:2,9:3,10:4,11:4,12:4,13:5,14:5,15:5,16:5,17:5,18:5,19:4,20:4,21:4,22:3,23:2},
   11:{8:2,9:3,10:4,11:4,12:5,13:5,14:5,15:6,16:6,17:5,18:5,19:5,20:4,21:4,22:3,23:2},
   12:{8:2,9:3,10:4,11:4,12:4,13:5,14:5,15:5,16:5,17:5,18:5,19:4,20:4,21:4,22:3,23:2},
   13:{9:2,10:3,11:4,12:4,13:5,14:5,15:5,16:5,17:5,18:5,19:4,20:4,21:3,22:2},
   14:{9:2,10:3,11:4,12:4,13:4,14:4,15:5,16:5,17:4,18:4,19:4,20:4,21:3,22:2}})),
 ('3707 WNC17run', _mk({8:{10:2,11:3,12:4,13:4,14:5,15:5,16:5,17:5,18:5,19:5,20:5,21:4,22:4,23:3,24:2},
   9:{10:2,11:3,12:4,13:5,14:5,15:5,16:6,17:6,18:6,19:5,20:5,21:5,22:4,23:3,24:2},
   10:{9:2,10:3,11:4,12:5,13:5,14:6,15:6,16:6,17:6,18:6,19:6,20:6,21:5,22:5,23:4,24:3,25:2},
   11:{9:2,10:3,11:4,12:5,13:5,14:6,15:6,16:6,17:6,18:6,19:6,20:6,21:5,22:5,23:4,24:3,25:2},
   12:{9:2,10:3,11:4,12:5,13:5,14:6,15:6,16:6,17:6,18:6,19:6,20:6,21:5,22:5,23:4,24:3,25:2},
   13:{10:2,11:3,12:4,13:5,14:5,15:5,16:6,17:6,18:6,19:5,20:5,21:5,22:4,23:3,24:2},
   14:{10:2,11:3,12:4,13:4,14:5,15:5,16:5,17:5,18:5,19:5,20:5,21:4,22:4,23:3,24:2}})), # FULL 15a donor 3712 (nx17 maxnc17 dome, h3-edge planes x15/x19): pinned the SHADOW-rule
 # gate = MAX-TOP not last-col Tlast (1-byte diff at junction 16|17).
 ('3712 FULLDOME17', _mk({9:{16:2,17:2,18:2},10:{13:2,14:2,15:3,16:3,17:3,18:3,19:3,20:2,21:2},
   11:{12:2,13:3,14:3,15:4,16:4,17:4,18:4,19:4,20:3,21:3,22:2},
   12:{11:2,12:3,13:4,14:4,15:5,16:5,17:5,18:5,19:5,20:4,21:4,22:3,23:2},
   13:{10:2,11:3,12:4,13:4,14:5,15:5,16:5,17:5,18:5,19:5,20:5,21:4,22:4,23:3,24:2},
   14:{10:2,11:3,12:4,13:5,14:5,15:5,16:6,17:6,18:6,19:5,20:5,21:5,22:4,23:3,24:2},
   15:{10:3,11:4,12:5,13:5,14:5,15:6,16:6,17:6,18:6,19:6,20:5,21:5,22:5,23:4,24:3},
   16:{9:2,10:3,11:4,12:5,13:5,14:6,15:6,16:6,17:6,18:6,19:6,20:6,21:5,22:5,23:4,24:3,25:2},
   17:{9:2,10:3,11:4,12:5,13:5,14:6,15:6,16:6,17:6,18:6,19:6,20:6,21:5,22:5,23:4,24:3,25:2},
   18:{9:2,10:3,11:4,12:5,13:5,14:6,15:6,16:6,17:6,18:6,19:6,20:6,21:5,22:5,23:4,24:3,25:2},
   19:{10:3,11:4,12:5,13:5,14:5,15:6,16:6,17:6,18:6,19:6,20:5,21:5,22:5,23:4,24:3},
   20:{10:2,11:3,12:4,13:5,14:5,15:5,16:6,17:6,18:6,19:5,20:5,21:5,22:4,23:3,24:2},
   21:{10:2,11:3,12:4,13:4,14:5,15:5,16:5,17:5,18:5,19:5,20:5,21:4,22:4,23:3,24:2},
   22:{11:2,12:3,13:4,14:4,15:5,16:5,17:5,18:5,19:5,20:4,21:4,22:3,23:2},
   23:{12:2,13:3,14:3,15:4,16:4,17:4,18:4,19:4,20:3,21:3,22:2},
   24:{13:2,14:2,15:3,16:3,17:3,18:3,19:3,20:2,21:2},25:{16:2,17:2,18:2}})),]
for name,vox in pipe_tests:
    n=name.split()[0]
    D,mc,bop=body(n)
    S=_P.build_scans(vox)[(8,8,8)]
    ok=S==D; allok&=ok
    print(f'{name}: BYTE-EXACT' if ok else f'{name}: {sum(1 for i in range(min(len(S),len(D))) if S[i]!=D[i])} diffs')

for name,vox in cavwin_tests:
    n=name.split()[0]
    D,mc,bop=body(n)
    S=_P.build_scans(vox)[(8,8,8)]
    ok=S==D; allok&=ok
    print(f'{name}: BYTE-EXACT' if ok else f'{name}: {sum(1 for i in range(min(len(S),len(D))) if S[i]!=D[i])} diffs len {len(S)}/{len(D)}')

for name,vox in h1_tests:
    n=name.split()[0]
    D,mc,bop=body(n)
    S=dg.build_multichunk(_P.to_columns(vox, min_thickness=1), mc=None)[(8,8,8)]
    ok=S==D; allok&=ok
    print(f'{name}: BYTE-EXACT' if ok else f'{name}: {sum(1 for i in range(min(len(S),len(D))) if S[i]!=D[i])} diffs len {len(S)}/{len(D)}')

# --- DEPLOY-PROVEN artifact: 13h dome (nx11=maxnc11 CURVED, pad=138 NO kink) ---
# Shape reconstructed from its own markers; guards the curved-vs-flat pad-kink split.
def _scan_of_bp(path):
    import base64, lz4.block
    for e in json.load(open(path))['VoxelData']:
        if e['h']!=3: continue
        raw=base64.b64decode(e['records']['voxel']['data']['$binary'])
        d=bytes(lz4.block.decompress(raw[12:],uncompressed_size=int.from_bytes(raw[4:8],'little')))
        if len(d)>700: return d[64:-40]
try:
    _D13h=_scan_of_bp('/home/du/tests/deployment13h_dome_r5.blueprint')
    _i=0
    while _i<len(_D13h) and _D13h[_i]==(0 if _i%2==0 else 0xff): _i+=1
    def _ism(j): return j+5<=len(_D13h) and _D13h[j+1]==1 and 2<=_D13h[j+2]<=17 and _D13h[j+3]<32 and _D13h[j+4]==0
    _pl=[]; _cur=[]
    while True:
        while _ism(_i): _cur.append(_D13h[_i+3]+1); _i+=5
        _pl.append(_cur); _cur=[]
        _j=_i
        while _j<len(_D13h) and _D13h[_j] in (0,0xff) and not _ism(_j): _j+=1
        if _ism(_j): _i=_j
        else: break
    _v13h={(11+pi,16-len(hs)//2+ci,z) for pi,hs in enumerate(_pl) for ci,h in enumerate(hs) for z in range(8,8+h)}
    _S=dg.build_multichunk(_P.to_columns(_v13h,min_thickness=1))[(8,8,8)]
    ok=_S==_D13h; allok&=ok
    print('13h deploy-proven dome: BYTE-EXACT' if ok else f'13h deploy-proven dome: DIFFS len {len(_S)}/{len(_D13h)}')
except FileNotFoundError:
    print('13h deploy-proven dome: blueprint missing, skipped')

print('=== REGRESSION:', 'ALL BYTE-EXACT' if allok else 'FAILURES ABOVE', '===')
