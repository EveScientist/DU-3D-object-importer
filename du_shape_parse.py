import json, base64, lz4.block
def chunks(p):
    bp=json.load(open(p)); out={}
    for e in bp['VoxelData']:
        if e['h']!=3: continue
        raw=base64.b64decode(e['records']['voxel']['data']['$binary'])
        size=int.from_bytes(raw[4:8],'little')
        out[(e['x']['$numberLong'],e['y']['$numberLong'],e['z']['$numberLong'])]=bytes(lz4.block.decompress(raw[12:],uncompressed_size=size)[64:-40])
    return out
def group_regions(B):
    def bg(i): return i+1<len(B) and ((B[i]==0 and B[i+1]==0xff) or (B[i]==0xff and B[i+1]==0))
    i=0; regs=[]
    while i<len(B):
        if bg(i): i+=2; continue
        st=i
        while i<len(B) and not bg(i): i+=1
        regs.append((st,i))
    return [r for r in regs if r[1]-r[0]>100]
def groups(B,st,en):
    g=[]; i=st
    while i<en:
        if i+1<en and B[i+1]==1:
            run=B[i+2]
            if i+8<=en and B[i+3]==0x7e and B[i+4]==0x7e and B[i+5]==0x7e and B[i+6]==run and B[i+7]==0:
                g.append(dict(val=B[i],run=run,off=i,xs=[0],ys=[0],zs=[0])); i+=8; continue
            xs=[B[i+3+4*k]-126 for k in range(run+1)]; ys=[B[i+4+4*k]-126 for k in range(run+1)]; zs=[B[i+5+4*k]-126 for k in range(run+1)]
            g.append(dict(val=B[i],run=run,off=i,xs=xs,ys=ys,zs=zs)); i+=4+4*(run+1); continue
        i+=1
    return g
def is_wall(gr): z=gr['zs']; return len(z)>=2 and abs(z[0]+z[-1])<=6
def plane_cols(g):
    a=0;b=len(g)
    while a<b and is_wall(g[a]): a+=1
    while b>a and is_wall(g[b-1]): b-=1
    body=g[a:b]
    walls_lo=g[:a]; walls_hi=g[b:]
    pairs=[]
    if len(body)%2==0:
        for p in range(len(body)//2): pairs.append((body[2*p],body[2*p+1]))
    return walls_lo,pairs,walls_hi


# --- corrected curved-shape column parse (2026-07-07 breakthrough) ---
def is_wall(gr):
    """A wall/corner group has z-SYMMETRIC displacement (|z[0]+z[-1]|<=6);
    a Bottom/Top cap is one-sided. Requires groups() to attach 'zs'."""
    z = gr.get('zs', [0])
    return len(z) >= 2 and abs(z[0] + z[-1]) <= 6


def plane_cols(g):
    """Strip leading/trailing z-symmetric wall/corner groups; pair the rest as
    (Bottom, Top). Returns (walls_lo, [(bottom,top),...], walls_hi).
    Column height h = Top_val + 2 (= 33 - Bottom_val - Bottom_run). Validated on
    all 21 planes of 3191 (single-chunk solid sphere)."""
    a = 0
    b = len(g)
    while a < b and is_wall(g[a]):
        a += 1
    while b > a and is_wall(g[b - 1]):
        b -= 1
    body = g[a:b]
    pairs = []
    if len(body) % 2 == 0:
        for p in range(len(body) // 2):
            pairs.append((body[2 * p], body[2 * p + 1]))
    return g[:a], pairs, g[b:]
