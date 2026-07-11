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
for name,cols,mcs in mctests:
    n=name.split()[0]
    don=mchunks(n); got=dg.build_multichunk(cols,mcs)
    for k in sorted(don):
        S=got.get(k); D=don[k][0]
        ok = S==D
        allok&=ok
        if ok: print(f'{name} chunk{k}: BYTE-EXACT')
        else:
            dif=[i for i in range(min(len(S or b''),len(D))) if S[i]!=D[i]]
            print(f'{name} chunk{k}: {len(dif)} diffs len {len(S or b"")}/{len(D)} @{dif[:5]}')
print('=== REGRESSION:', 'ALL BYTE-EXACT' if allok else 'FAILURES ABOVE', '===')
