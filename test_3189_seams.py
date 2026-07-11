"""3189 (24-vox sphere crossing X) revalidation vs build_multichunk.
Occupancy read from donor markers (z-symmetric around 16, y-centered around 16)."""
import sys; sys.path.insert(0,'/home/du'); sys.path.insert(0,'/home/du')
import importlib, du_general as dg; importlib.reload(dg)
import json, base64, lz4.block, os
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

don=chunks('3189')
C1,mc1=don[(8,8,8)]; C2,mc2=don[(9,8,8)]

def marker_planes(D):
    def is_m(i):
        return i+5<=len(D) and D[i+1]==1 and D[i+2]==2 and D[i+4]==0 and D[i+3]<32
    i=0; out=[]; cur=[]; start=None
    while i<len(D):
        if is_m(i) and not (D[i] in (0,0xff) and D[i+1]==1==0):  # marker
            if not cur: start=i
            cur.append((D[i],D[i+3]+1)); i+=5
        else:
            if cur: out.append((start,cur)); cur=[]
            if D[i] not in (0,0xff):
                # stop at mat byte (end of marker region)
                break
            i+=1
    if cur: out.append((start,cur))
    return out

mp1=marker_planes(C1); mp2=marker_planes(C2)
print('chunk1 marker planes:',len(mp1),'ncs',[len(p) for _,p in mp1])
print('chunk2 marker planes:',len(mp2),'ncs',[len(p) for _,p in mp2])

# global occupancy: chunk1 planes = x20..32; chunk2 = local -2..11 -> global 30..43
def occ_from(mps, x_start):
    cols={}
    for k,(off,pl) in enumerate(mps):
        x=x_start+k; nc=len(pl); ylo=16-nc//2
        for c,(v,h) in enumerate(pl):
            cols[(x,ylo+c)]=(16-h//2, 16+h//2-1)
        # sanity: h even
        assert all(h%2==0 for _,h in pl), (x,pl)
    return cols
o1=occ_from(mp1,20); o2=occ_from(mp2,30)
# overlap agreement
ov={k for k in o1 if k in o2}
bad=[k for k in ov if o1[k]!=o2[k]]
print('overlap cols:',len(ov),'disagreements:',len(bad))
cols={**o1,**o2}
xs=sorted({x for x,_ in cols})
print('global planes x',xs[0],'..',xs[-1],'total cols',len(cols))

# ---- generate both chunks (mirror build_multichunk's split, with measured leads) ----
sub1={(x,y):iv for (x,y),iv in cols.items() if x<=33}          # planes 20..32 + phantom 33
S1=dg.build_scan_general(sub1, mc1, xopen_hi=True, lead=215)
sub2={(x-32,y):iv for (x,y),iv in cols.items() if x>=30}       # local -2..11
S2=dg.build_scan_general(sub2, mc2, xseam_lo=True, lead=1)

def tokseq(D):
    """(val,run) sequence of the group region, handling plain/in-place/expanded groups.
    Returns list of (offset,val,run,kind). Walks from first token-like group after mat."""
    out=[]; i=0
    n=len(D)
    while i<n:
        if i+8<=n and D[i+1]==1:
            v,r=D[i],D[i+2]
            if D[i+3]==0x7e and D[i+4]==0x7e and D[i+5]==0x7e and D[i+6]==r and D[i+7]==0:
                out.append((i,v,r,'plain')); i+=8; continue
            if r==0 and D[i+6]==0 and D[i+7]==0:
                out.append((i,v,r,'inpl')); i+=8; continue
            # expanded runN: [v,1,r]+(r+1)*4+[0]
            L=3+4*(r+1)+1
            if i+L<=n and D[i+L-1]==0 and r>0:
                out.append((i,v,r,'exp')); i+=L; continue
        i+=1
    return out

for name,S,D in (('chunk1',S1,C1),('chunk2',S2,C2)):
    # markers: compare the marker region bytes (up to mat byte area)
    m_s=marker_planes(S); m_d=marker_planes(D)
    mok = [pl for _,pl in m_s]==[pl for _,pl in m_d] and [o for o,_ in m_s]==[o for o,_ in m_d]
    print(f'{name}: marker planes match={mok} (gen {len(m_s)} donor {len(m_d)})')
    if not mok:
        for k,((os_,ps),(od,pd)) in enumerate(zip(m_s,m_d)):
            if ps!=pd or os_!=od: print(f'  plane{k}: gen@{os_} donor@{od} '+('VALS DIFFER' if ps!=pd else 'offset only'))
    # groups: token sequences after the marker region
    mend_s=m_s[-1][0]+5*len(m_s[-1][1]); mend_d=m_d[-1][0]+5*len(m_d[-1][1])
    ts=[(o,v,r) for o,v,r,k in tokseq(S[mend_s:])]
    td=[(o,v,r) for o,v,r,k in tokseq(D[mend_d:])]
    vs=[(v,r) for _,v,r in ts]; vd=[(v,r) for _,v,r in td]
    if vs==vd: print(f'  groups: ALL {len(vs)} (val,run) tokens MATCH')
    else:
        print(f'  groups: gen {len(vs)} tokens, donor {len(vd)}')
        for k in range(min(len(vs),len(vd))):
            if vs[k]!=vd[k]:
                print(f'   first diff tok#{k}: gen {vs[k]} donor {vd[k]} (donor@{td[k][0]+mend_d})')
                print(f'   context gen  {vs[max(0,k-3):k+4]}')
                print(f'   context donor{vd[max(0,k-3):k+4]}')
                break
