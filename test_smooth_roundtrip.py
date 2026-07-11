"""Smoothing-path round-trips: extract donor displacement fields and regenerate
byte-exact through build_scan_general's smooth_fn path.
3191 = single-chunk smoothed sphere; 3189 = smoothed sphere ACROSS the X-seam."""
import sys, json, base64, lz4.block, os
sys.path.insert(0,'/home/du')
import du_general as dg

def chunks(name):
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

def marker_planes(B):
    def is_m(i):
        return i+5<=len(B) and B[i+1]==1 and B[i+2]==2 and B[i+4]==0 and B[i+3]<32
    i=0; out=[]; cur=[]
    while i<len(B):
        if is_m(i): cur.append((B[i],B[i+3]+1)); i+=5
        else:
            if cur: out.append(cur); cur=[]
            if B[i] not in (0,0xff): break
            i+=1
    if cur: out.append(cur)
    return out

def occ_from(mps,x_start):
    cols={}
    for k,pl in enumerate(mps):
        x=x_start+k; nc=len(pl); ylo=16-nc//2
        for c,(v,h) in enumerate(pl): cols[(x,ylo+c)]=(16-h//2,16+h//2-1)
    return cols

def after_markers(B):
    i=0
    while i<len(B):
        if B[i]==(0 if i%2==0 else 0xff): i+=1; continue
        if i+5<=len(B) and B[i+1]==1 and B[i+2]==2 and B[i+4]==0 and B[i+3]<32:
            i+=5; continue
        break
    return i

def gtokens(B):
    out=[]; i=0
    while i<len(B):
        if i+8<=len(B) and B[i+1]==1:
            v,r=B[i],B[i+2]
            if B[i+3]==0x7e and B[i+4]==0x7e and B[i+5]==0x7e and B[i+6]==r and B[i+7]==0:
                out.append((i,v,r,'plain',None)); i+=8; continue
            if r==0 and B[i+6]==0 and B[i+7]==0:
                out.append((i,v,r,'inpl',[(B[i+3],B[i+4],B[i+5])])); i+=8; continue
            L=3+4*(r+1)+1
            if i+L<=len(B) and B[i+L-1]==0 and r>0:
                out.append((i,v,r,'exp',[(B[i+3+4*k],B[i+4+4*k],B[i+5+4*k]) for k in range(r+1)])); i+=L; continue
        i+=1
    return out

def roundtrip(name, key, sub, mc, lead, **flags):
    D=chunks(name)[key][0]
    Q=[]
    dg.build_scan_general(sub,mc,lead=lead,smooth_fn=lambda x,y,z:(Q.append((x,y,z)) or (x,y,z)),**flags)
    field={}; qi=0
    for (off,v,r,k,pl) in gtokens(D[after_markers(D)+1:]):
        verts=Q[qi:qi+r+1]; qi+=r+1
        if k=='plain': continue
        for j,(vx,vy,vz) in enumerate(verts):
            dx,dy,dz=pl[j] if k=='exp' else pl[0]
            field[(vx,vy,vz)]=(vx+(dx-126)/84.0,vy+(dy-126)/84.0,vz+(dz-126)/84.0)
    S=dg.build_scan_general(sub,mc,lead=lead,smooth_fn=lambda x,y,z: field.get((x,y,z),(x,y,z)),**flags)
    ok=S==D
    print(f'{name} {key}: SMOOTH ROUND-TRIP {"BYTE-EXACT" if ok else f"FAIL ({len(S)}/{len(D)})"}')
    return ok

allok=True
D191,mc191=list(chunks('3191').items())[0][1]
c191=occ_from(marker_planes(D191),6)
allok&=roundtrip('3191',(8,8,8),c191,mc191,81,bnd_op=100)

don=chunks('3189')
c189={**occ_from(marker_planes(don[(8,8,8)][0]),20), **occ_from(marker_planes(don[(9,8,8)][0]),30)}
allok&=roundtrip('3189',(8,8,8),{(x,y):iv for (x,y),iv in c189.items() if x<=33},don[(8,8,8)][1],215,xopen_hi=True)
allok&=roundtrip('3189',(9,8,8),{(x-32,y):iv for (x,y),iv in c189.items() if x>=30},don[(9,8,8)][1],1,xseam_lo=True)
print('=== SMOOTH ROUND-TRIPS:', 'ALL BYTE-EXACT' if allok else 'FAILURES ABOVE','===')
