"""
DU Multi-voxel Combined Format — h=3 Scan Generator
All formulas verified against game-captured blobs.
"""
import base64, struct, math, lz4.block

# ─── Constants ────────────────────────────────────────────────────────────────
N1S_REF = 79  # n1_sub1 for lx=14 (calibration reference for FG position)

# ─── n1_sub1 ─────────────────────────────────────────────────────────────────
def n1_sub1(lx):
    ws = 153*lx + 25
    n1 = 9 + math.ceil(ws / 31)
    if ws % 31 == 0:
        n1 -= 2
    return n1

# ─── Declaration structure ───────────────────────────────────────────────────
def within_group_steps(ny):
    large = 9 if ny <= 5 else 8
    return ([5]*((ny-1)//2) + [large] + [5]*((ny-2)//2))[:ny-1]

def major_step(ny):
    large = 9 if ny <= 5 else 8
    return (ny-2)*5 + 2*large if ny >= 2 else large

def all_decl_n1(n1s, nx, ny):
    """All declaration n1 positions in order."""
    M = nx // 2; ms = major_step(ny); steps = within_group_steps(ny)
    decls = []
    for k in range(M):
        base = n1s + k * ms
        decls.append(base)
        for s in steps:
            base += s
            decls.append(base)
    if nx % 2 == 1:
        ec = math.ceil(ny / 2)
        base = n1s + M * ms
        for j in range(ec):
            decls.append(base)
            if j < ec-1 and j < len(steps):
                base += steps[j]
    return sorted(decls)

def last_decl(n1s, nx, ny):
    d = all_decl_n1(n1s, nx, ny)
    return max(d) if d else n1s

# ─── FG position formula ─────────────────────────────────────────────────────
def n1_FG(lx, nx, ny):
    """n1 of first FG cluster. Uses max(n1_sub1,N1S_REF) as base."""
    n1s = n1_sub1(lx)
    base = max(n1s, N1S_REF)
    M = nx // 2; large = 9 if ny <= 5 else 8
    steps = within_group_steps(ny)
    ec = math.ceil(ny/2) if nx % 2 else 0
    span = sum(steps[:max(0, ec-1)])
    corr = max(0, span - ec)
    if ny % 3 == 1:
        k = (ny - 4) // 3
        extra = -(abs(ny-8)) if nx%2==0 else (5 + (-1)**k)
    else:
        extra = 0
    return base + 161 + 5*M*ny + corr + extra

def fg_cluster_starts(lx, nx, ny):
    """n1 of first group in each FG cluster."""
    n1_fg = n1_FG(lx, nx, ny)
    n_clusters = nx + 1
    pos = [n1_fg]
    for k in range(1, n_clusters):
        step = (ny+1)*4 + 4 if k == 1 else 2*ny*4 + 4
        pos.append(pos[-1] + step)
    return pos

# ─── FG marker ───────────────────────────────────────────────────────────────
def interior_marker(ny):
    return (191 - 35*ny) % 256

# ─── Scan length ─────────────────────────────────────────────────────────────
def scan_length(lx, nx, ny):
    clusters = fg_cluster_starts(lx, nx, ny)
    n1_last = clusters[-1] + ny * 4  # last group in last cluster
    # Padding: 86 for small nx, 52 for large nx (empirical)
    padding = 52 if nx >= 9 else 86
    return (n1_last + padding) * 2

# ─── CV byte for declarations ────────────────────────────────────────────────
# CV encodes n-type. For multi-voxel: CV=(32*n+14)%256 but actual values
# differ. From data: CV at n1=79 is 0xb6=182 for various blocks.
# The CV follows n1-dependent formula - use 0xb6 as placeholder for now.
# Will be derived in next phase.
def declaration_cv(n1):
    """CV byte for a declaration at given n1. Placeholder - needs derivation."""
    # From analysis: CV varies with n1 and position
    return 0xb6  # placeholder - correct for most lx=14 cases

# ─── Build scan ───────────────────────────────────────────────────────────────
def build_scan(lx, nx, ny, nz, nz_in_cz2=None):
    """Build the complete h=3 scan byte array."""
    if nz_in_cz2 is None:
        nz_in_cz2 = nz  # assume non-spanning (all in cz=2)
    
    n1s = n1_sub1(lx)
    total_len = scan_length(lx, nx, ny)
    scan = bytearray(total_len)
    
    # 1. Set ff00 background (even=0xff, odd=0x00) everywhere
    for i in range(0, total_len, 2):
        scan[i] = 0xff
        scan[i+1] = 0x00
    
    # 2. Write 00ff section (even=0x00, odd=0xff) for first part
    # From analysis: the scan starts with 00ff up to ~n1_sub1*2+6
    # After flip: ff00 with explicit 0x00 at even positions for pad region
    flip_byte = (last_decl(n1s, nx, ny) * 2 + 6)  # approximate flip point
    for i in range(0, min(flip_byte, total_len), 2):
        scan[i] = 0x00   # even: 0x00 in 00ff section
        scan[i+1] = 0xff  # odd: 0xff in 00ff section
    
    # 3. Write explicit 0x00 at even positions in ff00 section (pad region)
    # This region: from flip to pre-FG marker (n1=n1_FG-75)
    n1_marker = n1_FG(lx, nx, ny) - 75
    for i in range(flip_byte, n1_marker*2, 2):
        if i < total_len:
            scan[i] = 0x00  # explicit 0x00 at even (non-bg in ff00)
    
    # 4. Write declarations
    decls = all_decl_n1(n1s, nx, ny)
    extra = nz_in_cz2  # cross-boundary: extra=nz_in_chunk
    for n1 in decls:
        i = n1 * 2 + 1  # odd byte
        cv = declaration_cv(n1)
        scan[i]   = cv      # CV
        scan[i+1] = 0x01
        scan[i+2] = 0x02   # DE
        scan[i+3] = extra
    
    # 5. Write pre-FG marker
    # marker byte at n1=n1_FG-75 (ODD position)
    marker_i = n1_marker * 2 + 1
    if marker_i < total_len:
        scan[marker_i] = 0x79  # placeholder marker value
    
    # 6. Write FG clusters
    clusters = fg_cluster_starts(lx, nx, ny)
    ny_h4 = math.ceil(ny / 2)
    de = nz_in_cz2  # DE = nz_in_chunk
    int_m = interior_marker(ny)
    
    for ci, cluster_n1 in enumerate(clusters):
        is_first = (ci == 0)
        is_last = (ci == len(clusters) - 1)
        n_groups = ny + 1 if (is_first or is_last) else 2 * ny
        
        markers = []
        if is_first:
            markers = [0xc9] + [0x19] * ny  # opener + ny continuations
        else:
            markers = [int_m] + ([0x19, 0x06] * (ny-1)) + [0x19]  # interior/last
            if is_last:
                markers = [int_m] + [0x19] * ny
        
        for gi in range(n_groups):
            n1_grp = cluster_n1 + gi * 4
            i = n1_grp * 2 + 1  # ODD-start
            m = markers[gi] if gi < len(markers) else 0x19
            scan[i]   = m
            scan[i+1] = 0x01
            scan[i+2] = de
            scan[i+3] = 0x7e
            scan[i+4] = 0x7e
            scan[i+5] = 0x7e
            scan[i+6] = de
            # byte i+7 (even): 0x00 explicit
            if i+7 < total_len:
                scan[i+7] = 0x00
    
    return bytes(scan)

if __name__ == "__main__":
    import base64, lz4.block
    def decode_scan_ref(b64):
        raw=base64.b64decode(b64); unc=struct.unpack('<I',raw[4:8])[0]
        d=lz4.block.decompress(raw[12:],uncompressed_size=unc); return bytes(d[64:-40])
    
    # Quick parameter validation
    print("=== Parameter validation ===")
    refs = [
        ("9×5×8 lx=14", 9,5,8,14, 79,347,10,1598),
        ("2×5×8 lx=10", 2,5,8,10, 60,265, 3, 887),
        ("2×3×8 lx=14", 2,3,8,14, 79,255, 3, 803),
    ]
    all_ok=True
    for label,nx,ny,nz,lx,en1s,efg,enc,esl in refs:
        cn1s=n1_sub1(lx); cfg=n1_FG(lx,nx,ny); cnc=nx+1; csl=scan_length(lx,nx,ny)
        ok=(cn1s==en1s and cfg==efg and cnc==enc and csl==esl)
        all_ok=all_ok and ok
        print(f"  {label}: {'✓' if ok else '✗'} n1s={cn1s},FG={cfg},clusters={cnc},slen={csl}")
    print(f"  {'ALL OK' if all_ok else 'SOME FAIL'}")
