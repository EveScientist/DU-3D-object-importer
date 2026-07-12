"""h=3 multi-voxel scan generator — v2 with correct 5-byte declaration layout"""
import math

N1S_REF = 79  # for FG position formula

def n1_sub1(lx):
    ws=153*lx+25; n=9+math.ceil(ws/31)
    if ws%31==0: n-=2
    return n

def major_step_bytes(ny):
    """Step between major groups in bytes."""
    large=9 if ny<=5 else 8
    return (ny-2)*5 + 2*large  # = ny*5+8

def n1_FG(lx, nx, ny):
    n1s=n1_sub1(lx); base=max(n1s,N1S_REF)
    M=nx//2; large=9 if ny<=5 else 8
    steps=([5]*((ny-1)//2)+[large]+[5]*((ny-2)//2))[:ny-1]
    ec=math.ceil(ny/2) if nx%2 else 0
    span=sum(steps[:max(0,ec-1)]); corr=max(0,span-ec)
    if ny%3==1:
        k=(ny-4)//3
        extra=-(abs(ny-8)) if nx%2==0 else (5+(-1)**k)
    else: extra=0
    return base+161+5*M*ny+corr+extra

def fg_cluster_starts(lx, nx, ny):
    n1_fg=n1_FG(lx,nx,ny); pos=[n1_fg]
    for k in range(1,nx+1):
        step=(ny+1)*4+4 if k==1 else 2*ny*4+4
        pos.append(pos[-1]+step)
    return pos

def scan_length(lx, nx, ny):
    n1l=fg_cluster_starts(lx,nx,ny)[-1]+ny*4
    p=52 if nx>=9 else 86; par=0 if nx>=9 else 1
    return (n1l+p)*2+par

def interior_marker(ny):
    return (191-35*ny)%256

def build_scan(lx, nx, ny, nz_extra):
    """
    nz_extra: extra byte value for declarations.
      For cross-boundary (typical): nz_extra = nz_in_cz2 (=nz for blocks at abs_z=64..)
      For isolated: nz_extra = max(1, nz-1)
    """
    n1s=n1_sub1(lx)
    total=scan_length(lx,nx,ny)
    B0=2*n1s+1  # byte of first sub-decl (always ODD)
    ms=major_step_bytes(ny)
    M=nx//2
    ec=math.ceil(ny/2) if nx%2 else 0
    flip=B0+ny*5  # flip from 00ff to ff00 (byte after group 0)
    
    scan=bytearray(total)
    
    # Set backgrounds
    for i in range(total):
        scan[i]=0x00 if i<flip and i%2==0 else \
                0xff if i<flip and i%2==1 else \
                0xff if i>=flip and i%2==0 else \
                0x00
    
    # Write declarations: 5 bytes each at B_grp + 5*j
    def write_decl(B, cv, extra):
        if B+4>=total: return
        scan[B]=cv; scan[B+1]=0x01; scan[B+2]=0x02; scan[B+3]=extra
        # Separator at B+4: write 0x00 only if it's non-background
        pos4=B+4; bg4=(0xff if pos4%2==0 else 0x00) if pos4>=flip else \
                      (0x00 if pos4%2==0 else 0xff)
        if bg4!=0x00:  # bg is 0xff → writing 0x00 is non-bg
            scan[pos4]=0x00
    
    # Major groups
    for k in range(M):
        B_grp=B0+k*ms
        for j in range(ny):
            cv=0xb6 if k==0 and j==0 else (0x34 if j==0 else 0x1a)
            write_decl(B_grp+5*j, cv, nz_extra)
    
    # Extra sub-decls for odd nx
    if nx%2==1:
        B_extra=B0+M*ms
        for j in range(ec):
            cv=0x34 if j==0 else 0x1a
            write_decl(B_extra+5*j, cv, nz_extra)
    
    # Pre-FG marker
    n1_marker=n1_FG(lx,nx,ny)-75
    i_marker=n1_marker*2+1
    if 0<=i_marker<total: scan[i_marker]=0x79  # placeholder
    
    # FG clusters
    clusters=fg_cluster_starts(lx,nx,ny)
    int_m=interior_marker(ny)
    de=nz_extra
    for ci,cn1 in enumerate(clusters):
        is_first=(ci==0); is_last=(ci==len(clusters)-1)
        n_grp=ny+1 if (is_first or is_last) else 2*ny
        mks=[0xc9]+[0x19]*ny if is_first else [int_m]+[0x19]*ny if is_last else \
            [int_m]+([0x19,0x06]*(ny-1))+[0x19]
        for gi in range(n_grp):
            n1g=cn1+gi*4; ig=n1g*2+1
            if ig+7>=total: continue
            scan[ig]=mks[gi] if gi<len(mks) else 0x19
            scan[ig+1]=0x01; scan[ig+2]=de
            scan[ig+3]=0x7e; scan[ig+4]=0x7e; scan[ig+5]=0x7e
            scan[ig+6]=de; scan[ig+7]=0x00
    
    return bytes(scan)

if __name__=="__main__":
    import base64, struct, lz4.block
    def decode_ref(b64):
        raw=base64.b64decode(b64); unc=struct.unpack('<I',raw[4:8])[0]
        d=lz4.block.decompress(raw[12:],uncompressed_size=unc); return bytes(d[64:-40])
    
    b64_9x5="+bYU+6YGAAAAAAAA9wIToLgnBgAAAJ4zgegJAAAAPwQAFyMEABdABAAXIAQALwD/AgCKb7YBAgcAGgUAAAS3AB80HAAAATAADyEA3A8CAEUf5x8Cgp/JAQh+fn4IABkIABQEHgEVEDAAcwB+fn4AAAYIAA8QAB8CgAAPWAD//2kCgAIPCAANBKACDwIARYDnAgAAAMdoaXoG8A0ARGVidWcxAAABpQKwywAAAABoZ0NhcmJvbgIB"
    ref=decode_ref(b64_9x5)
    gen=build_scan(14,9,5,8,7)  # nz_extra=7=max(1,8-1) for isolated block
    
    diffs=[(i,i//2,gen[i],ref[i]) for i in range(min(len(gen),len(ref))) if gen[i]!=ref[i]]
    print(f"9×5×8 lx=14: {len(diffs)} differences out of {len(ref)} bytes")
    
    # Show first 10 diffs categorized
    cats={'declaration':0,'fg_region':0,'pad_region':0,'marker':0,'other':0}
    for pos,n1,g,r in diffs[:50]:
        n1_fg_val=n1_FG(14,9,5)
        if n1<160: cats['declaration']+=1
        elif n1>=n1_fg_val: cats['fg_region']+=1
        elif abs(n1-(n1_fg_val-75))<3: cats['marker']+=1
        elif n1<n1_fg_val: cats['pad_region']+=1
        else: cats['other']+=1
    
    print("Diff categories (first 50):", {k:v for k,v in cats.items() if v>0})
    if diffs:
        print("First 5 diffs:")
        for pos,n1,g,r in diffs[:5]:
            print(f"  byte {pos} (n1={n1}): gen=0x{g:02x}, ref=0x{r:02x}")
